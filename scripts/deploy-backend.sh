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

git fetch --prune origin
git checkout main
git pull --ff-only origin main

if [[ -n "$EXPECTED_SHA" ]] && [[ "$(git rev-parse HEAD)" != "$EXPECTED_SHA" ]]; then
  echo "Expected commit $EXPECTED_SHA but EC2 is at $(git rev-parse HEAD)."
  exit 1
fi

COMPOSE=(docker compose -f docker-compose.prod.yml)

"${COMPOSE[@]}" config >/dev/null
"${COMPOSE[@]}" build backend frontend
"${COMPOSE[@]}" run --rm backend python -m alembic -c alembic.ini upgrade head
"${COMPOSE[@]}" up -d --no-deps --force-recreate backend frontend
"${COMPOSE[@]}" up -d caddy

for attempt in {1..18}; do
  if curl -fsS http://localhost/health >/dev/null && curl -fsS http://localhost/ >/dev/null; then
    echo "Production stack deployment succeeded: $(git rev-parse --short HEAD)"
    exit 0
  fi
  sleep 5
done

echo "Backend or frontend health check failed after deployment."
"${COMPOSE[@]}" logs --tail=100 backend frontend caddy
exit 1
