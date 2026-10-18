<#
.SYNOPSIS
    Dừng an toàn toàn bộ cụm dịch vụ Bản dùng thử (Usable Preview) Dippie Cinema.
.DESCRIPTION
    Đọc tệp trạng thái target\preview_stack.json, xác minh nghiêm ngặt danh tính từng tiến trình
    (PID, StartTime/CreationDate delta < 3.0s, ExecutablePath) trước khi gửi tín hiệu dừng.
    Tuyệt đối không dừng theo tên tiến trình (no broad kill-by-name).
    Nếu có gắn Google Drive, gọi scripts\drive\stop_drive.ps1 để tháo gắn an toàn.
#>
[CmdletBinding()]
param(
    [string]$StateFile,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $StateFile) {
    $StateFile = Join-Path $root "target\preview_stack.json"
}

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " DỪNG BẢN DÙNG THỬ (USABLE PREVIEW) — DIPPIE CINEMA" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

if (-not (Test-Path -Path $StateFile -PathType Leaf -ErrorAction SilentlyContinue)) {
    Write-Host "Không tìm thấy tệp trạng thái tại '$StateFile'. Không có cụm tiến trình nào đang theo dõi để dừng." -ForegroundColor Gray
    return
}

$stateRaw = Get-Content -Path $StateFile -Raw -Encoding UTF8
$state = $null
try {
    $state = $stateRaw | ConvertFrom-Json
} catch {
    Write-Warning "Tệp trạng thái tại '$StateFile' bị hỏng hoặc không thể đọc. Hủy an toàn không dừng tiến trình."
    return
}

if (-not $state.Processes -or $state.Processes.Count -eq 0) {
    Write-Host "Không có danh sách tiến trình trong tệp trạng thái." -ForegroundColor Gray
    Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
    return
}

$allStopped = $true

foreach ($p in $state.Processes) {
    $targetPid = [int]$p.PID
    $procName = [string]$p.Name
    $expectedExe = [string]$p.ExecutablePath
    $expectedStartTimeStr = [string]$p.StartTime

    Write-Host "`nĐang xác minh tiến trình $procName (PID $targetPid)..." -ForegroundColor Yellow

    if ($targetPid -le 0 -or [string]::IsNullOrWhiteSpace($expectedStartTimeStr)) {
        Write-Warning "  [BỎ QUA] Bản ghi tiến trình thiếu PID hoặc StartTime hợp lệ. Fail-closed."
        $allStopped = $false
        continue
    }

    $expectedStartTime = [DateTime]::Parse($expectedStartTimeStr)

    $cimProc = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction SilentlyContinue
    if (-not $cimProc) {
        Write-Host "  -> Tiến trình PID $targetPid ($procName) đã kết thúc trước đó." -ForegroundColor Gray
        continue
    }

    # Xác minh ExecutablePath
    $liveExe = [string]$cimProc.ExecutablePath
    if ([string]::IsNullOrWhiteSpace($liveExe)) {
        Write-Warning "  [TỪ CHỐI] Không đọc được ExecutablePath của live PID $targetPid. Fail-closed không gửi tín hiệu."
        $allStopped = $false
        continue
    }

    $normLive = [System.IO.Path]::GetFullPath($liveExe).ToLowerInvariant()
    $normExpected = [System.IO.Path]::GetFullPath($expectedExe).ToLowerInvariant()
    if ($normLive -ne $normExpected) {
        Write-Warning "  [TỪ CHỐI SAI DANH TÍNH] ExecutablePath '$normLive' không khớp kỳ vọng '$normExpected'. Không dừng PID này."
        $allStopped = $false
        continue
    }

    # Xác minh StartTime / CreationDate trong dung sai 3 giây
    $liveCreationDate = $cimProc.CreationDate.ToUniversalTime()
    $expectedUtc = $expectedStartTime.ToUniversalTime()
    $timeDelta = [Math]::Abs(($liveCreationDate - $expectedUtc).TotalSeconds)
    if ($timeDelta -gt 3.0) {
        Write-Warning "  [TỪ CHỐI SAI THỜI GIAN] CreationDate ($liveCreationDate) lệch StartTime ($expectedUtc) $timeDelta giây. Không dừng PID này."
        $allStopped = $false
        continue
    }

    Write-Host "  -> Xác minh danh tính thành công cho PID $targetPid ($procName, delta: $($timeDelta.ToString('F2'))s). Đang dừng..." -ForegroundColor Green
    try {
        Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
    } catch {}

    # Chờ tiến trình thoát
    $deadline = [DateTime]::UtcNow.AddSeconds(8)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (-not (Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction SilentlyContinue)) {
            break
        }
        Start-Sleep -Milliseconds 300
    }

    if (-not (Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction SilentlyContinue)) {
        Write-Host "  -> Tiến trình PID $targetPid đã dừng thành công." -ForegroundColor Green
    } else {
        Write-Warning "  -> Cảnh báo: Tiến trình PID $targetPid chưa dừng hẳn sau 8 giây."
        $allStopped = $false
    }
}

# Tháo gắn Google Drive nếu đã được gắn
if ($state.DriveMounted) {
    Write-Host "`nĐang tháo gắn ổ đĩa Google Drive..." -ForegroundColor Yellow
    $stopDriveScript = Join-Path $root "scripts\drive\stop_drive.ps1"
    if (Test-Path $stopDriveScript) {
        try {
            & powershell -NoProfile -File $stopDriveScript
        } catch {
            Write-Warning "Lỗi khi chạy stop_drive.ps1: $_"
        }
    }
}

if ($allStopped) {
    Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
    Write-Host "`n==========================================================================" -ForegroundColor Green
    Write-Host " TẤT CẢ TIẾN TRÌNH THUỘC BẢN DÙNG THỬ ĐÃ DỪNG HOÀN TOÀN." -ForegroundColor Green
    Write-Host "==========================================================================" -ForegroundColor Green
} else {
    Write-Warning "`nMột số tiến trình chưa dừng hoặc không thể xác minh. Tệp trạng thái được giữ lại tại: $StateFile"
}
