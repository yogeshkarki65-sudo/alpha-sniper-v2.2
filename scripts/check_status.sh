#!/bin/bash
# Quick status check for Alpha Sniper bot

echo "========================================="
echo "🤖 ALPHA SNIPER - STATUS CHECK"
echo "========================================="
echo ""

# Health check
curl -s http://localhost:8090/health | python3 -m json.tool

echo ""
echo "========================================="
