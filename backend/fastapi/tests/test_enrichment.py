import importlib.util
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.enrich.asr import transcribe
from ai.enrich.common import CATALOG, read, write
from ai.enrich.export import VALIDATOR, enrich
from ai.enrich import inventory as media_inventory
from ai.enrich.inventory import discover


def test_local_media_copy_fallback_publishes_only_the_mirror(tmp_path, monkeypatch):
    source = tmp_path / "outside.mp4"
    source.write_bytes(b"local video")
    row = {"episode_id": "ep1", "duration_ms": 3_900_000, "size_bytes": source.stat().st_size,
           "local_path": str(source)}
    def cross_volume(*args):
        raise OSError("cross-volume link unavailable")
    monkeypatch.setattr(media_inventory.os, "link", cross_volume)
    monkeypatch.setattr(media_inventory, "probe", lambda path: 3_900_000)
    result = media_inventory.stage(row, None, tmp_path)
    mirrored = tmp_path / "media-mirror" / "ep1" / "media.mp4"
    assert Path(result["source"]) == mirrored
    assert mirrored.read_bytes() == source.read_bytes()


def test_inventory_requires_matching_drive_identity_and_spreads_across_seasons():
    catalog = read(CATALOG)
    remote = [{"ID": asset["storage"]["drive_file_id"],
               "Path": asset["storage"]["relative_path"].removeprefix("VideoDieppie/"),
               "Size": asset["size_bytes"]} for asset in catalog["media_assets"]
              if asset["storage"]["drive_file_id"]]
    inventory = discover(catalog, remote_files=remote)
    assert len(inventory["pilot"]) == 5
    assert len({row["season_id"] for row in inventory["pilot"]}) == 4
    assert all(600000 <= row["duration_ms"] <= 2400000 for row in inventory["pilot"])
    ids = [row["episode_id"] for row in reversed(inventory["pilot"])]
    assert [row["episode_id"] for row in discover(catalog, remote_files=remote, pilot_ids=ids)["pilot"]] == ids
    altered = [{**row, "ID": f"other-{index}"} for index, row in enumerate(remote)]
    assert discover(catalog, remote_files=altered)["pilot"] == []


def test_drive_resume_checks_media_identity_and_final_md5(tmp_path, monkeypatch):
    data = b"firstsecond"
    checksum = hashlib.md5(data).hexdigest()
    row = {"remote_path": "season/movie.mp4", "remote_id": "drive-id", "size_bytes": len(data)}
    requests = []

    def read_remote(*args):
        requests.append(args)
        if args[0] == "lsjson":
            return json.dumps({"ID": "drive-id", "Size": len(data), "Hashes": {"md5": checksum}}).encode()
        offset, count = int(args[3]), int(args[5])
        return data[offset:offset + count]

    monkeypatch.setattr(media_inventory, "rclone_read", read_remote)
    existing = tmp_path / f"media.{checksum}.resume"
    existing.write_bytes(data[:5])
    result = media_inventory.download(row, "gdrive:pilot", tmp_path / "media.mp4", 4)
    assert result.read_bytes() == data
    assert [int(args[3]) for args in requests if args[0] == "cat"] == [5, 9]


def test_asr_cues_use_source_ms_and_keep_vad_and_hotwords():
    class Encoder:
        def transcribe(self, path, **kwargs):
            assert path == "test.mp4"
            assert kwargs["vad_filter"] and kwargs["hotwords"] == "Jadoo"
            return iter([SimpleNamespace(start=1.125, end=2.75, text=" lời thoại "),
                         SimpleNamespace(start=3.0, end=4.0, text=" ")]), None
    row = {"source": "test.mp4", "episode_id": "ep", "media_asset_id": "asset", "probed_duration_ms": 2500}
    result = transcribe(Encoder(), row, "Jadoo", "vi")
    assert result["cues"] == [{"id": "ep.cue.00001", "start_ms": 1125, "end_ms": 2500, "text": "lời thoại",
                               "speaker_character_ids": [], "confidence": None}]


@pytest.mark.parametrize("dialogue_only", [True, False])
def test_export_preserves_unselected_episodes_and_passes_schema(tmp_path, dialogue_only):
    payload = read(CATALOG)
    assets = {a["coverage"][0]["episode_id"]: a for a in payload["media_assets"]
              if a["role"] == "feature" and a["coverage"]}
    rows = [{"episode_id": ep["id"], "media_asset_id": assets[ep["id"]]["id"]}
            for ep in payload["episodes"] if ep["id"] in assets][:5]
    initial = [row["synopsis"] for row in payload["episodes"]]
    timestamp = "2026-11-10T00:00:00+00:00"
    for row in rows:
        directory = tmp_path / row["episode_id"]
        cue = {"id": row["episode_id"] + ".cue.00001", "start_ms": 0, "end_ms": 1000,
               "text": "Dữ liệu kiểm thử.", "speaker_character_ids": [], "confidence": None}
        write(directory / "asr.json", {**row, "model": "test", "revision": "v1",
              "language": "vi", "created_at": timestamp, "cues": [cue]})
        if not dialogue_only:
            scene = {"scene_id": row["episode_id"] + ".scene.0001", "start_ms": 0, "end_ms": 2000}
            write(directory / "scenes.json", {"scenes": [scene]})
            write(directory / "captions.json", {"model": "test", "prompt_version": "v2", "created_at": timestamp,
                  "scenes": [{**scene, "created_at": timestamp, "title": "Cảnh kiểm thử", "summary": "Nội dung kiểm thử.",
                              "visual_description": "Hình kiểm thử.", "character_ids": [], "keywords": [],
                              "themes": [], "visual_tags": [], "sound_events": []}]})
            write(directory / "synopsis.json", {"model": "test", "prompt_version": "v3", "created_at": timestamp,
                  "synopsis": "Tóm tắt kiểm thử.", "plot_facts": ["Sự kiện kiểm thử."]})
    export = enrich(payload, rows, tmp_path, dialogue_only)
    assert len(export["text_tracks"]) == 5
    assert len(export["scenes"]) == (0 if dialogue_only else 5)
    selected = {row["episode_id"] for row in rows}
    for index, episode in enumerate(export["episodes"]):
        expected = initial[index] if dialogue_only or episode["id"] not in selected else "Tóm tắt kiểm thử."
        assert episode["synopsis"] == expected
    assert all(track["provenance"]["tool_revision"] == "v1" for track in export["text_tracks"])
    assert all(scene["provenance"]["annotated_at"] == timestamp and scene["transcript_cue_ids"] for scene in export["scenes"])
    spec = importlib.util.spec_from_file_location("catalog_validator", VALIDATOR)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    assert not validator.validate(export)


def test_mirror_adopts_existing_media_and_retains_identity(tmp_path, monkeypatch):
    artifacts = tmp_path / "artifacts"
    old = artifacts / "ep" / "media.mp4"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"video")
    monkeypatch.setattr(media_inventory, "probe", lambda path: 3900000)
    row = {"episode_id": "ep", "size_bytes": 5, "duration_ms": 3900000, "remote_path": "x.mp4"}
    result = media_inventory.stage(row, "remote:", artifacts)
    assert Path(result["source"]).read_bytes() == b"video"
    assert Path(result["source"]).is_relative_to(artifacts / "media-mirror")
    assert old.samefile(result["source"])


def test_rclone_quota_error_retains_original_message(monkeypatch):
    monkeypatch.setattr(media_inventory.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stderr=b"403 quotaExceeded: exact reason", stdout=b""))
    with pytest.raises(ValueError, match="403 quotaExceeded: exact reason"):
        media_inventory.rclone_read("lsjson", "remote:")
