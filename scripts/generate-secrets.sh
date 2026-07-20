#!/usr/bin/env bash
# ─── VWA — generate production secrets ───────────────────────────────────────
# Generates random SECRET_KEY + DB password and patches backend/.env.production.
# Run once on the EC2 server before the first deploy.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/backend/.env.production"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "✗ $ENV_FILE not found. Copy .env.example first."
    exit 1
fi

echo "→ Generating secrets for $ENV_FILE"

# Generate a 64-byte hex secret key
SECRET_KEY="$(openssl rand -hex 64)"

# Generate a strong DB password (alphanumeric, safe for URLs)
DB_PASS="$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)"

# Patch in-place
sed -i "s|REPLACE_ME_PRODUCTION_SECRET_KEY|${SECRET_KEY}|g" "$ENV_FILE"
sed -i "s|REPLACE_ME_DB_PASSWORD|${DB_PASS}|g" "$ENV_FILE"

# Also patch docker-compose.prod.yml postgres password placeholder
COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"
sed -i "s|REPLACE_ME_DB_PASSWORD|${DB_PASS}|g" "$COMPOSE_FILE"

echo "✓ SECRET_KEY  → set (64-byte hex)"
echo "✓ DB password → ${DB_PASS}"
echo ""
echo "⚠  Save the DB password somewhere safe — it's now written into:"
echo "   $ENV_FILE"
echo "   $COMPOSE_FILE"
echo ""
echo "Next: review $ENV_FILE and replace any remaining REPLACE_ME values"
echo "      (SMTP, S3 keys, CORS origins, etc.)."
