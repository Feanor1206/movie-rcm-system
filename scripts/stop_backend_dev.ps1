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

$proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
if (-not $proc) {
    Write-Host "[stop_backend_dev] Process with PID $targetPid is no longer running."
    Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
    return
}

# Strict Identity Verification:
# 1. Process name must be java
if ($proc.ProcessName -ne "java") {
    throw "[stop_backend_dev] IDENTITY_MISMATCH: PID $targetPid process name is '$($proc.ProcessName)', expected 'java'. Aborting shutdown."
}

# 2. StartTime verification (within 2 seconds delta to account for parsing/resolution)
$timeDelta = [Math]::Abs(($proc.StartTime - $expectedStartTime).TotalSeconds)
if ($timeDelta -gt 2.0) {
    throw "[stop_backend_dev] IDENTITY_MISMATCH: PID $targetPid StartTime ($($proc.StartTime)) does not match recorded StartTime ($expectedStartTime). Aborting shutdown."
}

Write-Host "[stop_backend_dev] Stopping verified backend process PID $targetPid..."
Stop-Process -Id $targetPid -Force
Start-Sleep -Milliseconds 500

if (-not (Get-Process -Id $targetPid -ErrorAction SilentlyContinue)) {
    Write-Host "[stop_backend_dev] Process PID $targetPid stopped successfully."
    Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
} else {
    throw "[stop_backend_dev] Failed to stop process PID $targetPid."
}
