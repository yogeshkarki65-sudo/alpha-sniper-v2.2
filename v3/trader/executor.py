"""
Trade Executor for Alpha Sniper V3.2

Handles:
- Entry execution (limit/market orders)
- Position opening with risk management
- Integration with Risk Engine
- Execution cost tracking
"""
from typing import Dict, Optional, Tuple
from datetime import datetime

from v3.risk.risk_engine import risk_engine, Position
from v3.regime.detector import regime_detector
from v3.execution.cost_model import execution_cost_model
from v3.data.mexc_client import mexc_client


class TradeExecutor:
    """
    Executes trades based on signals
    """

    def __init__(
        self,
        mode: str = "SIM",  # SIM or LIVE
        max_slippage_pct: float = 0.5,  # Max acceptable slippage
        entry_urgency: str = "NORMAL"  # LOW, NORMAL, HIGH
    ):
        """
        Args:
            mode: Trading mode (SIM for simulation, LIVE for real)
            max_slippage_pct: Maximum acceptable slippage %
            entry_urgency: Entry urgency level
        """
        self.mode = mode
        self.max_slippage_pct = max_slippage_pct
        self.entry_urgency = entry_urgency

        # Statistics
        self.entry_attempts = 0
        self.successful_entries = 0
        self.rejected_entries = 0

    def execute_signal(self, signal: Dict) -> Optional[Position]:
        """
        Execute a trading signal

        Args:
            signal: Signal dict from scanner

        Returns:
            Position object if successful, None if rejected
        """
        symbol = signal['symbol']
        print(f"\n{'='*60}")
        print(f"🎯 EXECUTING SIGNAL: {symbol}")
        print(f"{'='*60}")

        self.entry_attempts += 1

        # 1. Get current regime
        regime, _ = regime_detector.detect()
        print(f"📊 Regime: {regime.value}")

        # 2. Get current price and spread
        ticker = self._get_current_ticker(symbol)
        if ticker is None:
            print(f"❌ Could not fetch ticker for {symbol}")
            self.rejected_entries += 1
            return None

        current_price = float(ticker.get('lastPrice', 0))
        spread_pct = mexc_client.get_spread_pct(symbol)

        if spread_pct is None or spread_pct > self.max_slippage_pct:
            print(f"❌ Spread too wide: {spread_pct}%")
            self.rejected_entries += 1
            return None

        print(f"💰 Current Price: ${current_price:.6f}")
        print(f"📏 Spread: {spread_pct:.3f}%")

        # 3. Calculate stop loss
        stop_loss_price = self._calculate_stop_loss(signal, current_price)
        print(f"🛑 Stop Loss: ${stop_loss_price:.6f} ({abs(current_price - stop_loss_price) / current_price * 100:.2f}%)")

        # 4. Calculate position size
        signal_quality = signal.get('score', 70) / 100.0  # Normalize to 0-1

        size_usd, sizing_details = risk_engine.calculate_position_size(
            symbol=symbol,
            entry_price=current_price,
            stop_loss_price=stop_loss_price,
            regime=regime,
            signal_quality=signal_quality
        )

        print(f"📐 Position Size: ${size_usd:.2f} ({sizing_details['position_size_pct_equity']:.1f}% of equity)")
        print(f"⚠️  Risk: {sizing_details['actual_risk_pct']:.3f}% (${sizing_details['risk_usd']:.2f})")

        # 5. Check if we can open position
        can_open, reason = risk_engine.can_open_position(
            symbol=symbol,
            risk_usd=sizing_details['risk_usd']
        )

        if not can_open:
            print(f"❌ Cannot open position: {reason}")
            self.rejected_entries += 1
            return None

        # 6. Estimate execution costs
        orderbook_depth = 10000  # Assume reasonable depth (would fetch real in live)
        cost_estimate = execution_cost_model.estimate_entry_cost(
            symbol=symbol,
            intended_price=current_price,
            order_size_usd=size_usd,
            spread_pct=spread_pct,
            orderbook_depth_usd=orderbook_depth,
            urgency=self.entry_urgency
        )

        print(f"💸 Estimated Cost: {cost_estimate['total_cost_pct']*100:.3f}%")
        print(f"   Expected Fill: ${cost_estimate['expected_fill_price']:.6f}")

        # 7. Execute entry (SIM or LIVE)
        if self.mode == "SIM":
            fill_price = self._simulate_entry(current_price, cost_estimate)
        else:
            fill_price = self._live_entry(symbol, current_price, size_usd, cost_estimate)

        if fill_price is None:
            print(f"❌ Entry failed")
            self.rejected_entries += 1
            return None

        # 8. Open position in risk engine
        position = risk_engine.open_position(
            symbol=symbol,
            entry_price=fill_price,
            size_usd=size_usd,
            stop_loss_price=stop_loss_price,
            timestamp=datetime.now()
        )

        # 9. Record fill for learning
        execution_cost_model.record_fill(
            symbol=symbol,
            side="BUY",
            intended_price=current_price,
            actual_fill_price=fill_price,
            size_usd=size_usd
        )

        self.successful_entries += 1

        print(f"✅ POSITION OPENED")
        print(f"   Entry: ${fill_price:.6f}")
        print(f"   Size: ${size_usd:.2f}")
        print(f"   Stop: ${stop_loss_price:.6f}")
        print(f"   Risk: {position.get_risk_pct(risk_engine.current_equity):.2f}%")
        print(f"{'='*60}\n")

        return position

    def _get_current_ticker(self, symbol: str) -> Optional[Dict]:
        """Get current ticker data"""
        try:
            # In production, would fetch single symbol ticker
            # For now, get from 24h tickers
            tickers = mexc_client.get_24h_tickers()
            for ticker in tickers:
                if ticker.get('symbol') == symbol:
                    return ticker
            return None
        except Exception as e:
            print(f"[Executor] Error fetching ticker: {e}")
            return None

    def _calculate_stop_loss(self, signal: Dict, entry_price: float) -> float:
        """
        Calculate stop loss price

        Uses ATR-based stop (2x ATR14 or structure low, whichever is larger)
        """
        features = signal.get('features', {})
        atr_14 = features.get('atr_14', 0)

        # ATR-based stop (2x ATR)
        atr_stop_distance = 2.0 * atr_14

        # Also check structure low (24h low)
        low_24h = features.get('low_24h', entry_price * 0.95)
        structure_stop_distance = entry_price - low_24h

        # Use the larger of the two (more conservative)
        stop_distance = max(atr_stop_distance, structure_stop_distance)

        # Ensure minimum stop (at least 2%)
        min_stop = entry_price * 0.02
        stop_distance = max(stop_distance, min_stop)

        # Ensure maximum stop (no more than 10%)
        max_stop = entry_price * 0.10
        stop_distance = min(stop_distance, max_stop)

        stop_price = entry_price - stop_distance

        return stop_price

    def _simulate_entry(self, intended_price: float, cost_estimate: Dict) -> float:
        """
        Simulate entry in SIM mode

        Uses cost model to estimate realistic fill price
        """
        fill_price = cost_estimate['expected_fill_price']
        return fill_price

    def _live_entry(
        self,
        symbol: str,
        price: float,
        size_usd: float,
        cost_estimate: Dict
    ) -> Optional[float]:
        """
        Execute live entry on exchange

        This would place actual orders via exchange API
        """
        # TODO: Implement live order placement
        # For now, return None (not implemented)
        print(f"[Executor] LIVE trading not implemented yet")
        return None

    def get_stats(self) -> Dict:
        """Get executor statistics"""
        success_rate = (
            self.successful_entries / self.entry_attempts * 100
            if self.entry_attempts > 0 else 0
        )

        return {
            'entry_attempts': self.entry_attempts,
            'successful_entries': self.successful_entries,
            'rejected_entries': self.rejected_entries,
            'success_rate_pct': success_rate
        }


# Singleton instance
trade_executor = TradeExecutor(
    mode="SIM",
    max_slippage_pct=0.5,
    entry_urgency="NORMAL"
)
