"""
Volatility-Adjusted Risk Model for Alpha Sniper Strategy.

Implements ATR-based position sizing and portfolio heat management.

Risk Model:
===========
ATR_SL = max(2*ATR14, entry_price - Pullback_Low)
Position_Size = (Risk% * Equity) / ATR_SL

Risk per trade:
- Bull = 0.40%
- Sideways = 0.25%
- Bear = 0.12%

Portfolio heat limit:
- sum(risk_pct of open trades) <= 1.5%

Daily loss limit:
- If cumulative daily loss <= -2% equity → block new entries
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class VolatilityAdjustedRiskModel:
    """
    Manages position sizing and risk limits based on ATR and regime.
    """

    # Risk per trade by regime (as fraction of equity)
    RISK_PCT_BULL = 0.0040  # 0.40%
    RISK_PCT_SIDEWAYS = 0.0025  # 0.25%
    RISK_PCT_BEAR = 0.0012  # 0.12%

    # Portfolio limits
    MAX_PORTFOLIO_HEAT = 0.015  # 1.5% total risk
    MAX_DAILY_LOSS_PCT = 0.02  # 2% daily loss limit

    # ATR multiplier for stop-loss
    ATR_SL_MULTIPLIER = 2.0

    def __init__(
        self,
        risk_pct_bull: float = 0.0040,
        risk_pct_sideways: float = 0.0025,
        risk_pct_bear: float = 0.0012,
        max_portfolio_heat: float = 0.015,
        max_daily_loss_pct: float = 0.02,
        atr_sl_mult: float = 2.0
    ):
        """
        Initialize risk model.

        Args:
            risk_pct_bull: Risk per trade in bull regime
            risk_pct_sideways: Risk per trade in sideways regime
            risk_pct_bear: Risk per trade in bear regime
            max_portfolio_heat: Maximum total portfolio risk
            max_daily_loss_pct: Maximum daily loss percentage
            atr_sl_mult: ATR multiplier for stop-loss
        """
        self.risk_pct = {
            'bull': risk_pct_bull,
            'sideways': risk_pct_sideways,
            'bear': risk_pct_bear
        }
        self.max_portfolio_heat = max_portfolio_heat
        self.max_daily_loss_pct = max_daily_loss_pct
        self.atr_sl_mult = atr_sl_mult

        logger.info(
            f"RiskModel initialized: Bull={risk_pct_bull:.2%}, "
            f"Sideways={risk_pct_sideways:.2%}, Bear={risk_pct_bear:.2%}, "
            f"Max Heat={max_portfolio_heat:.2%}"
        )

    def calculate_position_size(
        self,
        equity: float,
        entry_price: float,
        atr: float,
        pullback_low: float,
        regime: str
    ) -> Tuple[float, float, float]:
        """
        Calculate position size based on ATR and risk percentage.

        Args:
            equity: Current account equity
            entry_price: Entry price
            atr: ATR value (14-period)
            pullback_low: Lowest price in pullback
            regime: Market regime

        Returns:
            Tuple of (position_size, stop_loss_price, risk_amount)
        """
        # Get regime-specific risk percentage
        risk_pct = self.risk_pct.get(regime, self.risk_pct['sideways'])

        # Calculate ATR-based stop-loss distance
        atr_sl_distance = self.atr_sl_mult * atr

        # Calculate price-based stop-loss distance
        price_sl_distance = entry_price - pullback_low

        # Use the maximum (more conservative)
        sl_distance = max(atr_sl_distance, price_sl_distance)

        # Stop-loss price
        stop_loss_price = entry_price - sl_distance

        # Risk amount in dollars
        risk_amount = equity * risk_pct

        # Position size (in quote currency)
        position_size = risk_amount / sl_distance

        logger.debug(
            f"Position sizing: Equity=${equity:.2f}, Entry=${entry_price:.4f}, "
            f"SL=${stop_loss_price:.4f}, Risk=${risk_amount:.2f}, Size=${position_size:.2f}"
        )

        return position_size, stop_loss_price, risk_amount

    def calculate_portfolio_heat(
        self,
        open_positions: List[Dict]
    ) -> float:
        """
        Calculate total portfolio heat (risk).

        Args:
            open_positions: List of open position dictionaries

        Returns:
            Total portfolio heat as fraction of equity
        """
        total_risk = 0.0

        for pos in open_positions:
            risk_pct = pos.get('risk_pct', 0.0)
            total_risk += risk_pct

        return total_risk

    def check_portfolio_heat_ok(
        self,
        open_positions: List[Dict],
        new_risk_pct: float
    ) -> bool:
        """
        Check if adding new position exceeds portfolio heat limit.

        Args:
            open_positions: Current open positions
            new_risk_pct: Risk percentage of new position

        Returns:
            True if within limits, False otherwise
        """
        current_heat = self.calculate_portfolio_heat(open_positions)
        total_heat = current_heat + new_risk_pct

        if total_heat > self.max_portfolio_heat:
            logger.warning(
                f"Portfolio heat limit exceeded: {total_heat:.2%} > {self.max_portfolio_heat:.2%}"
            )
            return False

        return True

    def check_daily_loss_ok(
        self,
        starting_equity: float,
        current_equity: float
    ) -> bool:
        """
        Check if daily loss limit is breached.

        Args:
            starting_equity: Equity at start of day
            current_equity: Current equity

        Returns:
            True if within limits, False if limit breached
        """
        daily_return = (current_equity - starting_equity) / starting_equity

        if daily_return <= -self.max_daily_loss_pct:
            logger.error(
                f"Daily loss limit breached: {daily_return:.2%} <= {-self.max_daily_loss_pct:.2%}"
            )
            return False

        return True

    def adjust_position_size_for_limits(
        self,
        position_size: float,
        min_size: float,
        max_size: float
    ) -> float:
        """
        Adjust position size to respect exchange limits.

        Args:
            position_size: Calculated position size
            min_size: Minimum notional value
            max_size: Maximum notional value

        Returns:
            Adjusted position size
        """
        if position_size < min_size:
            logger.warning(f"Position size {position_size} < min {min_size}, using min")
            return min_size

        if position_size > max_size:
            logger.warning(f"Position size {position_size} > max {max_size}, using max")
            return max_size

        return position_size

    def get_risk_percentage(self, regime: str) -> float:
        """
        Get risk percentage for regime.

        Args:
            regime: Market regime

        Returns:
            Risk percentage
        """
        return self.risk_pct.get(regime, self.risk_pct['sideways'])


class ExitRulesManager:
    """
    Manages ATR-based exit rules with partial exits and trailing stops.

    Exit Rules:
    ===========
    TP1 = entry + 2*ATR_SL  (close 50%)
    TP2 = entry + 3*ATR_SL  (close 30%)
    Trailing stop = highest_close - 1.5*ATR14 after TP1 hit
    Hard SL = entry_price - ATR_SL
    """

    # Default multipliers
    TP1_MULTIPLIER = 2.0
    TP2_MULTIPLIER = 3.0
    TRAIL_MULTIPLIER = 1.5

    # Partial exit percentages
    TP1_EXIT_PCT = 0.50  # Close 50% at TP1
    TP2_EXIT_PCT = 0.30  # Close 30% at TP2 (of remaining = 60% of original)

    def __init__(
        self,
        tp1_mult: float = 2.0,
        tp2_mult: float = 3.0,
        trail_mult: float = 1.5,
        tp1_exit_pct: float = 0.50,
        tp2_exit_pct: float = 0.30
    ):
        """
        Initialize exit rules manager.

        Args:
            tp1_mult: TP1 multiplier (of ATR_SL)
            tp2_mult: TP2 multiplier (of ATR_SL)
            trail_mult: Trailing stop multiplier (of ATR)
            tp1_exit_pct: Percentage to close at TP1
            tp2_exit_pct: Percentage to close at TP2
        """
        self.tp1_mult = tp1_mult
        self.tp2_mult = tp2_mult
        self.trail_mult = trail_mult
        self.tp1_exit_pct = tp1_exit_pct
        self.tp2_exit_pct = tp2_exit_pct

        logger.info(
            f"ExitRulesManager initialized: TP1={tp1_mult}x, TP2={tp2_mult}x, Trail={trail_mult}x"
        )

    def calculate_exit_levels(
        self,
        entry_price: float,
        stop_loss_price: float,
        atr: float
    ) -> Dict[str, float]:
        """
        Calculate all exit levels.

        Args:
            entry_price: Entry price
            stop_loss_price: Stop-loss price
            atr: Current ATR

        Returns:
            Dictionary with exit levels
        """
        atr_sl_distance = entry_price - stop_loss_price

        # Take-profit levels
        tp1_price = entry_price + (self.tp1_mult * atr_sl_distance)
        tp2_price = entry_price + (self.tp2_mult * atr_sl_distance)

        # Initial trailing stop (inactive until TP1)
        trailing_stop = entry_price - (self.trail_mult * atr)

        return {
            'entry': entry_price,
            'stop_loss': stop_loss_price,
            'tp1': tp1_price,
            'tp2': tp2_price,
            'trailing_stop': trailing_stop,
            'atr_sl_distance': atr_sl_distance
        }

    def update_trailing_stop(
        self,
        highest_close: float,
        current_atr: float,
        current_trailing_stop: float,
        tp1_hit: bool
    ) -> float:
        """
        Update trailing stop based on highest close.

        Args:
            highest_close: Highest close since entry
            current_atr: Current ATR value
            current_trailing_stop: Current trailing stop price
            tp1_hit: Whether TP1 has been hit

        Returns:
            Updated trailing stop price
        """
        if not tp1_hit:
            # Don't trail until TP1 hit
            return current_trailing_stop

        # Calculate new trailing stop
        new_trailing_stop = highest_close - (self.trail_mult * current_atr)

        # Only move up, never down
        return max(new_trailing_stop, current_trailing_stop)

    def check_exit_conditions(
        self,
        position: Dict,
        current_price: float,
        current_atr: float
    ) -> Tuple[str, float]:
        """
        Check if any exit condition is met.

        Args:
            position: Position dictionary with all info
            current_price: Current market price
            current_atr: Current ATR

        Returns:
            Tuple of (exit_type, exit_percentage)
            exit_type: 'none', 'stop_loss', 'tp1', 'tp2', 'trailing'
            exit_percentage: Portion of position to close (0-1)
        """
        # Hard stop-loss
        if current_price <= position['stop_loss']:
            return ('stop_loss', 1.0)

        # Check TP1
        if not position.get('tp1_hit', False):
            if current_price >= position['tp1']:
                return ('tp1', self.tp1_exit_pct)

        # Check TP2 (only after TP1 hit)
        if position.get('tp1_hit', False) and not position.get('tp2_hit', False):
            if current_price >= position['tp2']:
                return ('tp2', self.tp2_exit_pct)

        # Check trailing stop (only after TP1 hit)
        if position.get('tp1_hit', False):
            # Update highest close
            highest_close = max(position.get('highest_close', position['entry']), current_price)

            # Update trailing stop
            trailing_stop = self.update_trailing_stop(
                highest_close,
                current_atr,
                position.get('trailing_stop', position['entry']),
                tp1_hit=True
            )

            if current_price <= trailing_stop:
                return ('trailing', 1.0)

        return ('none', 0.0)

    def update_position_after_partial_exit(
        self,
        position: Dict,
        exit_type: str,
        exit_percentage: float,
        exit_price: float
    ) -> Dict:
        """
        Update position after partial exit.

        Args:
            position: Position dictionary
            exit_type: Type of exit ('tp1', 'tp2', etc.)
            exit_percentage: Percentage closed
            exit_price: Exit price

        Returns:
            Updated position dictionary
        """
        # Update remaining size
        remaining_pct = 1.0 - exit_percentage
        position['remaining_size'] = position.get('remaining_size', 1.0) * remaining_pct

        # Mark which targets hit
        if exit_type == 'tp1':
            position['tp1_hit'] = True
        elif exit_type == 'tp2':
            position['tp2_hit'] = True

        # Update highest close
        position['highest_close'] = max(
            position.get('highest_close', position['entry']),
            exit_price
        )

        return position
