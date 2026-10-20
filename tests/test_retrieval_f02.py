"""
Regression and Adversarial Tests for Role A (Retrieval F02).
Tests:
- Scope splitting for negation vs positive target
- Review F1 Repro 1: 'Jadoo chơi bóng, không phải tập 999' on reviewer's 2-episode fixture
- Review F1 Repro 2: 'Jadoo tập 2 Jadoo chơi bóng' conflict resolution on reviewer's 2-episode fixture
- Real catalog tests: scope negation, nonexistent episode/season in positive scope vs negative scope
"""

import sys
import json
import pytest
from pathlib import Path

# Add backend/fastapi to sys.path
backend_fastapi_dir = Path(__file__).resolve().parent.parent / "backend" / "fastapi"
if str(backend_fastapi_dir) not in sys.path:
    sys.path.insert(0, str(backend_fastapi_dir))

from services.catalog_sync import CatalogSyncManager
from services.hybrid_retrieval import (
    HybridMovieIndex,
    split_query_scopes,
    parse_season_episode_intent
)


@pytest.fixture(scope="session")
def reviewer_fixture():
    """
    Reviewer repro fixture from AI_OPT_01_F01_REVIEW.md:
    Episode 1: 'Jadoo chơi bóng'
    Episode 2: 'Jadoo tập 2'
    """
    return [
        {
            "id": "ep_reviewer_01",
            "title": "Jadoo chơi bóng",
            "episode_number": 1,
            "season_number": 1,
            "item_type": "episode",
            "rating": None
        },
        {
            "id": "ep_reviewer_02",
            "title": "Jadoo tập 2",
            "episode_number": 2,
            "season_number": 1,
            "item_type": "episode",
            "rating": None
        }
    ]


@pytest.fixture(scope="session")
def reviewer_index(reviewer_fixture):
    idx = HybridMovieIndex()
    idx.build_from_catalog(reviewer_fixture, save_to_disk=False)
    return idx


@pytest.fixture(scope="session")
def real_catalog_items():
    catalog_path = Path(__file__).resolve().parent.parent / "data" / "catalog.jadoo_all.json"
    with open(catalog_path, "r", encoding="utf-8") as f:
        raw_catalog = json.load(f)
    mgr = CatalogSyncManager()
    mgr.load_from_payload(raw_catalog)
    return mgr.get_flattened_catalog()


@pytest.fixture(scope="session")
def real_hybrid_index(real_catalog_items):
    idx = HybridMovieIndex()
    idx.build_from_catalog(real_catalog_items, save_to_disk=False)
    return idx


# =============================================================================
# 1. SCOPE SPLITTING TESTS
# =============================================================================

def test_scope_split_simple_negation():
    pos, neg = split_query_scopes("Jadoo chơi bóng, không phải tập 999")
    assert "Jadoo chơi bóng" in pos
    assert "tập 999" in neg


def test_scope_split_tru_negation():
    pos, neg = split_query_scopes("Tìm phim Jadoo trừ mùa 2")
    assert "Tìm phim Jadoo" in pos
    assert "mùa 2" in neg


def test_scope_split_no_negation():
    pos, neg = split_query_scopes("Xin Chào Jadoo Mùa 1 Tập 1")
    assert pos == "Xin Chào Jadoo Mùa 1 Tập 1"
    assert neg == ""


# =============================================================================
# 2. REVIEWER F1 REPRO FIXTURE TESTS (FROM AI_OPT_01_F01_REVIEW.md)
# =============================================================================

def test_f1_repro1_negation_nonexistent_ep_does_not_reject(reviewer_index, reviewer_fixture):
    """
    Reviewer repro 1: 'Jadoo chơi bóng, không phải tập 999'
    Previously returned [] because 999 was treated as a target episode and didn't exist.
    Now: 999 is in exclusion scope, positive scope finds episode 1 ('Jadoo chơi bóng').
    """
    res = reviewer_index.search_hybrid(
        query_text="Jadoo chơi bóng, không phải tập 999",
        nlu_intent={"query": {"text": "Jadoo chơi bóng, không phải tập 999"}},
        catalog=reviewer_fixture
    )
    assert len(res) > 0, "Query must not return empty list!"
    top_ep = res[0]["movie"]
    assert top_ep["id"] == "ep_reviewer_01"
    assert top_ep.get("episode_number") == 1


def test_f1_repro2_conflict_episode_number_and_title(reviewer_index, reviewer_fixture):
    """
    Reviewer repro 2: 'Jadoo tập 2 Jadoo chơi bóng'
    User explicitly asks for 'tập 2', but 'Jadoo chơi bóng' is Episode 1's title.
    Now: Episode 2 must be ranked #1 because user explicitly asked for episode 2,
    and a conflict must be recorded in diagnostics.
    """
    res = reviewer_index.search_hybrid(
        query_text="Jadoo tập 2 Jadoo chơi bóng",
        nlu_intent={"query": {"text": "Jadoo tập 2 Jadoo chơi bóng"}},
        catalog=reviewer_fixture
    )
    assert len(res) > 0
    top = res[0]
    top_ep = top["movie"]
    # Episode 2 should be ranked top-1
    assert top_ep["id"] == "ep_reviewer_02"
    assert top_ep.get("episode_number") == 2
    # Diagnostics must record the detected conflict
    assert "conflict" in top["diagnostics"]
    conflict = top["diagnostics"]["conflict"]
    assert conflict["requested_episode"] == 2
    assert conflict["conflicting_episode"] == 1
    assert conflict["conflicting_title"] == "Jadoo chơi bóng"


# =============================================================================
# 3. REAL CATALOG BEHAVIOR TESTS
# =============================================================================

def test_positive_nonexistent_season_still_abstains(real_hybrid_index, real_catalog_items):
    """Explicitly asking for nonexistent season 99 must abstain cleanly."""
    res = real_hybrid_index.search_hybrid(
        query_text="Jadoo Mùa 99",
        nlu_intent={"query": {"text": "Jadoo Mùa 99"}},
        catalog=real_catalog_items
    )
    assert len(res) == 0


def test_positive_nonexistent_episode_still_abstains(real_hybrid_index, real_catalog_items):
    """Explicitly asking for nonexistent episode 999 in positive scope must abstain cleanly."""
    res = real_hybrid_index.search_hybrid(
        query_text="Jadoo tập 999",
        nlu_intent={"query": {"text": "Jadoo tập 999"}},
        catalog=real_catalog_items
    )
    assert len(res) == 0


def test_exclusion_filters_out_specific_episode(real_hybrid_index, real_catalog_items):
    """'Jadoo Mùa 1, không xem tập 1' should not return Episode 1 as top result."""
    res = real_hybrid_index.search_hybrid(
        query_text="Jadoo Mùa 1, không xem tập 1",
        nlu_intent={"query": {"text": "Jadoo Mùa 1, không xem tập 1"}},
        catalog=real_catalog_items
    )
    assert len(res) > 0
    returned_ep_numbers = [r["movie"].get("episode_number") for r in res]
    assert 1 not in returned_ep_numbers[:3]
