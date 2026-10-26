[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$global:PreviewApiCalls = New-Object System.Collections.Generic.List[object]
$global:PreviewValidationResult = $null
$global:PreviewTcpQueryError = $false

function global:Invoke-RestMethod {
    param($Uri, $Method, $Headers, $Body, $ContentType, $TimeoutSec, $ErrorAction)
    $global:PreviewApiCalls.Add([PSCustomObject]@{ Uri = [string]$Uri; Method = [string]$Method; Headers = $Headers; Body = [string]$Body })
    if ($Uri -match "/auth/login$") {
        return [PSCustomObject]@{ success = $true; data = [PSCustomObject]@{ token = "MOCK-BEARER-TOKEN"; role = "ROLE_ADMIN" } }
    }
    if ($Uri -match "/admin/catalog/validate$") {
        if ($global:PreviewValidationResult) { return $global:PreviewValidationResult }
        return [PSCustomObject]@{ valid = $true; packageId = "jadoo_all"; revision = 3; toCreate = 99; toUpdate = 0; unchanged = 0; conflicts = 0; errors = @() }
    }
    if ($Uri -match "/admin/catalog/import$") {
        return [PSCustomObject]@{ success = $true; packageId = "jadoo_all"; revision = 3; importId = "mock-import-42"; counts = [PSCustomObject]@{ series = 1; episodes = 99; mediaAssets = 99 }; indexStatus = "PENDING"; message = "Snapshot sync pending." }
    }
    throw "Unexpected mock API URL: $Uri"
}

function global:Get-NetTCPConnection {
    param($State, $ErrorAction)
    if ($global:PreviewTcpQueryError) { throw "Mock listener enumeration failure." }
    return @()
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "ASSERTION FAILED: $Message" }
}

function Invoke-ExpectedFailure {
    param([scriptblock]$Action, [string]$ExpectedText)
    $caught = $false
    try { & $Action } catch {
        $caught = $true
        if ($ExpectedText -and $_.Exception.Message -notlike "*$ExpectedText*") {
            throw "Expected error containing '$ExpectedText'; got '$($_.Exception.Message)'"
        }
    }
    if (-not $caught) { throw "Expected failure containing '$ExpectedText'." }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("preview-data-tools-test-" + [Guid]::NewGuid().ToString("N"))
$insideTemp = [System.IO.Path]::GetFullPath($testRoot).StartsWith([System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()), [System.StringComparison]::OrdinalIgnoreCase)
if (-not $insideTemp) { throw "Test fixture path did not resolve under the system temp directory." }

try {
    $scriptsPath = Join-Path $testRoot "scripts"
    $dataPath = Join-Path $testRoot "backend\springboot\data\preview"
    $backupRoot = Join-Path $testRoot "target\preview_backups"
    New-Item -ItemType Directory -Path $scriptsPath -Force | Out-Null
    New-Item -ItemType Directory -Path $dataPath -Force | Out-Null
    foreach ($name in @("import_preview_catalog.ps1", "backup_preview_data.ps1", "restore_preview_data.ps1")) {
        [System.IO.File]::Copy((Join-Path $repoRoot "scripts\$name"), (Join-Path $scriptsPath $name), $false)
    }

    $dbBytes = [System.Text.Encoding]::UTF8.GetBytes("fixture database bytes v1")
    $snapshotBytes = [System.Text.Encoding]::UTF8.GetBytes('{"schema_version":"dippie.catalog.v1","package":{"id":"jadoo_all","revision":3}}')
    [System.IO.File]::WriteAllBytes((Join-Path $dataPath "preview_db.mv.db"), $dbBytes)
    [System.IO.File]::WriteAllBytes((Join-Path $dataPath "committed_catalog_snapshot.json"), $snapshotBytes)

    $catalogPath = Join-Path $testRoot "catalog.json"
    $catalogJson = '{"schema_version":"dippie.catalog.v1","package":{"id":"jadoo_all","revision":3,"import_mode":"replace"},"series":[]}'
    [System.IO.File]::WriteAllText($catalogPath, $catalogJson, (New-Object System.Text.UTF8Encoding($false)))

    Assert-True ((Get-Command Invoke-RestMethod).CommandType -eq "Function") "the API call is isolated behind the mock"
    $global:PreviewApiCalls.Clear()
    $global:PreviewValidationResult = $null
    $securePassword = ConvertTo-SecureString "fixture-password" -AsPlainText -Force
    $importOutput = & (Join-Path $scriptsPath "import_preview_catalog.ps1") -CatalogPath $catalogPath `
        -ApiBaseUrl "http://127.0.0.1:8080/api" -Username "fixture-admin" -Password $securePassword 6>&1 | Out-String -Width 4096
    Assert-True ($global:PreviewApiCalls.Count -eq 3) "import calls login, validate, then import"
    Assert-True ($global:PreviewApiCalls[0].Uri -match "/auth/login$") "first API call logs in"
    Assert-True ($global:PreviewApiCalls[0].Body -match '"usernameOrEmail":"fixture-admin"') "login uses the production auth payload"
    Assert-True ($global:PreviewApiCalls[0].Body -match '"password":"fixture-password"') "secure password is sent only to login"
    Assert-True ($global:PreviewApiCalls[1].Body -ceq $catalogJson) "validation receives the original catalog JSON"
    Assert-True ($global:PreviewApiCalls[2].Body -ceq $catalogJson) "import receives the original catalog JSON"
    Assert-True ($global:PreviewApiCalls[2].Headers.Authorization -eq "Bearer MOCK-BEARER-TOKEN") "admin token is sent as a bearer header"
    Assert-True ($importOutput -match "Imported package jadoo_all revision 3") "import result names actual package and revision"
    Assert-True ($importOutput -match "episodes=99") "import result shows actual returned counts"
    Assert-True ($importOutput -match "indexStatus=PENDING") "import result reports deferred index status"
    Assert-True ($importOutput -notmatch "fixture-password|MOCK-BEARER-TOKEN") "output contains no password or token"
    Write-Host "PASS: importer uses login -> validate -> import, preserves JSON and reports server result without secrets."

    $global:PreviewApiCalls.Clear()
    $global:PreviewValidationResult = [PSCustomObject]@{ valid = $false; packageId = "jadoo_all"; revision = 3; toCreate = 0; toUpdate = 0; unchanged = 0; conflicts = 1; errors = @() }
    Invoke-ExpectedFailure {
        & (Join-Path $scriptsPath "import_preview_catalog.ps1") -CatalogPath $catalogPath `
            -ApiBaseUrl "http://127.0.0.1:8080/api" -Username "fixture-admin" -Password $securePassword
    } "no catalog was imported"
    Assert-True ($global:PreviewApiCalls.Count -eq 2) "conflict stops before the import endpoint"
    Write-Host "PASS: importer blocks invalid/conflicting catalog before import."

    Invoke-ExpectedFailure {
        & (Join-Path $scriptsPath "import_preview_catalog.ps1") -CatalogPath $catalogPath `
            -ApiBaseUrl "http://example.com/api" -Username "fixture-admin" -Password $securePassword
    } "loopback"
    Write-Host "PASS: importer rejects non-loopback API URLs."

    $backupScript = Join-Path $scriptsPath "backup_preview_data.ps1"
    $restoreScript = Join-Path $scriptsPath "restore_preview_data.ps1"
    New-Item -ItemType Directory -Path (Join-Path $testRoot "target") -Force | Out-Null
    $staleState = [PSCustomObject]@{
        SpringPort = 8080
        DataDirectory = $dataPath
        Processes = @([PSCustomObject]@{ Name = "SpringBoot"; PID = 2147483647; StartTime = "2000-01-01T00:00:00.0000000Z"; ExecutablePath = "C:\\stale\\java.exe"; Port = 8080 })
    }
    [System.IO.File]::WriteAllText((Join-Path $testRoot "target\preview_stack.json"), ($staleState | ConvertTo-Json -Depth 4), (New-Object System.Text.UTF8Encoding($false)))
    & $backupScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\stale-state-ignored" | Out-Null
    Write-Host "PASS: stale launcher state is ignored when its recorded PID is gone."

    & $backupScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\roundtrip" | Out-Null
    $backupPath = Join-Path $backupRoot "roundtrip"
    $manifest = Get-Content -LiteralPath (Join-Path $backupPath "manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($manifest.files.Count -eq 2) "backup manifest lists database and snapshot"
    foreach ($file in @($manifest.files)) {
        $expectedHash = (Get-FileHash -LiteralPath (Join-Path $dataPath $file.name) -Algorithm SHA256).Hash
        Assert-True ($file.sha256 -ieq $expectedHash) "backup manifest hash matches $($file.name)"
    }
    Write-Host "PASS: backup stores both preview files with verified SHA256 hashes."

    [System.IO.File]::WriteAllText((Join-Path $dataPath "preview_db.mv.db"), "pre-restore database", (New-Object System.Text.UTF8Encoding($false)))
    [System.IO.File]::WriteAllText((Join-Path $dataPath "committed_catalog_snapshot.json"), "pre-restore snapshot", (New-Object System.Text.UTF8Encoding($false)))
    $beforeDb = (Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash
    $beforeSnapshot = (Get-FileHash -LiteralPath (Join-Path $dataPath "committed_catalog_snapshot.json") -Algorithm SHA256).Hash
    $restoreOutput = & $restoreScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\roundtrip" 6>&1 | Out-String -Width 4096
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath (Join-Path $backupPath "preview_db.mv.db") -Algorithm SHA256).Hash) "restore reproduces database bytes"
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $dataPath "committed_catalog_snapshot.json") -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath (Join-Path $backupPath "committed_catalog_snapshot.json") -Algorithm SHA256).Hash) "restore reproduces snapshot bytes"
    Assert-True ($restoreOutput -match "Recovery backup created:") "restore reports its recovery copy"
    $recoveryMatch = [regex]::Match($restoreOutput, "Recovery backup created: ([^\r\n]+)")
    Assert-True $recoveryMatch.Success "recovery path is human-visible"
    $recoveryPath = $recoveryMatch.Groups[1].Value.Trim()
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $recoveryPath "preview_db.mv.db") -Algorithm SHA256).Hash -eq $beforeDb) "recovery copy preserves prior database"
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $recoveryPath "committed_catalog_snapshot.json") -Algorithm SHA256).Hash -eq $beforeSnapshot) "recovery copy preserves prior snapshot"
    Write-Host "PASS: restore verifies hashes, restores both files and retains a recovery backup of prior data."

    [System.IO.File]::WriteAllText((Join-Path $dataPath "preview_db.mv.db"), "must remain untouched after corrupt backup", (New-Object System.Text.UTF8Encoding($false)))
    [System.IO.File]::WriteAllText((Join-Path $dataPath "committed_catalog_snapshot.json"), "must remain untouched after corrupt backup", (New-Object System.Text.UTF8Encoding($false)))
    $currentDbHash = (Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash
    $currentSnapshotHash = (Get-FileHash -LiteralPath (Join-Path $dataPath "committed_catalog_snapshot.json") -Algorithm SHA256).Hash
    $recoveryCount = @(Get-ChildItem -LiteralPath $backupRoot -Directory | Where-Object { $_.Name -like "recovery-*" }).Count
    [System.IO.File]::AppendAllText((Join-Path $backupPath "preview_db.mv.db"), "corrupt")
    Invoke-ExpectedFailure {
        & $restoreScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\roundtrip"
    } "check failed"
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash -eq $currentDbHash) "corrupt backup is rejected before DB mutation"
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $dataPath "committed_catalog_snapshot.json") -Algorithm SHA256).Hash -eq $currentSnapshotHash) "corrupt backup is rejected before snapshot mutation"
    Assert-True (@(Get-ChildItem -LiteralPath $backupRoot -Directory | Where-Object { $_.Name -like "recovery-*" }).Count -eq $recoveryCount) "corrupt backup is rejected before recovery mutation"
    Write-Host "PASS: corrupt backup is rejected before recovery or preview-data mutation."

    [System.IO.File]::WriteAllBytes((Join-Path $backupPath "preview_db.mv.db"), $dbBytes)
    $manifestPath = Join-Path $backupPath "manifest.json"
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $manifest.files += [PSCustomObject]@{ name = "..\outside.mv.db"; length = 0; sha256 = ("0" * 64) }
    [System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 4), (New-Object System.Text.UTF8Encoding($false)))
    Invoke-ExpectedFailure {
        & $restoreScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\roundtrip"
    } "unsafe or unexpected file name"
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash -eq $currentDbHash) "traversal entry is rejected before mutation"
    Assert-True (@(Get-ChildItem -LiteralPath $backupRoot -Directory | Where-Object { $_.Name -like "recovery-*" }).Count -eq $recoveryCount) "traversal entry is rejected before recovery mutation"
    Write-Host "PASS: manifest path traversal is rejected before mutation."

    $movedDataPath = Join-Path (Split-Path -Parent $dataPath) "preview-before-empty-restore"
    Move-Item -LiteralPath $dataPath -Destination $movedDataPath
    & $restoreScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\stale-state-ignored" | Out-Null
    Assert-True (Test-Path -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -PathType Leaf) "restore creates a missing dedicated data directory"
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath (Join-Path $backupRoot "stale-state-ignored\preview_db.mv.db") -Algorithm SHA256).Hash) "restore into missing directory restores the DB"
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $dataPath "committed_catalog_snapshot.json") -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath (Join-Path $backupRoot "stale-state-ignored\committed_catalog_snapshot.json") -Algorithm SHA256).Hash) "restore into missing directory restores the snapshot"
    Write-Host "PASS: restore recreates the dedicated data directory when it does not exist."

    $tcpErrorRecoveryCount = @(Get-ChildItem -LiteralPath $backupRoot -Directory | Where-Object { $_.Name -like "recovery-*" }).Count
    $tcpErrorDbHash = (Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash
    $global:PreviewTcpQueryError = $true
    try {
        Invoke-ExpectedFailure {
            & $backupScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\listener-query-error"
        } "Could not verify whether port"
        Invoke-ExpectedFailure {
            & $restoreScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\stale-state-ignored"
        } "Could not verify whether port"
    } finally { $global:PreviewTcpQueryError = $false }
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $backupRoot "listener-query-error"))) "listener query failure creates no backup"
    Assert-True (@(Get-ChildItem -LiteralPath $backupRoot -Directory | Where-Object { $_.Name -like "recovery-*" }).Count -eq $tcpErrorRecoveryCount) "listener query failure creates no recovery backup"
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash -eq $tcpErrorDbHash) "listener query failure leaves data untouched"
    Write-Host "PASS: empty listener enumeration permits offline work, but enumeration errors fail closed."

    Invoke-ExpectedFailure {
        & $backupScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\..\escape"
    } "'..' path segment"
    Invoke-ExpectedFailure {
        & $backupScript -DataDirectory "backend\springboot\data\..\preview" -BackupDirectory "target\preview_backups\bad-data-path"
    } "'..' path segment"
    Write-Host "PASS: path traversal is rejected in explicit directory arguments."

    Remove-Item -LiteralPath (Join-Path $testRoot "target\preview_stack.json") -Force
    $beforeLockDbHash = (Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash
    $beforeLockSnapshotHash = (Get-FileHash -LiteralPath (Join-Path $dataPath "committed_catalog_snapshot.json") -Algorithm SHA256).Hash
    $beforeLockRecoveryCount = @(Get-ChildItem -LiteralPath $backupRoot -Directory | Where-Object { $_.Name -like "recovery-*" }).Count
    $openDatabase = [System.IO.File]::Open((Join-Path $dataPath "preview_db.mv.db"), [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    try {
        Invoke-ExpectedFailure {
            & $backupScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\locked-backup"
        } "exclusive access"
        Invoke-ExpectedFailure {
            & $restoreScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\stale-state-ignored"
        } "exclusive access"
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $backupRoot "locked-backup"))) "open database lock prevents backup creation"
        Assert-True (@(Get-ChildItem -LiteralPath $backupRoot -Directory | Where-Object { $_.Name -like "recovery-*" }).Count -eq $beforeLockRecoveryCount) "open database lock prevents recovery creation"
    } finally { $openDatabase.Dispose() }
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash -eq $beforeLockDbHash) "open database lock leaves the DB untouched"
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $dataPath "committed_catalog_snapshot.json") -Algorithm SHA256).Hash -eq $beforeLockSnapshotHash) "open database lock leaves the snapshot untouched"
    Write-Host "PASS: an exclusive H2 file lock blocks backup and restore before mutation, without launcher state."

    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $PID" -ErrorAction Stop
    $processStart = (Get-Process -Id $PID).StartTime.ToString("o")
    $state = [PSCustomObject]@{
        SpringPort = 8080
        DataDirectory = $dataPath
        Processes = @([PSCustomObject]@{ Name = "SpringBoot"; PID = $PID; StartTime = $processStart; ExecutablePath = $processInfo.ExecutablePath; Port = 8080 })
    }
    [System.IO.File]::WriteAllText((Join-Path $testRoot "target\preview_stack.json"), ($state | ConvertTo-Json -Depth 4), (New-Object System.Text.UTF8Encoding($false)))
    $beforeActiveRefusalHash = (Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash
    Invoke-ExpectedFailure {
        & $backupScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\active-refusal"
    } "Preview stack is still running"
    $activeRecoveryCount = @(Get-ChildItem -LiteralPath $backupRoot -Directory | Where-Object { $_.Name -like "recovery-*" }).Count
    Invoke-ExpectedFailure {
        & $restoreScript -DataDirectory "backend\springboot\data\preview" -BackupDirectory "target\preview_backups\stale-state-ignored"
    } "Preview stack is still running"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $backupRoot "active-refusal"))) "active stack refusal creates no backup"
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $dataPath "preview_db.mv.db") -Algorithm SHA256).Hash -eq $beforeActiveRefusalHash) "active stack refusal leaves data untouched"
    Assert-True (@(Get-ChildItem -LiteralPath $backupRoot -Directory | Where-Object { $_.Name -like "recovery-*" }).Count -eq $activeRecoveryCount) "active stack refusal creates no restore recovery copy"
    Write-Host "PASS: a live PID/executable/start-time identity blocks backup and restore."

    Write-Host "All preview data tool checks passed."
} finally {
    $resolvedTemp = [System.IO.Path]::GetFullPath($testRoot)
    $tempPrefix = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd([char]'\', [char]'/') + [System.IO.Path]::DirectorySeparatorChar
    if ($resolvedTemp.StartsWith($tempPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedTemp -PathType Container)) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
    }
}
