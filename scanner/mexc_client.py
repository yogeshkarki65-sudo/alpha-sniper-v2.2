"""
Alpha Sniper v4.1 MEXC API Client
Handles REST API calls for market data (tickers, klines, orderbook)
"""
import requests
from typing import List, Dict, Optional, Any
from config.config import config
from config.logging_config import logger


class MEXCClient:
    """MEXC REST API client for market data"""

    def __init__(self):
        self.base_url = config.MEXC_BASE_URL
        self.timeout = 10

    def get_24h_tickers(self) -> List[Dict[str, Any]]:
        """
        Fetch 24h ticker data for all symbols
        Returns: List of ticker dicts
        """
        try:
            url = f"{self.base_url}/api/v3/ticker/24hr"
            logger.debug(f"Fetching 24h tickers from: {url}")
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            tickers = resp.json()
            logger.info(f"Fetched {len(tickers)} 24h tickers")
            return tickers
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
            url = f"{self.base_url}/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            klines = resp.json()
            return klines
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
            resp = requests.get(url, params=params, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return float(data['price'])
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
            resp = requests.get(url, params=params, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Error fetching orderbook for {symbol}: {e}")
            return None


# Global client instance
mexc_client = MEXCClient()
