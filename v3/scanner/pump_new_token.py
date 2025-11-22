#!/usr/bin/env python3
"""
V4.2: New Token Pump Catcher Engine

Catches early pumps on newly listed tokens (3-48h old).
Uses dynamic 20-35% equity allocation based on market activity.

Configuration (from .env):
    ENABLE_PUMP_ENGINE=true
    PUMP_ALLOC_MIN=0.20
    PUMP_ALLOC_MAX=0.35
    PUMP_RISK_PER_TRADE=0.001  # 0.10%
    PUMP_MAX_CONCURRENT=2
    PUMP_MIN_AGE_HOURS=3
    PUMP_MAX_AGE_HOURS=48
    PUMP_MIN_VOLUME_USDT=50000
    PUMP_MIN_RVOL_15M=2.0
    PUMP_MIN_1H_MOMENTUM=0.25
    PUMP_MIN_24H_RETURN=0.30
    PUMP_MAX_24H_RETURN=4.0
    PUMP_MAX_SPREAD_PCT=1.5
    PUMP_MIN_DEPTH_10K=5000
    PUMP_ATR_SL_MULT=1.5
    PUMP_MAX_HOLD_HOURS=6
    PUMP_WR_LOOKBACK=20
    PUMP_WR_MIN=0.40
    PUMP_HOT_MARKET_THRESHOLD=5
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np

from v3.scanner.features import Features
from v3.regime.detector import Regime


@dataclass
class PumpStats:
    """Stats for pump engine health monitoring."""
    trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    recent_trades: List[Dict] = None  # Last N trades for win rate calc

    def __post_init__(self):
        if self.recent_trades is None:
            self.recent_trades = []

    @property
    def win_rate(self) -> float:
        """Calculate win rate from recent trades."""
        if not self.recent_trades:
            return 1.0  # Default to 100% if no trades
        wins = sum(1 for t in self.recent_trades if t.get('pnl', 0) > 0)
        return wins / len(self.recent_trades)

    def add_trade(self, trade: Dict):
        """Add a trade result to history."""
        self.recent_trades.append(trade)
        # Keep only last N trades
        lookback = int(os.getenv('PUMP_WR_LOOKBACK', '20'))
        if len(self.recent_trades) > lookback:
            self.recent_trades = self.recent_trades[-lookback:]


class PumpNewTokenEngine:
    """
    New Token Pump Catcher Engine.

    Detects early momentum on newly listed tokens (3-48h old) and
    allocates a dynamic 20-35% slice of equity for pump trades.

    Uses ultra-strict filters to only catch the highest-quality setups.
    """

    def __init__(self):
        # Enable/disable
        self.enabled = os.getenv('ENABLE_PUMP_ENGINE', 'false').lower() == 'true'

        # Allocation / Capital Slice
        self.alloc_min = float(os.getenv('PUMP_ALLOC_MIN', '0.20'))
        self.alloc_max = float(os.getenv('PUMP_ALLOC_MAX', '0.35'))
        self.risk_per_trade = float(os.getenv('PUMP_RISK_PER_TRADE', '0.001'))
        self.max_concurrent = int(os.getenv('PUMP_MAX_CONCURRENT', '2'))

        # New Token Filters
        self.min_age_hours = int(os.getenv('PUMP_MIN_AGE_HOURS', '3'))
        self.max_age_hours = int(os.getenv('PUMP_MAX_AGE_HOURS', '48'))
        self.min_volume_usdt = float(os.getenv('PUMP_MIN_VOLUME_USDT', '50000'))
        self.min_rvol_15m = float(os.getenv('PUMP_MIN_RVOL_15M', '2.0'))
        self.min_1h_momentum = float(os.getenv('PUMP_MIN_1H_MOMENTUM', '0.25'))
        self.min_24h_return = float(os.getenv('PUMP_MIN_24H_RETURN', '0.30'))
        self.max_24h_return = float(os.getenv('PUMP_MAX_24H_RETURN', '4.0'))
        self.max_spread_pct = float(os.getenv('PUMP_MAX_SPREAD_PCT', '1.5'))
        self.min_depth_10k = float(os.getenv('PUMP_MIN_DEPTH_10K', '5000'))

        # Exit Rules
        self.atr_sl_mult = float(os.getenv('PUMP_ATR_SL_MULT', '1.5'))
        self.max_hold_hours = float(os.getenv('PUMP_MAX_HOLD_HOURS', '6'))

        # Engine Health / Throttle
        self.wr_lookback = int(os.getenv('PUMP_WR_LOOKBACK', '20'))
        self.wr_min = float(os.getenv('PUMP_WR_MIN', '0.40'))
        self.hot_market_threshold = int(os.getenv('PUMP_HOT_MARKET_THRESHOLD', '5'))

        # Stats tracking
        self.stats = PumpStats()

        # Token listing times (symbol -> listing_timestamp)
        self._listing_times: Dict[str, datetime] = {}

        if self.enabled:
            print(f"[Pump Engine] ENABLED")
            print(f"   Allocation: {self.alloc_min*100:.0f}%-{self.alloc_max*100:.0f}%")
            print(f"   Risk per trade: {self.risk_per_trade*100:.2f}%")
            print(f"   Max concurrent: {self.max_concurrent}")
            print(f"   Token age: {self.min_age_hours}h - {self.max_age_hours}h")
            print(f"   Max hold: {self.max_hold_hours}h")

    def calculate_allocation(self, pumps_in_last_hour: int = 0) -> float:
        """
        Calculate dynamic equity allocation for pump engine.

        Base allocation: PUMP_ALLOC_MIN (20%)
        Add +5% for each detected pump (up to PUMP_ALLOC_MAX 35%)

        Args:
            pumps_in_last_hour: Number of pump signals in last hour

        Returns:
            Allocation percentage (0.20 - 0.35)
        """
        # Base allocation
        alloc = self.alloc_min

        # Add 5% per detected pump up to max
        bonus_per_pump = 0.05
        alloc += min(pumps_in_last_hour, 3) * bonus_per_pump

        # Cap at max
        alloc = min(alloc, self.alloc_max)

        return alloc

    def check_engine_health(self) -> bool:
        """
        Check if engine is healthy based on recent win rate.

        If win_rate < PUMP_WR_MIN (40%), engine pauses for 1 hour.

        Returns:
            True if engine is healthy, False if paused
        """
        if len(self.stats.recent_trades) < 5:
            return True  # Not enough trades to judge

        if self.stats.win_rate < self.wr_min:
            print(f"[Pump Engine] PAUSED - Win rate {self.stats.win_rate*100:.1f}% < {self.wr_min*100:.1f}%")
            return False

        return True

    def set_token_listing_time(self, symbol: str, listing_time: datetime):
        """Register a token's listing time."""
        self._listing_times[symbol] = listing_time

    def get_token_age_hours(self, symbol: str, now: datetime = None) -> Optional[float]:
        """
        Get token age in hours since listing.

        Returns None if listing time is unknown.
        """
        if now is None:
            now = datetime.now()

        listing_time = self._listing_times.get(symbol)
        if listing_time is None:
            return None

        age = now - listing_time
        return age.total_seconds() / 3600

    def scan_symbol(
        self,
        symbol: str,
        features: Features,
        regime: Regime,
        current_pump_longs: int,
        pump_equity: float,
        now: datetime = None
    ) -> Optional[Dict[str, Any]]:
        """
        Scan a single symbol for Pump Catcher setup.

        Args:
            symbol: Trading pair
            features: Extracted features
            regime: Current market regime
            current_pump_longs: Number of active pump positions
            pump_equity: Equity allocated to pump engine
            now: Current timestamp

        Returns:
            Signal dict if all filters pass, None otherwise.
        """
        if now is None:
            now = datetime.now()

        # Check engine health
        if not self.check_engine_health():
            return None

        # Check if we have room for more positions
        if current_pump_longs >= self.max_concurrent:
            return None

        # Get token age
        token_age_hours = self.get_token_age_hours(symbol, now)

        # Run all filters
        if not self._check_filters(symbol, features, token_age_hours):
            return None

        # Calculate stop loss and exit params
        stop_loss_price = self.calculate_stop_loss(features)
        exit_params = self.get_exit_params(features)

        # Build signal
        signal = {
            'symbol': symbol,
            'direction': 'LONG',
            'engine': 'pump_long',  # Tag as pump engine trade
            'score': 100,  # All filters passed
            'regime': regime.name,
            'entry_price': features.close,
            'stop_loss': stop_loss_price,
            'take_profit': exit_params['tp1_price'],  # Primary TP
            'take_profit_1': exit_params['tp1_price'],
            'take_profit_2': exit_params['tp2_price'],
            'tp1_pct': 0.40,  # Exit 40% at TP1
            'tp2_pct': 0.40,  # Exit 40% at TP2
            'trailing_pct': 0.20,  # Trailing on remaining 20%
            'trailing_distance': exit_params['trailing_distance'],
            'atr_15m': getattr(features, 'atr_15m', features.close * 0.02),
            'max_hold_hours': self.max_hold_hours,
            'nft_dead_hours': 3.5,  # NFT rule: kill dead pump after 3.5h
            'timestamp': now,
            'token_age_hours': token_age_hours,
            'pump_allocation': pump_equity,
            'reason': 'Pump catcher: New token + high momentum + all filters passed'
        }

        print(f"[Pump Engine] [{symbol}] PUMP SIGNAL!")
        if token_age_hours is not None:
            print(f"   Token age: {token_age_hours:.1f}h")
        print(f"   Entry: ${features.close:.6f}")
        print(f"   Stop Loss: ${stop_loss_price:.6f} ({((stop_loss_price/features.close - 1)*100):.2f}%)")
        print(f"   TP1 @ 1.5R: ${exit_params['tp1_price']:.6f} (exit 40%)")
        print(f"   TP2 @ 3.0R: ${exit_params['tp2_price']:.6f} (exit 40%)")
        print(f"   Trailing: 20% remainder")

        return signal

    def _check_filters(
        self,
        symbol: str,
        f: Features,
        token_age_hours: Optional[float]
    ) -> bool:
        """
        Check all pump filters. ALL must pass.

        Filters:
        1. Token age (if known): 3-48h
        2. Volume: >= $50k 24h
        3. Relative volume: >= 2.0
        4. 1h momentum: >= +25%
        5. 24h return: +30% to +400%
        6. Spread: <= 1.5%
        7. Depth: >= $5k at 10 levels
        8. No blowoff candles
        """

        # Filter 1: Token age (optional - only if we know listing time)
        if token_age_hours is not None:
            if token_age_hours < self.min_age_hours or token_age_hours > self.max_age_hours:
                return False

        # Filter 2: Volume
        volume_24h = getattr(f, 'volume_24h', 0)
        if volume_24h < self.min_volume_usdt:
            return False

        # Filter 3: Relative volume
        rvol = getattr(f, 'rvol', 0)
        if rvol < self.min_rvol_15m:
            return False

        # Filter 4: 1h momentum
        return_1h = getattr(f, 'return_1h', 0)
        if return_1h < self.min_1h_momentum:
            return False

        # Filter 5: 24h return sweet spot
        return_24h = getattr(f, 'return_24h', 0)
        if return_24h < self.min_24h_return or return_24h > self.max_24h_return:
            return False

        # Filter 6: Spread
        spread_pct = getattr(f, 'spread_pct', 999)
        if spread_pct > self.max_spread_pct:
            return False

        # Filter 7: Depth
        depth_10 = getattr(f, 'depth_10', 0)
        if depth_10 < self.min_depth_10k:
            return False

        # Filter 8: No blowoff candles (body > 4x ATR on 15m)
        if not self._check_no_blowoff_candles(f):
            return False

        return True

    def _check_no_blowoff_candles(self, features: Features) -> bool:
        """
        Check no blowoff candles on 15m (body > 4x ATR).

        Blowoff candles indicate tops - we want to avoid.
        """
        bars_15m = getattr(features, 'bars_15m', None)
        if bars_15m is None or len(bars_15m) < 20:
            return True  # Cannot check, allow

        atr_15m = self._calculate_atr(bars_15m, period=14)
        if atr_15m == 0:
            return True

        # Check last 3 candles for blowoff
        for i in range(-3, 0):
            bar = bars_15m[i]
            body = abs(bar['close'] - bar['open'])

            if body > 4 * atr_15m:
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

    def calculate_stop_loss(self, features: Features) -> float:
        """
        Calculate stop loss using ATR.

        SL = entry - (ATR_SL_MULT * ATR15m)
        Default: 1.5 x ATR
        """
        bars_15m = getattr(features, 'bars_15m', None)
        if bars_15m is None or len(bars_15m) < 20:
            # Fallback: 3% below current price
            return features.close * 0.97

        atr_15m = self._calculate_atr(bars_15m, period=14)
        stop_loss = features.close - (self.atr_sl_mult * atr_15m)

        # Ensure stop is below entry
        if stop_loss >= features.close:
            stop_loss = features.close * 0.97

        return stop_loss

    def get_exit_params(self, features: Features) -> Dict[str, float]:
        """
        Calculate exit parameters:
        - TP1 @ 1.5R: exit 40%
        - TP2 @ 3.0R: exit 40%
        - Trailing: 1.0 x ATR on remaining 20%

        Returns dict with tp1_price, tp2_price, trailing_distance.
        """
        stop_loss = self.calculate_stop_loss(features)
        entry = features.close

        # Calculate R (risk per share)
        r = entry - stop_loss

        # TP1 @ 1.5R
        tp1_price = entry + (1.5 * r)

        # TP2 @ 3.0R
        tp2_price = entry + (3.0 * r)

        # Trailing distance = 1.0 x ATR
        bars_15m = getattr(features, 'bars_15m', None)
        if bars_15m is not None and len(bars_15m) >= 20:
            atr_15m = self._calculate_atr(bars_15m, period=14)
            trailing_distance = 1.0 * atr_15m
        else:
            trailing_distance = entry * 0.015  # Fallback: 1.5%

        return {
            'tp1_price': tp1_price,
            'tp2_price': tp2_price,
            'trailing_distance': trailing_distance
        }

    def calculate_position_size(
        self,
        pump_equity: float,
        current_price: float,
        stop_loss_price: float
    ) -> float:
        """
        Calculate position size based on R-based sizing.

        size_usd = (pump_equity * risk_pct) / stop_distance_pct

        Args:
            pump_equity: Equity allocated to pump engine
            current_price: Entry price
            stop_loss_price: Stop loss price

        Returns:
            Position size in USD
        """
        if stop_loss_price >= current_price:
            return 0

        risk_usd = pump_equity * self.risk_per_trade
        price_risk_pct = (current_price - stop_loss_price) / current_price

        if price_risk_pct <= 0:
            return 0

        position_size_usd = risk_usd / price_risk_pct

        # Cap at 20% of pump equity per position
        max_position_usd = pump_equity * 0.20
        position_size_usd = min(position_size_usd, max_position_usd)

        return position_size_usd

    def check_nft_dead_pump(
        self,
        position: Dict,
        current_price: float,
        now: datetime = None
    ) -> bool:
        """
        NFT (No Follow Through) dead pump rule.

        If position is:
        - Held for > 3.5 hours AND
        - PnL is between -1% and +1%

        Then close at market - pump is dead.

        Args:
            position: Position dict with entry_time and entry_price
            current_price: Current market price
            now: Current timestamp

        Returns:
            True if should close (dead pump), False otherwise
        """
        if now is None:
            now = datetime.now()

        entry_time = position.get('entry_time')
        entry_price = position.get('entry_price', 0)

        if entry_time is None or entry_price == 0:
            return False

        # Check hold time
        nft_hours = position.get('nft_dead_hours', 3.5)
        hold_time = (now - entry_time).total_seconds() / 3600

        if hold_time < nft_hours:
            return False

        # Check if flat (between -1% and +1%)
        pnl_pct = (current_price / entry_price - 1)

        if -0.01 <= pnl_pct <= 0.01:
            print(f"[Pump Engine] NFT Rule triggered - Dead pump detected")
            print(f"   Hold time: {hold_time:.1f}h, PnL: {pnl_pct*100:.2f}%")
            return True

        return False


def generate_pump_signals(
    features_list: List[Features],
    engine: PumpNewTokenEngine,
    regime: Regime,
    now: datetime,
    total_equity: float,
    current_pump_longs: int = 0,
    pumps_in_last_hour: int = 0
) -> List[Dict[str, Any]]:
    """
    Generate pump signals from a list of features.

    Args:
        features_list: List of Features objects to scan
        engine: PumpNewTokenEngine instance
        regime: Current market regime
        now: Current timestamp
        total_equity: Total account equity
        current_pump_longs: Number of active pump positions
        pumps_in_last_hour: Number of recent pump signals (for allocation calc)

    Returns:
        List of signal dicts
    """
    if not engine.enabled:
        return []

    # Calculate dynamic allocation
    allocation = engine.calculate_allocation(pumps_in_last_hour)
    pump_equity = total_equity * allocation

    signals = []

    for features in features_list:
        # Skip if we've hit max concurrent
        if current_pump_longs + len(signals) >= engine.max_concurrent:
            break

        signal = engine.scan_symbol(
            symbol=features.symbol,
            features=features,
            regime=regime,
            current_pump_longs=current_pump_longs + len(signals),
            pump_equity=pump_equity,
            now=now
        )

        if signal:
            signals.append(signal)

    return signals


# Global instance
pump_new_token_engine = PumpNewTokenEngine()
