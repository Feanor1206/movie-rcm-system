# Windows Toolkit Verification Report (DRIVE-01-F03)

**Task:** DRIVE-01-F03  
**Date:** 2026-10-15  
**Engineers:** Agent B (Windows Ownership Implementation) & Agent E (Windows Regressions and Security Seams)  
**Runners Evaluated:**
1. **Windows PowerShell 5.1** (`powershell.exe -NoProfile -File ...`, CLR 4.0.30319.42000)
2. **PowerShell 7** (`pwsh.exe -NoProfile -File ...`, .NET 8.0+)

---

## 1. Executive Summary

This report documents the verification of Google Drive operational scripts under Windows following fixes for finding **R2 (Exact Process Creation Identity, Trustworthy Live Invocation Match, and Fail-Closed Enforcement)**.

All test suites executed with a 100% pass rate across both execution environments with zero syntax or parser errors.

| Test Suite | PowerShell 5.1 | PowerShell 7 | Pass Rate | Primary Focus |
| :--- | :---: | :---: | :---: | :--- |
| **Baseline Tooling Suite** (`test_drive_tooling.ps1`) | **14 / 14** | **14 / 14** | 100% | Preflight schema, dry-run flags, basic PID protection, secret hygiene |
| **Comprehensive Toolkit Suite** (`test_drive_toolkit_comprehensive.ps1`) | **28 / 28** | **28 / 28** | 100% | CJK/Vietnamese path handling, UTF-8 byte array construction, collision detection, argv quoting |
| **Security Seams & PID Safety Suite** (`test_drive_security_seams.ps1`) | **35 / 35** | **35 / 35** | 100% | 9 mandatory fields, exact creation time (<1ms), live `CommandLine` invocation matching, fail-closed audit |
| **Total Test Assertions** | **77 / 77** | **77 / 77** | **100%** | **All suites pass independently on both engines** |

---

## 2. Finding R2 Resolution: Exact Identity & Trustworthy Invocation Matching

### Root Cause
In `DRIVE-01-F02`, `stop_drive.ps1` used a loose start-time tolerance (`diffMs -lt 500`), allowing a process starting 200ms later to pass identity checks. Furthermore, while the 9 schema fields were required to be present in the state file, `stop_drive.ps1` never verified that the live process actually executed the intended mount command line, allowing an unrelated process with the same name/path/PID to be signaled.

### Solutions Applied
1. **Exact Process Creation Identity (Zero Loose Tolerance):**
   - Replaced `diffMs -lt 500` with exact creation time matching:
     `($actualStart -eq $parsedExpectedStart) -or ($diffMs -lt 1.0)`
   - Any difference $\ge 1\text{ ms}$ (including the reviewer's 200ms repro) is immediately rejected as `IDENTITY_MISMATCH` with `VerificationReason = "StartTimeMismatch"`.
   - The state file is preserved on disk; no termination signal is ever sent.
2. **Trustworthy Live Invocation Verification (`CommandLine`):**
   - Live process command line is queried via `$proc.CommandLine` with fallback to `Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid"` and `Get-WmiObject`.
   - Validates that the live command line contains the expected `mount` subcommand, the exact `$remoteTarget`, and the exact `$mountPoint`.
   - If the live command line is unreadable: fails closed (`Status = "VERIFICATION_FAILED"`, `VerificationReason = "CannotReadProcessCommandLine"`), preserves state file.
   - If the live command line does not match (e.g. running `mount unrelated:other Y:` instead of `expected:media Z:`): rejects termination (`Status = "IDENTITY_MISMATCH"`, `VerificationReason = "InvocationMismatch"`), preserves state file.
3. **Protection Against PID Reuse During Verification:**
   - Re-verifies process identity and start time immediately prior to issuing `Stop-Process`.
4. **Policy Synchronization Across Tooling:**
   - Applied identical exact creation identity and live invocation matching to `status_drive.ps1` and the launch-failure cleanup routine in `mount_drive.ps1`.

---

## 3. Reviewer Repro Detectors

| Repro Script | Runner | Status | Expected Output | Actual Output | Result |
| :--- | :--- | :---: | :--- | :--- | :---: |
| `DRIVE_F02_stop_reused_identity.ps1` | `powershell.exe` | Exit 0 | `...Mismatch=False` | `REPRO terminationRequestedDespiteCreationAndInvocationMismatch=False` | **PASS** |
| `DRIVE_F02_stop_reused_identity.ps1` | `pwsh` | Exit 0 | `...Mismatch=False` | `REPRO terminationRequestedDespiteCreationAndInvocationMismatch=False` | **PASS** |
| `DRIVE_F01_stop_missing_identity.ps1` | `powershell.exe` | Exit 0 | `...Fields=False` | `REPRO terminationRequestedWithMissingIdentityFields=False` | **PASS** |
| `DRIVE_F01_stop_missing_identity.ps1` | `pwsh` | Exit 0 | `...Fields=False` | `REPRO terminationRequestedWithMissingIdentityFields=False` | **PASS** |

---

## 4. Evidence Files

- `docs/reports/drive/DRIVE_01_F03/agent-e/toolkit_test_evidence.json`: Full structured test execution log for Windows PowerShell 5.1 (comprehensive 28 + security seams 35 = 63 tests).
- `docs/reports/drive/DRIVE_01_F03/agent-e/toolkit_test_evidence_pwsh.json`: Full structured test execution log for PowerShell 7 (comprehensive 28 + security seams 35 = 63 tests).
