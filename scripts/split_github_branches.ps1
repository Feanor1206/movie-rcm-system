[CmdletBinding()]
param(
    [switch]$PushToOrigin
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -Path $root

$currentBranch = (git rev-parse --abbrev-ref HEAD).Trim()
Write-Host "Nhánh hiện tại: $currentBranch" -ForegroundColor Cyan

$status = git status --porcelain
if ($status) {
    Write-Host "Đang commit các thay đổi hiện tại (MySQL 8.0 + Dual Backend + AI v4)..." -ForegroundColor Yellow
    git add -A
    git commit -m "feat: migrate database to MySQL 8.0 and support Java Main & Python Main backends"
}

$baseCommit = (git rev-parse HEAD).Trim()

Write-Host "`n[1/2] Khởi tạo / cập nhật nhánh 'java-main' (Spring Boot Main + FastAPI AI + MySQL)..." -ForegroundColor Green
git branch -f java-main $baseCommit

Write-Host "[2/2] Khởi tạo / cập nhật nhánh 'python-main' (FastAPI Full Main + AI + MySQL, lược bỏ Spring Boot)..." -ForegroundColor Green
git checkout -B python-main $baseCommit
if (Test-Path "backend\springboot") {
    git rm -rf backend/springboot | Out-Null
}
Set-Content -Path "start-all.ps1" -Value '& (Join-Path $PSScriptRoot "start-python-main.ps1") @args' -Encoding UTF8
git add start-all.ps1
git commit -m "chore(python-main): use FastAPI as unified main backend with MySQL and remove Spring Boot"

git checkout $currentBranch

Write-Host "`nHoàn tất tách 2 nhánh Git:" -ForegroundColor Cyan
Write-Host "  - java-main   : Spring Boot (Main Backend) + FastAPI (AI) + MySQL + Frontend" -ForegroundColor White
Write-Host "  - python-main : FastAPI (Unified Main Backend + AI) + MySQL + Frontend" -ForegroundColor White

if ($PushToOrigin) {
    Write-Host "`nĐang đẩy cả 2 nhánh lên GitHub (origin)..." -ForegroundColor Yellow
    git push -u origin java-main
    git push -u origin python-main
} else {
    Write-Host "`nĐể đẩy cả 2 bản lên GitHub, chạy:" -ForegroundColor Yellow
    Write-Host "  git push -u origin java-main python-main" -ForegroundColor White
}
