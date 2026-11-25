Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {}

$previewScript = Join-Path $PSScriptRoot "scripts\start_preview_stack.ps1"
$pythonMainScript = Join-Path $PSScriptRoot "start-python-main.ps1"

$hasOffMode = $false
for ($i = 0; $i -lt $args.Count; $i++) {
    $argStr = [string]$args[$i]
    if ($argStr -ieq "-ModelMode" -and ($i + 1) -lt $args.Count -and ([string]$args[$i + 1]) -ieq "off") {
        $hasOffMode = $true
        break
    }
    if ($argStr -imatch "^-ModelMode[:=]off$") {
        $hasOffMode = $true
        break
    }
}

$hasJavaRuntime = $false
if ($env:JAVA_HOME -and (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME "bin\java.exe") -PathType Leaf)) {
    $hasJavaRuntime = $true
} elseif (Get-Command java -ErrorAction SilentlyContinue) {
    $hasJavaRuntime = $true
} else {
    $jdkSearchRoots = @(
        "C:\Program Files\Java\jdk*",
        "C:\Program Files\Eclipse Adoptium\jdk*",
        "C:\Program Files\Microsoft\jdk*",
        "C:\Program Files\Amazon Corretto\jdk*",
        "C:\Program Files\Zulu\zulu*",
        "C:\Program Files\BellSoft\LibericaJDK*",
        "C:\Program Files\Semeru\jdk*",
        (Join-Path $env:LOCALAPPDATA "Programs\Eclipse Adoptium\jdk*"),
        (Join-Path $env:USERPROFILE ".jdks\*")
    )
    foreach ($pattern in $jdkSearchRoots) {
        $match = Get-ChildItem -Path $pattern -Directory -ErrorAction SilentlyContinue |
            Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "bin\java.exe") -PathType Leaf } |
            Select-Object -First 1
        if ($match) {
            $hasJavaRuntime = $true
            break
        }
    }
}

if (-not $hasJavaRuntime -and -not $hasOffMode -and (Test-Path -LiteralPath $pythonMainScript -PathType Leaf)) {
    Write-Warning "Không phát hiện Java JDK trên máy. Tự động chuyển sang chế độ Python Main (FastAPI + Next.js)."
    & $pythonMainScript @args
    exit $LASTEXITCODE
}

& $previewScript @args
exit $LASTEXITCODE
