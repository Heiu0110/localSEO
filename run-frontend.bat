@echo off
setlocal
cd /d "%~dp0"
echo [Frontend] Checking installed dependencies. Valid installations are reused.
where node >nul 2>&1
if errorlevel 1 (
  echo Install Node.js 24 LTS with npm and reopen the terminal.
  pause
  exit /b 1
)
node scripts\frontend.mjs --run %*
set "FRONTEND_EXIT=%ERRORLEVEL%"
if not "%FRONTEND_EXIT%"=="0" (
  echo Frontend could not start. Check the error above.
  pause
  exit /b %FRONTEND_EXIT%
)
exit /b 0
