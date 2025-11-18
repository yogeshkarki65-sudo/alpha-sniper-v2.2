"""
Position Manager for Alpha Sniper V3.2

Manages open positions:
- Stop loss monitoring
- Take profit levels (TP1, TP2)
- Trailing stop
- No-follow-through rule (exit dead trades early)
- Time-based exits
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from v3.risk.risk_engine import risk_engine, Position
from v3.execution.cost_model import execution_cost_model
from v3.data.mexc_client import mexc_client


class PositionManager:
    """
    Manages lifecycle of open positions
    """

    def __init__(
        self,
        # Take profit levels (in R multiples)
        tp1_r: float = 2.0,  # First take profit at 2R
        tp2_r: float = 3.0,  # Second take profit at 3R
        tp1_size_pct: float = 0.50,  # Take 50% at TP1
        tp2_size_pct: float = 0.30,  # Take 30% at TP2 (70% total)
        # Trailing stop (for remaining position)
        trailing_atr_mult: float = 1.5,
        # No-follow-through rule
        nft_bars: int = 12,  # 12 * 15m = 3 hours
        nft_min_mfe_r: float = 0.5,  # Must reach 0.5R MFE
        nft_range_r: tuple = (-0.5, 0.2),  # Current P&L between -0.5R and +0.2R
        # Time exit
        max_hold_hours: float = 48.0
    ):
        """
        Args:
            tp1_r: First take profit in R multiples
            tp2_r: Second take profit in R multiples
            tp1_size_pct: % of position to close at TP1
            tp2_size_pct: % of position to close at TP2
            trailing_atr_mult: ATR multiplier for trailing stop
            nft_bars: Number of bars for no-follow-through check
            nft_min_mfe_r: Minimum MFE to avoid NFT exit
            nft_range_r: P&L range for NFT exit
            max_hold_hours: Maximum hold time in hours
        """
        self.tp1_r = tp1_r
        self.tp2_r = tp2_r
        self.tp1_size_pct = tp1_size_pct
        self.tp2_size_pct = tp2_size_pct
        self.trailing_atr_mult = trailing_atr_mult
        self.nft_bars = nft_bars
        self.nft_min_mfe_r = nft_min_mfe_r
        self.nft_range_r = nft_range_r
        self.max_hold_hours = max_hold_hours

        # Position tracking
        self.position_metadata: Dict[str, Dict] = {}  # {symbol: {tp_levels, etc}}

    def manage_positions(self):
        """
        Main position management loop

        Checks all open positions for exit conditions
        """
        open_positions = list(risk_engine.open_positions.values())

        if len(open_positions) == 0:
            return

        print(f"\n{'='*60}")
        print(f"📊 MANAGING {len(open_positions)} OPEN POSITIONS")
        print(f"{'='*60}")

        for position in open_positions:
            try:
                self._manage_position(position)
            except Exception as e:
                print(f"[PositionMgr] Error managing {position.symbol}: {e}")
                import traceback
                traceback.print_exc()

        print(f"{'='*60}\n")

    def _manage_position(self, position: Position):
        """Manage a single position"""
        symbol = position.symbol

        # Get current price
        current_price = self._get_current_price(symbol)
        if current_price is None:
            print(f"⚠️  {symbol}: Could not fetch price")
            return

        # Update position price
        risk_engine.update_position_price(symbol, current_price)

        # Get/create metadata
        if symbol not in self.position_metadata:
            self._initialize_position_metadata(position)

        metadata = self.position_metadata[symbol]

        # Calculate current P&L
        pnl_r = position.get_unrealized_pnl_r()
        pnl_usd = position.get_unrealized_pnl_usd()

        # Hold time
        hold_hours = (datetime.now() - position.timestamp).total_seconds() / 3600

        print(f"📈 {symbol}: ${current_price:.6f} | "
              f"P&L: {pnl_r:+.2f}R (${pnl_usd:+.2f}) | "
              f"Hold: {hold_hours:.1f}h")

        # Check exit conditions (in priority order)
        exit_reason = None

        # 1. Stop loss
        if current_price <= position.stop_loss_price:
            exit_reason = "STOP_LOSS"

        # 2. Take profit levels
        elif not metadata['tp1_hit'] and pnl_r >= self.tp1_r:
            self._handle_tp1(position, current_price)
            return  # Don't check other exits this cycle

        elif metadata['tp1_hit'] and not metadata['tp2_hit'] and pnl_r >= self.tp2_r:
            self._handle_tp2(position, current_price)
            return

        # 3. Trailing stop (if TP1 hit)
        elif metadata['tp1_hit']:
            trailing_stop = metadata.get('trailing_stop_price')
            if trailing_stop is not None and current_price <= trailing_stop:
                exit_reason = "TRAILING_STOP"
            else:
                # Update trailing stop
                self._update_trailing_stop(position, metadata, current_price)

        # 4. No-follow-through rule
        elif self._check_no_follow_through(position, metadata, pnl_r, hold_hours):
            exit_reason = "NO_FOLLOW_THROUGH"

        # 5. Time exit
        elif hold_hours >= self.max_hold_hours:
            exit_reason = "TIME_EXIT"

        # Execute exit if triggered
        if exit_reason is not None:
            self._exit_position(position, current_price, exit_reason)

    def _initialize_position_metadata(self, position: Position):
        """Initialize tracking metadata for a position"""
        self.position_metadata[position.symbol] = {
            'tp1_hit': False,
            'tp2_hit': False,
            'tp1_price': position.entry_price + (position.entry_price - position.stop_loss_price) * self.tp1_r,
            'tp2_price': position.entry_price + (position.entry_price - position.stop_loss_price) * self.tp2_r,
            'trailing_stop_price': None,
            'original_size': position.size_usd,
            'bars_held': 0
        }

    def _handle_tp1(self, position: Position, current_price: float):
        """Handle TP1 hit - take partial profit"""
        metadata = self.position_metadata[position.symbol]

        print(f"🎯 {position.symbol}: TP1 HIT @ ${current_price:.6f}")

        # Calculate profit from partial close
        partial_size = metadata['original_size'] * self.tp1_size_pct
        partial_pnl = (current_price - position.entry_price) / position.entry_price * partial_size

        print(f"   Taking {self.tp1_size_pct*100:.0f}% profit: ${partial_pnl:.2f}")

        # Update metadata
        metadata['tp1_hit'] = True
        position.size_usd *= (1 - self.tp1_size_pct)

        # Move stop to breakeven
        position.stop_loss_price = position.entry_price
        print(f"   Stop moved to breakeven: ${position.stop_loss_price:.6f}")

        # Initialize trailing stop
        self._update_trailing_stop(position, metadata, current_price)

        # Update equity (realize partial profit)
        risk_engine.current_equity += partial_pnl

    def _handle_tp2(self, position: Position, current_price: float):
        """Handle TP2 hit - take more profit"""
        metadata = self.position_metadata[position.symbol]

        print(f"🎯 {position.symbol}: TP2 HIT @ ${current_price:.6f}")

        # Calculate profit from second partial close
        partial_size = metadata['original_size'] * self.tp2_size_pct
        partial_pnl = (current_price - position.entry_price) / position.entry_price * partial_size

        print(f"   Taking {self.tp2_size_pct*100:.0f}% more profit: ${partial_pnl:.2f}")

        # Update metadata
        metadata['tp2_hit'] = True
        position.size_usd *= (1 - self.tp2_size_pct / (1 - self.tp1_size_pct))

        # Update equity
        risk_engine.current_equity += partial_pnl

        # Update trailing stop for remaining position
        self._update_trailing_stop(position, metadata, current_price)

    def _update_trailing_stop(self, position: Position, metadata: Dict, current_price: float):
        """Update trailing stop price"""
        # Get ATR for trailing distance
        # In live, would fetch from features; for now use fixed %
        atr_estimate = position.entry_price * 0.02  # Estimate 2% ATR

        trailing_distance = self.trailing_atr_mult * atr_estimate

        # Trailing stop = highest price since entry - trailing distance
        new_trailing_stop = position.highest_price - trailing_distance

        # Only update if new stop is higher than current
        current_trailing = metadata.get('trailing_stop_price')
        if current_trailing is None or new_trailing_stop > current_trailing:
            metadata['trailing_stop_price'] = new_trailing_stop
            print(f"   Trailing stop updated: ${new_trailing_stop:.6f}")

    def _check_no_follow_through(
        self,
        position: Position,
        metadata: Dict,
        current_pnl_r: float,
        hold_hours: float
    ) -> bool:
        """
        Check no-follow-through rule

        Exit if:
        - Held for > nft_bars (e.g., 3 hours)
        - MFE < nft_min_mfe_r (never reached 0.5R)
        - Current P&L between -0.5R and +0.2R (dead trade)
        """
        # Convert bars to hours (assuming 15m bars)
        nft_hours = (self.nft_bars * 15) / 60

        if hold_hours < nft_hours:
            return False

        # Check MFE
        if position.max_favorable_excursion >= self.nft_min_mfe_r:
            return False  # Trade showed promise

        # Check current P&L range
        if not (self.nft_range_r[0] <= current_pnl_r <= self.nft_range_r[1]):
            return False  # P&L outside dead zone

        # All conditions met - dead trade
        print(f"   💀 No-follow-through detected (MFE={position.max_favorable_excursion:.2f}R)")
        return True

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for symbol"""
        try:
            tickers = mexc_client.get_24h_tickers()
            for ticker in tickers:
                if ticker.get('symbol') == symbol:
                    return float(ticker.get('lastPrice', 0))
            return None
        except Exception as e:
            print(f"[PositionMgr] Error fetching price: {e}")
            return None

    def _exit_position(self, position: Position, exit_price: float, reason: str):
        """Exit a position"""
        symbol = position.symbol

        print(f"🚪 EXITING {symbol} @ ${exit_price:.6f}")
        print(f"   Reason: {reason}")

        # Estimate exit cost
        spread_pct = 0.01  # Default 1bp spread
        cost_estimate = execution_cost_model.estimate_exit_cost(
            symbol=symbol,
            intended_price=exit_price,
            order_size_usd=position.size_usd,
            spread_pct=spread_pct,
            orderbook_depth_usd=10000,
            urgency="NORMAL"
        )

        actual_exit_price = cost_estimate['expected_fill_price']

        # Close position in risk engine
        trade_result = risk_engine.close_position(
            symbol=symbol,
            exit_price=actual_exit_price,
            exit_reason=reason,
            timestamp=datetime.now()
        )

        if trade_result:
            print(f"   P&L: {trade_result['pnl_r']:+.2f}R (${trade_result['pnl_usd']:+.2f})")
            print(f"   Hold: {trade_result['hold_time_hours']:.1f}h")

        # Clean up metadata
        if symbol in self.position_metadata:
            del self.position_metadata[symbol]

    def get_position_summary(self) -> Dict:
        """Get summary of all positions"""
        positions = []

        for position in risk_engine.open_positions.values():
            current_price = self._get_current_price(position.symbol)
            if current_price:
                risk_engine.update_position_price(position.symbol, current_price)

            metadata = self.position_metadata.get(position.symbol, {})

            positions.append({
                'symbol': position.symbol,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'size_usd': position.size_usd,
                'stop_loss': position.stop_loss_price,
                'pnl_r': position.get_unrealized_pnl_r(),
                'pnl_usd': position.get_unrealized_pnl_usd(),
                'hold_hours': (datetime.now() - position.timestamp).total_seconds() / 3600,
                'tp1_hit': metadata.get('tp1_hit', False),
                'tp2_hit': metadata.get('tp2_hit', False),
                'trailing_stop': metadata.get('trailing_stop_price')
            })

        return {
            'count': len(positions),
            'positions': positions,
            'total_pnl_usd': sum(p['pnl_usd'] for p in positions)
        }


# Singleton instance
position_manager = PositionManager(
    tp1_r=2.0,
    tp2_r=3.0,
    tp1_size_pct=0.50,
    tp2_size_pct=0.30,
    trailing_atr_mult=1.5,
    nft_bars=12,
    nft_min_mfe_r=0.5,
    max_hold_hours=48.0
)
