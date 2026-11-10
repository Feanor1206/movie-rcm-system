# Retrieval evaluation

API and snapshot regressions belong in pytest. Query scenarios from the former
retrieval implementation can be kept as `source: "legacy-regression"` cases and
run through `run_cases(search_fn, cases)` and `measure(cases, predictions)`. These
measurements describe regression fixtures; they are not independent model quality.

The publishable quality gate requires a separate, independently human-authored
test set, frozen before tuning, with `source: "human"` on every row. Keep episodes
disjoint from training and calibration. No human test data is bundled yet.

Labels are JSONL, one query per row:

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
