"""
Trailing Stop Loss Manager for Alpha Sniper V3.0

Provides clean, testable trailing stop logic that can be used
in both live trading and backtesting.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class TrailingStopConfig:
    """Configuration for trailing stop behavior"""
    entry_price: float
    activation_pct: float  # Profit % needed to activate trailing stop
    distance_pct: float    # How far stop trails from highest price
    breakeven_pct: float = 5.0  # Profit % to move stop to breakeven (optional)

    def __post_init__(self):
        """Validate configuration"""
        if self.entry_price <= 0:
            raise ValueError("entry_price must be positive")
        if self.activation_pct < 0:
            raise ValueError("activation_pct must be non-negative")
        if self.distance_pct < 0:
            raise ValueError("distance_pct must be non-negative")
        if self.breakeven_pct < 0:
            raise ValueError("breakeven_pct must be non-negative")


class TrailingStop:
    """
    Manages trailing stop logic for a single position.

    Example:
        >>> config = TrailingStopConfig(
        ...     entry_price=100.0,
        ...     activation_pct=4.0,  # Activate at 4% profit
        ...     distance_pct=2.0      # Trail 2% from highest
        ... )
        >>> ts = TrailingStop(config)
        >>>
        >>> # Price moves up
        >>> ts.update(105.0)  # +5% profit, trailing activates
        >>> ts.is_active
        True
        >>> ts.stop_price
        102.9  # 105 * (1 - 0.02)
        >>>
        >>> # Price continues up
        >>> ts.update(110.0)  # New high
        >>> ts.stop_price
        107.8  # 110 * (1 - 0.02)
        >>>
        >>> # Price drops to stop
        >>> ts.update(107.5)
        >>> ts.is_hit
        True
    """

    def __init__(self, config: TrailingStopConfig):
        """
        Initialize trailing stop manager.

        Args:
            config: TrailingStopConfig with entry price and parameters
        """
        self.config = config
        self._is_active = False
        self._highest_price = config.entry_price
        self._stop_price = 0.0
        self._is_hit = False
        self._breakeven_activated = False
        self._activation_price = config.entry_price * (1 + config.activation_pct / 100)
        self._breakeven_price = config.entry_price * (1 + config.breakeven_pct / 100)

    def update(self, current_price: float) -> bool:
        """
        Update trailing stop with new price.

        Args:
            current_price: Current market price

        Returns:
            True if stop was hit, False otherwise
        """
        if current_price <= 0:
            raise ValueError("current_price must be positive")

        # Already hit, no further updates
        if self._is_hit:
            return True

        # Check if we should activate
        if not self._is_active and current_price >= self._activation_price:
            self._is_active = True

        # Update highest price if active
        if self._is_active:
            if current_price > self._highest_price:
                self._highest_price = current_price

                # Check if we should activate breakeven protection
                if not self._breakeven_activated and current_price >= self._breakeven_price:
                    self._breakeven_activated = True
                    self._stop_price = self.config.entry_price  # Move to breakeven
                else:
                    # Normal trailing
                    self._stop_price = self._highest_price * (1 - self.config.distance_pct / 100)

            # Check if stop hit
            if current_price <= self._stop_price:
                self._is_hit = True
                return True

        return False

    @property
    def is_active(self) -> bool:
        """Whether trailing stop has been activated"""
        return self._is_active

    @property
    def is_hit(self) -> bool:
        """Whether stop has been hit"""
        return self._is_hit

    @property
    def stop_price(self) -> float:
        """Current stop price (0 if not active)"""
        return self._stop_price if self._is_active else 0.0

    @property
    def highest_price(self) -> float:
        """Highest price seen since activation"""
        return self._highest_price

    @property
    def current_profit_pct(self) -> float:
        """Current profit percentage from entry"""
        return ((self._highest_price - self.config.entry_price) / self.config.entry_price) * 100

    @property
    def breakeven_activated(self) -> bool:
        """Whether breakeven protection has been activated"""
        return self._breakeven_activated

    def get_state(self) -> dict:
        """
        Get current state as dictionary (for database storage).

        Returns:
            Dict with current state
        """
        return {
            'is_active': self._is_active,
            'is_hit': self._is_hit,
            'breakeven_activated': self._breakeven_activated,
            'highest_price': self._highest_price,
            'stop_price': self._stop_price,
            'current_profit_pct': self.current_profit_pct,
            'activation_price': self._activation_price,
            'breakeven_price': self._breakeven_price,
        }

    @classmethod
    def from_state(cls, config: TrailingStopConfig, state: dict) -> 'TrailingStop':
        """
        Restore trailing stop from saved state.

        Args:
            config: TrailingStopConfig
            state: State dict from get_state()

        Returns:
            TrailingStop instance with restored state
        """
        ts = cls(config)
        ts._is_active = state.get('is_active', False)
        ts._is_hit = state.get('is_hit', False)
        ts._breakeven_activated = state.get('breakeven_activated', False)
        ts._highest_price = state.get('highest_price', config.entry_price)
        ts._stop_price = state.get('stop_price', 0.0)
        return ts

    def __repr__(self) -> str:
        status = "HIT" if self._is_hit else ("ACTIVE" if self._is_active else "INACTIVE")
        return (
            f"TrailingStop(entry={self.config.entry_price:.4f}, "
            f"status={status}, highest={self._highest_price:.4f}, "
            f"stop={self._stop_price:.4f}, profit={self.current_profit_pct:.2f}%)"
        )


if __name__ == "__main__":
    # Test the trailing stop
    print("Testing TrailingStop class...")

    config = TrailingStopConfig(
        entry_price=100.0,
        activation_pct=4.0,
        distance_pct=2.0
    )

    ts = TrailingStop(config)
    print(f"\nInitial state: {ts}")

    # Price moves up but not enough to activate
    print("\n--- Price at 102 (+2%, below 4% activation) ---")
    ts.update(102.0)
    print(f"Active: {ts.is_active}, Stop: {ts.stop_price}")

    # Price reaches activation
    print("\n--- Price at 105 (+5%, activates trailing stop) ---")
    ts.update(105.0)
    print(f"Active: {ts.is_active}, Stop: {ts.stop_price:.2f}")
    print(f"State: {ts}")

    # Price continues up
    print("\n--- Price at 110 (+10%, new high) ---")
    ts.update(110.0)
    print(f"Stop now at: {ts.stop_price:.2f}")
    print(f"State: {ts}")

    # Price drops but above stop
    print("\n--- Price at 109 (slight pullback) ---")
    ts.update(109.0)
    print(f"Hit: {ts.is_hit}, Stop still at: {ts.stop_price:.2f}")

    # Price hits stop
    print("\n--- Price at 107 (hits stop) ---")
    hit = ts.update(107.0)
    print(f"Stop hit: {hit}")
    print(f"Final state: {ts}")

    print("\n✅ TrailingStop test complete!")
