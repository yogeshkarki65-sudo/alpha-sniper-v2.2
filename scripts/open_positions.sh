#!/bin/bash
# Show open positions

echo "========================================="
echo "📈 ALPHA SNIPER - OPEN POSITIONS"
echo "========================================="
echo ""

docker exec alpha-sniper-v2 sqlite3 -header -column /app/data/trades.db << 'SQL'
SELECT
    symbol,
    ROUND(entry_price, 4) as entry,
    ROUND(position_size, 2) as size,
    ROUND(stop_loss_price, 4) as stop_loss,
    ROUND(take_profit_price, 4) as take_profit,
    CASE WHEN trailing_stop_active = 1 THEN 'YES' ELSE 'NO' END as trailing,
    substr(datetime(opened_at_timestamp, 'unixepoch'), 1, 16) as opened_at
FROM positions;
SQL

COUNT=$(docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db "SELECT COUNT(*) FROM positions")

echo ""
echo "Total open positions: $COUNT"
echo "========================================="
