"""
Breakout Detection - Layer 2 of Intelligent Entry v6.0
Detects breakout + retest: price > 4h high AND current candle retesting breakout level
"""
import requests
from config.config import config


def get_klines(symbol, interval='4h', limit=50):
    """Fetch candlestick data from MEXC"""
    try:
        url = f"{config.MEXC_BASE_URL}/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        return data
    except Exception as e:
        print(f"[breakout_detector] Error fetching klines for {symbol}: {e}")
        return []


def detect_breakout_retest(symbol, retest_tolerance_pct=0.5):
    """
    Detect breakout + retest:
    - Current price > 4h high (from last 50 candles, excluding current)
    - Current candle low within retest_tolerance_pct of breakout level

    Returns: (is_breakout_retest: bool, breakout_level: float, current_price: float)
    """
    klines = get_klines(symbol, interval='4h', limit=50)
    if len(klines) < 10:
        return False, 0.0, 0.0

    # Get historical 4h high (exclude most recent candle)
    historical_candles = klines[:-1]
    high_4h = max(float(k[2]) for k in historical_candles)  # k[2] = high

    # Current candle data
    current_candle = klines[-1]
    current_close = float(current_candle[4])  # k[4] = close
    current_low = float(current_candle[3])    # k[3] = low
    current_high = float(current_candle[2])   # k[2] = high

    # Check if we broke above 4h high
    is_breakout = current_high > high_4h

    # Check if current low is retesting the breakout level
    retest_level = high_4h
    retest_distance_pct = abs(current_low - retest_level) / retest_level * 100
    is_retesting = retest_distance_pct <= retest_tolerance_pct

    is_breakout_retest = is_breakout and is_retesting

    return is_breakout_retest, high_4h, current_close


def detect_simple_breakout(symbol):
    """
    Simplified breakout detection: just check if price > 4h high

    Returns: (is_breakout: bool, high_4h: float, current_price: float)
    """
    klines = get_klines(symbol, interval='4h', limit=50)
    if len(klines) < 10:
        return False, 0.0, 0.0

    historical_candles = klines[:-1]
    high_4h = max(float(k[2]) for k in historical_candles)

    current_candle = klines[-1]
    current_close = float(current_candle[4])

    is_breakout = current_close > high_4h

    return is_breakout, high_4h, current_close


if __name__ == "__main__":
    # Test
    symbol = "BTCUSDT"
    is_br, level, price = detect_breakout_retest(symbol)
    print(f"{symbol}: Breakout+Retest={is_br}, Level={level:.2f}, Price={price:.2f}")
