import argparse
from bisect import bisect_left, bisect_right
import json
from pathlib import Path
import time

from .common import digest, episodes, now, pilot_options, read, write


VERSION = "dippie-scenes-v1"
MIN_MS = 30_000
TARGET_MS = 60_000
MAX_MS = 90_000


def group_shots(duration_ms, shot_cuts, cues, samples):
    if duration_ms <= 0:
        raise ValueError("Scene grouping requires a positive video duration")
    merged = []
    for start, end in sorted((cue["start_ms"], cue["end_ms"]) for cue in cues):
        if not 0 <= start < end <= duration_ms:
            raise ValueError("ASR cue lies outside the episode timeline")
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    voice_starts = [start for start, _ in merged]
    voice_ends = [end for _, end in merged]
    pauses = [(left + right) // 2 for left, right in zip([0, *voice_ends], [*voice_starts, duration_ms])
              if right - left >= 600]
    sample_times = [stamp for stamp, _ in samples]
    cuts = sorted({cut for cut in shot_cuts if 0 < cut < duration_ms})

    def boundary_score(stamp, target):
        left_voice = bisect_right(voice_starts, stamp) - 1
        if left_voice >= 0 and stamp < voice_ends[left_voice]:
            silence = -2
        else:
            before = voice_ends[left_voice] if left_voice >= 0 else 0
            after = voice_starts[left_voice + 1] if left_voice + 1 < len(voice_starts) else duration_ms
            silence = min(1, min(stamp - before, after - stamp) / 1200)
        right_frame = bisect_left(sample_times, stamp)
        visual = 0
        if 0 < right_frame < len(samples):
            visual = (samples[right_frame - 1][1] ^ samples[right_frame][1]).bit_count() / 63
        return silence + visual - abs(stamp - target) / MIN_MS

    scenes = []
    start = 0
    while duration_ms - start > MAX_MS:
        lower = start + MIN_MS
        upper = min(start + MAX_MS, duration_ms - MIN_MS)
        target = min(start + TARGET_MS, upper)
        choices = cuts[bisect_left(cuts, lower):bisect_right(cuts, upper)]
        if not choices:
            choices = pauses[bisect_left(pauses, lower):bisect_right(pauses, upper)] or [target]
        end = max(choices, key=lambda cut: (boundary_score(cut, target), -abs(cut - target), -cut))
        scenes.append((start, end))
        start = end
    return scenes + [(start, duration_ms)]


def detect_shots(source, duration_ms):
    import cv2
    from scenedetect import ContentDetector, SceneManager
    from scenedetect.backends.opencv import VideoCaptureAdapter

    cv2.setNumThreads(2)
    capture = cv2.VideoCapture(str(source), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 2])
    try:
        if not capture.isOpened():
            raise ValueError("Could not open staged video with OpenCV")
        video = VideoCaptureAdapter(capture)
        manager = SceneManager()
        manager.add_detector(ContentDetector(min_scene_len="0.5s"))
        manager.detect_scenes(video=video)
        shots = manager.get_scene_list(start_in_scene=True)
        if not shots or abs(round(shots[-1][1].get_seconds() * 1000) - duration_ms) > 2_000:
            raise ValueError("Shot detector did not decode the full episode")
        return [round(start.get_seconds() * 1000) for start, _ in shots[1:]]
    finally:
        capture.release()


def detect_episode(row, directory):
    source = Path(row["source"]).resolve(strict=True)
    stat = source.stat()
    duration = row["probed_duration_ms"]
    asr, keyframes = read(directory / "asr.json"), read(directory / "keyframes.json")
    for stage in (asr, keyframes):
        if (stage["episode_id"], stage["media_asset_id"], stage["duration_ms"]) != (
                row["episode_id"], row["media_asset_id"], duration):
            raise ValueError("ASR or keyframes belong to a different video")
    samples = sorted((sample["source_ms"], int(sample["phash"], 16)) for sample in keyframes["samples"])
    signature = digest([VERSION, row["media_asset_id"], duration, str(source), stat.st_size, stat.st_mtime_ns,
                        asr["cues"], samples])
    manifest = directory / "scenes.json"
    if manifest.is_file():
        cached = read(manifest)
        if cached.get("input_hash") == signature and cached.get("scenes"):
            return cached, True
    started = time.perf_counter()
    cuts = detect_shots(source, duration)
    groups = group_shots(duration, cuts, asr["cues"], samples)
    scenes = [{"scene_id": f"{row['episode_id']}.scene.{index:04d}", "start_ms": start, "end_ms": end}
              for index, (start, end) in enumerate(groups, 1)]
    result = {"episode_id": row["episode_id"], "media_asset_id": row["media_asset_id"], "duration_ms": duration,
              "version": VERSION, "created_at": now(), "device": "cpu", "input_hash": signature,
              "shot_count": len(cuts) + 1, "scenes": scenes, "elapsed_seconds": time.perf_counter() - started}
    write(manifest, result)
    return result, False


def main():
    parser = argparse.ArgumentParser(description="Detect shots and group them into scenes using keyframes and ASR pauses.")
    pilot_options(parser)
    args = parser.parse_args()
    try:
        for row in episodes(args.inventory, args.episode):
            result, cached = detect_episode(row, args.artifacts / row["episode_id"])
            print(json.dumps({"episode_id": row["episode_id"], "shot_count": result["shot_count"],
                              "scene_count": len(result["scenes"]), "cached": cached}), flush=True)
    except (KeyError, OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
