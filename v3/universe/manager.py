"""
Universe Manager for Alpha Sniper V3.2

Manages the trading universe with:
- Point-in-time symbol availability
- Liquidity filtering
- Spread filtering
- Delisting tracking
- Volume-based ranking
"""
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
import pandas as pd

from v3.data.mexc_client import mexc_client


class UniverseManager:
    """
    Manages trading universe with point-in-time awareness
    """

    def __init__(
        self,
        min_24h_volume_usd: float = 30000,
        max_spread_pct: float = 1.2,
        top_n_symbols: int = 150,
        excluded_symbols: Optional[Set[str]] = None
    ):
        """
        Args:
            min_24h_volume_usd: Minimum 24h volume in USD
            max_spread_pct: Maximum allowed spread %
            top_n_symbols: Keep top N by volume
            excluded_symbols: Set of symbols to exclude (e.g., stablecoins)
        """
        self.min_24h_volume_usd = min_24h_volume_usd
        self.max_spread_pct = max_spread_pct
        self.top_n_symbols = top_n_symbols

        if excluded_symbols is None:
            # Default exclusions: stablecoins, wrapped tokens, etc.
            excluded_symbols = {
                'USDCUSDT', 'TUSDUSDT', 'BUSDUSDT', 'DAIUSDT',
                'USDTUSDT', 'WBTCUSDT', 'WETHUSDT'
            }

        self.excluded_symbols = excluded_symbols

        # Point-in-time tracking
        self.symbol_availability: Dict[str, Dict] = {}  # {symbol: {first_seen, last_seen, is_delisted}}
        self.last_universe_update: Optional[datetime] = None
        self.current_universe: List[Dict] = []

    def update_universe(self, force_refresh: bool = False) -> List[Dict]:
        """
        Update trading universe

        Returns:
            List of dicts with symbol data:
            [{
                'symbol': str,
                'last_price': float,
                'volume_24h_usd': float,
                'price_change_pct': float,
                'high_24h': float,
                'low_24h': float,
                'spread_pct': float
            }, ...]
        """
        now = datetime.now()

        # Only update every 5 minutes unless forced
        if (not force_refresh and
            self.last_universe_update is not None and
            (now - self.last_universe_update).total_seconds() < 300):
            return self.current_universe

        print(f"[Universe] Updating universe at {now}")

        # Fetch all tickers
        all_tickers = mexc_client.get_24h_tickers()

        if not all_tickers:
            print("[Universe] WARNING: No tickers received")
            return self.current_universe

        # Filter to USDT pairs
        usdt_pairs = []
        for ticker in all_tickers:
            symbol = ticker.get('symbol', '')

            if not symbol.endswith('USDT'):
                continue

            if symbol in self.excluded_symbols:
                continue

            try:
                quote_volume = float(ticker.get('quoteVolume', 0) or 0)
                last_price = float(ticker.get('lastPrice', 0) or 0)
                price_change_pct = float(ticker.get('priceChangePercent', 0) or 0)
                high_price = float(ticker.get('highPrice', 0) or 0)
                low_price = float(ticker.get('lowPrice', 0) or 0)

                if quote_volume > 0 and last_price > 0:
                    usdt_pairs.append({
                        'symbol': symbol,
                        'volume_24h_usd': quote_volume,
                        'last_price': last_price,
                        'price_change_pct': price_change_pct,
                        'high_24h': high_price,
                        'low_24h': low_price
                    })

            except Exception as e:
                print(f"[Universe] Error processing {symbol}: {e}")
                continue

        if not usdt_pairs:
            print("[Universe] No valid USDT pairs found")
            return self.current_universe

        # Sort by volume and take top N
        usdt_pairs.sort(key=lambda x: x['volume_24h_usd'], reverse=True)
        top_pairs = usdt_pairs[:self.top_n_symbols]

        print(f"[Universe] Found {len(usdt_pairs)} USDT pairs, using top {len(top_pairs)}")

        # Apply liquidity and spread filters
        filtered_universe = []

        for pair in top_pairs:
            symbol = pair['symbol']

            # Liquidity filter
            if pair['volume_24h_usd'] < self.min_24h_volume_usd:
                continue

            # Spread filter (fetch from orderbook)
            spread_pct = mexc_client.get_spread_pct(symbol)

            if spread_pct is None:
                # Can't determine spread, skip for safety
                continue

            if spread_pct > self.max_spread_pct:
                print(f"[Universe] Skipping {symbol}: spread {spread_pct:.2f}% > {self.max_spread_pct}%")
                continue

            # Add spread to data
            pair['spread_pct'] = spread_pct

            filtered_universe.append(pair)

            # Update availability tracking
            self._update_availability(symbol, now)

        print(f"[Universe] Final universe: {len(filtered_universe)} symbols after all filters")

        self.current_universe = filtered_universe
        self.last_universe_update = now

        return self.current_universe

    def _update_availability(self, symbol: str, timestamp: datetime):
        """Track when symbols first/last seen"""
        if symbol not in self.symbol_availability:
            self.symbol_availability[symbol] = {
                'first_seen': timestamp,
                'last_seen': timestamp,
                'is_delisted': False
            }
        else:
            self.symbol_availability[symbol]['last_seen'] = timestamp

    def mark_delisted(self, symbol: str, timestamp: Optional[datetime] = None):
        """
        Mark a symbol as delisted

        This is called when we detect a symbol has been removed from exchange
        """
        if timestamp is None:
            timestamp = datetime.now()

        if symbol in self.symbol_availability:
            self.symbol_availability[symbol]['is_delisted'] = True
            self.symbol_availability[symbol]['delisted_at'] = timestamp

        print(f"[Universe] {symbol} marked as DELISTED at {timestamp}")

    def get_universe_at_time(self, timestamp: datetime) -> List[str]:
        """
        Get symbols that existed at a specific point in time

        Used for backtesting - only returns symbols that were available
        at the given timestamp.

        Args:
            timestamp: Historical timestamp

        Returns:
            List of symbol names that existed at that time
        """
        symbols = []

        for symbol, info in self.symbol_availability.items():
            first_seen = info['first_seen']
            last_seen = info['last_seen']

            # Symbol must have been seen by this time
            if timestamp < first_seen:
                continue

            # If delisted, must have been delisted after this time
            if info.get('is_delisted', False):
                delisted_at = info.get('delisted_at')
                if delisted_at and timestamp >= delisted_at:
                    continue

            # Check if symbol was still active at this time
            # If last_seen is way before timestamp, might be delisted
            if (timestamp - last_seen).total_seconds() > 86400 * 7:  # 7 days
                # Symbol likely delisted or inactive
                continue

            symbols.append(symbol)

        return symbols

    def get_current_universe_symbols(self) -> List[str]:
        """Get list of symbols in current universe"""
        return [pair['symbol'] for pair in self.current_universe]

    def get_symbol_data(self, symbol: str) -> Optional[Dict]:
        """Get data for a specific symbol from current universe"""
        for pair in self.current_universe:
            if pair['symbol'] == symbol:
                return pair

        return None

    def is_symbol_tradeable(self, symbol: str) -> bool:
        """Check if symbol is in current tradeable universe"""
        return symbol in self.get_current_universe_symbols()

    def get_universe_stats(self) -> Dict:
        """Get statistics about current universe"""
        if not self.current_universe:
            return {
                'symbol_count': 0,
                'total_volume_24h': 0,
                'avg_spread_pct': 0,
                'median_volume': 0
            }

        volumes = [p['volume_24h_usd'] for p in self.current_universe]
        spreads = [p['spread_pct'] for p in self.current_universe]

        return {
            'symbol_count': len(self.current_universe),
            'total_volume_24h': sum(volumes),
            'avg_spread_pct': sum(spreads) / len(spreads),
            'median_volume': pd.Series(volumes).median(),
            'min_volume': min(volumes),
            'max_volume': max(volumes),
            'last_update': self.last_universe_update
        }

    def export_availability_history(self) -> pd.DataFrame:
        """
        Export symbol availability history for backtesting

        Returns DataFrame with:
        - symbol
        - first_seen
        - last_seen
        - is_delisted
        """
        records = []

        for symbol, info in self.symbol_availability.items():
            records.append({
                'symbol': symbol,
                'first_seen': info['first_seen'],
                'last_seen': info['last_seen'],
                'is_delisted': info.get('is_delisted', False),
                'delisted_at': info.get('delisted_at', None)
            })

        return pd.DataFrame(records)


# Singleton instance
universe_manager = UniverseManager(
    min_24h_volume_usd=30000,
    max_spread_pct=1.2,
    top_n_symbols=150
)
