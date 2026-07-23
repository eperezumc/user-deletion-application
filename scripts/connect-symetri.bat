@echo off
set SERVER_URL=http://127.0.0.1:5000
cd /d "%~dp0.."
echo.
echo Symetri session refresh
echo Server: %SERVER_URL%
echo.
echo A browser will open. Sign in at my.symetri.com — this window waits until login finishes.
echo.
.venv\Scripts\python connect_sessions.py --platform symetri --server %SERVER_URL%
echo.
pause
