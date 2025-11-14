import schedule
import time
from datetime import datetime

from config.config import config
from scanner.scanner import run_scanner
from trader.trader import run_trader
from learning.self_trainer import run_self_learning
from monitoring.reporter import generate_daily_report
from monitoring.healthcheck import start_healthcheck_server
from monitoring import healthcheck as hc
from monitoring.telegram_alerter import send_alert
from monitoring.version import get_full_version_string, get_version_info
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

def main():
    print("=" * 60)
    print("🚀 ALPHA SNIPER V2 - Starting...")
    print("=" * 60)

    # Display version information
    version_str = get_full_version_string()
    version_info = get_version_info()
    print(f"📦 {version_str}")
    print("=" * 60)

    start_healthcheck_server()
    print("✅ Health check server started on port 8080")

    # Send startup alert with version info
    commit_short = version_info.get('git_commit', 'unknown')[:7] if version_info.get('git_commit') != 'unknown' else 'unknown'
    send_alert(f"🚀 Alpha Sniper V2 started successfully\n📦 Version: {version_info['version']} (commit: {commit_short})")
    
    schedule.every(config.SCANNER_INTERVAL).seconds.do(scanner_job)
    schedule.every(config.TRADER_INTERVAL).seconds.do(trader_job)
    schedule.every(config.LEARNING_INTERVAL).seconds.do(learning_job)
    
    schedule.every().day.at(f"{config.DAILY_REPORT_HOUR:02d}:00").do(report_job)
    schedule.every().day.at("00:00").do(daily_reset_job)
    schedule.every(1).hours.do(capital_scale_job)
    
    print(f"📅 Scanner runs every {config.SCANNER_INTERVAL}s")
    print(f"💼 Trader runs every {config.TRADER_INTERVAL}s")
    print(f"🧠 Learning runs every {config.LEARNING_INTERVAL}s")
    print(f"📊 Daily report at {config.DAILY_REPORT_HOUR}:00 UTC")
    print("=" * 60)
    
    scanner_job()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
