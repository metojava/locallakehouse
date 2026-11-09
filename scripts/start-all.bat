@echo off
setlocal
title Open Lakehouse Workbench
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-all.ps1" %*
if errorlevel 1 pause
endlocal
