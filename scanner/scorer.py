"""
Advanced Scoring System for Alpha Sniper V3.0

Provides multi-factor signal scoring with:
- Technical indicators (RSI, momentum, MA, ATR)
- Volume analysis
- Orderbook imbalance
- Learnable weights
- Component breakdowns for analysis
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, Optional
from pathlib import Path


@dataclass
class ScoreWeights:
    """
    Configurable weights for each scoring component.
    Sum should equal 1.0 for interpretability.
    """
    # Volume-based features
    rvol: float = 0.15              # Relative volume surge
    liquidity: float = 0.05         # 24h volume in USD

    # Price momentum features
    velocity_24h: float = 0.15      # 24h price change
    momentum_1h: float = 0.10       # 1h price change
    momentum_15m: float = 0.10      # 15m price change

    # Technical indicators
    rsi: float = 0.10               # RSI(14) - oversold/overbought
    trend_position: float = 0.10    # Position in 24h range
    above_ma: float = 0.05          # Price above 1h MA

    # Market microstructure
    orderbook_imbalance: float = 0.10  # Bid/ask pressure
    spread: float = 0.05            # Bid-ask spread (tighter = better)

    # Volatility
    atr_pct: float = 0.05           # Average True Range % (opportunity)

    def __post_init__(self):
        """Validate weights sum to 1.0"""
        total = sum(asdict(self).values())
        if not (0.99 <= total <= 1.01):  # Allow small floating point errors
            raise ValueError(f"Weights must sum to 1.0, got {total:.4f}")

    @classmethod
    def load(cls, filepath: str = "data/weights.json") -> 'ScoreWeights':
        """Load weights from file or return defaults"""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)

                # Migration map for old V2 weights to new V3 weights
                old_to_new = {
                    'velocity': 'velocity_24h',
                    'trend': 'trend_position',
                }

                # Check if this is an old format and migrate
                if 'velocity' in data or 'trend' in data:
                    print(f"[scorer] 🔄 Migrating old V2 weights format to V3...")
                    migrated = {}
                    for old_key, new_key in old_to_new.items():
                        if old_key in data:
                            migrated[new_key] = data[old_key]

                    # Keep keys that exist in both versions
                    for key in ['rvol', 'liquidity', 'orderbook_imbalance', 'spread']:
                        if key in data:
                            migrated[key] = data[key]

                    # Use migrated data or fall back to defaults
                    try:
                        weights = cls(**migrated)
                        print(f"[scorer] ✅ Migration successful, using migrated weights")
                        # Save the new format
                        weights.save(filepath)
                        return weights
                    except Exception as e:
                        print(f"[scorer] ⚠️ Migration failed: {e}, using defaults")
                        # Delete old file and use defaults
                        os.rename(filepath, filepath + ".v2.bak")
                        weights = cls()
                        weights.save(filepath)
                        return weights
                else:
                    # New format, load directly
                    try:
                        return cls(**data)
                    except Exception as e:
                        print(f"[scorer] ⚠️ Failed to load weights: {e}, using defaults")
                        os.rename(filepath, filepath + ".invalid.bak")
                        weights = cls()
                        weights.save(filepath)
                        return weights
        return cls()

    def save(self, filepath: str = "data/weights.json"):
        """Save weights to file"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(asdict(self), f, indent=2)


@dataclass
class ScoringFeatures:
    """
    All features used for scoring a trading signal.
    Missing features default to neutral values.
    """
    # Required features
    symbol: str
    last_price: float

    # Volume features
    rvol: float = 1.0                      # Relative volume (1.0 = average)
    liquidity_usd_24h: float = 0.0         # 24h volume in USD

    # Price momentum
    velocity_24h_pct: float = 0.0          # 24h % change
    momentum_1h_pct: float = 0.0           # 1h % change
    momentum_15m_pct: float = 0.0          # 15m % change

    # Technical indicators
    rsi_14: float = 50.0                   # RSI(14), neutral at 50
    trend_position: float = 0.5            # 0-1, where in 24h range
    above_ma_1h: bool = True               # Price above 1h MA

    # Market microstructure
    orderbook_imbalance: float = 0.0       # -1 to +1, 0 is balanced
    spread_bps: float = 10.0               # Bid-ask spread in basis points

    # Volatility
    atr_pct: float = 2.0                   # ATR as % of price


class SignalScorer:
    """
    Multi-factor signal scoring system.

    Example:
        >>> weights = ScoreWeights.load()
        >>> scorer = SignalScorer(weights)
        >>>
        >>> features = ScoringFeatures(
        ...     symbol="BTCUSDT",
        ...     last_price=50000,
        ...     rvol=2.5,
        ...     velocity_24h_pct=5.2,
        ...     rsi_14=35,  # Oversold
        ... )
        >>>
        >>> result = scorer.score(features)
        >>> print(f"Score: {result['total_score']:.1f}")
        >>> print(f"Components: {result['components']}")
    """

    def __init__(self, weights: Optional[ScoreWeights] = None):
        """
        Initialize scorer with weights.

        Args:
            weights: ScoreWeights instance, or None to load from file
        """
        self.weights = weights or ScoreWeights.load()

    def score(self, features: ScoringFeatures) -> Dict:
        """
        Calculate overall score and component breakdown.

        Args:
            features: ScoringFeatures with all available data

        Returns:
            Dict with:
                - total_score: 0-100
                - components: Dict of individual component scores
                - weights_used: Dict of weights applied
        """
        components = {}

        # 1. Volume surge (RVOL)
        # Higher is better, normalize with log scale
        # rvol of 2.0 = good, 3.0 = very good, 5.0+ = excellent
        components['rvol'] = self._normalize_rvol(features.rvol)

        # 2. Liquidity (24h volume)
        # More liquid = more tradeable, less slippage
        components['liquidity'] = self._normalize_liquidity(features.liquidity_usd_24h)

        # 3. 24h Velocity (price change)
        # Strong moves in either direction
        components['velocity_24h'] = self._normalize_velocity(features.velocity_24h_pct)

        # 4. 1h Momentum
        # Recent momentum confirms 24h trend
        components['momentum_1h'] = self._normalize_momentum(features.momentum_1h_pct)

        # 5. 15m Momentum
        # Very recent momentum for entry timing
        components['momentum_15m'] = self._normalize_momentum(features.momentum_15m_pct)

        # 6. RSI
        # Oversold (< 30) or overbought (> 70) conditions
        components['rsi'] = self._normalize_rsi(features.rsi_14)

        # 7. Trend Position
        # Where price is in 24h range (higher = more bullish)
        components['trend_position'] = features.trend_position * 100

        # 8. Above MA
        # Price above moving average = bullish
        components['above_ma'] = 100.0 if features.above_ma_1h else 0.0

        # 9. Orderbook Imbalance
        # Positive = buy pressure, negative = sell pressure
        components['orderbook_imbalance'] = self._normalize_imbalance(
            features.orderbook_imbalance
        )

        # 10. Spread
        # Tighter spread = better liquidity, lower is better
        components['spread'] = self._normalize_spread(features.spread_bps)

        # 11. ATR (volatility = opportunity)
        # Higher ATR = more opportunity, but capped
        components['atr_pct'] = self._normalize_atr(features.atr_pct)

        # Calculate weighted score
        total_score = (
            self.weights.rvol * components['rvol'] +
            self.weights.liquidity * components['liquidity'] +
            self.weights.velocity_24h * components['velocity_24h'] +
            self.weights.momentum_1h * components['momentum_1h'] +
            self.weights.momentum_15m * components['momentum_15m'] +
            self.weights.rsi * components['rsi'] +
            self.weights.trend_position * components['trend_position'] +
            self.weights.above_ma * components['above_ma'] +
            self.weights.orderbook_imbalance * components['orderbook_imbalance'] +
            self.weights.spread * components['spread'] +
            self.weights.atr_pct * components['atr_pct']
        )

        return {
            'total_score': min(100.0, max(0.0, total_score)),  # Clamp to 0-100
            'components': components,
            'weights_used': asdict(self.weights),
            'symbol': features.symbol,
        }

    # Normalization functions (each returns 0-100)

    def _normalize_rvol(self, rvol: float) -> float:
        """
        Normalize relative volume.
        1.0 = average (50 points)
        2.0 = 2x average (75 points)
        3.0+ = 3x+ average (90+ points)
        """
        if rvol <= 0:
            return 0.0
        # Logarithmic scale to handle extreme values
        import math
        score = 50 + (math.log(rvol) / math.log(2)) * 25
        return min(100.0, max(0.0, score))

    def _normalize_liquidity(self, liquidity_usd: float) -> float:
        """
        Normalize 24h volume in USD.
        $50k = 25 points
        $100k = 50 points
        $500k+ = 100 points
        """
        if liquidity_usd <= 0:
            return 0.0
        import math
        # Logarithmic scale
        score = (math.log10(max(1, liquidity_usd)) - 4) * 33.33  # 10^4 = $10k
        return min(100.0, max(0.0, score))

    def _normalize_velocity(self, velocity_pct: float) -> float:
        """
        Normalize 24h price change.
        ±5% = 50 points
        ±10% = 75 points
        ±20%+ = 100 points
        """
        abs_vel = abs(velocity_pct)
        score = min(abs_vel * 5, 100.0)  # 20% = 100 points
        return score

    def _normalize_momentum(self, momentum_pct: float) -> float:
        """
        Normalize short-term momentum.
        ±2% = 50 points
        ±5% = 100 points
        """
        abs_mom = abs(momentum_pct)
        score = min(abs_mom * 20, 100.0)  # 5% = 100 points
        return score

    def _normalize_rsi(self, rsi: float) -> float:
        """
        Normalize RSI.
        Extreme values (oversold/overbought) score higher.
        RSI 30 (oversold) = 80 points
        RSI 20 (very oversold) = 100 points
        RSI 50 (neutral) = 20 points
        RSI 70 (overbought) = 80 points
        RSI 80 (very overbought) = 100 points
        """
        if rsi < 30:
            # Oversold: lower is better
            score = 80 + (30 - rsi) * 2  # 20 RSI = 100 points
        elif rsi > 70:
            # Overbought: higher is better
            score = 80 + (rsi - 70) * 2  # 80 RSI = 100 points
        else:
            # Neutral zone: low score
            # RSI 50 = 20, RSI 40 or 60 = 40
            score = 20 + abs(50 - rsi) * 2
        return min(100.0, max(0.0, score))

    def _normalize_imbalance(self, imbalance: float) -> float:
        """
        Normalize orderbook imbalance (-1 to +1).
        Strong imbalance in either direction is good.
        0 (balanced) = 0 points
        ±0.5 = 50 points
        ±1.0 = 100 points
        """
        score = abs(imbalance) * 100
        return min(100.0, score)

    def _normalize_spread(self, spread_bps: float) -> float:
        """
        Normalize spread (lower is better).
        1 bp = 100 points (excellent)
        5 bps = 75 points (good)
        10 bps = 50 points (ok)
        50+ bps = 0 points (poor)
        """
        if spread_bps <= 0:
            return 100.0
        # Inverse relationship
        score = max(0, 100 - spread_bps * 2)
        return score

    def _normalize_atr(self, atr_pct: float) -> float:
        """
        Normalize ATR% (volatility = opportunity).
        1% = 25 points
        2% = 50 points
        5% = 100 points
        """
        score = min(atr_pct * 20, 100.0)  # 5% = 100 points
        return score


# Legacy compatibility function
def calculate_score(rvol: float, velocity: float, trend: float, orderbook_imbalance: float) -> float:
    """
    Legacy scoring function for backward compatibility.
    Will be removed in future versions.

    Use SignalScorer class instead for new code.
    """
    features = ScoringFeatures(
        symbol="LEGACY",
        last_price=1.0,
        rvol=rvol,
        velocity_24h_pct=velocity,
        trend_position=trend,
        orderbook_imbalance=orderbook_imbalance,
    )

    scorer = SignalScorer()
    result = scorer.score(features)
    return result['total_score']


# Weight management functions for learning module
def load_weights() -> ScoreWeights:
    """Load weights from file"""
    return ScoreWeights.load()


def save_weights(weights_dict: Dict):
    """Save weights to file"""
    weights = ScoreWeights(**weights_dict)
    weights.save()


if __name__ == "__main__":
    # Test the scorer
    print("Testing SignalScorer V3.0...")

    # Create test features
    features = ScoringFeatures(
        symbol="BTCUSDT",
        last_price=50000,
        rvol=2.5,                    # 2.5x average volume
        liquidity_usd_24h=1_000_000, # $1M 24h volume
        velocity_24h_pct=8.5,        # +8.5% in 24h
        momentum_1h_pct=2.3,         # +2.3% in 1h
        momentum_15m_pct=0.8,        # +0.8% in 15m
        rsi_14=35,                   # Oversold
        trend_position=0.75,         # In upper 25% of range
        above_ma_1h=True,            # Above MA
        orderbook_imbalance=0.6,     # Strong buy pressure
        spread_bps=5.0,              # 5 bps spread
        atr_pct=3.2,                 # 3.2% ATR
    )

    scorer = SignalScorer()
    result = scorer.score(features)

    print(f"\nTotal Score: {result['total_score']:.1f}/100")
    print("\nComponent Breakdown:")
    for component, score in sorted(result['components'].items(), key=lambda x: x[1], reverse=True):
        weight = result['weights_used'][component]
        contribution = weight * score
        print(f"  {component:20s}: {score:5.1f}/100 (weight: {weight:.2f}, contrib: {contribution:.1f})")

    print("\n✅ Scorer test complete!")
