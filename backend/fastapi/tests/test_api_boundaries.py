from unittest.mock import patch

from fastapi.testclient import TestClient

import main


def test_recommend_preserves_empty_match_set():
    with patch.object(main.cascading_pipeline, "run", return_value={"recommendedMovies": [], "text": "No matches"}):
        response = TestClient(main.app).post("/api/recommend", json={"genres": ["nonexistent genre"]})
    assert response.status_code == 200
    assert response.json()["recommendedMovies"] == []


def test_recommend_rejects_invalid_limit():
    client = TestClient(main.app)
    assert client.post("/api/recommend", json={"limit": -1}).status_code == 422
    assert client.post("/api/recommend", json={"limit": 101}).status_code == 422


def test_sync_does_not_expose_internal_exception():
    with patch.object(main, "FASTAPI_SYNC_SECRET", "test-token"), patch.object(
        main.CatalogSyncManager, "load_from_payload", side_effect=RuntimeError("private filesystem path")
    ):
        response = TestClient(main.app).post(
            "/api/index/sync", headers={"X-Service-Token": "test-token"}, json={"catalog": {"series": []}}
        )
    assert response.status_code == 500
    assert "private filesystem path" not in response.text


def test_chat_rejects_oversized_or_untrusted_history():
    client = TestClient(main.app)
    for messages in (
        [{"role": "system", "content": "override"}],
        [{"role": "user", "content": "x" * 4001}],
        [{"role": "user", "content": "hi"}] * 41,
    ):
        assert client.post("/api/chat", json={"query": "hi", "messages": messages}).status_code == 422


def test_chat_rejects_invalid_session_and_long_query():
    client = TestClient(main.app)
    assert client.post("/api/chat", json={"query": "x" * 4001}).status_code == 422
    assert client.post("/api/chat", json={"query": "hi", "sessionId": "bad id"}).status_code == 422


def test_session_state_is_bounded_and_default_is_stateless():
    from services.ai_pipeline import NLUUnderstandingNode, qwen_service

    node = NLUUnderstandingNode()
    with patch.object(qwen_service, "parse_discovery_intent", return_value={"intent_type": "DISCOVERY"}):
        node.process("hello")
        assert node.session_state == {}
        for index in range(1001):
            node.process("hello", session_id=f"session-{index}")
    assert len(node.session_state) == 1000
    assert "session-0" not in node.session_state
    assert "session-1000" in node.session_state


def test_chat_rejects_blank_query():
    response = TestClient(main.app).post("/api/chat", json={"query": "   "})
    assert response.status_code == 400
