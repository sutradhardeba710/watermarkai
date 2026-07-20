@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Video Watermark AI - local launcher
REM  Starts: PostgreSQL, Redis, Backend (uvicorn), Worker (celery+beat),
REM          Frontend (npm dev)
REM  Each service runs in its OWN visible window so crashes stay on
REM  screen. Re-running is safe: services already up are skipped.
REM
REM  NOTE: this project path contains parentheses ("New folder (2)"),
REM  which break %VAR% expansion inside if-blocks. All variables are
REM  therefore referenced with delayed expansion (!VAR!).
REM ============================================================

set "PROJECT_ROOT=%~dp0"
set "LOG_DIR=%PROJECT_ROOT%.run-logs"
set "PY=%PROJECT_ROOT%backend\.venv\Scripts\python.exe"

set "PG_CTL=F:\vw\pgsql\bin\pg_ctl.exe"
set "PG_DATA=F:\vw\pgsql\data"
set "PG_LOG=F:\vw\pgsql\logfile"
set "REDIS_EXE=F:\vw\redis\redis-server.exe"
set "REDIS_CONF=F:\vw\redis\redis.windows.conf"

if not exist "!LOG_DIR!" mkdir "!LOG_DIR!"

echo ============================================================
echo   Starting Video Watermark AI local services
echo ============================================================
echo.

REM --- sanity checks ---------------------------------------------------------
if not exist "!PY!" (
  echo [ERROR] Backend venv python not found: !PY!
  echo         Run scripts\setup.ps1 first to create the virtual environment.
  goto :fail
)
if not exist "!PROJECT_ROOT!frontend\node_modules" (
  echo [ERROR] frontend\node_modules missing.
  echo         Run:  cd frontend  then  npm install
  goto :fail
)
where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm is not on PATH. Install Node.js and reopen this window.
  goto :fail
)
if not exist "!PG_CTL!" (
  echo [ERROR] PostgreSQL not found: !PG_CTL!
  goto :fail
)
if not exist "!REDIS_EXE!" (
  echo [ERROR] Redis not found: !REDIS_EXE!
  goto :fail
)

REM --- PostgreSQL (5432) -----------------------------------------------------
call :is_up 5432
if "!PORT_UP!"=="1" (
  echo [ OK ] PostgreSQL already running on 5432
) else (
  echo [ .. ] Starting PostgreSQL...
  "!PG_CTL!" -D "!PG_DATA!" -l "!PG_LOG!" start >nul 2>nul
  call :wait_port 5432 20
  if "!PORT_UP!"=="1" (
    echo [ OK ] PostgreSQL is up
  ) else (
    echo [FAIL] PostgreSQL did not reach 5432 - check !PG_LOG!
    goto :fail
  )
)

REM --- Redis (6379) ----------------------------------------------------------
call :is_up 6379
if "!PORT_UP!"=="1" (
  echo [ OK ] Redis already running on 6379
) else (
  echo [ .. ] Starting Redis...
  start "VWA Redis" /min cmd /k ""!REDIS_EXE!" "!REDIS_CONF!""
  call :wait_port 6379 15
  if "!PORT_UP!"=="1" (
    echo [ OK ] Redis is up
  ) else (
    echo [FAIL] Redis did not reach 6379 - see the "VWA Redis" window
    goto :fail
  )
)

REM --- Backend / uvicorn (8000) ---------------------------------------------
REM  NOTE: --reload is intentionally omitted. This project lives in a OneDrive
REM  folder; the file watcher treats every sync touch as a code change and
REM  reload-loops. Re-run this file after backend code changes.
call :is_up 8000
if "!PORT_UP!"=="1" (
  echo [ OK ] Backend already running on 8000
) else (
  echo [ .. ] Starting Backend API...
  start "VWA Backend" cmd /k "cd /d "!PROJECT_ROOT!." && "!PY!" -m uvicorn app.main:app --app-dir backend --port 8000"
  call :wait_port 8000 40
  if "!PORT_UP!"=="1" (
    echo [ OK ] Backend is up
  ) else (
    echo [WARN] Backend not on 8000 yet - check the "VWA Backend" window for errors
  )
)

REM --- Celery worker + beat (no port; solo pool for Windows) ------------------
REM  -B embeds the beat scheduler so periodic jobs (credit reset, retention
REM  cleanup, metrics) run locally too. Detected via the "VWA Worker" window
REM  title so re-runs don't stack duplicate workers.
set "WORKER_UP=0"
for /f "tokens=*" %%L in ('tasklist /v ^| findstr /c:"VWA Worker"') do set "WORKER_UP=1"
if "!WORKER_UP!"=="1" (
  echo [ OK ] Worker already running
) else (
  echo [ .. ] Starting Worker...
  start "VWA Worker" cmd /k "cd /d "!PROJECT_ROOT!." && "!PY!" -m celery -A workers.celery_app worker -B -Q detection,processing,encoding --pool=solo -l info"
)

REM --- Frontend (3000) -------------------------------------------------------
call :is_up 3000
if "!PORT_UP!"=="1" (
  echo [ OK ] Frontend already running on 3000
) else (
  echo [ .. ] Starting Frontend...
  start "VWA Frontend" cmd /k "cd /d "!PROJECT_ROOT!frontend" && npm run dev"
  call :wait_port 3000 60
  if "!PORT_UP!"=="1" (
    echo [ OK ] Frontend is up
  ) else (
    echo [WARN] Frontend not on 3000 yet - check the "VWA Frontend" window
  )
)

REM --- Final health check ------------------------------------------------------
echo.
echo [ .. ] Checking API health...
powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 5; Write-Host '[ OK ] API health:' ($r | ConvertTo-Json -Compress) } catch { Write-Host '[WARN] API health check failed:' $_.Exception.Message }"

echo.
echo ============================================================
echo   Frontend : http://localhost:3000
echo   API      : http://localhost:8000/health
echo.
echo   Each service has its own window - close a window to stop
echo   that service. Re-running this file skips ones already up.
echo ============================================================
echo.
pause
exit /b 0

REM ==========================================================================
REM  Helpers
REM ==========================================================================

:is_up
REM  usage: call :is_up PORT  ->  sets PORT_UP to 1 or 0
set "PORT_UP=0"
for /f "tokens=*" %%L in ('netstat -ano ^| findstr /r /c:"LISTENING" ^| findstr /c:":%~1 "') do set "PORT_UP=1"
goto :eof

:wait_port
REM  usage: call :wait_port PORT TIMEOUT_SECONDS  ->  sets PORT_UP
set "_p=%~1"
set /a "_tries=%~2"
:wait_loop
call :is_up !_p!
if "!PORT_UP!"=="1" goto :eof
set /a "_tries-=1"
if !_tries! LEQ 0 goto :eof
timeout /t 1 /nobreak >nul
goto :wait_loop

:fail
echo.
echo Startup aborted. Fix the error above and run this file again.
echo.
pause
exit /b 1
