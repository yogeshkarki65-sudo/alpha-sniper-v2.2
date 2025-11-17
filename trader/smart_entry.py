"""
Smart Entry (Micro-Pullback) - Layer 4 of Intelligent Entry v6.0
Waits for 0.6-1.8% dip after breakout, then enters with limit order at dip + 0.2%
"""
import requests
from config.config import config


def get_current_price(symbol):
    """Fetch current price from MEXC"""
    try:
        url = f"{config.MEXC_BASE_URL}/api/v3/ticker/price"
        params = {'symbol': symbol}
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        return float(data['price'])
    except Exception as e:
        print(f"[smart_entry] Error fetching price for {symbol}: {e}")
        return None


def get_recent_high(symbol, lookback_candles=12):
    """Get recent high from 5min candles"""
    try:
        url = f"{config.MEXC_BASE_URL}/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': '5m',
            'limit': lookback_candles
        }
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        klines = resp.json()

        if not klines:
            return None

        recent_high = max(float(k[2]) for k in klines)  # k[2] = high
        return recent_high
    except Exception as e:
        print(f"[smart_entry] Error fetching recent high for {symbol}: {e}")
        return None


def detect_micro_pullback(symbol, pullback_min_pct=0.6, pullback_max_pct=1.8, entry_offset_pct=0.2):
    """
    Detect micro-pullback from recent high:
    - Calculate % pullback from recent high
    - If pullback is within min/max range, calculate optimal entry price

    Returns: (is_pullback: bool, entry_price: float, recent_high: float, pullback_pct: float)
    """
    recent_high = get_recent_high(symbol, lookback_candles=12)
    if recent_high is None:
        return False, 0.0, 0.0, 0.0

    current_price = get_current_price(symbol)
    if current_price is None:
        return False, 0.0, recent_high, 0.0

    # Calculate pullback percentage
    pullback_pct = ((recent_high - current_price) / recent_high) * 100

    # Check if pullback is within desired range
    is_pullback = pullback_min_pct <= pullback_pct <= pullback_max_pct

    # Calculate entry price: current price + offset
    entry_price = current_price * (1 + entry_offset_pct / 100)

    return is_pullback, entry_price, recent_high, pullback_pct


def calculate_smart_entry_price(symbol, breakout_level, pullback_min_pct=0.6, pullback_max_pct=1.8):
    """
    Calculate smart entry price based on micro-pullback from breakout level

    Returns: (should_enter: bool, entry_price: float, current_price: float, pullback_pct: float)
    """
    current_price = get_current_price(symbol)
    if current_price is None:
        return False, 0.0, 0.0, 0.0

    # Calculate pullback from breakout level
    pullback_pct = ((breakout_level - current_price) / breakout_level) * 100

    # Only enter if pullback is within range
    should_enter = pullback_min_pct <= pullback_pct <= pullback_max_pct

    # Entry at current price (market order in this simplified version)
    entry_price = current_price

    return should_enter, entry_price, current_price, pullback_pct


def check_entry_timing(symbol, intelligence_score, min_score_with_bonus=80):
    """
    Check if timing is right to enter based on intelligence score

    Returns: (should_enter: bool, entry_type: str)
    """
    if intelligence_score < min_score_with_bonus:
        return False, "score_too_low"

    # Check micro-pullback
    is_pullback, entry_price, recent_high, pullback_pct = detect_micro_pullback(symbol)

    if is_pullback:
        return True, "micro_pullback"

    # If no pullback but score is very high, allow market entry
    if intelligence_score >= 95:
        return True, "market_entry_high_score"

    return False, "waiting_for_pullback"


if __name__ == "__main__":
    # Test
    symbol = "BTCUSDT"
    is_pb, entry, high, pb_pct = detect_micro_pullback(symbol)
    print(f"{symbol}: Pullback={is_pb}, Entry=${entry:.2f}, High=${high:.2f}, PB%={pb_pct:.2f}%")
