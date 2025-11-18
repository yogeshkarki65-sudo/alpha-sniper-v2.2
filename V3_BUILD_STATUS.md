# ALPHA SNIPER V3.2 - BUILD STATUS

**Last Updated**: 2025-11-18

---

## ✅ PHASE 1: FOUNDATION (COMPLETED)

### Core Infrastructure

| Module | Status | File | Description |
|--------|--------|------|-------------|
| **Data Layer** | ✅ DONE | `v3/data/mexc_client.py` | MEXC API client with caching, rate limiting, retry logic |
| **Utilities** | ✅ DONE | `v3/utils/indicators.py` | Technical indicators (EMA, ATR, RSI, RVOL, Z-score) |
| **Regime Detector** | ✅ DONE | `v3/regime/detector.py` | Multi-signal regime detection with hysteresis (BULL/SIDEWAYS/BEAR) |
| **Symbol State Machine** | ✅ DONE | `v3/universe/symbol_state.py` | 6-state machine (FLAT/BASING/BREAKING_OUT/EXTENDED/FAILED/COOLDOWN) |
| **Universe Manager** | ✅ DONE | `v3/universe/manager.py` | Point-in-time universe with liquidity/spread filtering |
| **Execution Cost Model** | ✅ DONE | `v3/execution/cost_model.py` | Realistic slippage modeling + fill tracking |
| **Risk Engine** | ✅ DONE | `v3/risk/risk_engine.py` | Regime-adaptive sizing, portfolio heat, daily loss cap |

### Key Features Implemented

**Regime Detection:**
- Multi-signal voting (Z-score, EMA crossover, volatility regime, alt strength)
- 4-hour hysteresis to prevent whipsaw
- Risk multipliers: BULL=1.0x, SIDEWAYS=0.6x, BEAR=0.3x

**Symbol State Machine:**
- Prevents chasing extended moves (EXTENDED state)
- Blocks re-entry on failed setups (COOLDOWN state)
- Identifies compression patterns (BASING state)

**Execution Model:**
- Per-symbol slippage tracking
- Depth-aware sizing (avoid >10% of book)
- Adverse selection modeling (8bps on aggressive fills)
- Realistic backtest fills (pessimistic assumptions)

**Risk Management:**
- Regime-adaptive per-trade risk (0.12% to 0.4%)
- Portfolio heat cap (1.5%)
- Daily loss cap (2%)
- Max concurrent positions (5)
- Correlation checks (max 2 per sector)

---

## 🚧 PHASE 2: SMART SCANNER & TRADER (NEXT)

### Remaining Modules

| Module | Status | Description |
|--------|--------|-------------|
| **Scanner Features** | TODO | Feature extraction pipeline (RVOL, trend, compression, OB imbalance) |
| **Scanner Scorer** | TODO | ML-based scoring model (initially hand-weighted, then learned) |
| **Trader Executor** | TODO | Order placement, entry style selection |
| **Position Manager** | TODO | SL/TP/trailing logic, no-follow-through rule |
| **Backtest Engine** | TODO | Full point-in-time backtest with realistic fills |
| **Simple Validation** | TODO | Basic backtest to validate core edge |

---

## 📊 CURRENT CAPABILITIES

**What V3.2 Can Do RIGHT NOW:**

1. ✅ Detect market regime (BULL/SIDEWAYS/BEAR) using BTC + alt data
2. ✅ Filter universe to top 150 liquid USDT pairs with spread < 1.2%
3. ✅ Track symbol states (detect basing, breakouts, extensions, failures)
4. ✅ Calculate regime-adjusted position sizes
5. ✅ Enforce portfolio risk limits (heat, daily loss, position count)
6. ✅ Estimate execution costs per symbol
7. ✅ Manage open positions with P&L tracking

**What's Missing:**

- ❌ Scanner logic (feature computation + signal generation)
- ❌ Trader execution (order placement)
- ❌ Position exits (SL/TP/trailing/time)
- ❌ Backtest framework
- ❌ ML training pipeline
- ❌ Parameter optimization
- ❌ Live monitoring

---

## 🎯 IMMEDIATE NEXT STEPS

### Step 1: Build Scanner (2-3 hours)
- Feature extraction: RVOL, trend, compression, position in range, OB imbalance
- Hand-weighted scoring (initial version before ML)
- Signal ranking and top-K selection

### Step 2: Build Trader (2-3 hours)
- Entry execution with cost model integration
- SL/TP calculation using ATR
- Position management with trailing stops
- No-follow-through rule (exit dead trades early)

### Step 3: Simple Backtest (1 hour)
- Quick validation on recent data (last 30 days)
- Check if base strategy has edge (profit factor > 1.3)
- If yes → continue to ML/optimization
- If no → redesign entry logic

### Step 4: Full Backtest Engine (3-4 hours)
- Point-in-time universe simulation
- Realistic fill simulation
- Performance metrics (Sharpe, Sortino, Calmar, win rate, etc.)
- Trade-by-trade analysis

---

## 📈 ARCHITECTURE QUALITY

**Compared to V2.2:**

| Aspect | V2.2 | V3.2 Status |
|--------|------|-------------|
| Regime Awareness | ❌ None | ✅ Multi-signal with hysteresis |
| Symbol States | ❌ None | ✅ 6-state machine |
| Risk Sizing | ⚠️ Fixed | ✅ Regime-adaptive |
| Execution Modeling | ⚠️ Optimistic | ✅ Realistic slippage |
| Correlation Control | ⚠️ Basic | ✅ Sector-aware |
| Universe Management | ⚠️ Simple | ✅ Point-in-time aware |
| Position Limits | ⚠️ Simple | ✅ Multi-layer (heat/daily/count) |

**Code Quality:**
- ✅ Modular design (clean separation of concerns)
- ✅ Type hints throughout
- ✅ Singleton patterns for global state
- ✅ Comprehensive docstrings
- ✅ Error handling and logging
- ✅ Production-ready structure

---

## 💡 VALIDATION PLAN

Before adding ML/optimization complexity, we'll validate the base strategy:

```python
# Simple test:
# 1. Filter universe (liquid, tight spread)
# 2. Detect regime (BULL mode)
# 3. Find symbols in BASING state
# 4. Enter on breakout with RVOL > 2.0
# 5. Exit at 2R profit or -1R stop or 24h time
#
# If this DOESN'T work → rethink entry logic
# If this DOES work → add ML scoring and optimization
```

**Target Baseline Metrics (Simple Strategy):**
- Profit Factor: > 1.3
- Win Rate: > 35%
- Sharpe Ratio: > 0.5
- Max Drawdown: < 15%

If we hit these on recent 3-6 months of data, the edge exists and we can enhance it with ML.

---

## 🚀 ESTIMATED TIMELINE TO LIVE

**Realistic Timeline:**

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Phase 2**: Scanner + Trader | 1-2 days | Build scanner, trader, basic backtest |
| **Phase 3**: Validation | 1 day | Test on 3-6 months data, validate edge |
| **Phase 4**: ML Training | 2-3 days | Feature engineering, label generation, model training |
| **Phase 5**: Optimization | 2-3 days | Parameter tuning, walk-forward validation |
| **Phase 6**: Monitoring | 1 day | Circuit breakers, drift detection |
| **Phase 7**: Paper Trading | 7-14 days | Live paper trade, monitor performance |
| **Phase 8**: Live (Small)** | 7+ days | 10% capital, careful monitoring |

**Total**: ~3 weeks to careful live deployment

---

## 🎓 WHAT WE'VE LEARNED

**Key Insights from V3.2 Build:**

1. **Regime matters**: Same strategy performs very differently in bull vs bear
2. **State machines prevent mistakes**: Don't chase EXTENDED, don't re-buy FAILED
3. **Execution costs matter**: 0.5% round-trip cost = need 1R+ edges to be profitable
4. **Portfolio heat > position count**: Better to track total risk than just count
5. **Point-in-time is critical**: Can't backtest on current universe looking back 6 months

**Advantages Over Typical Bots:**

- ✅ Regime-adaptive (not blindly momentum in bear markets)
- ✅ Quality gating (only take top-ranked signals)
- ✅ State-aware (don't re-buy failures)
- ✅ Multi-layer risk control (not just per-trade stops)
- ✅ Realistic cost modeling (not overly optimistic fills)

---

## 📝 NOTES

**Data Availability:**
- ✅ BTC/ETH data available on MEXC for regime
- ⚠️ TOTAL3 not on MEXC → using ETHUSDT as alt proxy
- ✅ 24h tickers, orderbook, klines all working
- ⚠️ Historical data limited to 1000 bars per call

**Potential Issues:**
- MEXC API can be slow/unreliable → need retry logic (✅ implemented)
- Spread can widen suddenly on low-cap alts → filter by spread (✅ implemented)
- Delisting not announced via API → track last_seen timestamps (✅ implemented)

---

**Next Command**: Build scanner + trader modules, then run validation backtest.
