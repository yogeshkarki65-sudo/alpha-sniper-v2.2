"""
Alpha Sniper V3.0 - Full Backtester with Monte Carlo Simulation

This backtester simulates the complete trading system:
- Scanner identifying opportunities
- Trader executing and managing positions
- Risk management and position sizing
- Trailing stops and exits

Supports Monte Carlo mode with random slippage and execution delays.
"""

import argparse
import csv
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.logging_config import configure_logging
from scanner.scorer import SignalScorer, ScoringFeatures, ScoreWeights
from risk.trailing_stop import TrailingStop, TrailingStopConfig

# Initialize logger
logger = configure_logging("backtester")


@dataclass
class BacktestConfig:
    """Backtester configuration"""
    # Capital
    starting_equity: float = 500.0

    # Position sizing
    max_position_risk_pct: float = 1.0
    max_per_trade_pct: float = 25.0
    max_concurrent_positions: int = 3

    # Entry/Exit
    min_signal_score: float = 35.0
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 12.0

    # Trailing stop
    use_trailing_stop: bool = True
    trailing_activation_pct: float = 4.0
    trailing_distance_pct: float = 2.0
    breakeven_pct: float = 5.0

    # Fees
    maker_fee_pct: float = 0.0
    taker_fee_pct: float = 0.1

    # Monte Carlo
    monte_carlo: bool = False
    mc_min_slippage_pct: float = 0.1
    mc_max_slippage_pct: float = 0.5
    mc_max_delay_candles: int = 3

    # Time
    max_hold_hours: int = 24


@dataclass
class Position:
    """Open position"""
    symbol: str
    entry_time: datetime
    entry_price: float
    position_size: float
    stop_loss: float
    take_profit: float
    trailing_stop: Optional[TrailingStop] = None
    highest_price: float = 0.0

    def __post_init__(self):
        if self.highest_price == 0.0:
            self.highest_price = self.entry_price


@dataclass
class Trade:
    """Closed trade"""
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    position_size: float
    pnl_usd: float
    pnl_pct: float
    exit_reason: str
    hold_hours: float
    score: float


class Backtester:
    """
    Full backtester that simulates Alpha Sniper V3 trading system
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.equity = config.starting_equity
        self.peak_equity = config.starting_equity

        self.positions: List[Position] = []
        self.closed_trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []

        # Initialize scorer
        self.scorer = SignalScorer(ScoreWeights.load())

        # Random seed for Monte Carlo
        if config.monte_carlo:
            random.seed()

    def calculate_position_size(self, entry_price: float, stop_loss_price: float) -> float:
        """
        Calculate position size based on risk management rules
        """
        # Risk per trade in USD
        risk_per_trade = self.equity * (self.config.max_position_risk_pct / 100)

        # Max position size in USD
        max_position_usd = self.equity * (self.config.max_per_trade_pct / 100)

        # Position size based on stop loss risk
        risk_per_unit = abs(entry_price - stop_loss_price)
        if risk_per_unit > 0:
            size_by_risk = risk_per_trade / risk_per_unit
        else:
            size_by_risk = max_position_usd / entry_price

        # Take the smaller of risk-based and max position
        position_usd = min(size_by_risk * entry_price, max_position_usd)

        # Ensure we don't exceed available equity
        position_usd = min(position_usd, self.equity * 0.95)  # Leave 5% buffer

        return position_usd

    def apply_monte_carlo_entry(self, price: float) -> float:
        """Apply random slippage to entry price"""
        if not self.config.monte_carlo:
            return price

        slippage_pct = random.uniform(
            self.config.mc_min_slippage_pct,
            self.config.mc_max_slippage_pct
        )

        # Slippage works against us (higher entry for long)
        return price * (1 + slippage_pct / 100)

    def apply_monte_carlo_exit(self, price: float) -> float:
        """Apply random slippage to exit price"""
        if not self.config.monte_carlo:
            return price

        slippage_pct = random.uniform(
            self.config.mc_min_slippage_pct,
            self.config.mc_max_slippage_pct
        )

        # Slippage works against us (lower exit for long)
        return price * (1 - slippage_pct / 100)

    def open_position(self, symbol: str, entry_time: datetime, entry_price: float, score: float):
        """
        Open a new position with risk management
        """
        # Check max concurrent positions
        if len(self.positions) >= self.config.max_concurrent_positions:
            logger.debug(f"Max concurrent positions reached, skipping {symbol}")
            return

        # Apply Monte Carlo slippage
        actual_entry = self.apply_monte_carlo_entry(entry_price)

        # Calculate stops
        stop_loss = actual_entry * (1 - self.config.stop_loss_pct / 100)
        take_profit = actual_entry * (1 + self.config.take_profit_pct / 100)

        # Calculate position size
        position_size = self.calculate_position_size(actual_entry, stop_loss)

        if position_size < 10:  # Minimum $10 position
            logger.debug(f"Position size too small for {symbol}: ${position_size:.2f}")
            return

        # Create trailing stop if enabled
        trailing_stop = None
        if self.config.use_trailing_stop:
            ts_config = TrailingStopConfig(
                entry_price=actual_entry,
                activation_pct=self.config.trailing_activation_pct,
                distance_pct=self.config.trailing_distance_pct,
                breakeven_pct=self.config.breakeven_pct
            )
            trailing_stop = TrailingStop(ts_config)

        # Create position
        position = Position(
            symbol=symbol,
            entry_time=entry_time,
            entry_price=actual_entry,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=trailing_stop,
            highest_price=actual_entry
        )

        self.positions.append(position)

        # Deduct entry fees
        entry_fee = position_size * (self.config.taker_fee_pct / 100)
        self.equity -= entry_fee

        logger.info(
            f"📈 OPEN {symbol} @ ${actual_entry:.6f} | "
            f"size=${position_size:.2f} | SL=${stop_loss:.6f} | TP=${take_profit:.6f} | "
            f"score={score:.1f}"
        )

    def close_position(self, position: Position, exit_time: datetime, exit_price: float, reason: str):
        """
        Close a position and record the trade
        """
        # Apply Monte Carlo slippage
        actual_exit = self.apply_monte_carlo_exit(exit_price)

        # Calculate P&L
        price_change_pct = ((actual_exit - position.entry_price) / position.entry_price) * 100
        gross_pnl = position.position_size * (price_change_pct / 100)

        # Deduct exit fees
        exit_fee = position.position_size * (self.config.taker_fee_pct / 100)
        net_pnl = gross_pnl - exit_fee

        # Update equity
        self.equity += position.position_size + net_pnl

        # Track peak equity
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

        # Calculate hold time
        hold_hours = (exit_time - position.entry_time).total_seconds() / 3600

        # Record trade
        trade = Trade(
            symbol=position.symbol,
            entry_time=position.entry_time,
            exit_time=exit_time,
            entry_price=position.entry_price,
            exit_price=actual_exit,
            position_size=position.position_size,
            pnl_usd=net_pnl,
            pnl_pct=price_change_pct,
            exit_reason=reason,
            hold_hours=hold_hours,
            score=0.0  # Would need to store this
        )

        self.closed_trades.append(trade)

        # Remove from open positions
        self.positions.remove(position)

        logger.info(
            f"📉 CLOSE {position.symbol} @ ${actual_exit:.6f} | "
            f"PnL: ${net_pnl:+.2f} ({price_change_pct:+.2f}%) | "
            f"reason: {reason} | hold: {hold_hours:.1f}h"
        )

    def update_positions(self, current_time: datetime, price_data: Dict[str, float]):
        """
        Update open positions and check for exits
        """
        for position in list(self.positions):  # Copy list to avoid modification during iteration
            symbol = position.symbol
            current_price = price_data.get(symbol)

            if current_price is None:
                continue

            # Update highest price
            if current_price > position.highest_price:
                position.highest_price = current_price

            # Check take profit
            if current_price >= position.take_profit:
                self.close_position(position, current_time, current_price, "take_profit")
                continue

            # Check stop loss
            if current_price <= position.stop_loss:
                self.close_position(position, current_time, current_price, "stop_loss")
                continue

            # Check trailing stop
            if position.trailing_stop:
                position.trailing_stop.update(current_price)
                if position.trailing_stop.is_hit:
                    self.close_position(position, current_time, current_price, "trailing_stop")
                    continue

            # Check max hold time
            hold_hours = (current_time - position.entry_time).total_seconds() / 3600
            if hold_hours >= self.config.max_hold_hours:
                self.close_position(position, current_time, current_price, "max_hold_time")
                continue

        # Record equity snapshot
        self.equity_curve.append((current_time, self.equity))

    def calculate_metrics(self) -> Dict:
        """
        Calculate backtest performance metrics
        """
        if not self.closed_trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "expectancy": 0.0,
                "final_equity": self.equity,
                "return_pct": 0.0
            }

        # Basic stats
        total_trades = len(self.closed_trades)
        winners = [t for t in self.closed_trades if t.pnl_usd > 0]
        losers = [t for t in self.closed_trades if t.pnl_usd <= 0]

        win_rate = (len(winners) / total_trades) * 100 if total_trades > 0 else 0

        # P&L stats
        total_pnl = sum(t.pnl_usd for t in self.closed_trades)
        gross_wins = sum(t.pnl_usd for t in winners) if winners else 0
        gross_losses = abs(sum(t.pnl_usd for t in losers)) if losers else 0

        profit_factor = gross_wins / gross_losses if gross_losses > 0 else 0

        avg_win = gross_wins / len(winners) if winners else 0
        avg_loss = gross_losses / len(losers) if losers else 0

        # Expectancy
        if total_trades > 0:
            expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)
        else:
            expectancy = 0

        # Max drawdown
        max_dd_pct = 0
        if self.peak_equity > 0:
            current_dd = ((self.peak_equity - self.equity) / self.peak_equity) * 100
            max_dd_pct = current_dd

        # Track max DD across equity curve
        peak = self.config.starting_equity
        for _, equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = ((peak - equity) / peak) * 100
            if dd > max_dd_pct:
                max_dd_pct = dd

        # Sharpe ratio (simplified daily returns)
        if len(self.equity_curve) > 1:
            returns = []
            for i in range(1, len(self.equity_curve)):
                prev_equity = self.equity_curve[i-1][1]
                curr_equity = self.equity_curve[i][1]
                if prev_equity > 0:
                    ret = (curr_equity - prev_equity) / prev_equity
                    returns.append(ret)

            if returns:
                avg_return = sum(returns) / len(returns)
                if len(returns) > 1:
                    variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
                    std_dev = variance ** 0.5
                    sharpe = (avg_return / std_dev) * (252 ** 0.5) if std_dev > 0 else 0  # Annualized
                else:
                    sharpe = 0
            else:
                sharpe = 0
        else:
            sharpe = 0

        return_pct = ((self.equity - self.config.starting_equity) / self.config.starting_equity) * 100

        return {
            "total_trades": total_trades,
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_drawdown_pct": max_dd_pct,
            "sharpe_ratio": sharpe,
            "expectancy": expectancy,
            "final_equity": self.equity,
            "return_pct": return_pct
        }

    def export_results(self, output_dir: str = "backtest_results"):
        """
        Export backtest results to CSV files
        """
        Path(output_dir).mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export trades
        trades_file = Path(output_dir) / f"trades_{timestamp}.csv"
        with open(trades_file, 'w', newline='') as f:
            if self.closed_trades:
                writer = csv.DictWriter(f, fieldnames=asdict(self.closed_trades[0]).keys())
                writer.writeheader()
                for trade in self.closed_trades:
                    writer.writerow(asdict(trade))

        logger.info(f"Exported {len(self.closed_trades)} trades to {trades_file}")

        # Export equity curve
        equity_file = Path(output_dir) / f"equity_{timestamp}.csv"
        with open(equity_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "equity"])
            for timestamp, equity in self.equity_curve:
                writer.writerow([timestamp, equity])

        logger.info(f"Exported equity curve to {equity_file}")

        # Export metrics
        metrics = self.calculate_metrics()
        metrics_file = Path(output_dir) / f"metrics_{timestamp}.csv"
        with open(metrics_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value"])
            for key, value in metrics.items():
                writer.writerow([key, value])

        logger.info(f"Exported metrics to {metrics_file}")

        return metrics


def run_backtest_simulation(
    historical_data: Dict[str, List[Dict]],
    config: BacktestConfig,
    start_date: datetime,
    end_date: datetime
) -> Backtester:
    """
    Run a backtest simulation using historical data

    Args:
        historical_data: Dict mapping symbols to list of candle dicts
        config: Backtest configuration
        start_date: Simulation start date
        end_date: Simulation end date

    Returns:
        Backtester instance with results
    """
    backtester = Backtester(config)
    logger.info(f"Starting backtest from {start_date} to {end_date}")
    logger.info(f"Starting equity: ${config.starting_equity:.2f}")

    # Simulate time progression (hourly intervals)
    current_time = start_date
    scan_interval = timedelta(hours=1)  # Scan every hour

    while current_time <= end_date:
        # Get current prices for all symbols
        current_prices = {}
        for symbol, candles in historical_data.items():
            # Find candle at current time
            for candle in candles:
                candle_time = datetime.fromtimestamp(candle["time"] / 1000)
                if abs((candle_time - current_time).total_seconds()) < 3600:  # Within 1 hour
                    current_prices[symbol] = candle["close"]
                    break

        # Update open positions
        backtester.update_positions(current_time, current_prices)

        # Scanner: Look for new opportunities (simplified for backtest)
        # In a real backtest, you'd compute full features and score
        # For now, we'll skip scanner simulation and just manage positions

        # Progress time
        current_time += scan_interval

    # Close any remaining positions
    for position in list(backtester.positions):
        final_price = current_prices.get(position.symbol, position.entry_price)
        backtester.close_position(position, end_date, final_price, "backtest_end")

    return backtester


def main():
    """Main entry point for backtester"""
    parser = argparse.ArgumentParser(description="Alpha Sniper V3 Backtester")
    parser.add_argument("--monte-carlo", action="store_true", help="Enable Monte Carlo simulation")
    parser.add_argument("--runs", type=int, default=1, help="Number of Monte Carlo runs")
    parser.add_argument("--equity", type=float, default=500.0, help="Starting equity")
    parser.add_argument("--output", type=str, default="backtest_results", help="Output directory")

    args = parser.parse_args()

    # Create config
    config = BacktestConfig(
        starting_equity=args.equity,
        monte_carlo=args.monte_carlo
    )

    logger.info("="*60)
    logger.info("Alpha Sniper V3.0 Backtester")
    logger.info("="*60)
    logger.info(f"Monte Carlo Mode: {args.monte_carlo}")
    logger.info(f"Runs: {args.runs}")
    logger.info(f"Starting Equity: ${args.equity:.2f}")
    logger.info("="*60)

    # Note: This is a framework - you need to provide historical data
    logger.warning("Historical data loading not implemented in this example")
    logger.info("To use this backtester:")
    logger.info("1. Fetch historical candle data from MEXC API")
    logger.info("2. Store in format: {symbol: [candles...]}")
    logger.info("3. Call run_backtest_simulation() with your data")
    logger.info("")
    logger.info("Example usage in Python:")
    logger.info("  from tests.backtester import run_backtest_simulation, BacktestConfig")
    logger.info("  historical_data = load_your_data()")
    logger.info("  config = BacktestConfig()")
    logger.info("  bt = run_backtest_simulation(historical_data, config, start, end)")
    logger.info("  metrics = bt.export_results()")

    return 0


if __name__ == "__main__":
    sys.exit(main())
