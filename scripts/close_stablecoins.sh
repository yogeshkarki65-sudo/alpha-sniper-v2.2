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
WHERE exit_reason IS NULL
AND (
    symbol LIKE '%USDC%' OR
    symbol LIKE '%USDE%' OR
    symbol LIKE '%DAI%' OR
    symbol LIKE '%TUSD%' OR
    symbol LIKE '%BUSD%' OR
    symbol LIKE '%FDUSD%'
);
EOF

echo ""
echo "⚠️  Closing stablecoin positions (break-even exit)..."

# Close them at entry price (break-even)
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db <<EOF
UPDATE positions
SET
    exit_reason = 'MANUAL_STABLECOIN',
    exit_price = entry_price,
    closed_at = datetime('now'),
    pnl = -0.10  -- Account for 0.1% taker fee on exit
WHERE exit_reason IS NULL
AND (
    symbol LIKE '%USDC%' OR
    symbol LIKE '%USDE%' OR
    symbol LIKE '%DAI%' OR
    symbol LIKE '%TUSD%' OR
    symbol LIKE '%BUSD%' OR
    symbol LIKE '%FDUSD%'
);
EOF

echo "✅ Stablecoin positions closed!"
echo ""
echo "📊 Current open positions:"
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db "SELECT COUNT(*) as open_positions FROM positions WHERE exit_reason IS NULL;"

echo ""
echo "🚀 Bot can now trade real coins!"
