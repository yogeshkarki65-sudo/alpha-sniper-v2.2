#!/usr/bin/env python3
"""
V4 Performance Report Generator for Alpha Sniper V4 (V3.2 branch)
Run this script to generate a comprehensive performance report from V4 data.
Usage: python3 generate_v4_performance_report.py
"""

import json
import os
from datetime import datetime
from typing import Dict, List

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_subheader(title):
    """Print a formatted subheader"""
    print(f"\n--- {title} ---")

def load_sim_performance(filepath='sim_performance.json'):
    """Load sim_performance.json"""
    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None

def main():
    print_header("ALPHA SNIPER V4 (V3.2) - PERFORMANCE REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # Check if we're in the right directory
    if not os.path.exists('v3') or not os.path.exists('v3_main.py'):
        print("\n❌ ERROR: Not in V4 directory!")
        print("Please run this script from the alpha-sniper-v2.2 directory on the correct branch.")
        print(f"Current directory: {os.getcwd()}")
        print("\nExpected files: v3/, v3_main.py, sim_performance.json")
        return

    print("✅ V4 directory structure found")

    # Load performance data
    data = load_sim_performance('sim_performance.json')

    if data is None:
        print("\n❌ ERROR: sim_performance.json not found!")
        print("The bot may not have been started yet, or no trades have been executed.")
        print("\nTo start the V4 bot:")
        print("  python3 v3_main.py")
        return

    print("✅ Performance data loaded: sim_performance.json")

    # Extract data
    metrics = data.get('metrics', {})
    trade_history = data.get('trade_history', [])
    daily_returns = data.get('daily_returns', [])

    # ============================================================================
    # OVERALL PERFORMANCE
    # ============================================================================
    print_header("OVERALL PERFORMANCE")

    total_trades = metrics.get('total_trades', 0)

    if total_trades == 0:
        print("\n⚠️  No trades executed yet. Bot is scanning for signals...")
        return

    winning_trades = metrics.get('winning_trades', 0)
    losing_trades = metrics.get('losing_trades', 0)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    total_pnl = metrics.get('total_pnl', 0)
    total_r_multiple = metrics.get('total_r_multiple', 0)
    avg_r = total_r_multiple / total_trades if total_trades > 0 else 0

    current_equity = metrics.get('current_equity', 0)
    peak_equity = metrics.get('peak_equity', 0)
    max_dd_pct = metrics.get('max_drawdown_pct', 0) * 100

    confidence_score = metrics.get('confidence_score', 0)
    live_ready = metrics.get('live_ready', False)

    print(f"\n📊 Total Trades:        {total_trades}")
    print(f"✅ Winning Trades:      {winning_trades} ({win_rate:.1f}%)")
    print(f"❌ Losing Trades:       {losing_trades} ({100-win_rate:.1f}%)")
    print(f"\n💰 Total P&L:           ${total_pnl:.2f}")
    print(f"📈 Average R-Multiple:  {avg_r:.2f}R")
    print(f"\n💵 Current Equity:      ${current_equity:.2f}")
    print(f"🏆 Peak Equity:         ${peak_equity:.2f}")
    print(f"📉 Max Drawdown:        {max_dd_pct:.2f}%")

    # ============================================================================
    # TRADE QUALITY
    # ============================================================================
    print_header("TRADE QUALITY")

    avg_win_r = metrics.get('avg_win_r', 0)
    avg_loss_r = metrics.get('avg_loss_r', 0)
    largest_win_r = metrics.get('largest_win_r', 0)
    largest_loss_r = metrics.get('largest_loss_r', 0)

    profit_factor = abs(avg_win_r * winning_trades / (avg_loss_r * losing_trades)) if (losing_trades > 0 and avg_loss_r != 0) else 0

    print(f"\n⬆️  Average Win:         {avg_win_r:.2f}R")
    print(f"⬇️  Average Loss:        {avg_loss_r:.2f}R")
    print(f"🚀 Best Win:            {largest_win_r:.2f}R")
    print(f"💥 Worst Loss:          {largest_loss_r:.2f}R")
    print(f"📊 Profit Factor:       {profit_factor:.2f}")

    # Win/Loss Ratio
    if abs(avg_loss_r) > 0:
        win_loss_ratio = avg_win_r / abs(avg_loss_r)
        print(f"⚖️  Win/Loss Ratio:      {win_loss_ratio:.2f}")

    # ============================================================================
    # STREAKS & CONSISTENCY
    # ============================================================================
    print_header("STREAKS & CONSISTENCY")

    current_streak = metrics.get('current_streak', 0)
    max_win_streak = metrics.get('max_win_streak', 0)
    max_loss_streak = metrics.get('max_loss_streak', 0)

    streak_type = "wins" if current_streak > 0 else "losses"
    streak_emoji = "🔥" if current_streak > 0 else "❄️"

    print(f"\n{streak_emoji} Current Streak:      {abs(current_streak)} {streak_type}")
    print(f"🏆 Best Win Streak:     {max_win_streak}")
    print(f"💀 Worst Loss Streak:   {max_loss_streak}")

    # ============================================================================
    # CONFIDENCE & LIVE READINESS
    # ============================================================================
    print_header("CONFIDENCE SCORE & LIVE READINESS")

    print(f"\n📊 Confidence Score:    {confidence_score:.1f}/100")

    if live_ready:
        print("\n✅ STATUS: READY FOR LIVE TRADING! ✅")
        print("\nAll criteria met:")
        print("  ✅ Minimum 30 trades")
        print("  ✅ Win rate ≥ 55%")
        print("  ✅ Avg R ≥ 0.8")
        print("  ✅ Max drawdown < 8%")
        print("  ✅ Max loss streak ≤ 5")
    else:
        print("\n⏳ STATUS: Building Confidence...")

        # Show checklist
        print("\nLive Trading Criteria:")
        print(f"  {'✅' if total_trades >= 30 else '❌'} Trades: {total_trades}/30")
        print(f"  {'✅' if win_rate >= 55 else '❌'} Win Rate: {win_rate:.1f}% (need 55%)")
        print(f"  {'✅' if avg_r >= 0.8 else '❌'} Avg R: {avg_r:.2f}R (need 0.8R)")
        print(f"  {'✅' if max_dd_pct <= 8 else '❌'} Max DD: {max_dd_pct:.2f}% (max 8%)")
        print(f"  {'✅' if max_loss_streak <= 5 else '❌'} Loss Streak: {max_loss_streak} (max 5)")

    # ============================================================================
    # RECENT TRADES
    # ============================================================================
    print_header("RECENT TRADES (Last 20)")

    if trade_history:
        # Show last 20 trades
        recent_trades = trade_history[-20:]

        print(f"\n{'#':<4} {'Symbol':<12} {'Entry':<12} {'Exit':<12} {'P&L %':<10} {'R-Mult':<8} {'Exit Reason':<20} {'Hold Time':<10}")
        print("-" * 110)

        for i, trade in enumerate(reversed(recent_trades), 1):
            symbol = trade.get('symbol', 'N/A')
            entry = trade.get('entry_price', 0)
            exit_p = trade.get('exit_price', 0)
            pnl_pct = trade.get('pnl_pct', 0) * 100
            r_mult = trade.get('r_multiple', 0)
            reason = trade.get('exit_reason', 'N/A')
            hold_time = trade.get('hold_time_hours', 0)

            pnl_emoji = "✅" if r_mult > 0 else "❌"

            print(f"{pnl_emoji} {i:<2} {symbol:<12} ${entry:<11.6f} ${exit_p:<11.6f} {pnl_pct:>8.2f}% {r_mult:>7.2f}R {reason:<20} {hold_time:<9.1f}h")
    else:
        print("\n⚠️  No trade history available")

    # ============================================================================
    # REGIME PERFORMANCE (if regime data available)
    # ============================================================================
    print_header("REGIME-BASED PERFORMANCE ANALYSIS")

    # Group trades by regime if available
    regime_stats = {}
    for trade in trade_history:
        # V4 might store regime info in trades
        regime = trade.get('regime', 'UNKNOWN')

        if regime not in regime_stats:
            regime_stats[regime] = {
                'trades': 0,
                'wins': 0,
                'total_r': 0
            }

        regime_stats[regime]['trades'] += 1
        r_mult = trade.get('r_multiple', 0)
        regime_stats[regime]['total_r'] += r_mult
        if r_mult > 0:
            regime_stats[regime]['wins'] += 1

    if regime_stats and any(k != 'UNKNOWN' for k in regime_stats.keys()):
        print(f"\n{'Regime':<12} {'Trades':<8} {'Win Rate':<12} {'Avg R':<10}")
        print("-" * 50)

        for regime, stats in sorted(regime_stats.items()):
            trades = stats['trades']
            wins = stats['wins']
            win_rate_regime = (wins / trades * 100) if trades > 0 else 0
            avg_r_regime = stats['total_r'] / trades if trades > 0 else 0

            print(f"{regime:<12} {trades:<8} {win_rate_regime:>9.1f}% {avg_r_regime:>9.2f}R")
    else:
        print("\n⚠️  No regime data available in trade history")
        print("Note: V4 uses regime detection but may not tag individual trades with regime")

    # ============================================================================
    # EXIT REASON BREAKDOWN
    # ============================================================================
    print_header("EXIT REASON BREAKDOWN")

    exit_reasons = {}
    for trade in trade_history:
        reason = trade.get('exit_reason', 'UNKNOWN')
        r_mult = trade.get('r_multiple', 0)

        if reason not in exit_reasons:
            exit_reasons[reason] = {
                'count': 0,
                'total_r': 0,
                'wins': 0
            }

        exit_reasons[reason]['count'] += 1
        exit_reasons[reason]['total_r'] += r_mult
        if r_mult > 0:
            exit_reasons[reason]['wins'] += 1

    if exit_reasons:
        print(f"\n{'Exit Reason':<20} {'Count':<8} {'Win Rate':<12} {'Avg R':<10}")
        print("-" * 55)

        for reason, stats in sorted(exit_reasons.items(), key=lambda x: x[1]['count'], reverse=True):
            count = stats['count']
            wins = stats['wins']
            win_rate_exit = (wins / count * 100) if count > 0 else 0
            avg_r_exit = stats['total_r'] / count if count > 0 else 0

            print(f"{reason:<20} {count:<8} {win_rate_exit:>9.1f}% {avg_r_exit:>9.2f}R")

    # ============================================================================
    # SYSTEM INFORMATION
    # ============================================================================
    print_header("SYSTEM INFORMATION")

    last_updated = metrics.get('last_updated', 'N/A')
    last_saved = data.get('last_saved', 'N/A')

    print(f"\n📅 Last Trade:          {last_updated}")
    print(f"💾 Last Saved:          {last_saved}")
    print(f"📁 Data File:           sim_performance.json")
    print(f"🤖 Bot Version:         V4 (V3.2 architecture)")
    print(f"📊 Tracking Mode:       In-memory + JSON persistence")

    # V4 Features
    print("\n🔧 V4 Features:")
    print("  • Multi-signal regime detection (BULL/SIDEWAYS/BEAR)")
    print("  • Regime-adaptive position sizing")
    print("  • 6-state symbol tracking (FLAT/BASING/BREAKING_OUT/etc)")
    print("  • ATR-based stop loss (2x ATR or structure low)")
    print("  • Multi-level take profits (TP1 @ 2R, TP2 @ 3R)")
    print("  • Trailing stop (1.5x ATR from highest)")
    print("  • No-follow-through rule (exit dead trades)")
    print("  • Execution cost modeling")
    print("  • Confidence tracking for SIM→LIVE transition")

    # Important Note
    print_header("IMPORTANT NOTE")
    print("\n⚠️  V4 DOES NOT DO SHORT SELLING!")
    print("\nV4 behavior in different regimes:")
    print("  • BULL regime:     Full risk (1.0x multiplier), active trading")
    print("  • SIDEWAYS regime: Reduced risk (0.6x multiplier), selective trading")
    print("  • BEAR regime:     Minimal risk (0.3x multiplier), very selective/paused")
    print("\nV4 only takes LONG positions. In bear markets, it reduces")
    print("position sizing or stops trading entirely to preserve capital.")
    print("\nIf you want SHORT selling capability, that would need to be")
    print("implemented as a separate feature.")

    print_header("END OF REPORT")
    print()

if __name__ == "__main__":
    main()
