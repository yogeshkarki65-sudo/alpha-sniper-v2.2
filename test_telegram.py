"""
Quick test to verify Telegram notifications are working
"""
from dotenv import load_dotenv
load_dotenv()

from v4.monitoring.telegram_notifier import telegram_notifier

print("Testing Telegram notification...")
print(f"Telegram enabled: {telegram_notifier.enabled}")

if telegram_notifier.enabled:
    success = telegram_notifier.send_message(
        "🧪 *TEST MESSAGE*\n\n"
        "This is a test from Alpha Sniper V4.0.\n"
        "If you see this, Telegram notifications are working! ✅"
    )

    if success:
        print("✅ Message sent successfully!")
    else:
        print("❌ Failed to send message")
else:
    print("⚠️  Telegram is not enabled. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
