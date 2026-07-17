# Video Watermark AI — agent runbook

## Purpose

This is an authorized video-cleanup application. It supports registration and login,
video upload, ownership confirmation, manual masking, AI watermark detection, queued
video inpainting/encoding, progress streaming, preview/download, and admin/retention
operations. Do not weaken the ownership-confirmation or authorization controls.

## Local service topology

| Service | Address | Local installation |
| --- | --- | --- |
| Frontend (Next.js) | `http://localhost:3000` | `frontend/` |
| API (FastAPI) | `http://localhost:8000` | `backend/` |
| PostgreSQL | `localhost:5432` | `F:\\vw\\pgsql` |
| Redis / Celery broker | `localhost:6379` | `F:\\vw\\redis` |
| Local video storage | — | `F:\\vw\\storage` |
| Celery worker | detection, processing, encoding queues | `workers/` |

The backend `.env` is intentionally configured for the PostgreSQL, Redis, and storage
locations above. Keep credentials in `.env`; never copy them into documentation or logs.

## Start and verify

Run this from the repository root to start every required local service in the
background (including the Windows-safe Celery `solo` worker):

```powershell
.\scripts\start-local.ps1
```

Check that `http://localhost:3000`, `http://localhost:8000/health`, PostgreSQL, and
Redis all respond. Runtime logs are written to `.run-logs/`.

## Feature-to-service dependencies

| Feature | Requires |
| --- | --- |
| Landing page and static UI | Frontend |
| Login, users, dashboard, admin data | API + PostgreSQL |
| Upload and project metadata | API + PostgreSQL + `F:\\vw\\storage` |
| Detection, proxy generation, inpainting, encoding, downloads | API + PostgreSQL + Redis + Celery worker + FFmpeg |
| Live job progress | API + Redis + Celery worker |

## Development notes

- Use the backend virtual environment at `backend\\.venv`.
- On Windows the worker must use `--pool=solo`; the normal prefork pool can stall
  with the CV/ML dependencies.
- The health endpoint does not prove database or worker availability. Verify the
  service dependencies before diagnosing upload or processing failures.
- `F:\\vw\\test_video.mp4` is available for an authorized local smoke test.
