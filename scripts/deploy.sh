#!/usr/bin/env bash
# ─── VWA — server-side deploy script ─────────────────────────────────────────
# Run this on the EC2 instance to pull + rebuild + restart.
# Usage:
#   bash /opt/vwa/scripts/deploy.sh            # full redeploy
#   bash /opt/vwa/scripts/deploy.sh --no-pull  # rebuild without git pull
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="docker-compose.prod.yml"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   VWA Deploy — $TIMESTAMP   ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

cd "$PROJECT_DIR"

# ── 1. Pull latest code ───────────────────────────────────────────────────────
if [[ "${1:-}" != "--no-pull" ]]; then
    echo "→ Pulling latest code…"
    git pull --ff-only
fi

# ── 2. Validate env file exists ───────────────────────────────────────────────
if [[ ! -f backend/.env.production ]]; then
    echo "✗ ERROR: backend/.env.production not found."
    echo "  Copy backend/.env.example to backend/.env.production and fill in secrets."
    exit 1
fi

if grep -q "REPLACE_ME" backend/.env.production; then
    echo "✗ ERROR: backend/.env.production still contains REPLACE_ME placeholders."
    echo "  Run: bash scripts/generate-secrets.sh"
    exit 1
fi

# ── 3. Build Docker images ────────────────────────────────────────────────────
echo "→ Building Docker images…"
docker compose -f "$COMPOSE_FILE" build --parallel

# ── 4. Start infrastructure (postgres + redis) first ─────────────────────────
echo "→ Starting database and cache…"
docker compose -f "$COMPOSE_FILE" up -d postgres redis

echo "→ Waiting for postgres to be healthy…"
timeout 60 bash -c 'until docker compose -f '"$COMPOSE_FILE"' exec -T postgres pg_isready -U vwa_admin -d vwa &>/dev/null; do sleep 2; done'

# ── 5. Run database migrations ────────────────────────────────────────────────
echo "→ Running Alembic migrations…"
docker compose -f "$COMPOSE_FILE" run --rm backend python -m alembic upgrade head

# ── 6. Seed admin user (idempotent) ───────────────────────────────────────────
echo "→ Seeding admin user (idempotent)…"
docker compose -f "$COMPOSE_FILE" run --rm backend \
    python -c "import asyncio; from app.seed import seed; asyncio.run(seed())" || true

# ── 7. Start / restart all services ──────────────────────────────────────────
echo "→ Starting all services…"
docker compose -f "$COMPOSE_FILE" up -d

# ── 8. Health check ───────────────────────────────────────────────────────────
echo "→ Waiting for API health check…"
sleep 10
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "✓ API is healthy"
else
    echo "⚠ API health check failed — check logs:"
    echo "  docker compose -f $COMPOSE_FILE logs backend --tail=50"
fi

echo ""
echo "✓ Deploy complete!"
echo ""
echo "  Services:  docker compose -f $COMPOSE_FILE ps"
echo "  API logs:  docker compose -f $COMPOSE_FILE logs backend -f"
echo "  Worker:    docker compose -f $COMPOSE_FILE logs worker -f"
