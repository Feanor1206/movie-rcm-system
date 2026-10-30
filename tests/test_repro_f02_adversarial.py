"""
Role D: Comprehensive Reviewer and Adversarial Suite for AI-OPT-01-F02.
Independent adversarial verification of:
1. F1: Negation scope and conflict resolution
2. F2: Scorer HTTP error fail-closed & type conformance
3. F3: Production parser resilience and fail-closed bounds
4. Response quality: No overclaiming, no hallucinated fields, no similarity in exact lookups.
"""

import sys
import json
import pytest
from pathlib import Path

# Add paths
root_dir = Path(__file__).resolve().parent.parent
backend_fastapi_dir = root_dir / "backend" / "fastapi"
scripts_dir = root_dir / "scripts"
for p in [str(backend_fastapi_dir), str(scripts_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from services.hybrid_retrieval import HybridMovieIndex
from services.ai_pipeline import ExplanationGeneratorNode
from services.qwen_service import QwenRecommendationService, ModelOutputParseError
from evaluate_benchmark import score_evidence


# =============================================================================
# 1. REVIEWER F1 ADVERSARIAL REPRO
# =============================================================================

def test_reviewer_f1_negation_nonexistent_does_not_reject():
    """F1: 'Jadoo chơi bóng, không phải tập 999' on 2-episode fixture returns ep1."""
    fixture = [
        {"id": "ep_01", "title": "Jadoo chơi bóng", "episode_number": 1, "season_number": 1, "item_type": "episode"},
        {"id": "ep_02", "title": "Jadoo tập 2", "episode_number": 2, "season_number": 1, "item_type": "episode"},
    ]
    idx = HybridMovieIndex()
    idx.build_from_catalog(fixture, save_to_disk=False)

    res = idx.search_hybrid("Jadoo chơi bóng, không phải tập 999", nlu_intent={}, catalog=fixture)
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_01"
    assert res[0]["movie"]["episode_number"] == 1


def test_reviewer_f1_conflict_requested_ep_wins_over_title():
    """F1: 'Jadoo tập 2 Jadoo chơi bóng' on 2-episode fixture ranks ep2 top-1 and records conflict."""
    fixture = [
        {"id": "ep_01", "title": "Jadoo chơi bóng", "episode_number": 1, "season_number": 1, "item_type": "episode"},
        {"id": "ep_02", "title": "Jadoo tập 2", "episode_number": 2, "season_number": 1, "item_type": "episode"},
    ]
    idx = HybridMovieIndex()
    idx.build_from_catalog(fixture, save_to_disk=False)

    res = idx.search_hybrid("Jadoo tập 2 Jadoo chơi bóng", nlu_intent={}, catalog=fixture)
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_02"
    assert res[0]["movie"]["episode_number"] == 2
    assert "conflict" in res[0]["diagnostics"]
    conflict = res[0]["diagnostics"]["conflict"]
    assert conflict["requested_episode"] == 2
    assert conflict["conflicting_episode"] == 1


# =============================================================================
# 2. REVIEWER F2 SCORER FAIL-CLOSED ON HTTP ERRORS
# =============================================================================

def test_reviewer_f2_scorer_http_error_is_failure(tmp_path):
    """
    Reviewer repro F2:
    A mock evidence with 1 unanswerable query returning HTTP 500 error.
    Scorer must NOT count this as a successful rejection (unanswerable_rejected must be 0).
    """
    mock_benchmark = {
        "queries": [
            {
                "id": "eval_test_unans",
                "query": "Doraemon",
                "unanswerable": True,
                "expected_ids": [],
                "expected_type": "movie"
            }
        ]
    }
    mock_evidence = {
        "metadata": {},
        "details": [
            {
                "id": "eval_test_unans",
                "query": "Doraemon",
                "http_status": 500,
                "error": "Server error / timeout",
                "retrieved_ids": [],
                "retrieved_items": []
            }
        ]
    }
    bm_file = tmp_path / "mock_bm.json"
    ev_file = tmp_path / "mock_ev.json"
    bm_file.write_text(json.dumps(mock_benchmark), encoding="utf-8")
    ev_file.write_text(json.dumps(mock_evidence), encoding="utf-8")

    score_result = score_evidence(ev_file, bm_file)
    summary = score_result["summary"]

    assert summary["http_errors"] == 1
    # Must NOT count as successful rejection!
    assert summary["accuracy"]["unanswerable_rejection_rate"] == 0.0
    assert summary["accuracy"]["unanswerable_false_accept_count"] == 1


def test_reviewer_f2_scorer_type_conformance(tmp_path):
    """F2: Scorer properly tracks type conformance for episodes and segments."""
    mock_benchmark = {
        "queries": [
            {
                "id": "q1",
                "query": "Jadoo ep1",
                "unanswerable": False,
                "expected_ids": ["ep_01"],
                "expected_type": "episode"
            }
        ]
    }
    mock_evidence = {
        "metadata": {},
        "details": [
            {
                "id": "q1",
                "query": "Jadoo ep1",
                "http_status": 200,
                "retrieved_ids": ["ep_01"],
                "retrieved_items": [{"id": "ep_01", "item_type": "episode"}]
            }
        ]
    }
    bm_file = tmp_path / "mock_bm2.json"
    ev_file = tmp_path / "mock_ev2.json"
    bm_file.write_text(json.dumps(mock_benchmark), encoding="utf-8")
    ev_file.write_text(json.dumps(mock_evidence), encoding="utf-8")

    score_result = score_evidence(ev_file, bm_file)
    assert score_result["summary"]["accuracy"]["type_conformance_rate"] == 1.0


# =============================================================================
# 3. REVIEWER F3 PRODUCTION PARSER FAIL-CLOSED
# =============================================================================

def test_reviewer_f3_production_parser_garbage_fail_closed():
    """F3: Garbage input raises ModelOutputParseError."""
    with pytest.raises(ModelOutputParseError):
        QwenRecommendationService.extract_and_repair_json("Non json response from LLM")


def test_reviewer_f3_production_parser_repairs_trailing_commas():
    """F3: Production repair handles trailing commas in nested arrays."""
    corrupt = '{"query": {"text": "Jadoo"}, "genres": ["Comedy", "Kids", ], }'
    parsed = QwenRecommendationService.extract_and_repair_json(corrupt)
    assert parsed["query"]["text"] == "Jadoo"
    assert "Kids" in parsed["genres"]


# =============================================================================
# 4. REVIEWER PRESENTATION INVARIANTS
# =============================================================================

def test_reviewer_presentation_invariants():
    """Check all user-facing presentation constraints."""
    explainer = ExplanationGeneratorNode()

    # Invariant 1: No 00:00 for missing segment timestamp
    seg_resp = explainer.generate_explanation(
        [{"id": "s1", "title": "Tiểu phẩm 1", "item_type": "segment", "start_ms": None}],
        {"query": {"text": "Tiểu phẩm 1"}},
        query="Tiểu phẩm 1"
    )
    assert "00:00" not in seg_resp

    # Invariant 2: No 8.0 rating for missing rating
    ep_resp = explainer.generate_explanation(
        [{"id": "e1", "title": "Tập 1", "item_type": "episode", "episode_number": 1, "rating": None}],
        {"query": {"text": "Jadoo tập 1"}},
        query="Jadoo tập 1"
    )
    assert "8.0" not in ep_resp

    # Invariant 3: No 'đã loại trừ hoàn toàn' for non-violent condition
    noviolence_resp = explainer.generate_explanation(
        [{"id": "e2", "title": "Tập 2", "item_type": "episode", "episode_number": 2}],
        {"query": {"text": "Jadoo không có bạo lực"}},
        query="Jadoo không có bạo lực"
    )
    assert "đã loại trừ hoàn toàn" not in noviolence_resp
    assert "chưa ghi nhận cảnh báo bạo lực" in noviolence_resp
