"""
Verification Script for AI-OPT-01-F04:
Verifies behavioral correctness on live production HTTP API:
- B1 Genre / Descriptive Discovery (NOT rejected as foreign franchise):
  1. "Tìm phim hoạt hình gia đình hài hước" -> returns catalog candidates, not empty.
  2. "Gợi ý hoạt hình vui nhộn cho gia đình" -> returns catalog candidates, not empty.
  3. "Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối" -> empty recommendations (preserved foreign franchise rejection).
- B2 Negation Scope & Grounding:
  4. "Jadoo chơi bóng, không phải tập 999" -> NOT Episode 30, NOT Episode 9, NOT exact lookup statement ("Đây là Mùa 1, Tập 30").
  5. "Tập nào Jadoo muốn ăn ngon nhưng sợ bị tăng cân" -> ep_jadoo_s01_0002, cites eating/weight detail.
  6. "Tập nào Jadoo lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ" -> states no matching plot/episode found, does NOT claim match.
- Control Baseline (Preserved):
  7. "Tìm tập Anh sẽ mua cho em tất cả những gì em muốn ăn" -> ep_jadoo_s01_0001 (exact title).
  8. "Xin Chào Jadoo Mùa 1 Tập 1" -> ep_jadoo_s01_0001 (exact S01E01).
  9. "Truyện ngắn Cứu cá vàng và cuộc tình với chàng Romy" -> seg_jadoo_s01_008a (segment).
  10. "Phim hoạt hình Jadoo phát hành năm 2021 không có bạo lực" -> unverified condition note included.

Assesses BEHAVIORAL VERDICTS, not just HTTP 200.
Outputs full evidence JSON at docs/reviews/evidence/AI_OPT_01_F04_WEB_VERIFICATION.json.
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
        "id": "f04_b1_q01_generic_family_comedy",
        "category": "B1_GENRE_DESCRIPTIVE_DISCOVERY",
        "query": "Tìm phim hoạt hình gia đình hài hước",
        "min_results_count": 1,
        "disallowed_empty": True
    },
    {
        "id": "f04_b1_q02_fun_for_family",
        "category": "B1_GENRE_DESCRIPTIVE_DISCOVERY",
        "query": "Gợi ý hoạt hình vui nhộn cho gia đình",
        "min_results_count": 1,
        "disallowed_empty": True
    },
    {
        "id": "f04_b1_q03_doraemon_abstention",
        "category": "B1_FOREIGN_FRANCHISE_ABSTENTION",
        "query": "Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối",
        "expected_empty": True,
        "disallowed_ids": ["ep_jadoo_s03_0009"]
    },
    {
        "id": "f04_b2_q04_negation_scope_not_exact",
        "category": "B2_NEGATION_SCOPE_AND_EXACT_LOOKUP",
        "query": "Jadoo chơi bóng, không phải tập 999",
        "disallowed_episode_num": 9,
        "disallowed_ids": ["ep_jadoo_s01_0030", "ep_jadoo_s04_0009", "ep_jadoo_s03_0009", "ep_jadoo_s01_0009"],
        "forbidden_text_phrases": ["Đây là Mùa 1, Tập 30", "Đây là Tập 30", "Đây là Tập 999"]
    },
    {
        "id": "f04_b2_q05_plot_real_grounding",
        "category": "B2_PLOT_REAL_GROUNDING",
        "query": "Tập nào Jadoo muốn ăn ngon nhưng sợ bị tăng cân",
        "expected_top_id": "ep_jadoo_s01_0002",
        "required_any_phrase": ["ăn", "tăng cân", "muốn ăn nhưng lại sợ tăng cân"]
    },
    {
        "id": "f04_b2_q06_plot_fabricated_ungrounded",
        "category": "B2_PLOT_UNGROUNDED_ABSTENTION",
        "query": "Tập nào Jadoo lái tàu ngầm xuống đáy đại dương bắt cá mập trắng khổng lồ",
        "required_any_phrase": ["chưa tìm thấy", "chưa đủ dữ liệu", "không có", "chưa ghi nhận"]
    },
    {
        "id": "f04_ctrl_q07_exact_title",
        "category": "CTRL_EXACT_TITLE",
        "query": "Tìm tập Anh sẽ mua cho em tất cả những gì em muốn ăn",
        "expected_top_id": "ep_jadoo_s01_0001",
        "expected_type": "episode"
    },
    {
        "id": "f04_ctrl_q08_exact_season_ep",
        "category": "CTRL_EXACT_SEASON_EPISODE",
        "query": "Xin Chào Jadoo Mùa 1 Tập 1",
        "expected_top_id": "ep_jadoo_s01_0001",
        "expected_type": "episode"
    },
    {
        "id": "f04_ctrl_q09_segment",
        "category": "CTRL_SEGMENT",
        "query": "Truyện ngắn Cứu cá vàng và cuộc tình với chàng Romy",
        "expected_top_id": "seg_jadoo_s01_008a",
        "expected_type": "segment"
    },
    {
        "id": "f04_ctrl_q10_condition_violence",
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

    # Case: Generic descriptive queries must return candidates
    if tc.get("disallowed_empty"):
        if not recs:
            return False, "Expected non-empty recommendations for generic discovery query, got 0"
        if len(recs) < tc.get("min_results_count", 1):
            return False, f"Expected at least {tc.get('min_results_count')} results, got {len(recs)}"

    # Case: Exact title match
    if tc.get("expected_top_id"):
        exp_id = tc["expected_top_id"]
        if not recs:
            return False, f"Expected top item {exp_id}, but returned empty results"
        if top_item.get("id") != exp_id:
            return False, f"Top item id={top_item.get('id')}, expected {exp_id}"
        if tc.get("expected_type") and top_item.get("item_type") != tc["expected_type"]:
            return False, f"Top item type={top_item.get('item_type')}, expected {tc['expected_type']}"

    # Case: Foreign franchise abstention
    if tc.get("expected_empty"):
        if recs:
            return False, f"Expected empty recommendations for foreign franchise, got {rec_ids}"
        if tc.get("disallowed_ids"):
            for did in tc["disallowed_ids"]:
                if did in rec_ids:
                    return False, f"Disallowed item {did} was returned"

    # Case: Negation scope and disallowed items
    if tc.get("disallowed_episode_num"):
        bad_ep = tc["disallowed_episode_num"]
        if recs and top_item.get("episode_number") == bad_ep:
            return False, f"Negated episode {bad_ep} was returned as top result"
    if tc.get("disallowed_ids"):
        for did in tc["disallowed_ids"]:
            if recs and top_item.get("id") == did:
                return False, f"Disallowed item {did} returned from negated query"

    # Case: Forbidden text phrases
    if tc.get("forbidden_text_phrases"):
        for fphrase in tc["forbidden_text_phrases"]:
            if fphrase.lower() in explanation.lower():
                return False, f"Forbidden phrase '{fphrase}' found in explanation"

    # Case: Required specific text phrase
    if tc.get("required_text_phrase"):
        req_phrase = tc["required_text_phrase"]
        if req_phrase.lower() not in explanation.lower():
            return False, f"Missing required phrase '{req_phrase}' in explanation"

    # Case: Required ANY phrase from list
    if tc.get("required_any_phrase"):
        phrases = tc["required_any_phrase"]
        if not any(p.lower() in explanation.lower() for p in phrases):
            return False, f"Explanation did not contain any of required phrases: {phrases}"

    # Case: Release year check
    if tc.get("expected_year"):
        exp_year = tc["expected_year"]
        if recs and top_item.get("release_year") != exp_year and top_item.get("year") != exp_year:
            return False, f"Top item year={top_item.get('release_year') or top_item.get('year')}, expected {exp_year}"

    return True, "BEHAVIOR_VERIFIED"


def check_server():
    print(f"[*] Checking server readiness at {READY_ENDPOINT}...")
    req = urllib.request.Request(READY_ENDPOINT, headers={"User-Agent": "F04-Verifier/1.0"})
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
    print(f" STARTING AI-OPT-01-F04 VERIFICATION ({len(TEST_CASES)} queries)")
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
            "sessionId": f"verify-f04-{qid}"
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            CHAT_ENDPOINT,
            data=data_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "F04-Verifier/1.0"},
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
        print(f"    Status: {http_status} | Time: {client_http_ms}ms | Verdict: {verdict}")
        print(f"    Reason: {verdict_reason}")
        print(f"    Top Card: {retrieved_items[0] if retrieved_items else 'EMPTY'}")
        print(f"    Explanation: {explanation[:120]}...\n" if len(explanation) > 120 else f"    Explanation: {explanation}\n")

        results.append({
            "test_id": qid,
            "category": category,
            "query": query,
            "http_status": http_status,
            "client_latency_ms": client_http_ms,
            "verdict": verdict,
            "verdict_reason": verdict_reason,
            "error": error,
            "top_candidate": retrieved_items[0] if retrieved_items else None,
            "returned_count": len(retrieved_items),
            "retrieved_candidates": retrieved_items[:3],
            "explanation": explanation,
            "structured_intent": intent,
            "timings_ms": timings,
            "metrics": metrics
        })

    all_passed = (passed_count == len(TEST_CASES))

    evidence = {
        "benchmark_id": "AI-OPT-01-F04-WEB-VERIFICATION",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_queries": len(TEST_CASES),
        "passed_queries": passed_count,
        "failed_queries": len(TEST_CASES) - passed_count,
        "overall_verdict": "PASS" if all_passed else "FAIL",
        "endpoint": CHAT_ENDPOINT,
        "server_ready": server_info,
        "source_hashes": source_hashes,
        "browser_playback": "UNVERIFIED",
        "test_results": results
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)

    print(f"=======================================================")
    print(f" VERIFICATION COMPLETE: {passed_count}/{len(TEST_CASES)} PASSED")
    print(f" Overall Verdict: {'PASS' if all_passed else 'FAIL'}")
    print(f" Evidence written to: {output_path}")
    print(f"=======================================================\n")
    return all_passed


if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent.parent / "docs" / "reviews" / "evidence" / "AI_OPT_01_F04_WEB_VERIFICATION.json"
    success = run_verification(out_file)
    sys.exit(0 if success else 1)
