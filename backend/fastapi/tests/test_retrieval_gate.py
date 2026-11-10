from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ai.evaluation.retrieval_gate import gate, measure, run_cases


def test_metrics_measure_episode_rank_and_thirty_second_moment():
    labels = [{"id": "q1", "query": "chiếc bình", "episodeIds": ["ep1"],
               "moments": [{"episodeId": "ep1", "startMs": 100_000}], "source": "human"}]
    predictions = [{"id": "q1", "results": [{"episodeId": "ep2", "startMs": 0},
                                             {"episodeId": "ep1", "startMs": 130_000}]}]
    assert measure(labels, predictions) == {"recallAt5": 1.0, "mrr": 0.5, "momentRecallAt5": 1.0}


def test_quality_gate_requires_human_labels_and_configured_thresholds():
    labels = [{"id": "q1", "query": "bình hoa", "episodeIds": ["ep1"],
               "moments": [{"episodeId": "ep1", "startMs": 0}], "source": "legacy-regression"}]
    predictions = [{"id": "q1", "results": [{"episodeId": "ep1", "startMs": 0}]}]
    with pytest.raises(ValueError, match="human"):
        gate(labels, predictions, predictions, {"recallAt5": 0.5, "mrr": 0.5, "momentRecallAt5": 0.5})
    labels[0]["source"] = "human"
    with pytest.raises(ValueError, match="threshold"):
        gate(labels, predictions, predictions, {})


def test_quality_gate_cannot_pass_equal_or_worse_than_baseline():
    labels = [{"id": "q1", "query": "bình hoa", "episodeIds": ["ep1"],
               "moments": [{"episodeId": "ep1", "startMs": 0}], "source": "human"}]
    predictions = [{"id": "q1", "results": [{"episodeId": "ep1", "startMs": 0}]}]
    result = gate(labels, predictions, predictions, {"recallAt5": 0.5, "mrr": 0.5, "momentRecallAt5": 0.5})
    assert not result["passed"]
    assert len(result["reasons"]) == 3


def test_quality_gate_passes_improvement_at_all_thresholds():
    labels = [{"id": "q1", "query": "bình hoa", "episodeIds": ["ep1"],
               "moments": [{"episodeId": "ep1", "startMs": 0}], "source": "human"}]
    predictions = [{"id": "q1", "results": [{"episodeId": "ep1", "startMs": 0}]}]
    baseline = [{"id": "q1", "results": []}]
    assert gate(labels, predictions, baseline, {"recallAt5": 0.5, "mrr": 0.5, "momentRecallAt5": 0.5})["passed"]
    assert run_cases(lambda query: [{"episodeId": "ep1", "startMs": 0}], labels) == predictions


def test_missing_mismatched_or_duplicate_prediction_rows_fail():
    labels = [{"id": "q1", "query": "x", "episodeIds": ["ep1"]}]
    with pytest.raises(ValueError, match="same query"):
        measure(labels, [])
    with pytest.raises(ValueError, match="duplicate"):
        measure(labels, [{"id": "q1", "results": []}] * 2)
