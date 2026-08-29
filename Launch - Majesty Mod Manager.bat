@echo off
setlocal
powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0scripts\Launch-ModManager.ps1"
exit /b %errorlevel%
