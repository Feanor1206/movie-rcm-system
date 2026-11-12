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
$mergeResult = git merge dev --no-commit 2>&1
Write-Host $mergeResult

# Lược bỏ các file backend/springboot nếu bị kéo vào hoặc gặp xung đột modify/delete
if (Test-Path "backend\springboot") {
    $trackedSpringFiles = git ls-files backend/springboot
    if ($trackedSpringFiles) {
        git rm -rf backend/springboot | Out-Null
    }
}

# Dọn dẹp các trạng thái modify/delete conflict (UD) đối với backend/springboot
$conflicts = git status --porcelain
foreach ($line in ($conflicts -split "`n")) {
    if ($line -match "^\s*UD\s+(backend/springboot/.*)") {
        $conflictFile = $matches[1].Trim()
        git rm -f $conflictFile 2>$null | Out-Null
    }
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
    Write-Host "`nĐang đẩy cả 4 nhánh lên GitHub (origin) không dùng -f..." -ForegroundColor Yellow
    git push origin dev main java-main python-main
} else {
    Write-Host "`nĐể đẩy cả 4 nhánh lên GitHub, chạy:" -ForegroundColor Yellow
    Write-Host "  git push origin dev main java-main python-main" -ForegroundColor White
}
