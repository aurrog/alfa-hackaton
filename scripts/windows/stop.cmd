@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1" %*
timeout /t 3 >nul
