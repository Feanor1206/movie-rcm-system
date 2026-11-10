import copy
import json
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import create_app


ROOT = Path(__file__).resolve().parents[3]
TOKEN = {"X-Service-Token": "test-sync-secret"}


@pytest.fixture
def payload():
    return json.loads((ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8"))


@pytest.fixture
def app(tmp_path):
    return create_app(sync_secret="test-sync-secret", sync_path=tmp_path / "accepted.json",
                      cache_dir=tmp_path / "cache", load_default=False, model_mode="light")


def sync(client, payload, generation=1, **extra):
    return client.post("/api/index/sync", headers=TOKEN,
                       json={"catalog": payload, "generation": generation, **extra})


def test_authenticated_sync_hash_validation_and_empty_acceptance(app, payload):
    with TestClient(app) as client:
        assert client.post("/api/index/sync", json={"catalog": payload}).status_code == 401
        assert client.post("/api/index/sync", headers={"Authorization": "Bearer wrong"}, json={"catalog": payload}).status_code == 403
        assert sync(client, payload, content_hash="incorrect").status_code == 400
        assert app.state.runtime.snapshot is None
        response = sync(client, payload)
        assert response.status_code == 200 and response.json()["index_ready"]
        empty = copy.deepcopy(payload)
        for key in ("series", "seasons", "episodes", "segments", "scenes", "characters", "media_assets", "text_tracks"):
            empty[key] = []
        assert sync(client, empty, 2).status_code == 200
        assert app.state.runtime.snapshot.get_flattened_catalog() == []
        assert client.post("/v1/search", json={"query": "anything"}).json()["results"] == []


def test_generation_idempotency_conflict_stale_and_reader_ownership(app, payload):
    with TestClient(app) as client:
        accepted = sync(client, payload, 3)
        assert accepted.status_code == 200
        old = app.state.runtime.snapshot
        old_items = old.get_flattened_catalog()
        changed = copy.deepcopy(payload)
        changed["series"][0]["title"] += " Changed"
        assert sync(client, payload, 3).json()["status"] == "UNCHANGED"
        assert sync(client, changed, 3).status_code == 409
        assert sync(client, changed, 2).json()["status"] == "SKIPPED"
        assert sync(client, changed, 4).status_code == 200
        assert old.get_flattened_catalog() == old_items
        assert old.content_hash != app.state.runtime.snapshot.content_hash
        payload["series"][0]["title"] = "external mutation"
        exposed = old.get_flattened_catalog()
        exposed[0]["title"] = "reader mutation"
        assert old.get_flattened_catalog() == old_items


def test_failed_persistence_keeps_old_snapshot_and_hides_details(app, payload, monkeypatch):
    with TestClient(app) as client:
        assert sync(client, payload).status_code == 200
        old = app.state.runtime.snapshot
        def fail(*args):
            raise OSError("private filesystem path")
        monkeypatch.setattr(app.state.runtime, "save", fail)
        changed = copy.deepcopy(payload)
        changed["series"][0]["title"] += " v2"
        response = sync(client, changed, 2)
        assert response.status_code == 500
        assert "private filesystem path" not in response.text
        assert app.state.runtime.snapshot is old


def test_preparation_does_not_hold_publication_lock_and_rechecks_generation(app, payload, monkeypatch):
    with TestClient(app) as client:
        assert sync(client, payload).status_code == 200
        state = app.state.runtime
        original_build = state.build_index
        entered, release = threading.Event(), threading.Event()
        def blocked(manager, **kwargs):
            if manager.get_flattened_catalog()[0]["title"].endswith(" slow"):
                assert state.publish_lock.acquire(blocking=False)
                state.publish_lock.release()
                entered.set()
                assert release.wait(5)
            return original_build(manager, **kwargs)
        monkeypatch.setattr(state, "build_index", blocked)
        slow, newest = copy.deepcopy(payload), copy.deepcopy(payload)
        slow["series"][0]["title"] += " slow"
        newest["series"][0]["title"] += " latest"
        responses = []
        worker = threading.Thread(target=lambda: responses.append(sync(client, slow, 2)))
        worker.start()
        assert entered.wait(5)
        try:
            assert sync(client, newest, 3).status_code == 200
        finally:
            release.set()
            worker.join(5)
        assert not worker.is_alive()
        assert responses[0].json()["status"] == "SKIPPED"
        assert state.snapshot.generation == 3


def test_recovery_and_independent_app_instances(tmp_path, payload):
    options = dict(sync_secret="test-sync-secret", sync_path=tmp_path / "accepted.json",
                   cache_dir=tmp_path / "cache", load_default=False, model_mode="light")
    first = create_app(**options)
    with TestClient(first) as client:
        assert sync(client, payload, 7).status_code == 200
        content_hash = first.state.runtime.snapshot.content_hash
    recovered = create_app(**options)
    with TestClient(recovered) as client:
        assert recovered.state.runtime.snapshot.generation == 7
        assert recovered.state.runtime.snapshot.content_hash == content_hash
        assert client.get("/ready").json()["features"]["search"]["ready"]
    separate = create_app(**{**options, "sync_path": tmp_path / "other.json"})
    with TestClient(separate):
        assert separate.state.runtime.snapshot is None


def test_client_catalog_injection_is_rejected(app, payload):
    with TestClient(app) as client:
        assert sync(client, payload).status_code == 200
        for path in ("/api/chat", "/v1/discover", "/v1/search"):
            response = client.post(path, json={"query": "hello", "availableMovies": []})
            assert response.status_code == 422
