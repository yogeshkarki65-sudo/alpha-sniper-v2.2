"""
Alpha Sniper V3.2 - Main Entry Point

Orchestrates the complete trading system:
1. Regime detection
2. Universe filtering
3. Signal scanning
4. Trade execution
5. Position management
"""
import time
from datetime import datetime
import argparse

from v3.regime.detector import regime_detector
from v3.universe.manager import universe_manager
from v3.scanner.signals import signal_generator
from v3.trader.executor import trade_executor
from v3.trader.position_manager import position_manager
from v3.risk.risk_engine import risk_engine


class AlphaSniperV3:
    """
    Main trading bot orchestrator
    """

    def __init__(
        self,
        scan_interval_minutes: int = 15,
        position_check_interval_minutes: int = 5
    ):
        """
        Args:
            scan_interval_minutes: How often to run scanner
            position_check_interval_minutes: How often to check positions
        """
        self.scan_interval = scan_interval_minutes * 60  # Convert to seconds
        self.position_check_interval = position_check_interval_minutes * 60

        self.last_scan_time = None
        self.last_position_check = None

        self.running = False
        self.cycle_count = 0

    def run(self):
        """Main bot loop"""
        print("\n" + "="*70)
        print("  🚀 ALPHA SNIPER V3.2 - STARTING")
        print("="*70)
        print(f"  Mode: {trade_executor.mode}")
        print(f"  Initial Equity: ${risk_engine.current_equity:.2f}")
        print(f"  Scan Interval: {self.scan_interval / 60:.0f} minutes")
        print(f"  Position Check Interval: {self.position_check_interval / 60:.0f} minutes")
        print("="*70 + "\n")

        self.running = True

        try:
            while self.running:
                self.cycle_count += 1
                self._run_cycle()
                time.sleep(10)  # Sleep 10s between checks

        except KeyboardInterrupt:
            print("\n\n⚠️  Received stop signal...")
            self.stop()

    def _run_cycle(self):
        """Single cycle of the bot"""
        now = time.time()

        # 1. Check if it's time for position management
        if self._should_check_positions(now):
            position_manager.manage_positions()
            self.last_position_check = now

        # 2. Check if it's time for scanner
        if self._should_scan(now):
            self._run_scanner_cycle()
            self.last_scan_time = now

        # 3. Print status periodically
        if self.cycle_count % 30 == 0:  # Every ~5 minutes
            self._print_status()

    def _should_scan(self, now: float) -> bool:
        """Check if it's time to run scanner"""
        if self.last_scan_time is None:
            return True

        return (now - self.last_scan_time) >= self.scan_interval

    def _should_check_positions(self, now: float) -> bool:
        """Check if it's time to check positions"""
        # Always check if we have open positions
        if len(risk_engine.open_positions) == 0:
            return False

        if self.last_position_check is None:
            return True

        return (now - self.last_position_check) >= self.position_check_interval

    def _run_scanner_cycle(self):
        """Run complete scanner -> trader cycle"""
        # 1. Run scanner
        signals = signal_generator.scan()

        if len(signals) == 0:
            print("No valid signals this cycle\n")
            return

        # 2. Check if we can take new positions
        stats = risk_engine.get_stats()

        if stats['daily_loss_cap_hit']:
            print("⚠️  Daily loss cap hit - no new entries today\n")
            return

        if stats['open_positions'] >= 5:
            print(f"⚠️  Max positions reached ({stats['open_positions']}/5)\n")
            return

        # 3. Execute top signals
        max_entries_per_cycle = 2  # Don't flood
        entries_this_cycle = 0

        for signal in signals[:max_entries_per_cycle]:
            # Check if we still have capacity
            can_trade, reason = risk_engine.can_open_position(
                symbol=signal['symbol'],
                risk_usd=2.0  # Estimate
            )

            if not can_trade:
                print(f"⚠️  Cannot trade {signal['symbol']}: {reason}\n")
                continue

            # Execute
            position = trade_executor.execute_signal(signal)

            if position is not None:
                entries_this_cycle += 1

            # Check if we've hit limits after this entry
            if len(risk_engine.open_positions) >= 5:
                break

        print(f"✅ Entered {entries_this_cycle} position(s) this cycle\n")

    def _print_status(self):
        """Print current bot status"""
        stats = risk_engine.get_stats()
        position_summary = position_manager.get_position_summary()

        print("\n" + "="*70)
        print(f"  📊 STATUS UPDATE - Cycle #{self.cycle_count}")
        print("="*70)
        print(f"  💰 Equity: ${stats['current_equity']:.2f} "
              f"(Peak: ${stats['peak_equity']:.2f}, "
              f"DD: {stats['drawdown_pct']:.2f}%)")
        print(f"  📈 Daily P&L: ${stats['daily_pnl']:.2f} "
              f"({stats['daily_pnl_pct']:.2f}%)")
        print(f"  📊 Positions: {stats['open_positions']} open "
              f"({stats['total_trades']} total trades)")
        print(f"  ⚠️  Portfolio Heat: {stats['portfolio_heat_pct']:.2f}%")

        if position_summary['count'] > 0:
            print(f"\n  Open Positions:")
            for pos in position_summary['positions']:
                print(f"    {pos['symbol']}: "
                      f"{pos['pnl_r']:+.2f}R (${pos['pnl_usd']:+.2f}), "
                      f"{pos['hold_hours']:.1f}h, "
                      f"TP1:{pos['tp1_hit']}, TP2:{pos['tp2_hit']}")

        print("="*70 + "\n")

    def stop(self):
        """Stop the bot"""
        print("\n" + "="*70)
        print("  🛑 STOPPING ALPHA SNIPER V3.2")
        print("="*70)

        self.running = False

        # Close all positions
        if len(risk_engine.open_positions) > 0:
            print(f"\n⚠️  Closing {len(risk_engine.open_positions)} open positions...")

            for symbol in list(risk_engine.open_positions.keys()):
                position = risk_engine.open_positions[symbol]
                current_price = position.current_price

                risk_engine.close_position(
                    symbol=symbol,
                    exit_price=current_price,
                    exit_reason="BOT_STOP",
                    timestamp=datetime.now()
                )

        # Final stats
        self._print_final_stats()

    def _print_final_stats(self):
        """Print final performance statistics"""
        stats = risk_engine.get_stats()
        closed_trades = risk_engine.closed_positions

        print("\n" + "="*70)
        print("  📊 FINAL PERFORMANCE REPORT")
        print("="*70)

        print(f"\n  💰 Final Equity: ${stats['current_equity']:.2f}")
        print(f"  📈 Total P&L: ${stats['current_equity'] - risk_engine.initial_equity:.2f} "
              f"({(stats['current_equity'] / risk_engine.initial_equity - 1) * 100:+.2f}%)")
        print(f"  🏔️  Peak Equity: ${stats['peak_equity']:.2f}")
        print(f"  📉 Max Drawdown: {stats['drawdown_pct']:.2f}%")

        if len(closed_trades) > 0:
            wins = [t for t in closed_trades if t['pnl_r'] > 0]
            losses = [t for t in closed_trades if t['pnl_r'] <= 0]

            win_rate = len(wins) / len(closed_trades) * 100
            avg_win_r = sum(t['pnl_r'] for t in wins) / len(wins) if wins else 0
            avg_loss_r = sum(t['pnl_r'] for t in losses) / len(losses) if losses else 0

            gross_wins = sum(t['pnl_usd'] for t in wins)
            gross_losses = abs(sum(t['pnl_usd'] for t in losses))
            profit_factor = gross_wins / gross_losses if gross_losses > 0 else 0

            print(f"\n  📊 Trade Statistics:")
            print(f"    Total Trades: {len(closed_trades)}")
            print(f"    Win Rate: {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)")
            print(f"    Avg Win: {avg_win_r:+.2f}R")
            print(f"    Avg Loss: {avg_loss_r:.2f}R")
            print(f"    Profit Factor: {profit_factor:.2f}")

            # Best/worst trades
            best_trade = max(closed_trades, key=lambda t: t['pnl_r'])
            worst_trade = min(closed_trades, key=lambda t: t['pnl_r'])

            print(f"\n  🏆 Best Trade: {best_trade['symbol']} ({best_trade['pnl_r']:+.2f}R)")
            print(f"  💔 Worst Trade: {worst_trade['symbol']} ({worst_trade['pnl_r']:.2f}R)")

        print("\n" + "="*70)
        print("  ✅ ALPHA SNIPER V3.2 STOPPED")
        print("="*70 + "\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Alpha Sniper V3.2 Trading Bot')
    parser.add_argument(
        '--scan-interval',
        type=int,
        default=15,
        help='Scanner interval in minutes (default: 15)'
    )
    parser.add_argument(
        '--position-check-interval',
        type=int,
        default=5,
        help='Position check interval in minutes (default: 5)'
    )
    parser.add_argument(
        '--mode',
        type=str,
        default='SIM',
        choices=['SIM', 'LIVE'],
        help='Trading mode (default: SIM)'
    )

    args = parser.parse_args()

    # Set mode
    trade_executor.mode = args.mode

    # Create and run bot
    bot = AlphaSniperV3(
        scan_interval_minutes=args.scan_interval,
        position_check_interval_minutes=args.position_check_interval
    )

    bot.run()


if __name__ == "__main__":
    main()
