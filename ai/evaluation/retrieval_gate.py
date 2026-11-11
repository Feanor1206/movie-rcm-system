import argparse
import csv
import json
import math
from pathlib import Path
import re
import sys


METRICS = ("recallAt5", "mrr", "momentRecallAt5")
SEARCH_CSV_FIELDS = ("query", "episode_id", "start_ms", "end_ms", "writer", "notes")
ROOT = Path(__file__).resolve().parents[2]
FASTAPI_PATH = str(ROOT / "backend" / "fastapi")
if FASTAPI_PATH not in sys.path:
    sys.path.insert(0, FASTAPI_PATH)


def _rows_by_id(rows):
    mapping = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError("Each row requires a nonempty string id")
        if row["id"] in mapping:
            raise ValueError("Evaluation rows contain duplicate query ids")
        mapping[row["id"]] = row
    return mapping


def run_cases(search_fn, cases):
    _rows_by_id(cases)
    return [{"id": row["id"], "results": search_fn(row["query"])} for row in cases]


def _episode_results(results):
    if not isinstance(results, list):
        raise ValueError("Prediction results must be a list of result objects")
    episodes = {}
    for item in results:
        if not isinstance(item, dict):
            raise ValueError("Prediction results must be a list of result objects")
        episode_id = item.get("episodeId")
        if episode_id is None:
            continue
        if not isinstance(episode_id, str) or not episode_id:
            raise ValueError("A predicted episodeId must be a nonempty string or null")
        episodes.setdefault(episode_id, item)
    return episodes.values()


def _valid_timestamp(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and 0 <= value <= 2**63 - 1


def measure(labels, predictions):
    expected = _rows_by_id(labels)
    observed = _rows_by_id(predictions)
    if not expected or set(expected) != set(observed):
        raise ValueError("Labels and predictions must contain the same query ids")
    recall_at1 = recall_at5 = reciprocal_rank = 0.0
    moment_hits = moment_count = episode_moment_hits = accurate_episode_hits = 0
    for query_id, label in expected.items():
        relevant = label.get("episodeIds")
        if not isinstance(relevant, list) or not relevant or not all(isinstance(item, str) and item for item in relevant):
            raise ValueError("Labels require at least one relevant episodeId")
        relevant = set(relevant)
        results = _episode_results(observed[query_id].get("results"))
        found = [(rank, item) for rank, item in enumerate(results, 1) if item.get("episodeId") in relevant]
        recall_at1 += sum(rank == 1 for rank, _ in found) / len(relevant)
        recall_at5 += sum(rank <= 5 for rank, _ in found) / len(relevant)
        reciprocal_rank += 1 / found[0][0] if found else 0
        moments = label.get("moments", [])
        if moments:
            if not isinstance(moments, list) or not all(
                    isinstance(item, dict) and item.get("episodeId") in relevant
                    and _valid_timestamp(item.get("startMs")) for item in moments):
                raise ValueError("Moment labels require a relevant episodeId and finite startMs")
            moment_count += 1
            matched_moment = False
            for rank, item in found:
                if rank > 5:
                    break
                times = [moment["startMs"] for moment in moments if moment["episodeId"] == item["episodeId"]]
                if not times:
                    continue
                episode_moment_hits += 1
                start = item.get("startMs")
                if _valid_timestamp(start) and any(abs(label_start - start) <= 30_000 for label_start in times):
                    accurate_episode_hits += 1
                    matched_moment = True
            moment_hits += matched_moment
    return {"recallAt1": recall_at1 / len(expected), "recallAt5": recall_at5 / len(expected),
            "mrr": reciprocal_rank / len(expected),
            "momentRecallAt5": moment_hits / moment_count if moment_count else None,
            "timeHitRateAt5": accurate_episode_hits / episode_moment_hits if episode_moment_hits else None}



def measure_per_episode(labels, predictions):
    observed = _rows_by_id(predictions)
    result = {}
    for episode in sorted({episode for row in labels for episode in row["episodeIds"]}):
        subset = [{**row, "episodeIds": [episode],
                   "moments": [moment for moment in row.get("moments", []) if moment["episodeId"] == episode]}
                  for row in labels if episode in row["episodeIds"]]
        result[episode] = {"queryCount": len(subset),
                           "metrics": measure(subset, [observed[row["id"]] for row in subset])}
    return result

def gate(labels, predictions, baseline, thresholds):
    if not labels or any(row.get("source") != "human" for row in labels):
        raise ValueError("Quality gate requires independently human-authored labels")
    if not isinstance(thresholds, dict) or any(
            key not in thresholds or not isinstance(thresholds[key], (float, int))
            or not math.isfinite(thresholds[key]) or not 0 <= thresholds[key] <= 1 for key in METRICS):
        raise ValueError("Configure all metric thresholds as probabilities between zero and one")
    current = measure(labels, predictions)
    previous = measure(labels, baseline)
    if current["momentRecallAt5"] is None:
        raise ValueError("Quality gate requires held-out moment labels")
    reasons = []
    for key in METRICS:
        if current[key] < thresholds[key]:
            reasons.append(f"{key} below configured threshold")
        if current[key] <= previous[key]:
            reasons.append(f"{key} did not improve over baseline")
    return {"passed": not reasons, "metrics": current, "baseline": previous, "reasons": reasons}


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _csv_timestamp(value, name, line_number):
    if not value:
        return None
    if len(value) > 19 or not value.isdecimal() or not _valid_timestamp(int(value)):
        raise ValueError(f"CSV line {line_number}: {name} must be nonnegative whole milliseconds")
    return int(value)


def read_labels(path):
    path = Path(path)
    if path.suffix.lower() != ".csv":
        return read_jsonl(path)
    labels = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, strict=True)
            if tuple(reader.fieldnames or ()) != SEARCH_CSV_FIELDS:
                raise ValueError(f"Search CSV header must be {','.join(SEARCH_CSV_FIELDS)}")
            for row in reader:
                number = reader.line_num
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"CSV line {number}: expected {len(SEARCH_CSV_FIELDS)} columns")
                query, episode_id, start, end, writer, notes = (row[name].strip() for name in SEARCH_CSV_FIELDS)
                if not query or not episode_id or not writer:
                    raise ValueError(f"CSV line {number}: query, episode_id and writer are required")
                start = _csv_timestamp(start, "start_ms", number)
                end = _csv_timestamp(end, "end_ms", number)
                if end is not None and (start is None or end < start):
                    raise ValueError(f"CSV line {number}: end_ms requires start_ms and cannot precede it")
                moments = [] if start is None else [{"episodeId": episode_id, "startMs": start, "endMs": end}]
                labels.append({"id": f"q{len(labels) + 1}", "query": query, "episodeIds": [episode_id],
                               "moments": moments, "source": "human", "writer": writer, "notes": notes})
    except csv.Error as exc:
        raise ValueError(f"Invalid search CSV: {exc}") from exc
    if not labels:
        raise ValueError("Search CSV contains no human labels; fill in the template before evaluation")
    return labels


def _episode_ids(payload):
    if not isinstance(payload, dict) or payload.get("schema_version") != "dippie.catalog.v1":
        raise ValueError("Evaluation requires dippie.catalog.v1 catalog snapshots")
    episodes = payload.get("episodes")
    if not isinstance(episodes, list) or not all(isinstance(ep, dict) and isinstance(ep.get("id"), str)
                                                 and ep["id"] for ep in episodes):
        raise ValueError("Catalog episodes must have nonempty IDs")
    ids = {ep["id"] for ep in episodes}
    if len(ids) != len(episodes):
        raise ValueError("Catalog contains duplicate episode IDs")
    return ids


def _changed_rows(original, enriched, table):
    previous = {row["id"]: row for row in original.get(table, [])}
    return [row for row in enriched.get(table, []) if row != previous.get(row["id"])]


def _generated_pilot_rows(original, enriched):
    generated = {"episodes": {}, "scenes": {}, "text_tracks": {}}
    if (enriched.get("package") or {}).get("id") not in {"jadoo-pilot-dialogue", "jadoo-pilot-enriched"}:
        return generated
    coverage = {}
    for asset in enriched.get("media_assets", []):
        if (asset.get("access_policy", "public") != "public" or asset.get("enabled", True) is not True
                or (asset.get("record") or {}).get("status") in ("draft", "archived")):
            continue
        coverage[asset["id"]] = {row["episode_id"] for row in asset.get("coverage", [])
                                 if row.get("scope") == "full_episode"}
    for row in _changed_rows(original, enriched, "text_tracks"):
        episode_id = row["id"].removesuffix(".track.asr.vi")
        if (row["id"] == f"{episode_id}.track.asr.vi" and episode_id in coverage.get(row.get("media_asset_id"), ())
                and _record_provenance(row).get("origin") == "machine_generated"):
            generated["text_tracks"][row["id"]] = episode_id
    for row in _changed_rows(original, enriched, "scenes"):
        episode_id = row["episode_id"]
        if (episode_id in coverage.get(row.get("media_asset_id"), ())
                and re.fullmatch(re.escape(episode_id) + r"\.scene\.\d{4}", row["id"])
                and _record_provenance(row).get("origin") == "machine_generated"):
            generated["scenes"][row["id"]] = episode_id
    members = set(generated["text_tracks"].values()) | set(generated["scenes"].values())
    published = {row["id"] for row in original["episodes"]
                 if (row.get("record") or {}).get("status") not in ("draft", "archived")}
    for row in _changed_rows(original, enriched, "episodes"):
        provenance = _record_provenance(row)
        if (row["id"] in members & published and provenance.get("origin") == "machine_generated"
                and provenance.get("note") == "Generated fields: synopsis, plot_facts"):
            generated["episodes"][row["id"]] = row["id"]
    return generated


def _record_provenance(row):
    return (row.get("record") or {}).get("provenance") or {}


def _project_pilot_drafts(enriched, generated, selected):
    projection = dict(enriched)
    counts = {}
    for table, members in generated.items():
        projected_rows = []
        count = 0
        for row in enriched.get(table, []):
            record = row.get("record") or {}
            if members.get(row["id"]) in selected and record.get("status") == "draft":
                row = {**row, "record": {**record, "status": "ready"}}
                count += 1
            projected_rows.append(row)
        projection[table] = projected_rows
        counts[table] = count
    return projection, counts


def compare_catalogs(labels, original, enriched, encoder, cache_dir, pilot_ids=None):
    from services.catalog_sync import CatalogSyncManager
    from services.text_index import TextIndex, prepare_embeddings

    if not labels or any(row.get("source") != "human" for row in labels):
        raise ValueError("Pilot comparison requires human labels")
    original_ids, enriched_ids = _episode_ids(original), _episode_ids(enriched)
    generated = _generated_pilot_rows(original, enriched)
    if pilot_ids is not None:
        selected = set(pilot_ids)
    elif enriched_ids < original_ids:
        selected = enriched_ids
    else:
        selected = set(generated["text_tracks"].values()) | set(generated["scenes"].values())
        if not selected:
            selected = {row["episode_id"] for row in _changed_rows(original, enriched, "scenes")}
    if not 1 <= len(selected) <= 5:
        raise ValueError("Select one to five pilot episodes with --episode-id or provide an enriched pilot snapshot")
    if not selected <= (original_ids & enriched_ids):
        raise ValueError("Every pilot episode must exist in both catalog snapshots")
    if any(not row.get("episodeIds") or set(row["episodeIds"]) - selected for row in labels):
        raise ValueError("The search labels include an episode outside the pilot")

    configurations = {}
    hashes = {"original": CatalogSyncManager.compute_hash(original), "enriched": CatalogSyncManager.compute_hash(enriched)}
    projected, projected_counts = _project_pilot_drafts(enriched, generated, selected)
    for catalog_name, payload in (("original", original), ("enriched", projected)):
        manager = CatalogSyncManager()
        manager.load_from_payload(payload, include_draft=False, include_private=False)
        items = manager.get_flattened_catalog()
        episodes = [item for item in items if item.get("item_type") == "episode" and item["id"] in selected]
        if {item["id"] for item in episodes} != selected:
            raise ValueError(f"The {catalog_name} snapshot excludes an unpublished pilot episode")
        series_ids = {item.get("series_id") for item in episodes}
        documents = [item for item in items if item.get("episode_id") in selected or item["id"] in selected
                     or (item.get("item_type") == "series" and item["id"] in series_ids)]
        options = {"cache_dir": Path(cache_dir) / catalog_name, "payload": payload,
                   "content_hash": manager.content_hash}
        lexical = TextIndex.build(documents, **options)
        hybrid = prepare_embeddings(documents, encoder=encoder, model_id=encoder.model_id, **options)
        if not hybrid.dense_ready:
            raise ValueError(f"Dense index is unavailable for the {catalog_name} snapshot")
        for mode, index in (("Bm25", lexical), ("Hybrid", hybrid)):
            predictions = run_cases(lambda query: index.search(query, limit=30), labels)
            configurations[catalog_name + mode] = {"denseReady": index.dense_ready,
                                                    "metrics": measure(labels, predictions),
                                                    "perEpisode": measure_per_episode(labels, predictions)}
    return {"queryCount": len(labels), "pilotEpisodeIds": sorted(selected), "modelId": encoder.model_id,
            "catalogHashes": hashes, "projectedDrafts": projected_counts, "configurations": configurations}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--thresholds", type=Path)
    parser.add_argument("--original-catalog", type=Path, help="Original catalog for the four-way pilot comparison")
    parser.add_argument("--enriched-catalog", type=Path, help="Enriched catalog for the four-way pilot comparison")
    parser.add_argument("--encoder", type=Path, help="Local ONNX encoder artifact directory")
    parser.add_argument("--episode-id", action="append", help="Pilot episode ID; repeat to select a fixed pilot")
    parser.add_argument("--cache-dir", type=Path, help="Dedicated cache root for the pilot comparison")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    compare_inputs = (args.original_catalog, args.enriched_catalog, args.encoder)
    gate_inputs = (args.predictions, args.baseline, args.thresholds)
    compare_mode = any(compare_inputs) or args.episode_id is not None or args.cache_dir is not None
    if compare_mode and (not all(compare_inputs) or any(gate_inputs)):
        parser.error("Comparison requires --original-catalog, --enriched-catalog and --encoder")
    if not compare_mode and not all(gate_inputs):
        parser.error("Quality gate requires --predictions, --baseline and --thresholds")
    try:
        labels = read_labels(args.labels)
        if compare_mode:
            from services.encoders import OnnxTextEncoder

            original = json.loads(args.original_catalog.read_text(encoding="utf-8"))
            enriched = json.loads(args.enriched_catalog.read_text(encoding="utf-8"))
            cache_dir = args.cache_dir or ROOT / "data" / "indices" / "pilot_evaluation"
            report = compare_catalogs(labels, original, enriched, OnnxTextEncoder.from_directory(args.encoder),
                                      cache_dir, args.episode_id)
        else:
            report = gate(labels, read_jsonl(args.predictions), read_jsonl(args.baseline),
                          json.loads(args.thresholds.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
