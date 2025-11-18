"""
Signal Generator for Alpha Sniper V3.2

Main scanner that:
1. Gets universe from UniverseManager
2. Extracts features for each symbol
3. Updates symbol states
4. Scores signals
5. Ranks and filters top opportunities
"""
from typing import List, Dict, Optional
from datetime import datetime

from v3.universe.manager import universe_manager
from v3.universe.symbol_state import symbol_state_manager, SymbolState
from v3.regime.detector import regime_detector, Regime
from v3.scanner.features import feature_extractor
from v3.scanner.scorer import scanner_scorer
from v3.data.mexc_client import mexc_client


class SignalGenerator:
    """
    Generates trading signals from universe
    """

    def __init__(
        self,
        top_k_signals: int = 5,
        min_scanner_score: float = 60.0,
        fetch_orderbook: bool = True
    ):
        """
        Args:
            top_k_signals: Max number of signals to generate per scan
            min_scanner_score: Minimum score threshold
            fetch_orderbook: Whether to fetch orderbook data (slower but better)
        """
        self.top_k_signals = top_k_signals
        self.min_scanner_score = min_scanner_score
        self.fetch_orderbook = fetch_orderbook

        # Statistics
        self.last_scan_time: Optional[datetime] = None
        self.symbols_scanned = 0
        self.signals_generated = 0

    def scan(self) -> List[Dict]:
        """
        Run full scan cycle

        Returns:
            List of signal dicts, sorted by score (best first)
        """
        scan_start = datetime.now()
        print(f"\n{'='*60}")
        print(f"🔍 SCANNER CYCLE - {scan_start}")
        print(f"{'='*60}")

        # 1. Get current regime
        regime, regime_details = regime_detector.detect()
        print(f"📊 Regime: {regime.value}")
        print(f"   Z-Score: {regime_details['z_ret']:.2f}")
        print(f"   Alt Strength: {regime_details['alt_strength']:.4f}")

        # Check if we should trade
        if not regime_detector.should_trade_longs():
            print(f"⚠️  Regime {regime.value} - NOT trading longs")
            return []

        # 2. Update universe
        universe = universe_manager.update_universe()
        print(f"🌍 Universe: {len(universe)} symbols")

        if len(universe) == 0:
            print("⚠️  Empty universe, skipping scan")
            return []

        # 3. Scan each symbol
        all_signals = []
        scanned = 0

        for symbol_data in universe:
            try:
                signal = self._scan_symbol(symbol_data, regime)

                if signal is not None:
                    all_signals.append(signal)

                scanned += 1

            except Exception as e:
                print(f"[Scanner] Error scanning {symbol_data.get('symbol')}: {e}")
                continue

        print(f"\n📈 Scanned {scanned} symbols")
        print(f"✅ Generated {len(all_signals)} raw signals")

        # 4. Rank and filter signals
        top_signals = scanner_scorer.rank_signals(all_signals, top_k=self.top_k_signals)

        print(f"🎯 Top {len(top_signals)} signals after ranking:")
        for i, sig in enumerate(top_signals, 1):
            print(f"   {i}. {sig['symbol']}: "
                  f"score={sig['score']:.1f} ({sig['quality']}), "
                  f"state={sig['symbol_state']}, "
                  f"rvol={sig['features']['rvol_15m']:.2f}")

        # Update stats
        self.last_scan_time = scan_start
        self.symbols_scanned = scanned
        self.signals_generated = len(top_signals)

        scan_duration = (datetime.now() - scan_start).total_seconds()
        print(f"\n⏱️  Scan completed in {scan_duration:.2f}s")
        print(f"{'='*60}\n")

        return top_signals

    def _scan_symbol(
        self,
        symbol_data: Dict,
        regime: Regime
    ) -> Optional[Dict]:
        """
        Scan a single symbol

        Returns:
            Signal dict if valid, None otherwise
        """
        symbol = symbol_data['symbol']

        # 1. Extract features
        features = feature_extractor.extract_features(
            symbol=symbol,
            ticker_data=symbol_data,
            fetch_orderbook=self.fetch_orderbook
        )

        if features is None:
            return None

        # 2. Update symbol state
        state = symbol_state_manager.update_symbol(
            symbol=symbol,
            close=features['last_price'],
            high_24h=features['high_24h'],
            low_24h=features['low_24h'],
            atr_14=features['atr_14'],
            atr_24h_median=features['atr_median_24h'],
            rvol=features['rvol_15m']
        )

        # 3. Check if symbol is tradeable
        state_machine = symbol_state_manager.get_or_create(symbol)
        if not state_machine.is_tradeable():
            return None

        # 4. Calculate score
        score_result = scanner_scorer.calculate_score(
            features=features,
            regime=regime,
            symbol_state=state.value
        )

        # 5. Check validity
        if not score_result['is_valid']:
            return None

        # 6. Build signal
        signal = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'score': score_result['score'],
            'quality': score_result['quality'],
            'regime': regime.value,
            'symbol_state': state.value,
            'features': features,
            'component_scores': score_result['component_scores'],
            'weights': score_result['weights'],
            'is_valid': score_result['is_valid']
        }

        return signal

    def get_stats(self) -> Dict:
        """Get scanner statistics"""
        return {
            'last_scan_time': self.last_scan_time,
            'symbols_scanned': self.symbols_scanned,
            'signals_generated': self.signals_generated
        }


# Singleton instance
signal_generator = SignalGenerator(
    top_k_signals=5,
    min_scanner_score=60.0,
    fetch_orderbook=False  # Set False for speed, True for quality
)
