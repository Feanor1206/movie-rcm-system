"""
Production HTTP API Benchmark Runner for AI-OPT-01-F01.
Benchmarks the full Cascading AI Pipeline via real HTTP calls to FastAPI /api/chat.

Measures:
  - Client-side end-to-end HTTP latency (time.perf_counter())
  - Server-side stage timings (generation_ms, retrieval_ms, nlu_ms, ranker_ms, total_pipeline_ms)
  - Token throughput (prompt_tokens, completion_tokens, tokens_per_second)
  - Retrieval quality and type conformance
  - Steady-state warm repeat latencies (3 iterations across 6 representative queries)

Outputs evidence JSON matching evaluate_benchmark.py requirements.
"""

import sys
import time
import json
import argparse
import statistics
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def check_server_readiness(base_url: str, max_wait_sec: int = 120) -> Dict[str, Any]:
    ready_url = f"{base_url}/ready"
    start_time = time.perf_counter()
    print(f"[*] Checking server readiness at {ready_url}...")
    while time.perf_counter() - start_time < max_wait_sec:
        try:
            req = urllib.request.Request(ready_url, headers={"User-Agent": "AI-Benchmark/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("servingMode") != "full" or data.get("degraded") is True:
                        raise RuntimeError(f"Server is degraded or not in full mode: mode={data.get('servingMode')}, degraded={data.get('degraded')}")
                    print(f"[+] Server is READY! Mode: {data.get('servingMode')}, Backend: {data.get('activeInferenceBackend')}")
                    return data
        except Exception as e:
            if "Server is degraded" in str(e):
                raise
            time.sleep(2)
    raise TimeoutError(f"Server at {ready_url} did not become ready within {max_wait_sec}s.")


def get_health_status(base_url: str) -> Dict[str, Any]:
    try:
        req = urllib.request.Request(f"{base_url}/health", headers={"User-Agent": "AI-Benchmark/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def call_chat_endpoint(chat_url: str, query: str, timeout: int = 180) -> Dict[str, Any]:
    payload = {
        "query": query,
        "messages": [{"role": "user", "content": query}],
        "sessionId": "benchmark-session"
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        chat_url,
        data=data_bytes,
        headers={"Content-Type": "application/json", "User-Agent": "AI-Benchmark/1.0"},
        method="POST"
    )

    t_start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_body = resp.read().decode("utf-8")
            t_end = time.perf_counter()
            http_ms = round((t_end - t_start) * 1000, 2)
            resp_json = json.loads(raw_body)
            return {
                "http_status": resp.status,
                "client_http_ms": http_ms,
                "response": resp_json,
                "error": None
            }
    except urllib.error.HTTPError as he:
        t_end = time.perf_counter()
        http_ms = round((t_end - t_start) * 1000, 2)
        err_msg = he.read().decode("utf-8", errors="replace")
        return {
            "http_status": he.code,
            "client_http_ms": http_ms,
            "response": None,
            "error": f"HTTP {he.code}: {err_msg}"
        }
    except Exception as ex:
        t_end = time.perf_counter()
        http_ms = round((t_end - t_start) * 1000, 2)
        return {
            "http_status": 500,
            "client_http_ms": http_ms,
            "response": None,
            "error": str(ex)
        }


def run_http_benchmark(
    base_url: str,
    benchmark_path: Path,
    output_path: Path,
    label: str = "PRODUCTION_HTTP"
):
    chat_url = f"{base_url}/api/chat"
    readiness = check_server_readiness(base_url)
    health = get_health_status(base_url)

    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmark_data = json.load(f)

    queries = benchmark_data.get("queries", [])
    print(f"\n=======================================================")
    print(f" STARTING HTTP PRODUCTION BENCHMARK: {label}")
    print(f" URL: {chat_url}")
    print(f" Benchmark: {benchmark_path.name} ({len(queries)} queries)")
    print(f" Target Mode: {readiness.get('servingMode')}")
    print(f" Backend: {readiness.get('activeInferenceBackend')}")
    print(f"=======================================================\n")

    results = []
    warm_candidates = ["eval_01", "eval_06", "eval_12"]
    warm_queries_map = {}

    for idx, q_item in enumerate(queries, 1):
        qid = q_item["id"]
        q_text = q_item["query"]
        if qid in warm_candidates:
            warm_queries_map[qid] = q_text

        print(f"[{idx:02d}/{len(queries):02d}] {qid}: '{q_text}' ...", end=" ", flush=True)

        call_res = call_chat_endpoint(chat_url, q_text)
        client_ms = call_res["client_http_ms"]
        http_st = call_res["http_status"]
        resp_json = call_res["response"] or {}

        stages = resp_json.get("pipelineStages") or {}
        timings = stages.get("timings_ms") or {}
        metrics = stages.get("metrics") or {}
        retrieved_items = resp_json.get("recommendedMovies") or []
        parsed_intent = resp_json.get("structuredIntent") or {}

        # Fill in timing fields
        gen_ms = timings.get("generation_ms", 0.0)
        ret_ms = timings.get("retrieval_ms", 0.0)
        timings["total_http_ms"] = client_ms

        tok_s = metrics.get("tokens_per_second", 0.0)
        p_tok = metrics.get("prompt_tokens", 0)
        c_tok = metrics.get("completion_tokens", 0)

        ret_titles = [m.get("title", "") for m in retrieved_items[:2]]
        print(f"HTTP {http_st} in {client_ms:.1f}ms (gen: {gen_ms:.1f}ms, ret: {ret_ms:.1f}ms, tok/s: {tok_s:.1f}) -> {ret_titles}")

        results.append({
            "id": qid,
            "query": q_text,
            "category": q_item.get("category", ""),
            "expected_ids": q_item.get("expected_ids", []),
            "expected_type": q_item.get("expected_type", ""),
            "unanswerable": q_item.get("unanswerable", False),
            "holdout": q_item.get("holdout", False),
            "http_status": http_st,
            "retrieved_ids": [m.get("id") for m in retrieved_items if isinstance(m, dict)],
            "retrieved_items": retrieved_items,
            "parsed_intent": parsed_intent,
            "explanation": resp_json.get("text", ""),
            "timings_ms": timings,
            "tokens": {
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "tokens_per_second": tok_s
            },
            "error": call_res["error"]
        })

    # Steady-state warm repeat runs (3 iterations on 3 queries)
    print(f"\n[*] Running steady-state warm repeats (3 iterations across 3 representative queries)...")
    warm_runs = []
    for w_qid, w_qtext in warm_queries_map.items():
        w_latencies = []
        w_gen_latencies = []
        w_tps = []
        for it in range(3):
            time.sleep(0.5)
            w_res = call_chat_endpoint(chat_url, w_qtext)
            w_ms = w_res["client_http_ms"]
            w_resp = w_res["response"] or {}
            w_stages = w_resp.get("pipelineStages") or {}
            w_timings = w_stages.get("timings_ms") or {}
            w_metrics = w_stages.get("metrics") or {}
            w_latencies.append(w_ms)
            w_gen_latencies.append(w_timings.get("generation_ms", 0.0))
            w_tps.append(w_metrics.get("tokens_per_second", 0.0))
        warm_runs.append({
            "id": w_qid,
            "query": w_qtext,
            "repeat_http_ms": w_latencies,
            "median_http_ms": round(statistics.median(w_latencies), 2),
            "median_gen_ms": round(statistics.median(w_gen_latencies), 2),
            "avg_tps": round(statistics.mean(w_tps), 2) if w_tps else 0.0
        })
        print(f"    Warm {w_qid}: median HTTP {statistics.median(w_latencies):.1f}ms, median gen {statistics.median(w_gen_latencies):.1f}ms, avg TPS {statistics.mean(w_tps):.1f}")

    # Compute overall summary
    all_http_latencies = [r["timings_ms"]["total_http_ms"] for r in results if r["timings_ms"].get("total_http_ms")]
    all_gen_latencies = [r["timings_ms"]["generation_ms"] for r in results if r["timings_ms"].get("generation_ms")]
    all_ret_latencies = [r["timings_ms"]["retrieval_ms"] for r in results if r["timings_ms"].get("retrieval_ms")]
    all_tps = [r["tokens"]["tokens_per_second"] for r in results if r["tokens"].get("tokens_per_second")]

    evidence_data = {
        "metadata": {
            "label": label,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "chat_url": chat_url,
            "readiness": readiness,
            "health": health,
            "benchmark_file": benchmark_path.name,
            "total_queries": len(results),
        },
        "summary": {
            "median_http_latency_ms": round(statistics.median(all_http_latencies), 2) if all_http_latencies else 0.0,
            "p90_http_latency_ms": round(statistics.quantiles(all_http_latencies, n=10)[8], 2) if len(all_http_latencies) >= 10 else 0.0,
            "median_generation_latency_ms": round(statistics.median(all_gen_latencies), 2) if all_gen_latencies else 0.0,
            "median_retrieval_latency_ms": round(statistics.median(all_ret_latencies), 2) if all_ret_latencies else 0.0,
            "avg_tokens_per_second": round(statistics.mean(all_tps), 2) if all_tps else 0.0,
        },
        "warm_runs": warm_runs,
        "details": results
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evidence_data, f, ensure_ascii=False, indent=2)

    print(f"\n[+] Benchmark finished! Evidence saved to {output_path}")
    print(f"    - Median HTTP Latency: {evidence_data['summary']['median_http_latency_ms']} ms")
    print(f"    - P90 HTTP Latency:    {evidence_data['summary']['p90_http_latency_ms']} ms")
    print(f"    - Median Gen Latency:  {evidence_data['summary']['median_generation_latency_ms']} ms")
    print(f"    - Median Ret Latency:  {evidence_data['summary']['median_retrieval_latency_ms']} ms")
    print(f"    - Avg Token Throughput:{evidence_data['summary']['avg_tokens_per_second']} tok/s\n")
    return evidence_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Production HTTP Benchmark Runner")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL of FastAPI service")
    parser.add_argument("--benchmark", default="docs/benchmarks/jadoo_30_eval_calibrated.json", help="Benchmark JSON file")
    parser.add_argument("--output", required=True, help="Output evidence JSON path")
    parser.add_argument("--label", default="HTTP_BENCHMARK", help="Label for this run")

    args = parser.parse_args()
    bench_p = Path(args.benchmark)
    if not bench_p.is_absolute():
        bench_p = Path(__file__).resolve().parent.parent / args.benchmark
    out_p = Path(args.output)
    if not out_p.is_absolute():
        out_p = Path(__file__).resolve().parent.parent / args.output

    run_http_benchmark(args.url.rstrip("/"), bench_p, out_p, args.label)
