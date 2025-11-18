"""
Symbol State Machine for Alpha Sniper V3.2

Each symbol maintains a state that tracks its market behavior:
- FLAT: No clear setup
- BASING: Volatility compression, potential pre-breakout
- BREAKING_OUT: Fresh breakout detected
- EXTENDED: Large recent move, likely late
- FAILED: Clear failed breakout/breakdown
- COOLDOWN: Recently failed, temporarily ignored

State transitions prevent chasing exhausted names and re-buying failed setups.
"""
from enum import Enum
from typing import Dict, Optional
from datetime import datetime, timedelta
import pandas as pd

from v3.utils.indicators import (
    atr, ema, detect_compression, position_in_range, swing_low
)


class SymbolState(Enum):
    """Symbol states"""
    FLAT = "FLAT"
    BASING = "BASING"
    BREAKING_OUT = "BREAKING_OUT"
    EXTENDED = "EXTENDED"
    FAILED = "FAILED"
    COOLDOWN = "COOLDOWN"


class SymbolStateMachine:
    """
    Manages state for a single symbol
    """

    def __init__(
        self,
        symbol: str,
        cooldown_hours: int = 12,
        extended_threshold_pct: float = 35.0,
        breakout_rvol_threshold: float = 1.5,
        base_duration_min_bars: int = 16  # 4 hours @ 15m bars
    ):
        """
        Args:
            symbol: Trading symbol
            cooldown_hours: Hours to wait after failed setup
            extended_threshold_pct: % move to mark as extended
            breakout_rvol_threshold: RVOL threshold for breakout
            base_duration_min_bars: Minimum bars for valid base
        """
        self.symbol = symbol
        self.cooldown_hours = cooldown_hours
        self.extended_threshold_pct = extended_threshold_pct
        self.breakout_rvol_threshold = breakout_rvol_threshold
        self.base_duration_min_bars = base_duration_min_bars

        # State
        self.state = SymbolState.FLAT
        self.state_entry_time: Optional[datetime] = None
        self.state_metadata: Dict = {}

        # Tracking
        self.base_start_price: Optional[float] = None
        self.base_high: Optional[float] = None
        self.breakout_price: Optional[float] = None
        self.last_update: Optional[datetime] = None

    def update(
        self,
        close: float,
        high_24h: float,
        low_24h: float,
        atr_14: float,
        atr_24h_median: float,
        rvol: float,
        bars_data: Optional[pd.DataFrame] = None,
        timestamp: Optional[datetime] = None
    ) -> SymbolState:
        """
        Update symbol state based on current market data

        Args:
            close: Current close price
            high_24h: 24h high
            low_24h: 24h low
            atr_14: ATR(14) value
            atr_24h_median: Median ATR over 24h
            rvol: Relative volume
            bars_data: Optional OHLCV dataframe for deeper analysis
            timestamp: Current timestamp

        Returns:
            Updated state
        """
        if timestamp is None:
            timestamp = datetime.now()

        self.last_update = timestamp

        # State transition logic
        current_state = self.state

        # COOLDOWN → FLAT (after cooldown period)
        if current_state == SymbolState.COOLDOWN:
            if self._check_cooldown_expired(timestamp):
                self._transition_to(SymbolState.FLAT, timestamp, {})
                return self.state
            else:
                return self.state  # Still cooling down

        # ANY → EXTENDED (large move detected)
        if current_state not in [SymbolState.EXTENDED, SymbolState.FAILED, SymbolState.COOLDOWN]:
            if self._check_extended(close, low_24h):
                self._transition_to(SymbolState.EXTENDED, timestamp, {
                    'move_pct': (close / low_24h - 1) * 100,
                    'entry_price': close
                })
                return self.state

        # ANY → FAILED (breakdown detected)
        if current_state in [SymbolState.BASING, SymbolState.BREAKING_OUT]:
            if self._check_failed(close, bars_data):
                self._transition_to(SymbolState.FAILED, timestamp, {})
                # Immediately transition to cooldown
                self._transition_to(SymbolState.COOLDOWN, timestamp, {
                    'cooldown_until': timestamp + timedelta(hours=self.cooldown_hours)
                })
                return self.state

        # State-specific transitions
        if current_state == SymbolState.FLAT:
            # FLAT → BASING
            if self._check_basing(close, high_24h, low_24h, atr_14, atr_24h_median):
                self._transition_to(SymbolState.BASING, timestamp, {
                    'base_start_price': close,
                    'base_low': low_24h,
                    'base_high': high_24h
                })
                self.base_start_price = close
                self.base_high = high_24h

        elif current_state == SymbolState.BASING:
            # BASING → BREAKING_OUT
            if self._check_breakout(close, rvol, bars_data):
                self._transition_to(SymbolState.BREAKING_OUT, timestamp, {
                    'breakout_price': close,
                    'rvol': rvol
                })
                self.breakout_price = close

            # Update base tracking
            if self.base_high is not None:
                self.base_high = max(self.base_high, high_24h)

        elif current_state == SymbolState.BREAKING_OUT:
            # BREAKING_OUT → EXTENDED (if move becomes too large)
            if self.breakout_price and (close / self.breakout_price - 1) * 100 > self.extended_threshold_pct:
                self._transition_to(SymbolState.EXTENDED, timestamp, {
                    'move_from_breakout_pct': (close / self.breakout_price - 1) * 100
                })

        elif current_state == SymbolState.EXTENDED:
            # EXTENDED → FLAT (after cooldown or mean reversion)
            hours_extended = (timestamp - self.state_entry_time).total_seconds() / 3600
            if hours_extended > 24:
                # After 24h, reset to FLAT
                self._transition_to(SymbolState.FLAT, timestamp, {})

        return self.state

    def _check_basing(
        self,
        close: float,
        high_24h: float,
        low_24h: float,
        atr_14: float,
        atr_24h_median: float
    ) -> bool:
        """
        Check if entering BASING state

        Criteria:
        1. ATR compression (< 0.8 of 24h median)
        2. Price in upper half of 24h range
        """
        # ATR compression
        compression_ratio = detect_compression(atr_14, atr_24h_median)
        is_compressed = compression_ratio < 0.8

        # Position in range
        pos_in_range = position_in_range(close, high_24h, low_24h)
        in_upper_half = pos_in_range > 0.4

        return is_compressed and in_upper_half

    def _check_breakout(
        self,
        close: float,
        rvol: float,
        bars_data: Optional[pd.DataFrame]
    ) -> bool:
        """
        Check if breaking out from base

        Criteria:
        1. Close above recent range high
        2. RVOL > threshold
        3. Base duration is sufficient
        """
        # RVOL check
        if rvol < self.breakout_rvol_threshold:
            return False

        # Check if above base high
        if self.base_high is None:
            return False

        if close <= self.base_high:
            return False

        # Check base duration (if bars_data available)
        if bars_data is not None and self.state_entry_time is not None:
            duration_bars = len(bars_data[bars_data.index > self.state_entry_time])
            if duration_bars < self.base_duration_min_bars:
                return False

        return True

    def _check_extended(self, close: float, low_24h: float) -> bool:
        """
        Check if move is extended

        Extended = price > threshold% above 24h low
        """
        move_pct = (close / low_24h - 1) * 100

        return move_pct > self.extended_threshold_pct

    def _check_failed(self, close: float, bars_data: Optional[pd.DataFrame]) -> bool:
        """
        Check if setup has failed

        Failed = breakdown below key support with volume
        """
        # Simple check: if in BASING/BREAKING_OUT and close breaks below base low
        if self.state_metadata.get('base_low') is not None:
            base_low = self.state_metadata['base_low']
            if close < base_low * 0.98:  # 2% below base low
                return True

        # If in BREAKING_OUT, check if back below breakout price
        if self.state == SymbolState.BREAKING_OUT and self.breakout_price is not None:
            if close < self.breakout_price * 0.97:  # 3% below breakout
                return True

        return False

    def _check_cooldown_expired(self, timestamp: datetime) -> bool:
        """Check if cooldown period has expired"""
        cooldown_until = self.state_metadata.get('cooldown_until')

        if cooldown_until is None:
            return True

        return timestamp >= cooldown_until

    def _transition_to(self, new_state: SymbolState, timestamp: datetime, metadata: Dict):
        """Transition to new state"""
        old_state = self.state
        self.state = new_state
        self.state_entry_time = timestamp
        self.state_metadata = metadata

        # Reset tracking on major state changes
        if new_state == SymbolState.FLAT:
            self.base_start_price = None
            self.base_high = None
            self.breakout_price = None

        print(f"[State] {self.symbol}: {old_state.value} → {new_state.value}")

    def is_tradeable(self) -> bool:
        """Can we trade this symbol in its current state?"""
        return self.state not in [SymbolState.COOLDOWN, SymbolState.FAILED, SymbolState.EXTENDED]

    def get_state_info(self) -> Dict:
        """Get current state information"""
        return {
            'symbol': self.symbol,
            'state': self.state.value,
            'state_entry_time': self.state_entry_time,
            'metadata': self.state_metadata,
            'is_tradeable': self.is_tradeable(),
            'last_update': self.last_update
        }


class SymbolStateManager:
    """
    Manages states for all symbols in the universe
    """

    def __init__(self):
        self.symbol_states: Dict[str, SymbolStateMachine] = {}

    def get_or_create(self, symbol: str) -> SymbolStateMachine:
        """Get state machine for symbol, create if doesn't exist"""
        if symbol not in self.symbol_states:
            self.symbol_states[symbol] = SymbolStateMachine(symbol)

        return self.symbol_states[symbol]

    def update_symbol(
        self,
        symbol: str,
        close: float,
        high_24h: float,
        low_24h: float,
        atr_14: float,
        atr_24h_median: float,
        rvol: float,
        bars_data: Optional[pd.DataFrame] = None,
        timestamp: Optional[datetime] = None
    ) -> SymbolState:
        """Update state for a symbol"""
        state_machine = self.get_or_create(symbol)
        return state_machine.update(
            close, high_24h, low_24h, atr_14, atr_24h_median,
            rvol, bars_data, timestamp
        )

    def get_tradeable_symbols(self) -> list:
        """Get all symbols in tradeable states"""
        return [
            symbol for symbol, sm in self.symbol_states.items()
            if sm.is_tradeable()
        ]

    def get_state(self, symbol: str) -> Optional[SymbolState]:
        """Get current state for symbol"""
        if symbol in self.symbol_states:
            return self.symbol_states[symbol].state
        return None

    def get_all_states(self) -> Dict[str, Dict]:
        """Get state info for all symbols"""
        return {
            symbol: sm.get_state_info()
            for symbol, sm in self.symbol_states.items()
        }


# Singleton instance
symbol_state_manager = SymbolStateManager()
