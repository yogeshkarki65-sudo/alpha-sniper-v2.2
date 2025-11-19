"""
Telegram Notifier for Alpha Sniper V3.2

Sends alerts and reports via Telegram:
- Bot startup/shutdown
- New signals detected
- Positions opened/closed
- Risk limit hits (daily loss cap, portfolio heat)
- Performance summaries
- Error alerts
"""
import os
import asyncio
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Try to import telegram, but make it optional
try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except Exception as e:
    TELEGRAM_AVAILABLE = False
    print(f"[Telegram] Telegram notifications disabled: {type(e).__name__}: {e}")


class TelegramNotifier:
    """
    Sends notifications via Telegram
    """

    def __init__(self):
        """Initialize Telegram bot"""
        self.enabled = False
        self.bot = None
        self.chat_id = None

        if not TELEGRAM_AVAILABLE:
            return

        # Get credentials from environment
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')

        if bot_token and self.chat_id:
            try:
                self.bot = Bot(token=bot_token)
                self.enabled = True
                print("[Telegram] Notifications enabled")
            except Exception as e:
                print(f"[Telegram] Failed to initialize bot: {e}")
        else:
            print("[Telegram] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")

    def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """
        Send a message via Telegram

        Args:
            message: Message text (supports Markdown)
            parse_mode: 'Markdown' or 'HTML'

        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False

        try:
            # python-telegram-bot 20.x is async
            # Use get_event_loop() with run_until_complete() for better compatibility
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=parse_mode
                )
            )
            return True

        except TelegramError as e:
            print(f"[Telegram] Error sending message: {e}")
            return False

        except Exception as e:
            print(f"[Telegram] Error sending message: {type(e).__name__}: {e}")
            return False

    def send_startup_alert(self, mode: str, equity: float):
        """Send bot startup notification"""
        message = f"""
🚀 *ALPHA SNIPER V3.2 - STARTED*

*Mode:* {mode}
*Initial Equity:* ${equity:.2f}
*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Bot is now running and scanning for opportunities.
        """.strip()

        self.send_message(message)

    def send_shutdown_alert(self, equity: float, pnl: float, trades: int):
        """Send bot shutdown notification"""
        pnl_pct = (pnl / (equity - pnl)) * 100 if equity - pnl > 0 else 0

        message = f"""
🛑 *ALPHA SNIPER V3.2 - STOPPED*

*Final Equity:* ${equity:.2f}
*Total P&L:* ${pnl:+.2f} ({pnl_pct:+.2f}%)
*Total Trades:* {trades}
*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Bot has been stopped.
        """.strip()

        self.send_message(message)

    def send_signal_alert(self, signal: dict):
        """Send new signal notification"""
        message = f"""
🎯 *NEW SIGNAL*

*Symbol:* {signal['symbol']}
*Score:* {signal['score']:.1f} ({signal['quality']})
*State:* {signal['symbol_state']}
*Regime:* {signal['regime']}

*Features:*
• RVOL: {signal['features']['rvol_15m']:.2f}
• Trend Ratio: {signal['features']['trend_ratio']:.3f}
• Position in Range: {signal['features']['position_in_range']:.2f}
• Momentum 24h: {signal['features']['ret_24h']:+.2f}%
        """.strip()

        self.send_message(message)

    def send_position_opened_alert(self, position: dict):
        """Send position opened notification"""
        message = f"""
✅ *POSITION OPENED*

*Symbol:* {position['symbol']}
*Entry:* ${position['entry_price']:.6f}
*Size:* ${position['size_usd']:.2f}
*Stop Loss:* ${position['stop_price']:.6f}
*Risk:* {position['risk_pct']:.2f}%

Trade is now active.
        """.strip()

        self.send_message(message)

    def send_position_closed_alert(self, trade: dict):
        """Send position closed notification"""
        emoji = "🟢" if trade['pnl_r'] > 0 else "🔴"

        message = f"""
{emoji} *POSITION CLOSED*

*Symbol:* {trade['symbol']}
*Entry:* ${trade['entry_price']:.6f}
*Exit:* ${trade['exit_price']:.6f}
*P&L:* {trade['pnl_r']:+.2f}R (${trade['pnl_usd']:+.2f})
*Hold Time:* {trade['hold_time_hours']:.1f}h
*Reason:* {trade['exit_reason']}

*Stats:*
• MFE: {trade['mfe_r']:+.2f}R
• MAE: {trade['mae_r']:.2f}R
        """.strip()

        self.send_message(message)

    def send_risk_alert(self, alert_type: str, message_text: str):
        """
        Send risk-related alert

        Args:
            alert_type: 'DAILY_LOSS_CAP', 'PORTFOLIO_HEAT', 'DRAWDOWN'
            message_text: Alert details
        """
        emoji_map = {
            'DAILY_LOSS_CAP': '⚠️',
            'PORTFOLIO_HEAT': '🔥',
            'DRAWDOWN': '📉',
            'ERROR': '❌'
        }

        emoji = emoji_map.get(alert_type, '⚠️')

        message = f"""
{emoji} *RISK ALERT: {alert_type}*

{message_text}

*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()

        self.send_message(message)

    def send_daily_summary(
        self,
        equity: float,
        daily_pnl: float,
        open_positions: int,
        closed_trades_today: int,
        win_rate: Optional[float] = None
    ):
        """Send daily performance summary"""
        daily_pnl_pct = (daily_pnl / (equity - daily_pnl)) * 100 if equity - daily_pnl > 0 else 0

        message = f"""
📊 *DAILY SUMMARY*

*Current Equity:* ${equity:.2f}
*Daily P&L:* ${daily_pnl:+.2f} ({daily_pnl_pct:+.2f}%)
*Open Positions:* {open_positions}
*Closed Today:* {closed_trades_today}
        """.strip()

        if win_rate is not None:
            message += f"\n*Win Rate:* {win_rate:.1f}%"

        message += f"\n\n*Date:* {datetime.now().strftime('%Y-%m-%d')}"

        self.send_message(message)

    def send_regime_change_alert(self, old_regime: str, new_regime: str, details: dict):
        """Send regime change notification"""
        message = f"""
🔄 *REGIME CHANGE*

*Old:* {old_regime}
*New:* {new_regime}

*Indicators:*
• Z-Score: {details.get('z_ret', 0):.2f}
• EMA State: {details.get('ema_state', 'N/A')}
• Vol Regime: {details.get('vol_regime', 'N/A')}
• Alt Strength: {details.get('alt_strength', 0):.4f}

Strategy will adapt to new market conditions.
        """.strip()

        self.send_message(message)

    def send_error_alert(self, error_message: str, module: str):
        """Send error notification"""
        self.send_risk_alert(
            'ERROR',
            f"*Module:* {module}\n*Error:* {error_message}"
        )


# Singleton instance
telegram_notifier = TelegramNotifier()
