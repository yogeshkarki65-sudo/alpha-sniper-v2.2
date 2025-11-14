#!/bin/bash
# Show recent trades

echo "========================================="
echo "📊 ALPHA SNIPER - RECENT TRADES"
echo "========================================="
echo ""

docker exec alpha-sniper-v2 sqlite3 -header -column /app/data/trades.db << 'SQL'
SELECT
    symbol,
    ROUND(entry_price, 4) as entry,
    ROUND(exit_price, 4) as exit,
    ROUND(net_pnl_usd, 2) as pnl_usd,
    ROUND(pnl_pct, 2) || '%' as pnl_pct,
    exit_reason,
    substr(closed_at, 1, 16) as closed_at
FROM trades
ORDER BY closed_at DESC
LIMIT 10;
SQL

echo ""
echo "========================================="
