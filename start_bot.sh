#!/bin/bash
# Alpha Sniper Bot Deployment Script

echo "🚀 Starting Alpha Sniper Bot v2.2 with optimized settings..."

cd /home/user/alpha-sniper-v2.2

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p data

# Show current configuration
echo ""
echo "📊 Current Configuration:"
echo "  - Scanner Universe: 200 coins (was 60)"
echo "  - Liquidity Filter: \$30k (was \$100k)"
echo "  - Spread Filter: 2.0% (was 0.5%)"
echo "  - Position Risk: 0.25% (was 0.5%)"
echo "  - Cooldown: 1h (was 6h)"
echo "  - Trailing Stop: 5%/2.5% (was 2%/1%)"
echo "  - Velocity Weight: 45% (was 25%)"
echo ""

# Start the bot in background with nohup
nohup python3 -u main.py > logs/bot.log 2>&1 &
BOT_PID=$!

echo "✅ Bot started with PID: $BOT_PID"
echo "📝 Logs: logs/bot.log"
echo ""
echo "Commands:"
echo "  - View logs: tail -f logs/bot.log"
echo "  - Stop bot: kill $BOT_PID"
echo "  - Check status: ps aux | grep main.py"
echo ""
