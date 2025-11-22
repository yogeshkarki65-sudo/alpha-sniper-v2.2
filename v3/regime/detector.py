#!/usr/bin/env python3
"""
Regime Detector - Multi-signal regime classification with hysteresis

V4.2_FULL_DYNAMIC:
- 4 regimes: BULL, SIDEWAYS, MILD_BEAR, DEEP_BEAR
- MILD_BEAR: Shallow correction (-10% to -25% from ATH, breadth 30-45%)
- DEEP_BEAR: Deep crash (>-25% from ATH, breadth <30%, high volatility)
- Shorts enabled per-regime via ENABLE_SHORTS_IN_* env vars
"""

import os
from enum import Enum
from typing import Optional


class Regime(Enum):
    """
    Market regime classification (4 states).

    V4.2_FULL_DYNAMIC splits BEAR into MILD_BEAR and DEEP_BEAR:
    - BULL: Strong uptrend, score > 30
    - SIDEWAYS: Ranging market, score -30 to +30
    - MILD_BEAR: Shallow correction, score -30 to -60
    - DEEP_BEAR: Deep crash/capitulation, score < -60
    """
    BULL = "BULL"
    SIDEWAYS = "SIDEWAYS"
    MILD_BEAR = "MILD_BEAR"
    DEEP_BEAR = "DEEP_BEAR"


class RegimeDetector:
    """
    Detects market regime using multiple signals with hysteresis.

    V4.2_FULL_DYNAMIC: 4-regime system with granular bear detection.

    Signals:
    - BTC trend (EMA crossovers, slope)
    - Market breadth (% of coins above MA)
    - Volatility (distinguishes MILD vs DEEP bear)
    - Volume patterns
    """

    def __init__(self):
        self.current_regime = Regime.SIDEWAYS
        self.regime_score = 0  # -100 (DEEP_BEAR) to +100 (BULL)
        self.hysteresis_threshold = 15  # Points needed to change regime

        print(f"[RegimeDetector] Initialized - Starting regime: {self.current_regime.name}")

    def update_regime(self, btc_data: dict, market_breadth: dict) -> Regime:
        """
        Update current regime based on latest data.

        V4.2_FULL_DYNAMIC regime thresholds:
        - BULL: score > 30
        - SIDEWAYS: score -30 to +30
        - MILD_BEAR: score -30 to -60
        - DEEP_BEAR: score < -60

        Args:
            btc_data: BTC metrics (price, EMAs, volume, etc.)
            market_breadth: Market-wide metrics (% above MA, etc.)

        Returns:
            Current regime after update
        """
        # Calculate regime score from signals
        score = 0

        # Signal 1: BTC trend (±30 points)
        btc_trend = self._calculate_btc_trend(btc_data)
        score += btc_trend

        # Signal 2: Market breadth (±30 points)
        breadth_score = self._calculate_breadth_score(market_breadth)
        score += breadth_score

        # Signal 3: Volatility (±20 points)
        volatility_score = self._calculate_volatility_score(btc_data)
        score += volatility_score

        # Signal 4: Volume (±20 points)
        volume_score = self._calculate_volume_score(btc_data)
        score += volume_score

        # Update regime with hysteresis (4-regime system)
        old_regime = self.current_regime
        old_score = self.regime_score
        self.regime_score = score

        # Determine new regime based on score thresholds
        new_regime = self._score_to_regime(score)

        # Apply hysteresis - only change if score moved significantly
        if new_regime != self.current_regime:
            if abs(score - old_score) > self.hysteresis_threshold:
                self.current_regime = new_regime
            # For bear transitions, be more sensitive (less hysteresis)
            elif new_regime in [Regime.MILD_BEAR, Regime.DEEP_BEAR] and score < -30:
                self.current_regime = new_regime

        if old_regime != self.current_regime:
            print(f"🔄 [RegimeDetector] Regime changed: {old_regime.name} → {self.current_regime.name} (score: {score})")

        return self.current_regime

    def _score_to_regime(self, score: int) -> Regime:
        """
        Convert regime score to regime enum.

        Thresholds:
        - BULL: score > 30
        - SIDEWAYS: -30 to +30
        - MILD_BEAR: -30 to -60
        - DEEP_BEAR: < -60
        """
        if score > 30:
            return Regime.BULL
        elif score >= -30:
            return Regime.SIDEWAYS
        elif score >= -60:
            return Regime.MILD_BEAR
        else:
            return Regime.DEEP_BEAR

    def should_trade_longs(self) -> bool:
        """
        Should we take LONG positions in this regime?

        V4.2_FULL_DYNAMIC:
        - BULL: Yes (full longs)
        - SIDEWAYS: Yes (careful longs)
        - MILD_BEAR: Limited (bear-resilient micro-longs only)
        - DEEP_BEAR: Limited (bear-resilient micro-longs only)
        """
        ignore_regime = os.getenv('SIM_IGNORE_REGIME', 'false').lower() == 'true'
        if ignore_regime:
            return True

        # Longs allowed in all regimes, but risk engine adjusts sizing
        # Bear-resilient engine handles MILD_BEAR and DEEP_BEAR
        return True

    def should_trade_shorts(self) -> bool:
        """
        Should we take SHORT positions in this regime?

        V4.2_FULL_DYNAMIC:
        - BULL: NO (ENABLE_SHORTS_IN_BULL=false by default)
        - SIDEWAYS: Yes if ENABLE_SHORTS_IN_SIDEWAYS=true
        - MILD_BEAR: Yes if ENABLE_SHORTS_IN_MILD_BEAR=true
        - DEEP_BEAR: Yes if ENABLE_SHORTS_IN_DEEP_BEAR=true

        All require ENABLE_FUTURES=true and pass MAX_FUNDING_8H_SHORT filter.
        """
        ignore_regime = os.getenv('SIM_IGNORE_REGIME', 'false').lower() == 'true'
        if ignore_regime:
            return True

        # Check if futures are enabled (required for shorts)
        enable_futures = os.getenv('ENABLE_FUTURES', 'false').lower() == 'true'
        if not enable_futures:
            return False

        # Check regime-specific shorts settings
        enable_shorts_bull = os.getenv('ENABLE_SHORTS_IN_BULL', 'false').lower() == 'true'
        enable_shorts_sideways = os.getenv('ENABLE_SHORTS_IN_SIDEWAYS', 'false').lower() == 'true'
        enable_shorts_mild_bear = os.getenv('ENABLE_SHORTS_IN_MILD_BEAR', 'false').lower() == 'true'
        enable_shorts_deep_bear = os.getenv('ENABLE_SHORTS_IN_DEEP_BEAR', 'false').lower() == 'true'

        # V4.2_FULL_DYNAMIC: 4-regime shorts logic
        if self.current_regime == Regime.BULL and enable_shorts_bull:
            return True
        if self.current_regime == Regime.SIDEWAYS and enable_shorts_sideways:
            return True
        if self.current_regime == Regime.MILD_BEAR and enable_shorts_mild_bear:
            return True
        if self.current_regime == Regime.DEEP_BEAR and enable_shorts_deep_bear:
            return True

        return False

    def _calculate_btc_trend(self, btc_data: dict) -> int:
        """
        Calculate BTC trend score (-30 to +30).

        Factors:
        - EMA20 vs EMA50 crossover
        - Price slope
        - Price position relative to EMAs
        """
        score = 0

        price = btc_data.get('price', 0)
        ema20 = btc_data.get('ema20', price)
        ema50 = btc_data.get('ema50', price)

        # EMA crossover (±15 points)
        if ema20 > ema50 * 1.02:
            score += 15
        elif ema20 < ema50 * 0.98:
            score -= 15

        # Price position (±15 points)
        if price > ema20 * 1.05:
            score += 15
        elif price < ema20 * 0.95:
            score -= 15

        return max(-30, min(30, score))

    def _calculate_breadth_score(self, market_breadth: dict) -> int:
        """
        Calculate market breadth score (-30 to +30).

        V4.2_FULL_DYNAMIC: More granular for MILD vs DEEP bear detection.

        Factors:
        - % of coins above 50-day MA
        - % of coins making new highs vs lows
        """
        score = 0

        pct_above_ma = market_breadth.get('pct_above_50ma', 50)

        # Strong bull: >70% above MA
        if pct_above_ma > 70:
            score += 30
        # Bull: 55-70%
        elif pct_above_ma > 55:
            score += 15
        # Sideways: 45-55%
        elif pct_above_ma >= 45:
            score += 0
        # Mild bear: 30-45%
        elif pct_above_ma >= 30:
            score -= 15
        # Deep bear: <30%
        else:
            score -= 30

        return max(-30, min(30, score))

    def _calculate_volatility_score(self, btc_data: dict) -> int:
        """
        Calculate volatility score (-20 to +20).

        V4.2_FULL_DYNAMIC: High volatility + downtrend = DEEP_BEAR signal.

        Low volatility + rising = bullish
        High volatility + falling = bearish (deep bear signal)
        """
        score = 0

        volatility = btc_data.get('volatility', 0)
        trend = btc_data.get('trend', 0)

        # Low vol + uptrend = bullish
        if volatility < 0.02 and trend > 0:
            score += 20
        # Medium vol + downtrend = mild bear
        elif 0.02 <= volatility <= 0.05 and trend < 0:
            score -= 10
        # High vol + downtrend = deep bear signal
        elif volatility > 0.05 and trend < 0:
            score -= 20

        return max(-20, min(20, score))

    def _calculate_volume_score(self, btc_data: dict) -> int:
        """
        Calculate volume score (-20 to +20).

        Rising volume + rising price = bullish
        Rising volume + falling price = bearish
        """
        score = 0

        volume_trend = btc_data.get('volume_trend', 0)
        price_trend = btc_data.get('price_trend', 0)

        # Volume confirming uptrend
        if volume_trend > 0 and price_trend > 0:
            score += 20
        # Volume confirming downtrend (capitulation signal)
        elif volume_trend > 0 and price_trend < 0:
            score -= 20

        return max(-20, min(20, score))

    def get_regime_info(self) -> dict:
        """Get current regime information."""
        return {
            'regime': self.current_regime.name,
            'score': self.regime_score,
            'can_trade_longs': self.should_trade_longs(),
            'can_trade_shorts': self.should_trade_shorts()
        }

    def is_bear_regime(self) -> bool:
        """Check if current regime is any type of bear (MILD or DEEP)."""
        return self.current_regime in [Regime.MILD_BEAR, Regime.DEEP_BEAR]


# Global instance
regime_detector = RegimeDetector()
