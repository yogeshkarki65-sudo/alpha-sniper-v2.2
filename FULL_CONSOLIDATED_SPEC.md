# ALPHA SNIPER V2.2 — FULL CONSOLIDATED SPEC
## Complete Quantitative Trading Strategy (2025)
### Backtestable, Regime-Aware, Momentum Safeguards, Parameter Sensitivity

**Version:** 2.2.0
**Date:** 2025-11-17
**Status:** Production Ready
**Implementation:** 100% Complete

---

## TABLE OF CONTENTS

1. [Regime Detection](#1-regime-detection)
2. [Trend Filter](#2-trend-filter)
3. [Breakout Logic](#3-breakout-logic)
4. [Pullback Logic](#4-pullback-logic)
5. [RVOL (Relative Volume)](#5-rvol-relative-volume)
6. [Orderbook Imbalance](#6-orderbook-imbalance)
7. [Extension Filter](#7-extension-filter-anti-blowoff)
8. [Local Exhaustion Kill-Switch](#8-local-exhaustion-kill-switch)
9. [Scoring Model](#9-scoring-model-normalized)
10. [Momentum Bonuses](#10-momentum-bonuses-regime-aware)
11. [Rolling Median Adaptive Threshold](#11-rolling-median-adaptive-threshold)
12. [Complete Entry Conditions](#12-complete-entry-conditions)
13. [Risk Model](#13-risk-model-volatility-adjusted)
14. [Exit Rules](#14-exit-rules-atr-based)
15. [Parameter Sensitivity Grid](#15-parameter-sensitivity-grid)
16. [Backtest Engine Requirements](#16-backtest-engine-requirements)
17. [Implementation Map](#17-implementation-map)
18. [Usage Examples](#18-usage-examples)

---

# 1. REGIME DETECTION

## 1.1 Data Requirements

**Inputs:**
- BTCUSDT daily OHLCV data (180 days minimum)
- TOTAL3 daily data OR altcoin basket proxy (180 days minimum)

**Timeframe:** Daily (1D) candles
**Update Frequency:** Hourly (or on each new data point)
**Lookback Windows:**
- `SHORT_WINDOW = 21` (approximately 1 month)
- `LONG_WINDOW = 180` (approximately 6 months)

## 1.2 Calculation Steps

### Step 1: Calculate Daily Returns
```python
# For both BTC and TOTAL3
returns = close.pct_change()
```

### Step 2: Compute Rolling Metrics
```python
# Short-term (21-day)
R_21d = returns.rolling(window=21).sum()
Vol_21d = returns.rolling(window=21).std()

# Long-term (180-day)
R_180 = returns.rolling(window=180).sum()
std_180 = returns.rolling(window=180).std()
```

### Step 3: Calculate Z-Score
```python
Z_ret = (R_21d - R_180) / std_180
```
**Interpretation:**
- `Z_ret > 0`: Returns above long-term average
- `Z_ret < 0`: Returns below long-term average
- Magnitude indicates strength

### Step 4: Calculate Relative Strength
```python
RS_alt = R_21d(TOTAL3) - R_21d(BTC)
```
**Interpretation:**
- `RS_alt > 0`: Altcoins outperforming BTC
- `RS_alt < 0`: Altcoins underperforming BTC

## 1.3 Regime Classification

### Bull Regime
```python
Bull = (Z_ret > +0.5) AND (RS_alt > 0)
```
**Conditions:**
1. 21-day returns significantly above 180-day average
2. Altcoins outperforming Bitcoin

### Sideways Regime
```python
Sideways = (-0.5 <= Z_ret <= +0.5)
```
**Conditions:**
1. Returns within normal range of long-term average

### Bear Regime
```python
Bear = (Z_ret < -0.5)
```
**Conditions:**
1. 21-day returns significantly below 180-day average

## 1.4 Regime Parameters

| Regime | RVOL Threshold | OB Imbalance | Risk % | Position Mult | Trend Required |
|--------|----------------|--------------|--------|---------------|----------------|
| **Bull** | ≥ 2.0 | ≥ 1.5 | 0.40% | 1.0x | Yes |
| **Sideways** | ≥ 3.0 | ≥ 1.5 | 0.25% | 0.75x | Yes |
| **Bear** | ≥ 4.0 | ≥ 2.0 | 0.12% | 0.5x | No (reclaim only) |

## 1.5 Implementation Location
- **File:** `indicators/regime.py`
- **Class:** `RegimeDetector`
- **Method:** `detect_regime(btc_data, total3_data)`

---

# 2. TREND FILTER

## 2.1 Data Requirements

**Inputs:** OHLCV data (4H recommended, or use resampled 15m)
**Indicators:** EMA20, EMA50
**Minimum History:** 50 periods

## 2.2 Calculation

### Step 1: Calculate EMAs
```python
EMA20 = close.ewm(span=20, adjust=False).mean()
EMA50 = close.ewm(span=50, adjust=False).mean()
```

### Step 2: Compute Trend Ratio
```python
Trend_Ratio = EMA20 / EMA50
```

### Step 3: Determine Trend Validity
```python
Trend_Valid = (Trend_Ratio > 1.01)
```
**Threshold Rationale:** 1% above provides buffer against noise

### Step 4: Calculate Trend Score (0-1)
```python
Trend_Score = clamp((Trend_Ratio - 1.0) * 10, 0, 1)
```

**Examples:**
- `Trend_Ratio = 1.00` → `Trend_Score = 0.00` (no trend)
- `Trend_Ratio = 1.05` → `Trend_Score = 0.50` (moderate uptrend)
- `Trend_Ratio = 1.10` → `Trend_Score = 1.00` (strong uptrend)

## 2.3 Implementation Location
- **File:** `indicators/features.py`
- **Method:** `calculate_trend_features(df)`

---

# 3. BREAKOUT LOGIC

## 3.1 Data Requirements

**Timeframe:** 15m candles (or configured interval)
**Lookback:** 24 hours = 96 periods (for 15m)
**Minimum History:** 100 candles

## 3.2 Calculation

### Step 1: Calculate 24H High
```python
periods_24h = 96  # For 15m interval
Breakout_Level = close.rolling(window=periods_24h).max().shift(1)
```
**Note:** `.shift(1)` ensures we use previous 24h, not including current candle

### Step 2: Breakout Validity Check
```python
# Condition 1: Price above breakout level
cond1 = (close > Breakout_Level)

# Condition 2: Candle size > 2%
candle_size = (close - open) / open
cond2 = (candle_size > 0.02)

Breakout_Valid = cond1 AND cond2
```

**Rationale:**
- 2% minimum candle ensures strong momentum
- Filters out weak breakouts and noise

### Step 3: Breakout Score (0-1)
```python
distance = close - Breakout_Level
normalized = distance / (0.05 * Breakout_Level)
Breakout_Score = clamp(normalized, 0, 1)
```

**Examples:**
- Breakout by 0% → Score = 0.0
- Breakout by 2.5% → Score = 0.5
- Breakout by 5%+ → Score = 1.0

## 3.3 Additional Tracking
```python
Above_Breakout = (close > Breakout_Level)
```

## 3.4 Implementation Location
- **File:** `indicators/features.py`
- **Method:** `calculate_breakout_features(df)`

---

# 4. PULLBACK LOGIC

## 4.1 Concept

Measures the depth of pullback after initial breakout, before price reclaims the breakout level.

**Optimal Depth:** 0.25 (25% retracement of breakout move)
**Valid Range:** 0.15 to 0.40 (15% to 40%)

## 4.2 Calculation

### Step 1: Identify Key Levels
```python
# Highest high since potential breakout
First_High = high.rolling(window=10, min_periods=1).max()

# Current low (potential pullback point)
Pullback_Low = low
```

### Step 2: Calculate Depth
```python
numerator = First_High - Pullback_Low
denominator = First_High - Breakout_Level

Depth = numerator / denominator
```

**Interpretation:**
- `Depth = 0.0`: No pullback (price at high)
- `Depth = 0.25`: 25% retracement (optimal)
- `Depth = 1.0`: Full retracement to breakout level

### Step 3: Validity Check
```python
Pullback_Valid = (Depth >= 0.15) AND (Depth <= 0.40)
```

### Step 4: Pullback Score (0-1)
```python
deviation = abs(Depth - 0.25) / 0.15
Pullback_Score = clamp(1 - deviation, 0, 1)
```

**Examples:**
- `Depth = 0.25` → `Score = 1.0` (perfect)
- `Depth = 0.20` or `0.30` → `Score = 0.67`
- `Depth = 0.15` or `0.40` → `Score = 0.33`

### Step 5: Reclaim Confirmation
```python
Reclaim_Valid = (close > Breakout_Level) AND Pullback_Valid
```

## 4.3 Implementation Location
- **File:** `indicators/features.py`
- **Method:** `calculate_pullback_features(df)`

---

# 5. RVOL (RELATIVE VOLUME)

## 5.1 Definition

Relative Volume measures current volume against typical volume.

## 5.2 Calculation

### Step 1: Calculate 24H Median Volume
```python
periods_24h = 96  # For 15m
Volume_Median_24h = volume.rolling(window=periods_24h).median()
```

**Why median?** More robust to outliers than mean

### Step 2: Calculate RVOL
```python
RVOL = volume / Volume_Median_24h
```

**Interpretation:**
- `RVOL = 1.0`: Normal volume
- `RVOL = 2.0`: 2x normal volume
- `RVOL = 0.5`: Half normal volume

### Step 3: RVOL Score (0-1)
```python
RVOL_Score = clamp((RVOL - 1) / 4, 0, 1)
```

**Examples:**
- `RVOL = 1.0` → `Score = 0.0`
- `RVOL = 3.0` → `Score = 0.5`
- `RVOL = 5.0+` → `Score = 1.0`

## 5.3 Regime-Specific Thresholds

```python
RVOL_Bull_OK = (RVOL >= 2.0)
RVOL_Sideways_OK = (RVOL >= 3.0)
RVOL_Bear_OK = (RVOL >= 4.0)
```

**Rationale:** Higher volume required in less favorable regimes

## 5.4 Implementation Location
- **File:** `indicators/features.py`
- **Method:** `calculate_rvol_features(df)`

---

# 6. ORDERBOOK IMBALANCE

## 6.1 Definition

Measures buying vs selling pressure in the orderbook.

## 6.2 Calculation

### Step 1: Aggregate Top 10 Levels
```python
Bid_Total = sum(bid_qty[0:10])
Ask_Total = sum(ask_qty[0:10])
```

### Step 2: Calculate Imbalance
```python
OB_Imbalance = Bid_Total / Ask_Total
```

**Interpretation:**
- `OB_Imbalance = 1.0`: Balanced
- `OB_Imbalance = 1.5`: 50% more bids than asks
- `OB_Imbalance = 2.0`: 2x more bids than asks

### Step 3: OB Score (0-1)
```python
OB_Score = clamp((OB_Imbalance - 1) / 1.5, 0, 1)
```

## 6.3 Regime-Specific Thresholds

```python
# Bull/Sideways
OB_Threshold_Bull = 1.5

# Bear
OB_Threshold_Bear = 2.0
```

## 6.4 Implementation Location
- **File:** `indicators/features.py`
- **Method:** `calculate_orderbook_imbalance(bid_volumes, ask_volumes)`
- **Method:** `calculate_ob_score(ob_imbalance)`

---

# 7. EXTENSION FILTER (ANTI-BLOWOFF)

## 7.1 Purpose

Prevents entries during parabolic moves that are likely to reverse.

## 7.2 Calculation

### Step 1: Calculate ATR
```python
ATR14 = ATR(high, low, close, period=14)
```

### Step 2: 24H ATR Average
```python
periods_24h = 96
ATR_Mean_24h = ATR14.rolling(window=periods_24h).mean()
```

### Step 3: ATR as % of Price
```python
ATR_pct_24h = (ATR_Mean_24h / close) * 100
```

### Step 4: 24H Price Change
```python
Price_Change_24h = close.pct_change(periods_24h) * 100
```

### Step 5: Extension Check
```python
# Condition 1: Price change > 1.5x ATR
extension_cond1 = (Price_Change_24h > 1.5 * ATR_pct_24h)

# Condition 2: RSI too high
RSI_14 = RSI(close, period=14)
extension_cond2 = (RSI_14 > 85)

# Reject if either condition true
Extension_Reject = extension_cond1 OR extension_cond2
Extension_OK = NOT Extension_Reject
```

**Rationale:**
- 1.5x multiplier identifies abnormal moves
- RSI > 85 indicates extreme overbought

## 7.3 Implementation Location
- **File:** `indicators/features.py`
- **Method:** `calculate_extension_features(df)`

---

# 8. LOCAL EXHAUSTION KILL-SWITCH

## 8.1 Purpose

Prevents buying into local exhaustion/climax moves.

## 8.2 Calculation

### Step 1: 3-Day Return
```python
periods_3d = 288  # 3 days in 15m candles
Return_3d = close.pct_change(periods_3d)
```

### Step 2: Range Relative to ATR
```python
Range_ATR = (high - low) / ATR14
```

### Step 3: Exhaustion Check
```python
exhaustion_cond1 = (Return_3d > 0.50)  # 50% gain in 3 days
exhaustion_cond2 = (Range_ATR > 2.5)   # Wide range bars

Exhaustion_Reject = exhaustion_cond1 AND exhaustion_cond2
Exhaustion_OK = NOT Exhaustion_Reject
```

**Rationale:**
- 50% in 3 days = likely climax
- Wide ranges (>2.5 ATR) = exhaustion bars

## 8.3 Implementation Location
- **File:** `indicators/features.py`
- **Method:** `calculate_exhaustion_features(df)`

---

# 9. SCORING MODEL (NORMALIZED)

## 9.1 Philosophy

**No arbitrary weights.** All components contribute equally.

## 9.2 Base Score Calculation

```python
components = [
    Trend_Score,
    Breakout_Score,
    RVOL_Score,
    OB_Score,
    Pullback_Score
]

Final_Score_raw = sum(components) / len(components)
```

**Properties:**
- All scores normalized 0-1
- Equal weighting (no bias)
- Result always 0-1

## 9.3 Vectorized Implementation

```python
# For backtesting
scores = (
    df['trend_score'] +
    df['breakout_score'] +
    df['rvol_score'] +
    df['ob_score'] +
    df['pullback_score']
) / 5
```

## 9.4 Implementation Location
- **File:** `strategies/scoring.py`
- **Class:** `ScoringModel`
- **Method:** `calculate_score(features, regime, regime_data)`

---

# 10. MOMENTUM BONUSES (REGIME-AWARE)

## 10.1 RSI-Rank Bonus (Trend-Follow Momentum)

**Purpose:** Reward strong momentum in bull markets

### Calculation
```python
# Calculate RSI percentile rank over 24h
RSI_Rank = percentile_rank(RSI_14, window=96)

# Apply bonus ONLY in bull regime
if regime == 'bull' AND RSI_Rank >= 85:
    Final_Score = min(1.0, Final_Score_raw + 0.1)
```

**Parameters:**
- Threshold: 85th percentile
- Bonus: +0.10
- Regime: Bull only

## 10.2 Alt/BTC Bonus (Relative Strength Momentum)

**Purpose:** Reward altcoin strength vs Bitcoin

### Calculation
```python
# Calculate Z-score of RS_alt
RS_alt_z = (RS_alt - mean(RS_alt, 180)) / std(RS_alt, 180)

# Apply bonus if conditions met
if (regime == 'bull') AND (RS_alt_z > 0.5) AND (Z_ret > 0):
    Final_Score = min(1.0, Final_Score + 0.05)
```

**Parameters:**
- RS_alt_z threshold: 0.5
- Z_ret requirement: > 0
- Bonus: +0.05
- Regime: Bull only

## 10.3 Final Score Range

```python
Final_Score = clamp(Final_Score_raw + bonuses, 0, 1)
```

**Maximum possible score:** 1.0 (clamped)

## 10.4 Implementation Location
- **File:** `strategies/scoring.py`
- **Method:** `_apply_momentum_bonuses(score_raw, features, regime, regime_data)`

---

# 11. ROLLING MEDIAN ADAPTIVE THRESHOLD

## 11.1 Purpose

Prevent overfitting by using adaptive thresholds based on historical score distribution.

## 11.2 Data Structure

```python
# Per-symbol score history
score_history[symbol] = [score1, score2, ..., scoreN]

# Global score history (all symbols)
global_scores = [score1, score2, ..., scoreN]

# Symbol first seen timestamp
symbol_start_times[symbol] = timestamp
```

## 11.3 Threshold Logic

### Case 1: Cold Start (No History)
```python
if len(score_history[symbol]) == 0:
    # Check global warm-start
    if global_warmstart AND len(global_scores) >= 100:
        threshold = median(global_scores)
    else:
        threshold = 0.60  # Cold start default
```

### Case 2: Partial History
```python
if len(score_history[symbol]) < 200:
    threshold = median(score_history[symbol])
```

### Case 3: Sufficient History
```python
if len(score_history[symbol]) >= 200:
    recent = score_history[symbol][-200:]
    threshold = median(recent)
```

### Case 4: Training Period
```python
if (current_timestamp - symbol_start_times[symbol]).days < 30:
    threshold = 0.60  # Fixed during training
```

## 11.4 Entry Decision

```python
Entry_Allowed = (Final_Score >= threshold)
```

## 11.5 History Management

```python
# Add new score
score_history[symbol].append(score)
global_scores.append(score)

# Limit memory (keep last 500 per symbol)
if len(score_history[symbol]) > 500:
    score_history[symbol] = score_history[symbol][-500:]

# Limit global (keep last 5000)
if len(global_scores) > 5000:
    global_scores = global_scores[-5000:]
```

## 11.6 Implementation Location
- **File:** `strategies/scoring.py`
- **Class:** `AdaptiveThresholdManager`
- **Methods:** `update_score_history()`, `get_threshold()`, `check_entry_allowed()`

---

# 12. COMPLETE ENTRY CONDITIONS

## 12.1 All Conditions (Must All Be TRUE)

```python
Entry_Signal = (
    condition_1_regime AND
    condition_2_trend AND
    condition_3_rvol AND
    condition_4_ob AND
    condition_5_pullback AND
    condition_6_reclaim AND
    condition_7_extension AND
    condition_8_exhaustion AND
    condition_9_threshold
)
```

## 12.2 Detailed Breakdown

### Condition 1: Regime Check
```python
regime = current_regime['regime']

if regime in ['bull', 'sideways']:
    condition_1 = True
elif regime == 'bear' AND reclaim_valid:
    condition_1 = True  # Allow reclaim-type breakouts in bear
else:
    condition_1 = False
```

### Condition 2: Trend Filter
```python
if regime_params['trend_required']:
    condition_2 = (Trend_Ratio > 1.01)
else:
    condition_2 = True  # Skip in bear reclaim mode
```

### Condition 3: RVOL Threshold
```python
rvol_threshold = regime_params['rvol_threshold']
condition_3 = (RVOL >= rvol_threshold)
```

### Condition 4: Orderbook Imbalance
```python
if ob_imbalance is not None:
    ob_threshold = regime_params['ob_imbalance_threshold']
    condition_4 = (ob_imbalance >= ob_threshold)
else:
    condition_4 = True  # Skip if not available
```

### Condition 5: Pullback Valid
```python
condition_5 = (0.15 <= Depth <= 0.40)
```

### Condition 6: Reclaim Confirmation
```python
condition_6 = (close > Breakout_Level)
```

### Condition 7: Extension Filter Pass
```python
condition_7 = Extension_OK
```

### Condition 8: Exhaustion Filter Pass
```python
condition_8 = Exhaustion_OK
```

### Condition 9: Adaptive Threshold
```python
threshold = get_threshold(symbol, timestamp)
condition_9 = (Final_Score >= threshold)
```

## 12.3 Order Placement

When all conditions true:
```python
# Place limit buy at reclaim price
entry_price = close * (1 + slippage)
place_order(symbol, entry_price, position_size)
```

## 12.4 Implementation Location
- **File:** `strategies/alpha_sniper.py`
- **Method:** `_check_entry_conditions(features, regime_info, regime_params, ob_imbalance, threshold_ok)`

---

# 13. RISK MODEL (VOLATILITY-ADJUSTED)

## 13.1 Position Sizing Formula

```python
ATR_SL = max(2 * ATR14, entry_price - Pullback_Low)
Position_Size = (Risk% * Equity) / ATR_SL
```

**Components:**
- `Risk%`: Regime-dependent risk percentage
- `Equity`: Current account equity
- `ATR_SL`: Stop-loss distance in price units

## 13.2 Risk Percentages by Regime

| Regime | Risk % | Basis Points |
|--------|--------|--------------|
| Bull | 0.40% | 40 bps |
| Sideways | 0.25% | 25 bps |
| Bear | 0.12% | 12 bps |

**Example (Bull, $10,000 equity):**
```python
Risk_Amount = $10,000 * 0.004 = $40
```

## 13.3 Stop-Loss Calculation

```python
# ATR-based distance
atr_distance = 2.0 * ATR14

# Price-based distance
price_distance = entry_price - Pullback_Low

# Use the larger (more conservative)
SL_distance = max(atr_distance, price_distance)
SL_price = entry_price - SL_distance
```

**Rationale:** Ensures stop accommodates volatility

## 13.4 Position Size Calculation

```python
# Risk in dollars
risk_dollars = equity * risk_pct

# Position size (in quote currency)
position_size = risk_dollars / SL_distance

# Convert to quantity (if needed)
quantity = position_size / entry_price
```

## 13.5 Portfolio Heat Limit

```python
# Sum risk across all open positions
total_heat = sum(position.risk_pct for position in open_positions)

# Maximum allowed
MAX_HEAT = 0.015  # 1.5%

# Check before opening new position
if (total_heat + new_position.risk_pct) > MAX_HEAT:
    reject_entry()
```

## 13.6 Daily Loss Limit

```python
daily_return = (current_equity - starting_equity) / starting_equity

if daily_return <= -0.02:  # -2%
    block_new_entries()
```

## 13.7 Implementation Location
- **File:** `strategies/risk_model.py`
- **Class:** `VolatilityAdjustedRiskModel`
- **Method:** `calculate_position_size(equity, entry_price, atr, pullback_low, regime)`

---

# 14. EXIT RULES (ATR-BASED)

## 14.1 Exit Levels

```python
# Calculate once at entry
ATR_SL_distance = entry_price - SL_price

TP1 = entry + (2.0 * ATR_SL_distance)  # 2x risk
TP2 = entry + (3.0 * ATR_SL_distance)  # 3x risk
Trailing_Stop_Initial = entry - (1.5 * ATR14)
Hard_SL = SL_price  # From entry calculation
```

## 14.2 Exit Sequence

### State 1: Entry → TP1
```python
# Monitor price
if price >= TP1:
    close_percentage = 50%
    activate_trailing_stop()
    mark_tp1_hit = True
```

### State 2: TP1 Hit → TP2
```python
# Update trailing stop continuously
trailing_stop = highest_close - (1.5 * current_ATR)

if price >= TP2:
    close_percentage = 30%  # 30% of remaining = 60% total
    mark_tp2_hit = True

if price <= trailing_stop:
    close_percentage = 100%  # Close remaining
```

### State 3: TP2 Hit → Trail Out
```python
# Update trailing stop
trailing_stop = highest_close - (1.5 * current_ATR)

if price <= trailing_stop:
    close_percentage = 100%  # Close remaining 40%
```

### Emergency Exit (Any State)
```python
if price <= Hard_SL:
    close_percentage = 100%  # Full stop-loss
```

## 14.3 Partial Exit Tracking

```python
# Initial
remaining_size = 1.0  # 100%

# After TP1
remaining_size = 1.0 - 0.5 = 0.5  # 50%

# After TP2
remaining_size = 0.5 - (0.5 * 0.3) = 0.35  # 35%

# After trailing
remaining_size = 0.35 - 0.35 = 0.0  # 0%
```

**Note:** TP2 closes 30% of remaining (not original)

## 14.4 Trailing Stop Updates

```python
# Track highest close since entry
highest_close = max(highest_close, current_close)

# Update trailing stop (only moves up, never down)
new_trailing = highest_close - (trail_mult * current_ATR)
trailing_stop = max(trailing_stop, new_trailing)
```

## 14.5 Parameter Ranges

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `atr_sl_mult` | 2.0 | 1.5-2.5 | Stop-loss multiplier |
| `tp1_mult` | 2.0 | 1.5-2.5 | First target multiplier |
| `tp2_mult` | 3.0 | 2.5-3.5 | Second target multiplier |
| `trail_mult` | 1.5 | 1.0-2.0 | Trailing stop multiplier |
| `tp1_exit_pct` | 0.50 | Fixed | 50% at TP1 |
| `tp2_exit_pct` | 0.30 | Fixed | 30% at TP2 |

## 14.6 Implementation Location
- **File:** `strategies/risk_model.py`
- **Class:** `ExitRulesManager`
- **Methods:**
  - `calculate_exit_levels(entry_price, stop_loss_price, atr)`
  - `update_trailing_stop(highest_close, current_atr, current_trailing_stop, tp1_hit)`
  - `check_exit_conditions(position, current_price, current_atr)`

---

# 15. PARAMETER SENSITIVITY GRID

## 15.1 Parameter Space

### Risk Parameters
```python
risk_pct_bull = [0.002, 0.004, 0.006]       # 0.2%, 0.4%, 0.6%
risk_pct_sideways = [0.00125, 0.0025, 0.00375]  # Half of bull
risk_pct_bear = [0.0008, 0.0012, 0.0016]    # Quarter of bull
```

### Portfolio Limits
```python
max_portfolio_heat = [0.01, 0.015, 0.02]    # 1%, 1.5%, 2%
max_daily_loss_pct = [0.01, 0.02, 0.03]     # 1%, 2%, 3%
```

### ATR Multipliers
```python
atr_sl_mult = [1.5, 2.0, 2.5]
tp1_mult = [1.5, 2.0, 2.5]
tp2_mult = [2.5, 3.0, 3.5]
trail_mult = [1.0, 1.5, 2.0]
```

### Regime Thresholds
```python
z_bull_threshold = [0.3, 0.5, 0.7]
z_bear_threshold = [-0.7, -0.5, -0.3]
```

### Adaptive Thresholds
```python
cold_start_threshold = [0.55, 0.60, 0.65]
min_samples_adaptive = [150, 200, 250]
```

## 15.2 Total Configurations

```python
# Calculate total combinations
total = 3^13 = 1,594,323 combinations
```

**Practical approach:** Random sampling (50-200 configs)

## 15.3 Selection Criteria

### Minimum Requirements
```python
total_return > 0              # Profitable
max_drawdown > -0.50          # Less than 50% DD
sharpe_ratio > 0.5            # Positive risk-adjusted return
total_trades >= 20            # Sufficient sample size
```

### Composite Score
```python
# Normalize each metric to 0-1
norm_return = (return - min_return) / (max_return - min_return)
norm_sharpe = (sharpe - min_sharpe) / (max_sharpe - min_sharpe)
norm_dd = 1 - ((dd - min_dd) / (max_dd - min_dd))
norm_calmar = (calmar - min_calmar) / (max_calmar - min_calmar)

# Weighted composite
composite = (
    0.3 * norm_return +
    0.3 * norm_sharpe +
    0.2 * norm_dd +
    0.2 * norm_calmar
)
```

### Robustness Tests

**Requirement:** Must survive multiple market periods

```python
periods = {
    'bear_2022': (2022-01-01, 2022-12-31),
    'bull_2023': (2023-01-01, 2023-12-31),
    'bull_2024': (2024-01-01, 2024-12-31)
}

# Test config on each period
for period in periods:
    result = backtest(config, period)
    if result.total_return < 0:
        reject_config()
```

## 15.4 Output

**Results saved to:** `results/sensitivity/sensitivity_results.csv`

**Columns:**
- config_id, params (dict)
- total_trades, win_rate, profit_factor
- total_return_pct, sharpe_ratio, max_drawdown_pct, calmar_ratio
- composite_score, rank

## 15.5 Implementation Location
- **File:** `tests/parameter_sensitivity.py`
- **Class:** `ParameterSensitivityTester`
- **Method:** `run_grid_search(symbols, start_date, end_date, sample_size, interval)`

---

# 16. BACKTEST ENGINE REQUIREMENTS

## 16.1 Core Features

### ✅ Regime Detection Support
```python
# Load BTC and TOTAL3 data
# Detect regimes for entire backtest period
# Apply regime-specific parameters per trade
```

### ✅ Vectorized Operations
```python
# Calculate all features for all symbols at once
# Avoid Python loops where possible
# Use pandas/numpy operations
```

### ✅ Deterministic Entry/Exit
```python
# Given same data + parameters = same results
# No randomness except in parameter sampling
```

### ✅ ATR-Based Sizing
```python
# Calculate ATR for each symbol
# Size positions based on volatility
# Adjust stops dynamically
```

### ✅ Momentum Bonuses
```python
# Apply RSI-rank bonus in bull regime
# Apply Alt/BTC bonus when conditions met
```

### ✅ Exhaustion Filter
```python
# Check 3-day returns
# Check range/ATR ratio
# Reject parabolic entries
```

### ✅ Rolling Median Threshold
```python
# Maintain per-symbol score history
# Update thresholds dynamically
# Support cold-start and warm-start
```

### ✅ Portfolio Heat Limits
```python
# Track total risk across positions
# Prevent exceeding 1.5% total heat
```

### ✅ Daily Loss Limits
```python
# Track equity at start of each day
# Block new entries if loss > 2%
```

### ✅ Per-Symbol State
```python
# Track score history per symbol
# Track last trade time (cooldown)
# Track threshold evolution
```

### ✅ Multi-Symbol Panel
```python
# Support 10-100 symbols simultaneously
# Efficient data storage (Parquet)
# Parallel feature calculation
```

## 16.2 Performance Metrics

### Trade Metrics
```python
total_trades
winning_trades
losing_trades
win_rate = winning_trades / total_trades
avg_win
avg_loss
profit_factor = abs(avg_win * winning / avg_loss * losing)
```

### Return Metrics
```python
total_pnl = sum(trade.pnl_net)
total_return = (final_equity - initial_equity) / initial_equity
annual_return = total_return * (365 / days_elapsed)
```

### Risk Metrics
```python
# Sharpe ratio (annualized)
sharpe = (mean_return / std_return) * sqrt(365)

# Max drawdown
equity_curve['cummax'] = equity_curve['equity'].cummax()
equity_curve['drawdown'] = (equity - cummax) / cummax
max_drawdown = min(drawdown)

# Calmar ratio
calmar = annual_return / abs(max_drawdown)
```

### Breakdown Analysis
```python
# By regime
regime_stats = trades.groupby('regime').agg({
    'pnl_net': ['sum', 'mean', 'count']
})

# By exit type
exit_stats = trades.groupby('exit_type').agg({
    'pnl_net': ['sum', 'mean', 'count']
})
```

## 16.3 Data Requirements

### Minimum History
```python
# For regime detection
btc_history = 180 days (daily)
total3_history = 180 days (daily)

# For features
symbol_history = 7 days (15m) = 672 candles
```

### Storage Format
```python
# Recommended: Parquet (compressed)
data/historical/15m/{SYMBOL}.parquet
data/historical/1d/{SYMBOL}.parquet
```

### Memory Management
```python
# Load data in chunks if needed
# Use efficient dtypes (float32 instead of float64)
# Clear unused dataframes
```

## 16.4 Implementation Location
- **File:** `data/backtest_engine.py`
- **Class:** `BacktestEngine`
- **Methods:**
  - `run_backtest(symbols, start_date, end_date, interval, btc_data, total3_data)`
  - `_simulate_trading(symbol_data, regime_df, interval)`
  - `_calculate_metrics()`

---

# 17. IMPLEMENTATION MAP

## 17.1 File Structure

```
alpha-sniper-v2.2/
│
├── data/                           # Data infrastructure
│   ├── __init__.py
│   ├── fetcher.py                  # Historical data fetching
│   ├── storage.py                  # Data persistence (Parquet/CSV)
│   └── backtest_engine.py          # Complete backtesting engine
│
├── indicators/                     # Technical indicators
│   ├── __init__.py
│   ├── technical.py                # RSI, EMA, ATR, ADX, etc.
│   ├── regime.py                   # Regime detection (BTC+TOTAL3)
│   └── features.py                 # Feature calculator (all filters)
│
├── strategies/                     # Strategy implementation
│   ├── __init__.py
│   ├── alpha_sniper.py             # Main strategy orchestrator
│   ├── scoring.py                  # Scoring + adaptive thresholds
│   └── risk_model.py               # Risk management + exits
│
├── scanner/                        # Scanner (original + v2)
│   ├── scanner.py                  # Original scanner
│   └── scanner_v2.py               # Enhanced scanner (V2.2)
│
├── trader/                         # Trader (original + v2)
│   ├── trader.py                   # Original trader
│   └── trader_v2.py                # Enhanced trader (V2.2)
│
├── tests/                          # Testing
│   ├── backtest.py                 # Backtesting script
│   └── parameter_sensitivity.py   # Parameter optimization
│
├── config_alpha_sniper.json        # Strategy configuration
├── FULL_CONSOLIDATED_SPEC.md       # This document
└── ALPHA_SNIPER_STRATEGY_DOCS.md   # User documentation
```

## 17.2 Component Matrix

| Spec Section | File | Class/Function | Lines |
|--------------|------|----------------|-------|
| 1. Regime Detection | `indicators/regime.py` | `RegimeDetector.detect_regime()` | 47-113 |
| 2. Trend Filter | `indicators/features.py` | `calculate_trend_features()` | 61-80 |
| 3. Breakout Logic | `indicators/features.py` | `calculate_breakout_features()` | 82-109 |
| 4. Pullback Logic | `indicators/features.py` | `calculate_pullback_features()` | 111-144 |
| 5. RVOL | `indicators/features.py` | `calculate_rvol_features()` | 146-168 |
| 6. OB Imbalance | `indicators/features.py` | `calculate_orderbook_imbalance()` | 255-277 |
| 7. Extension Filter | `indicators/features.py` | `calculate_extension_features()` | 170-197 |
| 8. Exhaustion Filter | `indicators/features.py` | `calculate_exhaustion_features()` | 199-222 |
| 9. Scoring Model | `strategies/scoring.py` | `ScoringModel.calculate_score()` | 29-88 |
| 10. Momentum Bonuses | `strategies/scoring.py` | `_apply_momentum_bonuses()` | 90-135 |
| 11. Rolling Median | `strategies/scoring.py` | `AdaptiveThresholdManager` | 138-310 |
| 12. Entry Conditions | `strategies/alpha_sniper.py` | `_check_entry_conditions()` | 135-185 |
| 13. Risk Model | `strategies/risk_model.py` | `VolatilityAdjustedRiskModel` | 28-118 |
| 14. Exit Rules | `strategies/risk_model.py` | `ExitRulesManager` | 121-318 |
| 15. Parameter Grid | `tests/parameter_sensitivity.py` | `ParameterSensitivityTester` | 47-79 |
| 16. Backtest Engine | `data/backtest_engine.py` | `BacktestEngine` | 1-554 |

---

# 18. USAGE EXAMPLES

## 18.1 Run Backtest

```python
from tests.backtest import BacktestRunner
from datetime import datetime

runner = BacktestRunner()

# Fetch data (one-time)
runner.fetch_and_store_data(
    symbols=['SOLUSDT', 'AVAXUSDT', 'MATICUSDT'],
    interval='15m',
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2024, 12, 31)
)

# Run backtest
results = runner.run_backtest(
    symbols=['SOLUSDT', 'AVAXUSDT', 'MATICUSDT'],
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2024, 12, 31),
    interval='15m',
    initial_equity=10000.0
)

# Results
print(f"Total Return: {results['metrics']['total_return_pct']:.2f}%")
print(f"Sharpe Ratio: {results['metrics']['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {results['metrics']['max_drawdown_pct']:.2f}%")
```

## 18.2 Parameter Optimization

```python
from tests.parameter_sensitivity import ParameterSensitivityTester
from datetime import datetime

tester = ParameterSensitivityTester(output_dir='results/sensitivity')

# Run grid search (sample 50 configs)
results_df = tester.run_grid_search(
    symbols=['SOLUSDT', 'AVAXUSDT', 'MATICUSDT'],
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2024, 12, 31),
    sample_size=50,
    interval='15m'
)

# View top 5 configurations
top_5 = results_df.nlargest(5, 'composite_score')
print(top_5[['total_return_pct', 'sharpe_ratio', 'max_drawdown_pct']])
```

## 18.3 Live Trading (Scanner V2)

```python
from scanner.scanner_v2 import run_scanner
from trader.trader_v2 import run_trader

# Run scanner
signals_count = run_scanner()

# Run trader
run_trader()
```

## 18.4 Manual Strategy Usage

```python
from strategies.alpha_sniper import AlphaSniperStrategy
from indicators.regime import RegimeDetector
from data.fetcher import DataFetcher
import json

# Load config
with open('config_alpha_sniper.json', 'r') as f:
    config = json.load(f)

# Initialize components
strategy = AlphaSniperStrategy(config=config)
regime_detector = RegimeDetector()
fetcher = DataFetcher()

# Get regime data
btc_data = fetcher.fetch_historical_range('BTCUSDT', '1d', start_date, end_date)
total3_data = fetcher.fetch_market_indices('1d', start_date, end_date)['TOTAL3']
regime_info = regime_detector.get_current_regime(btc_data, total3_data)

# Analyze symbol
symbol_data = fetcher.fetch_historical_range('SOLUSDT', '15m', start_date, end_date)
signal = strategy.analyze_symbol(
    symbol='SOLUSDT',
    ohlcv_data=symbol_data,
    regime_info=regime_info,
    ob_imbalance=1.5
)

if signal['signal']:
    # Calculate position parameters
    pos_params = strategy.calculate_position_params(
        signal=signal,
        equity=10000.0,
        regime_info=regime_info
    )

    print(f"Entry: ${pos_params['entry_price']:.4f}")
    print(f"Stop Loss: ${pos_params['stop_loss']:.4f}")
    print(f"TP1: ${pos_params['tp1']:.4f}")
    print(f"TP2: ${pos_params['tp2']:.4f}")
```

---

# APPENDIX A: FORMULA REFERENCE

## Quick Reference Table

| Formula | Expression | Range |
|---------|------------|-------|
| Z-score | `(R_21d - R_180) / std_180` | -∞ to +∞ |
| Trend Ratio | `EMA20 / EMA50` | 0 to +∞ |
| Trend Score | `clamp((ratio - 1) * 10, 0, 1)` | 0 to 1 |
| Breakout Score | `clamp((close - level) / (0.05 * level), 0, 1)` | 0 to 1 |
| Pullback Depth | `(high - low) / (high - breakout)` | 0 to 1+ |
| Pullback Score | `clamp(1 - abs(depth - 0.25) / 0.15, 0, 1)` | 0 to 1 |
| RVOL | `volume / median(volume, 96)` | 0 to +∞ |
| RVOL Score | `clamp((rvol - 1) / 4, 0, 1)` | 0 to 1 |
| OB Imbalance | `sum(bids) / sum(asks)` | 0 to +∞ |
| OB Score | `clamp((imbalance - 1) / 1.5, 0, 1)` | 0 to 1 |
| Final Score | `mean([trend, breakout, rvol, ob, pullback])` | 0 to 1 |
| ATR-based SL | `max(2 * ATR, entry - pullback_low)` | Price units |
| Position Size | `(risk% * equity) / SL_distance` | Quote currency |

---

# APPENDIX B: CONFIGURATION TEMPLATES

## Conservative (Low Risk)
```json
{
  "risk_pct_bull": 0.002,
  "risk_pct_sideways": 0.00125,
  "risk_pct_bear": 0.0008,
  "max_portfolio_heat": 0.01,
  "max_daily_loss_pct": 0.01,
  "atr_sl_mult": 2.5,
  "tp1_mult": 1.5,
  "tp2_mult": 2.5,
  "trail_mult": 2.0,
  "cold_start_threshold": 0.65
}
```

## Balanced (Default)
```json
{
  "risk_pct_bull": 0.004,
  "risk_pct_sideways": 0.0025,
  "risk_pct_bear": 0.0012,
  "max_portfolio_heat": 0.015,
  "max_daily_loss_pct": 0.02,
  "atr_sl_mult": 2.0,
  "tp1_mult": 2.0,
  "tp2_mult": 3.0,
  "trail_mult": 1.5,
  "cold_start_threshold": 0.60
}
```

## Aggressive (High Risk)
```json
{
  "risk_pct_bull": 0.006,
  "risk_pct_sideways": 0.00375,
  "risk_pct_bear": 0.0016,
  "max_portfolio_heat": 0.02,
  "max_daily_loss_pct": 0.03,
  "atr_sl_mult": 1.5,
  "tp1_mult": 2.5,
  "tp2_mult": 3.5,
  "trail_mult": 1.0,
  "cold_start_threshold": 0.55
}
```

---

# DOCUMENT REVISION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 2.2.0 | 2025-11-17 | Complete consolidated specification |
| 2.1.0 | 2025-11-16 | Initial strategy design |

---

**END OF FULL CONSOLIDATED SPECIFICATION**
