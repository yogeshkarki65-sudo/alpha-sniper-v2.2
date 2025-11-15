"""
Alpha Sniper v4.1 Sniper Scoring Algorithm
Weighted scoring: Trend (35%), Volume (20%), MA Alignment (20%), RSI Regime (15%), Structure (10%)
Output: 0-100 score
"""
from typing import Dict
import numpy as np
from config.config import config


def normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize value to 0-1 range"""
    if max_val == min_val:
        return 0.5
    normalized = (value - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))


def score_trend_strength(features: Dict) -> float:
    """
    Trend Strength: Weighted sum of returns across timeframes
    Weight: 35%
    Returns: 0-1 score
    """
    # Normalize returns (assume 0-20% range for strong moves)
    ret_1h_norm = normalize(features['ret_1h_pct'], 0, 20)
    ret_4h_norm = normalize(features['ret_4h_pct'], 0, 20)
    ret_24h_norm = normalize(features['ret_24h_pct'], 0, 20)

    # Weighted average (1h: 40%, 4h: 40%, 24h: 20%)
    trend_score = (ret_1h_norm * 0.4) + (ret_4h_norm * 0.4) + (ret_24h_norm * 0.2)
    return trend_score


def score_volume_liquidity(features: Dict) -> float:
    """
    Volume & Liquidity: RVOL + quote volume
    Weight: 20%
    Returns: 0-1 score
    """
    # RVOL scoring (2.0-10.0 is excellent)
    rvol_norm = normalize(features['rvol_1h'], 2.0, 10.0)

    # Quote volume scoring (50k-500k range)
    qvol_norm = normalize(features['quote_volume_24h'], 50_000, 500_000)

    # Average the two
    volume_score = (rvol_norm * 0.7) + (qvol_norm * 0.3)
    return volume_score


def score_ma_alignment(features: Dict) -> float:
    """
    MA Alignment: Bonus for being above multiple MAs
    Weight: 20%
    Returns: 0-1 score
    """
    ma_count = 0
    if features['above_ma_1h_50']:
        ma_count += 1
    if features['above_ma_4h_50']:
        ma_count += 1
    if features['above_ma_24h_50']:
        ma_count += 1

    # Base score from count (0-3 → 0-0.7)
    base_score = ma_count / 3.0 * 0.7

    # Bonus +0.3 if above ALL three
    if ma_count == 3:
        base_score = 1.0

    return base_score


def score_rsi_regime(features: Dict) -> float:
    """
    RSI Regime: Peak score in 58-75 zone
    Weight: 15%
    Returns: 0-1 score
    """
    rsi = features['rsi_1h']

    # Ideal zone: 58-75
    if 58 <= rsi <= 75:
        # Linear ramp: 58→0.8, 66.5→1.0, 75→0.8
        if rsi <= 66.5:
            score = 0.8 + ((rsi - 58) / 8.5) * 0.2
        else:
            score = 1.0 - ((rsi - 66.5) / 8.5) * 0.2
        return score

    # Outside ideal zone
    if rsi < 58:
        # 50-58 → 0.4-0.8
        return normalize(rsi, 50, 58) * 0.8
    else:
        # 75-85 → 0.8-0.3
        return normalize(rsi, 85, 75) * 0.8 + 0.2


def score_market_structure(features: Dict) -> float:
    """
    Market Structure: Range position + spread penalty
    Weight: 10%
    Returns: 0-1 score
    """
    # Range position (higher is better: near highs)
    range_score = features['range_pos_24h']

    # Spread penalty (0-50 bps)
    spread_bps = features['spread_bps']
    if spread_bps <= 10:
        spread_penalty = 0.0
    elif spread_bps <= 30:
        spread_penalty = (spread_bps - 10) / 20 * 0.2  # up to -20%
    else:
        spread_penalty = 0.2 + (spread_bps - 30) / 20 * 0.3  # up to -50%

    structure_score = max(0.0, range_score - spread_penalty)
    return structure_score


def calculate_score(features: Dict) -> float:
    """
    Calculate weighted Sniper Score (0-100)
    Args:
        features: Feature dictionary
    Returns: Score 0-100
    """
    # Component scores (0-1)
    trend = score_trend_strength(features)
    volume = score_volume_liquidity(features)
    ma_align = score_ma_alignment(features)
    rsi = score_rsi_regime(features)
    structure = score_market_structure(features)

    # Weighted sum
    weighted_score = (
        (trend * config.WEIGHT_TREND) +
        (volume * config.WEIGHT_VOLUME) +
        (ma_align * config.WEIGHT_MA_ALIGNMENT) +
        (rsi * config.WEIGHT_RSI_REGIME) +
        (structure * config.WEIGHT_STRUCTURE)
    )

    # Scale to 0-100
    final_score = weighted_score * 100
    return final_score


# === LEGACY FUNCTION (for compatibility) ===
def calculate_score_legacy(rvol, velocity, trend, orderbook_imbalance):
    """
    Legacy scoring function (kept for backward compatibility)
    """
    features = {
        'ret_1h_pct': velocity,
        'ret_4h_pct': velocity * 0.8,
        'ret_24h_pct': velocity,
        'rvol_1h': rvol,
        'quote_volume_24h': 100000,
        'rsi_1h': 65,
        'above_ma_1h_50': True,
        'above_ma_4h_50': True,
        'above_ma_24h_50': True,
        'range_pos_24h': trend,
        'spread_bps': 20,
        'orderbook_imbalance': orderbook_imbalance,
    }
    return calculate_score(features)
