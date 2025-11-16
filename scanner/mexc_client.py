"""
Alpha Sniper v4.1 MEXC API Client
Handles REST API calls for market data (tickers, klines, orderbook)
"""
import requests
import subprocess
import json
import os
from typing import List, Dict, Optional, Any
from config.config import config
from config.logging_config import logger


class MEXCClient:
    """MEXC REST API client for market data"""

    def __init__(self):
        self.base_url = config.MEXC_BASE_URL
        self.timeout = 10
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://www.mexc.com',
            'Referer': 'https://www.mexc.com/',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
        # Create session that respects environment proxy settings
        self.session = requests.Session()
        self.session.trust_env = True  # Use environment proxy settings
        self.session.headers.update(self.headers)

    def _curl_get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Fallback to curl for API calls (MEXC blocks Python requests)
        """
        try:
            if params:
                url_params = '&'.join([f"{k}={v}" for k, v in params.items()])
                full_url = f"{url}?{url_params}"
            else:
                full_url = url

            result = subprocess.run(
                ['curl', '-s', '-m', str(self.timeout), full_url],
                capture_output=True,
                text=True,
                timeout=self.timeout + 2
            )

            if result.returncode == 0 and result.stdout:
                return json.loads(result.stdout)
            return None
        except Exception as e:
            logger.warning(f"Curl request failed: {e}")
            return None

    def get_24h_tickers(self) -> List[Dict[str, Any]]:
        """
        Fetch 24h ticker data for all symbols
        Returns: List of ticker dicts
        """
        try:
            url = f"{self.base_url}/api/v3/ticker/24hr"
            logger.debug(f"Fetching 24h tickers from: {url}")

            # Use curl (MEXC blocks Python requests)
            tickers = self._curl_get(url)
            if tickers and isinstance(tickers, list):
                logger.info(f"Fetched {len(tickers)} 24h tickers")
                return tickers
            else:
                logger.warning("No tickers received from exchange")
                return []
        except Exception as e:
            logger.error(f"Error fetching 24h tickers: {e}")
            return []

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100
    ) -> List[List]:
        """
        Fetch kline/candlestick data
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: '1h', '4h', '1d'
            limit: Number of candles (default 100)
        Returns: List of klines [[timestamp, open, high, low, close, volume, ...], ...]
        """
        try:
            # MEXC uses specific interval notation
            interval_map = {
                '1h': '60m',   # MEXC uses minutes for hourly
                '4h': '4h',    # 4h stays same
                '1d': '1d',    # 1d stays same
                '24h': '1d'    # Map 24h to 1d
            }

            mexc_interval = interval_map.get(interval, interval)

            url = f"{self.base_url}/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': mexc_interval,
                'limit': limit
            }

            # Use curl (MEXC blocks Python requests)
            klines = self._curl_get(url, params)
            if klines and isinstance(klines, list):
                return klines
            else:
                logger.debug(f"Klines not available for {symbol} {mexc_interval}")
                return []
        except Exception as e:
            logger.warning(f"Error fetching klines for {symbol} {interval}: {e}")
            return []

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
        Returns: Current price or None
        """
        try:
            url = f"{self.base_url}/api/v3/ticker/price"
            params = {'symbol': symbol}

            # Use curl (MEXC blocks Python requests)
            data = self._curl_get(url, params)
            if data and 'price' in data:
                return float(data['price'])
            return None
        except Exception as e:
            logger.warning(f"Error fetching price for {symbol}: {e}")
            return None

    def get_orderbook(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """
        Get orderbook depth
        Args:
            symbol: Trading pair
            limit: Depth limit (5, 10, 20, 50, 100, 500, 1000, 5000)
        Returns: {'bids': [[price, qty], ...], 'asks': [[price, qty], ...]}
        """
        try:
            url = f"{self.base_url}/api/v3/depth"
            params = {'symbol': symbol, 'limit': limit}

            # Use curl (MEXC blocks Python requests)
            data = self._curl_get(url, params)
            if data:
                return data
            return None
        except Exception as e:
            logger.warning(f"Error fetching orderbook for {symbol}: {e}")
            return None


# Global client instance
mexc_client = MEXCClient()
