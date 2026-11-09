@echo off
setlocal
title Open Lakehouse Workbench - Backend
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-backend.ps1" %*
if errorlevel 1 pause
endlocal
