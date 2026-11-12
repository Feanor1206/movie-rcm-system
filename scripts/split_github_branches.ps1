[CmdletBinding()]
param(
    [switch]$PushToOrigin
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -Path $root

$initialBranch = (git rev-parse --abbrev-ref HEAD).Trim()
Write-Host "Nhánh bắt đầu: $initialBranch" -ForegroundColor Cyan

$status = git status --porcelain
if ($status) {
    Write-Error "Thư mục làm việc không sạch (working tree dirty). Vui lòng commit hoặc stash trước khi đồng bộ nhánh."
}

# 1. Đảm bảo dev được cập nhật
Write-Host "`n[1/4] Kiểm tra nhánh dev..." -ForegroundColor Green
git checkout dev

# 2. Đồng bộ main và java-main bằng fast-forward
Write-Host "`n[2/4] Đồng bộ nhánh 'java-main' và 'main' từ 'dev' (fast-forward)..." -ForegroundColor Green
git checkout java-main
git merge --ff-only dev

git checkout main
git merge --ff-only dev

# 3. Đồng bộ nhánh python-main không phá hủy lịch sử (non-destructive merge)
Write-Host "`n[3/4] Đồng bộ nhánh 'python-main' từ 'dev' (non-destructive merge)..." -ForegroundColor Green
git checkout python-main

# Thực hiện merge với --no-commit để xử lý dọn dẹp backend/springboot an toàn
# Tạm thời hạ ErrorActionPreference để tránh NativeCommandError từ thông báo stderr của Git
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
git merge dev --no-commit
$ErrorActionPreference = $prevEAP

# Lược bỏ hoàn toàn backend/springboot khỏi python-main
if (Test-Path "backend\springboot") {
    Remove-Item -Recurse -Force "backend\springboot"
}
git rm -rf --cached --ignore-unmatch backend/springboot 2>$null | Out-Null

# Dọn dẹp bất kỳ file conflict nào của backend/springboot (DU, UD, v.v.)
$springConflicts = @(git diff --name-only --diff-filter=U 2>$null | Where-Object { $_ -like "backend/springboot/*" -or $_ -like "backend\springboot\*" })
if ($springConflicts.Count -gt 0) {
    git rm -f $springConflicts 2>$null | Out-Null
}

# Kiểm tra nghiêm ngặt xung đột merge ngoài backend/springboot
$unmergedFiles = @(git diff --name-only --diff-filter=U 2>$null | Where-Object { $_ -notlike "backend/springboot/*" -and $_ -notlike "backend\springboot\*" })
if ($unmergedFiles.Count -gt 0) {
    Write-Warning "Phát hiện xung đột merge ngoài backend/springboot: $($unmergedFiles -join ', ')"
    git merge --abort 2>$null | Out-Null
    git checkout $initialBranch
    throw "Đã tự động abort merge và quay lại nhánh '$initialBranch' do xung đột tại: $($unmergedFiles -join ', ')"
}

# Đảm bảo start-all.ps1 dùng backend python
Set-Content -Path "start-all.ps1" -Value '& (Join-Path $PSScriptRoot "start-python-main.ps1") @args' -Encoding UTF8
git add start-all.ps1

$pendingMerge = git status --porcelain
if ($pendingMerge) {
    git commit -m "chore(python-main): sync with dev (exclude backend/springboot)"
} else {
    Write-Host "Nhánh python-main đã đồng bộ hoàn toàn với dev." -ForegroundColor White
}

# 4. Trở về nhánh ban đầu
git checkout $initialBranch

Write-Host "`nHoàn tất đồng bộ 4 nhánh Git:" -ForegroundColor Cyan
Write-Host "  - dev         : Nhánh phát triển chính" -ForegroundColor White
Write-Host "  - java-main   : Spring Boot (Main Backend) + FastAPI (AI) + MySQL + Frontend" -ForegroundColor White
Write-Host "  - main        : Nhánh sản xuất đồng bộ với dev / java-main" -ForegroundColor White
Write-Host "  - python-main : FastAPI (Unified Main Backend + AI) + MySQL + Frontend" -ForegroundColor White

if ($PushToOrigin) {
    Write-Host "`nĐang đẩy cả 4 nhánh lên GitHub (origin) và thiết lập upstream tracking (-u)..." -ForegroundColor Yellow
    git push -u origin dev main java-main python-main
} else {
    Write-Host "`nĐể đẩy cả 4 nhánh lên GitHub và thiết lập tracking, chạy:" -ForegroundColor Yellow
    Write-Host "  git push -u origin dev main java-main python-main" -ForegroundColor White
}
