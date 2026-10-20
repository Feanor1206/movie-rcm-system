import pytest
import re
import json
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "fastapi")))

from services.qwen_service import QwenRecommendationService, ModelOutputParseError
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
# REPRO R3: PARSER TESTS
# =============================================================================

def test_r3_repro1_root_array_containing_object_is_rejected():
    """
    R3 Repro: Input '[{"intent_type":"DISCOVERY"}]' must be rejected as an array,
    NOT sliced from '{' to '}' to trick the parser into accepting a dict.
    """
    input_text = '[{"intent_type":"DISCOVERY"}]'
    with pytest.raises(ModelOutputParseError) as exc_info:
        QwenRecommendationService.extract_and_repair_json(input_text)
    assert "array" in str(exc_info.value).lower() or "object" in str(exc_info.value).lower()


def test_r3_repro2_truncated_string_value_is_rejected():
    """
    R3 Repro: Input '{"query":{"text":"Jadoo không có bạo' was cut off mid-string.
    The parser must NOT silently append quotes/braces to pretend the intent was complete.
    """
    truncated_input = '{"query":{"text":"Jadoo không có bạo'
    with pytest.raises(ModelOutputParseError) as exc_info:
        QwenRecommendationService.extract_and_repair_json(truncated_input)
    err = str(exc_info.value).lower()
    assert "truncated" in err or "unclosed" in err or "parse" in err or "string" in err


def test_r3_trailing_comma_inside_string_is_preserved():
    """
    Trailing comma regex must NOT alter commas or closing braces inside strings.
    """
    input_text = '{"query":{"text":"tập 1, 2, và 3,}"}}'
    parsed = QwenRecommendationService.extract_and_repair_json(input_text)
    assert parsed["query"]["text"] == "tập 1, 2, và 3,}"


def test_r3_markdown_wrapper_is_accepted():
    """
    Markdown code fence wrapped JSON dict must be parsed correctly.
    """
    input_text = '```json\n{"intent_type": "DISCOVERY", "query": {"text": "Jadoo"}}\n```'
    parsed = QwenRecommendationService.extract_and_repair_json(input_text)
    assert parsed["intent_type"] == "DISCOVERY"
    assert parsed["query"]["text"] == "Jadoo"


def test_r3_parse_discovery_intent_with_mock():
    """
    Test parse_discovery_intent with mock tokenizer/model (no GPU required).
    """
    service = QwenRecommendationService()
    service.is_loaded = True
    service.serving_mode = "full"
    service.enable_fallback = False
    service.phase23_adapter_loaded = True
    service.model = MagicMock()
    service.tokenizer = MagicMock()

    # Mock tokenizer output
    service.tokenizer.apply_chat_template.return_value = "<prompt>"
    mock_input_ids = MagicMock()
    mock_input_ids.shape = (1, 10)
    service.tokenizer.return_value = MagicMock(
        input_ids=mock_input_ids,
        to=MagicMock(return_value=MagicMock(input_ids=mock_input_ids))
    )

    # Mock model generate: simulate invalid truncated output
    mock_out_ids = MagicMock()
    mock_out_ids.shape = (1, 15)
    service.model.generate.return_value = mock_out_ids
    service.tokenizer.decode.return_value = '{"query":{"text":"Jadoo không có bạo'

    with pytest.raises(ModelOutputParseError):
        service.parse_discovery_intent("Jadoo không có bạo lực")


# =============================================================================
# REPRO R2: EXPLAINER TESTS
# =============================================================================

def test_r2_repro1_episode_not_called_series_when_query_has_phim_hoat_hinh():
    """
    R2 Repro: Episode fixture 'Bữa cơm gia đình' (Mùa 1, Tập 2).
    Query: 'Tìm phim hoạt hình Jadoo tập 2'
    Currently, substring 'tìm phim hoạt hình' makes explainer call it 'bộ phim hoạt hình ... (Hello Jadoo)'.
    Expected: It MUST be recognized as an episode, not a series!
    """
    node = ExplanationGeneratorNode()
    episode_item = {
        "id": "ep_jadoo_s01_0002",
        "title": "Bữa cơm gia đình",
        "item_type": "episode",
        "season_number": 1,
        "episode_number": 2,
        "synopsis": "Tập phim Bữa cơm gia đình ấm áp."
    }
    intent = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Jadoo tập 2"},
        "raw_query": "Tìm phim hoạt hình Jadoo tập 2"
    }

    explanation = node.generate_explanation(
        ranked_movies=[episode_item],
        nlu_output=intent,
        query="Tìm phim hoạt hình Jadoo tập 2"
    )

    assert "bộ phim hoạt hình Bữa cơm gia đình" not in explanation
    assert "Tập 2" in explanation or "tập 2" in explanation
    assert "(Hello Jadoo)" not in explanation


def test_r2_repro2_missing_violence_condition_reported_on_exact_lookup():
    """
    R2 Repro: Query 'Jadoo mùa 1 tập 2 không có bạo lực'.
    Must explicitly state:
    'Đã tìm thấy tập này, nhưng dữ liệu hiện chưa đủ để xác nhận tập không có bạo lực.'
    (Must NOT omit the condition, and must NOT use 'chưa ghi nhận cảnh báo' as safety assurance).
    """
    node = ExplanationGeneratorNode()
    episode_item = {
        "id": "ep_jadoo_s01_0002",
        "title": "Bữa cơm gia đình",
        "item_type": "episode",
        "season_number": 1,
        "episode_number": 2,
        "synopsis": "Tập phim Bữa cơm gia đình ấm áp."
    }
    intent = {
        "intent_type": "DISCOVERY",
        "query": {"text": "Jadoo mùa 1 tập 2 không có bạo lực"},
        "raw_query": "Jadoo mùa 1 tập 2 không có bạo lực",
        "constraints": {"exclude_genres": ["Violence"]}
    }

    explanation = node.generate_explanation(
        ranked_movies=[episode_item],
        nlu_output=intent,
        query="Jadoo mùa 1 tập 2 không có bạo lực"
    )

    assert "bạo lực" in explanation
    assert "dữ liệu hiện chưa đủ để xác nhận" in explanation.lower() or "chưa đủ để xác nhận" in explanation.lower()
    assert "đã loại trừ hoàn toàn" not in explanation


def test_r2_no_result_neutral_wording_no_hardcoded_franchise():
    """
    No-result branch must use neutral wording, without hardcoded franchise claims.
    """
    node = ExplanationGeneratorNode()
    intent = {"intent_type": "DISCOVERY", "query": {"text": "Phim xyz"}}
    explanation = node.generate_explanation(
        ranked_movies=[],
        nlu_output=intent,
        query="Phim xyz"
    )
    assert "(Hello Jadoo)" not in explanation
    assert "chưa tìm" in explanation.lower() or "không có" in explanation.lower()


# =============================================================================
# REPRO R1: RETRIEVAL & CONFLICT RESOLUTION
# =============================================================================

def test_r1_repro_q09_negation_999_does_not_match_episode_9():
    """
    R1 Repro Q9: 'Jadoo chơi bóng, không phải tập 999'.
    'tập 9' alias MUST NOT match inside 'tập 999' using substring matching.
    """
    pos, neg = split_query_scopes("Jadoo chơi bóng, không phải tập 999")
    pos_sea, pos_ep = parse_season_episode_intent(pos)
    neg_sea, neg_ep = parse_season_episode_intent(neg)

    assert pos_ep is None
    assert neg_ep == 999


def test_r1_repro_q10_raw_query_episode_preserved():
    """
    R1 Repro Q10: User asks 'Jadoo tập 2 Jadoo chơi bóng'.
    Even if Qwen rephrases query.text to omit 'tập 2', the system must preserve
    raw query episode request and not return a segment of episode 8 as top 1.
    """
    raw_query = "Jadoo tập 2 Jadoo chơi bóng"
    pos_scope, _ = split_query_scopes(raw_query)
    _, ep_num = parse_season_episode_intent(pos_scope)
    assert ep_num == 2


def test_r1_repro_q02_exact_title_match_with_trailing_period(catalog_fixture):
    """
    R1 Repro Q2: 'Tìm tập Anh sẽ mua cho em tất cả những gì em muốn ăn'.
    Must retrieve ep_jadoo_s01_0001 even if catalog title has a trailing period,
    and even if Qwen sets reference.status = 'UNRESOLVED_REFERENCE'.
    """
    index, catalog = catalog_fixture
    nlu_intent = {
        "intent_type": "DISCOVERY",
        "query": {"text": "tất cả những gì em muốn ăn"},
        "reference": {
            "text": "Anh sẽ mua cho em tất cả những gì em muốn ăn",
            "status": "UNRESOLVED_REFERENCE"
        },
        "raw_query": "Tìm tập Anh sẽ mua cho em tất cả những gì em muốn ăn"
    }

    results = index.search_hybrid(
        query_text="tất cả những gì em muốn ăn",
        nlu_intent=nlu_intent,
        catalog=catalog
    )

    assert len(results) > 0, "Exact title query must not return empty results"
    assert results[0]["movie"]["id"] == "ep_jadoo_s01_0001"


def test_r1_repro_q08_doraemon_foreign_franchise_is_rejected(catalog_fixture):
    """
    R1 Repro Q8: 'Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối'.
    Must NOT return ep_jadoo_s03_0009 ('Bí Mật') as the answer to a Doraemon request.
    Must abstain (return empty results) so user does not get the wrong movie card.
    """
    index, catalog = catalog_fixture
    nlu_intent = {
        "intent_type": "DISCOVERY",
        "query": {"text": "bí mật bảo bối"},
        "reference": {"text": "Bí Mật", "status": "CLEAR_REFERENCE_TEXT"},
        "raw_query": "Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối"
    }

    results = index.search_hybrid(
        query_text="bí mật bảo bối",
        nlu_intent=nlu_intent,
        catalog=catalog
    )

    if results:
        top_id = results[0]["movie"]["id"]
        assert top_id != "ep_jadoo_s03_0009", "Must NOT return Jadoo Bí Mật for a Doraemon query"
        assert False, f"Expected empty results for out-of-catalog Doraemon, got: {top_id}"


def test_r1_repro_q09_negation_999_does_not_return_episode_9(catalog_fixture):
    """
    R1 Repro Q9: 'Jadoo chơi bóng, không phải tập 999'.
    Must NOT return Episode 9 ('Tuyển tập...') due to 'tập 9' substring in 'tập 999'.
    """
    index, catalog = catalog_fixture
    nlu_intent = {
        "intent_type": "DISCOVERY",
        "query": {"text": "chơi bóng, không phải tập 999"},
        "raw_query": "Jadoo chơi bóng, không phải tập 999"
    }

    results = index.search_hybrid(
        query_text="chơi bóng, không phải tập 999",
        nlu_intent=nlu_intent,
        catalog=catalog
    )

    if results:
        top_ep = results[0]["movie"].get("episode_number")
        assert top_ep != 9, "Negation 'tập 999' must NOT boost Episode 9"

