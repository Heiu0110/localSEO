@echo off
setlocal
cd /d "%~dp0"
echo [Frontend] Preparing startup. First-time dependency installation may take a few minutes.
where node >nul 2>&1
if errorlevel 1 (
  echo Install Node.js 24 LTS with npm and reopen the terminal.
  pause
  exit /b 1
)
node scripts\frontend.mjs --run
if errorlevel 1 (
  echo Frontend could not start. Check the error above.
  pause
  exit /b 1
)
