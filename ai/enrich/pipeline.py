import argparse
import importlib.util
import json
from pathlib import Path

from .common import ARTIFACTS, CATALOG, episodes, pilot_options, read, write
from .export import VALIDATOR, enrich
from .keyframes import extract_episode
from .scenes import detect_episode


def run_pipeline(
    *,
    inventory_path: Path = ARTIFACTS / "inventory.json",
    artifacts_dir: Path = ARTIFACTS,
    catalog_path: Path = CATALOG,
    selected_episodes: list[str] | None = None,
    dialogue_only: bool = True,
    output_path: Path | None = None,
    skip_video_stages: bool = False,
) -> dict:
    rows = episodes(inventory_path, selected_episodes)
    catalog = read(catalog_path)
    stage_summary = []
    if not skip_video_stages:
        for row in rows:
            episode_dir = artifacts_dir / row["episode_id"]
            kf_res, kf_cached = extract_episode(row, episode_dir)
            sc_res, sc_cached = detect_episode(row, episode_dir)
            stage_summary.append({
                "episode_id": row["episode_id"],
                "frames": len(kf_res.get("frames", [])),
                "keyframes_cached": kf_cached,
                "scenes": len(sc_res.get("scenes", [])),
                "scenes_cached": sc_cached,
            })
    result = enrich(catalog, rows, artifacts_dir, dialogue_only)
    spec = importlib.util.spec_from_file_location("catalog_validator", VALIDATOR)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    failures = validator.validate(result)
    if failures:
        raise ValueError("Catalog validation failed:\n" + "\n".join(failures[:20]))
    destination = output_path or artifacts_dir / ("pilot-dialogue.json" if dialogue_only else "pilot-enriched.json")
    if destination.resolve() == Path(catalog_path).resolve():
        raise ValueError("Output must differ from the original catalog")
    write(destination, result)
    return {
        "episodes": [row["episode_id"] for row in rows],
        "dialogue_only": dialogue_only,
        "output": str(destination),
        "text_tracks": len(result.get("text_tracks", [])),
        "scenes": len(result.get("scenes", [])),
        "stages": stage_summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Unified offline enrichment pipeline runner.")
    pilot_options(parser)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dialogue-only", action="store_true")
    parser.add_argument("--skip-video-stages", action="store_true")
    args = parser.parse_args()
    try:
        report = run_pipeline(
            inventory_path=args.inventory,
            artifacts_dir=args.artifacts,
            catalog_path=args.catalog,
            selected_episodes=args.episode,
            dialogue_only=args.dialogue_only,
            output_path=args.output,
            skip_video_stages=args.skip_video_stages,
        )
    except (FileNotFoundError, ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
