[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$launcherPath = Join-Path $PSScriptRoot "start_preview_stack.ps1"
$tokens = $null
$parseErrors = $null
$launcherAst = [System.Management.Automation.Language.Parser]::ParseFile($launcherPath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) {
    throw "start_preview_stack.ps1 has PowerShell parse errors: $($parseErrors[0].Message)"
}

$helperAsts = @($launcherAst.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        @("Format-NativeArgument", "Start-ChildServiceProcess") -contains $node.Name
}, $true))
if ($helperAsts.Count -ne 2) {
    throw "Expected to find the launcher argument and process helpers."
}
foreach ($helperAst in $helperAsts) {
    . ([ScriptBlock]::Create($helperAst.Extent.Text))
}

function Assert-Equal {
    param($Expected, $Actual, [string]$Message)
    if ($Expected -cne $Actual) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
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
    if ($script:failStart) {
        throw "Injected Start-Process failure for launcher helper test."
    }
    return [PSCustomObject]@{ Id = 99; StartTime = [DateTime]::UtcNow }
}

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
        Start-ChildServiceProcess `
            -FileName "preview-child.exe" `
            -Arguments @() `
            -WorkingDirectory $env:TEMP `
            -EnvironmentVariables $childEnvironment `
            -StdOutFile "unused.stdout.log" `
            -StdErrFile "unused.stderr.log" | Out-Null
        throw "Expected injected process start failure."
    } catch {
        if ($_.Exception.Message -ne "Injected Start-Process failure for launcher helper test.") { throw }
    }
    Assert-Equal "parent-value" ([System.Environment]::GetEnvironmentVariable($script:testVariable, "Process")) "Parent environment changed after a failed spawn."

    $launcherText = Get-Content -LiteralPath $launcherPath -Raw
    if ($launcherText -match '-Dapp\.catalog\.sync-token=\$SyncSecret') {
        throw "Catalog sync secret must not be included in the Java command line."
    }
    if ($launcherText -notmatch '\$sbEnv\["CATALOG_SYNC_TOKEN"\]\s*=\s*\$SyncSecret') {
        throw "Spring Boot child environment is missing CATALOG_SYNC_TOKEN."
    }
    if ($launcherText -notmatch 'pom\.xml') {
        throw "Backend artifact freshness check does not include pom.xml."
    }

    Write-Host "PASS: launcher helpers parse, quote arguments, isolate child environment, and keep the sync secret out of Java arguments."
} finally {
    [System.Environment]::SetEnvironmentVariable($script:testVariable, $originalValue, "Process")
}
