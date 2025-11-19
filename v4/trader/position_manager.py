"""
Alpha Sniper V4.0 - Position Manager
Manages open positions with V4 spec exit logic

Adapted from V3, follows exact V4.0 spec from section F
"""
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json


@dataclass
class Position:
    """Open position"""
    symbol: str
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    current_price: float
    size_usdt: float
    stop_loss: float
    entry_time: datetime
    regime: str  # BULL, SIDEWAYS, BEAR

    # Risk metrics
    initial_risk_r: float  # Initial R (entry - SL distance)
    r_dollars: float  # Dollar value of 1R

    # Partial exits tracking
    tp1_hit: bool = False
    tp2_hit: bool = False
    remaining_pct: float = 1.0  # 100% initially

    # High water marks
    highest_price: float = 0.0
    lowest_price: float = 999999.0
    mfe_r: float = 0.0  # Max favorable excursion
    mae_r: float = 0.0  # Max adverse excursion

    # Trailing stop
    trailing_stop: Optional[float] = None

    # Bars since entry (for NFT rule)
    bars_since_entry: int = 0

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['entry_time'] = self.entry_time.isoformat()
        return d


class PositionManager:
    """
    Manages lifecycle of open positions with V4.0 exit logic
    """

    def __init__(
        self,
        mexc_client,
        execution_engine,
        telegram_notifier=None
    ):
        self.mexc_client = mexc_client
        self.execution_engine = execution_engine
        self.telegram = telegram_notifier

        # Position persistence
        self.positions_file = 'positions.json'

        # Open positions
        self.positions: Dict[str, Position] = {}  # symbol -> Position

        # Exit parameters from .env (regime-adaptive)
        self.atr_sl_mult_long = float(os.getenv('ATR_SL_MULT_LONG', 2.0))
        self.atr_sl_mult_short = float(os.getenv('ATR_SL_MULT_SHORT', 1.8))

        self.tp1_r_long = float(os.getenv('TP1_R_MULT_LONG', 2.0))
        self.tp2_r_long = float(os.getenv('TP2_R_MULT_LONG', 3.0))
        self.tp1_r_short = float(os.getenv('TP1_R_MULT_SHORT', 1.5))
        self.tp2_r_short = float(os.getenv('TP2_R_MULT_SHORT', 2.5))

        self.trail_mult_long = float(os.getenv('TRAIL_MULT_LONG', 1.5))
        self.trail_mult_short = float(os.getenv('TRAIL_MULT_SHORT', 1.0))

        # No-follow-through rule
        self.nft_bars_min = int(os.getenv('NO_FOLLOW_BARS_MIN', 12))
        self.nft_bars_max = int(os.getenv('NO_FOLLOW_BARS_MAX', 16))
        self.nft_min_mfe_r = float(os.getenv('NO_FOLLOW_MIN_MFE_R', 0.5))

        # Load existing positions from file
        self._load_positions()

    def _save_positions(self):
        """Save positions to file for persistence across restarts"""
        try:
            positions_data = {}
            for symbol, pos in self.positions.items():
                positions_data[symbol] = {
                    'symbol': pos.symbol,
                    'direction': pos.direction,
                    'entry_price': pos.entry_price,
                    'size_usdt': pos.size_usdt,
                    'stop_loss': pos.stop_loss,
                    'regime': pos.regime,
                    'entry_time': pos.entry_time.isoformat(),
                    'tp1_hit': pos.tp1_hit,
                    'tp2_hit': pos.tp2_hit,
                    'remaining_pct': pos.remaining_pct,
                    'trailing_stop': pos.trailing_stop,
                    'initial_risk_r': pos.initial_risk_r,
                    'r_dollars': pos.r_dollars,
                    'mfe_r': pos.mfe_r,
                    'mae_r': pos.mae_r,
                    'highest_price': pos.highest_price,
                    'lowest_price': pos.lowest_price,
                    'bars_since_entry': pos.bars_since_entry
                }

            with open(self.positions_file, 'w') as f:
                json.dump(positions_data, f, indent=2)

        except Exception as e:
            print(f"[PositionManager] Error saving positions: {e}")

    def _load_positions(self):
        """Load positions from file on startup"""
        try:
            if not os.path.exists(self.positions_file):
                return

            with open(self.positions_file, 'r') as f:
                positions_data = json.load(f)

            for symbol, data in positions_data.items():
                pos = Position(
                    symbol=data['symbol'],
                    direction=data['direction'],
                    entry_price=data['entry_price'],
                    size_usdt=data['size_usdt'],
                    stop_loss=data['stop_loss'],
                    regime=data['regime']
                )
                # Restore state
                pos.entry_time = datetime.fromisoformat(data['entry_time'])
                pos.tp1_hit = data['tp1_hit']
                pos.tp2_hit = data['tp2_hit']
                pos.remaining_pct = data['remaining_pct']
                pos.trailing_stop = data.get('trailing_stop')
                pos.initial_risk_r = data['initial_risk_r']
                pos.r_dollars = data['r_dollars']
                pos.mfe_r = data['mfe_r']
                pos.mae_r = data['mae_r']
                pos.highest_price = data['highest_price']
                pos.lowest_price = data['lowest_price']
                pos.bars_since_entry = data['bars_since_entry']

                self.positions[symbol] = pos

            if self.positions:
                print(f"[PositionManager] Loaded {len(self.positions)} position(s) from file")

        except Exception as e:
            print(f"[PositionManager] Error loading positions: {e}")

    def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        size_usdt: float,
        stop_loss: float,
        regime: str,
        atr: float
    ) -> Position:
        """
        Open new position

        Args:
            symbol: Trading pair
            direction: "LONG" or "SHORT"
            entry_price: Actual fill price (from execution engine)
            size_usdt: Position size in USDT
            stop_loss: Initial stop loss price
            regime: Current regime (BULL/SIDEWAYS/BEAR)
            atr: ATR for trailing stop calculation

        Returns:
            Position object
        """
        # Calculate R metrics
        if direction == "LONG":
            initial_risk_r = entry_price - stop_loss
        else:  # SHORT
            initial_risk_r = stop_loss - entry_price

        r_dollars = size_usdt * (initial_risk_r / entry_price) if entry_price > 0 else 0

        position = Position(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            current_price=entry_price,
            size_usdt=size_usdt,
            stop_loss=stop_loss,
            entry_time=datetime.now(),
            regime=regime,
            initial_risk_r=initial_risk_r,
            r_dollars=r_dollars,
            highest_price=entry_price,
            lowest_price=entry_price
        )

        self.positions[symbol] = position

        print(f"\n✅ POSITION OPENED: {symbol}")
        print(f"   Direction: {direction}")
        print(f"   Entry: ${entry_price:.4f}")
        print(f"   Size: ${size_usdt:.2f}")
        print(f"   Stop: ${stop_loss:.4f}")
        print(f"   Risk: {r_dollars:.2f} (1R)")
        print(f"   Regime: {regime}")

        # Send Telegram alert
        if self.telegram:
            self._send_open_alert(position)

        # Save positions to file
        self._save_positions()

        return position

    def update_positions(self, current_equity: float):
        """
        Update all open positions and check for exits

        Should be called every bar (15m)
        """
        if not self.positions:
            return

        closed_symbols = []

        for symbol, position in self.positions.items():
            # Fetch current price
            ticker = self.mexc_client.get_ticker_24h(symbol)
            if not ticker:
                continue

            current_price = float(ticker['lastPrice'])
            position.current_price = current_price
            position.bars_since_entry += 1

            # Update high water marks
            if position.direction == "LONG":
                position.highest_price = max(position.highest_price, current_price)
                position.mfe_r = (position.highest_price - position.entry_price) / position.initial_risk_r
                position.mae_r = (position.entry_price - position.lowest_price) / position.initial_risk_r
            else:  # SHORT
                position.lowest_price = min(position.lowest_price, current_price)
                position.mfe_r = (position.entry_price - position.lowest_price) / position.initial_risk_r
                position.mae_r = (current_price - position.entry_price) / position.initial_risk_r

            # Current P&L in R
            if position.direction == "LONG":
                current_r = (current_price - position.entry_price) / position.initial_risk_r
            else:
                current_r = (position.entry_price - current_price) / position.initial_risk_r

            # Check exits
            should_close, reason = self._check_exits(position, current_r, current_price)

            if should_close:
                self._close_position(position, current_price, reason, current_equity)
                closed_symbols.append(symbol)

        # Remove closed positions
        for symbol in closed_symbols:
            del self.positions[symbol]

        # Save positions after updates
        if closed_symbols or self.positions:
            self._save_positions()

    def _check_exits(
        self,
        position: Position,
        current_r: float,
        current_price: float
    ) -> tuple:
        """
        Check all exit conditions

        Returns:
            (should_close: bool, reason: str)
        """
        # 1. STOP LOSS
        if position.direction == "LONG":
            if current_price <= position.stop_loss:
                return True, "STOP_LOSS"
        else:  # SHORT
            if current_price >= position.stop_loss:
                return True, "STOP_LOSS"

        # 2. TAKE PROFIT 1
        if not position.tp1_hit:
            tp1_r = self.tp1_r_long if position.direction == "LONG" else self.tp1_r_short
            if current_r >= tp1_r:
                # Take 50%, move stop to breakeven
                position.tp1_hit = True
                position.remaining_pct = 0.50
                position.stop_loss = position.entry_price  # Breakeven
                print(f"   🎯 TP1 hit ({tp1_r:.1f}R) - Taking 50%, moved stop to breakeven")

                # Don't close yet, just partial exit
                return False, ""

        # 3. TAKE PROFIT 2
        if position.tp1_hit and not position.tp2_hit:
            tp2_r = self.tp2_r_long if position.direction == "LONG" else self.tp2_r_short
            if current_r >= tp2_r:
                # Take another 30% (20% remaining)
                position.tp2_hit = True
                position.remaining_pct = 0.20
                print(f"   🎯 TP2 hit ({tp2_r:.1f}R) - Taking 30%, 20% remaining")

                # Initialize trailing stop
                atr_mult = self.trail_mult_long if position.direction == "LONG" else self.trail_mult_short
                if position.direction == "LONG":
                    position.trailing_stop = position.highest_price - (atr_mult * position.initial_risk_r)
                else:
                    position.trailing_stop = position.lowest_price + (atr_mult * position.initial_risk_r)

                return False, ""

        # 4. TRAILING STOP (after TP2)
        if position.tp2_hit and position.trailing_stop:
            atr_mult = self.trail_mult_long if position.direction == "LONG" else self.trail_mult_short

            if position.direction == "LONG":
                # Update trailing stop
                new_trail = position.highest_price - (atr_mult * position.initial_risk_r)
                position.trailing_stop = max(position.trailing_stop, new_trail)

                if current_price <= position.trailing_stop:
                    return True, "TRAILING_STOP"
            else:  # SHORT
                new_trail = position.lowest_price + (atr_mult * position.initial_risk_r)
                position.trailing_stop = min(position.trailing_stop, new_trail)

                if current_price >= position.trailing_stop:
                    return True, "TRAILING_STOP"

        # 5. NO-FOLLOW-THROUGH RULE
        if (self.nft_bars_min <= position.bars_since_entry <= self.nft_bars_max):
            # Check MFE and current P&L
            if (position.mfe_r < self.nft_min_mfe_r and
                -0.5 <= current_r <= 0.2):
                return True, "NO_FOLLOW_THROUGH"

        # 6. TIME EXIT
        max_hold_hours = self._get_max_hold_hours(position.regime, position.direction)
        hours_held = (datetime.now() - position.entry_time).total_seconds() / 3600

        if hours_held >= max_hold_hours:
            return True, "TIME_EXIT"

        return False, ""

    def _get_max_hold_hours(self, regime: str, direction: str) -> float:
        """Get max hold time for regime and direction"""
        if direction == "LONG":
            if regime == "BULL":
                return float(os.getenv('MAX_HOLD_HOURS_BULL_LONG', 48))
            else:  # SIDEWAYS
                return float(os.getenv('MAX_HOLD_HOURS_SIDEWAYS_LONG', 24))
        else:  # SHORT
            return float(os.getenv('MAX_HOLD_HOURS_BEAR_SHORT', 36))

    def _close_position(
        self,
        position: Position,
        exit_price: float,
        reason: str,
        current_equity: float
    ):
        """Close position and record results"""
        # Calculate P&L
        if position.direction == "LONG":
            pnl_r = (exit_price - position.entry_price) / position.initial_risk_r
            pnl_pct = (exit_price / position.entry_price - 1) * 100
        else:  # SHORT
            pnl_r = (position.entry_price - exit_price) / position.initial_risk_r
            pnl_pct = (1 - exit_price / position.entry_price) * 100

        # Apply fees (TAKER_FEE_PCT)
        taker_fee_pct = float(os.getenv('TAKER_FEE_PCT', 0.1)) / 100.0
        fee_impact_r = taker_fee_pct * 2  # Entry + exit fees

        pnl_r_after_fees = pnl_r - fee_impact_r
        pnl_usd = pnl_r_after_fees * position.r_dollars * position.remaining_pct

        # Hold time
        hold_hours = (datetime.now() - position.entry_time).total_seconds() / 3600

        print(f"\n❌ POSITION CLOSED: {position.symbol}")
        print(f"   Reason: {reason}")
        print(f"   Exit: ${exit_price:.4f}")
        print(f"   P&L: {pnl_r_after_fees:+.2f}R (${pnl_usd:+.2f})")
        print(f"   Hold: {hold_hours:.1f}h")
        print(f"   MFE: {position.mfe_r:.2f}R | MAE: {position.mae_r:.2f}R")

        # Send Telegram alert
        if self.telegram:
            self._send_close_alert(position, exit_price, pnl_r_after_fees, pnl_usd, hold_hours, reason)

    def _send_open_alert(self, position: Position):
        """Send position opened alert via Telegram"""
        try:
            message = f"""
🟢 **POSITION OPENED**

**Symbol:** {position.symbol}
**Direction:** {position.direction}
**Entry:** ${position.entry_price:.4f}
**Size:** ${position.size_usdt:.2f}
**Stop:** ${position.stop_loss:.4f}
**Risk:** ${position.r_dollars:.2f} (1R)
**Regime:** {position.regime}
"""
            self.telegram.send_message(message)
        except Exception as e:
            print(f"[Telegram] Error sending open alert: {e}")

    def _send_close_alert(
        self,
        position: Position,
        exit_price: float,
        pnl_r: float,
        pnl_usd: float,
        hold_hours: float,
        reason: str
    ):
        """Send position closed alert via Telegram"""
        try:
            # Calculate percentage gain
            if position.direction == "LONG":
                pnl_pct = (exit_price / position.entry_price - 1) * 100
            else:  # SHORT
                pnl_pct = (1 - exit_price / position.entry_price) * 100

            # Apply fee impact to percentage
            taker_fee_pct = float(os.getenv('TAKER_FEE_PCT', 0.1)) / 100.0
            pnl_pct_after_fees = pnl_pct - (taker_fee_pct * 2 * 100)

            # Emoji based on P&L
            emoji = "🟢" if pnl_r > 0 else "🔴"
            result = "WIN" if pnl_r > 0 else "LOSS"

            message = f"""
{emoji} **POSITION CLOSED - {result}**

**Symbol:** {position.symbol}
**Direction:** {position.direction}
**Entry:** ${position.entry_price:.4f}
**Exit:** ${exit_price:.4f}

**💰 PROFIT/LOSS:**
• **R-Multiple:** {pnl_r:+.2f}R
• **Percentage:** {pnl_pct_after_fees:+.2f}%
• **USD P&L:** ${pnl_usd:+.2f}

**📊 TRADE STATS:**
• **Hold Time:** {hold_hours:.1f}h ({hold_hours/24:.1f} days)
• **MFE:** {position.mfe_r:.2f}R (best)
• **MAE:** {position.mae_r:.2f}R (worst)
• **Exit Reason:** {reason}

**⏰ Closed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.telegram.send_message(message)
        except Exception as e:
            print(f"[Telegram] Error sending close alert: {e}")

    def get_open_positions_count(self) -> int:
        """Get count of open positions"""
        return len(self.positions)

    def get_portfolio_heat(self) -> float:
        """Calculate total portfolio heat (sum of R at risk)"""
        total_heat = 0.0
        for position in self.positions.values():
            # Heat = current distance to stop in R terms
            if position.direction == "LONG":
                risk_r = (position.current_price - position.stop_loss) / position.initial_risk_r
            else:
                risk_r = (position.stop_loss - position.current_price) / position.initial_risk_r

            total_heat += max(risk_r, 0) * position.remaining_pct

        return total_heat


# Singleton instance (initialized in main)
position_manager = None
