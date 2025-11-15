# Alpha Sniper V2.2 - Comprehensive Project Report

## Executive Summary

Alpha Sniper V2.2 is an automated cryptocurrency trading bot designed for the MEXC exchange. It operates in both simulation (SIM) and live (LIVE) modes, with advanced risk management, self-learning capabilities, and comprehensive monitoring. The bot is currently deployed and operational on an Ubuntu server, running in SIM mode with a starting equity of $500.

---

## Project Overview

### Purpose
- Automated discovery and execution of cryptocurrency trading opportunities
- Risk-managed position sizing and portfolio management
- Self-learning optimization based on historical performance
- Real-time monitoring and alerting via Telegram

### Current Status
- ✅ **Deployed and Running** on Ubuntu 20.04 server
- ✅ **Mode**: SIM (Simulation with virtual money)
- ✅ **Starting Equity**: $500 (virtual)
- ✅ **Scanner**: Active, checking 58 liquid USDT pairs every 5 minutes
- ✅ **Trader**: Active, checking for trade opportunities every 60 seconds
- ✅ **Health Monitoring**: Operational on port 8090
- ✅ **Telegram Alerts**: Configured and working

### Technology Stack
- **Language**: Python 3.11
- **Framework**: Flask (health check server), Schedule (job scheduler)
- **Database**: SQLite3 (trades.db)
- **Deployment**: Docker + Docker Compose
- **Monitoring**: Telegram Bot API, custom shell scripts
- **API**: MEXC Exchange REST API (public endpoints for SIM mode)

---

## Architecture

### Core Components

#### 1. Scanner (`scanner/scanner.py`)
**Purpose**: Market scanning and opportunity detection

**Process**:
1. Fetches 24-hour ticker data from MEXC API for all USDT pairs
2. Filters by liquidity (minimum 24h volume: $100,000)
3. Checks spread (maximum 0.5% to ensure good liquidity)
4. Selects top 60 pairs by quote volume
5. Computes features for each pair:
   - **RVOL** (Relative Volume): Current volume vs. average
   - **Velocity**: 24-hour price change percentage
   - **Trend**: Price position within 24h high-low range
   - **Orderbook Imbalance**: Bid/ask pressure (optional)
6. Calculates composite signal score (0-100)
7. Stores signals with score ≥ 70 in database

**Current Behavior**:
- Running every 300 seconds (5 minutes)
- Currently finding 0 signals (market conditions don't meet threshold)

#### 2. Trader (`trader/trader.py`)
**Purpose**: Trade execution and position management

**Entry Logic**:
- Fetches unconsumed signals from database (score ≥ 70)
- Checks symbol cooldown (6 hours between trades on same symbol)
- Validates risk constraints (daily drawdown, max positions)
- Checks correlation with existing positions
- Calculates position size based on risk percentage
- Applies "moon shot" multiplier for high-confidence signals (score ≥ 90)
- Executes simulated entry with slippage

**Exit Logic**:
- **Stop Loss**: 5% below entry
- **Take Profit**: 10% above entry
- **Trailing Stop**: Activates at 2% profit, trails by 1%
- **Time Exit**: Closes after 24 hours maximum hold time

**Current Behavior**:
- Running every 60 seconds
- Monitoring 0 open positions
- Waiting for signals from scanner

#### 3. Risk Manager (`risk/risk_manager.py`)
**Purpose**: Enforce risk limits and calculate position sizes

**Key Functions**:
- **Daily Drawdown Check**: Stops trading if daily loss exceeds 2%
- **Position Sizing**: Calculates size based on equity and risk percentage (0.5%)
- **Correlation Check**: Prevents over-concentration in correlated assets
- **Concurrent Position Limit**: Maximum 2 positions at once
- **Per-Trade Limit**: Maximum 20% of equity per trade

#### 4. Learning Module (`learning/self_trainer.py`)
**Purpose**: Self-optimization of signal weights

**Process**:
- Requires minimum 30 trades before activating
- Analyzes last 30 days of trade history
- Performs statistical analysis (Information Coefficient) on features
- Adjusts signal weights if IC is positive
- Limits weight changes to ±15% per iteration
- Sends Telegram alert on significant weight changes

**Current Status**: Inactive (needs 30 trades first)

#### 5. Monitoring (`monitoring/`)
**Components**:
- **Health Check Server** (`healthcheck.py`): Flask server on port 8080, exposes `/health` endpoint
- **Telegram Alerter** (`telegram_alerter.py`): Sends notifications for trades, errors, drawdowns
- **Daily Reporter** (`reporter.py`): Generates daily performance summary at 9:00 UTC
- **Health Check Endpoint** returns:
  ```json
  {
    "status": "healthy",
    "current_equity": 500.0,
    "open_positions_count": 0,
    "daily_pnl": 0,
    "last_scanner_run": "2025-11-15T12:45:07.619186",
    "last_trader_run": "2025-11-15T12:45:42.627921"
  }
  ```

#### 6. Database (`database/models.py`)
**Schema**:
- **trades**: Complete trade history (id, symbol, entry_price, exit_price, pnl_usd, pnl_pct, timestamp, etc.)
- **signals**: Scanner output (symbol, score, features, timestamp)
- **daily_stats**: Daily performance tracking
- **weights**: Learning module weight history

#### 7. Capital Manager (`deployment/capital_manager.py`)
**Purpose**: Determines when to scale up capital based on performance

**Logic**:
- Analyzes last 50 trades
- Checks for consistent profitability
- Suggests capital increases if conditions are favorable
- Runs every hour

---

## Configuration

### Current Settings (`.env`)

```bash
# Trading Mode
MODE=SIM                          # SIM or LIVE
SIM_EQUITY_START=500              # Starting virtual equity
LIVE_EQUITY_START=0               # Not used in SIM mode

# Risk Management
MAX_DAILY_DRAWDOWN_PCT=2.0        # Stop trading if daily loss > 2%
MAX_POSITION_RISK_PCT=0.5         # Risk 0.5% of equity per position
MIN_LIQUIDITY_VOLUME_24H=100000   # Minimum $100k daily volume
MAX_CORRELATED_POSITIONS=2        # Max correlated positions
TRADING_PAUSED=false              # Emergency pause

# Position Management
MAX_CONCURRENT_POS=2              # Max 2 open positions
MAX_PER_TRADE_PCT=20.0            # Max 20% of equity per trade
STOP_LOSS_PCT=5.0                 # 5% stop loss
TAKE_PROFIT_PCT=10.0              # 10% take profit

# Exit Strategy
USE_TRAILING_STOP=true
TRAILING_STOP_ACTIVATION_PCT=2.0  # Activate trailing stop at 2% profit
TRAILING_STOP_DISTANCE_PCT=1.0    # Trail by 1%
MAX_HOLD_TIME_HOURS=24            # Max 24h hold time

# Fees & Slippage
MAKER_FEE_PCT=0.0
TAKER_FEE_PCT=0.1                 # MEXC taker fee
SLIPPAGE_PCT=0.05                 # Expected slippage

# Signal Configuration
MIN_SIGNAL_SCORE=70               # Minimum score to create signal
SYMBOL_COOLDOWN_HOURS=6           # Wait 6h before re-trading symbol
CHECK_ORDER_BOOK_IMBALANCE=true   # Use orderbook data
MOON_SCORE=90                     # High-confidence threshold
MOON_MULT=1.5                     # 1.5x position size for moon shots

# Self-Learning
LEARNING_ENABLED=true
MIN_TRADES_FOR_LEARNING=30
MAX_WEIGHT_CHANGE_PCT=15
LEARNING_LOOKBACK_DAYS=30

# Telegram
TELEGRAM_BOT_TOKEN=8541042711:AAH1kVhxBj8R_8S6kINWg2f3HhjK3aAF-3s
TELEGRAM_CHAT_ID=5809355125
ALERT_ON_DRAWDOWN_PCT=3.0
ALERT_ON_WEIGHT_CHANGE_PCT=10.0
DAILY_REPORT_HOUR=9

# Intervals
SCANNER_INTERVAL=300              # 5 minutes
TRADER_INTERVAL=60                # 1 minute
LEARNING_INTERVAL=3600            # 1 hour
```

---

## Deployment Infrastructure

### Docker Setup
- **Base Image**: python:3.11-slim
- **Installed Tools**: sqlite3, procps, curl (for monitoring)
- **Volumes**:
  - `./data:/app/data` (database persistence)
  - `./logs:/app/logs` (log files)
  - `./backups:/app/backups` (database backups)
- **Port**: 8090:8080 (health check)
- **Restart Policy**: unless-stopped

### Management Scripts

1. **`setup_server.sh`**: Full server setup (Docker, firewall, security, systemd service, log rotation, backups)
2. **`quick_start.sh`**: Quick start with config validation
3. **`monitor.sh`**: Real-time status monitoring (health, logs, stats, trades)
4. **`stats.sh`**: Detailed performance analytics
5. **`rebuild.sh`**: Quick rebuild after code changes
6. **`backup.sh`**: Manual database backup (auto-runs daily at 2 AM)
7. **`stop_trading.sh`**: Emergency stop

### Automation
- **Systemd Service**: Auto-starts bot on server reboot
- **Cron Job**: Daily database backup at 2:00 AM UTC
- **Log Rotation**: Keeps 14 days of logs
- **Backup Retention**: Keeps 30 days of backups

---

## Current Observations

### Scanner Performance
- **Successfully scanning**: 58 liquid USDT pairs from 2096 total pairs
- **Signal generation**: 0 signals created in initial run
- **Filtering**: Aggressive filtering (liquidity + spread + score threshold)
- **API calls**: ~60 calls per scan (orderbook checks for top pairs)

### Issues Identified
1. **No signals generated**: Current market conditions don't meet MIN_SIGNAL_SCORE=70
2. **Potential over-filtering**: May be missing opportunities due to strict thresholds
3. **Orderbook API calls**: Checking orderbook for 60 pairs = higher API usage

### Questions for Optimization

1. **Signal Scoring**:
   - Current weights are hardcoded in `scanner/scorer.py`
   - Is the scoring algorithm optimal?
   - Should we adjust MIN_SIGNAL_SCORE threshold?

2. **Position Sizing**:
   - Current: 0.5% risk per position, max 20% allocation
   - Is this too conservative for SIM mode?
   - Should moon shots (1.5x multiplier) be more/less aggressive?

3. **Exit Strategy**:
   - Stop loss: 5%, Take profit: 10% (2:1 reward:risk)
   - Trailing stop: Activates at 2%, trails by 1%
   - Are these parameters optimal for crypto volatility?

4. **Scanner Efficiency**:
   - Currently checking top 60 pairs by volume
   - Should we increase/decrease this number?
   - Is orderbook imbalance check worth the API calls?

5. **Learning Module**:
   - Requires 30 trades before activation
   - Is this threshold appropriate?
   - Should learning happen more/less frequently?

6. **Correlation Check**:
   - Currently uses crude 24h percent change correlation
   - Should we implement proper correlation coefficients?
   - What lookback period is best?

---

## Known Issues & Limitations

### From CRITICAL_ISSUES.md:

1. **Exchange/API Risk**:
   - MEXC API data could be stale or incorrect
   - No secondary validation or fallback
   - Mitigation: Basic try/except only

2. **Slippage & Fees**:
   - Modeled as fixed percentages (may not reflect reality)
   - SIM mode could be over-optimistic vs. live trading
   - Mitigation: Conservative assumptions (0.1% fee, 0.05% slippage)

3. **Daily Reset Logic**:
   - Relies on container local time (UTC)
   - Timezone mismatches could cause unexpected behavior

4. **Trailing Stop Behavior**:
   - Updates on every highest_price increase
   - Volatile markets may trigger premature exits

5. **Correlation Check**:
   - Uses 24h percent change only (crude proxy)
   - Highly correlated coins might sneak through

6. **Database Schema**:
   - Assumes fresh database
   - Reusing old trades.db could cause schema errors

7. **Capital Scaling**:
   - Uses last 50 trades for analysis
   - Regime changes could cause scaling at wrong time

8. **Learning Module**:
   - Feature indices are hardcoded
   - Schema changes could break learning silently

9. **Emergency Stop**:
   - `stop_trading.sh` sets TRADING_PAUSED but doesn't kill container
   - Must manually run `docker compose down` for full stop

10. **No Backtest Harness**:
    - Cannot replay historical data
    - Must rely on forward SIM testing

---

## Performance Expectations

### SIM Mode Goals (7-14 days):
- Validate bot runs without crashes
- Observe signal generation frequency
- Analyze trade quality and P&L distribution
- Check for any bugs or unexpected behavior
- Tune parameters based on SIM results

### Success Metrics:
- **Win Rate**: Target >50% (current baseline unknown)
- **Profit Factor**: Target >1.5 (gross profit / gross loss)
- **Max Drawdown**: Stay within 2% daily limit
- **Sharpe Ratio**: Positive risk-adjusted returns
- **Uptime**: 99%+ availability

---

## Questions for ChatGPT

### Strategy Optimization:
1. Are the current signal scoring weights logical for crypto markets?
2. Should we use different parameters for different market conditions (trending vs. ranging)?
3. Is a 2:1 reward:risk ratio (10% TP, 5% SL) appropriate for crypto volatility?
4. Should we implement multiple timeframe analysis?

### Risk Management:
1. Is 0.5% risk per trade too conservative? Should it scale with confidence?
2. Should we implement a "maximum portfolio heat" constraint?
3. How should correlation be properly measured for crypto pairs?
4. Should we have different risk settings for SIM vs. LIVE?

### Technical Implementation:
1. Should we add rate limiting for MEXC API calls to avoid bans?
2. Is SQLite appropriate or should we migrate to PostgreSQL?
3. Should we implement a proper backtesting framework?
4. How can we improve the learning module's reliability?

### Market Analysis:
1. What additional features should we calculate? (RSI, MACD, volume profile?)
2. Should we filter by market cap or other fundamental data?
3. How do we handle flash crashes and extreme volatility?
4. Should we implement time-of-day filters (avoid low liquidity periods)?

### Deployment & Monitoring:
1. What additional monitoring/alerting should we implement?
2. Should we log more granular data for analysis?
3. How can we improve the health check to detect subtle issues?
4. What disaster recovery procedures should we have?

### Moving to LIVE:
1. What additional safeguards should we implement before going live?
2. How should we handle API keys securely for live trading?
3. What starting capital is recommended for live trading?
4. Should we implement a "paper trading" mode that mirrors live but doesn't execute?

---

## Recent Development History

### Successfully Implemented:
- ✅ Complete server setup automation
- ✅ Docker containerization with all dependencies
- ✅ Comprehensive monitoring scripts
- ✅ Telegram integration for alerts
- ✅ Health check endpoint
- ✅ Database persistence with automatic backups
- ✅ Log rotation and management
- ✅ Emergency stop procedures
- ✅ Real-time logging with flush=True for immediate output
- ✅ Fixed all Docker warnings and errors
- ✅ Proper error handling throughout main loop

### Current Deployment:
- Server: Ubuntu 20.04 on AWS EC2 (or similar)
- Container: Running successfully since last rebuild
- Status: Healthy, monitoring markets, waiting for signals

---

## Code Quality & Maintainability

### Strengths:
- Clear separation of concerns (scanner, trader, risk, learning)
- Configuration via environment variables
- Comprehensive error handling in main loop
- Good documentation (README, DEPLOYMENT_GUIDE, CRITICAL_ISSUES)
- Automated deployment scripts

### Areas for Improvement:
- Limited unit test coverage (`tests/` directory is mostly empty)
- No integration tests
- Hardcoded magic numbers in some places
- Learning module needs more robust error handling
- No proper logging framework (using print statements)

---

## Request for Advice

I'm seeking advice on:

1. **Strategy Improvements**: How to improve signal quality and trade frequency
2. **Risk Optimization**: Better position sizing and portfolio management
3. **Technical Enhancements**: Code quality, testing, reliability
4. **Performance Tuning**: Parameter optimization based on crypto market characteristics
5. **Production Readiness**: What's missing before going live with real money
6. **Monitoring & Alerts**: What additional metrics should I track
7. **API Usage**: Best practices for exchange API interaction
8. **Machine Learning**: Better approach to self-learning optimization

**Current Pain Point**: Scanner finds 0 signals. Is this because:
- Market conditions are genuinely poor?
- Thresholds are too strict?
- Scoring algorithm is flawed?
- Need different features/indicators?

Please provide specific, actionable recommendations for improving this trading bot.

---

## Appendix: File Structure

```
alpha-sniper-v2.2/
├── config/
│   ├── __init__.py
│   └── config.py                 # Configuration loader
├── database/
│   ├── __init__.py
│   └── models.py                 # Database operations
├── deployment/
│   ├── backup.sh                 # Database backup script
│   ├── capital_manager.py        # Capital scaling logic
│   ├── DEPLOYMENT_GUIDE.md       # Complete deployment docs
│   ├── monitor.sh                # Status monitoring script
│   ├── preflight_checklist.md    # Pre-deployment checklist
│   ├── quick_start.sh            # Quick start script
│   ├── README.md                 # Deployment scripts documentation
│   ├── rebuild.sh                # Quick rebuild script
│   ├── setup_server.sh           # Full server setup automation
│   ├── stats.sh                  # Performance statistics script
│   └── stop_trading.sh           # Emergency stop script
├── learning/
│   ├── __init__.py
│   └── self_trainer.py           # Self-learning optimization
├── monitoring/
│   ├── __init__.py
│   ├── healthcheck.py            # Health check Flask server
│   ├── reporter.py               # Daily report generation
│   └── telegram_alerter.py       # Telegram notification sender
├── risk/
│   ├── __init__.py
│   ├── daily_reset.py            # Daily stat reset logic
│   └── risk_manager.py           # Risk management functions
├── scanner/
│   ├── __init__.py
│   ├── orderbook.py              # Orderbook analysis
│   ├── scanner.py                # Market scanning logic
│   └── scorer.py                 # Signal scoring algorithm
├── tests/
│   ├── __init__.py
│   └── backtest.py               # Placeholder for backtesting
├── trader/
│   ├── __init__.py
│   └── trader.py                 # Trade execution logic
├── .env                          # Configuration (not in git)
├── .env.example                  # Example configuration
├── .gitignore
├── CRITICAL_ISSUES.md            # Known risks and limitations
├── docker-compose.yml            # Docker Compose configuration
├── Dockerfile                    # Docker image definition
├── main.py                       # Entry point
├── README.md                     # Project overview
└── requirements.txt              # Python dependencies
```

---

**Document Version**: 1.0
**Date**: November 15, 2025
**Status**: Bot deployed and operational in SIM mode
**Next Review**: After 7 days of SIM trading or first 10 trades
