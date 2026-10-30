"""
Benchmark Runner for AI-OPT-01.
Evaluates Qwen3-4B + Phase 23 LoRA and Hybrid Retrieval on the fixed 30-question Jadoo benchmark.
Outputs structured evidence JSON.
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

# Ensure backend/fastapi is on path
backend_fastapi_dir = Path(__file__).resolve().parent.parent / "backend" / "fastapi"
sys.path.insert(0, str(backend_fastapi_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import torch
from services.qwen_service import QwenRecommendationService
from services.catalog_sync import CatalogSyncManager
from services.ai_pipeline import CascadingAIPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark_ai_opt_01")


def get_vram_info():
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated(0) / (1024 ** 2)
        reserved = torch.cuda.memory_reserved(0) / (1024 ** 2)
        total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 2)
        return {
            "device": torch.cuda.get_device_name(0),
            "allocated_mb": round(allocated, 2),
            "reserved_mb": round(reserved, 2),
            "total_mb": round(total, 2)
        }
    return {"device": "cpu"}


def run_benchmark(output_filename: str, run_mode: str = "full"):
    eval_path = Path(__file__).resolve().parent.parent / "docs" / "benchmarks" / "jadoo_30_eval.json"
    if not eval_path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {eval_path}")

    with open(eval_path, "r", encoding="utf-8") as f:
        benchmark_data = json.load(f)
    queries = benchmark_data.get("queries", [])

    catalog_path = Path(__file__).resolve().parent.parent / "data" / "catalog.jadoo_all.json"
    if not catalog_path.exists():
        catalog_path = Path(__file__).resolve().parent.parent / "backend" / "springboot" / "data" / "catalog" / "committed_catalog_snapshot.json"

    logger.info(f"Loading catalog from {catalog_path}...")
    with open(catalog_path, "r", encoding="utf-8") as f:
        raw_catalog = json.load(f)

    catalog_mgr = CatalogSyncManager()
    catalog_mgr.load_from_payload(raw_catalog)
    flattened_catalog = catalog_mgr.get_flattened_catalog()
    logger.info(f"Catalog flattened: {len(flattened_catalog)} items across hierarchy.")

    vram_before = get_vram_info()
    start_ts = datetime.now(timezone.utc).isoformat()

    logger.info("Initializing QwenRecommendationService (serving_mode='full', device='cuda')...")
    qwen = QwenRecommendationService(serving_mode="full", device="cuda")

    t0_load = time.perf_counter()
    qwen.load_model()
    load_time_ms = round((time.perf_counter() - t0_load) * 1000, 2)
    logger.info(f"Model loaded in {load_time_ms} ms")

    vram_after_load = get_vram_info()

    pipeline = CascadingAIPipeline()
    # Ensure pipeline uses our loaded qwen service and catalog
    import services.ai_pipeline as aip
    aip.qwen_service = qwen

    # Warm-up 1 query
    logger.info("Running warm-up inference...")
    try:
        _ = qwen.parse_discovery_intent("Xin Chào Jadoo", catalog=flattened_catalog)
    except Exception as e:
        logger.warning(f"Warm-up exception (non-fatal): {e}")

    results = []
    answerable_hits_1 = 0
    answerable_hits_3 = 0
    answerable_rr_sum = 0.0
    answerable_count = 0

    holdout_hits_1 = 0
    holdout_hits_3 = 0
    holdout_rr_sum = 0.0
    holdout_count = 0

    unanswerable_rejected = 0
    unanswerable_count = 0

    gen_times = []
    tokens_per_secs = []
    total_latencies = []

    for idx, item in enumerate(queries):
        qid = item["id"]
        q_text = item["query"]
        expected_ids = set(item.get("expected_ids", []))
        is_unanswerable = item.get("unanswerable", False)
        is_holdout = item.get("holdout", False)

        logger.info(f"\n[{idx+1}/{len(queries)}] Running ({'HOLDOUT' if is_holdout else 'DEV'}) '{q_text}'...")

        t0_total = time.perf_counter()

        # Step 1: NLU Intent Parsing with timings
        t0_nlu = time.perf_counter()
        raw_parsed = {}
        gen_ms = 0.0
        tok_per_sec = 0.0
        in_tok = 0
        out_tok = 0

        # Direct token-level measurement if GPU model available
        if qwen.is_loaded and qwen.model and qwen.tokenizer:
            try:
                messages = [
                    {"role": "system", "content": qwen.system_prompt_v2_2},
                    {"role": "user", "content": q_text}
                ]
                try:
                    p_text = qwen.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
                except TypeError:
                    p_text = qwen.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

                inputs = qwen.tokenizer(p_text, return_tensors="pt").to(qwen.model.device)
                in_tok = int(inputs.input_ids.shape[1])

                t0_gen = time.perf_counter()
                use_cache_val = getattr(qwen.model.config, "use_cache", True)
                with torch.inference_mode():
                    out_ids = qwen.model.generate(
                        **inputs,
                        max_new_tokens=qwen.max_new_tokens,
                        do_sample=False,
                        use_cache=use_cache_val,
                        pad_token_id=qwen.tokenizer.eos_token_id,
                        eos_token_id=[qwen.tokenizer.eos_token_id, 151643, 151645]
                    )
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                gen_ms = round((time.perf_counter() - t0_gen) * 1000, 2)
                out_tok = int(out_ids.shape[1] - in_tok)
                tok_per_sec = round(out_tok / (gen_ms / 1000.0), 2) if gen_ms > 0 else 0.0

                raw_text = qwen.tokenizer.decode(out_ids[0][in_tok:], skip_special_tokens=True).strip()
                import re
                cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
                s_idx = cleaned.find("{")
                e_idx = cleaned.rfind("}")
                if s_idx != -1 and e_idx != -1:
                    candidate_json = cleaned[s_idx:e_idx+1]
                    try:
                        raw_parsed = json.loads(candidate_json)
                    except json.JSONDecodeError:
                        repaired = candidate_json.rstrip().rstrip(",")
                        open_braces = repaired.count("{") - repaired.count("}")
                        open_brackets = repaired.count("[") - repaired.count("]")
                        if open_brackets > 0:
                            repaired += "]" * open_brackets
                        if open_braces > 0:
                            repaired += "}" * open_braces
                        try:
                            raw_parsed = json.loads(repaired)
                        except Exception:
                            raw_parsed = {}
            except Exception as ex:
                logger.warning(f"Direct generation error: {ex}")
                raw_parsed = {}

        if not raw_parsed:
            # Fallback to pipeline method
            raw_parsed = qwen.parse_discovery_intent(q_text, catalog=flattened_catalog)

        nlu_ms = round((time.perf_counter() - t0_nlu) * 1000, 2)

        # Step 2 & 3: Retrieval via pipeline / index
        t0_ret = time.perf_counter()
        pipeline_out = pipeline.run(
            query=q_text,
            catalog=flattened_catalog,
            session_id=f"bench_{qid}",
            nlu_intent=raw_parsed
        )
        ranked = pipeline_out.get("recommendedMovies", [])
        ret_ms = round((time.perf_counter() - t0_ret) * 1000, 2)

        total_ms = round((time.perf_counter() - t0_total) * 1000, 2)

        retrieved_ids = [m.get("id") for m in ranked]
        top1_id = retrieved_ids[0] if retrieved_ids else None
        top3_ids = retrieved_ids[:3]

        # Calculate metrics
        hit_1 = False
        hit_3 = False
        rr = 0.0

        if is_unanswerable:
            unanswerable_count += 1
            # For unanswerable, success means either empty result or no false hallucinated high-match
            # Or explanation clearly indicating no catalog match
            rejected = (len(retrieved_ids) == 0)
            if rejected:
                unanswerable_rejected += 1
            logger.info(f"  Unanswerable Query -> Rejected/Abstained: {rejected} (Retrieved: {retrieved_ids})")
        else:
            answerable_count += 1
            if top1_id in expected_ids:
                hit_1 = True
                answerable_hits_1 += 1
                rr = 1.0
            elif len(top3_ids) > 1 and top3_ids[1] in expected_ids:
                rr = 0.5
            elif len(top3_ids) > 2 and top3_ids[2] in expected_ids:
                rr = 1.0 / 3.0

            if any(tid in expected_ids for tid in top3_ids):
                hit_3 = True
                answerable_hits_3 += 1

            answerable_rr_sum += rr

            if is_holdout:
                holdout_count += 1
                if hit_1: holdout_hits_1 += 1
                if hit_3: holdout_hits_3 += 1
                holdout_rr_sum += rr

            logger.info(f"  Hit@1: {hit_1}, Hit@3: {hit_3}, RR: {rr:.3f} | Top3: {top3_ids} | Expected: {expected_ids}")

        gen_times.append(gen_ms)
        if tok_per_sec > 0:
            tokens_per_secs.append(tok_per_sec)
        total_latencies.append(total_ms)

        results.append({
            "id": qid,
            "query": q_text,
            "category": item.get("category"),
            "is_holdout": is_holdout,
            "unanswerable": is_unanswerable,
            "expected_ids": list(expected_ids),
            "retrieved_ids": retrieved_ids,
            "hit_at_1": hit_1,
            "hit_at_3": hit_3,
            "reciprocal_rank": rr,
            "tokens": {
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "tokens_per_second": tok_per_sec
            },
            "timings_ms": {
                "generation_ms": gen_ms,
                "nlu_total_ms": nlu_ms,
                "retrieval_ms": ret_ms,
                "total_ms": total_ms
            },
            "parsed_intent": raw_parsed
        })

    # Summary calculations
    import statistics
    median_total_ms = round(statistics.median(total_latencies), 2) if total_latencies else 0.0
    p90_total_ms = round(statistics.quantiles(total_latencies, n=10)[8], 2) if len(total_latencies) >= 10 else (max(total_latencies) if total_latencies else 0.0)
    avg_tok_s = round(sum(tokens_per_secs) / len(tokens_per_secs), 2) if tokens_per_secs else 0.0

    hit1_rate = round(answerable_hits_1 / answerable_count, 4) if answerable_count > 0 else 0.0
    hit3_rate = round(answerable_hits_3 / answerable_count, 4) if answerable_count > 0 else 0.0
    mrr = round(answerable_rr_sum / answerable_count, 4) if answerable_count > 0 else 0.0

    holdout_hit1_rate = round(holdout_hits_1 / holdout_count, 4) if holdout_count > 0 else 0.0
    holdout_hit3_rate = round(holdout_hits_3 / holdout_count, 4) if holdout_count > 0 else 0.0
    holdout_mrr = round(holdout_rr_sum / holdout_count, 4) if holdout_count > 0 else 0.0

    unanswerable_rejection_rate = round(unanswerable_rejected / unanswerable_count, 4) if unanswerable_count > 0 else 1.0

    summary = {
        "benchmark_file": "docs/benchmarks/jadoo_30_eval.json",
        "total_queries": len(queries),
        "answerable_count": answerable_count,
        "holdout_count": holdout_count,
        "unanswerable_count": unanswerable_count,
        "latency": {
            "median_total_ms": median_total_ms,
            "p90_total_ms": p90_total_ms,
            "avg_tokens_per_second": avg_tok_s
        },
        "retrieval_overall": {
            "hit_at_1": hit1_rate,
            "hit_at_3": hit3_rate,
            "mrr": mrr
        },
        "retrieval_holdout": {
            "hit_at_1": holdout_hit1_rate,
            "hit_at_3": holdout_hit3_rate,
            "mrr": holdout_mrr
        },
        "unanswerable_handling": {
            "rejection_rate": unanswerable_rejection_rate,
            "rejected_count": unanswerable_rejected
        }
    }

    report = {
        "timestamp": start_ts,
        "run_mode": run_mode,
        "environment": {
            "python_executable": sys.executable,
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "vram_before": vram_before,
            "vram_after_load": vram_after_load
        },
        "model": {
            "base_model_name": qwen.base_model_name,
            "active_adapter_path": qwen.active_adapter_path,
            "actual_device": qwen.actual_device,
            "quantization": qwen.quantization,
            "load_time_ms": load_time_ms
        },
        "summary": summary,
        "details": results
    }

    out_path = Path(__file__).resolve().parent.parent / "docs" / "reviews" / "evidence" / output_filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"\n========================================================")
    logger.info(f"BENCHMARK COMPLETED: {out_path}")
    logger.info(f"Summary: {json.dumps(summary, indent=2)}")
    logger.info(f"========================================================\n")
    return report


if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "AI_OPT_01_BASELINE_EVIDENCE.json"
    mode = sys.argv[2] if len(sys.argv) > 2 else "baseline"
    run_benchmark(out_file, mode)
