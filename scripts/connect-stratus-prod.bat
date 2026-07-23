@echo off
REM Double-click to refresh Stratus Production session on the server.
REM Edit SERVER_URL if the app is not on this PC.
set SERVER_URL=http://127.0.0.1:5000
cd /d "%~dp0.."
echo.
echo Stratus session refresh
echo Server: %SERVER_URL%
echo.
echo A browser will open. Sign in to Stratus, then this window continues automatically.
echo.
.venv\Scripts\python connect_sessions.py --platform stratus --environment prod --server %SERVER_URL%
echo.
pause
