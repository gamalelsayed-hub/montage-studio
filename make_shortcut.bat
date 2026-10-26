@echo off
rem Creates a "Montage Studio" icon on the Desktop and in the Start menu.
rem The icon opens the app in its own window (no black window).
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Get-Location).Path;" ^
  "$shell = New-Object -ComObject WScript.Shell;" ^
  "$places = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'));" ^
  "foreach ($dir in $places) {" ^
  "  $link = $shell.CreateShortcut((Join-Path $dir 'Montage Studio.lnk'));" ^
  "  $link.TargetPath = (Join-Path $root '.venv\Scripts\pythonw.exe');" ^
  "  $link.Arguments = 'run.py --app';" ^
  "  $link.WorkingDirectory = (Join-Path $root 'backend');" ^
  "  $link.IconLocation = (Join-Path $root 'assets\icon.ico');" ^
  "  $link.Description = 'Montage Studio';" ^
  "  $link.Save()" ^
  "}"
if errorlevel 1 (
  echo Could not create the icon. Take a screenshot and send it to Claude.
  pause
  exit /b 1
)
echo The "Montage Studio" icon is now on your Desktop and in the Start menu.
