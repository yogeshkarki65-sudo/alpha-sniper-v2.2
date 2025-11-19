# CRITICAL ISSUES - Alpha Sniper V4.0

**Last Updated:** 2025-11-19
**Status:** Production-ready with known limitations

---

## 🟢 RESOLVED (V4.0 Improvements)

### **1. Execution Engine - FIXED ✅**

**V3 Problem:**
- Fixed slippage percentage (0.1%)
- No orderbook depth checking
- No liquidity filtering
- Resulted in: terrible fills on thin books, capital burned on slippage

**V4 Solution:**
- ✅ Real-time orderbook depth analysis
- ✅ Dynamic spread checking (reject if >0.05%)
- ✅ Depth filtering (bid/ask depth must be >$10k)
- ✅ Dynamic position caps:
  - Max 8% of equity
  - Max 2.5% of 1h volume
  - Max 180% of visible depth
  - Hard cap $2,500
- ✅ Slippage modeling: `base + spread/2 + depth_pressure`
- ✅ Symbol blacklist (24h ban for bad symbols)
- ✅ Random order rejection simulation (0.5% of orders)

**Status:** Production-ready. Protects capital from MEXC liquidity traps.

---

### **2. Position Persistence - FIXED ✅**

**V3 Problem:**
- Positions lost on restart/crash
- No state recovery

**V4 Solution:**
- ✅ Auto-save to `positions.json` after every change
- ✅ Auto-load on startup
- ✅ Safe restarts without losing trades

**Status:** Production-ready.

---

### **3. MEXC API Compatibility - FIXED ✅**

**V3 Problem:**
- Used `1h` interval (not supported by MEXC)
- Wrong parameter names (`limit` vs `depth`)
- 400 errors on klines requests

**V4 Solution:**
- ✅ Maps `1h` → `60m` for MEXC compatibility
- ✅ Correct parameter names (`depth` for orderbook)
- ✅ Rate limiting + retry logic
- ✅ Caching to reduce API load

**Status:** Production-ready.

---

### **4. Telegram Notifications - FIXED ✅**

**V3 Problem:**
- Async event loop errors
- "Pool timeout" on rapid messages

**V4 Solution:**
- ✅ Proper event loop reuse
- ✅ Handles multiple notifications without crashes

**Status:** Production-ready.

---

## 🟡 KNOWN LIMITATIONS (Acceptable Trade-offs)

### **1. Backtest Harness - PARTIAL**

**Current State:**
- ✅ `test_v4_system.py` validates all components
- ❌ No full historical replay backtest harness

**What's Missing:**
- Replaying 2019-2024 candles through V4 pipeline
- Automated equity curve generation
- Statistical validation (WR, PF, Sharpe, DD)

**Workaround:**
- Manual backtesting done externally (proven: $500 → $2,560)
- All MEXC quirks modeled in execution engine
- `test_v4_system.py` ensures components work correctly

**Risk Level:** 🟡 Medium
- V4 code matches backtest spec
- Real MEXC data used in testing
- Position sizing + exits match backtest exactly

**Mitigation:**
- Run SIM mode for 30-50 trades
- Verify stats match backtest (WR ~68%, DD <20%)
- Start LIVE with small equity ($100-$200)

**Future Work:**
- Build `v4/backtest/backtest_harness.py` (see stub below)

---

### **2. Funding Edge - TODO (FUTURES Only)**

**Current State:**
- ✅ Rotation edge working (volume-based)
- ✅ Dominance edge working (BTC dominance)
- ⚠️ Funding edge stubbed (returns False)

**Implementation Status:**
```python
# v4/edges/edge_detector.py:72
# TODO: Implement when MARKET_TYPE=FUTURES
return False, 0.0
```

**Impact:**
- **SPOT mode:** No impact (funding not available anyway)
- **FUTURES mode:** Missing one edge signal (rotation + dominance still work)

**Risk Level:** 🟡 Low-Medium
- Other edges operational
- Backtest included funding logic
- Missing ~2% score bonus in some setups

**Mitigation:**
- Funding edge was conservative in backtest (rarely triggered)
- Rotation + dominance edges sufficient for most signals

**Future Work:**
- Implement MEXC Futures funding rate API
- Add compression detection logic

---

### **3. SPOT vs FUTURES - Manual Configuration Required**

**Current State:**
- ✅ SPOT mode: LONG only (correct)
- ✅ FUTURES mode: LONG + SHORT (correct)
- ⚠️ Must manually set `MARKET_TYPE` in .env

**Behavior:**
| Mode | LIVE SPOT | LIVE FUTURES | SIM SPOT | SIM FUTURES |
|------|-----------|--------------|----------|-------------|
| LONG | ✅ | ✅ | ✅ | ✅ |
| SHORT | ❌ | ✅ | ✅ (testing) | ✅ |

**Risk Level:** 🟡 Low
- Clear documentation
- Correct logic enforced in code
- Warning printed when BEAR + SPOT + LIVE

**Mitigation:**
- User must read docs
- Test in SIM first
- Telegram alerts show regime + mode

---

### **4. Daily Loss Cap - Not Integrated with Legacy RiskManager**

**Current State:**
- ✅ V4 has `MAX_DAILY_DRAW_PCT` in .env
- ❌ Not yet enforced in `v4_main.py`
- ⚠️ Legacy `risk/risk_manager.py` exists but unused

**Risk Level:** 🟡 Medium
- V4 has portfolio heat limit (1.5% max risk)
- Position-level risk controls working
- Missing circuit breaker for bad days

**Mitigation:**
- Portfolio heat limits aggregate risk
- Manual monitoring during first weeks
- Small start equity ($100-$200)

**Future Work:**
- Add daily loss tracking to `v4_main.py`
- Check before opening new positions
- Log to positions.json or separate file

---

## 🔴 REAL RISKS (Exchange & Market)

### **1. MEXC Exchange Risk - UNCONTROLLABLE**

**Risks:**
- API downtime during volatile moves
- Order rejections without warning
- Withdrawal issues
- Regulatory changes

**Mitigation:**
- ✅ Retry logic with exponential backoff
- ✅ Timeout handling (10s max per request)
- ✅ Error logging + Telegram alerts
- ⚠️ Keep majority of funds OFF exchange
- ⚠️ Set hard caps on position sizes

**Risk Level:** 🔴 High (inherent to centralized exchanges)

---

### **2. Market Risk - UNCONTROLLABLE**

**Black Swan Events:**
- Flash crashes (>30% in minutes)
- Multi-day bear capitulation
- Sector rotations away from tracked altcoins

**Backtest Includes:**
- ✅ 2020 COVID crash (-50% BTC)
- ✅ 2022 Luna collapse
- ✅ 2023 FTX aftermath
- ✅ Max DD: -18% despite these events

**Mitigation:**
- ✅ Regime-adaptive risk (0.12% in BEAR vs 0.30% in BULL)
- ✅ Time exits prevent holding losers
- ✅ Portfolio heat cap (1.5% total)
- ⚠️ Stop trading if equity drops >20% from peak

**Risk Level:** 🔴 High (inherent to crypto trading)

---

### **3. Slippage in Live vs Backtest - DIVERGENCE RISK**

**Risk:**
- Backtest assumes modeled slippage
- Live slippage may be worse during:
  - Low liquidity hours (3-6am UTC)
  - High volatility (news events)
  - MEXC server issues

**Mitigation:**
- ✅ Conservative slippage model (0.05% base)
- ✅ Reject orders with >1.2% expected slippage
- ✅ Blacklist bad symbols for 24h
- ✅ Dynamic caps limit exposure to thin books

**Validation:**
- Run SIM mode and compare:
  - Expected slippage (from execution engine)
  - Actual fills (if running paper trading with real quotes)

**Risk Level:** 🔴 Medium-High

---

### **4. Parameter Overfitting - MODEL RISK**

**Risk:**
- 498 trades over 6 years
- Parameters may be optimized to 2019-2024 conditions
- 2025+ markets may behave differently

**Indicators of Overfitting:**
- WR drops below 55% (vs 68% backtest)
- DD exceeds -25% (vs -18% backtest)
- Profit factor <1.2 (vs ~2.0 backtest)

**Mitigation:**
- ✅ Regime-adaptive logic (not curve-fit)
- ✅ Conservative risk (0.12-0.30% per trade)
- ✅ Broad parameter ranges (not hyper-optimized)
- ⚠️ Monitor first 30-50 LIVE trades closely
- ⚠️ Stop if stats diverge >20% from backtest

**Risk Level:** 🔴 Medium

---

## 📋 PRE-FLIGHT CHECKLIST

### **Before SIM:**
- [ ] All tests pass: `python test_v4_system.py`
- [ ] Telegram working: `python test_telegram.py`
- [ ] `.env` configured correctly (MODE=SIMULATION)
- [ ] Universe builds (200 symbols found)
- [ ] Regime detection working (shows current regime)

### **Before LIVE:**
- [ ] SIM ran for 30-50 trades
- [ ] WR within 10% of backtest (~68%)
- [ ] Max DD within 5% of backtest (-18%)
- [ ] No critical errors in logs
- [ ] Telegram alerts working
- [ ] Position persistence tested (restart bot, positions reload)
- [ ] MEXC API keys added (LIVE mode only)
- [ ] Start with small equity ($100-$200)
- [ ] Set hard position cap ($100-$500 per trade)

---

## 🔧 DEBUGGING

### **Issue: No trades for extended period**

**Diagnosis:**
1. Check regime: `grep "Regime:" <output>`
   - BEAR + SPOT + LIVE = 0 trades (CORRECT)
   - NEUTRAL = 0 trades (wait for regime shift)
2. Check universe: "Empty universe" = API issue or volume filter too strict
3. Check filters: Enable debug logging in `v4/scanner/filters.py`

**Fix:**
- Wait for regime shift (BULL/SIDEWAYS for LONGS)
- Lower `MIN_24H_QUOTE_VOLUME` if universe empty
- Check MEXC API status

---

### **Issue: High rejection rate**

**Diagnosis:**
```
[Execution] ❌ Symbol rejected: spread=0.09% or depth=$1,861
```

**Cause:** Execution engine protecting you from bad fills!

**Fix:**
- ✅ This is GOOD - keeps you out of thin books
- If too aggressive: increase `MAX_ALLOWED_SLIPPAGE_PCT` (default 1.2%)
- If too lenient: decrease to 0.8%

---

### **Issue: Positions not loading after restart**

**Diagnosis:**
Check for `positions.json` in project root:
```bash
ls -la positions.json
```

**Fix:**
- If missing: Position manager failed to save (check logs)
- If exists but not loading: Check JSON format (must be valid)
- If corrupted: Delete file (WARNING: loses position state)

---

## 📊 MONITORING METRICS

**Track these in first 30-50 trades:**

| Metric | Backtest | Target Range | Red Flag |
|--------|----------|--------------|----------|
| Win Rate | 68% | 60-75% | <55% or >80% |
| Profit Factor | 2.0 | 1.5-2.5 | <1.2 |
| Avg Win | +4.2% | +3-6% | <2% |
| Avg Loss | -1.8% | -1-3% | >-4% |
| Max DD | -18% | -15 to -25% | >-30% |
| Trades/Week | ~1.6 | 1-3 | <0.5 or >5 |

**Alerts:**
- 3 consecutive losses → Review signals manually
- DD >15% → Reduce position sizes by 50%
- DD >25% → STOP TRADING, investigate
- WR <50% after 20 trades → Parameter drift, halt

---

## 🆘 EMERGENCY STOPS

**Auto-stop conditions (implement in future):**
1. Daily draw >2.5%
2. Max DD >25%
3. 5+ consecutive losses
4. MEXC API errors >50% of requests

**Manual stop triggers:**
1. Regime detector malfunctions (stuck in one regime)
2. Execution engine bypassed (all orders executing without checks)
3. Position manager not saving (positions.json not updating)
4. Telegram alerts silent (no notifications for 24h)

---

## 🔮 FUTURE IMPROVEMENTS

**Priority 1 (Safety):**
- [ ] Implement daily loss cap enforcement
- [ ] Add equity tracking to database
- [ ] Emergency stop API (Telegram command: `/stop`)

**Priority 2 (Performance):**
- [ ] Funding edge implementation (FUTURES)
- [ ] Full backtest harness with historical replay
- [ ] Multi-symbol correlation analysis

**Priority 3 (UX):**
- [ ] Web dashboard for monitoring
- [ ] Performance analytics (Sharpe, Sortino, Calmar)
- [ ] Trade journal with screenshots

---

## 📝 VERSION HISTORY

**V4.0 (2025-11-19) - CURRENT:**
- ✅ Regime-adaptive strategy
- ✅ Execution engine with liquidity filtering
- ✅ Position persistence
- ✅ MEXC quirks modeled
- ✅ Telegram notifications
- ✅ SPOT/FUTURES mode support

**V3.2 (Legacy):**
- ⚠️ Fixed slippage
- ⚠️ No liquidity filtering
- ❌ DO NOT USE

**V2.2 (Legacy):**
- ❌ DO NOT USE

---

**Remember:** Trading is risky. V4.0 reduces risk through smart execution and regime adaptation, but cannot eliminate it. Start small, monitor closely, scale gradually.

**Alpha Sniper V4.0** - Built for MEXC reality. 🎯
