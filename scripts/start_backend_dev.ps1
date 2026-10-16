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

# Resolve java home
if (-not $env:JAVA_HOME -and (Test-Path "C:\Program Files\Java\jdk-25.0.3")) {
    $env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"
}

# R2 Fix: Always run incremental compilation to prevent stale bytecode execution
Write-Host "[start_backend_dev] Ensuring fresh bytecode via incremental compilation..."
cmd.exe /c "cd /d `"$backendDir`" && mvnw.cmd compile dependency:build-classpath `"-Dmdep.outputFile=target/cp.txt`" -q"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to compile backend or generate classpath via mvnw."
}

if (-not (Test-Path $classes) -or -not (Test-Path $cpFile)) {
    throw "Build artifacts missing after compilation: $classes or $cpFile"
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
    "--app.media.drive-metadata-timeout-ms=60000",
    "--app.media.drive-read-timeout-ms=60000"
)

# Start process and track PID / StartTime
$proc = Start-Process -FilePath $java -ArgumentList $argsList -PassThru -NoNewWindow
$startTime = $proc.StartTime

$state = [PSCustomObject]@{
    PID            = $proc.Id
    ProcessName    = $proc.ProcessName
    StartTime      = $startTime.ToString("o")
    ExecutablePath = $java
    CommandLine    = "$java $($argsList -join ' ')"
    Port           = 8080
    Address        = "127.0.0.1"
    Profile        = "snapshot"
}
$state | ConvertTo-Json -Depth 3 | Set-Content -Path $stateFile -Encoding UTF8
Write-Host "[start_backend_dev] Backend process spawned with PID $($proc.Id). Polling readiness endpoint..."

# R2 Fix: Poll real readiness endpoint with finite deadline (30 seconds)
$ready = $false
$deadline = [DateTime]::UtcNow.AddSeconds(35)
$readinessUrl = "http://127.0.0.1:8080/api/movies"

while ([DateTime]::UtcNow -lt $deadline) {
    if ($proc.HasExited) {
        Remove-Item -Path $stateFile -Force -ErrorAction SilentlyContinue
        throw "Backend process PID $($proc.Id) exited prematurely with exit code $($proc.ExitCode)."
    }

    try {
        $response = Invoke-WebRequest -Uri $readinessUrl -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        # Backend still starting up, wait and retry
        Start-Sleep -Milliseconds 600
    }
}

if (-not $ready) {
    Write-Warning "[start_backend_dev] Backend did not become ready within 35s. Terminating PID $($proc.Id)..."
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $stateFile -Force -ErrorAction SilentlyContinue
    throw "Readiness check timed out: Backend failed to respond on $readinessUrl within 35 seconds."
}

Write-Host "[start_backend_dev] SUCCESS: Backend verified ready on $readinessUrl (PID $($proc.Id)). State saved to $stateFile"

if (-not $Background) {
    try {
        $proc.WaitForExit()
    } finally {
        if (Test-Path $stateFile) {
            Remove-Item -Path $stateFile -Force -ErrorAction SilentlyContinue
        }
    }
}
