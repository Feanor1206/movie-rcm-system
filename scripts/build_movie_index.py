"""
Index Builder for Dippie Cinema Hybrid Retrieval (REC-01).

Builds BM25 statistics and dense embeddings (intfloat/multilingual-e5-small)
for the animation catalog and saves the precomputed index to data/indices/movie_index_v1.json.
"""

import sys
import json
from pathlib import Path

# Add backend/fastapi to sys.path
backend_fastapi_dir = Path(__file__).resolve().parent.parent / "backend" / "fastapi"
sys.path.insert(0, str(backend_fastapi_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from services.qwen_service import DEFAULT_MOVIES
from services.hybrid_retrieval import HybridMovieIndex, DEFAULT_INDEX_PATH
from services.canonical_importer import CanonicalMovieImporter

def load_canonical_catalog() -> list:
    """Load canonical sample and merge with DEFAULT_MOVIES."""
    sample_path = Path(__file__).resolve().parent.parent / "docs" / "contracts" / "canonical_catalog_sample.valid.json"
    movies_by_id = {m["id"]: dict(m) for m in DEFAULT_MOVIES}

    if sample_path.exists():
        importer = CanonicalMovieImporter()
        with open(sample_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for m in data.get("movies", []):
            mapped = importer.map_to_movie_item(m)
            mid = mapped["id"]
            if mid in movies_by_id:
                movies_by_id[mid].update(mapped)
            else:
                movies_by_id[mid] = mapped
        print(f"[INDEX_BUILDER] Loaded canonical enhancements from {sample_path}")

    return list(movies_by_id.values())

def main():
    print("[INDEX_BUILDER] Starting Hybrid Index construction (REC-01)...")
    catalog = load_canonical_catalog()
    print(f"[INDEX_BUILDER] Total catalog size: {len(catalog)} movies")

    index = HybridMovieIndex(index_path=DEFAULT_INDEX_PATH)
    index.build_from_catalog(catalog, save_to_disk=True)

    print(f"[INDEX_BUILDER] Index built successfully!")
    print(f"  - Output file: {DEFAULT_INDEX_PATH}")
    print(f"  - Encoder: {index.metadata_index.get('encoder_id')}")
    print(f"  - Dimensions: {index.metadata_index.get('encoder_dimension')}")
    print(f"  - Content Hash: {index.metadata_index.get('content_hash')}")
    print(f"  - Total Indexed: {index.metadata_index.get('movie_count')} documents")

if __name__ == "__main__":
    main()
