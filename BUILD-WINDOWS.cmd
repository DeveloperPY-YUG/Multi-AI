@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-windows.ps1"
if errorlevel 1 (
  echo Build failed. Check the error above.
  pause
  exit /b 1
)
echo Release ZIP ready in releasepause
