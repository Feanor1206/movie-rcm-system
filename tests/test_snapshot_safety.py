import copy
import json
import threading

import pytest

from schemas import IndexSyncRequest
from services.catalog_sync import AcceptedSnapshot, CatalogSyncManager
from services.text_index import TextIndex


def test_snapshot_owns_nested_manager_payload_and_returned_results(catalog_payload, tmp_path):
    manager = CatalogSyncManager()
    manager.load_from_payload(catalog_payload)
    index = TextIndex.build(manager.get_flattened_catalog(), cache_dir=tmp_path)
    snapshot = AcceptedSnapshot(0, manager.content_hash, manager, index, catalog_payload)
    original = snapshot.get_flattened_catalog()
    manager._flattened_items[0]["title"] = "mutated manager"
    catalog_payload["series"][0]["title"] = "mutated payload"
    exposed = snapshot.get_flattened_catalog()
    exposed[0]["genres"].append("mutated returned list")
    item = snapshot.get_item_by_id(original[0]["id"])
    item["title"] = "mutated item"
    assert snapshot.is_ready
    assert snapshot.get_flattened_catalog() == original
    assert snapshot.payload["series"][0]["title"] != "mutated payload"
    assert index.documents[0]["title"] == original[0]["title"]


@pytest.mark.parametrize("generation", [-1, 1.5, True, "1"])
def test_invalid_generation_rejected(client, catalog_payload, generation):
    response = client.post("/api/index/sync", headers={"X-Service-Token": "snapshot-token"},
                           json={"catalog": catalog_payload, "generation": generation})
    assert response.status_code == 422


def test_build_failure_keeps_durable_and_active_snapshot(accept, serving_app, catalog_payload, monkeypatch):
    assert accept(catalog_payload).status_code == 200
    state = serving_app.state.runtime
    snapshot = state.snapshot
    durable = state.sync_path.read_bytes()
    def fail(*args, **kwargs):
        raise RuntimeError("private model path")
    monkeypatch.setattr(state, "build_index", fail)
    changed = copy.deepcopy(catalog_payload)
    changed["series"][0]["title"] += " new"
    response = accept(changed, 2)
    assert response.status_code == 500
    assert "private model path" not in response.text
    assert state.snapshot is snapshot
    assert state.sync_path.read_bytes() == durable


def test_replace_failure_keeps_durable_and_active_snapshot(accept, serving_app, catalog_payload, monkeypatch):
    import services.runtime
    assert accept(catalog_payload).status_code == 200
    state = serving_app.state.runtime
    snapshot, durable = state.snapshot, state.sync_path.read_bytes()
    def fail(*args):
        raise OSError("replace failed")
    monkeypatch.setattr(services.runtime.os, "replace", fail)
    changed = copy.deepcopy(catalog_payload)
    changed["series"][0]["title"] += " new"
    assert accept(changed, 2).status_code == 500
    assert state.snapshot is snapshot
    assert state.sync_path.read_bytes() == durable
    assert not list(state.sync_path.parent.glob("accepted-*.tmp"))


def test_multiple_publications_retain_pure_reader_snapshots(accept, serving_app, catalog_payload):
    snapshots = []
    for generation in range(1, 5):
        payload = copy.deepcopy(catalog_payload)
        payload["series"][0]["title"] = f"Snapshot {generation}"
        assert accept(payload, generation).status_code == 200
        snapshots.append(serving_app.state.runtime.snapshot)
    for generation, snapshot in enumerate(snapshots, 1):
        assert snapshot.generation == generation
        assert snapshot.get_flattened_catalog()[0]["title"] == f"Snapshot {generation}"
        assert snapshot.hybrid_index.documents[0]["title"] == f"Snapshot {generation}"


def test_dense_delta_runs_outside_request_and_duplicate_jobs_are_coalesced(client, serving_app, catalog_payload, monkeypatch):
    import numpy as np
    state = serving_app.state.runtime
    entered, release = threading.Event(), threading.Event()
    class Encoder:
        model_id = "test-encoder-v1"
        def encode_documents(self, texts):
            entered.set()
            assert release.wait(5)
            return np.ones((len(texts), 2))
        def encode_queries(self, texts):
            return np.ones((len(texts), 2))
    state.registry.models["embedder"] = Encoder()
    body = {"catalog": catalog_payload, "generation": 1}
    headers = {"X-Service-Token": "snapshot-token"}
    response = client.post("/api/index/sync", headers=headers, json=body)
    assert response.status_code == 202 and not response.json()["index_ready"]
    assert entered.wait(5)
    assert state.snapshot is None
    try:
        assert client.post("/api/index/sync", headers=headers, json=body).status_code == 202
        assert state.publish_lock.acquire(blocking=False)
        state.publish_lock.release()
    finally:
        release.set()
        state.executor.shutdown(wait=True)
    assert state.snapshot.generation == 1
    assert state.snapshot.hybrid_index.dense_ready
    assert client.post("/api/index/sync", headers=headers, json=body).json()["status"] == "UNCHANGED"


def test_large_dense_cache_miss_requires_offline_preparation(accept, serving_app, catalog_payload):
    class Encoder:
        model_id = "not-prepared"
        def encode_documents(self, texts):
            raise AssertionError("Sync must not run full catalog encoding")
    state = serving_app.state.runtime
    state.registry.models["embedder"] = Encoder()
    state.max_delta_documents = 0
    assert accept(catalog_payload).status_code == 503
    assert state.snapshot is None and state.pending is None


def test_failed_background_job_is_reported_on_retry(accept, serving_app, catalog_payload):
    class Encoder:
        model_id = "broken-encoder"
        def encode_documents(self, texts):
            raise RuntimeError("private encoder failure")
    state = serving_app.state.runtime
    state.registry.models["embedder"] = Encoder()
    assert accept(catalog_payload).status_code == 202
    state.executor.submit(lambda: None).result(timeout=5)
    response = accept(catalog_payload)
    assert response.status_code == 500
    assert "private encoder failure" not in response.text
    assert state.snapshot is None
    assert state.pending is None
    assert accept(catalog_payload).status_code == 202


def test_concurrent_searches_retain_one_complete_snapshot(accept, serving_app, catalog_payload):
    from concurrent.futures import ThreadPoolExecutor
    assert accept(catalog_payload).status_code == 200
    state = serving_app.state.runtime
    barrier = threading.Barrier(4)
    def publish():
        barrier.wait(timeout=5)
        for generation in range(2, 10):
            payload = copy.deepcopy(catalog_payload)
            payload["series"][0]["title"] = f"Catalog {generation}"
            result, status = state.sync(IndexSyncRequest(catalog=payload, generation=generation))
            assert status == 200 and result["generation"] == generation
    def read():
        barrier.wait(timeout=5)
        for _ in range(40):
            snapshot = state.snapshot
            before = snapshot.get_flattened_catalog()
            assert snapshot.hybrid_index.documents[0]["title"] == before[0]["title"]
            state.search.search(snapshot, before[0]["title"])
            assert snapshot.get_flattened_catalog() == before
    with ThreadPoolExecutor(max_workers=4) as workers:
        futures = [workers.submit(publish)] + [workers.submit(read) for _ in range(3)]
        for future in futures:
            future.result(timeout=10)
    assert state.snapshot.generation == 9


def test_corrupt_saved_state_does_not_bootstrap_over_accepted_state(tmp_path, catalog_payload):
    from main import create_app
    from fastapi.testclient import TestClient
    path = tmp_path / "accepted.json"
    path.write_text(json.dumps({"generation": 5, "content_hash": "wrong", "catalog": catalog_payload}), encoding="utf-8")
    app = create_app(sync_path=path, cache_dir=tmp_path / "cache", load_default=True, model_mode="light")
    with TestClient(app) as client:
        assert app.state.runtime.snapshot is None
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["recoveryError"]
