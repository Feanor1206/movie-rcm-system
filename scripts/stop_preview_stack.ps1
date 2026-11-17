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
$StateFile = [System.IO.Path]::GetFullPath($StateFile)

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
    throw "Tệp trạng thái tại '$StateFile' bị hỏng hoặc không thể đọc. Không dừng tiến trình."
}
if (-not $state -or -not $state.PSObject.Properties["Processes"] -or -not $state.PSObject.Properties["DriveMounted"]) {
    throw "Tệp trạng thái tại '$StateFile' thiếu cấu trúc ownership bắt buộc. Không dừng tiến trình."
}

$allStopped = $true
$processRecords = @($state.Processes)
if ($processRecords.Count -eq 0 -and -not $state.DriveMounted) {
    Write-Host "Không có tiến trình hoặc drive thuộc stack trong tệp trạng thái." -ForegroundColor Gray
    Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
    return
}

for ($processIndex = $processRecords.Count - 1; $processIndex -ge 0; $processIndex--) {
    $p = $processRecords[$processIndex]
    if (-not $p -or -not $p.PSObject.Properties["PID"]) {
        Write-Warning "  [BỎ QUA] Bản ghi tiến trình thiếu PID. Fail-closed."
        $allStopped = $false
        continue
    }
    try { $targetPid = [int]$p.PID } catch {
        Write-Warning "  [BỎ QUA] PID trong tệp trạng thái không hợp lệ. Fail-closed."
        $allStopped = $false
        continue
    }
    $procName = if ($p.PSObject.Properties["Name"]) { [string]$p.Name } else { "unknown" }
    $expectedExe = if ($p.PSObject.Properties["ExecutablePath"]) { [string]$p.ExecutablePath } else { "" }
    $expectedStartTimeStr = if ($p.PSObject.Properties["StartTime"]) { [string]$p.StartTime } else { "" }

    Write-Host "`nĐang xác minh tiến trình $procName (PID $targetPid)..." -ForegroundColor Yellow

    if ($targetPid -le 0 -or [string]::IsNullOrWhiteSpace($expectedStartTimeStr)) {
        Write-Warning "  [BỎ QUA] Bản ghi tiến trình thiếu PID hoặc StartTime hợp lệ. Fail-closed."
        $allStopped = $false
        continue
    }

    try {
        $expectedStartTime = [DateTime]::Parse($expectedStartTimeStr)
    } catch {
        Write-Warning "  [BỎ QUA] StartTime của PID $targetPid không hợp lệ. Fail-closed."
        $allStopped = $false
        continue
    }

    if ([string]::IsNullOrWhiteSpace($expectedExe)) {
        Write-Warning "  [BỎ QUA] Bản ghi PID $targetPid thiếu ExecutablePath. Fail-closed."
        $allStopped = $false
        continue
    }

    $cimProc = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction SilentlyContinue
    if (-not $cimProc) {
        Write-Host "  -> Tiến trình PID $targetPid ($procName) đã kết thúc trước đó." -ForegroundColor Gray
        continue
    }

    $liveExe = [string]$cimProc.ExecutablePath
    if ([string]::IsNullOrWhiteSpace($liveExe)) {
        Write-Warning "  [TỪ CHỐI] Không đọc được ExecutablePath của live PID $targetPid. Fail-closed không gửi tín hiệu."
        $allStopped = $false
        continue
    }

    try {
        $normLive = [System.IO.Path]::GetFullPath($liveExe)
        $normExpected = [System.IO.Path]::GetFullPath($expectedExe)
    } catch {
        Write-Warning "  [TỪ CHỐI] Đường dẫn ExecutablePath của PID $targetPid không hợp lệ. Fail-closed không gửi tín hiệu."
        $allStopped = $false
        continue
    }
    if (-not [string]::Equals($normLive, $normExpected, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Warning "  [TỪ CHỐI SAI DANH TÍNH] ExecutablePath '$normLive' không khớp kỳ vọng '$normExpected'. Không dừng PID này."
        $allStopped = $false
        continue
    }

    try {
        $liveCreationDate = ([DateTime]$cimProc.CreationDate).ToUniversalTime()
        $expectedUtc = $expectedStartTime.ToUniversalTime()
    } catch {
        Write-Warning "  [TỪ CHỐI] Không đọc được CreationDate của live PID $targetPid. Fail-closed không gửi tín hiệu."
        $allStopped = $false
        continue
    }
    $timeDelta = [Math]::Abs(($liveCreationDate - $expectedUtc).TotalSeconds)
    if ($timeDelta -gt 3.0) {
        Write-Warning "  [TỪ CHỐI SAI THỜI GIAN] CreationDate ($liveCreationDate) lệch StartTime ($expectedUtc) $timeDelta giây. Không dừng PID này."
        $allStopped = $false
        continue
    }

    Write-Host "  -> Xác minh danh tính thành công cho PID $targetPid ($procName, delta: $($timeDelta.ToString('F2'))s). Đang dừng..." -ForegroundColor Green
    $descendants = @()
    $parents = @($targetPid)
    while ($parents.Count) {
        $children = @(foreach ($parentPid in $parents) {
            Get-CimInstance Win32_Process -Filter "ParentProcessId = $parentPid" -ErrorAction SilentlyContinue |
                Where-Object { ([DateTime]$_.CreationDate).ToUniversalTime() -ge $expectedUtc }
        })
        $descendants += $children
        $parents = @($children | Select-Object -ExpandProperty ProcessId)
    }
    foreach ($child in $descendants) {
        if (-not @($state.Processes | Where-Object PID -eq $child.ProcessId).Count) {
            $state.Processes = @($state.Processes) + @(@{
                Name = "Tiến trình con"
                PID = $child.ProcessId
                StartTime = ([DateTime]$child.CreationDate).ToString("o")
                ExecutablePath = $child.ExecutablePath
            })
        }
    }
    [IO.File]::WriteAllText($StateFile, ($state | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    for ($childIndex = $descendants.Count - 1; $childIndex -ge 0; $childIndex--) {
        $child = $descendants[$childIndex]
        $liveChild = Get-CimInstance Win32_Process -Filter "ProcessId = $($child.ProcessId)" -ErrorAction SilentlyContinue
        if ($liveChild -and $liveChild.CreationDate -eq $child.CreationDate -and $liveChild.ExecutablePath -eq $child.ExecutablePath) {
            Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
        }
        $childDeadline = [DateTime]::UtcNow.AddSeconds(2)
        while ((Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue) -and [DateTime]::UtcNow -lt $childDeadline) {
            Start-Sleep -Milliseconds 100
        }
        if (Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue) { $allStopped = $false }
    }
    try {
        Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
    } catch {}

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

if ($state.DriveMounted) {
    Write-Host "`nĐang tháo gắn ổ đĩa Google Drive..." -ForegroundColor Yellow
    $stopDriveScript = Join-Path $root "scripts\drive\stop_drive.ps1"
    $driveStateFile = if ($state.PSObject.Properties["DriveStateFile"]) { [string]$state.DriveStateFile } else { "" }
    if ([string]::IsNullOrWhiteSpace($driveStateFile)) {
        Write-Warning "Tệp trạng thái thiếu DriveStateFile riêng của stack. Bỏ qua để tránh dừng một mount không thuộc stack này."
        $allStopped = $false
    } elseif (Test-Path $stopDriveScript) {
        try {
            $driveResultText = (& powershell -NoProfile -File $stopDriveScript -StateFile $driveStateFile -AsJson | Out-String)
            $driveResult = $driveResultText | ConvertFrom-Json
            if ($LASTEXITCODE -ne 0 -or -not $driveResult.Success) { throw $driveResult.Message }
        } catch {
            Write-Warning "Lỗi khi chạy stop_drive.ps1: $_"
            $allStopped = $false
        }
    } else {
        Write-Warning "Không tìm thấy stop_drive.ps1 để dừng DriveStateFile '$driveStateFile'."
        $allStopped = $false
    }
}

if ($allStopped) {
    Remove-Item -Path $StateFile -Force -ErrorAction SilentlyContinue
    Write-Host "`n==========================================================================" -ForegroundColor Green
    Write-Host " TẤT CẢ TIẾN TRÌNH THUỘC BẢN DÙNG THỬ ĐÃ DỪNG HOÀN TOÀN." -ForegroundColor Green
    Write-Host "==========================================================================" -ForegroundColor Green
} else {
    throw "Một số tiến trình chưa dừng hoặc không thể xác minh. Tệp trạng thái được giữ lại tại: $StateFile"
}
