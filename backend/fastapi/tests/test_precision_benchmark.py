import numpy as np
import pytest

from ai.evaluation.precision_benchmark import compare_rankings


def test_per_episode_overlap_excludes_only_matching_document():
    docs = np.eye(12, dtype=np.float32)
    query = np.array([docs[0], docs[1]])
    altered = query.copy()
    altered[1] = docs[11]
    report = compare_rankings(docs, query, docs, altered, [0, 1], ["a", "b"])
    assert report["a"]["queryCount"] == 1
    assert report["a"]["meanTop10Overlap"] == 1
    assert report["b"]["meanTop10Overlap"] == pytest.approx(0.9)


def test_requires_at_least_ten_nonself_candidates():
    docs = np.eye(10, dtype=np.float32)
    with pytest.raises(ValueError, match="10"):
        compare_rankings(docs, docs[:1], docs, docs[:1], [0], ["a"])
