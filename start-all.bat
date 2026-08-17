@echo off
title Dippie Cinema Fullstack Microservices Launcher
echo ============================================================
echo    DIPPIE CINEMA - KHOI CHAY DONG THOI TAT CA MICROSERVICES
echo ============================================================

set ROOT_DIR=%~dp0

echo.
echo [1/3] Dang khoi dong Backend Spring Boot (:8080)...
start "1. Spring Boot Core (:8080)" cmd /k "cd /d %ROOT_DIR%backend\springboot && set JAVA_HOME=C:\Program Files\Java\jdk-25.0.3&& mvnw.cmd spring-boot:run"

echo [2/3] Dang khoi dong Backend AI Gateway (FastAPI :8000)...
start "2. FastAPI AI Gateway (:8000)" cmd /k "cd /d %ROOT_DIR%backend\fastapi && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo [3/3] Dang khoi dong Frontend Next.js (:3000)...
start "3. Frontend Next.js (:3000)" cmd /k "cd /d %ROOT_DIR%frontend && npm run dev"

echo.
echo ============================================================
echo    TAT CA 3 DICH VU MICROSERVICES DANG CHAY TREN MAY BAN!
echo ============================================================
echo - 1. Frontend Web:        http://localhost:3000
echo - 2. Backend Spring Boot: http://localhost:8080
echo - 3. Backend AI Gateway:  http://localhost:8000/docs
echo.
echo ============================================================
pause
