"""
Technical indicators and calculations for Alpha Sniper V3.2
"""
import numpy as np
import pandas as pd
from typing import Optional, Tuple


def ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)

    return true_range.rolling(window=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))


def compute_rvol(volume: pd.Series, window: int = 96) -> pd.Series:
    """
    Relative Volume

    For 15m bars, window=96 means last 24 hours
    RVOL = current_volume / median(volume_last_N_bars)
    """
    median_vol = volume.rolling(window=window).median()
    return volume / median_vol.replace(0, 1)


def compute_z_score(returns: pd.Series, short_window: int = 21, long_window: int = 180) -> float:
    """
    Z-score of returns for regime detection

    Z = (sum_short - mean_long) / std_long
    """
    if len(returns) < long_window:
        return 0.0

    sum_short = returns.tail(short_window).sum()
    mean_long = returns.tail(long_window).mean() * short_window  # Scaled mean
    std_long = returns.tail(long_window).std() * np.sqrt(short_window)  # Scaled std

    if std_long == 0:
        return 0.0

    return (sum_short - mean_long) / std_long


def compute_realized_volatility(returns: pd.Series, window: int = 30) -> float:
    """Realized volatility (annualized)"""
    if len(returns) < window:
        return 0.0

    # Daily volatility * sqrt(365) for annualization
    daily_std = returns.tail(window).std()
    return daily_std * np.sqrt(365)


def percentile_rank(value: float, series: pd.Series) -> float:
    """
    Percentile rank of a value in a series [0-100]
    """
    if len(series) == 0:
        return 50.0

    rank = (series < value).sum() / len(series) * 100
    return rank


def swing_low(low: pd.Series, lookback: int = 20) -> float:
    """Find recent swing low"""
    if len(low) < lookback:
        return low.min()

    return low.tail(lookback).min()


def swing_high(high: pd.Series, lookback: int = 20) -> float:
    """Find recent swing high"""
    if len(high) < lookback:
        return high.max()

    return high.tail(lookback).max()


def position_in_range(close: float, high_24h: float, low_24h: float) -> float:
    """
    Where is current price in 24h range [0-1]

    0 = at low
    1 = at high
    0.5 = middle
    """
    if high_24h == low_24h:
        return 0.5

    return (close - low_24h) / (high_24h - low_24h)


def detect_compression(atr_current: float, atr_24h_median: float) -> float:
    """
    Volatility compression ratio

    < 1.0 = compressing (coiling)
    > 1.0 = expanding
    """
    if atr_24h_median == 0:
        return 1.0

    return atr_current / atr_24h_median


def moving_percentile(series: pd.Series, window: int, percentile: int = 80) -> pd.Series:
    """Calculate rolling percentile"""
    return series.rolling(window=window).quantile(percentile / 100)


def normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize value to [0, 1] range"""
    if max_val == min_val:
        return 0.5

    normalized = (value - min_val) / (max_val - min_val)
    return np.clip(normalized, 0.0, 1.0)


def exponential_decay(base_value: float, time_elapsed: float, half_life: float) -> float:
    """
    Exponential decay function

    Used for: cooldown periods, regime confidence decay, etc.
    """
    decay_rate = np.log(2) / half_life
    return base_value * np.exp(-decay_rate * time_elapsed)
