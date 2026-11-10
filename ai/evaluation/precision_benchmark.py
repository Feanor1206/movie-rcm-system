import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend" / "fastapi"))

from ai.evaluation.retrieval_gate import _generated_pilot_rows, _project_pilot_drafts
from services.catalog_sync import CatalogSyncManager
from services.encoders import OnnxTextEncoder
from services.text_index import TextIndex, document_text


def compare_rankings(reference_docs, reference_queries, candidate_docs, candidate_queries, self_indices, episode_ids):
    if len(reference_docs) < 11 or len(reference_queries) != len(self_indices) or len(self_indices) != len(episode_ids):
        raise ValueError("Need at least 10 nonself candidates and matching queries")
    scores = []
    for docs, queries in ((reference_docs, reference_queries), (candidate_docs, candidate_queries)):
        similarity = queries @ np.asarray(docs, dtype=np.float16).T
        for row, index in enumerate(self_indices):
            if index is not None:
                similarity[row, index] = -np.inf
        scores.append(np.argsort(-similarity, axis=1, kind="stable")[:, :10])
    result = {}
    for episode in sorted(set(episode_ids)):
        indices = [i for i, value in enumerate(episode_ids) if value == episode]
        overlaps = [len(set(scores[0][i]) & set(scores[1][i])) / 10 for i in indices]
        result[episode] = {"queryCount": len(indices), "meanTop10Overlap": float(np.mean(overlaps))}
    return result


def corpus(original, enriched, selected, cache_dir):
    if (enriched.get("package") or {}).get("id") == "jadoo-partial-dialogue-preview":
        enriched = {**enriched, "package": {**enriched["package"], "id": "jadoo-pilot-dialogue"}}
    generated = _generated_pilot_rows(original, enriched)
    projected, counts = _project_pilot_drafts(enriched, generated, set(selected))
    manager = CatalogSyncManager()
    manager.load_from_payload(projected, include_draft=False, include_private=False)
    items = manager.get_flattened_catalog()
    episodes = [item for item in items if item.get("item_type") == "episode" and item["id"] in selected]
    if {item["id"] for item in episodes} != set(selected):
        raise ValueError("Every selected episode must be published in the source catalog")
    series = {item.get("series_id") for item in episodes}
    items = [item for item in items if item.get("episode_id") in selected or item["id"] in selected
             or (item.get("item_type") == "series" and item["id"] in series)]
    index = TextIndex.build(items, cache_dir=cache_dir, payload=projected)
    docs = index.documents
    query_indices = [i for i, doc in enumerate(docs) if doc.get("item_type") == "dialogue"]
    if not query_indices or {docs[i]["episode_id"] for i in query_indices} != set(selected):
        raise ValueError("Every selected episode must have projected dialogue windows")
    return docs, query_indices, counts


def embeddings(encoder, texts, kind, cache_dir, batch_size):
    key = hashlib.sha256(json.dumps([encoder.model_id, kind, texts], ensure_ascii=False).encode("utf-8")).hexdigest()
    path = cache_dir / (key + ".npy")
    if path.exists():
        result = np.load(path, allow_pickle=False)
        if result.ndim == 2 and len(result) == len(texts) and np.isfinite(result).all():
            return result
        raise ValueError(f"Invalid embedding cache: {path}")
    method = encoder.encode_documents if kind == "documents" else encoder.encode_queries
    result = np.concatenate([method(texts[i:i + batch_size]) for i in range(0, len(texts), batch_size)])
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.save(path, result, allow_pickle=False)
    return result


def run(original, enriched, selected, fp32, int8, cache_dir, batch_size, latency_samples):
    docs, indices, projected_counts = corpus(original, enriched, selected, cache_dir / "index")
    texts = [document_text(doc) for doc in docs]
    queries = [docs[i]["description"] for i in indices]
    episodes = [docs[i]["episode_id"] for i in indices]
    configs = [json.loads((path / "encoder.json").read_text(encoding="utf-8")) for path in (fp32, int8)]
    shared = ("source_model_fingerprint", "pooling", "max_length", "query_prefix", "document_prefix")
    if not configs[0].get("source_model_fingerprint") or any(configs[0].get(k) != configs[1].get(k) for k in shared):
        raise ValueError("FP32 and INT8 artifacts must share source, pooling, limits and prefixes")
    all_vectors = {}
    models = {}
    for name, path, expected in (("fp32", fp32, "fp32"), ("int8", int8, "dynamic-int8")):
        config = json.loads((path / "encoder.json").read_text(encoding="utf-8"))
        if config.get("quantization") != expected:
            raise ValueError(f"{name} artifact has incorrect quantization")
        encoder = OnnxTextEncoder.from_directory(path)
        models[name] = {"id": encoder.model_id, "artifact": str(path), "quantization": expected}
        all_vectors[name] = (embeddings(encoder, texts, "documents", cache_dir, batch_size),
                             embeddings(encoder, queries, "queries", cache_dir, batch_size))
        sample = [queries[i] for i in np.linspace(0, len(queries) - 1, latency_samples, dtype=int)]
        encoder.encode_queries([sample[0]])
        timings = []
        for query in sample:
            start = time.perf_counter()
            encoder.encode_queries([query])
            timings.append((time.perf_counter() - start) * 1000)
        models[name]["warmSingletonQueryLatencyMs"] = {"samples": len(timings),
            "p50": float(np.percentile(timings, 50)), "p95": float(np.percentile(timings, 95))}
        del encoder
        gc.collect()
    ref_docs, ref_queries = all_vectors["fp32"]
    int_docs, int_queries = all_vectors["int8"]
    return {"device": "CPUExecutionProvider", "episodeIds": sorted(selected), "documentCount": len(docs),
            "queryCount": len(queries), "projectedDrafts": projected_counts,
            "querySource": "dialogue window text", "indexScope": "full selected pilot document index",
            "selfPolicy": "exclude query window document by ID", "topK": 10,
            "reference": "FP32 documents and FP32 queries", "documentStorage": "float16",
            "sourceModelFingerprint": configs[0]["source_model_fingerprint"],
            "qualityMetrics": None, "qualityReason": "No independently human-labeled queries supplied",
            "models": models, "perEpisode": {
                "fp32DocumentsInt8Queries": compare_rankings(ref_docs, ref_queries, ref_docs, int_queries, indices, episodes),
                "int8DocumentsInt8Queries": compare_rankings(ref_docs, ref_queries, int_docs, int_queries, indices, episodes)}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-catalog", type=Path, required=True)
    parser.add_argument("--enriched-catalog", type=Path, required=True)
    parser.add_argument("--episode-id", action="append", required=True)
    parser.add_argument("--fp32", type=Path, required=True)
    parser.add_argument("--int8", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--latency-samples", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 64 or args.latency_samples < 1 or len(set(args.episode_id)) != len(args.episode_id):
        parser.error("Invalid batch size, latency sample count or duplicate episode IDs")
    report = run(json.loads(args.original_catalog.read_text(encoding="utf-8-sig")),
                 json.loads(args.enriched_catalog.read_text(encoding="utf-8-sig")), args.episode_id,
                 args.fp32, args.int8, args.cache_dir, args.batch_size, args.latency_samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
