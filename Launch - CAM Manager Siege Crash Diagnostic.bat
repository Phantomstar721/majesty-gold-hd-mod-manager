@echo off
set "RUNTIME_REPO=%~dp0..\majesty-gold-hd-expanded-building-slots"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%RUNTIME_REPO%\scripts\Launch-RuntimeProbe.ps1" -RuntimeRoot "%RUNTIME_REPO%\artifacts\runtime-siege-crash-diagnostic"
if errorlevel 1 pause
