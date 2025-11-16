import schedule
import time
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from config.config import config
from scanner.scanner import run_scanner
from trader.trader import run_trader
from learning.self_trainer import run_self_learning
from monitoring.reporter import generate_daily_report
from monitoring.healthcheck import start_healthcheck_server
from monitoring import healthcheck as hc
from monitoring.telegram_alerter import send_alert
from monitoring.observer import get_observer
from monitoring.v42_fallback import apply_v42_fallback
from monitoring.telegram_bot import start_telegram_bot
from scanner.validator import get_filter_config_summary
from risk.daily_reset import run_daily_reset
from deployment.capital_manager import check_scale_up

def scanner_job():
    try:
        run_scanner()
        hc.last_scanner_run = datetime.now()
    except Exception as e:
        print(f"Scanner error: {e}")
        send_alert(f"⚠️ Scanner Error: {str(e)}")

def trader_job():
    try:
        run_trader()
        hc.last_trader_run = datetime.now()
    except Exception as e:
        print(f"Trader error: {e}")
        send_alert(f"⚠️ Trader Error: {str(e)}")

def learning_job():
    try:
        run_self_learning()
    except Exception as e:
        print(f"Learning error: {e}")
        send_alert(f"⚠️ Learning Error: {str(e)}")

def report_job():
    try:
        generate_daily_report()
    except Exception as e:
        print(f"Report error: {e}")
        send_alert(f"⚠️ Report Error: {str(e)}")

def daily_reset_job():
    try:
        run_daily_reset()
    except Exception as e:
        print(f"Daily reset error: {e}")
        send_alert(f"⚠️ Daily Reset Error: {str(e)}")

def capital_scale_job():
    try:
        check_scale_up()
    except Exception as e:
        print(f"Capital manager error: {e}")

def observer_loop():
    """
    Background thread that checks hourly if v4.2 fallback should be activated
    Activates when v4.1.1 has run for 6+ hours with zero signals
    """
    try:
        while True:
            time.sleep(3600)  # Check every hour

            observer = get_observer()
            if observer.should_activate_v42():
                apply_v42_fallback()
                observer.mark_v42_activated()
                break  # Stop checking once activated

    except Exception as e:
        logger.error(f"Observer loop error: {e}")
        send_alert(f"⚠️ Observer Loop Error: {str(e)}")

def main():
    print("\n" + "=" * 60)
    print("🚀 ALPHA SNIPER V4.1.1 - Starting...")
    print("=" * 60)

    # Display comprehensive filter configuration
    print(get_filter_config_summary())

    # Initialize performance observer
    observer = get_observer()
    print("✅ v4.1.1 LIVE | Observer Active | Monitoring for 6h")

    # Start Telegram bot with command handlers
    start_telegram_bot()

    # Start observer loop in background thread
    observer_thread = threading.Thread(target=observer_loop, daemon=True)
    observer_thread.start()
    print("✅ Observer loop started (checks hourly for v4.2 fallback)")

    start_healthcheck_server()
    print("✅ Health check server started on port 8080")

    # Show runtime configuration
    print(f"\n📅 Scheduler Configuration:")
    print(f"  • Scanner: every {config.SCANNER_INTERVAL}s")
    print(f"  • Trader: every {config.TRADER_INTERVAL}s")
    print(f"  • Learning: every {config.LEARNING_INTERVAL}s")
    print(f"  • Daily report: {config.DAILY_REPORT_HOUR}:00 UTC")
    print(f"  • Mode: {config.MODE}")
    print("=" * 60 + "\n")

    send_alert("🚀 Alpha Sniper v4.1.1 started successfully\n\nPerformance monitoring active - /status for stats")

    schedule.every(config.SCANNER_INTERVAL).seconds.do(scanner_job)
    schedule.every(config.TRADER_INTERVAL).seconds.do(trader_job)
    schedule.every(config.LEARNING_INTERVAL).seconds.do(learning_job)

    schedule.every().day.at(f"{config.DAILY_REPORT_HOUR:02d}:00").do(report_job)
    schedule.every().day.at("00:00").do(daily_reset_job)
    schedule.every(1).hours.do(capital_scale_job)
    
    scanner_job()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
