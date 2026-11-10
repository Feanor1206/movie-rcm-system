# Retrieval evaluation

API and snapshot regressions belong in pytest. Query scenarios from the former
retrieval implementation can be kept as `source: "legacy-regression"` cases and
run through `run_cases(search_fn, cases)` and `measure(cases, predictions)`. These
measurements describe regression fixtures; they are not independent model quality.

The publishable quality gate requires a separate, independently human-authored
test set, frozen before tuning, with `source: "human"` on every row. Keep episodes
disjoint from training and calibration. No human test data is bundled yet.

The [search query template](../datasets/gold/search_queries_v1.csv) has a header
only. Follow the [writer guide](../datasets/gold/README.md) and fill it with human
labels before running the pilot comparison. An empty CSV exits with an error
before any model or catalog is loaded.

Run all four configurations with one command from the repo root. Substitute the
paths for your exported pilot catalog and local BGE-M3 ONNX artifact.

```powershell
python ai/evaluation/retrieval_gate.py --labels ai/datasets/gold/search_queries_v1.csv --original-catalog data/catalog.jadoo_all.json --enriched-catalog ai/artifacts/pilot-enriched.json --encoder ai/artifacts/models/bge-m3-onnx/int8 --output ai/artifacts/pilot_retrieval_metrics.json
```

The command compares BM25 and hybrid retrieval for both catalog snapshots using
the same labels and episode universe. It selects the episodes present in a
self-contained pilot snapshot or infers them from changed pilot transcripts and
scenes in a full snapshot. Repeat `--episode-id` to specify the pilot explicitly. Use one to five
IDs shared by both catalogs. Hybrid uses the same local encoder in both runs,
with separate caches under `data/indices/pilot_evaluation` by default. No
reranker or calibration is applied. For ASR-only evaluation, use `pilot-dialogue.json`.

The comparison includes generated drafts for selected pilot episodes only in an
in-memory evaluation view. Matching catalog package, record provenance and public
media coverage are required. `projectedDrafts` reports how many records were
included this way. The source catalog retains its review status.

Recall@1, Recall@5 and MRR rank unique episodes. `timeHitRateAt5` reports the
share of relevant top-five episode hits with a labeled start time whose returned
`startMs` is within 30 seconds, inclusive. A missing predicted time counts as a
miss. The rate is `null` when no timed episode label is retrieved. The existing
`momentRecallAt5` also counts queries with no retrieved episode in its denominator.

The threshold-based quality gate accepts the CSV or the existing JSONL format.
For JSONL, supply one labeled query per row.

```json
{"id":"q1","query":"tập nào làm vỡ bình hoa","episodeIds":["episode-12"],"moments":[{"episodeId":"episode-12","startMs":520000}],"source":"human"}
```

Predictions and baseline predictions use the same query IDs:

```json
{"id":"q1","results":[{"episodeId":"episode-12","startMs":525000}]}
```

Configure thresholds in a JSON object with `recallAt5`, `mrr` and
`momentRecallAt5`, each between zero and one, based on the project quality bar.
The tool supplies no default quality threshold. A moment is correct when the
episode matches and the predicted start time is within 30 seconds, inclusive.
Recall@5 averages per-query episode recall. MRR uses the full returned ranking.
Moment recall uses the first five results for queries with moment labels.

```powershell
python ai/evaluation/retrieval_gate.py --labels ai/datasets/search_test.jsonl --predictions artifacts/search_predictions.jsonl --baseline artifacts/search_baseline.jsonl --thresholds ai/datasets/search_thresholds.json --output artifacts/search_gate.json
```

Exit status is zero only when all configured floors are met and every metric
strictly improves over the baseline. Missing data, duplicate IDs, mismatched query
sets, missing moment labels and missing thresholds fail instead of producing a
passing report. The current implementation has no measured RTX 3050 latency or
quality result. Such results require actual artifacts, held-out labels and a
hardware benchmark.
