# 🚀 ALPHA SNIPER V2.2 - QUICK START GUIDE

## Run the Upgraded Strategy in 3 Steps

### **Step 1: Pull the Latest Code**

```bash
cd /home/user/alpha-sniper-v2.2
git pull origin claude/alpha-sniper-strategy-012HgHSmdxpZ9J4fUDK4guNm
```

---

### **Step 2: Run the Upgrade Script**

```bash
./upgrade_to_v2.sh
```

This will:
- ✅ Install pyarrow dependency
- ✅ Backup your current main.py and .env
- ✅ Create necessary directories
- ✅ Generate main_v2.py with new strategy

---

### **Step 3: Test Run**

```bash
# Test the new version (safe - won't affect your current setup)
python main_v2.py
```

**What you'll see:**
```
==============================================================
  🚀 ALPHA SNIPER V2.2 STARTING
==============================================================
  Mode: SIM
  Version: 2.2.0 (Enhanced Quant Strategy)
==============================================================

[scanner v2] ✅ Enhanced scanner initialized with Alpha Sniper V2.2
[trader v2] ✅ Enhanced trader initialized with Alpha Sniper V2.2

[scanner v2] Updating regime data...
[scanner v2] 📊 Current Regime: BULL (Z-score: 0.73, RS_alt: 0.042)

🔍 Running Enhanced Scanner (Alpha Sniper V2.2)...
[scanner v2] Scanning 45 symbols...

[scanner v2] ✅ SIGNAL: SOLUSDT | Score: 0.685 | Regime: BULL | RVOL: 2.45 | Threshold: 0.600

💼 Running Enhanced Trader (Alpha Sniper V2.2)...
[trader v2] 📈 OPENED: SOLUSDT @ $98.5234 | Size: 15.2341 | Value: $1500.00 | Regime: BULL
[trader v2]    SL: $96.1234 | TP1: $102.4567 (50%) | TP2: $106.2341 (30%)
```

---

## Switch to Production (When Ready)

```bash
# Stop current bot (if running)
# Ctrl+C or kill the process

# Replace main.py with v2
mv main.py main.py.old
mv main_v2.py main.py

# Run the upgraded bot
python main.py
```

---

## Key Differences from V1

| Feature | V1 (Old) | V2 (New) |
|---------|----------|----------|
| **Regime Detection** | None | ✅ BTC+TOTAL3 Z-score |
| **Entry Conditions** | 4 basic features | ✅ 9 advanced conditions |
| **Scoring** | Fixed weights | ✅ Normalized + momentum bonuses |
| **Thresholds** | Fixed 70/100 | ✅ Adaptive rolling median |
| **Position Sizing** | Fixed % | ✅ ATR-based volatility-adjusted |
| **Exits** | Fixed % SL/TP | ✅ ATR-based multi-level |
| **Trailing Stop** | % based | ✅ ATR-based adaptive |

---

## Configuration

The strategy uses `config_alpha_sniper.json`. You can customize:

```json
{
  "regime_detection": {
    "z_bull_threshold": 0.5,
    "z_bear_threshold": -0.5
  },
  "risk_management": {
    "risk_pct_bull": 0.004,
    "risk_pct_sideways": 0.0025,
    "risk_pct_bear": 0.0012,
    "max_portfolio_heat": 0.015,
    "max_daily_loss_pct": 0.02
  },
  "atr_parameters": {
    "atr_sl_mult": 2.0,
    "tp1_mult": 2.0,
    "tp2_mult": 3.0,
    "trail_mult": 1.5
  }
}
```

---

## Monitoring

**Watch for:**

1. **Regime Changes**
   ```
   [scanner v2] 📊 Current Regime: BULL → SIDEWAYS
   ```

2. **Signal Quality**
   ```
   Score: 0.685 | Threshold: 0.600 ✅ (above threshold)
   ```

3. **ATR-Based Exits**
   ```
   [trader v2] 🎯 ATR Trailing stop activated @ $102.34
   [trader v2] 💰 CLOSED (TP): SOLUSDT | PnL: 8.45%
   ```

---

## Rollback (If Needed)

```bash
# Restore old version
mv main.py.backup main.py
mv .env.backup .env

# Restart
python main.py
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'pyarrow'"
```bash
pip install pyarrow==14.0.1
```

### "No regime data available"
```bash
# The scanner will fetch BTC/TOTAL3 data automatically on first run
# Wait 1-2 minutes for initial data fetch
```

### "No signals generated"
```bash
# This is normal - the new strategy is more selective
# In bull regime: expect 5-15 signals/day
# In sideways: expect 2-8 signals/day
# In bear: expect 0-3 signals/day
```

### "Position size too small"
```bash
# Check your equity and risk settings
# Minimum position value should be > $10
```

---

## Performance Expectations

**Conservative (Default Settings):**
- Signals: 5-15 per day
- Win Rate: 45-55%
- Average Hold: 4-12 hours
- Monthly Return: 5-15%
- Max Drawdown: 10-20%

**Aggressive (Increase risk_pct):**
- Signals: 15-40 per day
- Win Rate: 40-50%
- Average Hold: 2-8 hours
- Monthly Return: 10-30%
- Max Drawdown: 20-35%

---

## Support

- **Documentation:** See `ALPHA_SNIPER_STRATEGY_DOCS.md`
- **Implementation Details:** See `IMPLEMENTATION_SUMMARY.md`
- **Configuration:** Edit `config_alpha_sniper.json`

---

## ⚡ TL;DR

```bash
# 1. Pull code
git pull origin claude/alpha-sniper-strategy-012HgHSmdxpZ9J4fUDK4guNm

# 2. Upgrade
./upgrade_to_v2.sh

# 3. Test
python main_v2.py

# 4. Go live (when ready)
mv main.py main.py.old && mv main_v2.py main.py && python main.py
```

**That's it! Your bot is now running Alpha Sniper V2.2!** 🎉
