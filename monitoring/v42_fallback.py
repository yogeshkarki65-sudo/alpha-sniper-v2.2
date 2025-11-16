"""
v4.2 Adaptive Fallback Module
Loosens filters when v4.1.1 generates no signals for 6+ hours
"""
import logging
from config.config import config
from monitoring.telegram_alerter import send_alert

logger = logging.getLogger(__name__)


def apply_v42_fallback() -> None:
    """
    Apply v4.2 adaptive mode by loosening filter parameters
    This is activated when v4.1.1 has produced zero signals in FALLBACK_TRIGGER_HOURS
    """

    # Store original values for logging
    original_values = {
        'MIN_SIGNAL_SCORE': config.MIN_SIGNAL_SCORE,
    }

    # Loosen signal score threshold to configured fallback value
    config.MIN_SIGNAL_SCORE = config.MIN_SIGNAL_SCORE_FALLBACK

    # Log the changes
    logger.warning("=" * 60)
    logger.warning("⚠️  v4.2 ADAPTIVE MODE ACTIVATED")
    logger.warning("=" * 60)
    logger.warning(f"Reason: No signals generated in {config.FALLBACK_TRIGGER_HOURS}+ hours")
    logger.warning(f"MIN_SIGNAL_SCORE: {original_values['MIN_SIGNAL_SCORE']} → {config.MIN_SIGNAL_SCORE}")
    logger.warning("=" * 60)

    # Print to console as well
    print("\n" + "=" * 60)
    print("⚠️  v4.2 ADAPTIVE MODE ACTIVATED - FILTERS LOOSENED")
    print("=" * 60)
    print(f"MIN_SIGNAL_SCORE: {original_values['MIN_SIGNAL_SCORE']} → {config.MIN_SIGNAL_SCORE}")
    print(f"Reason: No signals in {config.FALLBACK_TRIGGER_HOURS}+ hours - adapting to market conditions")
    print("=" * 60 + "\n")

    # Send Telegram alert
    alert_msg = (
        "⚠️ <b>v4.2 ADAPTIVE MODE ACTIVATED</b>\n\n"
        f"<b>Reason:</b> No signals in {config.FALLBACK_TRIGGER_HOURS}+ hours\n\n"
        f"<b>Filter Changes:</b>\n"
        f"MIN_SIGNAL_SCORE: {original_values['MIN_SIGNAL_SCORE']} → {config.MIN_SIGNAL_SCORE}\n\n"
        "The system will now accept slightly lower quality signals to adapt to current market conditions."
    )
    send_alert(alert_msg)


def get_current_filter_config() -> dict:
    """Return current filter configuration for status reporting"""
    return {
        'MIN_SIGNAL_SCORE': config.MIN_SIGNAL_SCORE,
        'SYMBOL_COOLDOWN_HOURS': config.SYMBOL_COOLDOWN_HOURS,
        'MIN_LIQUIDITY_VOLUME_24H': config.MIN_LIQUIDITY_VOLUME_24H,
        'MAX_CONCURRENT_POS': config.MAX_CONCURRENT_POS,
        'STOP_LOSS_PCT': config.STOP_LOSS_PCT,
        'TAKE_PROFIT_PCT': config.TAKE_PROFIT_PCT,
    }
