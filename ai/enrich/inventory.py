import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections import defaultdict
from pathlib import Path, PurePosixPath

from .common import ARTIFACTS, CATALOG, probe, read, write


RCLONE_CONFIG = ()

RCLONE_LIMITS = ("--contimeout", "12s", "--timeout", "35s", "--tpslimit", "1", "--tpslimit-burst", "1",
                 "--retries", "1", "--low-level-retries", "1", "--transfers", "1", "--checkers", "1")


def safe_relative(value):
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts or any(":" in part for part in path.parts):
        raise ValueError("Invalid media path")
    return path


def discover(catalog, local_root=None, remote_files=None, pilot_ids=None):
    groups = defaultdict(list)
    by_id = {row.get("ID"): row for row in remote_files or [] if row.get("ID")}
    by_path = {row["Path"]: row for row in remote_files or []}
    assets = defaultdict(list)
    for asset in catalog["media_assets"]:
        if (asset.get("content_type"), asset.get("role"), asset.get("access_policy"), asset.get("enabled")) != ("video", "feature", "public", True):
            continue
        if asset.get("record", {}).get("status") != "ready":
            continue
        for coverage in asset.get("coverage", []):
            if coverage.get("scope") == "full_episode" and coverage.get("source_in_ms") == 0 and coverage.get("episode_in_ms") == 0:
                assets[coverage["episode_id"]].append(asset)
    missing, anomalies = [], []
    found = 0
    for episode in catalog["episodes"]:
        episode_id = episode["id"]
        duration = episode.get("duration_ms")
        regular = episode.get("kind") == "regular" and isinstance(duration, int) and duration >= 600_000
        if not regular:
            anomalies.append({"episode_id": episode_id, "kind": episode.get("kind"), "duration_ms": duration})
        resolved = None
        for asset in assets[episode_id]:
            storage = asset["storage"]
            relative = safe_relative(storage["relative_path"])
            size = asset.get("size_bytes")
            if local_root:
                path = (local_root / str(relative)).resolve()
                if not path.is_relative_to(local_root):
                    continue
                if not path.is_file() and relative.parts[0] == "VideoDieppie":
                    path = (local_root / str(PurePosixPath(*relative.parts[1:]))).resolve()
                if path.is_relative_to(local_root) and path.is_file() and path.stat().st_size == size:
                    resolved = {"local_path": str(path), "size_bytes": size}
            else:
                row = by_id.get(storage.get("drive_file_id")) or by_path.get(relative.as_posix().removeprefix("VideoDieppie/"))
                if row and not row.get("IsDir") and row["Size"] == size and (not storage.get("drive_file_id") or row.get("ID") == storage["drive_file_id"]):
                    resolved = {"remote_path": safe_relative(row["Path"]).as_posix(), "size_bytes": size,
                                "remote_id": row.get("ID"), "remote_modified": row.get("ModTime")}
            if resolved:
                found += 1
                if regular:
                    groups[episode["season_id"]].append({"episode_id": episode_id, "season_id": episode["season_id"],
                        "number": episode["number"], "media_asset_id": asset["id"], "duration_ms": duration, **resolved})
                break
        if not resolved:
            missing.append(episode_id)
    ordered = lambda row: (row["size_bytes"], row["duration_ms"], row["episode_id"])
    pilot = [min(short, key=ordered) for _, group in sorted(groups.items()) if (short := [row for row in group if row["duration_ms"] <= 2_400_000])][:5]
    selected = {row["episode_id"] for row in pilot}
    remaining = [row for group in groups.values() for row in group if row["episode_id"] not in selected and row["duration_ms"] <= 2_400_000]
    pilot.extend(sorted(remaining, key=ordered)[:5 - len(pilot)])
    if pilot_ids is not None:
        candidates = {row["episode_id"]: row for group in groups.values() for row in group}
        if len(pilot_ids) != 5 or len(set(pilot_ids)) != 5 or not set(pilot_ids) <= candidates.keys():
            raise ValueError("Select five distinct, eligible episodes with resolved media")
        pilot = [candidates[episode_id] for episode_id in pilot_ids]
    return {"total_episodes": len(catalog["episodes"]), "resolved_episodes": found, "missing_episodes": missing,
            "duration_or_kind_anomalies": anomalies, "pilot": pilot}


def rclone_read(*arguments):
    for attempt in range(3):
        try:
            result = subprocess.run(["rclone", *arguments, *RCLONE_CONFIG, *RCLONE_LIMITS], capture_output=True, timeout=85)
        except subprocess.TimeoutExpired:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise ValueError("rclone timed out. Completed bytes remain available for a later resume.") from None
        if result.returncode == 0:
            return result.stdout
        message = result.stderr.decode("utf-8", errors="replace").strip()
        folded = message.casefold()
        if any(marker in folded for marker in ("rate limit", "ratelimit", "quota", "status 429", "error 429")):
            raise ValueError(message or "rclone reported a Drive quota or rate limit")
        if attempt < 2 and any(marker in folded for marker in ("timeout", "timed out", "connection reset", "status 500", "status 502", "status 503", "status 504")):
            time.sleep(2 ** attempt)
            continue
        raise ValueError(message or "rclone failed to read the media file")


def download(row, remote, destination, chunk_bytes):
    source = f"{remote.rstrip('/')}/{safe_relative(row['remote_path']).as_posix()}"
    metadata = json.loads(rclone_read("lsjson", source, "--stat", "--hash-type", "MD5"))
    if (metadata.get("IsDir") or metadata.get("Size") != row["size_bytes"]
            or row.get("remote_id") and metadata.get("ID") != row["remote_id"]
            or row.get("remote_modified") and metadata.get("ModTime") != row["remote_modified"]):
        raise ValueError("Remote media identity, size or modification time changed since inventory")
    hashes = {key.lower(): value for key, value in metadata.get("Hashes", {}).items()}
    expected = hashes.get("md5", "").lower()
    if not re.fullmatch(r"[0-9a-f]{32}", expected):
        raise ValueError("Drive did not provide an MD5 checksum for resumable staging")
    partial = destination.with_name(f"{destination.stem}.{expected}.resume")
    offset = partial.stat().st_size if partial.is_file() else 0
    if offset > row["size_bytes"]:
        raise ValueError(f"Resume file has an unexpected size: {partial.name}")
    while offset < row["size_bytes"]:
        count = min(chunk_bytes, row["size_bytes"] - offset)
        chunk = rclone_read("cat", source, "--offset", str(offset), "--count", str(count))
        if len(chunk) != count:
            raise ValueError(f"rclone returned {len(chunk)} bytes for a {count}-byte range at {offset}")
        with partial.open("ab") as stream:
            stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        offset += count
    with partial.open("rb") as stream:
        actual = hashlib.file_digest(stream, "md5").hexdigest()
    if actual != expected:
        raise ValueError(f"Resumed file failed the Drive MD5 checksum: {partial.name}")
    return partial


def stage(row, remote, artifacts, chunk_bytes=8 * 1024 * 1024):
    root = (artifacts / "media-mirror").resolve()
    folder = (root / row["episode_id"]).resolve()
    if folder.parent != root:
        raise ValueError("Episode staging folder must be directly inside the mirror root")
    destination = folder / "media.mp4"
    folder.mkdir(parents=True, exist_ok=True)
    old = Path(row.get("local_path") or row.get("source") or artifacts / row["episode_id"] / "media.mp4")
    if destination.is_symlink() or (destination.exists() and
            (not destination.is_file() or destination.stat().st_size != row["size_bytes"])):
        raise ValueError(f"Existing staged media has an unexpected size for {row['episode_id']}")
    try:
        if destination.exists():
            path = destination
        elif old.is_file() and old.stat().st_size == row["size_bytes"]:
            duration = probe(old)
            if abs(duration - row["duration_ms"]) > 2_000 or duration < 600_000:
                raise ValueError(f"Unexpected measured duration for {row['episode_id']}: {duration} ms")
            try:
                os.link(old, destination)
                path = destination
            except OSError:
                with tempfile.NamedTemporaryFile(dir=folder, suffix=".mp4", delete=False) as stream:
                    temporary = Path(stream.name)
                try:
                    shutil.copy2(old, temporary)
                    if temporary.stat().st_size != row["size_bytes"] or probe(temporary) != duration:
                        raise ValueError("Local source size or duration changed during mirror copy")
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
                path = destination
        else:
            path = download(row, remote, destination, chunk_bytes)
        duration = probe(path)
        if abs(duration - row["duration_ms"]) > 2_000 or duration < 600_000:
            raise ValueError(f"Unexpected measured duration for {row['episode_id']}: {duration} ms")
        if path != destination:
            os.replace(path, destination)
        return {**row, "source": str(destination), "probed_duration_ms": duration}
    except (ValueError, OSError) as error:
        raise ValueError(f"Could not stage {row['episode_id']}: {error}") from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--artifacts", type=Path, default=ARTIFACTS)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--media-root", type=Path)
    source.add_argument("--rclone-root")
    parser.add_argument("--remote-list", type=Path)
    parser.add_argument("--rclone-config", type=Path)
    parser.add_argument("--rclone-chunk-mib", type=int, choices=range(1, 33), default=8)
    parser.add_argument("--pilot-episode", action="append")
    parser.add_argument("--stage", action="store_true")
    args = parser.parse_args()
    global RCLONE_CONFIG
    RCLONE_CONFIG = ("--config", str(args.rclone_config)) if args.rclone_config else ()
    if args.remote_list and not args.rclone_root:
        parser.error("--remote-list requires --rclone-root")
    try:
        root = args.media_root.resolve(strict=True) if args.media_root else None
        files = None if root else read(args.remote_list) if args.remote_list else json.loads(rclone_read("lsjson", args.rclone_root, "--recursive", "--files-only"))
        result = discover(read(args.catalog), root, files, args.pilot_episode)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    report = args.artifacts / "inventory.json"
    write(report, result)
    if len(result["pilot"]) != 5:
        parser.error(f"Five eligible media files could not be resolved. See {report}")
    if args.stage:
        def stage_order(pair):
            row = pair[1]
            return (not ("local_path" in row or (args.artifacts / row["episode_id"] / "media.mp4").is_file() or (args.artifacts / "media-mirror" / row["episode_id"] / "media.mp4").is_file()), row["size_bytes"])

        for index, row in sorted(enumerate(result["pilot"]), key=stage_order):
            try:
                result["pilot"][index] = stage(row, args.rclone_root, args.artifacts, args.rclone_chunk_mib * 1024 * 1024)
            except (OSError, ValueError, subprocess.CalledProcessError) as error:
                parser.error(f"{error}. Staging progress is saved in {report}")
            write(report, result)
    print(json.dumps({"inventory": str(report), "resolved": result["resolved_episodes"], "missing": len(result["missing_episodes"]),
                      "anomalies": len(result["duration_or_kind_anomalies"]), "pilot": [row["episode_id"] for row in result["pilot"]]}))


if __name__ == "__main__":
    main()
