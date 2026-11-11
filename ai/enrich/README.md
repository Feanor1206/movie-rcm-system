# Offline pilot enrichment

Run the stages from the repository root. The inventory caps the pilot at five
regular episodes with catalog durations of at least 10 minutes. The automatic
selection prefers 10–40 minute episodes and spreads them across seasons. Explicit
selection also accepts longer regular episodes. It checks Drive IDs and byte counts before staging the selected
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
Repeat `--pilot-episode` five times to keep an explicit selection. Media is staged
under `ai/artifacts/media-mirror/<episode-id>/media.mp4`. Existing per-episode
media is checked by size and measured duration. Staging uses a hard link when the
source is on the same volume and copies once otherwise. Keep the original
file in place to reuse legacy keyframes after hard linking. Newly downloaded files are resumed in
chunks and checked against the Drive MD5. Use `--rclone-config <path>` or the
standard `RCLONE_CONFIG` environment variable to select a local rclone config.
Configure a user-owned Drive client ID and secret in that config.
A quota or rate limit stops staging, preserves completed byte ranges for a later
resume and reports the original rclone error. Transient connection errors
receive at most two short retries.

Resume the current five-episode selection with the same IDs. Set `--rclone-config`
if the remote with the user-owned Drive client is in a different config file.

```powershell
python -m ai.enrich.inventory --rclone-root 'gdrive:VideoDieppie' --stage --pilot-episode ep_jadoo_s01_0022 --pilot-episode ep_jadoo_s04_0021 --pilot-episode ep_jadoo_s04_0011 --pilot-episode ep_jadoo_s03_0008 --pilot-episode ep_jadoo_s01_0007
```

ASR and image stages keep per-episode artifacts and reuse outputs when their
inputs match. Keyframe extraction and scene grouping run on CPU. Keyframes
record video asset identity and source time. Scene grouping reads the ASR cues
and the sampled frame hashes. `asr_run.json` reports the sampled GPU memory peak
for the stage. New `asr.json` files also report the peak during each episode;
existing files are not altered. Windows reports total device memory including
other processes.

Dry-run writes each caption request plan and image count locally. It sends zero
requests. `TEACHER_BASE_URL`, `TEACHER_API_KEY` and `TEACHER_MODEL` configure an
OpenAI-compatible provider for a separately authorized run. Calling it requires
explicit `--execute --max-requests N --run-id NAME`. The two stages share a
persistent request cap when they use the same run ID and artifact directory.
Summarization needs completed captions.

The DeepSeek pilot covers S01E22 and S04E21 with a shared cap of 40 requests,
including the image probe. Start with `scripts/configure_llm.ps1` to enter the
credentials locally. The default offline command plans without API calls.
`--execute` sends one small pilot keyframe to the configured endpoint. An
explicit image rejection selects local llama-server captions and DeepSeek text
summaries. Set `LOCAL_VISION_BASE_URL` to the loopback server's `/v1` URL and
`LOCAL_VISION_MODEL` to its model ID before continuing that branch. An
inconclusive probe stops the run and keeps its status for investigation.

```powershell
python -m ai.enrich.deepseek_offline
python -m ai.enrich.deepseek_offline --execute
python -m ai.enrich.teacher_audit --episode ep_jadoo_s01_0022 --episode ep_jadoo_s04_0021 --run-id pilot-two-episodes --output ai/artifacts/pilot-teacher-audit.json
```

The default export requires captions and summaries for all five episodes. The
dialogue-only option produces a valid catalog with ASR tracks and their source
provenance. It leaves the original scene and synopsis data intact.

Use `publish_preview` to generate a scoped draft and a review receipt. Use
`--dialogue-only` to review ASR before captions are available. Repeating
`--episode` limits the package to specific pilot episodes.

```powershell
python -m ai.enrich.publish_preview --dialogue-only --episode ep_jadoo_s01_0022 --episode ep_jadoo_s04_0021 --output ai/artifacts/dialogue-review-draft.json --review-template ai/artifacts/dialogue-review.json
```

Review every listed record against its source. Enter the reviewer name and set
`approved` to `true` only for records that passed. Keep the record hashes as
generated. The publish command verifies exact review coverage, checks provenance
and validates the resulting package. The package retains the model provenance
and records the human review. Omit `--dialogue-only` in both commands to include
captions, scenes and summaries when available. Save the reviewed package as
`ai/artifacts/pilot-published.json` to let cloud chat use its published pilot
evidence independently of the Spring database.

```powershell
python -m ai.enrich.publish_preview --dialogue-only --episode ep_jadoo_s01_0022 --episode ep_jadoo_s04_0021 --output ai/artifacts/dialogue-ready.json --review ai/artifacts/dialogue-review.json
.\scripts\import_preview_catalog.ps1 -CatalogPath ai/artifacts/dialogue-ready.json -ApiBaseUrl http://127.0.0.1:18081/api -PreviewStateFile ai/artifacts/preview-stack.json
```

Start the dedicated preview with `-SpringPort 18081` and `-StateFile
ai/artifacts/preview-stack.json`. Give it a separate `-DataDirectory` under
`ai/artifacts/`. The import script checks the recorded Spring process and local
listener before authentication and again before importing. If Spring reports
`CACHE_REQUIRED`, run its cache command with the preview encoder selected and
retry the snapshot from the admin screen. The comparison command may use a
separate in-memory projection of pilot drafts for offline diagnosis.

See [encoder preparation](../EMBEDDING_CACHE.md) and [pilot evaluation](../evaluation/README.md).
