"""
Alpha Sniper V3.2 - Integration Test

Tests that all core modules work together:
1. Regime detection
2. Universe filtering
3. Symbol state tracking
4. Risk sizing
5. Execution cost estimation
"""
import sys
import os

# Add v3 to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from v3.regime.detector import regime_detector
from v3.universe.manager import universe_manager
from v3.universe.symbol_state import symbol_state_manager
from v3.risk.risk_engine import risk_engine
from v3.execution.cost_model import execution_cost_model
from v3.data.mexc_client import mexc_client


def test_regime_detection():
    """Test regime detection module"""
    print("\n" + "="*60)
    print("TEST 1: REGIME DETECTION")
    print("="*60)

    try:
        regime, details = regime_detector.detect(force_refresh=True)

        print(f"✅ Current Regime: {regime.value}")
        print(f"   Z-Score: {details['z_ret']:.2f}")
        print(f"   EMA State: {details['ema_state']}")
        print(f"   Vol Regime: {details['vol_regime']}")
        print(f"   Alt Strength: {details['alt_strength']:.4f}")
        print(f"   Risk Multiplier: {regime_detector.get_risk_multiplier():.2f}x")

        if details['pending_regime']:
            print(f"   ⏳ Pending Change to: {details['pending_regime']}")
            print(f"   Hours Pending: {details['hours_pending']:.1f}h")

        return True

    except Exception as e:
        print(f"❌ Regime detection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_universe_management():
    """Test universe filtering"""
    print("\n" + "="*60)
    print("TEST 2: UNIVERSE MANAGEMENT")
    print("="*60)

    try:
        universe = universe_manager.update_universe(force_refresh=True)

        stats = universe_manager.get_universe_stats()

        print(f"✅ Universe Size: {stats['symbol_count']} symbols")
        print(f"   Total 24h Volume: ${stats['total_volume_24h']:,.0f}")
        print(f"   Avg Spread: {stats['avg_spread_pct']:.3f}%")
        print(f"   Median Volume: ${stats['median_volume']:,.0f}")

        if len(universe) > 0:
            print(f"\n   Top 5 by volume:")
            for i, pair in enumerate(universe[:5], 1):
                print(f"   {i}. {pair['symbol']}: "
                      f"${pair['volume_24h_usd']:,.0f}, "
                      f"spread={pair['spread_pct']:.2f}%")

        return len(universe) > 0

    except Exception as e:
        print(f"❌ Universe management failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_symbol_states():
    """Test symbol state machine"""
    print("\n" + "="*60)
    print("TEST 3: SYMBOL STATE MACHINE")
    print("="*60)

    try:
        # Get a few symbols from universe
        universe = universe_manager.current_universe[:5]

        if len(universe) == 0:
            print("⚠️  No symbols in universe to test")
            return False

        print(f"Testing state updates for {len(universe)} symbols...\n")

        for pair in universe:
            symbol = pair['symbol']

            # Fetch 15m data for state detection
            bars = mexc_client.get_klines(symbol, interval="15m", limit=100)

            if bars is None or len(bars) < 20:
                print(f"   ⚠️  {symbol}: Insufficient data")
                continue

            # Calculate ATR
            from v3.utils.indicators import atr
            atr_14 = atr(bars['high'], bars['low'], bars['close'], 14).iloc[-1]
            atr_24h_median = atr(bars['high'], bars['low'], bars['close'], 14).median()

            # Calculate RVOL
            rvol = pair['volume_24h_usd'] / max(bars['volume'].median(), 1)

            # Update state
            state = symbol_state_manager.update_symbol(
                symbol=symbol,
                close=pair['last_price'],
                high_24h=pair['high_24h'],
                low_24h=pair['low_24h'],
                atr_14=atr_14,
                atr_24h_median=atr_24h_median,
                rvol=rvol,
                bars_data=bars
            )

            state_machine = symbol_state_manager.get_or_create(symbol)
            tradeable = "✅" if state_machine.is_tradeable() else "❌"

            print(f"   {tradeable} {symbol}: {state.value}")

        print(f"\n✅ State machine working")
        return True

    except Exception as e:
        print(f"❌ Symbol state machine failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_risk_sizing():
    """Test risk engine position sizing"""
    print("\n" + "="*60)
    print("TEST 4: RISK ENGINE")
    print("="*60)

    try:
        # Get current regime
        regime, _ = regime_detector.detect()

        # Test position sizing
        test_entry = 100.0
        test_stop = 95.0  # 5% stop

        size_usd, details = risk_engine.calculate_position_size(
            symbol="TESTUSDT",
            entry_price=test_entry,
            stop_loss_price=test_stop,
            regime=regime,
            signal_quality=0.8
        )

        print(f"✅ Position Sizing Test:")
        print(f"   Entry: ${test_entry}")
        print(f"   Stop: ${test_stop} (5% risk)")
        print(f"   Regime: {regime.value}")
        print(f"   Signal Quality: 0.8")
        print(f"\n   → Position Size: ${size_usd:.2f}")
        print(f"   → Risk %: {details['actual_risk_pct']:.3f}%")
        print(f"   → Risk $: ${details['risk_usd']:.2f}")
        print(f"   → Position % of Equity: {details['position_size_pct_equity']:.1f}%")

        # Test portfolio limits
        print(f"\n✅ Risk Limits:")
        stats = risk_engine.get_stats()
        print(f"   Current Equity: ${stats['current_equity']:.2f}")
        print(f"   Open Positions: {stats['open_positions']}")
        print(f"   Portfolio Heat: {stats['portfolio_heat_pct']:.2f}%")
        print(f"   Daily P&L: ${stats['daily_pnl']:.2f}")
        print(f"   Risk Multiplier: {stats['risk_multiplier']:.2f}x")

        return True

    except Exception as e:
        print(f"❌ Risk engine failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_execution_cost():
    """Test execution cost modeling"""
    print("\n" + "="*60)
    print("TEST 5: EXECUTION COST MODEL")
    print("="*60)

    try:
        # Test cost estimation
        test_symbol = "BTCUSDT"
        test_price = 50000.0
        test_size = 100.0
        test_spread = 0.01  # 1bp
        test_depth = 10000.0

        cost_estimate = execution_cost_model.estimate_entry_cost(
            symbol=test_symbol,
            intended_price=test_price,
            order_size_usd=test_size,
            spread_pct=test_spread,
            orderbook_depth_usd=test_depth,
            urgency="NORMAL"
        )

        print(f"✅ Cost Estimation for {test_symbol}:")
        print(f"   Intended Price: ${test_price}")
        print(f"   Order Size: ${test_size}")
        print(f"   Spread: {test_spread:.2f}%")
        print(f"\n   Cost Breakdown:")
        print(f"   - Fee: {cost_estimate['fee_pct']*100:.3f}%")
        print(f"   - Spread Cross: {cost_estimate['spread_cost_pct']*100:.3f}%")
        print(f"   - Market Impact: {cost_estimate['impact_pct']*100:.3f}%")
        print(f"   - Adverse Selection: {cost_estimate['adverse_selection_pct']*100:.3f}%")
        print(f"   → Total Cost: {cost_estimate['total_cost_pct']*100:.3f}%")
        print(f"   → Expected Fill: ${cost_estimate['expected_fill_price']:.2f}")
        print(f"   → Fill Probability: {cost_estimate['fill_probability']*100:.0f}%")

        return True

    except Exception as e:
        print(f"❌ Execution cost model failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_signal_flow():
    """Test complete signal flow from universe to position sizing"""
    print("\n" + "="*60)
    print("TEST 6: FULL SIGNAL FLOW")
    print("="*60)

    try:
        # 1. Get regime
        regime, regime_details = regime_detector.detect()
        print(f"1️⃣  Regime: {regime.value}")

        # 2. Get universe
        universe = universe_manager.current_universe
        print(f"2️⃣  Universe: {len(universe)} symbols")

        # 3. Get tradeable symbols
        tradeable = symbol_state_manager.get_tradeable_symbols()
        print(f"3️⃣  Tradeable: {len(tradeable)} symbols")

        # 4. Check if we can trade
        can_trade = regime_detector.should_trade_longs()
        print(f"4️⃣  Should Trade Longs: {can_trade}")

        # 5. Find a symbol to size
        if len(universe) > 0:
            test_symbol_data = universe[0]
            test_symbol = test_symbol_data['symbol']

            # Check risk capacity
            can_open, reason = risk_engine.can_open_position(
                symbol=test_symbol,
                risk_usd=2.0  # $2 risk
            )

            print(f"5️⃣  Can Open {test_symbol}: {can_open} ({reason})")

            if can_open:
                # Size a position
                entry = test_symbol_data['last_price']
                stop = entry * 0.97  # 3% stop

                size, details = risk_engine.calculate_position_size(
                    symbol=test_symbol,
                    entry_price=entry,
                    stop_loss_price=stop,
                    regime=regime,
                    signal_quality=0.75
                )

                print(f"6️⃣  Position Sizing:")
                print(f"     Size: ${size:.2f} ({details['position_size_pct_equity']:.1f}% of equity)")
                print(f"     Risk: {details['actual_risk_pct']:.3f}%")

        print(f"\n✅ Full signal flow working!")
        return True

    except Exception as e:
        print(f"❌ Full signal flow failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests"""
    print("\n" + "="*70)
    print("  ALPHA SNIPER V3.2 - INTEGRATION TEST SUITE")
    print("="*70)
    print(f"  Time: {datetime.now()}")
    print("="*70)

    tests = [
        ("Regime Detection", test_regime_detection),
        ("Universe Management", test_universe_management),
        ("Symbol States", test_symbol_states),
        ("Risk Sizing", test_risk_sizing),
        ("Execution Cost", test_execution_cost),
        ("Full Signal Flow", test_full_signal_flow),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*70)
    print("  TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")

    print("="*70)
    print(f"  Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("="*70)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! V3.2 core modules are working.")
        print("\nNext steps:")
        print("  1. Build scanner (feature extraction + scoring)")
        print("  2. Build trader (execution + position management)")
        print("  3. Run simple backtest to validate edge")
        print("  4. Add ML training if edge exists")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Fix before proceeding.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
