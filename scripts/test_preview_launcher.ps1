[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$launcherPath = Join-Path $PSScriptRoot "start_preview_stack.ps1"
$stopperPath = Join-Path $PSScriptRoot "stop_preview_stack.ps1"
$tokens = $null
$parseErrors = $null
$launcherAst = [System.Management.Automation.Language.Parser]::ParseFile($launcherPath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) { throw "start_preview_stack.ps1 has PowerShell parse errors: $($parseErrors[0].Message)" }
[System.Management.Automation.Language.Parser]::ParseFile($stopperPath, [ref]$tokens, [ref]$parseErrors) | Out-Null
if ($parseErrors.Count -gt 0) { throw "stop_preview_stack.ps1 has PowerShell parse errors: $($parseErrors[0].Message)" }

$helperNames = @(
    "Format-NativeArgument",
    "Start-ChildServiceProcess",
    "Get-PreviewPaths",
    "Get-PreviewRuntimeContract",
    "Get-SpringBootArguments",
    "Get-PreviewPortsToCheck",
    "Test-FrontendBuildStale",
    "Test-RecordedProcessIdentity"
)
$helperAsts = @($launcherAst.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $helperNames -contains $node.Name
}, $true))
if ($helperAsts.Count -ne $helperNames.Count) { throw "Expected to find all launcher helpers used by the runtime contract tests." }
foreach ($helperAst in $helperAsts) { . ([ScriptBlock]::Create($helperAst.Extent.Text)) }

function Assert-Equal {
    param($Expected, $Actual, [string]$Message)
    if ($Expected -cne $Actual) { throw "$Message Expected '$Expected', got '$Actual'." }
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

$script:testVariable = "PREVIEW_LAUNCHER_TEST_" + [Guid]::NewGuid().ToString("N")
$script:observedChildValue = $null
$script:observedArgumentList = $null
$script:failStart = $false
$originalValue = [System.Environment]::GetEnvironmentVariable($script:testVariable, "Process")

function Start-Process {
    param(
        [string]$FilePath,
        [string]$ArgumentList,
        [string]$WorkingDirectory,
        [string]$RedirectStandardOutput,
        [string]$RedirectStandardError,
        [switch]$PassThru,
        [string]$WindowStyle
    )

    Assert-Equal "Hidden" $WindowStyle "Background services must start hidden."
    $script:observedChildValue = [System.Environment]::GetEnvironmentVariable($script:testVariable, "Process")
    $script:observedArgumentList = $ArgumentList
    if ($script:failStart) { throw "Injected Start-Process failure for launcher helper test." }
    return [PSCustomObject]@{ Id = 99; Handle = [IntPtr]::Zero; StartTime = [DateTime]::UtcNow }
}

$tempRoot = Join-Path $env:TEMP ("preview-launcher-tests-" + [Guid]::NewGuid().ToString("N"))
try {
    [System.Environment]::SetEnvironmentVariable($script:testVariable, "parent-value", "Process")
    $childEnvironment = @{ $script:testVariable = "child-value" }
    $started = Start-ChildServiceProcess `
        -FileName "preview-child.exe" `
        -Arguments @("path with spaces", 'embedded"quote') `
        -WorkingDirectory $env:TEMP `
        -EnvironmentVariables $childEnvironment `
        -StdOutFile "unused.stdout.log" `
        -StdErrFile "unused.stderr.log"

    Assert-Equal "child-value" $script:observedChildValue "Child environment was not applied during spawn."
    Assert-Equal "parent-value" ([System.Environment]::GetEnvironmentVariable($script:testVariable, "Process")) "Parent environment changed after spawn."
    Assert-Equal '"path with spaces" "embedded\"quote"' $script:observedArgumentList "Native argument quoting changed."

    $script:failStart = $true
    try {
        Start-ChildServiceProcess -FileName "preview-child.exe" -Arguments @() -WorkingDirectory $env:TEMP -EnvironmentVariables $childEnvironment -StdOutFile "unused.stdout.log" -StdErrFile "unused.stderr.log" | Out-Null
        throw "Expected injected process start failure."
    } catch {
        if ($_.Exception.Message -ne "Injected Start-Process failure for launcher helper test.") { throw }
    }
    Assert-Equal "parent-value" ([System.Environment]::GetEnvironmentVariable($script:testVariable, "Process")) "Parent environment changed after a failed spawn."

    $dataDirectory = Join-Path $tempRoot "preview data"
    $customStateFile = Join-Path $tempRoot "state\preview.json"
    $previewPaths = Get-PreviewPaths -BackendDirectory (Join-Path $tempRoot "backend") -TargetDirectory (Join-Path $tempRoot "target") -DataDirectory $dataDirectory -StateFile $customStateFile
    Assert-Equal ([System.IO.Path]::GetFullPath($dataDirectory)) $previewPaths.DataDirectory "Preview data directory must be normalized to an absolute path."
    Assert-Equal ([System.IO.Path]::GetFullPath($customStateFile)) $previewPaths.StateFile "Custom state file must be normalized to an absolute path."
    Assert-Equal ([System.IO.Path]::GetFullPath((Join-Path $dataDirectory "drive_mount.json"))) $previewPaths.DriveStateFile "Drive state must be specific to this preview data directory."
    $defaultPaths = Get-PreviewPaths -BackendDirectory (Join-Path $tempRoot "backend") -TargetDirectory (Join-Path $tempRoot "target") -DataDirectory "" -StateFile ""
    Assert-Equal ([System.IO.Path]::GetFullPath((Join-Path $tempRoot "backend\data\preview"))) $defaultPaths.DataDirectory "Default preview data path changed."
    Assert-Equal ([System.IO.Path]::GetFullPath((Join-Path $tempRoot "target\preview_stack.json"))) $defaultPaths.StateFile "Default preview state path changed."
    $contract = Get-PreviewRuntimeContract -ModelMode off -SpringPort 18080 -FastApiPort 18000 -FrontendPort 13000 -DataDirectory $dataDirectory -SyncSecret "should-not-escape"
    Assert-True (-not $contract.StartFastApi) "ModelMode off must not start FastAPI."
    Assert-Equal "SpringBoot,NextFrontend" ($contract.ServiceNames -join ",") "ModelMode off service ownership changed."
    Assert-Equal "http://127.0.0.1:1/api/chat" $contract.FrontendEnvironment["MODEL_API_URL"] "ModelMode off must isolate server-side chat from any unrelated API on port 8000."
    Assert-Equal "http://127.0.0.1:1/api/chat" $contract.FrontendEnvironment["NEXT_PUBLIC_MODEL_API_URL"] "ModelMode off client chat endpoint changed."
    Assert-Equal "" $contract.SpringEnvironment["CATALOG_SYNC_TOKEN"] "ModelMode off must not inherit or create a sync secret."
    Assert-Equal "http://127.0.0.1:1/api/index/sync" $contract.SpringEnvironment["APP_CATALOG_SYNC_URL"] "ModelMode off sync target must be unavailable."
    Assert-True ($contract.SpringEnvironment["SPRING_DATASOURCE_URL"] -match "/preview_db;") "Preview H2 must use its isolated preview_db filename."
    Assert-Equal ([System.IO.Path]::GetFullPath((Join-Path $dataDirectory "committed_catalog_snapshot.json"))) $contract.SpringEnvironment["APP_CATALOG_SNAPSHOT_PATH"] "Catalog snapshot must stay under the preview data directory."
    $offPorts = Get-PreviewPortsToCheck -ModelMode off -SpringPort 18080 -FastApiPort 18000 -FrontendPort 13000
    Assert-Equal "18080,13000" (@($offPorts | ForEach-Object { $_.Port }) -join ",") "ModelMode off must not probe the FastAPI port."

    $lightContract = Get-PreviewRuntimeContract -ModelMode light -SpringPort 18080 -FastApiPort 18000 -FrontendPort 13000 -DataDirectory $dataDirectory -SyncSecret "test-sync-secret"
    Assert-True $lightContract.StartFastApi "Explicit light mode must start FastAPI."
    Assert-Equal "test-sync-secret" $lightContract.SpringEnvironment["CATALOG_SYNC_TOKEN"] "Explicit model mode should retain the supplied sync token in child environment."
    Assert-Equal "http://127.0.0.1:18000/api/chat" $lightContract.FrontendEnvironment["MODEL_API_URL"] "Explicit model mode should route server chat to its selected FastAPI port."
    $springArguments = Get-SpringBootArguments -SpringPort 18080 -DriveMountPoint "X:" -JarFile "backend.jar"
    Assert-True (-not (($springArguments -join " ").Contains("test-sync-secret"))) "The sync secret must stay out of Java command-line arguments."
    Assert-Equal "18000,18080,13000" (@((Get-PreviewPortsToCheck -ModelMode full -SpringPort 18080 -FastApiPort 18000 -FrontendPort 13000) | ForEach-Object { $_.Port }) -join ",") "Explicit model modes must preflight FastAPI."

    $buildId = Join-Path $tempRoot ".next\BUILD_ID"
    $standaloneServer = Join-Path $tempRoot ".next\standalone\server.js"
    $buildEnvironmentFile = Join-Path $tempRoot ".next\preview-build-env.json"
    $sourceDir = Join-Path $tempRoot "app"
    New-Item -ItemType Directory -Path $sourceDir -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path $buildId -Parent) -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path $standaloneServer -Parent) -Force | Out-Null
    Set-Content -LiteralPath $buildId -Value "build" -NoNewline
    Set-Content -LiteralPath $standaloneServer -Value "server" -NoNewline
    Set-Content -LiteralPath $buildEnvironmentFile -Value '{"SpringBootApiUrl":"http://127.0.0.1:18080/api"}' -NoNewline
    $sourceFile = Join-Path $sourceDir "page.tsx"
    Set-Content -LiteralPath $sourceFile -Value "source" -NoNewline
    $buildTime = [DateTime]::UtcNow.AddHours(-2)
    [System.IO.File]::SetLastWriteTimeUtc($buildId, $buildTime)
    [System.IO.File]::SetLastWriteTimeUtc($standaloneServer, $buildTime)
    [System.IO.File]::SetLastWriteTimeUtc($sourceFile, $buildTime.AddHours(-1))
    $buildEnvironment = '{"SpringBootApiUrl":"http://127.0.0.1:18080/api"}'
    Assert-True (-not (Test-FrontendBuildStale -FrontendDirectory $tempRoot -BuildIdPath $buildId -StandaloneServerPath $standaloneServer -BuildEnvironmentFile $buildEnvironmentFile -ExpectedBuildEnvironment $buildEnvironment)) "A current standalone build should be reusable."
    Assert-True (Test-FrontendBuildStale -FrontendDirectory $tempRoot -BuildIdPath $buildId -StandaloneServerPath $standaloneServer -BuildEnvironmentFile $buildEnvironmentFile -ExpectedBuildEnvironment '{"SpringBootApiUrl":"http://127.0.0.1:8080/api"}') "Changing the public API URL must trigger a build with the matching client bundle."
    [System.IO.File]::SetLastWriteTimeUtc($sourceFile, [DateTime]::UtcNow)
    Assert-True (Test-FrontendBuildStale -FrontendDirectory $tempRoot -BuildIdPath $buildId -StandaloneServerPath $standaloneServer -BuildEnvironmentFile $buildEnvironmentFile -ExpectedBuildEnvironment $buildEnvironment) "Newer frontend source must trigger a rebuild."
    Remove-Item -LiteralPath $standaloneServer -Force
    Assert-True (Test-FrontendBuildStale -FrontendDirectory $tempRoot -BuildIdPath $buildId -StandaloneServerPath $standaloneServer -BuildEnvironmentFile $buildEnvironmentFile -ExpectedBuildEnvironment $buildEnvironment) "Missing standalone server must trigger a build."

    $expectedPath = Join-Path $env:TEMP "owned-preview-process.exe"
    $creationDate = [DateTime]::UtcNow
    $ownedRecord = @{ PID = 12345; StartTime = $creationDate.ToString("o"); ExecutablePath = $expectedPath }
    $matchingProcess = [PSCustomObject]@{ ProcessId = 12345; CreationDate = $creationDate; ExecutablePath = $expectedPath }
    Assert-True (Test-RecordedProcessIdentity -Process $matchingProcess -Record $ownedRecord) "Recorded PID, executable, and start time should match."
    $wrongPathProcess = [PSCustomObject]@{ ProcessId = 12345; CreationDate = $creationDate; ExecutablePath = (Join-Path $env:TEMP "unowned-process.exe") }
    Assert-True (-not (Test-RecordedProcessIdentity -Process $wrongPathProcess -Record $ownedRecord)) "Cleanup must reject a reused PID with a different executable."
    $wrongTimeProcess = [PSCustomObject]@{ ProcessId = 12345; CreationDate = $creationDate.AddSeconds(5); ExecutablePath = $expectedPath }
    Assert-True (-not (Test-RecordedProcessIdentity -Process $wrongTimeProcess -Record $ownedRecord)) "Cleanup must reject a reused PID with a different creation time."

    $missingState = Join-Path $tempRoot "missing.json"
    & $stopperPath -StateFile $missingState | Out-Null
    Assert-True (-not (Test-Path -LiteralPath $missingState)) "Stopping a missing state file must not create or touch a state file."
    $corruptState = Join-Path $tempRoot "corrupt.json"
    Set-Content -LiteralPath $corruptState -Value "{not-json" -NoNewline
    $refused = $false
    try { & $stopperPath -StateFile $corruptState | Out-Null } catch { $refused = $true }
    Assert-True $refused "Unsafe stop must report failure, not a successful exit."
    Assert-True (Test-Path -LiteralPath $corruptState) "Stopping a corrupt state file must preserve it and fail closed."
    $badSchemaState = Join-Path $tempRoot "bad-schema.json"
    Set-Content -LiteralPath $badSchemaState -Value (@{ Status = "READY" } | ConvertTo-Json) -NoNewline
    $refused = $false
    try { & $stopperPath -StateFile $badSchemaState | Out-Null } catch { $refused = $true }
    Assert-True $refused "Unsafe stop must report failure, not a successful exit."
    Assert-True (Test-Path -LiteralPath $badSchemaState) "Stopping a state file without ownership fields must preserve it and fail closed."
    $unownedDriveState = Join-Path $tempRoot "unowned-drive.json"
    Set-Content -LiteralPath $unownedDriveState -Value (@{ Processes = @(); DriveMounted = $true } | ConvertTo-Json -Depth 3) -NoNewline
    $refused = $false
    try { & $stopperPath -StateFile $unownedDriveState | Out-Null } catch { $refused = $true }
    Assert-True $refused "Unsafe stop must report failure, not a successful exit."
    Assert-True (Test-Path -LiteralPath $unownedDriveState) "Stop must preserve an incomplete Drive ownership record instead of using a shared default mount state."

    Write-Host "PASS: launcher helpers enforce off/light/full branching, preview-only data paths, standalone build freshness, secret isolation, and process ownership."
} finally {
    [System.Environment]::SetEnvironmentVariable($script:testVariable, $originalValue, "Process")
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
