[CmdletBinding()]
param(
    [switch]$NoWorker
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repoRoot '.run-logs'
$postgresCtl = 'F:\vw\pgsql\bin\pg_ctl.exe'
$postgresData = 'F:\vw\pgsql\data'
$redisServer = 'F:\vw\redis\redis-server.exe'
$redisConfig = 'F:\vw\redis\redis.windows.conf'
$backendPython = Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Test-LocalPort([int]$Port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Wait-LocalPort([int]$Port, [int]$TimeoutSeconds = 15) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-LocalPort $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Start-LoggedProcess([string]$Name, [string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory) {
    $port = switch ($Name) {
        'frontend' { 3000 }
        'backend' { 8000 }
        default { 0 }
    }
    if ($port -and (Test-LocalPort $port)) {
        Write-Host "$Name is already running."
        return
    }

    $output = Join-Path $logDir "$Name.log"
    $error = Join-Path $logDir "$Name-error.log"
    Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -RedirectStandardOutput $output -RedirectStandardError $error | Out-Null
    Write-Host "Started $Name."
}

if (-not (Test-Path $postgresCtl) -or -not (Test-Path $postgresData)) { throw 'PostgreSQL was not found at F:\vw\pgsql.' }
if (-not (Test-Path $redisServer) -or -not (Test-Path $redisConfig)) { throw 'Redis was not found at F:\vw\redis.' }
if (-not (Test-Path $backendPython)) { throw 'Backend virtual environment is missing. Run scripts\setup.ps1 first.' }

& $postgresCtl -D $postgresData status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Starting PostgreSQL...'
    & $postgresCtl -D $postgresData -l 'F:\vw\pgsql\logfile' start | Out-Host
    if (-not (Wait-LocalPort 5432)) { throw 'PostgreSQL did not become ready on port 5432.' }
}
else {
    Write-Host 'PostgreSQL is already running.'
}
if (-not (Test-LocalPort 6379)) {
    # Redis' config sets `logfile ""` (stdout), which is discarded when the
    # process is started hidden — so a Redis that dies leaves no trace and the
    # whole pipeline silently runs with no broker (Approve -> 500, jobs stuck at
    # "Queued 0%"). Redirect its output to a log so crashes are diagnosable, and
    # re-check the port so we fail loudly if it did not stay up.
    $redisLog = Join-Path $logDir 'redis.log'
    $redisErr = Join-Path $logDir 'redis-error.log'
    Start-Process -FilePath $redisServer -ArgumentList $redisConfig -WorkingDirectory 'F:\vw\redis' -WindowStyle Hidden -RedirectStandardOutput $redisLog -RedirectStandardError $redisErr | Out-Null
    if (-not (Wait-LocalPort 6379)) { throw "Redis did not become ready on port 6379. See $redisLog." }
    Write-Host 'Started Redis.'
}
else {
    Write-Host 'Redis is already running.'
}

# Run from the repository root so sibling packages such as workers are on sys.path.
# --app-dir keeps the FastAPI app package importable.
# NOTE: --reload is intentionally omitted. This project lives inside a OneDrive
# folder whose background sync constantly touches files; uvicorn's file watcher
# treats every sync as a code change and reload-loops until the worker dies with
# a KeyboardInterrupt, leaving port 8000 empty (the frontend proxy then returns
# 500 on /api/v1/auth/login). Restart this script after backend code changes.
Start-LoggedProcess 'backend' $backendPython @('-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--port', '8000') $repoRoot
Start-LoggedProcess 'frontend' 'cmd.exe' @('/c', 'npm run dev') (Join-Path $repoRoot 'frontend')

if (-not $NoWorker) {
    $workerLog = Join-Path $logDir 'worker.log'
    $workerError = Join-Path $logDir 'worker-error.log'
    $workerAlreadyRunning = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -match 'celery.*workers.celery_app' }
    if ($workerAlreadyRunning) {
        Write-Host 'worker is already running.'
    }
    else {
        Start-Process -FilePath $backendPython -ArgumentList @('-m', 'celery', '-A', 'workers.celery_app', 'worker', '-Q', 'detection,processing,encoding', '--pool=solo', '-l', 'info') -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $workerLog -RedirectStandardError $workerError | Out-Null
        Write-Host 'Started worker.'
    }
}

Write-Host 'Services are launching. Verify: http://localhost:3000 and http://localhost:8000/health'
