"""
Alpha Sniper V4.0 - Core Entry Filters
Section C - EXACT IMPLEMENTATION

All engines must pass relevant filters before orders
"""
import os
from typing import Dict, Tuple


class EntryFilters:
    """
    Core entry filters (LONG FILTER 1-4, SHORT FILTER 5-6)
    """

    @staticmethod
    def check_long_filter_1_clean_4h_uptrend(features: Dict) -> Tuple[bool, str]:
        """
        LONG FILTER 1 – CLEAN 4H UPTREND
        - Trend_Ratio_4h ≥ 1.01
        - close > EMA20_4h
        - EMA20_4h ≥ EMA50_4h
        """
        trend_ratio = features.get('trend_ratio_4h', 0)
        close = features.get('close', 0)
        ema20_4h = features.get('ema20_4h', 0)
        ema50_4h = features.get('ema50_4h', 0)

        if trend_ratio < 1.01:
            return False, f"trend_ratio={trend_ratio:.3f} < 1.01"

        if close <= ema20_4h:
            return False, f"close={close:.4f} <= ema20={ema20_4h:.4f}"

        if ema20_4h < ema50_4h:
            return False, f"ema20={ema20_4h:.4f} < ema50={ema50_4h:.4f}"

        return True, "OK"

    @staticmethod
    def check_long_filter_2_healthy_rvol(features: Dict, regime: str) -> Tuple[bool, str]:
        """
        LONG FILTER 2 – HEALTHY RVOL
        - RVOL_15m ≥ MIN_RVOL_15M_REGIME
        - Reject if RVOL_15m > 5.0 AND 3d_return > 60% (blowoff)
        """
        rvol = features.get('rvol_15m', 0)
        ret_3d = features.get('return_3d', 0)

        # Min RVOL per regime
        if regime == "BULL":
            min_rvol = float(os.getenv('MIN_RVOL_15M_BULL', 1.2))
        elif regime == "SIDEWAYS":
            min_rvol = float(os.getenv('MIN_RVOL_15M_SIDEWAYS', 1.5))
        else:
            return False, f"regime={regime} not BULL/SIDEWAYS"

        if rvol < min_rvol:
            return False, f"rvol={rvol:.2f} < {min_rvol:.2f}"

        # Reject blowoff
        if rvol > 5.0 and ret_3d > 0.60:
            return False, f"blowoff: rvol={rvol:.2f}, ret_3d={ret_3d*100:.1f}%"

        return True, "OK"

    @staticmethod
    def check_long_filter_3_coil_buildup(features: Dict) -> Tuple[bool, str]:
        """
        LONG FILTER 3 – COIL / BUILDUP STRUCTURE
        - ATR14_15m < COIL_ATR_COMPRESSION * median(ATR14_15m last 24h)
        - price_pos_24h between 0.55 and 0.90
        - No 15m candle in last 6 bars with range > 2 × ATR14_15m
        """
        atr_now = features.get('atr_14_15m', 0)
        atr_median_24h = features.get('atr_median_24h', 0)
        price_pos = features.get('price_pos_24h', 0)
        max_range_6bars = features.get('max_range_6bars', 0)

        coil_threshold = float(os.getenv('COIL_ATR_COMPRESSION', 0.7))

        if atr_median_24h == 0:
            return False, "atr_median_24h=0"

        if atr_now >= coil_threshold * atr_median_24h:
            return False, f"atr={atr_now:.6f} >= {coil_threshold}*{atr_median_24h:.6f}"

        if price_pos < 0.55 or price_pos > 0.90:
            return False, f"price_pos={price_pos:.2f} not in [0.55, 0.90]"

        if max_range_6bars > 2.0 * atr_now:
            return False, f"big_candle: range={max_range_6bars:.6f} > 2*atr={2*atr_now:.6f}"

        return True, "OK"

    @staticmethod
    def check_long_filter_4_early_breakout(features: Dict) -> Tuple[bool, str]:
        """
        LONG FILTER 4 – EARLY BREAKOUT (NOT LATE)
        - Trigger_price_long = 24h_high * (1 + BREAKOUT_BUFFER_PCT)
        - close crosses above Trigger_price_long
        - last 3–4 bars show higher lows OR inside-bar coil then expansion
        - Reject if 24h_return > 35%
        """
        close = features.get('close', 0)
        high_24h = features.get('high_24h', 0)
        ret_24h = features.get('return_24h', 0)
        higher_lows = features.get('higher_lows_recent', False)

        buffer = float(os.getenv('BREAKOUT_BUFFER_PCT', 0.003))
        trigger_price = high_24h * (1.0 + buffer)

        if close < trigger_price:
            return False, f"close={close:.4f} < trigger={trigger_price:.4f}"

        if ret_24h > 0.35:
            return False, f"too_late: ret_24h={ret_24h*100:.1f}% > 35%"

        if not higher_lows:
            return False, "no higher lows pattern"

        return True, "OK"

    @staticmethod
    def check_short_filter_5_clean_4h_downtrend(features: Dict) -> Tuple[bool, str]:
        """
        SHORT FILTER 5 – CLEAN 4H DOWNTREND (BEAR ONLY)
        - Trend_Ratio_4h ≤ 0.99
        - close < EMA20_4h
        - EMA20_4h ≤ EMA50_4h
        """
        trend_ratio = features.get('trend_ratio_4h', 1.0)
        close = features.get('close', 0)
        ema20_4h = features.get('ema20_4h', 0)
        ema50_4h = features.get('ema50_4h', 0)

        if trend_ratio > 0.99:
            return False, f"trend_ratio={trend_ratio:.3f} > 0.99"

        if close >= ema20_4h:
            return False, f"close={close:.4f} >= ema20={ema20_4h:.4f}"

        if ema20_4h > ema50_4h:
            return False, f"ema20={ema20_4h:.4f} > ema50={ema50_4h:.4f}"

        return True, "OK"

    @staticmethod
    def check_short_filter_6_breakdown(features: Dict) -> Tuple[bool, str]:
        """
        SHORT FILTER 6 – BREAKDOWN + LOWER HIGH
        - lower high below last swing high
        - breakdown trigger = close < support_low * (1 - BREAKDOWN_BUFFER_PCT)
        - RVOL_15m ≥ MIN_RVOL_15M_BEAR_SHORT
        - RSI_1h between 30 and 55 (not oversold)
        """
        close = features.get('close', 0)
        support_low = features.get('support_low_24_48h', 0)
        rvol = features.get('rvol_15m', 0)
        rsi_1h = features.get('rsi_1h', 50)
        has_lower_high = features.get('has_lower_high', False)

        buffer = float(os.getenv('BREAKDOWN_BUFFER_PCT', 0.005))
        breakdown_trigger = support_low * (1.0 - buffer)

        min_rvol = float(os.getenv('MIN_RVOL_15M_BEAR_SHORT', 1.3))

        if close >= breakdown_trigger:
            return False, f"close={close:.4f} >= breakdown={breakdown_trigger:.4f}"

        if not has_lower_high:
            return False, "no lower high pattern"

        if rvol < min_rvol:
            return False, f"rvol={rvol:.2f} < {min_rvol:.2f}"

        if rsi_1h < 30 or rsi_1h > 55:
            return False, f"rsi_1h={rsi_1h:.1f} not in [30, 55]"

        return True, "OK"


# Singleton
entry_filters = EntryFilters()
