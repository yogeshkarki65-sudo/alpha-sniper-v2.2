"""
Alpha Sniper v4.1 Hard Directional Filters
ALL filters must pass for a signal to be valid
"""
from typing import Dict
from config.config import config
from config.logging_config import logger


def apply_directional_filters(features: Dict) -> tuple[bool, str]:
    """
    Apply all hard directional filters
    Args:
        features: Feature dictionary
    Returns: (passed: bool, fail_reason: str)
    """

    # === FILTER 1: 1H RETURN ===
    if features['ret_1h_pct'] < config.MIN_RET_1H_PCT:
        return False, f"ret_1h={features['ret_1h_pct']:.2f}% < {config.MIN_RET_1H_PCT}%"

    # === FILTER 2: 4H RETURN ===
    if features['ret_4h_pct'] < config.MIN_RET_4H_PCT:
        return False, f"ret_4h={features['ret_4h_pct']:.2f}% < {config.MIN_RET_4H_PCT}%"

    # === FILTER 3: 24H RETURN ===
    if features['ret_24h_pct'] < config.MIN_RET_24H_PCT:
        return False, f"ret_24h={features['ret_24h_pct']:.2f}% < {config.MIN_RET_24H_PCT}%"

    # === FILTER 4: SAME DIRECTION (1H & 4H agree) ===
    if config.REQUIRE_SAME_DIRECTION:
        ret_1h = features['ret_1h_pct']
        ret_4h = features['ret_4h_pct']
        if (ret_1h > 0 and ret_4h < 0) or (ret_1h < 0 and ret_4h > 0):
            return False, "ret_1h and ret_4h disagree on direction"

    # === FILTER 5: RELATIVE VOLUME ===
    if features['rvol_1h'] < config.MIN_RVOL_1H:
        return False, f"rvol_1h={features['rvol_1h']:.2f} < {config.MIN_RVOL_1H}"

    # === FILTER 6: RSI RANGE ===
    rsi = features['rsi_1h']
    if rsi < config.MIN_RSI_1H:
        return False, f"rsi_1h={rsi:.1f} < {config.MIN_RSI_1H}"
    if rsi > config.MAX_RSI_1H:
        return False, f"rsi_1h={rsi:.1f} > {config.MAX_RSI_1H}"

    # === FILTER 7: 24H MA ALIGNMENT (MANDATORY) ===
    if config.REQUIRE_ABOVE_MA_24H_50:
        if not features['above_ma_24h_50']:
            return False, "price below 24h MA(50)"

    # === ALL FILTERS PASSED ===
    return True, "OK"


def log_filter_failure(symbol: str, reason: str) -> None:
    """Log filter failure (debug level)"""
    logger.debug(f"[FILTER] {symbol} rejected: {reason}")
