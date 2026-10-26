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
    [string]$DriveRootFolderId,

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

    [Parameter(Mandatory = $false)]
    [int]$ReadinessTimeoutSeconds = $(if ($env:DRIVE_MOUNT_READINESS_TIMEOUT) { [int]$env:DRIVE_MOUNT_READINESS_TIMEOUT } else { 15 }),

    [Parameter(Mandatory = $false)]
    [int]$ReadinessIntervalMs = 250,

    [switch]$WhatIf,
    [switch]$Execute,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Format-NativeArgument {
    param([string]$Arg)
    if ([string]::IsNullOrEmpty($Arg)) { return '""' }
    if ($Arg -notmatch '[\s"\t\v\n]') { return $Arg }
    $escaped = [regex]::Replace($Arg, '(\\*)(")', { param($m) ($m.Groups[1].Value * 2) + '\"' })
    $escaped = [regex]::Replace($escaped, '(\\+)$', { param($m) ($m.Groups[1].Value * 2) })
    return '"' + $escaped + '"'
}

function Test-MountReadiness {
    param(
        [string]$Target
    )

    if ([string]::IsNullOrWhiteSpace($Target)) {
        return $false
    }

    try {
        if ($Target -match "^[A-Za-z]:?\\?$") {
            # Drive letter target (e.g. "M:" or "M:\")
            $letter = $Target.Substring(0, 1).ToUpper()
            $driveRoot = "$($letter):\"

            $drives = [System.IO.DriveInfo]::GetDrives()
            $matched = $drives | Where-Object { $_.Name.StartsWith($driveRoot, [System.StringComparison]::OrdinalIgnoreCase) }
            if (-not $matched -or -not $matched.IsReady) {
                return $false
            }

            if (-not (Test-Path -LiteralPath $driveRoot -ErrorAction SilentlyContinue)) {
                return $false
            }

            $null = [System.IO.Directory]::GetFileSystemEntries($driveRoot)
            return $true
        } else {
            # Directory target path
            if (-not (Test-Path -LiteralPath $Target -PathType Container -ErrorAction SilentlyContinue)) {
                return $false
            }

            # WinFsp directory mounts on Windows are NTFS reparse points
            $item = Get-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
            if (-not $item -or -not ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
                return $false
            }

            $null = [System.IO.Directory]::GetFileSystemEntries($Target)
            return $true
        }
    } catch {
        return $false
    }
}

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

if ($DriveRootFolderId -and ($RemoteSubpath -eq "DippieMedia") -and (-not $PSBoundParameters.ContainsKey('RemoteSubpath'))) {
    $RemoteSubpath = ""
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

    $rawArgPreview = @("mount")
    if ($DriveRootFolderId) {
        $rawArgPreview += @("--drive-root-folder-id", $DriveRootFolderId)
    }
    $rawArgPreview += @($remoteTarget, $MountPoint) + $baselineFlags
    if ($ConfigPath) {
        $rawArgPreview += @("--config", $ConfigPath)
    }
    if ($LogFile) {
        $rawArgPreview += @("--log-file", $LogFile, "--log-level", "INFO")
    }

    $formattedArgPreview = @($rawArgPreview | ForEach-Object { Format-NativeArgument $_ })
    $expectedCommand = "$rcloneCmd " + ($formattedArgPreview -join " ")

    $plan = [PSCustomObject]@{
        Timestamp           = [DateTime]::UtcNow.ToString("o")
        Mode                = "DRY_RUN"
        IsExecute           = $false
        Remote              = $effectiveRemote
        RemoteSubpath       = $RemoteSubpath
        DriveRootFolderId   = $DriveRootFolderId
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
                $startTimeMatch = $true
                if ($existingState.PSObject.Properties['startTime'] -and $existingState.startTime) {
                    try {
                        $expectedStart = [DateTimeOffset]::Parse([string]$existingState.startTime)
                        $actualStart = [DateTimeOffset]::new($existingProc.StartTime)
                        $diffMs = [math]::Abs(($actualStart - $expectedStart).TotalMilliseconds)
                        if (-not (($actualStart -eq $expectedStart) -or ($diffMs -lt 1.0))) {
                            $startTimeMatch = $false
                        }
                    } catch {
                        $startTimeMatch = $false
                    }
                }

                # Verify live invocation / command line
                $cmdMatch = $true
                $existingCmd = $null
                if ($existingProc.PSObject.Properties['CommandLine'] -and $existingProc.CommandLine) {
                    $existingCmd = [string]$existingProc.CommandLine
                }
                if (-not $existingCmd) {
                    try {
                        $cimExisting = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $($existingState.pid)" -ErrorAction SilentlyContinue
                        if ($cimExisting -and $cimExisting.CommandLine) {
                            $existingCmd = [string]$cimExisting.CommandLine
                        }
                    } catch {}
                }
                if ($existingCmd) {
                    if ($existingState.PSObject.Properties['remoteTarget'] -and $existingState.remoteTarget) {
                        if ($existingCmd.IndexOf([string]$existingState.remoteTarget, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
                            $cmdMatch = $false
                        }
                    }
                    if ($existingState.PSObject.Properties['mountPoint'] -and $existingState.mountPoint) {
                        $cleanExistingMount = ([string]$existingState.mountPoint).TrimEnd('\')
                        if ($existingCmd.IndexOf($cleanExistingMount, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
                            $cmdMatch = $false
                        }
                    }
                }

                if ($startTimeMatch -and $cmdMatch) {
                    throw "A previous rclone mount process (PID $($existingState.pid)) is currently running for mount point '$($existingState.mountPoint)'. Use stop_drive.ps1 before remounting."
                }
            }
        }
    } catch [System.Management.Automation.ItemNotFoundException] {
        # File disappeared, proceed
    }
}

# 3. Assemble arguments for rclone mount
$rawMountArgs = @(
    "mount"
)
if ($DriveRootFolderId) {
    $rawMountArgs += @("--drive-root-folder-id", $DriveRootFolderId)
}
$rawMountArgs += @(
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
    $rawMountArgs += @("--config", $ConfigPath)
}
if ($LogFile) {
    $rawMountArgs += @("--log-file", $LogFile, "--log-level", "INFO")
}

$formattedMountArgs = @($rawMountArgs | ForEach-Object { Format-NativeArgument $_ })

# 4. Launch hidden background rclone process
$stateDir = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($StateFile))
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
# Detached mounts must not inherit the launcher's stdout/stderr pipes.
$proc = Start-Process -FilePath $rcloneExe -ArgumentList $formattedMountArgs -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput ($StateFile + ".stdout.log") -RedirectStandardError ($StateFile + ".stderr.log")

if (-not $proc) {
    throw "Failed to start rclone process."
}

# 5. Save process state to JSON immediately with STARTING status
$currentProc = Get-Process -Id $PID
$startTimeIso = try { $proc.StartTime.ToString("o") } catch { [DateTime]::UtcNow.ToString("o") }
$procName = try { $proc.ProcessName } catch { "rclone" }
if (-not $procName) { $procName = "rclone" }

$stateRecord = [PSCustomObject]@{
    pid               = $proc.Id
    processName       = $procName
    startTime         = $startTimeIso
    executablePath    = $rcloneExe
    mountPoint        = $MountPoint
    remoteTarget      = $remoteTarget
    driveRootFolderId = $DriveRootFolderId
    arguments         = $rawMountArgs
    flags          = $baselineFlags
    commandLine    = "$rcloneExe " + ($formattedMountArgs -join " ")
    stateFile      = $StateFile
    logFile        = $LogFile
    sessionId      = $currentProc.SessionId
    user           = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    createdAt      = [DateTime]::UtcNow.ToString("o")
    status         = "STARTING"
}

$stateDir = [System.IO.Path]::GetDirectoryName($StateFile)
if ($stateDir -and -not (Test-Path -LiteralPath $stateDir -PathType Container)) {
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
}
$stateRecord | ConvertTo-Json -Depth 6 | Set-Content -Path $StateFile -Encoding UTF8

# 6. Bounded readiness verification loop
$isReady = $false
$elapsedMs = 0
$timeoutMs = $ReadinessTimeoutSeconds * 1000

while ($elapsedMs -lt $timeoutMs) {
    # Check if process exited early
    $hasExited = $false
    try {
        $hasExited = $proc.HasExited
    } catch {
        $liveProc = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
        $hasExited = ($liveProc -eq $null -or $liveProc.HasExited)
    }

    if ($hasExited) {
        $exitCode = try { $proc.ExitCode } catch { -1 }
        $stateRecord.status = "FAILED"
        $stateRecord | ConvertTo-Json -Depth 6 | Set-Content -Path $StateFile -Encoding UTF8

        $result = [PSCustomObject]@{
            Success      = $false
            Status       = "FAILED"
            PID          = $proc.Id
            ExitCode     = $exitCode
            MountPoint   = $MountPoint
            RemoteTarget = $remoteTarget
            StateFile    = $StateFile
            Message      = "Rclone mount process exited prematurely with exit code $exitCode."
        }

        if ($AsJson) {
            $result | ConvertTo-Json -Depth 5
        } else {
            $result
        }
        return
    }

    if (Test-MountReadiness -Target $MountPoint) {
        $isReady = $true
        break
    }

    Start-Sleep -Milliseconds $ReadinessIntervalMs
    $elapsedMs += $ReadinessIntervalMs
}

# 7. Evaluate readiness outcome
if (-not $isReady) {
    # Timeout reached without mount becoming readable. Clean up only strictly verified owned child process.
    $liveProc = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if ($liveProc -and -not $liveProc.HasExited) {
        $isOwned = $false
        try {
            # 1. Process Name match
            $nameMatches = ($liveProc.ProcessName -ieq "rclone") -and ($liveProc.ProcessName -ieq $procName)

            # 2. Executable Path match
            $liveProcPath = $null
            try {
                if ($liveProc.Path) { $liveProcPath = $liveProc.Path }
            } catch {}
            if (-not $liveProcPath) {
                try {
                    if ($liveProc.MainModule -and $liveProc.MainModule.FileName) { $liveProcPath = $liveProc.MainModule.FileName }
                } catch {}
            }
            $pathMatches = $false
            if ($liveProcPath -and $rcloneExe) {
                $normLivePath = [System.IO.Path]::GetFullPath($liveProcPath).TrimEnd('\')
                $normExpectedPath = [System.IO.Path]::GetFullPath($rcloneExe).TrimEnd('\')
                $pathMatches = [string]::Equals($normLivePath, $normExpectedPath, [System.StringComparison]::OrdinalIgnoreCase)
            }

            # 3. StartTime match (Exact process creation identity, preserved precision, <1ms delta)
            $startMatches = $false
            try {
                $expectedStart = [DateTimeOffset]::Parse($startTimeIso)
                $actualStart = [DateTimeOffset]::new($liveProc.StartTime)
                $diffMs = [math]::Abs(($actualStart - $expectedStart).TotalMilliseconds)
                if (($actualStart -eq $expectedStart) -or ($diffMs -lt 1.0)) {
                    $startMatches = $true
                }
            } catch {}

            # 4. SessionId match
            $sessionMatches = ($liveProc.SessionId -eq $currentProc.SessionId)

            # 5. Live Process Invocation & Command Line Verification
            $cmdMatches = $false
            $liveCmd = $null
            if ($liveProc.PSObject.Properties['CommandLine'] -and $liveProc.CommandLine) {
                $liveCmd = [string]$liveProc.CommandLine
            }
            if (-not $liveCmd) {
                try {
                    $cimProc = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue
                    if ($cimProc -and $cimProc.CommandLine) {
                        $liveCmd = [string]$cimProc.CommandLine
                    }
                } catch {}
            }
            if (-not $liveCmd) {
                try {
                    $wmiProc = Get-WmiObject -Class Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue
                    if ($wmiProc -and $wmiProc.CommandLine) {
                        $liveCmd = [string]$wmiProc.CommandLine
                    }
                } catch {}
            }

            if ($liveCmd -and -not [string]::IsNullOrWhiteSpace($liveCmd)) {
                $cleanMount = $MountPoint.TrimEnd('\')
                $hasMount = ($liveCmd -match '\bmount\b')
                $hasRemote = ($liveCmd.IndexOf($remoteTarget, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
                $hasTarget = (($liveCmd.IndexOf($cleanMount, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) -or ($liveCmd.IndexOf($MountPoint, [System.StringComparison]::OrdinalIgnoreCase) -ge 0))
                if ($hasMount -and $hasRemote -and $hasTarget) {
                    $cmdMatches = $true
                }
            }

            if ($nameMatches -and $pathMatches -and $startMatches -and $sessionMatches -and $cmdMatches) {
                $isOwned = $true
            }
        } catch {}

        if ($isOwned) {
            # Re-verify process identity immediately before termination signal to prevent PID reuse race
            $preCheck = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
            if ($preCheck) {
                try {
                    $preActual = [DateTimeOffset]::new($preCheck.StartTime)
                    $expectedStart = [DateTimeOffset]::Parse($startTimeIso)
                    if (($preActual -eq $expectedStart) -or ([math]::Abs(($preActual - $expectedStart).TotalMilliseconds) -lt 1.0)) {
                        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                    }
                } catch {}
            }
        }
    }

    $stateRecord.status = "TIMEOUT"
    $stateRecord | ConvertTo-Json -Depth 6 | Set-Content -Path $StateFile -Encoding UTF8

    $result = [PSCustomObject]@{
        Success      = $false
        Status       = "TIMEOUT"
        PID          = $proc.Id
        MountPoint   = $MountPoint
        RemoteTarget = $remoteTarget
        StateFile    = $StateFile
        Message      = "Rclone mount timed out after $($ReadinessTimeoutSeconds)s waiting for mount point '$MountPoint' to become ready and readable."
    }

    if ($AsJson) {
        $result | ConvertTo-Json -Depth 5
    } else {
        $result
    }
    return
}

# 8. Succeeded and verified ready
$stateRecord.status = "MOUNTED"
$stateRecord | ConvertTo-Json -Depth 6 | Set-Content -Path $StateFile -Encoding UTF8

$result = [PSCustomObject]@{
    Success      = $true
    Status       = "MOUNTED"
    PID          = $proc.Id
    MountPoint   = $MountPoint
    RemoteTarget = $remoteTarget
    StateFile    = $StateFile
    Message      = "Rclone mount started successfully in background with PID $($proc.Id) and verified ready."
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 5
} else {
    $result
}
