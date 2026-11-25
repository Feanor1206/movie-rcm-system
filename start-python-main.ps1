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
try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {}

$root = $PSScriptRoot
$fastapiDir = Join-Path $root "backend\fastapi"
$frontendDir = Join-Path $root "frontend"
$targetDir = Join-Path $root "target"
$logsDir = Join-Path $targetDir "preview_logs"
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
if (-not $StateFile) {
    $StateFile = Join-Path $targetDir "preview_stack.json"
}
$StateFile = [System.IO.Path]::GetFullPath($StateFile)
New-Item -ItemType Directory -Path ([System.IO.Path]::GetDirectoryName($StateFile)) -Force | Out-Null

$launcherAst = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $root "scripts\start_preview_stack.ps1"), [ref]$null, [ref]$null)
foreach ($helperName in @("Test-TcpPortOpen", "Test-PythonExecutableWorking", "Test-FastApiPythonPackages", "Resolve-FastApiPython", "Resolve-NodeToolchain", "Get-FrontendDependencyHash", "Test-FrontendDependenciesNeedInstall", "Ensure-FrontendDependencies", "Get-LogTailText")) {
    $fnAst = $launcherAst.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $helperName }, $true)
    if ($fnAst) { . ([ScriptBlock]::Create($fnAst.Extent.Text)) }
}

foreach ($portCheck in @(@{ Port = $FastApiPort; Name = "FastAPI Unified Backend" }, @{ Port = $FrontendPort; Name = "Next.js Web Frontend" })) {
    $conn = Get-NetTCPConnection -LocalPort $portCheck.Port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        throw "CỔNG BỊ CHIẾM: Cổng $($portCheck.Port) ($($portCheck.Name)) đang được sử dụng bởi PID $($conn.OwningProcess)."
    }
}

$env:MYSQL_HOST = $MysqlHost
$env:MYSQL_PORT = [string]$MysqlPort
$env:MYSQL_DB = $MysqlDb
$env:MYSQL_USER = $MysqlUser
$env:MYSQL_PASSWORD = $MysqlPassword
if (-not $env:DATABASE_URL) {
    if (Test-TcpPortOpen -HostName $MysqlHost -Port $MysqlPort -TimeoutMs 500) {
        $env:DATABASE_URL = "mysql+pymysql://${MysqlUser}:${MysqlPassword}@${MysqlHost}:${MysqlPort}/${MysqlDb}?charset=utf8mb4"
    } else {
        $sqlitePath = (Join-Path $root "data\python_main.db").Replace("\", "/")
        New-Item -ItemType Directory -Path (Join-Path $root "data") -Force | Out-Null
        $env:DATABASE_URL = "sqlite:///$sqlitePath"
        Write-Host " -> Không phát hiện MySQL tại ${MysqlHost}:${MysqlPort}; tự động dùng SQLite ($sqlitePath)." -ForegroundColor Yellow
    }
}
$env:BACKEND_INTERNAL_URL = "http://127.0.0.1:$FastApiPort"
$env:SPRINGBOOT_INTERNAL_URL = "http://127.0.0.1:$FastApiPort"
$env:MODEL_API_URL = "http://127.0.0.1:$FastApiPort/api/chat"
$env:MODEL_MODE = $ModelMode
$env:APP_DEMO_MODE = "true"
if (-not $env:APP_JWT_SECRET) {
    $jwtBytes = New-Object byte[] 32
    $jwtGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $jwtGenerator.GetBytes($jwtBytes) } finally { $jwtGenerator.Dispose() }
    $env:APP_JWT_SECRET = [Convert]::ToBase64String($jwtBytes)
}
$env:PYTHONPATH = $fastapiDir

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " DIPPIE CINEMA — CHẾ ĐỘ PYTHON MAIN (FastAPI Full Backend + AI + Database)" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " -> Database URL        : $($env:DATABASE_URL)" -ForegroundColor Gray
Write-Host " -> Unified Backend URL : http://127.0.0.1:$FastApiPort" -ForegroundColor Gray
Write-Host " -> Frontend Web URL    : http://localhost:$FrontendPort" -ForegroundColor Gray

$pythonExe = Resolve-FastApiPython -RootDirectory $root -FastApiDirectory $fastapiDir
$nodeToolchain = Resolve-NodeToolchain
Ensure-FrontendDependencies -FrontendDirectory $frontendDir -NpmCmd $nodeToolchain.NpmCmd

$faLog = Join-Path $logsDir "fastapi.stdout.log"
$faErr = Join-Path $logsDir "fastapi.stderr.log"
$feLog = Join-Path $logsDir "nextjs.stdout.log"
$feErr = Join-Path $logsDir "nextjs.stderr.log"

Write-Host "`n[1/2] Khởi động FastAPI Unified Backend (Core API + AI) trên cổng $FastApiPort..." -ForegroundColor Yellow
$faProc = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$FastApiPort") -WorkingDirectory $fastapiDir -RedirectStandardOutput $faLog -RedirectStandardError $faErr -PassThru -WindowStyle Hidden

$faReady = $false
$deadline = [DateTime]::UtcNow.AddSeconds(90)
while ([DateTime]::UtcNow -lt $deadline) {
    if ($faProc.HasExited) {
        $tail = Get-LogTailText -Path $faErr
        throw "FastAPI đã thoát bất thường (exit code $($faProc.ExitCode)).`n$tail"
    }
    try {
        $res = Invoke-WebRequest -Uri "http://127.0.0.1:$FastApiPort/health" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($res.StatusCode -eq 200) { $faReady = $true; break }
    } catch { Start-Sleep -Milliseconds 600 }
}
if (-not $faReady) { throw "FastAPI không sẵn sàng trên cổng $FastApiPort sau 90 giây." }
Write-Host "  -> FastAPI HEALTHY (200 OK)." -ForegroundColor Green

Write-Host "[2/2] Khởi động Next.js Frontend trên cổng $FrontendPort..." -ForegroundColor Yellow
$feExe = $nodeToolchain.NodeExe
$feProc = Start-Process -FilePath $feExe -ArgumentList @("node_modules\next\dist\bin\next", "dev", "-p", "$FrontendPort") -WorkingDirectory $frontendDir -RedirectStandardOutput $feLog -RedirectStandardError $feErr -PassThru -WindowStyle Hidden

$feReady = $false
$deadline = [DateTime]::UtcNow.AddSeconds(60)
while ([DateTime]::UtcNow -lt $deadline) {
    if ($feProc.HasExited) {
        if ($faProc -and -not $faProc.HasExited) { Stop-Process -Id $faProc.Id -Force -ErrorAction SilentlyContinue }
        $tail = Get-LogTailText -Path $feErr
        throw "Next.js đã thoát bất thường (exit code $($feProc.ExitCode)).`n$tail"
    }
    try {
        $res = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($res.StatusCode -eq 200) { $feReady = $true; break }
    } catch { Start-Sleep -Milliseconds 600 }
}
if (-not $feReady) {
    if ($faProc -and -not $faProc.HasExited) { Stop-Process -Id $faProc.Id -Force -ErrorAction SilentlyContinue }
    if ($feProc -and -not $feProc.HasExited) { Stop-Process -Id $feProc.Id -Force -ErrorAction SilentlyContinue }
    throw "Next.js không sẵn sàng trên cổng $FrontendPort sau 60 giây."
}
Write-Host "  -> Next.js Frontend HEALTHY (200 OK)." -ForegroundColor Green

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
            LogFile        = $faLog
        },
        @{
            Name           = "NextFrontend"
            PID            = $feProc.Id
            StartTime      = $feProc.StartTime.ToString("o")
            ExecutablePath = $feExe
            Port           = $FrontendPort
            LogFile        = $feLog
        }
    )
}
$jsonState = $stackState | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText($StateFile, $jsonState, [System.Text.UTF8Encoding]::new($false))

Write-Host "`n==========================================================================" -ForegroundColor Green
Write-Host " DIPPIE CINEMA (PYTHON MAIN) ĐÃ SẴN SÀNG PHỤC VỤ!" -ForegroundColor Green
Write-Host " URL Giao diện Web : http://localhost:$FrontendPort" -ForegroundColor White
Write-Host " Unified Backend   : http://127.0.0.1:$FastApiPort" -ForegroundColor White
Write-Host "==========================================================================" -ForegroundColor Green

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
