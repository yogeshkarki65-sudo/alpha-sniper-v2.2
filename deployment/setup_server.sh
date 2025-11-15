#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Alpha Sniper V2 - Server Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: Please run as root (use sudo)${NC}"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER=${SUDO_USER:-$USER}
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)

echo -e "${GREEN}[1/10]${NC} Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

echo -e "${GREEN}[2/10]${NC} Installing prerequisites..."
apt-get install -y -qq \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common \
    git \
    ufw \
    fail2ban \
    htop \
    vim \
    wget

echo -e "${GREEN}[3/10]${NC} Installing Docker..."
if ! command -v docker &> /dev/null; then
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc

    # Add Docker repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Add user to docker group
    usermod -aG docker $ACTUAL_USER
    echo -e "${GREEN}✓${NC} Docker installed successfully"
else
    echo -e "${YELLOW}✓${NC} Docker already installed"
fi

echo -e "${GREEN}[4/10]${NC} Configuring firewall (UFW)..."
# Allow SSH
ufw allow 22/tcp

# Allow monitoring port (optional, only if you want external access)
# ufw allow 80/tcp

# Enable firewall
echo "y" | ufw enable
ufw status

echo -e "${GREEN}[5/10]${NC} Setting up fail2ban..."
systemctl enable fail2ban
systemctl start fail2ban

echo -e "${GREEN}[6/10]${NC} Creating project directory structure..."
PROJECT_DIR="$ACTUAL_HOME/alpha-sniper-v2.2"

if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}Project directory not found. Please clone the repository first.${NC}"
    echo -e "${YELLOW}Run: git clone <your-repo-url> $PROJECT_DIR${NC}"
    exit 1
fi

cd "$PROJECT_DIR"

# Create necessary directories
mkdir -p data logs backups

# Set proper ownership
chown -R $ACTUAL_USER:$ACTUAL_USER "$PROJECT_DIR"

echo -e "${GREEN}[7/10]${NC} Setting up environment configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠ .env file created from example. PLEASE EDIT IT BEFORE STARTING!${NC}"
    echo -e "${YELLOW}   Edit: $PROJECT_DIR/.env${NC}"
else
    echo -e "${GREEN}✓${NC} .env file already exists"
fi

echo -e "${GREEN}[8/10]${NC} Setting up log rotation..."
cat > /etc/logrotate.d/alpha-sniper <<EOF
$PROJECT_DIR/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $ACTUAL_USER $ACTUAL_USER
}
EOF

echo -e "${GREEN}[9/10]${NC} Creating systemd service for auto-restart..."
cat > /etc/systemd/system/alpha-sniper.service <<EOF
[Unit]
Description=Alpha Sniper V2 Trading Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=$ACTUAL_USER

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable alpha-sniper.service

echo -e "${GREEN}[10/10]${NC} Setting up monitoring cron jobs..."
# Create backup script
cat > "$PROJECT_DIR/deployment/backup.sh" <<'EOF'
#!/bin/bash
BACKUP_DIR="$HOME/alpha-sniper-v2.2/backups"
DATE=$(date +%Y%m%d_%H%M%S)
cd $HOME/alpha-sniper-v2.2
docker compose exec -T alpha-sniper sqlite3 /app/data/trades.db ".backup /app/backups/trades_${DATE}.db"
# Keep only last 30 days of backups
find $BACKUP_DIR -name "trades_*.db" -mtime +30 -delete
EOF

chmod +x "$PROJECT_DIR/deployment/backup.sh"
chown $ACTUAL_USER:$ACTUAL_USER "$PROJECT_DIR/deployment/backup.sh"

# Add cron job for daily backup at 2 AM
(crontab -u $ACTUAL_USER -l 2>/dev/null; echo "0 2 * * * $PROJECT_DIR/deployment/backup.sh") | crontab -u $ACTUAL_USER -

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Server setup complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT NEXT STEPS:${NC}"
echo ""
echo -e "1. Edit configuration file:"
echo -e "   ${BLUE}nano $PROJECT_DIR/.env${NC}"
echo ""
echo -e "2. Configure these critical settings:"
echo -e "   - TELEGRAM_BOT_TOKEN"
echo -e "   - TELEGRAM_CHAT_ID"
echo -e "   - MODE (SIM or LIVE)"
echo -e "   - Risk management parameters"
echo ""
echo -e "3. Build and start the bot:"
echo -e "   ${BLUE}cd $PROJECT_DIR${NC}"
echo -e "   ${BLUE}docker compose build${NC}"
echo -e "   ${BLUE}docker compose up -d${NC}"
echo ""
echo -e "4. Check logs:"
echo -e "   ${BLUE}docker compose logs -f${NC}"
echo ""
echo -e "5. Monitor health:"
echo -e "   ${BLUE}curl http://localhost:80/health${NC}"
echo ""
echo -e "6. View running containers:"
echo -e "   ${BLUE}docker ps${NC}"
echo ""
echo -e "${RED}⚠ SECURITY NOTE:${NC}"
echo -e "   - You may need to log out and back in for Docker permissions"
echo -e "   - Keep your .env file secure (never commit it to git)"
echo -e "   - Start in SIM mode and monitor for 7-14 days"
echo ""
echo -e "${GREEN}Happy trading!${NC}"
