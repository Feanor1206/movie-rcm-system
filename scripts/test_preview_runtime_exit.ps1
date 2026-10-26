[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$tokens = $null; $parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'start_preview_stack.ps1'), [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'Launcher parse failed' }
foreach ($name in @('Format-NativeArgument', 'Start-ChildServiceProcess')) {
    $helper = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
    . ([ScriptBlock]::Create($helper.Extent.Text))
}
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('preview-exit-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
try {
    foreach ($expectedCode in @(0, 7)) {
        $process = Start-ChildServiceProcess -FileName (Get-Command powershell.exe).Source `
            -Arguments @('-NoProfile', '-Command', "exit $expectedCode") -WorkingDirectory $tempRoot `
            -StdOutFile (Join-Path $tempRoot "$expectedCode.out") -StdErrFile (Join-Path $tempRoot "$expectedCode.err")
        if (-not $process.WaitForExit(10000)) { throw 'Owned exit-test child did not finish' }
        if ($null -eq $process.ExitCode -or $process.ExitCode -ne $expectedCode) { throw "Expected exit code $expectedCode, got '$($process.ExitCode)'" }
        $process.Dispose()
    }
    Write-Host 'PASS: redirected child processes retain native exit codes 0 and 7.'
} finally {
    foreach ($name in @('0.out', '0.err', '7.out', '7.err')) {
        $file = Join-Path $tempRoot $name
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Force }
    }
    Remove-Item -LiteralPath $tempRoot -Force
}
