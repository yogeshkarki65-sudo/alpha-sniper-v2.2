"""
Alpha Sniper V4.0 - Regime Detector
BULL / SIDEWAYS / BEAR / NEUTRAL

Spec implementation from section B - battle-tested 2019-2024
"""
import os
import pandas as pd
import numpy as np
from typing import Dict, Tuple
from enum import Enum
from datetime import datetime, timedelta


class Regime(Enum):
    """Market regime states"""
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    NEUTRAL = "NEUTRAL"  # Transition state - no new trades


class RegimeDetector:
    """
    Multi-signal regime detector using BTC and ALT proxy

    Combines:
    - Z-score of returns (21d vs 60d)
    - ALT relative strength vs BTC
    - EMA trend confirmation (14 vs 50)
    - Volatility state
    """

    def __init__(
        self,
        lookback_short_days: int = 21,
        lookback_medium_days: int = 60,
        z_bull_threshold: float = 0.5,
        z_bear_threshold: float = -0.5,
        rsalt_threshold: float = 0.0,
        ema_fast: int = 14,
        ema_slow: int = 50
    ):
        """Initialize regime detector with spec parameters"""
        self.lookback_short = lookback_short_days
        self.lookback_medium = lookback_medium_days
        self.z_bull = z_bull_threshold
        self.z_bear = z_bear_threshold
        self.rsalt_threshold = rsalt_threshold
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow

        # Cache
        self.current_regime = Regime.NEUTRAL
        self.last_update = None
        self.regime_details = {}

    def detect(
        self,
        btc_data: pd.DataFrame,
        alt_data: pd.DataFrame,
        force_refresh: bool = False
    ) -> Tuple[Regime, Dict]:
        """
        Detect current market regime

        Args:
            btc_data: DataFrame with columns ['timestamp', 'close'] for BTCUSDT 1d
            alt_data: DataFrame with columns ['timestamp', 'close'] for ALT proxy 1d
            force_refresh: Force recalculation even if cached

        Returns:
            (Regime, details_dict)
        """
        # Check cache (regime updated once per day)
        now = datetime.now()
        if not force_refresh and self.last_update:
            if (now - self.last_update).total_seconds() < 86400:  # 24h
                return self.current_regime, self.regime_details

        if len(btc_data) < self.lookback_medium or len(alt_data) < self.lookback_medium:
            print(f"[Regime] Insufficient data: BTC={len(btc_data)}, ALT={len(alt_data)}")
            return Regime.NEUTRAL, {}

        # 1) Calculate returns
        btc_data = btc_data.copy().sort_values('timestamp')
        alt_data = alt_data.copy().sort_values('timestamp')

        btc_data['ret'] = btc_data['close'].pct_change()
        alt_data['ret'] = alt_data['close'].pct_change()

        # 2) Rolling metrics (last N days)
        latest_idx = -1  # Most recent day

        # R_21 = sum of returns last 21 days
        R_21 = btc_data['ret'].iloc[-self.lookback_short:].sum()

        # R_60 = sum of returns last 60 days
        R_60 = btc_data['ret'].iloc[-self.lookback_medium:].sum()

        # std_60 = std of returns last 60 days
        std_60 = btc_data['ret'].iloc[-self.lookback_medium:].std()

        # Z_ret = (R_21 - (R_60 * 21/60)) / std_60
        expected_21 = R_60 * (self.lookback_short / self.lookback_medium)
        Z_ret = (R_21 - expected_21) / std_60 if std_60 > 0 else 0.0

        # RS_alt_21 = sum(alt returns last 21d) - sum(btc returns last 21d)
        alt_R_21 = alt_data['ret'].iloc[-self.lookback_short:].sum()
        RS_alt_21 = alt_R_21 - R_21

        # 3) EMA trend confirmation
        close_series = btc_data['close']
        ema_fast_val = close_series.ewm(span=self.ema_fast, adjust=False).mean().iloc[-1]
        ema_slow_val = close_series.ewm(span=self.ema_slow, adjust=False).mean().iloc[-1]

        ema_state = +1 if ema_fast_val > ema_slow_val else -1

        # 4) Volatility state
        realized_vol_21 = btc_data['ret'].iloc[-self.lookback_short:].std()

        # Compare to median vol over last year (365d)
        if len(btc_data) >= 365:
            vol_365 = btc_data['ret'].iloc[-365:].rolling(window=self.lookback_short).std()
            vol_median = vol_365.median()
            vol_state = "HIGH" if realized_vol_21 > vol_median else "LOW"
        else:
            vol_state = "UNKNOWN"

        # 5) Regime classification (EXACT SPEC LOGIC)
        regime = self._classify_regime(Z_ret, RS_alt_21, ema_state)

        # Store details
        details = {
            'Z_ret': Z_ret,
            'R_21': R_21,
            'R_60': R_60,
            'RS_alt_21': RS_alt_21,
            'ema_fast': ema_fast_val,
            'ema_slow': ema_slow_val,
            'ema_state': ema_state,
            'vol_state': vol_state,
            'realized_vol_21': realized_vol_21,
            'timestamp': now.isoformat()
        }

        self.current_regime = regime
        self.regime_details = details
        self.last_update = now

        return regime, details

    def _classify_regime(
        self,
        Z_ret: float,
        RS_alt_21: float,
        ema_state: int
    ) -> Regime:
        """
        Classify regime based on signals (EXACT SPEC)

        BULL:
            - Z_ret > REGIME_Z_BULL
            - RS_alt_21 > REGIME_RSALT_THRESHOLD
            - EMA_state = +1

        BEAR:
            - Z_ret < REGIME_Z_BEAR
            - EMA_state = -1

        SIDEWAYS:
            - Else if |Z_ret| <= max(abs(REGIME_Z_BULL), abs(REGIME_Z_BEAR))

        NEUTRAL:
            - Else (transition)
        """
        # BULL check
        if (Z_ret > self.z_bull and
            RS_alt_21 > self.rsalt_threshold and
            ema_state == +1):
            return Regime.BULL

        # BEAR check
        if (Z_ret < self.z_bear and
            ema_state == -1):
            return Regime.BEAR

        # SIDEWAYS check
        z_threshold = max(abs(self.z_bull), abs(self.z_bear))
        if abs(Z_ret) <= z_threshold:
            return Regime.SIDEWAYS

        # NEUTRAL (transition)
        return Regime.NEUTRAL

    def should_trade_longs(self) -> bool:
        """Should we take new long positions?"""
        return self.current_regime in [Regime.BULL, Regime.SIDEWAYS]

    def should_trade_shorts(self) -> bool:
        """Should we take new short positions?"""
        return self.current_regime == Regime.BEAR

    def get_risk_multiplier(self) -> float:
        """Get risk sizing multiplier for current regime"""
        multipliers = {
            Regime.BULL: 1.0,
            Regime.SIDEWAYS: 0.83,  # 0.25% / 0.30%
            Regime.BEAR: 0.40,      # 0.12% / 0.30%
            Regime.NEUTRAL: 0.0     # No trades
        }
        return multipliers.get(self.current_regime, 0.0)

    def get_max_concurrent_longs(self) -> int:
        """Get max concurrent long positions for regime"""
        limits = {
            Regime.BULL: int(os.getenv('MAX_CONCURRENT_LONGS_BULL', 5)),
            Regime.SIDEWAYS: int(os.getenv('MAX_CONCURRENT_LONGS_SIDEWAYS', 3)),
            Regime.BEAR: 0,
            Regime.NEUTRAL: 0
        }
        return limits.get(self.current_regime, 0)

    def get_max_concurrent_shorts(self) -> int:
        """Get max concurrent short positions for regime"""
        limits = {
            Regime.BULL: 0,
            Regime.SIDEWAYS: 0,
            Regime.BEAR: int(os.getenv('MAX_CONCURRENT_SHORTS_BEAR', 2)),
            Regime.NEUTRAL: 0
        }
        return limits.get(self.current_regime, 0)


# Singleton instance
regime_detector = RegimeDetector(
    lookback_short_days=int(os.getenv('REGIME_LOOKBACK_SHORT_DAYS', 21)),
    lookback_medium_days=int(os.getenv('REGIME_LOOKBACK_MEDIUM_DAYS', 60)),
    z_bull_threshold=float(os.getenv('REGIME_Z_BULL', 0.5)),
    z_bear_threshold=float(os.getenv('REGIME_Z_BEAR', -0.5)),
    rsalt_threshold=float(os.getenv('REGIME_RSALT_THRESHOLD', 0.0)),
    ema_fast=int(os.getenv('REGIME_EMA_FAST', 14)),
    ema_slow=int(os.getenv('REGIME_EMA_SLOW', 50))
)
