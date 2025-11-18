"""
Regime Detection Module for Alpha Sniper Strategy.

Implements Z-score based regime detection using BTC and TOTAL3 (altcoin market cap).
Regime states: Bull, Sideways, Bear

Based on quantitative thresholds with no arbitrary parameters.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging

from .technical import calculate_returns, calculate_rolling_zscore

logger = logging.getLogger(__name__)


class RegimeDetector:
    """
    Detects market regime using BTC and TOTAL3 data with Z-score normalization.

    Regime Logic (Quant Standard):
    ==============================
    Compute daily returns for BTCUSDT and TOTAL3:
    - R_21d = sum of 21 daily returns
    - Vol_21d = rolling 21d std
    - R_180 = rolling 180d sum
    - std_180 = rolling 180d std of returns

    Z-score:
    - Z_ret = (R_21d - R_180) / std_180

    Relative Strength:
    - RS_alt = R_21d(TOTAL3) - R_21d(BTC)

    Regime Rules:
    - Bull = (Z_ret > +0.5) AND (RS_alt > 0)
    - Sideways = -0.5 <= Z_ret <= +0.5
    - Bear = Z_ret < -0.5

    Recompute hourly (or on each data update).
    """

    # Regime thresholds (configurable for sensitivity testing)
    Z_BULL_THRESHOLD = 0.5
    Z_BEAR_THRESHOLD = -0.5
    RS_ALT_THRESHOLD = 0.0

    # Lookback windows
    SHORT_WINDOW = 21  # ~1 month (daily data)
    LONG_WINDOW = 180  # ~6 months (daily data)

    def __init__(
        self,
        z_bull_threshold: float = 0.5,
        z_bear_threshold: float = -0.5,
        rs_alt_threshold: float = 0.0
    ):
        """
        Initialize regime detector.

        Args:
            z_bull_threshold: Z-score threshold for bull regime
            z_bear_threshold: Z-score threshold for bear regime
            rs_alt_threshold: Relative strength threshold for alts
        """
        self.z_bull_threshold = z_bull_threshold
        self.z_bear_threshold = z_bear_threshold
        self.rs_alt_threshold = rs_alt_threshold

        logger.info(
            f"RegimeDetector initialized: "
            f"Z_bull={z_bull_threshold}, Z_bear={z_bear_threshold}, RS_alt={rs_alt_threshold}"
        )

    def detect_regime(
        self,
        btc_data: pd.DataFrame,
        total3_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Detect market regime from BTC and TOTAL3 data.

        Args:
            btc_data: DataFrame with BTC OHLCV (must have 'close', 'timestamp')
            total3_data: DataFrame with TOTAL3 OHLCV (must have 'close', 'timestamp')

        Returns:
            DataFrame with regime information for each timestamp
        """
        # Align dataframes by timestamp
        btc = btc_data.set_index('timestamp').sort_index()
        total3 = total3_data.set_index('timestamp').sort_index()

        # Ensure we have common timestamps
        common_idx = btc.index.intersection(total3.index)
        if len(common_idx) == 0:
            logger.error("No common timestamps between BTC and TOTAL3 data")
            return pd.DataFrame()

        btc = btc.loc[common_idx]
        total3 = total3.loc[common_idx]

        # Calculate returns
        btc_returns = calculate_returns(btc['close'], periods=1)
        total3_returns = calculate_returns(total3['close'], periods=1)

        # Calculate 21-day and 180-day metrics
        R_21d_btc = btc_returns.rolling(window=self.SHORT_WINDOW).sum()
        R_180_btc = btc_returns.rolling(window=self.LONG_WINDOW).sum()
        std_180_btc = btc_returns.rolling(window=self.LONG_WINDOW).std()

        R_21d_total3 = total3_returns.rolling(window=self.SHORT_WINDOW).sum()

        # Calculate Z-score for returns
        Z_ret = (R_21d_btc - R_180_btc) / std_180_btc
        Z_ret = Z_ret.fillna(0)

        # Calculate relative strength (alts vs BTC)
        RS_alt = R_21d_total3 - R_21d_btc

        # Determine regime
        regime = pd.Series('sideways', index=common_idx)

        # Bull regime: Z_ret > threshold AND RS_alt > 0
        bull_mask = (Z_ret > self.z_bull_threshold) & (RS_alt > self.rs_alt_threshold)
        regime[bull_mask] = 'bull'

        # Bear regime: Z_ret < threshold
        bear_mask = Z_ret < self.z_bear_threshold
        regime[bear_mask] = 'bear'

        # Create result dataframe
        result = pd.DataFrame({
            'timestamp': common_idx,
            'regime': regime.values,
            'z_ret': Z_ret.values,
            'rs_alt': RS_alt.values,
            'r_21d_btc': R_21d_btc.values,
            'r_21d_total3': R_21d_total3.values,
            'btc_price': btc['close'].values,
            'total3_index': total3['close'].values
        })

        result = result.reset_index(drop=True)

        # Log regime distribution
        regime_counts = result['regime'].value_counts()
        logger.info(f"Regime distribution: {regime_counts.to_dict()}")

        return result

    def get_current_regime(
        self,
        btc_data: pd.DataFrame,
        total3_data: pd.DataFrame
    ) -> Dict:
        """
        Get the current (most recent) regime state.

        Args:
            btc_data: BTC OHLCV data
            total3_data: TOTAL3 OHLCV data

        Returns:
            Dictionary with current regime info
        """
        regime_df = self.detect_regime(btc_data, total3_data)

        if regime_df.empty:
            return {
                'regime': 'unknown',
                'z_ret': 0.0,
                'rs_alt': 0.0,
                'timestamp': None
            }

        latest = regime_df.iloc[-1]

        return {
            'regime': latest['regime'],
            'z_ret': latest['z_ret'],
            'rs_alt': latest['rs_alt'],
            'r_21d_btc': latest['r_21d_btc'],
            'r_21d_total3': latest['r_21d_total3'],
            'btc_price': latest['btc_price'],
            'total3_index': latest['total3_index'],
            'timestamp': latest['timestamp']
        }

    def calculate_regime_strength(self, z_ret: float, rs_alt: float) -> float:
        """
        Calculate regime strength (confidence) score (0-1).

        Args:
            z_ret: Z-score of returns
            rs_alt: Relative strength of alts

        Returns:
            Strength score (0 = weak, 1 = strong)
        """
        # Bull strength: how far above threshold
        if z_ret > self.z_bull_threshold:
            z_strength = min(abs(z_ret - self.z_bull_threshold) / 2.0, 1.0)
            rs_strength = min(max(rs_alt, 0) / 0.1, 1.0)
            return (z_strength + rs_strength) / 2.0

        # Bear strength: how far below threshold
        elif z_ret < self.z_bear_threshold:
            return min(abs(z_ret - self.z_bear_threshold) / 2.0, 1.0)

        # Sideways: distance from thresholds (inverse)
        else:
            distance_to_bull = abs(z_ret - self.z_bull_threshold)
            distance_to_bear = abs(z_ret - self.z_bear_threshold)
            min_distance = min(distance_to_bull, distance_to_bear)
            return 1.0 - min(min_distance / 0.5, 1.0)

    def get_regime_parameters(self, regime: str) -> Dict:
        """
        Get regime-specific trading parameters.

        Args:
            regime: 'bull', 'bear', or 'sideways'

        Returns:
            Dictionary with regime parameters
        """
        if regime == 'bull':
            return {
                'rvol_threshold': 2.0,
                'ob_imbalance_threshold': 1.5,
                'risk_pct': 0.40,  # 0.40% per trade
                'position_multiplier': 1.0,
                'trend_required': True
            }
        elif regime == 'sideways':
            return {
                'rvol_threshold': 3.0,
                'ob_imbalance_threshold': 1.5,
                'risk_pct': 0.25,  # 0.25% per trade
                'position_multiplier': 0.75,
                'trend_required': True
            }
        elif regime == 'bear':
            return {
                'rvol_threshold': 4.0,
                'ob_imbalance_threshold': 2.0,
                'risk_pct': 0.12,  # 0.12% per trade
                'position_multiplier': 0.5,
                'trend_required': False  # Allow reclaim-type breakouts
            }
        else:
            # Default conservative parameters
            return {
                'rvol_threshold': 3.0,
                'ob_imbalance_threshold': 1.5,
                'risk_pct': 0.20,
                'position_multiplier': 0.5,
                'trend_required': True
            }

    def calculate_rs_alt_zscore(self, rs_alt: pd.Series, window: int = 180) -> pd.Series:
        """
        Calculate Z-score of RS_alt for momentum bonus.

        Args:
            rs_alt: Relative strength of alts series
            window: Rolling window (default 180)

        Returns:
            RS_alt Z-score series
        """
        return calculate_rolling_zscore(rs_alt, window=window)

    def detect_regime_change(self, regime_df: pd.DataFrame, lookback: int = 5) -> pd.Series:
        """
        Detect regime changes (transitions).

        Args:
            regime_df: DataFrame with regime history
            lookback: Number of periods to check for consistency

        Returns:
            Series indicating if regime just changed (True/False)
        """
        if len(regime_df) < lookback + 1:
            return pd.Series(False, index=regime_df.index)

        regime_series = regime_df['regime']
        regime_changed = regime_series != regime_series.shift(1)

        # Only flag as change if regime stays for at least 'lookback' periods
        stable_regime = regime_series.rolling(window=lookback).apply(
            lambda x: len(set(x)) == 1, raw=False
        )

        # Changed and now stable
        return regime_changed & (stable_regime == 1.0)

    def get_volatility_regime(self, btc_data: pd.DataFrame, window: int = 21) -> pd.Series:
        """
        Calculate volatility regime (high/low volatility periods).

        Args:
            btc_data: BTC OHLCV data
            window: Rolling window for volatility

        Returns:
            Series with volatility regime ('high', 'normal', 'low')
        """
        returns = calculate_returns(btc_data['close'])
        volatility = returns.rolling(window=window).std()

        # Z-score of volatility
        vol_zscore = calculate_rolling_zscore(volatility, window=window * 4)

        regime = pd.Series('normal', index=btc_data.index)
        regime[vol_zscore > 1.0] = 'high'
        regime[vol_zscore < -1.0] = 'low'

        return regime

    def backtest_regime_performance(
        self,
        regime_df: pd.DataFrame,
        returns_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Analyze regime detection performance.

        Args:
            regime_df: DataFrame with regime classifications
            returns_df: DataFrame with asset returns

        Returns:
            Performance metrics per regime
        """
        merged = pd.merge(regime_df, returns_df, on='timestamp', how='inner')

        stats = merged.groupby('regime').agg({
            'returns': ['mean', 'std', 'count'],
            'z_ret': ['mean', 'min', 'max']
        })

        stats['sharpe'] = stats[('returns', 'mean')] / stats[('returns', 'std')] * np.sqrt(252)

        return stats
