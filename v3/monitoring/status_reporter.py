#!/usr/bin/env python3
"""
Status Reporter - Live position status with real-time MEXC prices

BUG FIX: Fetches live prices from MEXC API instead of showing stale/cached data.
Never returns 0 silently.
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime

from v3.data.mexc_client import mexc_client


class StatusReporter:
    """
    Reports live status of open positions with real-time prices from MEXC.
    """

    def __init__(self, positions_file: str = "data/positions.json"):
        self.positions_file = positions_file

    def get_current_status(self) -> Dict:
        """
        Get current status of all open positions.

        Returns dict with:
        - open_positions: list of position dicts with live prices
        - total_pnl_usd: sum of all unrealized P&L
        - total_pnl_pct: portfolio P&L percentage
        """
        # Load positions from file
        positions = self._load_positions()

        if not positions:
            return {
                'open_positions': [],
                'total_pnl_usd': 0,
                'total_pnl_pct': 0
            }

        # Enrich with live prices
        enriched_positions = []
        total_pnl_usd = 0

        for pos in positions:
            symbol = pos['symbol']
            current_price = self._fetch_current_price(symbol)

            if current_price is None:
                print(f"[StatusReporter] Warning: Could not fetch price for {symbol}, skipping")
                continue

            # Calculate P&L
            entry_price = pos['entry_price']
            size_usd = pos['size_usd']
            direction = pos.get('direction', 'LONG')

            if direction == 'LONG':
                pnl_pct = (current_price / entry_price - 1) * 100
            else:  # SHORT
                pnl_pct = (entry_price / current_price - 1) * 100

            pnl_usd = size_usd * (pnl_pct / 100)

            # MFE/MAE
            mfe_pct = pos.get('mfe_pct', 0)
            mae_pct = pos.get('mae_pct', 0)

            # Add to enriched list
            enriched_positions.append({
                'symbol': symbol,
                'direction': direction,
                'engine': pos.get('engine', 'standard_long'),
                'entry_price': entry_price,
                'current_price': current_price,
                'size_usd': size_usd,
                'initial_risk_usd': pos.get('initial_risk_usd', size_usd * 0.03),
                'stop_loss': pos.get('stop_loss', 0),
                'take_profit': pos.get('take_profit', 0),
                'pnl_usd': pnl_usd,
                'pnl_pct': pnl_pct,
                'mfe_pct': mfe_pct,
                'mae_pct': mae_pct,
                'timestamp': pos.get('timestamp', '')
            })

            total_pnl_usd += pnl_usd

        # Calculate portfolio P&L percentage
        total_invested = sum(p['size_usd'] for p in enriched_positions)
        total_pnl_pct = (total_pnl_usd / total_invested * 100) if total_invested > 0 else 0

        return {
            'open_positions': enriched_positions,
            'total_pnl_usd': total_pnl_usd,
            'total_pnl_pct': total_pnl_pct
        }

    def print_status(self):
        """
        Print formatted status report to console.
        """
        status = self.get_current_status()

        print("\n" + "="*80)
        print("📊 ALPHA SNIPER V4 - LIVE POSITION STATUS")
        print("="*80)

        positions = status['open_positions']

        if not positions:
            print("No open positions")
            print("="*80)
            return

        print(f"\nOpen Positions: {len(positions)}")
        print(f"Total P&L: ${status['total_pnl_usd']:.2f} ({status['total_pnl_pct']:+.2f}%)")
        print()

        for i, pos in enumerate(positions, 1):
            engine = pos.get('engine', 'standard_long')
            initial_risk = pos.get('initial_risk_usd', 0)
            print(f"{i}. {pos['symbol']} ({pos['direction']}) [{engine}]")
            print(f"   Entry: ${pos['entry_price']:.6f} | Current: ${pos['current_price']:.6f}")
            print(f"   Size: ${pos['size_usd']:.2f} | Risk (R): ${initial_risk:.2f}")
            print(f"   Stop: ${pos['stop_loss']:.6f} | TP: ${pos['take_profit']:.6f}")
            print(f"   P&L: ${pos['pnl_usd']:.2f} ({pos['pnl_pct']:+.2f}%)")
            print(f"   MFE: {pos['mfe_pct']:+.2f}% | MAE: {pos['mae_pct']:+.2f}%")
            print()

        print("="*80 + "\n")

    def _load_positions(self) -> List[Dict]:
        """
        Load positions from JSON file.
        """
        if not os.path.exists(self.positions_file):
            return []

        try:
            with open(self.positions_file, 'r') as f:
                data = json.load(f)
                return data.get('open_positions', [])
        except Exception as e:
            print(f"[StatusReporter] Error loading positions: {e}")
            return []

    def _fetch_current_price(self, symbol: str) -> Optional[float]:
        """
        Fetch current price from MEXC.

        BUG FIX: Must NOT return 0 silently if fetch fails.
        """
        try:
            ticker = mexc_client.get_ticker_24h(symbol)

            if ticker is None:
                print(f"[StatusReporter] Failed to fetch ticker for {symbol}")
                return None

            last_price = float(ticker.get('lastPrice', 0))

            if last_price == 0:
                print(f"[StatusReporter] Warning: {symbol} price is 0")
                return None

            return last_price

        except Exception as e:
            print(f"[StatusReporter] Error fetching price for {symbol}: {e}")
            return None


# Global instance
status_reporter = StatusReporter()


if __name__ == "__main__":
    # Standalone execution
    status_reporter.print_status()
