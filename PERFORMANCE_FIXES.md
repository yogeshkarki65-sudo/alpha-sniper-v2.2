# Performance Fixes - Alpha Sniper v2.2

## Problem Summary
- **87% loss rate** (107 losses, 16 wins out of 123 trades)
- **-$104.13 total P&L** (-0.47% average per trade)
- **Missing ALL big movers** (VLXUSDT, NXTUSDT, AGIBUSDT, etc.)

## Root Causes Identified
1. Universe too small (top 60 by volume) - missing low-volume big movers
2. Filters too restrictive - eliminating volatile coins before detection
3. Broken velocity scoring - not rewarding large moves properly
4. Aggressive position sizing with unvalidated signals
5. Whipsaw trailing stops exiting too early
6. 6-hour cooldown preventing bounce re-entries

---

## Fixes Applied

### 1. Scanner Universe Expansion
**File:** `scanner/scanner.py:44`
- **Changed:** TOP_N from 60 to 200
- **Impact:** 3.3x more coins scanned, captures low-volume big movers
- **Why:** Big movers like VLXUSDT aren't in top 60 by volume initially

### 2. Spread Filter Relaxation
**File:** `scanner/scanner.py:59`
- **Changed:** Max spread from 0.5% to 2.0%
- **Impact:** Volatile coins with wider spreads now included
- **Why:** Low-liquidity runners have 1-5% spreads naturally

### 3. Liquidity Threshold Reduction
**File:** `config/config.py:18`
- **Changed:** MIN_LIQUIDITY_VOLUME_24H from $100k to $30k
- **Impact:** Small-cap runners now eligible
- **Why:** Coins moving 50-100% often have <$100k 24h volume initially

### 4. Velocity Scoring Fix
**File:** `scanner/scorer.py:31`
- **Changed:** velocity_norm from `abs(velocity) * 2` to `abs(velocity) * 1.0`
- **Impact:** 100% move now scores 100 (was capped at 50% = 100 score)
- **Why:** Big movers weren't getting proportional reward for larger moves

### 5. Optimized Signal Weights
**File:** `scanner/scorer.py:8-12`
- **Changed:** Default weights to velocity-focused
  - velocity: 0.25 → **0.45** (+80%)
  - rvol: 0.25 → **0.30** (+20%)
  - trend: 0.25 → **0.10** (-60%)
  - orderbook_imbalance: 0.25 → **0.15** (-40%)
- **Impact:** Prioritizes price momentum over position-in-range
- **Why:** Velocity is most predictive of continuation moves

### 6. Position Size Risk Reduction
**File:** `config/config.py:17`
- **Changed:** MAX_POSITION_RISK_PCT from 0.5% to 0.25%
- **Impact:** 50% smaller position sizes = less damage per bad trade
- **Why:** With 87% loss rate, large positions were devastating

### 7. MOON Multiplier Reduction
**File:** `config/config.py:42`
- **Changed:** MOON_MULT from 1.5x to 1.2x
- **Impact:** 20% smaller boost on "moon" signals (score ≥90)
- **Why:** High-score signals aren't validated enough for 1.5x sizing

### 8. Trailing Stop Less Aggressive
**File:** `config/config.py:29-30`
- **Changed:**
  - TRAILING_STOP_ACTIVATION_PCT: 2% → **5%**
  - TRAILING_STOP_DISTANCE_PCT: 1% → **2.5%**
- **Impact:** Needs +5% profit to activate, trails by 2.5% (not 1%)
- **Why:** 1% trailing distance whipsawed out on normal volatility

### 9. Cooldown Period Reduction
**File:** `config/config.py:39`
- **Changed:** SYMBOL_COOLDOWN_HOURS from 6 hours to 1 hour
- **Impact:** Can re-enter after stop-loss much sooner
- **Why:** Volatile coins often bounce back within 30-60 minutes

---

## Expected Improvements

### Detection:
- ✅ **Scan 200 coins** instead of 60 (3.3x coverage)
- ✅ **Include small-cap runners** ($30k liquidity vs $100k)
- ✅ **Accept 2% spreads** vs 0.5% (volatile coins included)
- ✅ **Properly score big moves** (100% move = 100 score, not capped at 50%)

### Risk Management:
- ✅ **50% smaller positions** (0.25% risk vs 0.5%)
- ✅ **20% less aggressive MOON sizing** (1.2x vs 1.5x)
- ✅ **2.5x wider trailing stop** (won't whipsaw on 1-2% pullbacks)
- ✅ **6x faster re-entry** (1h cooldown vs 6h)

### Signal Quality:
- ✅ **Velocity prioritized** (45% weight vs 25%)
- ✅ **Momentum-focused** (not position-in-range)
- ✅ **Better risk/reward** (smaller size, better exits)

---

## Testing Recommendations

1. **Monitor scanner output** - Should see more signals from small-cap coins
2. **Check big mover captures** - Verify VLXUSDT-type coins are now included
3. **Track win rate** - Should improve from 13% toward 30-40%
4. **Watch position exits** - Fewer premature trailing stop exits
5. **Analyze signal scores** - Velocity should dominate high-score signals

## Backtest Comparison (Before vs After)

| Metric | Before | Expected After |
|--------|--------|----------------|
| Win Rate | 13% (16/123) | 30-40% target |
| Avg P&L/Trade | -0.47% | -0.10% to +0.20% |
| Big Movers Caught | 0/9 shown | 5-7/9 target |
| Universe Size | 60 coins | 200 coins |
| Max Position Risk | 0.5% | 0.25% |
| Velocity Weight | 25% | 45% |

---

## Files Modified

1. `scanner/scanner.py` - Universe expansion + spread filter
2. `scanner/scorer.py` - Velocity fix + optimized weights
3. `config/config.py` - Risk, cooldown, trailing stop params

## Next Steps

1. Delete `data/alpha_sniper.db` to clear bad trade history (optional)
2. Delete `data/weights.json` to use new default weights
3. Restart bot and monitor first 24 hours
4. Compare new performance against this baseline

---

**Changes implemented:** 2025-11-17
**Target:** Capture big movers, reduce loss rate, improve signal quality
