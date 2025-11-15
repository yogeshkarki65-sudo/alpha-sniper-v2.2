# Deployment Scripts

This directory contains all the scripts and documentation needed to deploy and manage Alpha Sniper V2.2.

## Quick Start

### Fresh Server Setup
```bash
# Run this on a fresh Ubuntu/Debian server
sudo ./setup_server.sh
```

### Already Configured Server
```bash
# Quick start for already configured servers
./quick_start.sh
```

## Scripts Overview

### setup_server.sh
**Purpose:** Complete server setup from scratch
**Usage:** `sudo ./setup_server.sh`
**What it does:**
- Installs Docker and Docker Compose
- Configures firewall (UFW)
- Sets up fail2ban for security
- Creates systemd service
- Configures log rotation
- Sets up automatic database backups

**When to use:** First time setting up a new server

---

### quick_start.sh
**Purpose:** Start the bot quickly on an already configured server
**Usage:** `./quick_start.sh`
**What it does:**
- Validates configuration
- Creates necessary directories
- Builds and starts Docker containers
- Shows initial logs

**When to use:** Starting the bot after initial setup or after stopping it

---

### monitor.sh
**Purpose:** Check bot status and health
**Usage:** `./monitor.sh`
**What it shows:**
- Container status
- Health check results
- Resource usage (CPU, memory)
- Recent logs
- Database statistics
- Recent trades
- Open positions

**When to use:** Regular monitoring, debugging issues

---

### stats.sh
**Purpose:** Detailed performance analytics
**Usage:** `./stats.sh`
**What it shows:**
- Overall performance metrics
- Daily performance breakdown
- Performance by symbol
- Performance by side (LONG/SHORT)
- Hourly patterns
- Monthly statistics
- Risk metrics (Sharpe ratio, profit factor, etc.)

**When to use:** Performance review, optimization decisions

---

### stop_trading.sh
**Purpose:** Emergency stop trading
**Usage:** `./stop_trading.sh`
**What it does:**
- Sets TRADING_PAUSED=true in .env
- Sends Telegram alert
- Note: You still need to run `docker compose down` to fully stop

**When to use:** Emergency situations, suspected issues

---

### backup.sh
**Purpose:** Manual database backup
**Usage:** `./backup.sh`
**What it does:**
- Creates timestamped backup of trades.db
- Stores in backups/ directory
- Automatically runs daily at 2 AM via cron

**When to use:** Before major changes, manual backups

---

### capital_manager.py
**Purpose:** Capital scaling logic (runs automatically)
**What it does:**
- Analyzes last 50 trades
- Determines if conditions are right to scale up capital
- Used internally by the bot

**When to use:** Automatic, no manual intervention needed

---

## File Overview

### DEPLOYMENT_GUIDE.md
Complete deployment documentation covering:
- Step-by-step setup instructions
- Configuration guide
- Management commands
- Monitoring procedures
- Troubleshooting
- Security best practices
- Moving to live trading

### preflight_checklist.md
Pre-deployment checklist (currently basic)

## Typical Workflows

### First Time Deployment
```bash
# 1. Clone repository
git clone <repo-url> ~/alpha-sniper-v2.2
cd ~/alpha-sniper-v2.2

# 2. Run setup
sudo ./deployment/setup_server.sh

# 3. Configure
nano .env

# 4. Start
./deployment/quick_start.sh

# 5. Monitor
./deployment/monitor.sh
```

### Daily Operations
```bash
# Morning check
./deployment/monitor.sh

# Review performance
./deployment/stats.sh

# Watch logs
docker compose logs -f
```

### After Code Updates
```bash
# Stop bot
docker compose down

# Backup database
./deployment/backup.sh

# Pull latest code
git pull

# Rebuild and start
docker compose build
docker compose up -d

# Monitor
docker compose logs -f
```

### Troubleshooting
```bash
# Check status
./deployment/monitor.sh

# View detailed logs
docker compose logs --tail=100

# Check container status
docker ps -a

# Restart
docker compose restart

# Full rebuild
docker compose down
docker compose build --no-cache
docker compose up -d
```

## Directory Structure
```
deployment/
├── README.md                   # This file
├── DEPLOYMENT_GUIDE.md         # Complete deployment docs
├── setup_server.sh             # Fresh server setup
├── quick_start.sh              # Quick start script
├── monitor.sh                  # Status monitoring
├── stats.sh                    # Performance statistics
├── stop_trading.sh             # Emergency stop
├── backup.sh                   # Database backup
├── capital_manager.py          # Capital scaling logic
└── preflight_checklist.md      # Pre-deployment checklist
```

## Security Notes

1. **Never commit .env** - Contains sensitive API keys and tokens
2. **Keep scripts executable** - Ensure proper permissions (chmod +x)
3. **Run setup as root** - setup_server.sh requires sudo
4. **Monitor regularly** - Use monitor.sh daily
5. **Backup frequently** - Automatic backups run daily, but manual backups before changes

## Support

For issues or questions:
1. Check logs: `docker compose logs -f`
2. Review DEPLOYMENT_GUIDE.md
3. Run monitor.sh for diagnostics
4. Check CRITICAL_ISSUES.md in project root

## Emergency Procedures

### Bot Misbehaving
```bash
# Quick stop
./deployment/stop_trading.sh
docker compose down
```

### Suspected Database Corruption
```bash
# Stop bot
docker compose down

# Backup current DB
cp data/trades.db backups/emergency_$(date +%Y%m%d_%H%M%S).db

# Check integrity
sqlite3 data/trades.db "PRAGMA integrity_check;"

# If corrupted, restore from backup
cp backups/trades_YYYYMMDD_HHMMSS.db data/trades.db
```

### Lost Connection
```bash
# Check container
docker ps -a

# Check logs
docker compose logs --tail=100

# Restart
docker compose restart

# If still failing, rebuild
docker compose down
docker compose build
docker compose up -d
```

## Best Practices

1. **Always start in SIM mode** for at least 7-14 days
2. **Monitor daily** using monitor.sh and Telegram alerts
3. **Review statistics weekly** using stats.sh
4. **Backup before changes** using backup.sh
5. **Test config changes in SIM** before switching to LIVE
6. **Keep logs** for at least 30 days
7. **Update regularly** but test changes in SIM first
8. **Never skip security updates** - Run `sudo apt update && sudo apt upgrade` regularly

## Additional Resources

- [Docker Docs](https://docs.docker.com/)
- [Docker Compose Docs](https://docs.docker.com/compose/)
- [MEXC API Docs](https://mexcdevelop.github.io/apidocs/)
- Project CRITICAL_ISSUES.md for known risks
