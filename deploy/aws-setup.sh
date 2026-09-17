#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# deploy/aws-setup.sh
#
# One-shot setup script for an Ubuntu 24.04 AWS EC2 instance.
# Run this ONCE after launching a fresh t2.micro / t3.micro.
#
# Usage:
#   1. SSH into your EC2 instance
#   2. Copy this script or clone the repo
#   3. Edit the .env values below
#   4. Run: chmod +x deploy/aws-setup.sh && sudo deploy/aws-setup.sh
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

echo "══════════════════════════════════════════════════════"
echo "  Business Card AI — AWS EC2 Setup"
echo "══════════════════════════════════════════════════════"

# ── 1. Install Docker ───────────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "[1/4] Installing Docker..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    echo "[1/4] Docker installed successfully."
else
    echo "[1/4] Docker already installed — skipping."
fi

# ── 2. Clone the repository (if not already present) ───────────
APP_DIR="/opt/business-card-ai"

if [ ! -d "$APP_DIR" ]; then
    echo "[2/4] Cloning repository..."
    apt-get install -y -qq git
    git clone https://github.com/AyaanShaheer/business-card-ai.git "$APP_DIR"
else
    echo "[2/4] Repository already exists at $APP_DIR — pulling latest..."
    cd "$APP_DIR" && git pull origin main
fi

cd "$APP_DIR"

# ── 3. Create .env file ────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    echo "[3/4] Creating .env file..."
    cat > "$APP_DIR/.env" << 'ENVEOF'
# ─── Database ───
POSTGRES_PASSWORD=business_card_ai_prod

# ─── Qwen VLM Inference ───
INFERENCE_BASE_URL=https://openrouter.ai/api/v1
INFERENCE_MODEL=qwen/qwen3-vl-30b-a3b-instruct
INFERENCE_API_KEY=REPLACE_WITH_YOUR_OPENROUTER_API_KEY
INFERENCE_TIMEOUT_SECONDS=120

# ─── Application ───
MAX_FILE_SIZE_MB=10
MAX_FILES_PER_JOB=50
ENVEOF
    echo ""
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║  IMPORTANT: Edit $APP_DIR/.env and set              ║"
    echo "║  INFERENCE_API_KEY to your OpenRouter API key        ║"
    echo "║  before proceeding!                                  ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    echo "  After editing .env, re-run this script or run:"
    echo "  cd $APP_DIR && docker compose -f infra/docker-compose.prod.yml up -d --build"
    echo ""
    exit 0
else
    echo "[3/4] .env file exists — using existing configuration."
fi

# ── 4. Build and start ─────────────────────────────────────────
echo "[4/4] Building and starting services..."
cd "$APP_DIR"
docker compose -f infra/docker-compose.prod.yml up -d --build

echo ""
echo "══════════════════════════════════════════════════════"
echo "  ✅ Deployment complete!"
echo ""
echo "  Your application is running at:"
echo "  http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo '<EC2-PUBLIC-IP>'):80"
echo ""
echo "  Useful commands:"
echo "  - View logs:    docker compose -f infra/docker-compose.prod.yml logs -f"
echo "  - Stop:         docker compose -f infra/docker-compose.prod.yml down"
echo "  - Restart:      docker compose -f infra/docker-compose.prod.yml restart"
echo "══════════════════════════════════════════════════════"
