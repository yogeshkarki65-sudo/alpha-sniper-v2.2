"""
Short Scanner Module

Generates short candidates by:
1. TOP LOSERS: Coins with largest negative 24h returns (sorted ASC)
2. BREAKDOWN: Coins breaking below support with volume

Candidates include direction='SHORT' for downstream processing.
"""

import requests
import time
from config.config import config
from scanner.orderbook import get_orderbook_imbalance, get_spread_pct
from shorts.regime_detector import regime_detector


def get_top_losers(limit=50):
    """
    Fetch top losing USDT pairs by 24h price change.
    Filters by min volume and max spread.

    Returns list of ticker dicts sorted by priceChangePercent ASC (biggest losers first)
    """
    try:
        url = f"{config.MEXC_BASE_URL}/api/v3/ticker/24hr"
        print(f"[short_scanner] Fetching 24h tickers for losers...")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        tickers = resp.json()
    except Exception as e:
        print(f"[short_scanner] Error fetching tickers: {e}")
        return []

    # Filter USDT pairs with negative returns
    losers = []
    for t in tickers:
        symbol = t.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue

        try:
            quote_volume = float(t.get("quoteVolume", 0) or 0)
            price_change = float(t.get("priceChangePercent", 0) or 0)
        except (ValueError, TypeError):
            continue

        # Only negative (losing) coins
        if price_change >= 0:
            continue

        # Volume filter
        if quote_volume < config.MIN_24H_QUOTE_VOLUME:
            continue

        losers.append((price_change, quote_volume, t))

    # Sort by price change ASC (most negative first)
    losers.sort(key=lambda x: x[0])

    # Take top N losers
    top_losers = losers[:limit]

    # Apply spread filter
    filtered = []
    for price_change, qvol, t in top_losers:
        symbol = t.get("symbol")
        try:
            spread = get_spread_pct(symbol)
            if spread > config.MAX_ALLOWED_SPREAD_PCT:
                continue
            t["spread_pct"] = spread
            filtered.append(t)
        except Exception as e:
            print(f"[short_scanner] Spread check failed for {symbol}: {e}")
            continue
        time.sleep(0.02)  # Rate limit

    print(f"[short_scanner] Found {len(filtered)} top losers after filters")
    return filtered


def get_funding_rate(symbol):
    """
    Get current funding rate for a futures symbol.
    Returns 8h funding rate as decimal (e.g., 0.0001 for 0.01%)

    Note: MEXC spot API doesn't have funding. For futures, use futures API.
    This is a placeholder - in production, connect to MEXC futures endpoint.
    """
    # For MEXC futures, the endpoint would be different
    # For now, return 0 (neutral funding) as placeholder
    # In production, implement actual futures funding fetch
    try:
        # Futures funding endpoint (example - adjust for actual MEXC futures API)
        # url = f"{config.MEXC_FUTURES_URL}/api/v1/contract/funding_rate/{symbol}"
        # For now, return safe default
        return 0.0001  # 0.01% - safe default
    except Exception:
        return 0.0001


def compute_short_features(ticker, regime):
    """
    Compute features relevant for short signals.

    For shorts, we want:
    - Negative velocity (already down)
    - Low trend (near daily low = breakdown)
    - High RVOL on red moves
    - Negative orderbook imbalance (more sells)
    """
    try:
        symbol = ticker["symbol"]
        volume = float(ticker.get("volume", 0) or 0)
        quote_volume = float(ticker.get("quoteVolume", 0) or 0)
        price_change_pct = float(ticker.get("priceChangePercent", 0) or 0)
        high_price = float(ticker.get("highPrice", 1) or 1)
        low_price = float(ticker.get("lowPrice", 1) or 1)
        last_price = float(ticker.get("lastPrice", 0) or 0)

        # RVOL: volume relative to average
        avg_hourly_volume = quote_volume / 24 if quote_volume > 0 else 1
        rvol = volume / max(avg_hourly_volume, 1)

        # Velocity: negative is good for shorts
        velocity = price_change_pct  # Already negative for losers

        # Trend position: 0 = at low, 1 = at high
        # For shorts, we want LOW trend (near breakdown level)
        price_range = high_price - low_price
        if price_range > 0:
            trend = (last_price - low_price) / price_range
        else:
            trend = 0.5

        # Short-specific: how much room to fall?
        # Distance from high as % (larger = already fallen a lot)
        if high_price > 0:
            drop_from_high = (high_price - last_price) / high_price
        else:
            drop_from_high = 0

        # Orderbook imbalance (negative = sell pressure)
        if config.CHECK_ORDER_BOOK_IMBALANCE:
            ob_imb = get_orderbook_imbalance(symbol)
        else:
            ob_imb = 0.0

        # Funding rate
        funding_8h = get_funding_rate(symbol)

        # Spread (may already be in ticker from get_top_losers)
        spread = ticker.get("spread_pct", get_spread_pct(symbol))

        return {
            "symbol": symbol,
            "direction": "SHORT",
            "rvol": rvol,
            "velocity": velocity,
            "trend": trend,
            "drop_from_high": drop_from_high,
            "orderbook_imbalance": ob_imb,
            "last_price": last_price,
            "quote_volume_24h": quote_volume,
            "funding_8h": funding_8h,
            "spread_pct": spread,
            "regime": regime,
        }
    except Exception as e:
        print(f"[short_scanner] Error computing features for {ticker.get('symbol')}: {e}")
        return None


def filter_short_candidate(features, regime):
    """
    Apply regime-specific filters to short candidates.

    Returns (passed: bool, reason: str)
    """
    symbol = features["symbol"]
    velocity = features["velocity"]  # 24h % change (negative)
    rvol = features["rvol"]
    trend = features["trend"]
    funding_8h = features["funding_8h"]
    spread = features["spread_pct"]

    # Universal filters
    if funding_8h > config.MAX_FUNDING_8H_SHORT:
        return False, f"Funding too high: {funding_8h:.5f}"

    if spread > config.MAX_ALLOWED_SPREAD_PCT:
        return False, f"Spread too wide: {spread:.2f}%"

    if rvol < config.MIN_RVOL_15M_BEAR_SHORT:
        return False, f"RVOL too low: {rvol:.2f}"

    # Regime-specific filters
    if regime == regime_detector.SIDEWAYS:
        # Sideways: fade failed breakouts, not extreme moves
        if velocity < -25:
            return False, f"Already dumped too much: {velocity:.1f}%"
        if velocity > -2:
            return False, f"Not weak enough: {velocity:.1f}%"
        # Trend should be low-mid (below 0.5 = near low)
        if trend > 0.6:
            return False, f"Price too high in range: {trend:.2f}"

    elif regime == regime_detector.MILD_BEAR:
        # Mild bear: trend following, avoid capitulation
        if velocity < -40:
            return False, f"Too extended: {velocity:.1f}%"
        if velocity > -5:
            return False, f"Not bearish enough: {velocity:.1f}%"
        # Should be in lower part of range
        if trend > 0.5:
            return False, f"Not breaking down: {trend:.2f}"

    elif regime == regime_detector.DEEP_BEAR:
        # Deep bear: careful continuation, avoid max pain
        if velocity < -50:
            return False, f"Capitulation - too risky: {velocity:.1f}%"
        if velocity > -8:
            return False, f"Not weak enough for deep bear: {velocity:.1f}%"
        # Extra liquidity check
        if features["quote_volume_24h"] < config.MIN_24H_QUOTE_VOLUME * 2:
            return False, "Insufficient liquidity for deep bear short"
        # Must be clearly breaking down
        if trend > 0.4:
            return False, f"Need cleaner breakdown: {trend:.2f}"

    return True, "OK"


def calculate_short_score(features, regime):
    """
    Calculate signal score for short candidates.

    Score components:
    - RVOL strength (high volume confirms move)
    - Velocity (stronger down = better, but not extreme)
    - Structure (low trend = clean breakdown)
    - Orderbook (negative = selling pressure)

    Returns score 0-100
    """
    rvol = features["rvol"]
    velocity = features["velocity"]
    trend = features["trend"]
    ob_imb = features["orderbook_imbalance"]

    # RVOL score: 1.25-3.0 is optimal, diminishing after
    if rvol < 1.0:
        rvol_score = rvol * 50
    elif rvol <= 3.0:
        rvol_score = 50 + (rvol - 1.0) * 25  # 50-100
    else:
        rvol_score = 100 - (rvol - 3.0) * 5  # Diminishing for extreme

    rvol_score = max(0, min(100, rvol_score))

    # Velocity score: -5% to -30% is sweet spot
    # More negative is better up to a point
    abs_vel = abs(velocity)
    if abs_vel < 2:
        vel_score = 20
    elif abs_vel <= 30:
        vel_score = 20 + (abs_vel - 2) * 2.86  # Scale to ~100 at -30%
    else:
        vel_score = 100 - (abs_vel - 30) * 2  # Diminishing for extreme dumps

    vel_score = max(0, min(100, vel_score))

    # Trend score: INVERTED for shorts
    # Low trend (near low) = clean breakdown = good for shorts
    # trend = 0 (at low) should give high score
    trend_score = (1 - trend) * 100
    trend_score = max(0, min(100, trend_score))

    # Orderbook score: negative imbalance = sell pressure = good for shorts
    # ob_imb ranges -1 to +1, we want negative
    ob_score = (1 - ob_imb) * 50  # -1 -> 100, +1 -> 0
    ob_score = max(0, min(100, ob_score))

    # Weighted combination
    # Regime-specific weights
    if regime == regime_detector.SIDEWAYS:
        # In sideways, structure matters more
        weights = {"rvol": 0.25, "velocity": 0.20, "trend": 0.35, "ob": 0.20}
    elif regime == regime_detector.MILD_BEAR:
        # In bear, momentum matters more
        weights = {"rvol": 0.30, "velocity": 0.30, "trend": 0.25, "ob": 0.15}
    else:  # DEEP_BEAR
        # In deep bear, be more conservative
        weights = {"rvol": 0.25, "velocity": 0.25, "trend": 0.30, "ob": 0.20}

    score = (
        weights["rvol"] * rvol_score +
        weights["velocity"] * vel_score +
        weights["trend"] * trend_score +
        weights["ob"] * ob_score
    )

    return round(score, 1)


def scan_for_shorts(regime=None):
    """
    Main entry point: scan for short candidates.

    Returns list of signal dicts ready for database insertion:
    {
        symbol, score, rvol, velocity, trend, orderbook_imbalance,
        last_price, direction, regime
    }
    """
    if regime is None:
        regime = regime_detector.detect_regime()

    # Check if shorts are allowed
    if not regime_detector.should_trade_shorts(regime):
        print(f"[short_scanner] Shorts disabled in {regime} regime")
        return []

    print(f"[short_scanner] Scanning for shorts in {regime} regime...")

    # Get top losers
    losers = get_top_losers(limit=60)
    if not losers:
        print("[short_scanner] No losers found")
        return []

    candidates = []
    for ticker in losers:
        features = compute_short_features(ticker, regime)
        if not features:
            continue

        # Apply filters
        passed, reason = filter_short_candidate(features, regime)
        if not passed:
            print(f"[short_scanner] {features['symbol']} filtered: {reason}")
            continue

        # Calculate score
        score = calculate_short_score(features, regime)

        if score >= config.MIN_SIGNAL_SCORE:
            candidates.append({
                "symbol": features["symbol"],
                "score": score,
                "rvol": features["rvol"],
                "velocity": features["velocity"],
                "trend": features["trend"],
                "orderbook_imbalance": features["orderbook_imbalance"],
                "last_price": features["last_price"],
                "direction": "SHORT",
                "regime": regime,
                "funding_8h": features["funding_8h"],
            })
            print(
                f"[short_scanner] SHORT candidate: {features['symbol']} "
                f"score={score:.1f} vel={features['velocity']:.1f}% "
                f"rvol={features['rvol']:.2f} trend={features['trend']:.2f}"
            )

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)

    print(f"[short_scanner] Found {len(candidates)} short candidates")
    return candidates


if __name__ == "__main__":
    # Test run
    regime = regime_detector.detect_regime()
    print(f"Current regime: {regime}")
    candidates = scan_for_shorts(regime)
    print(f"Short candidates: {len(candidates)}")
    for c in candidates[:5]:
        print(f"  {c['symbol']}: score={c['score']}, vel={c['velocity']:.1f}%")
