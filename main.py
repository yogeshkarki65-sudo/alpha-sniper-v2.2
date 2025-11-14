import schedule
import time
from datetime import datetime

from config.config import config
from scanner.scanner import run_scanner
from trader.trader import run_trader
from learning.self_trainer import run_self_learning
from monitoring.reporter import generate_daily_report
from monitoring.healthcheck import start_healthcheck_server
from monitoring.emergency import start_emergency_server
from monitoring import healthcheck as hc
from monitoring.telegram_alerter import send_alert
from risk.daily_reset import run_daily_reset
from deployment.capital_manager import check_scale_up
from database.models import db

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

def recover_positions():
    """Recover open positions on restart to prevent double-ins."""
    try:
        open_positions = db.get_open_positions()
        if open_positions:
            print(f"🔄 RECOVERING {len(open_positions)} open positions from previous session")
            for pos in open_positions:
                symbol = pos[2]
                entry_price = pos[3]
                position_size = pos[4]
                opened_at_ts = pos[11]
                position_value = entry_price * position_size
                send_alert(
                    f"🔄 RECOVERED POSITION\n"
                    f"Symbol: {symbol}\n"
                    f"Entry: ${entry_price:.6f}\n"
                    f"Size: {position_size:.4f}\n"
                    f"Value: ${position_value:.2f}\n"
                    f"Opened: {datetime.fromtimestamp(opened_at_ts).strftime('%Y-%m-%d %H:%M:%S')}"
                )
            print(f"✅ Successfully recovered {len(open_positions)} positions")
        else:
            print("✅ No positions to recover")
    except Exception as e:
        print(f"⚠️  Error recovering positions: {e}")
        send_alert(f"⚠️  Position Recovery Error: {str(e)}")

def main():
    print("=" * 60)
    print("🚀 ALPHA SNIPER V2 - Starting...")
    print("=" * 60)
    
    start_healthcheck_server()
    print("✅ Health check server started on port 8080")

    start_emergency_server(port=8081)
    print("✅ Emergency endpoint started on port 8081")

    # Recover any open positions from previous session
    recover_positions()

    send_alert("🚀 Alpha Sniper V2 started successfully")
    
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
