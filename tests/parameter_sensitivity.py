"""
Parameter Sensitivity Testing Framework for Alpha Sniper Strategy.

Tests multiple parameter configurations to find robust settings that:
- Survive 2022 bear market drawdowns
- Profit in 2023-2025 bull markets
- Have smooth equity curves (no death spirals)

Parameter Sensitivity Grid:
===========================
Risk parameters: {0.2%,0.4%,0.6%}
Portfolio heat: {1%,1.5%,2%}
Daily loss limit: {1%,2%,3%}
ATR multipliers: atr_sl_mult{1.5,2.0,2.5}, tp1_mult{1.5,2.0,2.5}, tp2_mult{2.5,3.0,3.5}, trail_mult{1.0,1.5,2.0}
RVOL thresholds: bull{1.5,2.0,2.5}, sideways{2.5,3.0,3.5}, bear{3.0,4.0,5.0}
Regime thresholds: z_bull{0.3,0.5,0.7}, z_bear{-0.3,-0.5,-0.7}
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime
from itertools import product
import logging
import json
from pathlib import Path

from strategies.alpha_sniper import AlphaSniperStrategy
from data.backtest_engine import BacktestEngine
from data.fetcher import DataFetcher
from data.storage import DataStorage

logger = logging.getLogger(__name__)


class ParameterSensitivityTester:
    """
    Runs grid search over parameter space to find robust configurations.
    """

    def __init__(self, output_dir: str = 'results/sensitivity'):
        """
        Initialize sensitivity tester.

        Args:
            output_dir: Directory to save results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: List[Dict] = []

        logger.info(f"ParameterSensitivityTester initialized, output: {self.output_dir}")

    def define_parameter_grid(self) -> Dict[str, List]:
        """
        Define parameter grid for testing.

        Returns:
            Dictionary mapping parameter name to list of values
        """
        grid = {
            # Risk parameters
            'risk_pct_bull': [0.002, 0.004, 0.006],  # 0.2%, 0.4%, 0.6%
            'risk_pct_sideways': [0.00125, 0.0025, 0.00375],  # 0.125%, 0.25%, 0.375%
            'risk_pct_bear': [0.0008, 0.0012, 0.0016],  # 0.08%, 0.12%, 0.16%

            # Portfolio limits
            'max_portfolio_heat': [0.01, 0.015, 0.02],  # 1%, 1.5%, 2%
            'max_daily_loss_pct': [0.01, 0.02, 0.03],  # 1%, 2%, 3%

            # ATR multipliers
            'atr_sl_mult': [1.5, 2.0, 2.5],
            'tp1_mult': [1.5, 2.0, 2.5],
            'tp2_mult': [2.5, 3.0, 3.5],
            'trail_mult': [1.0, 1.5, 2.0],

            # Regime thresholds
            'z_bull_threshold': [0.3, 0.5, 0.7],
            'z_bear_threshold': [-0.7, -0.5, -0.3],

            # Adaptive threshold parameters
            'cold_start_threshold': [0.55, 0.60, 0.65],
            'min_samples_adaptive': [150, 200, 250]
        }

        return grid

    def define_rvol_threshold_grid(self) -> List[Dict]:
        """
        Define RVOL threshold combinations.

        Returns:
            List of RVOL threshold configurations
        """
        return [
            {'bull': 1.5, 'sideways': 2.5, 'bear': 3.0},
            {'bull': 2.0, 'sideways': 3.0, 'bear': 4.0},
            {'bull': 2.5, 'sideways': 3.5, 'bear': 5.0}
        ]

    def create_config(self, params: Dict) -> Dict:
        """
        Create strategy configuration from parameters.

        Args:
            params: Parameter dictionary

        Returns:
            Configuration dictionary for strategy
        """
        return {
            'z_bull_threshold': params.get('z_bull_threshold', 0.5),
            'z_bear_threshold': params.get('z_bear_threshold', -0.5),
            'rs_alt_threshold': params.get('rs_alt_threshold', 0.0),
            'risk_pct_bull': params.get('risk_pct_bull', 0.004),
            'risk_pct_sideways': params.get('risk_pct_sideways', 0.0025),
            'risk_pct_bear': params.get('risk_pct_bear', 0.0012),
            'max_portfolio_heat': params.get('max_portfolio_heat', 0.015),
            'max_daily_loss_pct': params.get('max_daily_loss_pct', 0.02),
            'atr_sl_mult': params.get('atr_sl_mult', 2.0),
            'tp1_mult': params.get('tp1_mult', 2.0),
            'tp2_mult': params.get('tp2_mult', 3.0),
            'trail_mult': params.get('trail_mult', 1.5),
            'tp1_exit_pct': params.get('tp1_exit_pct', 0.50),
            'tp2_exit_pct': params.get('tp2_exit_pct', 0.30),
            'cold_start_threshold': params.get('cold_start_threshold', 0.60),
            'min_samples_adaptive': params.get('min_samples_adaptive', 200),
            'global_warmstart': True,
            'training_period_days': 30
        }

    def run_grid_search(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        sample_size: Optional[int] = None,
        interval: str = '15m'
    ) -> pd.DataFrame:
        """
        Run grid search over parameter space.

        Args:
            symbols: List of symbols to test
            start_date: Backtest start date
            end_date: Backtest end date
            sample_size: Optional random sample size (for faster testing)
            interval: Data interval

        Returns:
            DataFrame with results for all configurations
        """
        logger.info("Starting parameter grid search...")

        # Define grid
        param_grid = self.define_parameter_grid()

        # Generate all combinations
        keys = list(param_grid.keys())
        values = list(param_grid.values())

        all_combinations = list(product(*values))
        total_configs = len(all_combinations)

        logger.info(f"Total configurations to test: {total_configs}")

        # Sample if requested
        if sample_size and sample_size < total_configs:
            import random
            all_combinations = random.sample(all_combinations, sample_size)
            logger.info(f"Sampled {sample_size} configurations for testing")

        # Run backtests
        for idx, combo in enumerate(all_combinations):
            params = dict(zip(keys, combo))
            config_id = idx + 1

            logger.info(f"\nTesting configuration {config_id}/{len(all_combinations)}")
            logger.info(f"Parameters: {params}")

            try:
                # Create configuration
                config = self.create_config(params)

                # Run backtest
                result = self._run_single_backtest(
                    config=config,
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval
                )

                # Add config info to result
                result['config_id'] = config_id
                result['params'] = params

                self.results.append(result)

                # Save intermediate results
                if config_id % 10 == 0:
                    self._save_intermediate_results()

            except Exception as e:
                logger.error(f"Error testing config {config_id}: {e}")
                continue

        # Convert to DataFrame
        results_df = pd.DataFrame(self.results)

        # Save final results
        self._save_results(results_df)

        # Analyze and rank
        ranked_df = self._rank_configurations(results_df)

        return ranked_df

    def _run_single_backtest(
        self,
        config: Dict,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> Dict:
        """
        Run single backtest with given configuration.

        Args:
            config: Strategy configuration
            symbols: Symbols to trade
            start_date: Start date
            end_date: End date
            interval: Data interval

        Returns:
            Results dictionary
        """
        # Create strategy
        strategy = AlphaSniperStrategy(config=config)

        # Create backtest engine
        engine = BacktestEngine(
            strategy=strategy,
            initial_equity=10000.0,
            commission_pct=0.001,
            slippage_pct=0.0005
        )

        # Run backtest
        backtest_results = engine.run_backtest(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            interval=interval
        )

        # Extract metrics
        metrics = backtest_results.get('metrics', {})

        return {
            'config': config,
            'total_trades': metrics.get('total_trades', 0),
            'win_rate': metrics.get('win_rate', 0),
            'total_return_pct': metrics.get('total_return_pct', 0),
            'sharpe_ratio': metrics.get('sharpe_ratio', 0),
            'max_drawdown_pct': metrics.get('max_drawdown_pct', 0),
            'calmar_ratio': metrics.get('calmar_ratio', 0),
            'profit_factor': metrics.get('profit_factor', 0),
            'final_equity': metrics.get('final_equity', 0)
        }

    def _rank_configurations(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """
        Rank configurations by composite score.

        Criteria:
        1. Positive total return
        2. Sharpe ratio > 1.0
        3. Max drawdown < 30%
        4. Sufficient trades (> 20)
        5. Calmar ratio (return / max DD)

        Args:
            results_df: Results DataFrame

        Returns:
            Ranked DataFrame
        """
        if results_df.empty:
            return results_df

        # Filter criteria
        valid = results_df[
            (results_df['total_return_pct'] > 0) &
            (results_df['max_drawdown_pct'] > -50) &
            (results_df['total_trades'] >= 20)
        ].copy()

        if valid.empty:
            logger.warning("No configurations met minimum criteria")
            return results_df

        # Calculate composite score
        # Normalize metrics to 0-1 scale
        valid['norm_return'] = (valid['total_return_pct'] - valid['total_return_pct'].min()) / \
                                (valid['total_return_pct'].max() - valid['total_return_pct'].min() + 1e-6)

        valid['norm_sharpe'] = (valid['sharpe_ratio'] - valid['sharpe_ratio'].min()) / \
                               (valid['sharpe_ratio'].max() - valid['sharpe_ratio'].min() + 1e-6)

        # Invert drawdown (lower is better)
        valid['norm_dd'] = 1 - ((valid['max_drawdown_pct'] - valid['max_drawdown_pct'].min()) / \
                                (valid['max_drawdown_pct'].max() - valid['max_drawdown_pct'].min() + 1e-6))

        valid['norm_calmar'] = (valid['calmar_ratio'] - valid['calmar_ratio'].min()) / \
                               (valid['calmar_ratio'].max() - valid['calmar_ratio'].min() + 1e-6)

        # Composite score (weighted average)
        valid['composite_score'] = (
            0.3 * valid['norm_return'] +
            0.3 * valid['norm_sharpe'] +
            0.2 * valid['norm_dd'] +
            0.2 * valid['norm_calmar']
        )

        # Sort by composite score
        ranked = valid.sort_values('composite_score', ascending=False)

        logger.info(f"\nTop 5 configurations:")
        for idx, row in ranked.head(5).iterrows():
            logger.info(
                f"Rank {idx+1}: Return={row['total_return_pct']:.2f}%, "
                f"Sharpe={row['sharpe_ratio']:.2f}, DD={row['max_drawdown_pct']:.2f}%, "
                f"Score={row['composite_score']:.3f}"
            )

        return ranked

    def _save_results(self, results_df: pd.DataFrame):
        """Save results to CSV."""
        output_file = self.output_dir / 'sensitivity_results.csv'
        results_df.to_csv(output_file, index=False)
        logger.info(f"Results saved to {output_file}")

    def _save_intermediate_results(self):
        """Save intermediate results during grid search."""
        if self.results:
            results_df = pd.DataFrame(self.results)
            output_file = self.output_dir / 'sensitivity_results_partial.csv'
            results_df.to_csv(output_file, index=False)

    def test_robustness_across_periods(
        self,
        config: Dict,
        symbols: List[str],
        interval: str = '15m'
    ) -> Dict:
        """
        Test configuration robustness across different market periods.

        Args:
            config: Strategy configuration to test
            symbols: Symbols to trade
            interval: Data interval

        Returns:
            Dictionary with period-specific results
        """
        # Define test periods
        periods = {
            'bear_2022': (datetime(2022, 1, 1), datetime(2022, 12, 31)),
            'bull_2023': (datetime(2023, 1, 1), datetime(2023, 12, 31)),
            'bull_2024': (datetime(2024, 1, 1), datetime(2024, 12, 31)),
        }

        results = {}

        for period_name, (start, end) in periods.items():
            logger.info(f"Testing period: {period_name}")

            try:
                result = self._run_single_backtest(
                    config=config,
                    symbols=symbols,
                    start_date=start,
                    end_date=end,
                    interval=interval
                )

                results[period_name] = result

            except Exception as e:
                logger.error(f"Error testing period {period_name}: {e}")
                results[period_name] = {'error': str(e)}

        return results


def main():
    """Main function for parameter sensitivity testing."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Example usage
    tester = ParameterSensitivityTester(output_dir='results/sensitivity')

    # Test symbols (altcoins)
    symbols = [
        'SOLUSDT', 'AVAXUSDT', 'MATICUSDT', 'LINKUSDT', 'UNIUSDT',
        'AAVEUSDT', 'ATOMUSDT', 'DOTUSDT', 'NEARUSDT', 'FTMUSDT'
    ]

    # Date range
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 12, 31)

    # Run grid search (sample 50 configs for speed)
    results_df = tester.run_grid_search(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        sample_size=50,
        interval='15m'
    )

    print("\nGrid search complete!")
    print(f"Tested {len(results_df)} configurations")
    print(f"\nTop 3 configurations:")
    print(results_df.head(3)[['total_return_pct', 'sharpe_ratio', 'max_drawdown_pct', 'composite_score']])


if __name__ == '__main__':
    main()
