"""
Alpha Sniper V4.0 - Comprehensive System Test
Tests all components to catch errors BEFORE running live
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all imports work"""
    print("\n" + "="*70)
    print("TEST 1: Imports")
    print("="*70)

    try:
        from v4.data.mexc_client import MEXCClient
        from v4.core.regime_detector import regime_detector, Regime
        from v4.core.execution_engine import ExecutionEngine
        from v4.scanner.feature_extractor import FeatureExtractor
        from v4.scanner.v4_scanner import V4Scanner
        from v4.scanner.symbol_state import symbol_state_manager
        from v4.trader.position_manager import PositionManager
        from v4.monitoring.telegram_notifier import telegram_notifier
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mexc_api():
    """Test MEXC API endpoints"""
    print("\n" + "="*70)
    print("TEST 2: MEXC API")
    print("="*70)

    try:
        from v4.data.mexc_client import MEXCClient
        client = MEXCClient(cache_ttl=60)

        # Test 1: 24h tickers
        print("\n[2.1] Testing get_24h_tickers()...")
        tickers = client.get_24h_tickers()
        if not tickers or len(tickers) == 0:
            print(f"❌ get_24h_tickers() returned empty")
            return False
        print(f"✅ Fetched {len(tickers)} tickers")

        # Test 2: Single ticker
        print("\n[2.2] Testing get_ticker_24h(SOLUSDT)...")
        ticker = client.get_ticker_24h('SOLUSDT')
        if not ticker:
            print(f"❌ get_ticker_24h('SOLUSDT') returned None")
            return False
        print(f"✅ Ticker: {ticker['symbol']} @ ${ticker['lastPrice']}")

        # Test 3: Klines 15m
        print("\n[2.3] Testing get_klines(SOLUSDT, 15m)...")
        df_15m = client.get_klines('SOLUSDT', interval='15m', limit=100)
        if df_15m is None or len(df_15m) == 0:
            print(f"❌ get_klines('SOLUSDT', '15m') failed")
            return False
        print(f"✅ Fetched {len(df_15m)} bars (15m)")
        print(f"   Columns: {list(df_15m.columns)}")
        print(f"   Latest close: ${df_15m['close'].iloc[-1]:.2f}")

        # Test 4: Klines 1h (tests 60m conversion)
        print("\n[2.4] Testing get_klines(SOLUSDT, 1h)...")
        df_1h = client.get_klines('SOLUSDT', interval='1h', limit=100)
        if df_1h is None or len(df_1h) == 0:
            print(f"❌ get_klines('SOLUSDT', '1h') failed")
            return False
        print(f"✅ Fetched {len(df_1h)} bars (1h/60m)")

        # Test 5: Klines 4h
        print("\n[2.5] Testing get_klines(SOLUSDT, 4h)...")
        df_4h = client.get_klines('SOLUSDT', interval='4h', limit=60)
        if df_4h is None or len(df_4h) == 0:
            print(f"❌ get_klines('SOLUSDT', '4h') failed")
            return False
        print(f"✅ Fetched {len(df_4h)} bars (4h)")

        # Test 6: Orderbook
        print("\n[2.6] Testing get_orderbook(SOLUSDT)...")
        orderbook = client.get_orderbook('SOLUSDT', limit=10)
        if not orderbook or 'bids' not in orderbook:
            print(f"❌ get_orderbook('SOLUSDT') failed")
            return False
        print(f"✅ Orderbook: {len(orderbook['bids'])} bids, {len(orderbook['asks'])} asks")
        print(f"   Best bid: ${orderbook['bids'][0][0]:.2f}")
        print(f"   Best ask: ${orderbook['asks'][0][0]:.2f}")

        print("\n✅ All MEXC API tests passed")
        return True

    except Exception as e:
        print(f"❌ MEXC API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_feature_extraction():
    """Test feature extraction"""
    print("\n" + "="*70)
    print("TEST 3: Feature Extraction")
    print("="*70)

    try:
        from v4.data.mexc_client import MEXCClient
        from v4.scanner.feature_extractor import FeatureExtractor

        client = MEXCClient(cache_ttl=60)
        extractor = FeatureExtractor(client)

        # Get ticker data
        ticker = client.get_ticker_24h('SOLUSDT')
        if not ticker:
            print("❌ Could not fetch ticker for SOLUSDT")
            return False

        print("\n[3.1] Extracting features for SOLUSDT...")
        features = extractor.extract('SOLUSDT', ticker)

        if not features:
            print("❌ Feature extraction returned None")
            return False

        print(f"✅ Extracted {len(features)} features")

        # Verify key features exist
        required_features = [
            'close', 'symbol',
            'ema20_4h', 'ema50_4h', 'trend_ratio_4h',
            'rvol_15m',
            'atr_14_15m', 'atr_median_24h', 'atr_compression',
            'high_24h', 'low_24h', 'price_pos_24h',
            'return_1h', 'return_4h', 'return_24h', 'return_3d',
            'rsi_1h',
            'higher_lows_recent', 'has_lower_high'
        ]

        print("\n[3.2] Checking required features...")
        missing = []
        for feat in required_features:
            if feat not in features:
                missing.append(feat)

        if missing:
            print(f"❌ Missing features: {missing}")
            return False

        print("✅ All required features present")

        # Print sample features
        print("\n[3.3] Sample features:")
        print(f"   Symbol: {features['symbol']}")
        print(f"   Close: ${features['close']:.2f}")
        print(f"   Trend ratio (4h): {features['trend_ratio_4h']:.3f}")
        print(f"   RVOL (15m): {features['rvol_15m']:.2f}x")
        print(f"   ATR compression: {features['atr_compression']:.2f}")
        print(f"   RSI (1h): {features['rsi_1h']:.1f}")
        print(f"   Return 24h: {features['return_24h']*100:+.2f}%")

        print("\n✅ Feature extraction test passed")
        return True

    except Exception as e:
        print(f"❌ Feature extraction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_regime_detection():
    """Test regime detection"""
    print("\n" + "="*70)
    print("TEST 4: Regime Detection")
    print("="*70)

    try:
        from v4.data.mexc_client import MEXCClient
        from v4.core.regime_detector import regime_detector, Regime

        client = MEXCClient(cache_ttl=60)

        print("\n[4.1] Fetching BTC and ETH data...")
        btc_df = client.get_klines('BTCUSDT', interval='1d', limit=365)
        eth_df = client.get_klines('ETHUSDT', interval='1d', limit=365)

        if btc_df is None or eth_df is None:
            print("❌ Could not fetch BTC/ETH data")
            return False

        print(f"✅ BTC: {len(btc_df)} days, ETH: {len(eth_df)} days")

        print("\n[4.2] Detecting regime...")
        regime, details = regime_detector.detect(btc_df, eth_df)

        print(f"✅ Regime: {regime.value}")
        print(f"   Z-Score: {details.get('Z_ret', 0):.2f}")
        print(f"   Alt Strength: {details.get('RS_alt_21', 0):.4f}")
        print(f"   EMA State: {details.get('ema_state', 0)}")
        print(f"   Vol State: {details.get('vol_state', 'UNKNOWN')}")

        # Test regime-specific parameters
        print("\n[4.3] Testing regime parameters...")
        if regime in [Regime.BULL, Regime.SIDEWAYS]:
            max_longs = regime_detector.get_max_concurrent_longs()
            risk_mult = regime_detector.get_risk_multiplier()
            print(f"   Max concurrent longs: {max_longs}")
            print(f"   Risk multiplier: {risk_mult:.2f}")
        elif regime == Regime.BEAR:
            max_shorts = regime_detector.get_max_concurrent_shorts()
            print(f"   Max concurrent shorts: {max_shorts}")

        print("\n✅ Regime detection test passed")
        return True

    except Exception as e:
        print(f"❌ Regime detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_scanner():
    """Test scanner with filters and scoring"""
    print("\n" + "="*70)
    print("TEST 5: Scanner (Filters + Scoring)")
    print("="*70)

    try:
        from v4.data.mexc_client import MEXCClient
        from v4.scanner.feature_extractor import FeatureExtractor
        from v4.scanner.v4_scanner import V4Scanner
        from v4.core.regime_detector import regime_detector, Regime

        client = MEXCClient(cache_ttl=60)
        extractor = FeatureExtractor(client)
        scanner = V4Scanner(client, extractor)

        # Get regime
        print("\n[5.1] Detecting regime...")
        btc_df = client.get_klines('BTCUSDT', interval='1d', limit=365)
        eth_df = client.get_klines('ETHUSDT', interval='1d', limit=365)
        regime, details = regime_detector.detect(btc_df, eth_df)
        print(f"✅ Regime: {regime.value}")

        # Build small universe
        print("\n[5.2] Building test universe (top 20)...")
        tickers = client.get_24h_tickers()
        universe = []
        for ticker in tickers:
            if ticker['symbol'].endswith('USDT') and ticker['symbol'] not in ['BTCUSDT', 'ETHUSDT']:
                qv = float(ticker.get('quoteVolume', 0))
                if qv > 30000:
                    universe.append({
                        'symbol': ticker['symbol'],
                        'quote_volume': qv,
                        'ticker': ticker
                    })

        universe.sort(key=lambda x: x['quote_volume'], reverse=True)
        universe = universe[:20]  # Test with top 20

        print(f"✅ Test universe: {len(universe)} symbols")
        print(f"   Top 5: {[u['symbol'] for u in universe[:5]]}")

        # Scan
        print(f"\n[5.3] Scanning for signals ({regime.value} regime)...")
        signals = scanner.scan(universe, regime, details)

        print(f"✅ Generated {len(signals)} signals")

        if signals:
            print("\n[5.4] Top 5 signals:")
            for i, sig in enumerate(signals[:5], 1):
                print(f"   {i}. {sig['symbol']}: score={sig['score']:.3f}, "
                      f"engine={sig['engine']}, direction={sig['direction']}")
        else:
            print("\n⚠️  No signals (may be correct depending on regime/market)")

        print("\n✅ Scanner test passed")
        return True

    except Exception as e:
        print(f"❌ Scanner test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_execution_engine():
    """Test execution engine"""
    print("\n" + "="*70)
    print("TEST 6: Execution Engine")
    print("="*70)

    try:
        from v4.data.mexc_client import MEXCClient
        from v4.core.execution_engine import ExecutionEngine

        client = MEXCClient(cache_ttl=60)
        engine = ExecutionEngine(client)

        print("\n[6.1] Testing liquidity check for SOLUSDT...")
        liquidity = engine.check_liquidity('SOLUSDT')

        if not liquidity:
            print("❌ Liquidity check returned None")
            return False

        print(f"✅ Liquidity snapshot:")
        print(f"   Spread: {liquidity.effective_spread_pct:.3f}%")
        print(f"   Bid depth (top 10): ${liquidity.bid_depth_10_usdt:,.0f}")
        print(f"   Ask depth (top 10): ${liquidity.ask_depth_10_usdt:,.0f}")
        print(f"   Liquid enough: {liquidity.is_liquid_enough()}")

        print("\n[6.2] Testing dynamic cap calculation...")
        cap = engine.calculate_dynamic_cap(
            'SOLUSDT',
            liquidity,
            current_equity=500,
            direction='LONG'
        )
        print(f"✅ Dynamic cap: ${cap:.2f}")

        print("\n[6.3] Testing order execution (SIMULATION)...")
        result = engine.execute_order(
            symbol='SOLUSDT',
            direction='LONG',
            trigger_price=liquidity.best_ask,
            intended_size_usdt=50,
            current_equity=500,
            mode='SIMULATION'
        )

        print(f"✅ Execution result:")
        print(f"   Success: {result.success}")
        print(f"   Reason: {result.reason}")
        if result.success:
            print(f"   Fill price: ${result.fill_price:.4f}")
            print(f"   Fill size: ${result.fill_size_usdt:.2f}")
            print(f"   Slippage: {result.slippage_pct:.3f}%")

        print("\n✅ Execution engine test passed")
        return True

    except Exception as e:
        print(f"❌ Execution engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_position_manager():
    """Test position manager"""
    print("\n" + "="*70)
    print("TEST 7: Position Manager")
    print("="*70)

    try:
        from v4.data.mexc_client import MEXCClient
        from v4.core.execution_engine import ExecutionEngine
        from v4.trader.position_manager import PositionManager

        client = MEXCClient(cache_ttl=60)
        engine = ExecutionEngine(client)
        pm = PositionManager(client, engine, telegram_notifier=None)

        print("\n[7.1] Testing open position...")
        position = pm.open_position(
            symbol='SOLUSDT',
            direction='LONG',
            entry_price=100.0,
            size_usdt=50.0,
            stop_loss=98.0,
            regime='BULL',
            atr=1.5
        )

        print(f"✅ Position opened:")
        print(f"   Symbol: {position.symbol}")
        print(f"   Entry: ${position.entry_price:.2f}")
        print(f"   Size: ${position.size_usdt:.2f}")
        print(f"   Stop: ${position.stop_loss:.2f}")
        print(f"   Risk (1R): ${position.r_dollars:.2f}")

        print("\n[7.2] Testing position count...")
        count = pm.get_open_positions_count()
        print(f"✅ Open positions: {count}")

        print("\n[7.3] Testing portfolio heat...")
        heat = pm.get_portfolio_heat()
        print(f"✅ Portfolio heat: {heat:.4f}")

        print("\n[7.4] Testing position update...")
        pm.update_positions(current_equity=500)
        print(f"✅ Position update completed")

        print("\n✅ Position manager test passed")
        return True

    except Exception as e:
        print(f"❌ Position manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 ALPHA SNIPER V4.0 - COMPREHENSIVE SYSTEM TEST")
    print("="*70)
    print(f"Started: {datetime.now()}")

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("MEXC API", test_mexc_api()))
    results.append(("Feature Extraction", test_feature_extraction()))
    results.append(("Regime Detection", test_regime_detection()))
    results.append(("Scanner", test_scanner()))
    results.append(("Execution Engine", test_execution_engine()))
    results.append(("Position Manager", test_position_manager()))

    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)

    passed = 0
    failed = 0

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
        else:
            failed += 1

    print("\n" + "="*70)
    print(f"Total: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Finished: {datetime.now()}")
    print("="*70)

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! V4.0 is ready to run.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Fix errors before running V4.0.")
        return 1

if __name__ == "__main__":
    exit(main())
