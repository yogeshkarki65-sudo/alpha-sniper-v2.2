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
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db "SELECT symbol, entry_price, current_pnl_pct, status, datetime(opened_at_timestamp, 'unixepoch', 'localtime') as opened FROM positions WHERE status='OPEN';"
echo ""

echo "📊 8. DATABASE - ALL POSITIONS:"
echo "------------------------------------------"
docker exec alpha-sniper-v2 sqlite3 /app/data/trades.db "SELECT COUNT(*) as total, SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) as open, SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END) as closed FROM positions;"
echo ""

echo "🏥 9. HEALTH ENDPOINT:"
echo "------------------------------------------"
curl -s http://localhost:8090/health | python3 -m json.tool
echo ""

echo "⚙️  10. CURRENT CONFIGURATION:"
echo "------------------------------------------"
docker exec alpha-sniper-v2 sh -c 'echo "SCANNER_INTERVAL: $SCANNER_INTERVAL"; echo "MIN_SIGNAL_SCORE: $MIN_SIGNAL_SCORE"; echo "MAX_DAILY_DRAWDOWN_PCT: $MAX_DAILY_DRAWDOWN_PCT"; echo "MAX_POSITION_RISK_PCT: $MAX_POSITION_RISK_PCT"; echo "MAX_OPEN_POSITIONS: $MAX_OPEN_POSITIONS"; echo "MOON_MULT: $MOON_MULT"'
echo ""

echo "=========================================="
echo "✅ DIAGNOSTICS COMPLETE"
echo "=========================================="
