#!/usr/bin/env python3
"""
Signal Generator - Generate trading signals from features

NEW FEATURE: Integrated Bear-Resilient Long Engine routing
"""

from typing import Optional, Dict, List
from datetime import datetime

from v3.scanner.features import Features, extract_features
from v3.scanner.bear_resilient_long import bear_resilient_long_engine
from v3.regime.detector import Regime, regime_detector


class SignalGenerator:
    """
    Generates trading signals based on features and regime.

    NEW FEATURE: Routes to Bear-Resilient Long Engine in BEAR regime if enabled.
    """

    def __init__(self):
        self.min_score = 70  # Minimum score for standard signals
        print("[SignalGenerator] Initialized")

    def scan_universe(
        self,
        symbols: List[str],
        regime: Regime,
        equity: float,
        btc_return_14d: float = 0
    ) -> List[Dict]:
        """
        Scan all symbols and generate signals.

        Args:
            symbols: List of trading pairs to scan
            regime: Current market regime
            equity: Current account equity
            btc_return_14d: BTC 14-day return for RS calculation

        Returns:
            List of signal dicts sorted by score (descending)
        """
        signals = []
        failed_count = 0

        for symbol in symbols:
            try:
                signal = self._scan_symbol(
                    symbol=symbol,
                    regime=regime,
                    equity=equity,
                    btc_return_14d=btc_return_14d
                )

                if signal:
                    signals.append(signal)

            except Exception as e:
                print(f"[Signals] {symbol}: Error during scan: {e}")
                failed_count += 1

        print(f"[Signals] Scanned {len(symbols)} symbols: {len(signals)} signals, {failed_count} failed")

        # Sort by score descending
        signals.sort(key=lambda s: s.get('score', 0), reverse=True)

        return signals

    def _scan_symbol(
        self,
        symbol: str,
        regime: Regime,
        equity: float,
        btc_return_14d: float
    ) -> Optional[Dict]:
        """
        Scan a single symbol for trading signal.

        NEW FEATURE: Routes to Bear-Resilient Long Engine if in BEAR regime.

        Returns:
            Signal dict or None
        """
        # Extract features
        features = extract_features(
            symbol=symbol,
            equity=equity,
            btc_return_14d=btc_return_14d
        )

        if features is None:
            return None

        # NEW FEATURE: Check if using bear-resilient long engine
        if regime == Regime.BEAR and bear_resilient_long_engine.enabled:
            # Get current bear-resilient positions count
            from v3.risk.risk_engine import risk_engine
            current_bear_longs = sum(
                1 for pos in risk_engine.open_positions.values()
                if getattr(pos, 'engine', None) == 'bear_resilient_long'
            )

            # Try bear-resilient long engine
            signal = bear_resilient_long_engine.scan_symbol(
                symbol=symbol,
                features=features,
                regime=regime,
                current_bear_longs=current_bear_longs
            )

            if signal:
                return signal

            # If no bear-resilient signal, fall through to standard SHORT engine

        # Standard signal generation based on regime
        if regime == Regime.BEAR and regime_detector.should_trade_shorts():
            return self._generate_short_signal(features, regime, equity)

        elif regime_detector.should_trade_longs():
            return self._generate_long_signal(features, regime, equity)

        return None

    def _generate_long_signal(self, features: Features, regime: Regime, equity: float) -> Optional[Dict]:
        """
        Generate LONG signal using standard momentum/trend scoring.

        Returns:
            Signal dict or None
        """
        score = 0

        # Momentum (0-30 points)
        if features.return_24h > 0.05:
            score += 15
        if features.return_3d > 0.10:
            score += 15

        # Trend (0-25 points)
        if features.close > features.ema20_1h:
            score += 10
        if features.ema20_1h > features.ema50_1h:
            score += 15

        # Volume (0-20 points)
        if features.rvol > 1.5:
            score += 20

        # Liquidity (0-15 points)
        if features.spread_pct < 0.5:
            score += 10
        if features.depth_10 > 10000:
            score += 5

        # Structure (0-10 points)
        if 0.7 < features.price_pos_24h < 0.95:
            score += 10

        if score < self.min_score:
            return None

        # Calculate position parameters
        stop_loss = features.close * 0.97  # 3% stop loss
        take_profit = features.close * 1.06  # 6% take profit
        size_usd = equity * 0.20  # 20% of equity

        signal = {
            'symbol': features.symbol,
            'direction': 'LONG',
            'engine': 'standard',
            'score': score,
            'regime': regime.name,
            'entry_price': features.close,
            'size_usd': size_usd,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'timestamp': datetime.now(),
            'reason': f'Momentum + trend signal (score: {score})'
        }

        return signal

    def _generate_short_signal(self, features: Features, regime: Regime, equity: float) -> Optional[Dict]:
        """
        Generate SHORT signal for BEAR regime.

        Returns:
            Signal dict or None
        """
        score = 0

        # Negative momentum (0-30 points)
        if features.return_24h < -0.03:
            score += 15
        if features.return_3d < -0.05:
            score += 15

        # Downtrend (0-25 points)
        if features.close < features.ema20_1h:
            score += 10
        if features.ema20_1h < features.ema50_1h:
            score += 15

        # Volume (0-20 points)
        if features.rvol > 1.3:
            score += 20

        # Liquidity (0-15 points)
        if features.spread_pct < 0.5:
            score += 10
        if features.depth_10 > 10000:
            score += 5

        # Structure (0-10 points)
        if 0.05 < features.price_pos_24h < 0.3:
            score += 10

        if score < self.min_score:
            return None

        # Calculate position parameters
        stop_loss = features.close * 1.03  # 3% stop loss (above entry for SHORT)
        take_profit = features.close * 0.94  # 6% take profit (below entry for SHORT)
        size_usd = equity * 0.20  # 20% of equity

        signal = {
            'symbol': features.symbol,
            'direction': 'SHORT',
            'engine': 'standard',
            'score': score,
            'regime': regime.name,
            'entry_price': features.close,
            'size_usd': size_usd,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'timestamp': datetime.now(),
            'reason': f'Downtrend signal in BEAR regime (score: {score})'
        }

        return signal


# Global instance
signal_generator = SignalGenerator()
