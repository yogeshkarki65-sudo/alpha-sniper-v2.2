"""
Position Entry Validator
Verifies that opened positions meet v4.1.1 entry criteria
"""
import logging
from typing import Dict, Tuple
from config.config import config

logger = logging.getLogger(__name__)


def validate_entry_criteria(
    symbol: str,
    score: float,
    rvol: float,
    velocity: float,
    trend: float,
    orderbook_imbalance: float
) -> Tuple[bool, Dict[str, bool]]:
    """
    Validate that an entry meets v4.1.1 criteria

    Returns:
        (passes_all, criteria_dict)
    """
    criteria = {}

    # Score threshold
    criteria['score'] = score >= config.MIN_SIGNAL_SCORE

    # All criteria must pass
    passes_all = all(criteria.values())

    return passes_all, criteria


def print_entry_validation(
    symbol: str,
    score: float,
    rvol: float = None,
    velocity: float = None,
    trend: float = None,
    orderbook_imbalance: float = None
):
    """
    Print detailed validation report for a position entry
    """
    print(f"\n{'='*60}")
    print(f"📋 ENTRY VALIDATION: {symbol}")
    print(f"{'='*60}")

    # Validate
    passes_all, criteria = validate_entry_criteria(
        symbol, score, rvol, velocity, trend, orderbook_imbalance
    )

    # Score check
    status = "✔" if criteria['score'] else "✘"
    print(f"{status} Score: {score:.1f} >= {config.MIN_SIGNAL_SCORE}")

    # Optional feature display
    if rvol is not None:
        print(f"  RVOL: {rvol:.2f}")
    if velocity is not None:
        print(f"  Velocity: {velocity:.2f}%")
    if trend is not None:
        print(f"  Trend: {trend:.2f}")
    if orderbook_imbalance is not None:
        print(f"  OB Imbalance: {orderbook_imbalance:.2f}")

    print(f"\nOverall: {'✅ VALID' if passes_all else '❌ INVALID'}")
    print(f"{'='*60}\n")

    return passes_all


def validate_position_from_db(position_data: Dict) -> bool:
    """
    Validate a position from database data

    Expected keys: symbol, signal_score, signal_data (json with features)
    """
    symbol = position_data.get('symbol', 'UNKNOWN')
    score = position_data.get('signal_score', 0.0)

    # If signal data available, extract features
    signal_data = position_data.get('signal_data', {})
    rvol = signal_data.get('rvol')
    velocity = signal_data.get('velocity')
    trend = signal_data.get('trend')
    ob_imbalance = signal_data.get('orderbook_imbalance')

    return print_entry_validation(
        symbol, score, rvol, velocity, trend, ob_imbalance
    )


def get_filter_config_summary() -> str:
    """
    Return current filter configuration as formatted string
    """
    # Build fallback info string
    if config.ENABLE_V42_FALLBACK:
        fallback_info = f"ENABLED (base={config.MIN_SIGNAL_SCORE} → fallback={config.MIN_SIGNAL_SCORE_FALLBACK} after {config.FALLBACK_TRIGGER_HOURS}h)"
    else:
        fallback_info = "DISABLED"

    summary = f"""
ENTRY FILTERS ACTIVE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Signal Scoring:
  • Min Signal Score: {config.MIN_SIGNAL_SCORE}
  • Check Orderbook Imbalance: {config.CHECK_ORDER_BOOK_IMBALANCE}

v4.2 Adaptive Fallback:
  • Status: {fallback_info}

Risk Management:
  • Min Liquidity (24h): ${config.MIN_LIQUIDITY_VOLUME_24H:,.0f}
  • Max Spread: 0.5%
  • Symbol Cooldown: {config.SYMBOL_COOLDOWN_HOURS}h

Position Sizing:
  • Max Concurrent Positions: {config.MAX_CONCURRENT_POS}
  • Max Position Risk: {config.MAX_POSITION_RISK_PCT}%
  • Stop Loss: {config.STOP_LOSS_PCT}%
  • Take Profit: {config.TAKE_PROFIT_PCT}%

Exit Management:
  • Trailing Stop: {config.USE_TRAILING_STOP}
  • Trailing Activation: {config.TRAILING_STOP_ACTIVATION_PCT}%
  • Trailing Distance: {config.TRAILING_STOP_DISTANCE_PCT}%
  • Max Hold Time: {config.MAX_HOLD_TIME_HOURS}h

Debug:
  • Filter Debug Mode: {config.DEBUG_FILTERS}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return summary
