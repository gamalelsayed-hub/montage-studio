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
  if errorlevel 1 goto :manual_install
  set NEED_RESTART=1
) else (
  echo [1/3] Python found.
)

where node >nul 2>nul
if errorlevel 1 (
  echo [2/3] Installing Node.js LTS ...
  winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :manual_install
  set NEED_RESTART=1
) else (
  echo [2/3] Node.js found.
)

rem ffmpeg goes inside this folder (tools\ffmpeg), so no restart is needed for it
if exist "%~dp0tools\ffmpeg\bin\ffmpeg.exe" set "PATH=%~dp0tools\ffmpeg\bin;%PATH%"
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [3/3] Downloading ffmpeg into the tools folder ...
  call :get_ffmpeg
  if errorlevel 1 goto :ffmpeg_failed
  echo ffmpeg is ready.
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

rem NVIDIA libraries (about 1.3 GB) are only needed when there is an NVIDIA card
where nvidia-smi >nul 2>nul
if errorlevel 1 (
  echo No NVIDIA graphics card found: transcription will run on the processor.
) else (
  echo Installing NVIDIA libraries for fast transcription on the graphics card ...
  ".venv\Scripts\python.exe" -m pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
  if errorlevel 1 echo Skipped: transcription will use the processor instead. That is OK, just slower.
)

echo Building the interface ...
pushd backend
"..\.venv\Scripts\python.exe" -m montage.updater
if errorlevel 1 (popd & goto :error)
popd

echo Creating the Desktop icon ...
call make_shortcut.bat

echo.
echo ================================================
echo   Done! Open the app from the "Montage Studio"
echo   icon on your Desktop (or double-click start.bat).
echo ================================================
pause
exit /b 0

:get_ffmpeg
if not exist tools mkdir tools
if exist tools\ffmpeg.zip del tools\ffmpeg.zip
rem --ssl-no-revoke avoids the certificate revocation error some networks and antivirus programs cause
curl.exe -f -L --ssl-no-revoke --retry 3 -o tools\ffmpeg.zip https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
if errorlevel 1 curl.exe -f -L --ssl-no-revoke --retry 3 -o tools\ffmpeg.zip https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip
if errorlevel 1 exit /b 1
if exist tools\ffmpeg rmdir /s /q tools\ffmpeg
tar -xf tools\ffmpeg.zip -C tools
if errorlevel 1 exit /b 1
for /d %%d in (tools\ffmpeg-*) do move "%%d" tools\ffmpeg >nul
del tools\ffmpeg.zip
if not exist tools\ffmpeg\bin\ffmpeg.exe exit /b 1
set "PATH=%~dp0tools\ffmpeg\bin;%PATH%"
exit /b 0

:ffmpeg_failed
echo.
echo *** Could not download ffmpeg. ***
echo Check the internet connection, or pause the antivirus for a minute, then run setup.bat again.
echo (Manual way: see "ffmpeg" in README.md)
pause
exit /b 1

:manual_install
echo.
echo *** Automatic install failed. ***
echo Install it by hand from the link in README.md, then run setup.bat again.
pause
exit /b 1

:error
echo.
echo *** Something went wrong. Take a screenshot of this window and send it to Claude. ***
pause
exit /b 1
