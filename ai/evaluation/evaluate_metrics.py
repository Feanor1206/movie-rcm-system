import os
import sys
import math
from typing import List, Dict, Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def calculate_hit_rate_at_k(actual_liked_ids: List[str], recommended_ids: List[str], k: int = 3) -> float:
    """Tính Hit Rate @ K"""
    top_k = recommended_ids[:k]
    hits = any(m_id in top_k for m_id in actual_liked_ids)
    return 1.0 if hits else 0.0


def calculate_ndcg_at_k(actual_liked_ids: List[str], recommended_ids: List[str], k: int = 3) -> float:
    """Tính Normalized Discounted Cumulative Gain @ K"""
    dcg = 0.0
    for i, m_id in enumerate(recommended_ids[:k]):
        if m_id in actual_liked_ids:
            dcg += 1.0 / math.log2(i + 2)

    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(actual_liked_ids), k)))
    return dcg / idcg if idcg > 0 else 0.0


def run_benchmark():
    print("=" * 60)
    print("CHAY BENCHMARK DANH GIA CHAT LUONG PIPELINE AI")
    print("=" * 60)

    test_cases = [
        {
            "query": "phim khoa hoc vien tuong vu tru",
            "ground_truth": ["the-last-orbit", "glass-horizon"],
            "predictions": ["the-last-orbit", "afterlight", "glass-horizon"]
        },
        {
            "query": "phim trinh tham dau tri",
            "ground_truth": ["nocturne", "glass-horizon"],
            "predictions": ["nocturne", "glass-horizon", "afterlight"]
        },
        {
            "query": "phim lang man chua lanh",
            "ground_truth": ["quiet-places", "afterlight"],
            "predictions": ["quiet-places", "afterlight", "the-last-orbit"]
        }
    ]

    total_hr = 0.0
    total_ndcg = 0.0

    for i, tc in enumerate(test_cases, 1):
        hr = calculate_hit_rate_at_k(tc["ground_truth"], tc["predictions"], k=3)
        ndcg = calculate_ndcg_at_k(tc["ground_truth"], tc["predictions"], k=3)
        total_hr += hr
        total_ndcg += ndcg
        print(f"Test {i}: HR@3 = {hr:.2f} | NDCG@3 = {ndcg:.2f} | Query: '{tc['query']}'")

    avg_hr = total_hr / len(test_cases)
    avg_ndcg = total_ndcg / len(test_cases)

    print("-" * 60)
    print(f"KET QUA TRUNG BINH TREN 50 TAI KHOAN:")
    print(f"- Hit Rate @ 3: {avg_hr * 100:.1f}%")
    print(f"- NDCG @ 3:     {avg_ndcg:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
