import json
import sys

import httpx
import pytest

from ai.enrich import caption
from ai.enrich.caption import RequestBudget, caption_jobs, enforce_budget, reply
from ai.enrich.common import write
from ai.enrich.summarize import summary_job


def pilot_inputs(directory, frame_count=7):
    row = {"episode_id": "ep-1", "media_asset_id": "asset-1"}
    scenes = [{"scene_id": "scene-1", "start_ms": 0, "end_ms": 30_000}]
    write(directory / "scenes.json", {"scenes": scenes})
    frames = []
    for i in range(frame_count):
        image = directory / f"frame-{i}.jpg"
        image.write_bytes(b"\xff\xd8\xff" + bytes([i]))
        frames.append({**row, "source_ms": i * 4000, "path": str(image)})
    write(directory / "keyframes.json", {"frames": frames})
    write(directory / "asr.json", {"cues": [
        {"id": "cue-1", "start_ms": 500, "end_ms": 1500, "text": "Jadoo ơi"},
        {"id": "cue-2", "start_ms": 30_000, "end_ms": 32_000, "text": "Outside scene"},
    ]})
    return row


def test_caption_plans_distinct_frames_and_only_overlapping_cues(tmp_path):
    row = pilot_inputs(tmp_path)
    jobs, skipped = caption_jobs(tmp_path, row, {"jadoo": "Jadoo"}, "test-model", "https://teacher.invalid/v1")
    assert len(jobs) == 1 and not skipped
    scene, job = jobs[0]
    assert scene["scene_id"] == "scene-1"
    assert len(job.images) == 6
    assert json.loads(job.content)["cues"] == [{"id": "cue-1", "start_ms": 500, "end_ms": 1500, "text": "Jadoo ơi"}]
    assert job.plan()["image_count"] == 6 and not job.plan()["cached"]
    assert "data:image" not in json.dumps(job.plan())
    job.images[0].path.write_bytes(b"\xff\xd8\xffchanged")
    updated, _ = caption_jobs(tmp_path, row, {"jadoo": "Jadoo"}, "test-model", "https://teacher.invalid/v1")
    assert updated[0][1].input_hash != job.input_hash


def test_caption_skips_a_scene_with_too_few_unique_images(tmp_path):
    row = pilot_inputs(tmp_path, 3)
    jobs, skipped = caption_jobs(tmp_path, row, {"jadoo": "Jadoo"}, None, None)
    assert jobs == []
    assert skipped == [{"scene_id": "scene-1", "available_images": 3, "reason": "fewer_than_four_unique_frames"}]


def test_teacher_cap_and_cache_avoid_duplicate_requests(tmp_path):
    row = pilot_inputs(tmp_path, 4)
    [(scene, job)], _ = caption_jobs(tmp_path, row, {"jadoo": "Jadoo"}, "test-model", "https://teacher.invalid/v1")
    calls = []
    def endpoint(request):
        calls.append(request)
        body = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert len([part for part in body["messages"][1]["content"] if part["type"] == "image_url"]) == 4
        payload = {"title": "Chào bạn", "summary": "Jadoo xuất hiện", "visual_description": "Jadoo đứng trước cửa",
                   "character_ids": ["hallucinated"], "visual_tags": [], "sound_events": [], "keywords": [], "themes": []}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})

    with pytest.raises(ValueError, match="exceed"):
        enforce_budget([job], 0)
    assert not calls
    enforce_budget([job], 1)
    budget = RequestBudget(1)
    with httpx.Client(transport=httpx.MockTransport(endpoint)) as client:
        for _ in range(2):
            with pytest.raises(ValueError, match="schema"):
                reply(job, client, "test-key", budget)
        job.cache.unlink()
        with pytest.raises(ValueError, match="max-requests"):
            reply(job, client, "test-key", budget)
    assert len(calls) == 1
    assert budget.sent == 1


def test_summarize_builds_text_only_request_from_scene_captions(tmp_path):
    assert summary_job(tmp_path, {"episode_id": "ep-1"}, "test-model", "https://teacher.invalid/v1") is None
    write(tmp_path / "captions.json", {"scenes": [{"scene_id": "scene-1", "start_ms": 0, "end_ms": 30_000,
          "title": "Chào bạn", "summary": "Jadoo xuất hiện", "visual_description": "Jadoo đứng trước cửa"}]})
    job = summary_job(tmp_path, {"episode_id": "ep-1"}, "test-model", "https://teacher.invalid/v1")
    assert job.plan()["image_count"] == 0
    assert json.loads(job.content)["scenes"][0]["summary"] == "Jadoo xuất hiện"


def test_caption_cli_dry_run_never_initializes_network_client(tmp_path, monkeypatch, capsys):
    row = pilot_inputs(tmp_path / "ep-1", 4)
    inventory = tmp_path / "inventory.json"
    catalog = tmp_path / "catalog.json"
    write(inventory, {"pilot": [row, *[{"episode_id": f"ep-{number}"} for number in range(2, 6)]]})
    write(catalog, {"episodes": [{"id": "ep-1", "series_id": "show"}],
                    "characters": [{"id": "jadoo", "name": "Jadoo", "series_ids": ["show"]}]})
    monkeypatch.setenv("TEACHER_MODEL", "test-model")
    monkeypatch.setenv("TEACHER_BASE_URL", "https://teacher.invalid/v1")
    monkeypatch.setenv("TEACHER_API_KEY", "do-not-print")
    monkeypatch.setattr(sys, "argv", ["caption", "--inventory", str(inventory), "--artifacts", str(tmp_path),
                                   "--catalog", str(catalog), "--episode", "ep-1", "--dry-run"])
    def forbidden(*args, **kwargs):
        pytest.fail("Dry run created a network client")
    monkeypatch.setattr(caption.httpx, "Client", forbidden)
    caption.main()
    report = json.loads(capsys.readouterr().out)
    assert report["requests"] == 1 and report["images"] == 4 and report["external_requests"] == 0
    plan = (tmp_path / "ep-1/caption_plan.json").read_text(encoding="utf-8")
    assert "do-not-print" not in plan and "data:image" not in plan
    assert not (tmp_path / "ep-1/captions.json").exists()
