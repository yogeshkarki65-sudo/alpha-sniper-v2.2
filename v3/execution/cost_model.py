"""
Execution Cost Model for Alpha Sniper V3.2

Models realistic transaction costs:
- Exchange fees (maker/taker)
- Slippage (market impact + adverse selection)
- Spread crossing

Tracks per-symbol execution quality and adapts estimates.
"""
import numpy as np
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
from datetime import datetime


class ExecutionCostModel:
    """
    Models and tracks execution costs
    """

    def __init__(
        self,
        base_fee_pct: float = 0.001,  # 0.1% taker fee
        history_size: int = 50  # Keep last N fills per symbol
    ):
        """
        Args:
            base_fee_pct: Base exchange fee
            history_size: Number of fills to track per symbol
        """
        self.base_fee_pct = base_fee_pct
        self.history_size = history_size

        # Per-symbol fill tracking
        self.fill_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_size))

        # Global tracking
        self.total_fills = 0
        self.total_slippage_cost = 0.0

    def estimate_entry_cost(
        self,
        symbol: str,
        intended_price: float,
        order_size_usd: float,
        spread_pct: float,
        orderbook_depth_usd: float,
        urgency: str = "NORMAL"  # LOW, NORMAL, HIGH
    ) -> Dict[str, float]:
        """
        Estimate total entry cost for a trade

        Args:
            symbol: Trading symbol
            intended_price: Price we want to execute at (e.g., mid price)
            order_size_usd: Order size in USD
            spread_pct: Current spread as %
            orderbook_depth_usd: Available depth within 0.2% of mid
            urgency: Execution urgency

        Returns:
            Dict with:
            - fee_pct: Exchange fee
            - spread_cost_pct: Cost of crossing spread
            - slippage_pct: Market impact slippage
            - adverse_selection_pct: Adverse selection cost
            - total_cost_pct: Total estimated cost
            - expected_fill_price: Expected actual fill price
        """
        # 1. Fee (always paid)
        fee_pct = self.base_fee_pct

        # 2. Spread crossing
        # Passive limit order = 0 spread cost but low fill prob
        # Aggressive limit = cross partial spread
        # Market order = cross full spread
        if urgency == "LOW":
            spread_cost_pct = 0.0
            fill_probability = 0.5
        elif urgency == "NORMAL":
            spread_cost_pct = spread_pct * 0.3  # Cross 30% of spread
            fill_probability = 0.7
        else:  # HIGH
            spread_cost_pct = spread_pct * 0.5  # Cross 50% of spread
            fill_probability = 0.9

        # 3. Market impact (size vs depth)
        size_ratio = order_size_usd / max(orderbook_depth_usd, 1)

        if size_ratio < 0.05:  # <5% of depth
            impact_pct = 0.0001 * size_ratio  # Minimal
        elif size_ratio < 0.10:  # 5-10%
            impact_pct = 0.001 * size_ratio
        else:  # >10% - significant impact
            impact_pct = 0.005 * size_ratio

        # 4. Adverse selection
        # When we want to buy momentum, price is moving away from us
        # Historical average: ~5-10bps on aggressive entries
        symbol_avg_adverse = self._get_avg_adverse_selection(symbol)

        if urgency == "HIGH":
            adverse_selection_pct = max(symbol_avg_adverse, 0.0008)  # 8bps minimum
        elif urgency == "NORMAL":
            adverse_selection_pct = max(symbol_avg_adverse, 0.0003)  # 3bps
        else:
            adverse_selection_pct = 0.0001  # Minimal for passive

        # 5. Total cost
        slippage_pct = spread_cost_pct + impact_pct + adverse_selection_pct

        total_cost_pct = fee_pct + slippage_pct

        # Expected fill price (for longs, we pay more)
        expected_fill_price = intended_price * (1 + slippage_pct)

        return {
            'fee_pct': fee_pct,
            'spread_cost_pct': spread_cost_pct,
            'slippage_pct': slippage_pct,
            'adverse_selection_pct': adverse_selection_pct,
            'impact_pct': impact_pct,
            'total_cost_pct': total_cost_pct,
            'expected_fill_price': expected_fill_price,
            'fill_probability': fill_probability
        }

    def estimate_exit_cost(
        self,
        symbol: str,
        intended_price: float,
        order_size_usd: float,
        spread_pct: float,
        orderbook_depth_usd: float,
        urgency: str = "NORMAL"
    ) -> Dict[str, float]:
        """
        Estimate exit cost (similar to entry but slightly different adverse selection)

        For exits, adverse selection is usually lower (we're exiting at favorable prices)
        """
        cost = self.estimate_entry_cost(
            symbol, intended_price, order_size_usd,
            spread_pct, orderbook_depth_usd, urgency
        )

        # Reduce adverse selection for exits (exiting when profitable)
        cost['adverse_selection_pct'] *= 0.5
        cost['slippage_pct'] = (
            cost['spread_cost_pct'] +
            cost['impact_pct'] +
            cost['adverse_selection_pct']
        )
        cost['total_cost_pct'] = cost['fee_pct'] + cost['slippage_pct']

        # For longs closing, we get filled lower
        cost['expected_fill_price'] = intended_price * (1 - cost['slippage_pct'])

        return cost

    def record_fill(
        self,
        symbol: str,
        side: str,  # BUY or SELL
        intended_price: float,
        actual_fill_price: float,
        size_usd: float,
        timestamp: Optional[datetime] = None
    ):
        """
        Record an actual fill to learn execution quality

        Args:
            symbol: Trading symbol
            side: BUY or SELL
            intended_price: Price we intended to execute at
            actual_fill_price: Actual fill price
            size_usd: Order size in USD
            timestamp: Fill timestamp
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Calculate realized slippage
        if side == "BUY":
            slippage_pct = (actual_fill_price - intended_price) / intended_price
        else:  # SELL
            slippage_pct = (intended_price - actual_fill_price) / intended_price

        # Adverse selection component (unexpected slippage beyond spread)
        # This is the "we got filled when it was bad for us" cost
        adverse_selection = max(0, slippage_pct - 0.001)  # Beyond 10bps is adverse

        fill_record = {
            'symbol': symbol,
            'side': side,
            'timestamp': timestamp,
            'intended_price': intended_price,
            'actual_price': actual_fill_price,
            'size_usd': size_usd,
            'slippage_pct': slippage_pct,
            'adverse_selection_pct': adverse_selection
        }

        self.fill_history[symbol].append(fill_record)
        self.total_fills += 1
        self.total_slippage_cost += slippage_pct

    def _get_avg_adverse_selection(self, symbol: str) -> float:
        """Get average adverse selection for symbol"""
        if symbol not in self.fill_history or len(self.fill_history[symbol]) == 0:
            return 0.0005  # Default 5bps

        recent_fills = list(self.fill_history[symbol])[-20:]  # Last 20 fills
        adverse_costs = [f['adverse_selection_pct'] for f in recent_fills]

        return np.mean(adverse_costs)

    def get_symbol_fill_quality(self, symbol: str) -> Dict:
        """
        Get fill quality metrics for a symbol

        Returns:
        - avg_slippage_pct: Average slippage
        - avg_adverse_selection_pct: Average adverse selection
        - fill_count: Number of fills
        - quality_score: 0-1 score (lower slippage = higher score)
        """
        if symbol not in self.fill_history or len(self.fill_history[symbol]) == 0:
            return {
                'avg_slippage_pct': 0.0,
                'avg_adverse_selection_pct': 0.0,
                'fill_count': 0,
                'quality_score': 0.5
            }

        fills = list(self.fill_history[symbol])

        avg_slippage = np.mean([f['slippage_pct'] for f in fills])
        avg_adverse = np.mean([f['adverse_selection_pct'] for f in fills])

        # Quality score: good fills = low slippage
        # Map 0bps slippage = 1.0 score, 50bps = 0.5, 100bps+ = 0
        quality_score = max(0, 1.0 - avg_slippage * 100)

        return {
            'avg_slippage_pct': avg_slippage,
            'avg_adverse_selection_pct': avg_adverse,
            'fill_count': len(fills),
            'quality_score': quality_score
        }

    def should_trade_symbol(self, symbol: str, min_quality_score: float = 0.3) -> bool:
        """
        Should we trade this symbol based on fill quality?

        If historical fills are very poor, avoid the symbol
        """
        quality = self.get_symbol_fill_quality(symbol)

        # Need at least 5 fills to judge
        if quality['fill_count'] < 5:
            return True  # Give benefit of doubt

        return quality['quality_score'] >= min_quality_score

    def get_global_stats(self) -> Dict:
        """Get global execution statistics"""
        if self.total_fills == 0:
            return {
                'total_fills': 0,
                'avg_slippage_pct': 0.0,
                'total_cost_pct': 0.0
            }

        avg_slippage = self.total_slippage_cost / self.total_fills

        # Total cost including fees
        avg_total_cost = avg_slippage + self.base_fee_pct

        return {
            'total_fills': self.total_fills,
            'avg_slippage_pct': avg_slippage,
            'total_cost_pct': avg_total_cost
        }


class FillSimulator:
    """
    Simulates realistic fills for backtesting

    Uses historical OHLC data to determine if orders would have filled
    and at what price, accounting for slippage and adverse selection.
    """

    def __init__(self, cost_model: ExecutionCostModel):
        """
        Args:
            cost_model: ExecutionCostModel instance for cost estimation
        """
        self.cost_model = cost_model

    def simulate_limit_order_fill(
        self,
        side: str,
        limit_price: float,
        bar_data: Dict,  # OHLC bar data
        spread_pct: float = 0.003
    ) -> Optional[float]:
        """
        Simulate if and where a limit order would fill

        Args:
            side: BUY or SELL
            limit_price: Limit order price
            bar_data: Dict with keys: open, high, low, close
            spread_pct: Estimated spread

        Returns:
            Fill price if filled, None if not filled

        Logic:
        - For buy limit: only fill if bar's low traded through limit
          But use pessimistic fill price (not exact low)
        - For sell limit: only fill if bar's high traded through limit
        """
        high = bar_data['high']
        low = bar_data['low']
        close = bar_data['close']

        if side == "BUY":
            # Buy limit fills if price traded at or below limit
            if low <= limit_price:
                # But did it trade significantly through?
                # If low == limit_price exactly, that's suspicious (might not fill)
                # Require price to trade through by at least 0.1% or spread
                threshold = limit_price * 0.999

                if low < threshold:
                    # Fills at limit (or slightly better if available)
                    # Pessimistic: assume fill at limit price
                    fill_price = limit_price
                    return fill_price
                else:
                    # Touched but didn't trade through - no fill
                    return None
            else:
                return None

        else:  # SELL
            # Sell limit fills if price traded at or above limit
            if high >= limit_price:
                threshold = limit_price * 1.001

                if high > threshold:
                    fill_price = limit_price
                    return fill_price
                else:
                    return None
            else:
                return None

    def simulate_market_order_fill(
        self,
        side: str,
        bar_data: Dict,
        spread_pct: float = 0.003,
        slippage_pct: float = 0.0005
    ) -> float:
        """
        Simulate market order fill

        Assumes fill at pessimistic price (ask for buy, bid for sell)
        plus additional slippage

        Args:
            side: BUY or SELL
            bar_data: Dict with keys: open, high, low, close
            spread_pct: Estimated spread
            slippage_pct: Additional slippage beyond spread

        Returns:
            Estimated fill price
        """
        close = bar_data['close']

        if side == "BUY":
            # Pay the ask + slippage
            ask = close * (1 + spread_pct / 2)
            fill_price = ask * (1 + slippage_pct)
            return fill_price
        else:  # SELL
            # Get the bid - slippage
            bid = close * (1 - spread_pct / 2)
            fill_price = bid * (1 - slippage_pct)
            return fill_price


# Singleton instance
execution_cost_model = ExecutionCostModel()
fill_simulator = FillSimulator(execution_cost_model)
