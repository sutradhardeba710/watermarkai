# Backend agent runbook

Scoped to `backend/` (and the `workers/` code it shares `app/` with) — production
operations on the EC2 host, not local dev. For local dev topology see the
root-level [AGENTS.md](../AGENTS.md). For architecture reference see
[BACKEND_DETAILS.md](BACKEND_DETAILS.md); for the change history see
[PROJECT_UPDATE.md](PROJECT_UPDATE.md).

## Before editing backend code

1. Read [BACKEND_DETAILS.md](BACKEND_DETAILS.md) for the area you're touching —
   in particular the **storage abstraction** and **signed media token**
   sections if you're touching `api/preview.py`, `api/files.py`,
   `api/projects.py`, or anything under `storage/`. Getting the
   `mint_signed_token` vs `storage.signed_download_url` distinction wrong is
   the single most common source of prod-only bugs here (it doesn't show up
   under the `local` storage backend, only `minio`/S3).
2. Check the tail of [PROJECT_UPDATE.md](PROJECT_UPDATE.md) for recent
   incidents in the area — don't reintroduce something just fixed.
3. Run the test suite before making changes, so you know the baseline is
   green:
   ```bash
   cd backend
   .venv/Scripts/python.exe -m pytest tests/
   ```

## While editing

- Never commit `backend/.env.production` or print its secret values (DB
  password, S3/MinIO keys, JWT secret) anywhere — mask as `***`.
- If a change touches `app/` and workers import from it (most of `app/`
  does), remember the automated deploy pipeline **does not rebuild the
  worker/beat images** — see [BACKEND_DETAILS.md](BACKEND_DETAILS.md#docker-image-staleness--the-recurring-failure-mode).
  A manual rebuild on the EC2 host is required for those changes to take
  effect for Celery tasks.
- Keep the full test suite green (`pytest tests/`) before pushing.

## After making a change / fixing a bug

1. Re-run the full test suite and confirm the pass/skip counts.
2. Commit with a clear message; push to `main` triggers the self-hosted
   Actions runner deploy (`backend`, `frontend`, `caddy` only — see
   [BACKEND_DETAILS.md](BACKEND_DETAILS.md#deploy-pipeline)).
3. Verify the deploy: `gh run list` / `gh run view --json status,jobs`.
4. If the change touched `app/` or `workers/` in a way Celery tasks depend
   on, manually rebuild and recreate `worker`/`beat` on the EC2 host (see
   [BACKEND_DETAILS.md](BACKEND_DETAILS.md#docker-image-staleness--the-recurring-failure-mode)) —
   the CI pipeline will not do this for you.
5. **Add an entry to [PROJECT_UPDATE.md](PROJECT_UPDATE.md)** — symptom, root
   cause, fix, commit hash, deploy verification, and any outstanding
   follow-up. Newest entry goes at the top.
6. If the change altered architecture, the storage backend, the deploy
   pipeline, or introduced a new operational gotcha, update
   [BACKEND_DETAILS.md](BACKEND_DETAILS.md) too, not just the changelog.
