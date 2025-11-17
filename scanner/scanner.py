import requests
import time
from config.config import config
from database.models import db
from scanner.orderbook import get_orderbook_imbalance, get_spread_pct
from scanner.scorer import calculate_score


def get_usdt_pairs():
    """
    Fetch USDT pairs from MEXC 24h ticker endpoint, filter by liquidity + spread,
    and only keep the top N by quote volume so we don't hammer the API.
    """
    try:
        url = f"{config.MEXC_BASE_URL}/api/v3/ticker/24hr"
        print(f"[scanner] Fetching 24h tickers from: {url}")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        tickers = resp.json()
    except Exception as e:
        print(f"[scanner] Error fetching 24h tickers: {e}")
        return []

    # Filter only USDT symbols and with quoteVolume present
    usdt = []
    for t in tickers:
        symbol = t.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue

        try:
            quote_volume = float(t.get("quoteVolume", 0) or 0)
        except Exception:
            quote_volume = 0.0

        usdt.append((quote_volume, t))

    if not usdt:
        print("[scanner] No USDT tickers found from exchange")
        return []

    # Sort by quote volume (desc) and keep top N
    usdt.sort(key=lambda x: x[0], reverse=True)
    TOP_N = 200  # Increased from 60 to capture more big movers
    top = usdt[:TOP_N]

    print(f"[scanner] Got {len(usdt)} USDT pairs, using top {len(top)} by volume")

    filtered = []
    for idx, (qvol, t) in enumerate(top, start=1):
        symbol = t.get("symbol")
        try:
            # Liquidity filter
            if qvol < config.MIN_LIQUIDITY_VOLUME_24H:
                continue

            # Spread filter - increased tolerance for volatile coins
            spread = get_spread_pct(symbol)
            if spread > 2.0:  # Increased from 0.5% to 2.0% to capture big movers
                continue

            filtered.append(t)
        except Exception as e:
            print(f"[scanner] Skipping {symbol} due to error in filters: {e}")
            continue

        # Small delay to be nice to the API
        time.sleep(0.05)

    print(f"[scanner] After filters: {len(filtered)} liquid USDT pairs")
    return filtered


def compute_features(ticker):
    """
    Compute RVOL, velocity, trend, orderbook imbalance for a symbol.
    """
    try:
        symbol = ticker["symbol"]
        volume = float(ticker.get("volume", 0) or 0)
        quote_volume = float(ticker.get("quoteVolume", 0) or 0)
        price_change_pct = float(ticker.get("priceChangePercent", 0) or 0)
        high_price = float(ticker.get("highPrice", 1) or 1)
        low_price = float(ticker.get("lowPrice", 1) or 1)
        last_price = float(ticker.get("lastPrice", 0) or 0)

        # RVOL: crude approx using quote_volume / 24
        avg_hourly_volume = quote_volume / 24 if quote_volume > 0 else 1
        rvol = volume / max(avg_hourly_volume, 1)

        # Velocity: daily % move
        velocity = price_change_pct

        # Trend: where are we between low and high
        price_range = high_price - low_price
        if price_range > 0 and high_price > 0 and low_price > 0:
            trend = (last_price - low_price) / price_range
        else:
            trend = 0.5

        # Orderbook imbalance
        if config.CHECK_ORDER_BOOK_IMBALANCE:
            ob_imb = get_orderbook_imbalance(symbol)
        else:
            ob_imb = 0.0

        return {
            "symbol": symbol,
            "rvol": rvol,
            "velocity": velocity,
            "trend": trend,
            "orderbook_imbalance": ob_imb,
            "last_price": last_price,
        }
    except Exception as e:
        print(f"[scanner] Error computing features for {ticker.get('symbol')}: {e}")
        return None


def run_scanner():
    print("🔍 Running scanner...")
    pairs = get_usdt_pairs()
    print(f"[scanner] Final universe size: {len(pairs)} symbols")

    if not pairs:
        print("[scanner] No pairs to scan (check network / API / filters)")
        return 0

    signals_created = 0

    for t in pairs:
        f = compute_features(t)
        if not f:
            continue

        score = calculate_score(
            f["rvol"],
            f["velocity"],
            f["trend"],
            f["orderbook_imbalance"],
        )

        if score >= config.MIN_SIGNAL_SCORE:
            db.create_signal(
                f["symbol"],
                score,
                f["rvol"],
                f["velocity"],
                f["trend"],
                f["orderbook_imbalance"],
                f["last_price"],
            )
            signals_created += 1
            print(
                f"[scanner] ✅ Signal: {f['symbol']} "
                f"score={score:.1f} rvol={f['rvol']:.2f} "
                f"vel={f['velocity']:.2f}% trend={f['trend']:.2f} ob={f['orderbook_imbalance']:.2f}"
            )

    print(f"[scanner] Created {signals_created} signals this run")
    return signals_created


if __name__ == "__main__":
    run_scanner()
