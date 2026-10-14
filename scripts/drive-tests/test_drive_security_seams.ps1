<#
.SYNOPSIS
    Security and safety seam verification for Google Drive Windows tooling.
.DESCRIPTION
    Validates:
    1. Secret & Credential Hygiene:
       - Confirms preflight_drive.ps1, mount_drive.ps1, status_drive.ps1, and stop_drive.ps1
         never leak OAuth2 access tokens, refresh tokens, client secrets, passwords, or
         private keys across stdout, stderr, pipeline objects, or JSON serialization.
    2. PID Reuse & Process Identity Protection:
       - Verifies stop_drive.ps1 strictly validates PID identity against ProcessName and
         process StartTime before issuing any termination signals.
       - Tests refusal to terminate non-rclone active processes (e.g. powershell/pwsh/system)
         with Status = 'PID_REUSE_REJECTED'.
       - Tests refusal to terminate processes with mismatched start times.
       - Tests clean state cleanup for non-existent / dead PIDs with Status = 'ALREADY_STOPPED'.
       - Tests status_drive.ps1 diagnostic reporting of DEGRADED when PID reuse is detected.
       - Tests handling of missing, empty, and corrupted state files.
.OUTPUTS
    Console test execution report, exit code 0/1, and structured JSON evidence in
    docs/reports/drive/DRIVE_01/agent-e/toolkit_test_evidence.json.
#>
[CmdletBinding()]
param(
    [string]$EvidencePath,
    [switch]$VerboseOutput,
    [switch]$NoExit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Ensure UTF-8 output encoding across Windows PowerShell 5.1 and PowerShell 7
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}
$OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = $PSScriptRoot
$toolkitDir = (Resolve-Path (Join-Path $scriptDir "..\drive")).Path
$preflightPath = Join-Path $toolkitDir "preflight_drive.ps1"
$mountPath     = Join-Path $toolkitDir "mount_drive.ps1"
$statusPath    = Join-Path $toolkitDir "status_drive.ps1"
$stopPath      = Join-Path $toolkitDir "stop_drive.ps1"

if (-not $EvidencePath) {
    $f02EvidenceDir = Join-Path $scriptDir "..\..\docs\reports\drive\DRIVE_01_F02\agent-e"
    if (Test-Path -Path (Split-Path -Path $f02EvidenceDir -Parent) -PathType Container) {
        $EvidencePath = Join-Path $f02EvidenceDir "toolkit_test_evidence.json"
    } else {
        $EvidencePath = Join-Path $scriptDir "..\..\docs\reports\drive\DRIVE_01\agent-e\toolkit_test_evidence.json"
    }
}

# Verify toolkit scripts exist
$missingFiles = @()
foreach ($f in @($preflightPath, $mountPath, $statusPath, $stopPath)) {
    if (-not (Test-Path -Path $f -PathType Leaf)) {
        $missingFiles += $f
    }
}
if ($missingFiles.Count -gt 0) {
    throw "Required toolkit scripts not found: $($missingFiles -join ', ')"
}

$suiteStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$results = [System.Collections.Generic.List[PSCustomObject]]::new()

function Register-TestResult {
    param(
        [string]$TestId,
        [string]$Category,
        [string]$Name,
        [string]$Description,
        [bool]$Passed,
        [string]$FailureMessage = "",
        [object]$Expected = $null,
        [object]$Actual = $null,
        [double]$DurationMs = 0
    )

    if ($Passed) {
        $FailureMessage = ""
    }

    $obj = [PSCustomObject]@{
        TestId         = $TestId
        Category       = $Category
        Name           = $Name
        Description    = $Description
        Passed         = $Passed
        FailureMessage = $FailureMessage
        Expected       = $Expected
        Actual         = $Actual
        DurationMs     = [math]::Round($DurationMs, 2)
    }

    $results.Add($obj)

    if ($Passed) {
        Write-Host "  [PASS] $TestId : $Name ($([math]::Round($DurationMs, 1)) ms)" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] $TestId : $Name" -ForegroundColor Red
        Write-Host "         Reason: $FailureMessage" -ForegroundColor DarkRed
        if ($Expected -ne $null) { Write-Host "         Expected: $Expected" -ForegroundColor DarkGray }
        if ($Actual -ne $null)   { Write-Host "         Actual:   $Actual" -ForegroundColor DarkGray }
    }
}

# Helper to recursively inspect object graph for forbidden secret strings
function Test-ObjectContainsSecrets {
    param(
        [object]$TargetObject,
        [string[]]$SecretList,
        [int]$Depth = 0
    )

    if ($TargetObject -eq $null -or $Depth -gt 20) { return $false }

    # If string
    if ($TargetObject -is [string]) {
        foreach ($sec in $SecretList) {
            if ($TargetObject.Contains($sec)) {
                return $true
            }
        }
        return $false
    }

    # ValueTypes (int, bool, double, DateTime, etc.) cannot contain secret strings
    if ($TargetObject -is [System.ValueType]) {
        return $false
    }

    # If array or collection
    if ($TargetObject -is [System.Collections.IEnumerable] -and -not ($TargetObject -is [hashtable])) {
        foreach ($item in $TargetObject) {
            if (Test-ObjectContainsSecrets -TargetObject $item -SecretList $SecretList -Depth ($Depth + 1)) {
                return $true
            }
        }
        return $false
    }

    # If PSCustomObject or object with properties
    if ($TargetObject.PSObject -and $TargetObject.PSObject.Properties) {
        foreach ($prop in $TargetObject.PSObject.Properties) {
            if ($prop.Value) {
                if (Test-ObjectContainsSecrets -TargetObject $prop.Value -SecretList $SecretList -Depth ($Depth + 1)) {
                    return $true
                }
            }
        }
    }

    return $false
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " AGENT E: SECURITY SEAMS & PID SAFETY VERIFICATION (DRIVE-01)" -ForegroundColor Cyan
Write-Host " Target Toolkit : $toolkitDir" -ForegroundColor Cyan
Write-Host " Target Evidence: $EvidencePath" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

# ==============================================================================
# SUITE 1: Secret Hygiene & Credential Protection
# ==============================================================================
Write-Host "`n--- [SUITE 1] Secret Hygiene: Zero Credential Exposure ---" -ForegroundColor Yellow

$mockAccessToken   = "ya29.a0AfH6SM_SEAM_TEST_ACCESS_TOKEN_XYZ987654321_SUPER_SECRET"
$mockRefreshToken  = "1//04seam_test_refresh_token_complex_1234567890abcdef"
$mockClientSecret  = "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erification998877"
$mockPassword      = "secret_cleartext_password_should_never_leak_99"
$mockPrivateKey    = "-----BEGIN RSA PRIVATE KEY-----MOCK_KEY_DATA-----END RSA PRIVATE KEY-----"

$allSecrets = @(
    $mockAccessToken,
    $mockRefreshToken,
    $mockClientSecret,
    $mockPassword,
    $mockPrivateKey
)

$tempConfigPath = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-secret-test-$([Guid]::NewGuid().ToString('N')).conf"

$mockConfigContent = @"
[cinema-gdrive]
type = drive
client_id = 987654321000-movie-rcm-client.apps.googleusercontent.com
client_secret = $mockClientSecret
scope = drive.readonly
token = {"access_token":"$mockAccessToken","token_type":"Bearer","refresh_token":"$mockRefreshToken","expiry":"2035-12-31T23:59:59Z"}
password = $mockPassword
service_account_credentials = $mockPrivateKey
team_drive = 0ABCdef123456789
"@

Set-Content -Path $tempConfigPath -Value $mockConfigContent -Encoding UTF8

try {
    # Test 1.1: preflight_drive.ps1 raw output stream scanning
    $t1Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $preflightRawOut = & $preflightPath -ConfigPath $tempConfigPath | Out-String
    $t1Sw.Stop()

    $leakedInPreflightString = @()
    foreach ($sec in $allSecrets) {
        if ($preflightRawOut.Contains($sec)) {
            $leakedInPreflightString += $sec
        }
    }

    $p1Passed = ($leakedInPreflightString.Count -eq 0)
    Register-TestResult -TestId "TC-SEC-01" -Category "SecretHygiene" `
        -Name "preflight_drive raw stdout does not leak tokens or credentials" `
        -Description "Scans preflight_drive stdout stream to confirm zero credential leakage" `
        -Passed $p1Passed `
        -FailureMessage "Leaked in stdout: $($leakedInPreflightString -join ', ')" `
        -Expected "Zero occurrences" -Actual "$($leakedInPreflightString.Count) occurrences" `
        -DurationMs $t1Sw.Elapsed.TotalMilliseconds

    # Test 1.2: preflight_drive.ps1 object graph deep inspection
    $t2Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $preflightObj = $preflightRawOut | ConvertFrom-Json
    $hasSecretInObject = Test-ObjectContainsSecrets -TargetObject $preflightObj -SecretList $allSecrets
    $t2Sw.Stop()

    $configSafe = ($preflightObj.RcloneConfigFile.FileExists -eq $true) -and `
                  ($preflightObj.RcloneConfigFile.FileSizeBytes -gt 0) -and `
                  ($preflightObj.RcloneConfigFile.IsSafe -eq $true)

    $p2Passed = (-not $hasSecretInObject -and $configSafe)
    Register-TestResult -TestId "TC-SEC-02" -Category "SecretHygiene" `
        -Name "preflight_drive parsed JSON object graph contains zero secret properties" `
        -Description "Deep recursive property scan of preflight JSON object confirms no secret tokens retained" `
        -Passed $p2Passed `
        -FailureMessage "Secret found in object graph or RcloneConfigFile safety check failed" `
        -Expected "Zero secrets in object graph, IsSafe=True" `
        -Actual "SecretsInObject=$hasSecretInObject, ConfigSafe=$configSafe" `
        -DurationMs $t2Sw.Elapsed.TotalMilliseconds

    # Test 1.3: mount_drive.ps1 -WhatIf output scanning
    $t3Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $mountPlan = & $mountPath -WhatIf -ConfigPath $tempConfigPath -Remote "cinema-gdrive:"
    $mountPlanString = $mountPlan | Out-String
    $t3Sw.Stop()

    $hasSecretInMountObj = Test-ObjectContainsSecrets -TargetObject $mountPlan -SecretList $allSecrets
    $hasSecretInMountStr = $false
    foreach ($sec in $allSecrets) {
        if ($mountPlanString.Contains($sec)) { $hasSecretInMountStr = $true; break }
    }

    $p3Passed = (-not $hasSecretInMountObj -and -not $hasSecretInMountStr)
    Register-TestResult -TestId "TC-SEC-03" -Category "SecretHygiene" `
        -Name "mount_drive -WhatIf plan contains zero tokens or secrets" `
        -Description "Validates mount plan object and ExpectedCommand do not dump tokens or secret keys" `
        -Passed $p3Passed `
        -FailureMessage "Detected credential leak in mount_drive dry-run plan" `
        -Expected "Zero secrets in mount plan" `
        -Actual "SecretsInObject=$hasSecretInMountObj, SecretsInString=$hasSecretInMountStr" `
        -DurationMs $t3Sw.Elapsed.TotalMilliseconds

    # Test 1.4: mount_drive.ps1 -AsJson serialization scanning
    $t4Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $mountJsonRaw = & $mountPath -WhatIf -AsJson -ConfigPath $tempConfigPath -Remote "cinema-gdrive:"
    $t4Sw.Stop()

    $leakedInMountJson = @()
    foreach ($sec in $allSecrets) {
        if ($mountJsonRaw.Contains($sec)) {
            $leakedInMountJson += $sec
        }
    }

    $p4Passed = ($leakedInMountJson.Count -eq 0)
    Register-TestResult -TestId "TC-SEC-04" -Category "SecretHygiene" `
        -Name "mount_drive -AsJson JSON string output contains zero tokens or secrets" `
        -Description "Validates serialized JSON output does not leak secrets" `
        -Passed $p4Passed `
        -FailureMessage "Leaked in JSON: $($leakedInMountJson -join ', ')" `
        -Expected "Zero occurrences" -Actual "$($leakedInMountJson.Count) occurrences" `
        -DurationMs $t4Sw.Elapsed.TotalMilliseconds

    # Test 1.5: Error stream leakage protection
    $t5Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $nonExistentConfig = "C:\NonExistent\rclone-secret-$mockAccessToken.conf"
    $preflightErrOutput = & $preflightPath -ConfigPath $nonExistentConfig 2>&1 | Out-String
    $t5Sw.Stop()

    $preflightObjErr = $preflightErrOutput | ConvertFrom-Json
    $fileDoesNotExist = ($preflightObjErr.RcloneConfigFile.FileExists -eq $false)

    Register-TestResult -TestId "TC-SEC-05" -Category "SecretHygiene" `
        -Name "Missing config path handled gracefully without exception stack dumps" `
        -Description "Confirms missing config path gracefully marks FileExists=False without dumping raw traces" `
        -Passed $fileDoesNotExist `
        -FailureMessage "Config safety check failed on missing file" `
        -Expected "FileExists=False" -Actual "FileExists=$($preflightObjErr.RcloneConfigFile.FileExists)" `
        -DurationMs $t5Sw.Elapsed.TotalMilliseconds
} finally {
    if (Test-Path -Path $tempConfigPath) {
        Remove-Item -Path $tempConfigPath -Force -ErrorAction SilentlyContinue
    }
}

# ==============================================================================
# SUITE 2: PID Reuse Safety & Process Identity Verification
# ==============================================================================
Write-Host "`n--- [SUITE 2] PID Reuse Safety & Process Identity Verification ---" -ForegroundColor Yellow

$currentProcess = Get-Process -Id $PID

# Test 2.1: PID Reuse - Refuse to kill active PowerShell / system process (ProcessName mismatch)
$t6Sw = [System.Diagnostics.Stopwatch]::StartNew()
$pidMismatchStateFile = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-pid-mismatch-$([Guid]::NewGuid().ToString('N')).json"
try {
    # Create fake state recording current PowerShell process, but with actual process name powershell/pwsh
    $fakeState = [PSCustomObject]@{
        pid            = $currentProcess.Id
        processName    = "rclone"
        startTime      = $currentProcess.StartTime.ToString("o")
        executablePath = "C:\rclone\rclone.exe"
        mountPoint     = "M:"
        remoteTarget   = "cinema-gdrive:DippieMedia"
    }
    $fakeState | ConvertTo-Json | Set-Content -Path $pidMismatchStateFile -Encoding UTF8

    $stopRes1 = & $stopPath -StateFile $pidMismatchStateFile
    $t6Sw.Stop()

    $rejected = ($stopRes1.Success -eq $false) -and ($stopRes1.Status -in @("PID_REUSE_REJECTED", "IDENTITY_MISMATCH"))
    $hasSafetyMsg = ($stopRes1.Message -match "Refusing to kill PID|Process identity mismatch|PID reuse detected|Identity verification failed")
    $currentStillAlive = (Get-Process -Id $PID -ErrorAction SilentlyContinue) -ne $null
    $statePreserved = Test-Path -Path $pidMismatchStateFile -PathType Leaf

    $p6Passed = ($rejected -and $hasSafetyMsg -and $currentStillAlive -and $statePreserved)
    $msg = if (-not $p6Passed) { "Failed to reject kill on process name mismatch. Status: $($stopRes1.Status)" } else { "" }
    Register-TestResult -TestId "TC-PID-01" -Category "PIDSafety" `
        -Name "stop_drive refuses to kill active process on ProcessName mismatch (Status: PID_REUSE_REJECTED)" `
        -Description "Validates stop_drive detects active process is not rclone, aborts termination, and keeps state file for audit" `
        -Passed $p6Passed -FailureMessage $msg `
        -Expected "Status=PID_REUSE_REJECTED, Success=False, Process Alive=True" `
        -Actual "Status=$($stopRes1.Status), Success=$($stopRes1.Success), Process Alive=$currentStillAlive" `
        -DurationMs $t6Sw.Elapsed.TotalMilliseconds
} finally {
    if (Test-Path -Path $pidMismatchStateFile) {
        Remove-Item -Path $pidMismatchStateFile -Force -ErrorAction SilentlyContinue
    }
}

# Test 2.2: PID Reuse - Refuse to kill when claimed processName is 'rclone' but actual process is NOT rclone
$t7Sw = [System.Diagnostics.Stopwatch]::StartNew()
$claimedRcloneStateFile = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-claimed-rclone-$([Guid]::NewGuid().ToString('N')).json"
try {
    # State file claims processName is rclone, but PID points to current PowerShell/pwsh process
    $fakeClaimedState = [PSCustomObject]@{
        pid            = $currentProcess.Id
        processName    = "rclone"
        startTime      = $currentProcess.StartTime.ToString("o")
        executablePath = "C:\rclone\rclone.exe"
        mountPoint     = "M:"
        remoteTarget   = "cinema-gdrive:DippieMedia"
    }
    $fakeClaimedState | ConvertTo-Json | Set-Content -Path $claimedRcloneStateFile -Encoding UTF8

    $stopRes2 = & $stopPath -StateFile $claimedRcloneStateFile
    $t7Sw.Stop()

    $rejected2 = ($stopRes2.Success -eq $false) -and ($stopRes2.Status -eq "PID_REUSE_REJECTED")
    $actualNameReported = ($stopRes2.ActualName -match "powershell|pwsh")
    $currentStillAlive2 = (Get-Process -Id $PID -ErrorAction SilentlyContinue) -ne $null

    $p7Passed = ($rejected2 -and $actualNameReported -and $currentStillAlive2)
    $msg = if (-not $p7Passed) { "Failed to detect fake rclone process identity" } else { "" }
    Register-TestResult -TestId "TC-PID-02" -Category "PIDSafety" `
        -Name "stop_drive inspects actual active process name, ignoring spoofed state processName" `
        -Description "Validates stop_drive queries OS for actual process name rather than trusting state JSON processName" `
        -Passed $p7Passed -FailureMessage $msg `
        -Expected "Status=PID_REUSE_REJECTED, ActualName=powershell/pwsh" `
        -Actual "Status=$($stopRes2.Status), ActualName=$($stopRes2.ActualName)" `
        -DurationMs $t7Sw.Elapsed.TotalMilliseconds
} finally {
    if (Test-Path -Path $claimedRcloneStateFile) {
        Remove-Item -Path $claimedRcloneStateFile -Force -ErrorAction SilentlyContinue
    }
}

# Test 2.3: PID Reuse - Refuse to kill when StartTime does not match recorded state
$t8Sw = [System.Diagnostics.Stopwatch]::StartNew()
$timeMismatchStateFile = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-time-mismatch-$([Guid]::NewGuid().ToString('N')).json"
try {
    # Look for another process or simulate start time mismatch
    # In stop_drive.ps1: ProcessName must be rclone before checking StartTime.
    # To test StartTime verification branch logic safely:
    # If a real rclone process were running with different start time, it rejects.
    # Let's verify stop_drive logic handles start time calculation safely:
    $stExpected = [DateTimeOffset]::UtcNow.AddDays(-2).ToString("o")
    $fakeTimeState = [PSCustomObject]@{
        pid            = $currentProcess.Id
        processName    = "rclone"
        startTime      = $stExpected
        executablePath = "C:\rclone\rclone.exe"
        mountPoint     = "M:"
        remoteTarget   = "cinema-gdrive:DippieMedia"
    }
    $fakeTimeState | ConvertTo-Json | Set-Content -Path $timeMismatchStateFile -Encoding UTF8

    $stopRes3 = & $stopPath -StateFile $timeMismatchStateFile
    $t8Sw.Stop()

    # Rejection occurs on ProcessName first (or StartTime), both yielding PID_REUSE_REJECTED
    $rejected3 = ($stopRes3.Success -eq $false) -and ($stopRes3.Status -eq "PID_REUSE_REJECTED")

    Register-TestResult -TestId "TC-PID-03" -Category "PIDSafety" `
        -Name "stop_drive rejects termination of processes with identity or start time mismatch" `
        -Description "Validates that any mismatch between state and live process rejects termination" `
        -Passed $rejected3 -FailureMessage "Status was: $($stopRes3.Status)" `
        -Expected "Status=PID_REUSE_REJECTED" -Actual "Status=$($stopRes3.Status)" `
        -DurationMs $t8Sw.Elapsed.TotalMilliseconds
} finally {
    if (Test-Path -Path $timeMismatchStateFile) {
        Remove-Item -Path $timeMismatchStateFile -Force -ErrorAction SilentlyContinue
    }
}

# Test 2.4: status_drive reports DEGRADED when PID reuse is detected
$t9Sw = [System.Diagnostics.Stopwatch]::StartNew()
$degradedStateFile = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-status-degraded-$([Guid]::NewGuid().ToString('N')).json"
try {
    $degradedState = [PSCustomObject]@{
        pid            = $currentProcess.Id
        processName    = "rclone"
        startTime      = $currentProcess.StartTime.ToString("o")
        mountPoint     = "Z:"
        remoteTarget   = "cinema-gdrive:DippieMedia"
    }
    $degradedState | ConvertTo-Json | Set-Content -Path $degradedStateFile -Encoding UTF8

    $statusRes = & $statusPath -StateFile $degradedStateFile
    $t9Sw.Stop()

    $isDegraded = ($statusRes.Status -eq "DEGRADED")
    $hasPidReuseReason = ($statusRes.Reason -match "PID reuse detected")
    $procAlive = ($statusRes.ProcessAlive -eq $true)

    $p9Passed = ($isDegraded -and $hasPidReuseReason -and $procAlive)
    $msg = if (-not $p9Passed) { "status_drive failed to report DEGRADED on PID reuse: $($statusRes.Status), Reason=$($statusRes.Reason)" } else { "" }
    Register-TestResult -TestId "TC-PID-04" -Category "PIDSafety" `
        -Name "status_drive reports DEGRADED and alerts on PID reuse" `
        -Description "Validates status_drive flags process identity conflict as DEGRADED with PID reuse explanation" `
        -Passed $p9Passed -FailureMessage $msg `
        -Expected "Status=DEGRADED, Reason mentions PID reuse" `
        -Actual "Status=$($statusRes.Status), Reason=$($statusRes.Reason)" `
        -DurationMs $t9Sw.Elapsed.TotalMilliseconds
} finally {
    if (Test-Path -Path $degradedStateFile) {
        Remove-Item -Path $degradedStateFile -Force -ErrorAction SilentlyContinue
    }
}

# Test 2.5: Inactive / non-existent PID cleanup in stop_drive
$t10Sw = [System.Diagnostics.Stopwatch]::StartNew()
$deadPidStateFile = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-dead-pid-$([Guid]::NewGuid().ToString('N')).json"
try {
    # Find a PID guaranteed not to exist
    $deadPid = 999991
    while (Get-Process -Id $deadPid -ErrorAction SilentlyContinue) {
        $deadPid++
    }

    $deadState = [PSCustomObject]@{
        pid            = $deadPid
        processName    = "rclone"
        startTime      = [DateTimeOffset]::UtcNow.ToString("o")
        mountPoint     = "Z:"
        remoteTarget   = "cinema-gdrive:DippieMedia"
    }
    $deadState | ConvertTo-Json | Set-Content -Path $deadPidStateFile -Encoding UTF8

    $stopDeadRes = & $stopPath -StateFile $deadPidStateFile
    $t10Sw.Stop()

    $stoppedSuccess = ($stopDeadRes.Success -eq $true) -and ($stopDeadRes.Status -eq "ALREADY_STOPPED")
    $deadStateDeleted = (-not (Test-Path -Path $deadPidStateFile -PathType Leaf))

    $p10Passed = ($stoppedSuccess -and $deadStateDeleted)
    $msg = if (-not $p10Passed) { "Dead PID cleanup failed: Status=$($stopDeadRes.Status), FileExists=$deadStateDeleted" } else { "" }
    Register-TestResult -TestId "TC-PID-05" -Category "PIDSafety" `
        -Name "stop_drive cleans up stale state file for dead PID (Status: ALREADY_STOPPED)" `
        -Description "Validates that a state file referencing an exited PID is cleanly removed without errors" `
        -Passed $p10Passed -FailureMessage $msg `
        -Expected "Status=ALREADY_STOPPED, State file deleted" `
        -Actual "Status=$($stopDeadRes.Status), FileDeleted=$deadStateDeleted" `
        -DurationMs $t10Sw.Elapsed.TotalMilliseconds
} finally {
    if (Test-Path -Path $deadPidStateFile) {
        Remove-Item -Path $deadPidStateFile -Force -ErrorAction SilentlyContinue
    }
}

# Test 2.6: status_drive reports NOT_MOUNTED for inactive PID
$t11Sw = [System.Diagnostics.Stopwatch]::StartNew()
$deadStatusStateFile = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-dead-status-$([Guid]::NewGuid().ToString('N')).json"
try {
    $deadPid2 = 999993
    while (Get-Process -Id $deadPid2 -ErrorAction SilentlyContinue) {
        $deadPid2++
    }

    $deadState2 = [PSCustomObject]@{
        pid            = $deadPid2
        processName    = "rclone"
        startTime      = [DateTimeOffset]::UtcNow.ToString("o")
        mountPoint     = "Z:"
        remoteTarget   = "cinema-gdrive:DippieMedia"
    }
    $deadState2 | ConvertTo-Json | Set-Content -Path $deadStatusStateFile -Encoding UTF8

    $statusDeadRes = & $statusPath -StateFile $deadStatusStateFile
    $t11Sw.Stop()

    $isNotMounted = ($statusDeadRes.Status -eq "NOT_MOUNTED")
    $procNotAlive = ($statusDeadRes.ProcessAlive -eq $false)

    $p11Passed = ($isNotMounted -and $procNotAlive)
    Register-TestResult -TestId "TC-PID-06" -Category "PIDSafety" `
        -Name "status_drive reports NOT_MOUNTED for state file with dead PID" `
        -Description "Validates status_drive reports NOT_MOUNTED when recorded PID is no longer running" `
        -Passed $p11Passed -FailureMessage "Status was: $($statusDeadRes.Status)" `
        -Expected "Status=NOT_MOUNTED, ProcessAlive=False" `
        -Actual "Status=$($statusDeadRes.Status), ProcessAlive=$($statusDeadRes.ProcessAlive)" `
        -DurationMs $t11Sw.Elapsed.TotalMilliseconds
} finally {
    if (Test-Path -Path $deadStatusStateFile) {
        Remove-Item -Path $deadStatusStateFile -Force -ErrorAction SilentlyContinue
    }
}

# Test 2.7: Missing state file handled gracefully by stop_drive
$t12Sw = [System.Diagnostics.Stopwatch]::StartNew()
$missingStatePath = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-missing-$([Guid]::NewGuid().ToString('N')).json"
$stopMissingRes = & $stopPath -StateFile $missingStatePath
$t12Sw.Stop()

$missingHandled = ($stopMissingRes.Success -eq $false) -and ($stopMissingRes.Status -eq "NOT_FOUND")
Register-TestResult -TestId "TC-PID-07" -Category "PIDSafety" `
    -Name "stop_drive returns NOT_FOUND when state file does not exist" `
    -Description "Validates graceful handling of non-existent state file without throws or crashes" `
    -Passed $missingHandled -FailureMessage "Status was: $($stopMissingRes.Status)" `
    -Expected "Status=NOT_FOUND, Success=False" `
    -Actual "Status=$($stopMissingRes.Status), Success=$($stopMissingRes.Success)" `
    -DurationMs $t12Sw.Elapsed.TotalMilliseconds

# Test 2.8: Empty or invalid state file rejected and preserved (Fail Closed)
$t13Sw = [System.Diagnostics.Stopwatch]::StartNew()
$emptyStatePath = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-empty-$([Guid]::NewGuid().ToString('N')).json"
try {
    # Create empty state file (0 bytes)
    New-Item -ItemType File -Path $emptyStatePath -Force | Out-Null

    $stopEmptyRes = & $stopPath -StateFile $emptyStatePath
    $t13Sw.Stop()

    $emptyRejected = ($stopEmptyRes.Success -eq $false) -and ($stopEmptyRes.Status -eq "VERIFICATION_FAILED")
    $emptyFilePreserved = (Test-Path -Path $emptyStatePath -PathType Leaf)

    $p13Passed = ($emptyRejected -and $emptyFilePreserved)
    Register-TestResult -TestId "TC-PID-08" -Category "PIDSafety" `
        -Name "stop_drive fails closed on empty or invalid state file (Status: VERIFICATION_FAILED, state preserved)" `
        -Description "Validates empty state file is preserved for forensic inspection rather than deleted without verification" `
        -Passed $p13Passed -FailureMessage "Status was: $($stopEmptyRes.Status), FileDeleted=$(-not $emptyFilePreserved)" `
        -Expected "Status=VERIFICATION_FAILED, File preserved" `
        -Actual "Status=$($stopEmptyRes.Status), FilePreserved=$emptyFilePreserved" `
        -DurationMs $t13Sw.Elapsed.TotalMilliseconds
} finally {
    if (Test-Path -Path $emptyStatePath) {
        Remove-Item -Path $emptyStatePath -Force -ErrorAction SilentlyContinue
    }
}

# Test 2.9: Idempotent stop_drive invocations
$t14Sw = [System.Diagnostics.Stopwatch]::StartNew()
$idempotentStatePath = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-idempotent-$([Guid]::NewGuid().ToString('N')).json"
try {
    $deadPid3 = 999995
    $fakeState3 = [PSCustomObject]@{
        pid          = $deadPid3
        processName  = "rclone"
        startTime    = [DateTimeOffset]::UtcNow.ToString("o")
        mountPoint   = "Z:"
        remoteTarget = "cinema-gdrive:DippieMedia"
    }
    $fakeState3 | ConvertTo-Json | Set-Content -Path $idempotentStatePath -Encoding UTF8

    # First call: cleans up file and returns ALREADY_STOPPED
    $call1 = & $stopPath -StateFile $idempotentStatePath
    # Second call: detects file gone and returns NOT_FOUND
    $call2 = & $stopPath -StateFile $idempotentStatePath
    $t14Sw.Stop()

    $p14Passed = ($call1.Status -eq "ALREADY_STOPPED") -and ($call2.Status -eq "NOT_FOUND")
    Register-TestResult -TestId "TC-PID-09" -Category "PIDSafety" `
        -Name "stop_drive is idempotent across repeated invocations" `
        -Description "Validates calling stop_drive repeatedly transitions cleanly from ALREADY_STOPPED to NOT_FOUND" `
        -Passed $p14Passed -FailureMessage "Call1=$($call1.Status), Call2=$($call2.Status)" `
        -Expected "Call1=ALREADY_STOPPED, Call2=NOT_FOUND" `
        -Actual "Call1=$($call1.Status), Call2=$($call2.Status)" `
        -DurationMs $t14Sw.Elapsed.TotalMilliseconds
} finally {
    if (Test-Path -Path $idempotentStatePath) {
        Remove-Item -Path $idempotentStatePath -Force -ErrorAction SilentlyContinue
    }
}

# ==============================================================================
# SUITE 3: Strict Process Identity Verification & Fail-Closed Seams (Finding D2)
# ==============================================================================
Write-Host "`n--- [SUITE 3] Strict Process Identity & Fail-Closed Verification (Finding D2) ---" -ForegroundColor Yellow

$global:MockProcessMap = @{}
$global:MockStoppedPids = [System.Collections.Generic.List[int]]::new()

function global:Get-Process {
    [CmdletBinding()]
    param(
        [Parameter(ValueFromPipeline = $true)]
        [int[]]$Id
    )
    if ($Id -and $global:MockProcessMap.ContainsKey($Id[0])) {
        return $global:MockProcessMap[$Id[0]]
    }
    Microsoft.PowerShell.Management\Get-Process @PSBoundParameters
}

function global:Stop-Process {
    [CmdletBinding()]
    param(
        [Parameter(ValueFromPipeline = $true)]
        [int[]]$Id,
        [switch]$Force
    )
    if ($Id -and $global:MockProcessMap.ContainsKey($Id[0])) {
        $global:MockStoppedPids.Add($Id[0])
        $global:MockProcessMap.Remove($Id[0])
        return
    }
    Microsoft.PowerShell.Management\Stop-Process @PSBoundParameters
}

try {
    # Test 3.1: TC-D2-01 ExecutablePath mismatch fails closed
    $tD2_1Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $d2State1 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-d2-exepath-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $st1 = [DateTime]::UtcNow
        $global:MockProcessMap[880001] = [PSCustomObject]@{
            Id          = 880001
            ProcessName = "rclone"
            Path        = "C:\Different\rclone.exe"
            StartTime   = $st1
            SessionId   = 1
        }
        $stateContent1 = [PSCustomObject]@{
            pid            = 880001
            processName    = "rclone"
            executablePath = "C:\Expected\rclone.exe"
            startTime      = $st1.ToString("o")
            sessionId      = 1
            mountPoint     = "Z:"
            remoteTarget   = "cinema-gdrive:Media"
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            status         = "MOUNTED"
        }
        $stateContent1 | ConvertTo-Json | Set-Content -Path $d2State1 -Encoding UTF8

        $resD2_1 = & $stopPath -StateFile $d2State1
        $tD2_1Sw.Stop()

        $pD2_1Passed = ($resD2_1.Success -eq $false) -and `
                       ($resD2_1.Status -eq "IDENTITY_MISMATCH") -and `
                       ($resD2_1.VerificationReason -eq "ExecutablePathMismatch") -and `
                       ($global:MockStoppedPids -notcontains 880001) -and `
                       (Test-Path -Path $d2State1 -PathType Leaf)

        Register-TestResult -TestId "TC-D2-01" -Category "ProcessIdentity" `
            -Name "stop_drive refuses to kill process when ExecutablePath differs (Status: IDENTITY_MISMATCH)" `
            -Description "Confirms stop_drive strictly compares full executable path and aborts termination on mismatch" `
            -Passed $pD2_1Passed `
            -FailureMessage "Status: $($resD2_1.Status), Reason: $($resD2_1.VerificationReason), Stopped: $($global:MockStoppedPids -contains 880001)" `
            -Expected "Status=IDENTITY_MISMATCH, Reason=ExecutablePathMismatch, StatePreserved=True" `
            -Actual "Status=$($resD2_1.Status), Reason=$($resD2_1.VerificationReason), StatePreserved=$(Test-Path -Path $d2State1 -PathType Leaf)" `
            -DurationMs $tD2_1Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $d2State1) { Remove-Item -Path $d2State1 -Force -ErrorAction SilentlyContinue }
    }

    # Test 3.2: TC-D2-02 StartTime mismatch (delta >= 500ms) fails closed
    $tD2_2Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $d2State2 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-d2-starttime-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $st2 = [DateTime]::UtcNow
        $global:MockProcessMap[880002] = [PSCustomObject]@{
            Id          = 880002
            ProcessName = "rclone"
            Path        = "C:\Expected\rclone.exe"
            StartTime   = $st2
            SessionId   = 1
        }
        $stateContent2 = [PSCustomObject]@{
            pid            = 880002
            processName    = "rclone"
            executablePath = "C:\Expected\rclone.exe"
            startTime      = ($st2.AddSeconds(-3)).ToString("o")
            sessionId      = 1
            mountPoint     = "Z:"
            remoteTarget   = "cinema-gdrive:Media"
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            status         = "MOUNTED"
        }
        $stateContent2 | ConvertTo-Json | Set-Content -Path $d2State2 -Encoding UTF8

        $resD2_2 = & $stopPath -StateFile $d2State2
        $tD2_2Sw.Stop()

        $pD2_2Passed = ($resD2_2.Success -eq $false) -and `
                       ($resD2_2.Status -eq "IDENTITY_MISMATCH") -and `
                       ($resD2_2.VerificationReason -eq "StartTimeMismatch") -and `
                       ($global:MockStoppedPids -notcontains 880002) -and `
                       (Test-Path -Path $d2State2 -PathType Leaf)

        Register-TestResult -TestId "TC-D2-02" -Category "ProcessIdentity" `
            -Name "stop_drive refuses to kill process when StartTime delta >= 500ms (Status: IDENTITY_MISMATCH)" `
            -Description "Confirms stop_drive enforces strict 500ms tolerance on process start time verification" `
            -Passed $pD2_2Passed `
            -FailureMessage "Status: $($resD2_2.Status), Reason: $($resD2_2.VerificationReason), Stopped: $($global:MockStoppedPids -contains 880002)" `
            -Expected "Status=IDENTITY_MISMATCH, Reason=StartTimeMismatch, StatePreserved=True" `
            -Actual "Status=$($resD2_2.Status), Reason=$($resD2_2.VerificationReason), StatePreserved=$(Test-Path -Path $d2State2 -PathType Leaf)" `
            -DurationMs $tD2_2Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $d2State2) { Remove-Item -Path $d2State2 -Force -ErrorAction SilentlyContinue }
    }

    # Test 3.3: TC-D2-03 Missing startTime in state fails closed
    $tD2_3Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $d2State3 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-d2-nostart-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $st3 = [DateTime]::UtcNow
        $global:MockProcessMap[880003] = [PSCustomObject]@{
            Id          = 880003
            ProcessName = "rclone"
            Path        = "C:\Expected\rclone.exe"
            StartTime   = $st3
            SessionId   = 1
        }
        $stateContent3 = [PSCustomObject]@{
            pid            = 880003
            processName    = "rclone"
            executablePath = "C:\Expected\rclone.exe"
            sessionId      = 1
            mountPoint     = "Z:"
            remoteTarget   = "cinema-gdrive:Media"
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            status         = "MOUNTED"
        }
        $stateContent3 | ConvertTo-Json | Set-Content -Path $d2State3 -Encoding UTF8

        $resD2_3 = & $stopPath -StateFile $d2State3
        $tD2_3Sw.Stop()

        $pD2_3Passed = ($resD2_3.Success -eq $false) -and `
                       ($resD2_3.Status -eq "VERIFICATION_FAILED") -and `
                       ($resD2_3.VerificationReason -eq "MissingStartTimeInState") -and `
                       ($global:MockStoppedPids -notcontains 880003) -and `
                       (Test-Path -Path $d2State3 -PathType Leaf)

        Register-TestResult -TestId "TC-D2-03" -Category "ProcessIdentity" `
            -Name "stop_drive fails closed when state file lacks startTime (Status: VERIFICATION_FAILED)" `
            -Description "Confirms missing startTime is rejected without termination and state file is preserved" `
            -Passed $pD2_3Passed `
            -FailureMessage "Status: $($resD2_3.Status), Reason: $($resD2_3.VerificationReason)" `
            -Expected "Status=VERIFICATION_FAILED, Reason=MissingStartTimeInState, StatePreserved=True" `
            -Actual "Status=$($resD2_3.Status), Reason=$($resD2_3.VerificationReason), StatePreserved=$(Test-Path -Path $d2State3 -PathType Leaf)" `
            -DurationMs $tD2_3Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $d2State3) { Remove-Item -Path $d2State3 -Force -ErrorAction SilentlyContinue }
    }

    # Test 3.4: TC-D2-04 Missing executablePath in state fails closed
    $tD2_4Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $d2State4 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-d2-noexe-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $st4 = [DateTime]::UtcNow
        $global:MockProcessMap[880004] = [PSCustomObject]@{
            Id          = 880004
            ProcessName = "rclone"
            Path        = "C:\Expected\rclone.exe"
            StartTime   = $st4
            SessionId   = 1
        }
        $stateContent4 = [PSCustomObject]@{
            pid            = 880004
            processName    = "rclone"
            startTime      = $st4.ToString("o")
            sessionId      = 1
            mountPoint     = "Z:"
            remoteTarget   = "cinema-gdrive:Media"
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            status         = "MOUNTED"
        }
        $stateContent4 | ConvertTo-Json | Set-Content -Path $d2State4 -Encoding UTF8

        $resD2_4 = & $stopPath -StateFile $d2State4
        $tD2_4Sw.Stop()

        $pD2_4Passed = ($resD2_4.Success -eq $false) -and `
                       ($resD2_4.Status -eq "VERIFICATION_FAILED") -and `
                       ($resD2_4.VerificationReason -eq "MissingExecutablePathInState") -and `
                       ($global:MockStoppedPids -notcontains 880004) -and `
                       (Test-Path -Path $d2State4 -PathType Leaf)

        Register-TestResult -TestId "TC-D2-04" -Category "ProcessIdentity" `
            -Name "stop_drive fails closed when state lacks executablePath (Status: VERIFICATION_FAILED)" `
            -Description "Confirms missing executablePath is rejected without termination and state file is preserved" `
            -Passed $pD2_4Passed `
            -FailureMessage "Status: $($resD2_4.Status), Reason: $($resD2_4.VerificationReason)" `
            -Expected "Status=VERIFICATION_FAILED, Reason=MissingExecutablePathInState, StatePreserved=True" `
            -Actual "Status=$($resD2_4.Status), Reason=$($resD2_4.VerificationReason), StatePreserved=$(Test-Path -Path $d2State4 -PathType Leaf)" `
            -DurationMs $tD2_4Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $d2State4) { Remove-Item -Path $d2State4 -Force -ErrorAction SilentlyContinue }
    }

    # Test 3.5: TC-D2-05 SessionId mismatch fails closed
    $tD2_5Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $d2State5 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-d2-session-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $st5 = [DateTime]::UtcNow
        $global:MockProcessMap[880005] = [PSCustomObject]@{
            Id          = 880005
            ProcessName = "rclone"
            Path        = "C:\Expected\rclone.exe"
            StartTime   = $st5
            SessionId   = 1
        }
        $stateContent5 = [PSCustomObject]@{
            pid            = 880005
            processName    = "rclone"
            executablePath = "C:\Expected\rclone.exe"
            startTime      = $st5.ToString("o")
            sessionId      = 99
            mountPoint     = "Z:"
            remoteTarget   = "cinema-gdrive:Media"
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            status         = "MOUNTED"
        }
        $stateContent5 | ConvertTo-Json | Set-Content -Path $d2State5 -Encoding UTF8

        $resD2_5 = & $stopPath -StateFile $d2State5
        $tD2_5Sw.Stop()

        $pD2_5Passed = ($resD2_5.Success -eq $false) -and `
                       ($resD2_5.Status -eq "IDENTITY_MISMATCH") -and `
                       ($resD2_5.VerificationReason -eq "SessionIdMismatch") -and `
                       ($global:MockStoppedPids -notcontains 880005) -and `
                       (Test-Path -Path $d2State5 -PathType Leaf)

        Register-TestResult -TestId "TC-D2-05" -Category "ProcessIdentity" `
            -Name "stop_drive refuses to kill process when SessionId differs (Status: IDENTITY_MISMATCH)" `
            -Description "Confirms session ID mismatch prevents process termination" `
            -Passed $pD2_5Passed `
            -FailureMessage "Status: $($resD2_5.Status), Reason: $($resD2_5.VerificationReason)" `
            -Expected "Status=IDENTITY_MISMATCH, Reason=SessionIdMismatch, StatePreserved=True" `
            -Actual "Status=$($resD2_5.Status), Reason=$($resD2_5.VerificationReason), StatePreserved=$(Test-Path -Path $d2State5 -PathType Leaf)" `
            -DurationMs $tD2_5Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $d2State5) { Remove-Item -Path $d2State5 -Force -ErrorAction SilentlyContinue }
    }

    # Test 3.6: TC-D2-06 Fully verified process terminated cleanly and state file removed
    $tD2_6Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $d2State6 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-d2-success-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $st6 = [DateTime]::UtcNow
        $global:MockProcessMap[880006] = [PSCustomObject]@{
            Id          = 880006
            ProcessName = "rclone"
            Path        = "C:\Expected\rclone.exe"
            StartTime   = $st6
            SessionId   = 1
        }
        $stateContent6 = [PSCustomObject]@{
            pid            = 880006
            processName    = "rclone"
            executablePath = "C:\Expected\rclone.exe"
            startTime      = $st6.ToString("o")
            sessionId      = 1
            mountPoint     = "Z:"
            remoteTarget   = "cinema-gdrive:Media"
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            status         = "MOUNTED"
        }
        $stateContent6 | ConvertTo-Json | Set-Content -Path $d2State6 -Encoding UTF8

        $resD2_6 = & $stopPath -StateFile $d2State6
        $tD2_6Sw.Stop()

        $pD2_6Passed = ($resD2_6.Success -eq $true) -and `
                       ($resD2_6.Status -eq "STOPPED") -and `
                       ($global:MockStoppedPids -contains 880006) -and `
                       (-not (Test-Path -Path $d2State6 -PathType Leaf))

        Register-TestResult -TestId "TC-D2-06" -Category "ProcessIdentity" `
            -Name "stop_drive terminates strictly verified process and removes state file (Status: STOPPED)" `
            -Description "Confirms fully matching process is safely terminated and state file is deleted" `
            -Passed $pD2_6Passed `
            -FailureMessage "Status: $($resD2_6.Status), Stopped: $($global:MockStoppedPids -contains 880006), StateDeleted: $(-not (Test-Path -Path $d2State6 -PathType Leaf))" `
            -Expected "Status=STOPPED, Success=True, StateDeleted=True" `
            -Actual "Status=$($resD2_6.Status), Success=$($resD2_6.Success), StateDeleted=$(-not (Test-Path -Path $d2State6 -PathType Leaf))" `
            -DurationMs $tD2_6Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $d2State6) { Remove-Item -Path $d2State6 -Force -ErrorAction SilentlyContinue }
    }

    # ==============================================================================
    # SUITE 4: Comprehensive Process Identity Schema & Reviewer Repro (Finding F2)
    # ==============================================================================
    Write-Host "`n--- [SUITE 4] Strict Identity Schema & Reviewer Repro (Finding F2) ---" -ForegroundColor Yellow

    # Test 4.1: TC-F2-01 Missing processName in state fails closed (Status: VERIFICATION_FAILED)
    $tF2_1Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $f2State1 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-f2-noprocname-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $stF2_1 = [DateTime]::UtcNow
        $global:MockProcessMap[881001] = [PSCustomObject]@{
            Id          = 881001
            ProcessName = "rclone"
            Path        = "C:\Expected\rclone.exe"
            StartTime   = $stF2_1
            SessionId   = 1
        }
        $stateContentF2_1 = [PSCustomObject]@{
            pid            = 881001
            # Missing processName - must not fallback to rclone
            executablePath = "C:\Expected\rclone.exe"
            startTime      = $stF2_1.ToString("o")
            sessionId      = 1
            mountPoint     = "Z:"
            remoteTarget   = "cinema-gdrive:Media"
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            status         = "MOUNTED"
        }
        $stateContentF2_1 | ConvertTo-Json | Set-Content -Path $f2State1 -Encoding UTF8

        $resF2_1 = & $stopPath -StateFile $f2State1
        $tF2_1Sw.Stop()

        $pF2_1Passed = ($resF2_1.Success -eq $false) -and `
                       ($resF2_1.Status -eq "VERIFICATION_FAILED") -and `
                       ($resF2_1.VerificationReason -eq "MissingProcessNameInState") -and `
                       ($global:MockStoppedPids -notcontains 881001) -and `
                       (Test-Path -Path $f2State1 -PathType Leaf)

        Register-TestResult -TestId "TC-F2-01" -Category "ProcessIdentityF2" `
            -Name "stop_drive fails closed when state lacks processName (Status: VERIFICATION_FAILED)" `
            -Description "Confirms missing processName does not fallback to rclone, aborts termination and preserves state" `
            -Passed $pF2_1Passed `
            -FailureMessage "Status: $($resF2_1.Status), Reason: $($resF2_1.VerificationReason)" `
            -Expected "Status=VERIFICATION_FAILED, Reason=MissingProcessNameInState, StatePreserved=True" `
            -Actual "Status=$($resF2_1.Status), Reason=$($resF2_1.VerificationReason), StatePreserved=$(Test-Path -Path $f2State1 -PathType Leaf)" `
            -DurationMs $tF2_1Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $f2State1) { Remove-Item -Path $f2State1 -Force -ErrorAction SilentlyContinue }
    }

    # Test 4.2: TC-F2-02 Missing sessionId in state fails closed (Status: VERIFICATION_FAILED)
    $tF2_2Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $f2State2 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-f2-nosession-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $stF2_2 = [DateTime]::UtcNow
        $global:MockProcessMap[881002] = [PSCustomObject]@{
            Id          = 881002
            ProcessName = "rclone"
            Path        = "C:\Expected\rclone.exe"
            StartTime   = $stF2_2
            SessionId   = 1
        }
        $stateContentF2_2 = [PSCustomObject]@{
            pid            = 881002
            processName    = "rclone"
            executablePath = "C:\Expected\rclone.exe"
            startTime      = $stF2_2.ToString("o")
            # Missing sessionId
            mountPoint     = "Z:"
            remoteTarget   = "cinema-gdrive:Media"
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            status         = "MOUNTED"
        }
        $stateContentF2_2 | ConvertTo-Json | Set-Content -Path $f2State2 -Encoding UTF8

        $resF2_2 = & $stopPath -StateFile $f2State2
        $tF2_2Sw.Stop()

        $pF2_2Passed = ($resF2_2.Success -eq $false) -and `
                       ($resF2_2.Status -eq "VERIFICATION_FAILED") -and `
                       ($resF2_2.VerificationReason -eq "MissingSessionIdInState") -and `
                       ($global:MockStoppedPids -notcontains 881002) -and `
                       (Test-Path -Path $f2State2 -PathType Leaf)

        Register-TestResult -TestId "TC-F2-02" -Category "ProcessIdentityF2" `
            -Name "stop_drive fails closed when state lacks sessionId (Status: VERIFICATION_FAILED)" `
            -Description "Confirms missing sessionId is rejected without termination and state file is preserved" `
            -Passed $pF2_2Passed `
            -FailureMessage "Status: $($resF2_2.Status), Reason: $($resF2_2.VerificationReason)" `
            -Expected "Status=VERIFICATION_FAILED, Reason=MissingSessionIdInState, StatePreserved=True" `
            -Actual "Status=$($resF2_2.Status), Reason=$($resF2_2.VerificationReason), StatePreserved=$(Test-Path -Path $f2State2 -PathType Leaf)" `
            -DurationMs $tF2_2Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $f2State2) { Remove-Item -Path $f2State2 -Force -ErrorAction SilentlyContinue }
    }

    # Test 4.3: TC-F2-03 Missing mountPoint in state fails closed (Status: VERIFICATION_FAILED)
    $tF2_3Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $f2State3 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-f2-nomount-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $stF2_3 = [DateTime]::UtcNow
        $global:MockProcessMap[881003] = [PSCustomObject]@{
            Id          = 881003
            ProcessName = "rclone"
            Path        = "C:\Expected\rclone.exe"
            StartTime   = $stF2_3
            SessionId   = 1
        }
        $stateContentF2_3 = [PSCustomObject]@{
            pid            = 881003
            processName    = "rclone"
            executablePath = "C:\Expected\rclone.exe"
            startTime      = $stF2_3.ToString("o")
            sessionId      = 1
            # Missing mountPoint
            remoteTarget   = "cinema-gdrive:Media"
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            status         = "MOUNTED"
        }
        $stateContentF2_3 | ConvertTo-Json | Set-Content -Path $f2State3 -Encoding UTF8

        $resF2_3 = & $stopPath -StateFile $f2State3
        $tF2_3Sw.Stop()

        $pF2_3Passed = ($resF2_3.Success -eq $false) -and `
                       ($resF2_3.Status -eq "VERIFICATION_FAILED") -and `
                       ($resF2_3.VerificationReason -eq "MissingMountPointInState") -and `
                       ($global:MockStoppedPids -notcontains 881003) -and `
                       (Test-Path -Path $f2State3 -PathType Leaf)

        Register-TestResult -TestId "TC-F2-03" -Category "ProcessIdentityF2" `
            -Name "stop_drive fails closed when state lacks mountPoint (Status: VERIFICATION_FAILED)" `
            -Description "Confirms missing mountPoint is rejected without termination and state file is preserved" `
            -Passed $pF2_3Passed `
            -FailureMessage "Status: $($resF2_3.Status), Reason: $($resF2_3.VerificationReason)" `
            -Expected "Status=VERIFICATION_FAILED, Reason=MissingMountPointInState, StatePreserved=True" `
            -Actual "Status=$($resF2_3.Status), Reason=$($resF2_3.VerificationReason), StatePreserved=$(Test-Path -Path $f2State3 -PathType Leaf)" `
            -DurationMs $tF2_3Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $f2State3) { Remove-Item -Path $f2State3 -Force -ErrorAction SilentlyContinue }
    }

    # Test 4.4: TC-F2-04 Missing remoteTarget in state fails closed (Status: VERIFICATION_FAILED)
    $tF2_4Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $f2State4 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-f2-noremote-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $stF2_4 = [DateTime]::UtcNow
        $global:MockProcessMap[881004] = [PSCustomObject]@{
            Id          = 881004
            ProcessName = "rclone"
            Path        = "C:\Expected\rclone.exe"
            StartTime   = $stF2_4
            SessionId   = 1
        }
        $stateContentF2_4 = [PSCustomObject]@{
            pid            = 881004
            processName    = "rclone"
            executablePath = "C:\Expected\rclone.exe"
            startTime      = $stF2_4.ToString("o")
            sessionId      = 1
            mountPoint     = "Z:"
            # Missing remoteTarget
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            status         = "MOUNTED"
        }
        $stateContentF2_4 | ConvertTo-Json | Set-Content -Path $f2State4 -Encoding UTF8

        $resF2_4 = & $stopPath -StateFile $f2State4
        $tF2_4Sw.Stop()

        $pF2_4Passed = ($resF2_4.Success -eq $false) -and `
                       ($resF2_4.Status -eq "VERIFICATION_FAILED") -and `
                       ($resF2_4.VerificationReason -eq "MissingRemoteTargetInState") -and `
                       ($global:MockStoppedPids -notcontains 881004) -and `
                       (Test-Path -Path $f2State4 -PathType Leaf)

        Register-TestResult -TestId "TC-F2-04" -Category "ProcessIdentityF2" `
            -Name "stop_drive fails closed when state lacks remoteTarget (Status: VERIFICATION_FAILED)" `
            -Description "Confirms missing remoteTarget is rejected without termination and state file is preserved" `
            -Passed $pF2_4Passed `
            -FailureMessage "Status: $($resF2_4.Status), Reason: $($resF2_4.VerificationReason)" `
            -Expected "Status=VERIFICATION_FAILED, Reason=MissingRemoteTargetInState, StatePreserved=True" `
            -Actual "Status=$($resF2_4.Status), Reason=$($resF2_4.VerificationReason), StatePreserved=$(Test-Path -Path $f2State4 -PathType Leaf)" `
            -DurationMs $tF2_4Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $f2State4) { Remove-Item -Path $f2State4 -Force -ErrorAction SilentlyContinue }
    }

    # Test 4.5: TC-F2-05 Missing arguments in state fails closed (Status: VERIFICATION_FAILED)
    $tF2_5Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $f2State5 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-f2-noargs-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $stF2_5 = [DateTime]::UtcNow
        $global:MockProcessMap[881005] = [PSCustomObject]@{
            Id          = 881005
            ProcessName = "rclone"
            Path        = "C:\Expected\rclone.exe"
            StartTime   = $stF2_5
            SessionId   = 1
        }
        $stateContentF2_5 = [PSCustomObject]@{
            pid            = 881005
            processName    = "rclone"
            executablePath = "C:\Expected\rclone.exe"
            startTime      = $stF2_5.ToString("o")
            sessionId      = 1
            mountPoint     = "Z:"
            remoteTarget   = "cinema-gdrive:Media"
            # Missing arguments
            status         = "MOUNTED"
        }
        $stateContentF2_5 | ConvertTo-Json | Set-Content -Path $f2State5 -Encoding UTF8

        $resF2_5 = & $stopPath -StateFile $f2State5
        $tF2_5Sw.Stop()

        $pF2_5Passed = ($resF2_5.Success -eq $false) -and `
                       ($resF2_5.Status -eq "VERIFICATION_FAILED") -and `
                       ($resF2_5.VerificationReason -eq "MissingArgumentsInState") -and `
                       ($global:MockStoppedPids -notcontains 881005) -and `
                       (Test-Path -Path $f2State5 -PathType Leaf)

        Register-TestResult -TestId "TC-F2-05" -Category "ProcessIdentityF2" `
            -Name "stop_drive fails closed when state lacks arguments (Status: VERIFICATION_FAILED)" `
            -Description "Confirms missing arguments is rejected without termination and state file is preserved" `
            -Passed $pF2_5Passed `
            -FailureMessage "Status: $($resF2_5.Status), Reason: $($resF2_5.VerificationReason)" `
            -Expected "Status=VERIFICATION_FAILED, Reason=MissingArgumentsInState, StatePreserved=True" `
            -Actual "Status=$($resF2_5.Status), Reason=$($resF2_5.VerificationReason), StatePreserved=$(Test-Path -Path $f2State5 -PathType Leaf)" `
            -DurationMs $tF2_5Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $f2State5) { Remove-Item -Path $f2State5 -Force -ErrorAction SilentlyContinue }
    }

    # Test 4.6: TC-F2-06 Missing status in state fails closed (Status: VERIFICATION_FAILED)
    $tF2_6Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $f2State6 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-f2-nostatus-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $stF2_6 = [DateTime]::UtcNow
        $global:MockProcessMap[881006] = [PSCustomObject]@{
            Id          = 881006
            ProcessName = "rclone"
            Path        = "C:\Expected\rclone.exe"
            StartTime   = $stF2_6
            SessionId   = 1
        }
        $stateContentF2_6 = [PSCustomObject]@{
            pid            = 881006
            processName    = "rclone"
            executablePath = "C:\Expected\rclone.exe"
            startTime      = $stF2_6.ToString("o")
            sessionId      = 1
            mountPoint     = "Z:"
            remoteTarget   = "cinema-gdrive:Media"
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            # Missing status
        }
        $stateContentF2_6 | ConvertTo-Json | Set-Content -Path $f2State6 -Encoding UTF8

        $resF2_6 = & $stopPath -StateFile $f2State6
        $tF2_6Sw.Stop()

        $pF2_6Passed = ($resF2_6.Success -eq $false) -and `
                       ($resF2_6.Status -eq "VERIFICATION_FAILED") -and `
                       ($resF2_6.VerificationReason -eq "MissingStatusInState") -and `
                       ($global:MockStoppedPids -notcontains 881006) -and `
                       (Test-Path -Path $f2State6 -PathType Leaf)

        Register-TestResult -TestId "TC-F2-06" -Category "ProcessIdentityF2" `
            -Name "stop_drive fails closed when state lacks status (Status: VERIFICATION_FAILED)" `
            -Description "Confirms missing status is rejected without termination and state file is preserved" `
            -Passed $pF2_6Passed `
            -FailureMessage "Status: $($resF2_6.Status), Reason: $($resF2_6.VerificationReason)" `
            -Expected "Status=VERIFICATION_FAILED, Reason=MissingStatusInState, StatePreserved=True" `
            -Actual "Status=$($resF2_6.Status), Reason=$($resF2_6.VerificationReason), StatePreserved=$(Test-Path -Path $f2State6 -PathType Leaf)" `
            -DurationMs $tF2_6Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $f2State6) { Remove-Item -Path $f2State6 -Force -ErrorAction SilentlyContinue }
    }

    # Test 4.7: TC-F2-07 Missing or invalid pid in state fails closed (Status: VERIFICATION_FAILED)
    $tF2_7Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $f2State7 = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-f2-nopid-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $stF2_7 = [DateTime]::UtcNow
        $stateContentF2_7 = [PSCustomObject]@{
            # Missing pid
            processName    = "rclone"
            executablePath = "C:\Expected\rclone.exe"
            startTime      = $stF2_7.ToString("o")
            sessionId      = 1
            mountPoint     = "Z:"
            remoteTarget   = "cinema-gdrive:Media"
            arguments      = @("mount", "cinema-gdrive:Media", "Z:")
            status         = "MOUNTED"
        }
        $stateContentF2_7 | ConvertTo-Json | Set-Content -Path $f2State7 -Encoding UTF8

        $resF2_7 = & $stopPath -StateFile $f2State7
        $tF2_7Sw.Stop()

        $pF2_7Passed = ($resF2_7.Success -eq $false) -and `
                       ($resF2_7.Status -eq "VERIFICATION_FAILED") -and `
                       ($resF2_7.VerificationReason -match "MissingPid") -and `
                       (Test-Path -Path $f2State7 -PathType Leaf)

        Register-TestResult -TestId "TC-F2-07" -Category "ProcessIdentityF2" `
            -Name "stop_drive fails closed when state lacks valid PID (Status: VERIFICATION_FAILED)" `
            -Description "Confirms missing PID aborts termination and preserves state file" `
            -Passed $pF2_7Passed `
            -FailureMessage "Status: $($resF2_7.Status), Reason: $($resF2_7.VerificationReason)" `
            -Expected "Status=VERIFICATION_FAILED, Reason=MissingPid*, StatePreserved=True" `
            -Actual "Status=$($resF2_7.Status), Reason=$($resF2_7.VerificationReason), StatePreserved=$(Test-Path -Path $f2State7 -PathType Leaf)" `
            -DurationMs $tF2_7Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -Path $f2State7) { Remove-Item -Path $f2State7 -Force -ErrorAction SilentlyContinue }
    }

    # Test 4.8: TC-F2-08 Exact reproduction of reviewer DRIVE_F01_stop_missing_identity scenario
    $tF2_8Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $reproState = Join-Path ([System.IO.Path]::GetTempPath()) "codex-drive-f01-stop-test-$([Guid]::NewGuid().ToString('N')).json"
    try {
        $reproStart = [DateTime]::UtcNow
        $reproPid = 987654
        $global:MockProcessMap[$reproPid] = [PSCustomObject]@{
            Id          = $reproPid
            ProcessName = "rclone"
            Path        = "C:\Fixture\rclone.exe"
            StartTime   = $reproStart
            SessionId   = 1
        }
        # Reviewer state: contains only pid, processName, startTime, executablePath
        # Missing sessionId, mountPoint, remoteTarget, arguments, status
        $reviewerStateObj = [PSCustomObject]@{
            pid            = $reproPid
            processName    = "rclone"
            startTime      = $reproStart.ToString("o")
            executablePath = "C:\Fixture\rclone.exe"
        }
        $reviewerStateObj | ConvertTo-Json | Set-Content -LiteralPath $reproState -Encoding UTF8

        $reproRes = & $stopPath -StateFile $reproState -AsJson | ConvertFrom-Json
        $tF2_8Sw.Stop()

        $reproStopped = ($global:MockStoppedPids -contains $reproPid)
        $terminationRequested = $reproStopped
        $stateStillExists = (Test-Path -LiteralPath $reproState)

        $pF2_8Passed = ($reproRes.Success -eq $false) -and `
                       ($reproRes.Status -eq "VERIFICATION_FAILED") -and `
                       (-not $terminationRequested) -and `
                       $stateStillExists

        Register-TestResult -TestId "TC-F2-08" -Category "ProcessIdentityF2" `
            -Name "Reviewer repro DRIVE_F01_stop_missing_identity confirmation" `
            -Description "Confirms terminationRequestedWithMissingIdentityFields is FALSE and state file is preserved" `
            -Passed $pF2_8Passed `
            -FailureMessage "Success: $($reproRes.Success), Status: $($reproRes.Status), TerminationRequested: $terminationRequested" `
            -Expected "Success=False, Status=VERIFICATION_FAILED, TerminationRequested=False, StatePreserved=True" `
            -Actual "Success=$($reproRes.Success), Status=$($reproRes.Status), TerminationRequested=$terminationRequested, StatePreserved=$stateStillExists" `
            -DurationMs $tF2_8Sw.Elapsed.TotalMilliseconds
    } finally {
        if (Test-Path -LiteralPath $reproState) { Remove-Item -LiteralPath $reproState -Force -ErrorAction SilentlyContinue }
    }

    # Test 4.9: TC-F2-09 mount_drive timeout cleanup refuses to terminate process on identity mismatch
    $tF2_9Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $d4TempDirMismatch = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-f2-mount-mismatch-$([Guid]::NewGuid().ToString('N'))"
    try {
        New-Item -ItemType Directory -Path $d4TempDirMismatch -Force | Out-Null
        $preflightMockM = Join-Path $d4TempDirMismatch "preflight.ps1"
        $preflightBodyM = 'param($MountPoint,$RclonePath,$ConfigPath); [PSCustomObject]@{ IsReady=$true; Rclone=[PSCustomObject]@{ExecutablePath="C:\Fixture\rclone.exe"}; BlockReasons=@() } | ConvertTo-Json -Compress'
        Set-Content -LiteralPath $preflightMockM -Value $preflightBodyM -Encoding UTF8

        $mismatchChildPid = 882001
        $startM = [DateTime]::UtcNow
        # Mock child process returned by Start-Process has mismatched SessionId
        function Start-Process {
            param($FilePath, $ArgumentList, $WindowStyle, [switch]$PassThru)
            [PSCustomObject]@{
                Id          = $mismatchChildPid
                HasExited   = $false
                ProcessName = "rclone"
                StartTime   = $startM
                Path        = "C:\Fixture\rclone.exe"
            }
        }
        # In MockProcessMap, live process has SessionId 999 (which does not match caller's session)
        $global:MockProcessMap[$mismatchChildPid] = [PSCustomObject]@{
            Id          = $mismatchChildPid
            ProcessName = "rclone"
            Path        = "C:\Fixture\rclone.exe"
            StartTime   = $startM
            SessionId   = 999
            HasExited   = $false
        }

        $mountSourceM = Get-Content -LiteralPath $mountPath -Raw -Encoding UTF8
        $escapedPreflightM = $preflightMockM.Replace("\", "\\")
        $mountSourceM = $mountSourceM.Replace('$preflightScript = Join-Path $PSScriptRoot "preflight_drive.ps1"', ('$preflightScript = "' + $escapedPreflightM + '"'))

        $missingMountM = Join-Path $d4TempDirMismatch "unmounted-target"
        $stateFileM = Join-Path $d4TempDirMismatch "state.json"

        $resM = & ([scriptblock]::Create($mountSourceM)) -Execute -Remote "cinema-gdrive" -RemoteSubpath "Media" `
            -MountPoint $missingMountM -StateFile $stateFileM `
            -ReadinessTimeoutSeconds 1 -ReadinessIntervalMs 50

        $tF2_9Sw.Stop()

        # Termination should NOT have occurred because SessionId did not match
        $mismatchNotKilled = ($global:MockStoppedPids -notcontains $mismatchChildPid)
        $isTimeout = ($resM.Status -eq "TIMEOUT")

        $pF2_9Passed = ($isTimeout -and $mismatchNotKilled)

        Register-TestResult -TestId "TC-F2-09" -Category "ProcessIdentityF2" `
            -Name "mount_drive timeout cleanup refuses to kill child process on session/identity mismatch" `
            -Description "Confirms mount_drive verifies full identity before stopping child and preserves mismatched process" `
            -Passed $pF2_9Passed `
            -FailureMessage "Status: $($resM.Status), MismatchChildKilled: $(-not $mismatchNotKilled)" `
            -Expected "Status=TIMEOUT, MismatchChildKilled=False" `
            -Actual "Status=$($resM.Status), MismatchChildKilled=$(-not $mismatchNotKilled)" `
            -DurationMs $tF2_9Sw.Elapsed.TotalMilliseconds
    } finally {
        Remove-Item -Path "function:Start-Process" -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $d4TempDirMismatch) {
            Remove-Item -LiteralPath $d4TempDirMismatch -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    # Test 4.10: TC-F2-10 mount_drive timeout cleanup successfully terminates verified owned child process
    $tF2_10Sw = [System.Diagnostics.Stopwatch]::StartNew()
    $d4TempDirMatch = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-f2-mount-match-$([Guid]::NewGuid().ToString('N'))"
    try {
        New-Item -ItemType Directory -Path $d4TempDirMatch -Force | Out-Null
        $preflightMockOk = Join-Path $d4TempDirMatch "preflight.ps1"
        $preflightBodyOk = 'param($MountPoint,$RclonePath,$ConfigPath); [PSCustomObject]@{ IsReady=$true; Rclone=[PSCustomObject]@{ExecutablePath="C:\Fixture\rclone.exe"}; BlockReasons=@() } | ConvertTo-Json -Compress'
        Set-Content -LiteralPath $preflightMockOk -Value $preflightBodyOk -Encoding UTF8

        $matchChildPid = 882002
        $startOk = [DateTime]::UtcNow
        $currentSession = (Get-Process -Id $PID).SessionId

        function Start-Process {
            param($FilePath, $ArgumentList, $WindowStyle, [switch]$PassThru)
            [PSCustomObject]@{
                Id          = $matchChildPid
                HasExited   = $false
                ProcessName = "rclone"
                StartTime   = $startOk
                Path        = "C:\Fixture\rclone.exe"
            }
        }
        # In MockProcessMap, live process matches all identity factors exactly
        $global:MockProcessMap[$matchChildPid] = [PSCustomObject]@{
            Id          = $matchChildPid
            ProcessName = "rclone"
            Path        = "C:\Fixture\rclone.exe"
            StartTime   = $startOk
            SessionId   = $currentSession
            HasExited   = $false
        }

        $mountSourceOk = Get-Content -LiteralPath $mountPath -Raw -Encoding UTF8
        $escapedPreflightOk = $preflightMockOk.Replace("\", "\\")
        $mountSourceOk = $mountSourceOk.Replace('$preflightScript = Join-Path $PSScriptRoot "preflight_drive.ps1"', ('$preflightScript = "' + $escapedPreflightOk + '"'))

        $missingMountOk = Join-Path $d4TempDirMatch "unmounted-target"
        $stateFileOk = Join-Path $d4TempDirMatch "state.json"

        $resOk = & ([scriptblock]::Create($mountSourceOk)) -Execute -Remote "cinema-gdrive" -RemoteSubpath "Media" `
            -MountPoint $missingMountOk -StateFile $stateFileOk `
            -ReadinessTimeoutSeconds 1 -ReadinessIntervalMs 50

        $tF2_10Sw.Stop()

        # Termination SHOULD have occurred because all identity factors matched
        $matchKilled = ($global:MockStoppedPids -contains $matchChildPid)
        $isTimeoutOk = ($resOk.Status -eq "TIMEOUT")

        $pF2_10Passed = ($isTimeoutOk -and $matchKilled)

        Register-TestResult -TestId "TC-F2-10" -Category "ProcessIdentityF2" `
            -Name "mount_drive timeout cleanup safely terminates verified owned child process" `
            -Description "Confirms mount_drive successfully stops child process when all identity factors strictly match" `
            -Passed $pF2_10Passed `
            -FailureMessage "Status: $($resOk.Status), VerifiedChildKilled: $matchKilled" `
            -Expected "Status=TIMEOUT, VerifiedChildKilled=True" `
            -Actual "Status=$($resOk.Status), VerifiedChildKilled=$matchKilled" `
            -DurationMs $tF2_10Sw.Elapsed.TotalMilliseconds
    } finally {
        Remove-Item -Path "function:Start-Process" -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $d4TempDirMatch) {
            Remove-Item -LiteralPath $d4TempDirMatch -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
} finally {
    Remove-Item -Path "function:global:Get-Process" -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "function:global:Stop-Process" -Force -ErrorAction SilentlyContinue
}

# ==============================================================================
# EVIDENCE EXPORT & SUMMARY
# ==============================================================================
$suiteStopwatch.Stop()
$totalCount  = $results.Count
$passedCount = @($results | Where-Object { $_.Passed }).Count
$failedCount = @($results | Where-Object { -not $_.Passed }).Count
$durationSec = [math]::Round($suiteStopwatch.Elapsed.TotalSeconds, 3)

Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host " SECURITY SEAMS & PID SAFETY VERIFICATION SUMMARY" -ForegroundColor Cyan
Write-Host " Total Tests : $totalCount"
Write-Host " Passed      : $passedCount" -ForegroundColor $(if ($passedCount -eq $totalCount) { "Green" } else { "Yellow" })
Write-Host " Failed      : $failedCount" -ForegroundColor $(if ($failedCount -eq 0) { "Green" } else { "Red" })
Write-Host " Duration    : $durationSec seconds"
Write-Host "================================================================================" -ForegroundColor Cyan

# Update shared evidence JSON
try {
    $evidenceDir = Split-Path -Path $EvidencePath -Parent
    if (-not (Test-Path -Path $evidenceDir -PathType Container)) {
        New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
    }

    $evidenceDoc = $null
    if (Test-Path -Path $EvidencePath -PathType Leaf) {
        try {
            $rawJson = Get-Content -Path $EvidencePath -Raw -Encoding UTF8
            if ($rawJson) { $evidenceDoc = $rawJson | ConvertFrom-Json }
        } catch {}
    }

    if (-not $evidenceDoc) {
        $evidenceDoc = [PSCustomObject]@{
            timestamp       = [DateTime]::UtcNow.ToString("o")
            agent           = "Agent E (Windows Toolkit Verification Engineer)"
            mission         = "DRIVE-01"
            environment     = [PSCustomObject]@{
                os                  = [System.Environment]::OSVersion.VersionString
                powershell_version  = $PSVersionTable.PSVersion.ToString()
                powershell_edition  = $PSVersionTable.PSEdition
                user                = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
                machine             = $env:COMPUTERNAME
            }
            overall_status  = "PENDING"
            summary         = [PSCustomObject]@{
                total_tests     = 0
                passed_tests    = 0
                failed_tests    = 0
                success_rate    = "0%"
            }
            suites          = [PSCustomObject]@{}
        }
    }

    $suiteObj = [PSCustomObject]@{
        suite_name       = "Security Seams & PID Safety Verification"
        script           = "scripts/drive-tests/test_drive_security_seams.ps1"
        status           = $(if ($failedCount -eq 0) { "PASSED" } else { "FAILED" })
        total            = $totalCount
        passed           = $passedCount
        failed           = $failedCount
        duration_seconds = $durationSec
        tests            = $results
    }

    if (-not $evidenceDoc.suites) {
        $evidenceDoc | Add-Member -MemberType NoteProperty -Name "suites" -Value ([PSCustomObject]@{})
    }
    $evidenceDoc.suites | Add-Member -MemberType NoteProperty -Name "security_seams" -Value $suiteObj -Force

    # Recalculate summary across all recorded suites
    $allTotal = 0
    $allPassed = 0
    $allFailed = 0
    foreach ($p in $evidenceDoc.suites.PSObject.Properties) {
        if ($p.Value) {
            $allTotal  += [int]$p.Value.total
            $allPassed += [int]$p.Value.passed
            $allFailed += [int]$p.Value.failed
        }
    }

    $rate = if ($allTotal -gt 0) { "$([math]::Round(($allPassed / $allTotal) * 100, 1))%" } else { "0%" }
    $evidenceDoc.summary.total_tests  = $allTotal
    $evidenceDoc.summary.passed_tests = $allPassed
    $evidenceDoc.summary.failed_tests = $allFailed
    $evidenceDoc.summary.success_rate = $rate
    $evidenceDoc.overall_status       = if ($allFailed -eq 0) { "PASSED" } else { "FAILED" }
    $evidenceDoc.timestamp            = [DateTime]::UtcNow.ToString("o")

    $evidenceDoc | ConvertTo-Json -Depth 10 | Set-Content -Path $EvidencePath -Encoding UTF8
    Write-Host "Evidence JSON successfully updated at: $EvidencePath" -ForegroundColor Green
} catch {
    Write-Warning "Failed to write evidence JSON: $($_.Exception.Message)"
}

if ($failedCount -gt 0) {
    if (-not $NoExit) { exit 1 }
} else {
    if (-not $NoExit) { exit 0 }
}
