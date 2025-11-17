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
from risk.daily_reset import run_daily_reset
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
        import traceback
        traceback.print_exc()

def trader_job():
    """Trader job - runs every 1 minute"""
    if config.TRADING_PAUSED:
        return

    print(f"[{datetime.now()}] ━━━ TRADER JOB (V2) ━━━")
    try:
        run_trader()
    except Exception as e:
        print(f"[main] ❌ Trader error: {e}")
        import traceback
        traceback.print_exc()

def daily_reset_job():
    """Daily reset job"""
    print(f"[{datetime.now()}] ━━━ DAILY RESET ━━━")
    try:
        run_daily_reset()
    except Exception as e:
        print(f"[main] ❌ Daily reset error: {e}")
        import traceback
        traceback.print_exc()

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
