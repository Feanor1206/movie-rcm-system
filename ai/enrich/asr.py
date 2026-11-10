import argparse
import os
import subprocess
import threading
import time
from pathlib import Path

from .common import ARTIFACTS, CATALOG, digest, episodes, now, pilot_options, read, run, write


MODEL = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
VERSION = "dippie-asr-v1"


class GpuMonitor:
    def __init__(self):
        self.stopped = threading.Event()
        self.samples = []
        self.thread = threading.Thread(target=self.collect, daemon=True)

    def collect(self):
        while not self.stopped.is_set():
            try:
                result = run("nvidia-smi", "--id=0", "--query-gpu=memory.used", "--format=csv,noheader,nounits")
                self.samples.append(int(result.strip()))
            except (OSError, ValueError, subprocess.CalledProcessError):
                pass
            if self.stopped.wait(0.5):
                break

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stopped.set()
        self.thread.join()

    def report(self):
        return {"peak_gpu_mib": max(self.samples, default=None), "gpu_samples": len(self.samples),
                "gpu_scope": "device 0 total used memory from nvidia-smi"}


def hotwords(catalog):
    values = []
    for character in catalog["characters"]:
        values.append(character["name"])
        values.extend(alias if isinstance(alias, str) else alias.get("text", "") for alias in character.get("aliases", []))
    return ", ".join(dict.fromkeys(value.strip() for value in values if value.strip()))


def transcribe(model, row, words, language):
    started = time.perf_counter()
    segments, _ = model.transcribe(row["source"], language=language, vad_filter=True, hotwords=words,
                                   beam_size=3, condition_on_previous_text=False)
    cues = []
    duration = row["probed_duration_ms"]
    for segment in segments:
        start = max(0, round(segment.start * 1000))
        end = min(duration, round(segment.end * 1000))
        value = segment.text.strip()
        if start < end and value:
            cues.append({"id": f"{row['episode_id']}.cue.{len(cues) + 1:05}", "start_ms": start, "end_ms": end,
                         "text": value, "speaker_character_ids": [], "confidence": None})
    elapsed = time.perf_counter() - started
    return {"episode_id": row["episode_id"], "media_asset_id": row["media_asset_id"], "language": language,
            "model": MODEL, "revision": VERSION, "created_at": now(), "cues": cues, "duration_ms": duration,
            "elapsed_seconds": elapsed, "real_time_factor": elapsed / (duration / 1000)}


def main():
    parser = argparse.ArgumentParser()
    pilot_options(parser)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--model", type=Path, default=ARTIFACTS / "models/whisper-turbo")
    parser.add_argument("--language", default="vi")
    args = parser.parse_args()
    model_path = args.model.resolve(strict=True)
    weights = (model_path / "model.bin").stat()
    words = hotwords(read(args.catalog))
    pending = []
    for row in episodes(args.inventory, args.episode):
        source = Path(row["source"]).stat()
        signature = digest([row["media_asset_id"], source.st_size, source.st_mtime_ns, weights.st_size,
                            weights.st_mtime_ns, words, args.language, VERSION])
        path = args.artifacts / row["episode_id"] / "asr.json"
        if not path.exists() or read(path).get("input_hash") != signature:
            pending.append((row, path, signature))
    if not pending:
        print("ASR cache hit for selected episodes")
        return
    from faster_whisper import WhisperModel
    dll = None
    if os.name == "nt":
        import importlib.util
        torch = importlib.util.find_spec("torch")
        if torch:
            library = Path(torch.origin).parent / "lib"
            if library.is_dir():
                os.environ["PATH"] = str(library) + os.pathsep + os.environ["PATH"]
                dll = os.add_dll_directory(str(library))
    with GpuMonitor() as monitor:
        try:
            model = WhisperModel(str(model_path), device="cuda", device_index=0, compute_type="int8_float16",
                                 local_files_only=True)
            for row, path, signature in pending:
                with GpuMonitor() as episode_monitor:
                    result = transcribe(model, row, words, args.language)
                write(path, {**result, "input_hash": signature, **episode_monitor.report()})
                print(f"{row['episode_id']} {len(result['cues'])} cues, RTF={result['real_time_factor']:.4f}", flush=True)
            del model
        finally:
            if dll:
                dll.close()
    write(args.artifacts / "asr_run.json", {"episodes": [row["episode_id"] for row, _, _ in pending],
                                          "model": MODEL, "device": "cuda:0", **monitor.report()})


if __name__ == "__main__":
    main()
