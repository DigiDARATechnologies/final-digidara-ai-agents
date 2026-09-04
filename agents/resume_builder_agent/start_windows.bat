@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher was not found. Install Python 3.10 or newer.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Install Node.js 20 or newer.
  pause
  exit /b 1
)

if not exist "backend\.env" copy "backend\.env.example" "backend\.env" >nul
if not exist "frontend\.env" copy "frontend\.env.example" "frontend\.env" >nul
if not exist "backend\.venv\Scripts\python.exe" py -m venv "backend\.venv"

"backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto :failed

pushd "frontend"
call npm install
if errorlevel 1 goto :frontend_failed
popd

start "ResumeForge API" cmd /k "cd /d ""%~dp0backend"" && "".venv\Scripts\python.exe"" run.py"
start "ResumeForge UI" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
timeout /t 4 /nobreak >nul
start "" "http://localhost:5173"
exit /b 0

:frontend_failed
popd
:failed
echo Setup failed. Review the error above and retry.
pause
exit /b 1
