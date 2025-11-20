#!/usr/bin/env python3
"""
Performance Report Generator for Alpha Sniper V2.2
Run this script to generate a comprehensive performance report.
Usage: python3 generate_performance_report.py
"""

import sqlite3
import os
import json
from datetime import datetime, timedelta

def connect_db(db_path='data/trades.db'):
    """Connect to the database"""
    if not os.path.exists(db_path):
        return None
    return sqlite3.connect(db_path)

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_subheader(title):
    """Print a formatted subheader"""
    print(f"\n--- {title} ---")

def get_overall_stats(conn):
    """Get overall trading statistics"""
    cursor = conn.cursor()

    # Total trades and P&L
    cursor.execute('''
        SELECT
            COUNT(*) as total_trades,
            SUM(net_pnl_usd) as total_pnl,
            AVG(net_pnl_usd) as avg_pnl,
            SUM(CASE WHEN net_pnl_usd > 0 THEN 1 ELSE 0 END) as winning_trades,
            SUM(CASE WHEN net_pnl_usd <= 0 THEN 1 ELSE 0 END) as losing_trades,
            MAX(net_pnl_usd) as best_trade,
            MIN(net_pnl_usd) as worst_trade,
            AVG(hold_time_hours) as avg_hold_time,
            SUM(entry_fee_usd + exit_fee_usd + slippage_cost_usd) as total_costs
        FROM trades
    ''')

    return cursor.fetchone()

def get_recent_trades(conn, limit=20):
    """Get recent trades"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            symbol,
            entry_price,
            exit_price,
            position_size,
            net_pnl_usd,
            pnl_pct,
            exit_reason,
            closed_at,
            hold_time_hours
        FROM trades
        ORDER BY closed_at DESC
        LIMIT ?
    ''', (limit,))

    return cursor.fetchall()

def get_performance_by_symbol(conn):
    """Get performance breakdown by symbol"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            symbol,
            COUNT(*) as trades,
            SUM(net_pnl_usd) as total_pnl,
            AVG(net_pnl_usd) as avg_pnl,
            SUM(CASE WHEN net_pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
            AVG(pnl_pct) as avg_pnl_pct
        FROM trades
        GROUP BY symbol
        ORDER BY total_pnl DESC
    ''')

    return cursor.fetchall()

def get_performance_by_exit_reason(conn):
    """Get performance breakdown by exit reason"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            exit_reason,
            COUNT(*) as trades,
            SUM(net_pnl_usd) as total_pnl,
            AVG(net_pnl_usd) as avg_pnl
        FROM trades
        GROUP BY exit_reason
        ORDER BY trades DESC
    ''')

    return cursor.fetchall()

def get_open_positions(conn):
    """Get currently open positions"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            symbol,
            entry_price,
            position_size,
            stop_loss_price,
            take_profit_price,
            trailing_stop_active,
            trailing_stop_price,
            opened_at
        FROM positions
    ''')

    return cursor.fetchall()

def get_recent_signals(conn, limit=10):
    """Get recent signals"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            symbol,
            score,
            rvol,
            velocity,
            trend,
            orderbook_imbalance,
            last_price,
            created_at,
            consumed
        FROM signals
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,))

    return cursor.fetchall()

def get_learning_log(conn, limit=5):
    """Get recent learning updates"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            weights_before,
            weights_after,
            train_ic,
            test_ic,
            num_trades_used,
            created_at
        FROM learning_log
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,))

    return cursor.fetchall()

def get_daily_stats(conn, limit=30):
    """Get daily statistics"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            date,
            starting_equity,
            ending_equity,
            high_water_mark,
            max_drawdown_pct,
            num_trades,
            win_rate,
            total_fees
        FROM daily_stats
        ORDER BY date DESC
        LIMIT ?
    ''', (limit,))

    return cursor.fetchall()

def get_time_based_performance(conn):
    """Get performance over different time periods"""
    cursor = conn.cursor()

    periods = {
        'Last 24 Hours': 1,
        'Last 7 Days': 7,
        'Last 30 Days': 30
    }

    results = {}
    for period_name, days in periods.items():
        cursor.execute('''
            SELECT
                COUNT(*) as trades,
                SUM(net_pnl_usd) as total_pnl,
                SUM(CASE WHEN net_pnl_usd > 0 THEN 1 ELSE 0 END) as wins
            FROM trades
            WHERE closed_at > datetime('now', '-' || ? || ' days')
        ''', (days,))
        results[period_name] = cursor.fetchone()

    return results

def main():
    print_header("ALPHA SNIPER V2.2 - PERFORMANCE REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    db_path = 'data/trades.db'

    if not os.path.exists(db_path):
        print(f"\n❌ ERROR: Database not found at {db_path}")
        print("The bot may not have been started yet, or the database path is different.")
        print(f"Current directory: {os.getcwd()}")
        print(f"Directory contents:")
        os.system('ls -la')
        return

    conn = connect_db(db_path)
    if not conn:
        print(f"\n❌ ERROR: Could not connect to database at {db_path}")
        return

    print(f"✅ Database found: {db_path}")

    # Overall Statistics
    print_header("OVERALL PERFORMANCE")
    stats = get_overall_stats(conn)

    if stats and stats[0] > 0:
        total_trades, total_pnl, avg_pnl, wins, losses, best, worst, avg_hold, total_costs = stats
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        print(f"\nTotal Trades:        {total_trades}")
        print(f"Winning Trades:      {wins} ({win_rate:.1f}%)")
        print(f"Losing Trades:       {losses} ({100-win_rate:.1f}%)")
        print(f"\nTotal P&L:           ${total_pnl:.2f}")
        print(f"Average P&L:         ${avg_pnl:.2f}")
        print(f"Best Trade:          ${best:.2f}")
        print(f"Worst Trade:         ${worst:.2f}")
        print(f"\nAvg Hold Time:       {avg_hold:.2f} hours")
        print(f"Total Costs:         ${total_costs:.2f} (fees + slippage)")
    else:
        print("\n⚠️  No completed trades found in database")

    # Time-based Performance
    print_header("PERFORMANCE BY TIME PERIOD")
    time_perf = get_time_based_performance(conn)

    for period, data in time_perf.items():
        if data and data[0] > 0:
            trades, pnl, wins = data
            win_rate = (wins / trades * 100) if trades > 0 else 0
            print(f"\n{period}:")
            print(f"  Trades: {trades} | P&L: ${pnl:.2f} | Win Rate: {win_rate:.1f}%")
        else:
            print(f"\n{period}: No trades")

    # Open Positions
    print_header("OPEN POSITIONS")
    positions = get_open_positions(conn)

    if positions:
        print(f"\n{'Symbol':<12} {'Entry':<10} {'Size':<10} {'Stop Loss':<10} {'Take Profit':<12} {'Trailing':<8} {'Opened':<20}")
        print("-" * 100)
        for pos in positions:
            symbol, entry, size, sl, tp, trailing, trail_price, opened = pos
            trailing_str = "YES" if trailing else "NO"
            print(f"{symbol:<12} ${entry:<9.6f} {size:<10.4f} ${sl:<9.6f} ${tp:<11.6f} {trailing_str:<8} {opened}")
    else:
        print("\n✅ No open positions")

    # Performance by Symbol
    print_header("PERFORMANCE BY SYMBOL")
    symbol_perf = get_performance_by_symbol(conn)

    if symbol_perf:
        print(f"\n{'Symbol':<12} {'Trades':<8} {'Total P&L':<12} {'Avg P&L':<12} {'Wins':<6} {'Avg %':<10}")
        print("-" * 70)
        for row in symbol_perf[:20]:  # Top 20 symbols
            symbol, trades, total_pnl, avg_pnl, wins, avg_pct = row
            win_rate = (wins / trades * 100) if trades > 0 else 0
            print(f"{symbol:<12} {trades:<8} ${total_pnl:<11.2f} ${avg_pnl:<11.2f} {wins:<6} {avg_pct:>8.2f}%")
    else:
        print("\n⚠️  No symbol data available")

    # Performance by Exit Reason
    print_header("PERFORMANCE BY EXIT REASON")
    exit_perf = get_performance_by_exit_reason(conn)

    if exit_perf:
        print(f"\n{'Exit Reason':<20} {'Count':<8} {'Total P&L':<12} {'Avg P&L':<12}")
        print("-" * 60)
        for row in exit_perf:
            reason, count, total_pnl, avg_pnl = row
            print(f"{reason:<20} {count:<8} ${total_pnl:<11.2f} ${avg_pnl:<11.2f}")
    else:
        print("\n⚠️  No exit reason data available")

    # Recent Trades
    print_header("RECENT TRADES (Last 20)")
    recent = get_recent_trades(conn, 20)

    if recent:
        print(f"\n{'Symbol':<12} {'Entry':<10} {'Exit':<10} {'Size':<10} {'P&L $':<10} {'P&L %':<8} {'Exit Reason':<15} {'Hold Hrs':<8} {'Closed At':<20}")
        print("-" * 130)
        for trade in recent:
            symbol, entry, exit_p, size, pnl, pnl_pct, reason, closed, hold = trade
            pnl_str = f"${pnl:.2f}" if pnl else "$0.00"
            pnl_pct_str = f"{pnl_pct:.2f}%" if pnl_pct else "0.00%"
            print(f"{symbol:<12} ${entry:<9.6f} ${exit_p:<9.6f} {size:<10.4f} {pnl_str:<10} {pnl_pct_str:<8} {reason:<15} {hold:<8.1f} {closed}")
    else:
        print("\n⚠️  No recent trades")

    # Recent Signals
    print_header("RECENT SIGNALS (Last 10)")
    signals = get_recent_signals(conn, 10)

    if signals:
        print(f"\n{'Symbol':<12} {'Score':<8} {'RVOL':<8} {'Velocity':<10} {'Trend':<8} {'OB Imbal':<10} {'Price':<12} {'Consumed':<10} {'Created':<20}")
        print("-" * 120)
        for sig in signals:
            symbol, score, rvol, velocity, trend, ob_imb, price, created, consumed = sig
            consumed_str = "YES" if consumed else "NO"
            print(f"{symbol:<12} {score:<8.1f} {rvol:<8.2f} {velocity:<10.2f} {trend:<8.2f} {ob_imb:<10.2f} ${price:<11.6f} {consumed_str:<10} {created}")
    else:
        print("\n⚠️  No signals generated yet")

    # Learning Log
    print_header("LEARNING LOG (Weight Adjustments)")
    learning = get_learning_log(conn, 5)

    if learning:
        for i, log in enumerate(learning, 1):
            before, after, train_ic, test_ic, num_trades, created = log
            print(f"\n--- Update #{i} ({created}) ---")
            print(f"Trades Used: {num_trades}")
            print(f"Train IC: {train_ic:.4f} | Test IC: {test_ic:.4f}")

            if before and after:
                before_dict = json.loads(before)
                after_dict = json.loads(after)

                print("\nWeight Changes:")
                for key in before_dict:
                    old_val = before_dict.get(key, 0)
                    new_val = after_dict.get(key, 0)
                    change = ((new_val - old_val) / old_val * 100) if old_val != 0 else 0
                    print(f"  {key:<20} {old_val:.4f} → {new_val:.4f} ({change:+.1f}%)")
    else:
        print("\n⚠️  No learning updates yet")

    # Daily Stats
    print_header("DAILY STATISTICS (Last 30 Days)")
    daily = get_daily_stats(conn, 30)

    if daily:
        print(f"\n{'Date':<12} {'Start Equity':<14} {'End Equity':<14} {'HWM':<14} {'Max DD %':<10} {'Trades':<8} {'Win Rate':<10} {'Fees':<10}")
        print("-" * 110)
        for row in daily:
            date, start_eq, end_eq, hwm, max_dd, trades, win_rate, fees = row
            start_str = f"${start_eq:.2f}" if start_eq else "N/A"
            end_str = f"${end_eq:.2f}" if end_eq else "N/A"
            hwm_str = f"${hwm:.2f}" if hwm else "N/A"
            dd_str = f"{max_dd:.2f}%" if max_dd else "0.00%"
            wr_str = f"{win_rate:.1f}%" if win_rate else "0.0%"
            fees_str = f"${fees:.2f}" if fees else "$0.00"
            print(f"{date:<12} {start_str:<14} {end_str:<14} {hwm_str:<14} {dd_str:<10} {trades:<8} {wr_str:<10} {fees_str:<10}")
    else:
        print("\n⚠️  No daily stats recorded")

    conn.close()

    print_header("END OF REPORT")
    print()

if __name__ == "__main__":
    main()
