"""
Unit & Regression Test Suite for USABILITY-01:
Tests the 12-query catalog-grounded matrix:
1. Exact Title 1 ('Anh sẽ mua cho em...') -> exactly 1 card (ep_jadoo_s01_0001)
2. Exact Title 2 ('Muốn ăn nhưng lại sợ tăng cân') -> exactly 1 card (ep_jadoo_s01_0002)
3. Exact Season/Ep 1 ('Xin Chào Jadoo Mùa 1 Tập 1') -> exactly 1 card (ep_jadoo_s01_0001, no S3 or S6 secondary cards)
4. Exact Season/Ep 2 ('Jadoo Mùa 3 Tập 1') -> exactly 1 card (ep_jadoo_s03_0001, distinct from S1 E1)
5. Plot Proven 1 ('muốn ăn ngon nhưng sợ bị tăng cân') -> ep_jadoo_s01_0002 with plot facts
6. Plot Proven 2 ('học sinh mới E-cha với tô mì bí truyền') -> ep_jadoo_s01_0011 with E-cha synopsis
7. Segment Timestamp ('Truyện ngắn Cứu cá vàng và cuộc tình với chàng Romy') -> seg_jadoo_s01_008a
8. Genre Discovery ('Tìm phim hoạt hình gia đình hài hước') -> 1-3 candidates, not rejected
9. Negation Scope ('Jadoo chơi bóng, không phải tập 999') -> 0 cards, truthful abstention
10. Foreign Franchise ('Cho tôi xem phim hoạt hình Doraemon...') -> 0 cards, foreign franchise abstention
11. Fabricated Plot ('lái tàu ngầm xuống đáy đại dương bắt cá mập trắng') -> 0 cards, neutral follow-ups
12. Unverified Condition ('phát hành năm 2021 không có bạo lực') -> unverified condition note included
"""

import pytest
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "fastapi")))

from services.catalog_sync import catalog_sync_manager
from services.ai_pipeline import CascadingAIPipeline


@pytest.fixture(scope="module")
def jadoo_catalog_fixture():
    with open("data/catalog.jadoo_all.json", "r", encoding="utf-8") as f:
        pkg = json.load(f)
    catalog_sync_manager.load_from_payload(pkg)
    flat = catalog_sync_manager.get_flattened_catalog()
    return flat


# =============================================================================
# 1 & 2: EXACT TITLE LOOKUP (MUST RETURN EXACTLY 1 CARD)
# =============================================================================

def test_u01_exact_title_1(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Tìm tập Anh sẽ mua cho em tất cả những gì em muốn ăn"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Anh sẽ mua cho em tất cả những gì em muốn ăn"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    recs = res["recommendedMovies"]
    assert len(recs) == 1, f"Exact title lookup must return exactly 1 card, got {len(recs)}"
    assert recs[0]["id"] == "ep_jadoo_s01_0001"
    assert "Anh sẽ mua cho em" in res["text"]


def test_u01_exact_title_2(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Tìm tập Muốn ăn nhưng lại sợ tăng cân"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Muốn ăn nhưng lại sợ tăng cân"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    recs = res["recommendedMovies"]
    assert len(recs) == 1, f"Exact title lookup must return exactly 1 card, got {len(recs)}"
    assert recs[0]["id"] == "ep_jadoo_s01_0002"
    assert "Muốn ăn nhưng lại sợ tăng cân" in res["text"]


# =============================================================================
# 3 & 4: EXACT SEASON/EPISODE (MUST PRUNE SECONDARY MISMATCHED SEASONS)
# =============================================================================

def test_u01_exact_season_ep_s01e01(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Xin Chào Jadoo Mùa 1 Tập 1"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Xin Chào Jadoo Mùa 1 Tập 1"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    recs = res["recommendedMovies"]
    assert len(recs) == 1, f"Exact Season 1 Episode 1 must return exactly 1 card, got {len(recs)}"
    assert recs[0]["id"] == "ep_jadoo_s01_0001"
    assert recs[0].get("season_number") == 1
    assert recs[0].get("episode_number") == 1
    assert "Mùa 1, Tập 1" in res["text"]


def test_u01_exact_season_ep_s03e01(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Jadoo Mùa 3 Tập 1"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Jadoo Mùa 3 Tập 1"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    recs = res["recommendedMovies"]
    assert len(recs) == 1, f"Exact Season 3 Episode 1 must return exactly 1 card, got {len(recs)}"
    assert recs[0]["id"] == "ep_jadoo_s03_0001"
    assert recs[0].get("season_number") == 3
    assert recs[0].get("episode_number") == 1
    assert "Mùa 3, Tập 1" in res["text"]
    assert "Chào chồng tương lai" in res["text"]


# =============================================================================
# 5 & 6: PROVEN PLOT QUERIES (METADATA EVIDENCE IN SYNOPSIS / FACTS)
# =============================================================================

def test_u01_plot_proven_diet(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Tập nào Jadoo muốn ăn ngon nhưng sợ bị tăng cân"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "muốn ăn ngon nhưng sợ bị tăng cân"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    recs = res["recommendedMovies"]
    assert len(recs) >= 1
    assert recs[0]["id"] == "ep_jadoo_s01_0002"
    assert "Muốn ăn nhưng lại sợ tăng cân" in res["text"]


def test_u01_plot_proven_echa_noodle(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Tập phim có học sinh mới E-cha với tô mì bí truyền"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "học sinh mới E-cha với tô mì bí truyền"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    recs = res["recommendedMovies"]
    assert len(recs) >= 1
    # Both the parent episode (ep 11) and the specific segment (seg 11a "Tô mì bí truyền của học sinh mới E-cha") are valid
    assert recs[0]["id"] in ("ep_jadoo_s01_0011", "seg_jadoo_s01_011a")


# =============================================================================
# 7: SEGMENT WITH TIMESTAMP
# =============================================================================

def test_u01_segment_timestamp(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Truyện ngắn Cứu cá vàng và cuộc tình với chàng Romy"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Cứu cá vàng và cuộc tình với chàng Romy"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    recs = res["recommendedMovies"]
    assert len(recs) >= 1
    assert recs[0]["id"] == "seg_jadoo_s01_008a"
    assert recs[0]["item_type"] == "segment"
    assert "Gương kia" in res["text"]
    assert "Mốc thời gian" in res["text"]


# =============================================================================
# 8: GENRE DISCOVERY
# =============================================================================

def test_u01_genre_discovery(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Tìm phim hoạt hình gia đình hài hước"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "hoạt hình gia đình hài hước"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    recs = res["recommendedMovies"]
    assert len(recs) >= 1, "Genre discovery must return recommended candidates"
    assert "chưa tìm thấy" not in res["text"].lower()


# =============================================================================
# 9, 10, 11: NEGATION, FOREIGN FRANCHISE, UNGROUNDED ABSTENTIONS
# =============================================================================

def test_u01_negation_scope(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Jadoo chơi bóng, không phải tập 999"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "chơi bóng, không phải tập 999"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    assert len(res["recommendedMovies"]) == 0, "No ball playing in catalog: must return 0 cards"
    assert res["pipelineStages"]["rankedCount"] == 0
    assert "chưa tìm thấy" in res["text"].lower() or "không khớp" in res["text"].lower()


def test_u01_foreign_franchise(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Doraemon tập dài bí mật bảo bối"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    assert len(res["recommendedMovies"]) == 0
    assert res["pipelineStages"]["rankedCount"] == 0
    assert "không có trong hệ thống" in res["text"].lower() or "chưa tìm thấy" in res["text"].lower()


def test_u01_fabricated_plot(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Tập nào Jadoo lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ"
    nlu_mock = {
        "intent_type": "DISCOVERY",
        "query": {"text": "lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ"},
        "raw_query": q
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    assert len(res["recommendedMovies"]) == 0
    assert res["pipelineStages"]["rankedCount"] == 0
    assert "chưa tìm thấy" in res["text"].lower()
    follow_str = json.dumps(res.get("followUps", []), ensure_ascii=False).lower()
    assert "gương kia" not in follow_str
    assert "ep_jadoo_s01_0008" not in follow_str


# =============================================================================
# 12: UNVERIFIED ADVISORY CONDITION
# =============================================================================

def test_u01_unverified_condition_violence(jadoo_catalog_fixture):
    pipeline = CascadingAIPipeline()
    q = "Phim hoạt hình Jadoo phát hành năm 2021 không có bạo lực"
    nlu_mock = {
        "schema_version": "1.0",
        "intent_type": "DISCOVERY",
        "query": {"text": "Phim hoạt hình Jadoo phát hành năm 2021 không có bạo lực"},
        "raw_query": q,
        "constraints": {"year_min": 2021, "year_max": 2021, "include_genres": ["Animation"], "exclude_genres": ["Violence"]},
        "year_min": 2021,
        "year_max": 2021,
        "include_genres": ["Animation"],
        "exclude_genres": ["Violence"]
    }
    res = pipeline.run(q, catalog=jadoo_catalog_fixture, nlu_intent=nlu_mock)
    recs = res["recommendedMovies"]
    assert len(recs) >= 1
    assert "chưa đủ để xác nhận" in res["text"].lower()
    assert (recs[0].get("release_year") == 2021 or recs[0].get("year") == 2021)
