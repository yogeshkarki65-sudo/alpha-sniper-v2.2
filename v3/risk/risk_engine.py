#!/usr/bin/env python3
"""
Risk Engine - Position management and R-based risk controls

V4.1 FIXES:
- R-based position sizing using RISK_PER_TRADE_* from .env
- Portfolio heat = sum of initial R (risk dollars), not exposure
- MAX_PORTFOLIO_HEAT enforced in R-terms (default 1.5%)
- SIM/LIVE and SPOT/FUTURES mode handling
- Engine-specific risk parameters (standard_long, standard_short, bear_resilient_long)
"""

import json
import os
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class Position:
    """
    Open position tracker with R-based risk tracking.

    Key fields:
    - initial_risk_usd: The R value (dollars risked at entry)
    - size_usd: Actual position size in USD
    - engine: Which engine created this position
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

    # Performance tracking
    mfe_pct: float = 0  # Maximum Favorable Excursion
    mae_pct: float = 0  # Maximum Adverse Excursion
    current_pnl_pct: float = 0
    highest_price: float = 0  # For trailing stop

    # Exit tracking
    tp1_hit: bool = False
    tp2_hit: bool = False
    sl_moved_to_be: bool = False  # Stop loss moved to breakeven
    remaining_size_pct: float = 100  # % of position still open

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.highest_price == 0:
            self.highest_price = self.entry_price

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

    def should_exit(self, current_price: float, hours_held: float) -> tuple:
        """
        Check if position should be exited.

        Returns:
            (should_exit: bool, reason: str, exit_pct: float)
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

        # Max hold time based on engine
        max_hold_hours = 72  # Default 3 days for standard
        if self.engine == 'bear_resilient_long':
            max_hold_hours = int(os.getenv('MAX_HOLD_HOURS_BEAR_LONG', '24'))

        if hours_held >= max_hold_hours:
            return (True, f"Max hold time ({max_hold_hours}h) reached", 100)

        # NFT rule for bear_resilient_long: exit if MFE < 0.5R after 3h
        if self.engine == 'bear_resilient_long' and hours_held >= 3:
            r_value = abs(self.entry_price - self.stop_loss) / self.entry_price
            mfe_in_r = self.mfe_pct / 100 / r_value if r_value > 0 else 0
            if mfe_in_r < 0.5:
                return (True, "NFT rule: MFE < 0.5R after 3h", 100)

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
        # Handle old positions without initial_risk_usd
        if 'initial_risk_usd' not in data:
            data['initial_risk_usd'] = data.get('size_usd', 0) * 0.03  # Assume 3% risk
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

        # Load config from .env
        self.mode = os.getenv('MODE', 'SIMULATION')
        self.market_type = os.getenv('MARKET_TYPE', 'SPOT')

        # Risk parameters from .env
        self.risk_per_trade = {
            'BULL': float(os.getenv('RISK_PER_TRADE_BULL', '0.003')),
            'SIDEWAYS': float(os.getenv('RISK_PER_TRADE_SIDEWAYS', '0.0025')),
            'BEAR_SHORT': float(os.getenv('RISK_PER_TRADE_BEAR_SHORT', '0.0012')),
            'BEAR_LONG': float(os.getenv('RISK_PER_TRADE_BEAR_LONG', '0.0008')),
        }

        # Portfolio limits
        self.max_portfolio_heat = float(os.getenv('MAX_PORTFOLIO_HEAT', '0.015'))  # 1.5% default
        self.max_concurrent_positions = int(os.getenv('MAX_CONCURRENT_POSITIONS', '5'))
        self.max_concurrent_bear_longs = int(os.getenv('MAX_CONCURRENT_BEAR_LONGS', '1'))

        self._load_positions()
        print(f"[RiskEngine] Initialized - {len(self.open_positions)} open positions")
        print(f"   Mode: {self.mode}, Market: {self.market_type}")
        print(f"   Max portfolio heat: {self.max_portfolio_heat*100:.2f}%")

    def get_risk_per_trade(self, regime: str, engine: str) -> float:
        """
        Get risk per trade based on regime and engine.

        Returns fraction of equity to risk (e.g., 0.003 = 0.3%)
        """
        if engine == 'bear_resilient_long':
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

        # Create position
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
            timestamp=signal.get('timestamp', datetime.now())
        )

        self.open_positions[symbol] = position
        self._save_positions()

        stop_distance_pct = abs(signal['entry_price'] - signal['stop_loss']) / signal['entry_price'] * 100
        print(f"✅ [RiskEngine] Opened {signal['direction']} position: {symbol}")
        print(f"   Entry: ${signal['entry_price']:.6f} | Stop: ${signal['stop_loss']:.6f} ({stop_distance_pct:.2f}%)")
        print(f"   Size: ${size_usd:.2f} | Risk (R): ${initial_risk_usd:.2f} | Engine: {engine}")

        return position

    def close_position(self, symbol: str, exit_price: float, reason: str) -> Optional[dict]:
        """Close an open position and return trade result."""
        if symbol not in self.open_positions:
            return None

        position = self.open_positions[symbol]

        # Calculate final P&L
        if position.direction == 'LONG':
            pnl_pct = (exit_price / position.entry_price - 1) * 100
        else:
            pnl_pct = (position.entry_price / exit_price - 1) * 100

        pnl_usd = position.size_usd * (pnl_pct / 100)

        # Calculate R-multiple
        r_multiple = pnl_usd / position.initial_risk_usd if position.initial_risk_usd > 0 else 0

        # Build trade result
        trade_result = {
            'symbol': symbol,
            'direction': position.direction,
            'engine': position.engine,
            'regime': position.regime,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'size_usd': position.size_usd,
            'initial_risk_usd': position.initial_risk_usd,
            'pnl_usd': pnl_usd,
            'pnl_pct': pnl_pct,
            'r_multiple': r_multiple,
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

        print(f"🔴 [RiskEngine] Closed {position.direction}: {symbol} @ ${exit_price:.6f}")
        print(f"   P&L: ${pnl_usd:.2f} ({pnl_pct:+.2f}%) | R-Multiple: {r_multiple:+.2f}R | Reason: {reason}")

        return trade_result

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
