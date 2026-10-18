[CmdletBinding()]
param(
    [switch]$Background,
    [switch]$Jar,
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -Path $root

$backendDir = Join-Path $root "backend\springboot"
$classes = Join-Path $backendDir "target\classes"
$cpFile = Join-Path $backendDir "target\cp.txt"
$jarFile = Join-Path $backendDir "target\moviercm-backend-0.0.1-SNAPSHOT.jar"
$stateFile = Join-Path $backendDir "target\backend_dev.json"

# Resolve java home (process-scoped only, do not change OS environment)
if (-not $env:JAVA_HOME) {
    if (Test-Path "C:\Program Files\Java\jdk-25.0.3") {
        $env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"
    } else {
        $candidate = Get-ChildItem "C:\Program Files\Java\jdk-*" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($candidate) { $env:JAVA_HOME = $candidate.FullName }
    }
}

if ($Jar) {
    $needsBuild = -not (Test-Path $jarFile)
    if (-not $needsBuild) {
        $jarMtime = (Get-Item $jarFile).LastWriteTime
        $newestSrc = Get-ChildItem -Path (Join-Path $backendDir "src\main") -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($newestSrc -and ($newestSrc.LastWriteTime -gt $jarMtime)) {
            $needsBuild = $true
        }
    }
    if ($needsBuild) {
        Write-Host "[start_backend_dev] Building fresh jar $jarFile..."
        cmd.exe /c "cd /d `"$backendDir`" && mvnw.cmd clean package dependency:build-classpath `"-Dmdep.outputFile=target/cp.txt`" -DskipTests -q"
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $jarFile)) {
            throw "Failed to package backend jar via mvnw."
        }
    }
} else {
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
}

# Resolve java executable
$java = if ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME "bin\java.exe"))) {
    Join-Path $env:JAVA_HOME "bin\java.exe"
} elseif (Test-Path "C:\Program Files\Java\jdk-25.0.3\bin\java.exe") {
    "C:\Program Files\Java\jdk-25.0.3\bin\java.exe"
} else {
    (Get-Command java -ErrorAction Stop).Source
}

# Check port availability
$portConn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($portConn) {
    throw "Port $Port is already in use by PID $($portConn.OwningProcess). Please stop that process before starting backend."
}

Write-Host "[start_backend_dev] Starting Spring Boot (snapshot profile, loopback 127.0.0.1:$Port, Jar=$Jar)..."
$argsList = if ($Jar) {
    @(
        "-Dserver.address=127.0.0.1",
        "-Dserver.port=$Port",
        "-Dspring.profiles.active=snapshot",
        "-Dapp.media.drive-mount=X:",
        "-Dapp.media.drive-metadata-timeout-ms=60000",
        "-Dapp.media.drive-read-timeout-ms=60000",
        "-jar", $jarFile
    )
} else {
    @(
        "-cp", $cp,
        "com.dippie.moviercm.MovieRcmApplication",
        "--server.address=127.0.0.1",
        "--server.port=$Port",
        "--spring.profiles.active=snapshot",
        "--app.media.drive-mount=X:",
        "--app.media.drive-metadata-timeout-ms=60000",
        "--app.media.drive-read-timeout-ms=60000"
    )
}

# Start process and track PID / StartTime
$proc = Start-Process -FilePath $java -ArgumentList $argsList -PassThru -NoNewWindow
$startTime = $proc.StartTime

$state = [PSCustomObject]@{
    PID            = $proc.Id
    ProcessName    = $proc.ProcessName
    StartTime      = $startTime.ToString("o")
    ExecutablePath = $java
    CommandLine    = "$java $($argsList -join ' ')"
    Port           = $Port
    Address        = "127.0.0.1"
    Profile        = "snapshot"
}
$state | ConvertTo-Json -Depth 3 | Set-Content -Path $stateFile -Encoding UTF8
Write-Host "[start_backend_dev] Backend process spawned with PID $($proc.Id). Polling readiness endpoint..."

# R2 Fix: Poll real readiness endpoint with finite deadline (35 seconds)
$ready = $false
$deadline = [DateTime]::UtcNow.AddSeconds(35)
$readinessUrl = "http://127.0.0.1:$Port/api/movies"

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
