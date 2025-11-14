#!/bin/bash
# Check P&L for Alpha Sniper bot

echo "========================================="
echo "💰 ALPHA SNIPER - P&L SUMMARY"
echo "========================================="
echo ""

docker exec alpha-sniper-v2 sqlite3 -header -column /app/data/trades.db << 'SQL'
SELECT
    'Today' as Period,
    COUNT(*) as Trades,
    ROUND(SUM(net_pnl_usd), 2) as PnL_USD,
    ROUND(AVG(pnl_pct), 2) as Avg_PnL_Pct,
    ROUND(SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) || '%' as Win_Rate
FROM trades
WHERE DATE(closed_at) = DATE('now')
UNION ALL
SELECT
    'This Week',
    COUNT(*),
    ROUND(SUM(net_pnl_usd), 2),
    ROUND(AVG(pnl_pct), 2),
    ROUND(SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) || '%'
FROM trades
WHERE closed_at > datetime('now', '-7 days');
SQL

echo ""
echo "========================================="
