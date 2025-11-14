from flask import Flask, jsonify
from datetime import datetime
import threading

from database.models import db
from risk.risk_manager import risk_manager
from monitoring.version import get_version_info

app = Flask(__name__)

last_scanner_run = None
last_trader_run = None
start_time = datetime.now()

@app.route('/health', methods=['GET'])
def health():
    current_equity = risk_manager.get_current_equity()
    open_positions = db.get_open_positions()

    today = datetime.now().date().isoformat()
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT SUM(net_pnl_usd) FROM trades
        WHERE DATE(closed_at) = ?
    ''', (today,))
    result = cursor.fetchone()[0]
    conn.close()
    daily_pnl = result if result else 0

    # Calculate uptime
    uptime_seconds = (datetime.now() - start_time).total_seconds()
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    uptime_str = f"{hours}h {minutes}m"

    # Get version information
    version_info = get_version_info()

    return jsonify({
        'status': 'healthy',
        'version': version_info.get('version'),
        'git_commit': version_info.get('git_commit', 'unknown')[:7],  # Short hash
        'build_time': version_info.get('build_time'),
        'uptime': uptime_str,
        'current_equity': current_equity,
        'open_positions_count': len(open_positions),
        'daily_pnl': daily_pnl,
        'last_scanner_run': last_scanner_run.isoformat() if last_scanner_run else None,
        'last_trader_run': last_trader_run.isoformat() if last_trader_run else None
    })

def start_healthcheck_server():
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True).start()
