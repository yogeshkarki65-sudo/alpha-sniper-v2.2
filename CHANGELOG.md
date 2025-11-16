# Changelog - Alpha Sniper v4.1.1

All notable changes to the Alpha Sniper trading bot.

---

## [4.1.1] - 2025-11-16 - "Entry Quality Improvements"

### 🎯 **Objective**
Improve win rate from 40% to 55-60% by preventing late momentum entries and improving entry timing.

### 📊 **Performance Before Fixes**
- **Win Rate:** 40% (8 wins / 12 losses)
- **ROI:** +6.62% in 10 hours
- **Problem:** Too many stop loss hits (35% of trades)
- **Root Cause:** Entering late in momentum moves (catching reversals)

### ✅ **Changes Made**

#### **1. Tightened RSI Range**
**Why:** RSI > 75-80 indicates trend exhaustion and blow-off tops
```diff
- MIN_RSI_1H=58
- MAX_RSI_1H=85
+ MIN_RSI_1H=60
+ MAX_RSI_1H=75
```
**Impact:** Filters out overbought entries, reduces late-entry stop losses

---

#### **2. Increased Minimum Signal Score**
**Why:** Higher scores indicate cleaner momentum and better setup quality
```diff
- MIN_SIGNAL_SCORE=62
+ MIN_SIGNAL_SCORE=65
```
**Impact:** Reduces borderline setups, improves average trade quality

---

#### **3. Tightened Stop Loss**
**Why:** Most losers were hitting -3.8% anyway; faster cuts preserve capital
```diff
- STOP_LOSS_PCT=3.5
+ STOP_LOSS_PCT=3.0
```
**Impact:** Cuts losers faster, improves overall expectancy

---

#### **4. NEW: Parabolic Move Filter**
**Why:** Prevents FOMO entries into vertical spikes (blow-off tops)
```python
# Reject if 1H return > 4H return * 1.5
if ret_1h_pct > ret_4h_pct * 1.5:
    return False  # Too parabolic
```
**Added to:** `scanner/filters.py` (Filter 8)
**Config:** `REJECT_PARABOLIC_MOVES=true`, `PARABOLIC_THRESHOLD=1.5`
**Impact:** Avoids catching late-stage parabolic moves

---

#### **5. NEW: Daily Range Position Filter**
**Why:** Buying near 24H highs often leads to reversals
```python
# Reject if price is in top 15% of 24H range
range_pos = (current_price - low_24h) / (high_24h - low_24h)
if range_pos > 0.85:
    return False  # Too close to resistance
```
**Added to:** `scanner/filters.py` (Filter 9)
**Config:** `REJECT_HIGH_RANGE_ENTRIES=true`, `MAX_RANGE_POSITION_PCT=0.85`
**Impact:** Prevents buying into resistance zones

---

#### **6. NEW: Pullback Preference Filter**
**Why:** Better entries occur on pullbacks, not vertical breakouts
```python
# Check if current price >= recent highs (last 2 candles)
high_last_2 = max(klines_1h[-2][2], klines_1h[-3][2])
if current_price >= high_last_2:
    return False  # Buying breakout top (not pullback)
```
**Added to:** `scanner/features.py` (Pullback Check)
**Added to:** `scanner/filters.py` (Filter 10)
**Config:** `PREFER_PULLBACKS=true`
**Impact:** Shifts behavior from chasing breakouts to buying dips

---

### 📝 **Implementation Details**

#### **Files Modified:**
1. **`.env`**
   - Updated RSI: 60-75
   - Updated Score: 65
   - Updated SL: 3.0%
   - Added new filter parameters

2. **`config/config.py`**
   - Added `REJECT_PARABOLIC_MOVES`
   - Added `PARABOLIC_THRESHOLD`
   - Added `REJECT_HIGH_RANGE_ENTRIES`
   - Added `MAX_RANGE_POSITION_PCT`
   - Added `PREFER_PULLBACKS`
   - Updated default RSI values

3. **`scanner/filters.py`**
   - Added Filter 8: Parabolic move rejection
   - Added Filter 9: Daily range position check
   - Added Filter 10: Pullback preference
   - All filters with detailed comments

4. **`scanner/features.py`**
   - Added pullback detection logic
   - Compares current price vs recent 2-candle highs
   - Returns `is_pullback` boolean in feature dict

5. **`main.py`**
   - Enhanced startup config display
   - Shows all new filter parameters
   - Version updated to 4.1.1

---

### 🎯 **Expected Outcomes**

| Metric | Before (v4.1) | Target (v4.1.1) |
|--------|---------------|-----------------|
| **Win Rate** | 40% | 55-60% |
| **SL Hits** | 35% | <20% |
| **Avg Winner** | +$11.57 | +$13.20 |
| **Avg Loser** | -$9.99 | -$8.10 |
| **Profit Factor** | 1.16 | 2.0+ |

---

### 🔄 **Upgrade Instructions**

```bash
# On Ubuntu server
cd ~/alpha-sniper-v2.2
git pull origin claude/do-task-01HNsRrUm6U3iPJYnW9jbiPa

# Restart bot
pkill -f "python.*main.py"
source venv/bin/activate
python main.py > /dev/null 2>&1 &

# Verify config
tail -f logs/alpha_sniper.log
```

**Verify these lines appear in logs:**
```
Min Score: 65
RSI Range: 60-75
Parabolic Rejection: True (threshold: 1.5x)
High Range Rejection: True (max: 85%)
Pullback Preference: True
```

---

### 📌 **What Remains Unchanged**

✅ Trailing stop system (4% activation, 1.5% distance)
✅ Take profit target (10%)
✅ Position sizing (3% risk per trade)
✅ Max concurrent positions (3)
✅ Min hold time (4 hours)
✅ Volume filter (2.0x RVOL)
✅ Timeframe alignment requirement
✅ Symbol cooldown (12 hours)

---

### 🐛 **Bug Fixes**

None in this release (bugs fixed in v4.1.0):
- ✅ Timestamp storage (1970-01-01 issue)
- ✅ Duplicate position prevention
- ✅ Symbol cooldown enforcement

---

### 📊 **Monitoring Plan**

**Next 20 Trades:**
- Track win rate improvement
- Verify no parabolic/range rejections on good trades
- Confirm pullback entries outperform breakout entries
- Monitor SL hit rate reduction

**Success Criteria:**
- Win rate ≥ 50%
- SL hit rate < 25%
- Fewer duplicate symbols
- Avg score > 68

---

### 🔮 **Future Improvements (v4.2)**

Potential additions (NOT implemented yet):
- Volume profile analysis
- Session-based entry timing
- Dynamic position sizing based on score
- Machine learning weight optimization
- Multi-exchange support

---

**Version:** 4.1.1
**Release Date:** November 16, 2025
**Status:** ✅ Ready for Deployment
**Next Review:** After 20 trades or 24 hours
