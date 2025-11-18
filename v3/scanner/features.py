"""
Feature Extraction for Alpha Sniper V3.2

Computes all features needed for scanner scoring:
- RVOL (relative volume)
- Trend (EMA ratios, position in range)
- Compression (ATR compression ratio)
- Orderbook imbalance
- Momentum (recent returns, RSI rank)
- Exhaustion signals
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime

from v3.utils.indicators import (
    ema, atr, compute_rvol, position_in_range,
    detect_compression, percentile_rank
)
from v3.data.mexc_client import mexc_client


class FeatureExtractor:
    """
    Extracts trading features from market data
    """

    def __init__(self):
        """Initialize feature extractor"""
        pass

    def extract_features(
        self,
        symbol: str,
        ticker_data: Dict,
        bars_15m: Optional[pd.DataFrame] = None,
        bars_4h: Optional[pd.DataFrame] = None,
        fetch_orderbook: bool = True
    ) -> Optional[Dict]:
        """
        Extract all features for a symbol

        Args:
            symbol: Trading symbol
            ticker_data: 24h ticker data dict
            bars_15m: 15m OHLCV bars (optional, will fetch if None)
            bars_4h: 4h OHLCV bars (optional, will fetch if None)
            fetch_orderbook: Whether to fetch orderbook data

        Returns:
            Dict of features or None if insufficient data
        """
        try:
            # Extract from ticker
            last_price = float(ticker_data.get('lastPrice', 0))
            high_24h = float(ticker_data.get('highPrice', 0))
            low_24h = float(ticker_data.get('lowPrice', 0))
            volume_24h = float(ticker_data.get('volume', 0))
            quote_volume_24h = float(ticker_data.get('quoteVolume', 0))
            price_change_pct = float(ticker_data.get('priceChangePercent', 0))

            if last_price == 0 or high_24h == 0:
                return None

            # Fetch bars if not provided
            if bars_15m is None:
                bars_15m = mexc_client.get_klines(symbol, interval="15m", limit=100)
                if bars_15m is None or len(bars_15m) < 20:
                    return None

            if bars_4h is None:
                bars_4h = mexc_client.get_klines(symbol, interval="4h", limit=50)
                if bars_4h is None or len(bars_4h) < 20:
                    return None

            # Initialize features dict
            features = {
                'symbol': symbol,
                'timestamp': datetime.now(),
                'last_price': last_price,
                'high_24h': high_24h,
                'low_24h': low_24h,
            }

            # 1. TREND FEATURES
            trend_features = self._compute_trend_features(
                last_price, bars_4h, high_24h, low_24h
            )
            features.update(trend_features)

            # 2. VOLUME FEATURES
            volume_features = self._compute_volume_features(
                bars_15m, quote_volume_24h
            )
            features.update(volume_features)

            # 3. VOLATILITY/COMPRESSION FEATURES
            volatility_features = self._compute_volatility_features(
                bars_15m
            )
            features.update(volatility_features)

            # 4. MOMENTUM FEATURES
            momentum_features = self._compute_momentum_features(
                bars_15m, bars_4h, price_change_pct
            )
            features.update(momentum_features)

            # 5. ORDERBOOK FEATURES (optional)
            if fetch_orderbook:
                ob_features = self._compute_orderbook_features(symbol)
                features.update(ob_features)
            else:
                features['ob_imbalance'] = 1.0
                features['ob_score'] = 0.5

            # 6. EXHAUSTION CHECKS
            exhaustion_features = self._compute_exhaustion_features(
                bars_15m, bars_4h
            )
            features.update(exhaustion_features)

            return features

        except Exception as e:
            print(f"[Features] Error extracting features for {symbol}: {e}")
            return None

    def _compute_trend_features(
        self,
        current_price: float,
        bars_4h: pd.DataFrame,
        high_24h: float,
        low_24h: float
    ) -> Dict:
        """Compute trend-based features"""
        try:
            # EMA 20 and 50 on 4h
            ema_20_4h = ema(bars_4h['close'], 20).iloc[-1]
            ema_50_4h = ema(bars_4h['close'], 50).iloc[-1]

            # Trend ratio
            trend_ratio = ema_20_4h / ema_50_4h if ema_50_4h > 0 else 1.0

            # Trend score (normalized)
            # > 1.0 = uptrend, < 1.0 = downtrend
            # Map 0.95-1.05 to 0-1 range
            trend_score = np.clip((trend_ratio - 0.95) / 0.10, 0.0, 1.0)

            # Position in 24h range
            pos_in_range = position_in_range(current_price, high_24h, low_24h)

            # Price vs EMA20
            price_vs_ema20 = (current_price / ema_20_4h - 1) * 100 if ema_20_4h > 0 else 0

            return {
                'ema_20_4h': ema_20_4h,
                'ema_50_4h': ema_50_4h,
                'trend_ratio': trend_ratio,
                'trend_score': trend_score,
                'position_in_range': pos_in_range,
                'price_vs_ema20_pct': price_vs_ema20
            }

        except Exception as e:
            print(f"[Features] Trend feature error: {e}")
            return {
                'ema_20_4h': 0, 'ema_50_4h': 0, 'trend_ratio': 1.0,
                'trend_score': 0.5, 'position_in_range': 0.5, 'price_vs_ema20_pct': 0
            }

    def _compute_volume_features(
        self,
        bars_15m: pd.DataFrame,
        quote_volume_24h: float
    ) -> Dict:
        """Compute volume-based features"""
        try:
            # RVOL on 15m (last 96 bars = 24h)
            rvol_15m = compute_rvol(bars_15m['volume'], window=96).iloc[-1]

            # RVOL score (normalize 1.0-5.0 to 0-1)
            rvol_score = np.clip((rvol_15m - 1.0) / 4.0, 0.0, 1.0)

            # Recent volume surge (last 4 bars vs previous 20)
            recent_vol = bars_15m['volume'].tail(4).mean()
            prev_vol = bars_15m['volume'].tail(24).head(20).mean()
            vol_surge = recent_vol / prev_vol if prev_vol > 0 else 1.0

            return {
                'rvol_15m': rvol_15m,
                'rvol_score': rvol_score,
                'vol_surge': vol_surge,
                'quote_volume_24h': quote_volume_24h
            }

        except Exception as e:
            print(f"[Features] Volume feature error: {e}")
            return {
                'rvol_15m': 1.0, 'rvol_score': 0.0, 'vol_surge': 1.0,
                'quote_volume_24h': 0
            }

    def _compute_volatility_features(
        self,
        bars_15m: pd.DataFrame
    ) -> Dict:
        """Compute volatility/compression features"""
        try:
            # ATR 14 on 15m
            atr_14 = atr(bars_15m['high'], bars_15m['low'], bars_15m['close'], 14).iloc[-1]

            # ATR median over last 96 bars (24h)
            atr_median_24h = atr(
                bars_15m['high'], bars_15m['low'], bars_15m['close'], 14
            ).tail(96).median()

            # Compression ratio
            compression = detect_compression(atr_14, atr_median_24h)

            # Compression score (< 0.8 = compressed = high score)
            compression_score = np.clip(1.0 - compression, 0.0, 1.0)

            # ATR as % of price
            last_close = bars_15m['close'].iloc[-1]
            atr_pct = (atr_14 / last_close * 100) if last_close > 0 else 0

            return {
                'atr_14': atr_14,
                'atr_median_24h': atr_median_24h,
                'compression_ratio': compression,
                'compression_score': compression_score,
                'atr_pct': atr_pct
            }

        except Exception as e:
            print(f"[Features] Volatility feature error: {e}")
            return {
                'atr_14': 0, 'atr_median_24h': 0, 'compression_ratio': 1.0,
                'compression_score': 0.0, 'atr_pct': 0
            }

    def _compute_momentum_features(
        self,
        bars_15m: pd.DataFrame,
        bars_4h: pd.DataFrame,
        price_change_24h_pct: float
    ) -> Dict:
        """Compute momentum features"""
        try:
            # Recent returns
            ret_1h = (bars_15m['close'].iloc[-1] / bars_15m['close'].iloc[-5] - 1) * 100
            ret_4h = (bars_15m['close'].iloc[-1] / bars_15m['close'].iloc[-17] - 1) * 100

            # 3-day change (from 4h bars)
            if len(bars_4h) >= 18:  # 18 * 4h = 72h = 3 days
                ret_3d = (bars_4h['close'].iloc[-1] / bars_4h['close'].iloc[-18] - 1) * 100
            else:
                ret_3d = price_change_24h_pct

            # Momentum score (positive = good)
            momentum_score = np.clip(price_change_24h_pct / 50.0, -1.0, 1.0) * 0.5 + 0.5

            return {
                'ret_1h': ret_1h,
                'ret_4h': ret_4h,
                'ret_24h': price_change_24h_pct,
                'ret_3d': ret_3d,
                'momentum_score': momentum_score
            }

        except Exception as e:
            print(f"[Features] Momentum feature error: {e}")
            return {
                'ret_1h': 0, 'ret_4h': 0, 'ret_24h': 0, 'ret_3d': 0,
                'momentum_score': 0.5
            }

    def _compute_orderbook_features(self, symbol: str) -> Dict:
        """Compute orderbook-based features"""
        try:
            # Get orderbook imbalance
            ob_imbalance = mexc_client.get_orderbook_imbalance(symbol, depth=5)

            if ob_imbalance is None:
                return {'ob_imbalance': 1.0, 'ob_score': 0.5}

            # OB score (normalize 1.0-2.5 to 0-1)
            # > 1.5 = bid pressure (good for longs)
            ob_score = np.clip((ob_imbalance - 1.0) / 1.5, 0.0, 1.0)

            return {
                'ob_imbalance': ob_imbalance,
                'ob_score': ob_score
            }

        except Exception as e:
            print(f"[Features] OB feature error: {e}")
            return {'ob_imbalance': 1.0, 'ob_score': 0.5}

    def _compute_exhaustion_features(
        self,
        bars_15m: pd.DataFrame,
        bars_4h: pd.DataFrame
    ) -> Dict:
        """Compute exhaustion/extension features"""
        try:
            # Check for blowoff top patterns
            # Large move + expanding range = exhaustion

            # 3-day change
            if len(bars_4h) >= 18:
                ret_3d = (bars_4h['close'].iloc[-1] / bars_4h['close'].iloc[-18] - 1) * 100
            else:
                ret_3d = 0

            # Range factor (current range vs ATR)
            current_high = bars_15m['high'].tail(1).iloc[0]
            current_low = bars_15m['low'].tail(1).iloc[0]
            atr_14 = atr(bars_15m['high'], bars_15m['low'], bars_15m['close'], 14).iloc[-1]

            range_factor = (current_high - current_low) / atr_14 if atr_14 > 0 else 1.0

            # Exhaustion check (from spec)
            is_exhausted = (ret_3d > 50.0 and range_factor > 2.5)

            return {
                'range_factor': range_factor,
                'is_exhausted': is_exhausted
            }

        except Exception as e:
            print(f"[Features] Exhaustion feature error: {e}")
            return {'range_factor': 1.0, 'is_exhausted': False}


# Singleton instance
feature_extractor = FeatureExtractor()
