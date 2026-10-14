import json
import sys
from pathlib import Path
from collections import defaultdict, Counter

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
GOLD_FILE = BASE_DIR / "datasets/test_gold/phase23_test_gold_final_v1.jsonl"
PRED_FILE = BASE_DIR / "phase23_package/evaluation/phase23_test_gold_predictions.jsonl"
REPORT_MD = BASE_DIR / "evaluation/PHASE23_EVALUATION_REPORT.md"

def main():
    gold_rows = {
        r["id"]: r
        for r in (json.loads(l) for l in GOLD_FILE.open(encoding="utf-8") if l.strip())
    }
    pred_rows = [
        json.loads(l) for l in PRED_FILE.open(encoding="utf-8") if l.strip()
    ]

    total = len(pred_rows)
    by_source = defaultdict(lambda: defaultdict(int))
    by_task = defaultdict(lambda: defaultdict(int))
    intent_conf = Counter()

    for r in pred_rows:
        gid = r["id"]
        g_meta = gold_rows[gid]
        src = g_meta.get("gold_source", "UNKNOWN")
        tc = g_meta.get("task_class", "UNKNOWN")
        p = r.get("prediction_json")
        g = r.get("gold_output") or {}

        for bucket in (by_source[src], by_task[tc], by_source["ALL"]):
            bucket["total"] += 1
            if isinstance(p, dict):
                bucket["valid"] += 1
                if p.get("intent_type") == g.get("intent_type"):
                    bucket["intent"] += 1
                pc = p.get("constraints") or {}
                gc = g.get("constraints") or {}
                if pc.get("year_min") == gc.get("year_min") and pc.get("year_max") == gc.get("year_max"):
                    bucket["year"] += 1
                if set(pc.get("exclude_genres") or []) == set(gc.get("exclude_genres") or []):
                    bucket["excl"] += 1
                if p.get("requested_k") == g.get("requested_k"):
                    bucket["req_k"] += 1
                pcl = p.get("clarification") or {}
                gcl = g.get("clarification") or {}
                if pcl.get("required") == gcl.get("required"):
                    bucket["clar_req"] += 1
                if pcl.get("required") == gcl.get("required") and pcl.get("reason") == gcl.get("reason"):
                    bucket["clar_full"] += 1
                if p.get("no_op") == g.get("no_op"):
                    bucket["noop"] += 1

        if isinstance(p, dict):
            intent_conf[(g.get("intent_type"), p.get("intent_type"))] += 1

    lines = [
        "# Phase 23 Qwen3-4B Intent Parser — Official Evaluation Report (`TEST_GOLD`)",
        "",
        "## 1. Model & Training Summary",
        "- **Base Model:** `Qwen/Qwen3-4B` (4-bit NF4 QLoRA SFT)",
        "- **Best Adapter Checkpoint:** `checkpoint-200` (`phase23_reproduced_best_adapter`)",
        "- **Best Validation Loss:** `0.11049` (Final Step 516 Train Loss: `0.0406`, Eval Loss: `0.1134`)",
        "- **Benchmark Dataset:** `phase23_test_gold_final_v1.jsonl` (500 frozen rows: 304 deterministic + 196 human-reviewed)",
        "",
        "## 2. Overall & Source-Split Metrics",
        "",
        "| Subset | Samples | JSON Valid | Intent Acc | Year Acc | Exclude Genres | Requested K | Clarification (Req) | Clarification (Full) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for key in ["ALL", "DETERMINISTIC", "HUMAN_REVIEWED_WITH_DETERMINISTIC_SCHEMA_NORMALIZATION"]:
        b = by_source[key]
        t = b["total"]
        if t == 0:
            continue
        label = "ALL (Total)" if key == "ALL" else ("Deterministic" if key == "DETERMINISTIC" else "Human-Reviewed")
        lines.append(
            f"| **{label}** | {t} | {b['valid']/t*100:.1f}% | {b['intent']/t*100:.1f}% | "
            f"{b['year']/t*100:.1f}% | {b['excl']/t*100:.1f}% | {b['req_k']/t*100:.1f}% | "
            f"{b['clar_req']/t*100:.1f}% | {b['clar_full']/t*100:.1f}% |"
        )

    lines.extend([
        "",
        "## 3. Breakdown by Task Class",
        "",
        "| Task Class | Samples | JSON Valid | Intent Acc | Year Acc | Exclude Genres | Requested K |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])

    for tc, b in sorted(by_task.items()):
        t = b["total"]
        lines.append(
            f"| `{tc}` | {t} | {b['valid']/t*100:.1f}% | {b['intent']/t*100:.1f}% | "
            f"{b['year']/t*100:.1f}% | {b['excl']/t*100:.1f}% | {b['req_k']/t*100:.1f}% |"
        )

    lines.extend([
        "",
        "## 4. Intent Type Confusion Matrix (Gold → Predicted)",
        "",
        "| Gold Intent | Predicted Intent | Count |",
        "|---|---|---:|",
    ])
    for (gi, pi), cnt in intent_conf.most_common():
        lines.append(f"| `{gi}` | `{pi}` | {cnt} |")

    report_text = "\n".join(lines) + "\n"
    REPORT_MD.write_text(report_text, encoding="utf-8")
    print(report_text)

if __name__ == "__main__":
    main()
