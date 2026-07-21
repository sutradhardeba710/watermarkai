# AI Video Watermark Detection & Removal System — local setup (Windows PowerShell)
# Assumes: Python 3.11+, Node 20+, PostgreSQL, Redis, ffmpeg/ffprobe on PATH.
# Optional: `docker compose up -d postgres redis minio` for those services.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== Backend venv + deps =="
Push-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -e ".[dev]"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
Pop-Location

Write-Host "== Frontend deps =="
Push-Location "$root\frontend"
npm install
Pop-Location

Write-Host "== DB migrations =="
Push-Location "$root\backend"
& ".venv\Scripts\python.exe" -m alembic upgrade head
Pop-Location

Write-Host ""
Write-Host "Done."
Write-Host "  Backend :  backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000"
Write-Host "             (do NOT add --reload here: this repo lives in a OneDrive folder and"
Write-Host "              the synchronous /preview endpoint writes artifacts the watcher then"
Write-Host "              treats as code changes, restarting the server mid-request -> 500.)"
Write-Host "  Worker  :  backend\.venv\Scripts\python.exe -m celery -A workers.celery_app worker -Q detection,processing,encoding --pool=solo -l info"
Write-Host "  Frontend:  cd frontend; npm run dev   ->  http://localhost:3000"
