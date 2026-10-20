import pytest
import re
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "fastapi")))

from services.catalog_sync import catalog_sync_manager
from services.hybrid_retrieval import (
    HybridMovieIndex,
    split_query_scopes,
    parse_season_episode_intent,
    tokenize_text
)
from services.ai_pipeline import ExplanationGeneratorNode

@pytest.fixture(scope="module")
def catalog_fixture():
    with open("data/catalog.jadoo_all.json", "r", encoding="utf-8") as f:
        pkg = json.load(f)
    catalog_sync_manager.load_from_payload(pkg)
    flat = catalog_sync_manager.get_flattened_catalog()
    index = HybridMovieIndex()
    index.build_from_catalog(flat, save_to_disk=False)
    return index, flat


# =============================================================================
# B1: GENRE/DESCRIPTIVE QUERIES MUST NOT BE REJECTED AS FOREIGN FRANCHISES
# =============================================================================

def test_b1_generic_family_comedy_not_rejected(catalog_fixture):
    """
    B1 Repro: 'Tìm phim hoạt hình gia đình hài hước'
    Must NOT treat 'gia đình hài hước' as a foreign franchise and must NOT return empty.
    """
    index, catalog = catalog_fixture
    nlu_intent = {
        "intent_type": "DISCOVERY",
        "query": {"text": "gia đình hài hước"},
        "raw_query": "Tìm phim hoạt hình gia đình hài hước",
        "constraints": {"include_genres": ["Family", "Comedy"]}
    }
    results = index.search_hybrid("gia đình hài hước", nlu_intent=nlu_intent, catalog=catalog)
    assert len(results) > 0, "Genre/descriptive query must return matching catalog candidates"


def test_b1_fun_for_family_not_rejected(catalog_fixture):
    """
    B1: 'Gợi ý hoạt hình vui nhộn cho gia đình'
    Must NOT be rejected as a foreign franchise.
    """
    index, catalog = catalog_fixture
    nlu_intent = {
        "intent_type": "DISCOVERY",
        "query": {"text": "vui nhộn cho gia đình"},
        "raw_query": "Gợi ý hoạt hình vui nhộn cho gia đình"
    }
    results = index.search_hybrid("vui nhộn cho gia đình", nlu_intent=nlu_intent, catalog=catalog)
    assert len(results) > 0


def test_b1_find_cartoon_jadoo_succeeds(catalog_fixture):
    """
    B1: 'Tìm phim hoạt hình Jadoo' and 'Tìm phim hoạt hình Xin Chào Jadoo'
    Must return Jadoo results.
    """
    index, catalog = catalog_fixture
    for q in ["Tìm phim hoạt hình Jadoo", "Tìm phim hoạt hình Xin Chào Jadoo"]:
        nlu = {"intent_type": "DISCOVERY", "query": {"text": q}, "raw_query": q}
        results = index.search_hybrid(q, nlu_intent=nlu, catalog=catalog)
        assert len(results) > 0
        assert any(r["movie"].get("series_id") == "ser_jadoo" or r["movie"].get("id") == "ser_jadoo" for r in results)


def test_b1_doraemon_abstention_preserved(catalog_fixture):
    """
    B1: 'Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối'
    Must still be rejected (return empty results) because Doraemon is a real external franchise.
    """
    index, catalog = catalog_fixture
    nlu = {
        "intent_type": "DISCOVERY",
        "query": {"text": "bí mật bảo bối"},
        "raw_query": "Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối"
    }
    results = index.search_hybrid("bí mật bảo bối", nlu_intent=nlu, catalog=catalog)
    assert len(results) == 0


def test_b1_negation_doraemon_does_not_reject_jadoo(catalog_fixture):
    """
    B1: 'Tìm Jadoo, không phải Doraemon'
    Must NOT reject because Doraemon is in the negation clause.
    """
    index, catalog = catalog_fixture
    q = "Tìm Jadoo, không phải Doraemon"
    nlu = {"intent_type": "DISCOVERY", "query": {"text": "Tìm Jadoo"}, "raw_query": q}
    results = index.search_hybrid("Tìm Jadoo", nlu_intent=nlu, catalog=catalog)
    assert len(results) > 0


def test_b1_multi_series_catalog_fixture():
    """
    B1: Test with a catalog fixture having another series (e.g. 'Pororo')
    Code must NOT be hardcoded to Jadoo only; it must allow 'Pororo' if Pororo is in catalog.
    """
    dummy_catalog = [
        {
            "id": "ser_pororo",
            "title": "Chú Chim Cánh Cụt Pororo",
            "aliases": ["Pororo", "Pororo The Little Penguin"],
            "item_type": "series",
            "genres": ["Animation", "Family"]
        },
        {
            "id": "ep_pororo_01",
            "series_id": "ser_pororo",
            "title": "Chúng mình là bạn",
            "item_type": "episode",
            "episode_number": 1,
            "season_number": 1,
            "genres": ["Animation"]
        }
    ]
    idx = HybridMovieIndex()
    idx.build_from_catalog(dummy_catalog, save_to_disk=False)

    q = "Tìm phim hoạt hình Pororo"
    nlu = {"intent_type": "DISCOVERY", "query": {"text": "Pororo"}, "raw_query": q}
    results = idx.search_hybrid("Pororo", nlu_intent=nlu, catalog=dummy_catalog)
    assert len(results) > 0, "Must allow series 'Pororo' present in active catalog"
    assert results[0]["movie"]["id"] in ("ser_pororo", "ep_pororo_01")


# =============================================================================
# B2: NEGATION NUMBER MUST NOT BECOME EXACT LOOKUP & GROUNDING CHECK
# =============================================================================

def test_b2_negation_number_not_exact_lookup():
    """
    B2 Repro: 'Jadoo chơi bóng, không phải tập 999'
    Explainer MUST NOT treat this as an exact episode lookup ('Đây là Mùa 1, Tập 30: ...').
    """
    explainer = ExplanationGeneratorNode()
    episode_30 = {
        "id": "ep_jadoo_s01_0030",
        "title": "Không phải ai cũng có thể là người tốt.",
        "item_type": "episode",
        "season_number": 1,
        "episode_number": 30,
        "synopsis": "Tập phim kể về một ngày bình thường của Jadoo."
    }
    intent = {
        "intent_type": "DISCOVERY",
        "query": {"text": "chơi bóng, không phải tập 999"},
        "raw_query": "Jadoo chơi bóng, không phải tập 999"
    }

    res = explainer.generate_explanation(
        ranked_movies=[episode_30],
        nlu_output=intent,
        query="Jadoo chơi bóng, không phải tập 999"
    )

    assert "Đây là Mùa 1, Tập 30" not in res, "Must NOT treat negated number query as exact lookup"
    assert "Đây là Tập 30" not in res


def test_b2_negation_words_not_scored_as_title_keywords(catalog_fixture):
    """
    B2: 'Jadoo chơi bóng, không phải tập 999'
    Retrieval must NOT score 'không phải' as positive title keywords to pick episode 30 ('Không phải ai...').
    """
    index, catalog = catalog_fixture
    q = "Jadoo chơi bóng, không phải tập 999"
    nlu = {"intent_type": "DISCOVERY", "query": {"text": "chơi bóng, không phải tập 999"}, "raw_query": q}
    results = index.search_hybrid("chơi bóng, không phải tập 999", nlu_intent=nlu, catalog=catalog)

    if results:
        top_id = results[0]["movie"]["id"]
        assert top_id != "ep_jadoo_s01_0030", "Negation words 'không phải' must not pick Episode 30 as top result"
        assert results[0]["movie"].get("episode_number") != 9, "Negated 999 must not pick Episode 9"


def test_b2_grounding_real_plot_vs_ungrounded_plot():
    """
    B2 Grounding:
    - Real plot with metadata evidence: states the matching detail.
    - Fabricated plot with no metadata evidence: states no matching episode found.
    """
    explainer = ExplanationGeneratorNode()

    # Case 1: Real plot with provenance in synopsis
    ep_eating = {
        "id": "ep_jadoo_s01_0002",
        "title": "Muốn ăn nhưng lại sợ tăng cân",
        "item_type": "episode",
        "season_number": 1,
        "episode_number": 2,
        "synopsis": "Jadoo muốn ăn đồ ngon nhưng rất sợ bị tăng cân và mập lên."
    }
    intent_real = {
        "intent_type": "DISCOVERY",
        "query": {"text": "muốn ăn nhưng sợ tăng cân"},
        "raw_query": "Tập nào Jadoo muốn ăn ngon nhưng sợ bị tăng cân"
    }
    res_real = explainer.generate_explanation([ep_eating], intent_real, query=intent_real["raw_query"])
    assert "Muốn ăn nhưng lại sợ tăng cân" in res_real
    assert "ăn" in res_real.lower() or "tăng cân" in res_real.lower()

    # Case 2: Ungrounded query with zero metadata evidence
    ep_unrelated = {
        "id": "ep_jadoo_s01_0020",
        "title": "Ngày hè oi ả",
        "item_type": "episode",
        "season_number": 1,
        "episode_number": 20,
        "synopsis": "Thời tiết mùa hè nóng bức khiến mọi người mệt mỏi."
    }
    intent_fake = {
        "intent_type": "DISCOVERY",
        "query": {"text": "lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ"},
        "raw_query": "Tập nào Jadoo lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ"
    }
    res_fake = explainer.generate_explanation([ep_unrelated], intent_fake, query=intent_fake["raw_query"])
    assert "chưa tìm thấy" in res_fake.lower() or "chưa đủ dữ liệu" in res_fake.lower() or "không có" in res_fake.lower()

    # Case 3: Ungrounded query with only 1 coincidental word match ('cá')
    ep_fish = {
        "id": "ep_jadoo_s01_0008",
        "title": "Gương kia, ai đẹp nhất thế gian？",
        "item_type": "episode",
        "season_number": 1,
        "episode_number": 8,
        "synopsis": "Jadoo và các bạn chơi đùa và ngắm nhìn chú cá nhỏ trong bể."
    }
    res_fake_fish = explainer.generate_explanation([ep_fish], intent_fake, query=intent_fake["raw_query"])
    assert "chưa tìm thấy" in res_fake_fish.lower() or "chưa đủ dữ liệu" in res_fake_fish.lower() or "không có" in res_fake_fish.lower()


def test_b2_exact_season_ep_with_negation():
    """
    B2: 'Jadoo mùa 1 tập 1, không phải tập 2'
    Must perform exact lookup on Mùa 1 Tập 1, ignoring negated tập 2.
    """
    explainer = ExplanationGeneratorNode()
    ep_1 = {
        "id": "ep_jadoo_s01_0001",
        "title": "Anh sẽ mua cho em tất cả những gì em muốn ăn.",
        "item_type": "episode",
        "season_number": 1,
        "episode_number": 1,
        "synopsis": "Tập phim Mùa 1 Tập 1."
    }
    intent = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Jadoo mùa 1 tập 1"},
        "raw_query": "Jadoo mùa 1 tập 1, không phải tập 2"
    }
    res = explainer.generate_explanation([ep_1], intent, query=intent["raw_query"])
    assert "Mùa 1" in res and "Tập 1" in res
    assert "Tập 2" not in res
