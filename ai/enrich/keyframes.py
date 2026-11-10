import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

from .common import digest, episodes, now, pilot_options, read, run, write


VERSION = "dippie-keyframes-v1"
FRAME_INTERVAL_MS = 1000
HASH_DISTANCE = 4


def perceptual_hash(image):
    import cv2
    import numpy as np

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    low = cv2.dct(small)[:8, :8].reshape(-1)[1:]
    median = float(np.median(low))
    value = 0
    for coefficient in low:
        value = (value << 1) | int(coefficient > median)
    return value


def is_duplicate(value, retained):
    return any((value ^ previous).bit_count() <= HASH_DISTANCE for previous in retained)


def extract_episode(row, directory):
    import cv2
    import numpy as np

    source = Path(row["source"]).resolve(strict=True)
    stat = source.stat()
    duration = row["probed_duration_ms"]
    if not source.is_file() or not isinstance(duration, int) or duration <= 0:
        raise ValueError("A staged video and positive probed duration are required")
    signature = digest([VERSION, row["media_asset_id"], duration, str(source), stat.st_size, stat.st_mtime_ns])
    manifest = directory / "keyframes.json"
    output = (directory / "frames" / signature[:16]).resolve()
    if manifest.is_file():
        cached = read(manifest)
        if cached.get("input_hash") == signature and cached.get("frames") and cached.get("samples"):
            paths = [Path(frame["path"]).resolve() for frame in cached["frames"]]
            if all(path.is_relative_to(output) and path.is_file() and path.stat().st_size for path in paths):
                return cached, True
    if not output.is_relative_to(directory.resolve()):
        raise ValueError("Frame output must remain inside the episode artifact directory")
    directory.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(2)
    started = time.perf_counter()
    samples, frames, retained = [], [], []
    with tempfile.TemporaryDirectory(prefix="keyframes-", dir=directory) as scratch:
        run("ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror", "-threads", "2",
            "-filter_threads", "2", "-i", source, "-map", "0:v:0", "-an", "-sn", "-dn", "-vf",
            r"fps=1:start_time=0,scale=w=min(640\,iw):h=-2", "-threads", "2", "-q:v", "3",
            "-start_number", "0", Path(scratch) / "%07d.jpg")
        for frame_path in sorted(Path(scratch).glob("*.jpg")):
            source_ms = int(frame_path.stem) * FRAME_INTERVAL_MS
            if source_ms >= duration:
                continue
            image = cv2.imdecode(np.fromfile(frame_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"Could not decode extracted frame at {source_ms} ms")
            value = perceptual_hash(image)
            fingerprint = f"{value:016x}"
            samples.append({"source_ms": source_ms, "phash": fingerprint})
            if is_duplicate(value, retained):
                continue
            retained.append(value)
            target = output / frame_path.name
            os.replace(frame_path, target)
            frames.append({"episode_id": row["episode_id"], "media_asset_id": row["media_asset_id"],
                           "source_ms": source_ms, "path": str(target), "phash": fingerprint})
    expected = math.ceil(duration / FRAME_INTERVAL_MS)
    if not frames or len(samples) < expected - 2:
        raise ValueError(f"Video decoding ended early ({len(samples)} of about {expected} samples)")
    result = {"episode_id": row["episode_id"], "media_asset_id": row["media_asset_id"],
              "version": VERSION, "created_at": now(), "device": "cpu", "input_hash": signature,
              "duration_ms": duration, "sample_count": len(samples), "frames": frames, "samples": samples,
              "elapsed_seconds": time.perf_counter() - started}
    write(manifest, result)
    return result, False


def main():
    parser = argparse.ArgumentParser(description="Extract 1 fps CPU keyframes and deduplicate them by perceptual hash.")
    pilot_options(parser)
    args = parser.parse_args()
    try:
        for row in episodes(args.inventory, args.episode):
            result, cached = extract_episode(row, args.artifacts / row["episode_id"])
            print(json.dumps({"episode_id": row["episode_id"], "sample_count": result["sample_count"],
                              "frame_count": len(result["frames"]), "cached": cached}), flush=True)
    except subprocess.CalledProcessError as exc:
        parser.error((exc.stderr or "FFmpeg failed").strip())
    except (KeyError, OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
