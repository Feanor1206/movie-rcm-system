[CmdletBinding()]
param(
    [switch]$Background
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -Path $root

$backendDir = Join-Path $root "backend\springboot"
$classes = Join-Path $backendDir "target\classes"
$cpFile = Join-Path $backendDir "target\cp.txt"
$stateFile = Join-Path $backendDir "target\backend_dev.json"

# Auto-build target classes and dependency classpath if missing
if (-not (Test-Path $classes) -or -not (Test-Path $cpFile)) {
    Write-Host "[start_backend_dev] Classes or classpath missing. Compiling and generating classpath..."
    $mvnw = Join-Path $backendDir "mvnw.cmd"
    if (-not $env:JAVA_HOME -and (Test-Path "C:\Program Files\Java\jdk-25.0.3")) {
        $env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"
    }
    & $mvnw compile dependency:build-classpath "-Dmdep.outputFile=target/cp.txt" -f (Join-Path $backendDir "pom.xml")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to compile backend or generate classpath via mvnw."
    }
} elseif (Test-Path (Join-Path $backendDir "src\main\resources\application.yml")) {
    $srcRes = Join-Path $backendDir "src\main\resources\application.yml"
    $tgtRes = Join-Path $classes "application.yml"
    if (-not (Test-Path $tgtRes) -or (Get-Item $srcRes).LastWriteTime -gt (Get-Item $tgtRes).LastWriteTime) {
        Copy-Item (Join-Path $backendDir "src\main\resources\*") $classes -Recurse -Force
    }
}

$dependencies = (Get-Content $cpFile -Raw).Trim()
$cp = "$classes;$dependencies"

# Resolve java executable
$java = if ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME "bin\java.exe"))) {
    Join-Path $env:JAVA_HOME "bin\java.exe"
} elseif (Test-Path "C:\Program Files\Java\jdk-25.0.3\bin\java.exe") {
    "C:\Program Files\Java\jdk-25.0.3\bin\java.exe"
} else {
    (Get-Command java -ErrorAction Stop).Source
}

# Check port 8080 availability
$portConn = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
if ($portConn) {
    throw "Port 8080 is already in use by PID $($portConn.OwningProcess). Please stop that process before starting backend."
}

Write-Host "[start_backend_dev] Starting Spring Boot (snapshot profile, loopback 127.0.0.1:8080)..."
$argsList = @(
    "-cp", $cp,
    "com.dippie.moviercm.MovieRcmApplication",
    "--server.address=127.0.0.1",
    "--server.port=8080",
    "--spring.profiles.active=snapshot",
    "--app.media.drive-mount=X:",
    "--app.media.drive-metadata-timeout-ms=15000",
    "--app.media.drive-read-timeout-ms=15000"
)

# Start process and track PID / StartTime
$proc = Start-Process -FilePath $java -ArgumentList $argsList -PassThru -NoNewWindow
Start-Sleep -Milliseconds 500

$state = [PSCustomObject]@{
    PID            = $proc.Id
    ProcessName    = $proc.ProcessName
    StartTime      = $proc.StartTime.ToString("o")
    ExecutablePath = $java
    CommandLine    = "$java $($argsList -join ' ')"
    Port           = 8080
    Address        = "127.0.0.1"
    Profile        = "snapshot"
}
$state | ConvertTo-Json -Depth 3 | Set-Content -Path $stateFile -Encoding UTF8
Write-Host "[start_backend_dev] Backend started with PID $($proc.Id). State recorded at $stateFile"

if (-not $Background) {
    try {
        $proc.WaitForExit()
    } finally {
        if (Test-Path $stateFile) {
            Remove-Item -Path $stateFile -Force -ErrorAction SilentlyContinue
        }
    }
}
