#!/usr/bin/env python3
"""
Risk Engine - Position management and risk controls

NEW FEATURE: Track which engine created each position (standard vs bear_resilient_long)
"""

import json
import os
from typing import Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


@dataclass
class Position:
    """
    Open position tracker.

    NEW FEATURE: Added 'engine' parameter to track signal source.
    """
    symbol: str
    direction: str  # LONG or SHORT
    entry_price: float
    size_usd: float
    stop_loss: float
    take_profit: Optional[float] = None
    timestamp: Optional[datetime] = None
    engine: str = 'standard'  # NEW: 'standard' or 'bear_resilient_long'

    # Performance tracking
    mfe_pct: float = 0  # Maximum Favorable Excursion
    mae_pct: float = 0  # Maximum Adverse Excursion
    current_pnl_pct: float = 0

    # Exit tracking
    tp1_hit: bool = False
    tp2_hit: bool = False
    sl_moved_to_be: bool = False  # Stop loss moved to breakeven

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def update_pnl(self, current_price: float):
        """Update P&L and MFE/MAE tracking."""
        if self.direction == 'LONG':
            pnl_pct = (current_price / self.entry_price - 1) * 100
        else:  # SHORT
            pnl_pct = (self.entry_price / current_price - 1) * 100

        self.current_pnl_pct = pnl_pct

        # Update MFE/MAE
        if pnl_pct > self.mfe_pct:
            self.mfe_pct = pnl_pct

        if pnl_pct < self.mae_pct:
            self.mae_pct = pnl_pct

    def should_exit(self, current_price: float, hours_held: float) -> tuple:
        """
        Check if position should be exited.

        Returns:
            (should_exit: bool, reason: str, exit_pct: float)
            exit_pct: percentage of position to exit (0-100)
        """
        # Stop loss hit
        if self.direction == 'LONG' and current_price <= self.stop_loss:
            return (True, "Stop loss hit", 100)
        elif self.direction == 'SHORT' and current_price >= self.stop_loss:
            return (True, "Stop loss hit", 100)

        # Take profit hit
        if self.take_profit:
            if self.direction == 'LONG' and current_price >= self.take_profit:
                return (True, "Take profit hit", 100)
            elif self.direction == 'SHORT' and current_price <= self.take_profit:
                return (True, "Take profit hit", 100)

        # Max hold time (if set)
        max_hold_hours = 24
        if self.engine == 'bear_resilient_long':
            max_hold_hours = int(os.getenv('MAX_HOLD_HOURS_BEAR_LONG', '24'))

        if hours_held >= max_hold_hours:
            return (True, f"Max hold time ({max_hold_hours}h) reached", 100)

        return (False, "", 0)

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
        return cls(**data)


class RiskEngine:
    """
    Manages open positions and enforces risk limits.

    NEW FEATURE: Tracks position engine (standard vs bear_resilient_long) for routing.
    """

    def __init__(self, positions_file: str = "data/positions.json"):
        self.positions_file = positions_file
        self.open_positions: Dict[str, Position] = {}
        self.max_concurrent_positions = 3
        self.max_portfolio_heat_pct = 10.0  # Max % of equity at risk

        self._load_positions()
        print(f"[RiskEngine] Initialized - {len(self.open_positions)} open positions")

    def can_open_position(
        self,
        size_usd: float,
        equity: float,
        engine: str = 'standard'
    ) -> tuple:
        """
        Check if we can open a new position.

        NEW FEATURE: Checks engine-specific limits (e.g., max 1 bear_resilient_long).

        Returns:
            (can_open: bool, reason: str)
        """
        # Check max concurrent positions
        if len(self.open_positions) >= self.max_concurrent_positions:
            return (False, f"Max concurrent positions ({self.max_concurrent_positions}) reached")

        # NEW FEATURE: Check engine-specific limits
        if engine == 'bear_resilient_long':
            max_bear_longs = int(os.getenv('MAX_CONCURRENT_BEAR_LONGS', '1'))
            current_bear_longs = sum(
                1 for pos in self.open_positions.values()
                if pos.engine == 'bear_resilient_long'
            )

            if current_bear_longs >= max_bear_longs:
                return (False, f"Max bear-resilient longs ({max_bear_longs}) reached")

        # Check portfolio heat
        current_heat = self._calculate_portfolio_heat(equity)
        position_risk_pct = (size_usd / equity) * 100

        if current_heat + position_risk_pct > self.max_portfolio_heat_pct:
            return (False, f"Portfolio heat limit exceeded ({current_heat:.1f}% + {position_risk_pct:.1f}% > {self.max_portfolio_heat_pct}%)")

        # Check position size
        if size_usd > equity * 0.5:
            return (False, f"Position size too large ({size_usd:.2f} > 50% of equity)")

        return (True, "OK")

    def open_position(self, signal: dict) -> Optional[Position]:
        """
        Open a new position from signal.

        NEW FEATURE: Tracks engine from signal.

        Returns:
            Position object or None if cannot open
        """
        symbol = signal['symbol']
        size_usd = signal['size_usd']
        equity = signal.get('equity', 500)
        engine = signal.get('engine', 'standard')  # NEW

        # Check if we can open
        can_open, reason = self.can_open_position(size_usd, equity, engine=engine)
        if not can_open:
            print(f"[RiskEngine] Cannot open {symbol}: {reason}")
            return None

        # Create position
        position = Position(
            symbol=symbol,
            direction=signal['direction'],
            entry_price=signal['entry_price'],
            size_usd=size_usd,
            stop_loss=signal['stop_loss'],
            take_profit=signal.get('take_profit'),
            engine=engine,  # NEW
            timestamp=signal.get('timestamp', datetime.now())
        )

        self.open_positions[symbol] = position
        self._save_positions()

        print(f"✅ [RiskEngine] Opened {signal['direction']} position: {symbol} @ ${signal['entry_price']:.6f} (engine: {engine})")

        return position

    def close_position(self, symbol: str, exit_price: float, reason: str) -> Optional[dict]:
        """
        Close an open position.

        Returns:
            Trade result dict or None
        """
        if symbol not in self.open_positions:
            return None

        position = self.open_positions[symbol]

        # Calculate final P&L
        if position.direction == 'LONG':
            pnl_pct = (exit_price / position.entry_price - 1) * 100
        else:
            pnl_pct = (position.entry_price / exit_price - 1) * 100

        pnl_usd = position.size_usd * (pnl_pct / 100)

        # Build trade result
        trade_result = {
            'symbol': symbol,
            'direction': position.direction,
            'engine': position.engine,  # NEW
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'size_usd': position.size_usd,
            'pnl_usd': pnl_usd,
            'pnl_pct': pnl_pct,
            'mfe_pct': position.mfe_pct,
            'mae_pct': position.mae_pct,
            'hold_time_hours': (datetime.now() - position.timestamp).total_seconds() / 3600,
            'exit_reason': reason,
            'timestamp_entry': position.timestamp.isoformat(),
            'timestamp_exit': datetime.now().isoformat()
        }

        # Remove from open positions
        del self.open_positions[symbol]
        self._save_positions()

        print(f"🔴 [RiskEngine] Closed {position.direction} position: {symbol} @ ${exit_price:.6f} | P&L: ${pnl_usd:.2f} ({pnl_pct:+.2f}%) | Reason: {reason}")

        return trade_result

    def update_positions(self, current_prices: Dict[str, float]):
        """Update all open positions with current prices."""
        for symbol, position in self.open_positions.items():
            if symbol in current_prices:
                position.update_pnl(current_prices[symbol])

        self._save_positions()

    def _calculate_portfolio_heat(self, equity: float) -> float:
        """Calculate current portfolio heat (% of equity at risk)."""
        total_risk_usd = sum(pos.size_usd for pos in self.open_positions.values())
        return (total_risk_usd / equity) * 100 if equity > 0 else 0

    def _load_positions(self):
        """Load positions from JSON file."""
        if not os.path.exists(self.positions_file):
            return

        try:
            with open(self.positions_file, 'r') as f:
                data = json.load(f)
                positions_data = data.get('open_positions', [])

                for pos_dict in positions_data:
                    position = Position.from_dict(pos_dict)
                    self.open_positions[position.symbol] = position

        except Exception as e:
            print(f"[RiskEngine] Error loading positions: {e}")

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
