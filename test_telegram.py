#!/usr/bin/env python3
"""Quick test script to verify Telegram integration"""

import requests
from config.config import config

if __name__ == "__main__":
    test_message = """
🔔 <b>Alpha Sniper v4.1 - Test Alert</b>

✅ Telegram integration is working!

This is a test message to verify your bot configuration.

<i>If you received this, your Telegram alerts are configured correctly.</i>
"""

    print("Sending test Telegram message...")
    print(f"Bot Token: {config.TELEGRAM_BOT_TOKEN[:20]}... (hidden)")
    print(f"Chat ID: {config.TELEGRAM_CHAT_ID}")

    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': config.TELEGRAM_CHAT_ID,
            'text': test_message.strip(),
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=data, timeout=10)
        print(f"\nAPI Response Status: {response.status_code}")
        print(f"API Response: {response.json()}")

        if response.status_code == 200:
            print("\n✅ Message sent successfully! Check your Telegram.")
        else:
            print(f"\n❌ Failed to send message. Error: {response.json()}")
    except Exception as e:
        print(f"\n❌ Exception occurred: {e}")
