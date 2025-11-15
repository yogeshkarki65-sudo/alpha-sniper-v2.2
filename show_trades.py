#!/usr/bin/env python3
"""Show trading performance and P&L"""

import sqlite3
from config.config import config
from datetime import datetime

def show_performance():
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    print("=" * 60)
    print("ALPHA SNIPER V4.1 - TRADING PERFORMANCE")
    print("=" * 60)

    # Open Positions
    print("\n📊 OPEN POSITIONS:")
    print("-" * 60)
    cursor.execute("""
        SELECT p.symbol, p.entry_price, p.position_size, p.opened_at,
               p.is_moon_mode, s.score
        FROM positions p
        LEFT JOIN signals s ON p.signal_id = s.id
        ORDER BY p.opened_at DESC
    """)
    open_positions = cursor.fetchall()

    if open_positions:
        for pos in open_positions:
            symbol, entry, size, opened_at, moon, score = pos
            moon_flag = "🌙 MOON" if moon else ""
            score_str = f"{score:.1f}" if score else "N/A"
            print(f"  {symbol:12} | Entry: ${entry:8.4f} | Size: {size:8.4f} | Score: {score_str:>5} {moon_flag}")
            print(f"  {'':12} | Opened: {opened_at}")
    else:
        print("  No open positions")

    # Closed Trades
    print("\n\n📈 CLOSED TRADES:")
    print("-" * 60)
    cursor.execute("""
        SELECT symbol, entry_price, exit_price, position_size, net_pnl_usd, pnl_pct,
               exit_reason, opened_at, closed_at, was_moon_mode
        FROM trades
        ORDER BY closed_at DESC
        LIMIT 20
    """)
    closed_trades = cursor.fetchall()

    if closed_trades:
        total_pnl = 0
        wins = 0
        losses = 0

        for trade in closed_trades:
            symbol, entry, exit, size, pnl_usd, pnl_pct, reason, opened, closed, moon = trade
            pnl_sign = "🟢" if pnl_usd > 0 else "🔴"
            moon_flag = "🌙" if moon else " "

            print(f"  {moon_flag} {symbol:12} | Entry: ${entry:8.4f} → Exit: ${exit:8.4f}")
            print(f"  {'':12} | P&L: {pnl_sign} ${pnl_usd:8.2f} ({pnl_pct:+6.2f}%) | {reason}")
            print(f"  {'':12} | {opened} → {closed}")
            print()

            total_pnl += pnl_usd
            if pnl_usd > 0:
                wins += 1
            else:
                losses += 1

        # Summary Stats
        print("=" * 60)
        print("📊 SUMMARY STATISTICS:")
        print("-" * 60)
        print(f"  Total Trades:        {len(closed_trades)}")
        print(f"  Wins:                {wins} ({wins/(wins+losses)*100:.1f}%)")
        print(f"  Losses:              {losses} ({losses/(wins+losses)*100:.1f}%)")
        print(f"  Total P&L:           ${total_pnl:+.2f}")
        print(f"  Current Equity:      ${config.SIM_EQUITY_START + total_pnl:.2f}")
        print(f"  Return on Start:     {(total_pnl/config.SIM_EQUITY_START)*100:+.2f}%")
        print("=" * 60)

    else:
        print("  No closed trades yet")

    conn.close()

if __name__ == "__main__":
    show_performance()
