# Alpha Sniper V2.2 - Deployment Guide

## Quick Start (Fresh Ubuntu/Debian Server)

### Prerequisites
- Fresh Ubuntu 20.04+ or Debian 11+ server
- Root or sudo access
- At least 2GB RAM, 20GB disk space
- Stable internet connection

### 1. Initial Server Setup

```bash
# Clone the repository
git clone <your-repo-url> ~/alpha-sniper-v2.2
cd ~/alpha-sniper-v2.2

# Run the automated setup script
sudo ./deployment/setup_server.sh
```

This script will:
- Update system packages
- Install Docker and Docker Compose
- Configure firewall (UFW)
- Set up fail2ban for security
- Create necessary directories
- Set up log rotation
- Create systemd service
- Configure automatic backups

### 2. Configure Telegram Bot

**Get Bot Token:**
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow instructions
3. Copy the token you receive

**Get Chat ID:**
1. Search for `@userinfobot` on Telegram
2. Send `/start`
3. Copy your chat ID

**Test the Bot:**
```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/sendMessage?chat_id=<YOUR_CHAT_ID>&text=Test"
```

### 3. Edit Configuration

```bash
nano .env
```

**Critical settings to update:**
- `TELEGRAM_BOT_TOKEN` - Your bot token from BotFather
- `TELEGRAM_CHAT_ID` - Your chat ID
- `MODE=SIM` - Keep in SIM mode for testing
- `SIM_EQUITY_START=500` - Starting simulation balance

**Verify configuration:**
```bash
grep -E "TELEGRAM|MODE" .env
```

### 4. Build and Start

```bash
# Build the Docker image
docker compose build

# Start the bot
docker compose up -d

# Check if it's running
docker ps

# View logs
docker compose logs -f
```

### 5. Verify Deployment

**Check health endpoint:**
```bash
curl http://localhost:80/health
```

Expected response:
```json
{
  "status": "healthy",
  "mode": "SIM",
  "last_scanner_run": "...",
  "last_trader_run": "..."
}
```

**Check Telegram:**
- You should receive a startup message
- Test with `/health` command (if implemented)

**Monitor logs:**
```bash
# Real-time logs
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100

# Specific service logs
docker logs alpha-sniper-v2
```

## Management Commands

### Start/Stop/Restart

```bash
# Start
docker compose up -d

# Stop
docker compose down

# Restart
docker compose restart

# Rebuild after code changes
docker compose up -d --build
```

### View Status

```bash
# Container status
docker ps

# Resource usage
docker stats alpha-sniper-v2

# Health check
curl http://localhost:80/health
```

### View Logs

```bash
# All logs
docker compose logs

# Follow logs
docker compose logs -f

# Last N lines
docker compose logs --tail=50

# Specific timestamp
docker compose logs --since 30m
```

### Database Management

```bash
# Access database directly
docker compose exec alpha-sniper sqlite3 /app/data/trades.db

# Backup database
docker compose exec alpha-sniper sqlite3 /app/data/trades.db ".backup /app/backups/manual_backup.db"

# View tables
docker compose exec alpha-sniper sqlite3 /app/data/trades.db ".tables"

# Query trades
docker compose exec alpha-sniper sqlite3 /app/data/trades.db "SELECT * FROM trades LIMIT 10;"
```

### Emergency Stop

```bash
# Method 1: Using stop script
./deployment/stop_trading.sh

# Method 2: Manual stop
docker compose down

# Method 3: Pause trading (edit .env)
sed -i 's/TRADING_PAUSED=false/TRADING_PAUSED=true/' .env
docker compose restart
```

## Monitoring

### Daily Checks

1. **Check health endpoint**
   ```bash
   curl http://localhost:80/health
   ```

2. **Review logs for errors**
   ```bash
   docker compose logs --tail=100 | grep -i error
   ```

3. **Check disk space**
   ```bash
   df -h
   ```

4. **Review Telegram daily report**
   - Sent daily at configured hour (default 9:00 UTC)

### Weekly Checks

1. **Review database size**
   ```bash
   ls -lh data/trades.db
   ```

2. **Check backup integrity**
   ```bash
   ls -lh backups/
   ```

3. **Review performance metrics**
   ```bash
   docker compose exec alpha-sniper sqlite3 /app/data/trades.db \
     "SELECT COUNT(*), AVG(pnl_pct), MAX(pnl_pct), MIN(pnl_pct) FROM trades WHERE timestamp > datetime('now', '-7 days');"
   ```

### Performance Metrics

```bash
# Get daily P&L
docker compose exec alpha-sniper sqlite3 /app/data/trades.db \
  "SELECT DATE(timestamp), COUNT(*), SUM(pnl_usd), AVG(pnl_pct) FROM trades WHERE timestamp > datetime('now', '-30 days') GROUP BY DATE(timestamp);"

# Win rate
docker compose exec alpha-sniper sqlite3 /app/data/trades.db \
  "SELECT ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate FROM trades;"

# Current equity
curl http://localhost:80/health | jq '.equity'
```

## Troubleshooting

### Bot Not Starting

```bash
# Check logs
docker compose logs

# Check if container is running
docker ps -a

# Rebuild
docker compose down
docker compose build --no-cache
docker compose up -d
```

### No Telegram Messages

1. Verify bot token and chat ID in `.env`
2. Test manually:
   ```bash
   curl "https://api.telegram.org/bot$(grep TELEGRAM_BOT_TOKEN .env | cut -d= -f2)/sendMessage?chat_id=$(grep TELEGRAM_CHAT_ID .env | cut -d= -f2)&text=Test"
   ```
3. Check container logs for Telegram errors

### Database Locked

```bash
# Stop bot
docker compose down

# Wait a few seconds
sleep 5

# Restart
docker compose up -d
```

### High Memory Usage

```bash
# Check usage
docker stats alpha-sniper-v2

# Restart container
docker compose restart

# If persistent, check for memory leaks in logs
```

### Connection Issues

```bash
# Test MEXC API
curl https://api.mexc.com/api/v3/ping

# Check DNS
nslookup api.mexc.com

# Check firewall
sudo ufw status
```

## Upgrading

### Code Updates

```bash
# Stop bot
docker compose down

# Backup database
cp data/trades.db backups/pre_upgrade_$(date +%Y%m%d).db

# Pull latest code
git pull

# Rebuild and restart
docker compose build
docker compose up -d

# Monitor logs
docker compose logs -f
```

### Configuration Updates

```bash
# Edit config
nano .env

# Restart to apply
docker compose restart

# Verify changes took effect
docker compose logs --tail=50
```

## Security Best Practices

1. **Never commit .env to git**
   ```bash
   # Verify .env is in .gitignore
   cat .gitignore | grep .env
   ```

2. **Keep system updated**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

3. **Monitor failed login attempts**
   ```bash
   sudo fail2ban-client status sshd
   ```

4. **Use SSH keys, disable password auth**
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart sshd
   ```

5. **Restrict firewall**
   ```bash
   sudo ufw status
   # Only allow necessary ports (22, and optionally 80)
   ```

6. **Regular backups**
   - Automatic daily backups configured at 2 AM
   - Manual backup: `./deployment/backup.sh`
   - Keep backups off-server

## Moving to Live Trading

**DO NOT rush this! Follow these steps carefully:**

1. **Run in SIM mode for 7-14 days minimum**
   - Monitor performance
   - Review all trades
   - Check for any errors or crashes

2. **Analyze results**
   ```bash
   docker compose exec alpha-sniper sqlite3 /app/data/trades.db \
     "SELECT COUNT(*), AVG(pnl_pct), SUM(pnl_usd), MIN(pnl_pct), MAX(pnl_pct) FROM trades;"
   ```

3. **Review risk parameters**
   - Adjust `MAX_POSITION_RISK_PCT`
   - Set conservative `MAX_DAILY_DRAWDOWN_PCT`
   - Consider lowering `MAX_PER_TRADE_PCT`

4. **Start with minimal capital**
   ```bash
   nano .env
   # Set MODE=LIVE
   # Set LIVE_EQUITY_START=100  (or your minimum)
   docker compose restart
   ```

5. **Monitor closely**
   - Check every few hours initially
   - Verify all trades on MEXC
   - Compare expected vs actual fills

6. **Scale gradually**
   - Only increase capital after consistent profitable performance
   - Never risk more than you can afford to lose

## Support

- Check logs: `docker compose logs -f`
- Review critical issues: `cat CRITICAL_ISSUES.md`
- Telegram alerts will notify you of issues
- Monitor health endpoint regularly

## Useful Links

- MEXC API Docs: https://mexcdevelop.github.io/apidocs/
- Docker Compose: https://docs.docker.com/compose/
- UFW Firewall: https://help.ubuntu.com/community/UFW
