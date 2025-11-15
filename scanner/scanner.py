"""
Alpha Sniper V3.0 - Smart Scanner with Advanced Technical Analysis

This scanner implements a complete pipeline:
1. Fetch USDT pairs from MEXC
2. Apply liquidity and spread filters
3. Fetch candle data (15m, 1h, 24h) for technical indicators
4. Compute multi-factor features (RSI, momentum, MA, ATR, etc.)
5. Score using SignalScorer
6. Apply MIN_SIGNAL_SCORE and SYMBOL_COOLDOWN
7. Save qualified signals to database
"""

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config.config import config
from config.logging_config import configure_logging
from database.models import db
from scanner.orderbook import get_orderbook_imbalance, get_spread_pct
from scanner.scorer import SignalScorer, ScoringFeatures, ScoreWeights

# Initialize logger
logger = configure_logging("scanner")

# Initialize scorer
scorer = SignalScorer(ScoreWeights.load())


def get_candles(symbol: str, interval: str, limit: int = 100) -> Optional[List[Dict]]:
    """
    Fetch candlestick data from MEXC.

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        interval: Candle interval ('1m', '5m', '15m', '1h', '4h', '1d')
        limit: Number of candles to fetch (max 1000)

    Returns:
        List of candle dictionaries with OHLCV data, or None on error
    """
    try:
        url = f"{config.MEXC_BASE_URL}/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()

        # MEXC returns: [openTime, open, high, low, close, volume, closeTime, quoteVolume, ...]
        raw = resp.json()
        candles = []
        for k in raw:
            candles.append({
                "time": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "quote_volume": float(k[7]) if len(k) > 7 else 0.0
            })

        return candles
    except Exception as e:
        logger.debug(f"Failed to fetch {interval} candles for {symbol}: {e}")
        return None


def calculate_rsi(closes: List[float], period: int = 14) -> float:
    """Calculate RSI indicator"""
    if len(closes) < period + 1:
        return 50.0  # Neutral

    gains = []
    losses = []

    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    if len(gains) < period:
        return 50.0

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_atr_pct(candles: List[Dict], period: int = 14) -> float:
    """Calculate Average True Range as percentage of price"""
    if len(candles) < period + 1:
        return 2.0  # Default

    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)

    if not true_ranges or len(true_ranges) < period:
        return 2.0

    atr = sum(true_ranges[-period:]) / period
    current_price = candles[-1]["close"]

    if current_price == 0:
        return 2.0

    atr_pct = (atr / current_price) * 100
    return atr_pct


def get_usdt_pairs() -> List[Dict]:
    """
    Fetch USDT pairs from MEXC, apply liquidity and spread filters.
    Returns top N pairs by quote volume.
    """
    try:
        url = f"{config.MEXC_BASE_URL}/api/v3/ticker/24hr"
        logger.debug(f"Fetching 24h tickers from MEXC API")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        tickers = resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch 24h tickers: {e}")
        return []

    # Stablecoins to exclude (base assets that are stablecoins = no volatility)
    # These are stablecoin-to-stablecoin pairs with no directional edge
    STABLECOIN_BASES = {
        'USD1', 'USDE', 'USDC', 'DAI', 'FDUSD', 'TUSD', 'USDP',
        'BUSD', 'PAX', 'UST', 'USDD', 'LUSD', 'GUSD', 'SUSD',
        'FRAX', 'USDJ', 'USDN', 'CUSD', 'EURS', 'EURT'
    }

    # Filter USDT pairs
    usdt = []
    stablecoin_filtered = 0

    for t in tickers:
        symbol = t.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue

        # V3: Exclude stablecoin pairs (extract base asset)
        base = symbol[:-4]  # Remove 'USDT' suffix
        if base in STABLECOIN_BASES:
            stablecoin_filtered += 1
            continue

        try:
            quote_volume = float(t.get("quoteVolume", 0) or 0)
        except Exception:
            quote_volume = 0.0

        usdt.append((quote_volume, t))

    if not usdt:
        logger.warning("No USDT pairs found from exchange")
        return []

    # Sort by quote volume and keep top N
    usdt.sort(key=lambda x: x[0], reverse=True)
    TOP_N = 60
    top = usdt[:TOP_N]

    logger.info(
        f"Found {len(usdt)} USDT pairs (excluded {stablecoin_filtered} stablecoins), "
        f"analyzing top {len(top)} by volume"
    )

    # Apply filters
    filtered = []
    failed_liquidity = 0
    failed_spread = 0

    for qvol, t in top:
        symbol = t.get("symbol")

        try:
            # Liquidity filter
            if qvol < config.MIN_LIQUIDITY_VOLUME_24H:
                failed_liquidity += 1
                continue

            # Spread filter
            spread = get_spread_pct(symbol)
            if spread > 0.5:  # 0.5% max spread
                failed_spread += 1
                continue

            filtered.append(t)
        except Exception as e:
            logger.debug(f"Error filtering {symbol}: {e}")
            continue

        # Rate limiting
        time.sleep(0.05)

    logger.info(
        f"After filters: {len(filtered)} pairs "
        f"(rejected: {failed_liquidity} liquidity, {failed_spread} spread)"
    )

    return filtered


def compute_features(ticker: Dict) -> Optional[ScoringFeatures]:
    """
    Compute all features required for V3 multi-factor scoring.

    Features:
    - RVOL (relative volume)
    - Liquidity (24h quote volume)
    - Velocity (24h price change %)
    - Momentum 15m (last 15m vs 15m ago)
    - Momentum 1h (last 1h price change)
    - RSI(14) on 1h candles
    - Trend position (price position in 24h range)
    - Above MA50 (1h)
    - Orderbook imbalance (optional)
    - Spread (bid-ask)
    - ATR % (volatility)
    """
    try:
        symbol = ticker["symbol"]
        last_price = float(ticker.get("lastPrice", 0) or 0)
        quote_volume = float(ticker.get("quoteVolume", 0) or 0)
        volume = float(ticker.get("volume", 0) or 0)
        price_change_pct = float(ticker.get("priceChangePercent", 0) or 0)
        high_price = float(ticker.get("highPrice", 1) or 1)
        low_price = float(ticker.get("lowPrice", 1) or 1)

        if last_price == 0:
            return None

        # RVOL: Current volume vs average hourly volume
        avg_hourly_volume = quote_volume / 24 if quote_volume > 0 else 1
        rvol = volume / max(avg_hourly_volume, 1)

        # Liquidity: 24h quote volume
        liquidity_usd_24h = quote_volume

        # Velocity: 24h price change %
        velocity_24h_pct = price_change_pct

        # Trend position: where is price in 24h range (0=low, 1=high)
        price_range = high_price - low_price
        if price_range > 0:
            trend_position = (last_price - low_price) / price_range
        else:
            trend_position = 0.5

        # Fetch 1h candles for momentum, RSI, MA
        candles_1h = get_candles(symbol, "1h", limit=50)
        if candles_1h and len(candles_1h) >= 2:
            # Momentum 1h: last candle vs candle 1h ago
            momentum_1h_pct = ((candles_1h[-1]["close"] - candles_1h[-2]["close"]) / candles_1h[-2]["close"]) * 100

            # RSI(14) on 1h
            closes_1h = [c["close"] for c in candles_1h]
            rsi_14 = calculate_rsi(closes_1h, period=14)

            # Above MA50 (1h)
            if len(closes_1h) >= 50:
                ma50 = sum(closes_1h[-50:]) / 50
                above_ma_1h = last_price > ma50
            else:
                above_ma_1h = True  # Default to true if not enough data

            # ATR %
            atr_pct = calculate_atr_pct(candles_1h, period=14)
        else:
            momentum_1h_pct = 0.0
            rsi_14 = 50.0
            above_ma_1h = True
            atr_pct = 2.0

        # Fetch 15m candles for short-term momentum
        candles_15m = get_candles(symbol, "15m", limit=10)
        if candles_15m and len(candles_15m) >= 2:
            # Momentum 15m: last vs 15m ago
            momentum_15m_pct = ((candles_15m[-1]["close"] - candles_15m[-2]["close"]) / candles_15m[-2]["close"]) * 100
        else:
            momentum_15m_pct = 0.0

        # Orderbook imbalance (optional)
        if config.CHECK_ORDER_BOOK_IMBALANCE:
            try:
                ob_imbalance = get_orderbook_imbalance(symbol)
            except Exception:
                ob_imbalance = 0.0
        else:
            ob_imbalance = 0.0

        # Spread
        try:
            spread_bps = get_spread_pct(symbol) * 100  # Convert to basis points
        except Exception:
            spread_bps = 10.0

        # Create features dataclass
        features = ScoringFeatures(
            symbol=symbol,
            last_price=last_price,
            rvol=rvol,
            liquidity_usd_24h=liquidity_usd_24h,
            velocity_24h_pct=velocity_24h_pct,
            momentum_1h_pct=momentum_1h_pct,
            momentum_15m_pct=momentum_15m_pct,
            rsi_14=rsi_14,
            trend_position=trend_position,
            above_ma_1h=above_ma_1h,
            orderbook_imbalance=ob_imbalance,
            spread_bps=spread_bps,
            atr_pct=atr_pct
        )

        return features

    except Exception as e:
        logger.debug(f"Error computing features for {ticker.get('symbol')}: {e}")
        return None


def check_symbol_cooldown(symbol: str) -> bool:
    """
    Check if symbol is in cooldown period.
    Returns True if symbol can be traded, False if in cooldown.
    """
    try:
        cooldown_hours = config.SYMBOL_COOLDOWN_HOURS
        cutoff = datetime.now() - timedelta(hours=cooldown_hours)

        # Check last trade for this symbol
        last_trade = db.get_last_trade_for_symbol(symbol)
        if last_trade:
            # Assuming last_trade has 'closed_at' timestamp
            closed_at = last_trade.get('closed_at')
            if closed_at:
                if isinstance(closed_at, str):
                    closed_at_dt = datetime.fromisoformat(closed_at)
                else:
                    closed_at_dt = datetime.fromtimestamp(closed_at)

                if closed_at_dt > cutoff:
                    return False  # Still in cooldown

        return True  # Not in cooldown
    except Exception as e:
        logger.debug(f"Error checking cooldown for {symbol}: {e}")
        return True  # Default to allowing trade


def run_scanner() -> int:
    """
    Main scanner function - V3.0 implementation.

    Returns:
        Number of signals created
    """
    logger.info("🔍 Starting V3 scanner...")

    # Fetch and filter pairs
    pairs = get_usdt_pairs()
    logger.info(f"Final universe: {len(pairs)} symbols")

    if not pairs:
        logger.warning("No pairs to scan - check network/API/filters")
        return 0

    signals_created = 0
    scores = []
    feature_failures = 0
    cooldown_blocked = 0
    directional_blocked = 0

    for ticker in pairs:
        symbol = ticker.get("symbol")

        # Compute features
        features = compute_features(ticker)
        if not features:
            feature_failures += 1
            continue

        # V3: Directional movement filters (no flat/choppy coins)
        # Require real movement, not just noise
        momentum_ok = abs(features.momentum_1h_pct) >= 1.0  # At least 1% move in 1h
        velocity_ok = abs(features.velocity_24h_pct) >= 2.0  # At least 2% move in 24h
        rsi_ok = features.rsi_14 <= 40 or features.rsi_14 >= 60  # Oversold or overbought, not middle

        if not (momentum_ok and velocity_ok and rsi_ok):
            directional_blocked += 1
            logger.debug(
                f"🚫 {symbol} blocked by directional filters: "
                f"mom_1h={features.momentum_1h_pct:.1f}% (need ≥1%), "
                f"vel_24h={features.velocity_24h_pct:.1f}% (need ≥2%), "
                f"rsi={features.rsi_14:.0f} (need ≤40 or ≥60)"
            )
            continue

        # Score using V3 scorer
        result = scorer.score(features)
        total_score = result["total_score"]
        components = result["components"]

        scores.append(total_score)

        # Check if score meets threshold
        if total_score >= config.MIN_SIGNAL_SCORE:
            # Check cooldown
            if not check_symbol_cooldown(symbol):
                cooldown_blocked += 1
                logger.debug(f"{symbol} blocked by cooldown")
                continue

            # Create signal
            try:
                db.create_signal(
                    symbol=symbol,
                    score=total_score,
                    rvol=features.rvol,
                    velocity=features.velocity_24h_pct,
                    trend=features.trend_position,
                    orderbook_imbalance=features.orderbook_imbalance,
                    last_price=features.last_price
                )
                signals_created += 1

                logger.info(
                    f"✅ Signal: {symbol} | score={total_score:.1f} | "
                    f"rvol={features.rvol:.2f} | vel={features.velocity_24h_pct:.1f}% | "
                    f"rsi={features.rsi_14:.0f} | momentum_1h={features.momentum_1h_pct:.1f}%"
                )

                # Log component breakdown for debugging
                logger.debug(f"{symbol} breakdown: {components}")

            except Exception as e:
                logger.error(f"Failed to create signal for {symbol}: {e}")

    # Summary statistics
    if scores:
        min_score = min(scores)
        max_score = max(scores)
        avg_score = sum(scores) / len(scores)

        logger.info(
            f"📊 Summary → candidates={len(scores)} | signals={signals_created} | "
            f"score_min={min_score:.1f} | score_avg={avg_score:.1f} | score_max={max_score:.1f} | "
            f"threshold={config.MIN_SIGNAL_SCORE}"
        )
        logger.info(
            f"📊 Filters → feature_failures={feature_failures} | "
            f"directional_blocked={directional_blocked} | "
            f"cooldown_blocked={cooldown_blocked}"
        )
    else:
        logger.warning("No valid candidates after feature computation")

    logger.info(f"Created {signals_created} signals this run")
    return signals_created


if __name__ == "__main__":
    run_scanner()
