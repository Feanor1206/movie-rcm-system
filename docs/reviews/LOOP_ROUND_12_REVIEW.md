# Round 12 — Independent M3 review

2026-10-14. **REQUEST CHANGES — bootstrap implementation and corrected performance measurement accepted as a checkpoint; M3 not yet accepted.** Only two remaining verification fixes below; do not redo accepted UI or add features.

Round12 / prompt12 / run-round12-20261014-1245 matches status and control. All 25 manifest entries matched before and after checks. Reverse patch check passed. Reviewer did not modify application source or Gemini artifacts. Manual handoff remains in effect; automation remains off.

## Verified improvements

- Canonical Compose bootstrap now creates favorite_items with user FK, unique user/movie constraint and indexes. Additive migration preserves legacy account/library rows in executable isolated H2 tests. No claim of running PostgreSQL: a movie FK claimed in the handoff text is not present in the actual SQL; do not add destructive cascading behavior just to match prose.
- PerformanceObserver installed before navigation collects actual LCP and CLS session windows; no FCP substitution. Negative check succeeds by detecting missing selector/postcondition and an intentional layout shift of 0.222. Cold and warm results are separated, with cache policy, raw entries and CDP network accounting.
- npm test: **57/57 pass**; TypeScript and production build exit0. These comprise 54 component/provider behavior checks and 3 modal source-structure checks; the latter alone are not browser evidence.
- Reviewer wrapper ran the handed browser harness unmodified apart from redirecting output to a separate temporary folder. **14 UI journey steps pass**, plus 3 cold and 3 warm samples on each of 4 routes. Visual spot checks of mobile Home and desktop saved/rated Detail retain the green theme and usable layout.
- Bare backend command **mvnw.cmd test: 25/25 pass**, exit0. This does not establish CI compatibility; see D1.
- Independent manifest-based JS audit of the current build: Home 139231, Search 138015, Detail 140419, Profile 139137 gzip bytes. All are <=143360 bytes (140 KiB). This sums individually compressed, unique layout+route JavaScript files, excluding CSS/polyfills/RSC/API; it is not full-page wire transfer.

## D1 — P1: exact CI command fails; prod controls are not isolated

`.github/workflows/ci.yml:52` invokes `./mvnw test -Dspring.profiles.active=test`. Running its Windows equivalent, **mvnw.cmd test -Dspring.profiles.active=test**, exits1: 25 tests, 1 failure and 3 errors in SeedAndConfigPolicyTest. Positive bootstrap/migration contexts fail and the missing-JWT negative control gets the wrong failure. Log: evidence/ROUND_12/backend_ci_command.log.

The new SpringApplicationBuilder `.profiles("prod")` plus low-priority `.properties("spring.profiles.active=prod", ...)` does not isolate its configuration. Under the CI command, nested contexts log **prod,test**, and test properties contaminate production controls. With the bare command, nested contexts log **prod,dev** instead. A green bare run therefore does not prove a prod-only context. This is a reproducible CI regression, not a hypothetical production outage.

Fix configuration/profile precedence in the nested tests, preserving real production YAML, isolated fixture DBs, real bootstrap/migration validation, and specific missing-secret checks. Assert exact active profile prod and production seed/SQL-init/ddl policies in positive controls. Do not weaken preflight, skip tests, inject real credentials or point to a running DB. Both bare and exact current CI commands must pass; if the workflow is intentionally changed, explain why and test that exact new command as well.

## D2 — P2: JS budget evidence is a hardcoded table

`scripts/run_browser_walkthrough.cjs:1661–1666` hardcodes rawBytes/gzipBytes and `underBudget: true` for every route. Those constants are copied into each new perf_measurements.json without reading the current build or enforcing the limit. They differ from the reviewer rebuild and will keep reporting pass if a future build exceeds the budget. Current routes actually pass the independent measurement; this finding concerns the validity of the guard and evidence.

Compute sizes from the current build manifest/files, deduplicate shared chunks per route, state included/excluded assets and compression method, record BUILD_ID and file hashes, derive underBudget and fail nonzero if exceeded or an expected manifest/file is missing. Add a negative self-test using an isolated fixture/tiny budget; no source or real build mutation. Reviewer reference: repro/ROUND_12_build_bytes.cjs. Keep budget units consistent: 140 KiB = 143360 bytes.

## Reviewer performance baseline and limits

These are local fixture results, not public-network performance or a demonstrated application speedup:

| Route | LCP cold / warm median (ms) | CLS cold / warm median | CDP bytes cold / warm median |
| --- | --- | --- | --- |
| Home | 192 / 148 | 0.014 / 0.014 | 330450 / 16931 |
| Search | 184 / 112 | 0.072 / 0.069 | 320375 / 7799 |
| Detail | 184 / 120 | 0 / 0 | 332689 / 17023 |
| Profile | 164 / 108 | 0.008 / 0.007 | 319975 / 6548 |

Evidence is under docs/reviews/evidence/ROUND_12: exact-CI and bare backend logs, independent build bytes, browser assertions and raw performance samples. The performance JSON's hardcoded exactFirstLoadJsBytes fields are rejected by D2; use independent_build_bytes.json for current size evidence. INP, real video throughput, real PostgreSQL/container startup, public network and production load remain untested. H2 PG mode is explicitly limited evidence.

An initial reviewer command also supplied a global datasource URL and contaminated nested fixture DB configuration. That run is excluded as product evidence. D1 was reproduced afresh using only the exact CI profile argument, followed by a separate passing bare command.

## Next gate

Round13 is limited to D1 profile/CI isolation and D2 dynamic budget verification. Preserve accepted schema, green UI, accessibility, observer/cold-warm implementation, M1/M2 and data. Do not start Drive/storage or AI. Publish new frozen artifacts for manual review. Codex may commit/push this review checkpoint to dev under the user's explicit authorization; a checkpoint push is not milestone acceptance.
