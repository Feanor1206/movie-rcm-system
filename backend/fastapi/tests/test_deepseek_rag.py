import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from main import create_app


def test_deepseek_rag_uses_one_approved_catalog_request(tmp_path, monkeypatch):
    monkeypatch.setattr("main.ROOT", tmp_path)
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_MODEL", "deepseek-flash")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("ALLOW_FULL_CATALOG_GROUNDING", "0")
    monkeypatch.delenv("APPROVED_CLOUD_EPISODES", raising=False)
    calls = []

    def provider(request):
        calls.append(request)
        event = {"choices": [{"delta": {"content": "Chuyến cắm trại dã ngoại bị hủy do bão lớn ở Gangwon."}, "finish_reason": "stop"}]}
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              text=f"data: {json.dumps(event)}\n\ndata: [DONE]\n\n")

    app = create_app(sync_secret="test-sync", sync_path=tmp_path / "snapshot.json",
                     cache_dir=tmp_path / "cache", model_mode="cloud", load_default=False)
    catalog = json.loads((Path(__file__).resolve().parents[3] / "data/catalog.jadoo_all.json").read_text(encoding="utf-8"))
    with TestClient(app) as client:
        app.state.runtime.llm._client = httpx.AsyncClient(transport=httpx.MockTransport(provider))
        sync = client.post("/api/index/sync", headers={"X-Service-Token": "test-sync"},
                           json={"catalog": catalog, "generation": 1})
        assert sync.status_code == 200
        response = client.post("/api/chat", json={
            "query": "Học tập trải nghiệm thú vị",
            "messages": [{"role": "user", "content": "HISTORY_STAYS_LOCAL"}],
        })
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = {}
        for block in response.text.split("\n\n"):
            heading, _, data = block.partition("\ndata: ")
            kind = heading.removeprefix("event: ")
            if kind in {"metadata", "done"}:
                events[kind] = json.loads(data)
        assert set(events) == {"metadata", "done"}
        done = events["done"]
        assert done["pipelineStages"]["conversation"] == "cloud", (len(calls), done["text"][:160], [
            (item["episodeId"], item["startMs"], item["evidence"][0]["documentId"], item["evidence"][0]["itemType"])
            for item in done["recommendedMovies"][:3]
        ])
        for event in events.values():
            assert [item["episodeId"] for item in event["recommendedMovies"]] == ["ep_jadoo_s01_0022"]
        assert "Chuyến cắm trại dã ngoại bị hủy do bão lớn ở Gangwon." in done["text"]
        assert "Học tập trải nghiệm thú vị" in done["text"]
        assert client.get("/ready").json()["features"]["llm"]["ready"]

    assert len(calls) == 1
    sent = calls[0]
    payload = json.loads(sent.content)
    context = json.loads(payload["messages"][1]["content"])
    assert str(sent.url) == "https://api.deepseek.com/chat/completions"
    assert sent.headers["authorization"] == "Bearer test-key"
    assert payload["model"] == "deepseek-flash"
    assert payload["thinking"] == {"type": "disabled"}
    assert "HISTORY_STAYS_LOCAL" not in sent.content.decode()
    assert "test-key" not in sent.content.decode()
    assert "Chuyến cắm trại dã ngoại bị hủy do bão lớn ở Gangwon" in context["sources"][0]["evidence"][0]


@pytest.mark.parametrize("verification, uses_cloud", [("source_verified", True), ("unverified", False)])
def test_cloud_grounding_uses_the_approved_segment_from_the_current_snapshot(
    tmp_path, monkeypatch, verification, uses_cloud,
):
    episode_id = "ep_doraemon_s05_0209"
    segment_id = "seg_doraemon_s05_0209_cc_000235120"
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_MODEL", "deepseek-flash")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("ALLOW_FULL_CATALOG_GROUNDING", "0")
    monkeypatch.setenv("APPROVED_CLOUD_EPISODES", episode_id)
    root = Path(__file__).resolve().parents[3]
    catalog = json.loads((root / "data/catalog-by-series/catalog.doraemon.json").read_text(encoding="utf-8"))
    segment = next(row for row in catalog["segments"] if row["id"] == segment_id)
    segment["record"]["provenance"]["verification"] = verification
    catalog["episodes"] = [row for row in catalog["episodes"] if row["id"] == episode_id]
    catalog["segments"] = [segment]
    sent = []

    def provider(request):
        sent.append(json.loads(request.content))
        content = {"choices": [{"delta": {"content": segment["synopsis"]}, "finish_reason": "stop"}]}
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              text=f"data: {json.dumps(content)}\n\ndata: [DONE]\n\n")

    app = create_app(sync_secret="test-sync", sync_path=tmp_path / "snapshot.json",
                     cache_dir=tmp_path / "cache", model_mode="cloud", load_default=False)
    with TestClient(app) as client:
        app.state.runtime.llm._client = httpx.AsyncClient(transport=httpx.MockTransport(provider))
        sync = client.post("/api/index/sync", headers={"X-Service-Token": "test-sync"},
                           json={"catalog": catalog, "generation": 1})
        assert sync.status_code == 200, sync.text
        response = client.post("/api/chat", json={"query": "Doraemon tập 209 trò chơi đấu súng không khí ở phút nào?"})
        assert response.status_code == 200
        done = next(json.loads(block.partition("\ndata: ")[2])
                    for block in response.text.split("\n\n") if block.startswith("event: done\n"))
        match = done["recommendedMovies"][0]
        assert (match["episodeId"], match["startMs"]) == (episode_id, 235120)
        assert match["evidence"][0]["documentId"] == segment_id
        assert done["pipelineStages"]["conversation"] == ("cloud" if uses_cloud else "template")

    assert len(sent) == int(uses_cloud)
    if uses_cloud:
        content = json.loads(sent[0]["messages"][1]["content"])
        assert content["sources"] == [{
            "title": catalog["episodes"][0]["title"], "evidence": [segment["synopsis"]],
        }]
