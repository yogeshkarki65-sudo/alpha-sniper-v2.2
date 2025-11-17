"""
Enhanced Scanner with Alpha Sniper V2.2 Strategy Integration

This scanner uses:
- Regime detection (BTC + TOTAL3)
- Advanced feature calculation
- Normalized scoring with momentum bonuses
- Adaptive rolling median thresholds
"""

import requests
import time
import pandas as pd
from datetime import datetime, timedelta
from config.config import config
from database.models import db
from scanner.orderbook import get_orderbook_imbalance, get_spread_pct

# Import Alpha Sniper V2.2 components
from strategies.alpha_sniper import AlphaSniperStrategy
from indicators.regime import RegimeDetector
import json
from pathlib import Path


class EnhancedScanner:
    """Scanner with Alpha Sniper V2.2 integration"""

    def __init__(self):
        """Initialize enhanced scanner"""
        # Load strategy config
        config_path = Path('config_alpha_sniper.json')
        if config_path.exists():
            with open(config_path, 'r') as f:
                strategy_config = json.load(f)
            print("[scanner v2] Loaded Alpha Sniper config")
        else:
            # Use defaults
            strategy_config = self._get_default_config()
            print("[scanner v2] Using default Alpha Sniper config")

        # Initialize strategy components
        self.strategy = AlphaSniperStrategy(config=strategy_config)
        self.regime_detector = RegimeDetector()

        # Cache for regime data
        self.btc_cache = []
        self.total3_cache = []
        self.last_regime_update = None
        self.current_regime = None

        print("[scanner v2] ✅ Enhanced scanner initialized with Alpha Sniper V2.2")

    def _get_default_config(self):
        """Get default strategy configuration"""
        return {
            'z_bull_threshold': 0.5,
            'z_bear_threshold': -0.5,
            'rs_alt_threshold': 0.0,
            'risk_pct_bull': 0.004,
            'risk_pct_sideways': 0.0025,
            'risk_pct_bear': 0.0012,
            'max_portfolio_heat': 0.015,
            'max_daily_loss_pct': 0.02,
            'atr_sl_mult': 2.0,
            'tp1_mult': 2.0,
            'tp2_mult': 3.0,
            'trail_mult': 1.5,
            'tp1_exit_pct': 0.50,
            'tp2_exit_pct': 0.30,
            'cold_start_threshold': 0.60,
            'min_samples_adaptive': 200,
            'global_warmstart': True,
            'training_period_days': 30
        }

    def fetch_ohlcv_data(self, symbol, interval='15m', limit=500):
        """
        Fetch OHLCV data for a symbol (needed for feature calculation)

        Args:
            symbol: Trading pair
            interval: Timeframe (5m, 15m, 1h, etc.)
            limit: Number of candles

        Returns:
            DataFrame with OHLCV data
        """
        try:
            url = f"{config.MEXC_BASE_URL}/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }

            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            return df

        except Exception as e:
            print(f"[scanner v2] Error fetching OHLCV for {symbol}: {e}")
            return pd.DataFrame()

    def update_regime_data(self):
        """Update regime detection data (BTC and TOTAL3)"""
        try:
            # Update every 1 hour
            if (self.last_regime_update and
                (datetime.now() - self.last_regime_update).seconds < 3600):
                return True

            print("[scanner v2] Updating regime data...")

            # Fetch BTC data (30 days for regime calculation)
            btc_df = self.fetch_ohlcv_data('BTCUSDT', interval='1d', limit=180)

            if btc_df.empty:
                print("[scanner v2] ⚠️ Could not fetch BTC data")
                return False

            # For TOTAL3, we'll use a basket of major altcoins as proxy
            alt_symbols = ['ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
            alt_data = []

            for sym in alt_symbols:
                df = self.fetch_ohlcv_data(sym, interval='1d', limit=180)
                if not df.empty:
                    alt_data.append(df)
                time.sleep(0.2)

            if not alt_data:
                print("[scanner v2] ⚠️ Could not fetch altcoin data for TOTAL3 proxy")
                return False

            # Create TOTAL3 proxy (average of normalized altcoin prices)
            common_timestamps = set(btc_df['timestamp'])
            for df in alt_data:
                common_timestamps &= set(df['timestamp'])

            common_timestamps = sorted(common_timestamps)

            alt_prices = []
            for df in alt_data:
                df_aligned = df[df['timestamp'].isin(common_timestamps)].sort_values('timestamp')
                normalized = df_aligned['close'] / df_aligned['close'].iloc[0]
                alt_prices.append(normalized.values)

            avg_normalized = pd.Series(alt_prices).mean()

            total3_df = pd.DataFrame({
                'timestamp': common_timestamps,
                'open': avg_normalized,
                'high': avg_normalized,
                'low': avg_normalized,
                'close': avg_normalized,
                'volume': 0
            })

            # Store cache
            self.btc_cache = btc_df
            self.total3_cache = total3_df

            # Detect regime
            self.current_regime = self.regime_detector.get_current_regime(
                btc_df,
                total3_df
            )

            self.last_regime_update = datetime.now()

            print(
                f"[scanner v2] 📊 Current Regime: {self.current_regime['regime'].upper()} "
                f"(Z-score: {self.current_regime['z_ret']:.2f}, RS_alt: {self.current_regime['rs_alt']:.3f})"
            )

            return True

        except Exception as e:
            print(f"[scanner v2] Error updating regime data: {e}")
            return False

    def get_usdt_pairs(self):
        """
        Fetch USDT pairs from MEXC (same as original scanner)
        """
        try:
            url = f"{config.MEXC_BASE_URL}/api/v3/ticker/24hr"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            tickers = resp.json()
        except Exception as e:
            print(f"[scanner v2] Error fetching 24h tickers: {e}")
            return []

        # Filter USDT pairs
        usdt = []
        for t in tickers:
            symbol = t.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue

            try:
                quote_volume = float(t.get("quoteVolume", 0) or 0)
            except Exception:
                quote_volume = 0.0

            usdt.append((quote_volume, t))

        if not usdt:
            return []

        # Sort by volume and take top N
        usdt.sort(key=lambda x: x[0], reverse=True)
        TOP_N = 60
        top = usdt[:TOP_N]

        print(f"[scanner v2] Got {len(usdt)} USDT pairs, using top {len(top)} by volume")

        # Apply filters
        filtered = []
        for qvol, t in top:
            symbol = t.get("symbol")
            try:
                # Liquidity filter
                if qvol < config.MIN_LIQUIDITY_VOLUME_24H:
                    continue

                # Spread filter
                spread = get_spread_pct(symbol)
                if spread > 0.5:
                    continue

                filtered.append(t)
            except Exception as e:
                continue

            time.sleep(0.05)

        print(f"[scanner v2] After filters: {len(filtered)} liquid USDT pairs")
        return filtered

    def analyze_symbol(self, ticker):
        """
        Analyze symbol with Alpha Sniper V2.2 strategy

        Args:
            ticker: 24hr ticker data

        Returns:
            Signal dictionary or None
        """
        try:
            symbol = ticker['symbol']

            # Fetch OHLCV data (need history for features)
            ohlcv_data = self.fetch_ohlcv_data(symbol, interval='15m', limit=500)

            if ohlcv_data.empty or len(ohlcv_data) < 100:
                return None

            # Get orderbook imbalance
            if config.CHECK_ORDER_BOOK_IMBALANCE:
                ob_imbalance = get_orderbook_imbalance(symbol)
            else:
                ob_imbalance = None

            # Analyze with Alpha Sniper strategy
            signal = self.strategy.analyze_symbol(
                symbol=symbol,
                ohlcv_data=ohlcv_data,
                regime_info=self.current_regime,
                ob_imbalance=ob_imbalance
            )

            return signal

        except Exception as e:
            print(f"[scanner v2] Error analyzing {ticker.get('symbol')}: {e}")
            return None

    def run_scan(self):
        """Run enhanced scanner with Alpha Sniper V2.2"""
        print("🔍 Running Enhanced Scanner (Alpha Sniper V2.2)...")

        # Update regime data
        if not self.update_regime_data():
            print("[scanner v2] ⚠️ Regime update failed, using cached regime")
            if not self.current_regime:
                self.current_regime = {
                    'regime': 'sideways',
                    'z_ret': 0.0,
                    'rs_alt': 0.0
                }

        # Get tradable pairs
        pairs = self.get_usdt_pairs()
        print(f"[scanner v2] Scanning {len(pairs)} symbols...")

        if not pairs:
            print("[scanner v2] No pairs to scan")
            return 0

        signals_created = 0

        for ticker in pairs:
            signal = self.analyze_symbol(ticker)

            if signal and signal['signal']:
                # Store signal in database
                db.create_signal(
                    signal['symbol'],
                    signal['score'] * 100,  # Convert to 0-100 scale for compatibility
                    signal['features']['rvol'],
                    signal['features'].get('return_24h', 0),
                    signal['features'].get('trend_score', 0),
                    signal['features'].get('ob_score', 0),
                    signal['entry_price']
                )

                signals_created += 1

                print(
                    f"[scanner v2] ✅ SIGNAL: {signal['symbol']} | "
                    f"Score: {signal['score']:.3f} | "
                    f"Regime: {self.current_regime['regime'].upper()} | "
                    f"RVOL: {signal['features']['rvol']:.2f} | "
                    f"Threshold: {signal['threshold']:.3f}"
                )

            # Rate limiting
            time.sleep(0.1)

        print(f"[scanner v2] ✅ Created {signals_created} signals (Regime: {self.current_regime['regime'].upper()})")
        return signals_created


# Singleton instance
_scanner = None

def get_scanner():
    """Get or create scanner instance"""
    global _scanner
    if _scanner is None:
        _scanner = EnhancedScanner()
    return _scanner


def run_scanner():
    """Run enhanced scanner (backwards compatible)"""
    scanner = get_scanner()
    return scanner.run_scan()


if __name__ == "__main__":
    run_scanner()
