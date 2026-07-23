@echo off
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Run scripts\setup.bat first.
  pause
  exit /b 1
)
echo Running smoke test (read-only)...
.venv\Scripts\python test_smoke.py
echo.
pause
