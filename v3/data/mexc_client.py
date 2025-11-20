#!/usr/bin/env python3
"""
MEXC API Client

BUG FIX: Added get_ticker_24h() method for status reporter (BUG A)
"""

import requests
import time
from typing import Optional, Dict, List


class MexcClient:
    """Client for interacting with MEXC API."""

    def __init__(self, base_url: str = "https://api.mexc.com"):
        self.base_url = base_url
        self.session = requests.Session()

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make HTTP request to MEXC API.

        Returns:
            Response data as dict, or None on failure
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[MexcClient] Request failed: {e}")
            return None

    def get_ticker_24h(self, symbol: str) -> Optional[Dict]:
        """
        Get 24h ticker data for a single symbol.

        BUG FIX (BUG A): Added for status reporter to fetch live prices.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")

        Returns:
            Ticker dict with lastPrice, priceChangePercent, volume, etc.
            Returns None on failure.
        """
        params = {'symbol': symbol}
        data = self._request("/api/v3/ticker/24hr", params=params)

        if data is None:
            return None

        # MEXC returns single dict for single symbol query
        if isinstance(data, dict):
            return data

        # Sometimes returns list with single element
        if isinstance(data, list) and len(data) > 0:
            return data[0]

        return None

    def get_all_tickers(self) -> Optional[List[Dict]]:
        """
        Get 24h ticker data for all symbols.

        Returns:
            List of ticker dicts
        """
        data = self._request("/api/v3/ticker/24hr")

        if data is None:
            return None

        # Ensure it's a list
        if isinstance(data, list):
            return data

        return [data] if isinstance(data, dict) else None

    def get_klines(
        self,
        symbol: str,
        interval: str = "15m",
        limit: int = 100
    ) -> Optional[List[Dict]]:
        """
        Get OHLCV kline/candlestick data.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles to fetch

        Returns:
            List of OHLCV dicts with keys: timestamp, open, high, low, close, volume
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }

        data = self._request("/api/v3/klines", params=params)

        if data is None or not isinstance(data, list):
            return None

        # Parse MEXC kline format
        klines = []
        for k in data:
            if len(k) < 6:
                continue

            klines.append({
                'timestamp': int(k[0]),
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            })

        return klines if klines else None

    def get_orderbook(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """
        Get orderbook depth.

        Args:
            symbol: Trading pair
            limit: Depth limit (5, 10, 20, 50, 100, 500, 1000)

        Returns:
            Dict with 'bids' and 'asks' lists
        """
        params = {
            'symbol': symbol,
            'limit': limit
        }

        data = self._request("/api/v3/depth", params=params)

        if data is None:
            return None

        return {
            'bids': [[float(p), float(q)] for p, q in data.get('bids', [])],
            'asks': [[float(p), float(q)] for p, q in data.get('asks', [])]
        }

    def get_exchange_info(self) -> Optional[Dict]:
        """Get exchange trading rules and symbol info."""
        return self._request("/api/v3/exchangeInfo")

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get trading rules for specific symbol.

        Returns:
            Symbol info dict with filters, lot size, etc.
        """
        exchange_info = self.get_exchange_info()

        if not exchange_info or 'symbols' not in exchange_info:
            return None

        for s in exchange_info['symbols']:
            if s['symbol'] == symbol:
                return s

        return None


# Global instance
mexc_client = MexcClient()
