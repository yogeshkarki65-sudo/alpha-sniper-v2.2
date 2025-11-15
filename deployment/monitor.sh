#!/bin/bash

# Alpha Sniper V2 - Monitoring Script
# Run this to check bot status, performance, and health

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Alpha Sniper V2 - Status Monitor${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running
if ! docker ps | grep -q alpha-sniper-v2; then
    echo -e "${RED}❌ Bot is NOT running!${NC}"
    echo -e "${YELLOW}Start with: docker compose up -d${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Bot is running${NC}"
echo ""

# Container status
echo -e "${CYAN}[Container Status]${NC}"
docker ps --filter "name=alpha-sniper-v2" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Health check
echo -e "${CYAN}[Health Check]${NC}"
HEALTH=$(curl -s http://localhost:8090/health 2>/dev/null || echo '{"error": "Health endpoint unreachable"}')
echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
echo ""

# Resource usage
echo -e "${CYAN}[Resource Usage]${NC}"
docker stats alpha-sniper-v2 --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}"
echo ""

# Recent logs (last 20 lines)
echo -e "${CYAN}[Recent Logs (last 20 lines)]${NC}"
docker logs alpha-sniper-v2 --tail 20
echo ""

# Check for errors in recent logs
ERROR_COUNT=$(docker logs alpha-sniper-v2 --tail 100 | grep -i error | wc -l)
if [ $ERROR_COUNT -gt 0 ]; then
    echo -e "${YELLOW}⚠ Found $ERROR_COUNT error(s) in last 100 log lines${NC}"
    echo -e "${YELLOW}Recent errors:${NC}"
    docker logs alpha-sniper-v2 --tail 100 | grep -i error | tail -5
    echo ""
fi

# Database stats (if accessible)
echo -e "${CYAN}[Database Statistics]${NC}"
DB_STATS=$(docker compose exec -T alpha-sniper sqlite3 /app/data/trades.db \
    "SELECT
        COUNT(*) as total_trades,
        COUNT(CASE WHEN pnl_usd > 0 THEN 1 END) as wins,
        COUNT(CASE WHEN pnl_usd < 0 THEN 1 END) as losses,
        ROUND(100.0 * COUNT(CASE WHEN pnl_usd > 0 THEN 1 END) / COUNT(*), 2) as win_rate,
        ROUND(SUM(pnl_usd), 2) as total_pnl,
        ROUND(AVG(pnl_pct), 2) as avg_pnl_pct,
        ROUND(MAX(pnl_pct), 2) as max_win_pct,
        ROUND(MIN(pnl_pct), 2) as max_loss_pct
    FROM trades;" 2>/dev/null || echo "Unable to query database")

if [ "$DB_STATS" != "Unable to query database" ]; then
    echo "Total Trades: $(echo $DB_STATS | cut -d'|' -f1)"
    echo "Wins: $(echo $DB_STATS | cut -d'|' -f2)"
    echo "Losses: $(echo $DB_STATS | cut -d'|' -f3)"
    echo "Win Rate: $(echo $DB_STATS | cut -d'|' -f4)%"
    echo "Total P&L: \$$(echo $DB_STATS | cut -d'|' -f5)"
    echo "Avg P&L: $(echo $DB_STATS | cut -d'|' -f6)%"
    echo "Best Trade: $(echo $DB_STATS | cut -d'|' -f7)%"
    echo "Worst Trade: $(echo $DB_STATS | cut -d'|' -f8)%"
else
    echo "$DB_STATS"
fi
echo ""

# Disk usage
echo -e "${CYAN}[Disk Usage]${NC}"
du -sh data/ logs/ backups/ 2>/dev/null || echo "Directories not accessible"
echo ""

# Recent trades
echo -e "${CYAN}[Last 5 Trades]${NC}"
docker compose exec -T alpha-sniper sqlite3 /app/data/trades.db \
    "SELECT timestamp, symbol, side, entry_price, exit_price, pnl_pct, pnl_usd FROM trades ORDER BY timestamp DESC LIMIT 5;" 2>/dev/null | \
    column -t -s '|' || echo "Unable to query trades"
echo ""

# Open positions
echo -e "${CYAN}[Open Positions]${NC}"
OPEN_POS=$(docker compose exec -T alpha-sniper sqlite3 /app/data/trades.db \
    "SELECT symbol, side, entry_price, quantity, entry_time FROM trades WHERE exit_time IS NULL;" 2>/dev/null)

if [ -z "$OPEN_POS" ]; then
    echo "No open positions"
else
    echo "$OPEN_POS" | column -t -s '|'
fi
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Monitoring complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "For live logs: ${CYAN}docker compose logs -f${NC}"
echo -e "For detailed stats: ${CYAN}./deployment/stats.sh${NC}"
