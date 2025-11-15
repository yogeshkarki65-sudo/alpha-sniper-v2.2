"""
Alpha Sniper v4.1 Database Models
SQLite database with full feature tracking for Sniper Swing strategy
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from config.config import config


class Database:
    """Database manager for Alpha Sniper v4.1"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        # Ensure directory exists before creating database
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self.init_db()

    def get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    def init_db(self) -> None:
        """Initialize database schema with v4.1 features"""
        conn = self.get_conn()
        cursor = conn.cursor()

        # === SIGNALS TABLE ===
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                score REAL NOT NULL,

                -- Price returns
                ret_1h_pct REAL,
                ret_4h_pct REAL,
                ret_24h_pct REAL,

                -- Volume
                rvol_1h REAL,
                quote_volume_24h REAL,

                -- RSI
                rsi_1h REAL,

                -- Moving averages
                above_ma_1h_50 INTEGER,
                above_ma_4h_50 INTEGER,
                above_ma_24h_50 INTEGER,

                -- Market structure
                range_pos_24h REAL,
                spread_bps REAL,

                -- Orderbook (optional)
                orderbook_imbalance REAL,

                -- Price info
                last_price REAL,

                -- Metadata
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                consumed INTEGER DEFAULT 0,

                -- Legacy fields (for compatibility)
                rvol REAL,
                velocity REAL,
                trend REAL
            )
        ''')

        # === POSITIONS TABLE ===
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                position_size REAL NOT NULL,
                stop_loss_price REAL NOT NULL,
                take_profit_price REAL NOT NULL,
                highest_price REAL,

                -- Trailing stop system
                trailing_stop_active INTEGER DEFAULT 0,
                trailing_stop_price REAL,
                breakeven_moved INTEGER DEFAULT 0,

                -- Moon mode indicator
                is_moon_mode INTEGER DEFAULT 0,

                -- Timestamps
                opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
                opened_at_timestamp REAL,

                FOREIGN KEY(signal_id) REFERENCES signals(id)
            )
        ''')

        # === TRADES TABLE ===
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                symbol TEXT NOT NULL,

                -- Entry/exit
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                position_size REAL NOT NULL,

                -- P&L breakdown
                gross_pnl_usd REAL,
                entry_fee_usd REAL,
                exit_fee_usd REAL,
                slippage_cost_usd REAL,
                net_pnl_usd REAL,
                pnl_pct REAL,

                -- Exit metadata
                exit_reason TEXT,
                hold_time_hours REAL,

                -- Moon mode indicator
                was_moon_mode INTEGER DEFAULT 0,

                -- Timestamps
                opened_at TEXT,
                closed_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(signal_id) REFERENCES signals(id)
            )
        ''')

        # === LEARNING LOG TABLE ===
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learning_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weights_before TEXT,
                weights_after TEXT,
                train_ic REAL,
                test_ic REAL,
                num_trades_used INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # === DAILY STATS TABLE ===
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                starting_equity REAL,
                ending_equity REAL,
                high_water_mark REAL,
                max_drawdown_pct REAL,
                num_trades INTEGER,
                num_winners INTEGER,
                num_losers INTEGER,
                win_rate REAL,
                total_fees REAL,
                total_pnl REAL
            )
        ''')

        # === SYMBOL COOLDOWN TRACKING ===
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trades_symbol_closed
            ON trades(symbol, closed_at)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_signals_score
            ON signals(score DESC, consumed)
        ''')

        conn.commit()
        conn.close()

    # ==================== SIGNAL OPERATIONS ====================

    def create_signal(
        self,
        symbol: str,
        score: float,
        ret_1h_pct: float,
        ret_4h_pct: float,
        ret_24h_pct: float,
        rvol_1h: float,
        quote_volume_24h: float,
        rsi_1h: float,
        above_ma_1h_50: bool,
        above_ma_4h_50: bool,
        above_ma_24h_50: bool,
        range_pos_24h: float,
        spread_bps: float,
        last_price: float,
        orderbook_imbalance: float = 0.0
    ) -> int:
        """Create a new signal with full v4.1 features"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO signals (
                symbol, score, ret_1h_pct, ret_4h_pct, ret_24h_pct,
                rvol_1h, quote_volume_24h, rsi_1h,
                above_ma_1h_50, above_ma_4h_50, above_ma_24h_50,
                range_pos_24h, spread_bps, orderbook_imbalance, last_price,
                rvol, velocity, trend
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol, score, ret_1h_pct, ret_4h_pct, ret_24h_pct,
            rvol_1h, quote_volume_24h, rsi_1h,
            1 if above_ma_1h_50 else 0,
            1 if above_ma_4h_50 else 0,
            1 if above_ma_24h_50 else 0,
            range_pos_24h, spread_bps, orderbook_imbalance, last_price,
            # Legacy fields
            rvol_1h, ret_24h_pct, range_pos_24h
        ))
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return signal_id

    def get_unconsumed_signals(self, limit: int = 10) -> List[Tuple]:
        """Get top unconsumed signals by score"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM signals WHERE consumed=0 ORDER BY score DESC LIMIT ?',
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def mark_signal_consumed(self, signal_id: int) -> None:
        """Mark signal as consumed"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('UPDATE signals SET consumed=1 WHERE id=?', (signal_id,))
        conn.commit()
        conn.close()

    # ==================== POSITION OPERATIONS ====================

    def create_position(
        self,
        signal_id: int,
        symbol: str,
        entry_price: float,
        position_size: float,
        stop_loss_price: float,
        take_profit_price: float,
        is_moon_mode: bool = False
    ) -> int:
        """Create a new position"""
        conn = self.get_conn()
        cursor = conn.cursor()
        now_ts = datetime.now().timestamp()
        cursor.execute('''
            INSERT INTO positions
            (signal_id, symbol, entry_price, position_size, stop_loss_price,
             take_profit_price, highest_price, opened_at_timestamp, is_moon_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal_id, symbol, entry_price, position_size,
            stop_loss_price, take_profit_price, entry_price, now_ts,
            1 if is_moon_mode else 0
        ))
        position_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return position_id

    def get_open_positions(self) -> List[Tuple]:
        """Get all open positions"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM positions')
        rows = cursor.fetchall()
        conn.close()
        return rows

    def update_position_trailing(
        self,
        position_id: int,
        highest_price: float,
        trailing_active: bool,
        trailing_price: float
    ) -> None:
        """Update trailing stop for position"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE positions
            SET highest_price=?, trailing_stop_active=?, trailing_stop_price=?
            WHERE id=?
        ''', (highest_price, 1 if trailing_active else 0, trailing_price, position_id))
        conn.commit()
        conn.close()

    def move_stop_to_breakeven(
        self,
        position_id: int,
        new_stop_price: float
    ) -> None:
        """Move stop loss to breakeven"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE positions
            SET stop_loss_price=?, breakeven_moved=1
            WHERE id=?
        ''', (new_stop_price, position_id))
        conn.commit()
        conn.close()

    def close_position(
        self,
        position_id: int,
        exit_price: float,
        exit_reason: str
    ) -> Optional[float]:
        """Close position and create trade record"""
        conn = self.get_conn()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM positions WHERE id=?', (position_id,))
        pos = cursor.fetchone()
        if not pos:
            conn.close()
            return None

        # Parse position data
        signal_id = pos[1]
        symbol = pos[2]
        entry_price = pos[3]
        position_size = pos[4]
        opened_at_ts = pos[11]
        is_moon_mode = bool(pos[10]) if len(pos) > 10 else False

        # Calculate P&L
        entry_value = entry_price * position_size
        exit_value = exit_price * position_size

        entry_fee = entry_value * (config.TAKER_FEE_PCT / 100)
        exit_fee = exit_value * (config.TAKER_FEE_PCT / 100)
        slippage_cost = (
            (entry_value * config.SLIPPAGE_PCT / 100) +
            (exit_value * config.SLIPPAGE_PCT / 100)
        )

        gross_pnl = exit_value - entry_value
        net_pnl = gross_pnl - entry_fee - exit_fee - slippage_cost
        pnl_pct = (net_pnl / entry_value) * 100 if entry_value != 0 else 0

        # Calculate hold time
        closed_at_ts = datetime.now().timestamp()
        hold_time_hours = (closed_at_ts - opened_at_ts) / 3600

        # Create trade record
        cursor.execute('''
            INSERT INTO trades
            (signal_id, symbol, entry_price, exit_price, position_size,
             gross_pnl_usd, entry_fee_usd, exit_fee_usd, slippage_cost_usd,
             net_pnl_usd, pnl_pct, exit_reason, opened_at, hold_time_hours,
             was_moon_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            signal_id, symbol, entry_price, exit_price, position_size,
            gross_pnl, entry_fee, exit_fee, slippage_cost, net_pnl, pnl_pct,
            exit_reason, datetime.fromtimestamp(opened_at_ts).isoformat(),
            hold_time_hours, 1 if is_moon_mode else 0
        ))

        # Delete position
        cursor.execute('DELETE FROM positions WHERE id=?', (position_id,))

        conn.commit()
        conn.close()
        return net_pnl

    # ==================== TRADE OPERATIONS ====================

    def get_recent_trades(self, days: int = 30) -> List[Tuple]:
        """Get recent closed trades"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM trades
            WHERE closed_at > datetime('now', '-' || ? || ' days')
            ORDER BY closed_at DESC
        ''', (days,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_trade_with_signal(self, days: int = 30) -> List[Tuple]:
        """Get trades joined with signal features"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, s.ret_1h_pct, s.ret_4h_pct, s.ret_24h_pct,
                   s.rvol_1h, s.rsi_1h
            FROM trades t
            JOIN signals s ON t.signal_id = s.id
            WHERE t.closed_at > datetime('now', '-' || ? || ' days')
        ''', (days,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def log_learning_update(
        self,
        weights_before: Dict[str, float],
        weights_after: Dict[str, float],
        train_ic: float,
        test_ic: float,
        num_trades: int
    ) -> None:
        """Log learning weight updates"""
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO learning_log
            (weights_before, weights_after, train_ic, test_ic, num_trades_used)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            json.dumps(weights_before),
            json.dumps(weights_after),
            train_ic, test_ic, num_trades
        ))
        conn.commit()
        conn.close()


# Global database instance
db = Database()
