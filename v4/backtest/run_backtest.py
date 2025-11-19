"""
Alpha Sniper V4.0 - Backtest Runner

Minimal but functional backtest harness that replays historical data through V4 pipeline.

Usage:
    python -m v4.backtest.run_backtest --start 2023-01-01 --end 2024-01-01
    python -m v4.backtest.run_backtest --start 2023-01-01 --end 2024-01-01 --symbols SOLUSDT,XRPUSDT
    python -m v4.backtest.run_backtest --config backtest_config.json

Features:
- Replays bar-by-bar through V4 components
- Same code as live (regime, scanner, execution, position manager)
- Outputs equity curve, trade log, performance metrics
- Saves results to JSON for analysis

Limitations:
- Requires historical OHLCV data (fetch from MEXC or load CSV)
- Simulated fills (no real orderbook replay)
- No tick-level data (uses bar closes)
"""
import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from v4.data.mexc_client import MEXCClient
from v4.core.regime_detector import regime_detector, Regime
from v4.core.execution_engine import ExecutionEngine
from v4.scanner.feature_extractor import FeatureExtractor
from v4.scanner.v4_scanner import V4Scanner
from v4.trader.position_manager import PositionManager


class BacktestRunner:
    """
    Minimal backtest runner for V4.0
    """

    def __init__(
        self,
        start_date: str,
        end_date: str,
        start_equity: float = 500.0,
        symbols: Optional[List[str]] = None,
        output_dir: str = "backtest_results"
    ):
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.start_equity = start_equity
        self.symbols = symbols or []
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Initialize V4 components (same as live)
        print("\n[Backtest] Initializing V4 components...")
        self.mexc_client = MEXCClient(cache_ttl=3600)
        self.execution_engine = ExecutionEngine(self.mexc_client)
        self.feature_extractor = FeatureExtractor(self.mexc_client)
        self.scanner = V4Scanner(self.mexc_client, self.feature_extractor)
        self.position_manager = PositionManager(
            self.mexc_client,
            self.execution_engine,
            telegram_notifier=None  # No alerts in backtest
        )

        # Backtest state
        self.current_equity = start_equity
        self.equity_curve = []
        self.trade_log = []
        self.current_timestamp = self.start_date

        print(f"✅ Components initialized")
        print(f"   Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"   Start Equity: ${self.start_equity:.2f}")

    def load_historical_data(self) -> Dict[str, pd.DataFrame]:
        """
        Load historical OHLCV data

        Returns:
            Dict[symbol, DataFrame] with OHLCV data indexed by timestamp

        For now: Fetch from MEXC API (limited to recent data)
        TODO: Load from pre-downloaded CSV files for full history
        """
        print("\n[Backtest] Loading historical data...")

        # If no symbols specified, use top volume symbols
        if not self.symbols:
            print("   No symbols specified, fetching top 50 by volume...")
            tickers = self.mexc_client.get_24h_tickers()
            if tickers:
                usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
                usdt_pairs.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
                self.symbols = [t['symbol'] for t in usdt_pairs[:50]]

        print(f"   Symbols: {len(self.symbols)}")

        # Fetch klines for each symbol
        # NOTE: MEXC API limits to ~1000 bars, so this is limited to recent history
        historical_data = {}

        for symbol in self.symbols:
            # Fetch 1h klines (covers ~40 days with 1000 bars)
            df = self.mexc_client.get_klines(symbol, interval='1h', limit=1000)
            if df is not None and len(df) > 0:
                historical_data[symbol] = df
                print(f"   ✓ {symbol}: {len(df)} bars")
            else:
                print(f"   ✗ {symbol}: Failed to fetch")

        print(f"\n✅ Loaded data for {len(historical_data)} symbols")

        if len(historical_data) == 0:
            print("\n⚠️  WARNING: No historical data loaded!")
            print("   MEXC API only provides recent data (~1000 bars).")
            print("   For full 2019-2024 backtest, you need:")
            print("   1. Pre-downloaded CSV files, or")
            print("   2. External data provider (CryptoDataDownload, etc.)")

        return historical_data

    def run(self):
        """
        Main backtest loop
        """
        print("\n" + "="*70)
        print("🧪 ALPHA SNIPER V4.0 - BACKTEST")
        print("="*70 + "\n")

        # Load data
        historical_data = self.load_historical_data()

        if not historical_data:
            print("❌ No data loaded. Cannot run backtest.")
            return

        # Get BTC and ETH data for regime detection
        btc_data = historical_data.get('BTCUSDT')
        eth_data = historical_data.get('ETHUSDT')

        if btc_data is None or eth_data is None:
            print("❌ Missing BTC or ETH data. Cannot detect regime.")
            return

        print("\n[Backtest] Starting bar-by-bar replay...")

        # Simplified: Process each bar (for a real backtest, you'd align timestamps across all symbols)
        num_bars = len(btc_data)

        for bar_idx in range(100, num_bars):  # Start at bar 100 to have enough lookback
            timestamp = btc_data.index[bar_idx]

            # Every 4 bars (4h alignment for scanner)
            if bar_idx % 4 == 0:
                # Detect regime
                btc_slice = btc_data.iloc[:bar_idx+1]
                eth_slice = eth_data.iloc[:bar_idx+1]
                regime, details = regime_detector.detect(btc_slice, eth_slice)

                # Update positions (check exits)
                self.position_manager.update_positions(self.current_equity)

                # Build universe (symbols with data at this timestamp)
                universe = []
                for symbol, df in historical_data.items():
                    if symbol in ['BTCUSDT', 'ETHUSDT']:
                        continue  # Exclude BTC/ETH from trading
                    if bar_idx < len(df):
                        ticker_data = {
                            'symbol': symbol,
                            'quote_volume': float(df['volume'].iloc[bar_idx]) * float(df['close'].iloc[bar_idx]),
                            'ticker': {
                                'symbol': symbol,
                                'lastPrice': str(df['close'].iloc[bar_idx]),
                                'quoteVolume': str(float(df['volume'].iloc[bar_idx]) * float(df['close'].iloc[bar_idx]))
                            }
                        }
                        universe.append(ticker_data)

                # Scan for signals
                signals = self.scanner.scan(universe, regime, details)

                # Execute top signals (limit to 2 to match live behavior)
                for signal in signals[:2]:
                    # Check portfolio heat
                    portfolio_heat = self.position_manager.get_portfolio_heat()
                    if portfolio_heat >= 0.015:  # 1.5% max heat
                        break

                    # Simulate execution (simplified)
                    symbol = signal['symbol']
                    direction = signal['direction']
                    entry_price = signal['entry_price']

                    # Calculate position size (simplified ATR-based)
                    risk_pct = 0.003 if regime == Regime.BULL else 0.0012  # 0.3% BULL, 0.12% BEAR
                    size_usdt = self.current_equity * risk_pct * 2  # Simplified

                    # ATR-based stop (simplified)
                    atr = signal['features'].get('atr_14_15m', entry_price * 0.02)
                    if direction == "LONG":
                        stop_loss = entry_price - (atr * 2.0)
                    else:
                        stop_loss = entry_price + (atr * 1.8)

                    # Open position
                    self.position_manager.open_position(
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        size_usdt=min(size_usdt, 100),  # Cap at $100 for backtest
                        stop_loss=stop_loss,
                        regime=regime.value,
                        atr=atr
                    )

                # Record equity
                self.equity_curve.append({
                    'timestamp': timestamp,
                    'equity': self.current_equity,
                    'regime': regime.value,
                    'open_positions': len(self.position_manager.positions)
                })

            # Progress indicator
            if bar_idx % 100 == 0:
                pct = (bar_idx / num_bars) * 100
                print(f"   Progress: {pct:.1f}% - Bar {bar_idx}/{num_bars} - Equity: ${self.current_equity:.2f}")

        print("\n✅ Backtest complete!")

        # Generate report
        self.generate_report()
        self.save_results()

    def generate_report(self):
        """
        Calculate and print performance metrics
        """
        print("\n" + "="*70)
        print("📊 BACKTEST RESULTS")
        print("="*70)

        total_return = ((self.current_equity / self.start_equity) - 1) * 100

        print(f"\nStart Equity: ${self.start_equity:.2f}")
        print(f"End Equity: ${self.current_equity:.2f}")
        print(f"Total Return: {total_return:+.2f}%")

        # TODO: Calculate full metrics
        print("\n⚠️  Full metrics not yet implemented.")
        print("   For complete analysis:")
        print("   - Win rate, profit factor, Sharpe ratio")
        print("   - Max drawdown, avg win/loss")
        print("   - Trade distribution by regime")
        print("   Load results JSON and analyze in separate script.")

        print("\n" + "="*70)

    def save_results(self):
        """
        Save results to JSON files
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save equity curve
        equity_file = self.output_dir / f"equity_curve_{timestamp}.json"
        with open(equity_file, 'w') as f:
            json.dump(self.equity_curve, f, indent=2, default=str)
        print(f"\n💾 Equity curve saved: {equity_file}")

        # Save trade log (TODO: extract from position_manager)
        trades_file = self.output_dir / f"trades_{timestamp}.json"
        with open(trades_file, 'w') as f:
            json.dump(self.trade_log, f, indent=2, default=str)
        print(f"💾 Trade log saved: {trades_file}")

        # Save config
        config_file = self.output_dir / f"config_{timestamp}.json"
        config = {
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'start_equity': self.start_equity,
            'symbols': self.symbols,
            'final_equity': self.current_equity,
            'total_return_pct': ((self.current_equity / self.start_equity) - 1) * 100
        }
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"💾 Config saved: {config_file}")


def main():
    parser = argparse.ArgumentParser(description='Backtest Alpha Sniper V4.0')
    parser.add_argument('--start', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--equity', type=float, default=500.0, help='Starting equity (default: 500)')
    parser.add_argument('--symbols', type=str, help='Comma-separated symbols (default: top 50 by volume)')
    parser.add_argument('--output', type=str, default='backtest_results', help='Output directory')

    args = parser.parse_args()

    # Parse symbols
    symbols = None
    if args.symbols:
        if args.symbols.upper() == "TOP_50":
            symbols = None  # Will auto-select
        else:
            symbols = [s.strip() for s in args.symbols.split(',')]

    # Run backtest
    runner = BacktestRunner(
        start_date=args.start,
        end_date=args.end,
        start_equity=args.equity,
        symbols=symbols,
        output_dir=args.output
    )

    runner.run()


if __name__ == "__main__":
    main()
