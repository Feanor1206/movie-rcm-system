<#
.SYNOPSIS
    Queries and verifies the health and operational status of the Google Drive mount.
.DESCRIPTION
    Checks active rclone processes against state JSON with strict identity verification
    (PID, process name, normalized executable path, sub-second StartTime tolerance,
    and SessionId). Inspects mount target accessibility and filesystem responsiveness.
    Enforces complete 9-field schema verification. If any identity field is missing or
    mismatched, reports DEGRADED state with explanatory diagnostic reasons.
    Returns status: MOUNTED, NOT_MOUNTED, or DEGRADED.
    Enforces Fail-Closed posture and does NOT leak secrets or tokens.
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

# Extract complete state schema fields without permissive defaults
$savedPid = $null
if ($stateData -and $stateData.PSObject.Properties['pid'] -and $stateData.pid -ne $null) {
    $pVal = 0
    if ([int]::TryParse([string]$stateData.pid, [ref]$pVal) -and $pVal -gt 0) {
        $savedPid = $pVal
    }
}

$expectedName = if ($stateData -and $stateData.PSObject.Properties['processName'] -and $stateData.processName) { [string]$stateData.processName } else { $null }
$expectedPath = if ($stateData -and $stateData.PSObject.Properties['executablePath'] -and $stateData.executablePath) { [string]$stateData.executablePath } else { $null }
$recordedStartStr = if ($stateData -and $stateData.PSObject.Properties['startTime'] -and $stateData.startTime) {
                        if ($stateData.startTime -is [DateTime] -or $stateData.startTime -is [DateTimeOffset]) {
                            $stateData.startTime.ToString("o")
                        } else {
                            [string]$stateData.startTime
                        }
                    } else { $null }

$expectedSessionId = $null
if ($stateData -and $stateData.PSObject.Properties['sessionId'] -and $stateData.sessionId -ne $null) {
    $sVal = 0
    if ([int]::TryParse([string]$stateData.sessionId, [ref]$sVal)) {
        $expectedSessionId = $sVal
    }
}

$targetMount = if ($stateData -and $stateData.PSObject.Properties['mountPoint'] -and $stateData.mountPoint) { [string]$stateData.mountPoint } else { $MountPoint }
$remoteTarget = if ($stateData -and $stateData.PSObject.Properties['remoteTarget'] -and $stateData.remoteTarget) { [string]$stateData.remoteTarget } else { $null }
$arguments = if ($stateData) {
                 if ($stateData.PSObject.Properties['arguments'] -and $stateData.arguments) {
                     $stateData.arguments
                 } elseif ($stateData.PSObject.Properties['flags'] -and $stateData.flags) {
                     $stateData.flags
                 } else { $null }
             } else { $null }
$stateStatus = if ($stateData -and $stateData.PSObject.Properties['status'] -and $stateData.status) { [string]$stateData.status } else { $null }

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

# Scenario 1: No state file recorded or empty/corrupted state file
if (-not $stateExists -or -not $stateData) {
    $status = "NOT_MOUNTED"
    $reason = if (-not $stateExists) { "No state file found at '$StateFile'." } else { "State file at '$StateFile' is unreadable or empty." }

    if ($mountAccess.Exists) {
        $status = "DEGRADED"
        $reason = "Mount point '$targetMount' is present in the filesystem, but no state file was found at '$StateFile' (untracked or external mount)."
    }

    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = $status
        Reason         = $reason
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $null
        ProcessName    = $null
        ExecutablePath = $null
        StartTime      = $null
        SessionId      = $null
        RemoteTarget   = $null
        Arguments      = $null
        StateStatus    = $null
        ProcessAlive   = $false
        Accessible     = $mountAccess.IsReadable
    }

    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Scenario 2: State file recorded, inspect process
$proc = $null
if ($savedPid -and $savedPid -gt 0) {
    $proc = Get-Process -Id $savedPid -ErrorAction SilentlyContinue
}

# Process does not exist
if (-not $proc) {
    $status = "NOT_MOUNTED"
    $reason = "Recorded rclone process (PID $($savedPid)) is not active."
    if ($mountAccess.Exists) {
        $status = "DEGRADED"
        $reason = "Recorded process (PID $($savedPid)) has exited, but mount point '$targetMount' is still held or stale in the OS."
    }

    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = $status
        Reason         = $reason
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $savedPid
        ProcessName    = $expectedName
        ExecutablePath = $expectedPath
        StartTime      = $recordedStartStr
        SessionId      = $expectedSessionId
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        ProcessAlive   = $false
        Accessible     = $mountAccess.IsReadable
    }

    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# ================= STRICT PROCESS IDENTITY VERIFICATION =================

# Verification 1: ProcessName match against OS process
if ($proc.ProcessName -ine "rclone" -or ($expectedName -and $proc.ProcessName -ine $expectedName)) {
    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = "DEGRADED"
        Reason         = "PID $($savedPid) is occupied by '$($proc.ProcessName)', which does not match expected process '$expectedName'. PID reuse detected."
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $savedPid
        ProcessName    = $proc.ProcessName
        ExecutablePath = $expectedPath
        StartTime      = $recordedStartStr
        SessionId      = $expectedSessionId
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        ProcessAlive   = $true
        Accessible     = $mountAccess.IsReadable
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Schema completeness checks
if (-not $expectedName -or $expectedName -ine "rclone") {
    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = "DEGRADED"
        Reason         = "State file is missing or has invalid 'processName' field. Expected 'rclone'. Identity unverified."
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $savedPid
        ProcessName    = $proc.ProcessName
        ExecutablePath = $expectedPath
        StartTime      = $recordedStartStr
        SessionId      = $expectedSessionId
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        ProcessAlive   = $true
        Accessible     = $mountAccess.IsReadable
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

if (-not $expectedPath -or [string]::IsNullOrWhiteSpace($expectedPath)) {
    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = "DEGRADED"
        Reason         = "State file is missing required 'executablePath' field. Identity unverified."
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $savedPid
        ProcessName    = $proc.ProcessName
        ExecutablePath = $null
        StartTime      = $recordedStartStr
        SessionId      = $expectedSessionId
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        ProcessAlive   = $true
        Accessible     = $mountAccess.IsReadable
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Verification 2: Executable Path
$procPath = $null
try {
    if ($proc.Path) { $procPath = $proc.Path }
} catch {}
if (-not $procPath) {
    try {
        if ($proc.MainModule -and $proc.MainModule.FileName) { $procPath = $proc.MainModule.FileName }
    } catch {}
}

if (-not $procPath) {
    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = "DEGRADED"
        Reason         = "Unable to read process executable path for PID $($savedPid). Identity unverified."
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $savedPid
        ProcessName    = $proc.ProcessName
        ExecutablePath = $expectedPath
        StartTime      = $recordedStartStr
        SessionId      = $expectedSessionId
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        ProcessAlive   = $true
        Accessible     = $mountAccess.IsReadable
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

$normProcPath = ""
$normExpectedPath = ""
try {
    $normProcPath = [System.IO.Path]::GetFullPath($procPath).TrimEnd('\')
    $normExpectedPath = [System.IO.Path]::GetFullPath($expectedPath).TrimEnd('\')
} catch {}

if (-not [string]::Equals($normProcPath, $normExpectedPath, [System.StringComparison]::OrdinalIgnoreCase)) {
    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = "DEGRADED"
        Reason         = "PID $($savedPid) executable path '$procPath' does not match recorded executablePath '$expectedPath'. Identity mismatch / PID reuse detected."
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $savedPid
        ProcessName    = $proc.ProcessName
        ExecutablePath = $procPath
        StartTime      = $recordedStartStr
        SessionId      = $expectedSessionId
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        ProcessAlive   = $true
        Accessible     = $mountAccess.IsReadable
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Verification 3: StartTime (<500ms precision)
if (-not $recordedStartStr -or [string]::IsNullOrWhiteSpace($recordedStartStr)) {
    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = "DEGRADED"
        Reason         = "State file is missing required 'startTime' field. Identity unverified."
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $savedPid
        ProcessName    = $proc.ProcessName
        ExecutablePath = $expectedPath
        StartTime      = $null
        SessionId      = $expectedSessionId
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        ProcessAlive   = $true
        Accessible     = $mountAccess.IsReadable
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

$startTimeMatch = $false
try {
    $expectedStart = [DateTimeOffset]::Parse($recordedStartStr)
    $actualStart = [DateTimeOffset]::new($proc.StartTime)
    $diffMs = [math]::Abs(($actualStart - $expectedStart).TotalMilliseconds)
    if ($diffMs -lt 500) {
        $startTimeMatch = $true
    }
} catch {
    $startTimeMatch = $false
}

if (-not $startTimeMatch) {
    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = "DEGRADED"
        Reason         = "PID $($savedPid) start time ($($proc.StartTime.ToString('o'))) does not match recorded state ($recordedStartStr). PID reuse detected."
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $savedPid
        ProcessName    = $proc.ProcessName
        ExecutablePath = $expectedPath
        StartTime      = $proc.StartTime.ToString("o")
        SessionId      = $expectedSessionId
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        ProcessAlive   = $true
        Accessible     = $mountAccess.IsReadable
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Verification 4: SessionId
if ($expectedSessionId -eq $null) {
    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = "DEGRADED"
        Reason         = "State file is missing required 'sessionId' field. Identity unverified."
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $savedPid
        ProcessName    = $proc.ProcessName
        ExecutablePath = $expectedPath
        StartTime      = $recordedStartStr
        SessionId      = $null
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        ProcessAlive   = $true
        Accessible     = $mountAccess.IsReadable
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

if ($proc.SessionId -ne $expectedSessionId) {
    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = "DEGRADED"
        Reason         = "PID $($savedPid) SessionId ($($proc.SessionId)) does not match recorded sessionId ($expectedSessionId)."
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $savedPid
        ProcessName    = $proc.ProcessName
        ExecutablePath = $expectedPath
        StartTime      = $recordedStartStr
        SessionId      = $proc.SessionId
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        ProcessAlive   = $true
        Accessible     = $mountAccess.IsReadable
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Verification 5: Mount Target, Arguments, Status presence
if (-not $targetMount -or [string]::IsNullOrWhiteSpace($targetMount) -or
    -not $remoteTarget -or [string]::IsNullOrWhiteSpace($remoteTarget) -or
    -not $arguments -or -not $stateStatus) {
    $res = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        Status         = "DEGRADED"
        Reason         = "State file is missing required mountPoint, remoteTarget, arguments, or status fields. Identity unverified."
        MountPoint     = $targetMount
        StateFile      = $StateFile
        PID            = $savedPid
        ProcessName    = $proc.ProcessName
        ExecutablePath = $expectedPath
        StartTime      = $recordedStartStr
        SessionId      = $proc.SessionId
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        ProcessAlive   = $true
        Accessible     = $mountAccess.IsReadable
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Genuine rclone process confirmed running with 100% verified identity
if ($mountAccess.IsReadable) {
    $status = "MOUNTED"
    $reason = "Verified rclone mount process (PID $($savedPid)) is running and mount target '$targetMount' is responsive."
} else {
    $status = "DEGRADED"
    $reason = "Verified rclone mount process (PID $($savedPid)) is running, but mount target '$targetMount' is not yet readable or accessible."
}

$res = [PSCustomObject]@{
    Timestamp      = [DateTime]::UtcNow.ToString("o")
    Status         = $status
    Reason         = $reason
    MountPoint     = $targetMount
    StateFile      = $StateFile
    PID            = $savedPid
    ProcessName    = $proc.ProcessName
    ExecutablePath = $expectedPath
    StartTime      = $recordedStartStr
    SessionId      = $proc.SessionId
    RemoteTarget   = $remoteTarget
    Arguments      = $arguments
    StateStatus    = $stateStatus
    ProcessAlive   = $true
    Accessible     = $mountAccess.IsReadable
}

if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
