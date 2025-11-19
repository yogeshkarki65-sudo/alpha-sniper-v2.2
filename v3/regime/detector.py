"""
Multi-Signal Regime Detector for Alpha Sniper V3.2

Combines multiple signals to determine market regime:
- BULL: Strong uptrend, favorable for momentum longs
- SIDEWAYS: Choppy, selective trades only
- BEAR: Downtrend, minimal/no longs

Uses hysteresis to prevent whipsaw regime changes.
"""
import os
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
from enum import Enum

from v3.utils.indicators import compute_z_score, ema, compute_realized_volatility
from v3.data.mexc_client import mexc_client


class Regime(Enum):
    """Market regime states"""
    BULL = "BULL"
    SIDEWAYS = "SIDEWAYS"
    BEAR = "BEAR"
    UNKNOWN = "UNKNOWN"


class RegimeDetector:
    """
    Multi-signal regime detection with hysteresis
    """

    def __init__(
        self,
        btc_symbol: str = "BTCUSDT",
        alt_proxy_symbol: str = "ETHUSDT",  # Use ETH as alt proxy since TOTAL3 not available
        z_ret_bull_threshold: float = 0.5,
        z_ret_bear_threshold: float = -0.5,
        alt_strength_threshold: float = 0.0,
        hysteresis_hours: int = 4
    ):
        """
        Args:
            btc_symbol: BTC symbol for regime detection
            alt_proxy_symbol: Proxy for alt market (ETH since TOTAL3 unavailable on MEXC)
            z_ret_bull_threshold: Z-score threshold for bull regime
            z_ret_bear_threshold: Z-score threshold for bear regime
            alt_strength_threshold: Alt outperformance threshold for bull confirmation
            hysteresis_hours: Hours to wait before confirming regime change
        """
        self.btc_symbol = btc_symbol
        self.alt_proxy_symbol = alt_proxy_symbol

        # Thresholds
        self.z_ret_bull_threshold = z_ret_bull_threshold
        self.z_ret_bear_threshold = z_ret_bear_threshold
        self.alt_strength_threshold = alt_strength_threshold
        self.hysteresis_hours = hysteresis_hours

        # State
        self.current_regime = Regime.UNKNOWN
        self.regime_change_pending_since: Optional[datetime] = None
        self.pending_regime: Optional[Regime] = None

        # Historical data cache
        self.btc_data: Optional[pd.DataFrame] = None
        self.alt_data: Optional[pd.DataFrame] = None
        self.last_data_fetch: Optional[datetime] = None

    def _fetch_data(self, force_refresh: bool = False):
        """Fetch BTC and alt data"""
        now = datetime.now()

        # Only fetch every hour unless forced
        if (not force_refresh and
            self.last_data_fetch is not None and
            (now - self.last_data_fetch).total_seconds() < 3600):
            return

        print(f"[Regime] Fetching data for {self.btc_symbol} and {self.alt_proxy_symbol}...")

        # Fetch daily data (need ~180 days for z-score, but MEXC limits to 1000 bars)
        # Use 1d interval, get max available
        self.btc_data = mexc_client.get_klines(self.btc_symbol, interval="1d", limit=1000)
        self.alt_data = mexc_client.get_klines(self.alt_proxy_symbol, interval="1d", limit=1000)

        self.last_data_fetch = now

        if self.btc_data is None or len(self.btc_data) < 30:
            print(f"[Regime] WARNING: Insufficient BTC data")

        if self.alt_data is None or len(self.alt_data) < 30:
            print(f"[Regime] WARNING: Insufficient alt data")

    def _compute_z_return(self) -> float:
        """
        Compute Z-score of BTC returns

        Z = (R_21 - mean_long) / std_long

        Uses 60-day window instead of 180 for faster regime detection
        """
        if self.btc_data is None or len(self.btc_data) < 60:
            return 0.0

        # Daily returns
        returns = self.btc_data['close'].pct_change().fillna(0)

        # Z-score with 21d vs 60d (faster than 180d)
        z_score = compute_z_score(returns, short_window=21, long_window=60)

        return z_score

    def _compute_ema_state(self) -> str:
        """
        EMA crossover state (14d vs 50d)

        Returns: 'BULL', 'BEAR', 'SIDEWAYS'
        """
        if self.btc_data is None or len(self.btc_data) < 50:
            return 'SIDEWAYS'

        ema_14 = ema(self.btc_data['close'], 14).iloc[-1]
        ema_50 = ema(self.btc_data['close'], 50).iloc[-1]

        ratio = ema_14 / ema_50

        if ratio > 1.05:  # 5% above
            return 'BULL'
        elif ratio < 0.95:  # 5% below
            return 'BEAR'
        else:
            return 'SIDEWAYS'

    def _compute_vol_regime(self) -> str:
        """
        Volatility regime

        High vol = caution (treat as sideways/bear)
        Low vol = calm
        """
        if self.btc_data is None or len(self.btc_data) < 30:
            return 'CALM'

        returns = self.btc_data['close'].pct_change().fillna(0)
        realized_vol = compute_realized_volatility(returns, window=30)

        # Historical percentile
        historical_vols = returns.rolling(window=30).std() * np.sqrt(365)
        vol_percentile = (historical_vols < realized_vol).sum() / len(historical_vols) * 100

        if vol_percentile > 70:
            return 'VOLATILE'
        else:
            return 'CALM'

    def _compute_alt_strength(self) -> float:
        """
        Alt relative strength vs BTC

        RS = 21d_return_ALT - 21d_return_BTC

        Positive = alts outperforming
        """
        if self.btc_data is None or self.alt_data is None:
            return 0.0

        if len(self.btc_data) < 21 or len(self.alt_data) < 21:
            return 0.0

        btc_21d_ret = (self.btc_data['close'].iloc[-1] / self.btc_data['close'].iloc[-21] - 1)
        alt_21d_ret = (self.alt_data['close'].iloc[-1] / self.alt_data['close'].iloc[-21] - 1)

        rs_alt = alt_21d_ret - btc_21d_ret

        return rs_alt

    def _vote_regime(self) -> Tuple[Regime, Dict[str, any]]:
        """
        Combine multiple signals to vote on regime

        Returns:
            (regime, signal_details)
        """
        # Get all signals
        z_ret = self._compute_z_return()
        ema_state = self._compute_ema_state()
        vol_regime = self._compute_vol_regime()
        alt_strength = self._compute_alt_strength()

        signals = {
            'z_ret': z_ret,
            'ema_state': ema_state,
            'vol_regime': vol_regime,
            'alt_strength': alt_strength
        }

        # Voting logic
        votes = []

        # Signal 1: Z-score
        if z_ret > self.z_ret_bull_threshold:
            votes.append('BULL')
        elif z_ret < self.z_ret_bear_threshold:
            votes.append('BEAR')
        else:
            votes.append('SIDEWAYS')

        # Signal 2: EMA state
        votes.append(ema_state)

        # Determine regime from votes
        # If high vol, bias toward caution
        if vol_regime == 'VOLATILE':
            if 'BULL' in votes:
                # Downgrade bull to sideways in high vol
                regime = Regime.SIDEWAYS
            else:
                regime = Regime.BEAR
        else:
            # Normal voting
            bull_votes = votes.count('BULL')
            bear_votes = votes.count('BEAR')

            if bull_votes >= 1 and alt_strength > self.alt_strength_threshold:
                # Bull confirmed by alt strength
                regime = Regime.BULL
            elif bear_votes >= 2:
                regime = Regime.BEAR
            else:
                regime = Regime.SIDEWAYS

        return regime, signals

    def _apply_hysteresis(self, new_regime: Regime) -> Regime:
        """
        Apply hysteresis to prevent rapid regime flips

        Regime change must persist for hysteresis_hours before confirming
        """
        now = datetime.now()

        # If regime unchanged, reset pending
        if new_regime == self.current_regime:
            self.regime_change_pending_since = None
            self.pending_regime = None
            return self.current_regime

        # New regime different from current
        if self.pending_regime != new_regime:
            # Start new pending period
            self.regime_change_pending_since = now
            self.pending_regime = new_regime
            print(f"[Regime] Pending regime change to {new_regime.value}, waiting {self.hysteresis_hours}h for confirmation")
            return self.current_regime

        # Pending regime matches, check if enough time has passed
        hours_pending = (now - self.regime_change_pending_since).total_seconds() / 3600

        if hours_pending >= self.hysteresis_hours:
            # Confirm regime change
            print(f"[Regime] ✅ Regime changed: {self.current_regime.value} → {new_regime.value}")
            self.current_regime = new_regime
            self.regime_change_pending_since = None
            self.pending_regime = None
            return new_regime
        else:
            # Still pending
            print(f"[Regime] Regime change pending ({hours_pending:.1f}h / {self.hysteresis_hours}h)")
            return self.current_regime

    def detect(self, force_refresh: bool = False) -> Tuple[Regime, Dict]:
        """
        Detect current market regime

        Returns:
            (regime, details_dict)

        details_dict contains:
        - z_ret: Z-score of returns
        - ema_state: EMA crossover state
        - vol_regime: Volatility regime
        - alt_strength: Alt relative strength
        - pending_regime: If regime change is pending
        - hours_pending: Hours until regime change confirmation
        """
        # Fetch data
        self._fetch_data(force_refresh=force_refresh)

        # Vote on regime
        new_regime, signals = self._vote_regime()

        # Apply hysteresis
        final_regime = self._apply_hysteresis(new_regime)

        # Prepare details
        details = signals.copy()
        details['regime'] = final_regime.value
        details['pending_regime'] = self.pending_regime.value if self.pending_regime else None

        if self.regime_change_pending_since:
            hours_pending = (datetime.now() - self.regime_change_pending_since).total_seconds() / 3600
            details['hours_pending'] = hours_pending
        else:
            details['hours_pending'] = 0

        return final_regime, details

    def get_risk_multiplier(self) -> float:
        """
        Get risk multiplier based on regime

        BULL: 1.0 (full risk)
        SIDEWAYS: 0.6 (reduced risk)
        BEAR: 0.3 (minimal risk)
        """
        multipliers = {
            Regime.BULL: 1.0,
            Regime.SIDEWAYS: 0.6,
            Regime.BEAR: 0.3,
            Regime.UNKNOWN: 0.3
        }

        return multipliers[self.current_regime]

    def should_trade_longs(self) -> bool:
        """Should we take long positions in this regime?"""
        # In SIM mode, optionally allow trading in BEAR for testing (RISKY!)
        if os.getenv('MODE', 'SIM') == 'SIM':
            if os.getenv('SIM_TRADE_IN_BEAR', 'false').lower() == 'true':
                print("⚠️  [SIM] Trading in ALL regimes (including BEAR) - testing only!")
                return True

        # Normal: Only trade in BULL or SIDEWAYS
        return self.current_regime in [Regime.BULL, Regime.SIDEWAYS]


# Singleton instance
regime_detector = RegimeDetector(
    z_ret_bull_threshold=0.5,
    z_ret_bear_threshold=-0.5,
    alt_strength_threshold=0.0,
    hysteresis_hours=4
)
