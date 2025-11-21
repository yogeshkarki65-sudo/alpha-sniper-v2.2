#!/usr/bin/env python3
"""
Alpha Sniper V4.1 - Main Entry Point

Complete trading bot with:
- Regime-aware signal generation
- Bear-Resilient Long Engine
- Multi-level exits
- Live position tracking
- Telegram notifications
"""

import os
import sys
import time
import signal
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from v3.regime.detector import regime_detector, Regime
from v3.scanner.signals import signal_generator
from v3.risk.risk_engine import risk_engine
from v3.monitoring.status_reporter import status_reporter
from v3.monitoring.telegram_notifier import telegram
from v3.data.mexc_client import mexc_client


class AlphaSniperV4:
    """Alpha Sniper V4.1 Trading Bot"""

    # V4.1.1: Safety bounds for scanner interval
    MIN_SCANNER_INTERVAL = 60   # Minimum 60 seconds (safety guard)
    MAX_SCANNER_INTERVAL = 3600  # Maximum 1 hour
    DEFAULT_SCANNER_INTERVAL = 300  # 5 minutes (optimal from 2017-2025 backtest)

    def __init__(self):
        self.mode = os.getenv('MODE', 'SIM')
        self.equity = float(os.getenv(f'{self.mode}_EQUITY_START', 500))

        # V4.1.1: Scanner interval with safety bounds
        raw_interval = int(os.getenv('SCANNER_INTERVAL', str(self.DEFAULT_SCANNER_INTERVAL)))
        if raw_interval < self.MIN_SCANNER_INTERVAL:
            print(f"⚠️  SCANNER_INTERVAL={raw_interval}s is below minimum. Using {self.MIN_SCANNER_INTERVAL}s")
            self.scanner_interval = self.MIN_SCANNER_INTERVAL
        elif raw_interval > self.MAX_SCANNER_INTERVAL:
            print(f"⚠️  SCANNER_INTERVAL={raw_interval}s is above maximum. Using {self.MAX_SCANNER_INTERVAL}s")
            self.scanner_interval = self.MAX_SCANNER_INTERVAL
        else:
            self.scanner_interval = raw_interval

        self.running = True  # Flag for graceful shutdown
        self.last_regime = None  # Track regime changes for notifications

        print("=" * 80)
        print("🚀 ALPHA SNIPER V4.1.1 - Starting...")
        print("=" * 80)
        print(f"Mode: {self.mode}")
        print(f"Starting Equity: ${self.equity}")
        print(f"Scanner Interval: {self.scanner_interval}s")
        print("=" * 80)

        # Send startup notification
        telegram.send_startup(self.mode, self.equity)

    def update_regime(self):
        """Update market regime based on BTC and market breadth."""
        # Fetch BTC data
        btc_ticker = mexc_client.get_ticker_24h('BTCUSDT')

        if not btc_ticker:
            print("⚠️  Could not fetch BTC data, keeping current regime")
            return regime_detector.current_regime

        # Simplified regime update (you can enhance this)
        btc_data = {
            'price': float(btc_ticker.get('lastPrice', 0)),
            'ema20': float(btc_ticker.get('lastPrice', 0)),  # Simplified
            'ema50': float(btc_ticker.get('lastPrice', 0)),  # Simplified
            'volatility': 0.03,
            'trend': 0,
            'volume_trend': 0,
            'price_trend': 0
        }

        market_breadth = {
            'pct_above_50ma': 50  # Simplified
        }

        regime = regime_detector.update_regime(btc_data, market_breadth)

        print(f"📊 Current Regime: {regime.name}")

        # V4.1.1: Send Telegram notification on regime change
        if self.last_regime is not None and self.last_regime != regime:
            telegram.send_regime_change(self.last_regime.name, regime.name)
        self.last_regime = regime

        return regime

    def get_top_gainers(self, min_volume: float = 100000, limit: int = 50) -> list:
        """
        Get top gaining symbols from MEXC.

        Filters:
        - 24h volume > min_volume (USD)
        - Positive 24h change
        - USDT pairs only
        - Excludes stablecoins and leveraged tokens
        """
        print("📈 Fetching top gainers from MEXC...")

        all_tickers = mexc_client.get_all_tickers()
        if not all_tickers:
            print("⚠️  Could not fetch tickers, using fallback universe")
            return ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']

        # Filter and sort
        candidates = []
        exclude_patterns = ['UP', 'DOWN', 'BEAR', 'BULL', '3L', '3S', '2L', '2S',
                           'USDC', 'TUSD', 'BUSD', 'DAI', 'FDUSD']

        for ticker in all_tickers:
            symbol = ticker.get('symbol', '')

            # Only USDT pairs
            if not symbol.endswith('USDT'):
                continue

            # Skip leveraged tokens and stablecoins
            if any(pattern in symbol for pattern in exclude_patterns):
                continue

            try:
                volume = float(ticker.get('quoteVolume', 0))
                change_pct = float(ticker.get('priceChangePercent', 0))

                # Must have minimum volume and positive change
                if volume >= min_volume and change_pct > 0:
                    candidates.append({
                        'symbol': symbol,
                        'volume': volume,
                        'change_pct': change_pct
                    })
            except (ValueError, TypeError):
                continue

        # Sort by 24h change (descending)
        candidates.sort(key=lambda x: x['change_pct'], reverse=True)

        # Get top N symbols
        top_symbols = [c['symbol'] for c in candidates[:limit]]

        print(f"   Found {len(candidates)} candidates, scanning top {len(top_symbols)}")
        if top_symbols[:5]:
            print(f"   Top 5: {', '.join(top_symbols[:5])}")

        return top_symbols

    def scan_for_signals(self, regime: Regime):
        """Scan universe for trading signals."""
        # FIXED: Get TOP GAINERS dynamically instead of hardcoded large caps!
        min_volume = float(os.getenv('MIN_24H_QUOTE_VOLUME', 100000))
        universe = self.get_top_gainers(min_volume=min_volume, limit=50)

        print(f"\n🔍 Scanning {len(universe)} symbols in {regime.name} regime...")

        # Get BTC return for RS calculation
        btc_ticker = mexc_client.get_ticker_24h('BTCUSDT')
        btc_return_14d = 0  # Simplified, you can calculate actual

        # Scan universe
        signals = signal_generator.scan_universe(
            symbols=universe,
            regime=regime,
            equity=self.equity,
            btc_return_14d=btc_return_14d
        )

        if signals:
            print(f"✅ Found {len(signals)} signals")
            for sig in signals[:3]:  # Show top 3
                print(f"   {sig['symbol']}: {sig['direction']} @ ${sig['entry_price']:.6f} (score: {sig['score']}, engine: {sig.get('engine', 'standard')})")
        else:
            print("ℹ️  No signals found")

        return signals

    def execute_signals(self, signals: list):
        """Execute top signals based on available capital and R-based sizing."""
        if not signals:
            return

        for signal in signals:
            # Try to open position with R-based sizing
            position = risk_engine.open_position(signal, self.equity)

            if position:
                # Position opened - details already printed by risk_engine
                break  # Only open one position per scan (for safety)

    def manage_positions(self):
        """Update and manage open positions."""
        if not risk_engine.open_positions:
            return

        print(f"\n📊 Managing {len(risk_engine.open_positions)} open positions...")

        # Fetch current prices
        current_prices = {}
        for symbol in risk_engine.open_positions.keys():
            ticker = mexc_client.get_ticker_24h(symbol)
            if ticker:
                current_prices[symbol] = float(ticker.get('lastPrice', 0))

        # Update positions
        risk_engine.update_positions(current_prices)

        # Check exit conditions
        for symbol, position in list(risk_engine.open_positions.items()):
            if symbol not in current_prices:
                continue

            current_price = current_prices[symbol]
            hours_held = (datetime.now() - position.timestamp).total_seconds() / 3600

            should_exit, reason, exit_pct = position.should_exit(current_price, hours_held)

            if should_exit:
                risk_engine.close_position(symbol, current_price, reason)

    def run_scanner_cycle(self):
        """Run one complete scanner cycle."""
        try:
            print(f"\n{'='*80}")
            print(f"🔄 Scanner Cycle - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*80}")

            # 1. Update regime
            regime = self.update_regime()

            # 2. Manage existing positions
            self.manage_positions()

            # 3. Show current status
            status_reporter.print_status()

            # 4. Scan for new signals
            signals = self.scan_for_signals(regime)

            # 5. Execute signals
            self.execute_signals(signals)

            print(f"{'='*80}\n")

        except Exception as e:
            error_msg = f"Scanner cycle error: {e}"
            print(f"❌ {error_msg}")
            telegram.send_error(error_msg)
            import traceback
            traceback.print_exc()

    def stop(self):
        """Stop the bot gracefully."""
        self.running = False
        print("\n🔴 Stopping bot gracefully...")
        telegram.send_shutdown("User stopped (Ctrl+C)")

    def run(self):
        """Main loop."""
        print("\n✅ Alpha Sniper V4.1 started successfully!\n")

        # Run first cycle immediately
        self.run_scanner_cycle()

        # Main loop with graceful shutdown support
        while self.running:
            try:
                # Sleep in small increments to allow quick shutdown
                for _ in range(self.scanner_interval):
                    if not self.running:
                        break
                    time.sleep(1)

                if self.running:
                    self.run_scanner_cycle()

            except Exception as e:
                error_msg = f"Main loop error: {e}"
                print(f"❌ {error_msg}")
                telegram.send_error(error_msg)


# Global bot instance for signal handler
_bot_instance = None


def signal_handler(signum, frame):
    """Handle SIGINT (Ctrl+C) gracefully."""
    global _bot_instance
    if _bot_instance:
        _bot_instance.stop()
    else:
        print("\n🔴 Stopping...")
        telegram.send_shutdown("SIGINT received")
        sys.exit(0)


def main():
    """Entry point with graceful shutdown."""
    global _bot_instance

    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        _bot_instance = AlphaSniperV4()
        _bot_instance.run()
    except KeyboardInterrupt:
        print("\n🔴 Stopping bot gracefully...")
        telegram.send_shutdown("KeyboardInterrupt")
    except Exception as e:
        error_msg = f"Fatal error: {e}"
        print(f"❌ {error_msg}")
        telegram.send_error(error_msg)
        import traceback
        traceback.print_exc()
    finally:
        print("👋 Bot stopped.")


if __name__ == "__main__":
    main()
