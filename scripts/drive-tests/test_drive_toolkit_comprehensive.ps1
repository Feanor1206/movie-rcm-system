<#
.SYNOPSIS
    Comprehensive test suite for Google Drive operational tooling on Windows.
.DESCRIPTION
    Validates:
    1. Parameter handling: Whitespace, Unicode (Vietnamese, Japanese, diacritics), and complex paths
       in Remote, RemoteSubpath, MountPoint, and ConfigPath.
    2. Dry-Run mode: Both explicit (-WhatIf) and implicit (omitting -Execute), confirming zero
       background processes launched and zero state files persisted on disk.
    3. Mount collision detection (Occupied Mount Target): Active drive letters (e.g. C:, C:\) and
       non-empty directories, asserting proper collision detection and blocking.
    4. Baseline streaming flags: Exact enforcement of --read-only, --vfs-cache-mode off,
       --buffer-size 32M, --vfs-read-chunk-size 8M, --vfs-read-chunk-size-limit 32M,
       --vfs-read-chunk-streams 0, and auxiliary flags.
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
    $EvidencePath = Join-Path $scriptDir "..\..\docs\reports\drive\DRIVE_01\agent-e\toolkit_test_evidence.json"
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

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " AGENT E: COMPREHENSIVE TOOLKIT VERIFICATION (DRIVE-01)" -ForegroundColor Cyan
Write-Host " Target Toolkit : $toolkitDir" -ForegroundColor Cyan
Write-Host " Target Evidence: $EvidencePath" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

# ==============================================================================
# SUITE 1: Parameter Handling - Whitespace, Unicode & Complex Paths
# ==============================================================================
Write-Host "`n--- [SUITE 1] Parameter Robustness: Whitespace, Unicode & Complex Paths ---" -ForegroundColor Yellow

# Test 1.1: Remote with spaces and Vietnamese Unicode subpath
$t1Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $remoteWithSpace = "cinema gdrive:"
    $unicodeSubpath = "Kho Phim Việt/1080p - Bản Rõ & Đầy Đủ [2026]"
    $plan1 = & $mountPath -WhatIf -Remote $remoteWithSpace -RemoteSubpath $unicodeSubpath -MountPoint "M:"
    $t1Sw.Stop()

    $expectedTarget = "$remoteWithSpace$unicodeSubpath"
    $hasExpectedTarget = ($plan1.RemoteTarget -eq $expectedTarget)
    $cmdContainsTarget = ($plan1.ExpectedCommand -match [regex]::Escape($expectedTarget))
    $subpathPreserved = ($plan1.RemoteSubpath -eq $unicodeSubpath)

    $p1Passed = ($hasExpectedTarget -and $cmdContainsTarget -and $subpathPreserved)
    $msg = if (-not $p1Passed) { "Mismatch in target formatting or unicode preservation" } else { "" }
    Register-TestResult -TestId "TC-PARAM-01" -Category "Parameters" `
        -Name "Remote with whitespace and Vietnamese Unicode subpath" `
        -Description "Validates remote names containing spaces and subpaths with Vietnamese diacritics and brackets" `
        -Passed $p1Passed -FailureMessage $msg `
        -Expected $expectedTarget -Actual $plan1.RemoteTarget -DurationMs $t1Sw.Elapsed.TotalMilliseconds
} catch {
    $t1Sw.Stop()
    Register-TestResult -TestId "TC-PARAM-01" -Category "Parameters" `
        -Name "Remote with whitespace and Vietnamese Unicode subpath" `
        -Description "Validates remote names containing spaces and subpaths with Vietnamese diacritics and brackets" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t1Sw.Elapsed.TotalMilliseconds
}

# Test 1.2: Remote without trailing colon and Japanese/CJK Unicode subpath
$t2Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $remoteNoColon = "anime-gdrive"
    $cjkSubpath = "スタジオジブリ/映画/となりのトトロ (1988) [BD-Rip]"
    $plan2 = & $mountPath -WhatIf -Remote $remoteNoColon -RemoteSubpath $cjkSubpath -MountPoint "M:"
    $t2Sw.Stop()

    $expectedTarget2 = "$remoteNoColon`:$cjkSubpath"
    $hasColonNormalized = ($plan2.RemoteTarget -eq $expectedTarget2)
    $cmdMatches = ($plan2.ExpectedCommand -match [regex]::Escape($expectedTarget2))

    $p2Passed = ($hasColonNormalized -and $cmdMatches)
    $msg = if (-not $p2Passed) { "Failed to append colon properly or lost CJK characters" } else { "" }
    Register-TestResult -TestId "TC-PARAM-02" -Category "Parameters" `
        -Name "Remote without trailing colon and CJK Unicode subpath" `
        -Description "Validates automatic colon appending when omitted and preservation of CJK characters" `
        -Passed $p2Passed -FailureMessage $msg `
        -Expected $expectedTarget2 -Actual $plan2.RemoteTarget -DurationMs $t2Sw.Elapsed.TotalMilliseconds
} catch {
    $t2Sw.Stop()
    Register-TestResult -TestId "TC-PARAM-02" -Category "Parameters" `
        -Name "Remote without trailing colon and CJK Unicode subpath" `
        -Description "Validates automatic colon appending when omitted and preservation of CJK characters" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t2Sw.Elapsed.TotalMilliseconds
}

# Test 1.3: Empty Remote defaults to cinema-gdrive: and empty RemoteSubpath
$t3Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $plan3 = & $mountPath -WhatIf -Remote "" -RemoteSubpath "" -MountPoint "M:"
    $t3Sw.Stop()

    $expectedTarget3 = "cinema-gdrive:"
    $targetIsClean = ($plan3.RemoteTarget -eq $expectedTarget3)
    $noDoubleColons = (-not ($plan3.RemoteTarget -match "::"))

    $p3Passed = ($targetIsClean -and $noDoubleColons)
    $msg = if (-not $p3Passed) { "Empty remote or empty subpath resulted in malformed target: $($plan3.RemoteTarget)" } else { "" }
    Register-TestResult -TestId "TC-PARAM-03" -Category "Parameters" `
        -Name "Empty Remote fallback and empty RemoteSubpath clean handling" `
        -Description "Validates fallback to cinema-gdrive: without double colon or syntax errors when subpath is empty" `
        -Passed $p3Passed -FailureMessage $msg `
        -Expected $expectedTarget3 -Actual $plan3.RemoteTarget -DurationMs $t3Sw.Elapsed.TotalMilliseconds
} catch {
    $t3Sw.Stop()
    Register-TestResult -TestId "TC-PARAM-03" -Category "Parameters" `
        -Name "Empty Remote fallback and empty RemoteSubpath clean handling" `
        -Description "Validates fallback to cinema-gdrive: without double colon or syntax errors when subpath is empty" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t3Sw.Elapsed.TotalMilliseconds
}

# Test 1.4: ConfigPath with spaces, unicode and symbols
$t4Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $complexConfigPath = "C:\Users\Admin\Đường Dẫn Cấu Hình (Rclone)\rclone test [safe].conf"
    $plan4 = & $mountPath -WhatIf -ConfigPath $complexConfigPath -MountPoint "M:"
    $t4Sw.Stop()

    $configReported = ($plan4.ConfigProvided -eq $true)
    $cmdHasConfigArg = ($plan4.ExpectedCommand -match "--config\s+")
    $cmdContainsPath = ($plan4.ExpectedCommand -match [regex]::Escape($complexConfigPath))

    $p4Passed = ($configReported -and $cmdHasConfigArg -and $cmdContainsPath)
    $msg = if (-not $p4Passed) { "Config path with spaces/unicode not properly passed into command preview" } else { "" }
    Register-TestResult -TestId "TC-PARAM-04" -Category "Parameters" `
        -Name "ConfigPath with spaces, unicode, and symbols in ExpectedCommand" `
        -Description "Validates proper inclusion of complex config path with spaces and unicode diacritics in expected command" `
        -Passed $p4Passed -FailureMessage $msg `
        -Expected "Contains $complexConfigPath" -Actual $plan4.ExpectedCommand -DurationMs $t4Sw.Elapsed.TotalMilliseconds
} catch {
    $t4Sw.Stop()
    Register-TestResult -TestId "TC-PARAM-04" -Category "Parameters" `
        -Name "ConfigPath with spaces, unicode, and symbols in ExpectedCommand" `
        -Description "Validates proper inclusion of complex config path with spaces and unicode diacritics in expected command" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t4Sw.Elapsed.TotalMilliseconds
}

# Test 1.5: MountPoint drive letter variations (case insensitivity and slash variations)
$t5Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $planLower = & $mountPath -WhatIf -MountPoint "m:"
    $planSlash = & $mountPath -WhatIf -MountPoint "M:\"
    $t5Sw.Stop()

    $p5Passed = ($planLower.MountPoint -eq "m:") -and ($planSlash.MountPoint -eq "M:\")
    Register-TestResult -TestId "TC-PARAM-05" -Category "Parameters" `
        -Name "MountPoint accepts lowercase and trailing backslash drive letters" `
        -Description "Validates drive letter formatting robustness for lowercase and trailing backslash" `
        -Passed $p5Passed -FailureMessage "" `
        -Expected "m: and M:\" -Actual "$($planLower.MountPoint) and $($planSlash.MountPoint)" `
        -DurationMs $t5Sw.Elapsed.TotalMilliseconds
} catch {
    $t5Sw.Stop()
    Register-TestResult -TestId "TC-PARAM-05" -Category "Parameters" `
        -Name "MountPoint accepts lowercase and trailing backslash drive letters" `
        -Description "Validates drive letter formatting robustness for lowercase and trailing backslash" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t5Sw.Elapsed.TotalMilliseconds
}

# ==============================================================================
# SUITE 2: Dry-Run Mode & State Non-Persistence Verification
# ==============================================================================
Write-Host "`n--- [SUITE 2] Dry-Run Mode & State Non-Persistence ---" -ForegroundColor Yellow

# Test 2.1: Default invocation without -Execute is Dry-Run
$t6Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $defaultPlan = & $mountPath
    $t6Sw.Stop()

    $isDry = ($defaultPlan.Mode -eq "DRY_RUN") -and ($defaultPlan.IsExecute -eq $false)
    Register-TestResult -TestId "TC-DRY-01" -Category "DryRun" `
        -Name "Default invocation without -Execute defaults to Dry-Run" `
        -Description "Confirms that invoking mount_drive without parameters produces a safe dry-run plan" `
        -Passed $isDry -FailureMessage "Mode is '$($defaultPlan.Mode)', IsExecute is '$($defaultPlan.IsExecute)'" `
        -Expected "Mode=DRY_RUN, IsExecute=False" -Actual "Mode=$($defaultPlan.Mode), IsExecute=$($defaultPlan.IsExecute)" `
        -DurationMs $t6Sw.Elapsed.TotalMilliseconds
} catch {
    $t6Sw.Stop()
    Register-TestResult -TestId "TC-DRY-01" -Category "DryRun" `
        -Name "Default invocation without -Execute defaults to Dry-Run" `
        -Description "Confirms that invoking mount_drive without parameters produces a safe dry-run plan" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t6Sw.Elapsed.TotalMilliseconds
}

# Test 2.2: Explicit -WhatIf sets Dry-Run mode
$t7Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $whatIfPlan = & $mountPath -WhatIf -Remote "cinema-gdrive:"
    $t7Sw.Stop()

    $isWhatIf = ($whatIfPlan.Mode -eq "DRY_RUN") -and ($whatIfPlan.IsExecute -eq $false)
    Register-TestResult -TestId "TC-DRY-02" -Category "DryRun" `
        -Name "Explicit -WhatIf switch produces Dry-Run plan" `
        -Description "Confirms explicit -WhatIf switch produces DRY_RUN plan" `
        -Passed $isWhatIf -FailureMessage "Mode is '$($whatIfPlan.Mode)', IsExecute is '$($whatIfPlan.IsExecute)'" `
        -Expected "Mode=DRY_RUN, IsExecute=False" -Actual "Mode=$($whatIfPlan.Mode), IsExecute=$($whatIfPlan.IsExecute)" `
        -DurationMs $t7Sw.Elapsed.TotalMilliseconds
} catch {
    $t7Sw.Stop()
    Register-TestResult -TestId "TC-DRY-02" -Category "DryRun" `
        -Name "Explicit -WhatIf switch produces Dry-Run plan" `
        -Description "Confirms explicit -WhatIf switch produces DRY_RUN plan" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t7Sw.Elapsed.TotalMilliseconds
}

# Test 2.3: -WhatIf takes precedence over -Execute
$t8Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $conflictPlan = & $mountPath -WhatIf -Execute -Remote "cinema-gdrive:"
    $t8Sw.Stop()

    $whatIfDominates = ($conflictPlan.Mode -eq "DRY_RUN") -and ($conflictPlan.IsExecute -eq $false)
    Register-TestResult -TestId "TC-DRY-03" -Category "DryRun" `
        -Name "-WhatIf overrides -Execute to guarantee dry-run safety" `
        -Description "Validates that passing both -WhatIf and -Execute safely resolves to dry-run" `
        -Passed $whatIfDominates -FailureMessage "Mode was $($conflictPlan.Mode)" `
        -Expected "Mode=DRY_RUN" -Actual $conflictPlan.Mode -DurationMs $t8Sw.Elapsed.TotalMilliseconds
} catch {
    $t8Sw.Stop()
    Register-TestResult -TestId "TC-DRY-03" -Category "DryRun" `
        -Name "-WhatIf overrides -Execute to guarantee dry-run safety" `
        -Description "Validates that passing both -WhatIf and -Execute safely resolves to dry-run" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t8Sw.Elapsed.TotalMilliseconds
}

# Test 2.4: Zero processes spawned during Dry-Run
$t9Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $rcloneProcsBefore = @(Get-Process -Name "rclone" -ErrorAction SilentlyContinue)
    $null = & $mountPath -WhatIf -Remote "cinema-gdrive:" -RemoteSubpath "DippieMedia"
    $rcloneProcsAfter = @(Get-Process -Name "rclone" -ErrorAction SilentlyContinue)
    $t9Sw.Stop()

    $noNewProcesses = ($rcloneProcsAfter.Count -eq $rcloneProcsBefore.Count)
    Register-TestResult -TestId "TC-DRY-04" -Category "DryRun" `
        -Name "Dry-Run launches zero processes" `
        -Description "Confirms no background rclone process is spawned during dry-run evaluation" `
        -Passed $noNewProcesses -FailureMessage "Process count changed: Before=$($rcloneProcsBefore.Count), After=$($rcloneProcsAfter.Count)" `
        -Expected "Zero new processes" -Actual "$($rcloneProcsAfter.Count - $rcloneProcsBefore.Count) new processes" `
        -DurationMs $t9Sw.Elapsed.TotalMilliseconds
} catch {
    $t9Sw.Stop()
    Register-TestResult -TestId "TC-DRY-04" -Category "DryRun" `
        -Name "Dry-Run launches zero processes" `
        -Description "Confirms no background rclone process is spawned during dry-run evaluation" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t9Sw.Elapsed.TotalMilliseconds
}

# Test 2.5: Zero state files written to disk during Dry-Run
$t10Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $testStateFile = Join-Path ([System.IO.Path]::GetTempPath()) "test-dryrun-state-$([Guid]::NewGuid().ToString('N')).json"
    $planDry = & $mountPath -WhatIf -StateFile $testStateFile -Remote "cinema-gdrive:"
    $t10Sw.Stop()

    $fileCreated = Test-Path -Path $testStateFile -PathType Leaf
    if ($fileCreated) {
        Remove-Item -Path $testStateFile -Force -ErrorAction SilentlyContinue
    }

    $stateNotPersisted = (-not $fileCreated)
    Register-TestResult -TestId "TC-DRY-05" -Category "DryRun" `
        -Name "Dry-Run does not create or persist state file on disk" `
        -Description "Confirms that target StateFile path is untouched when operating in dry-run mode" `
        -Passed $stateNotPersisted -FailureMessage "State file was created at $testStateFile" `
        -Expected "State file should NOT exist" -Actual "Exists: $fileCreated" `
        -DurationMs $t10Sw.Elapsed.TotalMilliseconds
} catch {
    $t10Sw.Stop()
    Register-TestResult -TestId "TC-DRY-05" -Category "DryRun" `
        -Name "Dry-Run does not create or persist state file on disk" `
        -Description "Confirms that target StateFile path is untouched when operating in dry-run mode" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t10Sw.Elapsed.TotalMilliseconds
}

# Test 2.6: -AsJson switch produces valid JSON schema in Dry-Run
$t11Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $jsonOutput = & $mountPath -WhatIf -AsJson -Remote "cinema-gdrive:"
    $t11Sw.Stop()

    $parsedJson = $null
    $jsonValid = $false
    try {
        $parsedJson = $jsonOutput | ConvertFrom-Json
        $jsonValid = ($parsedJson -ne $null) -and ($parsedJson.Mode -eq "DRY_RUN")
    } catch {
        $jsonValid = $false
    }

    Register-TestResult -TestId "TC-DRY-06" -Category "DryRun" `
        -Name "-AsJson switch outputs valid parsable JSON object" `
        -Description "Verifies strict JSON output formatting for automation pipelines" `
        -Passed $jsonValid -FailureMessage "Failed to parse JSON string or Mode is not DRY_RUN" `
        -Expected "Valid JSON with Mode=DRY_RUN" -Actual $(if ($parsedJson) { $parsedJson.Mode } else { "Invalid JSON" }) `
        -DurationMs $t11Sw.Elapsed.TotalMilliseconds
} catch {
    $t11Sw.Stop()
    Register-TestResult -TestId "TC-DRY-06" -Category "DryRun" `
        -Name "-AsJson switch outputs valid parsable JSON object" `
        -Description "Verifies strict JSON output formatting for automation pipelines" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t11Sw.Elapsed.TotalMilliseconds
}

# ==============================================================================
# SUITE 3: Occupied Mount Target (Collision Detection)
# ==============================================================================
Write-Host "`n--- [SUITE 3] Mount Target Collision Detection ---" -ForegroundColor Yellow

# Test 3.1: Occupied system drive letter C:
$t12Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $preflightC = & $preflightPath -MountPoint "C:" | ConvertFrom-Json
    $t12Sw.Stop()

    $cBlocked = ($preflightC.MountTarget.Available -eq $false)
    $hasReason = ($preflightC.MountTarget.ConflictReason -match "in use|already assigned")
    $readinessBlocked = ($preflightC.IsReady -eq $false)

    $p12Passed = ($cBlocked -and $hasReason -and $readinessBlocked)
    $msg = if (-not $p12Passed) { "Drive C: collision was not properly flagged" } else { "" }
    Register-TestResult -TestId "TC-COLLISION-01" -Category "Collision" `
        -Name "Occupied system drive letter C: collision detected" `
        -Description "Validates preflight detects active drive C: as unavailable and includes conflict reason" `
        -Passed $p12Passed -FailureMessage $msg `
        -Expected "Available=False, IsReady=False" `
        -Actual "Available=$($preflightC.MountTarget.Available), Reason=$($preflightC.MountTarget.ConflictReason)" `
        -DurationMs $t12Sw.Elapsed.TotalMilliseconds
} catch {
    $t12Sw.Stop()
    Register-TestResult -TestId "TC-COLLISION-01" -Category "Collision" `
        -Name "Occupied system drive letter C: collision detected" `
        -Description "Validates preflight detects active drive C: as unavailable and includes conflict reason" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t12Sw.Elapsed.TotalMilliseconds
}

# Test 3.2: Occupied drive letter with trailing slash C:\
$t13Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $preflightCSlash = & $preflightPath -MountPoint "C:\" | ConvertFrom-Json
    $t13Sw.Stop()

    $slashBlocked = ($preflightCSlash.MountTarget.Available -eq $false)
    Register-TestResult -TestId "TC-COLLISION-02" -Category "Collision" `
        -Name "Occupied drive letter with trailing slash (C:\) collision detected" `
        -Description "Validates drive collision detection handles trailing backslash normalization" `
        -Passed $slashBlocked -FailureMessage "C:\ was reported as Available: $($preflightCSlash.MountTarget.Available)" `
        -Expected "Available=False" -Actual "Available=$($preflightCSlash.MountTarget.Available)" `
        -DurationMs $t13Sw.Elapsed.TotalMilliseconds
} catch {
    $t13Sw.Stop()
    Register-TestResult -TestId "TC-COLLISION-02" -Category "Collision" `
        -Name "Occupied drive letter with trailing slash (C:\) collision detected" `
        -Description "Validates drive collision detection handles trailing backslash normalization" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t13Sw.Elapsed.TotalMilliseconds
}

# Test 3.3: Available unused drive letter detection (e.g. searching Z..E)
$t14Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $usedLetters = (Get-PSDrive -PSProvider FileSystem | Select-Object -ExpandProperty Name)
    $availableLetter = $null
    foreach ($candidate in @("Z", "Y", "X", "W", "V", "U", "T", "S", "R", "Q", "P", "N", "M")) {
        if ($candidate -notin $usedLetters) {
            $availableLetter = "$candidate`:"
            break
        }
    }

    if (-not $availableLetter) {
        throw "Could not find an unused drive letter for collision baseline test"
    }

    $preflightFree = & $preflightPath -MountPoint $availableLetter | ConvertFrom-Json
    $t14Sw.Stop()

    $isFree = ($preflightFree.MountTarget.Available -eq $true)
    Register-TestResult -TestId "TC-COLLISION-03" -Category "Collision" `
        -Name "Unassigned drive letter ($availableLetter) recognized as available" `
        -Description "Validates that an unused drive letter passes target collision check" `
        -Passed $isFree -FailureMessage "Unused drive $availableLetter was flagged as unavailable" `
        -Expected "Available=True" -Actual "Available=$($preflightFree.MountTarget.Available)" `
        -DurationMs $t14Sw.Elapsed.TotalMilliseconds
} catch {
    $t14Sw.Stop()
    Register-TestResult -TestId "TC-COLLISION-03" -Category "Collision" `
        -Name "Unassigned drive letter recognized as available" `
        -Description "Validates that an unused drive letter passes target collision check" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t14Sw.Elapsed.TotalMilliseconds
}

# Test 3.4: Occupied directory collision (non-empty directory)
$t15Sw = [System.Diagnostics.Stopwatch]::StartNew()
$tempOccupiedDir = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-collision-dir-$([Guid]::NewGuid().ToString('N'))"
try {
    New-Item -ItemType Directory -Path $tempOccupiedDir -Force | Out-Null
    # Create multiple files to ensure collection count is robust in StrictMode
    Set-Content -Path (Join-Path $tempOccupiedDir "file1.txt") -Value "payload1"
    Set-Content -Path (Join-Path $tempOccupiedDir "file2.txt") -Value "payload2"

    $preflightDir = & $preflightPath -MountPoint $tempOccupiedDir | ConvertFrom-Json
    $t15Sw.Stop()

    $dirBlocked = ($preflightDir.MountTarget.Available -eq $false)
    $dirReasonMatch = ($preflightDir.MountTarget.ConflictReason -match "not empty")

    $p15Passed = ($dirBlocked -and $dirReasonMatch)
    $msg = if (-not $p15Passed) { "Non-empty directory was not blocked: $($preflightDir.MountTarget.ConflictReason)" } else { "" }
    Register-TestResult -TestId "TC-COLLISION-04" -Category "Collision" `
        -Name "Non-empty directory collision detected" `
        -Description "Validates that targeting a non-empty directory is blocked as unavailable" `
        -Passed $p15Passed -FailureMessage $msg `
        -Expected "Available=False with 'not empty' reason" `
        -Actual "Available=$($preflightDir.MountTarget.Available), Reason=$($preflightDir.MountTarget.ConflictReason)" `
        -DurationMs $t15Sw.Elapsed.TotalMilliseconds
} catch {
    $t15Sw.Stop()
    Register-TestResult -TestId "TC-COLLISION-04" -Category "Collision" `
        -Name "Non-empty directory collision detected" `
        -Description "Validates that targeting a non-empty directory is blocked as unavailable" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t15Sw.Elapsed.TotalMilliseconds
} finally {
    if (Test-Path -Path $tempOccupiedDir) {
        Remove-Item -Path $tempOccupiedDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Test 3.5: Regular file passed as mount target
$t16Sw = [System.Diagnostics.Stopwatch]::StartNew()
$tempTargetFile = Join-Path ([System.IO.Path]::GetTempPath()) "movie-rcm-file-target-$([Guid]::NewGuid().ToString('N')).txt"
try {
    Set-Content -Path $tempTargetFile -Value "regular file content"
    $preflightFileTarget = & $preflightPath -MountPoint $tempTargetFile | ConvertFrom-Json
    $t16Sw.Stop()

    $fileBlocked = ($preflightFileTarget.MountTarget.Available -eq $false)
    $fileReasonMatch = ($preflightFileTarget.MountTarget.ConflictReason -match "regular file, not a directory")

    $p16Passed = ($fileBlocked -and $fileReasonMatch)
    $msg = if (-not $p16Passed) { "Regular file target was not rejected: $($preflightFileTarget.MountTarget.ConflictReason)" } else { "" }
    Register-TestResult -TestId "TC-COLLISION-05" -Category "Collision" `
        -Name "Regular file collision rejected as invalid mount target" `
        -Description "Validates preflight rejects existing regular files passed as directory mount targets" `
        -Passed $p16Passed -FailureMessage $msg `
        -Expected "Available=False with regular file error" `
        -Actual "Available=$($preflightFileTarget.MountTarget.Available), Reason=$($preflightFileTarget.MountTarget.ConflictReason)" `
        -DurationMs $t16Sw.Elapsed.TotalMilliseconds
} catch {
    $t16Sw.Stop()
    Register-TestResult -TestId "TC-COLLISION-05" -Category "Collision" `
        -Name "Regular file collision rejected as invalid mount target" `
        -Description "Validates preflight rejects existing regular files passed as directory mount targets" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t16Sw.Elapsed.TotalMilliseconds
} finally {
    if (Test-Path -Path $tempTargetFile) {
        Remove-Item -Path $tempTargetFile -Force -ErrorAction SilentlyContinue
    }
}

# Test 3.6: Mount collision surfaced in mount_drive dry-run blockers
$t17Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $mountPlanC = & $mountPath -WhatIf -MountPoint "C:"
    $t17Sw.Stop()

    $planBlocked = ($mountPlanC.PreflightIsReady -eq $false)
    $blockersJoined = ($mountPlanC.PreflightBlockers -join "; ")
    $hasMountBlocker = ($blockersJoined -match "Mount target 'C:' is unavailable")

    $p17Passed = ($planBlocked -and $hasMountBlocker)
    Register-TestResult -TestId "TC-COLLISION-06" -Category "Collision" `
        -Name "mount_drive surfaces mount collision in PreflightBlockers" `
        -Description "Validates that mount_drive plan surfaces collision reasons in PreflightBlockers list" `
        -Passed $p17Passed -FailureMessage "Blockers missing collision notice: $blockersJoined" `
        -Expected "PreflightIsReady=False with collision in PreflightBlockers" `
        -Actual "PreflightIsReady=$($mountPlanC.PreflightIsReady), Blockers=$blockersJoined" `
        -DurationMs $t17Sw.Elapsed.TotalMilliseconds
} catch {
    $t17Sw.Stop()
    Register-TestResult -TestId "TC-COLLISION-06" -Category "Collision" `
        -Name "mount_drive surfaces mount collision in PreflightBlockers" `
        -Description "Validates that mount_drive plan surfaces collision reasons in PreflightBlockers list" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t17Sw.Elapsed.TotalMilliseconds
}

# ==============================================================================
# SUITE 4: Standard Baseline Streaming Flags Verification
# ==============================================================================
Write-Host "`n--- [SUITE 4] Baseline Streaming Flags Verification ---" -ForegroundColor Yellow

$t18Sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $planFlags = & $mountPath -WhatIf -Remote "cinema-gdrive:" -RemoteSubpath "DippieMedia" -MountPoint "M:"
    $t18Sw.Stop()

    $flagsList = $planFlags.BaselineFlags
    $cmdStr    = [string]$planFlags.ExpectedCommand
    $flagStr   = [string]$planFlags.BaselineFlagsString

    # 1. --read-only
    $hasReadOnly = ($flagsList -contains "--read-only") -and ($cmdStr -match "--read-only")
    Register-TestResult -TestId "TC-FLAGS-01" -Category "StreamingFlags" `
        -Name "Enforce --read-only baseline flag" `
        -Description "Validates --read-only flag is present in flags list and command line" `
        -Passed $hasReadOnly -FailureMessage "Missing --read-only flag" `
        -Expected "--read-only" -Actual $hasReadOnly -DurationMs 1

    # 2. --vfs-cache-mode off
    $vfsCacheIdx = [array]::IndexOf($flagsList, "--vfs-cache-mode")
    $hasVfsOff = ($vfsCacheIdx -ge 0) -and ($flagsList[$vfsCacheIdx + 1] -eq "off") -and ($cmdStr -match "--vfs-cache-mode\s+off")
    Register-TestResult -TestId "TC-FLAGS-02" -Category "StreamingFlags" `
        -Name "Enforce --vfs-cache-mode off (Direct RAM streaming)" `
        -Description "Validates cache mode is strictly set to off for pure RAM streaming without local caching" `
        -Passed $hasVfsOff -FailureMessage "Missing or incorrect --vfs-cache-mode off" `
        -Expected "--vfs-cache-mode off" -Actual $hasVfsOff -DurationMs 1

    # 3. --buffer-size 32M
    $bufIdx = [array]::IndexOf($flagsList, "--buffer-size")
    $hasBuf32M = ($bufIdx -ge 0) -and ($flagsList[$bufIdx + 1] -eq "32M") -and ($cmdStr -match "--buffer-size\s+32M")
    Register-TestResult -TestId "TC-FLAGS-03" -Category "StreamingFlags" `
        -Name "Enforce --buffer-size 32M (RFC 9110 compliant RAM buffer)" `
        -Description "Validates RAM read buffer size is bounded to 32MB" `
        -Passed $hasBuf32M -FailureMessage "Missing or incorrect --buffer-size 32M" `
        -Expected "--buffer-size 32M" -Actual $hasBuf32M -DurationMs 1

    # 4. --vfs-read-chunk-size 8M
    $chunkIdx = [array]::IndexOf($flagsList, "--vfs-read-chunk-size")
    $hasChunk8M = ($chunkIdx -ge 0) -and ($flagsList[$chunkIdx + 1] -eq "8M") -and ($cmdStr -match "--vfs-read-chunk-size\s+8M")
    Register-TestResult -TestId "TC-FLAGS-04" -Category "StreamingFlags" `
        -Name "Enforce --vfs-read-chunk-size 8M (Initial fast seek chunk)" `
        -Description "Validates initial read chunk size is set to 8MB" `
        -Passed $hasChunk8M -FailureMessage "Missing or incorrect --vfs-read-chunk-size 8M" `
        -Expected "--vfs-read-chunk-size 8M" -Actual $hasChunk8M -DurationMs 1

    # 5. --vfs-read-chunk-size-limit 32M
    $limitIdx = [array]::IndexOf($flagsList, "--vfs-read-chunk-size-limit")
    $hasLimit32M = ($limitIdx -ge 0) -and ($flagsList[$limitIdx + 1] -eq "32M") -and ($cmdStr -match "--vfs-read-chunk-size-limit\s+32M")
    Register-TestResult -TestId "TC-FLAGS-05" -Category "StreamingFlags" `
        -Name "Enforce --vfs-read-chunk-size-limit 32M (Maximum chunk cap)" `
        -Description "Validates chunk size limit does not exceed 32MB cap" `
        -Passed $hasLimit32M -FailureMessage "Missing or incorrect --vfs-read-chunk-size-limit 32M" `
        -Expected "--vfs-read-chunk-size-limit 32M" -Actual $hasLimit32M -DurationMs 1

    # 6. --vfs-read-chunk-streams 0
    $streamIdx = [array]::IndexOf($flagsList, "--vfs-read-chunk-streams")
    $hasStreams0 = ($streamIdx -ge 0) -and ($flagsList[$streamIdx + 1] -eq "0") -and ($cmdStr -match "--vfs-read-chunk-streams\s+0")
    Register-TestResult -TestId "TC-FLAGS-06" -Category "StreamingFlags" `
        -Name "Enforce --vfs-read-chunk-streams 0 (Sequential stream isolation)" `
        -Description "Validates chunk streams is disabled (0) to eliminate multi-range head races" `
        -Passed $hasStreams0 -FailureMessage "Missing or incorrect --vfs-read-chunk-streams 0" `
        -Expected "--vfs-read-chunk-streams 0" -Actual $hasStreams0 -DurationMs 1

    # 7. Auxiliary metadata performance flags
    $hasDirCache = ($cmdStr -match "--dir-cache-time\s+72h")
    $hasPollInt  = ($cmdStr -match "--poll-interval\s+15s")
    $hasAttrTime = ($cmdStr -match "--attr-timeout\s+1s")
    $pAuxPassed  = ($hasDirCache -and $hasPollInt -and $hasAttrTime)
    Register-TestResult -TestId "TC-FLAGS-07" -Category "StreamingFlags" `
        -Name "Enforce directory and attribute cache flags (72h dir-cache, 15s poll, 1s attr)" `
        -Description "Validates performance metadata caching flags for low API request overhead" `
        -Passed $pAuxPassed -FailureMessage "Missing auxiliary caching flags in command string" `
        -Expected "dir-cache 72h, poll-interval 15s, attr-timeout 1s" -Actual $pAuxPassed -DurationMs 1
} catch {
    $t18Sw.Stop()
    Register-TestResult -TestId "TC-FLAGS-00" -Category "StreamingFlags" `
        -Name "Baseline streaming flags extraction" `
        -Description "Validates error-free execution of baseline flag extraction" `
        -Passed $false -FailureMessage $_.Exception.Message -DurationMs $t18Sw.Elapsed.TotalMilliseconds
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
Write-Host " COMPREHENSIVE TOOLKIT VERIFICATION SUMMARY" -ForegroundColor Cyan
Write-Host " Total Tests : $totalCount"
Write-Host " Passed      : $passedCount" -ForegroundColor $(if ($passedCount -eq $totalCount) { "Green" } else { "Yellow" })
Write-Host " Failed      : $failedCount" -ForegroundColor $(if ($failedCount -eq 0) { "Green" } else { "Red" })
Write-Host " Duration    : $durationSec seconds"
Write-Host "================================================================================" -ForegroundColor Cyan

# Update or create shared evidence JSON
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

    # Attach this suite results
    $suiteObj = [PSCustomObject]@{
        suite_name       = "Comprehensive Toolkit Verification"
        script           = "scripts/drive-tests/test_drive_toolkit_comprehensive.ps1"
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
    $evidenceDoc.suites | Add-Member -MemberType NoteProperty -Name "comprehensive_toolkit" -Value $suiteObj -Force

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
