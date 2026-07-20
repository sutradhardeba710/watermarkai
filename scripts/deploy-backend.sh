#!/usr/bin/env bash
# Deploy the backend API, frontend, and reverse proxy on the production EC2 host.
# This script is intentionally run on the EC2 instance by a self-hosted GitHub
# Actions runner so production secrets remain on the server.
set -euo pipefail

PROJECT_DIR="/home/ubuntu/watermarkai"
EXPECTED_SHA="${1:-}"
LOCK_FILE="/tmp/vwa-production-deploy.lock"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Another backend deployment is already running."
  exit 1
fi

cd "$PROJECT_DIR"

if [[ ! -f backend/.env.production ]]; then
  echo "Missing backend/.env.production; refusing deployment."
  exit 1
fi

# ── Preserve the server-side production secrets across the pull ────────────────
# backend/.env.production lives only on this host (it is git-ignored and must
# never be committed). A pull that changes or removes the tracked copy would
# otherwise clobber the real secrets, so back them up and restore afterwards.
ENV_BACKUP="$(mktemp)"
cp backend/.env.production "$ENV_BACKUP"
trap 'rm -f "$ENV_BACKUP"' EXIT

git fetch --prune origin
git checkout main
# Drop any working-tree state for the secrets file so an ff-only pull can never
# be blocked (or the file deleted) by it; we restore the real file immediately.
git checkout -- backend/.env.production 2>/dev/null || true
git pull --ff-only origin main
cp "$ENV_BACKUP" backend/.env.production

if [[ -n "$EXPECTED_SHA" ]] && [[ "$(git rev-parse HEAD)" != "$EXPECTED_SHA" ]]; then
  echo "Expected commit $EXPECTED_SHA but EC2 is at $(git rev-parse HEAD)."
  exit 1
fi

COMPOSE=(docker compose -f docker-compose.prod.yml)
if [[ -f docker-compose.local.yml ]]; then
  COMPOSE+=(-f docker-compose.local.yml)
fi
# The tracked production stack uses profiles for the API and worker services.
# Activating them is harmless for compose files that do not define profiles.
COMPOSE+=(--profile api --profile worker)

"${COMPOSE[@]}" config >/dev/null
"${COMPOSE[@]}" build backend frontend
"${COMPOSE[@]}" run --rm backend python -m alembic -c alembic.ini upgrade head
"${COMPOSE[@]}" up -d --no-deps --force-recreate backend frontend
# Force-recreate caddy so it re-reads the bind-mounted Caddyfile. A plain
# `up -d caddy` is a no-op when only the mounted config changed, leaving the
# old reverse-proxy config (e.g. HTTP-only) running.
"${COMPOSE[@]}" up -d --no-deps --force-recreate caddy

# Health-check the containers directly over the Docker network. We no longer
# probe http://localhost through Caddy because Caddy now answers only for the
# configured domain (a Host: localhost request would not match and would fail
# even when the app is healthy). The backend image has curl available.
for attempt in {1..18}; do
  if "${COMPOSE[@]}" exec -T backend curl -fsS http://localhost:8000/health >/dev/null 2>&1 \
     && "${COMPOSE[@]}" exec -T backend curl -fsS http://frontend:3000/ >/dev/null 2>&1; then
    echo "Production stack deployment succeeded: $(git rev-parse --short HEAD)"
    exit 0
  fi
  sleep 5
done

echo "Backend or frontend health check failed after deployment."
"${COMPOSE[@]}" logs --tail=100 backend frontend caddy
exit 1
