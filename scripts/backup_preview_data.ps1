[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDirectory,
    [string]$DataDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:PreviewFiles = @("preview_db.mv.db", "committed_catalog_snapshot.json")

function Assert-NoTraversal {
    param([string]$Path, [string]$Label)
    $parts = $Path -split '[\\/]'
    if ($parts -contains "..") { throw "$Label must not contain a '..' path segment." }
}

function Get-ExpectedDataDirectory {
    param([string]$Root, [string]$Requested)
    $expected = [System.IO.Path]::GetFullPath((Join-Path $Root "backend\springboot\data\preview"))
    if ($Requested) {
        Assert-NoTraversal $Requested "DataDirectory"
        $candidate = if ([System.IO.Path]::IsPathRooted($Requested)) { $Requested } else { Join-Path $Root $Requested }
        if ([System.IO.Path]::GetFullPath($candidate) -ine $expected) {
            throw "DataDirectory must be the dedicated preview directory: $expected"
        }
    }
    return $expected
}

function Assert-NoReparsePointInPath {
    param([string]$Path, [string]$Root)
    $current = [System.IO.Path]::GetFullPath($Path)
    while ($current -and $current.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing a path that contains a junction or symbolic link: $current"
            }
        }
        if ($current -ieq $Root) { break }
        $current = [System.IO.Directory]::GetParent($current).FullName
    }
}

function Assert-PreviewStackStopped {
    param([string]$Root, [string]$ExpectedDataDirectory)

    $statePath = Join-Path $Root "target\preview_stack.json"
    $state = $null
    if (Test-Path -LiteralPath $statePath) {
        if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) { throw "Preview launcher state is not a file; refusing to assume the stack is stopped." }
        Assert-NoReparsePointInPath $statePath $Root
        try { $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { throw "Preview launcher state is unreadable; refusing to assume the stack is stopped." }
        if (-not $state -or -not $state.PSObject.Properties["Processes"] -or $null -eq $state.Processes) {
            throw "Preview launcher state is malformed; refusing to assume the stack is stopped."
        }
        if ($state.PSObject.Properties["DataDirectory"]) {
            if ([string]::IsNullOrWhiteSpace([string]$state.DataDirectory)) { throw "Preview launcher DataDirectory is empty; refusing to back up an uncertain data location." }
            $stateDataPath = if ([System.IO.Path]::IsPathRooted([string]$state.DataDirectory)) { [string]$state.DataDirectory } else { Join-Path $Root ([string]$state.DataDirectory) }
            if ([System.IO.Path]::GetFullPath($stateDataPath) -ine $ExpectedDataDirectory) { throw "Preview launcher DataDirectory does not match the dedicated preview directory; refusing to back up the wrong store." }
        }
    }

    if ($state -and $state.Processes) {
        foreach ($record in @($state.Processes)) {
            $pidValue = 0
            if (-not $record -or -not $record.PSObject.Properties["PID"] -or
                -not [int]::TryParse([string]$record.PID, [ref]$pidValue) -or $pidValue -le 0 -or
                -not $record.PSObject.Properties["StartTime"] -or [string]::IsNullOrWhiteSpace([string]$record.StartTime) -or
                -not $record.PSObject.Properties["ExecutablePath"] -or [string]::IsNullOrWhiteSpace([string]$record.ExecutablePath)) {
                throw "Preview launcher process state is malformed; refusing to assume the stack is stopped."
            }
            try { $live = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction Stop } catch {
                throw "Could not verify preview process PID $pidValue; refusing an online data operation."
            }
            if (-not $live) { continue }
            try {
                $liveExe = [System.IO.Path]::GetFullPath([string]$live.ExecutablePath)
                $expectedExe = [System.IO.Path]::GetFullPath([string]$record.ExecutablePath)
                $liveStart = $live.CreationDate.ToUniversalTime()
                $recordStart = [DateTime]::Parse([string]$record.StartTime).ToUniversalTime()
                $delta = [Math]::Abs(($liveStart - $recordStart).TotalSeconds)
            } catch { throw "Could not verify preview process identity for PID $pidValue; refusing an online data operation." }
            if ($liveExe -ieq $expectedExe -and $delta -le 3.0) {
                throw ("Preview stack is still running: {0} PID {1}. Stop it with scripts\stop_preview_stack.ps1 first." -f $record.Name, $pidValue)
            }
        }
    }

    $port = 8080
    if ($state -and $state.PSObject.Properties["SpringPort"] -and [int]$state.SpringPort -gt 0) { $port = [int]$state.SpringPort }
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        try { $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { [int]$_.LocalPort -eq $port }) } catch {
            throw "Could not verify whether port $port is listening; refusing an online data operation."
        }
        if ($listeners.Count -gt 0) { throw "Port $port has a listener; refusing to copy preview data while Spring Boot may be using it." }
    } else {
        if (-not (Get-Command netstat -ErrorAction SilentlyContinue)) { throw "Cannot verify whether port $port is listening; refusing an online data operation." }
        $netstat = @(netstat -ano -p tcp 2>$null)
        if ($netstat | Where-Object { $_ -match (":{0}\s+.*LISTENING\s+\d+\s*$" -f $port) }) {
            throw "Port $port has a listener; refusing to copy preview data while Spring Boot may be using it."
        }
    }
}

function Open-PreviewDatabaseExclusive {
    param([string]$Path)
    try { return [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None) } catch {
        throw "Cannot obtain exclusive access to $Path. Stop the preview stack and retry."
    }
}

function Get-BackupDirectoryPath {
    param([string]$Root, [string]$Requested)
    Assert-NoTraversal $Requested "BackupDirectory"
    $base = [System.IO.Path]::GetFullPath((Join-Path $Root "target\preview_backups"))
    $candidate = if ([System.IO.Path]::IsPathRooted($Requested)) { $Requested } else { Join-Path $Root $Requested }
    $full = [System.IO.Path]::GetFullPath($candidate)
    $prefix = $base.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "BackupDirectory must be a named child of target\preview_backups: $base"
    }
    Assert-NoReparsePointInPath (Split-Path -Parent $full) $Root
    if (Test-Path -LiteralPath $full) { throw "BackupDirectory already exists: $full" }
    return $full
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dataPath = Get-ExpectedDataDirectory $root $DataDirectory
Assert-PreviewStackStopped $root $dataPath
if (-not (Test-Path -LiteralPath $dataPath -PathType Container)) { throw "Preview data directory not found: $dataPath" }
Assert-NoReparsePointInPath $dataPath $root
$databasePath = Join-Path $dataPath "preview_db.mv.db"
$databaseLock = Open-PreviewDatabaseExclusive $databasePath

try {
    $stagingPath = $null
    $sourceFiles = @{}
    foreach ($name in $script:PreviewFiles) {
        $source = Join-Path $dataPath $name
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Required preview file not found: $source" }
        $item = Get-Item -LiteralPath $source -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing a linked preview file: $source" }
        if ($name -eq "preview_db.mv.db") {
            $databaseLock.Position = 0
            $sha = [System.Security.Cryptography.SHA256]::Create()
            try { $dbHash = ([BitConverter]::ToString($sha.ComputeHash($databaseLock))).Replace("-", "").ToLowerInvariant() } finally { $sha.Dispose() }
            $databaseLock.Position = 0
            $length = [long]$databaseLock.Length
        } else {
            $dbHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
            $length = [long]$item.Length
        }
        $sourceFiles[$name] = [PSCustomObject]@{ Path = $source; Length = $length; Sha256 = $dbHash }
    }

    $backupPath = Get-BackupDirectoryPath $root $BackupDirectory
    $backupParent = Split-Path -Parent $backupPath
    if (-not (Test-Path -LiteralPath $backupParent -PathType Container)) { New-Item -ItemType Directory -Path $backupParent -Force | Out-Null }
    Assert-NoReparsePointInPath $backupParent $root
    $stagingPath = Join-Path $backupParent (".preview-backup-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $stagingPath | Out-Null

    $manifestFiles = @()
    foreach ($name in $script:PreviewFiles) {
        $sourceInfo = $sourceFiles[$name]
        $target = Join-Path $stagingPath $name
        if ($name -eq "preview_db.mv.db") {
            $databaseLock.Position = 0
            $targetStream = [System.IO.File]::Open($target, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            try { $databaseLock.CopyTo($targetStream) } finally { $targetStream.Dispose() }
            $databaseLock.Position = 0
        } else {
            [System.IO.File]::Copy($sourceInfo.Path, $target, $false)
        }
        $targetInfo = Get-Item -LiteralPath $target
        $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
        if ([long]$targetInfo.Length -ne $sourceInfo.Length -or $targetHash -ine $sourceInfo.Sha256) {
            throw "Backup copy verification failed for $name."
        }
        $manifestFiles += [PSCustomObject]@{ name = $name; length = $sourceInfo.Length; sha256 = $sourceInfo.Sha256 }
    }
    $manifest = [ordered]@{
        format = "preview-data-backup-v1"
        createdUtc = [DateTime]::UtcNow.ToString("o")
        dataDirectory = "backend/springboot/data/preview"
        files = $manifestFiles
    }
    $json = $manifest | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText((Join-Path $stagingPath "manifest.json"), $json, (New-Object System.Text.UTF8Encoding($false)))
    [System.IO.Directory]::Move($stagingPath, $backupPath)
} catch {
    if ($stagingPath) {
        foreach ($name in $script:PreviewFiles) {
            $path = Join-Path $stagingPath $name
            if (Test-Path -LiteralPath $path -PathType Leaf) { Remove-Item -LiteralPath $path -Force }
        }
        $manifestPath = Join-Path $stagingPath "manifest.json"
        if (Test-Path -LiteralPath $manifestPath -PathType Leaf) { Remove-Item -LiteralPath $manifestPath -Force }
        if (Test-Path -LiteralPath $stagingPath -PathType Container) { Remove-Item -LiteralPath $stagingPath -Force }
    }
    throw
} finally {
    $databaseLock.Dispose()
}

Write-Host "Preview data backup created: $backupPath"
foreach ($name in $script:PreviewFiles) {
    Write-Host ("  {0}: {1} bytes, SHA256 {2}" -f $name, $sourceFiles[$name].Length, $sourceFiles[$name].Sha256)
}
