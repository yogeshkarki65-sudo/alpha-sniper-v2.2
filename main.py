"""
ALPHA SNIPER V4.1 - SNIPER SWING
Main orchestrator: Scanner + Trader loops with monitoring
"""
import schedule
import time
from datetime import datetime

from config.config import config
from config.logging_config import logger
from scanner.scanner import run_scanner
from trader.trader import run_trader
from learning.self_trainer import run_self_learning
from monitoring.reporter import generate_daily_report
from monitoring.healthcheck import start_healthcheck_server
from monitoring import healthcheck as hc
from monitoring.telegram_alerter import send_alert
from risk.daily_reset import run_daily_reset
from deployment.capital_manager import check_scale_up


def scanner_job():
    """Run scanner with error handling"""
    try:
        run_scanner()
        hc.last_scanner_run = datetime.now()
    except Exception as e:
        logger.error(f"Scanner error: {e}", exc_info=True)
        send_alert(f"⚠️ Scanner Error: {str(e)}")


def trader_job():
    """Run trader with error handling"""
    try:
        run_trader()
        hc.last_trader_run = datetime.now()
    except Exception as e:
        logger.error(f"Trader error: {e}", exc_info=True)
        send_alert(f"⚠️ Trader Error: {str(e)}")


def learning_job():
    """Run self-learning with error handling"""
    if not config.LEARNING_ENABLED:
        return

    try:
        run_self_learning()
    except Exception as e:
        logger.error(f"Learning error: {e}", exc_info=True)
        send_alert(f"⚠️ Learning Error: {str(e)}")


def report_job():
    """Generate daily report"""
    try:
        generate_daily_report()
    except Exception as e:
        logger.error(f"Report error: {e}", exc_info=True)
        send_alert(f"⚠️ Report Error: {str(e)}")


def daily_reset_job():
    """Reset daily counters"""
    try:
        run_daily_reset()
    except Exception as e:
        logger.error(f"Daily reset error: {e}", exc_info=True)
        send_alert(f"⚠️ Daily Reset Error: {str(e)}")


def capital_scale_job():
    """Check capital scaling"""
    try:
        check_scale_up()
    except Exception as e:
        logger.warning(f"Capital manager error: {e}")


def main():
    """Main entry point"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("🎯 ALPHA SNIPER V4.1 - SNIPER SWING")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Strategy: Long-only swing momentum trading")
    logger.info(f"Mode: {config.MODE}")
    logger.info(f"Starting Equity: ${config.SIM_EQUITY_START}")
    logger.info(f"Risk per Trade: {config.RISK_PER_TRADE_PCT}%")
    logger.info(f"Max Positions: {config.MAX_CONCURRENT_POS}")
    logger.info(f"Max Drawdown: {config.MAX_DAILY_DRAWDOWN_PCT}%")
    logger.info("")
    logger.info("=" * 70)
    logger.info("")

    # Start healthcheck server
    start_healthcheck_server()
    logger.info("✅ Health check server started on port 8080")

    # Send startup alert
    send_alert(
        "🎯 Alpha Sniper v4.1 Started\n"
        f"Strategy: Sniper Swing\n"
        f"Equity: ${config.SIM_EQUITY_START}\n"
        f"Risk: {config.RISK_PER_TRADE_PCT}% per trade"
    )

    # Schedule jobs
    schedule.every(config.SCANNER_INTERVAL).seconds.do(scanner_job)
    schedule.every(config.TRADER_INTERVAL).seconds.do(trader_job)

    if config.LEARNING_ENABLED:
        schedule.every(config.LEARNING_INTERVAL).seconds.do(learning_job)

    schedule.every().day.at(f"{config.DAILY_REPORT_HOUR:02d}:00").do(report_job)
    schedule.every().day.at("00:00").do(daily_reset_job)
    schedule.every(1).hours.do(capital_scale_job)

    logger.info(f"📅 Scanner runs every {config.SCANNER_INTERVAL}s (5 minutes)")
    logger.info(f"💼 Trader runs every {config.TRADER_INTERVAL}s (1 minute)")
    if config.LEARNING_ENABLED:
        logger.info(f"🧠 Learning runs every {config.LEARNING_INTERVAL}s")
    logger.info(f"📊 Daily report at {config.DAILY_REPORT_HOUR}:00 UTC")
    logger.info("=" * 70)
    logger.info("")

    # Run scanner once at startup
    logger.info("Running initial scanner...")
    scanner_job()

    # Main loop
    logger.info("Entering main loop...")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
