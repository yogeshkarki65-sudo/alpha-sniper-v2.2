"""
Technical indicator calculations using vectorized numpy/pandas operations.
All functions designed for backtesting with full historical data.
"""

import pandas as pd
import numpy as np
from typing import Union, Tuple


def calculate_returns(prices: pd.Series, periods: int = 1) -> pd.Series:
    """
    Calculate simple returns over specified periods.

    Args:
        prices: Price series
        periods: Number of periods for return calculation

    Returns:
        Series of returns
    """
    return prices.pct_change(periods)


def calculate_log_returns(prices: pd.Series, periods: int = 1) -> pd.Series:
    """
    Calculate log returns over specified periods.

    Args:
        prices: Price series
        periods: Number of periods

    Returns:
        Series of log returns
    """
    return np.log(prices / prices.shift(periods))


def calculate_rolling_zscore(
    series: pd.Series,
    window: int,
    min_periods: int = None
) -> pd.Series:
    """
    Calculate rolling Z-score.

    Args:
        series: Input series
        window: Rolling window size
        min_periods: Minimum periods required

    Returns:
        Z-score series
    """
    if min_periods is None:
        min_periods = window

    rolling_mean = series.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = series.rolling(window=window, min_periods=min_periods).std()

    zscore = (series - rolling_mean) / rolling_std
    return zscore


def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """
    Calculate Simple Moving Average.

    Args:
        prices: Price series
        period: SMA period

    Returns:
        SMA series
    """
    return prices.rolling(window=period).mean()


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average.

    Args:
        prices: Price series
        period: EMA period

    Returns:
        EMA series
    """
    return prices.ewm(span=period, adjust=False).mean()


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index.

    Args:
        prices: Price series
        period: RSI period (default 14)

    Returns:
        RSI series (0-100)
    """
    delta = prices.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Subsequent periods use EMA
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """
    Calculate Average True Range.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period (default 14)

    Returns:
        ATR series
    """
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())

    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()

    return atr


def calculate_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """
    Calculate Average Directional Index.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ADX period (default 14)

    Returns:
        ADX series (0-100)
    """
    # Calculate True Range
    tr = pd.DataFrame({
        'hl': high - low,
        'hc': np.abs(high - close.shift()),
        'lc': np.abs(low - close.shift())
    }).max(axis=1)

    # Calculate Directional Movement
    high_diff = high.diff()
    low_diff = -low.diff()

    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0.0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0.0)

    # Smooth the TR and DM
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

    # Calculate DX and ADX
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()

    return adx


def calculate_bollinger_bands(
    prices: pd.Series,
    period: int = 20,
    std_dev: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.

    Args:
        prices: Price series
        period: Period for moving average
        std_dev: Number of standard deviations

    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()

    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    return upper, middle, lower


def calculate_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Args:
        prices: Price series
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period

    Returns:
        Tuple of (macd_line, signal_line, histogram)
    """
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)

    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calculate_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3
) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate Stochastic Oscillator.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: Lookback period
        smooth_k: %K smoothing
        smooth_d: %D smoothing

    Returns:
        Tuple of (%K, %D)
    """
    lowest_low = low.rolling(window=period).min()
    highest_high = high.rolling(window=period).max()

    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    k = k.rolling(window=smooth_k).mean()
    d = k.rolling(window=smooth_d).mean()

    return k, d


def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Calculate On-Balance Volume.

    Args:
        close: Close prices
        volume: Volume series

    Returns:
        OBV series
    """
    obv = pd.Series(index=close.index, dtype=float)
    obv.iloc[0] = volume.iloc[0]

    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i - 1]:
            obv.iloc[i] = obv.iloc[i - 1] + volume.iloc[i]
        elif close.iloc[i] < close.iloc[i - 1]:
            obv.iloc[i] = obv.iloc[i - 1] - volume.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i - 1]

    return obv


def calculate_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series
) -> pd.Series:
    """
    Calculate Volume Weighted Average Price.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        volume: Volume series

    Returns:
        VWAP series
    """
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).cumsum() / volume.cumsum()

    return vwap


def calculate_percentile_rank(series: pd.Series, window: int) -> pd.Series:
    """
    Calculate rolling percentile rank (0-100).

    Args:
        series: Input series
        window: Rolling window

    Returns:
        Percentile rank series
    """
    def percentile_rank(x):
        if len(x) < 2:
            return 50.0
        return (x.iloc[-1] > x.iloc[:-1]).sum() / (len(x) - 1) * 100

    return series.rolling(window=window).apply(percentile_rank, raw=False)


def calculate_hurst_exponent(series: pd.Series, window: int = 100) -> pd.Series:
    """
    Calculate rolling Hurst exponent (mean reversion indicator).
    H < 0.5: Mean reverting
    H = 0.5: Random walk
    H > 0.5: Trending

    Args:
        series: Price series
        window: Rolling window

    Returns:
        Hurst exponent series
    """
    def hurst(ts):
        if len(ts) < 20:
            return 0.5

        lags = range(2, min(20, len(ts) // 2))
        tau = [np.std(np.subtract(ts[lag:], ts[:-lag])) for lag in lags]

        # Filter out zeros
        valid_idx = [i for i, t in enumerate(tau) if t > 0]
        if len(valid_idx) < 2:
            return 0.5

        lags_valid = [lags[i] for i in valid_idx]
        tau_valid = [tau[i] for i in valid_idx]

        poly = np.polyfit(np.log(lags_valid), np.log(tau_valid), 1)
        return poly[0] * 2.0

    return series.rolling(window=window).apply(hurst, raw=False)


def calculate_momentum(prices: pd.Series, period: int) -> pd.Series:
    """
    Calculate price momentum (rate of change).

    Args:
        prices: Price series
        period: Lookback period

    Returns:
        Momentum series (percentage change)
    """
    return prices.pct_change(period) * 100


def calculate_williams_r(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """
    Calculate Williams %R.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: Lookback period

    Returns:
        Williams %R series (-100 to 0)
    """
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()

    wr = -100 * (highest_high - close) / (highest_high - lowest_low)

    return wr
