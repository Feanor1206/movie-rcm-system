# ==========================================================
# DIPPIE CINEMA - FULLSTACK MICROSERVICES LAUNCHER
# Khởi chạy đồng thời 3 Dịch vụ: Spring Boot, FastAPI AI, Next.js
# ==========================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   DIPPIE CINEMA - KHOI CHAY TOAN BO HE THONG MICROSERVICES " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

$rootDir = $PSScriptRoot
$javaHome = "C:\Program Files\Java\jdk-25.0.3"

# 1. Start Spring Boot Backend (:8080)
Write-Host "`n[1/3] Dang khoi dong Backend Spring Boot (:8080)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$rootDir\backend\springboot'; `$env:JAVA_HOME = '$javaHome'; Write-Host '--- 1. BACKEND SPRING BOOT (:8080) ---' -ForegroundColor Green; .\mvnw.cmd spring-boot:run"

# 2. Start FastAPI AI Gateway (:8000)
Write-Host "[2/3] Dang khoi dong Backend AI Gateway (FastAPI :8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$rootDir\backend\fastapi'; Write-Host '--- 2. FASTAPI AI GATEWAY (:8000) ---' -ForegroundColor Green; python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

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
