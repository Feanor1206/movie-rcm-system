[CmdletBinding()]
param(
    [Alias("FrontendPort")][int]$Port = 3000,
    [int]$FastApiPort,
    [string]$MysqlHost = $(if ($env:MYSQL_HOST) { $env:MYSQL_HOST } else { "localhost" }),
    [int]$MysqlPort = $(if ($env:MYSQL_PORT) { [int]$env:MYSQL_PORT } else { 3306 }),
    [string]$MysqlDb = $(if ($env:MYSQL_DB) { $env:MYSQL_DB } else { "movie_rcm_db" }),
    [string]$MysqlUser = $(if ($env:MYSQL_USER) { $env:MYSQL_USER } else { "root" }),
    [string]$MysqlPassword = $env:MYSQL_PASSWORD,
    [ValidateSet("light", "cloud")][string]$ModelMode = "light",
    [string]$StateFile = (Join-Path $PSScriptRoot "target\preview_stack.json"),
    [switch]$Production,
    [switch]$Background
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (!$PSBoundParameters.ContainsKey("Port") -and $FastApiPort) { $Port = $FastApiPort }
$root = $PSScriptRoot
$fastapiDir = Join-Path $root "backend\fastapi"
$dist = if ($env:DIPPIE_WEB_DIST) { [IO.Path]::GetFullPath($env:DIPPIE_WEB_DIST) } else { Join-Path $root "frontend\dist" }
if (!(Test-Path -LiteralPath (Join-Path $dist "index.html") -PathType Leaf)) {
    throw "Cần build giao diện bằng npm run build trong thư mục frontend."
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Cổng $Port đang được sử dụng."
}
$StateFile = [IO.Path]::GetFullPath($StateFile)
New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($StateFile)) -Force | Out-Null
if (Test-Path -LiteralPath $StateFile) {
    $previous = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    foreach ($owned in $previous.Processes) {
        if (Get-Process -Id $owned.PID -ErrorAction SilentlyContinue) {
            throw "Tiến trình cũ vẫn đang chạy. Dùng scripts\stop_preview_stack.ps1 để dừng."
        }
    }
    Remove-Item -LiteralPath $StateFile -Force
}

$env:MYSQL_HOST = $MysqlHost
$env:MYSQL_PORT = [string]$MysqlPort
$env:MYSQL_DB = $MysqlDb
$env:MYSQL_USER = $MysqlUser
$env:MYSQL_PASSWORD = $MysqlPassword
$env:MODEL_MODE = $ModelMode
$env:DIPPIE_WEB_DIST = $dist
if (!$env:APP_JWT_SECRET) {
    if ($Production) { throw "Cần đặt APP_JWT_SECRET cố định cho môi trường này." }
    $jwtBytes = New-Object byte[] 32
    $jwtGenerator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $jwtGenerator.GetBytes($jwtBytes) } finally { $jwtGenerator.Dispose() }
    $env:APP_JWT_SECRET = [Convert]::ToBase64String($jwtBytes)
}

$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $pythonExe)) { $pythonExe = (Get-Command python).Source }
$url = "http://127.0.0.1:$Port"
$server = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$Port", "--no-proxy-headers") -WorkingDirectory $fastapiDir -PassThru -WindowStyle Hidden -RedirectStandardOutput ($StateFile + ".api.log") -RedirectStandardError ($StateFile + ".api.err.log")
$state = @{
    Status = "STARTING"
    ReleaseLevel = "python_main"
    ModelMode = $ModelMode
    FastApiPort = $Port
    FrontendPort = $Port
    DriveMounted = $false
    Processes = @(@{ Name = "FastAPI"; PID = $server.Id; StartTime = $server.StartTime.ToString("o"); ExecutablePath = $pythonExe; Port = $Port })
}

try {
    [IO.File]::WriteAllText($StateFile, ($state | ConvertTo-Json -Depth 4))
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    do {
        if ($server.HasExited) { throw "FastAPI đã dừng. Xem log cạnh tệp trạng thái." }
        try {
            $ready = (Invoke-WebRequest -UseBasicParsing -Uri "$url/api/health" -TimeoutSec 2).StatusCode -eq 200
        } catch { $ready = $false }
        if (!$ready) { Start-Sleep -Milliseconds 250 }
    } until ($ready -or [DateTime]::UtcNow -gt $deadline)
    if (!$ready) { throw "Dippie chưa sẵn sàng. Kiểm tra kết nối MySQL và log FastAPI." }
    $state.Status = "READY"
    [IO.File]::WriteAllText($StateFile, ($state | ConvertTo-Json -Depth 4))
    Write-Host "Dippie đang chạy tại http://localhost:$Port"
    if (!$Background) { Wait-Process -Id $server.Id }
} finally {
    if (!$Background -or $state.Status -ne "READY") {
        & (Join-Path $root "scripts\stop_preview_stack.ps1") -StateFile $StateFile
    }
}
