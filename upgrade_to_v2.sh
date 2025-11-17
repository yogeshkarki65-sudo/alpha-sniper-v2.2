#!/bin/bash

# Alpha Sniper V2.2 Upgrade Script
# This script upgrades your server to use the new Alpha Sniper V2.2 strategy

echo "=================================================="
echo "  ALPHA SNIPER V2.2 UPGRADE SCRIPT"
echo "=================================================="
echo ""

# 1. Install new dependencies
echo "📦 Step 1/5: Installing new dependencies..."
pip install pyarrow==14.0.1
if [ $? -ne 0 ]; then
    echo "❌ Failed to install pyarrow"
    exit 1
fi
echo "✅ Dependencies installed"
echo ""

# 2. Backup current main.py
echo "💾 Step 2/5: Backing up current configuration..."
if [ -f "main.py" ]; then
    cp main.py main.py.backup
    echo "✅ Backed up main.py to main.py.backup"
fi

if [ -f ".env" ]; then
    cp .env .env.backup
    echo "✅ Backed up .env to .env.backup"
fi
echo ""

# 3. Create data directories
echo "📁 Step 3/5: Creating data directories..."
mkdir -p data/historical/15m
mkdir -p data/historical/1d
mkdir -p results/backtest
mkdir -p results/sensitivity
echo "✅ Directories created"
echo ""

# 4. Update main.py to use v2 scanner and trader
echo "🔄 Step 4/5: Updating main.py..."
cat > main_v2.py << 'EOFMAIN'
"""
Alpha Sniper V2.2 - Main Entry Point with Enhanced Strategy
"""

import os
import schedule
import time
from datetime import datetime

# Import v2 components
from scanner.scanner_v2 import run_scanner
from trader.trader_v2 import run_trader
from risk.daily_reset import reset_daily_equity
from learning.self_trainer import run_training
from monitoring.healthcheck import start_healthcheck_server
from database.models import db
from config.config import config

def scanner_job():
    """Scanner job - runs every 5 minutes"""
    if config.TRADING_PAUSED:
        print("[main] ⏸️  Trading is PAUSED")
        return

    print(f"[{datetime.now()}] ━━━ SCANNER JOB (V2) ━━━")
    try:
        run_scanner()
    except Exception as e:
        print(f"[main] ❌ Scanner error: {e}")

def trader_job():
    """Trader job - runs every 1 minute"""
    if config.TRADING_PAUSED:
        return

    print(f"[{datetime.now()}] ━━━ TRADER JOB (V2) ━━━")
    try:
        run_trader()
    except Exception as e:
        print(f"[main] ❌ Trader error: {e}")

def daily_reset_job():
    """Daily reset job"""
    print(f"[{datetime.now()}] ━━━ DAILY RESET ━━━")
    reset_daily_equity()

def learning_job():
    """Learning job - disabled by default in V2"""
    # Alpha Sniper V2.2 uses fixed scoring, not self-learning
    # Keep for backwards compatibility but don't run
    if config.LEARNING_ENABLED:
        print("[main] ⚠️  Self-learning disabled in V2 (using fixed strategy)")

def main():
    """Main function"""
    print("="*60)
    print("  🚀 ALPHA SNIPER V2.2 STARTING")
    print("="*60)
    print(f"  Mode: {config.MODE}")
    print(f"  Version: 2.2.0 (Enhanced Quant Strategy)")
    print("="*60)
    print("")

    # Initialize database
    db.init_db()

    # Start healthcheck server in background
    import threading
    health_thread = threading.Thread(target=start_healthcheck_server, daemon=True)
    health_thread.start()

    # Schedule jobs
    schedule.every(config.SCANNER_INTERVAL).seconds.do(scanner_job)
    schedule.every(config.TRADER_INTERVAL).seconds.do(trader_job)
    schedule.every().day.at("00:00").do(daily_reset_job)

    print("[main] ✅ Scheduled jobs:")
    print(f"  - Scanner: every {config.SCANNER_INTERVAL}s")
    print(f"  - Trader: every {config.TRADER_INTERVAL}s")
    print(f"  - Daily reset: 00:00 UTC")
    print("")

    # Run initial jobs
    print("[main] 🏃 Running initial jobs...")
    scanner_job()
    time.sleep(5)
    trader_job()
    print("")

    print("[main] ♾️  Entering main loop...")
    print("="*60)
    print("")

    # Main loop
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
EOFMAIN

echo "✅ Created main_v2.py"
echo ""

# 5. Final instructions
echo "🎉 Step 5/5: Upgrade complete!"
echo ""
echo "=================================================="
echo "  NEXT STEPS:"
echo "=================================================="
echo ""
echo "1. Review the new main_v2.py file"
echo "2. Test the strategy:"
echo "   python main_v2.py"
echo ""
echo "3. If everything works, replace main.py:"
echo "   mv main.py main.py.old"
echo "   mv main_v2.py main.py"
echo ""
echo "4. Optional - Run backtest to validate:"
echo "   python tests/backtest.py"
echo ""
echo "=================================================="
echo "  ROLLBACK (if needed):"
echo "=================================================="
echo ""
echo "If you want to go back to the old version:"
echo "   mv main.py.backup main.py"
echo "   mv .env.backup .env"
echo ""
echo "=================================================="
