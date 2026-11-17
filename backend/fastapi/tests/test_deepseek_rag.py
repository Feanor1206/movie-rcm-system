import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from main import create_app


def test_deepseek_rag_uses_one_approved_catalog_request(tmp_path, monkeypatch):
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
        done = next(json.loads(event.split("data: ", 1)[1]) for event in response.text.split("\n\n")
                    if event.startswith("event: done\n"))
        assert done["pipelineStages"]["conversation"] == "cloud", (len(calls), done["text"][:160], [
            (item["episodeId"], item["startMs"], item["evidence"][0]["documentId"], item["evidence"][0]["itemType"])
            for item in done["recommendedMovies"][:3]
        ])
        assert done["recommendedMovies"][0]["episodeId"] == "ep_jadoo_s01_0022"
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
