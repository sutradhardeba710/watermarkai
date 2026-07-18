#!/usr/bin/env bash
# Deploy backend/API, Celery worker, and Celery beat on the production EC2 host.
# This script is intentionally run on the EC2 instance by a self-hosted GitHub
# Actions runner so production secrets remain on the server.
set -euo pipefail

PROJECT_DIR="/home/ubuntu/watermarkai"
EXPECTED_SHA="${1:-}"
LOCK_FILE="/tmp/vwa-backend-deploy.lock"

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

COMPOSE=(docker compose -f docker-compose.prod.yml -f docker-compose.local.yml --profile api --profile worker)

"${COMPOSE[@]}" config >/dev/null
"${COMPOSE[@]}" build backend worker beat
"${COMPOSE[@]}" run --rm backend python -m alembic -c alembic.ini upgrade head
"${COMPOSE[@]}" up -d --no-deps --force-recreate backend worker beat

for attempt in {1..18}; do
  if curl -fsS http://localhost/health >/dev/null; then
    echo "Backend deployment succeeded: $(git rev-parse --short HEAD)"
    exit 0
  fi
  sleep 5
done

echo "Backend health check failed after deployment."
"${COMPOSE[@]}" logs --tail=100 backend worker beat
exit 1
