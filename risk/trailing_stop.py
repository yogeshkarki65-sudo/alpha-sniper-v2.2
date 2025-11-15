"""
Alpha Sniper v4.1 Trailing Stop System
- Activation at +4% profit
- Distance: 1.5% below highest price
- Breakeven move at +5% profit (entry + 0.1% for fees)
"""
from typing import Tuple, Optional
from config.config import config
from config.logging_config import logger
from database.models import db


class TrailingStopManager:
    """Manages trailing stops and breakeven logic"""

    @staticmethod
    def should_activate_trailing(
        entry_price: float,
        current_price: float,
        trailing_active: bool
    ) -> bool:
        """
        Check if trailing stop should be activated
        Args:
            entry_price: Entry price
            current_price: Current price
            trailing_active: Is trailing already active?
        Returns: True if should activate
        """
        if trailing_active:
            return True  # Already active

        if not config.USE_TRAILING_STOP:
            return False

        profit_pct = ((current_price - entry_price) / entry_price) * 100
        return profit_pct >= config.TRAILING_ACTIVATION_PCT

    @staticmethod
    def calculate_trailing_price(highest_price: float) -> float:
        """
        Calculate trailing stop price
        Args:
            highest_price: Highest price since entry
        Returns: Trailing stop price
        """
        distance_pct = config.TRAILING_DISTANCE_PCT / 100
        trailing_price = highest_price * (1 - distance_pct)
        return trailing_price

    @staticmethod
    def should_move_to_breakeven(
        entry_price: float,
        current_price: float,
        breakeven_moved: bool
    ) -> bool:
        """
        Check if stop should be moved to breakeven
        Args:
            entry_price: Entry price
            current_price: Current price
            breakeven_moved: Has breakeven already been set?
        Returns: True if should move to breakeven
        """
        if breakeven_moved:
            return False  # Already moved

        profit_pct = ((current_price - entry_price) / entry_price) * 100
        return profit_pct >= config.BREAKEVEN_AFTER_PCT

    @staticmethod
    def calculate_breakeven_price(entry_price: float) -> float:
        """
        Calculate breakeven stop price (entry + small offset for fees)
        Args:
            entry_price: Entry price
        Returns: Breakeven stop price
        """
        offset_pct = config.BREAKEVEN_OFFSET_PCT / 100
        breakeven_price = entry_price * (1 + offset_pct)
        return breakeven_price

    @staticmethod
    def check_trailing_hit(
        current_price: float,
        trailing_price: float
    ) -> bool:
        """
        Check if trailing stop was hit
        Args:
            current_price: Current price
            trailing_price: Trailing stop price
        Returns: True if hit
        """
        return current_price <= trailing_price

    @staticmethod
    def update_position_trailing(
        position_id: int,
        entry_price: float,
        current_price: float,
        highest_price: float,
        trailing_active: bool,
        trailing_price: Optional[float],
        breakeven_moved: bool,
        current_stop_loss: float
    ) -> Tuple[float, bool, Optional[float], bool, float]:
        """
        Update trailing stop and breakeven for a position
        Args:
            position_id: Position ID
            entry_price: Entry price
            current_price: Current price
            highest_price: Highest price seen
            trailing_active: Is trailing active?
            trailing_price: Current trailing stop price
            breakeven_moved: Has breakeven been set?
            current_stop_loss: Current stop loss price
        Returns: (new_highest, trailing_active, trailing_price, breakeven_moved, new_stop_loss)
        """
        # Update highest price
        new_highest = max(highest_price, current_price)

        # Check if should move to breakeven
        new_breakeven_moved = breakeven_moved
        new_stop_loss = current_stop_loss

        if not breakeven_moved:
            if TrailingStopManager.should_move_to_breakeven(
                entry_price, current_price, breakeven_moved
            ):
                new_stop_loss = TrailingStopManager.calculate_breakeven_price(entry_price)
                new_breakeven_moved = True
                db.move_stop_to_breakeven(position_id, new_stop_loss)
                logger.info(
                    f"🎯 Breakeven activated | "
                    f"Stop moved to ${new_stop_loss:.6f} (entry +0.1%)"
                )

        # Check if should activate trailing
        new_trailing_active = TrailingStopManager.should_activate_trailing(
            entry_price, current_price, trailing_active
        )

        new_trailing_price = trailing_price

        if new_trailing_active:
            # Calculate new trailing price
            new_trailing_price = TrailingStopManager.calculate_trailing_price(new_highest)

            # Update database if changed
            if not trailing_active or new_trailing_price != trailing_price:
                db.update_position_trailing(
                    position_id,
                    new_highest,
                    new_trailing_active,
                    new_trailing_price
                )

                if not trailing_active:
                    logger.info(
                        f"🎯 Trailing stop activated | "
                        f"Stop @ ${new_trailing_price:.6f}"
                    )

        return (
            new_highest,
            new_trailing_active,
            new_trailing_price,
            new_breakeven_moved,
            new_stop_loss
        )


# Global instance
trailing_stop_manager = TrailingStopManager()
