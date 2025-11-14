#!/bin/bash
# Watch live logs from Alpha Sniper bot

echo "========================================="
echo "📝 ALPHA SNIPER - LIVE LOGS"
echo "========================================="
echo "Press Ctrl+C to stop"
echo ""

docker logs -f alpha-sniper-v2
