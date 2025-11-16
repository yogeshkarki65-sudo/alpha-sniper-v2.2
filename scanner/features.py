"""
Alpha Sniper v4.1 Feature Computation
Multi-timeframe indicators: RSI, EMA, returns, volume ratios
"""
from typing import List, Dict, Optional, Tuple
import numpy as np
from config.logging_config import logger
from scanner.mexc_client import mexc_client


def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """
    Calculate RSI (Relative Strength Index)
    Args:
        prices: List of closing prices
        period: RSI period (default 14)
    Returns: RSI value (0-100)
    """
    if len(prices) < period + 1:
        return 50.0  # Neutral default

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_ema(prices: List[float], period: int) -> float:
    """
    Calculate EMA (Exponential Moving Average)
    Args:
        prices: List of closing prices
        period: EMA period
    Returns: Current EMA value
    """
    if len(prices) < period:
        return np.mean(prices)  # Fallback to SMA

    prices_array = np.array(prices)
    multiplier = 2 / (period + 1)
    ema = np.mean(prices_array[:period])  # Start with SMA

    for price in prices_array[period:]:
        ema = (price * multiplier) + (ema * (1 - multiplier))

    return ema


def compute_returns(klines: List[List], periods_back: int = 1) -> float:
    """
    Calculate percentage return over N periods
    Args:
        klines: Kline data [[timestamp, o, h, l, c, v, ...], ...]
        periods_back: Number of periods to look back
    Returns: Percentage return
    """
    if len(klines) < periods_back + 1:
        return 0.0

    current_close = float(klines[-1][4])
    past_close = float(klines[-periods_back - 1][4])

    if past_close == 0:
        return 0.0

    ret_pct = ((current_close - past_close) / past_close) * 100
    return ret_pct


def compute_rvol(klines: List[List], current_volume: float, lookback: int = 20) -> float:
    """
    Calculate relative volume (current vs average)
    Args:
        klines: Historical kline data
        current_volume: Current period volume
        lookback: Periods to average (default 20)
    Returns: RVOL ratio
    """
    if len(klines) < lookback:
        return 1.0

    volumes = [float(k[5]) for k in klines[-lookback:]]
    avg_volume = np.mean(volumes)

    if avg_volume == 0:
        return 1.0

    rvol = current_volume / avg_volume
    return rvol


def get_symbol_features(
    symbol: str,
    ticker: Dict,
    use_orderbook: bool = False
) -> Optional[Dict]:
    """
    Compute all features for a symbol
    Args:
        symbol: Trading pair
        ticker: 24h ticker data
        use_orderbook: Whether to fetch orderbook imbalance
    Returns: Feature dict or None if error
    """
    try:
        # === BASIC DATA FROM TICKER ===
        last_price = float(ticker.get('lastPrice', 0) or 0)
        quote_volume_24h = float(ticker.get('quoteVolume', 0) or 0)
        high_24h = float(ticker.get('highPrice', 1) or 1)
        low_24h = float(ticker.get('lowPrice', 1) or 1)
        current_volume = float(ticker.get('volume', 0) or 0)

        if last_price == 0:
            return None

        # === FETCH KLINES FOR MULTI-TIMEFRAME DATA ===
        klines_1h = mexc_client.get_klines(symbol, '1h', limit=100)
        klines_4h = mexc_client.get_klines(symbol, '4h', limit=100)
        klines_1d = mexc_client.get_klines(symbol, '1d', limit=100)

        if not klines_1h or not klines_4h or not klines_1d:
            logger.debug(f"Incomplete kline data for {symbol}")
            return None

        # === RETURNS ===
        ret_1h_pct = compute_returns(klines_1h, periods_back=1)
        ret_4h_pct = compute_returns(klines_4h, periods_back=1)
        ret_24h_pct = compute_returns(klines_1d, periods_back=1)

        # === VOLUME ===
        rvol_1h = compute_rvol(klines_1h, current_volume, lookback=20)

        # === RSI ===
        prices_1h = [float(k[4]) for k in klines_1h]
        rsi_1h = calculate_rsi(prices_1h, period=14)

        # === EMA (50-period) ===
        ema_1h_50 = calculate_ema(prices_1h, period=50)

        prices_4h = [float(k[4]) for k in klines_4h]
        ema_4h_50 = calculate_ema(prices_4h, period=50)

        prices_1d = [float(k[4]) for k in klines_1d]
        ema_24h_50 = calculate_ema(prices_1d, period=50)

        above_ma_1h_50 = last_price > ema_1h_50
        above_ma_4h_50 = last_price > ema_4h_50
        above_ma_24h_50 = last_price > ema_24h_50

        # === MARKET STRUCTURE ===
        price_range = high_24h - low_24h
        if price_range > 0:
            range_pos_24h = (last_price - low_24h) / price_range
        else:
            range_pos_24h = 0.5

        # === PULLBACK CHECK (v4.1.1) ===
        # Check if current price is at/above recent highs (bad - buying breakout tops)
        # Good entries are pullbacks from recent highs
        is_pullback = True
        if config.PREFER_PULLBACKS and len(klines_1h) >= 3:
            # Get the high prices of the last 2 completed candles
            high_last_2 = max(float(klines_1h[-2][2]), float(klines_1h[-3][2]))
            # If current price is >= recent high, it's a breakout (not a pullback)
            if last_price >= high_last_2:
                is_pullback = False

        # === SPREAD (in bps) ===
        spread_bps = 0.0  # Computed separately in scanner

        # === ORDERBOOK IMBALANCE (optional) ===
        orderbook_imbalance = 0.0
        if use_orderbook:
            from scanner.orderbook import get_orderbook_imbalance
            orderbook_imbalance = get_orderbook_imbalance(symbol)

        return {
            'symbol': symbol,
            'last_price': last_price,
            'quote_volume_24h': quote_volume_24h,
            'ret_1h_pct': ret_1h_pct,
            'ret_4h_pct': ret_4h_pct,
            'ret_24h_pct': ret_24h_pct,
            'rvol_1h': rvol_1h,
            'rsi_1h': rsi_1h,
            'above_ma_1h_50': above_ma_1h_50,
            'above_ma_4h_50': above_ma_4h_50,
            'above_ma_24h_50': above_ma_24h_50,
            'range_pos_24h': range_pos_24h,
            'spread_bps': spread_bps,
            'orderbook_imbalance': orderbook_imbalance,
            'is_pullback': is_pullback,
        }

    except Exception as e:
        logger.warning(f"Error computing features for {symbol}: {e}")
        return None
