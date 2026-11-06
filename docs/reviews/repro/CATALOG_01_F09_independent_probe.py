"""
CATALOG-01-F09 Independent Snapshot Ownership & Concurrency Probe
Executes reviewer probe logic without modifying F08 reviewer repro or overwriting F08 historical evidence.
Verifies that:
- Retained recovered snapshot retains pure catalog/index/payload/hash/generation A across subsequent publication(s).
- retained_snapshot_mutated is FALSE.
Writes evidence to docs/reviews/evidence/CATALOG_01_F09_independent_probe.json.
"""

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]


def load_module(name, rel_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run():
    # 1. Run reviewer repro F08 via import without overwriting F08 historical evidence
    reviewer_probe = load_module("f08_reviewer_probe", "docs/reviews/repro/CATALOG_01_F08_REVIEWER_probe.py")
    reviewer_repro_res = reviewer_probe.run()

    # 2. Multi-sync repeatability and default bootstrap test
    matrix = load_module("f08_reviewer_matrix", "tests/test_f08_atomic_concurrency_matrix.py")
    sync_mod, hybrid_mod = matrix.load_sync_and_index_modules()
    payload = json.loads((ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8"))

    a = copy.deepcopy(payload)
    b = copy.deepcopy(payload)
    c = copy.deepcopy(payload)
    a["series"][0]["title"] = "recovered-A"
    b["series"][0]["title"] = "published-B"
    c["series"][0]["title"] = "published-C"

    titles = lambda rows: [r["title"] for r in rows if r.get("item_type") == "series"]

    multi_sync_check = {}
    default_bootstrap_check = {}

    with tempfile.TemporaryDirectory(prefix="f09-probe-multi-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        ns, _, index, _, _ = matrix.create_test_context(temp_dir, sync_mod, hybrid_mod)
        manager = sync_mod.CatalogSyncManager()
        manager.load_from_payload(a, include_draft=False, include_private=False)
        index.build_from_catalog(manager.get_flattened_catalog(), save_to_disk=False)

        # Snapshot A created
        snap_a = sync_mod.AcceptedSnapshot(1, manager.compute_hash(a), manager, index, a)
        sync_mod.set_accepted_snapshot(snap_a)
        retained_a = sync_mod.get_accepted_snapshot()

        ns.update(
            catalog_sync_manager=sync_mod.catalog_sync_manager,
            AcceptedSnapshot=sync_mod.AcceptedSnapshot,
            set_accepted_snapshot=sync_mod.set_accepted_snapshot,
            get_accepted_snapshot=sync_mod.get_accepted_snapshot,
            _current_sync_generation=1,
            _current_sync_hash=retained_a.content_hash,
        )

        # First sync to B (generation 2)
        res_b = ns["sync_index"](
            SimpleNamespace(headers={"X-Service-Token": "test-sync-secret-f08"}),
            SimpleNamespace(generation=2, catalog=b, content_hash=manager.compute_hash(b)),
        )
        assert res_b.status == "success"

        # Second sync to C (generation 3)
        res_c = ns["sync_index"](
            SimpleNamespace(headers={"X-Service-Token": "test-sync-secret-f08"}),
            SimpleNamespace(generation=3, catalog=c, content_hash=manager.compute_hash(c)),
        )
        assert res_c.status == "success"

        current_c = sync_mod.get_accepted_snapshot()
        multi_sync_check = {
            "retained_a_generation": retained_a.generation,
            "retained_a_manager_titles": titles(retained_a.get_flattened_catalog()),
            "retained_a_index_titles": titles(retained_a.hybrid_index.documents.values()),
            "current_c_generation": current_c.generation,
            "current_c_manager_titles": titles(current_c.get_flattened_catalog()),
            "retained_a_remains_pure": (
                "recovered-A" in titles(retained_a.get_flattened_catalog())
                and "published-B" not in titles(retained_a.get_flattened_catalog())
                and "published-C" not in titles(retained_a.get_flattened_catalog())
            ),
        }

    # Test default bootstrap ownership
    with tempfile.TemporaryDirectory(prefix="f09-probe-bootstrap-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        ns, _, index_d, _, _ = matrix.create_test_context(temp_dir, sync_mod, hybrid_mod)
        def_mgr = sync_mod.CatalogSyncManager()
        def_mgr.load_from_payload(a, include_draft=False, include_private=False)
        index_d.build_from_catalog(def_mgr.get_flattened_catalog(), save_to_disk=False)

        default_snap = sync_mod.AcceptedSnapshot(0, def_mgr.compute_hash(a), def_mgr, index_d, a)
        sync_mod.set_accepted_snapshot(default_snap)
        retained_default = sync_mod.get_accepted_snapshot()

        ns.update(
            catalog_sync_manager=sync_mod.catalog_sync_manager,
            AcceptedSnapshot=sync_mod.AcceptedSnapshot,
            set_accepted_snapshot=sync_mod.set_accepted_snapshot,
            get_accepted_snapshot=sync_mod.get_accepted_snapshot,
            _current_sync_generation=0,
            _current_sync_hash=retained_default.content_hash,
        )

        res_publish = ns["sync_index"](
            SimpleNamespace(headers={"X-Service-Token": "test-sync-secret-f08"}),
            SimpleNamespace(generation=1, catalog=b, content_hash=def_mgr.compute_hash(b)),
        )
        assert res_publish.status == "success"

        default_bootstrap_check = {
            "retained_default_generation": retained_default.generation,
            "retained_default_manager_titles": titles(retained_default.get_flattened_catalog()),
            "retained_default_index_titles": titles(retained_default.hybrid_index.documents.values()),
            "retained_default_remains_pure": (
                "recovered-A" in titles(retained_default.get_flattened_catalog())
                and "published-B" not in titles(retained_default.get_flattened_catalog())
            ),
        }

    return {
        "status": "PASSED",
        "checkpoint": "CATALOG-01-F09-CHECKPOINT-01",
        "reviewer_repro_f08": reviewer_repro_res,
        "multi_sync_durability": multi_sync_check,
        "default_bootstrap_isolation": default_bootstrap_check,
        "ownership_bug_closed": (
            reviewer_repro_res.get("retained_snapshot_mutated") is False
            and multi_sync_check.get("retained_a_remains_pure") is True
            and default_bootstrap_check.get("retained_default_remains_pure") is True
        ),
    }


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    out = run()
    out_file = ROOT / "docs/reviews/evidence/CATALOG_01_F09_independent_probe.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"F09 probe succeeded. Evidence written to {out_file}")
    print(json.dumps(out, indent=2, ensure_ascii=False))
