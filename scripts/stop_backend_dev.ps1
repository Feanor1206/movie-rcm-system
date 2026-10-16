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
$targetPid = [int]$state.PID
$expectedStartTime = [DateTime]::Parse($state.StartTime)
$expectedExe = [string]$state.ExecutablePath

# R3 Fix: Inspect live process through WMI/CIM for canonical executable, start time, and command line
$cimProc = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction SilentlyContinue
if (-not $cimProc) {
    Write-Host "[stop_backend_dev] Process with PID $targetPid is no longer running."
    Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
    return
}

# 1. Process Name verification
$procName = $cimProc.Name.ToLowerInvariant()
if ($procName -ne "java.exe" -and $procName -ne "java") {
    throw "[stop_backend_dev] IDENTITY_MISMATCH: Live process PID $targetPid name is '$($cimProc.Name)', expected 'java.exe'. Aborting fail-closed without signaling."
}

# 2. Executable Path verification (case-insensitive canonical comparison)
if ($expectedExe -and $cimProc.ExecutablePath) {
    $canonicalLiveExe = [System.IO.Path]::GetFullPath($cimProc.ExecutablePath).ToLowerInvariant()
    $canonicalExpectedExe = [System.IO.Path]::GetFullPath($expectedExe).ToLowerInvariant()
    if ($canonicalLiveExe -ne $canonicalExpectedExe) {
        throw "[stop_backend_dev] IDENTITY_MISMATCH: Live process PID $targetPid executable path '$canonicalLiveExe' does not match recorded executable '$canonicalExpectedExe'. Aborting fail-closed without signaling."
    }
}

# 3. CommandLine argument verification (must contain expected application and profile)
$cmdLine = [string]$cimProc.CommandLine
if (-not $cmdLine.Contains("MovieRcmApplication") -or -not $cmdLine.Contains("snapshot")) {
    throw "[stop_backend_dev] IDENTITY_MISMATCH: Live process PID $targetPid CommandLine does not contain expected application or profile markers. CommandLine: '$cmdLine'. Aborting fail-closed without signaling."
}

# 4. StartTime / CreationDate verification (within 3 seconds tolerance)
if ($cimProc.CreationDate) {
    $liveCreationDate = $cimProc.CreationDate.ToUniversalTime()
    $expectedUtc = $expectedStartTime.ToUniversalTime()
    $timeDelta = [Math]::Abs(($liveCreationDate - $expectedUtc).TotalSeconds)
    if ($timeDelta -gt 3.0) {
        throw "[stop_backend_dev] IDENTITY_MISMATCH: PID $targetPid CreationDate ($liveCreationDate) does not match recorded StartTime ($expectedUtc, delta $timeDelta s). Aborting fail-closed without signaling."
    }
}

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
    Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
} else {
    throw "[stop_backend_dev] FAILED: Process PID $targetPid could not be stopped within 10 seconds."
}
