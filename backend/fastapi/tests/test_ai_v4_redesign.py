import asyncio
import json
import sys
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend" / "fastapi") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend" / "fastapi"))

from ai.enrich.pipeline import run_pipeline
from main import create_app
from services.chat import ChatService, build_follow_ups
from services.frame_search import FrameSearchIndex, compute_phash
from services.llm_client import LLMClient
from services.model_registry import ModelRegistry
from services.pilot_catalog import evidence_for_results
from services.text_index import TextIndex


def test_field_weighted_bm25_and_bigram_phrase_ranking(tmp_path):
    catalog = [
        {
            "id": "ep_desc_only",
            "title": "Buổi sáng bình thường",
            "item_type": "episode",
            "episode_number": 1,
            "description": "Trong tập này có nhắc thoáng qua từ thám tử và từ nhí ở hai câu hoàn toàn tách biệt nhau.",
        },
        {
            "id": "ep_title_bigram",
            "title": "Thám tử nhí Jadoo",
            "item_type": "episode",
            "episode_number": 2,
            "characters": ["Jadoo", "Mimi"],
            "description": "Một vụ án thú vị trong lớp học.",
        },
    ]
    index = TextIndex.build(catalog, cache_dir=tmp_path)
    results = index.search("thám tử nhí")
    assert results[0]["id"] == "ep_title_bigram"
    assert results[0]["score"] > results[1]["score"]


def test_hybrid_affinity_recommender_ranks_shared_themes_and_characters_higher(tmp_path):
    app = create_app(
        sync_secret="test-token",
        sync_path=tmp_path / "state.json",
        cache_dir=tmp_path / "cache",
        model_mode="light",
        load_default=False,
    )
    payload = {
        "schema_version": "dippie.catalog.v1",
        "genres": [{"id": "comedy", "labels": [{"lang": "vi", "text": "Hài hước"}]}],
        "characters": [
            {"id": "jadoo", "name": "Jadoo"},
            {"id": "mimi", "name": "Mimi"},
            {"id": "other", "name": "Người lạ"},
        ],
        "series": [{"id": "s1", "title": "Xin chào Jadoo", "genre_ids": ["comedy"]}],
        "seasons": [{"id": "sea1", "series_id": "s1", "number": 1}],
        "episodes": [
            {
                "id": "ep_liked",
                "series_id": "s1",
                "season_id": "sea1",
                "number": 1,
                "title": "Tập gốc đã thích",
                "genre_ids": ["comedy"],
                "character_ids": ["jadoo", "mimi"],
                "themes": ["gia đình", "ẩm thực"],
                "keywords": ["bánh gạo", "bữa tối"],
            },
            {
                "id": "ep_unrelated",
                "series_id": "s1",
                "season_id": "sea1",
                "number": 2,
                "title": "Tập ít liên quan",
                "genre_ids": ["comedy"],
                "character_ids": ["other"],
                "themes": ["thể thao"],
                "keywords": ["chạy bộ"],
            },
            {
                "id": "ep_similar",
                "series_id": "s1",
                "season_id": "sea1",
                "number": 3,
                "title": "Tập cùng chủ đề và nhân vật",
                "genre_ids": ["comedy"],
                "character_ids": ["jadoo", "mimi"],
                "themes": ["gia đình", "ẩm thực"],
                "keywords": ["bánh gạo"],
            },
        ],
        "segments": [],
        "scenes": [],
        "media_assets": [],
        "text_tracks": [],
    }
    with TestClient(app) as client:
        sync_res = client.post("/api/index/sync", headers={"X-Service-Token": "test-token"}, json={"catalog": payload, "generation": 1})
        assert sync_res.status_code == 200
        rec_res = client.post("/api/recommend", json={"likedMovieIds": ["ep_liked"], "limit": 2})
        assert rec_res.status_code == 200
        body = rec_res.json()
        assert [m["id"] for m in body["recommendedMovies"]] == ["ep_similar", "ep_unrelated"]
        assert body["recommendedMovies"][0]["score"] > body["recommendedMovies"][1]["score"]
        assert "tương đồng" in body["reasoning"]


def test_frame_search_index_and_endpoint_match_keyframe_by_phash(tmp_path, monkeypatch):
    gradient = np.tile(np.linspace(0, 255, 64, dtype=np.uint8), (64, 1))
    image = np.stack([gradient, gradient, gradient], axis=-1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    image_bytes = encoded.tobytes()
    phash_hex = f"{compute_phash(image_bytes):016x}"

    ep_dir = tmp_path / "frames_index" / "ep_jadoo_s01_0022"
    ep_dir.mkdir(parents=True)
    (ep_dir / "keyframes.json").write_text(
        json.dumps({
            "episode_id": "ep_jadoo_s01_0022",
            "media_asset_id": "asset_22",
            "frames": [{"episode_id": "ep_jadoo_s01_0022", "media_asset_id": "asset_22", "source_ms": 42000, "phash": phash_hex}],
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("FRAME_INDEX_PATH", str(tmp_path / "frames_index"))
    app = create_app(
        sync_secret="test-token",
        sync_path=tmp_path / "state.json",
        cache_dir=tmp_path / "cache",
        model_mode="light",
        load_default=False,
    )
    payload = json.loads((ROOT / "docs/fixtures/retrieval_catalog.json").read_text(encoding="utf-8"))
    with TestClient(app) as client:
        client.post("/api/index/sync", headers={"X-Service-Token": "test-token"}, json={"catalog": payload, "generation": 1})
        assert client.get("/ready").json()["features"]["frameSearch"]["ready"]
        res = client.post("/v1/frame-search", content=image_bytes, headers={"Content-Type": "image/png"})
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) == 1
        assert results[0]["episodeId"] == "ep_jadoo_s01_0022"
        assert results[0]["startMs"] == 42000
        assert results[0]["matchPercentage"] == 100


def test_local_http_llm_client_and_natural_paraphrase_with_followups(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:3b")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    seen_headers = []

    def handler(request):
        seen_headers.append(dict(request.headers))
        payload = json.loads(request.content)
        if not payload.get("stream"):
            return httpx.Response(200, json={
                "choices": [{"message": {"content": json.dumps({"intent_type": "DISCOVERY", "mode": "find_moment", "scope": "scene"})}}]
            })
        body = (
            'data: {"choices":[{"delta":{"content":"Trong cảnh phim này, Chi đã làm vỡ bình hoa rất thú vị."},"finish_reason":"stop"}]}\n\n'
            'data: [DONE]\n\n'
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)

    movie = {
        "id": "ep_jadoo_s01_0022",
        "episodeId": "ep_jadoo_s01_0022",
        "title": "Tập 22",
        "startMs": 520000,
        "characters": ["Jadoo"],
        "genres": ["Hài hước"],
        "evidence": [{"documentId": "scene-22", "text": "Chi làm vỡ bình hoa.", "startMs": 520000}],
    }
    import services.chat as chat_module
    monkeypatch.setattr(chat_module, "evidence_for_results", lambda results: [{"title": "Tập 22", "startMs": 520000, "evidence": ["Chi làm vỡ bình hoa."]}])

    async def run():
        registry = ModelRegistry("cloud")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            llm = LLMClient(registry, client=http_client)
            service = ChatService(registry, lambda *a, **k: [movie], llm)
            events = [item async for item in service.stream("Chi làm vỡ bình hoa")]
            done_payload = events[-1][1]
            assert "Trong cảnh phim này, Chi đã làm vỡ bình hoa rất thú vị." in done_payload["text"]
            assert done_payload["pipelineStages"]["conversation"] == "cloud"
            assert any("Jadoo" in f for f in done_payload["followUps"])

    asyncio.run(run())
    assert seen_headers[0]["authorization"] == "Bearer local"


def test_full_catalog_grounding_unlocks_any_episode_when_enabled(monkeypatch):
    monkeypatch.setenv("ALLOW_FULL_CATALOG_GROUNDING", "1")
    episode = "ep_jadoo_s01_0001"
    result = {
        "episodeId": episode,
        "title": "any",
        "startMs": None,
        "evidence": [{"documentId": episode, "text": "any"}],
    }
    evidence = evidence_for_results([result])
    assert len(evidence) == 1
    assert evidence[0]["title"]


def test_unified_enrichment_pipeline_supports_arbitrary_episode_count(tmp_path):
    from ai.enrich.common import CATALOG, read, write

    payload = read(CATALOG)
    assets = {a["coverage"][0]["episode_id"]: a for a in payload["media_assets"] if a["role"] == "feature" and a["coverage"]}
    rows = [{"episode_id": ep["id"], "media_asset_id": assets[ep["id"]]["id"]} for ep in payload["episodes"] if ep["id"] in assets][:2]
    inventory_path = tmp_path / "inventory.json"
    write(inventory_path, {"pilot": rows})
    timestamp = "2026-11-11T00:00:00+00:00"
    for row in rows:
        ep_dir = tmp_path / row["episode_id"]
        cue = {"id": row["episode_id"] + ".cue.00001", "start_ms": 0, "end_ms": 1000, "text": "Xin chào Jadoo.", "speaker_character_ids": [], "confidence": None}
        write(ep_dir / "asr.json", {**row, "model": "whisper-turbo", "revision": "v1", "language": "vi", "created_at": timestamp, "cues": [cue]})

    output_path = tmp_path / "enriched_two_episodes.json"
    report = run_pipeline(
        inventory_path=inventory_path,
        artifacts_dir=tmp_path,
        catalog_path=CATALOG,
        dialogue_only=True,
        output_path=output_path,
        skip_video_stages=True,
    )
    assert report["episodes"] == [r["episode_id"] for r in rows]
    assert report["text_tracks"] == 2
    assert output_path.is_file()
