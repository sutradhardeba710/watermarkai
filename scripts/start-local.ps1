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
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        return $async.AsyncWaitHandle.WaitOne(1000) -and $client.Connected
    }
    finally {
        $client.Dispose()
    }
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

if (-not (Test-LocalPort 5432)) {
    & $postgresCtl -D $postgresData -l 'F:\vw\pgsql\logfile' start | Out-Host
}
if (-not (Test-LocalPort 6379)) {
    Start-Process -FilePath $redisServer -ArgumentList $redisConfig -WorkingDirectory 'F:\vw\redis' -WindowStyle Hidden | Out-Null
    Write-Host 'Started redis.'
}

# Run from the repository root so sibling packages such as workers are on sys.path.
# --app-dir keeps the FastAPI app package importable.
Start-LoggedProcess 'backend' $backendPython @('-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--reload', '--port', '8000') $repoRoot
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
