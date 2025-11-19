"""
Alpha Sniper V4.0 - Main Scanner
Combines: Regime + Filters + Edges + Scoring
"""
import os
from typing import List, Dict
from datetime import datetime

from v4.core.regime_detector import regime_detector, Regime
from v4.scanner.symbol_state import symbol_state_manager, SymbolState
from v4.scanner.filters import entry_filters
from v4.edges.edge_detector import edge_detector


class V4Scanner:
    """
    Main scanner for V4.0

    Scans universe, applies filters, scores with edges
    """

    def __init__(self, mexc_client, feature_extractor):
        self.mexc_client = mexc_client
        self.feature_extractor = feature_extractor

    def scan(self, universe: List[Dict], regime: Regime, regime_details: Dict) -> List[Dict]:
        """
        Scan universe for signals

        Returns:
            List of signal dicts with scores
        """
        print(f"\n{'='*60}")
        print(f"🔍 V4 SCANNER CYCLE - {datetime.now()}")
        print(f"{'='*60}")
        print(f"📊 Regime: {regime.value}")
        print(f"   Z-Score: {regime_details.get('Z_ret', 0):.2f}")
        print(f"   Alt Strength: {regime_details.get('RS_alt_21', 0):.4f}")

        # Update all symbol states
        symbol_state_manager.update_all()

        all_signals = []

        # Scan based on regime
        if regime == Regime.BULL or regime == Regime.SIDEWAYS:
            signals = self._scan_for_longs(universe, regime, regime_details)
            all_signals.extend(signals)

        elif regime == Regime.BEAR:
            market_type = os.getenv('MARKET_TYPE', 'SPOT')
            if market_type == 'FUTURES':
                signals = self._scan_for_shorts(universe, regime, regime_details)
                all_signals.extend(signals)
            else:
                print("⚠️  BEAR regime but MARKET_TYPE=SPOT, shorts disabled")

        elif regime == Regime.NEUTRAL:
            print("⚠️  NEUTRAL regime - no new trades")

        # Rank and filter
        all_signals.sort(key=lambda x: x['score'], reverse=True)

        print(f"\n✅ Generated {len(all_signals)} signals")
        for i, sig in enumerate(all_signals[:5], 1):
            print(f"   {i}. {sig['symbol']}: score={sig['score']:.2f}, "
                  f"engine={sig['engine']}, perfect_storm={sig['perfect_storm']}")

        return all_signals

    def _scan_for_longs(
        self,
        universe: List[Dict],
        regime: Regime,
        regime_details: Dict
    ) -> List[Dict]:
        """Scan for long signals (BULL/SIDEWAYS)"""
        signals = []
        alt_strength = regime_details.get('RS_alt_21', 0)

        for sym_data in universe:
            symbol = sym_data['symbol']

            # Check state
            state_machine = symbol_state_manager.get_or_create(symbol)
            if not state_machine.is_tradeable():
                continue

            # Extract features
            features = self.feature_extractor.extract(symbol, sym_data)
            if not features:
                continue

            # Try each long engine
            # 1) COIL BREAKOUT
            signal = self._try_coil_breakout_long(symbol, features, regime, alt_strength)
            if signal:
                signals.append(signal)

            # 2) TREND PULLBACK (BULL only)
            elif regime == Regime.BULL:
                signal = self._try_trend_pullback_long(symbol, features, regime, alt_strength)
                if signal:
                    signals.append(signal)

            # 3) RANGE EXPANSION (SIDEWAYS only)
            elif regime == Regime.SIDEWAYS:
                signal = self._try_range_expansion_long(symbol, features, regime, alt_strength)
                if signal:
                    signals.append(signal)

        return signals

    def _try_coil_breakout_long(
        self,
        symbol: str,
        features: Dict,
        regime: Regime,
        alt_strength: float
    ) -> Dict:
        """Try COIL BREAKOUT engine"""
        # Check filters
        ok, msg = entry_filters.check_long_filter_1_clean_4h_uptrend(features)
        if not ok:
            return None

        ok, msg = entry_filters.check_long_filter_2_healthy_rvol(features, regime.value)
        if not ok:
            return None

        ok, msg = entry_filters.check_long_filter_3_coil_buildup(features)
        if not ok:
            return None

        ok, msg = entry_filters.check_long_filter_4_early_breakout(features)
        if not ok:
            return None

        # Calculate score
        score = self._calculate_long_score(symbol, features, regime, alt_strength)

        if score < 0.7:  # Min threshold
            return None

        return {
            'symbol': symbol,
            'direction': 'LONG',
            'engine': 'COIL_BREAKOUT',
            'score': score,
            'entry_price': features.get('close'),
            'features': features,
            'perfect_storm': score > 0.85  # Likely has perfect storm boost
        }

    def _try_trend_pullback_long(
        self,
        symbol: str,
        features: Dict,
        regime: Regime,
        alt_strength: float
    ) -> Dict:
        """Try TREND PULLBACK engine (BULL only)"""
        # Simplified check (full implementation would be more detailed)
        ema20 = features.get('ema20_4h', 0)
        ema50 = features.get('ema50_4h', 0)
        pullback_pct = features.get('pullback_from_24h_high', 0)
        rsi_1h = features.get('rsi_1h', 50)
        rvol = features.get('rvol_15m', 0)

        min_rvol = float(os.getenv('MIN_RVOL_15M_BULL', 1.2))

        if ema20 <= ema50:
            return None

        if pullback_pct < 0.05 or pullback_pct > 0.10:  # 5-10% pullback
            return None

        if rsi_1h < 40 or rsi_1h > 70:
            return None

        if rvol < min_rvol:
            return None

        score = self._calculate_long_score(symbol, features, regime, alt_strength)

        if score < 0.7:
            return None

        return {
            'symbol': symbol,
            'direction': 'LONG',
            'engine': 'TREND_PULLBACK',
            'score': score,
            'entry_price': features.get('close'),
            'features': features,
            'perfect_storm': score > 0.85
        }

    def _try_range_expansion_long(
        self,
        symbol: str,
        features: Dict,
        regime: Regime,
        alt_strength: float
    ) -> Dict:
        """Try RANGE EXPANSION engine (SIDEWAYS only)"""
        # Check ATR expansion
        atr_now = features.get('atr_14_15m', 0)
        atr_yesterday = features.get('atr_14_15m_yesterday', 0)

        if atr_yesterday == 0:
            return None

        expansion_ratio = atr_now / atr_yesterday

        if expansion_ratio < 1.3:  # Need 30%+ ATR expansion
            return None

        # Check position in range
        price_pos = features.get('price_pos_24h', 0)
        if price_pos < 0.6 or price_pos > 0.9:
            return None

        # Check dominance edge (critical for sideways)
        edges = edge_detector.get_edge_signals(
            symbol, "LONG", regime.value, alt_strength
        )

        if not edges.dominance_edge_active:
            return None  # Need dominance confirmation in SIDEWAYS

        score = self._calculate_long_score(symbol, features, regime, alt_strength)

        if score < 0.7:
            return None

        return {
            'symbol': symbol,
            'direction': 'LONG',
            'engine': 'RANGE_EXPANSION',
            'score': score,
            'entry_price': features.get('close'),
            'features': features,
            'perfect_storm': score > 0.85
        }

    def _scan_for_shorts(
        self,
        universe: List[Dict],
        regime: Regime,
        regime_details: Dict
    ) -> List[Dict]:
        """Scan for short signals (BEAR only)"""
        signals = []
        alt_strength = regime_details.get('RS_alt_21', 0)

        for sym_data in universe:
            symbol = sym_data['symbol']

            state_machine = symbol_state_manager.get_or_create(symbol)
            if not state_machine.is_tradeable():
                continue

            features = self.feature_extractor.extract(symbol, sym_data)
            if not features:
                continue

            # Try short engines
            # 1) FAILED RALLY SHORT
            signal = self._try_failed_rally_short(symbol, features, regime, alt_strength)
            if signal:
                signals.append(signal)

            # 2) CLEAN BREAKDOWN SHORT
            if not signal:
                signal = self._try_breakdown_short(symbol, features, regime, alt_strength)
                if signal:
                    signals.append(signal)

        return signals

    def _try_failed_rally_short(
        self,
        symbol: str,
        features: Dict,
        regime: Regime,
        alt_strength: float
    ) -> Dict:
        """Try FAILED RALLY short engine"""
        # Check SHORT FILTER 5 (downtrend)
        ok, msg = entry_filters.check_short_filter_5_clean_4h_downtrend(features)
        if not ok:
            return None

        # Check rally stall + lower high
        rally_pct = features.get('rally_from_local_low', 0)
        rsi_1h = features.get('rsi_1h', 50)
        has_lower_high = features.get('has_lower_high', False)

        if rally_pct < 0.05 or rally_pct > 0.12:  # 5-12% rally
            return None

        if rsi_1h < 45 or rsi_1h > 60:  # Stall zone
            return None

        if not has_lower_high:
            return None

        # Check SHORT FILTER 6 (breakdown)
        ok, msg = entry_filters.check_short_filter_6_breakdown(features)
        if not ok:
            return None

        score = self._calculate_short_score(symbol, features, regime, alt_strength)

        if score < 0.65:  # Lower threshold for shorts
            return None

        return {
            'symbol': symbol,
            'direction': 'SHORT',
            'engine': 'FAILED_RALLY',
            'score': score,
            'entry_price': features.get('close'),
            'features': features,
            'perfect_storm': False  # Shorts don't use perfect storm
        }

    def _try_breakdown_short(
        self,
        symbol: str,
        features: Dict,
        regime: Regime,
        alt_strength: float
    ) -> Dict:
        """Try CLEAN BREAKDOWN short engine"""
        # Check filters
        ok, msg = entry_filters.check_short_filter_5_clean_4h_downtrend(features)
        if not ok:
            return None

        ok, msg = entry_filters.check_short_filter_6_breakdown(features)
        if not ok:
            return None

        # Check not capitulation yet
        ret_3d = features.get('return_3d', 0)
        rsi_1h = features.get('rsi_1h', 50)

        if ret_3d < -0.50:  # Already down 50%+
            return None

        if rsi_1h < 30:  # Oversold
            return None

        score = self._calculate_short_score(symbol, features, regime, alt_strength)

        if score < 0.65:
            return None

        return {
            'symbol': symbol,
            'direction': 'SHORT',
            'engine': 'BREAKDOWN',
            'score': score,
            'entry_price': features.get('close'),
            'features': features,
            'perfect_storm': False
        }

    def _calculate_long_score(
        self,
        symbol: str,
        features: Dict,
        regime: Regime,
        alt_strength: float
    ) -> float:
        """
        Calculate normalized long score [0, 1]

        Base score from features + edge bonuses
        """
        # Base score components
        trend_score = min(features.get('trend_ratio_4h', 1.0) - 1.0, 0.05) / 0.05  # 0-1
        rvol_score = min(features.get('rvol_15m', 0) / 3.0, 1.0)  # 0-1
        compression_score = 1.0 - min(features.get('atr_14_15m', 1) / features.get('atr_median_24h', 1), 1.0)
        momentum_score = min(max(features.get('return_24h', 0) / 0.20, 0), 1.0)  # 0-20% = 0-1

        base_score = (
            0.30 * trend_score +
            0.25 * rvol_score +
            0.25 * compression_score +
            0.20 * momentum_score
        )

        # Get edge bonuses
        edges = edge_detector.get_edge_signals(
            symbol, "LONG", regime.value, alt_strength
        )

        total_bonus = edges.total_score_bonus()

        final_score = min(base_score + total_bonus, 1.0)

        return final_score

    def _calculate_short_score(
        self,
        symbol: str,
        features: Dict,
        regime: Regime,
        alt_strength: float
    ) -> float:
        """
        Calculate normalized short score [0, 1]

        Different weighting for shorts
        """
        breakdown_strength = min(abs(features.get('breakdown_pct', 0)) / 0.05, 1.0)  # 0-1
        lower_high_quality = 1.0 if features.get('has_lower_high') else 0.0
        rvol_down = min(features.get('rvol_15m', 0) / 2.5, 1.0)
        trend_weakness = max(1.0 - features.get('trend_ratio_4h', 1.0), 0.0)

        base_score = (
            0.30 * breakdown_strength +
            0.25 * lower_high_quality +
            0.20 * rvol_down +
            0.15 * trend_weakness +
            0.10 * 0.5  # Placeholder for OB imbalance
        )

        # Get edge bonuses
        edges = edge_detector.get_edge_signals(
            symbol, "SHORT", regime.value, alt_strength
        )

        total_bonus = edges.funding_score_bonus + edges.rotation_score_bonus

        final_score = min(base_score + total_bonus, 1.0)

        return final_score
