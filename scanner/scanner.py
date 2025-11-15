"""
Alpha Sniper v4.1 Scanner
Multi-timeframe signal generation with hard directional filters
Runs every 5 minutes (300 seconds)
"""
import time
from typing import List, Dict
from config.config import config
from config.logging_config import logger
from database.models import db
from scanner.mexc_client import mexc_client
from scanner.features import get_symbol_features
from scanner.filters import apply_directional_filters, log_filter_failure
from scanner.scorer import calculate_score
from scanner.orderbook import get_spread_pct


def is_stablecoin(symbol: str) -> bool:
    """
    Check if symbol is a stablecoin pair
    Args:
        symbol: Trading pair (e.g., 'USDCUSDT')
    Returns: True if stablecoin
    """
    if not config.EXCLUDE_STABLECOINS:
        return False

    # Extract base asset (remove 'USDT' suffix)
    if symbol.endswith('USDT'):
        base = symbol[:-4]
        return base in config.STABLECOINS

    return False


def build_universe() -> List[Dict]:
    """
    Step 1: Universe Building
    - Fetch all USDT pairs
    - Exclude stablecoins
    - Apply liquidity filter
    - Apply spread filter
    Returns: List of valid ticker dicts
    """
    logger.info("=" * 60)
    logger.info("BUILDING UNIVERSE")
    logger.info("=" * 60)

    # Fetch 24h tickers
    tickers = mexc_client.get_24h_tickers()
    if not tickers:
        logger.warning("No tickers received from exchange")
        return []

    logger.info(f"Fetched {len(tickers)} tickers from exchange")

    # Filter USDT pairs
    usdt_pairs = []
    for t in tickers:
        symbol = t.get('symbol', '')
        if not symbol.endswith('USDT'):
            continue

        # Exclude stablecoins
        if is_stablecoin(symbol):
            logger.debug(f"Excluding stablecoin: {symbol}")
            continue

        usdt_pairs.append(t)

    logger.info(f"Found {len(usdt_pairs)} USDT pairs (after stablecoin exclusion)")

    # Sort by quote volume and keep top liquid pairs
    usdt_pairs_with_vol = []
    for t in usdt_pairs:
        try:
            qvol = float(t.get('quoteVolume', 0) or 0)
            usdt_pairs_with_vol.append((qvol, t))
        except:
            continue

    usdt_pairs_with_vol.sort(key=lambda x: x[0], reverse=True)

    # Keep top 80 by volume (configurable)
    top_pairs = usdt_pairs_with_vol[:80]
    logger.info(f"Keeping top 80 pairs by volume")

    # Apply liquidity and spread filters
    filtered = []
    for qvol, t in top_pairs:
        symbol = t.get('symbol')

        # Liquidity filter
        if qvol < config.MIN_LIQUIDITY_VOLUME_24H:
            logger.debug(f"{symbol}: quote_volume={qvol:,.0f} < {config.MIN_LIQUIDITY_VOLUME_24H:,.0f}")
            continue

        # Spread filter
        try:
            spread_bps = get_spread_pct(symbol) * 100  # Convert to bps
            if spread_bps > config.MAX_SPREAD_BPS:
                logger.debug(f"{symbol}: spread={spread_bps:.1f}bps > {config.MAX_SPREAD_BPS}bps")
                continue
            t['spread_bps'] = spread_bps
        except Exception as e:
            logger.debug(f"{symbol}: Failed to check spread: {e}")
            continue

        filtered.append(t)
        time.sleep(0.02)  # Rate limiting

    logger.info(f"✅ Final universe: {len(filtered)} liquid, tradable pairs")
    return filtered


def scan_symbol(ticker: Dict) -> bool:
    """
    Scan a single symbol through the full pipeline:
    1. Compute features
    2. Apply directional filters
    3. Calculate score
    4. Save signal if score >= MIN_SIGNAL_SCORE
    Returns: True if signal created
    """
    symbol = ticker['symbol']

    # Step 1: Compute features
    features = get_symbol_features(
        symbol,
        ticker,
        use_orderbook=config.CHECK_ORDER_BOOK_IMBALANCE
    )

    if not features:
        return False

    # Add spread from ticker
    features['spread_bps'] = ticker.get('spread_bps', 0)

    # Step 2: Apply directional filters (ALL must pass)
    passed, fail_reason = apply_directional_filters(features)
    if not passed:
        log_filter_failure(symbol, fail_reason)
        return False

    # Step 3: Calculate score
    score = calculate_score(features)

    # Step 4: Check minimum score threshold
    if score < config.MIN_SIGNAL_SCORE:
        logger.debug(f"{symbol}: score={score:.1f} < {config.MIN_SIGNAL_SCORE}")
        return False

    # Step 5: Check 12-hour cooldown
    from trader.trader import check_symbol_cooldown
    if not check_symbol_cooldown(symbol):
        logger.debug(f"{symbol}: In 12h cooldown period")
        return False

    # Step 6: Save signal
    try:
        db.create_signal(
            symbol=features['symbol'],
            score=score,
            ret_1h_pct=features['ret_1h_pct'],
            ret_4h_pct=features['ret_4h_pct'],
            ret_24h_pct=features['ret_24h_pct'],
            rvol_1h=features['rvol_1h'],
            quote_volume_24h=features['quote_volume_24h'],
            rsi_1h=features['rsi_1h'],
            above_ma_1h_50=features['above_ma_1h_50'],
            above_ma_4h_50=features['above_ma_4h_50'],
            above_ma_24h_50=features['above_ma_24h_50'],
            range_pos_24h=features['range_pos_24h'],
            spread_bps=features['spread_bps'],
            last_price=features['last_price'],
            orderbook_imbalance=features['orderbook_imbalance']
        )

        logger.info(
            f"✅ SIGNAL: {symbol} | score={score:.1f} | "
            f"ret_1h={features['ret_1h_pct']:.1f}% | "
            f"ret_4h={features['ret_4h_pct']:.1f}% | "
            f"rvol={features['rvol_1h']:.1f} | "
            f"rsi={features['rsi_1h']:.0f} | "
            f"above_24h_ma={features['above_ma_24h_50']}"
        )
        return True

    except Exception as e:
        logger.error(f"Error saving signal for {symbol}: {e}")
        return False


def run_scanner() -> int:
    """
    Main scanner entry point
    Runs full pipeline: universe → features → filters → scoring → signals
    Returns: Number of signals created
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("🔍 ALPHA SNIPER v4.1 SCANNER")
    logger.info("=" * 60)

    # Build universe
    universe = build_universe()
    if not universe:
        logger.warning("Empty universe. No signals generated.")
        return 0

    # Scan each symbol
    logger.info("")
    logger.info("SCANNING SYMBOLS")
    logger.info("=" * 60)

    signals_created = 0
    for ticker in universe:
        if scan_symbol(ticker):
            signals_created += 1
        time.sleep(0.05)  # Rate limiting

    logger.info("=" * 60)
    logger.info(f"✅ Scanner complete: {signals_created} signals created")
    logger.info("=" * 60)

    return signals_created


if __name__ == "__main__":
    run_scanner()
