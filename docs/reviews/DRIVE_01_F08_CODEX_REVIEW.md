# F08 checkpoint review

Verdict: **substantial progress; full snapshot acceptance remains pending.** No commit/push, agent CLI, automation, service, mount or GPU startup was performed by this review.

## Checks and improvements

- All14 frozen manifest entries match size/SHA256; current patch matches the on-disk manifest. The pasted report cites an earlier patch hash/size (115082 bytes), whereas the current consistent manifest/patch is115440 bytes, SHA981A858C41077D76C86C2CC55DF63F81F75DD000BD0D3CB08FA18F8CCFAB7A31. Use the checked on-disk artifacts for identification.
- Reverse patch check passes. Clean application from declared c2d29c0 base reconstructs14/14 patch paths with normalized text matching; no reconstructed Maven suite was rerun by reviewer.
- executeWithTimeout now acquires a lifecycle reservation before executing the callable, closing the earlier supported generic-resource off-budget admission gap. Metadata/read are separated, and position(newPosition) now returns null inside the scalar callable. The saturation regression now joins read futures and waits main-worker accounting before recovery.
- Startup compiles before each launch and polls readiness; source freshness is improved. Browser script has isolated profile/port, slider-only seek and RVFC capture. The supplied browser JSON contains actual1920x1080 frame metadata near60/200/400seconds and time advancement; this is useful recorded decoder evidence, not a new live execution by reviewer.
- Node script syntax and both PowerShell parsers pass. Full161 backend tests and Ubuntu/JDK17 CI are reported/not freshly verified here; raw F08 full-suite logs and the Linux CI run evidence are not included in the14-entry manifest. Frontend unchanged from the previously verified Node20 build.

## Remaining findings

### R1 — P2: scalar contract rejection still swallows a failed native close

DriveIoExecutor.executeScalar, around225–229, invokes close on forbidden AutoCloseable and catches Throwable without retaining ownership or surfacing the close failure. The public generic callable still accepts this type at compile time. The new regression tests successful forbidden-resource close only, not its failure.

Directly compiled production-source repro `docs/reviews/repro/DRIVE_F08_scalar_cleanup.java` runs a forbidden scalar return whose first close throws before closing a real temporary FileChannel. Output:

```json
{"error":"IllegalArgumentException","nativeOpen":true,"closeAttempts":1,"retained":0,"lostCleanup":true}
```

Exit1 confirms failed cleanup disappears. Fixture finally closes its native file/releases permit; no OS handle left open. This is a **scalar contract-violation boundary case**, not an observed failure through the audited normal adapter's scalar call sites, and should not be confused with the previously fixed resource lane. Either enforce a genuinely non-resource API boundary or define bounded ownership/recovery for rejection; do not claim never-leak by swallowing close exceptions.

### R2 — P2: stop script is not fail-closed for incomplete process identity

stop_backend_dev.ps1 only compares executable when both expected and live values are truthy, and only checks creation time when CIM supplies it. Missing required data therefore skips checks. It verifies command-line substrings rather than the recorded complete identity, and does not actually reacquire/validate a retained process handle before Stop-Process despite the handoff claim.

Safe fixture `docs/reviews/repro/DRIVE_F08_stop_missing_identity.ps1` shadows both Get-CimInstance and Stop-Process; it uses no real process inspection/signals. A state lacking ExecutablePath plus a fake live process lacking it is accepted and reaches the mocked stop:

```json
{"realProcessSignals":0,"missingExecutableIdentityAccepted":true}
```

Exit1 asserts fail-closed requirement. Require complete nonempty state/live identity, exact creation identity and parsed expected application/profile arguments; hold the verified process instance for signaling and guard state removal against new-start races. Do not test against user processes.

### R3 — P2: verifier records decoded-frame success even when that assertion fails

test_live_browser_f08.cjs around244–277 accepts hasRvfc=false fallback; unexpected/missing frame data or a width other than1280 merely console.warn instead of failing. Actual supplied JSON is1920x1080, so this warning branch is taken even for the intended video. The final frameCallbackDecoded=true is unconditional. Its CDP helper also resolves protocol responses without rejecting data.error or Runtime.evaluate exceptionDetails.

Validate positive dimensions, actual presented frame/mediaTime near each requested target and continued playback, rejecting failed protocol/evaluation/frame evidence. If an explicit alternate decoder-evidence path is supported, validate it and label it separately rather than setting RVFC success. The supplied positive evidence remains valuable; the test gate is not strict enough to certify failures reliably.

### R4 — P2: final usage and CI evidence still incomplete

qwen_inference_f08.json records a real-looking recommendation response and the report explicitly identifies FastAPI POST /api/chat, but it does not record the requested browser CineBot send/render interaction. Supply the ordinary browser UI path/model identity/readiness/request linkage without loading a duplicate model. Existing review runbook still reflects F06/F07 warnings and does not document the new launcher60-second Drive timeouts; provide an up-to-date current usage note while preserving historical artifacts. Publish raw full backend log and the exact Linux/JDK17 CI result for the changed fixture; a local Java25 claim does not establish that environment.

## Review scope / next handoff

Two bounded reviewer repros were executed: one Java temp-file boundary case and one purely mocked PowerShell stop fixture. No application source was changed by reviewer; historical repros/status/manifests stay untouched. Hashes were checked before/after. F08 is not automatically committed or pushed: the current message supplied a report for review, and prior commit/push requests were performed for F06/F07. Continue manual copy/paste only.
