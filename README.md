# Alpha Sniper V2.2

An automated cryptocurrency trading bot for MEXC exchange with advanced risk management, self-learning capabilities, and comprehensive monitoring.

## Features

- **Automated Trading**: Scans for opportunities and executes trades automatically
- **Risk Management**: Daily drawdown limits, position sizing, correlation checks
- **Self-Learning**: Adapts signal weights based on historical performance
- **Telegram Alerts**: Real-time notifications and daily reports
- **SIM Mode**: Test strategies without real money
- **Health Monitoring**: Built-in health check endpoint
- **Database Tracking**: Complete trade history and analytics

## Quick Start

### New Server Setup

```bash
# Clone the repository
git clone <your-repo-url> ~/alpha-sniper-v2.2
cd ~/alpha-sniper-v2.2

# Run automated setup (Ubuntu/Debian)
sudo ./deployment/setup_server.sh

# Configure your settings
nano .env

# Start the bot
./deployment/quick_start.sh
```

### Already Configured Server

```bash
cd ~/alpha-sniper-v2.2
./deployment/quick_start.sh
```

## Documentation

- **[Complete Deployment Guide](deployment/DEPLOYMENT_GUIDE.md)** - Full setup instructions
- **[Deployment Scripts](deployment/README.md)** - Script documentation
- **[Critical Issues](CRITICAL_ISSUES.md)** - Known risks and limitations

## Architecture

```
alpha-sniper-v2.2/
├── scanner/          # Market scanning and opportunity detection
├── trader/           # Trade execution and position management
├── risk/             # Risk management and daily reset logic
├── learning/         # Self-learning weight optimization
├── monitoring/       # Health checks, alerts, and reporting
├── database/         # Database schema and operations
├── config/           # Configuration management
├── deployment/       # Deployment scripts and docs
└── tests/            # Test suite
```

## Configuration

Key settings in `.env`:

```bash
# Trading Mode
MODE=SIM                          # SIM or LIVE (always start with SIM!)

# Risk Management
MAX_DAILY_DRAWDOWN_PCT=2.0       # Stop trading if daily loss exceeds this
MAX_POSITION_RISK_PCT=0.5        # Max risk per position
MAX_CONCURRENT_POS=2             # Max open positions

# Telegram (Required)
TELEGRAM_BOT_TOKEN=your_token    # From @BotFather
TELEGRAM_CHAT_ID=your_chat_id    # From @userinfobot
```

See `.env.example` for all available options.

## Management Commands

```bash
# Start bot
docker compose up -d

# Stop bot
docker compose down

# View logs
docker compose logs -f

# Check status
./deployment/monitor.sh

# View statistics
./deployment/stats.sh

# Emergency stop
./deployment/stop_trading.sh

# Manual backup
./deployment/backup.sh
```

## Monitoring

### Health Check
```bash
curl http://localhost:8090/health
```

### Quick Status
```bash
./deployment/monitor.sh
```

### Performance Statistics
```bash
./deployment/stats.sh
```

### Telegram
- Startup notification
- Trade notifications
- Daily report (configurable hour)
- Drawdown alerts
- Error alerts

## Safety Features

1. **SIM Mode**: Test without real money
2. **Daily Drawdown Limit**: Auto-pause if daily loss exceeds threshold
3. **Position Limits**: Max concurrent positions and per-trade size
4. **Correlation Checks**: Prevent over-concentration
5. **Liquidity Filters**: Only trade liquid markets
6. **Trailing Stops**: Protect profits
7. **Emergency Stop**: Quick shutdown script
8. **Automatic Backups**: Daily database backups

## Development

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- MEXC account (for live trading)
- Telegram bot token

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Run locally (without Docker)
python main.py
```

## Production Deployment

⚠️ **IMPORTANT: Always follow these steps**

1. **Start in SIM mode** for 7-14 days minimum
2. **Monitor daily** via Telegram and logs
3. **Review statistics** using stats.sh
4. **Verify configuration** is correct
5. **Start with minimal capital** when going live
6. **Scale gradually** based on proven performance

See [DEPLOYMENT_GUIDE.md](deployment/DEPLOYMENT_GUIDE.md) for detailed instructions.

## Risk Warning

⚠️ **CRYPTOCURRENCY TRADING IS RISKY**

- This bot is provided as-is with no guarantees
- You can lose all your capital
- Past performance does not guarantee future results
- Always start with SIM mode
- Never trade more than you can afford to lose
- Review [CRITICAL_ISSUES.md](CRITICAL_ISSUES.md) before deploying

## Troubleshooting

### Bot not starting
```bash
docker compose logs
```

### No Telegram messages
1. Verify bot token and chat ID in `.env`
2. Test manually: `curl "https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=Test"`

### Database issues
```bash
docker compose exec alpha-sniper sqlite3 /app/data/trades.db "PRAGMA integrity_check;"
```

### Performance issues
```bash
docker stats alpha-sniper-v2
./deployment/monitor.sh
```

See [DEPLOYMENT_GUIDE.md](deployment/DEPLOYMENT_GUIDE.md) for more troubleshooting steps.

## Architecture Details

### Core Components

- **Scanner**: Fetches market data from MEXC, analyzes opportunities, stores signals
- **Trader**: Evaluates signals, manages positions, executes entry/exit logic
- **Risk Manager**: Enforces limits, calculates position sizes, monitors drawdown
- **Learning Module**: Analyzes trade outcomes, adjusts signal weights
- **Monitor**: Health checks, Telegram alerts, daily reports
- **Capital Manager**: Determines safe capital scaling based on performance

### Trading Flow

1. Scanner fetches market data every 5 minutes (configurable)
2. Calculates signal scores based on price action, volume, volatility
3. Stores opportunities in database
4. Trader evaluates signals every 60 seconds
5. Checks risk limits, correlation, liquidity
6. Executes trades if criteria met
7. Monitors positions for exit conditions
8. Learning module refines weights based on outcomes

### Database Schema

- **trades**: Complete trade history
- **signals**: Market scanning results
- **daily_stats**: Daily performance tracking
- **weights**: Learning module weight history

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly in SIM mode
5. Submit a pull request

## License

[Your License Here]

## Support

- Check documentation in `deployment/`
- Review logs: `docker compose logs -f`
- Run diagnostics: `./deployment/monitor.sh`
- Check health: `curl http://localhost:8090/health`

## Credits

Built for automated cryptocurrency trading with a focus on risk management and continuous improvement.

---

**Remember**: Always start in SIM mode. Never trade more than you can afford to lose. Past performance does not guarantee future results.
