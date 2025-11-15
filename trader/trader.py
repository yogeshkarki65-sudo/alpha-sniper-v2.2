"""
Alpha Sniper v4.1 Trader
- Entry: Max 3 concurrent positions, correlation check, Moon mode
- Exit Priority: Trailing → Max hold time (36h) → Stop loss → Take profit
- Min hold: 4 hours, Max hold: 36 hours (fallback 48h)
"""
import time
from datetime import datetime, timedelta
from typing import Optional
from config.config import config
from config.logging_config import logger
from database.models import db
from risk.risk_manager import risk_manager
from risk.trailing_stop import trailing_stop_manager
from scanner.mexc_client import mexc_client
from monitoring.telegram_alerter import send_alert


def check_symbol_cooldown(symbol: str) -> bool:
    """
    Check if symbol is in cooldown period (12 hours since last trade)
    Args:
        symbol: Trading pair
    Returns: True if cooldown expired
    """
    cooldown_time = datetime.now() - timedelta(hours=config.SYMBOL_COOLDOWN_HOURS)
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM trades
        WHERE symbol=? AND closed_at > ?
    ''', (symbol, cooldown_time.isoformat()))
    count = cursor.fetchone()[0]
    conn.close()
    return count == 0


def open_position_from_signal(signal: tuple) -> bool:
    """
    Open position from signal
    Args:
        signal: Signal tuple from database
    Returns: True if position opened
    """
    signal_id = signal[0]
    symbol = signal[1]
    score = signal[2]

    # Check cooldown
    if not check_symbol_cooldown(symbol):
        logger.info(f"⏸️  {symbol} in cooldown period")
        db.mark_signal_consumed(signal_id)
        return False

    # Check if can trade
    can_trade, reason = risk_manager.can_trade()
    if not can_trade:
        logger.info(f"🚫 Cannot trade: {reason}")
        return False

    # Check correlation
    open_positions = db.get_open_positions()
    if not risk_manager.check_correlation(symbol, open_positions):
        logger.info(f"⚠️ {symbol} too correlated with existing positions")
        db.mark_signal_consumed(signal_id)
        return False

    # Get current price
    current_price = mexc_client.get_current_price(symbol)
    if not current_price:
        logger.warning(f"Failed to fetch price for {symbol}")
        return False

    # Add slippage for entry
    entry_price = current_price * (1 + config.SLIPPAGE_PCT / 100)

    # Check if Moon mode
    is_moon_mode = score >= config.MOON_SCORE_THRESHOLD

    # Calculate position size
    position_size = risk_manager.calculate_position_size(entry_price, is_moon_mode)
    if position_size <= 0:
        logger.warning(f"⚠️ Position size <= 0 for {symbol}")
        db.mark_signal_consumed(signal_id)
        return False

    # Calculate stops
    stop_loss_price = entry_price * (1 - config.STOP_LOSS_PCT / 100)
    take_profit_price = entry_price * (1 + config.TAKE_PROFIT_PCT / 100)

    # Create position
    position_id = db.create_position(
        signal_id,
        symbol,
        entry_price,
        position_size,
        stop_loss_price,
        take_profit_price,
        is_moon_mode
    )

    db.mark_signal_consumed(signal_id)

    position_value = entry_price * position_size
    moon_tag = "🌙 MOON " if is_moon_mode else ""

    logger.info(
        f"📈 {moon_tag}OPENED: {symbol} @ ${entry_price:.6f} | "
        f"Size: {position_size:.4f} | Value: ${position_value:.2f} | "
        f"Score: {score:.1f}"
    )

    if config.ALERT_ON_POSITION_OPEN:
        send_alert(
            f"📈 {moon_tag}Position Opened\n"
            f"Symbol: {symbol}\n"
            f"Score: {score:.1f}\n"
            f"Entry: ${entry_price:.6f}\n"
            f"Value: ${position_value:.2f}\n"
            f"SL: ${stop_loss_price:.6f} | TP: ${take_profit_price:.6f}"
        )

    return True


def monitor_positions() -> None:
    """
    Monitor all open positions and execute exits
    Exit priority:
    1. Min hold time check (must hold at least 4 hours)
    2. Trailing stop (if active and hit)
    3. Max hold time (36 hours, fallback 48h)
    4. Stop loss (-3.5%)
    5. Take profit (+10%)
    """
    positions = db.get_open_positions()
    if not positions:
        return

    logger.info(f"👀 Monitoring {len(positions)} positions...")

    for pos in positions:
        position_id = pos[0]
        symbol = pos[2]
        entry_price = pos[3]
        position_size = pos[4]
        stop_loss_price = pos[5]
        take_profit_price = pos[6]
        highest_price = pos[7]
        trailing_stop_active = bool(pos[8])
        trailing_stop_price = pos[9]
        breakeven_moved = bool(pos[10])
        opened_at_ts = pos[12]

        # Get current price
        current_price = mexc_client.get_current_price(symbol)
        if not current_price:
            logger.warning(f"Failed to fetch price for {symbol}")
            continue

        # Calculate metrics
        current_profit_pct = ((current_price - entry_price) / entry_price) * 100
        now_ts = datetime.now().timestamp()
        hold_time_hours = (now_ts - opened_at_ts) / 3600

        # === MIN HOLD TIME CHECK ===
        if hold_time_hours < config.MIN_HOLD_HOURS:
            logger.debug(
                f"  {symbol}: Hold {hold_time_hours:.1f}h < {config.MIN_HOLD_HOURS}h min | "
                f"PnL: {current_profit_pct:.2f}%"
            )
            continue

        # === UPDATE TRAILING STOP & BREAKEVEN ===
        (
            highest_price,
            trailing_stop_active,
            trailing_stop_price,
            breakeven_moved,
            stop_loss_price
        ) = trailing_stop_manager.update_position_trailing(
            position_id,
            entry_price,
            current_price,
            highest_price,
            trailing_stop_active,
            trailing_stop_price,
            breakeven_moved,
            stop_loss_price
        )

        # === EXIT 1: TRAILING STOP ===
        if trailing_stop_active and trailing_stop_price:
            if trailing_stop_manager.check_trailing_hit(current_price, trailing_stop_price):
                exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
                db.close_position(position_id, exit_price, 'trailing_stop')
                logger.info(
                    f"📉 CLOSED (trailing): {symbol} @ ${exit_price:.6f} | "
                    f"PnL: {current_profit_pct:.2f}% | Hold: {hold_time_hours:.1f}h"
                )
                if config.ALERT_ON_POSITION_CLOSE:
                    send_alert(
                        f"📉 Trailing Stop Hit\n{symbol} | "
                        f"PnL: {current_profit_pct:.2f}%"
                    )
                continue

        # === EXIT 2: MAX HOLD TIME ===
        if hold_time_hours >= config.MAX_HOLD_HOURS:
            exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
            db.close_position(position_id, exit_price, 'max_hold_time')
            logger.info(
                f"⏰ CLOSED (time): {symbol} @ ${exit_price:.6f} | "
                f"PnL: {current_profit_pct:.2f}% | Hold: {hold_time_hours:.1f}h"
            )
            if config.ALERT_ON_POSITION_CLOSE:
                send_alert(
                    f"⏰ Max Hold Time\n{symbol} | "
                    f"PnL: {current_profit_pct:.2f}%"
                )
            continue

        # === EXIT 3: STOP LOSS ===
        if current_price <= stop_loss_price:
            exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
            db.close_position(position_id, exit_price, 'stop_loss')
            logger.info(
                f"🛑 CLOSED (SL): {symbol} @ ${exit_price:.6f} | "
                f"PnL: {current_profit_pct:.2f}% | Hold: {hold_time_hours:.1f}h"
            )
            if config.ALERT_ON_POSITION_CLOSE:
                send_alert(
                    f"🛑 Stop Loss Hit\n{symbol} | "
                    f"PnL: {current_profit_pct:.2f}%"
                )
            continue

        # === EXIT 4: TAKE PROFIT ===
        if current_price >= take_profit_price:
            exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
            db.close_position(position_id, exit_price, 'take_profit')
            logger.info(
                f"💰 CLOSED (TP): {symbol} @ ${exit_price:.6f} | "
                f"PnL: {current_profit_pct:.2f}% | Hold: {hold_time_hours:.1f}h"
            )
            if config.ALERT_ON_POSITION_CLOSE:
                send_alert(
                    f"💰 Take Profit Hit\n{symbol} | "
                    f"PnL: {current_profit_pct:.2f}%"
                )
            continue

        # === POSITION STILL OPEN ===
        trailing_status = f"[T-STOP @ ${trailing_stop_price:.6f}]" if trailing_stop_active else ""
        logger.info(
            f"  {symbol}: ${current_price:.6f} | "
            f"PnL: {current_profit_pct:+.2f}% | "
            f"Hold: {hold_time_hours:.1f}h {trailing_status}"
        )


def run_trader() -> None:
    """
    Main trader entry point
    1. Monitor existing positions
    2. Open new positions from signals
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("💼 ALPHA SNIPER v4.1 TRADER")
    logger.info("=" * 60)

    # Monitor existing positions
    monitor_positions()

    # Check if can open new positions
    can_trade, reason = risk_manager.can_trade()
    if not can_trade:
        logger.info(f"🚫 Cannot open new positions: {reason}")
        logger.info("=" * 60)
        return

    # Calculate available slots
    open_positions = db.get_open_positions()
    slots_available = config.MAX_CONCURRENT_POS - len(open_positions)

    if slots_available <= 0:
        logger.info("📊 All position slots filled")
        logger.info("=" * 60)
        return

    # Fetch signals
    signals = db.get_unconsumed_signals(limit=slots_available)
    if not signals:
        logger.info("📭 No signals to process")
        logger.info("=" * 60)
        return

    logger.info(f"Found {len(signals)} signals to process")
    for signal in signals:
        if open_position_from_signal(signal):
            time.sleep(1)  # Rate limiting

    logger.info("=" * 60)


if __name__ == "__main__":
    run_trader()
