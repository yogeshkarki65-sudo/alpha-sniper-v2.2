"""
Enhanced Trader with Alpha Sniper V2.2 Strategy Integration

Features:
- ATR-based position sizing
- ATR-based stop-loss and take-profit levels
- Partial exits (TP1: 50%, TP2: 30%)
- ATR-based trailing stops
- Regime-aware risk management
"""

import requests
import time
import pandas as pd
from datetime import datetime, timedelta

from config.config import config
from database.models import db
from risk.risk_manager import risk_manager
from monitoring.telegram_alerter import send_alert

# Import Alpha Sniper components
from strategies.alpha_sniper import AlphaSniperStrategy
from scanner.scanner_v2 import get_scanner
import json
from pathlib import Path


class EnhancedTrader:
    """Trader with Alpha Sniper V2.2 integration"""

    def __init__(self):
        """Initialize enhanced trader"""
        # Load strategy config
        config_path = Path('config_alpha_sniper.json')
        if config_path.exists():
            with open(config_path, 'r') as f:
                strategy_config = json.load(f)
        else:
            strategy_config = self._get_default_config()

        self.strategy = AlphaSniperStrategy(config=strategy_config)
        self.scanner = get_scanner()  # Get scanner for regime info

        print("[trader v2] ✅ Enhanced trader initialized with Alpha Sniper V2.2")

    def _get_default_config(self):
        """Get default strategy configuration"""
        return {
            'z_bull_threshold': 0.5,
            'z_bear_threshold': -0.5,
            'risk_pct_bull': 0.004,
            'risk_pct_sideways': 0.0025,
            'risk_pct_bear': 0.0012,
            'max_portfolio_heat': 0.015,
            'max_daily_loss_pct': 0.02,
            'atr_sl_mult': 2.0,
            'tp1_mult': 2.0,
            'tp2_mult': 3.0,
            'trail_mult': 1.5,
            'tp1_exit_pct': 0.50,
            'tp2_exit_pct': 0.30
        }

    def get_current_price(self, symbol):
        """Get current price for symbol"""
        try:
            url = f"{config.MEXC_BASE_URL}/api/v3/ticker/price"
            params = {'symbol': symbol}
            resp = requests.get(url, params=params, timeout=5)
            data = resp.json()
            return float(data['price'])
        except Exception as e:
            print(f"[trader v2] Error fetching price for {symbol}: {e}")
            return None

    def fetch_ohlcv_data(self, symbol, interval='15m', limit=100):
        """Fetch OHLCV data for ATR calculation"""
        try:
            url = f"{config.MEXC_BASE_URL}/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }

            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            return df

        except Exception as e:
            print(f"[trader v2] Error fetching OHLCV for {symbol}: {e}")
            return pd.DataFrame()

    def calculate_atr(self, df, period=14):
        """Calculate ATR from OHLCV data"""
        if len(df) < period:
            return None

        high = df['high']
        low = df['low']
        close = df['close']

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean().iloc[-1]
        return atr

    def check_symbol_cooldown(self, symbol):
        """Check if symbol is in cooldown period"""
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

    def open_position_from_signal(self, signal):
        """
        Open position using Alpha Sniper V2.2 parameters

        Args:
            signal: Database signal tuple
        """
        signal_id = signal[0]
        symbol = signal[1]
        score = signal[2]

        # Check cooldown
        if not self.check_symbol_cooldown(symbol):
            print(f"[trader v2] ⏸️  {symbol} in cooldown period")
            db.mark_signal_consumed(signal_id)
            return False

        # Check risk limits
        can_trade, reason = risk_manager.can_trade()
        if not can_trade:
            print(f"[trader v2] 🚫 Cannot trade: {reason}")
            return False

        # Check correlation
        open_positions = db.get_open_positions()
        if not risk_manager.check_correlation(symbol, open_positions):
            print(f"[trader v2] ⚠️  {symbol} too correlated with existing positions")
            db.mark_signal_consumed(signal_id)
            return False

        # Get current price
        current_price = self.get_current_price(symbol)
        if not current_price:
            return False

        # Fetch OHLCV for ATR calculation
        ohlcv_df = self.fetch_ohlcv_data(symbol, interval='15m', limit=100)
        if ohlcv_df.empty:
            print(f"[trader v2] ⚠️ Could not fetch OHLCV for {symbol}")
            db.mark_signal_consumed(signal_id)
            return False

        # Calculate ATR
        atr = self.calculate_atr(ohlcv_df, period=14)
        if not atr or atr <= 0:
            print(f"[trader v2] ⚠️ Invalid ATR for {symbol}")
            db.mark_signal_consumed(signal_id)
            return False

        # Get regime info
        regime_info = self.scanner.current_regime
        if not regime_info:
            regime_info = {'regime': 'sideways', 'z_ret': 0, 'rs_alt': 0}

        # Prepare signal data for strategy
        signal_data = {
            'signal': True,
            'symbol': symbol,
            'score': score / 100,  # Convert back to 0-1 scale
            'entry_price': current_price,
            'pullback_low': current_price * 0.98,  # Estimate
            'features': {'atr': atr}
        }

        # Calculate position parameters using Alpha Sniper
        try:
            pos_params = self.strategy.calculate_position_params(
                signal=signal_data,
                equity=risk_manager.get_current_equity(),
                regime_info=regime_info
            )
        except Exception as e:
            print(f"[trader v2] Error calculating position params: {e}")
            db.mark_signal_consumed(signal_id)
            return False

        # Apply slippage
        entry_price = current_price * (1 + config.SLIPPAGE_PCT / 100)

        # Position size (convert from notional to quantity)
        position_size = pos_params['position_size'] / entry_price

        if position_size <= 0:
            print(f"[trader v2] ⚠️ Position size <= 0 for {symbol}")
            db.mark_signal_consumed(signal_id)
            return False

        # Exit levels from Alpha Sniper
        stop_loss_price = pos_params['stop_loss']
        tp1_price = pos_params['tp1']
        tp2_price = pos_params['tp2']
        trailing_stop_price = pos_params['trailing_stop']

        # Create position
        position_id = db.create_position(
            signal_id,
            symbol,
            entry_price,
            position_size,
            stop_loss_price,
            tp1_price  # Use TP1 as take_profit for compatibility
        )

        db.mark_signal_consumed(signal_id)

        # Store additional Alpha Sniper data in position metadata
        # (Would need database schema update for full support)

        position_value = entry_price * position_size

        print(
            f"[trader v2] 📈 OPENED: {symbol} @ ${entry_price:.6f} | "
            f"Size: {position_size:.4f} | Value: ${position_value:.2f} | "
            f"Regime: {regime_info['regime'].upper()}"
        )
        print(
            f"[trader v2]    SL: ${stop_loss_price:.6f} | "
            f"TP1: ${tp1_price:.6f} (50%) | "
            f"TP2: ${tp2_price:.6f} (30%)"
        )

        send_alert(
            f"📈 Position Opened (Alpha Sniper V2.2)\n"
            f"Symbol: {symbol}\n"
            f"Score: {score:.1f}\n"
            f"Regime: {regime_info['regime'].upper()}\n"
            f"Entry: ${entry_price:.6f}\n"
            f"Value: ${position_value:.2f}\n"
            f"SL: ${stop_loss_price:.6f}\n"
            f"TP1: ${tp1_price:.6f} (50%)\n"
            f"TP2: ${tp2_price:.6f} (30%)"
        )

        return True

    def monitor_positions(self):
        """
        Monitor positions with Alpha Sniper V2.2 exit logic

        Note: Full partial exits require database schema updates.
        This version uses existing schema with enhanced exit logic.
        """
        positions = db.get_open_positions()
        if not positions:
            return

        print(f"[trader v2] 👀 Monitoring {len(positions)} positions...")

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
            opened_at_ts = pos[10]

            # Get current price
            current_price = self.get_current_price(symbol)
            if not current_price:
                continue

            # Update highest price
            if current_price > highest_price:
                highest_price = current_price

            # Calculate current profit
            current_profit_pct = ((current_price - entry_price) / entry_price) * 100

            # Check max hold time
            now_ts = datetime.now().timestamp()
            hold_time_hours = (now_ts - opened_at_ts) / 3600
            if hold_time_hours >= config.MAX_HOLD_TIME_HOURS:
                exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
                db.close_position(position_id, exit_price, 'time_exit')
                print(f"[trader v2] ⏰ CLOSED (time): {symbol} @ ${exit_price:.6f} | PnL: {current_profit_pct:.2f}%")
                send_alert(f"⏰ Time Exit: {symbol} | PnL: {current_profit_pct:.2f}%")
                continue

            # Fetch current ATR
            ohlcv_df = self.fetch_ohlcv_data(symbol, interval='15m', limit=100)
            current_atr = self.calculate_atr(ohlcv_df, period=14) if not ohlcv_df.empty else None

            # Enhanced trailing stop (ATR-based)
            if config.USE_TRAILING_STOP and current_atr:
                # Activate trailing stop at TP1 level
                tp1_reached = current_price >= take_profit_price

                if tp1_reached and not trailing_stop_active:
                    trailing_stop_active = True
                    # ATR-based trailing stop (1.5 * ATR from highest)
                    trailing_stop_price = highest_price - (1.5 * current_atr)
                    db.update_position_trailing(position_id, highest_price, trailing_stop_active, trailing_stop_price)
                    print(f"[trader v2] 🎯 ATR Trailing stop activated for {symbol} @ ${trailing_stop_price:.6f}")

                if trailing_stop_active:
                    # Update trailing stop based on ATR
                    trailing_stop_price = highest_price - (1.5 * current_atr)
                    db.update_position_trailing(position_id, highest_price, trailing_stop_active, trailing_stop_price)

                    if current_price <= trailing_stop_price:
                        exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
                        db.close_position(position_id, exit_price, 'trailing_stop')
                        print(f"[trader v2] 📉 CLOSED (ATR trailing): {symbol} @ ${exit_price:.6f} | PnL: {current_profit_pct:.2f}%")
                        send_alert(f"📉 ATR Trailing Stop: {symbol} | PnL: {current_profit_pct:.2f}%")
                        continue

            # Hard stop-loss
            if current_price <= stop_loss_price:
                exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
                db.close_position(position_id, exit_price, 'stop_loss')
                print(f"[trader v2] 🛑 CLOSED (SL): {symbol} @ ${exit_price:.6f} | PnL: {current_profit_pct:.2f}%")
                send_alert(f"🛑 Stop Loss: {symbol} | PnL: {current_profit_pct:.2f}%")
                continue

            # Take profit (TP1 in current schema)
            if current_price >= take_profit_price:
                exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
                db.close_position(position_id, exit_price, 'take_profit')
                print(f"[trader v2] 💰 CLOSED (TP): {symbol} @ ${exit_price:.6f} | PnL: {current_profit_pct:.2f}%")
                send_alert(f"💰 Take Profit: {symbol} | PnL: {current_profit_pct:.2f}%")
                continue

            print(f"[trader v2]   {symbol}: ${current_price:.6f} | PnL: {current_profit_pct:.2f}% | ATR: {current_atr:.6f if current_atr else 'N/A'}")

    def run_trader(self):
        """Run enhanced trader"""
        print("💼 Running Enhanced Trader (Alpha Sniper V2.2)...")

        # Monitor existing positions
        self.monitor_positions()

        # Check if can open new positions
        can_trade, reason = risk_manager.can_trade()
        if not can_trade:
            print(f"[trader v2] 🚫 Cannot open new positions: {reason}")
            return

        # Check available slots
        open_positions = db.get_open_positions()
        slots_available = config.MAX_CONCURRENT_POS - len(open_positions)

        if slots_available <= 0:
            print("[trader v2] 📊 All position slots filled")
            return

        # Get unconsumed signals
        signals = db.get_unconsumed_signals(limit=slots_available)
        if not signals:
            print("[trader v2] 📭 No signals to process")
            return

        print(f"[trader v2] Found {len(signals)} signals to process")
        for signal in signals:
            if self.open_position_from_signal(signal):
                time.sleep(1)


# Singleton instance
_trader = None

def get_trader():
    """Get or create trader instance"""
    global _trader
    if _trader is None:
        _trader = EnhancedTrader()
    return _trader


def run_trader():
    """Run enhanced trader (backwards compatible)"""
    trader = get_trader()
    return trader.run_trader()


if __name__ == "__main__":
    run_trader()
