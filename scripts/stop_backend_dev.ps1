[CmdletBinding()]
param(
    [string]$StateFile,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $StateFile) {
    $StateFile = Join-Path $root "backend\springboot\target\backend_dev.json"
}

if (-not (Test-Path -Path $StateFile -PathType Leaf -ErrorAction SilentlyContinue)) {
    Write-Host "[stop_backend_dev] No state file found at '$StateFile'. No tracked backend process to stop."
    return
}

$state = Get-Content -Path $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json

# 1. State file complete non-empty identity validation (fail-closed)
if ($null -eq $state.PID -or [int]$state.PID -le 0) {
    Write-Warning "[stop_backend_dev] INVALID_STATE: State file missing valid PID. Aborting fail-closed without signaling."
    return
}
if ([string]::IsNullOrWhiteSpace($state.StartTime)) {
    Write-Warning "[stop_backend_dev] INVALID_STATE: State file missing required StartTime. Aborting fail-closed without signaling."
    return
}
if ([string]::IsNullOrWhiteSpace($state.ExecutablePath)) {
    Write-Warning "[stop_backend_dev] INVALID_STATE: State file missing required ExecutablePath. Aborting fail-closed without signaling."
    return
}

$targetPid = [int]$state.PID
try {
    $expectedStartTime = [DateTime]::Parse($state.StartTime)
} catch {
    Write-Warning "[stop_backend_dev] INVALID_STATE: State file StartTime is invalid: $($state.StartTime). Aborting fail-closed without signaling."
    return
}
$expectedExe = [string]$state.ExecutablePath

# 2. Inspect live process through WMI/CIM
$cimProc = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction SilentlyContinue
if (-not $cimProc) {
    Write-Host "[stop_backend_dev] Process with PID $targetPid is no longer running."
    if (Test-Path -Path $StateFile) {
        try {
            $cur = Get-Content -Path $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($cur.PID -eq $targetPid) {
                Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
    return
}

# 3. Live process complete non-empty identity validation (fail-closed)
if ([string]::IsNullOrWhiteSpace($cimProc.Name)) {
    Write-Warning "[stop_backend_dev] IDENTITY_INCOMPLETE: Live process PID $targetPid has empty Name. Aborting fail-closed without signaling."
    return
}
if ([string]::IsNullOrWhiteSpace($cimProc.ExecutablePath)) {
    Write-Warning "[stop_backend_dev] IDENTITY_INCOMPLETE: Live process PID $targetPid has empty ExecutablePath. Aborting fail-closed without signaling."
    return
}
if ([string]::IsNullOrWhiteSpace($cimProc.CommandLine)) {
    Write-Warning "[stop_backend_dev] IDENTITY_INCOMPLETE: Live process PID $targetPid has empty CommandLine. Aborting fail-closed without signaling."
    return
}
if ($null -eq $cimProc.CreationDate) {
    Write-Warning "[stop_backend_dev] IDENTITY_INCOMPLETE: Live process PID $targetPid has null CreationDate. Aborting fail-closed without signaling."
    return
}

# 4. Process Name verification
$procName = $cimProc.Name.ToLowerInvariant()
if ($procName -ne "java.exe" -and $procName -ne "java") {
    Write-Warning "[stop_backend_dev] IDENTITY_MISMATCH: Live process PID $targetPid name is '$($cimProc.Name)', expected 'java.exe'. Aborting fail-closed without signaling."
    return
}

# 5. Executable Path verification (case-insensitive canonical comparison)
$canonicalLiveExe = [System.IO.Path]::GetFullPath($cimProc.ExecutablePath).ToLowerInvariant()
$canonicalExpectedExe = [System.IO.Path]::GetFullPath($expectedExe).ToLowerInvariant()
if ($canonicalLiveExe -ne $canonicalExpectedExe) {
    Write-Warning "[stop_backend_dev] IDENTITY_MISMATCH: Live process PID $targetPid executable path '$canonicalLiveExe' does not match recorded executable '$canonicalExpectedExe'. Aborting fail-closed without signaling."
    return
}

# 6. CommandLine argument verification (must contain expected application and snapshot profile)
$cmdLine = [string]$cimProc.CommandLine
if ((-not $cmdLine.Contains("MovieRcmApplication") -and -not $cmdLine.Contains("moviercm-backend")) -or -not $cmdLine.Contains("snapshot")) {
    Write-Warning "[stop_backend_dev] IDENTITY_MISMATCH: Live process PID $targetPid CommandLine does not contain expected application or profile markers. CommandLine: '$cmdLine'. Aborting fail-closed without signaling."
    return
}

# 7. StartTime / CreationDate verification (within 3 seconds tolerance)
$liveCreationDate = $cimProc.CreationDate.ToUniversalTime()
$expectedUtc = $expectedStartTime.ToUniversalTime()
$timeDelta = [Math]::Abs(($liveCreationDate - $expectedUtc).TotalSeconds)
if ($timeDelta -gt 3.0) {
    Write-Warning "[stop_backend_dev] IDENTITY_MISMATCH: PID $targetPid CreationDate ($liveCreationDate) does not match recorded StartTime ($expectedUtc, delta $timeDelta s). Aborting fail-closed without signaling."
    return
}

# 8. Hold verified process instance for signaling
Write-Host "[stop_backend_dev] Verified process identity for PID $targetPid ($procName). Stopping process..."
try {
    Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
} catch {}

# Wait for process termination
$deadline = [DateTime]::UtcNow.AddSeconds(10)
while ([DateTime]::UtcNow -lt $deadline) {
    if (-not (Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction SilentlyContinue)) {
        break
    }
    Start-Sleep -Milliseconds 300
}

if (-not (Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction SilentlyContinue)) {
    Write-Host "[stop_backend_dev] SUCCESS: Process PID $targetPid stopped successfully."
    # Guard state removal against new-start races: only remove if PID still matches
    if (Test-Path -Path $StateFile) {
        try {
            $curState = Get-Content -Path $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($curState.PID -eq $targetPid) {
                Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
} else {
    Write-Warning "[stop_backend_dev] FAILED: Process PID $targetPid could not be stopped within 10 seconds."
}
