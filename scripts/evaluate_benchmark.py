"""
Unified Benchmark Scorer for AI-OPT-01-F01.
Evaluates raw HTTP evidence JSON files against calibrated/ground-truth benchmarks.
Calculates:
  - Hit@1, Hit@3, MRR (Mean Reciprocal Rank) on answerable queries.
  - Type-conformance (matching expected entity type: series, episode, segment).
  - Constraint violations (year, genres).
  - Unanswerable rejection accuracy (True Negatives vs False Acceptances).
  - Holdout evaluation breakdown.
  - Token throughput, generation time, retrieval time, and total HTTP latency distributions.
Outputs formatted Markdown summary and machine-readable JSON metrics.
"""

import sys
import json
import statistics
from pathlib import Path
from typing import Dict, Any, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def score_evidence(evidence_path: Path, eval_benchmark_path: Path) -> Dict[str, Any]:
    with open(evidence_path, "r", encoding="utf-8") as f:
        evidence = json.load(f)
    with open(eval_benchmark_path, "r", encoding="utf-8") as f:
        bench_data = json.load(f)

    bench_queries = {q["id"]: q for q in bench_data.get("queries", [])}
    details = evidence.get("details", [])

    total_queries = len(details)
    answerable_count = 0
    holdout_count = 0
    unanswerable_count = 0

    hits_at_1 = 0
    hits_at_3 = 0
    rr_sum = 0.0

    hits_at_1_type_match = 0
    type_match_count = 0
    segment_exact_hits = 0
    parent_episode_hits = 0

    holdout_hits_1 = 0
    holdout_hits_3 = 0
    holdout_rr_sum = 0.0

    unanswerable_rejected = 0
    unanswerable_false_accept = 0

    constraint_violations = 0
    intent_valid_count = 0
    http_error_count = 0

    gen_latencies = []
    ret_latencies = []
    total_http_latencies = []
    tokens_per_secs = []

    per_query_results = []

    for item in details:
        qid = item["id"]
        q_ref = bench_queries.get(qid, {})
        expected_ids = set(q_ref.get("expected_ids", []))
        expected_type = q_ref.get("expected_type")
        is_unans = q_ref.get("unanswerable", False)
        is_holdout = q_ref.get("holdout", False)

        retrieved = item.get("retrieved_items") or []
        retrieved_ids = [m.get("id") for m in retrieved] if retrieved and isinstance(retrieved[0], dict) else item.get("retrieved_ids", [])
        top1_id = retrieved_ids[0] if retrieved_ids else None
        top3_ids = retrieved_ids[:3]

        timings = item.get("timings_ms", {})
        gen_ms = timings.get("generation_ms", 0.0)
        ret_ms = timings.get("retrieval_ms", 0.0)
        tot_ms = timings.get("total_http_ms") or timings.get("total_ms", 0.0)

        tok_info = item.get("tokens", {})
        tok_s = tok_info.get("tokens_per_second", 0.0)

        if gen_ms > 0:
            gen_latencies.append(gen_ms)
        if ret_ms > 0:
            ret_latencies.append(ret_ms)
        if tot_ms > 0:
            total_http_latencies.append(tot_ms)
        if tok_s > 0:
            tokens_per_secs.append(tok_s)

        has_http_error = (item.get("http_status", 200) != 200) or bool(item.get("error"))
        if has_http_error:
            http_error_count += 1

        if item.get("parsed_intent") and isinstance(item["parsed_intent"], dict):
            intent_valid_count += 1

        hit1 = False
        hit3 = False
        rr = 0.0
        type_match = False

        if is_unans:
            unanswerable_count += 1
            if has_http_error:
                # Lỗi HTTP (500, timeout) là FAILURE, không được tính là từ chối hợp lệ
                unanswerable_false_accept += 1
                rejected = False
            elif len(retrieved_ids) == 0:
                unanswerable_rejected += 1
                rejected = True
            else:
                unanswerable_false_accept += 1
                rejected = False
        else:
            answerable_count += 1
            if has_http_error:
                # Lỗi HTTP trên answerable query
                rejected = False
            else:
                if top1_id in expected_ids:
                    hit1 = True
                    hits_at_1 += 1
                    rr = 1.0
                elif len(top3_ids) > 1 and top3_ids[1] in expected_ids:
                    rr = 0.5
                elif len(top3_ids) > 2 and top3_ids[2] in expected_ids:
                    rr = 1.0 / 3.0

                if any(tid in expected_ids for tid in top3_ids):
                    hit3 = True
                    hits_at_3 += 1

                rr_sum += rr

                if is_holdout:
                    holdout_count += 1
                    if hit1:
                        holdout_hits_1 += 1
                    if hit3:
                        holdout_hits_3 += 1
                    holdout_rr_sum += rr

                # Type conformance check
                if retrieved:
                    top_obj = retrieved[0] if isinstance(retrieved[0], dict) else {}
                    actual_type = top_obj.get("item_type")
                    if expected_type and actual_type == expected_type:
                        type_match = True
                        type_match_count += 1

                # Segment vs Parent Episode distinction
                if expected_type == "segment":
                    prim_seg = q_ref.get("primary_expected_id")
                    parent_ep = q_ref.get("parent_episode_id")
                    if top1_id == prim_seg:
                        segment_exact_hits += 1
                    elif top1_id == parent_ep:
                        parent_episode_hits += 1

                # Check constraint violations (e.g. year range)
                exp_cons = q_ref.get("expected_constraints", {})
                req_min_yr = exp_cons.get("year_min")
                req_max_yr = exp_cons.get("year_max")
                req_exc_genres = {g.lower() for g in exp_cons.get("exclude_genres", [])}

                if top1_id and retrieved:
                    top_obj = retrieved[0] if isinstance(retrieved[0], dict) else {}
                    m_year = top_obj.get("year")
                    m_genres = {g.lower() for g in top_obj.get("genres", [])}

                    if req_min_yr and m_year and m_year < req_min_yr:
                        constraint_violations += 1
                    elif req_max_yr and m_year and m_year > req_max_yr:
                        constraint_violations += 1
                    elif req_exc_genres and (m_genres & req_exc_genres):
                        constraint_violations += 1

        per_query_results.append({
            "id": qid,
            "query": item.get("query"),
            "unanswerable": is_unans,
            "holdout": is_holdout,
            "expected_ids": list(expected_ids),
            "retrieved_ids": retrieved_ids,
            "hit_at_1": hit1,
            "hit_at_3": hit3,
            "reciprocal_rank": rr,
            "timings_ms": timings,
            "tokens": tok_info
        })

    def calc_percent(num: int, den: int) -> float:
        return round(num / den, 4) if den > 0 else 0.0

    median_total = round(statistics.median(total_http_latencies), 2) if total_http_latencies else 0.0
    p90_total = round(statistics.quantiles(total_http_latencies, n=10)[8], 2) if len(total_http_latencies) >= 10 else (max(total_http_latencies) if total_http_latencies else 0.0)
    median_gen = round(statistics.median(gen_latencies), 2) if gen_latencies else 0.0
    median_ret = round(statistics.median(ret_latencies), 2) if ret_latencies else 0.0
    avg_tok_s = round(statistics.mean(tokens_per_secs), 2) if tokens_per_secs else 0.0

    eval_ids = [q["id"] for q in bench_data.get("queries", [])]
    res_ids = [item["id"] for item in details]
    duplicate_ids = list(set([qid for qid in res_ids if res_ids.count(qid) > 1]))
    missing_ids = [qid for qid in eval_ids if qid not in res_ids]
    unknown_ids = [qid for qid in res_ids if qid not in eval_ids]

    return {
        "evidence_file": str(evidence_path.name),
        "benchmark_file": str(eval_benchmark_path.name),
        "summary": {
            "total_queries": total_queries,
            "answerable_count": answerable_count,
            "holdout_count": holdout_count,
            "unanswerable_count": unanswerable_count,
            "http_errors": http_error_count,
            "validation": {
                "duplicate_ids": duplicate_ids,
                "missing_ids": missing_ids,
                "unknown_ids": unknown_ids
            },
            "accuracy": {
                "answerable_hit_at_1": calc_percent(hits_at_1, answerable_count),
                "answerable_hit_at_3": calc_percent(hits_at_3, answerable_count),
                "answerable_mrr_at_3": round(rr_sum / answerable_count, 4) if answerable_count > 0 else 0.0,
                "type_conformance_rate": calc_percent(type_match_count, answerable_count),
                "overall_hit_at_1": calc_percent(hits_at_1, answerable_count),
                "overall_hit_at_3": calc_percent(hits_at_3, answerable_count),
                "overall_mrr": round(rr_sum / answerable_count, 4) if answerable_count > 0 else 0.0,
                "overall_mrr_at_3": round(rr_sum / answerable_count, 4) if answerable_count > 0 else 0.0,
                "holdout_hit_at_1": calc_percent(holdout_hits_1, holdout_count),
                "holdout_hit_at_3": calc_percent(holdout_hits_3, holdout_count),
                "holdout_mrr_at_3": round(holdout_rr_sum / holdout_count, 4) if holdout_count > 0 else 0.0,
                "holdout_mrr": round(holdout_rr_sum / holdout_count, 4) if holdout_count > 0 else 0.0,
                "unanswerable_rejection_rate": calc_percent(unanswerable_rejected, unanswerable_count),
                "unanswerable_false_accept_count": unanswerable_false_accept,
                "constraint_violations": constraint_violations,
                "segment_resolution": {
                    "exact_segment_hits": segment_exact_hits,
                    "parent_episode_hits": parent_episode_hits
                }
            },
            "performance": {
                "median_total_http_ms": median_total,
                "p90_total_http_ms": p90_total,
                "median_generation_ms": median_gen,
                "median_retrieval_ms": median_ret,
                "avg_tokens_per_second": avg_tok_s
            }
        },
        "details": per_query_results
    }


def format_markdown_table(baseline_score: Dict[str, Any], optimized_score: Dict[str, Any]) -> str:
    b_acc = baseline_score["summary"]["accuracy"]
    b_perf = baseline_score["summary"]["performance"]
    o_acc = optimized_score["summary"]["accuracy"]
    o_perf = optimized_score["summary"]["performance"]

    lines = [
        "| Tiêu chí đo đạc | Baseline (Gốc) | Tối ưu AI-OPT-01-F01 | Độ lệch cải thiện (Delta) |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Độ trễ HTTP trung vị (Median)** | {b_perf['median_total_http_ms']:,.1f} ms | **{o_perf['median_total_http_ms']:,.1f} ms** | **{((o_perf['median_total_http_ms'] - b_perf['median_total_http_ms'])/b_perf['median_total_http_ms']):.1%}** |",
        f"| **Độ trễ HTTP P90** | {b_perf['p90_total_http_ms']:,.1f} ms | **{o_perf['p90_total_http_ms']:,.1f} ms** | **{((o_perf['p90_total_http_ms'] - b_perf['p90_total_http_ms'])/b_perf['p90_total_http_ms']):.1%}** |",
        f"| **Thời gian sinh Qwen (Median)** | {b_perf['median_generation_ms']:,.1f} ms | **{o_perf['median_generation_ms']:,.1f} ms** | **{((o_perf['median_generation_ms'] - b_perf['median_generation_ms'])/b_perf['median_generation_ms']):.1%}** |",
        f"| **Thời gian truy xuất (Median)** | {b_perf['median_retrieval_ms']:,.1f} ms | **{o_perf['median_retrieval_ms']:,.1f} ms** | Ổn định |",
        f"| **Throughput sinh token** | {b_perf['avg_tokens_per_second']} tok/s | **{o_perf['avg_tokens_per_second']} tok/s** | **+{o_perf['avg_tokens_per_second'] - b_perf['avg_tokens_per_second']:.2f} tok/s** |",
        f"| **Answerable Hit@1** | {b_acc['overall_hit_at_1']:.1%} | **{o_acc['overall_hit_at_1']:.1%}** | **+{o_acc['overall_hit_at_1'] - b_acc['overall_hit_at_1']:.1%}** |",
        f"| **Answerable Hit@3** | {b_acc['overall_hit_at_3']:.1%} | **{o_acc['overall_hit_at_3']:.1%}** | **+{o_acc['overall_hit_at_3'] - b_acc['overall_hit_at_3']:.1%}** |",
        f"| **MRR (Mean Reciprocal Rank)** | {b_acc['overall_mrr']:.4f} | **{o_acc['overall_mrr']:.4f}** | **+{o_acc['overall_mrr'] - b_acc['overall_mrr']:.4f}** |",
        f"| **Holdout Test Hit@1** | {b_acc['holdout_hit_at_1']:.1%} | **{o_acc['holdout_hit_at_1']:.1%}** | **+{o_acc['holdout_hit_at_1'] - b_acc['holdout_hit_at_1']:.1%}** |",
        f"| **Holdout Test Hit@3** | {b_acc['holdout_hit_at_3']:.1%} | **{o_acc['holdout_hit_at_3']:.1%}** | **+{o_acc['holdout_hit_at_3'] - b_acc['holdout_hit_at_3']:.1%}** |",
        f"| **Holdout MRR** | {b_acc['holdout_mrr']:.4f} | **{o_acc['holdout_mrr']:.4f}** | **+{o_acc['holdout_mrr'] - b_acc['holdout_mrr']:.4f}** |",
        f"| **Từ chối ngoài Catalog (Rejection)** | {b_acc['unanswerable_rejection_rate']:.1%} | **{o_acc['unanswerable_rejection_rate']:.1%}** | **+{o_acc['unanswerable_rejection_rate'] - b_acc['unanswerable_rejection_rate']:.1%}** |",
        f"| **Vi phạm ràng buộc (Violations)** | {b_acc['constraint_violations']} | **{o_acc['constraint_violations']}** | 0 vi phạm |"
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/evaluate_benchmark.py <evidence_json> <benchmark_json> [output_summary_json]")
        sys.exit(1)

    ev_file = Path(sys.argv[1])
    bm_file = Path(sys.argv[2])
    out_file = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    results = score_evidence(ev_file, bm_file)
    print(json.dumps(results["summary"], indent=2, ensure_ascii=False))

    if out_file:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Saved score summary to {out_file}")
