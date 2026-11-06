@echo off
title Dippie Cinema Fullstack Microservices Launcher
echo ============================================================
echo    DIPPIE CINEMA - KHOI CHAY DONG THOI TAT CA MICROSERVICES
echo ============================================================

set ROOT_DIR=%~dp0

rem Tu dong nhan dien JDK tren he thong (uu tien JDK 17/21 cho Spring Boot 3)
set "DETECTED_JAVA_HOME="
for /d %%d in ("C:\Program Files\Microsoft\jdk-17*" "C:\Program Files\Eclipse Adoptium\jdk-17*" "C:\Program Files\Java\jdk-17*" "C:\Program Files\Microsoft\jdk-21*" "C:\Program Files\Eclipse Adoptium\jdk-21*" "C:\Program Files\Java\jdk-21*") do (
    if exist "%%d\bin\java.exe" if "%DETECTED_JAVA_HOME%"=="" set "DETECTED_JAVA_HOME=%%d"
)
if "%DETECTED_JAVA_HOME%"=="" (
    if defined JAVA_HOME (
        if exist "%JAVA_HOME%\bin\java.exe" set "DETECTED_JAVA_HOME=%JAVA_HOME%"
    )
)
if "%DETECTED_JAVA_HOME%"=="" (
    for /f "delims=" %%i in ('where java.exe 2^>nul') do (
        for %%j in ("%%~dpi..") do (
            if exist "%%~fj\bin\java.exe" if "%DETECTED_JAVA_HOME%"=="" set "DETECTED_JAVA_HOME=%%~fj"
        )
    )
)
if "%DETECTED_JAVA_HOME%"=="" (
    for /d %%d in ("C:\Program Files\Microsoft\jdk*" "C:\Program Files\Eclipse Adoptium\jdk*" "C:\Program Files\Java\jdk*") do (
        if exist "%%d\bin\java.exe" if "%DETECTED_JAVA_HOME%"=="" set "DETECTED_JAVA_HOME=%%d"
    )
)
if not "%DETECTED_JAVA_HOME%"=="" (
    set "JAVA_HOME=%DETECTED_JAVA_HOME%"
    echo [JDK] Phat hien JDK: %DETECTED_JAVA_HOME%
)

echo.
echo [1/3] Dang khoi dong Backend Spring Boot (:8080)...
start "1. Spring Boot Core (:8080)" cmd /k "cd /d %ROOT_DIR%backend\springboot && set JAVA_HOME=%JAVA_HOME%&& set PATH=%JAVA_HOME%\bin;%%PATH%%&& mvnw.cmd spring-boot:run"

echo [2/3] Dang khoi dong Backend AI Gateway (FastAPI :8000)...
set FASTAPI_PY=python
if exist "%USERPROFILE%\anaconda3\envs\dippie-qwen\python.exe" set FASTAPI_PY="%USERPROFILE%\anaconda3\envs\dippie-qwen\python.exe"
if exist "%USERPROFILE%\miniconda3\envs\dippie-qwen\python.exe" set FASTAPI_PY="%USERPROFILE%\miniconda3\envs\dippie-qwen\python.exe"
if exist "C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe" set FASTAPI_PY="C:\Users\Admin\anaconda3\envs\dippie-qwen\python.exe"
start "2. FastAPI AI Gateway (:8000)" cmd /k "cd /d %ROOT_DIR%backend\fastapi && set SERVING_MODE=auto&& set DEVICE=auto&& set ENABLE_FALLBACK=true&& %FASTAPI_PY% -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

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
