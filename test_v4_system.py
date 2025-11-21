#!/usr/bin/env python3
"""
Alpha Sniper V4.1 - System Health Check
Tests all components to ensure everything is working
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("  ALPHA SNIPER V4.1 - SYSTEM HEALTH CHECK")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

tests_passed = 0
tests_failed = 0
results = []

def test(name, func):
    global tests_passed, tests_failed
    try:
        result = func()
        if result:
            print(f"  [PASS] {name}")
            tests_passed += 1
            results.append((name, "PASS", None))
            return True
        else:
            print(f"  [FAIL] {name}")
            tests_failed += 1
            results.append((name, "FAIL", "Returned False"))
            return False
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        tests_failed += 1
        results.append((name, "FAIL", str(e)))
        return False


# ============================================================================
# TEST 1: MEXC API Client
# ============================================================================
print("\n[1/8] MEXC API CLIENT")
print("-" * 50)

def test_mexc_import():
    from v3.data.mexc_client import mexc_client
    return mexc_client is not None

def test_mexc_get_ticker_24h():
    from v3.data.mexc_client import mexc_client
    ticker = mexc_client.get_ticker_24h('BTCUSDT')
    if ticker and 'lastPrice' in ticker:
        price = float(ticker['lastPrice'])
        print(f"       BTC Price: ${price:,.2f}")
        return True
    return False

def test_mexc_get_all_tickers():
    from v3.data.mexc_client import mexc_client
    tickers = mexc_client.get_all_tickers()
    if tickers and len(tickers) > 100:
        print(f"       Total tickers: {len(tickers)}")
        return True
    return False

def test_mexc_get_klines():
    from v3.data.mexc_client import mexc_client
    klines = mexc_client.get_klines('BTCUSDT', '15m', 10)
    if klines and len(klines) >= 5:
        print(f"       Klines fetched: {len(klines)}")
        return True
    return False

test("Import mexc_client", test_mexc_import)
test("get_ticker_24h(BTCUSDT)", test_mexc_get_ticker_24h)
test("get_all_tickers()", test_mexc_get_all_tickers)
test("get_klines(BTCUSDT, 15m)", test_mexc_get_klines)


# ============================================================================
# TEST 2: Top Gainers Scanner
# ============================================================================
print("\n[2/8] TOP GAINERS SCANNER")
print("-" * 50)

def test_top_gainers():
    from v3.data.mexc_client import mexc_client

    all_tickers = mexc_client.get_all_tickers()
    if not all_tickers:
        return False

    candidates = []
    exclude = ['UP', 'DOWN', 'BEAR', 'BULL', '3L', '3S', '2L', '2S', 'USDC', 'TUSD', 'BUSD', 'DAI', 'FDUSD']

    for t in all_tickers:
        sym = t.get('symbol', '')
        if not sym.endswith('USDT') or any(p in sym for p in exclude):
            continue
        try:
            vol = float(t.get('quoteVolume', 0))
            chg = float(t.get('priceChangePercent', 0))
            if vol >= 100000 and chg > 0:
                candidates.append({'symbol': sym, 'change': chg, 'volume': vol})
        except:
            continue

    candidates.sort(key=lambda x: x['change'], reverse=True)

    if len(candidates) > 0:
        print(f"       Gainers found: {len(candidates)}")
        top5 = [f"{c['symbol']}(+{c['change']:.1f}%)" for c in candidates[:5]]
        print(f"       Top 5: {', '.join(top5)}")
        return True
    return False

test("Scan top gainers from MEXC", test_top_gainers)


# ============================================================================
# TEST 3: Regime Detector
# ============================================================================
print("\n[3/8] REGIME DETECTOR")
print("-" * 50)

def test_regime_import():
    from v3.regime.detector import regime_detector, Regime
    return regime_detector is not None and Regime is not None

def test_regime_current():
    from v3.regime.detector import regime_detector
    regime = regime_detector.current_regime
    print(f"       Current regime: {regime.name}")
    return regime is not None

def test_regime_update():
    from v3.regime.detector import regime_detector
    btc_data = {
        'price': 85000, 'ema20': 85000, 'ema50': 85000,
        'volatility': 0.03, 'trend': 0, 'volume_trend': 0, 'price_trend': 0
    }
    market_breadth = {'pct_above_50ma': 50}
    regime = regime_detector.update_regime(btc_data, market_breadth)
    print(f"       Updated regime: {regime.name}")
    return regime is not None

test("Import regime_detector", test_regime_import)
test("Get current regime", test_regime_current)
test("Update regime", test_regime_update)


# ============================================================================
# TEST 4: Feature Extraction
# ============================================================================
print("\n[4/8] FEATURE EXTRACTION")
print("-" * 50)

def test_features_import():
    from v3.scanner.features import extract_features
    return extract_features is not None

def test_features_btc():
    from v3.scanner.features import extract_features
    features = extract_features('BTCUSDT', equity=500)
    if features:
        print(f"       BTC Close: ${features.close:,.2f}")
        print(f"       BTC 24h Return: {features.return_24h*100:.2f}%")
        print(f"       BTC RVOL: {features.rvol:.2f}")
        return True
    return False

test("Import extract_features", test_features_import)
test("Extract features for BTCUSDT", test_features_btc)


# ============================================================================
# TEST 5: Signal Generator
# ============================================================================
print("\n[5/8] SIGNAL GENERATOR")
print("-" * 50)

def test_signals_import():
    from v3.scanner.signals import signal_generator
    return signal_generator is not None

def test_signals_scan():
    from v3.scanner.signals import signal_generator
    from v3.regime.detector import Regime

    signals = signal_generator.scan_universe(
        symbols=['BTCUSDT', 'ETHUSDT'],
        regime=Regime.SIDEWAYS,
        equity=500
    )
    print(f"       Signals generated: {len(signals)}")
    return True  # Even 0 signals is valid

test("Import signal_generator", test_signals_import)
test("Scan universe for signals", test_signals_scan)


# ============================================================================
# TEST 6: Bear-Resilient Long Engine
# ============================================================================
print("\n[6/8] BEAR-RESILIENT LONG ENGINE")
print("-" * 50)

def test_bear_engine_import():
    from v3.scanner.bear_resilient_long import bear_resilient_long_engine
    return bear_resilient_long_engine is not None

def test_bear_engine_config():
    from v3.scanner.bear_resilient_long import bear_resilient_long_engine
    engine = bear_resilient_long_engine
    print(f"       Enabled: {engine.enabled}")
    print(f"       Risk per trade: {engine.risk_per_trade*100:.2f}%")
    print(f"       Max concurrent: {engine.max_concurrent}")
    print(f"       Max hold hours: {engine.max_hold_hours}h")
    return engine is not None

test("Import bear_resilient_long_engine", test_bear_engine_import)
test("Bear engine configuration", test_bear_engine_config)


# ============================================================================
# TEST 7: Risk Engine
# ============================================================================
print("\n[7/8] RISK ENGINE")
print("-" * 50)

def test_risk_import():
    from v3.risk.risk_engine import risk_engine
    return risk_engine is not None

def test_risk_positions():
    from v3.risk.risk_engine import risk_engine
    positions = risk_engine.open_positions
    print(f"       Open positions: {len(positions)}")
    return True

test("Import risk_engine", test_risk_import)
test("Check open positions", test_risk_positions)


# ============================================================================
# TEST 8: Status Reporter
# ============================================================================
print("\n[8/8] STATUS REPORTER")
print("-" * 50)

def test_status_import():
    from v3.monitoring.status_reporter import status_reporter
    return status_reporter is not None

test("Import status_reporter", test_status_import)


# ============================================================================
# TEST 9: Configuration
# ============================================================================
print("\n[9/9] CONFIGURATION (.env)")
print("-" * 50)

def test_env_mode():
    mode = os.getenv('MODE', 'NOT_SET')
    print(f"       MODE: {mode}")
    return mode in ['SIM', 'SIMULATION', 'LIVE', 'PAPER']

def test_env_equity():
    equity = os.getenv('SIM_EQUITY_START', os.getenv('SIMULATION_EQUITY_START', 'NOT_SET'))
    print(f"       Equity: ${equity}")
    return equity != 'NOT_SET'

def test_env_telegram():
    token = os.getenv('TELEGRAM_BOT_TOKEN', 'NOT_SET')
    chat_id = os.getenv('TELEGRAM_CHAT_ID', 'NOT_SET')
    configured = token != 'NOT_SET' and chat_id != 'NOT_SET'
    print(f"       Telegram: {'Configured' if configured else 'NOT CONFIGURED'}")
    return configured

def test_env_bear_longs():
    enabled = os.getenv('ENABLE_BEAR_LONGS', 'false').lower() == 'true'
    print(f"       Bear Longs: {'Enabled' if enabled else 'Disabled'}")
    return True  # Just informational

test("MODE setting", test_env_mode)
test("Equity setting", test_env_equity)
test("Telegram configuration", test_env_telegram)
test("Bear-Resilient Long setting", test_env_bear_longs)


# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("  SUMMARY")
print("=" * 70)
print(f"  Tests Passed: {tests_passed}")
print(f"  Tests Failed: {tests_failed}")
print(f"  Total:        {tests_passed + tests_failed}")
print("=" * 70)

if tests_failed > 0:
    print("\n  FAILED TESTS:")
    for name, status, error in results:
        if status == "FAIL":
            print(f"    - {name}: {error}")
    print()
    sys.exit(1)
else:
    print("\n  All tests passed! V4.1 is ready to run.")
    print("  Start with: python3 v4_main.py")
    print()
    sys.exit(0)
