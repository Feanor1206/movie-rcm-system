<#
.SYNOPSIS
    Safely terminates an rclone Google Drive mount process on Windows.
.DESCRIPTION
    Reads state JSON and strictly verifies the recorded PID against process name,
    executable path, and process start time before termination.
    Prevents killing unrelated processes or other user rclone instances (no broad kill-by-name).
    Cleans up the state file upon successful termination.
.PARAMETER StateFile
    Path to runtime process state JSON. Defaults to $env:TEMP\movie-rcm-drive-mount.json.
.PARAMETER Force
    Force kill the verified rclone process.
.PARAMETER AsJson
    Output results strictly as JSON string.
#>
[CmdletBinding()]
param(
    [string]$StateFile,
    [switch]$Force,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $StateFile) {
    $tempDir = if ($env:TEMP) { $env:TEMP } else { [System.IO.Path]::GetTempPath() }
    $StateFile = Join-Path $tempDir "movie-rcm-drive-mount.json"
}

if (-not (Test-Path -Path $StateFile -PathType Leaf -ErrorAction SilentlyContinue)) {
    $res = [PSCustomObject]@{
        Success   = $false
        Status    = "NOT_FOUND"
        PID       = $null
        Message   = "State file '$StateFile' was not found. No tracked rclone mount process to stop."
        StateFile = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Read state JSON
$stateRaw = Get-Content -Path $StateFile -Raw -Encoding UTF8
$stateData = $null
try {
    $stateData = $stateRaw | ConvertFrom-Json
} catch {
    throw "Corrupted or unreadable state file at '$StateFile': $($_.Exception.Message)"
}

if (-not $stateData -or -not $stateData.pid) {
    Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
    $res = [PSCustomObject]@{
        Success   = $true
        Status    = "CLEANED_EMPTY_STATE"
        PID       = $null
        Message   = "State file did not contain a valid PID. Cleaned up state file."
        StateFile = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

$targetPid = [int]$stateData.pid
$proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue

# If process is already terminated, clean up state file
if (-not $proc) {
    Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
    $res = [PSCustomObject]@{
        Success   = $true
        Status    = "ALREADY_STOPPED"
        PID       = $targetPid
        Message   = "Process with PID $targetPid is already inactive. Cleaned up state file."
        StateFile = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# ================= PID REUSE & IDENTITY VERIFICATION =================
# Check 1: Process Name must be rclone
if ($proc.ProcessName -ine "rclone") {
    $res = [PSCustomObject]@{
        Success    = $false
        Status     = "PID_REUSE_REJECTED"
        PID        = $targetPid
        ActualName = $proc.ProcessName
        Message    = "Refusing to kill PID $($targetPid): active process name is '$($proc.ProcessName)', which does not match expected process 'rclone'. Process identity mismatch / PID reuse detected."
        StateFile  = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Check 2: Start time verification
$startTimeMatch = $true
$recordedStartStr = [string]$stateData.startTime
if ($recordedStartStr) {
    try {
        $expectedStart = [DateTimeOffset]::Parse($recordedStartStr)
        $actualStart = [DateTimeOffset]::new($proc.StartTime)
        $diffSeconds = [math]::Abs(($actualStart - $expectedStart).TotalSeconds)
        if ($diffSeconds -gt 5) {
            $startTimeMatch = $false
        }
    } catch {
        if ($recordedStartStr -ne $proc.StartTime.ToString("o")) {
            $startTimeMatch = $false
        }
    }
}

if (-not $startTimeMatch) {
    $res = [PSCustomObject]@{
        Success           = $false
        Status            = "PID_REUSE_REJECTED"
        PID               = $targetPid
        ActualStartTime   = $proc.StartTime.ToString("o")
        ExpectedStartTime = $recordedStartStr
        Message           = "Refusing to kill PID $($targetPid): process start time ($($proc.StartTime.ToString('o'))) does not match recorded state ($recordedStartStr). PID reuse detected."
        StateFile         = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# ================= TERMINATION OF VERIFIED PROCESS =================
try {
    Stop-Process -Id $targetPid -Force:$Force -ErrorAction Stop

    # Wait up to 5 seconds for process termination
    $exited = $false
    for ($i = 0; $i -lt 10; $i++) {
        if (-not (Get-Process -Id $targetPid -ErrorAction SilentlyContinue)) {
            $exited = $true
            break
        }
        Start-Sleep -Milliseconds 500
    }

    if ($exited) {
        Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
        $res = [PSCustomObject]@{
            Success    = $true
            Status     = "STOPPED"
            PID        = $targetPid
            MountPoint = $stateData.mountPoint
            Message    = "Successfully stopped verified rclone mount process (PID $targetPid)."
            StateFile  = $StateFile
        }
    } else {
        $res = [PSCustomObject]@{
            Success    = $false
            Status     = "STOP_TIMEOUT"
            PID        = $targetPid
            MountPoint = $stateData.mountPoint
            Message    = "Process (PID $targetPid) was signaled to stop, but was still running after 5 seconds."
            StateFile  = $StateFile
        }
    }
} catch {
    $res = [PSCustomObject]@{
        Success    = $false
        Status     = "STOP_ERROR"
        PID        = $targetPid
        MountPoint = $stateData.mountPoint
        Message    = "Failed to stop process (PID $targetPid): $($_.Exception.Message)"
        StateFile  = $StateFile
    }
}

if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
