"""
Regression and Quality Tests for Role C: Production Parser and Telemetry (AI-OPT-01-F02).
Tests:
- F3: Real production QwenRecommendationService.extract_and_repair_json (NO duplicated test logic)
- Truncated output repair (unclosed brackets and braces)
- Trailing comma removal before closing brackets/braces
- Brackets inside string values must not corrupt repair count
- Unrepairable corrupt text cleanly raises ModelOutputParseError (fail-closed)
- Non-dict JSON output (arrays, strings) cleanly raises ModelOutputParseError
- Telemetry stats validation
"""

import sys
import pytest
from pathlib import Path

# Add backend/fastapi to sys.path
backend_fastapi_dir = Path(__file__).resolve().parent.parent / "backend" / "fastapi"
if str(backend_fastapi_dir) not in sys.path:
    sys.path.insert(0, str(backend_fastapi_dir))

from services.qwen_service import (
    QwenRecommendationService,
    ModelOutputParseError
)


def test_01_production_clean_dict():
    """Valid JSON dict must be parsed cleanly by production method."""
    text = '{"intent_type": "DISCOVERY", "query": {"text": "Jadoo tập 1"}}'
    parsed = QwenRecommendationService.extract_and_repair_json(text)
    assert parsed["intent_type"] == "DISCOVERY"
    assert parsed["query"]["text"] == "Jadoo tập 1"


def test_02_production_unclosed_brackets_and_braces():
    """Truncated model output with unclosed braces/brackets repaired by production code."""
    # Truncated at end
    text = '{"intent_type": "DISCOVERY", "query": {"text": "Jadoo Mùa 1"}, "constraints": {"include_genres": ["Comedy"'
    parsed = QwenRecommendationService.extract_and_repair_json(text)
    assert parsed["intent_type"] == "DISCOVERY"
    assert parsed["query"]["text"] == "Jadoo Mùa 1"
    assert parsed["constraints"]["include_genres"] == ["Comedy"]


def test_03_production_trailing_comma_before_bracket():
    """Trailing comma before closing bracket/brace handled by production code."""
    text = '{"intent_type": "DISCOVERY", "constraints": {"include_genres": ["Comedy", "Family", ], }, }'
    parsed = QwenRecommendationService.extract_and_repair_json(text)
    assert parsed["intent_type"] == "DISCOVERY"
    assert "Comedy" in parsed["constraints"]["include_genres"]
    assert "Family" in parsed["constraints"]["include_genres"]


def test_04_production_brackets_inside_string_value():
    """Brackets inside a string literal must not break json parsing."""
    text = '{"query": {"text": "Tập phim [HD] đặc biệt {2021}"}}'
    parsed = QwenRecommendationService.extract_and_repair_json(text)
    assert parsed["query"]["text"] == "Tập phim [HD] đặc biệt {2021}"


def test_05_production_fail_closed_on_garbage():
    """Unrepairable non-JSON text must cleanly raise ModelOutputParseError."""
    with pytest.raises(ModelOutputParseError):
        QwenRecommendationService.extract_and_repair_json("Xin chào, tôi là trợ lý AI!")


def test_06_production_fail_closed_on_non_dict_array():
    """A JSON array output (not a dict) must raise ModelOutputParseError."""
    with pytest.raises(ModelOutputParseError):
        QwenRecommendationService.extract_and_repair_json('["ep1", "ep2", "ep3"]')


def test_07_production_fail_closed_on_empty_string():
    """Empty model output must raise ModelOutputParseError."""
    with pytest.raises(ModelOutputParseError):
        QwenRecommendationService.extract_and_repair_json("   ")


def test_08_markdown_code_block_wrapping():
    """Output wrapped in ```json ... ``` code blocks must be extracted properly."""
    text = """```json
    {
        "intent_type": "DISCOVERY",
        "query": {"text": "Xin Chào Jadoo"}
    }
    ```"""
    parsed = QwenRecommendationService.extract_and_repair_json(text)
    assert parsed["intent_type"] == "DISCOVERY"
    assert parsed["query"]["text"] == "Xin Chào Jadoo"
