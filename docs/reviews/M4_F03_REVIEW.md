# M4-F03 — Independent acceptance review

2026-10-15. **ACCEPTED: M4 local media playback.** T1 is closed; no remaining blocking finding in the reviewed M4 scope. Google Drive remains **BLOCKED_EXTERNAL_INPUT / NOT_IMPLEMENTED**, a separate gate. This acceptance does not authorize deployment or open another milestone.

Checkpoint M4-F03-CHECKPOINT-01, task M4-F03, promptVersion3, explicit ready_for_review/sourceFrozen=true. All16 manifest entries matched SHA256 and byte length before and after verification; reverse patch check passed. Gemini artifacts were preserved. Codex changed only reviewer material and coordination documents, not application code. Automation remains paused/manual.

## T1 resolution

Production mediaService distinguishes internal TimeoutError from caller AbortError and rejects missing required fields, non-boolean flags, invalid advertised assets and literal movieId mismatch. MovieDetail terminates current failed requests with an alert/retry; canceled obsolete requests cannot overwrite the current movie. Legacy trailer preview remains independent.

The unchanged F02 reviewer repro passes timeout, missing-fields and wrong-ID scenarios. F01 legacy/non-legacy HTTP503 repro also passed. These execute production service/component code through the hook harness, not a browser. An additional native HTTP probe sends headers and partial JSON then stalls: actual production service raises TimeoutError at its deadline (115ms for100ms limit), versus caller AbortError (48ms for40ms abort). This verifies pending-body behavior beyond a synthetic fetch rejection.

## Independent checks

| Check | Result and scope |
| --- | --- |
| Bare Maven and exact CI test-profile command | 43/43 each, exit0, isolated H2; local JDK25.0.3 targeting Java17 |
| Seven frontend suites | 83/83 on Node26 and separately Node20.20.2 |
| TypeScript and production Next build | Exit0 |
| Dynamic route JS guard | All routes pass; detail143264/143360bytes, only96bytes headroom |
| Handed browser walkthrough | Exit0: descriptor503/retry, decoded playback/time progression, three UI seeks, pause/resume, player retry, close/focus, mobile44px/no collisions |
| Additional browser faults | Timeout, malformed200 and wrong movieId show error/retry, suppress feature button, recover on UI retry |
| Actual Spring HTTP benchmarks | Range/admission/cleanup checks pass; counter returns to0 after disconnect; overload429 |
| Monitored media root | Three files unchanged in count, size and hash |

Additional CDP fault probe observed terminal errors after6202ms (production6000ms timeout),542ms (malformed),543ms (mismatch). These are real browser observations under controlled network interception, not real Drive/backend malformed-response measurements. The primary walkthrough separately exercises actual Spring streaming and Chrome video decoding using a synthetic20s MP4. Reviewer inspected desktop failure and mobile playback screenshots.

The first additional browser run failed to connect to Chrome before application checks. A bounded retry increased only the reviewer wrapper's Chrome startup allowance from4s to15s and completed exit0. The original handed walkthrough already passed without that change. Both logs are retained; this is not reported as a product failure.

## Evidence and limits

docs/reviews/evidence/M4_F03 contains independent Maven, Node20/26, build/budget, browser logs, native-body and terminal-state repro outputs, descriptor-fault results, benchmark JSON and final manifest verification. Reviewer helpers under docs/reviews/repro/M4_F03_*.cjs redirect output to temp so frozen Gemini evidence is untouched. Primary browser output: C:\Users\Admin\AppData\Local\Temp\codex-m4-f03-browser-UORk0G; additional faults: C:\Users\Admin\AppData\Local\Temp\codex-m4-f03-faults-d9g0C0.

Acceptance incorporates previously closed F01/F02 public/private policy, Node20 compatibility, player identity/focus, read-only root and truthful cache/runbook findings. Local Maven pass is not remote GitHub CI/JDK17 evidence. Loopback fixtures do not prove WAN throughput, long-film reliability, real Drive playback, OS-wide zero writes or OS-wide leak freedom. Gemini subagent ownership/IDs are self-reported; Codex did not inspect those conversations.

## Handoff

Control=stop; no F04 prompt is needed. Keep automation paused. No Gemini restart, Drive install/mount, live DB, AI or deployment. Commit/push reviewed checkpoint directly to dev under existing user authorization; exclude unrelated backend/fastapi/.env.example.
