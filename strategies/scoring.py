"""
Scoring Model and Adaptive Threshold System for Alpha Sniper Strategy.

Implements:
- Normalized scoring (no arbitrary weights)
- Momentum bonuses (regime-aware)
- Rolling median adaptive threshold
- Cold-start logic
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ScoringModel:
    """
    Calculates final scores with normalized components and momentum bonuses.

    Scoring Model:
    ==============
    Final_Score_raw = (Trend_Score + Breakout_Score + RVOL_Score + OB_Score + Pullback_Score) / 5

    Momentum Bonuses (Regime-Aware):
    ================================
    10A. RSI-Rank Bonus:
        If regime=='bull' AND RSI_Rank>=85:
            Final_Score = min(1.0, Final_Score_raw + 0.1)

    10B. Alt/BTC Bonus:
        If regime=='bull' AND RS_alt_z > 0.5 AND Z_ret > 0:
            Final_Score += 0.05 (clamped to 1.0)
    """

    def __init__(self):
        """Initialize scoring model."""
        self.RSI_RANK_THRESHOLD = 85
        self.RSI_BONUS = 0.1
        self.RS_ALT_Z_THRESHOLD = 0.5
        self.RS_ALT_BONUS = 0.05

        logger.info("ScoringModel initialized")

    def calculate_score(
        self,
        features: pd.Series,
        regime: str,
        regime_data: Dict
    ) -> float:
        """
        Calculate final score for a single data point.

        Args:
            features: Series with all feature values
            regime: Current regime ('bull', 'sideways', 'bear')
            regime_data: Dictionary with regime info (z_ret, rs_alt, rs_alt_z)

        Returns:
            Final score (0-1)
        """
        # Base components (all normalized 0-1)
        components = []

        # 1. Trend Score
        if 'trend_score' in features:
            components.append(features['trend_score'])

        # 2. Breakout Score
        if 'breakout_score' in features:
            components.append(features['breakout_score'])

        # 3. RVOL Score
        if 'rvol_score' in features:
            components.append(features['rvol_score'])

        # 4. OB Score (if available)
        if 'ob_score' in features:
            components.append(features['ob_score'])

        # 5. Pullback Score
        if 'pullback_score' in features:
            components.append(features['pullback_score'])

        # Calculate raw score (average of components)
        if not components:
            return 0.0

        score_raw = sum(components) / len(components)

        # Apply momentum bonuses
        final_score = self._apply_momentum_bonuses(
            score_raw,
            features,
            regime,
            regime_data
        )

        # Clamp to [0, 1]
        final_score = np.clip(final_score, 0, 1)

        return final_score

    def calculate_scores_vectorized(
        self,
        df: pd.DataFrame,
        regime: str,
        regime_data: Dict
    ) -> pd.Series:
        """
        Calculate scores for entire dataframe (vectorized for backtesting).

        Args:
            df: DataFrame with all features
            regime: Current regime
            regime_data: Dictionary with regime info

        Returns:
            Series of final scores
        """
        # Calculate base score (average of 5 components)
        components = []

        if 'trend_score' in df.columns:
            components.append(df['trend_score'])
        if 'breakout_score' in df.columns:
            components.append(df['breakout_score'])
        if 'rvol_score' in df.columns:
            components.append(df['rvol_score'])
        if 'ob_score' in df.columns:
            components.append(df['ob_score'])
        if 'pullback_score' in df.columns:
            components.append(df['pullback_score'])

        if not components:
            return pd.Series(0.0, index=df.index)

        # Calculate mean of components
        scores_raw = sum(components) / len(components)

        # Apply momentum bonuses (vectorized)
        scores_final = self._apply_momentum_bonuses_vectorized(
            scores_raw,
            df,
            regime,
            regime_data
        )

        # Clamp to [0, 1]
        scores_final = np.clip(scores_final, 0, 1)

        return scores_final

    def _apply_momentum_bonuses(
        self,
        score_raw: float,
        features: pd.Series,
        regime: str,
        regime_data: Dict
    ) -> float:
        """Apply momentum bonuses to raw score."""
        score = score_raw

        # Bonus 1: RSI-Rank Bonus (bull only)
        if regime == 'bull' and 'rsi_rank' in features:
            if features['rsi_rank'] >= self.RSI_RANK_THRESHOLD:
                score = min(1.0, score + self.RSI_BONUS)
                logger.debug(f"Applied RSI-rank bonus: {score}")

        # Bonus 2: Alt/BTC Bonus (bull only)
        if regime == 'bull':
            rs_alt_z = regime_data.get('rs_alt_z', 0)
            z_ret = regime_data.get('z_ret', 0)

            if rs_alt_z > self.RS_ALT_Z_THRESHOLD and z_ret > 0:
                score = min(1.0, score + self.RS_ALT_BONUS)
                logger.debug(f"Applied RS_alt bonus: {score}")

        return score

    def _apply_momentum_bonuses_vectorized(
        self,
        scores_raw: pd.Series,
        df: pd.DataFrame,
        regime: str,
        regime_data: Dict
    ) -> pd.Series:
        """Apply momentum bonuses (vectorized)."""
        scores = scores_raw.copy()

        # Bonus 1: RSI-Rank Bonus (bull only)
        if regime == 'bull' and 'rsi_rank' in df.columns:
            rsi_bonus_mask = df['rsi_rank'] >= self.RSI_RANK_THRESHOLD
            scores[rsi_bonus_mask] = np.minimum(1.0, scores[rsi_bonus_mask] + self.RSI_BONUS)

        # Bonus 2: Alt/BTC Bonus (bull only)
        if regime == 'bull':
            rs_alt_z = regime_data.get('rs_alt_z', 0)
            z_ret = regime_data.get('z_ret', 0)

            if rs_alt_z > self.RS_ALT_Z_THRESHOLD and z_ret > 0:
                # Apply to all (since this is market-wide)
                scores = np.minimum(1.0, scores + self.RS_ALT_BONUS)

        return scores


class AdaptiveThresholdManager:
    """
    Manages rolling median adaptive thresholds per symbol.

    Rolling Median Entry Threshold:
    ================================
    Maintain score_history[sym] list.

    Threshold rules:
    - If len == 0: threshold = 0.60 (cold start)
    - If len < 200: threshold = median(score_history[sym])
    - If len >= 200: threshold = median(last 200 scores)

    Optional global warm-start: if global_scores>=100 and symbol empty, use median(global_scores).
    Optional training period: first 30 days use fixed threshold=0.60.
    """

    def __init__(
        self,
        cold_start_threshold: float = 0.60,
        min_samples_for_adaptive: int = 200,
        global_warmstart: bool = True,
        training_period_days: int = 30
    ):
        """
        Initialize adaptive threshold manager.

        Args:
            cold_start_threshold: Initial threshold when no history (default 0.60)
            min_samples_for_adaptive: Min samples before using rolling median
            global_warmstart: Use global scores for new symbols
            training_period_days: Days to use fixed threshold initially
        """
        self.cold_start_threshold = cold_start_threshold
        self.min_samples = min_samples_for_adaptive
        self.global_warmstart = global_warmstart
        self.training_period_days = training_period_days

        # Per-symbol score history
        self.score_history: Dict[str, List[float]] = defaultdict(list)

        # Global score history (for warm-start)
        self.global_scores: List[float] = []

        # Track first score timestamp per symbol
        self.symbol_start_times: Dict[str, pd.Timestamp] = {}

        logger.info(
            f"AdaptiveThresholdManager initialized: "
            f"cold_start={cold_start_threshold}, min_samples={self.min_samples}"
        )

    def update_score_history(
        self,
        symbol: str,
        score: float,
        timestamp: pd.Timestamp
    ) -> None:
        """
        Update score history for a symbol.

        Args:
            symbol: Trading symbol
            score: Calculated score
            timestamp: Score timestamp
        """
        # Add to symbol history
        self.score_history[symbol].append(score)

        # Add to global history
        self.global_scores.append(score)

        # Track first timestamp for symbol
        if symbol not in self.symbol_start_times:
            self.symbol_start_times[symbol] = timestamp

        # Limit history size (keep last 500 for memory efficiency)
        if len(self.score_history[symbol]) > 500:
            self.score_history[symbol] = self.score_history[symbol][-500:]

        if len(self.global_scores) > 5000:
            self.global_scores = self.global_scores[-5000:]

    def get_threshold(
        self,
        symbol: str,
        current_timestamp: Optional[pd.Timestamp] = None
    ) -> float:
        """
        Get adaptive threshold for a symbol.

        Args:
            symbol: Trading symbol
            current_timestamp: Current timestamp (for training period check)

        Returns:
            Threshold value (0-1)
        """
        history = self.score_history.get(symbol, [])

        # Check if in training period
        if current_timestamp and symbol in self.symbol_start_times:
            days_since_start = (current_timestamp - self.symbol_start_times[symbol]).days
            if days_since_start < self.training_period_days:
                logger.debug(
                    f"{symbol} in training period ({days_since_start}/{self.training_period_days} days)"
                )
                return self.cold_start_threshold

        # Case 1: No history - cold start
        if len(history) == 0:
            # Check global warm-start
            if self.global_warmstart and len(self.global_scores) >= 100:
                threshold = np.median(self.global_scores)
                logger.info(f"{symbol} using global warm-start threshold: {threshold:.3f}")
                return threshold
            else:
                logger.info(f"{symbol} using cold-start threshold: {self.cold_start_threshold}")
                return self.cold_start_threshold

        # Case 2: Less than min_samples - use all available history
        elif len(history) < self.min_samples:
            threshold = np.median(history)
            logger.debug(
                f"{symbol} using partial history threshold: {threshold:.3f} "
                f"(n={len(history)})"
            )
            return threshold

        # Case 3: Enough samples - use rolling median of last N samples
        else:
            recent_history = history[-self.min_samples:]
            threshold = np.median(recent_history)
            logger.debug(
                f"{symbol} using adaptive threshold: {threshold:.3f} "
                f"(rolling median of {len(recent_history)})"
            )
            return threshold

    def check_entry_allowed(
        self,
        symbol: str,
        score: float,
        current_timestamp: Optional[pd.Timestamp] = None
    ) -> bool:
        """
        Check if score meets adaptive threshold.

        Args:
            symbol: Trading symbol
            score: Calculated score
            current_timestamp: Current timestamp

        Returns:
            True if entry allowed, False otherwise
        """
        threshold = self.get_threshold(symbol, current_timestamp)
        return score >= threshold

    def get_all_thresholds(self) -> Dict[str, float]:
        """
        Get current thresholds for all symbols.

        Returns:
            Dictionary mapping symbol -> threshold
        """
        thresholds = {}
        for symbol in self.score_history.keys():
            thresholds[symbol] = self.get_threshold(symbol)
        return thresholds

    def reset_symbol_history(self, symbol: str) -> None:
        """
        Reset history for a symbol.

        Args:
            symbol: Trading symbol
        """
        if symbol in self.score_history:
            del self.score_history[symbol]
        if symbol in self.symbol_start_times:
            del self.symbol_start_times[symbol]
        logger.info(f"Reset history for {symbol}")

    def get_statistics(self) -> Dict:
        """
        Get statistics about threshold system.

        Returns:
            Dictionary with statistics
        """
        return {
            'num_symbols': len(self.score_history),
            'total_global_scores': len(self.global_scores),
            'global_median': np.median(self.global_scores) if self.global_scores else 0.0,
            'symbols_tracked': list(self.score_history.keys()),
            'symbol_sample_counts': {
                sym: len(hist) for sym, hist in self.score_history.items()
            }
        }
