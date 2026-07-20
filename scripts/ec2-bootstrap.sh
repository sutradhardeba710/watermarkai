#!/usr/bin/env bash
# ─── VWA — EC2 cloud-init bootstrap ──────────────────────────────────────────
# Paste this into the EC2 "User data" field (Advanced Details) when launching.
# It runs once as root on first boot.
#
# BEFORE launching: fill in the three REPLACE_ME values below.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── USER CONFIG — fill these in before pasting into EC2 User Data ─────────────
GITHUB_REPO="https://github.com/REPLACE_ME_GITHUB_USER/REPLACE_ME_REPO_NAME.git"
# Your EC2 public IP or domain (used in CORS + Caddy config)
PUBLIC_HOST="REPLACE_ME_EC2_PUBLIC_IP_OR_DOMAIN"
# Optional: your SMTP host for email verification (leave blank to use console mode)
SMTP_HOST=""
# ─────────────────────────────────────────────────────────────────────────────

LOG_FILE="/var/log/vwa-bootstrap.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== VWA Bootstrap started at $(date) ==="

# ── 1. System update + Docker install ────────────────────────────────────────
apt-get update -y
apt-get install -y \
    docker.io \
    docker-compose-plugin \
    git \
    curl \
    openssl \
    jq

systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu

# ── 2. Clone repository ───────────────────────────────────────────────────────
PROJECT_DIR="/opt/vwa"
if [[ -d "$PROJECT_DIR/.git" ]]; then
    echo "Repo already cloned — pulling latest…"
    cd "$PROJECT_DIR"
    git pull --ff-only
else
    git clone "$GITHUB_REPO" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi
chown -R ubuntu:ubuntu "$PROJECT_DIR"

# ── 3. Create production env from example ────────────────────────────────────
if [[ ! -f backend/.env.production ]]; then
    cp backend/.env.example backend/.env.production
fi

# ── 4. Generate secrets ───────────────────────────────────────────────────────
bash scripts/generate-secrets.sh

# ── 5. Patch env: update hostnames for Docker networking ──────────────────────
# Use container service names (postgres, redis) not localhost
sed -i "s|@localhost:5432|@postgres:5432|g" backend/.env.production
sed -i "s|redis://localhost|redis://redis|g" backend/.env.production

# Set storage to local (EBS-backed volume inside container)
sed -i "s|VWA_STORAGE_BACKEND=.*|VWA_STORAGE_BACKEND=local|g" backend/.env.production
sed -i "s|VWA_STORAGE_LOCAL_ROOT=.*|VWA_STORAGE_LOCAL_ROOT=/app/.storage|g" backend/.env.production

# Update CORS to allow public host
sed -i "s|VWA_CORS_ORIGINS=.*|VWA_CORS_ORIGINS=[\"http://${PUBLIC_HOST}\",\"https://${PUBLIC_HOST}\"]|g" backend/.env.production
sed -i "s|VWA_APP_BASE_URL=.*|VWA_APP_BASE_URL=http://${PUBLIC_HOST}|g" backend/.env.production

# SMTP: use console mode if no SMTP host provided
if [[ -z "$SMTP_HOST" ]]; then
    sed -i "s|VWA_SMTP_CONSOLE=.*|VWA_SMTP_CONSOLE=true|g" backend/.env.production
else
    sed -i "s|VWA_SMTP_HOST=.*|VWA_SMTP_HOST=${SMTP_HOST}|g" backend/.env.production
fi

# ── 6. Update Caddyfile for IP-only HTTP (no domain = no HTTPS) ───────────────
# If PUBLIC_HOST looks like a domain (has a dot, not just an IP), enable HTTPS
if echo "$PUBLIC_HOST" | grep -qP '^[a-z]'; then
    # Domain-based — Caddy will auto-obtain TLS cert
    cat > Caddyfile <<CADDY
${PUBLIC_HOST} {
    handle_path /api/* {
        reverse_proxy backend:8000
    }
    handle_path /health/* {
        reverse_proxy backend:8000
    }
    handle {
        reverse_proxy frontend:3000
    }
}
CADDY
else
    # IP-only — HTTP only
    cat > Caddyfile <<CADDY
:80 {
    handle_path /api/* {
        reverse_proxy backend:8000
    }
    handle_path /health/* {
        reverse_proxy backend:8000
    }
    handle {
        reverse_proxy frontend:3000
    }
}
CADDY
fi

# ── 7. Run deploy ─────────────────────────────────────────────────────────────
echo "=== Running deploy ==="
sudo -u ubuntu bash scripts/deploy.sh --no-pull

echo ""
echo "=== Bootstrap complete at $(date) ==="
echo "    App: http://${PUBLIC_HOST}"
echo "    Logs: journalctl -u docker or docker compose -f docker-compose.prod.yml logs -f"
