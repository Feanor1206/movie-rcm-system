import argparse
import copy
import importlib.util
from pathlib import Path

from .common import ARTIFACTS, CATALOG, digest, episodes, now, pilot_options, read, write
from .export import VALIDATOR, enrich


TABLES = ("episodes", "scenes", "text_tracks")


def validate(payload):
    spec = importlib.util.spec_from_file_location("pilot_catalog_validator", VALIDATOR)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    errors = validator.validate(payload)
    if errors:
        raise ValueError("\n".join(errors[:20]))


def scope_catalog(payload, selected):
    selected = set(selected)
    result = copy.deepcopy(payload)
    result["episodes"] = [row for row in result["episodes"] if row["id"] in selected]
    if {row["id"] for row in result["episodes"]} != selected:
        raise ValueError("An episode is missing from the input catalog")
    result["segments"] = [row for row in result["segments"] if row["episode_id"] in selected]
    result["scenes"] = [row for row in result["scenes"] if row["episode_id"] in selected]
    assets = {row["id"]: row for row in result["media_assets"]}
    included = {asset["id"] for asset in assets.values()
                if any(c["episode_id"] in selected for c in asset["coverage"])}
    result["text_tracks"] = [track for track in result["text_tracks"] if track["media_asset_id"] in included]
    pending = list(included)
    while pending:
        related = assets[pending.pop()].get("related_asset_id")
        if related and related not in included:
            if related not in assets:
                raise ValueError(f"Related media asset is missing: {related}")
            included.add(related)
            pending.append(related)
    result["media_assets"] = [asset for asset in assets.values() if asset["id"] in included]
    for asset in result["media_assets"]:
        asset["coverage"] = [c for c in asset["coverage"] if c["episode_id"] in selected]
    return result


def review_records(base, draft):
    records = {}
    for table in TABLES:
        previous = {row["id"]: row for row in base[table]}
        for row in draft[table]:
            if row == previous.get(row["id"]):
                continue
            record = row["record"]
            if record["status"] != "draft" or record["provenance"]["origin"] != "machine_generated":
                raise ValueError(f"Expected a generated draft for {row['id']}")
            records[row["id"]] = row
    if not records:
        raise ValueError("No generated records to review")
    return records


def review_template(base, draft):
    return {"reviewer": "", "records": [{"id": key, "sha256": digest(row), "approved": False}
                                       for key, row in review_records(base, draft).items()]}


def approve(base, draft, review, approved_at):
    result = copy.deepcopy(draft)
    records = review_records(base, result)
    reviewer = review.get("reviewer")
    entries = review.get("records")
    if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(entries, list):
        raise ValueError("A named reviewer and review records are required")
    if len(entries) != len(records) or {row["id"] for row in entries} != set(records):
        raise ValueError("Review must cover exactly the generated records")
    for entry in entries:
        row = records[entry["id"]]
        if entry.get("approved") is not True or entry.get("sha256") != digest(row):
            raise ValueError(f"Missing approval or changed content for {row['id']}")
        record = row["record"]
        record["status"] = "ready"
        record["updated_at"] = approved_at
        provenance = record["provenance"]
        provenance["verification"] = "human_verified"
        provenance["note"] = f"{provenance.get('note') or ''} Reviewed by {reviewer.strip()} on {approved_at}.".strip()
        if "provenance" in row:
            row["provenance"] = copy.deepcopy(provenance)
    result["package"]["created_at"] = approved_at
    result["package"]["description"] = "Reviewed pilot catalog for isolated preview import"
    validate(result)
    return result


def main():
    parser = argparse.ArgumentParser(description="Prepare or publish a reviewed pilot package for preview import")
    pilot_options(parser)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--dialogue-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--review-template", type=Path)
    mode.add_argument("--review", type=Path)
    args = parser.parse_args()
    try:
        destinations = [args.output, args.review_template or args.review]
        if len({path.resolve() for path in [args.catalog, args.inventory, *destinations]}) != 4:
            raise ValueError("Catalog, inventory, output and review paths must be distinct")
        rows = episodes(args.inventory, args.episode)
        base = scope_catalog(read(args.catalog), [row["episode_id"] for row in rows])
        draft = enrich(copy.deepcopy(base), rows, args.artifacts, args.dialogue_only)
        validate(draft)
        if args.review_template:
            if args.review_template.exists():
                raise ValueError("Review template already exists")
            write(args.output, draft)
            write(args.review_template, review_template(base, draft))
        else:
            write(args.output, approve(base, draft, read(args.review), now()))
        print(args.output)
    except (FileNotFoundError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
