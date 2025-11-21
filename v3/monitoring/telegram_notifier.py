#!/usr/bin/env python3
"""
Telegram Notifier - Send alerts to Telegram

Sends notifications for:
- Bot startup/shutdown
- Trade opened/closed
- Critical errors

Fails silently if TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID are not set.
"""

import os
import requests
from typing import Optional


class TelegramNotifier:
    """Send messages to Telegram bot."""

    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            print("[Telegram] WARNING: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set - notifications disabled")

    def send(self, message: str) -> bool:
        """
        Send message to Telegram.

        Args:
            message: Text to send (supports basic markdown)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                return True
            else:
                print(f"[Telegram] Failed to send: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"[Telegram] Error sending message: {e}")
            return False

    def send_startup(self, mode: str, equity: float):
        """Send bot startup notification."""
        msg = f"🚀 <b>Alpha Sniper V4.1 Started</b>\n"
        msg += f"Mode: {mode}\n"
        msg += f"Equity: ${equity:.2f}"
        self.send(msg)

    def send_shutdown(self, reason: str = "User stopped"):
        """Send bot shutdown notification."""
        msg = f"🔴 <b>Alpha Sniper V4.1 Stopped</b>\n"
        msg += f"Reason: {reason}"
        self.send(msg)

    def send_trade_opened(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        size_usd: float,
        risk_usd: float,
        engine: str
    ):
        """Send trade opened notification."""
        emoji = "🟢" if direction == "LONG" else "🔴"
        stop_pct = abs(entry_price - stop_loss) / entry_price * 100

        msg = f"{emoji} <b>{direction} OPENED: {symbol}</b>\n"
        msg += f"Entry: ${entry_price:.6f}\n"
        msg += f"Stop: ${stop_loss:.6f} ({stop_pct:.2f}%)\n"
        msg += f"Size: ${size_usd:.2f}\n"
        msg += f"Risk (R): ${risk_usd:.2f}\n"
        msg += f"Engine: {engine}"
        self.send(msg)

    def send_trade_closed(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        pnl_usd: float,
        pnl_pct: float,
        r_multiple: float,
        hold_time_hours: float,
        reason: str,
        engine: str
    ):
        """Send trade closed notification."""
        emoji = "✅" if pnl_usd >= 0 else "❌"

        msg = f"{emoji} <b>{direction} CLOSED: {symbol}</b>\n"
        msg += f"Entry: ${entry_price:.6f}\n"
        msg += f"Exit: ${exit_price:.6f}\n"
        msg += f"P&L: ${pnl_usd:+.2f} ({pnl_pct:+.2f}%)\n"
        msg += f"R-Multiple: {r_multiple:+.2f}R\n"
        msg += f"Hold time: {hold_time_hours:.1f}h\n"
        msg += f"Reason: {reason}\n"
        msg += f"Engine: {engine}"
        self.send(msg)

    def send_signal_found(self, symbol: str, direction: str, score: int, engine: str):
        """Send signal found notification (optional - can be noisy)."""
        msg = f"📊 <b>Signal Found: {symbol}</b>\n"
        msg += f"Direction: {direction}\n"
        msg += f"Score: {score}\n"
        msg += f"Engine: {engine}"
        self.send(msg)

    def send_error(self, error_message: str):
        """Send error notification."""
        msg = f"⚠️ <b>ERROR</b>\n"
        msg += f"{error_message}"
        self.send(msg)


# Global instance
telegram = TelegramNotifier()


def send_telegram(message: str) -> bool:
    """Convenience function to send telegram message."""
    return telegram.send(message)
