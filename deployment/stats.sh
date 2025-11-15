#!/bin/bash

# Alpha Sniper V2 - Detailed Statistics
# Provides detailed performance analytics

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

DB_PATH="/app/data/trades.db"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Alpha Sniper V2 - Statistics${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Overall Performance
echo -e "${CYAN}[Overall Performance]${NC}"
docker compose exec -T alpha-sniper sqlite3 $DB_PATH <<EOF
SELECT
    'Total Trades: ' || COUNT(*) ||
    '\nWin Rate: ' || ROUND(100.0 * SUM(CASE WHEN net_pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) || '%' ||
    '\nTotal P&L: $' || ROUND(SUM(net_pnl_usd), 2) ||
    '\nAvg P&L per Trade: $' || ROUND(AVG(net_pnl_usd), 2) ||
    '\nAvg P&L %: ' || ROUND(AVG(pnl_pct), 2) || '%' ||
    '\nBest Trade: ' || ROUND(MAX(pnl_pct), 2) || '%' ||
    '\nWorst Trade: ' || ROUND(MIN(pnl_pct), 2) || '%' ||
    '\nAvg Hold Time: ' || ROUND(AVG(hold_time_minutes), 1) || ' minutes'
FROM trades;
EOF
echo ""

# Last 7 Days
echo -e "${CYAN}[Last 7 Days Performance]${NC}"
docker compose exec -T alpha-sniper sqlite3 $DB_PATH <<EOF
.mode column
.headers on
SELECT
    DATE(timestamp) as Date,
    COUNT(*) as Trades,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) || '%' as WinRate,
    '$' || ROUND(SUM(net_pnl_usd), 2) as PnL,
    ROUND(AVG(pnl_pct), 2) || '%' as AvgPnL
FROM trades
WHERE timestamp > datetime('now', '-7 days')
GROUP BY DATE(timestamp)
ORDER BY Date DESC;
EOF
echo ""

# Performance by Symbol
echo -e "${CYAN}[Top 10 Symbols by Trade Count]${NC}"
docker compose exec -T alpha-sniper sqlite3 $DB_PATH <<EOF
.mode column
.headers on
SELECT
    symbol as Symbol,
    COUNT(*) as Trades,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) || '%' as WinRate,
    '$' || ROUND(SUM(net_pnl_usd), 2) as TotalPnL,
    ROUND(AVG(pnl_pct), 2) || '%' as AvgPnL
FROM trades
GROUP BY symbol
ORDER BY COUNT(*) DESC
LIMIT 10;
EOF
echo ""

# Performance by Side (LONG vs SHORT)
echo -e "${CYAN}[Performance by Side]${NC}"
docker compose exec -T alpha-sniper sqlite3 $DB_PATH <<EOF
.mode column
.headers on
SELECT
    side as Side,
    COUNT(*) as Trades,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) || '%' as WinRate,
    '$' || ROUND(SUM(net_pnl_usd), 2) as TotalPnL,
    ROUND(AVG(pnl_pct), 2) || '%' as AvgPnL
FROM trades
GROUP BY side;
EOF
echo ""

# Hourly Performance Pattern
echo -e "${CYAN}[Performance by Hour of Day (UTC)]${NC}"
docker compose exec -T alpha-sniper sqlite3 $DB_PATH <<EOF
.mode column
.headers on
SELECT
    CAST(strftime('%H', timestamp) as INTEGER) as Hour,
    COUNT(*) as Trades,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) || '%' as WinRate,
    '$' || ROUND(SUM(net_pnl_usd), 2) as PnL
FROM trades
GROUP BY Hour
ORDER BY Hour;
EOF
echo ""

# Monthly Performance
echo -e "${CYAN}[Monthly Performance]${NC}"
docker compose exec -T alpha-sniper sqlite3 $DB_PATH <<EOF
.mode column
.headers on
SELECT
    strftime('%Y-%m', timestamp) as Month,
    COUNT(*) as Trades,
    ROUND(100.0 * SUM(CASE WHEN net_pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) || '%' as WinRate,
    '$' || ROUND(SUM(net_pnl_usd), 2) as PnL,
    ROUND(AVG(pnl_pct), 2) || '%' as AvgPnL
FROM trades
GROUP BY Month
ORDER BY Month DESC;
EOF
echo ""

# Risk Metrics
echo -e "${CYAN}[Risk Metrics]${NC}"
docker compose exec -T alpha-sniper sqlite3 $DB_PATH <<EOF
SELECT
    'Sharpe Ratio (approx): ' || ROUND(AVG(pnl_pct) / NULLIF(STDEV(pnl_pct), 0), 2) ||
    '\nMax Drawdown: ' || ROUND(MIN(pnl_pct), 2) || '%' ||
    '\nProfit Factor: ' || ROUND(
        SUM(CASE WHEN net_pnl_usd > 0 THEN net_pnl_usd ELSE 0 END) /
        NULLIF(ABS(SUM(CASE WHEN net_pnl_usd < 0 THEN net_pnl_usd ELSE 0 END)), 0),
    2) ||
    '\nAvg Win: ' || ROUND(AVG(CASE WHEN net_pnl_usd > 0 THEN pnl_pct END), 2) || '%' ||
    '\nAvg Loss: ' || ROUND(AVG(CASE WHEN net_pnl_usd < 0 THEN pnl_pct END), 2) || '%'
FROM trades;

-- Note: SQLite doesn't have STDEV by default, using approximation
SELECT 'StdDev P&L%: ' || ROUND(
    SQRT(AVG(pnl_pct * pnl_pct) - AVG(pnl_pct) * AVG(pnl_pct)), 2
) || '%' FROM trades;
EOF
echo ""

# Current Status
echo -e "${CYAN}[Current Status]${NC}"
HEALTH=$(curl -s http://localhost:80/health 2>/dev/null)
if [ -n "$HEALTH" ]; then
    echo "$HEALTH" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Mode: {data.get('mode', 'N/A')}\"); print(f\"Equity: \${data.get('equity', 'N/A')}\"); print(f\"Open Positions: {data.get('open_positions', 'N/A')}\"); print(f\"Trading Paused: {data.get('trading_paused', 'N/A')}\")" 2>/dev/null || echo "Unable to parse health data"
else
    echo "Health endpoint unavailable"
fi
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Statistics complete!${NC}"
echo -e "${BLUE}========================================${NC}"
