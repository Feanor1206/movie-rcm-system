import json
from pathlib import Path

from services.catalog_sync import CatalogSyncManager
from services.search import SearchService
from services.catalog_sync import AcceptedSnapshot
from services.text_index import TextIndex
from ai.evaluation.retrieval_gate import measure, run_cases
import pytest


ROOT = Path(__file__).resolve().parents[3]


def test_catalog_hierarchy_and_grounded_episode_evaluation(tmp_path):
    payload = json.loads((ROOT / "docs/fixtures/retrieval_catalog.json").read_text(encoding="utf-8"))
    manager = CatalogSyncManager()
    counts = manager.load_from_payload(payload)
    assert counts["series"] == 2 and counts["episodes"] == 2 and counts["scenes"] == 1
    catalog = manager.get_flattened_catalog()
    scene = next(item for item in catalog if item["item_type"] == "scene")
    assert scene["episode_id"] == "ep_chronicles_01" and scene["start_ms"] == 70000
    index = TextIndex.build(catalog, cache_dir=tmp_path, payload=payload)
    snapshot = AcceptedSnapshot(1, manager.content_hash, manager, index, payload)
    service = SearchService()
    cases = [
        {"id": "mars", "query": "Bình Minh Trên Sao Hỏa", "episodeIds": ["ep_chronicles_01"], "source": "legacy-regression"},
        {"id": "ghost", "query": "Đêm Trăng Máu", "episodeIds": ["ep_spooky_01"], "source": "legacy-regression"},
        {"id": "moment", "query": "xe địa hình phóng qua vực đá đỏ", "episodeIds": ["ep_chronicles_01"],
         "moments": [{"episodeId": "ep_chronicles_01", "startMs": 70000}], "source": "legacy-regression"},
    ]
    predictions = run_cases(lambda query: service.search(snapshot, query), cases)
    metrics = measure(cases, predictions)
    assert metrics["recallAt5"] == 1.0 and metrics["mrr"] == 1.0
    assert metrics["momentRecallAt5"] == 1.0


def test_legacy_scenarios_remain_available_for_labeling():
    rows = [json.loads(line) for line in (ROOT / "ai/evaluation/legacy_scenarios.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 140
    assert all(row["source"] == "legacy-regression" and row["originalFile"] for row in rows)


@pytest.mark.parametrize("change", [{"record": {"status": "draft"}}, {"record": {"status": "archived"}}, {"enabled": False}])
def test_scene_summary_excludes_ineligible_text_tracks(change):
    payload = json.loads((ROOT / "docs/fixtures/retrieval_catalog.json").read_text(encoding="utf-8"))
    payload["text_tracks"][0].update(change)
    manager = CatalogSyncManager()
    manager.load_from_payload(payload)
    scene = next(item for item in manager.get_flattened_catalog() if item["item_type"] == "scene")
    assert not scene["dialogue_summary"]


@pytest.mark.parametrize("change", [{"enabled": False}, {"record": {"status": "draft"}}, {"access_policy": "restricted"}])
def test_scene_excludes_ineligible_media_assets(change):
    payload = json.loads((ROOT / "docs/fixtures/retrieval_catalog.json").read_text(encoding="utf-8"))
    asset = next(asset for asset in payload["media_assets"] if asset["id"] == payload["scenes"][0]["media_asset_id"])
    asset.update(change)
    manager = CatalogSyncManager()
    manager.load_from_payload(payload)
    assert not any(item["item_type"] == "scene" for item in manager.get_flattened_catalog())
