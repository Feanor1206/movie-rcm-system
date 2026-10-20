import pytest
import re
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "fastapi")))

from services.catalog_sync import catalog_sync_manager
from services.hybrid_retrieval import HybridMovieIndex
from services.ai_pipeline import CascadingAIPipeline


@pytest.fixture(scope="module")
def jadoo_catalog_fixture():
    with open("data/catalog.jadoo_all.json", "r", encoding="utf-8") as f:
        pkg = json.load(f)
    catalog_sync_manager.load_from_payload(pkg)
    flat = catalog_sync_manager.get_flattened_catalog()
    return flat


# =============================================================================
# C1: REPRO TEST — ABSTENTION MUST YIELD EMPTY CARDS AND NEUTRAL FOLLOWUPS
# =============================================================================

def test_c1_fabricated_plot_pipeline_abstains_consistently(jadoo_catalog_fixture):
    """
    C1 Repro: 'Tập nào Jadoo lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ'
    When explanation says 'Hiện chưa tìm thấy...', recommendedMovies MUST be empty,
    rankedCount MUST be 0, and followUps MUST NOT mention rejected cards (e.g. ep 8).
    """
    pipeline = CascadingAIPipeline()
    q = "Tập nào Jadoo lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ"},
        "raw_query": q
    }

    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)

    # C1 Assertions:
    assert len(res["recommendedMovies"]) == 0, (
        f"C1 Failure: recommendedMovies must be empty for ungrounded plot query, but got {len(res['recommendedMovies'])} items: "
        f"{[m.get('id') for m in res['recommendedMovies']]}"
    )
    assert res["pipelineStages"]["rankedCount"] == 0, "rankedCount must be 0 when no grounded candidates exist"
    assert "chưa tìm thấy" in res["text"].lower(), f"Explanation should state no matching episode found, got: {res['text']}"

    # Follow-ups must not reference rejected candidate cards
    follow_str = json.dumps(res.get("followUps", []), ensure_ascii=False).lower()
    assert "gương kia" not in follow_str, "Follow-ups must not reference rejected episode 8"
    assert "ep_jadoo_s01_0008" not in follow_str


# =============================================================================
# C2: REPRO TEST — TWO-TOKEN QUERY WITH GENERIC ACTION VERB ('CHƠI BÓNG')
# =============================================================================

def test_c2_two_token_generic_verb_does_not_ground_unrelated_item(jadoo_catalog_fixture):
    """
    C2 Repro: 'Jadoo chơi bóng, không phải tập 999'
    In catalog, ep_jadoo_s04_0015 is 'Đừng chơi, hãy học' with no ball playing.
    Matching only the generic verb 'chơi' without 'bóng' MUST NOT count as grounding.
    """
    pipeline = CascadingAIPipeline()
    q = "Jadoo chơi bóng, không phải tập 999"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "chơi bóng, không phải tập 999"},
        "raw_query": q
    }

    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)

    # In current real catalog, there is no ball playing episode.
    # Therefore, ep_jadoo_s04_0015 must NOT be returned as a valid grounded match!
    rec_ids = [m.get("id") for m in res["recommendedMovies"]]
    assert "ep_jadoo_s04_0015" not in rec_ids, "C2 Failure: ep_jadoo_s04_0015 must not match 'chơi bóng' merely because title has 'chơi'"
    assert len(res["recommendedMovies"]) == 0, f"Expected 0 grounded movies, got {rec_ids}"
    assert "chưa tìm thấy" in res["text"].lower(), f"Explanation should state no matching episode found, got: {res['text']}"


def test_c2_positive_grounding_fixture_with_real_ball_playing():
    """
    C2 Positive Fixture:
    Catalog contains an episode that genuinely has ball playing in its synopsis and facts.
    Query 'Jadoo chơi bóng, không phải tập 999' MUST successfully match and ground on that episode.
    """
    custom_catalog = [
        {
            "id": "ep_dummy_no_ball",
            "title": "Đừng chơi, hãy học",
            "item_type": "episode",
            "episode_number": 15,
            "season_number": 4,
            "synopsis": "Tập phim Đừng chơi hãy học về việc học tập của các bạn nhỏ.",
            "plot_facts": [],
            "genres": ["Animation", "Family"]
        },
        {
            "id": "ep_dummy_real_ball",
            "title": "Giải đấu bóng trường học",
            "item_type": "episode",
            "episode_number": 25,
            "season_number": 1,
            "synopsis": "Jadoo cùng các bạn tham gia trận đấu chơi bóng né và ném bóng đầy kịch tính.",
            "plot_facts": ["Jadoo ném bóng chính xác để cứu đồng đội"],
            "genres": ["Animation", "Family", "Sports"]
        }
    ]

    pipeline = CascadingAIPipeline()
    q = "Jadoo chơi bóng, không phải tập 999"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "chơi bóng, không phải tập 999"},
        "raw_query": q
    }

    res = pipeline.run(q, catalog=custom_catalog, nlu_intent=nlu_mock)

    assert len(res["recommendedMovies"]) == 1, f"Expected 1 grounded movie, got {len(res['recommendedMovies'])}"
    assert res["recommendedMovies"][0]["id"] == "ep_dummy_real_ball"
    assert "Giải đấu bóng trường học" in res["text"]
    assert "bóng" in res["text"].lower()


def test_c2_general_multi_series_counterexample():
    """
    C2 Generalization / Reviewer Counterexample:
    Test on another series 'Pororo' (not hardcoded to Jadoo):
    Query: 'Pororo đi câu cá' (action='đi', object='câu cá').
    Episode title has 'Đừng đi lung tung' (matches only 'đi').
    Must NOT be treated as a grounded match for 'câu cá'.
    """
    pororo_catalog = [
        {
            "id": "ep_pororo_wandering",
            "title": "Đừng đi lung tung",
            "item_type": "episode",
            "episode_number": 5,
            "synopsis": "Pororo và Crong được khuyên không nên đi lung tung một mình trong rừng.",
            "plot_facts": [],
            "genres": ["Animation"]
        }
    ]

    pipeline = CascadingAIPipeline()
    q = "Pororo đi câu cá"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Pororo đi câu cá"},
        "raw_query": q
    }

    res = pipeline.run(q, catalog=pororo_catalog, nlu_intent=nlu_mock)

    assert len(res["recommendedMovies"]) == 0, "Must not ground on 'Đừng đi lung tung' when 'câu cá' is absent"
    assert "chưa tìm thấy" in res["text"].lower()


# =============================================================================
# CONTROL TESTS (EXACT LOOKUPS & GENRE QUERIES MUST REMAIN GROUNDED)
# =============================================================================

def test_control_exact_title_pipeline(jadoo_catalog_fixture):
    """Exact title match must remain grounded and return correct episode card."""
    pipeline = CascadingAIPipeline()
    q = "Tìm tập Anh sẽ mua cho em tất cả những gì em muốn ăn"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Anh sẽ mua cho em tất cả những gì em muốn ăn"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    assert len(res["recommendedMovies"]) > 0
    assert res["recommendedMovies"][0]["id"] == "ep_jadoo_s01_0001"
    assert "Anh sẽ mua cho em" in res["text"]


def test_control_exact_season_ep_pipeline(jadoo_catalog_fixture):
    """Exact season/episode must remain grounded and return correct episode card."""
    pipeline = CascadingAIPipeline()
    q = "Xin Chào Jadoo Mùa 1 Tập 1"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Xin Chào Jadoo Mùa 1 Tập 1"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    assert len(res["recommendedMovies"]) > 0
    assert res["recommendedMovies"][0]["id"] == "ep_jadoo_s01_0001"
    assert "Mùa 1" in res["text"] and "Tập 1" in res["text"]


def test_control_generic_family_comedy_pipeline(jadoo_catalog_fixture):
    """Generic descriptive/genre query must remain grounded and return recommended movies."""
    pipeline = CascadingAIPipeline()
    q = "Tìm phim hoạt hình gia đình hài hước"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "gia đình hài hước"},
        "raw_query": q,
        "constraints": {"include_genres": ["Family", "Comedy"]}
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    assert len(res["recommendedMovies"]) > 0, "Generic genre queries must return recommendation cards"
    assert "Hiện chưa tìm thấy" not in res["text"]


def test_control_segment_lookup_pipeline(jadoo_catalog_fixture):
    """Segment lookup must remain grounded and return segment card."""
    pipeline = CascadingAIPipeline()
    q = "Truyện ngắn Cứu cá vàng và cuộc tình với chàng Romy"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Cứu cá vàng và cuộc tình với chàng Romy"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    assert len(res["recommendedMovies"]) > 0
    assert res["recommendedMovies"][0]["id"] == "seg_jadoo_s01_008a"
    assert "Cứu cá vàng" in res["text"]


def test_control_doraemon_abstention_pipeline(jadoo_catalog_fixture):
    """Foreign franchise query must return 0 cards and abstention text."""
    pipeline = CascadingAIPipeline()
    q = "Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "phim hoạt hình Doraemon tập dài bí mật bảo bối"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    assert len(res["recommendedMovies"]) == 0
    assert "chưa tìm thấy" in res["text"].lower() or "không có trong hệ thống" in res["text"].lower()
