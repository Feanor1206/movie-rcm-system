# DRIVE-01 — Google Drive implementation / parallel agents

New user assignment on 2026-10-15: implement Google Drive mounted storage on Windows with multiple real Gemini agents working in parallel. Work at D:\Class\movie-rcm-system on dev. Read and execute docs/prompts/DRIVE_01_GEMINI_PROMPT.md in full; coordination is docs/prompts/DRIVE_REVIEW_CONTROL.json (taskId DRIVE-01, promptVersion1).

Use three subagents with separate ownership: A storage boundary, B Windows operations toolkit, C HTTP/browser verification; parent owns shared integration/config/contracts and final artifacts. Finish implementation and isolated verification even if actual OAuth/mount prerequisites are missing; label real Drive gates blocked honestly. Prepare reviewable setup commands; no installer/OAuth/mount execution in the coding checkpoint.

M4 local remains ACCEPTED at7c825b6; M4_REVIEW_CONTROL stays stop and is historical for this task. Preserve its frozen artifacts. Automation remains PAUSED, manual handoff only. Freeze then publish DRIVE_01 artifacts/status ready_for_review and end the turn; no polling or automatic next milestone. Do not edit Codex prompts/control/reviews, live DB, AI/FastAPI/Qwen/GPU, OS settings or deploy. No commit/push/reset/new branch. Existing backend/fastapi/.env.example is outside scope.
