"""
Alpha Sniper v4.1 Risk Manager
- Portfolio drawdown monitoring (15% max)
- Position sizing (3% risk per trade)
- Correlation management (max 0.8 threshold)
- Moon mode (2x position size for score >= 75)
"""
import os
from datetime import datetime
from typing import Tuple, List
from config.config import config
from config.logging_config import logger
from database.models import db
from scanner.mexc_client import mexc_client


class RiskManager:
    """Manages risk for Alpha Sniper v4.1"""

    def __init__(self):
        self.daily_hwm = self.get_current_equity()
        self.load_daily_stats()

    def get_current_equity(self) -> float:
        """Calculate current equity (starting capital + realized P&L)"""
        conn = db.get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT SUM(net_pnl_usd) FROM trades')
        result = cursor.fetchone()[0]
        conn.close()
        total_pnl = result if result else 0
        equity = config.SIM_EQUITY_START + total_pnl
        return equity

    def load_daily_stats(self) -> None:
        """Load daily high water mark from database"""
        today = datetime.now().date().isoformat()
        conn = db.get_conn()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT high_water_mark FROM daily_stats WHERE date=?',
            (today,)
        )
        result = cursor.fetchone()
        conn.close()

        if result:
            self.daily_hwm = result[0]
        else:
            self.daily_hwm = self.get_current_equity()
            self.save_daily_hwm()

    def save_daily_hwm(self) -> None:
        """Save daily high water mark to database"""
        today = datetime.now().date().isoformat()
        current_equity = self.get_current_equity()

        conn = db.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO daily_stats (date, high_water_mark, starting_equity)
            VALUES (?, ?, ?)
        ''', (today, max(self.daily_hwm, current_equity), config.SIM_EQUITY_START))
        conn.commit()
        conn.close()

    def check_drawdown(self) -> Tuple[bool, float]:
        """
        Check if drawdown is within acceptable limits
        Returns: (within_limits: bool, current_dd_pct: float)
        """
        current_equity = self.get_current_equity()

        # Update HWM if we've made new highs
        if current_equity > self.daily_hwm:
            self.daily_hwm = current_equity
            self.save_daily_hwm()

        if self.daily_hwm <= 0:
            return True, 0.0

        drawdown_pct = ((self.daily_hwm - current_equity) / self.daily_hwm) * 100

        if drawdown_pct >= config.MAX_DAILY_DRAWDOWN_PCT:
            self.pause_trading(f"Max drawdown reached: {drawdown_pct:.2f}%")
            return False, drawdown_pct

        return True, drawdown_pct

    def pause_trading(self, reason: str) -> None:
        """Pause trading by updating .env file"""
        logger.error(f"🚨 PAUSING TRADING: {reason}")

        env_path = '.env'
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()
            with open(env_path, 'w') as f:
                for line in lines:
                    if line.startswith('TRADING_PAUSED='):
                        f.write('TRADING_PAUSED=true\n')
                    else:
                        f.write(line)

        # Send alert
        try:
            from monitoring.telegram_alerter import send_alert
            send_alert(f"🚨 TRADING PAUSED: {reason}")
        except Exception:
            pass

    def calculate_position_size(
        self,
        entry_price: float,
        is_moon_mode: bool = False
    ) -> float:
        """
        Calculate position size based on risk per trade
        Args:
            entry_price: Entry price
            is_moon_mode: Whether this is a Moon mode signal
        Returns: Position size in base currency
        """
        current_equity = self.get_current_equity()

        # Risk amount in USD
        risk_amount = current_equity * (config.RISK_PER_TRADE_PCT / 100)

        # Stop loss distance
        stop_loss_pct = config.STOP_LOSS_PCT / 100

        # Position size calculation
        # risk_amount = position_size * entry_price * stop_loss_pct
        # position_size = risk_amount / (entry_price * stop_loss_pct)

        if entry_price <= 0 or stop_loss_pct <= 0:
            return 0.0

        position_size = risk_amount / (entry_price * stop_loss_pct)

        # Apply Moon mode multiplier
        if is_moon_mode:
            position_size *= config.MOON_MULTIPLIER
            logger.info(
                f"🌙 MOON MODE: Position size multiplied by {config.MOON_MULTIPLIER}x"
            )

        # Sanity check: max 50% of equity in one position
        max_position_value = current_equity * 0.5
        max_position_size = max_position_value / entry_price
        position_size = min(position_size, max_position_size)

        return position_size

    def check_correlation(
        self,
        new_symbol: str,
        open_positions: List[Tuple]
    ) -> bool:
        """
        Check if new symbol is too correlated with existing positions
        Args:
            new_symbol: Symbol to check
            open_positions: List of open position tuples
        Returns: True if correlation is acceptable
        """
        if len(open_positions) == 0:
            return True

        try:
            # Fetch 24h price changes
            tickers = mexc_client.get_24h_tickers()
            ticker_dict = {t['symbol']: float(t.get('priceChangePercent', 0))
                          for t in tickers}
        except Exception as e:
            logger.warning(f"Failed to fetch tickers for correlation check: {e}")
            return True  # Allow trade if we can't check

        new_change = ticker_dict.get(new_symbol, 0)

        # Count correlated positions
        correlated_count = 0
        for pos in open_positions:
            pos_symbol = pos[2]  # symbol is 3rd field
            pos_change = ticker_dict.get(pos_symbol, 0)

            # Check correlation: same direction and both significant moves
            if abs(new_change) > 3 and abs(pos_change) > 3:
                if (new_change > 0 and pos_change > 0) or \
                   (new_change < 0 and pos_change < 0):
                    correlated_count += 1

        # Check threshold
        if correlated_count >= config.MAX_CORRELATED_POSITIONS:
            logger.info(
                f"⚠️ {new_symbol} too correlated with {correlated_count} existing positions"
            )
            return False

        return True

    def can_trade(self) -> Tuple[bool, str]:
        """
        Check if we can open new trades
        Returns: (can_trade: bool, reason: str)
        """
        # Check if trading is paused
        if config.TRADING_PAUSED:
            return False, "Trading is paused"

        # Check drawdown
        dd_ok, dd_pct = self.check_drawdown()
        if not dd_ok:
            return False, f"Max drawdown exceeded ({dd_pct:.2f}%)"

        # Check max concurrent positions
        open_positions = db.get_open_positions()
        if len(open_positions) >= config.MAX_CONCURRENT_POS:
            return False, "Max concurrent positions reached"

        return True, "OK"


# Global instance
risk_manager = RiskManager()
