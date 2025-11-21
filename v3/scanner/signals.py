#!/usr/bin/env python3
"""
Signal Generator - Generate trading signals from features

V4.1.1 UPDATES:
- Tuned parameters from 2017-2025 backtest
- ATR-based stop losses instead of fixed %
- Perfect storm score boost
- All thresholds loaded from .env
"""

import os
from typing import Optional, Dict, List
from datetime import datetime

from v3.scanner.features import Features, extract_features
from v3.scanner.bear_resilient_long import bear_resilient_long_engine
from v3.regime.detector import Regime, regime_detector


class SignalGenerator:
    """
    Generates trading signals based on features and regime.

    V4.1.1 Tuned Parameters (from 2017-2025 backtest):
    - MIN_RVOL_15M_BULL: 1.15 (was 1.5)
    - TREND_RATIO_4H_CUTOFF: 1.008
    - ATR_SL_MULT_LONG: 1.9 (ATR-based stops)
    - PERFECT_STORM_SCORE_BOOST: 0.17
    - MAX_ALLOWED_SPREAD_PCT: 1.1%
    - MIN_RVOL_15M_BEAR_SHORT: 1.25 (was 1.3)
    """

    def __init__(self):
        self.min_score = int(os.getenv('MIN_SIGNAL_SCORE', '80'))

        # V4.1.1 Tuned Parameters from .env
        self.min_rvol_bull = float(os.getenv('MIN_RVOL_15M_BULL', '1.15'))
        self.trend_ratio_cutoff = float(os.getenv('TREND_RATIO_4H_CUTOFF', '1.008'))
        self.atr_sl_mult_long = float(os.getenv('ATR_SL_MULT_LONG', '1.9'))
        self.perfect_storm_boost = float(os.getenv('PERFECT_STORM_SCORE_BOOST', '0.17'))
        self.max_spread_pct = float(os.getenv('MAX_ALLOWED_SPREAD_PCT', '1.1'))
        self.min_rvol_bear_short = float(os.getenv('MIN_RVOL_15M_BEAR_SHORT', '1.25'))

        print(f"[SignalGenerator] Initialized with tuned parameters:")
        print(f"   Min score: {self.min_score}, RVOL bull: {self.min_rvol_bull}, RVOL bear short: {self.min_rvol_bear_short}")
        print(f"   Trend ratio cutoff: {self.trend_ratio_cutoff}, ATR SL mult: {self.atr_sl_mult_long}")
        print(f"   Max spread: {self.max_spread_pct}%, Perfect storm boost: {self.perfect_storm_boost*100:.0f}%")

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

        V4.1.1 Tuned Parameters:
        - MIN_RVOL_15M_BULL: 1.15 (was 1.5)
        - TREND_RATIO_4H_CUTOFF: 1.008
        - ATR_SL_MULT_LONG: 1.9 (ATR-based stops)
        - MAX_ALLOWED_SPREAD_PCT: 1.1%
        - PERFECT_STORM_SCORE_BOOST: 0.17

        Returns:
            Signal dict or None
        """
        # Hard reject if spread too wide (V4.1.1: 1.1% max)
        if features.spread_pct > self.max_spread_pct:
            return None

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

        # V4.1.1: Trend ratio check on 4h (cutoff 1.008)
        trend_ratio_4h = getattr(features, 'trend_ratio_4h', 1.0)
        if trend_ratio_4h >= self.trend_ratio_cutoff:
            score += 5  # Bonus for clean uptrend

        # Volume (0-20 points) - V4.1.1: RVOL threshold 1.15 for bull/sideways
        if features.rvol >= self.min_rvol_bull:
            score += 20

        # Liquidity (0-15 points) - V4.1.1: spread check moved to hard reject
        if features.spread_pct < 0.5:
            score += 10
        if features.depth_10 > 10000:
            score += 5

        # Structure (0-10 points)
        if 0.7 < features.price_pos_24h < 0.95:
            score += 10

        # V4.1.1: Perfect storm boost (17% bonus when multiple factors align)
        # Check for confluence: strong trend + high RVOL + good structure
        if (trend_ratio_4h >= 1.02 and
            features.rvol >= 2.0 and
            features.return_24h > 0.08 and
            features.price_pos_24h > 0.75):
            perfect_storm_bonus = int(score * self.perfect_storm_boost)
            score += perfect_storm_bonus

        if score < self.min_score:
            return None

        # V4.1.1: ATR-based stop loss (1.9 × ATR) instead of fixed 3%
        atr_15m = getattr(features, 'atr_15m', features.close * 0.02)
        stop_distance = self.atr_sl_mult_long * atr_15m
        stop_loss = features.close - stop_distance

        # Ensure stop is at least 1% and at most 5% below entry
        min_stop = features.close * 0.95  # Max 5% stop
        max_stop = features.close * 0.99  # Min 1% stop
        stop_loss = max(min_stop, min(max_stop, stop_loss))

        # Take profit at 2:1 R:R based on actual stop distance
        actual_stop_pct = (features.close - stop_loss) / features.close
        take_profit = features.close * (1 + 2 * actual_stop_pct)

        signal = {
            'symbol': features.symbol,
            'direction': 'LONG',
            'engine': 'standard_long',
            'score': score,
            'regime': regime.name,
            'entry_price': features.close,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'atr_15m': atr_15m,
            'timestamp': datetime.now(),
            'reason': f'Momentum + trend signal (score: {score})'
            # NOTE: size_usd is calculated by risk_engine based on R
        }

        return signal

    def _generate_short_signal(self, features: Features, regime: Regime, equity: float) -> Optional[Dict]:
        """
        Generate SHORT signal for BEAR regime.

        V4.1.1 Tuned Parameters:
        - MIN_RVOL_15M_BEAR_SHORT: 1.25 (was 1.3)
        - MAX_ALLOWED_SPREAD_PCT: 1.1%

        Returns:
            Signal dict or None
        """
        # Hard reject if spread too wide (V4.1.1: 1.1% max)
        if features.spread_pct > self.max_spread_pct:
            return None

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

        # Volume (0-20 points) - V4.1.1: RVOL threshold 1.25 for bear shorts
        if features.rvol >= self.min_rvol_bear_short:
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

        # ATR-based stop loss for shorts (same multiplier as longs)
        atr_15m = getattr(features, 'atr_15m', features.close * 0.02)
        stop_distance = self.atr_sl_mult_long * atr_15m
        stop_loss = features.close + stop_distance  # Above entry for SHORT

        # Ensure stop is at least 1% and at most 5% above entry
        min_stop = features.close * 1.01  # Min 1% stop
        max_stop = features.close * 1.05  # Max 5% stop
        stop_loss = max(min_stop, min(max_stop, stop_loss))

        # Take profit at 2:1 R:R based on actual stop distance
        actual_stop_pct = (stop_loss - features.close) / features.close
        take_profit = features.close * (1 - 2 * actual_stop_pct)

        signal = {
            'symbol': features.symbol,
            'direction': 'SHORT',
            'engine': 'standard_short',
            'score': score,
            'regime': regime.name,
            'entry_price': features.close,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'atr_15m': atr_15m,
            'timestamp': datetime.now(),
            'reason': f'Downtrend signal in BEAR regime (score: {score})'
            # NOTE: size_usd is calculated by risk_engine based on R
        }

        return signal


# Global instance
signal_generator = SignalGenerator()
