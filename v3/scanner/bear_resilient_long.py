#!/usr/bin/env python3
"""
Bear-Resilient Long Engine

Ultra-conservative micro long engine for BEAR regime only.
Designed to catch 50-150% pumps during bear markets while protecting capital.

Only active in BEAR regime on SPOT with extreme filters.
"""

import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import numpy as np

from v3.scanner.features import Features
from v3.regime.detector import Regime


class BearResilientLongEngine:
    """
    Bear-Resilient Long Engine for catching ultra-strong outliers in BEAR markets.

    Configuration (from .env):
        ENABLE_BEAR_LONGS=true
        RISK_PER_TRADE_BEAR_LONG=0.0008  # 0.08%
        MAX_CONCURRENT_BEAR_LONGS=1
        MAX_HOLD_HOURS_BEAR_LONG=24
        MIN_RVOL_15M_BEAR_LONG=1.5
        MIN_24H_RETURN_BEAR_LONG=0.05
        MAX_24H_RETURN_BEAR_LONG=0.40
        MIN_DEPTH_10K_BEAR_LONG=10000
        MAX_SPREAD_PCT_BEAR_LONG=1.0
    """

    def __init__(self):
        # Load configuration
        self.enabled = os.getenv('ENABLE_BEAR_LONGS', 'false').lower() == 'true'
        self.risk_per_trade = float(os.getenv('RISK_PER_TRADE_BEAR_LONG', '0.0008'))
        self.max_concurrent = int(os.getenv('MAX_CONCURRENT_BEAR_LONGS', '1'))
        self.max_hold_hours = int(os.getenv('MAX_HOLD_HOURS_BEAR_LONG', '24'))

        # Filter thresholds
        self.min_rvol_15m = float(os.getenv('MIN_RVOL_15M_BEAR_LONG', '1.5'))
        self.min_24h_return = float(os.getenv('MIN_24H_RETURN_BEAR_LONG', '0.05'))
        self.max_24h_return = float(os.getenv('MAX_24H_RETURN_BEAR_LONG', '0.40'))
        self.min_depth_10k = float(os.getenv('MIN_DEPTH_10K_BEAR_LONG', '10000'))
        self.max_spread_pct = float(os.getenv('MAX_SPREAD_PCT_BEAR_LONG', '1.0'))

        if self.enabled:
            print(f"🐻💎 [Bear-Resilient Long Engine] ENABLED")
            print(f"   Risk per trade: {self.risk_per_trade*100:.2f}%")
            print(f"   Max concurrent: {self.max_concurrent}")
            print(f"   Max hold time: {self.max_hold_hours}h")

    def scan_symbol(
        self,
        symbol: str,
        features: Features,
        regime: Regime,
        current_bear_longs: int
    ) -> Optional[Dict[str, Any]]:
        """
        Scan a single symbol for Bear-Resilient Long setup.

        Returns signal dict if all filters pass, None otherwise.
        """
        # Only active in BEAR regime
        if regime != Regime.BEAR:
            return None

        # Check if we have room for more positions
        if current_bear_longs >= self.max_concurrent:
            return None

        # Run all filters
        if not self._check_filters(symbol, features):
            return None

        # Check entry trigger
        if not self._check_entry_trigger(symbol, features):
            return None

        # Calculate stop loss and exit params
        stop_loss_price = self.calculate_stop_loss(features)
        exit_params = self.get_exit_params(features)

        # Build signal - size_usd is calculated by risk_engine using R-based sizing
        signal = {
            'symbol': symbol,
            'direction': 'LONG',
            'engine': 'bear_resilient_long',
            'score': 100,  # All filters passed
            'regime': regime.name,
            'entry_price': features.close,
            'stop_loss': stop_loss_price,
            'take_profit': exit_params['tp1_price'],  # Primary TP
            'take_profit_1': exit_params['tp1_price'],
            'take_profit_2': exit_params['tp2_price'],
            'trailing_distance': exit_params['trailing_distance'],
            'atr_15m': getattr(features, 'atr_15m', features.close * 0.02),
            'max_hold_hours': self.max_hold_hours,
            'timestamp': datetime.now(),
            'reason': 'Bear-resilient long: All filters passed + entry trigger confirmed'
            # NOTE: size_usd calculated by risk_engine using RISK_PER_TRADE_BEAR_LONG
        }

        print(f"🐻💎 [{symbol}] BEAR-RESILIENT LONG SIGNAL!")
        print(f"   Entry: ${features.close:.6f}")
        print(f"   Stop Loss: ${stop_loss_price:.6f} ({((stop_loss_price/features.close - 1)*100):.2f}%)")
        print(f"   TP1 @ 1.5R: ${exit_params['tp1_price']:.6f}")
        print(f"   TP2 @ 2.5R: ${exit_params['tp2_price']:.6f}")

        return signal

    def _check_filters(self, symbol: str, f: Features) -> bool:
        """
        Check all 5 filter groups. ALL must pass.

        1. Trend: trend_ratio_4h >= 1.03, EMA20_4h > EMA50_4h
        2. Outperformance: RS vs BTC > +5%
        3. 24h return sweet spot: +5% to +40%
        4. Volume/liquidity: RVOL >= 1.5, spread <= 1.0%, depth >= $10k
        5. Structure: price_pos_24h 0.5-0.9, 3d_return < +80%, no blowoff
        """

        # Filter 1: Trend
        trend_ratio_4h = getattr(f, 'trend_ratio_4h', 1.0)
        ema20_4h = getattr(f, 'ema20_4h', f.close)
        ema50_4h = getattr(f, 'ema50_4h', f.close)

        if trend_ratio_4h < 1.03:
            return False

        if ema20_4h <= ema50_4h:
            return False

        # Filter 2: Outperformance vs BTC
        rs_vs_btc = self._calculate_rs_vs_btc(symbol, f)
        if rs_vs_btc is None or rs_vs_btc <= 0.05:  # Must be > +5%
            return False

        # Filter 3: 24h return sweet spot
        return_24h = getattr(f, 'return_24h', 0)
        if return_24h < self.min_24h_return or return_24h > self.max_24h_return:
            return False

        # Filter 4: Volume and liquidity
        rvol = getattr(f, 'rvol', 0)
        if rvol < self.min_rvol_15m:
            return False

        spread_pct = getattr(f, 'spread_pct', 999)
        if spread_pct > self.max_spread_pct:
            return False

        depth_10 = getattr(f, 'depth_10', 0)
        if depth_10 < self.min_depth_10k:
            return False

        # Filter 5: Structure
        price_pos_24h = getattr(f, 'price_pos_24h', 0.5)
        if price_pos_24h < 0.5 or price_pos_24h > 0.9:
            return False

        return_3d = getattr(f, 'return_3d', 0)
        if return_3d >= 0.80:  # No parabolic moves > +80% in 3 days
            return False

        # No blowoff candles on 15m
        if not self._check_no_blowoff_candles(f):
            return False

        return True

    def _calculate_rs_vs_btc(self, symbol: str, features: Features) -> Optional[float]:
        """
        Calculate 14-day relative strength vs BTC.

        RS = (symbol_return_14d - btc_return_14d)

        Returns None if cannot calculate.
        """
        # Get symbol 14d return
        symbol_return_14d = getattr(features, 'return_14d', None)
        if symbol_return_14d is None:
            return None

        # Get BTC 14d return from features (should be pre-calculated)
        btc_return_14d = getattr(features, 'btc_return_14d', None)
        if btc_return_14d is None:
            # Fallback: assume 0 if not available
            btc_return_14d = 0

        rs = symbol_return_14d - btc_return_14d
        return rs

    def _check_no_blowoff_candles(self, features: Features) -> bool:
        """
        Check no blowoff candles on 15m (body > 3x ATR).

        A blowoff candle indicates parabolic price action that's likely to reverse.
        We want to avoid catching tops.
        """
        # Get 15m bars
        bars_15m = getattr(features, 'bars_15m', None)
        if bars_15m is None or len(bars_15m) < 20:
            return True  # Cannot check, allow

        # Calculate ATR on 15m
        atr_15m = self._calculate_atr(bars_15m, period=14)
        if atr_15m == 0:
            return True

        # Check last 5 candles for blowoff
        for i in range(-5, 0):
            bar = bars_15m[i]
            body = abs(bar['close'] - bar['open'])

            if body > 3 * atr_15m:
                return False  # Blowoff detected

        return True

    def _calculate_atr(self, bars: list, period: int = 14) -> float:
        """Calculate Average True Range."""
        if len(bars) < period + 1:
            return 0

        trs = []
        for i in range(1, len(bars)):
            high = bars[i]['high']
            low = bars[i]['low']
            prev_close = bars[i-1]['close']

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            trs.append(tr)

        if len(trs) < period:
            return 0

        return np.mean(trs[-period:])

    def _check_entry_trigger(self, symbol: str, features: Features) -> bool:
        """
        Check entry trigger:
        - close > 24h_high * 1.003 (breakout)
        - higher_lows_recent (structure confirmation)
        """
        high_24h = getattr(features, 'high_24h', features.close)

        # Breakout above 24h high
        if features.close <= high_24h * 1.003:
            return False

        # Check for higher lows on recent 15m bars
        if not self._check_higher_lows(features):
            return False

        return True

    def _check_higher_lows(self, features: Features) -> bool:
        """
        Check for higher lows pattern on recent 15m bars.

        Confirms upward structure before entry.
        """
        bars_15m = getattr(features, 'bars_15m', None)
        if bars_15m is None or len(bars_15m) < 10:
            return True  # Cannot check, allow

        # Get last 10 lows
        lows = [bar['low'] for bar in bars_15m[-10:]]

        # Simple check: last 3 swing lows should be ascending
        swing_lows = []
        for i in range(1, len(lows) - 1):
            if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                swing_lows.append(lows[i])

        if len(swing_lows) < 2:
            return True  # Not enough swing lows to check

        # Check if ascending
        return swing_lows[-1] > swing_lows[-2]

    def calculate_position_size(
        self,
        equity: float,
        current_price: float,
        stop_loss_price: float
    ) -> float:
        """
        Calculate position size based on 0.08% risk per trade.

        position_size_usd = (equity * risk_pct) / (entry_price - stop_loss_price) * entry_price
        """
        if stop_loss_price >= current_price:
            return 0

        risk_usd = equity * self.risk_per_trade
        price_risk_pct = (current_price - stop_loss_price) / current_price

        if price_risk_pct <= 0:
            return 0

        position_size_usd = risk_usd / price_risk_pct

        # Cap at reasonable size
        max_position_usd = equity * 0.05  # Max 5% of equity per position
        position_size_usd = min(position_size_usd, max_position_usd)

        return position_size_usd

    def calculate_stop_loss(self, features: Features) -> float:
        """
        Calculate stop loss:
        SL = max(1.5 × ATR15m, swing low)

        Returns stop loss price.
        """
        bars_15m = getattr(features, 'bars_15m', None)
        if bars_15m is None or len(bars_15m) < 20:
            # Fallback: 2% below current price
            return features.close * 0.98

        # Calculate ATR-based stop
        atr_15m = self._calculate_atr(bars_15m, period=14)
        atr_stop = features.close - (1.5 * atr_15m)

        # Find recent swing low (lowest low in last 10 bars)
        recent_lows = [bar['low'] for bar in bars_15m[-10:]]
        swing_low = min(recent_lows)

        # Use the higher of the two (tighter stop)
        stop_loss = max(atr_stop, swing_low)

        # Ensure stop is below entry
        if stop_loss >= features.close:
            stop_loss = features.close * 0.98

        return stop_loss

    def get_exit_params(self, features: Features) -> Dict[str, float]:
        """
        Calculate exit parameters:
        - TP1 @ 1.5R: exit 40%
        - TP2 @ 2.5R: exit 40% (total 80% exited)
        - Trailing: highest - 1.0 × ATR

        Returns dict with tp1_price, tp2_price, trailing_distance.
        """
        stop_loss = self.calculate_stop_loss(features)
        entry = features.close

        # Calculate R (risk per share)
        r = entry - stop_loss

        # TP1 @ 1.5R
        tp1_price = entry + (1.5 * r)

        # TP2 @ 2.5R
        tp2_price = entry + (2.5 * r)

        # Trailing distance = 1.0 × ATR
        bars_15m = getattr(features, 'bars_15m', None)
        if bars_15m is not None and len(bars_15m) >= 20:
            atr_15m = self._calculate_atr(bars_15m, period=14)
            trailing_distance = 1.0 * atr_15m
        else:
            # Fallback: 1% of price
            trailing_distance = entry * 0.01

        return {
            'tp1_price': tp1_price,
            'tp2_price': tp2_price,
            'trailing_distance': trailing_distance
        }


# Global instance
bear_resilient_long_engine = BearResilientLongEngine()
