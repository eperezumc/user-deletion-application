@echo off
set SERVER_URL=http://127.0.0.1:5000
cd /d "%~dp0.."
echo.
echo Stratus Dev session refresh
echo Server: %SERVER_URL%
echo.
.venv\Scripts\python connect_sessions.py --platform stratus --environment dev --server %SERVER_URL%
echo.
pause
