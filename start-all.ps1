# ==========================================================
# DIPPIE CINEMA - FULLSTACK MICROSERVICES LAUNCHER
# Khởi chạy đồng thời 3 Dịch vụ: Spring Boot, FastAPI AI, Next.js
# ==========================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   DIPPIE CINEMA - KHOI CHAY TOAN BO HE THONG MICROSERVICES " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

$rootDir = $PSScriptRoot

# Tu dong phat hien JDK tren he thong (uu tien JDK 17/21 cho Spring Boot 3)
$javaHome = $null
$candidates = @(
    (Get-ChildItem "C:\Program Files\Microsoft\jdk-17*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName),
    (Get-ChildItem "C:\Program Files\Eclipse Adoptium\jdk-17*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName),
    (Get-ChildItem "C:\Program Files\Java\jdk-17*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName),
    (Get-ChildItem "C:\Program Files\Microsoft\jdk-21*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName),
    (Get-ChildItem "C:\Program Files\Eclipse Adoptium\jdk-21*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName),
    (Get-ChildItem "C:\Program Files\Java\jdk-21*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
)
$found = $candidates | Where-Object { $_ -and (Test-Path (Join-Path $_ "bin\java.exe")) } | Select-Object -First 1
if ($found) {
    $javaHome = $found
} elseif ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME "bin\java.exe"))) {
    $javaHome = $env:JAVA_HOME
} else {
    $candidatesAll = @(
        (Get-ChildItem "C:\Program Files\Microsoft\jdk*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName),
        (Get-ChildItem "C:\Program Files\Eclipse Adoptium\jdk*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName),
        (Get-ChildItem "C:\Program Files\Java\jdk*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    )
    $foundAll = $candidatesAll | Where-Object { $_ -and (Test-Path (Join-Path $_ "bin\java.exe")) } | Select-Object -First 1
    if ($foundAll) {
        $javaHome = $foundAll
    } else {
        $javaCmd = Get-Command java -ErrorAction SilentlyContinue
        if ($javaCmd) {
            $javaHome = (Get-Item (Split-Path (Split-Path $javaCmd.Source -Parent) -Parent)).FullName
        }
    }
}

# 1. Start Spring Boot Backend (:8080)
Write-Host "`n[1/3] Dang khoi dong Backend Spring Boot (:8080)..." -ForegroundColor Yellow
if ($javaHome) {
    Write-Host "  -> Su dung JDK: $javaHome" -ForegroundColor Gray
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$rootDir\backend\springboot'; `$env:JAVA_HOME = '$javaHome'; `$env:PATH = '$javaHome\bin;' + `$env:PATH; Write-Host '--- 1. BACKEND SPRING BOOT (:8080) ---' -ForegroundColor Green; .\mvnw.cmd spring-boot:run"
} else {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$rootDir\backend\springboot'; Write-Host '--- 1. BACKEND SPRING BOOT (:8080) ---' -ForegroundColor Green; .\mvnw.cmd spring-boot:run"
}

# 2. Start FastAPI AI Gateway (:8000)
Write-Host "[2/3] Dang khoi dong Backend AI Gateway (FastAPI :8000)..." -ForegroundColor Yellow
$pyCmd = "python"
$condaPaths = @(
    "$env:USERPROFILE\anaconda3\envs\dippie-qwen\python.exe",
    "$env:USERPROFILE\miniconda3\envs\dippie-qwen\python.exe",
    "C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe"
)
foreach ($cp in $condaPaths) {
    if (Test-Path $cp) {
        $pyCmd = "& '$cp'"
        break
    }
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$rootDir\backend\fastapi'; `$env:SERVING_MODE = 'auto'; `$env:DEVICE = 'auto'; `$env:ENABLE_FALLBACK = 'true'; Write-Host '--- 2. FASTAPI AI GATEWAY (:8000) ---' -ForegroundColor Green; $pyCmd -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

# 3. Start Frontend Next.js (:3000)
Write-Host "[3/3] Dang khoi dong Frontend Next.js (:3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$rootDir\frontend'; Write-Host '--- 3. FRONTEND NEXT.JS (:3000) ---' -ForegroundColor Green; npm run dev"

Start-Sleep -Seconds 3

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "   TAT CA 3 DICH VU MICROSERVICES DA DUOC KHOI CHAY!       " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "• 1. Frontend Web:       http://localhost:3000" -ForegroundColor White
Write-Host "• 2. Backend Spring Boot:http://localhost:8080" -ForegroundColor White
Write-Host "• 3. Backend AI Gateway: http://localhost:8000/docs" -ForegroundColor White
Write-Host "============================================================`n" -ForegroundColor Cyan
