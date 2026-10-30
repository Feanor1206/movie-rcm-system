"""
Verification Script for AI-OPT-01-F02:
Runs a curated set of 10 queries covering all target behaviors via production HTTP API:
- Exact Series (Q1)
- Exact Title (Q2)
- Plot search (Q3)
- Exact Season/Episode (Q4)
- Segment / Scene (Q5)
- Metadata condition / No violence (Q6)
- Out-of-catalog abstention (Q7)
- Out-of-catalog with keyword overlap (Q8)
- Negation scope with nonexistent ep (Q9 - F1 repro)
- Conflict episode number vs title (Q10 - F1 repro)

Outputs full evidence JSON including question, intent, IDs, response explanation, and timings.
"""

import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SERVER_URL = "http://127.0.0.1:8000"
CHAT_ENDPOINT = f"{SERVER_URL}/api/chat"
READY_ENDPOINT = f"{SERVER_URL}/ready"

TEST_QUERIES = [
    {
        "id": "f02_q01_exact_series",
        "category": "EXACT_SERIES",
        "query": "Tìm phim hoạt hình Xin Chào Jadoo"
    },
    {
        "id": "f02_q02_exact_title",
        "category": "EXACT_TITLE",
        "query": "Tìm tập Anh sẽ mua cho em tất cả những gì em muốn ăn"
    },
    {
        "id": "f02_q03_plot_search",
        "category": "PLOT_SEARCH",
        "query": "Tập nào Jadoo muốn ăn ngon nhưng lại sợ bị mập tăng cân"
    },
    {
        "id": "f02_q04_exact_season_ep",
        "category": "EXACT_SEASON_EPISODE",
        "query": "Xin Chào Jadoo Mùa 1 Tập 1"
    },
    {
        "id": "f02_q05_segment",
        "category": "SEGMENT_SCENE",
        "query": "Truyện ngắn Cứu cá vàng và cuộc tình với chàng Romy"
    },
    {
        "id": "f02_q06_condition_no_violence",
        "category": "MISSING_CONDITION_NO_VIOLENCE",
        "query": "Phim hoạt hình Jadoo phát hành năm 2021 không có bạo lực"
    },
    {
        "id": "f02_q07_foreign_franchise",
        "category": "OUT_OF_CATALOG_FOREIGN",
        "query": "Gợi ý phim hoạt hình Dragon Ball Bảy Viên Ngọc Rồng"
    },
    {
        "id": "f02_q08_doraemon_overlap",
        "category": "OUT_OF_CATALOG_OVERLAP",
        "query": "Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối"
    },
    {
        "id": "f02_q09_negation_scope",
        "category": "NEGATION_SCOPE_F1",
        "query": "Jadoo chơi bóng, không phải tập 999"
    },
    {
        "id": "f02_q10_conflict_ep_title",
        "category": "CONFLICT_EP_TITLE_F1",
        "query": "Jadoo tập 2 Jadoo chơi bóng"
    }
]


def check_server():
    print(f"[*] Checking server readiness at {READY_ENDPOINT}...")
    req = urllib.request.Request(READY_ENDPOINT, headers={"User-Agent": "F02-Verifier/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"[+] Server Ready: mode={data.get('servingMode')}, backend={data.get('activeInferenceBackend')}, phase23Loaded={data.get('phase23AdapterLoaded')}")
        if data.get("servingMode") != "full" or data.get("degraded") is True:
            raise RuntimeError(f"Server is not in full mode: {data}")
        return data


def run_verification(output_path: Path):
    server_info = check_server()

    results = []
    print(f"\n=======================================================")
    print(f" STARTING AI-OPT-01-F02 VERIFICATION ({len(TEST_QUERIES)} queries)")
    print(f" Endpoint: {CHAT_ENDPOINT}")
    print(f"=======================================================\n")

    for idx, tq in enumerate(TEST_QUERIES, 1):
        qid = tq["id"]
        category = tq["category"]
        query = tq["query"]

        payload = {
            "query": query,
            "messages": [{"role": "user", "content": query}],
            "sessionId": f"verify-f02-{qid}"
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            CHAT_ENDPOINT,
            data=data_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "F02-Verifier/1.0"},
            method="POST"
        )

        t_start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
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

        recs = resp_json.get("recommendedMovies") or resp_json.get("data", {}).get("recommendations", [])
        explanation = resp_json.get("text") or resp_json.get("data", {}).get("explanation", "")
        stages = resp_json.get("pipelineStages", {})
        timings = stages.get("timings_ms", {})
        metrics = stages.get("metrics", {})
        intent = resp_json.get("structuredIntent") or stages.get("nluIntent", {})

        retrieved_items = [
            {
                "id": m.get("id"),
                "title": m.get("title"),
                "item_type": m.get("item_type"),
                "season_number": m.get("season_number"),
                "episode_number": m.get("episode_number")
            }
            for m in recs
        ]

        print(f"[{idx:02d}/{len(TEST_QUERIES)}] {qid} ({category}): '{query}'")
        print(f"     -> HTTP {http_status} in {client_http_ms:.1f}ms (gen: {timings.get('generation_ms', 0):.1f}ms, ret: {timings.get('retrieval_ms', 0):.1f}ms, tok/s: {metrics.get('tokens_per_second', 0):.1f})")
        print(f"     -> Retrieved: {[m['id'] for m in retrieved_items]}")
        print(f"     -> Explanation: \"{explanation[:120]}...\"\n")

        results.append({
            "id": qid,
            "category": category,
            "query": query,
            "http_status": http_status,
            "client_http_ms": client_http_ms,
            "retrieved_items": retrieved_items,
            "explanation": explanation,
            "timings_ms": timings,
            "metrics": metrics,
            "intent": intent,
            "error": error
        })

    evidence = {
        "metadata": {
            "task": "AI-OPT-01-F02",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_info": server_info,
            "total_queries": len(results)
        },
        "results": results
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)

    print(f"[+] Verification completed! Evidence saved to: {output_path}")


if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent.parent / "docs" / "reviews" / "evidence" / "AI_OPT_01_F02_WEB_VERIFICATION.json"
    run_verification(out_file)
