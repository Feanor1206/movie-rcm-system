<#
.SYNOPSIS
    Preflight verification for Google Drive mount tooling on Windows.
.DESCRIPTION
    Inspects host OS, rclone executable, WinFsp installation, mount target collision,
    user session isolation, RAM and disk capacity.
    Outputs structured JSON. Does NOT log or leak config secrets or tokens.
.PARAMETER MountPoint
    Target drive letter (e.g. "M:") or NTFS directory path. Default is "M:".
.PARAMETER RclonePath
    Optional explicit path to rclone.exe. If omitted, PATH and common install locations are checked.
.PARAMETER ConfigPath
    Optional explicit path to rclone.conf. Validates file existence and size without dumping contents.
.OUTPUTS
    Structured JSON object containing health and readiness assessment.
#>
[CmdletBinding()]
param(
    [string]$MountPoint = "M:",
    [string]$RclonePath,
    [string]$ConfigPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-WinFspInstalled {
    $result = [PSCustomObject]@{
        Installed      = $false
        RegistryFound  = $false
        RegistryPath   = $null
        InstallDir     = $null
        Version        = $null
        DllFound       = $false
        DllPaths       = @()
        DriverLoaded   = $false
        DetectionNotes = @()
    }

    # 1. Registry verification
    $regCandidates = @(
        "HKLM:\SOFTWARE\WinFsp",
        "HKLM:\SOFTWARE\WOW6432Node\WinFsp"
    )
    foreach ($regPath in $regCandidates) {
        if (Test-Path -Path $regPath -ErrorAction SilentlyContinue) {
            $result.RegistryFound = $true
            $result.RegistryPath = $regPath
            try {
                $item = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
                if ($item) {
                    if ($item.InstallDir) { $result.InstallDir = [string]$item.InstallDir }
                    if ($item.Version) { $result.Version = [string]$item.Version }
                }
            } catch {
                # Ignore read error
            }
            $result.DetectionNotes += "Registry key verified at $regPath"
            break
        }
    }

    # 2. File and DLL verification (System32 & Program Files)
    $dllCandidates = @()
    if ($env:SystemRoot) {
        $dllCandidates += (Join-Path $env:SystemRoot "System32\winfsp-x64.dll")
        $dllCandidates += (Join-Path $env:SystemRoot "System32\winfsp-x86.dll")
        $dllCandidates += (Join-Path $env:SystemRoot "System32\winfsp-a64.dll")
    }
    if ($env:ProgramFiles) {
        $dllCandidates += (Join-Path $env:ProgramFiles "WinFsp\bin\winfsp-x64.dll")
        $dllCandidates += (Join-Path $env:ProgramFiles "WinFsp\bin\winfsp-a64.dll")
    }
    $programFilesX86 = ${env:ProgramFiles(x86)}
    if ($programFilesX86) {
        $dllCandidates += (Join-Path $programFilesX86 "WinFsp\bin\winfsp-x86.dll")
    }
    if ($result.InstallDir) {
        $dllCandidates += (Join-Path $result.InstallDir "bin\winfsp-x64.dll")
        $dllCandidates += (Join-Path $result.InstallDir "bin\winfsp-x86.dll")
    }

    $foundDlls = @()
    foreach ($dll in ($dllCandidates | Select-Object -Unique)) {
        if ($dll -and (Test-Path -Path $dll -PathType Leaf -ErrorAction SilentlyContinue)) {
            $foundDlls += $dll
        }
    }
    if ($foundDlls.Count -gt 0) {
        $result.DllFound = $true
        $result.DllPaths = $foundDlls
        $result.DetectionNotes += "WinFsp DLL verified: $($foundDlls -join '; ')"
    }

    # 3. Filter driver verification via fltmc
    try {
        $fltCmd = Get-Command "fltmc.exe" -ErrorAction SilentlyContinue
        if ($fltCmd) {
            $fltOutput = & $fltCmd.Source "filters" 2>&1
            if ($LASTEXITCODE -eq 0 -and $fltOutput) {
                $match = $fltOutput | Where-Object { $_ -match "\b(winfsp|fsp)\b" }
                if ($match) {
                    $result.DriverLoaded = $true
                    $result.DetectionNotes += "WinFsp mini-filter driver active in fltmc filters"
                }
            } else {
                $result.DetectionNotes += "fltmc filters requires elevated privileges or returned code $LASTEXITCODE"
            }
        }
    } catch {
        $result.DetectionNotes += "fltmc filter check skipped: $($_.Exception.Message)"
    }

    # Composite decision
    if ($result.RegistryFound -or $result.DllFound -or $result.DriverLoaded) {
        $result.Installed = $true
    }

    return $result
}

function Find-RcloneExecutable {
    param([string]$ExplicitPath)

    if ($ExplicitPath) {
        if (Test-Path -Path $ExplicitPath -PathType Leaf -ErrorAction SilentlyContinue) {
            return (Resolve-Path -Path $ExplicitPath).Path
        }
        return $null
    }

    # Check PATH
    $cmd = Get-Command "rclone.exe" -ErrorAction SilentlyContinue
    if (-not $cmd) {
        $cmd = Get-Command "rclone" -ErrorAction SilentlyContinue
    }
    if ($cmd -and $cmd.Source) {
        return $cmd.Source
    }

    # Common installation locations on Windows
    $candidates = @()
    if ($env:ProgramFiles) {
        $candidates += (Join-Path $env:ProgramFiles "Rclone\rclone.exe")
        $candidates += (Join-Path $env:ProgramFiles "rclone\rclone.exe")
    }
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA "Programs\rclone\rclone.exe")
        $candidates += (Join-Path $env:LOCALAPPDATA "Programs\Rclone\rclone.exe")
    }
    $candidates += "C:\rclone\rclone.exe"
    $candidates += "C:\Tools\rclone\rclone.exe"
    if ($env:ChocolateyInstall) {
        $candidates += (Join-Path $env:ChocolateyInstall "bin\rclone.exe")
    }
    if ($env:USERPROFILE) {
        $candidates += (Join-Path $env:USERPROFILE "scoop\shims\rclone.exe")
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -Path $candidate -PathType Leaf -ErrorAction SilentlyContinue) {
            return (Resolve-Path -Path $candidate).Path
        }
    }

    return $null
}

function Test-MountPointAvailable {
    param([string]$Target)

    $res = [PSCustomObject]@{
        Target           = $Target
        IsDriveLetter    = $false
        IsDirectory      = $false
        Available        = $true
        ConflictReason   = $null
        FileSystem       = $null
    }

    # Check if target is a drive letter (e.g. "M:" or "M:\")
    if ($Target -match "^[A-Za-z]:?\\?$") {
        $res.IsDriveLetter = $true
        $driveLetter = $Target.Substring(0, 1).ToUpper()
        $drivePrefix = "$($driveLetter):"

        # Check PowerShell drives
        $psDrive = Get-PSDrive -Name $driveLetter -ErrorAction SilentlyContinue
        if ($psDrive) {
            $res.Available = $false
            $res.ConflictReason = "Drive letter '$drivePrefix' is in use (Provider: $($psDrive.Provider.Name), Root: $($psDrive.Root))."
            return $res
        }

        # Check Windows logical drives via .NET DriveInfo
        try {
            $drives = [System.IO.DriveInfo]::GetDrives()
            $matching = $drives | Where-Object { $_.Name.StartsWith($drivePrefix, [System.StringComparison]::OrdinalIgnoreCase) }
            if ($matching) {
                $res.Available = $false
                $res.ConflictReason = "Drive letter '$drivePrefix' is already assigned (Type: $($matching.DriveType))."
                return $res
            }
        } catch {
            # Ignore drive enumeration error
        }

        $res.Available = $true
        return $res
    }

    # Otherwise treat target as an NTFS directory path
    $res.IsDirectory = $true
    if (Test-Path -Path $Target -ErrorAction SilentlyContinue) {
        $item = Get-Item -Path $Target -ErrorAction SilentlyContinue
        if ($item -and -not $item.PSIsContainer) {
            $res.Available = $false
            $res.ConflictReason = "Mount point '$Target' exists and is a regular file, not a directory."
            return $res
        }

        # Check if directory is empty (rclone directory mount requires empty directory)
        $children = Get-ChildItem -Path $Target -Force -ErrorAction SilentlyContinue
        if ($children -and $children.Count -gt 0) {
            $res.Available = $false
            $res.ConflictReason = "Mount directory '$Target' is not empty ($($children.Count) items found)."
            return $res
        }
    }

    # Check filesystem type of target volume (must be NTFS for WinFsp directory mount)
    try {
        $fullPath = [System.IO.Path]::GetFullPath($Target)
        $root = [System.IO.Path]::GetPathRoot($fullPath)
        $driveInfo = [System.IO.DriveInfo]::new($root)
        $res.FileSystem = $driveInfo.DriveFormat
        if ($driveInfo.DriveFormat -ne "NTFS") {
            $res.Available = $false
            $res.ConflictReason = "Directory mount target root ($root) filesystem is '$($driveInfo.DriveFormat)'. WinFsp directory mounts require NTFS."
            return $res
        }
    } catch {
        # Fallback if DriveInfo fails
    }

    return $res
}

function Get-UserSessionInfo {
    $currentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($currentIdentity)
    $isElevated = $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
    $currentProc = Get-Process -Id $PID

    # Check EnableLinkedConnections in registry (relevant for elevated vs non-elevated drive mapping)
    $linkedConnections = $null
    $regPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
    if (Test-Path -Path $regPath -ErrorAction SilentlyContinue) {
        try {
            $sysPol = Get-ItemProperty -Path $regPath -Name "EnableLinkedConnections" -ErrorAction SilentlyContinue
            if ($sysPol -and $sysPol.EnableLinkedConnections -ne $null) {
                $linkedConnections = [int]$sysPol.EnableLinkedConnections
            }
        } catch {}
    }

    return [PSCustomObject]@{
        UserName                 = $currentIdentity.Name
        UserSid                  = $currentIdentity.User.Value
        SessionId                = $currentProc.SessionId
        IsElevatedAdministrator  = $isElevated
        EnableLinkedConnections  = $linkedConnections
        SessionNotes             = "Mount must run in same Windows Logon Session (SessionId: $($currentProc.SessionId)) as the backend application for drive letters to be visible."
    }
}

function Get-SystemCapacityInfo {
    $totalRamMB = 0
    $freeRamMB = 0
    try {
        $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
        if ($os) {
            $totalRamMB = [math]::Round($os.TotalVisibleMemorySize / 1024, 2)
            $freeRamMB = [math]::Round($os.FreePhysicalMemory / 1024, 2)
        }
    } catch {
        # Fallback if CIM instance is restricted
    }

    $systemDriveFreeGB = 0
    try {
        $sysDriveLetter = "C"
        if ($env:SystemDrive) {
            $sysDriveLetter = $env:SystemDrive.TrimEnd(':')
        }
        $sysDrive = Get-PSDrive -Name $sysDriveLetter -ErrorAction SilentlyContinue
        if ($sysDrive -and $sysDrive.Free) {
            $systemDriveFreeGB = [math]::Round($sysDrive.Free / 1GB, 2)
        }
    } catch {}

    return [PSCustomObject]@{
        TotalMemoryMB      = $totalRamMB
        FreeMemoryMB       = $freeRamMB
        HasSufficientRam   = ($freeRamMB -ge 128)
        SystemDriveFreeGB  = $systemDriveFreeGB
    }
}

function Check-RcloneConfigSafe {
    param([string]$Path)

    $result = [PSCustomObject]@{
        Specified       = $false
        ConfigPath      = $null
        FileExists      = $false
        FileSizeBytes   = 0
        IsSafe          = $true
        Note            = "Secret tokens and config contents are strictly omitted to prevent credential exposure."
    }

    $targetConfig = $Path
    if (-not $targetConfig) {
        $appDataPath = ""
        if ($env:APPDATA) {
            $appDataPath = $env:APPDATA
        }
        if ($appDataPath) {
            $defaultConfig = Join-Path $appDataPath "rclone\rclone.conf"
            if (Test-Path -Path $defaultConfig -PathType Leaf -ErrorAction SilentlyContinue) {
                $targetConfig = $defaultConfig
            }
        }
    } else {
        $result.Specified = $true
    }

    if ($targetConfig) {
        $result.ConfigPath = $targetConfig
        if (Test-Path -Path $targetConfig -PathType Leaf -ErrorAction SilentlyContinue) {
            $result.FileExists = $true
            try {
                $item = Get-Item -Path $targetConfig -ErrorAction SilentlyContinue
                if ($item) {
                    $result.FileSizeBytes = $item.Length
                }
            } catch {}
        }
    }

    return $result
}

# ----------------- MAIN EXECUTION -----------------

# 1. OS Info
$osCaption = "Unknown Windows"
$osVersion = [System.Environment]::OSVersion.VersionString
try {
    $osInfo = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction SilentlyContinue
    if ($osInfo) {
        $osCaption = $osInfo.Caption
        $osVersion = $osInfo.Version
    }
} catch {}

$osObj = [PSCustomObject]@{
    Caption      = $osCaption
    Version      = $osVersion
    Architecture = $env:PROCESSOR_ARCHITECTURE
    IsWindows    = $true
}

# 2. Rclone detection
$rcloneExe = Find-RcloneExecutable -ExplicitPath $RclonePath
$rcloneVersion = $null
if ($rcloneExe) {
    try {
        $verRaw = & $rcloneExe "version" 2>&1
        if ($verRaw) {
            $firstLine = ($verRaw | Select-Object -First 1).ToString().Trim()
            $rcloneVersion = $firstLine
        }
    } catch {
        $rcloneVersion = "Error reading version: $($_.Exception.Message)"
    }
}

$rcloneObj = [PSCustomObject]@{
    Installed       = [bool]$rcloneExe
    ExecutablePath  = $rcloneExe
    Version         = $rcloneVersion
    InstallGuideUrl = "https://rclone.org/install/"
}

# 3. WinFsp detection
$winfspObj = Test-WinFspInstalled

# 4. Mount point availability
$mountObj = Test-MountPointAvailable -Target $MountPoint

# 5. User session
$sessionObj = Get-UserSessionInfo

# 6. Capacity
$capacityObj = Get-SystemCapacityInfo

# 7. Config safety check
$configObj = Check-RcloneConfigSafe -Path $ConfigPath

# 8. Readiness assessment
$reasons = @()
if (-not $rcloneObj.Installed) {
    $reasons += "rclone executable is not found in PATH or standard install paths. Run 'winget install Rclone.Rclone' or download from https://rclone.org."
}
if (-not $winfspObj.Installed) {
    $reasons += "WinFsp is not installed or registered. WinFsp is required on Windows for rclone mount. Run 'winget install WinFsp.WinFsp' or download from https://winfsp.dev."
}
if (-not $mountObj.Available) {
    $reasons += "Mount target '$MountPoint' is unavailable: $($mountObj.ConflictReason)"
}
if (-not $capacityObj.HasSufficientRam) {
    $reasons += "Free physical RAM is critically low ($($capacityObj.FreeMemoryMB) MB < 128 MB threshold)."
}

$isReady = ($reasons.Count -eq 0)

$report = [PSCustomObject]@{
    Timestamp          = [DateTime]::UtcNow.ToString("o")
    IsReady            = $isReady
    Status             = $(if ($isReady) { "READY" } else { "BLOCKED" })
    BlockReasons       = $reasons
    HostOS             = $osObj
    Rclone             = $rcloneObj
    WinFsp             = $winfspObj
    MountTarget        = $mountObj
    UserSession        = $sessionObj
    SystemCapacity     = $capacityObj
    RcloneConfigFile   = $configObj
}

# Output strictly structured JSON
$report | ConvertTo-Json -Depth 6
