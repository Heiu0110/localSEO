@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 scripts\backend.py --run
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Install Python 3.11 or newer and enable Add Python to PATH.
    pause
    exit /b 1
  )
  python scripts\backend.py --run
)
if errorlevel 1 (
  echo Backend could not start. Check the error above.
  pause
  exit /b 1
)
