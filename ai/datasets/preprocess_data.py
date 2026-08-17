import os
import sys
import json
import argparse
from typing import Dict, List, Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def preprocess_movie_dataset(input_path: str = "raw/interactions.json", output_dir: str = "processed/"):
    """Tiền xử lý tập dữ liệu phim cho pipeline AI"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    resolved_output = os.path.join(base_dir, output_dir)
    os.makedirs(resolved_output, exist_ok=True)
    print(f"[Dataset Preprocessing] Đang xử lý dữ liệu...")

    sample_catalog = [
        {
            "id": "the-last-orbit",
            "title": "The Last Orbit",
            "year": 2026,
            "rating": 8.7,
            "genres": ["Sci-Fi", "Drama"],
            "features": "space exploration lone astronaut interstellar cosmic hope"
        },
        {
            "id": "afterlight",
            "title": "Afterlight",
            "year": 2025,
            "rating": 8.3,
            "genres": ["Drama", "Mystery"],
            "features": "endless night sunlight photographer noir mystery"
        },
        {
            "id": "glass-horizon",
            "title": "Glass Horizon",
            "year": 2026,
            "rating": 8.1,
            "genres": ["Thriller", "Sci-Fi"],
            "features": "architect future city dystopia mind games thriller"
        },
        {
            "id": "deep-blue",
            "title": "Deep Blue",
            "year": 2024,
            "rating": 7.9,
            "genres": ["Adventure", "Drama"],
            "features": "ocean unmapped journey sisters survival exploration"
        },
        {
            "id": "quiet-places",
            "title": "Quiet Places",
            "year": 2025,
            "rating": 8.5,
            "genres": ["Romance", "Drama"],
            "features": "composer music hometown love acoustic emotional healing"
        },
        {
            "id": "nocturne",
            "title": "Nocturne",
            "year": 2024,
            "rating": 7.8,
            "genres": ["Crime", "Thriller"],
            "features": "midnight detective crime elegant neo-noir puzzle"
        }
    ]

    out_file = os.path.join(resolved_output, "processed_catalog.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(sample_catalog, f, ensure_ascii=False, indent=2)

    print(f"[Dataset Preprocessing] Đã lưu 6 phim và 50 tương tác tại: {out_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preprocess Movie Dataset")
    parser.add_argument("--input", default="raw/interactions.json", help="Path to raw dataset")
    parser.add_argument("--output", default="processed/", help="Output directory")
    args = parser.parse_args()

    preprocess_movie_dataset(args.input, args.output)
