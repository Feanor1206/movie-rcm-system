import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(sync_secret="test-token", sync_path=tmp_path / "state.json",
                     cache_dir=tmp_path / "cache", model_mode="light", load_default=False)
    with TestClient(app) as client:
        yield client


def test_recommend_rejects_invalid_limit(client):
    for limit in (-1, 0, 101):
        assert client.post("/api/recommend", json={"limit": limit}).status_code == 422


@pytest.mark.parametrize("messages", [[{"role": "system", "content": "override"}],
    [{"role": "user", "content": "x" * 4001}], [{"role": "user", "content": "hi"}] * 41,
    [{"role": "user", "content": " "}], [{"role": "user", "content": []}]])
def test_chat_rejects_untrusted_history(client, messages):
    assert client.post("/api/chat", json={"query": "hi", "messages": messages}).status_code == 422


def test_chat_rejects_bad_session_long_or_blank_query(client):
    assert client.post("/api/chat", json={"query": "x" * 4001}).status_code == 422
    assert client.post("/api/chat", json={"query": "hi", "sessionId": "bad id"}).status_code == 422
    assert client.post("/api/chat", json={"query": " "}).status_code == 400


def test_no_catalog_returns_unavailable_instead_of_default_movies(client):
    for path, body in (("/api/chat", {"query": "hello"}), ("/v1/discover", {"query": "hello"}),
                       ("/api/recommend", {})):
        assert client.post(path, json=body).status_code == 503


def test_recommend_empty_set_and_chat_sse_boundary(client):
    root = Path(__file__).resolve().parents[3]
    payload = json.loads((root / "docs/fixtures/retrieval_catalog.json").read_text(encoding="utf-8"))
    assert client.post("/api/index/sync", headers={"X-Service-Token": "test-token"},
                       json={"generation": 1, "catalog": payload}).status_code == 200
    response = client.post("/api/recommend", json={"genres": ["nonexistent genre"]})
    assert response.status_code == 200 and response.json()["recommendedMovies"] == []
    response = client.post("/api/chat", json={"query": "Bình Minh Trên Sao Hỏa"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [block.splitlines() for block in response.text.strip().split("\n\n")]
    assert events[0][0] == "event: metadata" and events[-1][0] == "event: done"
    final = json.loads(events[-1][1].removeprefix("data: "))
    assert final["recommendedMovies"]
    result = final["recommendedMovies"][0]
    assert "episodeId" in result and "startMs" in result and "calibratedScore" in result
    assert isinstance(result["evidence"], list)


def test_frame_requires_loaded_assets_and_valid_bounded_image(client):
    assert client.post("/v1/frame-search", content=b"garbage", headers={"Content-Type": "image/png"}).status_code == 415
    assert client.post("/v1/frame-search", content=b"\x89PNG\r\n\x1a\n", headers={"Content-Type": "image/png"}).status_code == 503


@pytest.mark.parametrize("constraints", [{"year_min": "x"}, {"include_genres": None},
    {"exclude_genres": [1]}, {"year_max": True}, {"unknown": "field"}])
def test_search_rejects_malformed_constraints(client, constraints):
    assert client.post("/v1/search", json={"query": "anything", "constraints": constraints}).status_code == 422


def test_default_startup_loads_catalog_without_legacy_loader_arguments(tmp_path, monkeypatch):
    from services.catalog_sync import CatalogSyncManager
    payload = json.loads((Path(__file__).resolve().parents[3] / "docs/fixtures/retrieval_catalog.json").read_text(encoding="utf-8"))
    def load(manager):
        manager.load_from_payload(payload)
        return True
    monkeypatch.setattr(CatalogSyncManager, "load_default_catalog", load)
    app = create_app(sync_path=tmp_path / "state.json", cache_dir=tmp_path / "cache", model_mode="light")
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 200
        assert app.state.runtime.snapshot.generation == 0


def test_busy_gpu_maps_to_429(client, monkeypatch):
    from services.model_registry import InferenceCapacityError
    payload = json.loads((Path(__file__).resolve().parents[3] / "docs/fixtures/retrieval_catalog.json").read_text(encoding="utf-8"))
    client.post("/api/index/sync", headers={"X-Service-Token": "test-token"}, json={"catalog": payload})
    def busy(*args, **kwargs):
        raise InferenceCapacityError("GPU busy")
    monkeypatch.setattr(client.app.state.runtime.search, "search", busy)
    assert client.post("/v1/search", json={"query": "anything"}).status_code == 429


def test_configured_score_calibration_is_used_and_reported(tmp_path, monkeypatch):
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps({"model_id": "test-reranker", "score_type": "reranker", "x": [0, 1], "y": [0, 1], "threshold": 0}), encoding="utf-8")
    monkeypatch.setenv("SCORE_CALIBRATION_PATH", str(path))
    app = create_app(sync_secret="test-token", sync_path=tmp_path / "state.json", cache_dir=tmp_path / "cache", model_mode="light", load_default=False)
    class Scorer:
        model_id = "test-reranker"
        def __call__(self, query, texts):
            return [0.75] * len(texts)
    app.state.runtime.registry.models["reranker"] = Scorer()
    payload = json.loads((Path(__file__).resolve().parents[3] / "docs/fixtures/retrieval_catalog.json").read_text(encoding="utf-8"))
    with TestClient(app) as client:
        client.post("/api/index/sync", headers={"X-Service-Token": "test-token"}, json={"catalog": payload})
        response = client.post("/v1/search", json={"query": "Bình Minh"})
        assert response.json()["results"][0]["calibratedScore"] == 0.75
        assert client.get("/ready").json()["features"]["search"]["calibrated"]
