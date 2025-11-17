"""
Orderbook Momentum Detection - Layer 3 of Intelligent Entry v6.0
Detects buying pressure: 5min bid volume >= 2.5x ask volume
"""
import requests
import time
from config.config import config


def get_orderbook_depth(symbol, limit=100):
    """Fetch orderbook depth from MEXC"""
    try:
        url = f"{config.MEXC_BASE_URL}/api/v3/depth"
        params = {'symbol': symbol, 'limit': limit}
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        return data
    except Exception as e:
        print(f"[orderbook_momentum] Error fetching depth for {symbol}: {e}")
        return None


def get_recent_trades(symbol, limit=500):
    """Fetch recent trades from MEXC"""
    try:
        url = f"{config.MEXC_BASE_URL}/api/v3/trades"
        params = {'symbol': symbol, 'limit': limit}
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        return data
    except Exception as e:
        print(f"[orderbook_momentum] Error fetching trades for {symbol}: {e}")
        return []


def detect_orderbook_momentum(symbol, min_bid_ask_ratio=2.5, time_window_sec=300):
    """
    Detect orderbook momentum:
    - Calculate bid vs ask volume from recent trades (last 5 minutes)
    - Bid volume >= min_bid_ask_ratio * ask volume

    Returns: (has_momentum: bool, bid_ask_ratio: float, bid_volume: float, ask_volume: float)
    """
    trades = get_recent_trades(symbol, limit=1000)
    if not trades:
        return False, 0.0, 0.0, 0.0

    current_time = time.time()
    cutoff_time = (current_time - time_window_sec) * 1000  # Convert to milliseconds

    bid_volume = 0.0  # Buyers (buy orders)
    ask_volume = 0.0  # Sellers (sell orders)

    for trade in trades:
        trade_time = int(trade['time'])
        if trade_time < cutoff_time:
            continue

        qty = float(trade['qty'])
        is_buyer_maker = trade.get('isBuyerMaker', False)

        # If buyer is maker, it's a sell order hitting the bid
        # If seller is maker, it's a buy order hitting the ask
        if is_buyer_maker:
            ask_volume += qty  # Sell pressure
        else:
            bid_volume += qty  # Buy pressure

    if ask_volume == 0:
        bid_ask_ratio = bid_volume if bid_volume > 0 else 0.0
    else:
        bid_ask_ratio = bid_volume / ask_volume

    has_momentum = bid_ask_ratio >= min_bid_ask_ratio

    return has_momentum, bid_ask_ratio, bid_volume, ask_volume


def get_orderbook_imbalance_snapshot(symbol):
    """
    Alternative: snapshot orderbook imbalance

    Returns: (bid_volume: float, ask_volume: float, imbalance: float)
    """
    depth = get_orderbook_depth(symbol, limit=100)
    if not depth:
        return 0.0, 0.0, 0.0

    bid_volume = sum(float(bid[1]) for bid in depth.get('bids', []))
    ask_volume = sum(float(ask[1]) for ask in depth.get('asks', []))

    if bid_volume + ask_volume == 0:
        return bid_volume, ask_volume, 0.0

    imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)

    return bid_volume, ask_volume, imbalance


if __name__ == "__main__":
    # Test
    symbol = "BTCUSDT"
    has_mom, ratio, bid_vol, ask_vol = detect_orderbook_momentum(symbol)
    print(f"{symbol}: Momentum={has_mom}, Ratio={ratio:.2f}, Bid={bid_vol:.2f}, Ask={ask_vol:.2f}")
