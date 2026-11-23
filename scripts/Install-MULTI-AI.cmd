@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Create-Desktop-Shortcut.ps1"
if errorlevel 1 (
  echo Could not create the desktop shortcut.
  pause
  exit /b 1
)
echo.
echo MULTI-AI is ready. Use your desktop shortcut to launch it.
pause
