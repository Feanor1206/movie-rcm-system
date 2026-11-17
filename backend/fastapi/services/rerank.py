from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class ScoreCalibration:
    x: np.ndarray
    y: np.ndarray
    threshold: float
    model_id: str
    score_type: str = "reranker"

    @classmethod
    def from_file(cls, path, *, model_id, score_type="reranker"):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("model_id") != model_id or data.get("score_type") != score_type:
            raise ValueError("Calibration model identity or score stage does not match")
        x = np.asarray(data.get("x", []), dtype=np.float64)
        y = np.asarray(data.get("y", []), dtype=np.float64)
        if (x.ndim != 1 or x.size < 2 or y.shape != x.shape or not np.isfinite(x).all()
                or not np.isfinite(y).all() or not (np.diff(x) > 0).all()
                or not (np.diff(y) >= 0).all() or (y < 0).any() or (y > 1).any()):
            raise ValueError("Calibration requires finite monotonic score and probability knots")
        threshold = data.get("threshold")
        if not isinstance(threshold, (float, int)) or not 0 <= threshold <= 1:
            raise ValueError("Calibration requires a probability rejection threshold")
        x.flags.writeable = y.flags.writeable = False
        return cls(x, y, float(threshold), model_id, score_type)

    def __call__(self, score):
        if not np.isfinite(score):
            raise ValueError("Calibration input must be finite")
        return float(np.interp(score, self.x, self.y))
