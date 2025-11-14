import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self, db_path='data/trades.db'):
        self.db_path = db_path
        self.init_db()
    
    def get_conn(self):
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        conn = self.get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                score REAL NOT NULL,
                rvol REAL,
                velocity REAL,
                trend REAL,
                orderbook_imbalance REAL,
                last_price REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                consumed INTEGER DEFAULT 0
            )
        ''')
        
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
                trailing_stop_active INTEGER DEFAULT 0,
                trailing_stop_price REAL,
                opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
                opened_at_timestamp REAL,
                FOREIGN KEY(signal_id) REFERENCES signals(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                position_size REAL NOT NULL,
                gross_pnl_usd REAL,
                entry_fee_usd REAL,
                exit_fee_usd REAL,
                slippage_cost_usd REAL,
                net_pnl_usd REAL,
                pnl_pct REAL,
                exit_reason TEXT,
                opened_at TEXT,
                closed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                hold_time_hours REAL,
                FOREIGN KEY(signal_id) REFERENCES signals(id)
            )
        ''')
        
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                starting_equity REAL,
                ending_equity REAL,
                high_water_mark REAL,
                max_drawdown_pct REAL,
                num_trades INTEGER,
                win_rate REAL,
                total_fees REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_signal(self, symbol, score, rvol, velocity, trend, orderbook_imbalance, last_price):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO signals (symbol, score, rvol, velocity, trend, orderbook_imbalance, last_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, score, rvol, velocity, trend, orderbook_imbalance, last_price))
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return signal_id
    
    def get_unconsumed_signals(self, limit=10):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM signals WHERE consumed=0 ORDER BY score DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def mark_signal_consumed(self, signal_id):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('UPDATE signals SET consumed=1 WHERE id=?', (signal_id,))
        conn.commit()
        conn.close()
    
    def create_position(self, signal_id, symbol, entry_price, position_size, stop_loss_price, take_profit_price):
        conn = self.get_conn()
        cursor = conn.cursor()
        now_ts = datetime.now().timestamp()
        cursor.execute('''
            INSERT INTO positions 
            (signal_id, symbol, entry_price, position_size, stop_loss_price, take_profit_price, 
             highest_price, opened_at_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (signal_id, symbol, entry_price, position_size, stop_loss_price, take_profit_price, 
              entry_price, now_ts))
        position_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return position_id
    
    def get_open_positions(self):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM positions')
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def update_position_trailing(self, position_id, highest_price, trailing_active, trailing_price):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE positions 
            SET highest_price=?, trailing_stop_active=?, trailing_stop_price=?
            WHERE id=?
        ''', (highest_price, 1 if trailing_active else 0, trailing_price, position_id))
        conn.commit()
        conn.close()
    
    def close_position(self, position_id, exit_price, exit_reason):
        conn = self.get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM positions WHERE id=?', (position_id,))
        pos = cursor.fetchone()
        if not pos:
            conn.close()
            return None
        
        from config.config import config
        
        entry_price = pos[3]
        position_size = pos[4]
        opened_at = pos[10]  # actually opened_at_timestamp; see below
        opened_at_ts = pos[10]
        
        entry_value = entry_price * position_size
        exit_value = exit_price * position_size
        
        entry_fee = entry_value * (config.TAKER_FEE_PCT / 100)
        exit_fee = exit_value * (config.TAKER_FEE_PCT / 100)
        slippage_cost = (entry_value * config.SLIPPAGE_PCT / 100) + (exit_value * config.SLIPPAGE_PCT / 100)
        
        gross_pnl = exit_value - entry_value
        net_pnl = gross_pnl - entry_fee - exit_fee - slippage_cost
        pnl_pct = (net_pnl / entry_value) * 100 if entry_value != 0 else 0
        
        closed_at = datetime.now().isoformat()
        closed_at_ts = datetime.now().timestamp()
        hold_time_hours = (closed_at_ts - opened_at_ts) / 3600
        
        cursor.execute('''
            INSERT INTO trades 
            (signal_id, symbol, entry_price, exit_price, position_size, gross_pnl_usd,
             entry_fee_usd, exit_fee_usd, slippage_cost_usd, net_pnl_usd, pnl_pct,
             exit_reason, opened_at, hold_time_hours)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pos[1], pos[2], entry_price, exit_price, position_size, gross_pnl,
              entry_fee, exit_fee, slippage_cost, net_pnl, pnl_pct,
              exit_reason, datetime.fromtimestamp(opened_at_ts).isoformat(), hold_time_hours))
        
        cursor.execute('DELETE FROM positions WHERE id=?', (position_id,))
        
        conn.commit()
        conn.close()
        return net_pnl
    
    def get_recent_trades(self, days=30):
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
    
    def get_trade_with_signal(self, days=30):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, s.rvol, s.velocity, s.trend, s.orderbook_imbalance
            FROM trades t
            JOIN signals s ON t.signal_id = s.id
            WHERE t.closed_at > datetime('now', '-' || ? || ' days')
        ''', (days,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def log_learning_update(self, weights_before, weights_after, train_ic, test_ic, num_trades):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO learning_log 
            (weights_before, weights_after, train_ic, test_ic, num_trades_used)
            VALUES (?, ?, ?, ?, ?)
        ''', (json.dumps(weights_before), json.dumps(weights_after), train_ic, test_ic, num_trades))
        conn.commit()
        conn.close()

db = Database()
