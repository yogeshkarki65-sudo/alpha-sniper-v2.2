#!/bin/bash
# Show what the scanner is seeing right now

echo "========================================="
echo "🔍 SCANNER DEBUG - Current Market Scores"
echo "========================================="
echo ""

docker exec alpha-sniper-v2 python3 /app/monitoring/scanner_debug.py
