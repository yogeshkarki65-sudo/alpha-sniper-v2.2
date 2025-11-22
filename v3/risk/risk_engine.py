#!/usr/bin/env python3
"""
Risk Engine - Position management and R-based risk controls

V4.2 UPDATES:
- Added pump_long engine support for new token pump catcher
- Dynamic pump allocation (20-35% equity slice)
- pump_long multi-TP: TP1 @ 1.5R (40%), TP2 @ 3.0R (40%), trailing (20%)
- pump_long NFT dead rule: exit after 3.5h if flat (-1% to +1%)
- pump_long max hold: 6 hours

V4.1.1 UPDATES:
- R-based position sizing using RISK_PER_TRADE_* from .env
- Portfolio heat = sum of initial R (risk dollars), not exposure
- MAX_PORTFOLIO_HEAT enforced in R-terms (default 1.5%)
- SIM/LIVE and SPOT/FUTURES mode handling
- Engine-specific risk parameters (standard_long, standard_short, bear_resilient_long, pump_long)
- Telegram notifications for trade open/close
- Multi-TP exits for standard_long: TP1 @ 1.5R (40%), TP2 @ 3R (40%), trailing (20%)
- NFT rule for standard_long: exit dead trades after 3-4 hours
- Trade score CSV logging
"""

import csv
import json
import os
from typing import Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict, field
from pathlib import Path

# Import telegram notifier (fails silently if not configured)
try:
    from v3.monitoring.telegram_notifier import telegram
except ImportError:
    telegram = None


@dataclass
class Position:
    """
    Open position tracker with R-based risk tracking and multi-TP exits.

    Key fields:
    - initial_risk_usd: The R value (dollars risked at entry)
    - size_usd: Actual position size in USD
    - engine: Which engine created this position

    Multi-TP Exit Logic (standard_long):
    - TP1 @ 1.5R: Exit 40%, move SL to breakeven
    - TP2 @ 3R: Exit 40%
    - Trailing: Remaining 20% with ATR-based trailing stop
    """
    symbol: str
    direction: str  # LONG or SHORT
    entry_price: float
    size_usd: float
    stop_loss: float
    initial_risk_usd: float  # R value - dollars at risk
    take_profit: Optional[float] = None
    timestamp: Optional[datetime] = None
    engine: str = 'standard_long'
    regime: str = 'SIDEWAYS'
    score: int = 0  # Signal score at entry (for logging)
    atr_15m: float = 0  # ATR for trailing stop calculation

    # Performance tracking
    mfe_pct: float = 0  # Maximum Favorable Excursion
    mae_pct: float = 0  # Maximum Adverse Excursion
    current_pnl_pct: float = 0
    highest_price: float = 0  # For trailing stop
    bars_since_entry: int = 0  # For NFT rule (15m bars)

    # Exit tracking
    tp1_hit: bool = False
    tp2_hit: bool = False
    sl_moved_to_be: bool = False  # Stop loss moved to breakeven
    remaining_size_pct: float = 100  # % of position still open
    original_stop_loss: float = 0  # Store original SL before moving to BE

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.highest_price == 0:
            self.highest_price = self.entry_price
        if self.original_stop_loss == 0:
            self.original_stop_loss = self.stop_loss

    def get_r_value(self) -> float:
        """Get R value as a fraction (e.g., 0.03 for 3% SL)."""
        return abs(self.entry_price - self.original_stop_loss) / self.entry_price

    def get_current_r_multiple(self, current_price: float) -> float:
        """Get current P&L as R-multiple."""
        r_value = self.get_r_value()
        if r_value <= 0:
            return 0
        if self.direction == 'LONG':
            pnl_pct = (current_price - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - current_price) / self.entry_price
        return pnl_pct / r_value

    def update_pnl(self, current_price: float):
        """Update P&L and MFE/MAE tracking."""
        if self.direction == 'LONG':
            pnl_pct = (current_price / self.entry_price - 1) * 100
            if current_price > self.highest_price:
                self.highest_price = current_price
        else:  # SHORT
            pnl_pct = (self.entry_price / current_price - 1) * 100
            if current_price < self.highest_price:
                self.highest_price = current_price

        self.current_pnl_pct = pnl_pct

        # Update MFE/MAE
        if pnl_pct > self.mfe_pct:
            self.mfe_pct = pnl_pct
        if pnl_pct < self.mae_pct:
            self.mae_pct = pnl_pct

    def should_exit(self, current_price: float, hours_held: float) -> Tuple[bool, str, float]:
        """
        Check if position should be exited with multi-TP logic.

        Returns:
            (should_exit: bool, reason: str, exit_pct: float)
            exit_pct is percentage of REMAINING position to close (not original)
        """
        r_multiple = self.get_current_r_multiple(current_price)
        r_value = self.get_r_value()

        # === STOP LOSS CHECK ===
        if self.direction == 'LONG' and current_price <= self.stop_loss:
            return (True, "Stop loss hit", 100)
        elif self.direction == 'SHORT' and current_price >= self.stop_loss:
            return (True, "Stop loss hit", 100)

        # === MULTI-TP LOGIC FOR STANDARD_LONG ===
        if self.engine == 'standard_long' and self.direction == 'LONG':
            return self._check_standard_long_exits(current_price, hours_held, r_multiple, r_value)

        # === V4.2: PUMP_LONG EXITS ===
        if self.engine == 'pump_long':
            return self._check_pump_long_exits(current_price, hours_held, r_multiple, r_value)

        # === BEAR_RESILIENT_LONG EXITS (existing logic) ===
        if self.engine == 'bear_resilient_long':
            return self._check_bear_resilient_exits(current_price, hours_held, r_multiple, r_value)

        # === SIMPLE EXIT FOR OTHER ENGINES ===
        # Take profit hit (fallback for engines without multi-TP)
        if self.take_profit:
            if self.direction == 'LONG' and current_price >= self.take_profit:
                return (True, "Take profit hit", 100)
            elif self.direction == 'SHORT' and current_price <= self.take_profit:
                return (True, "Take profit hit", 100)

        # Max hold time
        max_hold_hours = 72
        if hours_held >= max_hold_hours:
            return (True, f"Max hold time ({max_hold_hours}h) reached", 100)

        return (False, "", 0)

    def _check_standard_long_exits(
        self, current_price: float, hours_held: float, r_multiple: float, r_value: float
    ) -> Tuple[bool, str, float]:
        """
        Multi-TP exit logic for standard_long:
        - TP1 @ 1.5R: Exit 40% of original, move SL to breakeven
        - TP2 @ 3R: Exit 40% of original (80% total closed)
        - Trailing: Remaining 20% with ATR-based stop
        - NFT: Exit dead trades after 3-4 hours
        """
        # TP1 @ 1.5R - Exit 40%, move SL to breakeven
        if not self.tp1_hit and r_multiple >= 1.5:
            self.tp1_hit = True
            self.sl_moved_to_be = True
            self.stop_loss = self.entry_price  # Move SL to breakeven
            self.remaining_size_pct = 60  # 40% closed, 60% remaining
            return (True, "TP1 hit @ 1.5R - closing 40%, SL to breakeven", 40)

        # TP2 @ 3R - Exit another 40% (80% total closed)
        if self.tp1_hit and not self.tp2_hit and r_multiple >= 3.0:
            self.tp2_hit = True
            self.remaining_size_pct = 20  # Another 40% closed, 20% remaining
            return (True, "TP2 hit @ 3R - closing 40%, trailing remaining 20%", 67)  # 40/60 = 67% of remaining

        # Trailing stop on remaining 20% (after TP2)
        if self.tp2_hit and self.remaining_size_pct > 0:
            trailing_stop = self._calculate_trailing_stop()
            if current_price <= trailing_stop:
                return (True, f"Trailing stop hit @ ${trailing_stop:.6f}", 100)

        # NFT Rule: Exit dead trades after 3-4 hours (12-16 bars at 15m)
        # If MFE < 0.5R and PnL between -0.5R and +0.2R after ~3.5 hours
        if hours_held >= 3.5:
            mfe_in_r = self.mfe_pct / 100 / r_value if r_value > 0 else 0
            if mfe_in_r < 0.5 and -0.5 <= r_multiple <= 0.2:
                return (True, "NFT rule: Dead trade (MFE < 0.5R after 3.5h)", 100)

        # Max hold time for standard_long
        max_hold_hours = 72  # 3 days
        if hours_held >= max_hold_hours:
            return (True, f"Max hold time ({max_hold_hours}h) reached", 100)

        return (False, "", 0)

    def _check_bear_resilient_exits(
        self, current_price: float, hours_held: float, r_multiple: float, r_value: float
    ) -> Tuple[bool, str, float]:
        """
        Existing bear_resilient_long exit logic:
        - TP1 @ 1.5R: Exit 40%, move SL to breakeven
        - TP2 @ 2.5R: Exit 40%
        - Trailing on remaining 20%
        - NFT: Exit if MFE < 0.5R after 3h
        - Max hold: 24h
        """
        # TP1 @ 1.5R
        if not self.tp1_hit and r_multiple >= 1.5:
            self.tp1_hit = True
            self.sl_moved_to_be = True
            self.stop_loss = self.entry_price
            self.remaining_size_pct = 60
            return (True, "TP1 hit @ 1.5R - closing 40%, SL to breakeven", 40)

        # TP2 @ 2.5R (bear_resilient uses 2.5R, not 3R)
        if self.tp1_hit and not self.tp2_hit and r_multiple >= 2.5:
            self.tp2_hit = True
            self.remaining_size_pct = 20
            return (True, "TP2 hit @ 2.5R - closing 40%, trailing remaining 20%", 67)

        # Trailing stop
        if self.tp2_hit and self.remaining_size_pct > 0:
            trailing_stop = self._calculate_trailing_stop()
            if current_price <= trailing_stop:
                return (True, f"Trailing stop hit @ ${trailing_stop:.6f}", 100)

        # NFT rule
        if hours_held >= 3:
            mfe_in_r = self.mfe_pct / 100 / r_value if r_value > 0 else 0
            if mfe_in_r < 0.5:
                return (True, "NFT rule: MFE < 0.5R after 3h", 100)

        # Max hold time for bear_resilient_long
        max_hold_hours = int(os.getenv('MAX_HOLD_HOURS_BEAR_LONG', '24'))
        if hours_held >= max_hold_hours:
            return (True, f"Max hold time ({max_hold_hours}h) reached", 100)

        return (False, "", 0)

    def _check_pump_long_exits(
        self, current_price: float, hours_held: float, r_multiple: float, r_value: float
    ) -> Tuple[bool, str, float]:
        """
        V4.2: Pump engine exit logic:
        - TP1 @ 1.5R: Exit 40%, move SL to breakeven
        - TP2 @ 3.0R: Exit 40% (80% total closed)
        - Trailing on remaining 20%
        - NFT Dead: Exit if flat (-1% to +1%) after 3.5h
        - Max hold: 6h
        """
        # TP1 @ 1.5R - Exit 40%, move SL to breakeven
        if not self.tp1_hit and r_multiple >= 1.5:
            self.tp1_hit = True
            self.sl_moved_to_be = True
            self.stop_loss = self.entry_price
            self.remaining_size_pct = 60
            return (True, "Pump TP1 @ 1.5R - closing 40%, SL to breakeven", 40)

        # TP2 @ 3.0R - Exit another 40%
        if self.tp1_hit and not self.tp2_hit and r_multiple >= 3.0:
            self.tp2_hit = True
            self.remaining_size_pct = 20
            return (True, "Pump TP2 @ 3.0R - closing 40%, trailing 20%", 67)

        # Trailing stop on remaining 20%
        if self.tp2_hit and self.remaining_size_pct > 0:
            trailing_stop = self._calculate_trailing_stop()
            if current_price <= trailing_stop:
                return (True, f"Pump trailing stop @ ${trailing_stop:.6f}", 100)

        # NFT Dead Pump Rule: Exit if flat after 3.5h
        # Flat = PnL between -1% and +1%
        if hours_held >= 3.5:
            pnl_pct = (current_price / self.entry_price - 1)
            if -0.01 <= pnl_pct <= 0.01:
                return (True, f"NFT Dead pump (flat {pnl_pct*100:+.1f}% after {hours_held:.1f}h)", 100)

        # Max hold time for pump_long
        max_hold_hours = float(os.getenv('PUMP_MAX_HOLD_HOURS', '6'))
        if hours_held >= max_hold_hours:
            return (True, f"Pump max hold time ({max_hold_hours}h) reached", 100)

        return (False, "", 0)

    def _calculate_trailing_stop(self) -> float:
        """Calculate trailing stop based on highest price and ATR."""
        if self.atr_15m > 0:
            # Trailing stop = highest - 1.5 * ATR
            return self.highest_price - (1.5 * self.atr_15m)
        else:
            # Fallback: 2% below highest
            return self.highest_price * 0.98

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat() if self.timestamp else None
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Create Position from dictionary."""
        if 'timestamp' in data and data['timestamp']:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        # Handle old positions without new fields
        if 'initial_risk_usd' not in data:
            data['initial_risk_usd'] = data.get('size_usd', 0) * 0.03
        if 'original_stop_loss' not in data:
            data['original_stop_loss'] = data.get('stop_loss', 0)
        if 'score' not in data:
            data['score'] = 0
        if 'atr_15m' not in data:
            data['atr_15m'] = 0
        if 'bars_since_entry' not in data:
            data['bars_since_entry'] = 0
        return cls(**data)


class RiskEngine:
    """
    Manages open positions with R-based risk sizing.

    Key concepts:
    - R = dollars at risk per trade (entry to stop loss)
    - Position size = R / stop_distance_pct
    - Portfolio heat = sum(R) / equity (capped at MAX_PORTFOLIO_HEAT)
    """

    def __init__(self, positions_file: str = "data/positions.json"):
        self.positions_file = positions_file
        self.open_positions: Dict[str, Position] = {}
        self.trade_log_file = "logs/v4_trade_scores.csv"

        # Load config from .env
        self.mode = os.getenv('MODE', 'SIMULATION')
        self.market_type = os.getenv('MARKET_TYPE', 'SPOT')

        # Risk parameters from .env
        self.risk_per_trade = {
            'BULL': float(os.getenv('RISK_PER_TRADE_BULL', '0.003')),
            'SIDEWAYS': float(os.getenv('RISK_PER_TRADE_SIDEWAYS', '0.0025')),
            'BEAR_SHORT': float(os.getenv('RISK_PER_TRADE_BEAR_SHORT', '0.0012')),
            'BEAR_LONG': float(os.getenv('RISK_PER_TRADE_BEAR_LONG', '0.0008')),
            'PUMP_LONG': float(os.getenv('PUMP_RISK_PER_TRADE', '0.001')),  # V4.2
        }

        # Portfolio limits
        self.max_portfolio_heat = float(os.getenv('MAX_PORTFOLIO_HEAT', '0.015'))  # 1.5% default
        self.max_concurrent_positions = int(os.getenv('MAX_CONCURRENT_POSITIONS', '5'))
        self.max_concurrent_bear_longs = int(os.getenv('MAX_CONCURRENT_BEAR_LONGS', '1'))
        self.max_concurrent_pump_longs = int(os.getenv('PUMP_MAX_CONCURRENT', '2'))  # V4.2

        # V4.2 Pump engine allocation
        self.pump_alloc_min = float(os.getenv('PUMP_ALLOC_MIN', '0.20'))
        self.pump_alloc_max = float(os.getenv('PUMP_ALLOC_MAX', '0.35'))
        self.pump_max_hold_hours = float(os.getenv('PUMP_MAX_HOLD_HOURS', '6'))

        self._load_positions()
        self._ensure_log_file()
        print(f"[RiskEngine] Initialized - {len(self.open_positions)} open positions")
        print(f"   Mode: {self.mode}, Market: {self.market_type}")
        print(f"   Max portfolio heat: {self.max_portfolio_heat*100:.2f}%")

    def _ensure_log_file(self):
        """Ensure trade log CSV exists with headers."""
        log_path = Path(self.trade_log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not log_path.exists():
            with open(log_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp_close', 'symbol', 'engine', 'regime', 'score',
                    'entry_price', 'exit_price', 'r_multiple', 'pnl_pct',
                    'hold_time_hours', 'exit_reason', 'win_or_loss'
                ])

    def get_risk_per_trade(self, regime: str, engine: str) -> float:
        """
        Get risk per trade based on regime and engine.

        Returns fraction of equity to risk (e.g., 0.003 = 0.3%)
        """
        if engine == 'pump_long':
            return self.risk_per_trade['PUMP_LONG']
        elif engine == 'bear_resilient_long':
            return self.risk_per_trade['BEAR_LONG']
        elif engine == 'standard_short':
            return self.risk_per_trade['BEAR_SHORT']
        elif regime == 'BULL':
            return self.risk_per_trade['BULL']
        else:  # SIDEWAYS or default
            return self.risk_per_trade['SIDEWAYS']

    def calculate_position_size(
        self,
        signal: dict,
        equity: float
    ) -> tuple:
        """
        Calculate R-based position size.

        Args:
            signal: Signal dict with entry_price, stop_loss, engine, regime
            equity: Current account equity

        Returns:
            (size_usd, initial_risk_usd, reason) or (0, 0, error_reason)
        """
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        engine = signal.get('engine', 'standard_long')
        regime = signal.get('regime', 'SIDEWAYS')

        # Calculate stop distance
        if signal['direction'] == 'LONG':
            stop_distance_pct = (entry_price - stop_loss) / entry_price
        else:  # SHORT
            stop_distance_pct = (stop_loss - entry_price) / entry_price

        if stop_distance_pct <= 0:
            return (0, 0, "Invalid stop distance")

        # Get risk per trade for this regime/engine
        risk_pct = self.get_risk_per_trade(regime, engine)

        # Calculate R (dollars at risk)
        initial_risk_usd = equity * risk_pct

        # Calculate position size: size = R / stop_distance
        size_usd = initial_risk_usd / stop_distance_pct

        # Cap size at reasonable limits
        max_size_pct = 0.20  # Max 20% of equity per position
        if engine == 'bear_resilient_long':
            max_size_pct = 0.05  # Max 5% for bear micro-longs
        elif engine == 'pump_long':
            # V4.2: Pump trades use dynamic allocation slice
            # Max 20% of pump allocation per position
            pump_alloc = float(os.getenv('PUMP_ALLOC_MAX', '0.35'))
            max_size_pct = pump_alloc * 0.20  # ~7% of total equity

        max_size_usd = equity * max_size_pct
        if size_usd > max_size_usd:
            size_usd = max_size_usd
            # Recalculate actual R based on capped size
            initial_risk_usd = size_usd * stop_distance_pct

        return (size_usd, initial_risk_usd, "OK")

    def can_open_position(
        self,
        signal: dict,
        equity: float
    ) -> tuple:
        """
        Check if we can open a new position with R-based risk.

        Returns:
            (can_open: bool, reason: str, size_usd: float, initial_risk_usd: float)
        """
        engine = signal.get('engine', 'standard_long')
        direction = signal.get('direction', 'LONG')

        # Check SPOT market constraints
        if self.market_type == 'SPOT' and direction == 'SHORT':
            return (False, "SPOT market: cannot short", 0, 0)

        # Check max concurrent positions
        if len(self.open_positions) >= self.max_concurrent_positions:
            return (False, f"Max concurrent positions ({self.max_concurrent_positions}) reached", 0, 0)

        # Check engine-specific limits
        if engine == 'bear_resilient_long':
            current_bear_longs = sum(
                1 for pos in self.open_positions.values()
                if pos.engine == 'bear_resilient_long'
            )
            if current_bear_longs >= self.max_concurrent_bear_longs:
                return (False, f"Max bear-resilient longs ({self.max_concurrent_bear_longs}) reached", 0, 0)

        # V4.2: Pump engine limits
        if engine == 'pump_long':
            current_pump_longs = sum(
                1 for pos in self.open_positions.values()
                if pos.engine == 'pump_long'
            )
            if current_pump_longs >= self.max_concurrent_pump_longs:
                return (False, f"Max pump longs ({self.max_concurrent_pump_longs}) reached", 0, 0)

        # Calculate position size
        size_usd, initial_risk_usd, calc_reason = self.calculate_position_size(signal, equity)
        if size_usd == 0:
            return (False, f"Size calculation failed: {calc_reason}", 0, 0)

        # Check portfolio heat (R-based)
        current_heat = self._calculate_portfolio_heat(equity)
        new_heat = initial_risk_usd / equity

        if current_heat + new_heat > self.max_portfolio_heat:
            return (False, f"Portfolio heat limit exceeded ({current_heat*100:.2f}% + {new_heat*100:.2f}% > {self.max_portfolio_heat*100:.2f}%)", 0, 0)

        return (True, "OK", size_usd, initial_risk_usd)

    def open_position(self, signal: dict, equity: float) -> Optional[Position]:
        """
        Open a new position with R-based sizing.

        Args:
            signal: Signal dict from scanner
            equity: Current account equity

        Returns:
            Position object or None if cannot open
        """
        symbol = signal['symbol']
        engine = signal.get('engine', 'standard_long')

        # Check if we can open and get calculated size
        can_open, reason, size_usd, initial_risk_usd = self.can_open_position(signal, equity)
        if not can_open:
            print(f"[RiskEngine] Cannot open {symbol}: {reason}")
            return None

        # Create position with new fields
        position = Position(
            symbol=symbol,
            direction=signal['direction'],
            entry_price=signal['entry_price'],
            size_usd=size_usd,
            stop_loss=signal['stop_loss'],
            initial_risk_usd=initial_risk_usd,
            take_profit=signal.get('take_profit'),
            engine=engine,
            regime=signal.get('regime', 'SIDEWAYS'),
            score=signal.get('score', 0),
            atr_15m=signal.get('atr_15m', signal['entry_price'] * 0.02),
            timestamp=signal.get('timestamp', datetime.now())
        )

        self.open_positions[symbol] = position
        self._save_positions()

        stop_distance_pct = abs(signal['entry_price'] - signal['stop_loss']) / signal['entry_price'] * 100
        print(f"✅ [RiskEngine] Opened {signal['direction']} position: {symbol}")
        print(f"   Entry: ${signal['entry_price']:.6f} | Stop: ${signal['stop_loss']:.6f} ({stop_distance_pct:.2f}%)")
        print(f"   Size: ${size_usd:.2f} | Risk (R): ${initial_risk_usd:.2f} | Engine: {engine}")

        # Send Telegram notification
        if telegram:
            telegram.send_trade_opened(
                symbol=symbol,
                direction=signal['direction'],
                entry_price=signal['entry_price'],
                stop_loss=signal['stop_loss'],
                size_usd=size_usd,
                risk_usd=initial_risk_usd,
                engine=engine
            )

        return position

    def close_position(self, symbol: str, exit_price: float, reason: str, exit_pct: float = 100) -> Optional[dict]:
        """
        Close an open position (fully or partially) and return trade result.

        Args:
            exit_pct: Percentage of REMAINING position to close (default 100 = full close)
        """
        if symbol not in self.open_positions:
            return None

        position = self.open_positions[symbol]

        # Calculate final P&L
        if position.direction == 'LONG':
            pnl_pct = (exit_price / position.entry_price - 1) * 100
        else:
            pnl_pct = (position.entry_price / exit_price - 1) * 100

        # Calculate size being closed
        remaining_size = position.size_usd * (position.remaining_size_pct / 100)
        closing_size = remaining_size * (exit_pct / 100)
        pnl_usd = closing_size * (pnl_pct / 100)

        # Calculate R-multiple
        r_value = position.get_r_value()
        r_multiple = (pnl_pct / 100) / r_value if r_value > 0 else 0

        hold_time_hours = (datetime.now() - position.timestamp).total_seconds() / 3600

        # Build trade result
        trade_result = {
            'symbol': symbol,
            'direction': position.direction,
            'engine': position.engine,
            'regime': position.regime,
            'score': position.score,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'size_usd': closing_size,
            'initial_risk_usd': position.initial_risk_usd,
            'pnl_usd': pnl_usd,
            'pnl_pct': pnl_pct,
            'r_multiple': r_multiple,
            'mfe_pct': position.mfe_pct,
            'mae_pct': position.mae_pct,
            'hold_time_hours': hold_time_hours,
            'exit_reason': reason,
            'exit_pct': exit_pct,
            'timestamp_entry': position.timestamp.isoformat(),
            'timestamp_exit': datetime.now().isoformat()
        }

        # Handle partial vs full close
        if exit_pct >= 100 or position.remaining_size_pct <= 0.01:
            # Full close - remove position
            del self.open_positions[symbol]
            self._log_trade(trade_result)
        else:
            # Partial close - update remaining size
            position.remaining_size_pct = position.remaining_size_pct * (1 - exit_pct / 100)

        self._save_positions()

        print(f"🔴 [RiskEngine] Closed {position.direction}: {symbol} @ ${exit_price:.6f}")
        print(f"   P&L: ${pnl_usd:.2f} ({pnl_pct:+.2f}%) | R-Multiple: {r_multiple:+.2f}R | Reason: {reason}")

        # Send Telegram notification
        if telegram:
            telegram.send_trade_closed(
                symbol=symbol,
                direction=position.direction,
                entry_price=position.entry_price,
                exit_price=exit_price,
                pnl_usd=pnl_usd,
                pnl_pct=pnl_pct,
                r_multiple=r_multiple,
                hold_time_hours=hold_time_hours,
                reason=reason,
                engine=position.engine
            )

        return trade_result

    def _log_trade(self, trade_result: dict):
        """Log closed trade to CSV file."""
        try:
            with open(self.trade_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    trade_result['timestamp_exit'],
                    trade_result['symbol'],
                    trade_result['engine'],
                    trade_result['regime'],
                    trade_result['score'],
                    trade_result['entry_price'],
                    trade_result['exit_price'],
                    f"{trade_result['r_multiple']:.2f}",
                    f"{trade_result['pnl_pct']:.2f}",
                    f"{trade_result['hold_time_hours']:.2f}",
                    trade_result['exit_reason'],
                    'WIN' if trade_result['pnl_usd'] > 0 else 'LOSS'
                ])
        except Exception as e:
            print(f"[RiskEngine] Error logging trade: {e}")

    def update_positions(self, current_prices: Dict[str, float]):
        """Update all open positions with current prices."""
        for symbol, position in self.open_positions.items():
            if symbol in current_prices:
                position.update_pnl(current_prices[symbol])
        self._save_positions()

    def _calculate_portfolio_heat(self, equity: float) -> float:
        """
        Calculate current portfolio heat in R-terms.

        Portfolio heat = sum(initial_risk_usd) / equity
        """
        total_risk_usd = sum(pos.initial_risk_usd for pos in self.open_positions.values())
        return total_risk_usd / equity if equity > 0 else 0

    def get_portfolio_summary(self, equity: float) -> dict:
        """Get portfolio summary for status display."""
        total_risk = sum(pos.initial_risk_usd for pos in self.open_positions.values())
        total_size = sum(pos.size_usd for pos in self.open_positions.values())
        total_pnl = sum(pos.size_usd * pos.current_pnl_pct / 100 for pos in self.open_positions.values())

        return {
            'open_positions': len(self.open_positions),
            'total_size_usd': total_size,
            'total_risk_usd': total_risk,
            'portfolio_heat_pct': (total_risk / equity * 100) if equity > 0 else 0,
            'unrealized_pnl_usd': total_pnl,
            'max_heat_pct': self.max_portfolio_heat * 100,
            'mode': self.mode,
            'market_type': self.market_type
        }

    def _load_positions(self):
        """Load positions from JSON file."""
        if not os.path.exists(self.positions_file):
            return

        try:
            with open(self.positions_file, 'r') as f:
                data = json.load(f)
                positions_data = data.get('open_positions', [])

                for pos_dict in positions_data:
                    try:
                        position = Position.from_dict(pos_dict)
                        self.open_positions[position.symbol] = position
                    except Exception as e:
                        print(f"[RiskEngine] Error loading position: {e}")

        except Exception as e:
            print(f"[RiskEngine] Error loading positions file: {e}")

    def _save_positions(self):
        """Save positions to JSON file."""
        os.makedirs(os.path.dirname(self.positions_file), exist_ok=True)

        data = {
            'open_positions': [pos.to_dict() for pos in self.open_positions.values()],
            'last_updated': datetime.now().isoformat()
        }

        try:
            with open(self.positions_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[RiskEngine] Error saving positions: {e}")


# Global instance
risk_engine = RiskEngine()
