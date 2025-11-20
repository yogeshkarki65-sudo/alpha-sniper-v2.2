#!/usr/bin/env python3
"""
Feature Extractor - Extract technical features from OHLCV data

BUG FIX: Proper error handling for kline fetching (BUG B)
- Individual symbol failures no longer cancel entire batch
- Per-symbol error logging
- Graceful degradation
"""

import numpy as np
from typing import Optional, Dict, List
from dataclasses import dataclass

from v3.data.mexc_client import mexc_client


@dataclass
class Features:
    """Container for extracted features."""
    symbol: str
    close: float
    volume_24h: float

    # Returns
    return_1h: float
    return_4h: float
    return_24h: float
    return_3d: float
    return_7d: float
    return_14d: float

    # Trend
    ema20_1h: float
    ema50_1h: float
    ema20_4h: float
    ema50_4h: float
    trend_ratio_4h: float

    # Volatility
    atr_15m: float
    atr_1h: float
    volatility_24h: float

    # Volume
    rvol: float  # Relative volume

    # Liquidity
    spread_pct: float
    depth_10: float  # Orderbook depth at 10 levels

    # Structure
    price_pos_24h: float  # Price position in 24h range (0-1)
    high_24h: float
    low_24h: float

    # Raw data (for additional calculations)
    bars_15m: Optional[List[Dict]] = None
    bars_1h: Optional[List[Dict]] = None
    bars_4h: Optional[List[Dict]] = None

    # Additional context
    equity: float = 500  # Current equity for position sizing
    btc_return_14d: float = 0  # BTC 14d return for RS calculation


def extract_features(
    symbol: str,
    equity: float = 500,
    btc_return_14d: float = 0
) -> Optional[Features]:
    """
    Extract all features for a symbol.

    BUG FIX (BUG B): Robust error handling - individual failures don't crash entire batch.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        equity: Current account equity
        btc_return_14d: BTC 14-day return for relative strength

    Returns:
        Features object or None if extraction fails
    """
    try:
        # Fetch OHLCV data for multiple timeframes
        bars_15m = _fetch_klines(symbol, "15m", 100)
        bars_1h = _fetch_klines(symbol, "1h", 168)  # 1 week
        bars_4h = _fetch_klines(symbol, "4h", 168)  # 4 weeks

        # BUG FIX: Check if we have minimum required data
        if bars_15m is None or len(bars_15m) < 20:
            print(f"[Features] {symbol}: Insufficient 15m data ({len(bars_15m) if bars_15m is not None else 0} bars)")
            return None

        if bars_1h is None or len(bars_1h) < 50:
            print(f"[Features] {symbol}: Insufficient 1h data ({len(bars_1h) if bars_1h is not None else 0} bars)")
            return None

        if bars_4h is None or len(bars_4h) < 50:
            print(f"[Features] {symbol}: Insufficient 4h data ({len(bars_4h) if bars_4h is not None else 0} bars)")
            return None

        # Get current price and 24h stats
        ticker = mexc_client.get_ticker_24h(symbol)
        if ticker is None:
            print(f"[Features] {symbol}: Failed to fetch ticker")
            return None

        close = float(ticker.get('lastPrice', 0))
        volume_24h = float(ticker.get('quoteVolume', 0))
        high_24h = float(ticker.get('highPrice', close))
        low_24h = float(ticker.get('lowPrice', close))

        if close == 0:
            print(f"[Features] {symbol}: Invalid price (0)")
            return None

        # Calculate returns
        return_1h = _calculate_return(bars_1h, periods=1)
        return_4h = _calculate_return(bars_4h, periods=1)
        return_24h = _calculate_return(bars_1h, periods=24)
        return_3d = _calculate_return(bars_1h, periods=72)
        return_7d = _calculate_return(bars_1h, periods=168)
        return_14d = _calculate_return(bars_4h, periods=84)

        # Calculate EMAs
        ema20_1h = _calculate_ema(bars_1h, period=20)
        ema50_1h = _calculate_ema(bars_1h, period=50)
        ema20_4h = _calculate_ema(bars_4h, period=20)
        ema50_4h = _calculate_ema(bars_4h, period=50)

        # Trend ratio
        trend_ratio_4h = ema20_4h / ema50_4h if ema50_4h > 0 else 1.0

        # Volatility
        atr_15m = _calculate_atr(bars_15m, period=14)
        atr_1h = _calculate_atr(bars_1h, period=14)
        volatility_24h = _calculate_volatility(bars_1h, periods=24)

        # Relative volume
        avg_volume = np.mean([b['volume'] for b in bars_1h[-24:]])
        current_volume = bars_1h[-1]['volume']
        rvol = current_volume / avg_volume if avg_volume > 0 else 1.0

        # Liquidity metrics
        orderbook = mexc_client.get_orderbook(symbol, limit=10)
        if orderbook:
            spread_pct, depth_10 = _calculate_liquidity(orderbook, close)
        else:
            spread_pct = 999  # Invalid spread (will fail filters)
            depth_10 = 0

        # Price position in 24h range
        if high_24h > low_24h:
            price_pos_24h = (close - low_24h) / (high_24h - low_24h)
        else:
            price_pos_24h = 0.5

        # Build Features object
        features = Features(
            symbol=symbol,
            close=close,
            volume_24h=volume_24h,
            return_1h=return_1h,
            return_4h=return_4h,
            return_24h=return_24h,
            return_3d=return_3d,
            return_7d=return_7d,
            return_14d=return_14d,
            ema20_1h=ema20_1h,
            ema50_1h=ema50_1h,
            ema20_4h=ema20_4h,
            ema50_4h=ema50_4h,
            trend_ratio_4h=trend_ratio_4h,
            atr_15m=atr_15m,
            atr_1h=atr_1h,
            volatility_24h=volatility_24h,
            rvol=rvol,
            spread_pct=spread_pct,
            depth_10=depth_10,
            price_pos_24h=price_pos_24h,
            high_24h=high_24h,
            low_24h=low_24h,
            bars_15m=bars_15m,
            bars_1h=bars_1h,
            bars_4h=bars_4h,
            equity=equity,
            btc_return_14d=btc_return_14d
        )

        return features

    except Exception as e:
        # BUG FIX: Catch-all for unexpected errors
        print(f"[Features] {symbol}: Unexpected error during feature extraction: {e}")
        return None


def _fetch_klines(symbol: str, interval: str, limit: int) -> Optional[List[Dict]]:
    """
    Fetch klines with proper error handling.

    BUG FIX (BUG B): Graceful error handling per symbol/timeframe.
    """
    try:
        bars = mexc_client.get_klines(symbol, interval=interval, limit=limit)

        if bars is None or len(bars) == 0:
            print(f"[Features] {symbol}: No {interval} klines returned")
            return None

        return bars

    except Exception as e:
        print(f"[Features] {symbol}: Failed to fetch {interval} klines: {e}")
        return None


def _calculate_return(bars: List[Dict], periods: int) -> float:
    """Calculate percentage return over N periods."""
    if len(bars) < periods + 1:
        return 0

    close_now = bars[-1]['close']
    close_then = bars[-(periods + 1)]['close']

    if close_then == 0:
        return 0

    return (close_now / close_then - 1)


def _calculate_ema(bars: List[Dict], period: int) -> float:
    """Calculate Exponential Moving Average."""
    if len(bars) < period:
        return bars[-1]['close'] if bars else 0

    closes = [b['close'] for b in bars[-period*2:]]

    multiplier = 2 / (period + 1)
    ema = sum(closes[:period]) / period  # SMA for first value

    for close in closes[period:]:
        ema = (close - ema) * multiplier + ema

    return ema


def _calculate_atr(bars: List[Dict], period: int = 14) -> float:
    """Calculate Average True Range."""
    if len(bars) < period + 1:
        return 0

    trs = []
    for i in range(1, len(bars)):
        high = bars[i]['high']
        low = bars[i]['low']
        prev_close = bars[i-1]['close']

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        trs.append(tr)

    if len(trs) < period:
        return 0

    return np.mean(trs[-period:])


def _calculate_volatility(bars: List[Dict], periods: int) -> float:
    """Calculate volatility (std dev of returns)."""
    if len(bars) < periods + 1:
        return 0

    returns = []
    for i in range(-periods, 0):
        if bars[i-1]['close'] == 0:
            continue
        ret = bars[i]['close'] / bars[i-1]['close'] - 1
        returns.append(ret)

    if not returns:
        return 0

    return np.std(returns)


def _calculate_liquidity(orderbook: Dict, price: float) -> tuple:
    """
    Calculate spread and depth metrics.

    Returns:
        (spread_pct, depth_10): Spread percentage and total depth in USD
    """
    bids = orderbook.get('bids', [])
    asks = orderbook.get('asks', [])

    if not bids or not asks:
        return (999, 0)

    best_bid = bids[0][0]
    best_ask = asks[0][0]

    # Spread percentage
    spread_pct = (best_ask - best_bid) / best_bid * 100

    # Depth at 10 levels (total USD value)
    bid_depth = sum(p * q for p, q in bids[:10])
    ask_depth = sum(p * q for p, q in asks[:10])
    depth_10 = (bid_depth + ask_depth) / 2

    return (spread_pct, depth_10)
