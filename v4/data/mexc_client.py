"""
MEXC API Client for Alpha Sniper V4.0

Handles all communication with MEXC exchange API with:
- Rate limiting
- Error handling
- Data caching
- Retry logic

Ported from V3, compatible with V4 execution engine
"""
import requests
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
from collections import defaultdict


class MEXCClient:
    """
    Robust MEXC API client with rate limiting and caching
    """

    BASE_URL = "https://api.mexc.com"

    def __init__(self, cache_ttl: int = 60):
        """
        Args:
            cache_ttl: Cache time-to-live in seconds
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AlphaSniperV3.2',
        })

        # Rate limiting
        self.last_request_time = defaultdict(float)
        self.min_request_interval = 0.1  # 100ms between requests

        # Caching
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_ttl = cache_ttl

    def _rate_limit(self, endpoint: str):
        """Enforce rate limiting"""
        now = time.time()
        time_since_last = now - self.last_request_time[endpoint]

        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)

        self.last_request_time[endpoint] = time.time()

    def _get_cached(self, key: str) -> Optional[any]:
        """Get from cache if still valid"""
        if key not in self.cache:
            return None

        age = time.time() - self.cache_timestamps[key]
        if age > self.cache_ttl:
            del self.cache[key]
            del self.cache_timestamps[key]
            return None

        return self.cache[key]

    def _set_cache(self, key: str, value: any):
        """Set cache value"""
        self.cache[key] = value
        self.cache_timestamps[key] = time.time()

    def _request(self, endpoint: str, params: Optional[Dict] = None, max_retries: int = 3) -> Optional[Dict]:
        """
        Make API request with retries and error handling

        Args:
            endpoint: API endpoint
            params: Query parameters
            max_retries: Maximum retry attempts

        Returns:
            JSON response or None on failure
        """
        url = f"{self.BASE_URL}{endpoint}"

        for attempt in range(max_retries):
            try:
                self._rate_limit(endpoint)

                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()

                return response.json()

            except requests.exceptions.Timeout:
                print(f"[MEXC] Timeout on {endpoint} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit
                    print(f"[MEXC] Rate limited, backing off...")
                    time.sleep(5)
                    continue
                else:
                    print(f"[MEXC] HTTP error {e.response.status_code}: {e}")
                    return None

            except Exception as e:
                print(f"[MEXC] Request error: {e}")
                return None

        print(f"[MEXC] Failed after {max_retries} attempts: {endpoint}")
        return None

    def get_24h_tickers(self) -> List[Dict]:
        """
        Get 24h ticker data for all symbols

        Returns list of ticker dicts with keys:
        - symbol
        - lastPrice
        - priceChangePercent
        - volume
        - quoteVolume
        - highPrice
        - lowPrice
        """
        cache_key = "24h_tickers"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = self._request("/api/v3/ticker/24hr")

        if data is None:
            return []

        # Filter valid tickers
        tickers = []
        for ticker in data:
            if not isinstance(ticker, dict):
                continue

            # Ensure required fields exist
            required_fields = ['symbol', 'lastPrice', 'volume', 'quoteVolume']
            if all(field in ticker for field in required_fields):
                tickers.append(ticker)

        self._set_cache(cache_key, tickers)
        return tickers

    def get_orderbook(self, symbol: str, depth: int = 10) -> Optional[Dict]:
        """
        Get orderbook for symbol

        Returns:
        {
            'bids': [(price, qty), ...],
            'asks': [(price, qty), ...]
        }
        """
        cache_key = f"orderbook_{symbol}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        params = {'symbol': symbol, 'limit': depth}
        data = self._request("/api/v3/depth", params=params)

        if data is None:
            return None

        try:
            orderbook = {
                'bids': [(float(p), float(q)) for p, q in data.get('bids', [])],
                'asks': [(float(p), float(q)) for p, q in data.get('asks', [])]
            }

            self._set_cache(cache_key, orderbook)
            return orderbook

        except Exception as e:
            print(f"[MEXC] Error parsing orderbook for {symbol}: {e}")
            return None

    def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Get OHLCV kline data

        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            interval: 1m, 5m, 15m, 1h, 4h, 1d
            limit: Number of bars (max 1000)

        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': min(limit, 1000)
        }

        data = self._request("/api/v3/klines", params=params)

        if data is None or len(data) == 0:
            return None

        try:
            # MEXC klines format: Handle variable column counts (8 or 11 columns)
            num_cols = len(data[0]) if len(data) > 0 else 0

            if num_cols == 8:
                # Format: [timestamp, open, high, low, close, volume, close_time, quote_volume]
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume'
                ])
            elif num_cols >= 11:
                # Format: [timestamp, open, high, low, close, volume, close_time, quote_volume, trades, ...]
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote'
                ])
            else:
                print(f"[MEXC] Unexpected klines format: {num_cols} columns")
                return None

            # Convert types
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df.set_index('timestamp', inplace=True)

            return df

        except Exception as e:
            print(f"[MEXC] Error parsing klines for {symbol}: {e}")
            return None

    def get_spread_pct(self, symbol: str) -> Optional[float]:
        """
        Calculate spread percentage from orderbook

        spread_pct = (ask - bid) / mid * 100
        """
        orderbook = self.get_orderbook(symbol, depth=1)

        if orderbook is None:
            return None

        try:
            if len(orderbook['bids']) == 0 or len(orderbook['asks']) == 0:
                return None

            best_bid = orderbook['bids'][0][0]
            best_ask = orderbook['asks'][0][0]

            mid = (best_bid + best_ask) / 2
            spread = best_ask - best_bid

            spread_pct = (spread / mid) * 100

            return spread_pct

        except Exception as e:
            print(f"[MEXC] Error calculating spread for {symbol}: {e}")
            return None

    def get_orderbook_imbalance(self, symbol: str, depth: int = 5) -> Optional[float]:
        """
        Calculate orderbook imbalance (bid/ask ratio)

        Uses top N levels weighted by distance from mid

        Returns:
            > 1.0: More buy pressure
            < 1.0: More sell pressure
        """
        orderbook = self.get_orderbook(symbol, depth=depth)

        if orderbook is None:
            return None

        try:
            if len(orderbook['bids']) == 0 or len(orderbook['asks']) == 0:
                return 1.0

            # Calculate weighted depth within 0.2% of mid
            best_bid = orderbook['bids'][0][0]
            best_ask = orderbook['asks'][0][0]
            mid = (best_bid + best_ask) / 2

            threshold = 0.002  # 0.2%

            bid_depth = sum(
                qty for price, qty in orderbook['bids']
                if price >= mid * (1 - threshold)
            )

            ask_depth = sum(
                qty * price for price, qty in orderbook['asks']
                if price <= mid * (1 + threshold)
            )

            if ask_depth == 0:
                return 2.0  # Cap at 2x

            imbalance = bid_depth / ask_depth
            return min(imbalance, 3.0)  # Cap at 3x

        except Exception as e:
            print(f"[MEXC] Error calculating OB imbalance for {symbol}: {e}")
            return 1.0

    def get_exchange_info(self) -> Optional[Dict]:
        """
        Get exchange information (trading pairs, status, etc.)
        """
        cache_key = "exchange_info"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = self._request("/api/v3/exchangeInfo")

        if data is not None:
            self._set_cache(cache_key, data)

        return data


# Singleton instance
mexc_client = MEXCClient(cache_ttl=60)
