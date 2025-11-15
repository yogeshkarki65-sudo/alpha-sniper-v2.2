# Alpha Sniper V2 - Deployment Guide

## Quick Deploy Commands

### 1. Clone the Repository on Your Server

```bash
git clone https://github.com/yogeshkarki65-sudo/alpha-sniper-v2.2.git
cd alpha-sniper-v2.2
git checkout claude/latest-fixes-01QVwRQY57npqebQKVvUBaHd
```

### 2. Install Dependencies

```bash
# Install Python 3.11+ if not installed
sudo apt update
sudo apt install python3 python3-pip -y

# Install required packages
pip3 install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Required changes in .env:**
- `TELEGRAM_BOT_TOKEN` - Get from @BotFather on Telegram
- `TELEGRAM_CHAT_ID` - Get from @userinfobot on Telegram
- `MODE=SIM` - Start with simulation mode first!

### 4. Create Required Directories

```bash
mkdir -p data logs backups
```

### 5. Test Run (Foreground)

```bash
python3 main.py
```

Press Ctrl+C to stop. If it starts successfully, proceed to production deployment.

### 6. Production Deployment Options

#### Option A: Using screen (Simple)

```bash
# Start in screen session
screen -S alpha-sniper
python3 main.py

# Detach with: Ctrl+A then D
# Reattach with: screen -r alpha-sniper
# Stop: screen -r alpha-sniper then Ctrl+C
```

#### Option B: Using systemd (Recommended)

```bash
# Create systemd service file
sudo nano /etc/systemd/system/alpha-sniper.service
```

Paste this content:
```ini
[Unit]
Description=Alpha Sniper Trading Bot
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/alpha-sniper-v2.2
ExecStart=/usr/bin/python3 /home/YOUR_USERNAME/alpha-sniper-v2.2/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable alpha-sniper
sudo systemctl start alpha-sniper

# Check status
sudo systemctl status alpha-sniper

# View logs
sudo journalctl -u alpha-sniper -f

# Stop bot
sudo systemctl stop alpha-sniper

# Restart bot
sudo systemctl restart alpha-sniper
```

#### Option C: Using Docker

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Restart
docker-compose restart
```

### 7. Monitor the Bot

**Health Check:**
```bash
curl http://localhost:8080/health
```

**Emergency Stop:**
```bash
curl -X POST http://localhost:8081/emergency-stop
```

**View Logs:**
```bash
# If using systemd
sudo journalctl -u alpha-sniper -f

# If using screen
screen -r alpha-sniper

# If using docker
docker-compose logs -f
```

### 8. Important Notes

⚠️ **Start in SIM mode first!**
- Run for at least 7-14 days in simulation
- Monitor daily reports and performance
- Only switch to LIVE mode with small capital

⚠️ **Security:**
- Never commit .env file to git
- Keep your Telegram token private
- Use firewall to restrict port access

⚠️ **Monitoring:**
- Check Telegram alerts daily
- Monitor /health endpoint
- Review logs for errors

### 9. Switching to Live Trading

Once satisfied with SIM performance:

```bash
# Edit .env
nano .env

# Change:
MODE=LIVE

# Restart bot
sudo systemctl restart alpha-sniper
# OR
screen -r alpha-sniper # then Ctrl+C and restart
```

### 10. Emergency Procedures

**Pause Trading:**
```bash
curl -X POST http://localhost:8081/emergency-stop
```

**Or edit .env:**
```bash
nano .env
# Set: TRADING_PAUSED=true
sudo systemctl restart alpha-sniper
```

**Close All Positions Manually:**
```bash
# Access your MEXC account and close positions manually
# The bot will detect they're closed on next check
```

## Troubleshooting

**Bot won't start:**
```bash
# Check Python version
python3 --version  # Should be 3.11+

# Reinstall dependencies
pip3 install -r requirements.txt --force-reinstall

# Check .env exists
ls -la .env
```

**API errors:**
- Verify internet connection
- Check MEXC API status
- Ensure no firewall blocking

**No signals created:**
- Normal if market is quiet
- Check MIN_SIGNAL_SCORE setting
- Verify MEXC API is responding

## Server Requirements

- **CPU:** 1 core minimum, 2+ recommended
- **RAM:** 1GB minimum, 2GB recommended
- **Storage:** 10GB minimum
- **Network:** Stable internet connection
- **OS:** Ubuntu 20.04+ or any Linux distro
- **Python:** 3.11+

## Recommended VPS Providers

- DigitalOcean ($6/month)
- Linode ($5/month)
- Vultr ($5/month)
- AWS EC2 (t3.micro)
- Google Cloud (e2-micro)
