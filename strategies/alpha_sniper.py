"""
Alpha Sniper Strategy - Main Strategy Class

Complete implementation of the full quant strategy with:
- Regime detection
- Feature calculation
- Normalized scoring
- Adaptive thresholds
- Risk management
- Exit rules
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

from indicators.regime import RegimeDetector
from indicators.features import AdvancedFeatureCalculator
from .scoring import ScoringModel, AdaptiveThresholdManager
from .risk_model import VolatilityAdjustedRiskModel, ExitRulesManager

logger = logging.getLogger(__name__)


class AlphaSniperStrategy:
    """
    Main Alpha Sniper trading strategy.

    Combines all components:
    1. Regime detection (BTC + TOTAL3)
    2. Feature calculation (breakout, pullback, RVOL, etc.)
    3. Normalized scoring with momentum bonuses
    4. Adaptive rolling median thresholds
    5. ATR-based risk management
    6. Multi-level exit rules
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize Alpha Sniper strategy.

        Args:
            config: Configuration dictionary with strategy parameters
        """
        self.config = config or {}

        # Initialize components
        self.regime_detector = RegimeDetector(
            z_bull_threshold=self.config.get('z_bull_threshold', 0.5),
            z_bear_threshold=self.config.get('z_bear_threshold', -0.5),
            rs_alt_threshold=self.config.get('rs_alt_threshold', 0.0)
        )

        self.feature_calculator = AdvancedFeatureCalculator()

        self.scoring_model = ScoringModel()

        self.threshold_manager = AdaptiveThresholdManager(
            cold_start_threshold=self.config.get('cold_start_threshold', 0.60),
            min_samples_for_adaptive=self.config.get('min_samples_adaptive', 200),
            global_warmstart=self.config.get('global_warmstart', True),
            training_period_days=self.config.get('training_period_days', 30)
        )

        self.risk_model = VolatilityAdjustedRiskModel(
            risk_pct_bull=self.config.get('risk_pct_bull', 0.0040),
            risk_pct_sideways=self.config.get('risk_pct_sideways', 0.0025),
            risk_pct_bear=self.config.get('risk_pct_bear', 0.0012),
            max_portfolio_heat=self.config.get('max_portfolio_heat', 0.015),
            max_daily_loss_pct=self.config.get('max_daily_loss_pct', 0.02),
            atr_sl_mult=self.config.get('atr_sl_mult', 2.0)
        )

        self.exit_manager = ExitRulesManager(
            tp1_mult=self.config.get('tp1_mult', 2.0),
            tp2_mult=self.config.get('tp2_mult', 3.0),
            trail_mult=self.config.get('trail_mult', 1.5),
            tp1_exit_pct=self.config.get('tp1_exit_pct', 0.50),
            tp2_exit_pct=self.config.get('tp2_exit_pct', 0.30)
        )

        logger.info("AlphaSniperStrategy initialized with config: %s", self.config)

    def analyze_symbol(
        self,
        symbol: str,
        ohlcv_data: pd.DataFrame,
        regime_info: Dict,
        ob_imbalance: Optional[float] = None
    ) -> Dict:
        """
        Analyze a symbol and generate entry signal if conditions met.

        Args:
            symbol: Trading symbol
            ohlcv_data: OHLCV DataFrame for symbol
            regime_info: Regime information dictionary
            ob_imbalance: Orderbook imbalance (if available)

        Returns:
            Analysis results with signal information
        """
        if ohlcv_data.empty:
            return {'signal': False, 'reason': 'No data'}

        # Calculate all features
        df_with_features = self.feature_calculator.calculate_all_features(
            ohlcv_data,
            regime=regime_info['regime']
        )

        if df_with_features.empty:
            return {'signal': False, 'reason': 'Feature calculation failed'}

        # Get latest data point
        latest = df_with_features.iloc[-1]

        # Calculate orderbook score if available
        if ob_imbalance is not None:
            ob_score = self.feature_calculator.calculate_ob_score(ob_imbalance)
        else:
            ob_score = 0.5  # Neutral if not available

        # Add OB score to features
        latest_dict = latest.to_dict()
        latest_dict['ob_score'] = ob_score

        # Calculate final score
        score = self.scoring_model.calculate_score(
            features=pd.Series(latest_dict),
            regime=regime_info['regime'],
            regime_data=regime_info
        )

        # Update score history
        timestamp = latest['timestamp'] if 'timestamp' in latest_dict else pd.Timestamp.now()
        self.threshold_manager.update_score_history(symbol, score, timestamp)

        # Check if score meets adaptive threshold
        threshold = self.threshold_manager.get_threshold(symbol, timestamp)
        threshold_ok = score >= threshold

        # Get regime parameters
        regime_params = self.regime_detector.get_regime_parameters(regime_info['regime'])

        # Check all entry conditions
        entry_conditions = self._check_entry_conditions(
            latest_dict,
            regime_info,
            regime_params,
            ob_imbalance,
            threshold_ok
        )

        # Generate signal
        signal = all(entry_conditions.values())

        result = {
            'signal': signal,
            'symbol': symbol,
            'score': score,
            'threshold': threshold,
            'regime': regime_info['regime'],
            'conditions': entry_conditions,
            'features': {
                'trend_score': latest_dict.get('trend_score', 0),
                'breakout_score': latest_dict.get('breakout_score', 0),
                'rvol_score': latest_dict.get('rvol_score', 0),
                'pullback_score': latest_dict.get('pullback_score', 0),
                'ob_score': ob_score,
                'rvol': latest_dict.get('rvol', 0),
                'rsi': latest_dict.get('rsi_14', 0),
                'atr': latest_dict.get('atr_14', 0)
            },
            'entry_price': latest_dict.get('close', 0),
            'pullback_low': latest_dict.get('low', 0),
            'timestamp': timestamp
        }

        return result

    def _check_entry_conditions(
        self,
        features: Dict,
        regime_info: Dict,
        regime_params: Dict,
        ob_imbalance: Optional[float],
        threshold_ok: bool
    ) -> Dict[str, bool]:
        """
        Check all entry conditions.

        Returns:
            Dictionary of condition name -> bool
        """
        conditions = {}

        # 1. Regime check (allow bull/sideways, bear only if special conditions)
        regime = regime_info['regime']
        conditions['regime_ok'] = regime in ['bull', 'sideways'] or (
            regime == 'bear' and features.get('reclaim_valid', False)
        )

        # 2. Trend valid (if required by regime)
        if regime_params['trend_required']:
            conditions['trend_ok'] = features.get('trend_valid', False)
        else:
            conditions['trend_ok'] = True

        # 3. RVOL threshold
        rvol_threshold = regime_params['rvol_threshold']
        conditions['rvol_ok'] = features.get('rvol', 0) >= rvol_threshold

        # 4. Orderbook imbalance
        if ob_imbalance is not None:
            ob_threshold = regime_params['ob_imbalance_threshold']
            conditions['ob_ok'] = ob_imbalance >= ob_threshold
        else:
            conditions['ob_ok'] = True  # Skip if not available

        # 5. Pullback valid
        conditions['pullback_ok'] = features.get('pullback_valid', False)

        # 6. Reclaim confirmation
        conditions['reclaim_ok'] = features.get('reclaim_valid', False)

        # 7. Extension filter
        conditions['extension_ok'] = features.get('extension_ok', True)

        # 8. Exhaustion filter
        conditions['exhaustion_ok'] = features.get('exhaustion_ok', True)

        # 9. Adaptive threshold
        conditions['threshold_ok'] = threshold_ok

        return conditions

    def calculate_position_params(
        self,
        signal: Dict,
        equity: float,
        regime_info: Dict
    ) -> Dict:
        """
        Calculate position parameters (size, stops, targets).

        Args:
            signal: Signal dictionary from analyze_symbol
            equity: Current account equity
            regime_info: Regime information

        Returns:
            Dictionary with position parameters
        """
        entry_price = signal['entry_price']
        atr = signal['features']['atr']
        pullback_low = signal['pullback_low']
        regime = regime_info['regime']

        # Calculate position size
        position_size, stop_loss, risk_amount = self.risk_model.calculate_position_size(
            equity=equity,
            entry_price=entry_price,
            atr=atr,
            pullback_low=pullback_low,
            regime=regime
        )

        # Calculate exit levels
        exit_levels = self.exit_manager.calculate_exit_levels(
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            atr=atr
        )

        # Calculate risk percentage
        risk_pct = self.risk_model.get_risk_percentage(regime)

        return {
            'position_size': position_size,
            'entry_price': entry_price,
            'stop_loss': exit_levels['stop_loss'],
            'tp1': exit_levels['tp1'],
            'tp2': exit_levels['tp2'],
            'trailing_stop': exit_levels['trailing_stop'],
            'risk_amount': risk_amount,
            'risk_pct': risk_pct,
            'atr': atr
        }

    def check_exit_signal(
        self,
        position: Dict,
        current_price: float,
        current_atr: float
    ) -> Tuple[bool, str, float]:
        """
        Check if position should be exited.

        Args:
            position: Position dictionary
            current_price: Current market price
            current_atr: Current ATR

        Returns:
            Tuple of (should_exit, exit_type, exit_percentage)
        """
        exit_type, exit_pct = self.exit_manager.check_exit_conditions(
            position=position,
            current_price=current_price,
            current_atr=current_atr
        )

        should_exit = exit_type != 'none'

        return should_exit, exit_type, exit_pct

    def update_position_after_exit(
        self,
        position: Dict,
        exit_type: str,
        exit_percentage: float,
        exit_price: float
    ) -> Dict:
        """
        Update position after partial or full exit.

        Args:
            position: Position dictionary
            exit_type: Type of exit
            exit_percentage: Percentage of position closed
            exit_price: Exit price

        Returns:
            Updated position dictionary
        """
        return self.exit_manager.update_position_after_partial_exit(
            position=position,
            exit_type=exit_type,
            exit_percentage=exit_percentage,
            exit_price=exit_price
        )

    def get_strategy_state(self) -> Dict:
        """
        Get current strategy state and statistics.

        Returns:
            Dictionary with strategy state
        """
        return {
            'threshold_stats': self.threshold_manager.get_statistics(),
            'config': self.config
        }
