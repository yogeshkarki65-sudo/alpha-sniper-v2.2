# Alpha Sniper v2.2 - Technical Review Request

## Project Overview

Alpha Sniper v2.2 is an automated cryptocurrency trading bot for MEXC exchange that implements a self-learning quantitative trading system. The bot scans for high-momentum USDT pairs, executes trades with comprehensive risk management, and continuously optimizes its strategy through statistical learning.

## System Architecture

### 1. Market Scanner (`scanner/`)

**Functionality:**
- Fetches 24h ticker data from MEXC API for all USDT pairs
- Filters top 60 pairs by quote volume to reduce API load
- Applies liquidity filter (min $100k 24h volume) and spread filter (max 0.5%)
- Computes 4 quantitative features per symbol:

**Feature Engineering:**
```python
# RVOL (Relative Volume)
avg_hourly_volume = quote_volume / 24
rvol = current_volume / avg_hourly_volume

# Velocity (Price Momentum)
velocity = 24h_price_change_percent

# Trend (Position in Daily Range)
trend = (last_price - low_price) / (high_price - low_price)

# Orderbook Imbalance
imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
```

**Scoring System:**
- Weighted composite score from normalized features
- Default weights: 25% each (rvol, velocity, trend, orderbook_imbalance)
- Weights are dynamically adjusted by learning system
- Signals generated for scores ≥ 70 (threshold configurable)

### 2. Trading Engine (`trader/`)

**Position Management:**
- Opens positions from highest-scoring unconsumed signals
- Symbol cooldown: 6 hours between trades on same pair
- Correlation check: Prevents clustering in correlated assets
- Position sizing: Kelly-inspired using `max_loss_usd / (entry_price * stop_loss_pct)`
- Cap at 20% of equity per position
- "MOON signal" multiplier: 1.5x size for scores ≥ 90

**Exit Strategy (Multi-tiered):**
1. **Hard Stop Loss**: -5% from entry
2. **Take Profit**: +10% from entry
3. **Trailing Stop**:
   - Activates at +2% profit
   - Trails 1% below highest price reached
4. **Time-based Exit**: 24 hours max hold time

**Execution Model:**
- Simulated slippage: +0.05% on entry, -0.05% on exit
- Taker fees: 0.1% on both entry and exit
- All costs deducted from P&L calculations

### 3. Risk Management (`risk/`)

**Real-time Risk Controls:**
- Daily drawdown limit: 2% from daily high-water mark
- Max position risk: 0.5% of equity per trade
- Max concurrent positions: 2
- Max correlated positions: 2 (using 24h price change as correlation proxy)

**Auto-pause Mechanism:**
- Writes `TRADING_PAUSED=true` to .env on breach
- Sends Telegram alert
- Resets automatically at daily reset (midnight UTC)

**Equity Tracking:**
```python
current_equity = SIM_EQUITY_START + sum(all_net_pnl)
daily_hwm = max(daily_hwm, current_equity)
drawdown_pct = ((daily_hwm - current_equity) / daily_hwm) * 100
```

### 4. Self-Learning System (`learning/`)

**Statistical Validation Approach:**
- Triggered hourly, requires minimum 30 trades
- Fetches trades from last 30 days with associated signal features
- 70/30 train/test split with random shuffle

**Information Coefficient Method:**
```python
# For each feature
train_ic = pearson_correlation(feature_values, pnl_outcomes)
test_ic = pearson_correlation(test_feature_values, test_pnl_outcomes)

# Only update if test_ic > 0 (out-of-sample validation)
if avg_test_ic > 0:
    new_weights = normalize(train_ic_values)
```

**Weight Update Logic:**
- Caps changes at ±15% per update to prevent overfitting
- Normalizes weights to sum to 1.0
- Logs all updates with train/test IC for audit trail
- Alerts on Telegram if weight change exceeds 10%

### 5. Monitoring & Reporting (`monitoring/`)

**Health Check API:**
- Flask server on port 8080
- Endpoint: `GET /health`
- Returns: equity, position count, daily P&L, last run timestamps

**Telegram Integration:**
- Real-time alerts for all position entries/exits
- Risk events (drawdown, pauses, weight changes)
- Daily report at 9:00 AM UTC with:
  - Current equity, daily/weekly P&L
  - Win rates, Sharpe ratio
  - Best/worst trades

**Performance Metrics:**
```python
sharpe_ratio = (mean_pnl_pct / std_pnl_pct) * sqrt(365)
max_drawdown = max((peak - valley) / peak * 100)
win_rate = winning_trades / total_trades * 100
```

### 6. Capital Scaling (`deployment/`)

**Auto-scale Logic:**
- Evaluates every 50 trades
- Requirements for +20% capital increase:
  - Win rate > 55%
  - Sharpe ratio > 1.0
  - Max drawdown < 5%
- Automatically updates `SIM_EQUITY_START` in .env
- Sends Telegram notification with metrics

## Database Schema (SQLite)

```sql
signals: id, symbol, score, rvol, velocity, trend, orderbook_imbalance,
         last_price, created_at, consumed

positions: id, signal_id, symbol, entry_price, position_size,
          stop_loss_price, take_profit_price, highest_price,
          trailing_stop_active, trailing_stop_price,
          opened_at (TEXT), opened_at_timestamp (REAL)

trades: id, signal_id, symbol, entry_price, exit_price, position_size,
        gross_pnl_usd, entry_fee_usd, exit_fee_usd, slippage_cost_usd,
        net_pnl_usd, pnl_pct, exit_reason, opened_at, closed_at,
        hold_time_hours

learning_log: id, weights_before, weights_after, train_ic, test_ic,
              num_trades_used, created_at

daily_stats: id, date, starting_equity, ending_equity, high_water_mark,
             max_drawdown_pct, num_trades, win_rate, total_fees
```

## Recent Bug Fixes (Latest Commit)

**Critical Issues Resolved:**

1. **Position Timestamp Bug** (database/models.py, trader/trader.py):
   - Problem: Was accessing `pos[10]` (TEXT field) instead of `pos[11]` (REAL timestamp)
   - Impact: Hold time calculations would fail or be incorrect
   - Fix: Changed all timestamp references to use `pos[11]` (opened_at_timestamp)

2. **Validation Return Consistency** (learning/validation.py):
   - Problem: Returned `None, None` tuple instead of single `None`
   - Impact: Caller expected single value when validation fails
   - Fix: Changed to `return None`

## Configuration Management

All settings via environment variables (.env):
- Trading parameters (stop loss, take profit, trailing stop)
- Risk limits (drawdown, position size, correlations)
- API endpoints and credentials
- Learning parameters (min trades, weight change limits)
- Telegram bot credentials
- Scheduler intervals

## Known Limitations & Risks (from CRITICAL_ISSUES.md)

1. **Exchange/API Risk**: No secondary validation if MEXC returns stale/bad data
2. **Slippage Model**: Fixed percentages may not reflect real market conditions
3. **Correlation Check**: Uses simple 24h % change, not true correlation coefficient
4. **Daily Reset Timezone**: Relies on container local time
5. **Capital Scaling**: Uses trailing 50 trades, may scale up before regime change
6. **Learning Module**: Hard-coded feature indices, fragile to schema changes
7. **No Backtest Harness**: True historical replay not implemented
8. **Emergency Stop**: Updates .env but doesn't kill Docker container

## Deployment

- Dockerized with docker-compose.yml
- Requires: Python 3.9+, SQLite, Flask, NumPy, pandas, scipy
- Health check for orchestration readiness
- Persistent volumes: ./data (database, weights)

## Questions for Review

**1. Architecture & Design:**
- Is the feature engineering approach sound for crypto momentum trading?
- Should we implement more sophisticated correlation measures (rolling correlation matrix)?
- Is the single-threaded scheduler approach sufficient, or should we use async/concurrent execution?

**2. Risk Management:**
- Is 2% daily drawdown limit too aggressive/conservative?
- Should position sizing use Kelly criterion with win rate estimates?
- Should we implement portfolio-level stops (in addition to position-level)?

**3. Learning System:**
- Is Pearson correlation (IC) the best metric for feature importance?
- Should we use more sophisticated methods (random forests, gradient boosting)?
- Should we implement walk-forward optimization instead of random train/test split?
- Is 15% max weight change per update appropriate?

**4. Exit Strategy:**
- Are the stop loss (-5%) and take profit (+10%) levels optimal?
- Should trailing stop parameters be dynamic based on volatility?
- Is time-based exit (24h) necessary, or should we let positions run?

**5. Production Readiness:**
- What additional error handling/retry logic is needed for API calls?
- Should we implement circuit breakers for API failures?
- Do we need more sophisticated logging (structured logs, log aggregation)?
- Should we add more comprehensive unit/integration tests?

**6. Performance Optimization:**
- Can scanner be optimized to reduce API calls?
- Should we cache ticker data with TTL?
- Is SQLite sufficient, or should we migrate to PostgreSQL?

**7. Feature Additions:**
- Should we add more features (RSI, MACD, volume profile)?
- Should we implement multi-timeframe analysis?
- Should we add sentiment analysis (social media, news)?
- Should we implement portfolio rebalancing logic?

**8. Security:**
- Are API credentials properly secured?
- Should we implement rate limiting on health check endpoint?
- Do we need authentication for the Flask health check server?

## Testing Strategy

Currently minimal testing. Recommendations needed for:
- Unit tests for calculation functions
- Integration tests for database operations
- Mock API tests for scanner/trader
- Backtesting framework for strategy validation

## Performance Expectations

Based on design:
- Expected Sharpe Ratio: 1.0-2.0 (after optimization)
- Expected Win Rate: 55-65%
- Expected Max Drawdown: <5% (with 2% daily stops)
- Expected Trade Frequency: 2-10 trades/day
- Expected Hold Time: 2-12 hours average

---

**Request:** Please review this system and provide feedback on:
1. Critical flaws or vulnerabilities I should address immediately
2. Improvements to the learning system and feature engineering
3. Production hardening recommendations
4. Performance optimization opportunities
5. Any other architectural or implementation concerns

Thank you for your detailed analysis!
