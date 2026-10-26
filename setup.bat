@echo off
setlocal
cd /d "%~dp0"
title Montage Studio - Setup
echo ================================================
echo   Montage Studio - first-time setup
echo ================================================
echo.

set NEED_RESTART=0

where python >nul 2>nul
if errorlevel 1 (
  echo [1/3] Installing Python 3.12 ...
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  set NEED_RESTART=1
) else (
  echo [1/3] Python found.
)

where node >nul 2>nul
if errorlevel 1 (
  echo [2/3] Installing Node.js LTS ...
  winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
  set NEED_RESTART=1
) else (
  echo [2/3] Node.js found.
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [3/3] Installing ffmpeg ...
  winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
  set NEED_RESTART=1
) else (
  echo [3/3] ffmpeg found.
)

if "%NEED_RESTART%"=="1" (
  echo.
  echo ------------------------------------------------
  echo  New programs were installed.
  echo  CLOSE this window and double-click setup.bat AGAIN.
  echo ------------------------------------------------
  pause
  exit /b 0
)

echo.
echo Creating Python environment (.venv) ...
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto :error
)

echo Installing Python packages (this can take a few minutes) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 goto :error

echo Installing NVIDIA libraries for fast transcription on the graphics card ...
".venv\Scripts\python.exe" -m pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
if errorlevel 1 echo (Skipped: transcription will use the CPU instead. That is OK, just slower.)

echo Building the interface ...
pushd frontend
call npm install
if errorlevel 1 (popd & goto :error)
call npm run build
if errorlevel 1 (popd & goto :error)
popd

echo.
echo ================================================
echo   Done! Double-click start.bat to open the app.
echo ================================================
pause
exit /b 0

:error
echo.
echo *** Something went wrong. Take a screenshot of this window and send it to Claude. ***
pause
exit /b 1
