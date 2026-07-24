# ClearFrame Backend — Details

Reference doc for the FastAPI backend: structure, storage, workers, deploy
pipeline, and operational gotchas discovered in production. Companion to
[AGENTS.md](AGENTS.md) (the workflow to follow before/after editing this
backend), [PROJECT_UPDATE.md](PROJECT_UPDATE.md) (the changelog), and the
root-level [PROGRESS.md](../PROGRESS.md) (full feature-build history).

## Stack

- **API**: FastAPI (`backend/app/main.py`), SQLAlchemy + PostgreSQL, Alembic migrations.
- **Async work**: Celery workers (`workers/`), queues `detection`, `processing`, `encoding`, plus `celery beat` for scheduled maintenance.
- **Storage**: pluggable — local disk or MinIO/S3, selected by `VWA_STORAGE_BACKEND` env var (see below).
- **Frontend**: Next.js (`frontend/`), served behind Caddy as reverse proxy.
- **Auth**: JWT access tokens (`app/core/security.py`, `app/auth/dependencies.py`).
- **Prod host**: single EC2 instance, all services via Docker Compose, a self-hosted GitHub Actions runner auto-deploys on push to `main`.

## Backend app layout (`backend/app/`)

| Dir | Purpose |
|---|---|
| `api/` | Route modules: `auth`, `uploads`, `projects`, `masks`, `processing`, `preview`, `detection`, `files`, `payments`, `admin`, `health` |
| `auth/` | `dependencies.py` — `get_current_user`, bearer/scheme parsing |
| `core/` | `config.py` (settings/env), `db.py`, `security.py` (JWT), `errors.py`/`error_handlers.py` (`AppError` → HTTP mapping), `tokens.py`, `maintenance.py` |
| `models/` | SQLAlchemy models (`VideoProject`, `User`, `ProcessingJob`, `WatermarkMask`, `ComplianceConfirmation`, etc.) |
| `repositories/` | DB query helpers per domain (`uploads`, `processing`, `candidates`, `admin`) |
| `schemas/` | Pydantic request/response models |
| `services/` | Business logic (`encode.py`, `compliance.py`, `validation.py`, `payment_service.py`, `admin_service.py`, …) |
| `storage/` | Storage abstraction — see below |

## Storage abstraction

`app/storage/factory.py` picks the backend from `settings.storage_backend` (env `VWA_STORAGE_BACKEND`, default `local`):

- `local` → `LocalFsStorage` (`app/storage/local_fs.py`) — files under `settings.storage_local_path` (container path `/app/.storage`, backed by the `storage` named Docker volume).
- `minio` → `MinioStorage` (`app/storage/minio.py`) — real S3/MinIO via `minio` Python client. One physical bucket (`minio_bucket_prefix`), logical buckets (`proxies`, `thumbnails`, `previews`, `outputs`, `inputs`, …) are just key prefixes (`_full_key` → `f"{bucket}/{key}"`).

**Production is on `minio` pointed at a real AWS S3 bucket** (`vwa-media-watermarkai-2026`), not local disk. All pre-existing local-volume objects were migrated into that bucket in this session (see [PROJECT_UPDATE.md](PROJECT_UPDATE.md)).

### Signed media tokens — critical invariant

The app streams media through its own routes rather than redirecting browsers to storage directly:

- `GET /projects/{id}/proxy`, `/thumbnail` (`api/files.py`)
- `GET /projects/{id}/preview-clip`, `/output` (`api/preview.py`)

These routes call `storage.get()` / `FileResponse` and authenticate the request via a `?token=` query param — a short-lived **app-minted HS256 JWT** (`{bucket, key, exp}`), because raw `<video src>`/`<img src>` elements can't attach an `Authorization` header.

**That token must always come from `app.storage.local_fs.mint_signed_token(bucket, key, expires_seconds)`, never from `storage.signed_download_url(...)`.** The two look similar but are not interchangeable:

- `LocalFsStorage.signed_download_url()` happens to return `f"token:{mint_signed_token(...)}"` — same JWT, so using it "worked" under the `local` backend.
- `MinioStorage.signed_download_url()` returns a **real S3 presigned URL** (`presigned_get_object`). If that gets forwarded to an app route as `?token=`, `parse_signed_token` can't JWT-decode it and the request 403s (this shipped as a production bug — see [PROJECT_UPDATE.md](PROJECT_UPDATE.md)).

Rule of thumb: `mint_signed_token` / `parse_signed_token` is the **app's own auth scheme** for its same-origin streaming routes. `storage.signed_download_url()` is a **backend-specific direct-to-storage URL** and should only be used where the caller will fetch straight from the storage backend itself (currently nothing in this codebase does that end-to-end — if you add such a feature, remember it will produce a real S3 URL only on `minio`, and a `token:`-prefixed app URL on `local`).

## Celery workers

- `workers/celery_app.py` — Celery app + queue config.
- `workers/tasks/{detection,processing,maintenance}.py` — task entrypoints.
- `workers/{detection,encoding,inpainting,tracking}/` — the actual CV/ML pipeline modules.
- Queues: `detection`, `processing`, `encoding` (all consumed by one `worker` container, `--concurrency=2`); `beat` runs scheduled jobs (retention cleanup, stale-job sweep) on its own container.

### Docker image freshness

`docker-compose.worker.yml` bind-mounts `workers/` from the host (always fresh on `git pull`), but **`app/` (the whole FastAPI package the workers import from, e.g. `app.services.encode`) is baked into the image at build time.** If backend code under `app/` changes but the worker image isn't rebuilt, the worker/beat containers run stale code — this has caused a production `AttributeError` for a function (`transcode_audio_aac_args`) that existed in the repo but not in the running image.

The automated deploy pipeline (`.github/workflows/deploy-backend.yml` → `scripts/deploy-backend.sh`) rebuilds and recreates `worker`/`beat` on every deployment, including changes under `app/` or `workers/`. It then requires a successful Celery ping and a running Beat container before reporting success. For manual recovery, use:

```bash
docker compose -f docker-compose.worker.yml build worker
docker compose -f docker-compose.worker.yml up -d --no-deps --force-recreate worker beat
```

(`beat` uses the same image as `worker` — re-tag/rebuild together.)

## Email / SMTP

Transactional email (account lifecycle) is sent **asynchronously via Celery** so a slow or unreachable SMTP server never blocks an API request.

- **`app/services/email_service.py`** — the single email entrypoint.
  - `render_email(template_name, context)` → `(subject, html, text)`. Subjects are a dict in this module; bodies are Jinja2 `.html.jinja` / `.txt.jinja` pairs under `app/templates/email/` (multipart/alternative — HTML + plaintext fallback for better inbox/spam handling). `base.html.jinja` holds the branded layout; each template `extends` it.
  - `queue_email(to, template_name, context)` — called by API/service code. Hands off to the Celery task through the resilient `dispatch_task(...)` publisher on the **`processing`** queue. **Never raises**: a notification that fails to enqueue must not turn a successful register/reset into a 500 (it logs and swallows `BrokerUnavailable` and any other error).
  - `_deliver_smtp(to, subject, html, text)` — the actual network send; **only ever runs in the worker process**. When `VWA_SMTP_CONSOLE=true` (dev default) it prints the message instead of connecting.
- **`workers/tasks/notifications.py`** — `send_email` task (`bind=True, max_retries=3, queue="processing"`). Renders + delivers; drops unknown templates, retries transient SMTP failures with backoff. Registered in `workers/celery_app.py` `include=[...]` and routed to `processing` in `task_routes`.
- **Events wired** (`auth_service` / `account_service`): `welcome_verify` (register), `email_verified` (verify), `password_reset` (forgot-password), `password_changed` (change-password), `account_deleted` (delete-account). Login alerts and "video ready" are intentionally out of scope.
- **Config** (`Settings`, prefix `VWA_`): `smtp_console` (default `true`), `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`, `app_base_url` (used to build `verify_url` / `reset_url`). See `.env.example`.
- **Gmail production setup**: `VWA_SMTP_HOST=smtp.gmail.com`, `VWA_SMTP_PORT=587` (STARTTLS), `VWA_SMTP_USER=<address>`, `VWA_SMTP_PASSWORD=<16-char Google App Password>` (requires 2-Step Verification; **not** the account password), `VWA_SMTP_FROM` must equal the authenticated address, `VWA_SMTP_CONSOLE=false`. The App Password is a secret — mask as `***`, never commit it.
- **Deploy behavior**: the `send_email` task lives under `workers/` and imports `email_service` from `app/`; automated deployments rebuild and recreate `worker`/`beat` so email code cannot remain stale.

## Deploy pipeline

- Trigger: push to `main` touching `backend/**`, `workers/**`, `ai-models/**`, `frontend/**`, `Caddyfile`, `Dockerfile`, `docker-compose.prod.yml`, `docker-compose.local.yml`, or the workflow/script itself.
- Runner: self-hosted GitHub Actions runner on the EC2 host itself (service `actions.runner.*-watermarkai.*.service`), working directory `/home/ubuntu/watermarkai`.
- Flow (`deploy-backend.sh`):
  1. Back up `backend/.env.production` (git-ignored, prod-only secrets) to a temp file.
  2. `git fetch` + hard-reset workflow step syncs the tree to the pushed commit, preserving/restoring the live secrets file around the reset.
  3. `git pull --ff-only origin main`, restore `.env.production`.
  4. Verify `HEAD` matches the expected commit SHA.
  5. Build `backend`/`frontend` from `docker-compose.prod.yml` and `worker`/`beat` from `docker-compose.worker.yml`.
  6. Run Alembic migrations (`upgrade head`) via a throwaway `backend` container.
  7. Recreate `backend`, `frontend`, `worker`, `beat`, then `caddy` (force-recreated separately so it reliably re-reads the bind-mounted Caddyfile).
  8. Health-check backend/frontend over the Docker network, require a successful Celery worker ping, and require Beat to be running, with up to 18 retries (5s apart).
- A `flock` on `/tmp/vwa-production-deploy.lock` prevents concurrent deploy runs.
- All long-running containers use `restart: unless-stopped`, so Docker restores the stack after an EC2 reboot. The self-hosted Actions runner is managed by systemd and resumes GitHub-triggered deployments after boot.

## Admin system-health monitoring

`GET /api/v1/admin/system-health` performs bounded, admin-only dependency
checks for frontend, backend, PostgreSQL, Redis, Celery/processing workers,
object storage, Razorpay, SMTP email, and app-signed media tokens.

- Frontend and backend use HTTP probes; workers require Redis heartbeats no
  older than 60 seconds.
- Object storage performs a cached write/read/delete round trip against the
  configured backend, so S3 credentials and I/O are tested rather than merely
  checking configuration.
- Razorpay validates the configured credentials with a read-only Plans request.
  SMTP connects, upgrades with STARTTLS, and authenticates without sending mail.
- External and storage probes are cached for five minutes and run concurrently;
  the admin page may poll every 30 seconds without repeatedly hitting providers.
- `RequestIdMiddleware` records API response time and 5xx counts after the
  response is sent. Per-minute Redis hashes aggregate a rolling five-minute
  window across all four Uvicorn workers.
- Metrics also include PostgreSQL connection utilization and latency, Redis
  memory, queue depth, stale worker count, and one-hour webhook/email probe
  failures. The board refreshes every 30 seconds and reports the check time.
## Production environment

- Prod env file: `backend/.env.production` on the EC2 host (git-ignored — never committed; `.bak-local-<timestamp>` backups are made before any manual edit).
- Key vars: `VWA_STORAGE_BACKEND` (`local` | `minio`), `MINIO_*` / S3 credentials, `SECRET_KEY` (JWT signing — shared by `mint_signed_token`/`parse_signed_token`), DB connection string, Celery broker/result backend (Redis).
- **Never** print raw secret values (DB passwords, S3 keys, JWT secret) in logs, docs, or chat — always mask as `***` when referencing them.

## Known operational gotchas (learned in production)

1. **Worker health** — deployments rebuild/recreate worker/beat and fail unless the worker answers a Celery ping. If the worker is absent after a reboot, verify Docker and the self-hosted Actions runner systemd services are enabled.
2. **EC2 disk exhaustion** — `docker compose build` can fail with `No space left on device` once Docker's build cache + old image layers accumulate (observed at 91% disk usage, recurring after each manual worker rebuild). Fix: `docker builder prune -af && docker image prune -af` — safe, only removes unused/dangling layers, does not affect images backing currently-running containers. Re-run the failed step/workflow afterward (`gh run rerun <id> --failed`).
3. **Storage backend must match intent** — `VWA_STORAGE_BACKEND` can silently drift from `minio` to `local` (or vice versa) across env-file edits. If S3 credentials are present but uploads keep landing in the local `storage` volume, check this var directly rather than assuming.
4. **Signed-token backend independence** — see "Signed media tokens" above; this is the single most important invariant to preserve when touching `preview.py`, `files.py`, or `projects.py`'s `_attach_signed_media_urls`.

## Tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/
```

459 passed, 12 skipped as of 2026-07-21 (commit `87a97d9`). Keep this green before every push — the deploy pipeline does not run the test suite itself, so a red suite locally means a red suite in prod.
