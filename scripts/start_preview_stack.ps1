<#
.SYNOPSIS
    Khởi động toàn bộ cụm dịch vụ Bản dùng thử (Usable Preview) Dippie Cinema.
.DESCRIPTION
    Khởi động Spring Boot và Next.js; FastAPI chỉ chạy khi chọn -ModelMode light/full:
    1. FastAPI (Cổng 8000 hoặc tùy chọn) - AI & Hybrid Index Sync (tùy chọn)
    2. Spring Boot (Cổng 8080 hoặc tùy chọn) - Core Backend sử dụng moviercm-backend-0.0.1-SNAPSHOT.jar
    3. Next.js Frontend (Cổng 3000 hoặc tùy chọn) - Giao diện Web
    Tùy chọn gắn Google Drive (X:) an toàn qua rclone WinFsp (--drive-root-folder-id 1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ).
    Tương thích hoàn toàn Windows PowerShell 5.1 và PowerShell 7+.
    Ghi nhận quyền sở hữu (ownership) tăng dần ngay sau từng bước tạo tài nguyên.
    Bọc toàn bộ vòng đời khởi tạo bằng khối dọn dẹp tự động (cleanup on failure) chuẩn xác theo PID.
.PARAMETER SpringPort
    Cổng lắng nghe của Spring Boot (mặc định: 8080).
.PARAMETER FastApiPort
    Cổng lắng nghe của FastAPI (mặc định: 8000).
.PARAMETER FrontendPort
    Cổng lắng nghe của Next.js (mặc định: 3000).
.PARAMETER SyncSecret
    Mã bí mật đồng bộ catalog giữa Spring Boot và FastAPI. Lấy từ biến môi trường ngoài Git nếu không truyền.
.PARAMETER ModelMode
    Chế độ AI: 'off' (mặc định, không chạy FastAPI), 'light' hoặc 'full' (Qwen3-4B + Phase23 LoRA trên CUDA).
.PARAMETER DataDirectory
    Thư mục H2 và catalog snapshot riêng cho preview.
.PARAMETER StateFile
    Tệp trạng thái riêng để quản lý tiến trình preview.
.PARAMETER MountDrive
    Gắn kết ổ đĩa Google Drive chế độ chỉ đọc vào điểm gắn chỉ định.
.PARAMETER DriveMountPoint
    Điểm gắn Google Drive (mặc định: 'X:').
.PARAMETER DriveRemote
    Tên remote rclone đã cấu hình (mặc định: 'cinema-drive:').
.PARAMETER DriveFolderId
    ID thư mục gốc Google Drive (mặc định: '1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ').
.PARAMETER Background
    Chạy các tiến trình ở chế độ nền và lưu tệp trạng thái để quản lý sau.
.PARAMETER TestInjectFailureAfter
    Tham số kiểm thử nội bộ để giả lập lỗi có kiểm soát sau một mốc cụ thể.
#>
[CmdletBinding()]
param(
    [int]$SpringPort = 8080,
    [int]$FastApiPort = 8000,
    [int]$FrontendPort = 3000,
    [string]$SyncSecret,
    [ValidateSet("off", "light", "full")]
    [string]$ModelMode = "off",
    [string]$DataDirectory,
    [string]$StateFile,
    [switch]$MountDrive,
    [string]$DriveMountPoint = "X:",
    [string]$DriveRemote = "cinema-drive:",
    [string]$DriveFolderId = "1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ",
    [switch]$Background,
    [Parameter(DontShow = $true)]
    [string]$TestInjectFailureAfter
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -Path $root

$backendDir = Join-Path $root "backend\springboot"
$fastapiDir = Join-Path $root "backend\fastapi"
$frontendDir = Join-Path $root "frontend"
$targetDir = Join-Path $root "target"

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " KHỞI ĐỘNG BẢN DÙNG THỬ (USABLE PREVIEW) — DIPPIE CINEMA" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

# -----------------------------------------------------------------------------
# Helper: Định dạng đối số dòng lệnh an toàn cho PowerShell 5.1 & Windows
# -----------------------------------------------------------------------------
function Format-NativeArgument {
    param([string]$Arg)
    if ([string]::IsNullOrEmpty($Arg)) { return '""' }
    if ($Arg -notmatch '[\s"\t\v\n]') { return $Arg }
    $escaped = [regex]::Replace($Arg, '(\\*)(")', { param($m) ($m.Groups[1].Value * 2) + '\"' })
    $escaped = [regex]::Replace($escaped, '(\\+)$', { param($m) ($m.Groups[1].Value * 2) })
    return '"' + $escaped + '"'
}

# -----------------------------------------------------------------------------
# Helper: Khởi chạy tiến trình con tương thích PowerShell 5.1 & PowerShell 7+
# -----------------------------------------------------------------------------
function Start-ChildServiceProcess {
    param(
        [string]$FileName,
        [string[]]$Arguments,
        [string]$WorkingDirectory,
        [System.Collections.IDictionary]$EnvironmentVariables,
        [string]$StdOutFile = $null,
        [string]$StdErrFile = $null
    )

    $argString = ($Arguments | ForEach-Object { Format-NativeArgument $_ }) -join ' '

    if ($StdOutFile -and $StdErrFile) {
        $previousEnvironment = @{}
        if ($EnvironmentVariables) {
            foreach ($key in $EnvironmentVariables.Keys) {
                $previousEnvironment[$key] = [System.Environment]::GetEnvironmentVariable($key, "Process")
            }
        }
        try {
            if ($EnvironmentVariables) {
                foreach ($key in $EnvironmentVariables.Keys) {
                    [System.Environment]::SetEnvironmentVariable($key, [string]$EnvironmentVariables[$key], "Process")
                }
            }
            $proc = Start-Process -FilePath $FileName `
                -ArgumentList $argString `
                -WorkingDirectory $WorkingDirectory `
                -RedirectStandardOutput $StdOutFile `
                -RedirectStandardError $StdErrFile `
                -PassThru -WindowStyle Hidden
        } finally {
            if ($EnvironmentVariables) {
                foreach ($key in $EnvironmentVariables.Keys) {
                    [System.Environment]::SetEnvironmentVariable($key, $previousEnvironment[$key], "Process")
                }
            }
        }
    } else {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $FileName
        $psi.Arguments = $argString
        $psi.WorkingDirectory = $WorkingDirectory
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true

        if ($EnvironmentVariables) {
            foreach ($key in $EnvironmentVariables.Keys) {
                $psi.EnvironmentVariables[$key] = [string]$EnvironmentVariables[$key]
            }
        }

        $proc = [System.Diagnostics.Process]::Start($psi)
    }

    if (-not $proc) {
        throw "Không thể khởi tạo tiến trình con cho '$FileName'."
    }
    # Keep the native handle open so PowerShell 5.1 retains ExitCode after WaitForExit.
    $null = $proc.Handle
    return $proc
}

function Get-PreviewPaths {
    param([string]$BackendDirectory, [string]$TargetDirectory, [string]$DataDirectory, [string]$StateFile)
    if (-not $DataDirectory) { $DataDirectory = Join-Path $BackendDirectory "data\preview" }
    if (-not $StateFile) { $StateFile = Join-Path $TargetDirectory "preview_stack.json" }
    $DataDirectory = [System.IO.Path]::GetFullPath($DataDirectory)
    $StateFile = [System.IO.Path]::GetFullPath($StateFile)
    return [PSCustomObject]@{
        DataDirectory = $DataDirectory
        StateFile = $StateFile
        DriveStateFile = Join-Path $DataDirectory "drive_mount.json"
    }
}

function Get-PreviewRuntimeContract {
    param(
        [ValidateSet("off", "light", "full")][string]$ModelMode,
        [int]$SpringPort,
        [int]$FastApiPort,
        [int]$FrontendPort,
        [string]$DataDirectory,
        [string]$SyncSecret
    )

    $DataDirectory = [System.IO.Path]::GetFullPath($DataDirectory)
    $databasePath = (Join-Path $DataDirectory "preview_db").Replace("\", "/")
    $syncUrl = if ($ModelMode -eq "off") { "http://127.0.0.1:1/api/index/sync" } else { "http://127.0.0.1:$FastApiPort/api/index/sync" }
    $modelUrl = if ($ModelMode -eq "off") { "http://127.0.0.1:1/api/chat" } else { "http://127.0.0.1:$FastApiPort/api/chat" }
    $syncToken = if ($ModelMode -eq "off") { "" } else { $SyncSecret }
    $springEnvironment = [System.Collections.Generic.Dictionary[string, string]]::new()
    $springEnvironment["SPRING_DATASOURCE_URL"] = "jdbc:h2:file:$databasePath;DB_CLOSE_DELAY=-1;DB_CLOSE_ON_EXIT=FALSE;MODE=PostgreSQL;NON_KEYWORDS=YEAR,USER"
    $springEnvironment["APP_CATALOG_SNAPSHOT_PATH"] = Join-Path $DataDirectory "committed_catalog_snapshot.json"
    $springEnvironment["APP_CATALOG_SYNC_URL"] = $syncUrl
    $springEnvironment["CATALOG_SYNC_TOKEN"] = $syncToken
    $springEnvironment["FASTAPI_SYNC_SECRET"] = $syncToken
    $springEnvironment["APP_CORS_ALLOWED_ORIGINS"] = "http://127.0.0.1:$FrontendPort,http://localhost:$FrontendPort"
    if ($env:APP_CORS_ALLOWED_ORIGINS) { $springEnvironment["APP_CORS_ALLOWED_ORIGINS"] += ",$env:APP_CORS_ALLOWED_ORIGINS" }

    $frontendEnvironment = [System.Collections.Generic.Dictionary[string, string]]::new()
    $frontendEnvironment["PORT"] = [string]$FrontendPort
    $frontendEnvironment["HOSTNAME"] = "127.0.0.1"
    $frontendEnvironment["NODE_ENV"] = "production"
    $frontendEnvironment["NEXT_PUBLIC_API_URL"] = "/api"
    $frontendEnvironment["NEXT_PUBLIC_SPRINGBOOT_API_URL"] = "/api"
    $frontendEnvironment["SPRINGBOOT_INTERNAL_URL"] = "http://127.0.0.1:$SpringPort"
    $frontendEnvironment["NEXT_PUBLIC_MODEL_API_URL"] = $modelUrl
    $frontendEnvironment["MODEL_API_URL"] = $modelUrl

    $serviceNames = if ($ModelMode -eq "off") { @("SpringBoot", "NextFrontend") } else { @("FastAPI", "SpringBoot", "NextFrontend") }
    return [PSCustomObject]@{
        StartFastApi = ($ModelMode -ne "off")
        ServiceNames = $serviceNames
        SpringEnvironment = $springEnvironment
        FrontendEnvironment = $frontendEnvironment
        CatalogSyncUrl = $syncUrl
        ModelApiUrl = $modelUrl
    }
}

function Get-SpringBootArguments {
    param([int]$SpringPort, [string]$DriveMountPoint, [string]$JarFile)
    return @(
        "-Dserver.address=127.0.0.1",
        "-Dserver.port=$SpringPort",
        "-Dspring.profiles.active=dev",
        "-Dapp.media.drive-mount=$DriveMountPoint",
        "-Dapp.media.drive.mount-path=$DriveMountPoint\",
        "-Dapp.media.drive-metadata-timeout-ms=60000",
        "-Dapp.media.drive-read-timeout-ms=60000",
        "-jar", $JarFile
    )
}

function Get-PreviewPortsToCheck {
    param([ValidateSet("off", "light", "full")][string]$ModelMode, [int]$SpringPort, [int]$FastApiPort, [int]$FrontendPort)
    $ports = @(
        @{ Port = $SpringPort; Name = "Spring Boot Backend" },
        @{ Port = $FrontendPort; Name = "Next.js Web Frontend" }
    )
    if ($ModelMode -ne "off") { $ports = @(@{ Port = $FastApiPort; Name = "FastAPI AI Engine" }) + $ports }
    return $ports
}

function Test-FrontendBuildStale {
    param([string]$FrontendDirectory, [string]$BuildIdPath, [string]$StandaloneServerPath, [string]$BuildEnvironmentFile, [string]$ExpectedBuildEnvironment)
    if (-not (Test-Path -LiteralPath $BuildIdPath -PathType Leaf) -or -not (Test-Path -LiteralPath $StandaloneServerPath -PathType Leaf) -or -not (Test-Path -LiteralPath $BuildEnvironmentFile -PathType Leaf)) { return $true }
    if ((Get-Content -LiteralPath $BuildEnvironmentFile -Raw) -cne $ExpectedBuildEnvironment) { return $true }

    $buildTime = (Get-Item -LiteralPath $BuildIdPath).LastWriteTimeUtc
    $sourceFiles = @()
    $sourceFiles += @(Get-ChildItem -LiteralPath $FrontendDirectory -File -Force -ErrorAction SilentlyContinue)
    foreach ($directory in @("app", "components", "features", "lib", "public", "types")) {
        $sourceDirectory = Join-Path $FrontendDirectory $directory
        if (Test-Path -LiteralPath $sourceDirectory -PathType Container) {
            $sourceFiles += @(Get-ChildItem -LiteralPath $sourceDirectory -Recurse -File -Force -ErrorAction SilentlyContinue)
        }
    }
    foreach ($sourceFile in $sourceFiles) {
        if ($sourceFile.LastWriteTimeUtc -gt $buildTime) { return $true }
    }
    return $false
}

function Test-RecordedProcessIdentity {
    param($Process, $Record)
    if (-not $Process -or -not $Record -or [string]::IsNullOrWhiteSpace([string]$Record.ExecutablePath) -or [string]::IsNullOrWhiteSpace([string]$Record.StartTime)) { return $false }
    try {
        $expectedPath = [System.IO.Path]::GetFullPath([string]$Record.ExecutablePath)
        $livePath = [System.IO.Path]::GetFullPath([string]$Process.ExecutablePath)
        $expectedStart = [DateTime]::Parse([string]$Record.StartTime).ToUniversalTime()
        $liveStart = ([DateTime]$Process.CreationDate).ToUniversalTime()
        if ($Process.PSObject.Properties["ProcessId"] -and [int]$Process.ProcessId -ne [int]$Record.PID) { return $false }
        return [string]::Equals($livePath, $expectedPath, [System.StringComparison]::OrdinalIgnoreCase) -and [Math]::Abs(($liveStart - $expectedStart).TotalSeconds) -le 3.0
    } catch {
        return $false
    }
}

$previewPaths = Get-PreviewPaths -BackendDirectory $backendDir -TargetDirectory $targetDir -DataDirectory $DataDirectory -StateFile $StateFile
$DataDirectory = $previewPaths.DataDirectory
$stateFile = $previewPaths.StateFile
$driveStateFile = $previewPaths.DriveStateFile
New-Item -ItemType Directory -Path $DataDirectory -Force | Out-Null
New-Item -ItemType Directory -Path ([System.IO.Path]::GetDirectoryName($stateFile)) -Force | Out-Null

# -----------------------------------------------------------------------------
# 0. Kiểm tra Stack đang chạy (không ghi đè state của stack đang hoạt động)
# -----------------------------------------------------------------------------
if (Test-Path -Path $stateFile -PathType Leaf -ErrorAction SilentlyContinue) {
    try {
        $existingState = Get-Content -Path $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $existingState -or -not $existingState.PSObject.Properties["Processes"] -or -not $existingState.PSObject.Properties["DriveMounted"]) {
            throw "Tệp trạng thái '$stateFile' thiếu cấu trúc ownership. Không ghi đè để tránh mất thông tin tiến trình."
        }
        if ($existingState.DriveMounted) {
            throw "Stack hiện có ghi nhận Drive đã gắn trong '$stateFile'. Vui lòng dừng stack cũ trước."
        }
        if ($existingState.Processes) {
            $hasLive = $false
            foreach ($p in $existingState.Processes) {
                if ($p.PID -and [int]$p.PID -gt 0) {
                    $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $($p.PID)" -ErrorAction SilentlyContinue
                    if ($cim -and (Test-RecordedProcessIdentity -Process $cim -Record $p)) {
                        $hasLive = $true
                        break
                    }
                }
            }
            if ($hasLive) {
                throw "ĐÃ CÓ STACK HOẠT ĐỘNG: Phát hiện tệp trạng thái '$stateFile' có tiến trình đang chạy. Vui lòng dừng stack trước bằng lệnh: powershell -File scripts\stop_preview_stack.ps1"
            }
        }
    } catch [System.Management.Automation.ItemNotFoundException] {
        # File không tồn tại, tiếp tục
    }
}

# Khởi tạo đối tượng trạng thái theo dõi tăng dần
$stackState = [PSCustomObject]@{
    Timestamp       = [DateTime]::UtcNow.ToString("o")
    ReleaseLevel    = "usable_preview"
    Status          = "STARTING"
    SpringPort      = $SpringPort
    FastApiPort     = $FastApiPort
    FrontendPort    = $FrontendPort
    ModelMode       = $ModelMode
    DataDirectory   = $DataDirectory
    StateFile       = $stateFile
    DriveStateFile  = $driveStateFile
    DriveMounted    = $false
    DriveMountPoint = $DriveMountPoint
    DriveRemote     = $DriveRemote
    DriveFolderId   = $DriveFolderId
    Processes       = @()
}
$faProc = $null
$sbProc = $null
$feProc = $null

function Save-StackState {
    $json = $stackState | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($stateFile, $json, [System.Text.UTF8Encoding]::new($false))
}

# Lưu trạng thái STARTING ban đầu
Save-StackState

# -----------------------------------------------------------------------------
# Khối Thực Thi Có Bọc Dọn Dẹp An Toàn (Try / Catch Cleanup Handler)
# -----------------------------------------------------------------------------
try {
    # -------------------------------------------------------------------------
    # 1. Preflight kiểm tra cổng mạng
    # -------------------------------------------------------------------------
    Write-Host "`n[1/7] Kiểm tra sẵn sàng các cổng mạng..." -ForegroundColor Yellow
    $portsToCheck = Get-PreviewPortsToCheck -ModelMode $ModelMode -SpringPort $SpringPort -FastApiPort $FastApiPort -FrontendPort $FrontendPort

    foreach ($p in $portsToCheck) {
        $conn = Get-NetTCPConnection -LocalPort $p.Port -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            throw "CỔNG BỊ CHIẾM: Cổng $($p.Port) ($($p.Name)) đang được sử dụng bởi PID $($conn.OwningProcess). Vui lòng dừng tiến trình đó trước khi khởi động bản dùng thử."
        }
    }
    $checkedPorts = @($portsToCheck | ForEach-Object { $_.Port }) -join ", "
    Write-Host "  -> Tất cả các cổng ($checkedPorts) đều đang trống và sẵn sàng." -ForegroundColor Green

    # -------------------------------------------------------------------------
    # 2. Phát hiện JDK cho tiến trình (không thay đổi biến môi trường OS)
    # -------------------------------------------------------------------------
    Write-Host "`n[2/7] Kiểm tra môi trường Java & JDK..." -ForegroundColor Yellow
    if (-not $env:JAVA_HOME) {
        if (Test-Path "C:\Program Files\Java\jdk-25.0.3") {
            $env:JAVA_HOME = "C:\Program Files\Java\jdk-25.0.3"
        } else {
            $candidate = Get-ChildItem "C:\Program Files\Java\jdk-*" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($candidate) { $env:JAVA_HOME = $candidate.FullName }
        }
    }

    $javaBin = if ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME "bin\java.exe"))) {
        Join-Path $env:JAVA_HOME "bin\java.exe"
    } elseif (Test-Path "C:\Program Files\Java\jdk-25.0.3\bin\java.exe") {
        "C:\Program Files\Java\jdk-25.0.3\bin\java.exe"
    } else {
        (Get-Command java -ErrorAction Stop).Source
    }
    Write-Host "  -> Java executable: $javaBin" -ForegroundColor Green
    Write-Host "  -> Process JAVA_HOME: $env:JAVA_HOME (chỉ áp dụng trong phiên làm việc này)" -ForegroundColor Gray

    # -------------------------------------------------------------------------
    # 3. Kiểm tra và đảm bảo Backend Jar tươi mới (moviercm-backend-0.0.1-SNAPSHOT.jar)
    # -------------------------------------------------------------------------
    Write-Host "`n[3/7] Kiểm tra tính tươi mới của artifact Backend..." -ForegroundColor Yellow
    $jarFile = Join-Path $backendDir "target\moviercm-backend-0.0.1-SNAPSHOT.jar"
    $needsBuild = -not (Test-Path $jarFile)

    if (-not $needsBuild) {
        $jarMtime = (Get-Item $jarFile).LastWriteTime
        $newestSrc = Get-ChildItem -Path (Join-Path $backendDir "src\main") -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($newestSrc -and ($newestSrc.LastWriteTime -gt $jarMtime)) {
            Write-Host "  -> Phát hiện mã nguồn mới hơn artifact ($($newestSrc.Name) lúc $($newestSrc.LastWriteTime)). Yêu cầu đóng gói lại." -ForegroundColor Yellow
            $needsBuild = $true
        }
        $pomFile = Join-Path $backendDir "pom.xml"
        if ((Test-Path $pomFile) -and ((Get-Item $pomFile).LastWriteTime -gt $jarMtime)) {
            Write-Host "  -> Phát hiện cấu hình Maven mới hơn artifact (pom.xml). Yêu cầu đóng gói lại." -ForegroundColor Yellow
            $needsBuild = $true
        }
    }

    if ($needsBuild) {
        Write-Host "  -> Đang đóng gói moviercm-backend-0.0.1-SNAPSHOT.jar bằng Maven..." -ForegroundColor Yellow
        cmd.exe /c "cd /d `"$backendDir`" && mvnw.cmd clean package dependency:build-classpath `"-Dmdep.outputFile=target/cp.txt`" -DskipTests -q"
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $jarFile)) {
            throw "Đóng gói backend jar thất bại. Vui lòng kiểm tra lỗi Maven."
        }
        Write-Host "  -> Đóng gói thành công: $jarFile ($((Get-Item $jarFile).Length) bytes)." -ForegroundColor Green
    } else {
        Write-Host "  -> Artifact jar đã sẵn sàng và khớp mã nguồn: $jarFile" -ForegroundColor Green
    }

    # -------------------------------------------------------------------------
    # 4. Thiết lập Secret đồng bộ và chế độ Mô hình AI
    # -------------------------------------------------------------------------
    Write-Host "`n[4/7] Thiết lập cấu hình đồng bộ bảo mật và Mô hình AI..." -ForegroundColor Yellow
    if ($ModelMode -eq "off") {
        $SyncSecret = ""
    } elseif (-not $SyncSecret) {
        if ($env:FASTAPI_SYNC_SECRET) {
            $SyncSecret = $env:FASTAPI_SYNC_SECRET
        } elseif ($env:CATALOG_SYNC_TOKEN) {
            $SyncSecret = $env:CATALOG_SYNC_TOKEN
        } else {
            $SyncSecret = "preview_session_" + [Guid]::NewGuid().ToString("N").Substring(0, 16)
        }
    }

    $runtimeContract = Get-PreviewRuntimeContract `
        -ModelMode $ModelMode `
        -SpringPort $SpringPort `
        -FastApiPort $FastApiPort `
        -FrontendPort $FrontendPort `
        -DataDirectory $DataDirectory `
        -SyncSecret $SyncSecret

    Write-Host "  -> Chế độ phục vụ AI (ModelMode): $ModelMode" -ForegroundColor Cyan
    if ($ModelMode -eq "full") {
        Write-Host "  -> CHÚ Ý: Chế độ 'full' sử dụng mô hình thật Qwen3-4B + Phase23 LoRA trên CUDA/GPU." -ForegroundColor Magenta
        Write-Host "  -> Tuyệt đối không gọi fallback/template là mô hình thật." -ForegroundColor Magenta
    } elseif ($ModelMode -eq "light") {
        Write-Host "  -> Chế độ 'light' sử dụng semantic search và embedding gọn nhẹ, phù hợp CPU." -ForegroundColor Gray
    } else {
        Write-Host "  -> AI tắt; Spring Boot và giao diện vẫn chạy, FastAPI không được khởi động." -ForegroundColor Gray
    }

    # -------------------------------------------------------------------------
    # 5. Gắn kết Google Drive (nếu được yêu cầu)
    # -------------------------------------------------------------------------
    if ($MountDrive) {
        Write-Host "`n[5/7] Gắn kết Google Drive ($DriveRemote) vào điểm gắn $DriveMountPoint..." -ForegroundColor Yellow
        $mountScript = Join-Path $root "scripts\drive\mount_drive.ps1"
        $mountResultText = (& $mountScript -Execute -Remote $DriveRemote -DriveRootFolderId $DriveFolderId -MountPoint $DriveMountPoint -StateFile $driveStateFile -AsJson | Out-String)
        $mountResult = $mountResultText | ConvertFrom-Json
        if (-not $mountResult.Success -or $mountResult.Status -ne "MOUNTED") {
            throw "Gắn kết Google Drive thất bại. Vui lòng kiểm tra lại dịch vụ WinFsp hoặc rclone."
        }
        $stackState.DriveMounted = $true
        Save-StackState
        Write-Host "  -> Google Drive đã gắn thành công tại $DriveMountPoint (read-only, cache-off)." -ForegroundColor Green
    } else {
        Write-Host "`n[5/7] Bỏ qua gắn kết Google Drive (truyền -MountDrive để tự động gắn)." -ForegroundColor Gray
    }

    # -------------------------------------------------------------------------
    # 6. Khởi chạy 3 Dịch vụ
    # -------------------------------------------------------------------------
    Write-Host "`n[6/7] Đang khởi động các dịch vụ..." -ForegroundColor Yellow

    # Tạo thư mục và đường dẫn log riêng cho các dịch vụ nền
    $logsDir = Join-Path $root "target\preview_logs"
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    }
    $faLog = Join-Path $logsDir "fastapi.stdout.log"
    $faErr = Join-Path $logsDir "fastapi.stderr.log"
    $sbLog = Join-Path $logsDir "springboot.stdout.log"
    $sbErr = Join-Path $logsDir "springboot.stderr.log"
    $feLog = Join-Path $logsDir "nextjs.stdout.log"
    $feErr = Join-Path $logsDir "nextjs.stderr.log"

    if ($runtimeContract.StartFastApi) {
        # 6.1. FastAPI AI Engine (explicit light/full opt-in only)
        Write-Host "  [a] Khởi động FastAPI trên cổng $FastApiPort..." -ForegroundColor Yellow
        $faEnv = [System.Collections.Generic.Dictionary[string, string]]::new()
        foreach ($key in [System.Environment]::GetEnvironmentVariables().Keys) {
            $faEnv[$key] = [System.Environment]::GetEnvironmentVariable($key)
        }
        $faEnv["PORT"] = [string]$FastApiPort
        $faEnv["FASTAPI_SYNC_SECRET"] = $SyncSecret
        $faEnv["CATALOG_SYNC_TOKEN"] = $SyncSecret
        $faEnv["SERVING_MODE"] = $ModelMode
        $faEnv["USE_FULL_QWEN3_4B_LORA"] = if ($ModelMode -eq "full") { "true" } else { "false" }
        $faEnv["PYTHONPATH"] = $fastapiDir

        $pythonExe = (Get-Command python -ErrorAction Stop).Source
        $faArgs = @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", [string]$FastApiPort, "--log-level", "warning")
        $faProc = Start-ChildServiceProcess -FileName $pythonExe -Arguments $faArgs -WorkingDirectory $fastapiDir -EnvironmentVariables $faEnv -StdOutFile $faLog -StdErrFile $faErr

        $stackState.Processes += @{
            Name           = "FastAPI"
            PID            = $faProc.Id
            StartTime      = $faProc.StartTime.ToString("o")
            ExecutablePath = $pythonExe
            Port           = $FastApiPort
            LogFile        = $faLog
        }
        Save-StackState
        Write-Host "      FastAPI đã spawn với PID $($faProc.Id). Chờ readiness..." -ForegroundColor Gray

        if ($TestInjectFailureAfter -eq "FastApiSpawn") {
            throw "TEST_INJECTED_FAILURE: Giả lập lỗi có kiểm soát ngay sau khi FastAPI vừa spawn."
        }

        $faReady = $false
        $deadline = [DateTime]::UtcNow.AddSeconds(90)
        while ([DateTime]::UtcNow -lt $deadline) {
            if ($faProc.HasExited) { throw "FastAPI tiến trình PID $($faProc.Id) đã thoát bất thường với mã $($faProc.ExitCode)." }
            try {
                $res = Invoke-WebRequest -Uri "http://127.0.0.1:$FastApiPort/health" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
                if ($res.StatusCode -eq 200) { $faReady = $true; break }
            } catch { Start-Sleep -Milliseconds 600 }
        }
        if (-not $faReady) { throw "FastAPI không sẵn sàng trên cổng $FastApiPort sau 90 giây." }
        Write-Host "      FastAPI HEALTHY (200 OK)." -ForegroundColor Green
    } else {
        Write-Host "  [a] FastAPI không được khởi động trong ModelMode off." -ForegroundColor Gray
    }

    # 6.2. Spring Boot Core Backend
    Write-Host "  [b] Khởi động Spring Boot trên cổng $SpringPort..." -ForegroundColor Yellow
    $springArgs = Get-SpringBootArguments -SpringPort $SpringPort -DriveMountPoint $DriveMountPoint -JarFile $jarFile

    $sbEnv = [System.Collections.Generic.Dictionary[string, string]]::new()
    foreach ($key in [System.Environment]::GetEnvironmentVariables().Keys) {
        $sbEnv[$key] = [System.Environment]::GetEnvironmentVariable($key)
    }
    foreach ($key in $runtimeContract.SpringEnvironment.Keys) {
        $sbEnv[$key] = $runtimeContract.SpringEnvironment[$key]
    }
    $sbProc = Start-ChildServiceProcess -FileName $javaBin -Arguments $springArgs -WorkingDirectory $backendDir -EnvironmentVariables $sbEnv -StdOutFile $sbLog -StdErrFile $sbErr

    # Lưu ownership ngay khi tiến trình spawn
    $stackState.Processes += @{
        Name           = "SpringBoot"
        PID            = $sbProc.Id
        StartTime      = $sbProc.StartTime.ToString("o")
        ExecutablePath = $javaBin
        Port           = $SpringPort
        LogFile        = $sbLog
    }
    Save-StackState
    Write-Host "      Spring Boot đã spawn với PID $($sbProc.Id). Chờ readiness..." -ForegroundColor Gray

    # Failure Injection Hook kiểm thử
    if ($TestInjectFailureAfter -eq "SpringBootSpawn") {
        throw "TEST_INJECTED_FAILURE: Giả lập lỗi có kiểm soát ngay sau khi Spring Boot vừa spawn."
    }

    # Chờ Spring Boot sẵn sàng
    $sbReady = $false
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($sbProc.HasExited) { throw "Spring Boot tiến trình PID $($sbProc.Id) đã thoát bất thường với mã $($sbProc.ExitCode)." }
        try {
            $res = Invoke-WebRequest -Uri "http://127.0.0.1:$SpringPort/api/health" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if ($res.StatusCode -eq 200) { $sbReady = $true; break }
        } catch { Start-Sleep -Milliseconds 800 }
    }
    if (-not $sbReady) { throw "Spring Boot không sẵn sàng trên cổng $SpringPort sau 60 giây." }
    Write-Host "      Spring Boot HEALTHY (200 OK)." -ForegroundColor Green

    # 6.3. Next.js Web Frontend
    Write-Host "  [c] Khởi động Next.js Frontend trên cổng $FrontendPort..." -ForegroundColor Yellow
    $feEnv = [System.Collections.Generic.Dictionary[string, string]]::new()
    foreach ($key in [System.Environment]::GetEnvironmentVariables().Keys) {
        $feEnv[$key] = [System.Environment]::GetEnvironmentVariable($key)
    }
    foreach ($key in $runtimeContract.FrontendEnvironment.Keys) {
        $feEnv[$key] = $runtimeContract.FrontendEnvironment[$key]
    }
    $nodeExe = (Get-Command node -ErrorAction Stop).Source
    $nextBin = Join-Path $frontendDir "node_modules\next\dist\bin\next"
    $buildIdPath = Join-Path $frontendDir ".next\BUILD_ID"
    $standaloneDir = Join-Path $frontendDir ".next\standalone"
    $standaloneServer = Join-Path $standaloneDir "server.js"
    $buildEnvironmentFile = Join-Path $frontendDir ".next\preview-build-env.json"
    $expectedBuildEnvironment = [PSCustomObject]@{
        ProxyTarget = $feEnv["SPRINGBOOT_INTERNAL_URL"]
        ApiUrl = $feEnv["NEXT_PUBLIC_API_URL"]
        SpringBootApiUrl = $feEnv["NEXT_PUBLIC_SPRINGBOOT_API_URL"]
        ModelApiUrl = $feEnv["NEXT_PUBLIC_MODEL_API_URL"]
    } | ConvertTo-Json -Compress
    if (Test-FrontendBuildStale -FrontendDirectory $frontendDir -BuildIdPath $buildIdPath -StandaloneServerPath $standaloneServer -BuildEnvironmentFile $buildEnvironmentFile -ExpectedBuildEnvironment $expectedBuildEnvironment) {
        Write-Host "      Frontend build chưa có hoặc đã cũ; đang build standalone..." -ForegroundColor Yellow
        $buildOut = Join-Path $logsDir "next-build.stdout.log"
        $buildErr = Join-Path $logsDir "next-build.stderr.log"
        $buildProc = Start-ChildServiceProcess -FileName $nodeExe -Arguments @($nextBin, "build") -WorkingDirectory $frontendDir -EnvironmentVariables $feEnv -StdOutFile $buildOut -StdErrFile $buildErr
        $stackState.Processes += @{
            Name = "FrontendBuild"
            PID = $buildProc.Id
            StartTime = $buildProc.StartTime.ToString("o")
            ExecutablePath = $nodeExe
            Port = $null
            LogFile = $buildOut
        }
        Save-StackState
        if (-not $buildProc.WaitForExit(300000)) { throw "Next.js standalone build timed out after 300 seconds." }
        $stackState.Processes = @($stackState.Processes | Where-Object { [int]$_.PID -ne $buildProc.Id })
        Save-StackState
        if ($buildProc.ExitCode -ne 0) { throw "Next.js standalone build thất bại với mã thoát $($buildProc.ExitCode)." }
        [System.IO.File]::WriteAllText($buildEnvironmentFile, $expectedBuildEnvironment, [System.Text.UTF8Encoding]::new($false))
    }
    if (-not (Test-Path -LiteralPath $standaloneServer -PathType Leaf)) { throw "Không tìm thấy frontend standalone server tại '$standaloneServer'." }

    $sourceStatic = Join-Path $frontendDir ".next\static"
    $standaloneStatic = Join-Path $standaloneDir ".next\static"
    New-Item -ItemType Directory -Path $standaloneStatic -Force | Out-Null
    if (Test-Path -LiteralPath $sourceStatic -PathType Container) {
        $staticItems = @(Get-ChildItem -LiteralPath $sourceStatic -Force)
        foreach ($item in $staticItems) { Copy-Item -LiteralPath $item.FullName -Destination $standaloneStatic -Recurse -Force }
    }
    $sourcePublic = Join-Path $frontendDir "public"
    $standalonePublic = Join-Path $standaloneDir "public"
    if (Test-Path -LiteralPath $sourcePublic -PathType Container) {
        New-Item -ItemType Directory -Path $standalonePublic -Force | Out-Null
        foreach ($item in @(Get-ChildItem -LiteralPath $sourcePublic -Force)) { Copy-Item -LiteralPath $item.FullName -Destination $standalonePublic -Recurse -Force }
    }

    $feProc = Start-ChildServiceProcess -FileName $nodeExe -Arguments @("server.js") -WorkingDirectory $standaloneDir -EnvironmentVariables $feEnv -StdOutFile $feLog -StdErrFile $feErr

    # Lưu ownership ngay khi tiến trình spawn
    $stackState.Processes += @{
        Name           = "NextFrontend"
        PID            = $feProc.Id
        StartTime      = $feProc.StartTime.ToString("o")
        ExecutablePath = $nodeExe
        Port           = $FrontendPort
        LogFile        = $feLog
    }
    Save-StackState
    Write-Host "      Next.js đã spawn với PID $($feProc.Id). Chờ readiness..." -ForegroundColor Gray

    # Chờ Next.js sẵn sàng
    $feReady = $false
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($feProc.HasExited) { throw "Next.js tiến trình PID $($feProc.Id) đã thoát bất thường với mã $($feProc.ExitCode)." }
        try {
            $res = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if ($res.StatusCode -eq 200) { $feReady = $true; break }
        } catch { Start-Sleep -Milliseconds 600 }
    }
    if (-not $feReady) { throw "Next.js không sẵn sàng trên cổng $FrontendPort sau 45 giây." }
    Write-Host "      Next.js Frontend HEALTHY (200 OK)." -ForegroundColor Green

    # Cập nhật trạng thái READY chính thức
    $stackState.Status = "READY"
    Save-StackState

    Write-Host "`n==========================================================================" -ForegroundColor Green
    Write-Host " BẢN DÙNG THỬ (USABLE PREVIEW) ĐÃ SẴN SÀNG PHỤC VỤ!" -ForegroundColor Green
    Write-Host "==========================================================================" -ForegroundColor Green
    Write-Host " URL Giao diện Web   : http://localhost:$FrontendPort" -ForegroundColor White
    Write-Host " Core Backend API    : http://localhost:$SpringPort" -ForegroundColor White
    if ($runtimeContract.StartFastApi) {
        Write-Host " AI & Sync Engine    : http://localhost:$FastApiPort ($ModelMode)" -ForegroundColor White
    } else {
        Write-Host " AI & Sync Engine    : disabled (ModelMode off; FastAPI không được khởi động)" -ForegroundColor Gray
    }
    Write-Host " Tài khoản Admin     : admin / password123 (truy cập /admin/import)" -ForegroundColor White
    Write-Host " Tài khoản User      : user / password123 (xem phim, tìm kiếm)" -ForegroundColor White
    Write-Host " Tệp trạng thái      : $stateFile" -ForegroundColor Gray
    Write-Host "`nĐể dừng toàn bộ cụm tiến trình trên an toàn, chạy lệnh:" -ForegroundColor Yellow
    Write-Host "  powershell -NoProfile -File scripts\stop_preview_stack.ps1 -StateFile `"$stateFile`"" -ForegroundColor Yellow
    Write-Host "==========================================================================" -ForegroundColor Green

    if (-not $Background) {
        Write-Host "`nĐang giữ phiên làm việc... Nhấn Ctrl+C để dừng." -ForegroundColor Gray
        try {
            while ((-not $runtimeContract.StartFastApi -or -not $faProc.HasExited) -and -not $sbProc.HasExited -and -not $feProc.HasExited) {
                Start-Sleep -Seconds 2
            }
        } finally {
            Write-Host "`nPhát hiện yêu cầu dừng. Đang dọn dẹp các tiến trình..." -ForegroundColor Yellow
            $stopScript = Join-Path $PSScriptRoot "stop_preview_stack.ps1"
            if (Test-Path $stopScript) {
                & powershell -NoProfile -File $stopScript -StateFile $stateFile
            }
        }
    }
}
catch {
    $caughtErr = $_
    Write-Host "`n[CẢNH BÁO LỖI KHỞI ĐỘNG] Gặp sự cố trong quá trình khởi động:" -ForegroundColor Red
    Write-Host "  $($caughtErr.Exception.Message)" -ForegroundColor Red
    Write-Host "Đang kích hoạt dọn dẹp an toàn các tài nguyên đã tạo..." -ForegroundColor Yellow

    $cleanupFailed = $false

    # Dừng ngược thứ tự các tiến trình đã tạo
    if ($stackState.Processes -and $stackState.Processes.Count -gt 0) {
        for ($i = $stackState.Processes.Count - 1; $i -ge 0; $i--) {
            $pInfo = $stackState.Processes[$i]
            $procId = [int]$pInfo.PID
            $pName = [string]$pInfo.Name
            $pStartStr = [string]$pInfo.StartTime

            Write-Host "  -> Đang dọn dẹp $pName (PID $procId)..." -ForegroundColor Gray
            if ($procId -gt 0 -and $pStartStr) {
                $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
                if ($cim) {
                    if (Test-RecordedProcessIdentity -Process $cim -Record $pInfo) {
                        try {
                            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                        } catch {}

                        # Chờ tối đa 5 giây
                        $dead = [DateTime]::UtcNow.AddSeconds(5)
                        while ([DateTime]::UtcNow -lt $dead) {
                            if (-not (Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue)) { break }
                            Start-Sleep -Milliseconds 300
                        }

                        if (-not (Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue)) {
                            Write-Host "  -> $pName (PID $procId) đã dừng thành công." -ForegroundColor Green
                        } else {
                            Write-Warning "  -> $pName (PID $procId) chưa dừng được."
                            $cleanupFailed = $true
                        }
                    } else {
                        Write-Warning "  -> Không khớp danh tính PID $procId. Bỏ qua không dừng."
                        $cleanupFailed = $true
                    }
                } else {
                    Write-Host "  -> $pName (PID $procId) không còn chạy." -ForegroundColor Gray
                }
            }
        }
    }

    # Tháo gắn Google Drive nếu đã được gắn
    if ($stackState.DriveMounted) {
        Write-Host "  -> Tháo gắn Google Drive ($DriveMountPoint)..." -ForegroundColor Gray
        $stopDriveScript = Join-Path $root "scripts\drive\stop_drive.ps1"
        if (Test-Path $stopDriveScript) {
            try {
                $driveResultText = (& powershell -NoProfile -File $stopDriveScript -StateFile $driveStateFile -AsJson | Out-String)
                $driveResult = $driveResultText | ConvertFrom-Json
                if (-not $driveResult.Success) { throw $driveResult.Message }
            } catch {
                Write-Warning "Lỗi khi chạy stop_drive.ps1: $_"
                $cleanupFailed = $true
            }
        } else {
            Write-Warning "Không tìm thấy stop_drive.ps1 để tháo gắn drive thuộc stack này."
            $cleanupFailed = $true
        }
    }

    if (-not $cleanupFailed) {
        Remove-Item -Path $stateFile -Force -ErrorAction SilentlyContinue
        Write-Host "  -> Dọn dẹp hoàn tất: mọi tài nguyên tạo bởi lượt chạy này đã được giải phóng." -ForegroundColor Green
    } else {
        $stackState.Status = "FAILED_NEEDS_CLEANUP"
        try { Save-StackState } catch { Write-Warning "Không thể lưu ownership state sau lỗi dọn dẹp: $_" }
        Write-Warning "  -> Một số tài nguyên chưa dừng được hẳn. Giữ tệp trạng thái tại: $stateFile để người dùng kiểm tra."
    }

    throw $caughtErr
}
