"""
Scanner Scorer for Alpha Sniper V3.2

Scores signals based on extracted features.

Initially uses hand-weighted scoring, designed to be replaced
with ML models later (Phase 3).
"""
import numpy as np
from typing import Dict, Optional
from v3.regime.detector import Regime


class ScannerScorer:
    """
    Scores trading signals based on features and regime
    """

    def __init__(
        self,
        # Base weights (can be tuned via optimization)
        trend_weight: float = 0.25,
        rvol_weight: float = 0.30,
        compression_weight: float = 0.20,
        momentum_weight: float = 0.15,
        ob_weight: float = 0.10
    ):
        """
        Args:
            trend_weight: Weight for trend features
            rvol_weight: Weight for volume features
            compression_weight: Weight for compression/basing features
            momentum_weight: Weight for momentum features
            ob_weight: Weight for orderbook features
        """
        self.base_weights = {
            'trend': trend_weight,
            'rvol': rvol_weight,
            'compression': compression_weight,
            'momentum': momentum_weight,
            'ob': ob_weight
        }

        # Regime-specific adjustments
        self.regime_adjustments = {
            Regime.BULL: {
                'trend': 0.20,
                'rvol': 0.35,
                'compression': 0.15,
                'momentum': 0.25,
                'ob': 0.05
            },
            Regime.SIDEWAYS: {
                'trend': 0.30,
                'rvol': 0.25,
                'compression': 0.30,
                'momentum': 0.10,
                'ob': 0.05
            },
            Regime.BEAR: {
                'trend': 0.40,
                'rvol': 0.20,
                'compression': 0.25,
                'momentum': 0.05,
                'ob': 0.10
            },
            Regime.UNKNOWN: {
                'trend': 0.30,
                'rvol': 0.25,
                'compression': 0.25,
                'momentum': 0.10,
                'ob': 0.10
            }
        }

    def calculate_score(
        self,
        features: Dict,
        regime: Regime,
        symbol_state: Optional[str] = None
    ) -> Dict:
        """
        Calculate scanner score for a symbol

        Args:
            features: Feature dict from FeatureExtractor
            regime: Current market regime
            symbol_state: Current symbol state (BASING, BREAKING_OUT, etc.)

        Returns:
            Dict with:
            - score: Overall score [0-100]
            - component_scores: Breakdown by component
            - quality: Quality grade (A/B/C/D/F)
            - is_valid: Whether signal passes minimum thresholds
        """
        # Get regime-adjusted weights
        weights = self.regime_adjustments.get(regime, self.base_weights)

        # Calculate component scores [0-1]
        component_scores = {
            'trend': self._score_trend(features),
            'rvol': self._score_rvol(features),
            'compression': self._score_compression(features),
            'momentum': self._score_momentum(features, regime),
            'ob': self._score_orderbook(features)
        }

        # Weighted sum
        raw_score = sum(
            component_scores[component] * weight
            for component, weight in weights.items()
        )

        # State bonus (if in favorable state)
        state_multiplier = self._get_state_multiplier(symbol_state)
        raw_score *= state_multiplier

        # Convert to 0-100 scale
        final_score = raw_score * 100

        # Apply penalties
        final_score = self._apply_penalties(final_score, features, regime)

        # Determine quality grade
        quality = self._get_quality_grade(final_score)

        # Check if valid (passes minimum thresholds)
        is_valid = self._check_validity(features, final_score, regime)

        return {
            'score': np.clip(final_score, 0, 100),
            'component_scores': component_scores,
            'weights': weights,
            'state_multiplier': state_multiplier,
            'quality': quality,
            'is_valid': is_valid
        }

    def _score_trend(self, features: Dict) -> float:
        """Score trend component"""
        # Already normalized in features
        trend_score = features.get('trend_score', 0.5)

        # Bonus for price in upper range
        pos_in_range = features.get('position_in_range', 0.5)
        if pos_in_range > 0.6:
            trend_score *= 1.1

        return np.clip(trend_score, 0.0, 1.0)

    def _score_rvol(self, features: Dict) -> float:
        """Score volume component"""
        # Already normalized in features
        rvol_score = features.get('rvol_score', 0.0)

        # Bonus for volume surge
        vol_surge = features.get('vol_surge', 1.0)
        if vol_surge > 1.5:
            rvol_score *= 1.2

        return np.clip(rvol_score, 0.0, 1.0)

    def _score_compression(self, features: Dict) -> float:
        """Score compression/basing component"""
        # Already normalized in features
        compression_score = features.get('compression_score', 0.0)

        # Bonus for price in upper half during compression
        if compression_score > 0.5:
            pos_in_range = features.get('position_in_range', 0.5)
            if pos_in_range > 0.5:
                compression_score *= 1.15

        return np.clip(compression_score, 0.0, 1.0)

    def _score_momentum(self, features: Dict, regime: Regime) -> float:
        """Score momentum component"""
        momentum_score = features.get('momentum_score', 0.5)

        # In bull regime, reward strong positive momentum
        if regime == Regime.BULL:
            ret_24h = features.get('ret_24h', 0)
            if ret_24h > 10:  # >10% in 24h
                momentum_score *= 1.3
            elif ret_24h > 5:
                momentum_score *= 1.15

        # In bear/sideways, be more selective
        elif regime in [Regime.BEAR, Regime.SIDEWAYS]:
            ret_24h = features.get('ret_24h', 0)
            if ret_24h < 5:  # Less than 5% move
                momentum_score *= 0.7

        return np.clip(momentum_score, 0.0, 1.0)

    def _score_orderbook(self, features: Dict) -> float:
        """Score orderbook component"""
        # Already normalized in features
        ob_score = features.get('ob_score', 0.5)

        return np.clip(ob_score, 0.0, 1.0)

    def _get_state_multiplier(self, symbol_state: Optional[str]) -> float:
        """
        Get score multiplier based on symbol state

        BASING = 1.2x (good setup)
        BREAKING_OUT = 1.1x (momentum)
        FLAT = 1.0x (neutral)
        EXTENDED/FAILED/COOLDOWN = 0.0x (reject)
        """
        if symbol_state is None:
            return 1.0

        multipliers = {
            'BASING': 1.2,
            'BREAKING_OUT': 1.1,
            'FLAT': 1.0,
            'EXTENDED': 0.0,
            'FAILED': 0.0,
            'COOLDOWN': 0.0
        }

        return multipliers.get(symbol_state, 1.0)

    def _apply_penalties(self, score: float, features: Dict, regime: Regime) -> float:
        """Apply penalty filters"""
        # Exhaustion penalty
        if features.get('is_exhausted', False):
            print(f"[Scorer] Exhaustion penalty for {features.get('symbol')}")
            return 0.0

        # Weak RVOL in bull (want confirmation)
        if regime == Regime.BULL:
            rvol = features.get('rvol_15m', 1.0)
            if rvol < 1.2:
                score *= 0.7

        # Downtrend penalty
        trend_ratio = features.get('trend_ratio', 1.0)
        if trend_ratio < 0.98:  # EMA20 < EMA50
            score *= 0.5

        return score

    def _get_quality_grade(self, score: float) -> str:
        """Assign quality grade based on score"""
        if score >= 80:
            return 'A'
        elif score >= 70:
            return 'B'
        elif score >= 60:
            return 'C'
        elif score >= 50:
            return 'D'
        else:
            return 'F'

    def _check_validity(self, features: Dict, score: float, regime: Regime) -> bool:
        """
        Check if signal passes minimum thresholds

        Returns True if signal is valid for trading
        """
        # Minimum score threshold (regime-dependent)
        min_scores = {
            Regime.BULL: 60,
            Regime.SIDEWAYS: 70,
            Regime.BEAR: 80,
            Regime.UNKNOWN: 75
        }

        min_score = min_scores.get(regime, 70)

        if score < min_score:
            return False

        # Minimum RVOL
        rvol = features.get('rvol_15m', 0)
        min_rvol = 1.2 if regime == Regime.BULL else 1.5

        if rvol < min_rvol:
            return False

        # No exhaustion
        if features.get('is_exhausted', False):
            return False

        # Must have some positive momentum
        ret_24h = features.get('ret_24h', 0)
        if ret_24h < 0:  # No negative momentum
            return False

        return True

    def rank_signals(self, signals: list, top_k: int = 5) -> list:
        """
        Rank signals by score and return top K

        Args:
            signals: List of signal dicts (with 'score' key)
            top_k: Number of top signals to return

        Returns:
            List of top K signals, sorted by score descending
        """
        # Filter valid signals only
        valid_signals = [s for s in signals if s.get('is_valid', False)]

        # Sort by score
        sorted_signals = sorted(
            valid_signals,
            key=lambda x: x.get('score', 0),
            reverse=True
        )

        return sorted_signals[:top_k]


# Singleton instance
scanner_scorer = ScannerScorer()
