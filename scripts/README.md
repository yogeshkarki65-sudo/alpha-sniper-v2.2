# Alpha Sniper Monitoring Scripts

Simple copy-paste scripts to monitor your bot.

## Quick Start

All scripts are in the `scripts/` directory. Just run them!

### 1. Check Status
```bash
./scripts/check_status.sh
```
Shows current version, equity, P&L, and positions.

### 2. Check P&L
```bash
./scripts/check_pnl.sh
```
Shows today's and this week's P&L summary.

### 3. Watch Live Logs
```bash
./scripts/watch_logs.sh
```
Shows live activity (press Ctrl+C to stop).

### 4. Recent Trades
```bash
./scripts/recent_trades.sh
```
Shows last 10 trades with details.

### 5. Open Positions
```bash
./scripts/open_positions.sh
```
Shows all currently open positions.

---

## One-Time Setup

Make scripts executable (only need to do this once):
```bash
chmod +x scripts/*.sh
```

---

## Manual Commands

If you prefer manual commands:

**Status:**
```bash
curl http://localhost:8090/health
```

**Live logs:**
```bash
docker logs -f alpha-sniper-v2
```

**Last 50 lines:**
```bash
docker logs --tail 50 alpha-sniper-v2
```

**Restart bot:**
```bash
docker compose restart
```

---

**Most important:** Check Telegram - you get daily reports automatically!
