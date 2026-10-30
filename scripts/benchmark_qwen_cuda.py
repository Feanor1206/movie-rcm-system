"""
Direct benchmark for Qwen3-4B + Phase 23 LoRA on RTX 3050 CUDA in dippie-qwen environment.
Measures actual device placement, quantization, VRAM, token counts, generation latency,
and tokens/second. Outputs results to docs/reviews/evidence/ai_cuda_baseline_rec01.json.
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime, timezone

# Add backend/fastapi to sys.path
backend_fastapi_dir = Path(__file__).resolve().parent.parent / "backend" / "fastapi"
sys.path.insert(0, str(backend_fastapi_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import torch
import transformers
import peft
import bitsandbytes
import accelerate
from services.qwen_service import QwenRecommendationService

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

def run_benchmark():
    vram_before = get_vram_info()
    start_ts = datetime.now(timezone.utc).isoformat()

    print("[BENCHMARK] Initializing QwenRecommendationService (serving_mode='full', device='cuda')...")
    service = QwenRecommendationService(serving_mode="full", device="cuda")

    t0_load = time.perf_counter()
    service.load_model()
    load_ms = round((time.perf_counter() - t0_load) * 1000, 2)
    print(f"[BENCHMARK] Model loaded in {load_ms} ms")

    vram_after_load = get_vram_info()
    print(f"[BENCHMARK] VRAM after load: {vram_after_load}")
    print(f"[BENCHMARK] Actual device: {service.actual_device}, Quantization: {service.quantization}")
    print(f"[BENCHMARK] Placement map count: {len(service.device_placement)}")

    queries = [
        "Gợi ý cho tôi 2 phim hoạt hình phiêu lưu trước năm 2010 không có kinh dị",
        "Cô bé vào thế giới linh hồn, bố mẹ thành lợn",
        "Giống Spirited Away nhưng bớt u tối"
    ]

    results = []
    # Test cold then warm
    for idx, q in enumerate(queries):
        is_cold = (idx == 0)
        print(f"\n[BENCHMARK] Running Query {idx+1} ({'COLD' if is_cold else 'WARM'}): '{q}'")

        # 1. System prompt & template
        t0_prep = time.perf_counter()
        messages = [
            {"role": "system", "content": service.system_prompt_v2_2},
            {"role": "user", "content": q}
        ]
        prompt_text = service.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        prep_ms = round((time.perf_counter() - t0_prep) * 1000, 2)

        # 2. Tokenize
        t0_tok = time.perf_counter()
        inputs = service.tokenizer(prompt_text, return_tensors="pt").to(service.model.device)
        input_tokens = int(inputs.input_ids.shape[1])
        tok_ms = round((time.perf_counter() - t0_tok) * 1000, 2)

        # 3. Generate
        t0_gen = time.perf_counter()
        with torch.no_grad():
            out_ids = service.model.generate(
                **inputs,
                max_new_tokens=service.max_new_tokens,
                do_sample=False,
                pad_token_id=service.tokenizer.eos_token_id
            )
        gen_ms = round((time.perf_counter() - t0_gen) * 1000, 2)
        output_tokens = int(out_ids.shape[1] - input_tokens)

        # 4. Decode
        t0_dec = time.perf_counter()
        raw_text = service.tokenizer.decode(out_ids[0][input_tokens:], skip_special_tokens=True).strip()
        dec_ms = round((time.perf_counter() - t0_dec) * 1000, 2)

        tok_per_sec = round(output_tokens / (gen_ms / 1000), 2) if gen_ms > 0 else 0.0

        # 5. Parse
        t0_parse = time.perf_counter()
        parsed_json = None
        parse_valid = False
        try:
            import re
            cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
            # Find first JSON object
            start_idx = cleaned.find("{")
            end_idx = cleaned.rfind("}")
            if start_idx != -1 and end_idx != -1:
                parsed_json = json.loads(cleaned[start_idx:end_idx+1])
                parse_valid = True
        except Exception as e:
            parse_valid = False
        parse_ms = round((time.perf_counter() - t0_parse) * 1000, 2)

        total_ms = round(prep_ms + tok_ms + gen_ms + dec_ms + parse_ms, 2)

        print(f"  -> Generated {output_tokens} tokens in {gen_ms} ms ({tok_per_sec} tok/s), total: {total_ms} ms, JSON valid: {parse_valid}")

        results.append({
            "query": q,
            "is_cold": is_cold,
            "timings_ms": {
                "prep_ms": prep_ms,
                "tokenize_ms": tok_ms,
                "generate_ms": gen_ms,
                "decode_ms": dec_ms,
                "parse_ms": parse_ms,
                "total_ms": total_ms
            },
            "tokens": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "tokens_per_second": tok_per_sec
            },
            "generation_params": {
                "max_new_tokens": service.max_new_tokens,
                "do_sample": False
            },
            "parsed_intent": parsed_json,
            "json_valid": parse_valid
        })

    report = {
        "timestamp": start_ts,
        "environment": {
            "python_executable": sys.executable,
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "transformers_version": transformers.__version__,
            "peft_version": peft.__version__,
            "bitsandbytes_version": bitsandbytes.__version__,
            "accelerate_version": accelerate.__version__,
            "vram_before": vram_before,
            "vram_after_load": vram_after_load
        },
        "model": {
            "base_model_name": service.base_model_name,
            "active_adapter_path": service.active_adapter_path,
            "actual_device": service.actual_device,
            "quantization": service.quantization,
            "actual_dtype": service.actual_dtype,
            "active_inference_backend": service.active_inference_backend,
            "device_placement": service.device_placement,
            "load_time_ms": load_ms
        },
        "benchmark_queries": results
    }

    out_path = Path(__file__).resolve().parent.parent / "docs" / "reviews" / "evidence" / "ai_cuda_baseline_rec01.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n[BENCHMARK] Baseline report saved to {out_path}")

if __name__ == "__main__":
    run_benchmark()
