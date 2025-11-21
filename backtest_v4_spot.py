#!/usr/bin/env python3
"""
Alpha Sniper V4.1 - Spot Backtest Harness (2016-2025)

Simulates the V4.1 strategy using synthetic data that mimics realistic
crypto market conditions with proper regime changes.

Usage:
    python backtest_v4_spot.py
"""

import os
import sys
import random
import math
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import numpy as np

# Seed for reproducibility
random.seed(42)
np.random.seed(42)


class Regime(Enum):
    BULL = "BULL"
    SIDEWAYS = "SIDEWAYS"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"


@dataclass
class SyntheticBar:
    """OHLCV bar for synthetic data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class SyntheticCoin:
    """Synthetic coin with OHLCV history."""
    symbol: str
    bars_15m: List[SyntheticBar] = field(default_factory=list)
    bars_1h: List[SyntheticBar] = field(default_factory=list)
    bars_4h: List[SyntheticBar] = field(default_factory=list)

    # Current state
    price: float = 1.0
    volume_24h: float = 500000.0
    return_24h: float = 0.0
    return_3d: float = 0.0
    rvol: float = 1.0
    trend_ratio_4h: float = 1.0
    spread_pct: float = 0.3
    depth_10: float = 50000.0
    atr_15m: float = 0.02
    price_pos_24h: float = 0.5


@dataclass
class Position:
    """Open position tracker."""
    symbol: str
    direction: str
    entry_price: float
    size_usd: float
    stop_loss: float
    initial_risk_usd: float
    take_profit: float
    engine: str
    regime: str
    score: int
    atr_15m: float
    entry_time: datetime
    highest_price: float = 0.0
    tp1_hit: bool = False
    tp2_hit: bool = False
    sl_moved_to_be: bool = False
    remaining_pct: float = 100.0


@dataclass
class Trade:
    """Completed trade record."""
    symbol: str
    direction: str
    engine: str
    regime: str
    entry_price: float
    exit_price: float
    size_usd: float
    pnl_usd: float
    pnl_pct: float
    r_multiple: float
    hold_hours: float
    exit_reason: str
    entry_time: datetime
    exit_time: datetime


class SyntheticDataGenerator:
    """Generates realistic crypto market data with regime changes."""

    # Historical regime patterns (approximate based on BTC history)
    REGIME_PATTERNS = {
        2016: [(Regime.SIDEWAYS, 0.3), (Regime.BULL, 0.5), (Regime.SIDEWAYS, 0.2)],
        2017: [(Regime.BULL, 0.8), (Regime.SIDEWAYS, 0.15), (Regime.BEAR, 0.05)],
        2018: [(Regime.BEAR, 0.7), (Regime.SIDEWAYS, 0.2), (Regime.NEUTRAL, 0.1)],
        2019: [(Regime.SIDEWAYS, 0.4), (Regime.BULL, 0.4), (Regime.SIDEWAYS, 0.2)],
        2020: [(Regime.BEAR, 0.1), (Regime.SIDEWAYS, 0.3), (Regime.BULL, 0.6)],
        2021: [(Regime.BULL, 0.6), (Regime.SIDEWAYS, 0.2), (Regime.BEAR, 0.2)],
        2022: [(Regime.BEAR, 0.6), (Regime.SIDEWAYS, 0.3), (Regime.NEUTRAL, 0.1)],
        2023: [(Regime.SIDEWAYS, 0.5), (Regime.BULL, 0.4), (Regime.SIDEWAYS, 0.1)],
        2024: [(Regime.BULL, 0.5), (Regime.SIDEWAYS, 0.3), (Regime.BULL, 0.2)],
        2025: [(Regime.SIDEWAYS, 0.4), (Regime.BULL, 0.4), (Regime.SIDEWAYS, 0.2)],
    }

    def __init__(self):
        self.current_regime = Regime.SIDEWAYS
        self.coins: Dict[str, SyntheticCoin] = {}
        self.universe_size = 50  # Top gainers to scan

    def get_regime_for_date(self, dt: datetime) -> Regime:
        """Get regime based on historical patterns."""
        year = dt.year
        if year not in self.REGIME_PATTERNS:
            year = 2025  # Default

        patterns = self.REGIME_PATTERNS[year]
        day_of_year = dt.timetuple().tm_yday
        year_progress = day_of_year / 365.0

        cumulative = 0.0
        for regime, weight in patterns:
            cumulative += weight
            if year_progress <= cumulative:
                return regime
        return patterns[-1][0]

    def generate_coin_features(self, regime: Regime) -> Dict[str, SyntheticCoin]:
        """Generate synthetic coins based on current regime."""
        coins = {}

        # Number of coins showing momentum varies by regime
        if regime == Regime.BULL:
            momentum_coins = random.randint(15, 30)
            avg_return = 0.08
            return_std = 0.06
        elif regime == Regime.SIDEWAYS:
            momentum_coins = random.randint(8, 20)
            avg_return = 0.03
            return_std = 0.04
        elif regime == Regime.BEAR:
            momentum_coins = random.randint(3, 10)
            avg_return = -0.02
            return_std = 0.05
        else:  # NEUTRAL
            momentum_coins = random.randint(2, 8)
            avg_return = 0.01
            return_std = 0.03

        for i in range(self.universe_size):
            symbol = f"COIN{i:03d}USDT"
            coin = SyntheticCoin(symbol=symbol)

            # Generate features
            is_momentum = i < momentum_coins

            if is_momentum:
                coin.return_24h = max(0.05, np.random.normal(avg_return + 0.10, return_std))
                coin.return_3d = coin.return_24h * np.random.uniform(1.5, 3.0)
                coin.rvol = np.random.uniform(1.2, 3.0)
                coin.trend_ratio_4h = np.random.uniform(1.01, 1.05)
                coin.price_pos_24h = np.random.uniform(0.7, 0.95)
            else:
                coin.return_24h = np.random.normal(avg_return, return_std)
                coin.return_3d = coin.return_24h * np.random.uniform(0.8, 2.0)
                coin.rvol = np.random.uniform(0.5, 1.5)
                coin.trend_ratio_4h = np.random.uniform(0.98, 1.02)
                coin.price_pos_24h = np.random.uniform(0.3, 0.7)

            # Common features
            coin.price = np.random.uniform(0.001, 100.0)
            coin.volume_24h = np.random.uniform(100000, 5000000)
            coin.spread_pct = np.random.uniform(0.1, 1.5)
            coin.depth_10 = np.random.uniform(5000, 100000)
            coin.atr_15m = coin.price * np.random.uniform(0.015, 0.04)

            coins[symbol] = coin

        return coins


class V4BacktestEngine:
    """V4.1 Backtest Engine - Spot Only."""

    def __init__(self, config: dict = None):
        self.config = config or {}

        # V4.1.1 Tuned Parameters
        self.min_score = self.config.get('MIN_SIGNAL_SCORE', 80)
        self.min_rvol_bull = self.config.get('MIN_RVOL_15M_BULL', 1.15)
        self.trend_ratio_cutoff = self.config.get('TREND_RATIO_4H_CUTOFF', 1.008)
        self.atr_sl_mult = self.config.get('ATR_SL_MULT_LONG', 1.9)
        self.perfect_storm_boost = self.config.get('PERFECT_STORM_SCORE_BOOST', 0.17)
        self.max_spread_pct = self.config.get('MAX_ALLOWED_SPREAD_PCT', 1.1)
        self.min_rvol_bear_short = self.config.get('MIN_RVOL_15M_BEAR_SHORT', 1.25)

        # Risk parameters
        self.risk_per_trade = {
            'BULL': self.config.get('RISK_PER_TRADE_BULL', 0.003),
            'SIDEWAYS': self.config.get('RISK_PER_TRADE_SIDEWAYS', 0.0025),
            'BEAR_SHORT': self.config.get('RISK_PER_TRADE_BEAR_SHORT', 0.0012),
            'BEAR_LONG': self.config.get('RISK_PER_TRADE_BEAR_LONG', 0.0008),
        }
        self.max_portfolio_heat = self.config.get('MAX_PORTFOLIO_HEAT', 0.015)
        self.max_concurrent = self.config.get('MAX_CONCURRENT_POSITIONS', 5)

        # State
        self.equity = self.config.get('STARTING_EQUITY', 500.0)
        self.starting_equity = self.equity
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.peak_equity = self.equity
        self.max_drawdown = 0.0

        # Data generator
        self.data_gen = SyntheticDataGenerator()

    def score_long_signal(self, coin: SyntheticCoin, regime: Regime) -> Tuple[int, str]:
        """Score a potential long signal using V4.1.1 logic."""
        # Hard reject if spread too wide
        if coin.spread_pct > self.max_spread_pct:
            return 0, "spread_reject"

        score = 0

        # Momentum (0-30)
        if coin.return_24h > 0.05:
            score += 15
        if coin.return_3d > 0.10:
            score += 15

        # Trend (0-25)
        if coin.trend_ratio_4h >= self.trend_ratio_cutoff:
            score += 10
        if coin.trend_ratio_4h >= 1.01:  # EMA20 > EMA50
            score += 15

        # Trend ratio bonus
        if coin.trend_ratio_4h >= self.trend_ratio_cutoff:
            score += 5

        # Volume (0-20)
        if coin.rvol >= self.min_rvol_bull:
            score += 20

        # Liquidity (0-15)
        if coin.spread_pct < 0.5:
            score += 10
        if coin.depth_10 > 10000:
            score += 5

        # Structure (0-10)
        if 0.7 < coin.price_pos_24h < 0.95:
            score += 10

        # Perfect storm boost
        if (coin.trend_ratio_4h >= 1.02 and
            coin.rvol >= 2.0 and
            coin.return_24h > 0.08 and
            coin.price_pos_24h > 0.75):
            bonus = int(score * self.perfect_storm_boost)
            score += bonus

        return score, "standard_long"

    def score_short_signal(self, coin: SyntheticCoin, regime: Regime) -> Tuple[int, str]:
        """Score a potential short signal (SPOT market - disabled)."""
        # SPOT market cannot short
        return 0, "spot_no_short"

    def calculate_position_size(self, coin: SyntheticCoin, regime: Regime, engine: str) -> Tuple[float, float, float]:
        """Calculate R-based position size. Returns (size_usd, risk_usd, stop_loss)."""
        # Get risk per trade
        if engine == 'bear_resilient_long':
            risk_pct = self.risk_per_trade['BEAR_LONG']
        elif engine == 'standard_short':
            risk_pct = self.risk_per_trade['BEAR_SHORT']
        elif regime == Regime.BULL:
            risk_pct = self.risk_per_trade['BULL']
        else:
            risk_pct = self.risk_per_trade['SIDEWAYS']

        # ATR-based stop loss
        stop_distance = self.atr_sl_mult * coin.atr_15m
        stop_loss = coin.price - stop_distance

        # Clamp stop to 1-5%
        min_stop = coin.price * 0.95
        max_stop = coin.price * 0.99
        stop_loss = max(min_stop, min(max_stop, stop_loss))

        # Calculate risk and size
        stop_pct = (coin.price - stop_loss) / coin.price
        risk_usd = self.equity * risk_pct
        size_usd = risk_usd / stop_pct

        # Cap size at 20% of equity
        max_size = self.equity * 0.20
        if size_usd > max_size:
            size_usd = max_size
            risk_usd = size_usd * stop_pct

        return size_usd, risk_usd, stop_loss

    def get_portfolio_heat(self) -> float:
        """Calculate current portfolio heat in R-terms."""
        total_risk = sum(pos.initial_risk_usd for pos in self.positions.values())
        return total_risk / self.equity if self.equity > 0 else 0

    def can_open_position(self, symbol: str, risk_usd: float) -> Tuple[bool, str]:
        """Check if we can open a new position."""
        if symbol in self.positions:
            return False, "already_open"

        if len(self.positions) >= self.max_concurrent:
            return False, "max_positions"

        current_heat = self.get_portfolio_heat()
        new_heat = risk_usd / self.equity

        if current_heat + new_heat > self.max_portfolio_heat:
            return False, "heat_limit"

        return True, "ok"

    def open_position(self, coin: SyntheticCoin, regime: Regime, score: int,
                      engine: str, current_time: datetime):
        """Open a new position."""
        size_usd, risk_usd, stop_loss = self.calculate_position_size(coin, regime, engine)

        can_open, reason = self.can_open_position(coin.symbol, risk_usd)
        if not can_open:
            return None

        # Take profit at 2:1 R:R
        stop_pct = (coin.price - stop_loss) / coin.price
        take_profit = coin.price * (1 + 2 * stop_pct)

        position = Position(
            symbol=coin.symbol,
            direction='LONG',
            entry_price=coin.price,
            size_usd=size_usd,
            stop_loss=stop_loss,
            initial_risk_usd=risk_usd,
            take_profit=take_profit,
            engine=engine,
            regime=regime.name,
            score=score,
            atr_15m=coin.atr_15m,
            entry_time=current_time,
            highest_price=coin.price
        )

        self.positions[coin.symbol] = position
        return position

    def update_position(self, position: Position, current_price: float,
                        current_time: datetime) -> Optional[Trade]:
        """Update position and check for exits. Returns Trade if closed."""
        # Update highest price
        if current_price > position.highest_price:
            position.highest_price = current_price

        hours_held = (current_time - position.entry_time).total_seconds() / 3600

        # Calculate R-multiple
        r_value = (position.entry_price - position.stop_loss) / position.entry_price
        pnl_pct = (current_price - position.entry_price) / position.entry_price
        r_multiple = pnl_pct / r_value if r_value > 0 else 0

        exit_reason = None
        exit_pct = 0

        # Stop loss check
        if current_price <= position.stop_loss:
            exit_reason = "stop_loss"
            exit_pct = 100

        # Multi-TP for standard_long
        elif position.engine == 'standard_long':
            # TP1 @ 1.5R
            if not position.tp1_hit and r_multiple >= 1.5:
                position.tp1_hit = True
                position.sl_moved_to_be = True
                position.stop_loss = position.entry_price
                position.remaining_pct = 60
                exit_reason = "tp1_partial"
                exit_pct = 40

            # TP2 @ 3R
            elif position.tp1_hit and not position.tp2_hit and r_multiple >= 3.0:
                position.tp2_hit = True
                position.remaining_pct = 20
                exit_reason = "tp2_partial"
                exit_pct = 67  # 40/60 of remaining

            # Trailing stop after TP2
            elif position.tp2_hit:
                trailing_stop = position.highest_price - (1.5 * position.atr_15m)
                if current_price <= trailing_stop:
                    exit_reason = "trailing_stop"
                    exit_pct = 100

            # NFT rule: dead trade after 3.5h
            if exit_reason is None and hours_held >= 3.5:
                mfe_pct = (position.highest_price - position.entry_price) / position.entry_price
                mfe_r = mfe_pct / r_value if r_value > 0 else 0
                if mfe_r < 0.5 and -0.5 <= r_multiple <= 0.2:
                    exit_reason = "nft_rule"
                    exit_pct = 100

            # Max hold time
            if exit_reason is None and hours_held >= 72:
                exit_reason = "max_hold"
                exit_pct = 100

        # Take profit for other engines
        elif current_price >= position.take_profit:
            exit_reason = "take_profit"
            exit_pct = 100

        # Max hold time (fallback)
        elif hours_held >= 72:
            exit_reason = "max_hold"
            exit_pct = 100

        if exit_reason and exit_pct > 0:
            return self.close_position(position, current_price, exit_reason,
                                       exit_pct, current_time)

        return None

    def close_position(self, position: Position, exit_price: float,
                       reason: str, exit_pct: float, current_time: datetime) -> Trade:
        """Close a position (fully or partially)."""
        pnl_pct = (exit_price - position.entry_price) / position.entry_price

        # Calculate size being closed
        remaining_size = position.size_usd * (position.remaining_pct / 100)
        closing_size = remaining_size * (exit_pct / 100)
        pnl_usd = closing_size * pnl_pct

        # R-multiple
        r_value = (position.entry_price - position.stop_loss) / position.entry_price
        r_multiple = pnl_pct / r_value if r_value > 0 else 0

        hours_held = (current_time - position.entry_time).total_seconds() / 3600

        trade = Trade(
            symbol=position.symbol,
            direction=position.direction,
            engine=position.engine,
            regime=position.regime,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size_usd=closing_size,
            pnl_usd=pnl_usd,
            pnl_pct=pnl_pct * 100,
            r_multiple=r_multiple,
            hold_hours=hours_held,
            exit_reason=reason,
            entry_time=position.entry_time,
            exit_time=current_time
        )

        self.trades.append(trade)

        # Update equity
        self.equity += pnl_usd

        # Track drawdown
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
        current_dd = (self.peak_equity - self.equity) / self.peak_equity
        if current_dd > self.max_drawdown:
            self.max_drawdown = current_dd

        # Remove position if fully closed
        if exit_pct >= 100 or position.remaining_pct <= 0.01:
            del self.positions[position.symbol]
        else:
            position.remaining_pct = position.remaining_pct * (1 - exit_pct / 100)

        return trade

    def simulate_price_evolution(self, entry_price: float, regime: Regime,
                                  hours: int) -> List[float]:
        """Simulate price evolution for a position."""
        prices = [entry_price]
        price = entry_price

        # Volatility and drift based on regime
        if regime == Regime.BULL:
            drift = 0.0003  # Positive drift
            vol = 0.02
        elif regime == Regime.SIDEWAYS:
            drift = 0.0001
            vol = 0.015
        elif regime == Regime.BEAR:
            drift = -0.0001
            vol = 0.025
        else:
            drift = 0
            vol = 0.012

        for _ in range(hours):
            change = np.random.normal(drift, vol)
            price = price * (1 + change)
            prices.append(price)

        return prices

    def run_scan_cycle(self, current_time: datetime, regime: Regime):
        """Run a single scan cycle."""
        # Generate synthetic coins
        coins = self.data_gen.generate_coin_features(regime)

        # Update existing positions first
        positions_to_check = list(self.positions.values())
        for position in positions_to_check:
            if position.symbol not in coins:
                # Generate a synthetic price for the position
                hours = int((current_time - position.entry_time).total_seconds() / 3600)
                prices = self.simulate_price_evolution(position.entry_price,
                                                        Regime[position.regime], hours)
                current_price = prices[-1] if prices else position.entry_price
            else:
                coin = coins[position.symbol]
                # Simulate some price movement from entry
                hours = max(1, int((current_time - position.entry_time).total_seconds() / 3600))
                prices = self.simulate_price_evolution(position.entry_price,
                                                        Regime[position.regime], hours)
                current_price = prices[-1]

            self.update_position(position, current_price, current_time)

        # Only trade longs in BULL/SIDEWAYS (SPOT)
        if regime not in [Regime.BULL, Regime.SIDEWAYS]:
            return

        # Score and rank signals
        signals = []
        for symbol, coin in coins.items():
            if symbol in self.positions:
                continue

            score, engine = self.score_long_signal(coin, regime)
            if score >= self.min_score:
                signals.append((score, coin, engine))

        # Sort by score and take best
        signals.sort(key=lambda x: x[0], reverse=True)

        for score, coin, engine in signals[:3]:  # Max 3 new positions per cycle
            self.open_position(coin, regime, score, engine, current_time)

    def run_backtest(self, start_date: datetime, end_date: datetime,
                      scan_interval_hours: float = 1.0):
        """Run full backtest."""
        current_time = start_date
        cycle_count = 0

        print(f"\n{'='*70}")
        print(f"  ALPHA SNIPER V4.1 - SPOT BACKTEST")
        print(f"  Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"  Starting Equity: ${self.starting_equity:.2f}")
        print(f"{'='*70}\n")

        yearly_stats = {}
        current_year = start_date.year
        year_start_equity = self.equity
        year_trades = []

        while current_time < end_date:
            # Check for year change
            if current_time.year != current_year:
                # Record yearly stats
                year_trades_list = [t for t in self.trades if t.entry_time.year == current_year]
                wins = sum(1 for t in year_trades_list if t.pnl_usd > 0)
                wr = (wins / len(year_trades_list) * 100) if year_trades_list else 0
                roi = (self.equity - year_start_equity) / year_start_equity * 100 if year_start_equity > 0 else 0

                yearly_stats[current_year] = {
                    'trades': len(year_trades_list),
                    'wins': wins,
                    'wr': wr,
                    'roi': roi,
                    'end_equity': self.equity
                }

                current_year = current_time.year
                year_start_equity = self.equity

            # Get regime
            regime = self.data_gen.get_regime_for_date(current_time)

            # Run scan cycle
            self.run_scan_cycle(current_time, regime)

            # Advance time (5 min interval = 12 cycles per hour)
            current_time += timedelta(hours=scan_interval_hours)
            cycle_count += 1

            # Progress update
            if cycle_count % 5000 == 0:
                print(f"  {current_time.strftime('%Y-%m-%d')} | Equity: ${self.equity:.2f} | Trades: {len(self.trades)} | Positions: {len(self.positions)}")

        # Final year stats
        year_trades_list = [t for t in self.trades if t.entry_time.year == current_year]
        if year_trades_list:
            wins = sum(1 for t in year_trades_list if t.pnl_usd > 0)
            wr = wins / len(year_trades_list) * 100
            roi = (self.equity - year_start_equity) / year_start_equity * 100 if year_start_equity > 0 else 0
            yearly_stats[current_year] = {
                'trades': len(year_trades_list),
                'wins': wins,
                'wr': wr,
                'roi': roi,
                'end_equity': self.equity
            }

        return yearly_stats

    def print_results(self, yearly_stats: dict):
        """Print backtest results."""
        total_trades = len(self.trades)
        wins = sum(1 for t in self.trades if t.pnl_usd > 0)
        losses = total_trades - wins

        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        avg_win = np.mean([t.pnl_pct for t in self.trades if t.pnl_usd > 0]) if wins > 0 else 0
        avg_loss = np.mean([t.pnl_pct for t in self.trades if t.pnl_usd <= 0]) if losses > 0 else 0

        gross_profit = sum(t.pnl_usd for t in self.trades if t.pnl_usd > 0)
        gross_loss = abs(sum(t.pnl_usd for t in self.trades if t.pnl_usd <= 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        total_roi = (self.equity - self.starting_equity) / self.starting_equity * 100

        print(f"\n{'='*70}")
        print(f"  BACKTEST RESULTS - SPOT ONLY")
        print(f"{'='*70}")
        print(f"\n  Overall Metrics:")
        print(f"  -----------------")
        print(f"  Total Trades:    {total_trades}")
        print(f"  Wins:            {wins} ({win_rate:.1f}%)")
        print(f"  Losses:          {losses}")
        print(f"  Avg Win:         {avg_win:+.2f}%")
        print(f"  Avg Loss:        {avg_loss:+.2f}%")
        print(f"  Profit Factor:   {profit_factor:.2f}")
        print(f"  Max Drawdown:    {self.max_drawdown*100:.2f}%")
        print(f"\n  Equity:")
        print(f"  -----------------")
        print(f"  Starting:        ${self.starting_equity:.2f}")
        print(f"  Final:           ${self.equity:.2f}")
        print(f"  Peak:            ${self.peak_equity:.2f}")
        print(f"  Total ROI:       {total_roi:+.1f}%")

        print(f"\n  Per-Year Breakdown:")
        print(f"  -----------------")
        print(f"  {'Year':<6} {'Trades':<8} {'WR%':<8} {'ROI%':<10} {'End Equity':<12}")
        print(f"  {'-'*50}")
        for year, stats in sorted(yearly_stats.items()):
            print(f"  {year:<6} {stats['trades']:<8} {stats['wr']:<8.1f} {stats['roi']:<+10.1f} ${stats['end_equity']:<12.2f}")

        # Engine breakdown
        print(f"\n  Per-Engine Breakdown:")
        print(f"  -----------------")
        engines = {}
        for t in self.trades:
            if t.engine not in engines:
                engines[t.engine] = {'trades': 0, 'wins': 0, 'pnl': 0}
            engines[t.engine]['trades'] += 1
            if t.pnl_usd > 0:
                engines[t.engine]['wins'] += 1
            engines[t.engine]['pnl'] += t.pnl_usd

        for engine, stats in engines.items():
            wr = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
            print(f"  {engine:<20} Trades: {stats['trades']:<5} WR: {wr:.1f}% PnL: ${stats['pnl']:+.2f}")

        print(f"\n{'='*70}\n")

        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': self.max_drawdown * 100,
            'total_roi': total_roi,
            'final_equity': self.equity,
            'yearly_stats': yearly_stats
        }


def main():
    """Run spot-only backtest."""
    # V4.1.1 Config
    config = {
        'STARTING_EQUITY': 500.0,
        'MIN_SIGNAL_SCORE': 80,
        'MIN_RVOL_15M_BULL': 1.15,
        'TREND_RATIO_4H_CUTOFF': 1.008,
        'ATR_SL_MULT_LONG': 1.9,
        'PERFECT_STORM_SCORE_BOOST': 0.17,
        'MAX_ALLOWED_SPREAD_PCT': 1.1,
        'MIN_RVOL_15M_BEAR_SHORT': 1.25,
        'RISK_PER_TRADE_BULL': 0.003,
        'RISK_PER_TRADE_SIDEWAYS': 0.0025,
        'RISK_PER_TRADE_BEAR_SHORT': 0.0012,
        'RISK_PER_TRADE_BEAR_LONG': 0.0008,
        'MAX_PORTFOLIO_HEAT': 0.015,
        'MAX_CONCURRENT_POSITIONS': 5,
    }

    engine = V4BacktestEngine(config)

    # Run 2016-2025 backtest
    start = datetime(2016, 1, 1)
    end = datetime(2025, 12, 31)

    # ~1 hour scan interval for speed (in real V4.1 it's 5 min)
    yearly_stats = engine.run_backtest(start, end, scan_interval_hours=1.0)

    results = engine.print_results(yearly_stats)

    return results


if __name__ == "__main__":
    results = main()
