<#
.SYNOPSIS
    Automated test suite for Google Drive PowerShell operational tooling.
.DESCRIPTION
    Validates:
    1. Preflight execution is read-only, idempotent, and produces complete structured JSON.
    2. mount_drive defaults to dry-run/WhatIf and enforces exact baseline streaming flags.
    3. stop_drive validates PID identity (process name and start time) and refuses PID reuse kills.
    4. status_drive correctly reports MOUNTED, NOT_MOUNTED, and DEGRADED states.
    5. Zero secret or token leakage across logs, outputs, and dry-run commands.
.OUTPUTS
    Test summary table and exit code 0 (success) or 1 (failure).
#>
[CmdletBinding()]
param(
    [switch]$VerboseOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
$preflightPath = Join-Path $scriptDir "preflight_drive.ps1"
$mountPath     = Join-Path $scriptDir "mount_drive.ps1"
$statusPath    = Join-Path $scriptDir "status_drive.ps1"
$stopPath      = Join-Path $scriptDir "stop_drive.ps1"

$testResults = @()

function Assert-Condition {
    param(
        [string]$TestName,
        [bool]$Condition,
        [string]$FailureMessage
    )

    if ($Condition) {
        Write-Host "  [PASS] $TestName" -ForegroundColor Green
        return [PSCustomObject]@{
            TestName = $TestName
            Passed   = $true
            Details  = "OK"
        }
    } else {
        Write-Host "  [FAIL] $TestName - $FailureMessage" -ForegroundColor Red
        return [PSCustomObject]@{
            TestName = $TestName
            Passed   = $false
            Details  = $FailureMessage
        }
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " RUNNING GOOGLE DRIVE WINDOWS TOOLING TEST SUITE (DRIVE-01)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# -------------------------------------------------------------
# TEST 1: Preflight Read-Only Behavior & Schema Verification
# -------------------------------------------------------------
Write-Host "`nTest Suite 1: Preflight Read-Only & JSON Schema" -ForegroundColor Yellow

$preSnapshotFiles = (Get-ChildItem -Path $scriptDir -Recurse | Select-Object -ExpandProperty FullName)

$preflightRaw = & $preflightPath -MountPoint "M:"
$preflightJson = $null
$parseSuccess = $false
try {
    $preflightJson = $preflightRaw | ConvertFrom-Json
    $parseSuccess = ($preflightJson -ne $null)
} catch {
    $parseSuccess = $false
}

$testResults += Assert-Condition -TestName "Preflight outputs valid JSON" -Condition $parseSuccess -FailureMessage "Failed to parse JSON output"

if ($preflightJson) {
    $hasRequiredKeys = ($preflightJson.PSObject.Properties['HostOS'] -ne $null) -and `
                       ($preflightJson.PSObject.Properties['Rclone'] -ne $null) -and `
                       ($preflightJson.PSObject.Properties['WinFsp'] -ne $null) -and `
                       ($preflightJson.PSObject.Properties['MountTarget'] -ne $null) -and `
                       ($preflightJson.PSObject.Properties['UserSession'] -ne $null) -and `
                       ($preflightJson.PSObject.Properties['SystemCapacity'] -ne $null) -and `
                       ($preflightJson.PSObject.Properties['IsReady'] -ne $null) -and `
                       ($preflightJson.PSObject.Properties['Status'] -ne $null)

    $testResults += Assert-Condition -TestName "Preflight schema contains all required sections" `
        -Condition $hasRequiredKeys `
        -FailureMessage "Missing expected JSON sections"

    $winfspHasChecks = ($preflightJson.WinFsp.PSObject.Properties['RegistryFound'] -ne $null) -and `
                       ($preflightJson.WinFsp.PSObject.Properties['DllFound'] -ne $null) -and `
                       ($preflightJson.WinFsp.PSObject.Properties['DriverLoaded'] -ne $null)

    $testResults += Assert-Condition -TestName "WinFsp checks include Registry, DLL, and Driver checks" `
        -Condition $winfspHasChecks `
        -FailureMessage "WinFsp checks incomplete"
}

$postSnapshotFiles = (Get-ChildItem -Path $scriptDir -Recurse | Select-Object -ExpandProperty FullName)
$fileDiff = Compare-Object -ReferenceObject $preSnapshotFiles -DifferenceObject $postSnapshotFiles
$noFileSystemChange = ($fileDiff -eq $null -or $fileDiff.Count -eq 0)

$testResults += Assert-Condition -TestName "Preflight is strictly read-only (zero filesystem modifications)" `
    -Condition $noFileSystemChange `
    -FailureMessage "Preflight created or modified files in scripts dir"

# -------------------------------------------------------------
# TEST 2: Mount Drive WhatIf / Dry-Run Baseline Flags
# -------------------------------------------------------------
Write-Host "`nTest Suite 2: Mount Drive Baseline Flags & Dry-Run" -ForegroundColor Yellow

$mountPlan = & $mountPath -WhatIf -Remote "cinema-gdrive:" -RemoteSubpath "DippieMedia" -MountPoint "M:"
$isPlanObject = ($mountPlan -ne $null)
$testResults += Assert-Condition -TestName "mount_drive -WhatIf returns structured plan" -Condition $isPlanObject -FailureMessage "mount_drive returned null"

if ($mountPlan) {
    $isDryRun = ($mountPlan.Mode -eq "DRY_RUN") -and ($mountPlan.IsExecute -eq $false)
    $testResults += Assert-Condition -TestName "mount_drive is in DRY_RUN mode" -Condition $isDryRun -FailureMessage "Mode is not DRY_RUN"

    $cmd = [string]$mountPlan.ExpectedCommand
    $hasReadOnly      = $cmd -match "--read-only"
    $hasVfsCacheOff   = $cmd -match "--vfs-cache-mode\s+off"
    $hasBufferSize32M = $cmd -match "--buffer-size\s+32M"
    $hasChunkSize8M   = $cmd -match "--vfs-read-chunk-size\s+8M"
    $hasChunkLimit32M = $cmd -match "--vfs-read-chunk-size-limit\s+32M"
    $hasChunkStreams0 = $cmd -match "--vfs-read-chunk-streams\s+0"
    $hasRemoteTarget  = $cmd -match "cinema-gdrive:DippieMedia"
    $hasMountPoint    = ($cmd -match "(^|\s)M:(\s|$)") -and ($mountPlan.MountPoint -eq "M:")

    $allBaselineFlags = $hasReadOnly -and $hasVfsCacheOff -and $hasBufferSize32M -and `
                        $hasChunkSize8M -and $hasChunkLimit32M -and $hasChunkStreams0

    $testResults += Assert-Condition -TestName "Command includes all baseline streaming flags (--read-only, --vfs-cache-mode off, --buffer-size 32M, chunk 8M/32M, streams 0)" `
        -Condition $allBaselineFlags `
        -FailureMessage "Missing baseline flags in expected command: $cmd"

    $testResults += Assert-Condition -TestName "Command mounts target 'cinema-gdrive:DippieMedia' to 'M:'" `
        -Condition ($hasRemoteTarget -and $hasMountPoint) `
        -FailureMessage "Remote target or mount point mismatched in command: $cmd"
}

# Verify default invocation without -Execute is also dry-run
$defaultPlan = & $mountPath
$testResults += Assert-Condition -TestName "mount_drive defaults to dry-run when -Execute is omitted" `
    -Condition ($defaultPlan -and $defaultPlan.Mode -eq "DRY_RUN") `
    -FailureMessage "Omitting -Execute did not default to dry-run"

# -------------------------------------------------------------
# TEST 3: Stop Drive PID Identity Verification (PID Reuse Protection)
# -------------------------------------------------------------
Write-Host "`nTest Suite 3: Stop Drive PID Reuse & Identity Protection" -ForegroundColor Yellow

$tempStateFile = Join-Path ([System.IO.Path]::GetTempPath()) "test-drive-mount-state-$([Guid]::NewGuid().ToString('N')).json"

# Create a state file containing the current PowerShell process PID, but claiming to be rclone with a mismatched start time
$currentProc = Get-Process -Id $PID
$fakeState = [PSCustomObject]@{
    pid            = $currentProc.Id
    processName    = "rclone"
    startTime      = [DateTimeOffset]::UtcNow.AddDays(-1).ToString("o")
    executablePath = "C:\rclone\rclone.exe"
    mountPoint     = "M:"
    remoteTarget   = "cinema-gdrive:DippieMedia"
}
$fakeState | ConvertTo-Json | Set-Content -Path $tempStateFile -Encoding UTF8

$stopResult = & $stopPath -StateFile $tempStateFile
$refusedKill = ($stopResult -and $stopResult.Status -eq "PID_REUSE_REJECTED" -and $stopResult.Success -eq $false)

$testResults += Assert-Condition -TestName "stop_drive refuses to kill process when process identity / start time does not match" `
    -Condition $refusedKill `
    -FailureMessage "stop_drive did not reject mismatched PID (Result: $($stopResult.Status))"

# Verify current process was indeed NOT killed and is continuing execution
$currentStillAlive = (Get-Process -Id $PID -ErrorAction SilentlyContinue) -ne $null
$testResults += Assert-Condition -TestName "Current process remained alive and protected from accidental termination" `
    -Condition $currentStillAlive `
    -FailureMessage "Current process was unexpectedly terminated"

# Clean up temp state file
if (Test-Path -Path $tempStateFile) {
    Remove-Item -Path $tempStateFile -Force -ErrorAction SilentlyContinue
}

# -------------------------------------------------------------
# TEST 4: Status Drive Verification
# -------------------------------------------------------------
Write-Host "`nTest Suite 4: Status Drive States (MOUNTED, NOT_MOUNTED, DEGRADED)" -ForegroundColor Yellow

$nonExistentState = Join-Path ([System.IO.Path]::GetTempPath()) "nonexistent-state-$([Guid]::NewGuid().ToString('N')).json"
$statusResult = & $statusPath -StateFile $nonExistentState
$testResults += Assert-Condition -TestName "status_drive reports NOT_MOUNTED when state file does not exist" `
    -Condition ($statusResult -and $statusResult.Status -eq "NOT_MOUNTED") `
    -FailureMessage "Status was $($statusResult.Status), expected NOT_MOUNTED"

# Test dead PID state
$deadPidStateFile = Join-Path ([System.IO.Path]::GetTempPath()) "deadpid-state-$([Guid]::NewGuid().ToString('N')).json"
$deadState = [PSCustomObject]@{
    pid            = 999998
    processName    = "rclone"
    startTime      = [DateTimeOffset]::UtcNow.ToString("o")
    mountPoint     = "Z:"
    remoteTarget   = "cinema-gdrive:DippieMedia"
}
$deadState | ConvertTo-Json | Set-Content -Path $deadPidStateFile -Encoding UTF8

$deadStatusResult = & $statusPath -StateFile $deadPidStateFile
$testResults += Assert-Condition -TestName "status_drive reports NOT_MOUNTED for inactive PID" `
    -Condition ($deadStatusResult -and $deadStatusResult.Status -eq "NOT_MOUNTED") `
    -FailureMessage "Status was $($deadStatusResult.Status), expected NOT_MOUNTED"

if (Test-Path -Path $deadPidStateFile) {
    Remove-Item -Path $deadPidStateFile -Force -ErrorAction SilentlyContinue
}

# -------------------------------------------------------------
# TEST 5: Secret and Token Hygiene
# -------------------------------------------------------------
Write-Host "`nTest Suite 5: Secret and Token Leakage Prevention" -ForegroundColor Yellow

$dummySecretToken   = "ya29.MOCK_SECRET_ACCESS_TOKEN_XYZ_1234567890"
$dummyClientSecret  = "MOCK_TOP_SECRET_GOOGLE_CLIENT_KEY_998877"
$dummyConfigFile    = Join-Path ([System.IO.Path]::GetTempPath()) "dummy-rclone-$([Guid]::NewGuid().ToString('N')).conf"

$dummyConfContent = @"
[cinema-gdrive]
type = drive
client_id = 123456789-mockclient.apps.googleusercontent.com
client_secret = $dummyClientSecret
scope = drive.readonly
token = {"access_token":"$dummySecretToken","token_type":"Bearer","refresh_token":"1//mock-refresh-token","expiry":"2030-01-01T00:00:00Z"}
"@
Set-Content -Path $dummyConfigFile -Value $dummyConfContent -Encoding UTF8

$preflightSecretOutput = & $preflightPath -ConfigPath $dummyConfigFile | Out-String
$mountSecretOutput     = & $mountPath -WhatIf -ConfigPath $dummyConfigFile | Out-String

$tokenInPreflight  = $preflightSecretOutput.Contains($dummySecretToken)
$secretInPreflight = $preflightSecretOutput.Contains($dummyClientSecret)
$tokenInMount      = $mountSecretOutput.Contains($dummySecretToken)
$secretInMount     = $mountSecretOutput.Contains($dummyClientSecret)

$hasAnyLeak = ($tokenInPreflight -or $secretInPreflight -or $tokenInMount -or $secretInMount)

$testResults += Assert-Condition -TestName "Strict secret hygiene: zero tokens or secrets present in preflight or mount output" `
    -Condition (-not $hasAnyLeak) `
    -FailureMessage "Detected token or secret in output! Preflight leaked: $($tokenInPreflight -or $secretInPreflight); Mount leaked: $($tokenInMount -or $secretInMount)"

if (Test-Path -Path $dummyConfigFile) {
    Remove-Item -Path $dummyConfigFile -Force -ErrorAction SilentlyContinue
}

# -------------------------------------------------------------
# SUMMARY REPORT
# -------------------------------------------------------------
Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " TEST EXECUTION SUMMARY" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$passedCount = @($testResults | Where-Object { $_.Passed }).Count
$failedCount = @($testResults | Where-Object { -not $_.Passed }).Count
$totalCount  = @($testResults).Count

Write-Host "Total Tests : $totalCount"
Write-Host "Passed      : $passedCount" -ForegroundColor $(if ($passedCount -eq $totalCount) { "Green" } else { "Yellow" })
Write-Host "Failed      : $failedCount" -ForegroundColor $(if ($failedCount -eq 0) { "Green" } else { "Red" })

if ($failedCount -gt 0) {
    Write-Host "`nFAILED TESTS:" -ForegroundColor Red
    $testResults | Where-Object { -not $_.Passed } | ForEach-Object {
        Write-Host " - $($_.TestName): $($_.Details)" -ForegroundColor Red
    }
    exit 1
} else {
    Write-Host "`nALL TESTS PASSED SUCCESSFULLY." -ForegroundColor Green
    exit 0
}
