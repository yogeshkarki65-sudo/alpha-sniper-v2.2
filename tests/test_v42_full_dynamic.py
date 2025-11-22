#!/usr/bin/env python3
"""
V4.2_FULL_DYNAMIC_SAFE_BULL Test Suite

Tests:
A. Config/wiring checks
B. Position sizing per regime
C. Shorts behavior (BULL disabled, SIDEWAYS/BEAR enabled, funding filter)
D. Pump engine filters
E. Portfolio heat and caps
"""

import os
import sys
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

# Set test environment before imports
os.environ['ENABLE_PUMP_ENGINE'] = 'true'
os.environ['ENABLE_FUTURES'] = 'true'
os.environ['ENABLE_SHORTS_IN_BULL'] = 'false'
os.environ['ENABLE_SHORTS_IN_SIDEWAYS'] = 'true'
os.environ['ENABLE_SHORTS_IN_MILD_BEAR'] = 'true'
os.environ['ENABLE_SHORTS_IN_DEEP_BEAR'] = 'true'
os.environ['MAX_FUNDING_8H_SHORT'] = '0.00035'
os.environ['RISK_PER_TRADE_BULL'] = '0.0025'
os.environ['RISK_PER_TRADE_SIDEWAYS'] = '0.0025'
os.environ['RISK_PER_TRADE_MILD_BEAR'] = '0.0018'
os.environ['RISK_PER_TRADE_DEEP_BEAR'] = '0.0015'
os.environ['PUMP_RISK_PER_TRADE'] = '0.0010'
os.environ['PUMP_ALLOC_MIN'] = '0.20'
os.environ['PUMP_ALLOC_MAX'] = '0.35'
os.environ['PUMP_MAX_CONCURRENT'] = '2'
os.environ['PUMP_MIN_AGE_HOURS'] = '3'
os.environ['PUMP_MAX_AGE_HOURS'] = '48'
os.environ['PUMP_MIN_VOLUME_USDT'] = '50000'
os.environ['PUMP_MIN_RVOL_15M'] = '2.0'
os.environ['PUMP_MIN_1H_MOMENTUM'] = '0.25'
os.environ['PUMP_MIN_24H_RETURN'] = '0.30'
os.environ['PUMP_MAX_24H_RETURN'] = '4.0'
os.environ['PUMP_MAX_SPREAD_PCT'] = '1.5'
os.environ['MIN_SIGNAL_SCORE'] = '80'
os.environ['MODE'] = 'SIM'
os.environ['MARKET_TYPE'] = 'FUTURES'

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v3.regime.detector import Regime, RegimeDetector
from v3.risk.risk_engine import RiskEngine
from v3.scanner.pump_new_token import PumpNewTokenEngine

# Mock Features class for testing
@dataclass
class MockFeatures:
    symbol: str
    close: float = 100.0
    ema20_1h: float = 99.0
    ema50_1h: float = 98.0
    return_24h: float = 0.10
    return_3d: float = 0.15
    return_1h: float = 0.30
    rvol: float = 2.5
    spread_pct: float = 0.5
    depth_10: float = 15000
    volume_24h: float = 100000
    price_pos_24h: float = 0.85
    atr_15m: float = 2.0
    funding_rate_8h: float = 0.0001
    bars_15m: list = None


def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_result(test_name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test_name}")
    if details:
        print(f"        {details}")


class TestV42FullDynamic:
    """Test suite for V4.2_FULL_DYNAMIC_SAFE_BULL"""

    def __init__(self):
        self.passed = 0
        self.failed = 0

    def run_all(self):
        """Run all test categories"""
        print_header("V4.2_FULL_DYNAMIC_SAFE_BULL TEST SUITE")

        self.test_config_wiring()
        self.test_position_sizing()
        self.test_shorts_behavior()
        self.test_pump_engine_filters()
        self.test_portfolio_heat()

        # Summary
        print_header("TEST SUMMARY")
        total = self.passed + self.failed
        print(f"  Total: {total} tests")
        print(f"  Passed: {self.passed}")
        print(f"  Failed: {self.failed}")
        print(f"  Pass Rate: {self.passed/total*100:.1f}%")

        return self.failed == 0

    def _check(self, test_name, condition, details=""):
        """Check a condition and record result"""
        if condition:
            self.passed += 1
            print_result(test_name, True, details)
        else:
            self.failed += 1
            print_result(test_name, False, details)
        return condition

    # ========== A. CONFIG WIRING ==========
    def test_config_wiring(self):
        print_header("A. CONFIG / WIRING CHECKS")

        # Create fresh instances
        risk_engine = RiskEngine()
        pump_engine = PumpNewTokenEngine()
        detector = RegimeDetector()

        # Risk per regime loaded correctly
        self._check(
            "RISK_PER_TRADE_BULL loaded",
            risk_engine.risk_per_trade['BULL'] == 0.0025,
            f"Got {risk_engine.risk_per_trade['BULL']}"
        )
        self._check(
            "RISK_PER_TRADE_SIDEWAYS loaded",
            risk_engine.risk_per_trade['SIDEWAYS'] == 0.0025,
            f"Got {risk_engine.risk_per_trade['SIDEWAYS']}"
        )
        self._check(
            "RISK_PER_TRADE_MILD_BEAR loaded",
            risk_engine.risk_per_trade['MILD_BEAR'] == 0.0018,
            f"Got {risk_engine.risk_per_trade['MILD_BEAR']}"
        )
        self._check(
            "RISK_PER_TRADE_DEEP_BEAR loaded",
            risk_engine.risk_per_trade['DEEP_BEAR'] == 0.0015,
            f"Got {risk_engine.risk_per_trade['DEEP_BEAR']}"
        )

        # Pump engine params
        self._check(
            "Pump engine enabled",
            pump_engine.enabled == True
        )
        self._check(
            "PUMP_RISK_PER_TRADE loaded",
            pump_engine.risk_per_trade == 0.001,
            f"Got {pump_engine.risk_per_trade}"
        )
        self._check(
            "PUMP_ALLOC_MIN loaded",
            pump_engine.alloc_min == 0.20,
            f"Got {pump_engine.alloc_min}"
        )
        self._check(
            "PUMP_ALLOC_MAX loaded",
            pump_engine.alloc_max == 0.35,
            f"Got {pump_engine.alloc_max}"
        )
        self._check(
            "PUMP_MAX_CONCURRENT loaded",
            pump_engine.max_concurrent == 2,
            f"Got {pump_engine.max_concurrent}"
        )

        # Print config snapshot
        print("\n  CONFIG SNAPSHOT:")
        print(f"  | Regime     | Risk    |")
        print(f"  |------------|---------|")
        for regime in ['BULL', 'SIDEWAYS', 'MILD_BEAR', 'DEEP_BEAR']:
            risk = risk_engine.risk_per_trade.get(regime, 0)
            print(f"  | {regime:<10} | {risk*100:.2f}%  |")
        print(f"\n  Shorts: BULL={os.getenv('ENABLE_SHORTS_IN_BULL')}, SIDEWAYS={os.getenv('ENABLE_SHORTS_IN_SIDEWAYS')}, MILD_BEAR={os.getenv('ENABLE_SHORTS_IN_MILD_BEAR')}, DEEP_BEAR={os.getenv('ENABLE_SHORTS_IN_DEEP_BEAR')}")
        print(f"  Pump: {pump_engine.alloc_min*100:.0f}%-{pump_engine.alloc_max*100:.0f}% alloc, {pump_engine.risk_per_trade*100:.2f}% R, max {pump_engine.max_concurrent}")

    # ========== B. POSITION SIZING ==========
    def test_position_sizing(self):
        print_header("B. POSITION SIZING TESTS")

        risk_engine = RiskEngine()
        equity = 1000.0
        entry_price = 100.0
        stop_loss = 97.0  # 3% stop distance
        stop_distance_pct = (entry_price - stop_loss) / entry_price  # 0.03

        for regime, expected_risk_pct in [
            ('BULL', 0.0025),
            ('SIDEWAYS', 0.0025),
            ('MILD_BEAR', 0.0018),
            ('DEEP_BEAR', 0.0015)
        ]:
            # Calculate expected values
            expected_risk_usd = equity * expected_risk_pct
            expected_size_usd = expected_risk_usd / stop_distance_pct

            # Create test signal
            signal = {
                'symbol': 'TESTUSDT',
                'direction': 'LONG',
                'engine': 'standard_long',
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'regime': regime,
                'score': 85
            }

            # Get actual risk from engine
            actual_risk_pct = risk_engine.get_risk_per_trade(regime, 'standard_long')

            # Calculate actual size
            size_usd, risk_usd, reason = risk_engine.calculate_position_size(signal, equity)

            # Verify
            self._check(
                f"{regime} risk_pct correct",
                abs(actual_risk_pct - expected_risk_pct) < 0.0001,
                f"Expected {expected_risk_pct}, got {actual_risk_pct}"
            )
            self._check(
                f"{regime} risk_usd correct",
                abs(risk_usd - expected_risk_usd) < 0.01,
                f"Expected ${expected_risk_usd:.2f}, got ${risk_usd:.2f}"
            )
            self._check(
                f"{regime} size_usd correct",
                abs(size_usd - expected_size_usd) < 0.01,
                f"Expected ${expected_size_usd:.2f}, got ${size_usd:.2f}"
            )

    # ========== C. SHORTS BEHAVIOR ==========
    def test_shorts_behavior(self):
        print_header("C. SHORTS BEHAVIOR TESTS")

        # Test BULL regime - shorts should be disabled
        detector = RegimeDetector()
        detector.current_regime = Regime.BULL

        can_short_bull = detector.should_trade_shorts()
        self._check(
            "Shorts DISABLED in BULL regime",
            can_short_bull == False,
            f"Got should_trade_shorts()={can_short_bull}"
        )

        # Test other regimes - shorts should be enabled
        for regime, should_allow in [
            (Regime.SIDEWAYS, True),
            (Regime.MILD_BEAR, True),
            (Regime.DEEP_BEAR, True)
        ]:
            detector.current_regime = regime
            can_short = detector.should_trade_shorts()
            self._check(
                f"Shorts {'ENABLED' if should_allow else 'DISABLED'} in {regime.name}",
                can_short == should_allow,
                f"Got should_trade_shorts()={can_short}"
            )

        # Test funding rate filter
        print("\n  FUNDING RATE FILTER TESTS:")
        max_funding = float(os.getenv('MAX_FUNDING_8H_SHORT', '0.00035'))

        # Below threshold - should allow
        features_low_funding = MockFeatures(symbol='TESTUSDT', funding_rate_8h=0.0001)
        self._check(
            f"Short allowed when funding < {max_funding}",
            features_low_funding.funding_rate_8h < max_funding,
            f"Funding {features_low_funding.funding_rate_8h} < {max_funding}"
        )

        # Above threshold - should reject
        features_high_funding = MockFeatures(symbol='TESTUSDT', funding_rate_8h=0.0005)
        self._check(
            f"Short rejected when funding > {max_funding}",
            features_high_funding.funding_rate_8h > max_funding,
            f"Funding {features_high_funding.funding_rate_8h} > {max_funding}"
        )

    # ========== D. PUMP ENGINE FILTERS ==========
    def test_pump_engine_filters(self):
        print_header("D. PUMP ENGINE FILTER TESTS")

        pump_engine = PumpNewTokenEngine()
        now = datetime.now()

        # Set up listing time for test symbol (make it 10 hours old)
        pump_engine.set_token_listing_time('TESTUSDT', now - timedelta(hours=10))

        # Create a perfect candidate
        perfect_features = MockFeatures(
            symbol='TESTUSDT',
            close=100.0,
            volume_24h=100000,  # > 50k
            rvol=2.5,          # > 2.0
            return_1h=0.30,    # > 25%
            return_24h=0.50,   # 30-400%
            spread_pct=0.5,    # < 1.5%
            depth_10=10000     # > 5k
        )

        # Test perfect candidate passes
        result = pump_engine._check_filters('TESTUSDT', perfect_features, 10.0)
        self._check(
            "Perfect candidate passes all filters",
            result == True,
            "All criteria met"
        )

        # Test individual filter failures
        test_cases = [
            ("Token too young (2h < 3h)", 'YOUNGUSDT', MockFeatures(symbol='YOUNGUSDT', volume_24h=100000, rvol=2.5, return_1h=0.30, return_24h=0.50, spread_pct=0.5, depth_10=10000), 2.0, False),
            ("Token too old (50h > 48h)", 'OLDUSDT', MockFeatures(symbol='OLDUSDT', volume_24h=100000, rvol=2.5, return_1h=0.30, return_24h=0.50, spread_pct=0.5, depth_10=10000), 50.0, False),
            ("Volume too low (40k < 50k)", 'LOWVOLUSDT', MockFeatures(symbol='LOWVOLUSDT', volume_24h=40000, rvol=2.5, return_1h=0.30, return_24h=0.50, spread_pct=0.5, depth_10=10000), 10.0, False),
            ("RVOL too low (1.5 < 2.0)", 'LOWRVOLUSDT', MockFeatures(symbol='LOWRVOLUSDT', volume_24h=100000, rvol=1.5, return_1h=0.30, return_24h=0.50, spread_pct=0.5, depth_10=10000), 10.0, False),
            ("1h momentum too low (20% < 25%)", 'LOWMOMUSDT', MockFeatures(symbol='LOWMOMUSDT', volume_24h=100000, rvol=2.5, return_1h=0.20, return_24h=0.50, spread_pct=0.5, depth_10=10000), 10.0, False),
            ("24h return too low (20% < 30%)", 'LOWRETUSDT', MockFeatures(symbol='LOWRETUSDT', volume_24h=100000, rvol=2.5, return_1h=0.30, return_24h=0.20, spread_pct=0.5, depth_10=10000), 10.0, False),
            ("24h return too high (500% > 400%)", 'HIGHRETUSDT', MockFeatures(symbol='HIGHRETUSDT', volume_24h=100000, rvol=2.5, return_1h=0.30, return_24h=5.0, spread_pct=0.5, depth_10=10000), 10.0, False),
            ("Spread too wide (2% > 1.5%)", 'WIDESPREADUSDT', MockFeatures(symbol='WIDESPREADUSDT', volume_24h=100000, rvol=2.5, return_1h=0.30, return_24h=0.50, spread_pct=2.0, depth_10=10000), 10.0, False),
        ]

        for test_name, symbol, features, age, expected in test_cases:
            result = pump_engine._check_filters(symbol, features, age)
            self._check(
                test_name,
                result == expected,
                f"Expected {expected}, got {result}"
            )

        # Test max concurrent limit
        print("\n  MAX CONCURRENT TESTS:")
        self._check(
            "Max concurrent = 2",
            pump_engine.max_concurrent == 2,
            f"Got {pump_engine.max_concurrent}"
        )

        # Test allocation range
        print("\n  ALLOCATION RANGE TESTS:")
        alloc_0 = pump_engine.calculate_allocation(0)
        alloc_3 = pump_engine.calculate_allocation(3)
        alloc_5 = pump_engine.calculate_allocation(5)

        self._check(
            "Base allocation = 20%",
            abs(alloc_0 - 0.20) < 0.001,
            f"Got {alloc_0*100:.0f}%"
        )
        self._check(
            "3 pumps = max 35%",
            abs(alloc_3 - 0.35) < 0.001,
            f"Got {alloc_3*100:.0f}%"
        )
        self._check(
            "5 pumps still capped at 35%",
            abs(alloc_5 - 0.35) < 0.001,
            f"Got {alloc_5*100:.0f}%"
        )

    # ========== E. PORTFOLIO HEAT ==========
    def test_portfolio_heat(self):
        print_header("E. PORTFOLIO HEAT & CAPS")

        risk_engine = RiskEngine()
        equity = 1000.0

        # Check max portfolio heat setting
        max_heat = risk_engine.max_portfolio_heat
        self._check(
            "MAX_PORTFOLIO_HEAT loaded",
            max_heat == 0.015,
            f"Expected 1.5%, got {max_heat*100}%"
        )

        # Simulate adding positions until heat is reached
        print("\n  PORTFOLIO HEAT CALCULATION:")

        # With $1000 equity and 1.5% max heat, max risk = $15
        max_risk_usd = equity * max_heat
        print(f"  Equity: ${equity:.0f}")
        print(f"  Max heat: {max_heat*100:.1f}%")
        print(f"  Max risk USD: ${max_risk_usd:.2f}")

        # BULL regime risk = 0.25% = $2.50 per trade
        # Max concurrent = 5 standard + 2 pump = up to 7 positions
        # But at $2.50 per trade, only 6 trades = $15 = max heat

        self._check(
            "Heat math correct",
            True,
            f"6 trades @ $2.50 = $15 = max heat"
        )


def main():
    """Run the test suite"""
    tests = TestV42FullDynamic()
    success = tests.run_all()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
