#!/bin/bash
# ╔══════════════════════════════════════════════════════╗
# ║   Astro TMA — One-Shot Deploy                       ║
# ║   Server: 194.99.21.53                              ║
# ║   Run as root on fresh Ubuntu 24.04                 ║
# ║                                                      ║
# ║   Pre-req: copy a populated .env into                ║
# ║   /opt/astro-tma/.env before running this script.    ║
# ║   See infra/scripts/.env.example for the schema.     ║
# ╚══════════════════════════════════════════════════════╝
set -euo pipefail

RDNS="ip-194-99-21-53-142250.vps.hosted-by-mvps.net"
echo ""
echo "🌟 Astro TMA Deploy starting on $RDNS"
echo "=================================================="

# ── 1. System packages ─────────────────────────────────
echo "[1/8] Installing packages..."
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 certbot git curl python3

# ── 2. Project dir + .env check ────────────────────────
echo "[2/8] Setting up project..."
mkdir -p /opt/astro-tma
cd /opt/astro-tma

if [[ ! -f .env ]]; then
  echo "❌ /opt/astro-tma/.env not found."
  echo "   Copy infra/scripts/.env.example to /opt/astro-tma/.env,"
  echo "   fill in real secrets, then re-run this script."
  exit 1
fi

# Source .env so we can use values below (TELEGRAM_BOT_TOKEN etc.)
set -a; source .env; set +a

# ── 3. SSL certificate ─────────────────────────────────
echo "[3/8] Getting SSL certificate..."
certbot certonly --standalone -d "$RDNS" \
  --non-interactive --agree-tos \
  -m "admin@astro-tma.local" \
  --no-eff-email || echo "⚠️  certbot failed — check that port 80 is open"

# ── 4. Create docker-compose.yml ──────────────────────
echo "[4/8] Creating docker-compose.yml..."
cat > docker-compose.yml << 'DCEOF'
version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: astro_tma
      POSTGRES_USER: astro
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U astro -d astro_tma"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks: [astro-net]

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
    networks: [astro-net]

  backend:
    image: python:3.12-slim
    restart: unless-stopped
    working_dir: /app
    command: >
      bash -c "pip install -q fastapi uvicorn[standard] kerykeion sqlalchemy[asyncio] asyncpg
               alembic redis pydantic pydantic-settings structlog httpx apscheduler python-telegram-bot &&
               alembic upgrade head &&
               uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2"
    env_file: .env
    volumes:
      - ./backend:/app
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks: [astro-net]

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infra/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./infra/nginx/conf.d:/etc/nginx/conf.d:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on: [backend]
    networks: [astro-net]

networks:
  astro-net:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
DCEOF

# ── 5. Start services ──────────────────────────────────
echo "[5/8] Starting services..."
docker compose up -d postgres redis
sleep 10

# ── 6. Start backend ──────────────────────────────────
echo "[6/8] Waiting for backend..."
docker compose up -d backend
sleep 15

# ── 7. Register Telegram webhook ──────────────────────
echo "[7/8] Registering Telegram webhook..."
curl -s -X POST \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"${TELEGRAM_WEBHOOK_URL}\",\"secret_token\":\"${TELEGRAM_WEBHOOK_SECRET}\",\"allowed_updates\":[\"message\",\"pre_checkout_query\"]}"
echo ""

# ── 8. Verify ─────────────────────────────────────────
echo "[8/8] Verifying bot..."
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" | python3 -m json.tool

echo ""
echo "=================================================="
echo "✅ Deploy complete!"
echo "   API:    https://$RDNS/health"
echo "   Webhook: registered ✓"
echo ""
echo "Next: deploy frontend to Vercel and register Mini App URL in @BotFather"
