"""
Performance Measurement Runner for USABILITY-01:
Measures production HTTP latency, token throughput, and stage breakdown across 4 representative queries:
1. Exact lookup: 'Xin Chào Jadoo Mùa 1 Tập 1'
2. Proven plot: 'Tập nào Jadoo muốn ăn ngon nhưng sợ bị tăng cân'
3. No-answer ungrounded: 'Tập nào Jadoo lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ'
4. Complex condition: 'Phim hoạt hình Jadoo phát hành năm 2021 không có bạo lực'

Runs warm-up first, followed by 3 sequential runs per query without model reloading.
Calculates min, max, median, and mean for each query.
Outputs full evidence to docs/reviews/evidence/USABILITY_01_BENCHMARK_EVIDENCE.json.
"""

import sys
import json
import time
import urllib.request
import urllib.error
import hashlib
import statistics
from pathlib import Path
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SERVER_URL = "http://127.0.0.1:8000"
CHAT_ENDPOINT = f"{SERVER_URL}/api/chat"
READY_ENDPOINT = f"{SERVER_URL}/ready"

BENCHMARK_QUERIES = [
    {
        "id": "perf_exact_lookup",
        "category": "EXACT_LOOKUP",
        "query": "Xin Chào Jadoo Mùa 1 Tập 1",
        "description": "Exact season & episode lookup with 1 card expectation"
    },
    {
        "id": "perf_proven_plot",
        "category": "PROVEN_PLOT",
        "query": "Tập nào Jadoo muốn ăn ngon nhưng sợ bị tăng cân",
        "description": "Proven plot search with synopsis facts"
    },
    {
        "id": "perf_no_answer_ungrounded",
        "category": "NO_ANSWER_UNGROUNDED",
        "query": "Tập nào Jadoo lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ",
        "description": "Fabricated plot query expecting clean abstention (0 cards)"
    },
    {
        "id": "perf_complex_condition",
        "category": "COMPLEX_CONDITION",
        "query": "Phim hoạt hình Jadoo phát hành năm 2021 không có bạo lực",
        "description": "Multi-constraint query with year and advisory note"
    }
]

REPETITIONS_PER_QUERY = 3


def check_server_readiness():
    print(f"[*] Checking server readiness at {READY_ENDPOINT}...")
    req = urllib.request.Request(READY_ENDPOINT, headers={"User-Agent": "Usability01-Benchmark/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"[+] Server Ready: mode={data.get('servingMode')}, backend={data.get('activeInferenceBackend')}, phase23Loaded={data.get('phase23AdapterLoaded')}")
        if data.get("servingMode") != "full" or data.get("degraded") is True:
            raise RuntimeError(f"Server is not in full mode: {data}")
        return data


def compute_source_hashes():
    files_to_hash = [
        "backend/fastapi/services/qwen_service.py",
        "backend/fastapi/services/hybrid_retrieval.py",
        "backend/fastapi/services/ai_pipeline.py",
        "backend/fastapi/main.py"
    ]
    hashes = {}
    for fp in files_to_hash:
        p = Path(fp)
        if p.exists():
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            hashes[fp] = h
    return hashes


def execute_single_query(query: str, session_id: str) -> dict:
    payload = {
        "query": query,
        "messages": [{"role": "user", "content": query}],
        "sessionId": session_id
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        CHAT_ENDPOINT,
        data=data_bytes,
        headers={"Content-Type": "application/json", "User-Agent": "Usability01-Benchmark/1.0"},
        method="POST"
    )

    t_start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw_body = resp.read().decode("utf-8")
            t_end = time.perf_counter()
            client_http_ms = round((t_end - t_start) * 1000, 2)
            resp_json = json.loads(raw_body)
            http_status = resp.status
            error = None
    except Exception as e:
        t_end = time.perf_counter()
        client_http_ms = round((t_end - t_start) * 1000, 2)
        resp_json = {}
        http_status = 500
        error = str(e)

    stages = resp_json.get("pipelineStages", {})
    timings = stages.get("timings_ms", {})
    metrics = stages.get("metrics", {})
    recs = resp_json.get("recommendedMovies") or []

    return {
        "http_status": http_status,
        "client_http_ms": client_http_ms,
        "error": error,
        "cards_returned": len(recs),
        "explanation": resp_json.get("text", ""),
        "timings_ms": timings,
        "metrics": metrics
    }


def run_benchmark(output_path: Path):
    server_info = check_server_readiness()
    source_hashes = compute_source_hashes()

    print("\n=======================================================")
    print(" USABILITY-01 BENCHMARK: WARM-UP EXECUTION")
    print("=======================================================\n")
    warmup_query = "Xin Chào Jadoo"
    print(f"[*] Running warm-up query: '{warmup_query}'...")
    warmup_res = execute_single_query(warmup_query, "warmup-session")
    print(f"[+] Warm-up complete in {warmup_res['client_http_ms']} ms (status={warmup_res['http_status']})\n")

    print("=======================================================")
    print(f" USABILITY-01 BENCHMARK: {len(BENCHMARK_QUERIES)} queries x {REPETITIONS_PER_QUERY} repetitions")
    print("=======================================================\n")

    benchmark_results = []

    for q_idx, q_item in enumerate(BENCHMARK_QUERIES, 1):
        qid = q_item["id"]
        category = q_item["category"]
        query = q_item["query"]

        print(f"[{q_idx}/{len(BENCHMARK_QUERIES)}] Query: '{query}' ({category})")
        runs = []

        for r_idx in range(1, REPETITIONS_PER_QUERY + 1):
            sess_id = f"bench-u01-{qid}-run{r_idx}"
            print(f"    Run {r_idx}/{REPETITIONS_PER_QUERY}...", end="", flush=True)
            res = execute_single_query(query, sess_id)
            runs.append(res)
            print(f" Done in {res['client_http_ms']} ms | Gen: {res['timings_ms'].get('generation_ms', 0)} ms | Tok/s: {res['metrics'].get('tokens_per_second', 0)} | Cards: {res['cards_returned']}")

        latencies = [r["client_http_ms"] for r in runs if r["http_status"] == 200]
        gen_times = [r["timings_ms"].get("generation_ms", 0) for r in runs if r["http_status"] == 200]
        tok_per_sec = [r["metrics"].get("tokens_per_second", 0) for r in runs if r["http_status"] == 200]
        out_tokens = [r["metrics"].get("completion_tokens", 0) for r in runs if r["http_status"] == 200]

        summary = {
            "query_id": qid,
            "category": category,
            "query": query,
            "total_runs": len(runs),
            "successful_runs": len(latencies),
            "latency_ms": {
                "min": round(min(latencies), 2) if latencies else None,
                "max": round(max(latencies), 2) if latencies else None,
                "median": round(statistics.median(latencies), 2) if latencies else None,
                "mean": round(statistics.mean(latencies), 2) if latencies else None,
                "spread_ms": round(max(latencies) - min(latencies), 2) if latencies else None
            },
            "generation_ms": {
                "median": round(statistics.median(gen_times), 2) if gen_times else None,
                "mean": round(statistics.mean(gen_times), 2) if gen_times else None
            },
            "tokens_per_second": {
                "median": round(statistics.median(tok_per_sec), 2) if tok_per_sec else None,
                "mean": round(statistics.mean(tok_per_sec), 2) if tok_per_sec else None
            },
            "completion_tokens": {
                "median": int(statistics.median(out_tokens)) if out_tokens else None,
                "mean": round(statistics.mean(out_tokens), 1) if out_tokens else None
            },
            "runs": runs
        }

        benchmark_results.append(summary)
        print(f"    --> Summary: Median Latency = {summary['latency_ms']['median']} ms (range: {summary['latency_ms']['min']} - {summary['latency_ms']['max']} ms), Median Tok/s = {summary['tokens_per_second']['median']}\n")

    evidence = {
        "benchmark_id": "USABILITY-01-PERFORMANCE-EVIDENCE",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "device_info": {
            "device": server_info.get("device"),
            "backend": server_info.get("activeInferenceBackend"),
            "servingMode": server_info.get("servingMode"),
            "quantization": server_info.get("quantization")
        },
        "source_hashes": source_hashes,
        "warmup_run": warmup_res,
        "benchmark_results": benchmark_results
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)

    print("=======================================================")
    print(" BENCHMARK COMPLETED")
    print(f" Evidence written to: {output_path}")
    print("=======================================================\n")
    return benchmark_results


if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent.parent / "docs" / "reviews" / "evidence" / "USABILITY_01_BENCHMARK_EVIDENCE.json"
    run_benchmark(out_file)
