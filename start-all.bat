@echo off
setlocal
set ROOT_DIR=%~dp0
powershell -ExecutionPolicy Bypass -File "%ROOT_DIR%start-all.ps1" %*
