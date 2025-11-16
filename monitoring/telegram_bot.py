"""
Telegram Bot with Command Handlers
Provides /status command for real-time v4.1.1 performance monitoring
"""
import threading
import time
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext
from config.config import config
from monitoring.observer import get_observer
from monitoring.v42_fallback import get_current_filter_config
import logging

logger = logging.getLogger(__name__)


def status_command(update: Update, context: CallbackContext) -> None:
    """Handle /status command - show v4.1.1 observer stats"""
    try:
        observer = get_observer()
        stats = observer.get_stats()
        filter_config = get_current_filter_config()

        # Build status message
        msg = (
            f"📊 <b>v4.1.1 OBSERVER STATUS</b>\n\n"
            f"<b>Runtime:</b> {stats['runtime']}\n"
            f"<b>Started:</b> {stats['start_time']}\n"
            f"<b>Mode:</b> {'v4.2 Adaptive' if stats['v42_activated'] else 'v4.1.1 Standard'}\n\n"

            f"<b>SIGNALS</b>\n"
            f"  Total: {stats['signals']}\n"
            f"  Avg Score: {stats['avg_score']:.1f}\n"
        )

        if stats['time_since_first_signal'] is not None:
            msg += f"  First signal: {stats['time_since_first_signal']:.1f}h ago\n"
        else:
            msg += f"  First signal: None yet\n"

        msg += (
            f"\n<b>TRADES</b>\n"
            f"  Total: {stats['trades']}\n"
            f"  Win Rate: {stats['win_rate']:.1f}%\n"
            f"  Avg PnL: {stats['avg_pnl']:.2f}%\n\n"

            f"<b>FILTERS (Current)</b>\n"
            f"  Min Score: {filter_config['MIN_SIGNAL_SCORE']}\n"
            f"  Max Positions: {filter_config['MAX_CONCURRENT_POS']}\n"
            f"  SL: {filter_config['STOP_LOSS_PCT']}% | TP: {filter_config['TAKE_PROFIT_PCT']}%\n"
        )

        # Add warning if approaching fallback
        if not stats['v42_activated'] and stats['signals'] == 0:
            hours_left = 6.0 - stats['runtime_hours']
            if hours_left > 0:
                msg += f"\n⚠️ v4.2 fallback in {hours_left:.1f}h if no signals"
            else:
                msg += f"\n⚠️ v4.2 fallback criteria met"

        update.message.reply_text(msg, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in /status command: {e}")
        update.message.reply_text(f"Error getting status: {str(e)}")


def help_command(update: Update, context: CallbackContext) -> None:
    """Handle /help command"""
    msg = (
        "<b>Alpha Sniper v4.1.1 Bot Commands</b>\n\n"
        "/status - Show current performance stats\n"
        "/help - Show this help message\n"
    )
    update.message.reply_text(msg, parse_mode='HTML')


def start_telegram_bot() -> None:
    """Start the Telegram bot in a background thread"""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not configured, bot commands disabled")
        return

    def run_bot():
        try:
            updater = Updater(token=config.TELEGRAM_BOT_TOKEN, use_context=True)
            dispatcher = updater.dispatcher

            # Register command handlers
            dispatcher.add_handler(CommandHandler('status', status_command))
            dispatcher.add_handler(CommandHandler('help', help_command))
            dispatcher.add_handler(CommandHandler('start', help_command))

            logger.info("Telegram bot started, listening for commands...")
            print("✅ Telegram bot ready - /status command available")

            updater.start_polling()
            updater.idle()

        except Exception as e:
            logger.error(f"Error starting Telegram bot: {e}")
            print(f"⚠️  Telegram bot failed to start: {e}")

    # Run bot in daemon thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
