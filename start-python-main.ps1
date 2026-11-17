[CmdletBinding()]
param(
    [int]$FastApiPort = 8000,
    [int]$FrontendPort = 3000,
    [string]$MysqlHost = $(if ($env:MYSQL_HOST) { $env:MYSQL_HOST } else { "localhost" }),
    [int]$MysqlPort = $(if ($env:MYSQL_PORT) { [int]$env:MYSQL_PORT } else { 3306 }),
    [string]$MysqlDb = $(if ($env:MYSQL_DB) { $env:MYSQL_DB } else { "movie_rcm_db" }),
    [string]$MysqlUser = $(if ($env:MYSQL_USER) { $env:MYSQL_USER } else { "root" }),
    [string]$MysqlPassword = $(if ($env:MYSQL_PASSWORD) { $env:MYSQL_PASSWORD } else { "" }),
    [ValidateSet("light", "cloud")]
    [string]$ModelMode = "light",
    [string]$StateFile,
    [switch]$Production,
    [switch]$Background
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$fastapiDir = Join-Path $root "backend\fastapi"
$frontendDir = Join-Path $root "frontend"
$targetDir = Join-Path $root "target"
if (-not $StateFile) {
    $StateFile = Join-Path $targetDir "preview_stack.json"
}
$StateFile = [System.IO.Path]::GetFullPath($StateFile)
New-Item -ItemType Directory -Path ([System.IO.Path]::GetDirectoryName($StateFile)) -Force | Out-Null
foreach ($port in @($FastApiPort, $FrontendPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Cổng $port đang được sử dụng. Dừng ứng dụng hiện tại trước khi chạy lại."
    }
}
if (Test-Path -LiteralPath $StateFile) {
    $previous = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    foreach ($owned in $previous.Processes) {
        if (Get-Process -Id $owned.PID -ErrorAction SilentlyContinue) {
            throw "Tệp trạng thái còn tiến trình hoạt động. Dừng ứng dụng bằng scripts\stop_preview_stack.ps1 trước."
        }
    }
    Remove-Item -LiteralPath $StateFile -Force
}

$env:MYSQL_HOST = $MysqlHost
$env:MYSQL_PORT = [string]$MysqlPort
$env:MYSQL_DB = $MysqlDb
$env:MYSQL_USER = $MysqlUser
$env:MYSQL_PASSWORD = $MysqlPassword
$env:BACKEND_INTERNAL_URL = "http://127.0.0.1:$FastApiPort"
$env:SPRINGBOOT_INTERNAL_URL = "http://127.0.0.1:$FastApiPort"
$env:MODEL_API_URL = "http://127.0.0.1:$FastApiPort/api/chat"
$env:MODEL_MODE = $ModelMode
if (-not $env:APP_JWT_SECRET) {
    if ($Production) { throw "Cần đặt APP_JWT_SECRET cố định trước khi chạy bản build." }
    $jwtBytes = New-Object byte[] 32
    $jwtGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $jwtGenerator.GetBytes($jwtBytes) } finally { $jwtGenerator.Dispose() }
    $env:APP_JWT_SECRET = [Convert]::ToBase64String($jwtBytes)
}
$env:PYTHONPATH = $fastapiDir

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " DIPPIE CINEMA — CHẾ ĐỘ PYTHON MAIN (FastAPI Full Backend + AI + MySQL 8.0)" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " -> MySQL               : ${MysqlHost}:${MysqlPort}/${MysqlDb}" -ForegroundColor Gray
Write-Host " -> Unified Backend URL : http://127.0.0.1:$FastApiPort" -ForegroundColor Gray
Write-Host " -> Frontend Web URL    : http://localhost:$FrontendPort" -ForegroundColor Gray

$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = (Get-Command python -ErrorAction Stop).Source
}

Write-Host "`n[1/2] Khởi động FastAPI Unified Backend (Core API + AI) trên cổng $FastApiPort..." -ForegroundColor Yellow
$faProc = $null
$feProc = $null
try {
    $faProc = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$FastApiPort", "--no-proxy-headers") -WorkingDirectory $fastapiDir -PassThru -WindowStyle Hidden -RedirectStandardOutput ($StateFile + ".api.log") -RedirectStandardError ($StateFile + ".api.err.log")

    Write-Host "[2/2] Khởi động Next.js Frontend trên cổng $FrontendPort..." -ForegroundColor Yellow
    $nextBin = Join-Path $frontendDir "node_modules\next\dist\bin\next"
    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if ($Production) {
        $server = Join-Path $frontendDir ".next\standalone\server.js"
        $manifest = Join-Path $frontendDir ".next\routes-manifest.json"
        if (-not $nodeCmd -or -not (Test-Path $server) -or -not (Test-Path $manifest)) {
            throw "Chưa có bản build. Chạy npm run build trong thư mục frontend trước."
        }
        $routes = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
        $rewrites = @($routes.rewrites.afterFiles | Where-Object source -eq "/api/:path*")
        if ($rewrites.Count -ne 1 -or $rewrites[0].destination -ne "$($env:BACKEND_INTERNAL_URL)/api/:path*") {
            throw "Bản build đang trỏ sang backend khác. Đặt BACKEND_INTERNAL_URL=$($env:BACKEND_INTERNAL_URL) rồi chạy lại npm run build."
        }
        $standalone = Split-Path -Parent $server
        Copy-Item -LiteralPath (Join-Path $frontendDir "public") -Destination $standalone -Recurse -Force
        Copy-Item -LiteralPath (Join-Path $frontendDir ".next\static") -Destination (Join-Path $standalone ".next") -Recurse -Force
        $env:HOSTNAME = "127.0.0.1"
        $env:PORT = [string]$FrontendPort
        $feExe = $nodeCmd.Source
        $feProc = Start-Process -FilePath $feExe -ArgumentList @("`"$server`"") -WorkingDirectory $frontendDir -PassThru -WindowStyle Hidden -RedirectStandardOutput ($StateFile + ".web.log") -RedirectStandardError ($StateFile + ".web.err.log")
    } elseif ($nodeCmd -and (Test-Path $nextBin)) {
        $feExe = $nodeCmd.Source
        $feProc = Start-Process -FilePath $feExe -ArgumentList @("node_modules\next\dist\bin\next", "dev", "-p", "$FrontendPort") -WorkingDirectory $frontendDir -PassThru -WindowStyle Hidden -RedirectStandardOutput ($StateFile + ".web.log") -RedirectStandardError ($StateFile + ".web.err.log")
    } else {
        $feExe = (Get-Command npm.cmd -ErrorAction Stop).Source
        $feProc = Start-Process -FilePath $feExe -ArgumentList @("run", "dev", "--", "-p", "$FrontendPort") -WorkingDirectory $frontendDir -PassThru -WindowStyle Hidden
    }

    $stackState = [PSCustomObject]@{
        Timestamp      = [DateTime]::UtcNow.ToString("o")
        ReleaseLevel   = "python_main"
        Status         = "STARTING"
        FastApiPort    = $FastApiPort
        FrontendPort   = $FrontendPort
        ModelMode      = $ModelMode
        StateFile      = $StateFile
        DriveMounted   = $false
        Processes      = @(
            @{
                Name           = "FastAPI"
                PID            = $faProc.Id
                StartTime      = $faProc.StartTime.ToString("o")
                ExecutablePath = $pythonExe
                Port           = $FastApiPort
            },
            @{
                Name           = "NextFrontend"
                PID            = $feProc.Id
                StartTime      = $feProc.StartTime.ToString("o")
                ExecutablePath = $feExe
                Port           = $FrontendPort
            }
        )
    }
    $jsonState = $stackState | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($StateFile, $jsonState, [System.Text.UTF8Encoding]::new($false))
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    $ready = $false
    do {
        if ($faProc.HasExited -or $feProc.HasExited) { throw "Dịch vụ đã dừng khi khởi động. Kiểm tra các tệp log cạnh $StateFile." }
        try {
            $api = Invoke-WebRequest -Uri "http://127.0.0.1:$FastApiPort/api/health" -UseBasicParsing -TimeoutSec 2
            $web = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/api/health" -UseBasicParsing -TimeoutSec 2
            $ready = $api.StatusCode -eq 200 -and $web.StatusCode -eq 200
        } catch {}
        if (-not $ready) { Start-Sleep -Milliseconds 250 }
    } until ($ready -or [DateTime]::UtcNow -gt $deadline)
    if (-not $ready) { throw "Dịch vụ chưa sẵn sàng. Kiểm tra kết nối MySQL và các tệp log cạnh $StateFile." }
    $stackState.Status = "READY"
    [System.IO.File]::WriteAllText($StateFile, ($stackState | ConvertTo-Json -Depth 5), [System.Text.UTF8Encoding]::new($false))
} catch {
    if (-not (Test-Path -LiteralPath $StateFile)) {
        $started = @(foreach ($process in @($faProc, $feProc)) {
            if ($process -and -not $process.HasExited) {
                @{ Name = "Dippie"; PID = $process.Id; StartTime = $process.StartTime.ToString("o"); ExecutablePath = $process.Path }
            }
        })
        $partial = @{ Processes = $started; DriveMounted = $false } | ConvertTo-Json -Depth 5
        [IO.File]::WriteAllText($StateFile, $partial, [Text.UTF8Encoding]::new($false))
    }
    & (Join-Path $root "scripts\stop_preview_stack.ps1") -StateFile $StateFile
    throw
}

if ($Background) {
    Write-Host "`nĐã khởi động chế độ PYTHON MAIN ở chế độ nền (-Background)." -ForegroundColor Green
    Write-Host "Để dừng toàn bộ dịch vụ, chạy lệnh: .\scripts\stop_preview_stack.ps1" -ForegroundColor Yellow
} else {
    try {
        Write-Host "`nĐang chạy chế độ PYTHON MAIN. Nhấn Ctrl+C để dừng..." -ForegroundColor Green
        while (-not $faProc.HasExited -and -not $feProc.HasExited) {
            Start-Sleep -Seconds 2
        }
    } finally {
        & (Join-Path $root "scripts\stop_preview_stack.ps1") -StateFile $StateFile
    }
}
