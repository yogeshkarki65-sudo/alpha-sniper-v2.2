import requests
import time
from datetime import datetime, timedelta

from config.config import config
from database.models import db
from risk.risk_manager import risk_manager
from monitoring.telegram_alerter import send_alert

def get_current_price(symbol):
    try:
        url = f"{config.MEXC_BASE_URL}/api/v3/ticker/price"
        params = {'symbol': symbol}
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        return float(data['price'])
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return None

def check_symbol_cooldown(symbol):
    cooldown_time = datetime.now() - timedelta(hours=config.SYMBOL_COOLDOWN_HOURS)
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM trades 
        WHERE symbol=? AND closed_at > ?
    ''', (symbol, cooldown_time.isoformat()))
    count = cursor.fetchone()[0]
    conn.close()
    return count == 0

def open_position_from_signal(signal):
    signal_id = signal[0]
    symbol = signal[1]
    score = signal[2]
    
    if not check_symbol_cooldown(symbol):
        print(f"⏸️  {symbol} in cooldown period")
        db.mark_signal_consumed(signal_id)
        return False
    
    can_trade, reason = risk_manager.can_trade()
    if not can_trade:
        print(f"🚫 Cannot trade: {reason}")
        return False
    
    open_positions = db.get_open_positions()
    if not risk_manager.check_correlation(symbol, open_positions):
        print(f"⚠️  {symbol} too correlated with existing positions")
        db.mark_signal_consumed(signal_id)
        return False
    
    current_price = get_current_price(symbol)
    if not current_price:
        return False
    
    entry_price = current_price * (1 + config.SLIPPAGE_PCT / 100)
    
    position_size = risk_manager.calculate_position_size(entry_price, config.STOP_LOSS_PCT)
    if position_size <= 0:
        print(f"⚠️ Position size <= 0 for {symbol}")
        db.mark_signal_consumed(signal_id)
        return False
    
    if score >= config.MOON_SCORE:
        position_size *= config.MOON_MULT
        print(f"🌙 MOON signal detected! Multiplying position by {config.MOON_MULT}x")
    
    stop_loss_price = entry_price * (1 - config.STOP_LOSS_PCT / 100)
    take_profit_price = entry_price * (1 + config.TAKE_PROFIT_PCT / 100)
    
    position_id = db.create_position(
        signal_id,
        symbol,
        entry_price,
        position_size,
        stop_loss_price,
        take_profit_price
    )
    
    db.mark_signal_consumed(signal_id)
    
    position_value = entry_price * position_size
    print(f"📈 OPENED: {symbol} @ ${entry_price:.6f} | Size: {position_size:.4f} | Value: ${position_value:.2f}")
    
    send_alert(
        f"📈 Position Opened\n"
        f"Symbol: {symbol}\n"
        f"Score: {score:.1f}\n"
        f"Entry: ${entry_price:.6f}\n"
        f"Value: ${position_value:.2f}\n"
        f"SL: ${stop_loss_price:.6f} | TP: ${take_profit_price:.6f}"
    )
    
    return True

def monitor_positions():
    positions = db.get_open_positions()
    if not positions:
        return
    
    print(f"👀 Monitoring {len(positions)} positions...")
    
    for pos in positions:
        position_id = pos[0]
        symbol = pos[2]
        entry_price = float(pos[3])
        position_size = float(pos[4])
        stop_loss_price = float(pos[5])
        take_profit_price = float(pos[6])
        highest_price = float(pos[7]) if pos[7] else entry_price
        trailing_stop_active = bool(pos[8])
        trailing_stop_price = float(pos[9]) if pos[9] else 0.0

        # Parse opened_at datetime string to timestamp
        if pos[10]:
            try:
                opened_at_dt = datetime.fromisoformat(pos[10])
                opened_at_ts = opened_at_dt.timestamp()
            except (ValueError, TypeError):
                # Fallback if it's already a timestamp
                opened_at_ts = float(pos[10])
        else:
            opened_at_ts = datetime.now().timestamp()

        current_price = get_current_price(symbol)
        if not current_price:
            continue

        if current_price > highest_price:
            highest_price = current_price
        
        current_profit_pct = ((current_price - entry_price) / entry_price) * 100
        
        now_ts = datetime.now().timestamp()
        hold_time_hours = (now_ts - opened_at_ts) / 3600
        if hold_time_hours >= config.MAX_HOLD_TIME_HOURS:
            exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
            db.close_position(position_id, exit_price, 'time_exit')
            print(f"⏰ CLOSED (time): {symbol} @ ${exit_price:.6f} | PnL: {current_profit_pct:.2f}%")
            send_alert(f"⏰ Time Exit: {symbol} | PnL: {current_profit_pct:.2f}%")
            continue
        
        if config.USE_TRAILING_STOP:
            if current_profit_pct >= config.TRAILING_STOP_ACTIVATION_PCT and not trailing_stop_active:
                trailing_stop_active = True
                trailing_stop_price = highest_price * (1 - config.TRAILING_STOP_DISTANCE_PCT / 100)
                db.update_position_trailing(position_id, highest_price, trailing_stop_active, trailing_stop_price)
                print(f"🎯 Trailing stop activated for {symbol} @ ${trailing_stop_price:.6f}")
            
            if trailing_stop_active:
                trailing_stop_price = highest_price * (1 - config.TRAILING_STOP_DISTANCE_PCT / 100)
                db.update_position_trailing(position_id, highest_price, trailing_stop_active, trailing_stop_price)
                
                if current_price <= trailing_stop_price:
                    exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
                    db.close_position(position_id, exit_price, 'trailing_stop')
                    print(f"📉 CLOSED (trailing): {symbol} @ ${exit_price:.6f} | PnL: {current_profit_pct:.2f}%")
                    send_alert(f"📉 Trailing Stop: {symbol} | PnL: {current_profit_pct:.2f}%")
                    continue
        
        if current_price <= stop_loss_price:
            exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
            db.close_position(position_id, exit_price, 'stop_loss')
            print(f"🛑 CLOSED (SL): {symbol} @ ${exit_price:.6f} | PnL: {current_profit_pct:.2f}%")
            send_alert(f"🛑 Stop Loss: {symbol} | PnL: {current_profit_pct:.2f}%")
            continue
        
        if current_price >= take_profit_price:
            exit_price = current_price * (1 - config.SLIPPAGE_PCT / 100)
            db.close_position(position_id, exit_price, 'take_profit')
            print(f"💰 CLOSED (TP): {symbol} @ ${exit_price:.6f} | PnL: {current_profit_pct:.2f}%")
            send_alert(f"💰 Take Profit: {symbol} | PnL: {current_profit_pct:.2f}%")
            continue
        
        print(f"  {symbol}: ${current_price:.6f} | PnL: {current_profit_pct:.2f}%")

def run_trader():
    print("💼 Running trader...")
    
    monitor_positions()
    
    can_trade, reason = risk_manager.can_trade()
    if not can_trade:
        print(f"🚫 Cannot open new positions: {reason}")
        return
    
    open_positions = db.get_open_positions()
    slots_available = config.MAX_CONCURRENT_POS - len(open_positions)
    
    if slots_available <= 0:
        print("📊 All position slots filled")
        return
    
    signals = db.get_unconsumed_signals(limit=slots_available)
    if not signals:
        print("📭 No signals to process")
        return
    
    print(f"Found {len(signals)} signals to process")
    for signal in signals:
        if open_position_from_signal(signal):
            time.sleep(1)
