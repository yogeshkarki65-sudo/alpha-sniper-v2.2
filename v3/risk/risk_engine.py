"""
Risk Engine for Alpha Sniper V3.2

Handles:
- Regime-adaptive position sizing
- Portfolio heat management
- Daily loss limits
- Position limits
- Correlation checks
"""
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
import numpy as np

from v3.regime.detector import Regime, regime_detector


class Position:
    """Represents an open position"""

    def __init__(
        self,
        symbol: str,
        entry_price: float,
        size_usd: float,
        stop_loss_price: float,
        timestamp: Optional[datetime] = None
    ):
        """
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            size_usd: Position size in USD
            stop_loss_price: Initial stop loss price
            timestamp: Entry timestamp
        """
        self.symbol = symbol
        self.entry_price = entry_price
        self.size_usd = size_usd
        self.stop_loss_price = stop_loss_price
        self.timestamp = timestamp or datetime.now()

        # Tracking
        self.current_price = entry_price
        self.highest_price = entry_price
        self.lowest_price = entry_price

        # Risk metrics
        self.risk_usd = abs(entry_price - stop_loss_price) / entry_price * size_usd
        self.max_adverse_excursion = 0.0  # MAE in R multiples
        self.max_favorable_excursion = 0.0  # MFE in R multiples

    def update_price(self, current_price: float):
        """Update current price and tracking metrics"""
        self.current_price = current_price
        self.highest_price = max(self.highest_price, current_price)
        self.lowest_price = min(self.lowest_price, current_price)

        # Update MAE/MFE (in R multiples)
        risk_per_unit = abs(self.entry_price - self.stop_loss_price)

        if risk_per_unit > 0:
            current_pnl = (current_price - self.entry_price)
            self.max_favorable_excursion = max(
                self.max_favorable_excursion,
                current_pnl / risk_per_unit
            )
            self.max_adverse_excursion = min(
                self.max_adverse_excursion,
                current_pnl / risk_per_unit
            )

    def get_unrealized_pnl_usd(self) -> float:
        """Get unrealized P&L in USD"""
        return (self.current_price - self.entry_price) / self.entry_price * self.size_usd

    def get_unrealized_pnl_r(self) -> float:
        """Get unrealized P&L in R multiples"""
        risk_per_unit = abs(self.entry_price - self.stop_loss_price)

        if risk_per_unit == 0:
            return 0.0

        pnl_per_unit = self.current_price - self.entry_price
        return pnl_per_unit / risk_per_unit

    def get_risk_pct(self, equity: float) -> float:
        """Get risk as % of equity"""
        return (self.risk_usd / equity) * 100 if equity > 0 else 0.0


class RiskEngine:
    """
    Portfolio risk management engine
    """

    def __init__(
        self,
        initial_equity: float = 500.0,
        base_risk_pct_bull: float = 0.4,
        base_risk_pct_sideways: float = 0.25,
        base_risk_pct_bear: float = 0.12,
        max_portfolio_heat_pct: float = 1.5,
        daily_loss_cap_pct: float = 2.0,
        max_concurrent_positions: int = 5,
        max_correlated_positions: int = 2
    ):
        """
        Args:
            initial_equity: Starting equity
            base_risk_pct_bull: Risk per trade in bull regime
            base_risk_pct_sideways: Risk per trade in sideways
            base_risk_pct_bear: Risk per trade in bear
            max_portfolio_heat_pct: Max total portfolio risk%
            daily_loss_cap_pct: Max daily loss as % of equity
            max_concurrent_positions: Max number of open positions
            max_correlated_positions: Max positions in correlated assets
        """
        # Equity tracking
        self.initial_equity = initial_equity
        self.current_equity = initial_equity
        self.peak_equity = initial_equity
        self.daily_start_equity = initial_equity

        # Risk parameters
        self.base_risk_pct = {
            Regime.BULL: base_risk_pct_bull,
            Regime.SIDEWAYS: base_risk_pct_sideways,
            Regime.BEAR: base_risk_pct_bear,
            Regime.UNKNOWN: base_risk_pct_bear
        }

        self.max_portfolio_heat_pct = max_portfolio_heat_pct
        self.daily_loss_cap_pct = daily_loss_cap_pct
        self.max_concurrent_positions = max_concurrent_positions
        self.max_correlated_positions = max_correlated_positions

        # Positions
        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: List[Dict] = []

        # Daily tracking
        self.daily_reset_time: Optional[datetime] = None
        self.daily_pnl = 0.0
        self.daily_loss_cap_hit = False

        # Risk adjustments (for drawdown periods)
        self.risk_multiplier = 1.0  # Can be reduced during drawdowns

    def reset_daily(self):
        """Reset daily tracking"""
        now = datetime.now()
        print(f"[Risk] Daily reset at {now}")

        self.daily_start_equity = self.current_equity
        self.daily_pnl = 0.0
        self.daily_loss_cap_hit = False
        self.daily_reset_time = now

        # Reset risk multiplier if equity recovered
        drawdown_pct = (1 - self.current_equity / self.peak_equity) * 100

        if drawdown_pct < 3:
            # Small/no drawdown, reset multiplier
            self.risk_multiplier = 1.0
        elif drawdown_pct < 5:
            # Moderate drawdown, reduce risk
            self.risk_multiplier = 0.5
        else:
            # Significant drawdown, minimal risk
            self.risk_multiplier = 0.3

    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: float,
        regime: Regime,
        signal_quality: float = 1.0
    ) -> Tuple[float, Dict]:
        """
        Calculate position size based on risk parameters

        Args:
            symbol: Trading symbol
            entry_price: Intended entry price
            stop_loss_price: Stop loss price
            regime: Current market regime
            signal_quality: Signal quality score [0-1], higher = better

        Returns:
            (position_size_usd, sizing_details)
        """
        # Base risk for regime
        base_risk_pct = self.base_risk_pct[regime]

        # Adjust for signal quality (higher quality = larger size)
        quality_multiplier = 0.5 + (signal_quality * 0.5)  # Range: 0.5 to 1.0

        # Apply risk multiplier (reduced during drawdowns)
        adjusted_risk_pct = base_risk_pct * quality_multiplier * self.risk_multiplier

        # Calculate dollar risk
        risk_usd = (adjusted_risk_pct / 100) * self.current_equity

        # Calculate position size
        price_risk_per_unit = abs(entry_price - stop_loss_price)

        if price_risk_per_unit == 0:
            return 0.0, {'error': 'Stop loss price equals entry price'}

        position_size_usd = risk_usd / (price_risk_per_unit / entry_price)

        # Cap position size at reasonable % of equity
        max_position_size_pct = 20.0  # No single position > 20% of equity
        max_position_size_usd = (max_position_size_pct / 100) * self.current_equity

        if position_size_usd > max_position_size_usd:
            position_size_usd = max_position_size_usd
            actual_risk_pct = (risk_usd / self.current_equity) * 100
        else:
            actual_risk_pct = adjusted_risk_pct

        sizing_details = {
            'regime': regime.value,
            'base_risk_pct': base_risk_pct,
            'signal_quality': signal_quality,
            'quality_multiplier': quality_multiplier,
            'risk_multiplier': self.risk_multiplier,
            'adjusted_risk_pct': adjusted_risk_pct,
            'actual_risk_pct': actual_risk_pct,
            'risk_usd': risk_usd,
            'position_size_usd': position_size_usd,
            'position_size_pct_equity': (position_size_usd / self.current_equity) * 100
        }

        return position_size_usd, sizing_details

    def can_open_position(
        self,
        symbol: str,
        risk_usd: float,
        check_correlation: bool = True
    ) -> Tuple[bool, str]:
        """
        Check if we can open a new position

        Returns:
            (can_open: bool, reason: str)
        """
        # 1. Check daily loss cap
        if self.daily_loss_cap_hit:
            return False, "Daily loss cap hit"

        daily_pnl_pct = (self.daily_pnl / self.daily_start_equity) * 100

        if daily_pnl_pct <= -self.daily_loss_cap_pct:
            self.daily_loss_cap_hit = True
            return False, f"Daily loss cap hit: {daily_pnl_pct:.2f}%"

        # 2. Check max concurrent positions
        if len(self.open_positions) >= self.max_concurrent_positions:
            return False, f"Max concurrent positions reached ({self.max_concurrent_positions})"

        # 3. Check portfolio heat
        current_heat_pct = self.get_portfolio_heat_pct()
        new_risk_pct = (risk_usd / self.current_equity) * 100

        if current_heat_pct + new_risk_pct > self.max_portfolio_heat_pct:
            return False, f"Portfolio heat would exceed {self.max_portfolio_heat_pct}%"

        # 4. Check if symbol already has open position
        if symbol in self.open_positions:
            return False, f"Already have open position in {symbol}"

        # 5. Check correlation (simple version: same sector/similar names)
        if check_correlation:
            correlated_count = self._count_correlated_positions(symbol)

            if correlated_count >= self.max_correlated_positions:
                return False, f"Max correlated positions reached ({correlated_count})"

        return True, "OK"

    def open_position(
        self,
        symbol: str,
        entry_price: float,
        size_usd: float,
        stop_loss_price: float,
        timestamp: Optional[datetime] = None
    ) -> Position:
        """
        Open a new position

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            size_usd: Position size in USD
            stop_loss_price: Initial stop loss
            timestamp: Entry timestamp

        Returns:
            Position object
        """
        position = Position(symbol, entry_price, size_usd, stop_loss_price, timestamp)

        self.open_positions[symbol] = position

        print(f"[Risk] Opened position: {symbol} @ ${entry_price:.4f}, "
              f"size=${size_usd:.2f}, risk={position.get_risk_pct(self.current_equity):.2f}%")

        return position

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str,
        timestamp: Optional[datetime] = None
    ) -> Optional[Dict]:
        """
        Close an open position

        Returns:
            Trade result dict with P&L and metrics
        """
        if symbol not in self.open_positions:
            print(f"[Risk] WARNING: Attempted to close non-existent position {symbol}")
            return None

        position = self.open_positions[symbol]

        # Calculate P&L
        pnl_usd = position.get_unrealized_pnl_usd()
        pnl_r = position.get_unrealized_pnl_r()
        pnl_pct = (pnl_usd / self.current_equity) * 100

        # Update equity
        self.current_equity += pnl_usd
        self.daily_pnl += pnl_usd

        # Update peak
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity

        # Record trade
        trade_result = {
            'symbol': symbol,
            'entry_time': position.timestamp,
            'exit_time': timestamp or datetime.now(),
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'size_usd': position.size_usd,
            'stop_loss': position.stop_loss_price,
            'pnl_usd': pnl_usd,
            'pnl_r': pnl_r,
            'pnl_pct': pnl_pct,
            'mae_r': position.max_adverse_excursion,
            'mfe_r': position.max_favorable_excursion,
            'exit_reason': exit_reason,
            'hold_time_hours': (
                (timestamp or datetime.now()) - position.timestamp
            ).total_seconds() / 3600
        }

        self.closed_positions.append(trade_result)

        # Remove from open positions
        del self.open_positions[symbol]

        print(f"[Risk] Closed position: {symbol} @ ${exit_price:.4f}, "
              f"P&L={pnl_r:.2f}R (${pnl_usd:.2f}), reason={exit_reason}")

        return trade_result

    def update_position_price(self, symbol: str, current_price: float):
        """Update current price for a position"""
        if symbol in self.open_positions:
            self.open_positions[symbol].update_price(current_price)

    def get_portfolio_heat_pct(self) -> float:
        """Get current portfolio heat (sum of position risks as % of equity)"""
        total_risk = sum(
            pos.risk_usd for pos in self.open_positions.values()
        )

        return (total_risk / self.current_equity) * 100 if self.current_equity > 0 else 0.0

    def _count_correlated_positions(self, symbol: str) -> int:
        """
        Count how many open positions are correlated with this symbol

        Simple heuristic: check for common prefixes/tokens
        (e.g., DOGEUSDT and SHIBUSDT both meme coins)
        """
        # Extract base token
        base_token = symbol.replace('USDT', '').replace('USDC', '')

        # Meme coin clusters
        meme_tokens = {'DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BONK'}
        ai_tokens = {'AGIX', 'FET', 'RNDR', 'OCEAN'}
        gaming_tokens = {'AXS', 'SAND', 'MANA', 'GALA'}

        def get_cluster(token):
            if token in meme_tokens:
                return 'MEME'
            if token in ai_tokens:
                return 'AI'
            if token in gaming_tokens:
                return 'GAMING'
            return None

        my_cluster = get_cluster(base_token)

        if my_cluster is None:
            return 0

        # Count positions in same cluster
        count = 0
        for pos_symbol in self.open_positions.keys():
            pos_token = pos_symbol.replace('USDT', '').replace('USDC', '')
            if get_cluster(pos_token) == my_cluster:
                count += 1

        return count

    def get_stats(self) -> Dict:
        """Get current risk/equity statistics"""
        return {
            'current_equity': self.current_equity,
            'peak_equity': self.peak_equity,
            'drawdown_pct': (1 - self.current_equity / self.peak_equity) * 100,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': (self.daily_pnl / self.daily_start_equity) * 100,
            'open_positions': len(self.open_positions),
            'portfolio_heat_pct': self.get_portfolio_heat_pct(),
            'risk_multiplier': self.risk_multiplier,
            'daily_loss_cap_hit': self.daily_loss_cap_hit,
            'total_trades': len(self.closed_positions)
        }


# Singleton instance
risk_engine = RiskEngine(
    initial_equity=500.0,
    base_risk_pct_bull=0.4,
    base_risk_pct_sideways=0.25,
    base_risk_pct_bear=0.12,
    max_portfolio_heat_pct=1.5,
    daily_loss_cap_pct=2.0,
    max_concurrent_positions=5
)
