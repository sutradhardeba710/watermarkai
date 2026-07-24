## 2026-07-24 - Functional maintenance scheduling and public status experience

- **Symptom**: the public maintenance page looked unfinished, the real maintenance
  schedule could not be configured in the admin UI, and the separate switch in
  general settings did not control the API maintenance gate.
- **Root cause**: the operational maintenance setting is a dedicated persisted
  state, but the admin form omitted its start/end controls and general settings
  exposed an unrelated legacy configuration flag.
- **Fix**: consolidated maintenance control into the dedicated Operations page,
  added local-time schedule inputs and active-window feedback, removed the
  misleading duplicate switch, redesigned the public status screen with clear
  recovery details and live refresh, and added server validation for schedule
  order and public status URLs.
- **Tests**: full backend suite: 488 passed, 12 skipped; frontend typecheck and
  production build passed.
- **Commit / deployment verification**: `cc5f559` — GitHub Actions run
  `30076217170` completed successfully on the EC2 self-hosted runner. Public
  checks returned 200 for `/health`, `/health/maintenance`, and `/maintenance`.

---
# Backend Project Update Log

Living changelog for backend/production work on ClearFrame. Newest entries at
the top. See [AGENTS.md](AGENTS.md) for the workflow this log is part of
(check before editing, add an entry here after), [BACKEND_DETAILS.md](BACKEND_DETAILS.md)
for the architecture reference these entries assume, and the root
[PROGRESS.md](../PROGRESS.md) for the full feature-build history (Phases 1-9 +
Admin Panel).

---

## 2026-07-24 - Real EC2 system-health probes and rolling API telemetry

- **Symptom**: the admin System Health page showed Frontend, Celery, object
  storage, Razorpay, email, and signed URLs as `unknown`; most metric cards were
  blank and the overall state was permanently `Degraded` despite healthy EC2
  containers.
- **Root cause**: `/admin/system-health` only populated four checks. Redis was
  incorrectly inferred from worker-heartbeat presence, and no request,
  database, storage, webhook, email, or external-service telemetry was
  collected.
- **Fix**: added bounded live probes for all ten services, fresh worker
  heartbeat validation, S3 read/write cleanup checks, Razorpay and authenticated
  SMTP probes, signed-token round trips, PostgreSQL/Redis metrics, one-hour
  failure counts, and Redis-backed five-minute API latency/error telemetry
  shared by all Uvicorn workers. Probe results are cached for five minutes and
  API metric writes run as response background tasks.
- **UI**: service cards now show probe detail, metrics show units, and the board
  displays its last check time while continuing to refresh every 30 seconds.
- **Tests**: full backend suite: 486 passed, 12 skipped; production Next.js
  build passed.
- **Commit / deployment verification**: pending.

---
## 2026-07-23 � Promo discount type alignment

- **Symptom**: creating a percentage or flat promo code in the admin UI failed with `discount_type must be one of fixed, percentage, free_trial_extension, bonus_credits, first_cycle, multi_cycle`.
- **Root cause**: the form sent obsolete `percent` and `flat` values, while the API accepts canonical `percentage` and `fixed` values. Fixed promos were also not recognized by the checkout calculator.
- **Fix**: aligned the form and its value conversion with the API contract, and made checkout treat `fixed` promos as paise-denominated fixed discounts (while retaining compatibility with `fixed_amount`).
- **Tests**: `tests/test_admin_panel_phase4.py` � 27 passed; frontend `npm run typecheck` passed.
- **Commit / deployment verification**: pending.

---
## 2026-07-23 � Clear deleted-account login status

- **Symptom**: a user who had deleted their account saw the generic �Invalid email or password� message when attempting to sign in again.
- **Root cause**: the authentication service deliberately mapped deleted accounts to `INVALID_CREDENTIALS`, so the UI could not distinguish a confirmed deletion from bad credentials.
- **Fix**: authenticated password and Google sign-ins for deleted accounts now return `ACCOUNT_DELETED` (403); the login screen displays a clear, professional explanation and also shows it immediately after self-service deletion redirects to `?deleted=1`. Invalid passwords remain generic.
- **Tests**: `tests/test_google_auth.py` � 14 passed; frontend `npm run typecheck` passed.
- **Commit / deployment verification**: pending.

---
## 2026-07-23 — Automated worker deployment and EC2 restart recovery

- **Symptom**: registration verification and forgot-password emails were queued
  but never sent because production had no running `vwa-worker` container.
- **Root cause**: GitHub Actions rebuilt/recreated only backend, frontend, and
  Caddy. Worker/Beat used a separate Compose file and required a manual rebuild.
- **Fix**: the production deploy now validates both Compose configurations,
  rebuilds and recreates `worker`/`beat` on every deployment, requires a
  successful Celery ping plus a running Beat container, and includes worker logs
  in failed deployment diagnostics. Changes to `docker-compose.worker.yml` now
  trigger the GitHub workflow. All services retain `restart: unless-stopped` for
  automatic recovery after EC2/Docker restarts.
- **Commit**: `3d47168` — "Automate EC2 worker deployment and health checks".
- **Tests**: full backend suite green — 482 passed, 12 skipped.
- **Deployment verification**: pending push, GitHub Actions run, and live EC2
  smoke test.

---

## 2026-07-22 — Transactional email integration (Gmail SMTP, async via Celery)

Wired real account-lifecycle emails across the site. Previously auth used a
no-op `_send_email` stub; there was no way to actually deliver a verification or
reset link.

### What was added

- **`app/services/email_service.py`** (new) — `render_email` (Jinja2 templates →
  subject/html/text), `queue_email` (async hand-off, never raises), `_deliver_smtp`
  (worker-only SMTP send; console-prints when `VWA_SMTP_CONSOLE=true`).
- **`app/templates/email/`** (new, 11 files) — branded `base.html.jinja` +
  `.html.jinja`/`.txt.jinja` pairs for each of the 5 events (multipart/alternative).
- **`workers/tasks/notifications.py`** (new) — `send_email` Celery task
  (`queue="processing"`, `max_retries=3`, backoff); registered + routed in
  `workers/celery_app.py`.
- **Wiring** — `auth_service.register` → `welcome_verify` (with `verify_url`);
  `verify_email` → `email_verified`; `forgot_password` → `password_reset` (with
  `reset_url`); `account_service.change_password` → `password_changed`;
  `delete_account` → `account_deleted`. Old `_send_email` stub removed.
- **Config/docs** — `.env.example` gained a documented Email block (Gmail App
  Password, `smtp.gmail.com:587`, 2-Step Verification requirement); `jinja2>=3.1`
  pinned in `pyproject.toml`; Email/SMTP section added to
  [BACKEND_DETAILS.md](BACKEND_DETAILS.md#email--smtp).

### Design choices

- **Async, not inline**: `queue_email` publishes through the resilient
  `dispatch_task` on the `processing` queue so a slow/unreachable SMTP server
  never blocks (or fails) a register/reset request. It swallows
  `BrokerUnavailable` and any other error — a notification must never break its
  caller.
- **Scope**: verify, email-verified, password-reset, password-changed,
  account-deleted. Login alerts and "video ready" deliberately excluded.

### Tests

- `tests/test_email_phase10.py` (new, 10 tests): render for all 5 templates
  (context substitution + unknown-template `ValueError`), `queue_email` dispatches
  to the `processing` queue and swallows `BrokerUnavailable`, `_deliver_smtp`
  console branch (no network), and the `send_email` task's console path.
- `tests/conftest.py` now puts the repo root on `sys.path` so `workers` is
  importable (matches the Docker image layout).
- Full suite: **469 passed, 12 skipped** (was 459 baseline).

### Deploy / rollout (not yet done)

- After push, the **worker image must be manually rebuilt** on EC2 (`send_email`
  imports `app/`; CI won't rebuild `worker`/`beat`) — see the staleness rule.
- Production SMTP requires adding the user's own **Gmail App Password** to
  `backend/.env.production` and setting `VWA_SMTP_CONSOLE=false`. Keep the App
  Password masked (`***`); never commit `.env.production`.

---

## 2026-07-21 — Production incident response: preview/download errors on EC2

Three related production bugs surfaced back-to-back on the live Preview &
Approve screen (`65.0.179.69`) and were diagnosed/fixed/deployed the same day.

### 1. `FileNotFoundError` leaking raw `repr(exc)` to the frontend

- **Symptom**: Preview/Approve screen showed a raw Python exception string instead of a user-facing error.
- **Root cause**: `preview.py` / `processing.py` let a bare `FileNotFoundError` propagate and get `repr()`'d into the API error response, with no existence check before reading the source file.
- **Fix**: added `exists()` checks before reading source video files; raise `AppError("SOURCE_MISSING", ...)` with a clean message instead; `logger.exception` for server-side visibility.
- **Commit**: `b3d18f0` — "Fix FileNotFoundError leak in preview/processing; verify source exists"
- **Deploy**: pushed to `main`, CI run `29836411258` — `completed / success`. Verified live via grep on the deployed container (new error messages present; only remaining `repr(exc)` reference is an explanatory code comment, not live code).

### 2. `AttributeError: module 'app.services.encode' has no attribute 'transcode_audio_aac_args'`

- **Symptom**: Clicking "Approve and process full video" failed with this AttributeError, even though the function exists in `backend/app/services/encode.py` (used by `workers/tasks/processing.py`'s `_try_remux_audio`).
- **Root cause**: **stale `watermarkai-worker` Docker image** — the worker container bind-mounts `workers/` from the host but has `app/` baked in at build time, and the automated deploy pipeline never rebuilds `worker`/`beat` (see [BACKEND_DETAILS.md](BACKEND_DETAILS.md#docker-image-staleness--the-recurring-failure-mode)). The image predated the function's addition.
- **Fix**: manually rebuilt the worker image on the EC2 host:
  ```bash
  docker compose -f docker-compose.worker.yml -f docker-compose.workercode.yml build worker
  ```
  - Hit `No space left on device` mid-build (see disk-space note below); resolved with `docker builder prune -af` (reclaimed 10.4GB), then rebuild succeeded.
  - Re-tagged `watermarkai-beat:latest` from the new worker image, recreated both `worker` and `beat` containers.
  - Verified `hasattr(app.services.encode, "transcode_audio_aac_args")` → `True` inside the running image.

### 3. Storage backend mismatch — S3 was set up but not actually in use

- **User ask**: confirm production storage is really S3, not local disk.
- **Finding**: both `backend/.env.production` (on EC2) and its backup copy (`~/vwa-env-production.live`) had `VWA_STORAGE_BACKEND=local`, despite valid S3/MinIO credentials already being present in the same file.
- **Fix**:
  1. Backed up both env files (`.bak-local-<timestamp>`).
  2. Flipped `VWA_STORAGE_BACKEND` to `minio` in both via `sed -i`.
  3. Migrated all 28 pre-existing objects from the local `storage` Docker volume into the real S3 bucket `vwa-media-watermarkai-2026` — ran a one-off Python script inside the `vwa-backend` container that walked `/app/.storage` and uploaded any object not already present in the bucket.
  4. Recreated the `backend` container (`--no-deps --force-recreate`) to pick up the new env.
  5. Verified both `backend` and `worker` resolve `get_storage()` → `MinioStorage`.

### 4. `HTTP 403` on "Download cleaned video" (and black preview/proxy players)

- **Symptom**: After the S3 migration, clicking "Download cleaned video" returned `Download failed (HTTP 403)`.
- **Root cause**: `MinioStorage.signed_download_url()` returns a real S3 presigned URL (not the app's `token:<jwt>` scheme). The frontend forwarded that entire S3 URL as `?token=` to the app's own `/output` streaming route, which tried to JWT-decode it and failed → 403. The same bug affected `_attach_signed_media_urls` in `projects.py` (proxy/thumbnail/preview URLs), which would have produced black/broken media elements under the `minio` backend even though it "worked" under `local` (where `signed_download_url` happens to return the same JWT scheme).
- **Fix**: added `mint_signed_token(bucket, key, expires_seconds)` to `app/storage/local_fs.py` — a storage-backend-independent JWT minter. Switched:
  - `issue_download_url` in `api/preview.py`
  - all 4 call sites in `_attach_signed_media_urls` (`api/projects.py`) — `proxy_url`, `thumbnail_url`, `preview_url`, `before_preview_url`

  to call `mint_signed_token` directly instead of `storage.signed_download_url`. Removed the now-dead `_strip_scheme` helper (previously used to strip a `token:` prefix that only existed on the `local` backend).
- **Tests**: full suite green — 459 passed, 12 skipped.
- **Commit**: `87a97d9` — "Fix HTTP 403 on download/preview when storage backend is minio/S3"
- **Deploy**:
  - First attempt (CI run `29840398239`) **failed**: `System.IO.IOException: No space left on device` writing the Actions runner's own log — EC2 disk back up to 91% used (4.8GB free) after the earlier worker-image rebuild refilled Docker's build cache.
  - Resolved: SSH'd in, `docker builder prune -af` (reclaimed 10.17GB) + `docker image prune -af` (reclaimed 3.15GB) — confirmed all 7 containers stayed running throughout (prune only removes unused/dangling layers). Disk usage dropped from 91% → 59% (20GB free).
  - Re-ran the same workflow run: `gh run rerun 29840398239 --failed` → succeeded, `12m40s`, `completed / success`.
- **Verification status**: CI/CD deploy confirmed successful and the diagnostic (`hasattr`) checks passed server-side. **Not yet independently re-verified** by clicking "Download cleaned video" live in a browser post-deploy — recommended as a follow-up smoke test.

### Disk-space management note

Both the worker rebuild and the `87a97d9` deploy hit `No space left on device` from accumulated Docker build cache/image layers on the EC2 host. `docker builder prune -af` + `docker image prune -af` is the established, safe remedy (verified non-destructive to running containers both times). If this keeps recurring, consider adding a scheduled prune (e.g. a weekly cron) rather than firefighting it manually each time.

---

## How to add new entries

Append new dated sections above this line (or add a new top section, keeping
newest-first). For each incident/change, include: symptom, root cause, fix,
commit hash + message, deploy verification, and outstanding follow-ups. Always
mask secrets (`***`) in anything written here.
