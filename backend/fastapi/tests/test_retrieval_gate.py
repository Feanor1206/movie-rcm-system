import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ai.evaluation.retrieval_gate import compare_catalogs, gate, measure, read_labels, run_cases


ROOT = Path(__file__).resolve().parents[3]
CSV_HEADER = "query,episode_id,start_ms,end_ms,writer,notes\n"


class FixtureEncoder:
    model_id = "test-only-encoder"

    def encode_documents(self, texts):
        return np.ones((len(texts), 2), dtype=np.float32)

    def encode_queries(self, texts):
        return np.ones((len(texts), 2), dtype=np.float32)


def test_metrics_measure_episode_rank_and_thirty_second_moment():
    labels = [{"id": "q1", "query": "chiếc bình", "episodeIds": ["ep1"],
               "moments": [{"episodeId": "ep1", "startMs": 100_000}], "source": "human"}]
    predictions = [{"id": "q1", "results": [{"episodeId": "ep2", "startMs": 0},
                                             {"episodeId": "ep1", "startMs": 130_000}]}]
    assert measure(labels, predictions) == {"recallAt1": 0.0, "recallAt5": 1.0, "mrr": 0.5,
                                            "momentRecallAt5": 1.0, "timeHitRateAt5": 1.0}


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


def test_episode_ranks_deduplicate_and_time_rate_counts_only_timed_episode_hits():
    labels = [{"id": q, "episodeIds": ["ep1"], "moments": [{"episodeId": "ep1", "startMs": 100_000}]}
              for q in ("exact", "wrong_time", "miss")]
    predictions = [
        {"id": "exact", "results": [{"episodeId": None}, {"episodeId": "ep2"}, {"episodeId": "ep2"},
                                    {"episodeId": "ep1", "startMs": 130_000}]},
        {"id": "wrong_time", "results": [{"episodeId": "ep1", "startMs": None}]},
        {"id": "miss", "results": [{"episodeId": "ep2", "startMs": 100_000}]},
    ]
    assert measure(labels, predictions) == {"recallAt1": 1 / 3, "recallAt5": 2 / 3, "mrr": 0.5,
                                            "momentRecallAt5": 1 / 3, "timeHitRateAt5": 0.5}


def test_gold_csv_reads_bom_quoted_query_and_optional_moment(tmp_path):
    labels = tmp_path / "labels.csv"
    labels.write_text(CSV_HEADER + '"Bình Minh, cảnh nào?",ep1,0,3000,writer-a,"ghi chú, có dấu"\n'
                      + 'Đêm Trăng Máu,ep2,,,writer-b,\n', encoding="utf-8-sig")
    rows = read_labels(labels)
    assert [row["query"] for row in rows] == ["Bình Minh, cảnh nào?", "Đêm Trăng Máu"]
    assert [row["episodeIds"] for row in rows] == [["ep1"], ["ep2"]]
    assert rows[0]["moments"] == [{"episodeId": "ep1", "startMs": 0, "endMs": 3000}]
    assert rows[1]["moments"] == []
    assert [row["source"] for row in rows] == ["human", "human"]
    assert len({row["id"] for row in rows}) == 2


@pytest.mark.parametrize("contents,message", [
    (CSV_HEADER, "no human labels"),
    ("query,episode_id\na,ep1\n", "header"),
    (CSV_HEADER + "a,ep1,0,9,writer,notes,extra\n", "columns"),
    (CSV_HEADER + "a,ep1,0,9,,notes\n", "writer"),
    (CSV_HEADER + "a,ep1,,9,writer,notes\n", "start_ms"),
    (CSV_HEADER + "a,ep1,10,9,writer,notes\n", "end_ms"),
])
def test_gold_csv_rejects_missing_labels_or_malformed_rows(tmp_path, contents, message):
    path = tmp_path / "labels.csv"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        read_labels(path)


def test_pilot_compares_four_modes_on_one_episode_universe(tmp_path):
    original = json.loads((ROOT / "docs" / "fixtures" / "retrieval_catalog.json").read_text(encoding="utf-8"))
    enriched = json.loads(json.dumps(original))
    selected = enriched["scenes"][0]["episode_id"]
    enriched["scenes"][0]["summary"] = "Enriched pilot"
    episode = next(episode for episode in original["episodes"] if episode["id"] == selected)
    labels = [{"id": "test", "query": episode["title"], "episodeIds": [selected], "source": "human"}]

    report = compare_catalogs(labels, original, enriched, FixtureEncoder(), tmp_path)
    assert report["pilotEpisodeIds"] == [selected]
    assert report["queryCount"] == 1
    assert set(report["configurations"]) == {"originalBm25", "originalHybrid", "enrichedBm25", "enrichedHybrid"}
    assert all(config["metrics"]["recallAt1"] == 1.0 for config in report["configurations"].values())
    assert all(config["denseReady"] == ("Hybrid" in name) for name, config in report["configurations"].items())
    assert {path.name for path in tmp_path.iterdir()} == {"original", "enriched"}
    labels[0]["episodeIds"] = [next(ep["id"] for ep in original["episodes"] if ep["id"] != selected)]
    with pytest.raises(ValueError, match="outside the pilot"):
        compare_catalogs(labels, original, enriched, FixtureEncoder(), tmp_path)


def test_dialogue_only_evaluation_projects_generated_drafts_but_excludes_unrelated_drafts(tmp_path):
    original = json.loads((ROOT / "docs" / "fixtures" / "retrieval_catalog.json").read_text(encoding="utf-8"))
    enriched = json.loads(json.dumps(original))
    enriched["package"]["id"] = "jadoo-pilot-dialogue"
    asset = enriched["media_assets"][0]
    episode_id = asset["coverage"][0]["episode_id"]
    status = {"status": "draft", "provenance": {"origin": "machine_generated"}}
    enriched["text_tracks"].extend([
        {"id": f"{episode_id}.track.asr.vi", "media_asset_id": asset["id"], "record": status,
         "cues": [{"start_ms": 90_000, "end_ms": 91_000, "text": "pilotwordqx"}]},
        {"id": f"{episode_id}.track.unrelated.vi", "media_asset_id": asset["id"], "record": status,
         "cues": [{"start_ms": 95_000, "end_ms": 96_000, "text": "unrelatedwordqx"}]},
    ])
    labels = [{"id": word, "query": word, "episodeIds": [episode_id], "source": "human"}
              for word in ("pilotwordqx", "unrelatedwordqx")]
    before = json.loads(json.dumps(enriched))
    report = compare_catalogs(labels, original, enriched, FixtureEncoder(), tmp_path)
    assert report["pilotEpisodeIds"] == [episode_id]
    assert report["configurations"]["originalBm25"]["metrics"]["recallAt1"] == 0.0
    assert report["configurations"]["enrichedBm25"]["metrics"]["recallAt1"] == 0.5
    assert report["projectedDrafts"] == {"episodes": 0, "scenes": 0, "text_tracks": 1}
    assert enriched == before


def test_enriched_projection_keeps_previously_ready_episode_with_draft_synopsis(tmp_path):
    original = json.loads((ROOT / "docs" / "fixtures" / "retrieval_catalog.json").read_text(encoding="utf-8"))
    enriched = json.loads(json.dumps(original))
    enriched["package"]["id"] = "jadoo-pilot-enriched"
    scene = enriched["scenes"][0]
    episode_id = scene["episode_id"]
    status = {"status": "draft", "provenance": {"origin": "machine_generated"}}
    enriched["scenes"][0] = {**scene, "id": f"{episode_id}.scene.0001", "visual_description": "pilotwordsceneqx",
                              "record": status}
    episode = next(item for item in enriched["episodes"] if item["id"] == episode_id)
    episode.update(synopsis="pilotwordsynopsisqx", record={"status": "draft", "provenance": {
        "origin": "machine_generated", "note": "Generated fields: synopsis, plot_facts"}})
    labels = [{"id": word, "query": word, "episodeIds": [episode_id], "source": "human"}
              for word in ("pilotwordsceneqx", "pilotwordsynopsisqx")]
    report = compare_catalogs(labels, original, enriched, FixtureEncoder(), tmp_path)
    assert report["projectedDrafts"] == {"episodes": 1, "scenes": 1, "text_tracks": 0}
    assert report["configurations"]["enrichedBm25"]["metrics"]["recallAt1"] == 1.0


def test_comparison_cli_refuses_header_only_before_loading_artifacts(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text(CSV_HEADER, encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "ai" / "evaluation" / "retrieval_gate.py"),
                             "--labels", str(path), "--original-catalog", "missing.json",
                             "--enriched-catalog", "missing-pilot.json", "--encoder", "missing-model"],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert "no human labels" in result.stderr
