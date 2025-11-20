#!/usr/bin/env python3
"""
Regime Detector - Multi-signal regime classification with hysteresis

BUG FIX: SIM_IGNORE_REGIME flag replaces automatic SIM override (BUG C)
"""

import os
from enum import Enum
from typing import Optional


class Regime(Enum):
    """Market regime classification."""
    BULL = "BULL"
    SIDEWAYS = "SIDEWAYS"
    BEAR = "BEAR"


class RegimeDetector:
    """
    Detects market regime using multiple signals with hysteresis.

    Signals:
    - BTC trend (EMA crossovers, slope)
    - Market breadth (% of coins above MA)
    - Volatility
    - Volume patterns
    """

    def __init__(self):
        self.current_regime = Regime.SIDEWAYS
        self.regime_score = 0  # -100 (BEAR) to +100 (BULL)
        self.hysteresis_threshold = 15  # Points needed to change regime

        print(f"[RegimeDetector] Initialized - Starting regime: {self.current_regime.name}")

    def update_regime(self, btc_data: dict, market_breadth: dict) -> Regime:
        """
        Update current regime based on latest data.

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

        # Update regime with hysteresis
        old_regime = self.current_regime
        self.regime_score = score

        if score > 30 and (self.current_regime != Regime.BULL or score > self.regime_score + self.hysteresis_threshold):
            self.current_regime = Regime.BULL
        elif score < -30 and (self.current_regime != Regime.BEAR or score < self.regime_score - self.hysteresis_threshold):
            self.current_regime = Regime.BEAR
        elif -30 <= score <= 30:
            if abs(score - self.regime_score) > self.hysteresis_threshold:
                self.current_regime = Regime.SIDEWAYS

        if old_regime != self.current_regime:
            print(f"🔄 [RegimeDetector] Regime changed: {old_regime.name} → {self.current_regime.name} (score: {score})")

        return self.current_regime

    def should_trade_longs(self) -> bool:
        """
        Should we take LONG positions in this regime?

        BUG FIX (BUG C): SIM must behave EXACTLY like LIVE by default.
        Use SIM_IGNORE_REGIME=true to override (RISKY!)
        """
        # Check if override flag is set
        ignore_regime = os.getenv('SIM_IGNORE_REGIME', 'false').lower() == 'true'

        if ignore_regime:
            print("⚠️  [WARNING] SIM_IGNORE_REGIME=true - Trading in ALL regimes (RISKY!)")
            return True

        # Normal behavior: Only trade longs in BULL or SIDEWAYS
        return self.current_regime in [Regime.BULL, Regime.SIDEWAYS]

    def should_trade_shorts(self) -> bool:
        """
        Should we take SHORT positions in this regime?

        BUG FIX (BUG C): Respects SIM_IGNORE_REGIME flag.
        """
        # Check if override flag is set
        ignore_regime = os.getenv('SIM_IGNORE_REGIME', 'false').lower() == 'true'

        if ignore_regime:
            return True

        # Normal behavior: Only trade shorts in BEAR
        return self.current_regime == Regime.BEAR

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
        # Bear: <30%
        elif pct_above_ma < 30:
            score -= 30
        # Weak: 30-45%
        elif pct_above_ma < 45:
            score -= 15

        return max(-30, min(30, score))

    def _calculate_volatility_score(self, btc_data: dict) -> int:
        """
        Calculate volatility score (-20 to +20).

        Low volatility + rising = bullish
        High volatility + falling = bearish
        """
        score = 0

        volatility = btc_data.get('volatility', 0)
        trend = btc_data.get('trend', 0)

        # Low vol + uptrend = bullish
        if volatility < 0.02 and trend > 0:
            score += 20
        # High vol + downtrend = bearish
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
        # Volume confirming downtrend
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


# Global instance
regime_detector = RegimeDetector()
