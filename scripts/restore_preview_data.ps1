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
    if (($Path -split '[\\/]') -contains "..") { throw "$Label must not contain a '..' path segment." }
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
            if ([string]::IsNullOrWhiteSpace([string]$state.DataDirectory)) { throw "Preview launcher DataDirectory is empty; refusing to restore to an uncertain data location." }
            $stateDataPath = if ([System.IO.Path]::IsPathRooted([string]$state.DataDirectory)) { [string]$state.DataDirectory } else { Join-Path $Root ([string]$state.DataDirectory) }
            if ([System.IO.Path]::GetFullPath($stateDataPath) -ine $ExpectedDataDirectory) { throw "Preview launcher DataDirectory does not match the dedicated preview directory; refusing to restore the wrong store." }
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
        if ($listeners.Count -gt 0) { throw "Port $port has a listener; refusing to replace preview data while Spring Boot may be using it." }
    } else {
        if (-not (Get-Command netstat -ErrorAction SilentlyContinue)) { throw "Cannot verify whether port $port is listening; refusing an online data operation." }
        $netstat = @(netstat -ano -p tcp 2>$null)
        if ($netstat | Where-Object { $_ -match (":{0}\s+.*LISTENING\s+\d+\s*$" -f $port) }) {
            throw "Port $port has a listener; refusing to replace preview data while Spring Boot may be using it."
        }
    }
}

function Open-PreviewDatabaseExclusive {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
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
    $prefix = $base.TrimEnd([char]'\', [char]'/') + [System.IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "BackupDirectory must be a named child of target\preview_backups: $base"
    }
    Assert-NoReparsePointInPath $full $Root
    if (-not (Test-Path -LiteralPath $full -PathType Container)) { throw "BackupDirectory not found: $full" }
    return $full
}

function Read-VerifiedBackup {
    param([string]$Directory)

    $manifestPath = Join-Path $Directory "manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Backup manifest missing: $manifestPath" }
    $manifestItem = Get-Item -LiteralPath $manifestPath -Force
    if (($manifestItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing a linked backup manifest." }
    try { $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { throw "Backup manifest is not valid JSON." }
    if (-not $manifest -or $manifest.format -ne "preview-data-backup-v1") { throw "Unsupported preview backup manifest format." }

    $entries = @{}
    foreach ($entry in @($manifest.files)) {
        $name = [string]$entry.name
        if ($name -notin $script:PreviewFiles) { throw "Backup manifest contains an unsafe or unexpected file name: $name" }
        if ($entries.ContainsKey($name)) { throw "Backup manifest repeats file: $name" }
        if ([string]$entry.sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "Backup manifest has an invalid SHA256 for $name." }
        $length = 0L
        if (-not [long]::TryParse([string]$entry.length, [ref]$length) -or $length -lt 0) { throw "Backup manifest has an invalid length for $name." }
        $path = Join-Path $Directory $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Backup file missing: $name" }
        $item = Get-Item -LiteralPath $path -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing a linked backup file: $name" }
        if ([long]$item.Length -ne $length) { throw "Backup length check failed for $name." }
        $actualHash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($actualHash -ine [string]$entry.sha256) { throw "Backup SHA256 check failed for $name." }
        $entries[$name] = [PSCustomObject]@{ Path = $path; Length = $length; Sha256 = $actualHash.ToLowerInvariant() }
    }
    if ($entries.Count -ne $script:PreviewFiles.Count) { throw "Backup must contain the database and committed catalog snapshot." }
    foreach ($name in $script:PreviewFiles) { if (-not $entries.ContainsKey($name)) { throw "Backup file missing from manifest: $name" } }
    return $entries
}

function New-RecoveryBackup {
    param([string]$Root, [string]$DataPath)

    $backupBase = Join-Path $Root "target\preview_backups"
    if (-not (Test-Path -LiteralPath $backupBase -PathType Container)) { New-Item -ItemType Directory -Path $backupBase -Force | Out-Null }
    Assert-NoReparsePointInPath $backupBase $Root
    $name = "recovery-" + [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssfffZ") + "-" + [Guid]::NewGuid().ToString("N").Substring(0, 8)
    $finalPath = Join-Path $backupBase $name
    $stagingPath = Join-Path $backupBase (".preview-recovery-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $stagingPath | Out-Null
    $manifestFiles = @()
    try {
        $databaseLock = $null
        if (Test-Path -LiteralPath $DataPath -PathType Container) {
            Assert-NoReparsePointInPath $DataPath $Root
            $databasePath = Join-Path $DataPath "preview_db.mv.db"
            $databaseLock = Open-PreviewDatabaseExclusive $databasePath
        }
        try {
            if (Test-Path -LiteralPath $DataPath -PathType Container) {
            foreach ($fileName in $script:PreviewFiles) {
                $source = Join-Path $DataPath $fileName
                if (-not (Test-Path -LiteralPath $source)) { continue }
                if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "A preview file path is not a file: $source" }
                $item = Get-Item -LiteralPath $source -Force
                if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing a linked preview file: $source" }
                $target = Join-Path $stagingPath $fileName
                if ($fileName -eq "preview_db.mv.db") {
                    if (-not $databaseLock) { throw "Preview database disappeared before recovery copy." }
                    $databaseLock.Position = 0
                    $sourceHash = [System.Security.Cryptography.SHA256]::Create()
                    try { $hash = ([BitConverter]::ToString($sourceHash.ComputeHash($databaseLock))).Replace("-", "").ToLowerInvariant() } finally { $sourceHash.Dispose() }
                    $databaseLock.Position = 0
                    $targetStream = [System.IO.File]::Open($target, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
                    try { $databaseLock.CopyTo($targetStream) } finally { $targetStream.Dispose() }
                    $databaseLock.Position = 0
                } else {
                    [System.IO.File]::Copy($source, $target, $false)
                    $hash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
                }
                $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
                if ([long](Get-Item -LiteralPath $target).Length -ne [long]$item.Length -or $hash -ine $targetHash) {
                    throw "Could not verify the recovery copy of $fileName."
                }
                $manifestFiles += [PSCustomObject]@{ name = $fileName; length = [long]$item.Length; sha256 = $hash }
            }
            }
        } finally {
            if ($databaseLock) { $databaseLock.Dispose() }
        }
        $manifest = [ordered]@{ format = "preview-data-backup-v1"; createdUtc = [DateTime]::UtcNow.ToString("o"); dataDirectory = "backend/springboot/data/preview"; files = $manifestFiles }
        [System.IO.File]::WriteAllText((Join-Path $stagingPath "manifest.json"), ($manifest | ConvertTo-Json -Depth 4), (New-Object System.Text.UTF8Encoding($false)))
        [System.IO.Directory]::Move($stagingPath, $finalPath)
    } catch {
        foreach ($fileName in $script:PreviewFiles) { $path = Join-Path $stagingPath $fileName; if (Test-Path -LiteralPath $path -PathType Leaf) { Remove-Item -LiteralPath $path -Force } }
        $manifestPath = Join-Path $stagingPath "manifest.json"
        if (Test-Path -LiteralPath $manifestPath -PathType Leaf) { Remove-Item -LiteralPath $manifestPath -Force }
        if (Test-Path -LiteralPath $stagingPath -PathType Container) { Remove-Item -LiteralPath $stagingPath -Force }
        throw
    }
    return [PSCustomObject]@{ Path = $finalPath; Files = $manifestFiles }
}

function Set-FileAtomically {
    param([string]$StagedPath, [string]$TargetPath, [string]$BackupSuffix)
    if (Test-Path -LiteralPath $TargetPath) {
        if (-not (Test-Path -LiteralPath $TargetPath -PathType Leaf)) { throw "A preview file path is not a file: $TargetPath" }
        $replaceBackup = $TargetPath + ".preview-replaced-" + $BackupSuffix
        [System.IO.File]::Replace($StagedPath, $TargetPath, $replaceBackup)
        if (Test-Path -LiteralPath $replaceBackup -PathType Leaf) { Remove-Item -LiteralPath $replaceBackup -Force -ErrorAction SilentlyContinue }
    } else {
        [System.IO.File]::Move($StagedPath, $TargetPath)
    }
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dataPath = Get-ExpectedDataDirectory $root $DataDirectory
Assert-PreviewStackStopped $root $dataPath
$backupPath = Get-BackupDirectoryPath $root $BackupDirectory
$verifiedFiles = Read-VerifiedBackup $backupPath

if (Test-Path -LiteralPath $dataPath) {
    if (-not (Test-Path -LiteralPath $dataPath -PathType Container)) { throw "DataDirectory is not a directory: $dataPath" }
    Assert-NoReparsePointInPath $dataPath $root
}
$dbPreflight = Open-PreviewDatabaseExclusive (Join-Path $dataPath "preview_db.mv.db")
if ($dbPreflight) { $dbPreflight.Dispose() }
$recovery = New-RecoveryBackup $root $dataPath
Write-Host "Recovery backup created: $($recovery.Path)"

if (-not (Test-Path -LiteralPath $dataPath -PathType Container)) { New-Item -ItemType Directory -Path $dataPath -Force | Out-Null }
Assert-NoReparsePointInPath $dataPath $root
$restoreId = [Guid]::NewGuid().ToString("N")
$stagedFiles = @{}
try {
    foreach ($name in $script:PreviewFiles) {
        $stage = Join-Path $dataPath (".preview-restore-" + $restoreId + "-" + $name)
        [System.IO.File]::Copy($verifiedFiles[$name].Path, $stage, $false)
        if ((Get-FileHash -LiteralPath $stage -Algorithm SHA256).Hash -ine $verifiedFiles[$name].Sha256) { throw "Staged restore hash check failed for $name." }
        $stagedFiles[$name] = $stage
    }
    Assert-PreviewStackStopped $root $dataPath
    $dbPreApply = Open-PreviewDatabaseExclusive (Join-Path $dataPath "preview_db.mv.db")
    if ($dbPreApply) { $dbPreApply.Dispose() }
} catch {
    foreach ($path in $stagedFiles.Values) { if (Test-Path -LiteralPath $path -PathType Leaf) { Remove-Item -LiteralPath $path -Force } }
    foreach ($name in $script:PreviewFiles) { $path = Join-Path $dataPath (".preview-restore-" + $restoreId + "-" + $name); if (Test-Path -LiteralPath $path -PathType Leaf) { Remove-Item -LiteralPath $path -Force } }
    throw "Restore staging failed. Current data is preserved; recovery backup: $($recovery.Path). $($_.Exception.Message)"
}

$changedFiles = @()
try {
    foreach ($name in $script:PreviewFiles) {
        $target = Join-Path $dataPath $name
        $changedFiles += $name
        Set-FileAtomically $stagedFiles[$name] $target $restoreId
    }
} catch {
    $restoreError = $_.Exception.Message
    $recoveryFiles = @{}
    foreach ($entry in @((Get-Content -LiteralPath (Join-Path $recovery.Path "manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json).files)) { $recoveryFiles[[string]$entry.name] = $entry }
    foreach ($name in $changedFiles) {
        $target = Join-Path $dataPath $name
        if ($recoveryFiles.ContainsKey($name)) {
            $rollback = Join-Path $dataPath (".preview-rollback-" + $restoreId + "-" + $name)
            [System.IO.File]::Copy((Join-Path $recovery.Path $name), $rollback, $false)
            Set-FileAtomically $rollback $target ("rollback-" + $restoreId)
        } elseif (Test-Path -LiteralPath $target -PathType Leaf) {
            Remove-Item -LiteralPath $target -Force
        }
    }
    foreach ($name in $script:PreviewFiles) { $path = Join-Path $dataPath (".preview-restore-" + $restoreId + "-" + $name); if (Test-Path -LiteralPath $path -PathType Leaf) { Remove-Item -LiteralPath $path -Force } }
    throw "Restore failed; rollback attempted. Recovery copy is preserved at $($recovery.Path). $restoreError"
}

Write-Host "Restored preview database and committed catalog snapshot from: $backupPath"
foreach ($name in $script:PreviewFiles) { Write-Host ("  {0}: {1} bytes, SHA256 {2}" -f $name, $verifiedFiles[$name].Length, $verifiedFiles[$name].Sha256) }
