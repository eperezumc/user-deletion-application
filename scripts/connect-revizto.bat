@echo off
set SERVER_URL=http://127.0.0.1:5000
cd /d "%~dp0.."
echo.
echo Revizto session refresh
echo Server: %SERVER_URL%
echo.
echo A browser will open. Sign in to Revizto — this window waits until login finishes.
echo.
.venv\Scripts\python connect_sessions.py --platform revizto --server %SERVER_URL%
echo.
pause
