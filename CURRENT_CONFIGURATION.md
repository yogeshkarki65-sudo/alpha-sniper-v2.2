# ALPHA SNIPER V2.2 - CURRENT CONFIGURATION SUMMARY

**Generated:** November 14, 2025
**Mode:** SIMULATION (Paper Trading)
**Exchange:** MEXC

---

## 🎯 TRADING MODE

| Setting | Value | Description |
|---------|-------|-------------|
| **MODE** | `SIM` | **Simulation mode** - Paper trading, no real money |
| **SIM_EQUITY_START** | `$500` | Starting virtual balance |
| **TRADING_PAUSED** | `false` | Bot is active and running |

---

## 💰 RISK MANAGEMENT

| Setting | Value | What It Means |
|---------|-------|---------------|
| **MAX_DAILY_DRAWDOWN_PCT** | `2.0%` | Bot stops trading if you lose 2% in one day |
| **MAX_POSITION_RISK_PCT** | `0.5%` | Each trade risks max 0.5% of equity |
| **MIN_LIQUIDITY_VOLUME_24H** | `$100,000` | Only trade coins with >$100k daily volume |
| **MAX_CORRELATED_POSITIONS** | `2` | Max 2 positions in correlated assets |
| **MAX_CONCURRENT_POS** | `2` | Maximum 2 open positions at once |

**Risk Assessment:** ✅ **CONSERVATIVE** - Good for beginners and testing

---

## 📊 POSITION SIZING

| Setting | Value | Calculation |
|---------|-------|-------------|
| **Per Trade** | ~20% of equity | $100 per trade (at $500 equity) |
| **Stop Loss** | 5% from entry | Exit if price drops 5% |
| **Take Profit** | 10% from entry | Exit if price rises 10% |

**Example Trade:**
- Entry: $1.00
- Position Size: $100 (100 coins)
- Stop Loss: $0.95 (5% down)
- Take Profit: $1.10 (10% up)
- Max Loss: $5
- Max Gain: $10

---

## 🎯 EXIT STRATEGY

| Setting | Value | Description |
|---------|-------|-------------|
| **USE_TRAILING_STOP** | `true` | Locks in profits as price rises |
| **TRAILING_STOP_ACTIVATION_PCT** | `2.0%` | Activates after 2% gain |
| **TRAILING_STOP_DISTANCE_PCT** | `1.0%` | Trails 1% below highest price |
| **MAX_HOLD_TIME_HOURS** | `24` | Force exit after 24 hours |

**Example:**
1. Buy at $1.00
2. Price rises to $1.02 (2%) → Trailing stop activates
3. Price rises to $1.05 → Trailing stop at $1.04 (1% below)
4. Price drops to $1.04 → **SOLD** (locked in 4% gain)

---

## 🔍 SIGNAL GENERATION

| Setting | Value | Impact |
|---------|-------|--------|
| **MIN_SIGNAL_SCORE** | `70` | **High bar** - Only takes quality setups |
| **SYMBOL_COOLDOWN_HOURS** | `6` | Can't retrade same coin for 6 hours |
| **CHECK_ORDER_BOOK_IMBALANCE** | `true` | Checks buy/sell pressure |
| **MOON_SCORE** | `90` | "Home run" trade threshold |
| **MOON_MULT** | `1.5x` | Increases position size by 50% for exceptional setups |

**Scoring Components:**
- **RVOL** (Relative Volume): Is trading volume higher than normal?
- **Velocity**: How fast is price moving? (% change in 24h)
- **Trend**: Where is price in its 24h range? (0-1 scale)
- **Orderbook Imbalance**: More buyers or sellers?

**Current Market:** Highest score = 62.2 → **NO SIGNALS** (below 70 threshold)

---

## 💸 FEES & COSTS

| Setting | Value | Annual Cost |
|---------|-------|-------------|
| **TAKER_FEE_PCT** | `0.1%` | MEXC standard fee |
| **SLIPPAGE_PCT** | `0.05%` | Market impact estimate |
| **Total Per Trade** | `~0.30%` | Round-trip cost (entry + exit) |

**Example on $100 trade:**
- Entry fee: $0.10
- Exit fee: $0.10
- Slippage: $0.10
- **Total cost: $0.30**

---

## 🧠 SELF-LEARNING

| Setting | Value | Purpose |
|---------|-------|---------|
| **LEARNING_ENABLED** | `true` | Bot adjusts scoring weights based on results |
| **MIN_TRADES_FOR_LEARNING** | `30` | Needs 30 trades before adjusting |
| **MAX_WEIGHT_CHANGE_PCT** | `15%` | Won't change weights by more than 15% |
| **LEARNING_LOOKBACK_DAYS** | `30` | Uses last 30 days of data |

**How it works:**
1. Bot trades for 30+ trades
2. Analyzes which features predicted winners
3. Adjusts scoring weights (e.g., if high RVOL predicted wins, increase RVOL weight)
4. Caps changes at 15% to prevent overfitting

**Status:** Not active yet (need 30 trades first)

---

## ⏱️ SCHEDULE

| Task | Frequency | Purpose |
|------|-----------|---------|
| **Scanner** | Every 5 minutes (300s) | Find new trading opportunities |
| **Trader** | Every 1 minute (60s) | Check positions, execute exits |
| **Learning** | Every 1 hour (3600s) | Adjust weights if conditions met |
| **Daily Report** | 9:00 AM UTC | Send Telegram summary |

---

## 📱 ALERTS & MONITORING

| Setting | Value | Trigger |
|---------|-------|---------|
| **TELEGRAM_BOT_TOKEN** | *(configured)* | For sending alerts |
| **TELEGRAM_CHAT_ID** | *(configured)* | Your Telegram chat |
| **ALERT_ON_DRAWDOWN_PCT** | `3.0%` | Alert if daily loss hits 3% |
| **ALERT_ON_WEIGHT_CHANGE_PCT** | `10.0%` | Alert when learning changes weights >10% |
| **DAILY_REPORT_HOUR** | `9` | Daily report at 9 AM UTC |

**You'll receive Telegram alerts for:**
- Bot startup/shutdown
- Trade entries
- Trade exits (with P&L)
- Daily performance reports
- Risk limit warnings
- Learning weight changes

---

## 🎲 CURRENT MARKET CONDITIONS

Based on latest scan:

| Metric | Value | Assessment |
|--------|-------|------------|
| **Coins Scanned** | 2,095 total | Full MEXC USDT market |
| **Passed Filters** | 59 coins | Good liquidity pool |
| **Highest Score** | 62.2 (ASTERUSDT) | Below threshold |
| **Signals Generated** | 0 | Market too quiet |
| **Best Velocity** | 0.29% (STRKUSDT) | Very low volatility |

**Conclusion:** Market is in consolidation. Bot is correctly waiting for better setups.

---

## ⚙️ CONFIGURATION PHILOSOPHY

### Conservative Settings (Current)
✅ **Pros:**
- Lower risk of large losses
- Only takes high-quality setups
- Good for learning and testing
- Protects capital during quiet markets

⚠️ **Cons:**
- Fewer trading opportunities
- May miss some profitable moves
- Requires volatile markets to trigger

### More Aggressive Alternative
If you wanted more trades, you could:
- Lower `MIN_SIGNAL_SCORE` to 50-60
- Increase `MAX_CONCURRENT_POS` to 3-5
- Reduce `SYMBOL_COOLDOWN_HOURS` to 3
- Increase `MAX_POSITION_RISK_PCT` to 1.0%

**Recommendation:** Keep current settings until you have 30+ trades, then review performance.

---

## 📈 EXPECTED PERFORMANCE

With current settings in **normal** market conditions:

| Metric | Conservative Estimate |
|--------|----------------------|
| **Trades per Day** | 1-3 trades |
| **Win Rate Target** | 55-65% |
| **Average Hold Time** | 4-12 hours |
| **Sharpe Ratio Goal** | >1.5 |
| **Max Drawdown** | <5% |

**In Current Market (quiet):**
- Trades per day: 0-1
- Bot is being patient ✅

---

## 🔐 VERSION TRACKING

| Component | Version | Commit |
|-----------|---------|--------|
| **Bot Version** | 2.2.0 | dd2c56d |
| **Deployment** | Zero-trust validation enabled | ✅ |
| **Health Endpoint** | http://localhost:8090/health | ✅ |

---

## 🚨 IMPORTANT NOTES

### 1. **This is SIMULATION Mode**
- No real money at risk
- Uses $500 virtual balance
- Perfect for testing and learning

### 2. **Safe to Run 24/7**
- Risk limits in place
- Will auto-stop if daily loss >2%
- Max 2 positions limits exposure

### 3. **Why No Trades Yet?**
- Market velocity too low (0.06% moves)
- Highest score: 62.2 / 70 required
- Bot is working correctly
- **This is GOOD** - protecting you from low-quality setups

### 4. **When Will It Trade?**
- When Bitcoin/crypto gets volatile
- During US/Asian market hours
- When coins show strong momentum
- Typical: 1-3 trades per day in active markets

### 5. **Monitoring**
```bash
# Quick status
./scripts/check_status.sh

# See current scores
docker exec alpha-sniper-v2 python3 -c "..." # (use command from earlier)

# Watch live
./scripts/watch_logs.sh
```

---

## 💡 RECOMMENDATIONS FOR SECOND OPINION

Share these key points:

1. **Risk per trade:** 0.5% of equity ($2.50 on $500)
2. **Max daily loss:** 2% ($10 on $500)
3. **Signal threshold:** 70/100 score
4. **Stop loss:** 5%, Take profit: 10%
5. **Max positions:** 2 concurrent
6. **Mode:** Simulation (no real money)

**Questions to ask:**
- Is 70 signal threshold too conservative?
- Should I trade more aggressively during quiet markets?
- Is 2% daily drawdown limit appropriate?
- Should I increase position size from 20%?

---

## 📋 QUICK REFERENCE

**Start bot:**
```bash
cd ~/alpha-sniper-v2
./deployment/deploy.sh
```

**Check status:**
```bash
./scripts/check_status.sh
```

**View current opportunities:**
```bash
docker exec alpha-sniper-v2 python3 -c "..." # (market scores command)
```

**Modify settings:**
```bash
nano .env
docker compose restart
```

**Stop trading (emergency):**
```bash
./deployment/stop_trading.sh
```

---

**Configuration saved for review:** ✅
**Bot status:** Healthy, waiting for quality setups ✅
**Risk level:** Conservative ✅
**Ready for second opinion:** ✅
