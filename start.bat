@echo off
cd /d "%~dp0"
title Montage Studio
if not exist ".venv\Scripts\python.exe" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo The interface is not built yet. Run setup.bat first.
  pause
  exit /b 1
)
echo Montage Studio is running at http://127.0.0.1:8765
echo Keep this window open while you work. Close it to stop the app.
echo.
cd backend
"..\.venv\Scripts\python.exe" run.py
pause
