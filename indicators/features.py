"""
Advanced Feature Calculator for Alpha Sniper Strategy.

Implements all feature calculations with proper vectorization for backtesting:
- Breakout detection (24h high)
- Pullback logic (micro-pullback depth)
- RVOL (relative volume)
- Extension filters (anti-blowoff)
- Local exhaustion kill-switch
- Trend filters
- Orderbook imbalance
- Momentum features
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import logging

from .technical import (
    calculate_ema,
    calculate_rsi,
    calculate_atr,
    calculate_percentile_rank
)

logger = logging.getLogger(__name__)


class AdvancedFeatureCalculator:
    """
    Calculates all features needed for Alpha Sniper strategy.
    Designed for vectorized backtest operations.
    """

    def __init__(self):
        """Initialize feature calculator."""
        logger.info("AdvancedFeatureCalculator initialized")

    def calculate_all_features(
        self,
        df: pd.DataFrame,
        regime: str = 'sideways',
        timeframe: str = '15m'
    ) -> pd.DataFrame:
        """
        Calculate all features for a symbol's OHLCV data.

        Args:
            df: DataFrame with OHLCV data (timestamp, open, high, low, close, volume)
            regime: Current market regime ('bull', 'sideways', 'bear')
            timeframe: Data timeframe

        Returns:
            DataFrame with all features added
        """
        result = df.copy()

        # 1. Trend Filter (4H would need resampling, using current timeframe)
        result = self.calculate_trend_features(result)

        # 2. Breakout Logic
        result = self.calculate_breakout_features(result)

        # 3. Pullback Logic
        result = self.calculate_pullback_features(result)

        # 4. RVOL (Relative Volume)
        result = self.calculate_rvol_features(result)

        # 5. Extension Filter
        result = self.calculate_extension_features(result)

        # 6. Local Exhaustion
        result = self.calculate_exhaustion_features(result)

        # 7. Momentum Features
        result = self.calculate_momentum_features(result)

        # 8. Additional Technical Indicators
        result = self.calculate_technical_features(result)

        return result

    def calculate_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate trend filter features.

        Trend Filter (4H):
        - EMA20 and EMA50
        - Trend_Ratio = EMA20 / EMA50
        - Trend valid if Trend_Ratio > 1.01
        - Trend_Score = clamp((Trend_Ratio - 1.0) * 10, 0, 1)
        """
        result = df.copy()

        # Calculate EMAs
        result['ema_20'] = calculate_ema(result['close'], 20)
        result['ema_50'] = calculate_ema(result['close'], 50)

        # Trend ratio
        result['trend_ratio'] = result['ema_20'] / result['ema_50']

        # Trend valid (boolean)
        result['trend_valid'] = result['trend_ratio'] > 1.01

        # Trend score (0-1)
        result['trend_score'] = np.clip((result['trend_ratio'] - 1.0) * 10, 0, 1)

        return result

    def calculate_breakout_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate breakout features.

        Breakout Logic (24H HIGH):
        - Breakout_Level = highest close of last 24h (96 periods for 15m)
        - Breakout valid if: close > Breakout_Level AND (close - open)/open > 0.02 (2%)
        - Breakout_Score = clamp((close - Breakout_Level) / (0.05 * Breakout_Level), 0, 1)
        """
        result = df.copy()

        # Calculate 24h lookback (depends on timeframe)
        # For 15m: 24h = 96 periods
        # For 5m: 24h = 288 periods
        # For 1h: 24h = 24 periods
        periods_24h = 96  # Default for 15m

        # 24h highest close
        result['breakout_level'] = result['close'].rolling(window=periods_24h).max().shift(1)

        # Breakout valid conditions
        breakout_cond1 = result['close'] > result['breakout_level']
        breakout_cond2 = (result['close'] - result['open']) / result['open'] > 0.02

        result['breakout_valid'] = breakout_cond1 & breakout_cond2

        # Breakout score
        breakout_distance = (result['close'] - result['breakout_level']) / (0.05 * result['breakout_level'])
        result['breakout_score'] = np.clip(breakout_distance, 0, 1)

        # Track if we're above breakout level
        result['above_breakout'] = result['close'] > result['breakout_level']

        return result

    def calculate_pullback_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate pullback features.

        Pullback Logic (MICRO-PULLBACK):
        - First_High = highest high of breakout candle
        - Pullback_Low = lowest low before reclaim
        - Depth = (First_High - Pullback_Low) / (First_High - Breakout_Level)
        - Valid if 0.15 <= Depth <= 0.40
        - Pullback_Score = clamp(1 - abs(Depth - 0.25)/0.15, 0, 1)
        """
        result = df.copy()

        # Detect breakout candles
        breakout_candles = result['breakout_valid']

        # First high after breakout
        result['first_high'] = result['high'].copy()

        # Calculate pullback depth
        # This is complex for vectorized calculation, simplified approach:
        # Use rolling high since breakout and current low

        # Rolling high (since potential breakout)
        result['rolling_high'] = result['high'].rolling(window=10, min_periods=1).max()

        # Pullback depth calculation
        numerator = result['rolling_high'] - result['low']
        denominator = result['rolling_high'] - result['breakout_level']
        denominator = denominator.replace(0, np.nan)

        result['pullback_depth'] = numerator / denominator

        # Valid pullback depth (0.15 to 0.40)
        result['pullback_valid'] = (result['pullback_depth'] >= 0.15) & (result['pullback_depth'] <= 0.40)

        # Pullback score (optimal at 0.25)
        depth_deviation = np.abs(result['pullback_depth'] - 0.25) / 0.15
        result['pullback_score'] = np.clip(1 - depth_deviation, 0, 1)

        # Reclaim confirmation (close > breakout level after pullback)
        result['reclaim_valid'] = (result['close'] > result['breakout_level']) & result['pullback_valid']

        return result

    def calculate_rvol_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate relative volume features.

        RVOL = volume / median(volume over last 24h)
        Thresholds:
        - Bull: RVOL >= 2.0
        - Sideways: RVOL >= 3.0
        - Bear: RVOL >= 4.0
        RVOL_Score = clamp((RVOL - 1)/4, 0, 1)
        """
        result = df.copy()

        # 24h median volume (96 periods for 15m)
        periods_24h = 96
        result['volume_median_24h'] = result['volume'].rolling(window=periods_24h).median()

        # RVOL
        result['rvol'] = result['volume'] / result['volume_median_24h']
        result['rvol'] = result['rvol'].replace([np.inf, -np.inf], np.nan).fillna(1.0)

        # RVOL score (normalized)
        result['rvol_score'] = np.clip((result['rvol'] - 1) / 4, 0, 1)

        # RVOL thresholds for each regime
        result['rvol_bull_ok'] = result['rvol'] >= 2.0
        result['rvol_sideways_ok'] = result['rvol'] >= 3.0
        result['rvol_bear_ok'] = result['rvol'] >= 4.0

        return result

    def calculate_extension_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate extension filter (anti-blowoff).

        Extension Filter:
        - ATR14 (15m)
        - ATR_pct_24h = ATR14_mean_24h / close * 100
        - 24h_change = pct change in 24h closes
        - Reject if: 24h_change > 1.5 * ATR_pct_24h OR RSI_1h > 85
        """
        result = df.copy()

        # Calculate ATR
        result['atr_14'] = calculate_atr(result['high'], result['low'], result['close'], period=14)

        # 24h ATR mean
        periods_24h = 96
        result['atr_mean_24h'] = result['atr_14'].rolling(window=periods_24h).mean()

        # ATR as percentage of price
        result['atr_pct_24h'] = (result['atr_mean_24h'] / result['close']) * 100

        # 24h price change
        result['price_change_24h'] = result['close'].pct_change(periods_24h) * 100

        # Extension reject condition
        extension_cond1 = result['price_change_24h'] > (1.5 * result['atr_pct_24h'])

        # RSI for additional check (using current timeframe as proxy)
        result['rsi_14'] = calculate_rsi(result['close'], period=14)
        extension_cond2 = result['rsi_14'] > 85

        result['extension_reject'] = extension_cond1 | extension_cond2
        result['extension_ok'] = ~result['extension_reject']

        return result

    def calculate_exhaustion_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate local exhaustion kill-switch.

        Local Exhaustion Kill-Switch:
        - R_3d = close / close_3d_ago - 1
        - RANGE = (high - low) / ATR14
        - Reject entry if: R_3d > +0.50 AND RANGE > 2.5
        """
        result = df.copy()

        # 3-day return (for 15m: 3 days = 288 periods)
        periods_3d = 288  # 3 days * 24 hours * 4 (15m intervals)
        result['return_3d'] = result['close'].pct_change(periods_3d)

        # Range relative to ATR
        if 'atr_14' not in result.columns:
            result['atr_14'] = calculate_atr(result['high'], result['low'], result['close'], period=14)

        result['range_atr'] = (result['high'] - result['low']) / result['atr_14']
        result['range_atr'] = result['range_atr'].replace([np.inf, -np.inf], np.nan).fillna(0)

        # Exhaustion conditions
        exhaustion_cond1 = result['return_3d'] > 0.50
        exhaustion_cond2 = result['range_atr'] > 2.5

        result['exhaustion_reject'] = exhaustion_cond1 & exhaustion_cond2
        result['exhaustion_ok'] = ~result['exhaustion_reject']

        return result

    def calculate_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate momentum features for bonuses.

        Momentum Features:
        - RSI_Rank = 24h performance percentile (0-100)
        - Price momentum over various periods
        """
        result = df.copy()

        # RSI percentile rank (24h)
        if 'rsi_14' not in result.columns:
            result['rsi_14'] = calculate_rsi(result['close'], period=14)

        result['rsi_rank'] = calculate_percentile_rank(result['rsi_14'], window=96)

        # Price returns for momentum
        result['return_1h'] = result['close'].pct_change(4)  # 4 periods for 15m
        result['return_4h'] = result['close'].pct_change(16)  # 16 periods for 15m
        result['return_24h'] = result['close'].pct_change(96)  # 96 periods for 15m

        # Momentum score (24h percentile)
        result['momentum_score'] = calculate_percentile_rank(result['close'], window=96) / 100

        return result

    def calculate_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate additional technical features.
        """
        result = df.copy()

        # EMAs for various periods
        if 'ema_20' not in result.columns:
            result['ema_20'] = calculate_ema(result['close'], 20)

        result['ema_10'] = calculate_ema(result['close'], 10)
        result['ema_100'] = calculate_ema(result['close'], 100)

        # Price relative to EMAs
        result['price_vs_ema20'] = (result['close'] - result['ema_20']) / result['ema_20']
        result['price_vs_ema50'] = (result['close'] - result['ema_50']) / result['ema_50'] if 'ema_50' in result.columns else 0

        # Volume features
        result['volume_ma_20'] = result['volume'].rolling(window=20).mean()
        result['volume_ratio'] = result['volume'] / result['volume_ma_20']

        return result

    def calculate_orderbook_imbalance(
        self,
        bid_volumes: list,
        ask_volumes: list
    ) -> float:
        """
        Calculate orderbook imbalance from top levels.

        OB_imbalance = sum(bid_qty_top10) / sum(ask_qty_top10)
        Thresholds:
        - Bull/Sideways: >= 1.5
        - Bear: >= 2.0
        """
        if not bid_volumes or not ask_volumes:
            return 1.0

        total_bids = sum(bid_volumes[:10])
        total_asks = sum(ask_volumes[:10])

        if total_asks == 0:
            return 1.0

        imbalance = total_bids / total_asks
        return imbalance

    def calculate_ob_score(self, ob_imbalance: float) -> float:
        """
        Calculate orderbook imbalance score (0-1).

        OB_Score = clamp((OB_imbalance - 1)/1.5, 0, 1)
        """
        return np.clip((ob_imbalance - 1) / 1.5, 0, 1)

    def resample_to_higher_timeframe(
        self,
        df: pd.DataFrame,
        target_timeframe: str
    ) -> pd.DataFrame:
        """
        Resample data to higher timeframe (e.g., 15m -> 4h).

        Args:
            df: OHLCV DataFrame
            target_timeframe: Target timeframe ('1h', '4h', '1d')

        Returns:
            Resampled DataFrame
        """
        # Set timestamp as index
        df_indexed = df.set_index('timestamp')

        # Resample
        resampled = df_indexed.resample(target_timeframe).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })

        resampled = resampled.dropna()
        resampled = resampled.reset_index()

        return resampled

    def detect_entry_signals(
        self,
        df: pd.DataFrame,
        regime: str,
        rvol_threshold: float,
        ob_imbalance: float = 1.5,
        require_trend: bool = True
    ) -> pd.Series:
        """
        Detect valid entry signals based on all conditions.

        Args:
            df: DataFrame with all features
            regime: Current regime
            rvol_threshold: RVOL threshold for regime
            ob_imbalance: Orderbook imbalance value
            require_trend: Whether trend is required

        Returns:
            Boolean series indicating valid entries
        """
        # All conditions must be True
        conditions = pd.Series(True, index=df.index)

        # 1. Trend valid (if required)
        if require_trend:
            conditions &= df['trend_valid']

        # 2. RVOL threshold
        conditions &= df['rvol'] >= rvol_threshold

        # 3. Pullback valid
        conditions &= df['pullback_valid']

        # 4. Reclaim valid
        conditions &= df['reclaim_valid']

        # 5. Extension OK
        conditions &= df['extension_ok']

        # 6. Exhaustion OK
        conditions &= df['exhaustion_ok']

        # 7. Orderbook imbalance (single value, not vectorized)
        # This would be checked per-signal in live trading

        return conditions
