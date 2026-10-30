"""
Verification Script for AI-OPT-01-F03:
Verifies behavioral correctness on live production HTTP API:
- 4 R1 Failure Cases:
  1. Exact Title ("Tìm tập Anh sẽ mua cho em tất cả những gì em muốn ăn" -> ep_jadoo_s01_0001)
  2. Doraemon Foreign Franchise Abstention ("Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối" -> empty cards, no Jadoo card)
  3. Conflict Episode Number vs Title ("Jadoo tập 2 Jadoo chơi bóng" -> Tập 2 preserved, NOT seg_jadoo_s01_008a)
  4. Negation Scope ("Jadoo chơi bóng, không phải tập 999" -> NOT Episode 9)
- 4 Control Cases:
  5. Exact Series ("Tìm phim hoạt hình Xin Chào Jadoo" -> ser_jadoo)
  6. Exact Season/Episode ("Xin Chào Jadoo Mùa 1 Tập 1" -> ep_jadoo_s01_0001)
  7. Segment / Scene ("Truyện ngắn Cứu cá vàng và cuộc tình với chàng Romy" -> seg_jadoo_s01_008a)
  8. Missing Condition ("Phim hoạt hình Jadoo phát hành năm 2021 không có bạo lực" -> unverified condition note)

Assesses BEHAVIORAL VERDICTS, not just HTTP 200.
Outputs full evidence JSON at docs/reviews/evidence/AI_OPT_01_F03_WEB_VERIFICATION.json.
"""

import sys
import json
import time
import urllib.request
import urllib.error
import hashlib
from pathlib import Path
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SERVER_URL = "http://127.0.0.1:8000"
CHAT_ENDPOINT = f"{SERVER_URL}/api/chat"
READY_ENDPOINT = f"{SERVER_URL}/ready"

TEST_CASES = [
    {
        "id": "f03_r1_q01_exact_title",
        "category": "R1_EXACT_TITLE",
        "query": "Tìm tập Anh sẽ mua cho em tất cả những gì em muốn ăn",
        "expected_top_id": "ep_jadoo_s01_0001",
        "expected_type": "episode"
    },
    {
        "id": "f03_r1_q02_doraemon_abstention",
        "category": "R1_FOREIGN_FRANCHISE_ABSTENTION",
        "query": "Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối",
        "expected_empty": True,
        "disallowed_ids": ["ep_jadoo_s03_0009"]
    },
    {
        "id": "f03_r1_q03_conflict_preserved",
        "category": "R1_CONFLICT_EPISODE_PRESERVED",
        "query": "Jadoo tập 2 Jadoo chơi bóng",
        "expected_episode_num": 2,
        "disallowed_ids": ["seg_jadoo_s01_008a", "ep_jadoo_s01_0008"]
    },
    {
        "id": "f03_r1_q04_negation_scope",
        "category": "R1_NEGATION_SCOPE",
        "query": "Jadoo chơi bóng, không phải tập 999",
        "disallowed_episode_num": 9,
        "disallowed_ids": ["ep_jadoo_s04_0009", "ep_jadoo_s03_0009", "ep_jadoo_s01_0009"]
    },
    {
        "id": "f03_ctrl_q05_exact_series",
        "category": "CTRL_EXACT_SERIES",
        "query": "Tìm phim hoạt hình Xin Chào Jadoo",
        "expected_top_id": "ser_jadoo",
        "expected_type": "series"
    },
    {
        "id": "f03_ctrl_q06_exact_season_ep",
        "category": "CTRL_EXACT_SEASON_EPISODE",
        "query": "Xin Chào Jadoo Mùa 1 Tập 1",
        "expected_top_id": "ep_jadoo_s01_0001",
        "expected_type": "episode"
    },
    {
        "id": "f03_ctrl_q07_segment",
        "category": "CTRL_SEGMENT",
        "query": "Truyện ngắn Cứu cá vàng và cuộc tình với chàng Romy",
        "expected_top_id": "seg_jadoo_s01_008a",
        "expected_type": "segment"
    },
    {
        "id": "f03_ctrl_q08_condition_violence",
        "category": "CTRL_UNVERIFIED_CONDITION",
        "query": "Phim hoạt hình Jadoo phát hành năm 2021 không có bạo lực",
        "expected_year": 2021,
        "required_text_phrase": "chưa đủ để xác nhận"
    }
]


def evaluate_case_verdict(tc: dict, resp_json: dict, http_status: int) -> tuple[bool, str]:
    if http_status != 200:
        return False, f"HTTP failure status={http_status}"

    recs = resp_json.get("recommendedMovies") or resp_json.get("data", {}).get("recommendations", [])
    explanation = resp_json.get("text") or resp_json.get("data", {}).get("explanation", "")
    rec_ids = [m.get("id") for m in recs]
    top_item = recs[0] if recs else {}

    # Case 1: Exact title match
    if tc.get("expected_top_id"):
        exp_id = tc["expected_top_id"]
        if not recs:
            return False, f"Expected top item {exp_id}, but returned empty results"
        if top_item.get("id") != exp_id:
            return False, f"Top item id={top_item.get('id')}, expected {exp_id}"
        if tc.get("expected_type") and top_item.get("item_type") != tc["expected_type"]:
            return False, f"Top item type={top_item.get('item_type')}, expected {tc['expected_type']}"

    # Case 2: Foreign franchise abstention
    if tc.get("expected_empty"):
        if recs:
            return False, f"Expected empty recommendations for foreign franchise, got {rec_ids}"
        if tc.get("disallowed_ids"):
            for did in tc["disallowed_ids"]:
                if did in rec_ids:
                    return False, f"Disallowed item {did} was returned"

    # Case 3: Conflict episode number preserved
    if tc.get("expected_episode_num"):
        exp_ep = tc["expected_episode_num"]
        if tc.get("disallowed_ids"):
            for did in tc["disallowed_ids"]:
                if did in rec_ids:
                    return False, f"Disallowed item {did} returned as answer to episode conflict"
        if recs and top_item.get("episode_number") != exp_ep:
            return False, f"Top item episode_number={top_item.get('episode_number')}, expected {exp_ep}"

    # Case 4: Negation scope
    if tc.get("disallowed_episode_num"):
        bad_ep = tc["disallowed_episode_num"]
        if recs and top_item.get("episode_number") == bad_ep:
            return False, f"Negated episode {bad_ep} was returned as top result"
        if tc.get("disallowed_ids"):
            for did in tc["disallowed_ids"]:
                if recs and top_item.get("id") == did:
                    return False, f"Disallowed item {did} returned from negated query"

    # Case 8: Required text phrase for unverified condition
    if tc.get("required_text_phrase"):
        req_phrase = tc["required_text_phrase"]
        if req_phrase.lower() not in explanation.lower():
            return False, f"Missing required condition phrase '{req_phrase}' in explanation"

    return True, "BEHAVIOR_VERIFIED"


def check_server():
    print(f"[*] Checking server readiness at {READY_ENDPOINT}...")
    req = urllib.request.Request(READY_ENDPOINT, headers={"User-Agent": "F03-Verifier/1.0"})
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


def run_verification(output_path: Path):
    server_info = check_server()
    source_hashes = compute_source_hashes()

    results = []
    print(f"\n=======================================================")
    print(f" STARTING AI-OPT-01-F03 VERIFICATION ({len(TEST_CASES)} queries)")
    print(f" Endpoint: {CHAT_ENDPOINT}")
    print(f"=======================================================\n")

    passed_count = 0

    for idx, tc in enumerate(TEST_CASES, 1):
        qid = tc["id"]
        category = tc["category"]
        query = tc["query"]

        payload = {
            "query": query,
            "messages": [{"role": "user", "content": query}],
            "sessionId": f"verify-f03-{qid}"
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            CHAT_ENDPOINT,
            data=data_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "F03-Verifier/1.0"},
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

        is_pass, verdict_reason = evaluate_case_verdict(tc, resp_json, http_status)
        verdict = "PASS" if is_pass else "FAIL"
        if is_pass:
            passed_count += 1

        print(f"[{idx:02d}/{len(TEST_CASES)}] {qid} ({category}): '{query}'")
        print(f"     -> HTTP {http_status} in {client_http_ms:.1f}ms (gen: {timings.get('generation_ms', 0):.1f}ms, ret: {timings.get('retrieval_ms', 0):.1f}ms, tok/s: {metrics.get('tokens_per_second', 0):.1f})")
        print(f"     -> Retrieved: {[m['id'] for m in retrieved_items]}")
        print(f"     -> Explanation: \"{explanation[:120]}...\"")
        print(f"     -> VERDICT: [{verdict}] ({verdict_reason})\n")

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
            "verdict": verdict,
            "verdict_reason": verdict_reason,
            "error": error
        })

    summary = {
        "total": len(TEST_CASES),
        "passed": passed_count,
        "failed": len(TEST_CASES) - passed_count,
        "pass_rate": f"{passed_count / len(TEST_CASES) * 100:.1f}%",
        "overall_status": "PASSED" if passed_count == len(TEST_CASES) else "FAILED"
    }

    evidence = {
        "metadata": {
            "task": "AI-OPT-01-F03",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_info": server_info,
            "source_hashes": source_hashes,
            "summary": summary
        },
        "results": results
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)

    print(f"\n=======================================================")
    print(f" SUMMARY: {passed_count}/{len(TEST_CASES)} PASSED ({summary['pass_rate']}) - {summary['overall_status']}")
    print(f" Evidence saved to: {output_path}")
    print(f"=======================================================\n")


if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent.parent / "docs" / "reviews" / "evidence" / "AI_OPT_01_F03_WEB_VERIFICATION.json"
    run_verification(out_file)
