# Alpha Sniper V2.3 Upgrade Guide

## Overview

Version 2.3 addresses the critical issue of **zero signal generation** in V2.2 by optimizing parameters for better market coverage while maintaining robust risk management.

## Key Problems Solved

1. **Zero Signals**: V2.2 filters were too strict
2. **Slow Learning**: Required 30 trades before activation
3. **Premature Exits**: Trailing stops activated too early
4. **Limited Portfolio**: Only 2 concurrent positions
5. **API Overhead**: Orderbook checks for all pairs

---

## What's New in V2.3

### Scanner Improvements

| Parameter | V2.2 | V2.3 | Impact |
|-----------|------|------|--------|
| MIN_SIGNAL_SCORE | 70 | 60 | **↑ More signals** |
| MIN_LIQUIDITY_VOLUME_24H | 100k | 50k | **↑ More opportunities** |
| CHECK_ORDER_BOOK_IMBALANCE | true | false | **↓ Fewer API calls** |
| SYMBOL_COOLDOWN_HOURS | 6 | 3 | **↑ Faster re-entry** |
| MOON_SCORE | 90 | 85 | **↑ More high-confidence trades** |

### Risk Management

| Parameter | V2.2 | V2.3 | Impact |
|-----------|------|------|--------|
| MAX_POSITION_RISK_PCT | 0.5% | 1.0% | **↑ More data in SIM** |
| MAX_CONCURRENT_POS | 2 | 3 | **↑ Better diversification** |
| MAX_PER_TRADE_PCT | 20% | 25% | **↑ Slightly more aggressive** |

### Exit Strategy

| Parameter | V2.2 | V2.3 | Impact |
|-----------|------|------|--------|
| TAKE_PROFIT_PCT | 10% | 12% | **↑ Better R:R ratio** |
| TRAILING_STOP_ACTIVATION_PCT | 2% | 4% | **↓ Less premature activation** |
| TRAILING_STOP_DISTANCE_PCT | 1% | 2% | **↓ Less whipsaw exits** |

### Learning Module

| Parameter | V2.2 | V2.3 | Impact |
|-----------|------|------|--------|
| MIN_TRADES_FOR_LEARNING | 30 | 20 | **↑ Faster activation** |
| LEARNING_LOOKBACK_DAYS | 30 | 20 | **↑ More responsive** |
| LEARNING_INTERVAL | 3600s | 1800s | **↑ Runs every 30 min** |

### Code Improvements

1. **Scanner Instrumentation**
   - Now logs detailed statistics after each scan
   - Shows min/avg/max scores and threshold
   - Helps diagnose why signals pass/fail

2. **Better Logging**
   - All prints now use `flush=True` for real-time output
   - More detailed progress messages
   - Clearer error reporting

---

## Expected Results

### V2.2 (Before)
- **Signals per scan**: 0
- **Trades per day**: 0
- **Learning activation**: Never
- **Data for optimization**: None

### V2.3 (After)
- **Signals per scan**: 5-15
- **Trades per day**: 3-10
- **Learning activation**: After ~1 week
- **Data for optimization**: Abundant

---

## How to Upgrade

### Step 1: Backup Current Configuration

```bash
cd ~/alpha-sniper-v2.2
cp .env .env.v2.2.backup
```

### Step 2: Pull V2.3 Updates

```bash
git pull origin claude/setup-new-server-013UrZEWVYQFRi5YL56gEUXp
```

### Step 3: Update Your .env

**Option A: Automatic (Recommended)**

```bash
# Copy the new example
cp .env.example .env

# Re-add your Telegram credentials
nano .env
# Update TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
```

**Option B: Manual**

Update these lines in your existing `.env`:

```bash
# Scanner
MIN_SIGNAL_SCORE=60
MIN_LIQUIDITY_VOLUME_24H=50000
CHECK_ORDER_BOOK_IMBALANCE=false
SYMBOL_COOLDOWN_HOURS=3
MOON_SCORE=85

# Risk
MAX_POSITION_RISK_PCT=1.0
MAX_CONCURRENT_POS=3
MAX_PER_TRADE_PCT=25.0

# Exits
TAKE_PROFIT_PCT=12.0
TRAILING_STOP_ACTIVATION_PCT=4.0
TRAILING_STOP_DISTANCE_PCT=2.0

# Learning
MIN_TRADES_FOR_LEARNING=20
LEARNING_LOOKBACK_DAYS=20
LEARNING_INTERVAL=1800
```

### Step 4: Rebuild and Restart

```bash
./deployment/rebuild.sh
```

### Step 5: Monitor the Changes

```bash
# Watch logs for new scanner statistics
docker compose logs -f

# Check status
./deployment/monitor.sh

# After a few hours, check if you're getting signals
curl http://localhost/health | jq
```

---

## What to Look For

### Scanner Logs (V2.3)

You should now see detailed statistics:

```
🔍 Running scanner...
[scanner] Fetching 24h tickers from: https://api.mexc.com/api/v3/ticker/24hr
[scanner] Got 2096 USDT pairs, using top 60 by volume
[scanner] After filters: 58 liquid USDT pairs
[scanner] Final universe size: 58 symbols
[scanner] ✅ Signal: BTCUSDT score=72.5 rvol=1.85 vel=3.20% trend=0.68 ob=0.00
[scanner] ✅ Signal: ETHUSDT score=68.2 rvol=1.42 vel=2.10% trend=0.72 ob=0.00
...
[scanner] 📊 Summary → candidates=58 | signals=8 | score_min=42.3 | score_avg=61.7 | score_max=75.2 | threshold=60
[scanner] Created 8 signals this run
```

**Key metrics:**
- `candidates`: How many pairs passed filters
- `signals`: How many exceeded threshold (60)
- `score_avg`: Average score (should be close to threshold)
- `score_max`: Best opportunity found

### Health Endpoint

Check your bot is generating signals:

```bash
curl http://localhost/health | jq
```

Look for:
- `last_scanner_run` updating every 5 minutes
- Non-zero signal counts in database

---

## Troubleshooting

### Still Getting 0 Signals?

**Check scanner output:**

```bash
docker compose logs | grep "scanner"
```

If you see:
- `score_max < 60` → Market is genuinely quiet, wait for volatility
- `candidates=0` → Liquidity filter too strict, lower MIN_LIQUIDITY_VOLUME_24H
- `score_avg` much lower than 60 → Adjust weights in `scanner/scorer.py`

### Too Many Signals?

If you're getting 20+ signals per scan:

```bash
# Tighten the threshold
nano .env
# Set MIN_SIGNAL_SCORE=65 or 70
./deployment/rebuild.sh
```

### Trades Not Executing?

Check risk constraints:

```bash
docker compose logs | grep "trader"
```

Common blocks:
- "All position slots filled" → Good! Working as intended
- "Cannot trade: daily drawdown" → Risk manager working
- "too correlated" → Diversification working

---

## Performance Monitoring

### After 24 Hours

```bash
./deployment/stats.sh
```

Expected:
- **3-10 trades** completed
- **Win rate**: Unknown yet (need more data)
- **Signals generated**: 50-100 total

### After 7 Days

```bash
./deployment/stats.sh
```

Expected:
- **20-70 trades** completed
- **Win rate**: >40% (hopeful target)
- **Learning module**: Should be active
- **Profit factor**: >1.0 (target)

---

## Rolling Back to V2.2

If you need to revert:

```bash
cd ~/alpha-sniper-v2.2

# Restore old config
cp .env.v2.2.backup .env

# Restore old code
git checkout 71ea2ef  # V2.2 commit hash

# Rebuild
./deployment/rebuild.sh
```

---

## Next Steps After V2.3

Once you have 50+ trades in SIM:

1. **Analyze Performance**
   ```bash
   ./deployment/stats.sh
   ```

2. **Review Trade Quality**
   ```bash
   docker compose exec alpha-sniper sqlite3 /app/data/trades.db
   SELECT symbol, entry_price, exit_price, pnl_pct, exit_reason
   FROM trades ORDER BY timestamp DESC LIMIT 20;
   ```

3. **Check Learning Module**
   - Look for "Learning module adjusted weights" in Telegram
   - Verify improvements in subsequent trades

4. **Consider Live Trading**
   - Only if: Win rate >50%, Profit factor >1.5, No crashes
   - Start with minimal capital ($50-100)
   - Keep SIM running in parallel

---

## FAQ

**Q: Should I clear my database when upgrading?**

A: No! Keep your existing trades.db. V2.3 is backward compatible.

**Q: Will my existing open positions be affected?**

A: No. Open positions use the SL/TP set at entry time. Only new trades use V2.3 parameters.

**Q: Can I mix V2.2 and V2.3 settings?**

A: Yes! All parameters are independent. You can cherry-pick what to change.

**Q: How long before I see trades?**

A: With V2.3 defaults, expect first signal within 5-30 minutes. First trade within 1-6 hours (depends on market conditions).

**Q: Is V2.3 safe for live trading?**

A: No! Still test in SIM for 7-14 days minimum. V2.3 is optimized for SIM data collection, not yet proven in live markets.

---

## Support

- **Logs**: `docker compose logs -f`
- **Status**: `./deployment/monitor.sh`
- **Stats**: `./deployment/stats.sh`
- **Health**: `curl http://localhost/health`
- **Report Issues**: Check PROJECT_REPORT.md for full context

---

**Version**: 2.3.0
**Release Date**: November 15, 2025
**Author**: Alpha Sniper Development Team
**Previous Version**: 2.2.0
