"""
Alpha Sniper V3.0 - Trader Module

Handles position management:
- Opening positions from signals
- Monitoring open positions
- Executing exits (stop loss, take profit, trailing stop, time-based)
- Risk management integration
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple

from config.config import config
from config.logging_config import configure_logging
from database.models import db
from risk.risk_manager import risk_manager
from risk.trailing_stop import TrailingStop, TrailingStopConfig
from monitoring.telegram_alerter import send_alert

# Initialize logger
logger = configure_logging("trader")

# Cache for trailing stop instances
_trailing_stops = {}


def get_current_price(symbol: str) -> Optional[float]:
    """
    Fetch current price for a symbol from MEXC

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')

    Returns:
        Current price or None on error
    """
    try:
        url = f"{config.MEXC_BASE_URL}/api/v3/ticker/price"
        params = {'symbol': symbol}
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        return float(data['price'])
    except Exception as e:
        logger.error(f"Failed to fetch price for {symbol}: {e}")
        return None


def check_symbol_cooldown(symbol: str) -> bool:
    """
    Check if symbol is in cooldown period

    Args:
        symbol: Trading symbol

    Returns:
        True if symbol can be traded, False if in cooldown
    """
    try:
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
    except Exception as e:
        logger.error(f"Error checking cooldown for {symbol}: {e}")
        return True  # Default to allowing trade


def open_position_from_signal(signal: Tuple) -> bool:
    """
    Open a position from a signal

    Args:
        signal: Signal tuple from database

    Returns:
        True if position opened successfully, False otherwise
    """
    signal_id = signal[0]
    symbol = signal[1]
    score = signal[2]

    # Check cooldown
    if not check_symbol_cooldown(symbol):
        logger.info(f"⏸️  {symbol} in cooldown period")
        db.mark_signal_consumed(signal_id)
        return False

    # Check risk manager
    can_trade, reason = risk_manager.can_trade()
    if not can_trade:
        logger.warning(f"🚫 Cannot trade: {reason}")
        return False

    # Check correlation
    open_positions = db.get_open_positions()
    if not risk_manager.check_correlation(symbol, open_positions):
        logger.info(f"⚠️  {symbol} too correlated with existing positions")
        db.mark_signal_consumed(signal_id)
        return False

    # Get current price
    current_price = get_current_price(symbol)
    if not current_price:
        return False

    # Calculate entry with slippage
    entry_price = current_price * (1 + config.SLIPPAGE_PCT / 100)

    # Calculate position size
    position_size = risk_manager.calculate_position_size(entry_price, config.STOP_LOSS_PCT)
    if position_size <= 0:
        logger.warning(f"⚠️ Position size <= 0 for {symbol}")
        db.mark_signal_consumed(signal_id)
        return False

    # Moon signal multiplier
    if score >= config.MOON_SCORE:
        position_size *= config.MOON_MULT
        logger.info(f"🌙 MOON signal detected! Multiplying position by {config.MOON_MULT}x")

    # Calculate stops
    stop_loss_price = entry_price * (1 - config.STOP_LOSS_PCT / 100)
    take_profit_price = entry_price * (1 + config.TAKE_PROFIT_PCT / 100)

    # Create position in database
    position_id = db.create_position(
        signal_id,
        symbol,
        entry_price,
        position_size,
        stop_loss_price,
        take_profit_price
    )

    db.mark_signal_consumed(signal_id)

    # Create trailing stop instance
    if config.USE_TRAILING_STOP:
        ts_config = TrailingStopConfig(
            entry_price=entry_price,
            activation_pct=config.TRAILING_STOP_ACTIVATION_PCT,
            distance_pct=config.TRAILING_STOP_DISTANCE_PCT,
            breakeven_pct=getattr(config, 'BREAKEVEN_PCT', 5.0)
        )
        _trailing_stops[position_id] = TrailingStop(ts_config)

    position_value = entry_price * position_size
    logger.info(
        f"📈 OPENED: {symbol} @ ${entry_price:.6f} | "
        f"Size: {position_size:.4f} | Value: ${position_value:.2f}"
    )

    send_alert(
        f"📈 Position Opened\n"
        f"Symbol: {symbol}\n"
        f"Score: {score:.1f}\n"
        f"Entry: ${entry_price:.6f}\n"
        f"Value: ${position_value:.2f}\n"
        f"SL: ${stop_loss_price:.6f} | TP: ${take_profit_price:.6f}"
    )

    return True


def monitor_positions():
    """
    Monitor all open positions and execute exits when conditions are met
    """
    positions = db.get_open_positions()
    if not positions:
        return

    logger.info(f"👀 Monitoring {len(positions)} positions...")

    for pos in positions:
        position_id = pos[0]
        symbol = pos[2]
        entry_price = float(pos[3])
        position_size = float(pos[4])
        stop_loss_price = float(pos[5])
        take_profit_price = float(pos[6])
        highest_price = float(pos[7]) if pos[7] else entry_price
        trailing_stop_active = bool(pos[8])
        trailing_stop_price = float(pos[9]) if pos[9] else 0.0

        # Parse opened_at datetime
        if pos[10]:
            try:
                opened_at_dt = datetime.fromisoformat(pos[10])
                opened_at_ts = opened_at_dt.timestamp()
            except (ValueError, TypeError):
                opened_at_ts = float(pos[10])
        else:
            opened_at_ts = datetime.now().timestamp()

        # Get current price
        current_price = get_current_price(symbol)
        if not current_price:
            continue

        # Update highest price
        if current_price > highest_price:
            highest_price = current_price

        # Calculate current P&L
        current_profit_pct = ((current_price - entry_price) / entry_price) * 100

        # Check max hold time
        now_ts = datetime.now().timestamp()
        hold_time_hours = (now_ts - opened_at_ts) / 3600
        if hold_time_hours >= config.MAX_HOLD_TIME_HOURS:
            exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
            db.close_position(position_id, exit_price, 'time_exit')
            logger.info(f"⏰ CLOSED (time): {symbol} @ ${exit_price:.6f} | PnL: {current_profit_pct:.2f}%")
            send_alert(f"⏰ Time Exit: {symbol} | PnL: {current_profit_pct:.2f}%")

            # Clean up trailing stop
            if position_id in _trailing_stops:
                del _trailing_stops[position_id]

            continue

        # V3: Use TrailingStop class
        if config.USE_TRAILING_STOP:
            # Get or create trailing stop instance
            if position_id not in _trailing_stops:
                ts_config = TrailingStopConfig(
                    entry_price=entry_price,
                    activation_pct=config.TRAILING_STOP_ACTIVATION_PCT,
                    distance_pct=config.TRAILING_STOP_DISTANCE_PCT,
                    breakeven_pct=getattr(config, 'BREAKEVEN_PCT', 5.0)
                )
                trailing_stop = TrailingStop(ts_config)

                # Initialize with highest price if we have it
                if highest_price > entry_price:
                    trailing_stop.update(highest_price)

                _trailing_stops[position_id] = trailing_stop
            else:
                trailing_stop = _trailing_stops[position_id]

            # Update trailing stop with current price
            trailing_stop.update(current_price)

            # Check if trailing stop was hit
            if trailing_stop.is_hit:
                exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
                db.close_position(position_id, exit_price, 'trailing_stop')
                logger.info(
                    f"📉 CLOSED (trailing): {symbol} @ ${exit_price:.6f} | "
                    f"PnL: {current_profit_pct:.2f}%"
                )
                send_alert(f"📉 Trailing Stop: {symbol} | PnL: {current_profit_pct:.2f}%")

                # Clean up
                del _trailing_stops[position_id]
                continue

            # Update database with new highest/stop prices
            if trailing_stop.is_active:
                db.update_position_trailing(
                    position_id,
                    trailing_stop.highest_price,
                    True,
                    trailing_stop.stop_price
                )

                if not trailing_stop_active:  # Just activated
                    logger.info(f"🎯 Trailing stop activated for {symbol} @ ${trailing_stop.stop_price:.6f}")

        # Check stop loss
        if current_price <= stop_loss_price:
            exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
            db.close_position(position_id, exit_price, 'stop_loss')
            logger.info(f"🛑 CLOSED (SL): {symbol} @ ${exit_price:.6f} | PnL: {current_profit_pct:.2f}%")
            send_alert(f"🛑 Stop Loss: {symbol} | PnL: {current_profit_pct:.2f}%")

            # Clean up trailing stop
            if position_id in _trailing_stops:
                del _trailing_stops[position_id]

            continue

        # Check take profit
        if current_price >= take_profit_price:
            exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
            db.close_position(position_id, exit_price, 'take_profit')
            logger.info(f"💰 CLOSED (TP): {symbol} @ ${exit_price:.6f} | PnL: {current_profit_pct:.2f}%")
            send_alert(f"💰 Take Profit: {symbol} | PnL: {current_profit_pct:.2f}%")

            # Clean up trailing stop
            if position_id in _trailing_stops:
                del _trailing_stops[position_id]

            continue

        # Position still open - log status
        logger.info(f"  {symbol}: ${current_price:.6f} | PnL: {current_profit_pct:.2f}%")


def run_trader():
    """
    Main trader function - monitors positions and processes signals
    """
    logger.info("💼 Running trader...")

    # Monitor existing positions
    monitor_positions()

    # Check if we can open new positions
    can_trade, reason = risk_manager.can_trade()
    if not can_trade:
        logger.warning(f"🚫 Cannot open new positions: {reason}")
        return

    # Check available slots
    open_positions = db.get_open_positions()
    slots_available = config.MAX_CONCURRENT_POS - len(open_positions)

    if slots_available <= 0:
        logger.debug("📊 All position slots filled")
        return

    # Get unconsumed signals
    signals = db.get_unconsumed_signals(limit=slots_available)
    if not signals:
        logger.debug("📭 No signals to process")
        return

    logger.info(f"Found {len(signals)} signals to process")
    for signal in signals:
        if open_position_from_signal(signal):
            time.sleep(1)  # Small delay between position opens
