#!/bin/bash
# Diagnostic script to check why bot isn't catching trades

echo "=========================================="
echo "🔍 ALPHA SNIPER TRADING DIAGNOSTICS"
echo "=========================================="
echo ""

echo "📊 1. RECENT LOGS (Last 50 lines):"
echo "------------------------------------------"
docker logs --tail 50 alpha-sniper-v2 2>&1
echo ""

echo "📡 2. SCANNER ACTIVITY (Last 20 lines):"
echo "------------------------------------------"
docker logs alpha-sniper-v2 2>&1 | grep -E "scanner|Signal|signal" | tail -20
echo ""

echo "💰 3. TRADER ACTIVITY (Last 20 lines):"
echo "------------------------------------------"
docker logs alpha-sniper-v2 2>&1 | grep -E "trader|Trader|ENTRY|EXIT|Position" | tail -20
echo ""

echo "⚠️  4. ERRORS (Last 10):"
echo "------------------------------------------"
docker logs alpha-sniper-v2 2>&1 | grep -iE "error|exception|failed|traceback" | tail -10
echo ""

echo "💾 5. DATABASE - SIGNALS:"
echo "------------------------------------------"
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db "SELECT COUNT(*) as total_signals, SUM(CASE WHEN consumed=1 THEN 1 ELSE 0 END) as consumed, SUM(CASE WHEN consumed=0 THEN 1 ELSE 0 END) as unconsumed FROM signals;"
echo ""

echo "📈 6. DATABASE - RECENT SIGNALS (Last 5):"
echo "------------------------------------------"
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db "SELECT symbol, score, consumed, datetime(created_at, 'unixepoch', 'localtime') as time FROM signals ORDER BY created_at DESC LIMIT 5;"
echo ""

echo "💼 7. DATABASE - OPEN POSITIONS:"
echo "------------------------------------------"
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db "SELECT id, symbol, ROUND(entry_price, 6) as entry, ROUND(stop_loss_price, 6) as SL, ROUND(take_profit_price, 6) as TP, datetime(opened_at_timestamp, 'unixepoch', 'localtime') as opened FROM positions;"
echo ""

echo "📊 8. DATABASE - CLOSED TRADES:"
echo "------------------------------------------"
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db "SELECT symbol, exit_reason, ROUND(pnl_pct, 2) as pnl_pct, datetime(closed_at, 'localtime') as closed FROM trades ORDER BY id DESC LIMIT 5;"
echo ""

echo "📈 9. DATABASE - STATS:"
echo "------------------------------------------"
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db "SELECT (SELECT COUNT(*) FROM positions) as open_positions, (SELECT COUNT(*) FROM trades) as closed_trades, (SELECT ROUND(SUM(net_pnl_usd), 2) FROM trades) as total_pnl;"
echo ""

echo "🏥 10. HEALTH ENDPOINT:"
echo "------------------------------------------"
curl -s http://localhost:8090/health | python3 -m json.tool
echo ""

echo "⚙️  11. CURRENT CONFIGURATION:"
echo "------------------------------------------"
docker exec alpha-sniper-v2 sh -c 'echo "SCANNER_INTERVAL: $SCANNER_INTERVAL"; echo "MIN_SIGNAL_SCORE: $MIN_SIGNAL_SCORE"; echo "MAX_DAILY_DRAWDOWN_PCT: $MAX_DAILY_DRAWDOWN_PCT"; echo "MAX_POSITION_RISK_PCT: $MAX_POSITION_RISK_PCT"; echo "MAX_OPEN_POSITIONS: $MAX_OPEN_POSITIONS"; echo "MOON_MULT: $MOON_MULT"'
echo ""

echo "=========================================="
echo "✅ DIAGNOSTICS COMPLETE"
echo "=========================================="
