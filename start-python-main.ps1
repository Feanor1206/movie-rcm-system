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

$env:MYSQL_HOST = $MysqlHost
$env:MYSQL_PORT = [string]$MysqlPort
$env:MYSQL_DB = $MysqlDb
$env:MYSQL_USER = $MysqlUser
$env:MYSQL_PASSWORD = $MysqlPassword
if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "mysql+pymysql://${MysqlUser}:${MysqlPassword}@${MysqlHost}:${MysqlPort}/${MysqlDb}?charset=utf8mb4"
}
$env:BACKEND_INTERNAL_URL = "http://127.0.0.1:$FastApiPort"
$env:SPRINGBOOT_INTERNAL_URL = "http://127.0.0.1:$FastApiPort"
$env:MODEL_API_URL = "http://127.0.0.1:$FastApiPort/api/chat"
$env:MODEL_MODE = $ModelMode
$env:PYTHONPATH = $fastapiDir

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " DIPPIE CINEMA — CHẾ ĐỘ PYTHON MAIN (FastAPI Full Backend + AI + MySQL 8.0)" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " -> Database URL        : $($env:DATABASE_URL)" -ForegroundColor Gray
Write-Host " -> Unified Backend URL : http://127.0.0.1:$FastApiPort" -ForegroundColor Gray
Write-Host " -> Frontend Web URL    : http://localhost:$FrontendPort" -ForegroundColor Gray

$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = (Get-Command python -ErrorAction Stop).Source
}

Write-Host "`n[1/2] Khởi động FastAPI Unified Backend (Core API + AI) trên cổng $FastApiPort..." -ForegroundColor Yellow
$faProc = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$FastApiPort") -WorkingDirectory $fastapiDir -PassThru -WindowStyle Hidden

Write-Host "[2/2] Khởi động Next.js Frontend trên cổng $FrontendPort..." -ForegroundColor Yellow
$nextBin = Join-Path $frontendDir "node_modules\next\dist\bin\next"
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCmd -and (Test-Path $nextBin)) {
    $feExe = $nodeCmd.Source
    $feProc = Start-Process -FilePath $feExe -ArgumentList @($nextBin, "dev", "-p", "$FrontendPort") -WorkingDirectory $frontendDir -PassThru -WindowStyle Hidden
} else {
    $feExe = (Get-Command npm.cmd -ErrorAction Stop).Source
    $feProc = Start-Process -FilePath $feExe -ArgumentList @("run", "dev", "--", "-p", "$FrontendPort") -WorkingDirectory $frontendDir -PassThru -WindowStyle Hidden
}

$stackState = [PSCustomObject]@{
    Timestamp      = [DateTime]::UtcNow.ToString("o")
    ReleaseLevel   = "python_main"
    Status         = "READY"
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
        if ($faProc -and -not $faProc.HasExited) { Stop-Process -Id $faProc.Id -Force -ErrorAction SilentlyContinue }
        if ($feProc -and -not $feProc.HasExited) { Stop-Process -Id $feProc.Id -Force -ErrorAction SilentlyContinue }
        Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
    }
}
