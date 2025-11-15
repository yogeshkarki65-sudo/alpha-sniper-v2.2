# Alpha Sniper V2.2

Automated crypto trading bot for MEXC exchange with AI-powered signal scoring, risk management, and self-learning capabilities.

## 🚀 Quick Deploy (3 Commands)

```bash
git clone https://github.com/yogeshkarki65-sudo/alpha-sniper-v2.2.git
cd alpha-sniper-v2.2
./deploy.sh
```

That's it! The script will guide you through the rest.

## 📋 What It Does

- **Scans** MEXC for high-volume USDT pairs every 5 minutes
- **Scores** opportunities based on volume, velocity, trend, and orderbook
- **Opens** positions automatically when signals exceed threshold
- **Manages** positions with stop-loss, take-profit, and trailing stops
- **Learns** from past trades to improve signal scoring
- **Alerts** you via Telegram for all important events

## ✨ Features

### Risk Management
- Daily drawdown limits (default 2%)
- Per-position risk limits (default 0.5%)
- Correlation checks to avoid overexposure
- Emergency stop endpoint
- Trading pause functionality

### Position Management
- Automatic stop-loss and take-profit
- Trailing stops to lock in profits
- Time-based exits (optional)
- Position recovery on restart
- Duplicate order prevention

### Self-Learning
- Analyzes past trades
- Adjusts signal weights based on performance
- Uses information coefficient for validation
- Gradual weight changes (max 15% per update)

### Monitoring
- Health check endpoint (:8080)
- Emergency stop endpoint (:8081)
- Telegram alerts for all trades
- Daily performance reports
- Position recovery logs

## 📦 Requirements

- Python 3.11+
- 1GB+ RAM
- Stable internet connection
- MEXC account (no API keys needed for SIM mode)
- Telegram bot (for alerts)

## 🔧 Manual Setup

If you prefer manual setup:

```bash
# 1. Clone and checkout latest
git clone https://github.com/yogeshkarki65-sudo/alpha-sniper-v2.2.git
cd alpha-sniper-v2.2
git checkout claude/latest-fixes-01QVwRQY57npqebQKVvUBaHd

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Setup environment
cp .env.example .env
nano .env  # Add your Telegram credentials

# 4. Create directories
mkdir -p data logs backups

# 5. Run
python3 main.py
```

## ⚙️ Configuration

Edit `.env` to customize:

```bash
# Trading Mode
MODE=SIM                    # SIM or LIVE
SIM_EQUITY_START=500        # Starting capital for simulation

# Risk (CRITICAL!)
MAX_DAILY_DRAWDOWN_PCT=2.0  # Stop trading if down this much
MAX_POSITION_RISK_PCT=0.5   # Risk per position

# Position Management
MAX_CONCURRENT_POS=2        # Max open positions
STOP_LOSS_PCT=5.0           # Stop loss percentage
TAKE_PROFIT_PCT=10.0        # Take profit percentage

# Signals
MIN_SIGNAL_SCORE=70         # Minimum score to trade
MOON_SCORE=90               # Score for position sizing boost

# Telegram Alerts
TELEGRAM_BOT_TOKEN=your_token    # Get from @BotFather
TELEGRAM_CHAT_ID=your_chat_id    # Get from @userinfobot
```

## 📊 Monitoring

**Health Check:**
```bash
curl http://localhost:8080/health
```

**Emergency Stop:**
```bash
curl -X POST http://localhost:8081/emergency-stop
```

**View Logs (systemd):**
```bash
sudo journalctl -u alpha-sniper -f
```

## 🎯 Usage Flow

1. **Start in SIM mode** - Run for 7-14 days
2. **Monitor performance** - Check daily reports
3. **Analyze results** - Review win rate, drawdown, profit
4. **Switch to LIVE** - Start with small capital
5. **Scale gradually** - Increase as confidence grows

## 🛡️ Safety Features

- **Daily drawdown limits** - Auto-pauses if exceeded
- **Position recovery** - Restores state after restart
- **Duplicate prevention** - Blocks duplicate orders
- **Rate limiting** - Prevents API bans
- **Emergency endpoint** - Instant trading stop
- **Correlation checks** - Avoids overexposure

## 📁 Project Structure

```
alpha-sniper-v2.2/
├── config/          # Configuration management
├── scanner/         # Market scanning and signals
├── trader/          # Position management
├── risk/            # Risk management
├── learning/        # Self-learning module
├── monitoring/      # Health checks and alerts
├── database/        # SQLite data storage
├── deployment/      # Deployment tools
├── main.py          # Main entry point
├── deploy.sh        # One-click deployment
└── DEPLOYMENT.md    # Detailed deployment guide
```

## 🐛 Troubleshooting

**Bot won't start?**
- Check Python version: `python3 --version`
- Verify .env exists: `ls -la .env`
- Check dependencies: `pip3 install -r requirements.txt`

**No signals created?**
- Normal if market is quiet
- Lower MIN_SIGNAL_SCORE in .env
- Check MEXC API is accessible

**API errors?**
- Verify internet connection
- Check MEXC status
- Review rate limiting logs

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed troubleshooting.

## 📝 Important Notes

⚠️ **Always start in SIM mode first!**

⚠️ **Never share your .env file** - Contains secrets

⚠️ **Monitor daily** - Check Telegram alerts and logs

⚠️ **Start small** - Use minimal capital when going LIVE

⚠️ **No guarantees** - Trading crypto is risky

## 📚 Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Full deployment guide
- [CRITICAL_ISSUES.md](CRITICAL_ISSUES.md) - Known limitations
- [GROK_FIXES_IMPLEMENTED.md](GROK_FIXES_IMPLEMENTED.md) - Security audit fixes
- [GROK_PROJECT_REVIEW.md](GROK_PROJECT_REVIEW.md) - Technical review

## 🔗 Links

- Repository: https://github.com/yogeshkarki65-sudo/alpha-sniper-v2.2
- Latest Branch: `claude/latest-fixes-01QVwRQY57npqebQKVvUBaHd`

## ⚖️ License

Use at your own risk. No warranty provided.

## 🤝 Support

For issues and questions, check existing documentation first:
- DEPLOYMENT.md for setup issues
- CRITICAL_ISSUES.md for known limitations
- Telegram alerts for runtime issues

---

**Good luck and trade responsibly! 📈**
