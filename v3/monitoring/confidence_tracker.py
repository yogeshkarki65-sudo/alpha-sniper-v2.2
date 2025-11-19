"""
Confidence Tracker - Monitors SIM performance and recommends LIVE trading

Tracks:
- Win rate
- Average R-multiple
- Sharpe ratio
- Max drawdown
- Consecutive wins/losses
- Total P&L

Recommends switching to LIVE when confidence thresholds met:
- Min 30 trades
- Win rate ≥ 55%
- Avg R ≥ 0.8
- Max DD < 8%
- No streak > 5 losses
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np


@dataclass
class ConfidenceMetrics:
    """Performance metrics for confidence assessment"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_r_multiple: float = 0.0
    max_drawdown_pct: float = 0.0
    current_streak: int = 0  # Positive = wins, negative = losses
    max_win_streak: int = 0
    max_loss_streak: int = 0
    avg_win_r: float = 0.0
    avg_loss_r: float = 0.0
    largest_win_r: float = 0.0
    largest_loss_r: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    last_updated: str = ""

    # Confidence score (0-100)
    confidence_score: float = 0.0
    live_ready: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


class ConfidenceTracker:
    """
    Tracks SIM trading performance and calculates confidence score
    """

    def __init__(self, filepath: str = "sim_performance.json"):
        """Initialize tracker"""
        self.filepath = filepath
        self.metrics = ConfidenceMetrics()
        self.trade_history: List[Dict] = []
        self.daily_returns: List[float] = []

        # Confidence thresholds for LIVE recommendation
        self.thresholds = {
            'min_trades': 30,
            'min_win_rate': 0.55,  # 55%
            'min_avg_r': 0.8,      # 0.8R average
            'max_drawdown': 0.08,  # 8%
            'max_loss_streak': 5,
            'min_sharpe': 1.0,
            'min_profit_factor': 1.5
        }

        self._load()

    def _load(self):
        """Load existing metrics from file"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    data = json.load(f)

                    # Load metrics
                    if 'metrics' in data:
                        for key, value in data['metrics'].items():
                            if hasattr(self.metrics, key):
                                setattr(self.metrics, key, value)

                    # Load trade history
                    self.trade_history = data.get('trade_history', [])
                    self.daily_returns = data.get('daily_returns', [])

                    print(f"[Confidence] Loaded {self.metrics.total_trades} trades from history")
            except Exception as e:
                print(f"[Confidence] Error loading history: {e}")

    def _save(self):
        """Save metrics to file"""
        try:
            data = {
                'metrics': self.metrics.to_dict(),
                'trade_history': self.trade_history[-100:],  # Keep last 100 trades
                'daily_returns': self.daily_returns[-90:],   # Keep last 90 days
                'last_saved': datetime.now().isoformat()
            }

            with open(self.filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Confidence] Error saving: {e}")

    def record_trade(self, trade: Dict):
        """
        Record completed trade and update metrics

        Args:
            trade: {
                'symbol': str,
                'entry_price': float,
                'exit_price': float,
                'pnl': float,
                'pnl_pct': float,
                'r_multiple': float,
                'hold_time_hours': float,
                'exit_reason': str,
                'timestamp': str
            }
        """
        # Add trade to history
        self.trade_history.append({
            **trade,
            'recorded_at': datetime.now().isoformat()
        })

        # Update basic counts
        self.metrics.total_trades += 1
        r_multiple = trade.get('r_multiple', 0.0)
        pnl = trade.get('pnl', 0.0)

        if r_multiple > 0:
            self.metrics.winning_trades += 1
            self.metrics.avg_win_r = (
                (self.metrics.avg_win_r * (self.metrics.winning_trades - 1) + r_multiple)
                / self.metrics.winning_trades
            )
            self.metrics.largest_win_r = max(self.metrics.largest_win_r, r_multiple)

            # Update streak
            if self.metrics.current_streak >= 0:
                self.metrics.current_streak += 1
            else:
                self.metrics.current_streak = 1
            self.metrics.max_win_streak = max(self.metrics.max_win_streak, self.metrics.current_streak)
        else:
            self.metrics.losing_trades += 1
            self.metrics.avg_loss_r = (
                (self.metrics.avg_loss_r * (self.metrics.losing_trades - 1) + r_multiple)
                / self.metrics.losing_trades
            )
            self.metrics.largest_loss_r = min(self.metrics.largest_loss_r, r_multiple)

            # Update streak
            if self.metrics.current_streak <= 0:
                self.metrics.current_streak -= 1
            else:
                self.metrics.current_streak = -1
            self.metrics.max_loss_streak = max(self.metrics.max_loss_streak, abs(self.metrics.current_streak))

        # Update P&L
        self.metrics.total_pnl += pnl
        self.metrics.total_r_multiple += r_multiple

        # Update equity tracking
        self.metrics.current_equity = trade.get('current_equity', self.metrics.current_equity)
        self.metrics.peak_equity = max(self.metrics.peak_equity, self.metrics.current_equity)

        # Calculate drawdown
        if self.metrics.peak_equity > 0:
            dd = (self.metrics.peak_equity - self.metrics.current_equity) / self.metrics.peak_equity
            self.metrics.max_drawdown_pct = max(self.metrics.max_drawdown_pct, dd)

        # Update timestamp
        self.metrics.last_updated = datetime.now().isoformat()

        # Recalculate confidence
        self._calculate_confidence()

        # Save
        self._save()

        print(f"[Confidence] Trade #{self.metrics.total_trades} recorded: {r_multiple:.2f}R, "
              f"Score: {self.metrics.confidence_score:.1f}/100")

    def _calculate_confidence(self):
        """Calculate overall confidence score (0-100)"""
        if self.metrics.total_trades == 0:
            self.metrics.confidence_score = 0.0
            self.metrics.live_ready = False
            return

        score = 0.0
        max_score = 100.0

        # 1. Win rate (0-25 points)
        win_rate = self.metrics.winning_trades / self.metrics.total_trades
        if win_rate >= 0.65:
            score += 25
        elif win_rate >= 0.55:
            score += 20
        elif win_rate >= 0.50:
            score += 15
        elif win_rate >= 0.45:
            score += 10
        else:
            score += 5

        # 2. Average R-multiple (0-25 points)
        avg_r = self.metrics.total_r_multiple / self.metrics.total_trades
        if avg_r >= 1.2:
            score += 25
        elif avg_r >= 0.8:
            score += 20
        elif avg_r >= 0.5:
            score += 15
        elif avg_r >= 0.2:
            score += 10
        else:
            score += 5

        # 3. Max drawdown (0-20 points)
        if self.metrics.max_drawdown_pct <= 0.05:
            score += 20
        elif self.metrics.max_drawdown_pct <= 0.08:
            score += 15
        elif self.metrics.max_drawdown_pct <= 0.12:
            score += 10
        else:
            score += 5

        # 4. Consistency - loss streak (0-15 points)
        if self.metrics.max_loss_streak <= 3:
            score += 15
        elif self.metrics.max_loss_streak <= 5:
            score += 10
        elif self.metrics.max_loss_streak <= 7:
            score += 5

        # 5. Sample size (0-15 points)
        if self.metrics.total_trades >= 50:
            score += 15
        elif self.metrics.total_trades >= 30:
            score += 10
        elif self.metrics.total_trades >= 20:
            score += 5

        self.metrics.confidence_score = min(score, max_score)

        # Check if LIVE ready
        self._check_live_ready(win_rate, avg_r)

    def _check_live_ready(self, win_rate: float, avg_r: float):
        """Check if bot meets LIVE trading criteria"""
        checks = {
            'min_trades': self.metrics.total_trades >= self.thresholds['min_trades'],
            'win_rate': win_rate >= self.thresholds['min_win_rate'],
            'avg_r': avg_r >= self.thresholds['min_avg_r'],
            'max_dd': self.metrics.max_drawdown_pct <= self.thresholds['max_drawdown'],
            'loss_streak': self.metrics.max_loss_streak <= self.thresholds['max_loss_streak'],
        }

        # All checks must pass
        self.metrics.live_ready = all(checks.values())

        return self.metrics.live_ready, checks

    def get_status_report(self) -> str:
        """Generate human-readable status report"""
        if self.metrics.total_trades == 0:
            return "📊 No trades yet - waiting for signals..."

        win_rate = self.metrics.winning_trades / self.metrics.total_trades * 100
        avg_r = self.metrics.total_r_multiple / self.metrics.total_trades

        report = f"""
📊 **SIM PERFORMANCE REPORT**

**Overall Stats:**
• Total Trades: {self.metrics.total_trades}
• Win Rate: {win_rate:.1f}% ({self.metrics.winning_trades}W / {self.metrics.losing_trades}L)
• Avg R-Multiple: {avg_r:.2f}R
• Total P&L: ${self.metrics.total_pnl:.2f}

**Trade Quality:**
• Avg Win: {self.metrics.avg_win_r:.2f}R | Avg Loss: {self.metrics.avg_loss_r:.2f}R
• Best Win: {self.metrics.largest_win_r:.2f}R | Worst Loss: {self.metrics.largest_loss_r:.2f}R
• Current Streak: {abs(self.metrics.current_streak)} {'wins' if self.metrics.current_streak > 0 else 'losses'}
• Max Loss Streak: {self.metrics.max_loss_streak}

**Risk Metrics:**
• Current Equity: ${self.metrics.current_equity:.2f}
• Peak Equity: ${self.metrics.peak_equity:.2f}
• Max Drawdown: {self.metrics.max_drawdown_pct*100:.1f}%

**Confidence Score: {self.metrics.confidence_score:.1f}/100**
"""

        # Add LIVE readiness status
        if self.metrics.live_ready:
            report += "\n✅ **READY FOR LIVE TRADING!**"
        else:
            live_ready, checks = self._check_live_ready(win_rate/100, avg_r)
            report += "\n⏳ **Building confidence...**\n"
            report += f"• Trades: {'✅' if checks['min_trades'] else '❌'} {self.metrics.total_trades}/{self.thresholds['min_trades']}\n"
            report += f"• Win Rate: {'✅' if checks['win_rate'] else '❌'} {win_rate:.1f}% (need {self.thresholds['min_win_rate']*100:.0f}%)\n"
            report += f"• Avg R: {'✅' if checks['avg_r'] else '❌'} {avg_r:.2f}R (need {self.thresholds['min_avg_r']:.1f}R)\n"
            report += f"• Max DD: {'✅' if checks['max_dd'] else '❌'} {self.metrics.max_drawdown_pct*100:.1f}% (max {self.thresholds['max_drawdown']*100:.0f}%)\n"
            report += f"• Loss Streak: {'✅' if checks['loss_streak'] else '❌'} {self.metrics.max_loss_streak} (max {self.thresholds['max_loss_streak']})"

        return report

    def should_alert_live_ready(self) -> bool:
        """Check if we should send LIVE ready alert (only once)"""
        # Check if we just became LIVE ready
        if self.metrics.live_ready and self.metrics.total_trades >= self.thresholds['min_trades']:
            # Check if we already sent alert (stored in trade history metadata)
            if not any(t.get('live_ready_alert_sent') for t in self.trade_history[-5:]):
                return True
        return False

    def mark_live_alert_sent(self):
        """Mark that LIVE ready alert was sent"""
        if self.trade_history:
            self.trade_history[-1]['live_ready_alert_sent'] = True
            self._save()


# Global instance
confidence_tracker = ConfidenceTracker()
