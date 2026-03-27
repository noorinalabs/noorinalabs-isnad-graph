#!/usr/bin/env bash
# =============================================================================
# bootstrap-vps.sh — First-time VPS setup for isnad-graph
#
# Run as root on a fresh Hetzner VPS:
#   ssh -i ~/.ssh/isnad_deploy root@isnad-graph.noorinalabs.com
#   curl -sL https://raw.githubusercontent.com/parametrization/isnad-graph/main/scripts/bootstrap-vps.sh | bash
#
# Or copy this script to the VPS and run:
#   chmod +x bootstrap-vps.sh && ./bootstrap-vps.sh
# =============================================================================
set -euo pipefail

REPO_URL="https://github.com/parametrization/isnad-graph.git"
INSTALL_DIR="/opt/isnad-graph"
DEPLOY_USER="deploy"

echo "============================================="
echo "  isnad-graph VPS bootstrap"
echo "============================================="
echo ""

# ── Preflight checks ────────────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: This script must be run as root."
  exit 1
fi

# ── Step 1: System packages ─────────────────────────────────────────────────
echo "==> [1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 docker-buildx git curl > /dev/null
systemctl enable docker
systemctl start docker
echo "    Docker version: $(docker --version)"

# ── Step 2: Create deploy user ──────────────────────────────────────────────
echo "==> [2/7] Creating deploy user..."
if id "$DEPLOY_USER" &>/dev/null; then
  echo "    User '$DEPLOY_USER' already exists, skipping."
else
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
  echo "    Created user '$DEPLOY_USER'."
fi
usermod -aG docker "$DEPLOY_USER"

# ── Step 3: Copy SSH authorized_keys to deploy user ─────────────────────────
echo "==> [3/7] Setting up SSH for deploy user..."
mkdir -p /home/$DEPLOY_USER/.ssh
touch /home/$DEPLOY_USER/.ssh/authorized_keys
# Copy root's authorized_keys (Terraform puts the deploy key here)
if [ -f /root/.ssh/authorized_keys ]; then
  cp /root/.ssh/authorized_keys /home/$DEPLOY_USER/.ssh/authorized_keys
  echo "    Copied root authorized_keys to deploy user."
else
  echo "    WARNING: /root/.ssh/authorized_keys not found."
  echo "    You'll need to manually add your public key to /home/$DEPLOY_USER/.ssh/authorized_keys"
fi
chown -R $DEPLOY_USER:$DEPLOY_USER /home/$DEPLOY_USER/.ssh
chmod 700 /home/$DEPLOY_USER/.ssh
chmod 600 /home/$DEPLOY_USER/.ssh/authorized_keys

# ── Step 4: Clone the repository ────────────────────────────────────────────
echo "==> [4/7] Cloning repository to $INSTALL_DIR..."
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "    Repository already exists, pulling latest..."
  cd "$INSTALL_DIR" && git fetch origin main && git reset --hard origin/main
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
chown -R $DEPLOY_USER:$DEPLOY_USER "$INSTALL_DIR"

# ── Step 5: Create production .env ──────────────────────────────────────────
echo "==> [5/7] Creating production .env..."
ENV_FILE="$INSTALL_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  echo "    .env already exists, skipping. Edit manually if needed:"
  echo "    nano $ENV_FILE"
else
  cat > "$ENV_FILE" << 'ENVEOF'
# =============================================================================
# isnad-graph production environment
# Fill in all values marked CHANGE-ME before starting the stack.
# =============================================================================

# Neo4j [REQUIRED]
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=CHANGE-ME
NEO4J_PASSWORD=CHANGE-ME

# PostgreSQL [REQUIRED]
POSTGRES_USER=CHANGE-ME
POSTGRES_PASSWORD=CHANGE-ME
POSTGRES_DB=isnad_graph

# Redis [REQUIRED]
REDIS_URL=redis://:CHANGE-ME@redis:6379/0
REDIS_PASSWORD=CHANGE-ME

# Grafana [REQUIRED]
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=CHANGE-ME
GRAFANA_ROOT_URL=https://isnad-graph.noorinalabs.com/grafana

# CORS
CORS_ORIGINS=["https://isnad-graph.noorinalabs.com"]

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=120
RATE_LIMIT_WINDOW_SECONDS=60

# Paths
DATA_RAW_DIR=./data/raw
DATA_STAGING_DIR=./data/staging
DATA_CURATED_DIR=./data/curated
ENVEOF
  chmod 600 "$ENV_FILE"
  chown $DEPLOY_USER:$DEPLOY_USER "$ENV_FILE"
  echo ""
  echo "    ╔═══════════════════════════════════════════════════════╗"
  echo "    ║  IMPORTANT: Edit $ENV_FILE before starting!          ║"
  echo "    ║  Replace all CHANGE-ME values with real credentials. ║"
  echo "    ╚═══════════════════════════════════════════════════════╝"
  echo ""
  echo "    nano $ENV_FILE"
  echo ""
fi

# ── Step 6: Install rclone for backups ──────────────────────────────────────
echo "==> [6/7] Installing rclone for backups..."
if command -v rclone &>/dev/null; then
  echo "    rclone already installed: $(rclone version --check | head -1)"
else
  curl -sL https://rclone.org/install.sh | bash > /dev/null 2>&1
  echo "    rclone installed: $(rclone version --check 2>/dev/null | head -1 || echo 'installed')"
fi

# ── Step 7: Install backup systemd timer ────────────────────────────────────
echo "==> [7/7] Installing backup timer..."
if [ -f "$INSTALL_DIR/systemd/isnad-backup.service" ]; then
  cp "$INSTALL_DIR/systemd/isnad-backup.service" /etc/systemd/system/
  cp "$INSTALL_DIR/systemd/isnad-backup.timer" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable isnad-backup.timer
  echo "    Backup timer installed (daily at 03:00 UTC)."
  echo "    Start with: systemctl start isnad-backup.timer"
else
  echo "    Backup systemd files not found, skipping."
fi

# ── Done ────────────────────────────────────────────────────────────────────
echo ""
echo "============================================="
echo "  Bootstrap complete!"
echo "============================================="
echo ""
echo "Next steps:"
echo "  1. Edit the .env file with your production credentials:"
echo "     nano $ENV_FILE"
echo ""
echo "  2. Start the stack as the deploy user:"
echo "     su - $DEPLOY_USER"
echo "     cd $INSTALL_DIR"
echo "     docker compose -f docker-compose.prod.yml up -d --build"
echo ""
echo "  3. Verify:"
echo "     curl http://localhost:8000/health"
echo ""
echo "  4. Add VPS_HOST variable in GitHub repo settings:"
echo "     Settings → Variables → New: VPS_HOST = isnad-graph.noorinalabs.com"
echo ""
echo "  5. Start the backup timer:"
echo "     systemctl start isnad-backup.timer"
echo ""
