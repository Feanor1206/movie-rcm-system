# Offline pilot enrichment

Run the stages from the repository root. The inventory caps the pilot at five
regular episodes with catalog durations from 10 to 40 minutes and spreads them
across seasons. It checks Drive IDs and byte counts before staging the selected
videos. `ffprobe` checks the staged durations. The inventory also records missing
assets and episodes outside the pilot duration or kind criteria.

Use a separate Python environment with `ai/enrich/requirements.txt`. Install
FFmpeg, FFprobe and rclone for the Drive path. Windows ASR needs CTranslate2
compatible CUDA and cuDNN DLLs. The ASR launcher can locate those DLLs in a local
CUDA-enabled Torch install. Download the CTranslate2 Whisper turbo model to
`ai/artifacts/models/whisper-turbo` before running ASR. ASR loads that local
directory on GPU 0 with `int8_float16`, Vietnamese VAD and catalog hotwords.

```powershell
python -m ai.enrich.inventory --rclone-root 'gdrive:VideoDieppie' --stage
python -m ai.enrich.asr
python -m ai.enrich.keyframes
python -m ai.enrich.scenes
python -m ai.enrich.caption --dry-run
python -m ai.enrich.summarize --dry-run
python -m ai.enrich.export --dialogue-only
```

Use `--media-root` with a local folder or mount in place of `--rclone-root`.
Repeat `--pilot-episode` five times to keep an explicit selection. A rate limit
stops Drive staging and preserves completed byte ranges for a later resume.
ASR and image stages keep per-episode artifacts and reuse outputs when their
inputs match. Keyframe extraction and scene grouping run on CPU. Keyframes
record video asset identity and source time. Scene grouping reads the ASR cues
and the sampled frame hashes. `asr_run.json` reports the sampled GPU memory peak
for the stage. Windows reports total device memory including other processes.

Dry-run writes each caption request plan and image count locally. It sends zero
requests. `TEACHER_BASE_URL`, `TEACHER_API_KEY` and `TEACHER_MODEL` configure an
OpenAI-compatible provider for a separately authorized run. Calling it requires
explicit `--execute --max-requests N`. Summarization needs completed captions.
The default export requires captions and summaries for all five episodes. The
dialogue-only option produces a valid catalog with ASR tracks and their source
provenance. It leaves the original scene and synopsis data intact.

Generated records are drafts. Review the cues, scene captions and synopsis,
then record the reviewer and source in provenance before marking them ready.
Validate the reviewed file with `docs/contracts/animation-catalog-v1/validate_catalog.py`.
Import through the admin import screen or run
`.\scripts\import_preview_catalog.ps1 -CatalogPath '<reviewed-catalog.json>'`
after review. Exports never trigger import. The comparison command may include
the identified pilot drafts in memory so the draft catalog remains reviewable.

See [encoder preparation](../EMBEDDING_CACHE.md) and [pilot evaluation](../evaluation/README.md).
