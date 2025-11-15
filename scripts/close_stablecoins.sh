#!/bin/bash
# Close stablecoin positions manually (they'll never hit TP/SL)

echo "🔍 Finding stablecoin positions..."

# Find stablecoin positions (USDC, USDT, USDE, etc.)
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db <<EOF
SELECT
    id,
    symbol,
    entry_price,
    ROUND((julianday('now') - julianday(opened_at)) * 24, 1) as hours_open
FROM positions
WHERE (
    symbol LIKE '%USDC%' OR
    symbol LIKE '%USDE%' OR
    symbol LIKE '%DAI%' OR
    symbol LIKE '%TUSD%' OR
    symbol LIKE '%BUSD%' OR
    symbol LIKE '%FDUSD%'
);
EOF

echo ""
echo "⚠️  Deleting stablecoin positions from database..."

# Delete stablecoin positions (positions table doesn't have exit_reason column)
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db <<EOF
DELETE FROM positions
WHERE (
    symbol LIKE '%USDC%' OR
    symbol LIKE '%USDE%' OR
    symbol LIKE '%DAI%' OR
    symbol LIKE '%TUSD%' OR
    symbol LIKE '%BUSD%' OR
    symbol LIKE '%FDUSD%'
);
EOF

echo "✅ Stablecoin positions removed!"
echo ""
echo "📊 Current open positions:"
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db "SELECT COUNT(*) as remaining FROM positions;"

echo ""
echo "🚀 Bot can now trade real coins!"
