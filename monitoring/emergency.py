import os
from flask import Flask, jsonify, request
from database.models import db
from monitoring.telegram_alerter import send_alert
from trader.trader import get_current_price

emergency_app = Flask(__name__)

@emergency_app.route('/emergency_flat', methods=['POST'])
def emergency_flat():
    """
    Emergency endpoint to close all positions and pause trading.
    Call this when you need to exit everything immediately.
    """
    try:
        # Get all open positions
        open_positions = db.get_open_positions()

        if not open_positions:
            return jsonify({
                'status': 'success',
                'message': 'No open positions to close'
            }), 200

        # Close all positions
        closed_count = 0
        for pos in open_positions:
            position_id = pos[0]
            symbol = pos[2]
            entry_price = pos[3]

            # Get current price
            current_price = get_current_price(symbol)
            if not current_price:
                current_price = entry_price  # Fallback to entry if price unavailable

            # Close position with emergency exit reason
            exit_price = current_price * 0.995  # Apply slippage
            db.close_position(position_id, exit_price, 'emergency_flat')
            closed_count += 1

            print(f"🚨 EMERGENCY FLAT: Closed {symbol} @ ${exit_price:.6f}")

        # Pause trading
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
        send_alert(
            f"🚨 EMERGENCY FLAT EXECUTED\n"
            f"Closed {closed_count} positions\n"
            f"Trading PAUSED\n"
            f"Manual intervention required"
        )

        return jsonify({
            'status': 'success',
            'message': f'Emergency flat executed: {closed_count} positions closed',
            'positions_closed': closed_count
        }), 200

    except Exception as e:
        error_msg = f"Emergency flat error: {str(e)}"
        print(f"❌ {error_msg}")
        send_alert(f"❌ {error_msg}")
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500

@emergency_app.route('/emergency_status', methods=['GET'])
def emergency_status():
    """Check current emergency status."""
    try:
        open_positions = db.get_open_positions()
        return jsonify({
            'status': 'ok',
            'open_positions': len(open_positions),
            'positions': [{
                'symbol': pos[2],
                'entry_price': pos[3],
                'size': pos[4]
            } for pos in open_positions]
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def start_emergency_server(port=8081):
    """Start emergency endpoint server on separate port."""
    from threading import Thread
    Thread(target=lambda: emergency_app.run(host='0.0.0.0', port=port), daemon=True).start()
    print(f"🚨 Emergency endpoint started on port {port}")
