"""
CATALOG-01-F09: Production Snapshot Ownership & Multi-Sync Regression Test Suite
Validates that:
1. Recovered snapshot A (gen 1) retains pure state when B (gen 2) is published with REAL setter.
2. Repeated syncs (B -> C) never mutate retained snapshot A.
3. Default bootstrap snapshot (gen 0) retains pure state when a new package is published.
4. Durable write failure preserves active snapshot without leaking candidate.
5. AcceptedSnapshot.__post_init__ guarantees manager isolation even if singleton is passed.
"""

import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def matrix_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("f08_matrix", ROOT / "tests/test_f08_atomic_concurrency_matrix.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def sync_hybrid(matrix_mod):
    return matrix_mod.load_sync_and_index_modules()


@pytest.fixture
def catalog_fixture():
    p = ROOT / "docs/fixtures/rehearsal_catalog.json"
    return json.loads(p.read_text(encoding="utf-8"))


def titles(rows):
    return [r["title"] for r in rows if r.get("item_type") == "series"]


def test_recovered_snapshot_ownership_real_setter(matrix_mod, sync_hybrid, catalog_fixture):
    """Test 1: Recovered snapshot A is not mutated when B is published via real setter."""
    sync_mod, hybrid_mod = sync_hybrid
    a = copy.deepcopy(catalog_fixture)
    b = copy.deepcopy(catalog_fixture)
    a["series"][0]["title"] = "recovered-A"
    b["series"][0]["title"] = "published-B"

    with tempfile.TemporaryDirectory(prefix="test-f09-rec-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        ns, _, index, _, _ = matrix_mod.create_test_context(temp_dir, sync_mod, hybrid_mod)

        # 1. Startup recovery: creates isolated manager
        rec_mgr = sync_mod.CatalogSyncManager()
        rec_mgr.load_from_payload(a, include_draft=False, include_private=False)
        index.build_from_catalog(rec_mgr.get_flattened_catalog(), save_to_disk=False)

        recovered = sync_mod.AcceptedSnapshot(
            generation=1,
            content_hash=rec_mgr.compute_hash(a),
            catalog_manager=rec_mgr,
            hybrid_index=index,
            payload=a,
        )
        sync_mod.set_accepted_snapshot(recovered)
        retained_a = sync_mod.get_accepted_snapshot()

        # Connect REAL production setter/getter
        ns.update(
            catalog_sync_manager=sync_mod.catalog_sync_manager,
            AcceptedSnapshot=sync_mod.AcceptedSnapshot,
            set_accepted_snapshot=sync_mod.set_accepted_snapshot,
            get_accepted_snapshot=sync_mod.get_accepted_snapshot,
            _current_sync_generation=1,
            _current_sync_hash=retained_a.content_hash,
        )

        # 2. Publish B
        res = ns["sync_index"](
            SimpleNamespace(headers={"X-Service-Token": "test-sync-secret-f08"}),
            SimpleNamespace(generation=2, catalog=b, content_hash=rec_mgr.compute_hash(b)),
        )
        assert res.status == "success"

        # 3. Retained snapshot A must be 100% pure A
        assert retained_a.generation == 1
        assert "recovered-A" in titles(retained_a.get_flattened_catalog())
        assert "published-B" not in titles(retained_a.get_flattened_catalog())
        assert "recovered-A" in titles(retained_a.hybrid_index.documents.values())
        assert "published-B" not in titles(retained_a.hybrid_index.documents.values())

        # 4. New snapshot must be 100% pure B
        current = sync_mod.get_accepted_snapshot()
        assert current.generation == 2
        assert "published-B" in titles(current.get_flattened_catalog())
        assert "recovered-A" not in titles(current.get_flattened_catalog())


def test_multi_sync_durability(matrix_mod, sync_hybrid, catalog_fixture):
    """Test 2: Repeated syncs (B -> C) never mutate retained snapshot A."""
    sync_mod, hybrid_mod = sync_hybrid
    a = copy.deepcopy(catalog_fixture)
    b = copy.deepcopy(catalog_fixture)
    c = copy.deepcopy(catalog_fixture)
    a["series"][0]["title"] = "recovered-A"
    b["series"][0]["title"] = "published-B"
    c["series"][0]["title"] = "published-C"

    with tempfile.TemporaryDirectory(prefix="test-f09-multi-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        ns, _, index, _, _ = matrix_mod.create_test_context(temp_dir, sync_mod, hybrid_mod)

        rec_mgr = sync_mod.CatalogSyncManager()
        rec_mgr.load_from_payload(a, include_draft=False, include_private=False)
        index.build_from_catalog(rec_mgr.get_flattened_catalog(), save_to_disk=False)

        recovered = sync_mod.AcceptedSnapshot(
            generation=1,
            content_hash=rec_mgr.compute_hash(a),
            catalog_manager=rec_mgr,
            hybrid_index=index,
            payload=a,
        )
        sync_mod.set_accepted_snapshot(recovered)
        retained_a = sync_mod.get_accepted_snapshot()

        ns.update(
            catalog_sync_manager=sync_mod.catalog_sync_manager,
            AcceptedSnapshot=sync_mod.AcceptedSnapshot,
            set_accepted_snapshot=sync_mod.set_accepted_snapshot,
            get_accepted_snapshot=sync_mod.get_accepted_snapshot,
            _current_sync_generation=1,
            _current_sync_hash=retained_a.content_hash,
        )

        # Sync B
        ns["sync_index"](
            SimpleNamespace(headers={"X-Service-Token": "test-sync-secret-f08"}),
            SimpleNamespace(generation=2, catalog=b, content_hash=rec_mgr.compute_hash(b)),
        )

        # Sync C
        ns["sync_index"](
            SimpleNamespace(headers={"X-Service-Token": "test-sync-secret-f08"}),
            SimpleNamespace(generation=3, catalog=c, content_hash=rec_mgr.compute_hash(c)),
        )

        # Retained A remains pure
        assert retained_a.generation == 1
        mgr_titles = titles(retained_a.get_flattened_catalog())
        assert "recovered-A" in mgr_titles
        assert "published-B" not in mgr_titles
        assert "published-C" not in mgr_titles


def test_default_bootstrap_ownership(matrix_mod, sync_hybrid, catalog_fixture):
    """Test 3: Default bootstrap snapshot (gen 0) is not mutated when package is published."""
    sync_mod, hybrid_mod = sync_hybrid
    a = copy.deepcopy(catalog_fixture)
    b = copy.deepcopy(catalog_fixture)
    a["series"][0]["title"] = "default-A"
    b["series"][0]["title"] = "published-B"

    with tempfile.TemporaryDirectory(prefix="test-f09-boot-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        ns, _, index, _, _ = matrix_mod.create_test_context(temp_dir, sync_mod, hybrid_mod)

        def_mgr = sync_mod.CatalogSyncManager()
        def_mgr.load_from_payload(a, include_draft=False, include_private=False)
        index.build_from_catalog(def_mgr.get_flattened_catalog(), save_to_disk=False)

        default_snap = sync_mod.AcceptedSnapshot(
            generation=0,
            content_hash=def_mgr.compute_hash(a),
            catalog_manager=def_mgr,
            hybrid_index=index,
            payload=a,
        )
        sync_mod.set_accepted_snapshot(default_snap)
        retained_def = sync_mod.get_accepted_snapshot()

        ns.update(
            catalog_sync_manager=sync_mod.catalog_sync_manager,
            AcceptedSnapshot=sync_mod.AcceptedSnapshot,
            set_accepted_snapshot=sync_mod.set_accepted_snapshot,
            get_accepted_snapshot=sync_mod.get_accepted_snapshot,
            _current_sync_generation=0,
            _current_sync_hash=retained_def.content_hash,
        )

        ns["sync_index"](
            SimpleNamespace(headers={"X-Service-Token": "test-sync-secret-f08"}),
            SimpleNamespace(generation=1, catalog=b, content_hash=def_mgr.compute_hash(b)),
        )

        assert retained_def.generation == 0
        def_titles = titles(retained_def.get_flattened_catalog())
        assert "default-A" in def_titles
        assert "published-B" not in def_titles


def test_post_init_guard_isolates_singleton(sync_hybrid, catalog_fixture):
    """Test 4: Even if caller explicitly passes catalog_sync_manager singleton, __post_init__ isolates it."""
    sync_mod, _ = sync_hybrid
    mgr = sync_mod.catalog_sync_manager
    mgr.load_from_payload(catalog_fixture, include_draft=False, include_private=False)

    snap = sync_mod.AcceptedSnapshot(
        generation=1,
        content_hash="test-hash",
        catalog_manager=mgr,
        hybrid_index=None,
    )
    # The snapshot's manager must be an isolated instance, not the singleton!
    assert snap.catalog_manager is not mgr
    assert snap.catalog_manager.content_hash == mgr.content_hash


def test_durable_failure_preserves_isolated_snapshot(matrix_mod, sync_hybrid, catalog_fixture):
    """Test 5: Durable save failure preserves active snapshot without candidate leak."""
    sync_mod, hybrid_mod = sync_hybrid
    a = copy.deepcopy(catalog_fixture)
    b = copy.deepcopy(catalog_fixture)
    a["series"][0]["title"] = "accepted-A"
    b["series"][0]["title"] = "rejected-B"

    with tempfile.TemporaryDirectory(prefix="test-f09-fail-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        ns, _, index, _, _ = matrix_mod.create_test_context(temp_dir, sync_mod, hybrid_mod)

        rec_mgr = sync_mod.CatalogSyncManager()
        rec_mgr.load_from_payload(a, include_draft=False, include_private=False)
        index.build_from_catalog(rec_mgr.get_flattened_catalog(), save_to_disk=False)

        active_snap = sync_mod.AcceptedSnapshot(
            generation=1,
            content_hash=rec_mgr.compute_hash(a),
            catalog_manager=rec_mgr,
            hybrid_index=index,
            payload=a,
        )
        sync_mod.set_accepted_snapshot(active_snap)

        # Inject disk save failure
        ns["_save_sync_state"] = lambda *args, **kwargs: (_ for _ in ()).throw(OSError("Injected disk failure"))
        ns.update(
            catalog_sync_manager=sync_mod.catalog_sync_manager,
            AcceptedSnapshot=sync_mod.AcceptedSnapshot,
            set_accepted_snapshot=sync_mod.set_accepted_snapshot,
            get_accepted_snapshot=sync_mod.get_accepted_snapshot,
            _current_sync_generation=1,
            _current_sync_hash=active_snap.content_hash,
        )

        with pytest.raises(Exception):
            ns["sync_index"](
                SimpleNamespace(headers={"X-Service-Token": "test-sync-secret-f08"}),
                SimpleNamespace(generation=2, catalog=b, content_hash=rec_mgr.compute_hash(b)),
            )

        current = sync_mod.get_accepted_snapshot()
        assert current.generation == 1
        assert "accepted-A" in titles(current.get_flattened_catalog())
        assert "rejected-B" not in titles(current.get_flattened_catalog())
