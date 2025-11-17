"""
Volume Trend Detection - Layer 1 of Intelligent Entry v6.0
Detects RVOL explosion: rising RVOL streak + current RVOL >= threshold
"""
import requests
from config.config import config


def get_klines(symbol, interval='5m', limit=10):
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
        print(f"[volume_trend] Error fetching klines for {symbol}: {e}")
        return []


def calculate_rvol(volume, avg_volume):
    """Calculate relative volume"""
    if avg_volume == 0:
        return 0.0
    return volume / avg_volume


def detect_volume_explosion(symbol, min_rvol_streak=3, min_rvol_explosion=6.0):
    """
    Detect volume explosion:
    - RVOL rising for last N candles
    - Current RVOL >= threshold

    Returns: (is_explosion: bool, current_rvol: float, streak_length: int)
    """
    klines = get_klines(symbol, interval='5m', limit=10)
    if len(klines) < min_rvol_streak + 1:
        return False, 0.0, 0

    # Calculate avg volume from older candles
    older_candles = klines[:-min_rvol_streak]
    if not older_candles:
        return False, 0.0, 0

    avg_volume = sum(float(k[5]) for k in older_candles) / len(older_candles)
    if avg_volume == 0:
        return False, 0.0, 0

    # Calculate RVOL for recent candles
    recent_candles = klines[-min_rvol_streak:]
    rvols = [calculate_rvol(float(k[5]), avg_volume) for k in recent_candles]

    # Check if RVOL is rising
    is_rising = all(rvols[i] < rvols[i+1] for i in range(len(rvols)-1))
    current_rvol = rvols[-1]

    # Volume explosion detected if:
    # 1. RVOL rising streak
    # 2. Current RVOL >= threshold
    is_explosion = is_rising and current_rvol >= min_rvol_explosion

    streak_length = len(rvols) if is_rising else 0

    return is_explosion, current_rvol, streak_length


if __name__ == "__main__":
    # Test
    symbol = "BTCUSDT"
    is_exp, rvol, streak = detect_volume_explosion(symbol)
    print(f"{symbol}: Explosion={is_exp}, RVOL={rvol:.2f}, Streak={streak}")
