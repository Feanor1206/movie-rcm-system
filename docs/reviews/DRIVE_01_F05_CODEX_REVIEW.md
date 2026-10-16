# DRIVE-01-F05-CHECKPOINT-FINAL — Codex review

Verdict: NOT ACCEPTED. Static source/artifact review only; no new Maven, GPU, browser, CLI agent, automation or mount was started. Branch dev. All26 manifest file sizes/SHA256 matched before review; reverse patch check succeeded. Existing full-backend log reports154 tests, zero failures/errors/skips. These positives do not close the findings below.

## R1 — P1: failed unreserved resources remain outside the lifecycle budget

DriveIoExecutor.java recordUnreservedFailedCleanup (around553–565), closeLateResourceOnWorker and closeResourceSafely stop charging when lifecycle total reaches capacity but still call recordFailedCleanup with chargesPending=false. The retained resource map therefore acquires real close obligations that active+pending does not count. submitRetryTask charges these only later. Counter nonnegativity and a clamped decrement do not establish bounded ownership.

Repro to implement: hold all capacity with legitimate reservations; repeatedly execute the public unreserved open/AutoCloseable helper with timeout/late return and an injected physical-close exception. Keep resource objects distinct. Observe retainedFailedResources/failed count grow while lifecycle total stays at cap; after cooldown permit subsequent calls rather than treating circuit breaker as a hard resource bound. Also test shutdown with an uncharged retained record: retry refuses shutdown and cleanup shutdown is decided using charged total only. Distinguish helper paths from production adapter's reserved path. This is source-established admission gap; the repeated runtime sequence was not executed by Codex in this review.

Require pre-admitted bounded ownership across every retained path, or a safe explicit helper contract preventing such resources from being opened. No unlimited off-budget quarantine, arbitrary cap increase or silent drop. Add regression measuring actual retained resources as well as advertised counters.

## R2 — P1: patch does not reproduce tested source

DRIVE_01_F05.patch contains only nine diff headers and omits LunaDriveCleanupOpenLifecycleTest.java, LunaDriveCleanupShutdownOwnershipTest.java and test/resources/mockito-extensions/org.mockito.plugins.MockMaker, even though all three are in manifest and are essential to the reported tests/environment fix. Reverse apply passing only proves included hunks match. Export complete new/untracked text files; record exact base commit; demonstrate clean reconstruction matches source manifest, then run checks on that reconstruction. Include relevant preexisting Qwen files/config in a reproducibility inventory with hashes if no diff is needed, never weights/secrets.

## R3 — P1: usable snapshot and Qwen app integration are not established

Real Drive evidence is valuable actual decoder/HTTP evidence, but reviewer harness starts transient H2, seeds synthetic movie mapping, rewrites baked API URLs through Chrome CDP and tears owned processes down. The provided ordinary startup commands do not recreate that movie mapping/database or CDP rewrite. RealDrivePlaybackServer and real_drive_playback.cjs document this distinction; do not call those mocks, but do not equate that harness pass to a persistent user snapshot.

backend/fastapi/tests/test_serving_integration.py constructs QwenRecommendationService directly, calls get_health_status/get_readiness_status and parse_discovery_intent. Its integer200 is a service return value, not observed HTTP readiness. This test does not prove frontend -> Spring -> FastAPI -> fine-tuned model -> UI, or that normal gateway startup selects full model/adapter. No Qwen raw test log is included in the26-file manifest.

Provide a dedicated reproducible snapshot launcher/config with isolated persistent demo database and Drive video mapping, correct frontend/backend/AI endpoints, loopback bindings, available ports/process ownership and truthful final service state. Verify normal browser navigation without CDP API rewriting and one Qwen app request returning through UI. Preserve live DB and user services; no second model load if existing suitable service is available. Record timeout/error behavior and actual model identity. Do not rerun training or download/install models.

## R4 — P2: final cross-review sign-off references an obsolete audit

CROSS_REVIEW.md claims Agent E final PASS citing docs/reviews/DRIVE_F05_GEMINI_INDEPENDENT_AUDIT.md. That cited audit explicitly reviews in-progress F05_04 hash dd44e84d... and lists open findings; final IoExecutor is57065d5e.... It cannot serve as final-source sign-off. Perform new read-only audit against final hashes and publish actual reviewer identity/evidence; preserve the old audit unchanged.

Additional reporting corrections: measured Drive cold start about12.2seconds and two seeks about13.48/10.99seconds should remain explicit limitations. Cache-off flags alone do not prove a measured0-byte disk delta. Health-object tests are not HTTP tests. Do not claim complete WCAG conformance from three44px control measurements alone.

Next work is manual Gemini follow-up; no automatic agent dispatch authorized. Historical status/manifest/report stay unchanged. G1 remains unaccepted; existing Drive/browser evidence is acknowledged, not rerun. Final user snapshot remains incomplete.
