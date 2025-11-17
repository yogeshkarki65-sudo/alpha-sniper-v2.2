"""
Alpha Sniper V2.2 - Backtesting Script

Full implementation of backtesting engine using the Alpha Sniper strategy.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import logging
from datetime import datetime
from typing import List, Optional

from strategies.alpha_sniper import AlphaSniperStrategy
from data.backtest_engine import BacktestEngine
from data.fetcher import DataFetcher
from data.storage import DataStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BacktestRunner:
    """
    Runner for Alpha Sniper backtests.
    """

    def __init__(self):
        """Initialize backtest runner."""
        self.fetcher = DataFetcher(source='binance')
        self.storage = DataStorage(base_path='data/historical')

    def fetch_and_store_data(
        self,
        symbols: List[str],
        interval: str,
        start_date: datetime,
        end_date: datetime
    ) -> None:
        """
        Fetch and store historical data for backtesting.

        Args:
            symbols: List of symbols to fetch
            interval: Data interval ('5m', '15m', '1h', '4h', '1d')
            start_date: Start date
            end_date: End date
        """
        logger.info(f"Fetching data for {len(symbols)} symbols...")

        for symbol in symbols:
            logger.info(f"Fetching {symbol}...")

            try:
                df = self.fetcher.fetch_historical_range(
                    symbol=symbol,
                    interval=interval,
                    start_date=start_date,
                    end_date=end_date
                )

                if not df.empty:
                    self.storage.save_ohlcv(symbol, interval, df, format='parquet')
                    logger.info(f"Saved {len(df)} candles for {symbol}")
                else:
                    logger.warning(f"No data fetched for {symbol}")

            except Exception as e:
                logger.error(f"Error fetching {symbol}: {e}")

        # Fetch market indices (BTC, TOTAL3)
        logger.info("Fetching market indices...")
        market_data = self.fetcher.fetch_market_indices(interval, start_date, end_date)

        if 'BTC' in market_data:
            self.storage.save_ohlcv('BTCUSDT', interval, market_data['BTC'], format='parquet')
            logger.info(f"Saved {len(market_data['BTC'])} candles for BTC")

        if 'TOTAL3' in market_data:
            self.storage.save_ohlcv('TOTAL3', interval, market_data['TOTAL3'], format='parquet')
            logger.info(f"Saved {len(market_data['TOTAL3'])} candles for TOTAL3")

    def run_backtest(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        interval: str = '15m',
        config: Optional[dict] = None,
        initial_equity: float = 10000.0
    ) -> dict:
        """
        Run backtest with specified parameters.

        Args:
            symbols: List of symbols to trade
            start_date: Backtest start date
            end_date: Backtest end date
            interval: Data interval
            config: Strategy configuration (uses defaults if None)
            initial_equity: Starting capital

        Returns:
            Backtest results dictionary
        """
        logger.info("="*80)
        logger.info("ALPHA SNIPER V2.2 - BACKTEST")
        logger.info("="*80)
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Symbols: {len(symbols)}")
        logger.info(f"Interval: {interval}")
        logger.info(f"Initial Equity: ${initial_equity:.2f}")
        logger.info("="*80)

        # Create strategy with config
        if config is None:
            config = self._get_default_config()

        strategy = AlphaSniperStrategy(config=config)

        # Create backtest engine
        engine = BacktestEngine(
            strategy=strategy,
            initial_equity=initial_equity,
            commission_pct=0.001,
            slippage_pct=0.0005
        )

        # Load BTC and TOTAL3 data
        btc_data = self.storage.load_ohlcv('BTCUSDT', interval, start_date, end_date)
        total3_data = self.storage.load_ohlcv('TOTAL3', interval, start_date, end_date)

        if btc_data.empty:
            logger.error("BTC data not found. Run fetch_and_store_data first.")
            return {'error': 'Missing BTC data'}

        if total3_data.empty:
            logger.warning("TOTAL3 data not found, will attempt to create proxy")
            # Could create proxy here if needed
            return {'error': 'Missing TOTAL3 data'}

        # Run backtest
        results = engine.run_backtest(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            btc_data=btc_data,
            total3_data=total3_data
        )

        # Print results
        self._print_results(results)

        # Save results
        output_dir = f"results/backtest_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        engine.save_results(output_dir)

        return results

    def _get_default_config(self) -> dict:
        """Get default strategy configuration."""
        return {
            # Regime detection
            'z_bull_threshold': 0.5,
            'z_bear_threshold': -0.5,
            'rs_alt_threshold': 0.0,

            # Risk management
            'risk_pct_bull': 0.0040,  # 0.40%
            'risk_pct_sideways': 0.0025,  # 0.25%
            'risk_pct_bear': 0.0012,  # 0.12%
            'max_portfolio_heat': 0.015,  # 1.5%
            'max_daily_loss_pct': 0.02,  # 2%

            # ATR parameters
            'atr_sl_mult': 2.0,
            'tp1_mult': 2.0,
            'tp2_mult': 3.0,
            'trail_mult': 1.5,

            # Exit percentages
            'tp1_exit_pct': 0.50,  # 50%
            'tp2_exit_pct': 0.30,  # 30%

            # Adaptive threshold
            'cold_start_threshold': 0.60,
            'min_samples_adaptive': 200,
            'global_warmstart': True,
            'training_period_days': 30
        }

    def _print_results(self, results: dict):
        """Print backtest results."""
        if 'error' in results:
            logger.error(f"Backtest error: {results['error']}")
            return

        metrics = results.get('metrics', {})

        logger.info("\n" + "="*80)
        logger.info("BACKTEST RESULTS")
        logger.info("="*80)

        logger.info(f"Total Trades: {metrics.get('total_trades', 0)}")
        logger.info(f"Winning Trades: {metrics.get('winning_trades', 0)}")
        logger.info(f"Losing Trades: {metrics.get('losing_trades', 0)}")
        logger.info(f"Win Rate: {metrics.get('win_rate', 0):.2%}")

        logger.info("\nPROFITABILITY")
        logger.info(f"Total Return: {metrics.get('total_return_pct', 0):.2f}%")
        logger.info(f"Final Equity: ${metrics.get('final_equity', 0):.2f}")
        logger.info(f"Total PnL: ${metrics.get('total_pnl', 0):.2f}")

        logger.info("\nRISK METRICS")
        logger.info(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        logger.info(f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%")
        logger.info(f"Calmar Ratio: {metrics.get('calmar_ratio', 0):.2f}")

        logger.info("\nTRADE METRICS")
        logger.info(f"Average Win: ${metrics.get('avg_win', 0):.2f}")
        logger.info(f"Average Loss: ${metrics.get('avg_loss', 0):.2f}")
        logger.info(f"Profit Factor: {metrics.get('profit_factor', 0):.2f}")

        logger.info("="*80)


def main():
    """Main function for backtesting."""
    runner = BacktestRunner()

    # Define symbols to test (top altcoins)
    symbols = [
        'SOLUSDT', 'AVAXUSDT', 'MATICUSDT', 'LINKUSDT', 'UNIUSDT',
        'AAVEUSDT', 'ATOMUSDT', 'DOTUSDT', 'NEARUSDT', 'FTMUSDT',
        'SANDUSDT', 'MANAUSDT', 'ALGOUSDT', 'ICPUSDT', 'FILUSDT'
    ]

    # Date range
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 12, 31)
    interval = '15m'

    # Step 1: Fetch and store data (run once)
    # Uncomment to fetch data:
    # logger.info("Fetching historical data...")
    # runner.fetch_and_store_data(
    #     symbols=symbols,
    #     interval=interval,
    #     start_date=start_date,
    #     end_date=end_date
    # )

    # Step 2: Run backtest
    logger.info("Running backtest...")
    results = runner.run_backtest(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        initial_equity=10000.0
    )

    logger.info("\nBacktest complete!")


if __name__ == "__main__":
    main()
