"""
Alpha Sniper V4.0 - Symbol State Machine
States: FLAT, BUILDUP, TRIGGERED, ACTIVE, COOLDOWN
"""
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, Optional


class SymbolState(Enum):
    """Symbol states for entry engines"""
    FLAT = "FLAT"              # No setup
    BUILDUP = "BUILDUP"        # Coil forming, waiting for trigger
    TRIGGERED = "TRIGGERED"    # Breakout triggered, order pending
    ACTIVE = "ACTIVE"          # Position open
    COOLDOWN = "COOLDOWN"      # Recently closed, cooling down


class SymbolStateMachine:
    """Tracks state of individual symbols"""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.state = SymbolState.FLAT

        # Buildup tracking
        self.buildup_start = None
        self.base_high = None
        self.base_low = None

        # Cooldown tracking
        self.cooldown_until = None

    def enter_buildup(self, base_high: float, base_low: float):
        """Enter BUILDUP state"""
        self.state = SymbolState.BUILDUP
        self.buildup_start = datetime.now()
        self.base_high = base_high
        self.base_low = base_low

    def trigger(self):
        """Enter TRIGGERED state"""
        self.state = SymbolState.TRIGGERED

    def activate(self):
        """Enter ACTIVE state (position opened)"""
        self.state = SymbolState.ACTIVE

    def enter_cooldown(self, cooldown_hours: float = 6.0):
        """Enter COOLDOWN state after position closed"""
        self.state = SymbolState.COOLDOWN
        self.cooldown_until = datetime.now() + timedelta(hours=cooldown_hours)

    def reset(self):
        """Reset to FLAT"""
        self.state = SymbolState.FLAT
        self.buildup_start = None
        self.base_high = None
        self.base_low = None

    def is_tradeable(self) -> bool:
        """Can we trade this symbol?"""
        if self.state in [SymbolState.ACTIVE, SymbolState.TRIGGERED]:
            return False

        if self.state == SymbolState.COOLDOWN:
            if datetime.now() < self.cooldown_until:
                return False
            else:
                # Cooldown expired, reset to FLAT
                self.reset()

        return True

    def update_cooldown(self):
        """Check and update cooldown state"""
        if self.state == SymbolState.COOLDOWN:
            if datetime.now() >= self.cooldown_until:
                self.reset()


class SymbolStateManager:
    """Manages state for all symbols"""

    def __init__(self):
        self.states: Dict[str, SymbolStateMachine] = {}

    def get_or_create(self, symbol: str) -> SymbolStateMachine:
        """Get state machine for symbol"""
        if symbol not in self.states:
            self.states[symbol] = SymbolStateMachine(symbol)
        return self.states[symbol]

    def update_all(self):
        """Update all state machines (check cooldowns, etc.)"""
        for state in self.states.values():
            state.update_cooldown()


# Singleton
symbol_state_manager = SymbolStateManager()
