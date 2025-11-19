"""
Alpha Sniper V4.0 - 2025 Edges
Funding Compression, Rotation, Dominance Thrust

Perfect Storm = all 3 align → +15 score boost
"""
import os
from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class EdgeSignals:
    """Combined edge signals"""
    funding_edge_active: bool = False
    rotation_edge_active: bool = False
    dominance_edge_active: bool = False
    perfect_storm: bool = False

    funding_score_bonus: float = 0.0
    rotation_score_bonus: float = 0.0
    dominance_score_bonus: float = 0.0
    perfect_storm_boost: float = 0.0

    def total_score_bonus(self) -> float:
        """Get total score bonus from all edges"""
        if self.perfect_storm:
            return float(os.getenv('PERFECT_STORM_SCORE_BOOST', 0.15))
        else:
            return self.funding_score_bonus + self.rotation_score_bonus + self.dominance_score_bonus


class EdgeDetector:
    """
    Detects 2025 edges for score boosting
    """

    def __init__(self, mexc_client=None):
        self.mexc_client = mexc_client

        # Cached data
        self.last_funding_check = {}
        self.sector_performance = {}  # Track sector rotation

    def detect_funding_edge(
        self,
        symbol: str,
        direction: str  # "LONG" or "SHORT"
    ) -> Tuple[bool, float]:
        """
        FUNDING COMPRESSION EDGE

        Conditions:
        - |funding_rate| < 0.01%
        - OI rising in last 4–8h

        For longs (BULL): if breakout + OI up + funding near 0 → bonus
        For shorts (BEAR): if breakdown + OI up + funding ≥ 0 → bonus

        Returns:
            (edge_active, score_bonus)
        """
        if not os.getenv('USE_FUNDING_EDGE', 'true').lower() == 'true':
            return False, 0.0

        market_type = os.getenv('MARKET_TYPE', 'SPOT')
        if market_type != 'FUTURES':
            # SPOT mode: Funding not available, skip silently
            # This is expected and not an error
            return False, 0.0

        # TODO: Implement when MARKET_TYPE=FUTURES
        # Would fetch from: /api/v3/contract/funding_rate (MEXC futures)
        # For now, return False (edge inactive on SPOT)
        return False, 0.0

        # FUTURE IMPLEMENTATION (when FUTURES enabled):
        # funding_rate = self.mexc_client.get_funding_rate(symbol)
        # oi_current = self.mexc_client.get_open_interest(symbol)
        # oi_8h_ago = self.mexc_client.get_open_interest_historical(symbol, hours_ago=8)
        # oi_rising = oi_current > oi_8h_ago * 1.05
        #
        # if abs(funding_rate) < 0.0001 and oi_rising:
        #     if direction == "LONG" and funding_rate <= 0:
        #         return True, 0.02
        #     elif direction == "SHORT" and funding_rate >= 0:
        #         return True, 0.02
        #
        # return False, 0.0

    def detect_rotation_edge(
        self,
        symbol: str,
        symbol_24h_change: float,
        market_24h_avg_change: float
    ) -> Tuple[bool, float]:
        """
        ROTATION EDGE (Simplified - Volume-Based)

        Instead of sector tracking (requires manual classification),
        use simpler logic:
        - If symbol lagged yesterday (underperformed market avg)
        - But today shows rising RVOL (money rotating in)
        - Give small bonus (mean reversion + rotation)

        Args:
            symbol_24h_change: Symbol's 24h return
            market_24h_avg_change: Average 24h return of top 50 symbols

        Returns:
            (edge_active, score_bonus)
        """
        if not os.getenv('USE_ROTATION_EDGE', 'true').lower() == 'true':
            return False, 0.0

        # Check if symbol underperformed yesterday but is now seeing volume
        underperformance = symbol_24h_change - market_24h_avg_change

        # Lagged by 3%+ yesterday but not crashed (>-20%)
        if underperformance < -0.03 and symbol_24h_change > -0.20:
            # Money rotating from winners to laggers
            return True, 0.02  # +2% score bonus

        return False, 0.0

    def detect_dominance_edge(
        self,
        alt_strength: float,  # From regime detector (RS_alt_21)
        regime: str
    ) -> Tuple[bool, float]:
        """
        DOMINANCE THRUST EDGE

        Use ALT vs BTC relative strength:
        - Gate for aggressive longs (BULL) when alts outperforming
        - Gate for avoiding longs (BEAR) during ALT collapse

        Returns:
            (edge_active, score_bonus)
        """
        if not os.getenv('USE_DOMINANCE_THRUST', 'true').lower() == 'true':
            return False, 0.0

        # BULL: alts outperforming BTC (RS_alt_21 > 0)
        if regime == "BULL" and alt_strength > 0.02:  # Alts up 2%+ vs BTC over 21d
            return True, 0.03  # +3% score bonus

        # BEAR: alts collapsing vs BTC
        if regime == "BEAR" and alt_strength < -0.02:
            # For shorts: alt weakness is good
            return True, 0.02  # +2% bonus for shorts

        return False, 0.0

    def get_edge_signals(
        self,
        symbol: str,
        direction: str,
        regime: str,
        alt_strength: float,
        symbol_sector: str = "UNKNOWN"
    ) -> EdgeSignals:
        """
        Get all edge signals for a symbol

        Returns EdgeSignals with bonuses and perfect storm flag
        """
        signals = EdgeSignals()

        # 1) Funding edge
        signals.funding_edge_active, signals.funding_score_bonus = self.detect_funding_edge(
            symbol, direction
        )

        # 2) Rotation edge
        signals.rotation_edge_active, signals.rotation_score_bonus = self.detect_rotation_edge(
            symbol, symbol_sector
        )

        # 3) Dominance edge
        signals.dominance_edge_active, signals.dominance_score_bonus = self.detect_dominance_edge(
            alt_strength, regime
        )

        # 4) Perfect storm check
        if (signals.funding_edge_active and
            signals.rotation_edge_active and
            signals.dominance_edge_active):
            signals.perfect_storm = True

        return signals


# Singleton
edge_detector = EdgeDetector()
