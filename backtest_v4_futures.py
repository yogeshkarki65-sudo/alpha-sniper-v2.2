#!/usr/bin/env python3
"""
Alpha Sniper V4.1 - Futures Backtest Harness (2017-2025)

Compares SPOT-only vs SPOT+FUTURES (1x leverage shorts in bear regime).

Usage:
    python backtest_v4_futures.py
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

# Import the spot backtest components
from backtest_v4_spot import (
    Regime, SyntheticBar, SyntheticCoin, Position, Trade,
    SyntheticDataGenerator, V4BacktestEngine
)

# Seed for reproducibility
random.seed(42)
np.random.seed(42)


class V4FuturesBacktestEngine(V4BacktestEngine):
    """V4.1 Backtest Engine with Futures Short capability."""

    def __init__(self, config: dict = None, enable_shorts: bool = True):
        super().__init__(config)
        self.enable_shorts = enable_shorts
        self.market_type = 'FUTURES' if enable_shorts else 'SPOT'

        # Futures-specific config
        self.risk_per_trade_short = self.config.get('RISK_PER_TRADE_BEAR_SHORT_FUTURES', 0.0010)
        self.funding_rate_hourly = self.config.get('FUNDING_RATE_HOURLY', 0.0001)  # 0.01%/hr

        # Track funding costs
        self.total_funding_paid = 0.0

    def score_short_signal(self, coin: SyntheticCoin, regime: Regime) -> Tuple[int, str]:
        """Score a potential short signal for BEAR regime."""
        if not self.enable_shorts:
            return 0, "shorts_disabled"

        if regime != Regime.BEAR:
            return 0, "not_bear_regime"

        # Hard reject if spread too wide
        if coin.spread_pct > self.max_spread_pct:
            return 0, "spread_reject"

        score = 0

        # Negative momentum (0-30)
        if coin.return_24h < -0.03:
            score += 15
        if coin.return_3d < -0.05:
            score += 15

        # Downtrend (0-25)
        if coin.trend_ratio_4h < 0.99:  # EMA20 < EMA50
            score += 10
        if coin.trend_ratio_4h < 0.98:
            score += 15

        # Volume (0-20)
        if coin.rvol >= self.min_rvol_bear_short:
            score += 20

        # Liquidity (0-15)
        if coin.spread_pct < 0.5:
            score += 10
        if coin.depth_10 > 10000:
            score += 5

        # Structure (0-10) - price near lows
        if 0.05 < coin.price_pos_24h < 0.3:
            score += 10

        return score, "standard_short"

    def calculate_short_position_size(self, coin: SyntheticCoin) -> Tuple[float, float, float]:
        """Calculate R-based position size for shorts. Returns (size_usd, risk_usd, stop_loss)."""
        risk_pct = self.risk_per_trade_short

        # ATR-based stop loss (above entry for shorts)
        stop_distance = self.atr_sl_mult * coin.atr_15m
        stop_loss = coin.price + stop_distance

        # Clamp stop to 1-5% above entry
        min_stop = coin.price * 1.01
        max_stop = coin.price * 1.05
        stop_loss = max(min_stop, min(max_stop, stop_loss))

        # Calculate risk and size
        stop_pct = (stop_loss - coin.price) / coin.price
        risk_usd = self.equity * risk_pct
        size_usd = risk_usd / stop_pct

        # Cap size at 10% of equity for shorts (more conservative)
        max_size = self.equity * 0.10
        if size_usd > max_size:
            size_usd = max_size
            risk_usd = size_usd * stop_pct

        return size_usd, risk_usd, stop_loss

    def open_short_position(self, coin: SyntheticCoin, regime: Regime, score: int,
                             engine: str, current_time: datetime):
        """Open a short position (futures only)."""
        size_usd, risk_usd, stop_loss = self.calculate_short_position_size(coin)

        can_open, reason = self.can_open_position(coin.symbol, risk_usd)
        if not can_open:
            return None

        # Take profit at 2:1 R:R (below entry for shorts)
        stop_pct = (stop_loss - coin.price) / coin.price
        take_profit = coin.price * (1 - 2 * stop_pct)

        position = Position(
            symbol=coin.symbol,
            direction='SHORT',
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
            highest_price=coin.price  # For shorts, track lowest
        )

        self.positions[coin.symbol] = position
        return position

    def update_short_position(self, position: Position, current_price: float,
                               current_time: datetime) -> Optional[Trade]:
        """Update short position and check for exits."""
        # Track lowest price (for trailing)
        if current_price < position.highest_price:
            position.highest_price = current_price

        hours_held = (current_time - position.entry_time).total_seconds() / 3600

        # Calculate funding cost
        funding_cost = position.size_usd * self.funding_rate_hourly * hours_held
        self.total_funding_paid += funding_cost

        # Calculate R-multiple for shorts
        r_value = (position.stop_loss - position.entry_price) / position.entry_price
        pnl_pct = (position.entry_price - current_price) / position.entry_price
        r_multiple = pnl_pct / r_value if r_value > 0 else 0

        exit_reason = None
        exit_pct = 0

        # Stop loss check (above entry for shorts)
        if current_price >= position.stop_loss:
            exit_reason = "stop_loss"
            exit_pct = 100

        # TP1 @ 1.5R for shorts
        elif not position.tp1_hit and r_multiple >= 1.5:
            position.tp1_hit = True
            position.sl_moved_to_be = True
            position.stop_loss = position.entry_price  # Move to breakeven
            position.remaining_pct = 60
            exit_reason = "tp1_partial"
            exit_pct = 40

        # TP2 @ 2.5R for shorts (more conservative than longs)
        elif position.tp1_hit and not position.tp2_hit and r_multiple >= 2.5:
            position.tp2_hit = True
            position.remaining_pct = 20
            exit_reason = "tp2_partial"
            exit_pct = 67

        # Trailing stop after TP2
        elif position.tp2_hit:
            trailing_stop = position.highest_price + (1.5 * position.atr_15m)
            if current_price >= trailing_stop:
                exit_reason = "trailing_stop"
                exit_pct = 100

        # NFT rule for shorts
        if exit_reason is None and hours_held >= 3.0:
            mfe_pct = (position.entry_price - position.highest_price) / position.entry_price
            mfe_r = mfe_pct / r_value if r_value > 0 else 0
            if mfe_r < 0.5 and -0.5 <= r_multiple <= 0.2:
                exit_reason = "nft_rule"
                exit_pct = 100

        # Max hold time (shorter for shorts)
        if exit_reason is None and hours_held >= 48:
            exit_reason = "max_hold"
            exit_pct = 100

        # Take profit
        if exit_reason is None and current_price <= position.take_profit:
            exit_reason = "take_profit"
            exit_pct = 100

        if exit_reason and exit_pct > 0:
            return self.close_short_position(position, current_price, exit_reason,
                                              exit_pct, current_time, funding_cost)

        return None

    def close_short_position(self, position: Position, exit_price: float,
                              reason: str, exit_pct: float, current_time: datetime,
                              funding_cost: float = 0) -> Trade:
        """Close a short position."""
        # P&L for shorts (inverted)
        pnl_pct = (position.entry_price - exit_price) / position.entry_price

        # Calculate size being closed
        remaining_size = position.size_usd * (position.remaining_pct / 100)
        closing_size = remaining_size * (exit_pct / 100)
        pnl_usd = closing_size * pnl_pct

        # Deduct funding cost (proportional to closing size)
        funding_deduction = funding_cost * (closing_size / position.size_usd)
        pnl_usd -= funding_deduction

        # R-multiple
        r_value = (position.stop_loss - position.entry_price) / position.entry_price
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

    def run_scan_cycle(self, current_time: datetime, regime: Regime):
        """Run a single scan cycle with futures support."""
        # Generate synthetic coins
        coins = self.data_gen.generate_coin_features(regime)

        # Update existing positions
        positions_to_check = list(self.positions.values())
        for position in positions_to_check:
            hours = max(1, int((current_time - position.entry_time).total_seconds() / 3600))
            prices = self.simulate_price_evolution(position.entry_price,
                                                    Regime[position.regime], hours)
            current_price = prices[-1]

            if position.direction == 'SHORT':
                self.update_short_position(position, current_price, current_time)
            else:
                self.update_position(position, current_price, current_time)

        # === LONG SIGNALS (BULL/SIDEWAYS) ===
        if regime in [Regime.BULL, Regime.SIDEWAYS]:
            signals = []
            for symbol, coin in coins.items():
                if symbol in self.positions:
                    continue
                score, engine = self.score_long_signal(coin, regime)
                if score >= self.min_score:
                    signals.append((score, coin, engine, 'LONG'))

            signals.sort(key=lambda x: x[0], reverse=True)
            for score, coin, engine, direction in signals[:3]:
                self.open_position(coin, regime, score, engine, current_time)

        # === SHORT SIGNALS (BEAR) - FUTURES ONLY ===
        if regime == Regime.BEAR and self.enable_shorts:
            signals = []
            for symbol, coin in coins.items():
                if symbol in self.positions:
                    continue
                score, engine = self.score_short_signal(coin, regime)
                if score >= self.min_score:
                    signals.append((score, coin, engine, 'SHORT'))

            signals.sort(key=lambda x: x[0], reverse=True)
            for score, coin, engine, direction in signals[:2]:  # Max 2 shorts
                self.open_short_position(coin, regime, score, engine, current_time)

        # === BEAR MICRO-LONG (both SPOT and FUTURES) ===
        if regime == Regime.BEAR:
            # Ultra-selective long in bear (bear_resilient_long logic)
            for symbol, coin in coins.items():
                if symbol in self.positions:
                    continue
                # Bear micro-long filters
                if (coin.return_24h > 0.10 and
                    coin.rvol >= 2.0 and
                    coin.trend_ratio_4h >= 1.03 and
                    coin.spread_pct < 0.8 and
                    coin.price_pos_24h > 0.7):

                    # Only 1 bear micro-long at a time
                    bear_longs = sum(1 for p in self.positions.values()
                                     if p.engine == 'bear_resilient_long')
                    if bear_longs == 0:
                        self.open_position(coin, regime, 90, 'bear_resilient_long', current_time)
                        break

    def run_backtest(self, start_date: datetime, end_date: datetime,
                      scan_interval_hours: float = 1.0):
        """Run full backtest."""
        current_time = start_date
        cycle_count = 0

        mode_str = "SPOT + FUTURES" if self.enable_shorts else "SPOT ONLY"
        print(f"\n{'='*70}")
        print(f"  ALPHA SNIPER V4.1 - {mode_str} BACKTEST")
        print(f"  Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"  Starting Equity: ${self.starting_equity:.2f}")
        print(f"{'='*70}\n")

        yearly_stats = {}
        current_year = start_date.year
        year_start_equity = self.equity

        while current_time < end_date:
            # Check for year change
            if current_time.year != current_year:
                year_trades_list = [t for t in self.trades if t.entry_time.year == current_year]
                wins = sum(1 for t in year_trades_list if t.pnl_usd > 0)
                wr = (wins / len(year_trades_list) * 100) if year_trades_list else 0
                roi = (self.equity - year_start_equity) / year_start_equity * 100 if year_start_equity > 0 else 0

                shorts = sum(1 for t in year_trades_list if t.direction == 'SHORT')

                yearly_stats[current_year] = {
                    'trades': len(year_trades_list),
                    'wins': wins,
                    'wr': wr,
                    'roi': roi,
                    'shorts': shorts,
                    'end_equity': self.equity
                }

                current_year = current_time.year
                year_start_equity = self.equity

            regime = self.data_gen.get_regime_for_date(current_time)
            self.run_scan_cycle(current_time, regime)

            current_time += timedelta(hours=scan_interval_hours)
            cycle_count += 1

            if cycle_count % 5000 == 0:
                print(f"  {current_time.strftime('%Y-%m-%d')} | Equity: ${self.equity:.2f} | Trades: {len(self.trades)} | Positions: {len(self.positions)}")

        # Final year stats
        year_trades_list = [t for t in self.trades if t.entry_time.year == current_year]
        if year_trades_list:
            wins = sum(1 for t in year_trades_list if t.pnl_usd > 0)
            wr = wins / len(year_trades_list) * 100
            roi = (self.equity - year_start_equity) / year_start_equity * 100 if year_start_equity > 0 else 0
            shorts = sum(1 for t in year_trades_list if t.direction == 'SHORT')
            yearly_stats[current_year] = {
                'trades': len(year_trades_list),
                'wins': wins,
                'wr': wr,
                'roi': roi,
                'shorts': shorts,
                'end_equity': self.equity
            }

        return yearly_stats

    def print_results(self, yearly_stats: dict):
        """Print backtest results with futures details."""
        total_trades = len(self.trades)
        wins = sum(1 for t in self.trades if t.pnl_usd > 0)
        losses = total_trades - wins

        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        long_trades = [t for t in self.trades if t.direction == 'LONG']
        short_trades = [t for t in self.trades if t.direction == 'SHORT']

        avg_win = np.mean([t.pnl_pct for t in self.trades if t.pnl_usd > 0]) if wins > 0 else 0
        avg_loss = np.mean([t.pnl_pct for t in self.trades if t.pnl_usd <= 0]) if losses > 0 else 0

        gross_profit = sum(t.pnl_usd for t in self.trades if t.pnl_usd > 0)
        gross_loss = abs(sum(t.pnl_usd for t in self.trades if t.pnl_usd <= 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        total_roi = (self.equity - self.starting_equity) / self.starting_equity * 100

        mode_str = "SPOT + FUTURES" if self.enable_shorts else "SPOT ONLY"
        print(f"\n{'='*70}")
        print(f"  BACKTEST RESULTS - {mode_str}")
        print(f"{'='*70}")
        print(f"\n  Overall Metrics:")
        print(f"  -----------------")
        print(f"  Total Trades:    {total_trades} ({len(long_trades)} longs, {len(short_trades)} shorts)")
        print(f"  Wins:            {wins} ({win_rate:.1f}%)")
        print(f"  Losses:          {losses}")
        print(f"  Avg Win:         {avg_win:+.2f}%")
        print(f"  Avg Loss:        {avg_loss:+.2f}%")
        print(f"  Profit Factor:   {profit_factor:.2f}")
        print(f"  Max Drawdown:    {self.max_drawdown*100:.2f}%")

        if self.enable_shorts:
            print(f"\n  Futures Specific:")
            print(f"  -----------------")
            print(f"  Total Funding Paid: ${self.total_funding_paid:.2f}")

            # Short-specific stats
            if short_trades:
                short_wins = sum(1 for t in short_trades if t.pnl_usd > 0)
                short_wr = short_wins / len(short_trades) * 100
                short_pnl = sum(t.pnl_usd for t in short_trades)
                print(f"  Short Trades:       {len(short_trades)}")
                print(f"  Short Win Rate:     {short_wr:.1f}%")
                print(f"  Short Total PnL:    ${short_pnl:+.2f}")

        print(f"\n  Equity:")
        print(f"  -----------------")
        print(f"  Starting:        ${self.starting_equity:.2f}")
        print(f"  Final:           ${self.equity:.2f}")
        print(f"  Peak:            ${self.peak_equity:.2f}")
        print(f"  Total ROI:       {total_roi:+.1f}%")

        print(f"\n  Per-Year Breakdown:")
        print(f"  -----------------")
        print(f"  {'Year':<6} {'Trades':<8} {'Shorts':<8} {'WR%':<8} {'ROI%':<10} {'End Equity':<12}")
        print(f"  {'-'*58}")
        for year, stats in sorted(yearly_stats.items()):
            print(f"  {year:<6} {stats['trades']:<8} {stats.get('shorts', 0):<8} {stats['wr']:<8.1f} {stats['roi']:<+10.1f} ${stats['end_equity']:<12.2f}")

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
            'long_trades': len(long_trades),
            'short_trades': len(short_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': self.max_drawdown * 100,
            'total_roi': total_roi,
            'final_equity': self.equity,
            'funding_paid': self.total_funding_paid,
            'yearly_stats': yearly_stats
        }


def run_comparison():
    """Run side-by-side comparison of SPOT vs SPOT+FUTURES."""
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
        'RISK_PER_TRADE_BEAR_SHORT_FUTURES': 0.0010,  # 0.10% for futures shorts
        'FUNDING_RATE_HOURLY': 0.0001,  # 0.01%/hr
        'MAX_PORTFOLIO_HEAT': 0.015,
        'MAX_CONCURRENT_POSITIONS': 5,
    }

    # Period: 2017-2025 (futures existed from 2017)
    start = datetime(2017, 1, 1)
    end = datetime(2025, 12, 31)

    print("\n" + "=" * 70)
    print("  ALPHA SNIPER V4.1 - SPOT vs FUTURES COMPARISON")
    print("  Period: 2017-2025 (9 years)")
    print("=" * 70)

    # Run SPOT-only
    print("\n>>> Running SPOT-only backtest...")
    random.seed(42)
    np.random.seed(42)
    spot_engine = V4FuturesBacktestEngine(config, enable_shorts=False)
    spot_yearly = spot_engine.run_backtest(start, end, scan_interval_hours=1.0)
    spot_results = spot_engine.print_results(spot_yearly)

    # Run SPOT+FUTURES
    print("\n>>> Running SPOT+FUTURES backtest...")
    random.seed(42)
    np.random.seed(42)
    futures_engine = V4FuturesBacktestEngine(config, enable_shorts=True)
    futures_yearly = futures_engine.run_backtest(start, end, scan_interval_hours=1.0)
    futures_results = futures_engine.print_results(futures_yearly)

    # Comparison summary
    print("\n" + "=" * 70)
    print("  COMPARISON SUMMARY")
    print("=" * 70)
    print(f"\n  {'Metric':<25} {'SPOT Only':<15} {'SPOT+FUTURES':<15} {'Delta':<15}")
    print(f"  {'-'*70}")

    metrics = [
        ('Total Trades', 'total_trades', '{:.0f}'),
        ('Win Rate (%)', 'win_rate', '{:.1f}'),
        ('Profit Factor', 'profit_factor', '{:.2f}'),
        ('Max Drawdown (%)', 'max_drawdown', '{:.2f}'),
        ('Total ROI (%)', 'total_roi', '{:.1f}'),
        ('Final Equity ($)', 'final_equity', '{:.2f}'),
    ]

    for label, key, fmt in metrics:
        spot_val = spot_results[key]
        fut_val = futures_results[key]
        delta = fut_val - spot_val
        delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"
        print(f"  {label:<25} {fmt.format(spot_val):<15} {fmt.format(fut_val):<15} {delta_str:<15}")

    print(f"\n  Short Trades (Futures):  {futures_results['short_trades']}")
    print(f"  Funding Paid (Futures):  ${futures_results['funding_paid']:.2f}")

    # Per-regime analysis
    print(f"\n  Bear Year Performance (2018, 2022):")
    print(f"  {'-'*50}")
    for year in [2018, 2022]:
        if year in spot_yearly and year in futures_yearly:
            spot_yr = spot_yearly[year]
            fut_yr = futures_yearly[year]
            print(f"  {year}:")
            print(f"    SPOT:    ROI {spot_yr['roi']:+.1f}%, WR {spot_yr['wr']:.1f}%, Trades {spot_yr['trades']}")
            print(f"    FUTURES: ROI {fut_yr['roi']:+.1f}%, WR {fut_yr['wr']:.1f}%, Trades {fut_yr['trades']} ({fut_yr.get('shorts', 0)} shorts)")

    # Verdict
    print(f"\n{'='*70}")
    print("  VERDICT")
    print(f"{'='*70}")

    spot_safe = spot_results['max_drawdown'] < 15 and spot_results['profit_factor'] >= 1.5
    futures_safe = futures_results['max_drawdown'] < 15 and futures_results['profit_factor'] >= 1.5
    futures_better = (futures_results['total_roi'] > spot_results['total_roi'] and
                      futures_results['max_drawdown'] <= spot_results['max_drawdown'] * 1.2)

    print(f"\n  SPOT-only V4.1:")
    print(f"    - PF {spot_results['profit_factor']:.2f}, DD {spot_results['max_drawdown']:.1f}%")
    print(f"    - Status: {'SAFE' if spot_safe else 'CAUTION'}")

    print(f"\n  SPOT+FUTURES V4.1:")
    print(f"    - PF {futures_results['profit_factor']:.2f}, DD {futures_results['max_drawdown']:.1f}%")
    print(f"    - Status: {'SAFE' if futures_safe else 'CAUTION'}")
    print(f"    - Improvement: {'YES' if futures_better else 'NO'}")

    print(f"\n  Recommendation:")
    if futures_safe and futures_better:
        print(f"    ENABLE futures shorts in LIVE with:")
        print(f"      - 1x leverage")
        print(f"      - 0.10% risk/trade for shorts")
        print(f"      - Same safety rails as SPOT")
    elif spot_safe:
        print(f"    KEEP using SPOT-only V4.1 in LIVE.")
        print(f"    Futures shorts provide marginal benefit with added complexity.")
    else:
        print(f"    REVIEW strategy - metrics outside safe bounds.")

    print(f"\n{'='*70}\n")

    return spot_results, futures_results


def main():
    """Run futures comparison backtest."""
    return run_comparison()


if __name__ == "__main__":
    main()
