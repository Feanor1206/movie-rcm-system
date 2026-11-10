import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.rerank import ScoreCalibration


def test_monotonic_calibration_is_bound_to_model_and_score_stage(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps({"model_id": "reranker@v1", "score_type": "reranker",
                                "x": [-2, 0, 2], "y": [0.05, 0.5, 0.95], "threshold": 0.6}))
    calibration = ScoreCalibration.from_file(path, model_id="reranker@v1")
    assert calibration(1) == pytest.approx(0.725)
    assert calibration.threshold == 0.6
    assert calibration(99) == 0.95
    with pytest.raises(ValueError, match="model"):
        ScoreCalibration.from_file(path, model_id="reranker@v2")


def test_invalid_or_unconfigured_calibration_fails(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps({"model_id": "model", "score_type": "reranker",
                                "x": [0, 1], "y": [0.8, 0.2], "threshold": 0.6}))
    with pytest.raises(ValueError, match="monotonic"):
        ScoreCalibration.from_file(path, model_id="model")
