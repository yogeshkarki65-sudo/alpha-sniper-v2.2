#!/usr/bin/env python3
"""Quick test script to verify Telegram integration"""

from monitoring.telegram_alerter import send_alert

if __name__ == "__main__":
    test_message = """
🔔 <b>Alpha Sniper v4.1 - Test Alert</b>

✅ Telegram integration is working!

This is a test message to verify your bot configuration.

<i>If you received this, your Telegram alerts are configured correctly.</i>
"""

    print("Sending test Telegram message...")
    send_alert(test_message.strip())
    print("Test message sent! Check your Telegram.")
