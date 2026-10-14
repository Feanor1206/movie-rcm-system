# Phase 23 Qwen3-4B Intent Parser — Official Evaluation Report (`TEST_GOLD`)

## 1. Model & Training Summary
- **Base Model:** `Qwen/Qwen3-4B` (4-bit NF4 QLoRA SFT)
- **Best Adapter Checkpoint:** `checkpoint-200` (`phase23_reproduced_best_adapter`)
- **Best Validation Loss:** `0.11049` (Final Step 516 Train Loss: `0.0406`, Eval Loss: `0.1134`)
- **Benchmark Dataset:** `phase23_test_gold_final_v1.jsonl` (500 frozen rows: 304 deterministic + 196 human-reviewed)

## 2. Overall & Source-Split Metrics

| Subset | Samples | JSON Valid | Intent Acc | Year Acc | Exclude Genres | Requested K | Clarification (Req) | Clarification (Full) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **ALL (Total)** | 500 | 100.0% | 82.0% | 92.0% | 97.8% | 96.2% | 94.8% | 89.4% |
| **Deterministic** | 304 | 100.0% | 74.3% | 87.2% | 96.7% | 95.4% | 95.4% | 95.4% |
| **Human-Reviewed** | 196 | 100.0% | 93.9% | 99.5% | 99.5% | 97.4% | 93.9% | 80.1% |

## 3. Breakdown by Task Class

| Task Class | Samples | JSON Valid | Intent Acc | Year Acc | Exclude Genres | Requested K |
|---|---:|---:|---:|---:|---:|---:|
| `AMBIGUOUS_REFERENCE` | 12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `CONFLICTING_YEAR` | 12 | 100.0% | 100.0% | 91.7% | 100.0% | 100.0% |
| `CONVERSATIONAL_PATCH` | 65 | 100.0% | 1.5% | 40.0% | 87.7% | 89.2% |
| `DIVERSIFY` | 17 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `GENRE_EXCLUDE` | 27 | 100.0% | 96.3% | 100.0% | 96.3% | 100.0% |
| `GENRE_INCLUDE` | 27 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `INVALID_COUNT` | 10 | 100.0% | 100.0% | 100.0% | 100.0% | 50.0% |
| `MULTI_CONSTRAINT` | 50 | 100.0% | 100.0% | 100.0% | 98.0% | 100.0% |
| `NO_OP` | 7 | 100.0% | 57.1% | 100.0% | 100.0% | 100.0% |
| `PERSONALIZATION` | 17 | 100.0% | 76.5% | 100.0% | 100.0% | 100.0% |
| `QUERY_ONLY` | 30 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `QUERY_REFERENCE` | 30 | 100.0% | 86.7% | 100.0% | 96.7% | 100.0% |
| `REFERENCE_ONLY` | 25 | 100.0% | 88.0% | 100.0% | 100.0% | 100.0% |
| `RESULT_COUNT` | 18 | 100.0% | 44.4% | 100.0% | 100.0% | 61.1% |
| `UNRESOLVED_REFERENCE` | 13 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `UNSUPPORTED_FACET` | 30 | 100.0% | 96.7% | 100.0% | 100.0% | 100.0% |
| `YEAR_INCLUSIVE_FROM` | 23 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `YEAR_INCLUSIVE_UNTIL` | 18 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `YEAR_RANGE` | 23 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `YEAR_STRICT_AFTER` | 23 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `YEAR_STRICT_BEFORE` | 23 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

## 4. Intent Type Confusion Matrix (Gold → Predicted)

| Gold Intent | Predicted Intent | Count |
|---|---|---:|
| `DISCOVERY` | `DISCOVERY` | 358 |
| `CLARIFICATION` | `CLARIFICATION` | 47 |
| `DISCOVERY` | `CLARIFICATION` | 23 |
| `CONVERSATIONAL_PATCH` | `DISCOVERY` | 17 |
| `CONVERSATIONAL_PATCH` | `UPDATE_CONSTRAINTS` | 17 |
| `CONVERSATIONAL_PATCH` | `MODIFY` | 10 |
| `CONVERSATIONAL_PATCH` | `UPDATE` | 8 |
| `CONVERSATIONAL_PATCH` | `MODIFY_CONSTRAINTS` | 5 |
| `NO_OP` | `NO_OP` | 4 |
| `CONVERSATIONAL_PATCH` | `UPDATE_CONSTRAINT` | 3 |
| `CONVERSATIONAL_PATCH` | `None` | 1 |
| `NO_OP` | `None` | 1 |
| `NO_OP` | `CLARIFICATION` | 1 |
| `CONVERSATIONAL_PATCH` | `CONVERSATIONAL_PATCH` | 1 |
| `NO_OP` | `NOOP` | 1 |
| `CONVERSATIONAL_PATCH` | `MODIFY_REQUEST` | 1 |
| `CONVERSATIONAL_PATCH` | `CLEAR_CONSTRAINT` | 1 |
| `CONVERSATIONAL_PATCH` | `CLARIFICATION` | 1 |
