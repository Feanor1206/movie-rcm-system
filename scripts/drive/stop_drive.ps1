<#
.SYNOPSIS
    Safely terminates an rclone Google Drive mount process on Windows.
.DESCRIPTION
    Reads state JSON and strictly verifies the recorded PID against process name,
    executable path (normalized full path), process start time (<500ms tolerance),
    and session ID before issuing any termination signal.
    Enforces Fail-Closed security: all 9 identity fields (pid, processName,
    executablePath, startTime, sessionId, mountPoint, remoteTarget, arguments, status)
    must be present, non-empty, and valid. If any identity attribute is missing,
    unreadable, or mismatched, termination is strictly rejected (IDENTITY_MISMATCH /
    VERIFICATION_FAILED) and the state file is preserved on disk for diagnostic inspection.
    Only the verified PID is terminated (never broad kill-by-name).
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
        Success        = $false
        Status         = "NOT_FOUND"
        PID            = $null
        ProcessName    = $null
        ExecutablePath = $null
        StartTime      = $null
        SessionId      = $null
        MountPoint     = $null
        RemoteTarget   = $null
        Arguments      = $null
        StateStatus    = $null
        Message        = "State file '$StateFile' was not found. No tracked rclone mount process to stop."
        StateFile      = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# 1. Read and parse state JSON
$stateRaw = Get-Content -Path $StateFile -Raw -Encoding UTF8
$stateData = $null
try {
    $stateData = $stateRaw | ConvertFrom-Json
} catch {
    # Fail closed on corrupt state file - do not kill any process
    $res = [PSCustomObject]@{
        Success        = $false
        Status         = "VERIFICATION_FAILED"
        PID            = $null
        ProcessName    = $null
        ExecutablePath = $null
        StartTime      = $null
        SessionId      = $null
        MountPoint     = $null
        RemoteTarget   = $null
        Arguments      = $null
        StateStatus    = $null
        Message        = "Corrupted or unreadable state file at '$StateFile': $($_.Exception.Message). Preserving state file."
        StateFile      = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

if (-not $stateData) {
    # Fail closed on empty state file
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $null
        ProcessName        = $null
        ExecutablePath     = $null
        StartTime          = $null
        SessionId          = $null
        MountPoint         = $null
        RemoteTarget       = $null
        Arguments          = $null
        StateStatus        = $null
        VerificationReason = "EmptyStateFile"
        Message            = "State file '$StateFile' is empty or invalid JSON. Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# 2. Extract state schema fields
$targetPid = $null
if ($stateData.PSObject.Properties['pid'] -and $stateData.pid -ne $null) {
    $parsedPid = 0
    if ([int]::TryParse([string]$stateData.pid, [ref]$parsedPid) -and $parsedPid -gt 0) {
        $targetPid = $parsedPid
    }
}

$expectedName = if ($stateData.PSObject.Properties['processName'] -and $stateData.processName) { [string]$stateData.processName } else { $null }
$expectedPath = if ($stateData.PSObject.Properties['executablePath'] -and $stateData.executablePath) { [string]$stateData.executablePath } else { $null }
$recordedStartStr = if ($stateData.PSObject.Properties['startTime'] -and $stateData.startTime) {
                        if ($stateData.startTime -is [DateTime] -or $stateData.startTime -is [DateTimeOffset]) {
                            $stateData.startTime.ToString("o")
                        } else {
                            [string]$stateData.startTime
                        }
                    } else { $null }

$expectedSessionId = $null
if ($stateData.PSObject.Properties['sessionId'] -and $stateData.sessionId -ne $null) {
    $parsedSession = 0
    if ([int]::TryParse([string]$stateData.sessionId, [ref]$parsedSession)) {
        $expectedSessionId = $parsedSession
    }
}

$mountPoint = if ($stateData.PSObject.Properties['mountPoint'] -and $stateData.mountPoint) { [string]$stateData.mountPoint } else { $null }
$remoteTarget = if ($stateData.PSObject.Properties['remoteTarget'] -and $stateData.remoteTarget) { [string]$stateData.remoteTarget } else { $null }
$arguments = if ($stateData.PSObject.Properties['arguments'] -and $stateData.arguments) {
                 $stateData.arguments
             } elseif ($stateData.PSObject.Properties['flags'] -and $stateData.flags) {
                 $stateData.flags
             } else { $null }
$stateStatus = if ($stateData.PSObject.Properties['status'] -and $stateData.status) { [string]$stateData.status } else { $null }

# Fail closed if PID is missing or invalid
if (-not $targetPid -or $targetPid -le 0) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $null
        ProcessName        = $expectedName
        ExecutablePath     = $expectedPath
        StartTime          = $recordedStartStr
        SessionId          = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "MissingPidInState"
        Message            = "State file does not contain a valid PID. Fail closed: refusing to stop any process. Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# 3. Retrieve live process
$proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue

# If process is not running, clean up state file
if (-not $proc) {
    Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
    $res = [PSCustomObject]@{
        Success        = $true
        Status         = "ALREADY_STOPPED"
        PID            = $targetPid
        ProcessName    = $expectedName
        ExecutablePath = $expectedPath
        StartTime      = $recordedStartStr
        SessionId      = $expectedSessionId
        MountPoint     = $mountPoint
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        Message        = "Process with PID $($targetPid) is no longer active. Cleaned up state file."
        StateFile      = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# ================= STRICT PROCESS IDENTITY VERIFICATION (FAIL CLOSED) =================

# Verification 1: Process Name match against active OS process
if ($proc.ProcessName -ine "rclone" -or ($expectedName -and $proc.ProcessName -ine $expectedName)) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "PID_REUSE_REJECTED"
        IdentityStatus     = "IDENTITY_MISMATCH"
        PID                = $targetPid
        ActualName         = $proc.ProcessName
        ExpectedName       = $expectedName
        ActualPath         = $null
        ExpectedPath       = $expectedPath
        ActualStartTime    = $proc.StartTime.ToString("o")
        ExpectedStartTime  = $recordedStartStr
        ActualSessionId    = $proc.SessionId
        ExpectedSessionId  = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "ProcessNameMismatch"
        Message            = "Refusing to kill PID $($targetPid): active process name is '$($proc.ProcessName)', which does not match expected process '$expectedName'. PID reuse detected. Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Mandatory Schema Field Check 1: processName
if (-not $expectedName -or [string]::IsNullOrWhiteSpace($expectedName)) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $targetPid
        ProcessName        = $null
        ExecutablePath     = $expectedPath
        StartTime          = $recordedStartStr
        SessionId          = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "MissingProcessNameInState"
        Message            = "State file is missing required 'processName' field. Fail closed: preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

if ($expectedName -ine "rclone") {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "PID_REUSE_REJECTED"
        IdentityStatus     = "IDENTITY_MISMATCH"
        PID                = $targetPid
        ProcessName        = $expectedName
        ExecutablePath     = $expectedPath
        StartTime          = $recordedStartStr
        SessionId          = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "ProcessNameMismatch"
        Message            = "State file processName '$expectedName' does not equal required 'rclone'. Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Mandatory Schema Field Check 2: executablePath
if (-not $expectedPath -or [string]::IsNullOrWhiteSpace($expectedPath)) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $targetPid
        ProcessName        = $proc.ProcessName
        ExecutablePath     = $null
        StartTime          = $recordedStartStr
        SessionId          = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "MissingExecutablePathInState"
        Message            = "State file is missing required 'executablePath' field. Fail closed: refusing to stop process $($targetPid). Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Verification 2: Executable Path match (Normalized full path, case-insensitive)
$procPath = $null
try {
    if ($proc.Path) {
        $procPath = $proc.Path
    }
} catch {}

if (-not $procPath) {
    try {
        if ($proc.MainModule -and $proc.MainModule.FileName) {
            $procPath = $proc.MainModule.FileName
        }
    } catch {}
}

if (-not $procPath) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $targetPid
        ActualName         = $proc.ProcessName
        ExpectedName       = $expectedName
        ActualPath         = $null
        ExpectedPath       = $expectedPath
        ActualStartTime    = $proc.StartTime.ToString("o")
        ExpectedStartTime  = $recordedStartStr
        ActualSessionId    = $proc.SessionId
        ExpectedSessionId  = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "CannotReadProcessPath"
        Message            = "Refusing to kill PID $($targetPid): unable to read process executable path from OS. Fail closed: preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

$normProcPath = ""
$normExpectedPath = ""
try {
    $normProcPath = [System.IO.Path]::GetFullPath($procPath).TrimEnd('\')
    $normExpectedPath = [System.IO.Path]::GetFullPath($expectedPath).TrimEnd('\')
} catch {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $targetPid
        ActualPath         = $procPath
        ExpectedPath       = $expectedPath
        VerificationReason = "PathNormalizationFailed"
        Message            = "Path normalization failed for PID $($targetPid) ($($_.Exception.Message)). Fail closed: preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

if (-not [string]::Equals($normProcPath, $normExpectedPath, [System.StringComparison]::OrdinalIgnoreCase)) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "IDENTITY_MISMATCH"
        IdentityStatus     = "IDENTITY_MISMATCH"
        PID                = $targetPid
        ActualName         = $proc.ProcessName
        ExpectedName       = $expectedName
        ActualPath         = $procPath
        ExpectedPath       = $expectedPath
        ActualStartTime    = $proc.StartTime.ToString("o")
        ExpectedStartTime  = $recordedStartStr
        ActualSessionId    = $proc.SessionId
        ExpectedSessionId  = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "ExecutablePathMismatch"
        Message            = "Refusing to kill PID $($targetPid): process path '$procPath' does not match recorded executablePath '$expectedPath'. Identity verification failed. Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Mandatory Schema Field Check 3: startTime
$parsedExpectedStart = $null
if ($recordedStartStr -and -not [string]::IsNullOrWhiteSpace($recordedStartStr)) {
    try {
        $parsedExpectedStart = [DateTimeOffset]::Parse($recordedStartStr)
    } catch {
        $parsedExpectedStart = $null
    }
}
if (-not $parsedExpectedStart) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $targetPid
        ProcessName        = $proc.ProcessName
        ExecutablePath     = $expectedPath
        StartTime          = $null
        SessionId          = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "MissingStartTimeInState"
        Message            = "State file is missing or contains invalid 'startTime' field. Fail closed: refusing to stop process $($targetPid). Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Verification 3: Process StartTime match (Strict <500ms window)
$startTimeMatch = $false
$diffMs = $null
try {
    $actualStart = [DateTimeOffset]::new($proc.StartTime)
    $diffMs = [math]::Abs(($actualStart - $parsedExpectedStart).TotalMilliseconds)
    if ($diffMs -lt 500) {
        $startTimeMatch = $true
    }
} catch {
    $startTimeMatch = $false
}

if (-not $startTimeMatch) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "IDENTITY_MISMATCH"
        IdentityStatus     = "IDENTITY_MISMATCH"
        PID                = $targetPid
        ActualName         = $proc.ProcessName
        ExpectedName       = $expectedName
        ActualPath         = $procPath
        ExpectedPath       = $expectedPath
        ActualStartTime    = $proc.StartTime.ToString("o")
        ExpectedStartTime  = $recordedStartStr
        TimeDeltaMs        = $diffMs
        ActualSessionId    = $proc.SessionId
        ExpectedSessionId  = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "StartTimeMismatch"
        Message            = "Refusing to kill PID $($targetPid): process start time ($($proc.StartTime.ToString('o'))) does not match recorded state ($recordedStartStr, delta: $diffMs ms >= 500ms). Identity verification failed. Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Mandatory Schema Field Check 4: sessionId
if ($expectedSessionId -eq $null) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $targetPid
        ProcessName        = $proc.ProcessName
        ExecutablePath     = $expectedPath
        StartTime          = $recordedStartStr
        SessionId          = $null
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "MissingSessionIdInState"
        Message            = "State file is missing required 'sessionId' field. Fail closed: refusing to stop process $($targetPid). Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Verification 4: Session ID match
if ($proc.SessionId -ne $expectedSessionId) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "IDENTITY_MISMATCH"
        IdentityStatus     = "IDENTITY_MISMATCH"
        PID                = $targetPid
        ActualName         = $proc.ProcessName
        ExpectedName       = $expectedName
        ActualPath         = $procPath
        ExpectedPath       = $expectedPath
        ActualStartTime    = $proc.StartTime.ToString("o")
        ExpectedStartTime  = $recordedStartStr
        ActualSessionId    = $proc.SessionId
        ExpectedSessionId  = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "SessionIdMismatch"
        Message            = "Refusing to kill PID $($targetPid): process SessionId ($($proc.SessionId)) does not match recorded sessionId ($expectedSessionId). Identity verification failed. Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Mandatory Schema Field Check 5: mountPoint
if (-not $mountPoint -or [string]::IsNullOrWhiteSpace($mountPoint)) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $targetPid
        ProcessName        = $proc.ProcessName
        ExecutablePath     = $expectedPath
        StartTime          = $recordedStartStr
        SessionId          = $expectedSessionId
        MountPoint         = $null
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "MissingMountPointInState"
        Message            = "State file is missing required 'mountPoint' field. Fail closed: refusing to stop process $($targetPid). Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Mandatory Schema Field Check 6: remoteTarget
if (-not $remoteTarget -or [string]::IsNullOrWhiteSpace($remoteTarget)) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $targetPid
        ProcessName        = $proc.ProcessName
        ExecutablePath     = $expectedPath
        StartTime          = $recordedStartStr
        SessionId          = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $null
        Arguments          = $arguments
        StateStatus        = $stateStatus
        VerificationReason = "MissingRemoteTargetInState"
        Message            = "State file is missing required 'remoteTarget' field. Fail closed: refusing to stop process $($targetPid). Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Mandatory Schema Field Check 7: arguments
$hasArgs = $false
if ($arguments -ne $null) {
    if ($arguments -is [string] -and -not [string]::IsNullOrWhiteSpace($arguments)) {
        $hasArgs = $true
    } elseif ($arguments -is [System.Collections.IEnumerable] -and -not ($arguments -is [string]) -and @($arguments).Count -gt 0) {
        $hasArgs = $true
    }
}
if (-not $hasArgs) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $targetPid
        ProcessName        = $proc.ProcessName
        ExecutablePath     = $expectedPath
        StartTime          = $recordedStartStr
        SessionId          = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $null
        StateStatus        = $stateStatus
        VerificationReason = "MissingArgumentsInState"
        Message            = "State file is missing required 'arguments' field. Fail closed: refusing to stop process $($targetPid). Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# Mandatory Schema Field Check 8: status
if (-not $stateStatus -or [string]::IsNullOrWhiteSpace($stateStatus)) {
    $res = [PSCustomObject]@{
        Success            = $false
        Status             = "VERIFICATION_FAILED"
        IdentityStatus     = "VERIFICATION_FAILED"
        PID                = $targetPid
        ProcessName        = $proc.ProcessName
        ExecutablePath     = $expectedPath
        StartTime          = $recordedStartStr
        SessionId          = $expectedSessionId
        MountPoint         = $mountPoint
        RemoteTarget       = $remoteTarget
        Arguments          = $arguments
        StateStatus        = $null
        VerificationReason = "MissingStatusInState"
        Message            = "State file is missing required 'status' field. Fail closed: refusing to stop process $($targetPid). Preserving state file."
        StateFile          = $StateFile
    }
    if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
    return
}

# ================= TERMINATION OF STRICTLY VERIFIED PROCESS =================
try {
    Stop-Process -Id $targetPid -Force:$Force -ErrorAction Stop

    # Wait up to 5 seconds for verified process termination
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
            Success        = $true
            Status         = "STOPPED"
            PID            = $targetPid
            ProcessName    = $proc.ProcessName
            ExecutablePath = $expectedPath
            StartTime      = $recordedStartStr
            SessionId      = $proc.SessionId
            MountPoint     = $mountPoint
            RemoteTarget   = $remoteTarget
            Arguments      = $arguments
            StateStatus    = $stateStatus
            Message        = "Successfully stopped verified rclone mount process (PID $($targetPid))."
            StateFile      = $StateFile
        }
    } else {
        $res = [PSCustomObject]@{
            Success        = $false
            Status         = "STOP_TIMEOUT"
            PID            = $targetPid
            ProcessName    = $proc.ProcessName
            ExecutablePath = $expectedPath
            StartTime      = $recordedStartStr
            SessionId      = $proc.SessionId
            MountPoint     = $mountPoint
            RemoteTarget   = $remoteTarget
            Arguments      = $arguments
            StateStatus    = $stateStatus
            Message        = "Process (PID $($targetPid)) was signaled to stop, but was still running after 5 seconds."
            StateFile      = $StateFile
        }
    }
} catch {
    $res = [PSCustomObject]@{
        Success        = $false
        Status         = "STOP_ERROR"
        PID            = $targetPid
        ProcessName    = $proc.ProcessName
        ExecutablePath = $expectedPath
        StartTime      = $recordedStartStr
        SessionId      = $proc.SessionId
        MountPoint     = $mountPoint
        RemoteTarget   = $remoteTarget
        Arguments      = $arguments
        StateStatus    = $stateStatus
        Message        = "Failed to stop process (PID $($targetPid)): $($_.Exception.Message)"
        StateFile      = $StateFile
    }
}

if ($AsJson) { $res | ConvertTo-Json -Depth 5 } else { $res }
