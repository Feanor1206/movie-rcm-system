<#
.SYNOPSIS
    Queries and verifies the health and operational status of the Google Drive mount.
.DESCRIPTION
    Checks active rclone processes against state JSON (validating PID, process name,
    and start time to prevent PID reuse misreports). Inspects mount target accessibility.
    Returns status: MOUNTED, NOT_MOUNTED, or DEGRADED with explanatory diagnostic reasons.
    Does NOT leak secrets, tokens, or credential contents.
.PARAMETER MountPoint
    Target mount point to verify (default "M:").
.PARAMETER StateFile
    Path to runtime process state JSON. Defaults to $env:TEMP\movie-rcm-drive-mount.json.
.PARAMETER AsJson
    Output status strictly as JSON string.
#>
[CmdletBinding()]
param(
    [string]$MountPoint = "M:",
    [string]$StateFile,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $StateFile) {
    $tempDir = if ($env:TEMP) { $env:TEMP } else { [System.IO.Path]::GetTempPath() }
    $StateFile = Join-Path $tempDir "movie-rcm-drive-mount.json"
}

$stateExists = Test-Path -Path $StateFile -PathType Leaf -ErrorAction SilentlyContinue
$stateData = $null
if ($stateExists) {
    try {
        $stateRaw = Get-Content -Path $StateFile -Raw -Encoding UTF8
        if ($stateRaw) {
            $stateData = $stateRaw | ConvertFrom-Json
        }
    } catch {
        # State file read or parse error
    }
}

# Determine effective target mount point
$targetMount = $MountPoint
if ($stateData -and $stateData.mountPoint) {
    $targetMount = $stateData.mountPoint
}

# Helper to check if a drive or directory is accessible
function Test-MountAccessibility {
    param([string]$Target)

    $access = [PSCustomObject]@{
        Exists       = $false
        IsReadable   = $false
        DriveFormat  = $null
        ErrorMessage = $null
    }

    if (-not $Target) {
        return $access
    }

    try {
        if ($Target -match "^[A-Za-z]:?\\?$") {
            $letter = $Target.Substring(0, 1).ToUpper()
            $prefix = "$($letter):\"
            $drives = [System.IO.DriveInfo]::GetDrives()
            $matched = $drives | Where-Object { $_.Name.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase) }
            if ($matched) {
                $access.Exists = $true
                try {
                    $access.DriveFormat = $matched.DriveFormat
                    $access.IsReadable = $matched.IsReady
                } catch {
                    $access.ErrorMessage = $_.Exception.Message
                }
            } else {
                # Fallback to Test-Path
                if (Test-Path -Path $Target -ErrorAction SilentlyContinue) {
                    $access.Exists = $true
                    $access.IsReadable = $true
                }
            }
        } else {
            if (Test-Path -Path $Target -ErrorAction SilentlyContinue) {
                $access.Exists = $true
                # Test directory readability
                $null = Get-ChildItem -Path $Target -ErrorAction Stop | Select-Object -First 1
                $access.IsReadable = $true
            }
        }
    } catch {
        $access.ErrorMessage = $_.Exception.Message
    }

    return $access
}

$mountAccess = Test-MountAccessibility -Target $targetMount

# Scenario 1: No state file recorded
if (-not $stateExists -or -not $stateData) {
    $status = "NOT_MOUNTED"
    $reason = "No state file found at '$StateFile'."

    if ($mountAccess.Exists) {
        $status = "DEGRADED"
        $reason = "Mount point '$targetMount' is present in the filesystem, but no state file was found at '$StateFile' (untracked or external mount)."
    }

    $res = [PSCustomObject]@{
        Timestamp    = [DateTime]::UtcNow.ToString("o")
        Status       = $status
        Reason       = $reason
        MountPoint   = $targetMount
        StateFile    = $StateFile
        PID          = $null
        ProcessAlive = $false
        Accessible   = $mountAccess.IsReadable
        RemoteTarget = $null
    }

    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Scenario 2: State file recorded, inspect process
$savedPid = $stateData.pid
$proc = $null
if ($savedPid) {
    $proc = Get-Process -Id $savedPid -ErrorAction SilentlyContinue
}

# Process does not exist
if (-not $proc) {
    $status = "NOT_MOUNTED"
    $reason = "Recorded rclone process (PID $savedPid) is not active."
    if ($mountAccess.Exists) {
        $status = "DEGRADED"
        $reason = "Recorded process (PID $savedPid) has exited, but mount point '$targetMount' is still held or stale."
    }

    $res = [PSCustomObject]@{
        Timestamp    = [DateTime]::UtcNow.ToString("o")
        Status       = $status
        Reason       = $reason
        MountPoint   = $targetMount
        StateFile    = $StateFile
        PID          = $savedPid
        ProcessAlive = $false
        Accessible   = $mountAccess.IsReadable
        RemoteTarget = $stateData.remoteTarget
    }

    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Process exists - validate identity to protect against PID reuse
$isRcloneProcess = ($proc.ProcessName -ieq "rclone")
$startTimeMatch = $true
if ($stateData.startTime) {
    try {
        $expectedStart = [DateTimeOffset]::Parse([string]$stateData.startTime)
        $actualStart = [DateTimeOffset]::new($proc.StartTime)
        $diffSeconds = [math]::Abs(($actualStart - $expectedStart).TotalSeconds)
        if ($diffSeconds -gt 5) {
            $startTimeMatch = $false
        }
    } catch {
        # If parsing fails, fall back to string equality check
        if ($stateData.startTime -ne $proc.StartTime.ToString("o")) {
            $startTimeMatch = $false
        }
    }
}

if (-not $isRcloneProcess -or -not $startTimeMatch) {
    $status = "DEGRADED"
    $reason = "PID $savedPid is occupied by a different process ('$($proc.ProcessName)', StartTime: $($proc.StartTime.ToString('o'))). PID reuse detected."

    $res = [PSCustomObject]@{
        Timestamp    = [DateTime]::UtcNow.ToString("o")
        Status       = $status
        Reason       = $reason
        MountPoint   = $targetMount
        StateFile    = $StateFile
        PID          = $savedPid
        ProcessAlive = $true
        Accessible   = $mountAccess.IsReadable
        RemoteTarget = $stateData.remoteTarget
    }

    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Genuine rclone process confirmed running
if ($mountAccess.IsReadable) {
    $status = "MOUNTED"
    $reason = "Verified rclone mount process (PID $savedPid) is running and mount target '$targetMount' is accessible."
} else {
    $status = "DEGRADED"
    $reason = "Verified rclone mount process (PID $savedPid) is running, but mount target '$targetMount' is not yet readable or accessible."
}

$res = [PSCustomObject]@{
    Timestamp    = [DateTime]::UtcNow.ToString("o")
    Status       = $status
    Reason       = $reason
    MountPoint   = $targetMount
    StateFile    = $StateFile
    PID          = $savedPid
    ProcessAlive = $true
    Accessible   = $mountAccess.IsReadable
    RemoteTarget = $stateData.remoteTarget
}

if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
