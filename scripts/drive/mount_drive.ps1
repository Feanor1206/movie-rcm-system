<#
.SYNOPSIS
    Mounts a Google Drive remote on Windows using rclone and WinFsp.
.DESCRIPTION
    Implements safe baseline Google Drive mounting on Windows.
    Default mode is dry-run (-WhatIf or omitting -Execute) to plan and validate flags.
    Enforces baseline streaming flags: read-only, cache-off, 32M buffer, 8M initial chunk.
    When -Execute is passed, runs preflight verification first and persists PID & process state to JSON.
.PARAMETER Remote
    The rclone remote name (e.g. "cinema-gdrive:" or "gdrive").
.PARAMETER RemoteSubpath
    Subpath on the remote. Default is "DippieMedia".
.PARAMETER MountPoint
    Windows mount target (drive letter like "M:" or empty NTFS directory). Default is "M:".
.PARAMETER ConfigPath
    Optional explicit path to rclone.conf.
.PARAMETER RclonePath
    Optional explicit path to rclone executable.
.PARAMETER StateFile
    Path to save runtime process state JSON. Defaults to $env:TEMP\movie-rcm-drive-mount.json.
.PARAMETER LogFile
    Optional log file path for rclone logging.
.PARAMETER WhatIf
    Explicitly request a dry-run plan without mounting.
.PARAMETER Execute
    Execute the mount process in background.
.PARAMETER AsJson
    Output plan / result strictly as JSON string.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Remote,

    [Parameter(Mandatory = $false)]
    [string]$RemoteSubpath = "DippieMedia",

    [Parameter(Mandatory = $false)]
    [string]$MountPoint = "M:",

    [Parameter(Mandatory = $false)]
    [string]$ConfigPath,

    [Parameter(Mandatory = $false)]
    [string]$RclonePath,

    [Parameter(Mandatory = $false)]
    [string]$StateFile,

    [Parameter(Mandatory = $false)]
    [string]$LogFile,

    [switch]$WhatIf,
    [switch]$Execute,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Resolve state file location
if (-not $StateFile) {
    $tempDir = if ($env:TEMP) { $env:TEMP } else { [System.IO.Path]::GetTempPath() }
    $StateFile = Join-Path $tempDir "movie-rcm-drive-mount.json"
}

# Resolve remote target path
$effectiveRemote = $Remote
if (-not $effectiveRemote) {
    # Default placeholder for preview / dry-run mode
    $effectiveRemote = "cinema-gdrive:"
}

$remoteTarget = ""
if ($effectiveRemote.EndsWith(":")) {
    if ($RemoteSubpath) {
        $remoteTarget = "$($effectiveRemote)$($RemoteSubpath)"
    } else {
        $remoteTarget = $effectiveRemote
    }
} else {
    if ($RemoteSubpath) {
        $remoteTarget = "$($effectiveRemote):$($RemoteSubpath)"
    } else {
        $remoteTarget = "$($effectiveRemote):"
    }
}

# Baseline streaming flags (RFC 9110 HTTP Range compliant, RAM buffer 32M, cache-off)
$baselineFlags = @(
    "--read-only",
    "--vfs-cache-mode", "off",
    "--buffer-size", "32M",
    "--vfs-read-chunk-size", "8M",
    "--vfs-read-chunk-size-limit", "32M",
    "--vfs-read-chunk-streams", "0",
    "--dir-cache-time", "72h",
    "--poll-interval", "15s",
    "--attr-timeout", "1s"
)

# Baseline flags string representation
$baselineFlagsString = "--read-only --vfs-cache-mode off --buffer-size 32M --vfs-read-chunk-size 8M --vfs-read-chunk-size-limit 32M --vfs-read-chunk-streams 0 --dir-cache-time 72h --poll-interval 15s --attr-timeout 1s"

# Locate preflight script
$preflightScript = Join-Path $PSScriptRoot "preflight_drive.ps1"
if (-not (Test-Path -Path $preflightScript -PathType Leaf -ErrorAction SilentlyContinue)) {
    throw "Preflight script not found at expected path: $preflightScript"
}

# Determine execution mode (Dry-run by default unless -Execute is specified AND -WhatIf is not)
$isDryRun = (-not $Execute) -or $WhatIf

if ($isDryRun) {
    # Perform preflight evaluation in dry-run mode
    $preflightJsonRaw = & $preflightScript -MountPoint $MountPoint -RclonePath $RclonePath -ConfigPath $ConfigPath
    $preflightObj = $null
    try {
        $preflightObj = $preflightJsonRaw | ConvertFrom-Json
    } catch {
        # Fallback if json parse fails
    }

    $rcloneCmd = "rclone"
    if ($preflightObj -and $preflightObj.Rclone -and $preflightObj.Rclone.ExecutablePath) {
        $rcloneCmd = $preflightObj.Rclone.ExecutablePath
    } elseif ($RclonePath) {
        $rcloneCmd = $RclonePath
    }

    $argPreview = @("mount", $remoteTarget, $MountPoint) + $baselineFlags
    if ($ConfigPath) {
        $argPreview += @("--config", $ConfigPath)
    }
    if ($LogFile) {
        $argPreview += @("--log-file", $LogFile, "--log-level", "INFO")
    }

    $expectedCommand = "$rcloneCmd " + ($argPreview -join " ")

    $plan = [PSCustomObject]@{
        Timestamp           = [DateTime]::UtcNow.ToString("o")
        Mode                = "DRY_RUN"
        IsExecute           = $false
        Remote              = $effectiveRemote
        RemoteSubpath       = $RemoteSubpath
        RemoteTarget        = $remoteTarget
        MountPoint          = $MountPoint
        BaselineFlags       = $baselineFlags
        BaselineFlagsString = $baselineFlagsString
        ExpectedCommand     = $expectedCommand
        StateFile           = $StateFile
        PreflightIsReady    = if ($preflightObj) { [bool]$preflightObj.IsReady } else { $false }
        PreflightStatus     = if ($preflightObj) { [string]$preflightObj.Status } else { "UNKNOWN" }
        PreflightBlockers   = if ($preflightObj) { $preflightObj.BlockReasons } else { @() }
        ConfigProvided      = [bool]$ConfigPath
        LogFile             = $LogFile
        Guidance            = "Dry-run plan created. To mount Google Drive, install prerequisites if needed and invoke with '-Execute'."
    }

    if ($AsJson) {
        $plan | ConvertTo-Json -Depth 6
    } else {
        # Return structured object to pipeline
        $plan
    }
    return
}

# ================= EXECUTION MODE (-Execute) =================

if (-not $Remote) {
    throw "Parameter -Remote is required when running with -Execute. Example: -Remote 'cinema-gdrive:'"
}

# 1. Run Preflight verification
$preflightJsonRaw = & $preflightScript -MountPoint $MountPoint -RclonePath $RclonePath -ConfigPath $ConfigPath
$preflightObj = $preflightJsonRaw | ConvertFrom-Json

if (-not $preflightObj.IsReady) {
    $blockers = ($preflightObj.BlockReasons -join "; ")
    throw "Preflight verification failed. Drive cannot be mounted: $blockers"
}

$rcloneExe = $preflightObj.Rclone.ExecutablePath
if (-not $rcloneExe) {
    throw "Rclone executable not resolved by preflight check."
}

# 2. Check existing state file for running mount
if (Test-Path -Path $StateFile -PathType Leaf -ErrorAction SilentlyContinue) {
    try {
        $existingState = Get-Content -Path $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($existingState -and $existingState.pid) {
            $existingProc = Get-Process -Id $existingState.pid -ErrorAction SilentlyContinue
            if ($existingProc -and ($existingProc.ProcessName -ieq "rclone")) {
                throw "A previous rclone mount process (PID $($existingState.pid)) is currently running for mount point '$($existingState.mountPoint)'. Use stop_drive.ps1 before remounting."
            }
        }
    } catch [System.Management.Automation.ItemNotFoundException] {
        # File disappeared, proceed
    }
}

# 3. Assemble arguments for rclone mount
$mountArgs = @(
    "mount",
    $remoteTarget,
    $MountPoint,
    "--read-only",
    "--vfs-cache-mode", "off",
    "--buffer-size", "32M",
    "--vfs-read-chunk-size", "8M",
    "--vfs-read-chunk-size-limit", "32M",
    "--vfs-read-chunk-streams", "0",
    "--dir-cache-time", "72h",
    "--poll-interval", "15s",
    "--attr-timeout", "1s"
)

if ($ConfigPath) {
    $mountArgs += @("--config", $ConfigPath)
}
if ($LogFile) {
    $mountArgs += @("--log-file", $LogFile, "--log-level", "INFO")
}

# 4. Launch hidden background rclone process
$proc = Start-Process -FilePath $rcloneExe -ArgumentList $mountArgs -WindowStyle Hidden -PassThru

if (-not $proc) {
    throw "Failed to start rclone process."
}

# Short stabilization check (1 second) to detect immediate startup crash
Start-Sleep -Seconds 1
if ($proc.HasExited) {
    throw "Rclone process exited immediately with exit code $($proc.ExitCode). Check config and logs for details."
}

# 5. Save process state to JSON
$currentProc = Get-Process -Id $PID
$stateRecord = [PSCustomObject]@{
    pid            = $proc.Id
    processName    = $proc.ProcessName
    startTime      = $proc.StartTime.ToString("o")
    executablePath = $rcloneExe
    mountPoint     = $MountPoint
    remoteTarget   = $remoteTarget
    flags          = $baselineFlags
    commandLine    = "$rcloneExe " + ($mountArgs -join " ")
    stateFile      = $StateFile
    logFile        = $LogFile
    sessionId      = $currentProc.SessionId
    user           = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    createdAt      = [DateTime]::UtcNow.ToString("o")
    status         = "RUNNING"
}

$stateRecord | ConvertTo-Json -Depth 6 | Set-Content -Path $StateFile -Encoding UTF8

$result = [PSCustomObject]@{
    Success      = $true
    Status       = "MOUNTED"
    PID          = $proc.Id
    MountPoint   = $MountPoint
    RemoteTarget = $remoteTarget
    StateFile    = $StateFile
    Message      = "Rclone mount started successfully in background with PID $($proc.Id)."
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 5
} else {
    $result
}
