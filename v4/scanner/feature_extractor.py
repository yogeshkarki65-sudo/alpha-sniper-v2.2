"""
Alpha Sniper V4.0 - Feature Extractor
Extracts all features needed for V4 filters and scoring

Ported and adapted from V3
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime


class FeatureExtractor:
    """
    Extract trading features for V4 scanner

    Features extracted:
    - Trend: trend_ratio_4h, ema20_4h, ema50_4h
    - Volume: rvol_15m
    - Volatility: atr_14_15m, atr_median_24h, atr_compression
    - Price structure: high_24h, low_24h, close, price_pos_24h
    - Momentum: return_1h, return_4h, return_24h, return_3d
    - RSI: rsi_1h
    - Pattern detection: higher_lows_recent, has_lower_high
    """

    def __init__(self, mexc_client):
        """
        Args:
            mexc_client: MEXC API client for fetching OHLCV data
        """
        self.mexc_client = mexc_client

    def extract(self, symbol: str, ticker_data: Dict) -> Optional[Dict]:
        """
        Extract all features for a symbol

        Args:
            symbol: Trading pair (e.g., "BNBUSDT")
            ticker_data: 24h ticker data from universe manager

        Returns:
            Dict of features or None if extraction fails
        """
        try:
            # Fetch OHLCV data
            # 15m bars (last 200 bars = ~50 hours)
            df_15m = self.mexc_client.get_klines(symbol, interval='15m', limit=200)
            if df_15m is None or len(df_15m) < 100:
                return None

            # 1h bars (last 100 bars = ~4 days)
            df_1h = self.mexc_client.get_klines(symbol, interval='1h', limit=100)
            if df_1h is None or len(df_1h) < 50:
                return None

            # 4h bars (last 60 bars = 10 days)
            df_4h = self.mexc_client.get_klines(symbol, interval='4h', limit=60)
            if df_4h is None or len(df_4h) < 30:
                return None

            features = {}

            # Current price
            features['close'] = float(df_15m['close'].iloc[-1])
            features['symbol'] = symbol

            # === TREND FEATURES (4h) ===
            df_4h['ema20'] = df_4h['close'].ewm(span=20, adjust=False).mean()
            df_4h['ema50'] = df_4h['close'].ewm(span=50, adjust=False).mean()

            features['ema20_4h'] = float(df_4h['ema20'].iloc[-1])
            features['ema50_4h'] = float(df_4h['ema50'].iloc[-1])
            features['trend_ratio_4h'] = features['close'] / features['ema50_4h']

            # === VOLUME FEATURES (15m) ===
            median_vol_15m = df_15m['volume'].rolling(window=96).median().iloc[-1]  # 24h median
            current_vol_15m = df_15m['volume'].iloc[-1]
            features['rvol_15m'] = current_vol_15m / median_vol_15m if median_vol_15m > 0 else 0

            # === VOLATILITY FEATURES (15m) ===
            df_15m['high_low_range'] = df_15m['high'] - df_15m['low']
            df_15m['tr'] = df_15m[['high_low_range',
                                    (df_15m['high'] - df_15m['close'].shift()).abs(),
                                    (df_15m['low'] - df_15m['close'].shift()).abs()]].max(axis=1)

            df_15m['atr_14'] = df_15m['tr'].rolling(window=14).mean()

            features['atr_14_15m'] = float(df_15m['atr_14'].iloc[-1])
            features['atr_median_24h'] = float(df_15m['atr_14'].rolling(window=96).median().iloc[-1])

            # ATR compression ratio
            if features['atr_median_24h'] > 0:
                features['atr_compression'] = features['atr_14_15m'] / features['atr_median_24h']
            else:
                features['atr_compression'] = 1.0

            # === PRICE STRUCTURE (24h) ===
            # Last 96 bars = 24h of 15m data
            high_24h = float(df_15m['high'].iloc[-96:].max())
            low_24h = float(df_15m['low'].iloc[-96:].min())

            features['high_24h'] = high_24h
            features['low_24h'] = low_24h

            # Price position in 24h range
            if high_24h > low_24h:
                features['price_pos_24h'] = (features['close'] - low_24h) / (high_24h - low_24h)
            else:
                features['price_pos_24h'] = 0.5

            # === MOMENTUM FEATURES ===
            # 1h return
            if len(df_1h) >= 2:
                features['return_1h'] = (df_1h['close'].iloc[-1] / df_1h['close'].iloc[-2]) - 1.0
            else:
                features['return_1h'] = 0.0

            # 4h return
            if len(df_4h) >= 2:
                features['return_4h'] = (df_4h['close'].iloc[-1] / df_4h['close'].iloc[-2]) - 1.0
            else:
                features['return_4h'] = 0.0

            # 24h return
            if len(df_1h) >= 24:
                features['return_24h'] = (df_1h['close'].iloc[-1] / df_1h['close'].iloc[-24]) - 1.0
            else:
                features['return_24h'] = 0.0

            # 3d return (72h)
            if len(df_1h) >= 72:
                features['return_3d'] = (df_1h['close'].iloc[-1] / df_1h['close'].iloc[-72]) - 1.0
            else:
                features['return_3d'] = 0.0

            # === RSI (1h) ===
            features['rsi_1h'] = self._calculate_rsi(df_1h['close'], period=14)

            # === PATTERN DETECTION ===
            # Higher lows in last 3-4 bars (15m)
            recent_lows = df_15m['low'].iloc[-4:].values
            features['higher_lows_recent'] = all(recent_lows[i] < recent_lows[i+1] for i in range(len(recent_lows)-1))

            # Lower high pattern (for shorts)
            # Check if recent high is lower than previous swing high
            highs_24h = df_15m['high'].iloc[-96:].values
            recent_high = highs_24h[-12:].max()  # Last 3h
            prev_high = highs_24h[-96:-12].max()  # Previous 21h
            features['has_lower_high'] = recent_high < prev_high * 0.98  # 2% lower

            # === RANGE FEATURES ===
            # Max candle range in last 6 bars (for coil filter)
            ranges_6bars = (df_15m['high'].iloc[-6:] - df_15m['low'].iloc[-6:]).values
            features['max_range_6bars'] = float(ranges_6bars.max())

            # Support/resistance levels for shorts
            features['support_low_24_48h'] = float(df_15m['low'].iloc[-192:-96].min())  # 24-48h ago lows

            # Pullback from 24h high
            features['pullback_from_24h_high'] = (high_24h - features['close']) / high_24h if high_24h > 0 else 0

            # Rally from local low (for shorts)
            local_low = df_15m['low'].iloc[-96:-24].min()  # 6-24h ago low
            features['rally_from_local_low'] = (features['close'] - local_low) / local_low if local_low > 0 else 0

            # Breakdown percentage (for shorts)
            features['breakdown_pct'] = (features['support_low_24_48h'] - features['close']) / features['support_low_24_48h'] if features['support_low_24_48h'] > 0 else 0

            # ATR yesterday (for range expansion engine)
            if len(df_15m) >= 96:
                atr_yesterday = df_15m['atr_14'].iloc[-96]
                features['atr_14_15m_yesterday'] = float(atr_yesterday) if not pd.isna(atr_yesterday) else features['atr_14_15m']
            else:
                features['atr_14_15m_yesterday'] = features['atr_14_15m']

            return features

        except Exception as e:
            print(f"[Features] Error extracting for {symbol}: {e}")
            return None

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        except:
            return 50.0


# Singleton instance (initialized with mexc_client in main)
feature_extractor = None
