@echo off
setlocal
title Open Lakehouse Workbench - Frontend
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-frontend.ps1" %*
if errorlevel 1 pause
endlocal
