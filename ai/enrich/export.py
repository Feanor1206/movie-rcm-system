import argparse
import importlib.util
import json
from pathlib import Path

from .common import ARTIFACTS, CATALOG, ROOT, episodes, pilot_options, read, write


VALIDATOR = ROOT / "docs/contracts/animation-catalog-v1/validate_catalog.py"
SCENE_FIELDS = ("title", "summary", "visual_description", "character_ids", "keywords", "themes",
                "visual_tags", "sound_events")


def provenance(model, version, created_at, fields, source_ids):
    return {"source_ids": source_ids, "origin": "machine_generated", "verification": "unverified", "confidence": None,
            "annotator": None, "tool_or_model": model, "tool_revision": version, "annotated_at": created_at,
            "note": f"Generated fields: {', '.join(fields)}"}


def record(prov, previous=None):
    previous = previous or {}
    return {"status": "draft", "revision": previous.get("revision", 0) + 1,
            "created_at": previous.get("created_at") or prov["annotated_at"],
            "updated_at": prov["annotated_at"], "provenance": prov}


def upsert(rows, entry):
    for index, row in enumerate(rows):
        if row["id"] == entry["id"]:
            rows[index] = entry
            return
    rows.append(entry)


def enrich(payload, inventory, artifacts, dialogue_only):
    entries = {row["id"]: row for row in payload["episodes"]}
    assets = {row["id"]: row for row in payload["media_assets"]}
    timestamps = []
    for row in inventory:
        episode_id = row["episode_id"]
        asset_id = row["media_asset_id"]
        folder = artifacts / episode_id
        asr = read(folder / "asr.json")
        if asr["episode_id"] != episode_id or asr["media_asset_id"] != asset_id:
            raise ValueError(f"ASR artifact does not match {episode_id}")
        asset_duration = assets[asset_id]["duration_ms"]
        source_ids = assets[asset_id]["record"]["provenance"]["source_ids"]
        cues = [{**cue, "end_ms": min(cue["end_ms"], asset_duration)} for cue in asr["cues"] if cue["start_ms"] < asset_duration]
        asr_prov = provenance(asr["model"], asr["revision"], asr["created_at"],
                              ("cues.id", "cues.start_ms", "cues.end_ms", "cues.text"), source_ids)
        timestamps.append(asr["created_at"])
        track = {"id": f"{episode_id}.track.asr.vi", "media_asset_id": asset_id, "kind": "transcript",
                 "language": asr["language"], "format": "inline", "external_file": None, "cues": cues,
                 "provenance": asr_prov, "record": record(asr_prov)}
        upsert(payload["text_tracks"], track)
        if dialogue_only:
            continue
        plan = read(folder / "scenes.json")["scenes"]
        captions = read(folder / "captions.json")
        summary = read(folder / "synopsis.json")
        matches = {scene["scene_id"]: scene for scene in captions["scenes"]}
        if set(matches) != {scene["scene_id"] for scene in plan}:
            raise ValueError(f"Scene captions incomplete for {episode_id}")
        timestamps.extend((captions["created_at"], summary["created_at"]))
        for scene in plan:
            scene_id = scene["scene_id"]
            start, end = scene["start_ms"], min(scene["end_ms"], asset_duration)
            caption = matches[scene_id]
            scene_prov = provenance(captions["model"], captions["prompt_version"], caption["created_at"], SCENE_FIELDS, source_ids)
            scene_prov["note"] += ". Intervals from PySceneDetect and dialogue pauses."
            values = {field: caption[field] for field in SCENE_FIELDS}
            upsert(payload["scenes"], {"id": scene_id, "episode_id": episode_id, "segment_id": None,
                "media_asset_id": asset_id, "start_ms": start, "end_ms": end, **values,
                "transcript_cue_ids": [cue["id"] for cue in cues if cue["start_ms"] < end and cue["end_ms"] > start],
                "spoiler_level": "mild", "provenance": scene_prov, "record": record(scene_prov)})
        episode = entries[episode_id]
        summary_prov = provenance(summary["model"], summary["prompt_version"], summary["created_at"], ("synopsis", "plot_facts"), source_ids)
        episode["synopsis"] = summary["synopsis"]
        episode["plot_facts"] = [{"id": f"{episode_id}.fact.{index:03}", "text": fact, "language": asr["language"],
                                  "character_ids": [], "spoiler_level": "mild", "provenance": summary_prov}
                                 for index, fact in enumerate(summary["plot_facts"], 1)]
        episode["record"] = record(summary_prov, episode["record"])
    payload["package"] = {"id": "jadoo-pilot-dialogue" if dialogue_only else "jadoo-pilot-enriched",
                          "revision": 1, "created_at": max(timestamps), "default_language": "vi",
                          "import_mode": "upsert", "reference_scope": "self_contained",
                          "description": "Five-episode ASR pilot" if dialogue_only else "Five-episode enrichment pilot"}
    return payload


def main():
    parser = argparse.ArgumentParser()
    pilot_options(parser)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dialogue-only", action="store_true")
    args = parser.parse_args()
    if args.episode:
        parser.error("Export requires all five pilot episodes")
    output = args.output or args.artifacts / ("pilot-dialogue.json" if args.dialogue_only else "pilot-enriched.json")
    if output.resolve() == args.catalog.resolve():
        parser.error("Output must differ from the original catalog")
    try:
        result = enrich(read(args.catalog), episodes(args.inventory), args.artifacts, args.dialogue_only)
        spec = importlib.util.spec_from_file_location("catalog_validator", VALIDATOR)
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        failures = validator.validate(result)
        if failures:
            parser.error("Catalog validation failed:\n" + "\n".join(failures[:20]))
        write(output, result)
    except (FileNotFoundError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps({"output": str(output), "scenes": len(result["scenes"]), "text_tracks": len(result["text_tracks"]),
                      "review_required": True,
                      "import_after_review": ".\\scripts\\import_preview_catalog.ps1 -CatalogPath '<reviewed-catalog.json>'"}))


if __name__ == "__main__":
    main()
