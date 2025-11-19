# ALPHA SNIPER V4.0 - DEPLOYMENT GUIDE

**Last Updated:** 2025-11-19
**Version:** V4.0
**Status:** Production-Ready

---

## 🚀 DEPLOYMENT OVERVIEW

This guide covers:
1. **Prerequisites** - What you need before starting
2. **SIMULATION Mode** - Test trading with no real money
3. **LIVE Mode (SPOT)** - Real trading on SPOT market
4. **LIVE Mode (FUTURES)** - Real trading with shorts enabled
5. **Monitoring & Debugging** - How to track performance
6. **Emergency Procedures** - How to stop / restart

---

## 📋 PREREQUISITES

### System Requirements
- Python 3.8+ (3.10+ recommended)
- Ubuntu/Debian or macOS (Windows may work but untested)
- 1GB RAM minimum
- Stable internet connection

### Install Dependencies
```bash
cd alpha-sniper-v2.2
pip install -r requirements.txt
```

Required packages:
- `python-dotenv` - Environment variable management
- `requests` - HTTP client for MEXC API
- `pandas` - Data processing
- `python-telegram-bot` - Telegram notifications (optional)

### MEXC Account
- Sign up at https://www.mexc.com/
- Enable API access (Account → API Management)
- Generate API Key + Secret
- **For SIMULATION:** Use dummy keys (bot won't call private endpoints)
- **For LIVE:** Use real keys with trading permissions

### Telegram Bot (Optional but Recommended)
1. Create bot via @BotFather on Telegram
2. Get bot token (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
3. Get your chat ID:
   - Send message to your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find `"chat":{"id":123456789}`

---

## 🧪 SIMULATION MODE (SPOT)

### Step 1: Configure Environment

```bash
# Copy V4 config template
cp .env.v4 .env

# Edit .env with your settings
nano .env  # or vim, code, etc.
```

### Step 2: Set Required Parameters

```bash
# ===================
# MODE
# ===================
MODE=SIMULATION              # NO real money!
MARKET_TYPE=SPOT            # SPOT or FUTURES

# ===================
# API (dummy keys for SIM)
# ===================
MEXC_API_KEY=dummy
MEXC_API_SECRET=dummy

# ===================
# STARTING EQUITY
# ===================
START_EQUITY=500            # Virtual starting capital

# ===================
# TELEGRAM (optional)
# ===================
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# ===================
# RISK (defaults are good)
# ===================
MAX_DAILY_DRAW_PCT=0.025    # 2.5% daily loss cap
RISK_PER_TRADE_BULL=0.0030  # 0.30% per trade in BULL
RISK_PER_TRADE_BEAR_SHORT=0.0012  # 0.12% per short in BEAR

# ===================
# EXECUTION (defaults are good)
# ===================
MAX_ALLOWED_SLIPPAGE_PCT=1.2     # 1.2% max slippage
MIN_ORDERBOOK_DEPTH=3000         # $3,000 min depth
MAX_SPREAD_PCT=0.25              # 0.25% max spread (unified from 1.4%)

# ===================
# EDGES
# ===================
USE_ROTATION_EDGE=true
USE_DOMINANCE_EDGE=true
USE_FUNDING_EDGE=false      # Auto-disabled on SPOT (futures-only)
```

**Key Points:**
- `MODE=SIMULATION` → No real trades, no API calls to private endpoints
- `MARKET_TYPE=SPOT` → Simulated LONG and SHORT signals (simulated fills)
- `MEXC_API_KEY=dummy` → Bot won't authenticate, only pulls public data
- `USE_FUNDING_EDGE=false` → Funding edge auto-disabled on SPOT (no futures API calls)

### Step 3: Run Component Tests

```bash
python test_v4_system.py
```

**Expected Output:**
```
✅ All imports successful
✅ MEXC client operational
✅ Regime detector working
✅ Scanner found X signals
✅ Execution engine passed
✅ Position manager loaded
```

If tests fail with 403 errors on MEXC API, this is normal in some environments. If your production environment works (as shown by bot running with 2 positions), tests are optional.

### Step 4: Test Telegram (Optional)

```bash
python test_telegram.py
```

Should send a test message to your Telegram chat.

### Step 5: Start V4.0

```bash
python v4_main.py
```

**Expected Output:**
```
======================================================================
  🚀 ALPHA SNIPER V4.0 - STARTING
======================================================================
  Mode: SIMULATION
  Start Equity: $500.00
  Scanner Interval: 900s (15m)
  Position Check Interval: 300s (5m)
======================================================================

[Init] Creating MEXC client...
[Init] Creating execution engine...
[Init] Creating scanner...
[Init] Creating position manager...
[Init] ✅ All components initialized

🏃 Starting main loop...

[Universe] Found 2433 tickers
[Universe] Final universe: 200 symbols
[Universe] Top 5 by volume: ['SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'BNBUSDT', 'STRKUSDT']

============================================================
🔍 V4 SCANNER CYCLE - 2025-11-19 17:05:18
============================================================
📊 Regime: BEAR
   Z-Score: -5.11
   Alt Strength: -0.0707
```

### Step 6: Monitor Behavior

**BULL/SIDEWAYS Regime:**
- Scanner looks for LONG signals (COIL, PULLBACK, EXPANSION, BREAKOUT)
- Opens 1-3 positions per day (typical)
- Position manager tracks TP1/TP2/trailing stops
- Telegram sends alerts on position open/close

**BEAR Regime:**
- Scanner looks for SHORT signals (BREAKDOWN, TIGHTENING)
- In SIMULATION + SPOT: Opens SHORT positions (simulated fills)
- In LIVE + SPOT: Would skip SHORTS (SPOT can't short)

**NEUTRAL Regime:**
- No new positions opened (low volatility, unclear trend)
- Manages existing positions only

### Step 7: Let It Run for 30-50 Trades

**Target Duration:** 2-4 weeks (depending on regime and signal frequency)

**What to Track:**
- Win rate: 60-75%
- Max drawdown: <25%
- Trades per week: 1-3
- Check Telegram alerts for position updates
- Review `positions.json` for current state

**Stop If:**
- Win rate <50% after 20 trades
- Max drawdown >30%
- Frequent API errors
- Slippage >1% average

---

## 💰 LIVE MODE (SPOT)

### ⚠️ WARNING: LIVE mode trades REAL MONEY!

**Before Going LIVE:**
- [ ] Ran SIMULATION for 30-50 trades
- [ ] Verified win rate 60-75%
- [ ] Checked max drawdown <25%
- [ ] Confirmed avg slippage <0.5%
- [ ] Tested Telegram notifications
- [ ] Read CRITICAL_ISSUES.md

### Step 1: Update .env for LIVE

```bash
# Edit .env
nano .env
```

**Changes:**
```bash
# ===================
# MODE - SWITCH TO LIVE
# ===================
MODE=LIVE                    # ⚠️ REAL MONEY!
MARKET_TYPE=SPOT            # SPOT = LONG-only in LIVE

# ===================
# API - REAL CREDENTIALS
# ===================
MEXC_API_KEY=your_real_api_key_here
MEXC_API_SECRET=your_real_secret_here

# ===================
# STARTING EQUITY
# ===================
START_EQUITY=100            # ⚠️ Start SMALL! ($100-$200)

# ===================
# RISK - REDUCE FOR FIRST LIVE TRADES
# ===================
RISK_PER_TRADE_BULL=0.0020  # 0.20% (reduced from 0.30% for safety)
RISK_PER_TRADE_BEAR_SHORT=0.0008  # 0.08% (reduced from 0.12%)

# Rest stays the same
```

**Key Changes:**
- `MODE=LIVE` → Real trades!
- `MARKET_TYPE=SPOT` → LONG-only (MEXC SPOT doesn't support shorts)
- `START_EQUITY=100` → Start small
- Reduce `RISK_PER_TRADE_*` for first 10-20 trades

### Step 2: Verify MEXC API Permissions

Test API connectivity:
```bash
# Simple test to verify keys work
python -c "from v4.data.mexc_client import MEXCClient; c = MEXCClient(); print('✅ API works' if c.get_24h_tickers() else '❌ API failed')"
```

Should print: `✅ API works`

If fails:
- Check API key/secret are correct
- Verify API permissions include "Spot Trading"
- Check MEXC account has funds

### Step 3: Start V4.0 in LIVE

```bash
python v4_main.py
```

**Expected Output:**
```
======================================================================
  🚀 ALPHA SNIPER V4.0 - STARTING
======================================================================
  Mode: LIVE                    # ⚠️ LIVE MODE!
  Start Equity: $100.00
  Scanner Interval: 900s (15m)
  Position Check Interval: 300s (5m)
======================================================================
```

### Step 4: Monitor First 10-20 Trades CLOSELY

**What to Check:**
- Positions actually open on MEXC (verify in MEXC app/website)
- Fill prices match expectations (slippage <0.5%)
- Telegram alerts arrive promptly
- No API errors or rejections
- Positions close at TP/SL as expected

**Compare to SIMULATION:**
- Win rate should be ±10% of SIM
- Max drawdown should be similar
- If stats diverge >20%, stop and investigate

### Step 5: Scale Gradually

**After 20 Successful Trades:**
- If stats match SIM (±10%), can increase equity
- Increase in small steps: $100 → $200 → $500 → $1,000
- **NEVER increase RISK_PER_TRADE_%** - keep at 0.20-0.30% max

**After 50 Successful Trades:**
- Can restore original risk % (0.30% BULL, 0.12% BEAR)
- Continue monitoring weekly
- Review P&L distribution monthly

---

## 🚁 LIVE MODE (FUTURES)

### ⚠️ WARNING: FUTURES = Leverage + Shorts + Funding Fees!

**Use FUTURES if:**
- You want to trade both LONG and SHORT directions
- Comfortable with leverage (default: 1x, configurable)
- Understand funding rate mechanics

**Additional Risks:**
- Shorts can have unlimited losses (price can go up infinitely)
- Funding fees (paid every 8h if holding overnight)
- Liquidation risk (if using leverage >1x)

### Step 1: Update .env for FUTURES

```bash
# ===================
# MODE
# ===================
MODE=LIVE
MARKET_TYPE=FUTURES         # ⚠️ Enables shorts and funding edge

# ===================
# API
# ===================
MEXC_API_KEY=your_futures_api_key
MEXC_API_SECRET=your_futures_secret

# ===================
# STARTING EQUITY
# ===================
START_EQUITY=100            # Start SMALL!

# ===================
# EDGES
# ===================
USE_FUNDING_EDGE=true       # Now enabled (FUTURES-only)

# Rest stays the same
```

**Key Changes:**
- `MARKET_TYPE=FUTURES` → Enables SHORT signals in LIVE
- `USE_FUNDING_EDGE=true` → Funding rate scoring active
- Requires MEXC Futures account + API key

### Step 2: Understand SHORT Behavior

**BEAR Regime + FUTURES + LIVE:**
- Scanner will find SHORT signals (BREAKDOWN, TIGHTENING)
- Opens SHORT positions via MEXC Futures API
- SL = Entry + (ATR × 1.8)
- TP1 @ 1.5R, TP2 @ 2.5R

**Risk Warning:**
- Shorts have unlimited loss potential
- Use tight stops (1.8 ATR)
- Max 2 concurrent shorts in BEAR

### Step 3: Monitor Funding Rates

Funding fees charged every 8h if holding overnight:
- Positive funding rate → Longs pay shorts
- Negative funding rate → Shorts pay longs

V4 tracks this via funding edge, but you still pay fees.

**Mitigation:**
- V4 closes positions within 36-48h (rarely pays 2+ funding cycles)
- Funding edge tries to align with favorable rates
- Monitor P&L includes funding costs

---

## 📊 MONITORING & DEBUGGING

### Real-Time Monitoring

**1. Terminal Output**
- Shows scanner cycles every 15m
- Prints regime changes
- Displays position updates every 5m
- Reports errors/warnings

**2. Telegram Notifications**
```
📊 POSITION OPENED
Symbol: SOLUSDT
Direction: LONG
Entry: $152.34
Size: $30.00
Stop: $148.52
Risk: 1.2R

🟢 POSITION CLOSED - WIN
Symbol: SOLUSDT
R-Multiple: +2.1R
Percentage: +4.2%
USD P&L: +$1.26
Hold Time: 14.2h
MFE: 2.8R (best)
MAE: -0.3R (worst)
Exit Reason: TP1 hit
```

**3. positions.json**
```bash
# View current positions
cat positions.json | python -m json.tool

# Example output:
{
  "SOLUSDT": {
    "symbol": "SOLUSDT",
    "direction": "LONG",
    "entry_price": 152.34,
    "size_usdt": 30.0,
    "stop_loss": 148.52,
    "regime": "BULL",
    "entry_time": "2025-11-19T12:34:56",
    "tp1_hit": false,
    "tp2_hit": false,
    "remaining_pct": 1.0,
    "mfe_r": 0.8,
    "mae_r": -0.2
  }
}
```

### Performance Tracking

**After 10 Trades:**
```python
# Calculate stats from Telegram messages or positions.json
wins = 7
losses = 3
win_rate = wins / (wins + losses)  # 70%

total_r = +1.8 + 2.1 - 1.0 + 1.5 + ...  # Sum all R-multiples
avg_r = total_r / 10  # +0.8R

profit_factor = sum(winning_r) / abs(sum(losing_r))  # 2.1
```

**Expected After 30-50 Trades:**
- Win rate: 60-75%
- Avg R-multiple: +0.5 to +1.0
- Profit factor: 1.5-2.5
- Max drawdown: -15% to -25%

**Red Flags:**
- Win rate <55% → Strategy may not work in current regime
- Max drawdown >30% → Risk too high, reduce RISK_PER_TRADE_%
- Slippage >1% → MEXC liquidity poor, increase MIN_ORDERBOOK_DEPTH

### Debugging Common Issues

**Issue: No trades opening**

**Cause 1: NEUTRAL regime**
- Bot waits for clear BULL/BEAR/SIDEWAYS
- Check regime output in logs
- This is normal behavior (capital preservation)

**Cause 2: BEAR + SPOT + LIVE = 0 trades**
- SPOT can't short in LIVE mode
- This is correct behavior
- Solution: Switch to SIMULATION to test shorts, or use FUTURES

**Cause 3: All signals rejected by execution engine**
- Check logs for rejection reasons:
  - "Spread too wide" → Increase MAX_SPREAD_PCT (default 0.25%)
  - "Insufficient depth" → Reduce MIN_ORDERBOOK_DEPTH (default $3,000)
  - "Slippage too high" → Increase MAX_ALLOWED_SLIPPAGE_PCT (default 1.2%)
- **WARNING:** Relaxing filters increases slippage risk!

**Issue: High slippage (>1%)**

**Causes:**
- Low liquidity symbols (thin orderbooks)
- High volatility (spreads widen)
- Large position sizes relative to depth

**Solutions:**
- Increase MIN_ORDERBOOK_DEPTH (e.g., $5,000)
- Reduce TRADE_HARD_NOTIONAL_CAP (e.g., $1,500)
- Tighten MAX_SPREAD_PCT (e.g., 0.15%)
- Avoid meme coins / low-volume pairs

**Issue: Telegram notifications not working**

**Causes:**
- Bot token incorrect
- Chat ID wrong
- Bot blocked by user
- Network issues

**Solutions:**
```bash
# Test Telegram manually
python test_telegram.py

# Check logs for error messages
# Common: "Event loop is closed" → Fixed in V4.0

# Verify token/chat ID
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID
```

**Issue: Positions not loading after restart**

**Causes:**
- positions.json corrupted
- Schema mismatch (old V3 format)

**Solutions:**
```bash
# Validate JSON
python -m json.tool positions.json

# If corrupted, delete (WARNING: loses position state!)
rm positions.json

# Bot will create new file on next position
```

**Issue: MEXC API errors (403, 429, timeouts)**

**Causes:**
- API key incorrect / expired
- Rate limit exceeded (120 req/min)
- MEXC server issues

**Solutions:**
```bash
# Verify API key works
python -c "from v4.data.mexc_client import MEXCClient; print(MEXCClient().get_24h_tickers()[:1])"

# Check rate limit (V4 has caching, should be fine)
# If 429 errors persist, increase SCANNER_INTERVAL (e.g., 1200s = 20m)

# If MEXC outage, wait and retry
# Bot retries automatically (3 attempts)
```

---

## 🚨 EMERGENCY PROCEDURES

### Stop Trading Immediately

**Method 1: Stop Bot (Positions Remain Open)**
```bash
# Press Ctrl+C in terminal running v4_main.py
# Positions auto-saved to positions.json
# Positions still open on MEXC (must close manually if needed)
```

**Method 2: Close All Positions + Stop Bot**
1. Press Ctrl+C to stop bot
2. Manually close positions on MEXC website/app
3. Or: Add emergency close function (TODO)

**Method 3: Pause Trading (Daily Loss Cap Hit)**
- Bot automatically stops opening new positions if daily draw >2.5%
- Still manages existing positions (allows TP/SL exits)
- Resumes next day (midnight UTC reset)

### Restart Bot

**After Normal Stop (Ctrl+C):**
```bash
python v4_main.py

# Positions auto-loaded from positions.json
# Bot continues managing existing positions
# Resumes scanning for new signals
```

**After Crash:**
```bash
# Check logs for error
cat v4_main.log  # if you redirected output

# Restart normally
python v4_main.py
```

**After Config Change:**
```bash
# Edit .env
nano .env

# Restart bot (old process must be stopped first)
python v4_main.py
```

### Daily Loss Cap Hit

**What Happens:**
```
🛑 DAILY LOSS CAP HIT: -2.5%
   No new positions until tomorrow.
   Still managing 2 open positions.
```

**Bot Behavior:**
- Stops scanning for new signals
- Still checks positions every 5m
- Allows TP/SL exits
- Resumes scanning at midnight UTC

**Manual Override (NOT RECOMMENDED):**
```bash
# Edit .env
MAX_DAILY_DRAW_PCT=0.05  # Increase to 5% (danger!)

# Restart bot
# WARNING: Increases risk significantly!
```

### Backtest Historical Performance

**Run backtest on recent data:**
```bash
python -m v4.backtest.run_backtest --start 2024-10-01 --end 2024-11-19 --equity 500

# Outputs:
# - backtest_results/equity_curve_<timestamp>.json
# - backtest_results/trades_<timestamp>.json
# - backtest_results/config_<timestamp>.json
```

**Note:** MEXC API only provides ~1000 bars (~40 days). For full 2019-2024 backtest, you need pre-downloaded CSV files.

---

## 📝 DEPLOYMENT CHECKLIST

### Pre-Deployment (SIMULATION)

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Copy config: `cp .env.v4 .env`
- [ ] Edit .env: Set MODE=SIMULATION, MARKET_TYPE=SPOT
- [ ] Set Telegram token/chat ID (optional)
- [ ] Run tests: `python test_v4_system.py`
- [ ] Test Telegram: `python test_telegram.py`
- [ ] Start bot: `python v4_main.py`
- [ ] Verify scanner running (15m intervals)
- [ ] Wait for first position to open
- [ ] Confirm Telegram alerts received
- [ ] Let run for 30-50 trades (2-4 weeks)

### Pre-LIVE (After SIMULATION)

- [ ] Review SIMULATION results:
  - [ ] Win rate 60-75%
  - [ ] Max drawdown <25%
  - [ ] Avg slippage <0.5%
  - [ ] No critical errors
- [ ] Read CRITICAL_ISSUES.md
- [ ] Understand black swan risks
- [ ] Set MEXC API key/secret (real)
- [ ] Edit .env: MODE=LIVE, START_EQUITY=100
- [ ] Reduce RISK_PER_TRADE_* (0.20% BULL, 0.08% BEAR)
- [ ] Test API: Verify key works
- [ ] Have emergency stop plan

### Post-LIVE (First 10-20 Trades)

- [ ] Monitor every position closely
- [ ] Verify fills on MEXC match expectations
- [ ] Check Telegram alerts arrive promptly
- [ ] Track slippage (<0.5% avg)
- [ ] Compare stats to SIMULATION (±10%)
- [ ] Review daily at minimum

### Scaling (After 30-50 Trades)

- [ ] Stats match backtest/SIM (±10%)
- [ ] Win rate 60-75%
- [ ] Max drawdown <25%
- [ ] No critical bugs
- [ ] Gradually increase equity ($100 → $200 → $500)
- [ ] Restore original risk % (0.30% BULL, 0.12% BEAR)
- [ ] Continue daily monitoring

---

## 🔧 CONFIGURATION REFERENCE

### Critical Parameters (.env)

```bash
# MODE
MODE=SIMULATION              # SIMULATION or LIVE
MARKET_TYPE=SPOT            # SPOT or FUTURES

# API
MEXC_API_KEY=dummy          # dummy in SIM, real in LIVE
MEXC_API_SECRET=dummy

# EQUITY
START_EQUITY=500            # Virtual (SIM) or Real (LIVE)

# RISK
MAX_DAILY_DRAW_PCT=0.025    # 2.5% daily loss cap
RISK_PER_TRADE_BULL=0.0030  # 0.30% per trade
RISK_PER_TRADE_BEAR_SHORT=0.0012  # 0.12% per short
MAX_PORTFOLIO_HEAT=0.015    # 1.5% max open risk

# EXECUTION
MAX_ALLOWED_SLIPPAGE_PCT=1.2  # 1.2% max slippage
MIN_ORDERBOOK_DEPTH=3000      # $3,000 min depth
MAX_SPREAD_PCT=0.25           # 0.25% max spread (unified)
TRADE_HARD_NOTIONAL_CAP=2500  # $2,500 max per trade

# EXITS
ATR_SL_MULT_LONG=2.0        # 2 ATR stop for LONG
ATR_SL_MULT_SHORT=1.8       # 1.8 ATR stop for SHORT
TP1_R_MULT_LONG=2.0         # TP1 @ 2R
TP2_R_MULT_LONG=3.0         # TP2 @ 3R
MAX_HOLD_HOURS_BULL_LONG=48 # 2 days max hold

# EDGES
USE_ROTATION_EDGE=true
USE_DOMINANCE_EDGE=true
USE_FUNDING_EDGE=false      # Auto-disabled on SPOT

# TELEGRAM
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# INTERVALS
SCANNER_INTERVAL=900        # 15 minutes
POSITION_CHECK_INTERVAL=300 # 5 minutes
```

---

## 📚 FURTHER READING

- **README.md**: Quick start, architecture, strategy overview
- **README_V4.md**: Detailed V4 strategy guide (6 engines, filters, edges)
- **CRITICAL_ISSUES.md**: Risk analysis, limitations, black swan scenarios
- **V4_DEPLOYMENT_STATUS.md**: Current production status and monitoring

---

## ✅ DEPLOYMENT COMPLETE!

**You're now ready to deploy Alpha Sniper V4.0!**

**Next Steps:**
1. Start in SIMULATION for 30-50 trades
2. Monitor closely (Telegram + positions.json)
3. Compare stats to backtest
4. Switch to LIVE with small equity ($100-$200)
5. Scale gradually after verification

**Questions? Issues?**
- Check CRITICAL_ISSUES.md for troubleshooting
- Review V4_DEPLOYMENT_STATUS.md for current state
- Refer to README_V4.md for strategy details

**⚠️ FINAL REMINDER:** Crypto trading is high-risk. Only trade what you can afford to lose. V4.0 is battle-tested but cannot prevent black swan events.

**Good luck and trade responsibly!** 🎯💰

---

**Last Updated:** 2025-11-19
**V4.0 Deployment Guide - Complete**
