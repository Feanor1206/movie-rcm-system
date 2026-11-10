import argparse
import json
import math
from pathlib import Path


METRICS = ("recallAt5", "mrr", "momentRecallAt5")


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


def measure(labels, predictions):
    expected = _rows_by_id(labels)
    observed = _rows_by_id(predictions)
    if not expected or set(expected) != set(observed):
        raise ValueError("Labels and predictions must contain the same query ids")
    recall, reciprocal_rank, moment_hits, moment_count = 0.0, 0.0, 0, 0
    for query_id, label in expected.items():
        relevant = label.get("episodeIds")
        if not isinstance(relevant, list) or not relevant or not all(isinstance(item, str) and item for item in relevant):
            raise ValueError("Labels require at least one relevant episodeId")
        relevant = set(relevant)
        results = observed[query_id].get("results")
        if not isinstance(results, list) or not all(isinstance(item, dict) for item in results):
            raise ValueError("Prediction results must be a list of result objects")
        found = [(rank, item) for rank, item in enumerate(results, 1) if item.get("episodeId") in relevant]
        recall += len({item["episodeId"] for rank, item in found if rank <= 5}) / len(relevant)
        reciprocal_rank += 1 / found[0][0] if found else 0
        moments = label.get("moments", [])
        if moments:
            if not isinstance(moments, list) or not all(
                    isinstance(item, dict) and item.get("episodeId") in relevant
                    and isinstance(item.get("startMs"), (float, int)) and math.isfinite(item["startMs"])
                    and item["startMs"] >= 0 for item in moments):
                raise ValueError("Moment labels require a relevant episodeId and finite startMs")
            moment_count += 1
            moment_hits += any(
                rank <= 5 and isinstance(item.get("startMs"), (float, int))
                and math.isfinite(item["startMs"]) and item["startMs"] >= 0
                and any(moment["episodeId"] == item.get("episodeId")
                        and abs(moment["startMs"] - item["startMs"]) <= 30_000 for moment in moments)
                for rank, item in found)
    return {"recallAt5": recall / len(expected), "mrr": reciprocal_rank / len(expected),
            "momentRecallAt5": moment_hits / moment_count if moment_count else None}


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--thresholds", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = gate(read_jsonl(args.labels), read_jsonl(args.predictions), read_jsonl(args.baseline),
                      json.loads(args.thresholds.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
