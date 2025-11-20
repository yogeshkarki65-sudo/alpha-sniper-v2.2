#!/usr/bin/env python3
"""
Quick V4 Status Checker
Reads positions.json to see current state
"""
import json
import os
from datetime import datetime

def main():
    print("=" * 80)
    print("  V4 BOT STATUS CHECK")
    print("=" * 80)

    # Check if V4 is running
    import subprocess
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    if 'v4_main.py' in result.stdout or 'v3_main.py' in result.stdout:
        for line in result.stdout.split('\n'):
            if 'v4_main.py' in line or 'v3_main.py' in line:
                print(f"\n✅ V4 Bot Running:")
                print(f"   {line.strip()}")
    else:
        print("\n⚠️  V4 Bot not running")

    # Check positions.json
    print("\n" + "=" * 80)
    print("  OPEN POSITIONS")
    print("=" * 80)

    if os.path.exists('positions.json'):
        try:
            with open('positions.json', 'r') as f:
                positions = json.load(f)

            if not positions or len(positions) == 0:
                print("\n✅ No open positions")
            else:
                print(f"\n📊 Total Open Positions: {len(positions)}\n")

                for symbol, pos in positions.items():
                    print(f"--- {symbol} ---")
                    print(f"  Direction: {pos.get('direction', 'UNKNOWN')}")
                    print(f"  Entry Price: ${pos.get('entry_price', 0):.6f}")
                    print(f"  Current Price: ${pos.get('current_price', 0):.6f}")
                    print(f"  Size: ${pos.get('size_usd', 0):.2f}")
                    print(f"  Stop Loss: ${pos.get('stop_loss_price', 0):.6f}")

                    # Calculate P&L
                    entry = pos.get('entry_price', 0)
                    current = pos.get('current_price', entry)
                    direction = pos.get('direction', 'LONG')

                    if direction == 'LONG':
                        pnl_pct = ((current - entry) / entry) * 100 if entry > 0 else 0
                    else:  # SHORT
                        pnl_pct = ((entry - current) / entry) * 100 if entry > 0 else 0

                    pnl_emoji = "🟢" if pnl_pct > 0 else "🔴"
                    print(f"  P&L: {pnl_emoji} {pnl_pct:+.2f}%")

                    # Time in position
                    entry_time = pos.get('entry_time')
                    if entry_time:
                        try:
                            entry_dt = datetime.fromisoformat(entry_time)
                            hold_time = (datetime.now() - entry_dt).total_seconds() / 3600
                            print(f"  Hold Time: {hold_time:.1f} hours")
                        except:
                            pass

                    # TP levels
                    tp1_hit = pos.get('tp1_hit', False)
                    tp2_hit = pos.get('tp2_hit', False)
                    print(f"  TP1 Hit: {'✅' if tp1_hit else '❌'}")
                    print(f"  TP2 Hit: {'✅' if tp2_hit else '❌'}")

                    # Trailing
                    trailing = pos.get('trailing_stop_price')
                    if trailing:
                        print(f"  Trailing Stop: ${trailing:.6f}")

                    print()

        except Exception as e:
            print(f"❌ Error reading positions.json: {e}")
    else:
        print("\n⚠️  No positions.json file found")

    # Check for sim_performance.json
    print("=" * 80)
    print("  COMPLETED TRADES")
    print("=" * 80)

    if os.path.exists('sim_performance.json'):
        try:
            with open('sim_performance.json', 'r') as f:
                data = json.load(f)

            metrics = data.get('metrics', {})
            total_trades = metrics.get('total_trades', 0)

            print(f"\n✅ Found performance data:")
            print(f"   Total Trades: {total_trades}")

            if total_trades > 0:
                wins = metrics.get('winning_trades', 0)
                win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
                total_pnl = metrics.get('total_pnl', 0)
                avg_r = metrics.get('total_r_multiple', 0) / total_trades if total_trades > 0 else 0

                print(f"   Win Rate: {win_rate:.1f}%")
                print(f"   Total P&L: ${total_pnl:.2f}")
                print(f"   Avg R: {avg_r:.2f}R")

                print("\n   Run 'python3 generate_v4_performance_report.py' for full report")
        except Exception as e:
            print(f"❌ Error reading sim_performance.json: {e}")
    else:
        print("\n⚠️  No completed trades yet (sim_performance.json not found)")
        print("   V4 tracks completed trades in sim_performance.json")
        print("   Check back after first position closes")

    # Check data/trades.db (V2 data)
    print("\n" + "=" * 80)
    print("  V2 DATA (OLD)")
    print("=" * 80)

    if os.path.exists('data/trades.db'):
        import sqlite3
        try:
            conn = sqlite3.connect('data/trades.db')
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM trades')
            count = cursor.fetchone()[0]
            conn.close()

            print(f"\n⚠️  Found V2 database with {count} old trades")
            print("   This is from the previous V2 bot (not V4)")
            print("   V4 uses sim_performance.json instead")
        except Exception as e:
            print(f"❌ Error reading V2 database: {e}")

    print("\n" + "=" * 80)
    print()

if __name__ == '__main__':
    main()
