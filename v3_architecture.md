# ALPHA SNIPER V3.2 - ARCHITECTURE

## Directory Structure

```
alpha-sniper-v2.2/
├── v3/                          # V3.2 core modules
│   ├── __init__.py
│   ├── regime/                  # Regime detection
│   │   ├── __init__.py
│   │   ├── detector.py          # Multi-signal regime detection
│   │   └── regime_state.py      # Regime state management
│   ├── universe/                # Symbol universe management
│   │   ├── __init__.py
│   │   ├── manager.py           # Point-in-time universe
│   │   └── symbol_state.py      # State machine for symbols
│   ├── scanner/                 # Smart scanner V3
│   │   ├── __init__.py
│   │   ├── features.py          # Feature computation
│   │   ├── scorer.py            # ML-based scoring
│   │   └── signals.py           # Signal generation
│   ├── trader/                  # Smart trader V3
│   │   ├── __init__.py
│   │   ├── executor.py          # Order execution
│   │   ├── position_manager.py  # Position management
│   │   └── exits.py             # SL/TP/trailing logic
│   ├── risk/                    # Risk engine
│   │   ├── __init__.py
│   │   ├── risk_engine.py       # Portfolio risk control
│   │   └── position_sizer.py    # Dynamic sizing
│   ├── execution/               # Execution layer
│   │   ├── __init__.py
│   │   ├── cost_model.py        # Slippage/fee modeling
│   │   └── fill_simulator.py    # Realistic fill simulation
│   ├── learning/                # ML components
│   │   ├── __init__.py
│   │   ├── feature_engineering.py
│   │   ├── label_generator.py
│   │   ├── models.py            # Scanner scoring models
│   │   └── training.py
│   ├── optimization/            # Parameter tuning
│   │   ├── __init__.py
│   │   ├── parameter_space.py
│   │   ├── objective.py
│   │   └── walk_forward.py
│   ├── backtest/                # Backtesting engine
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── metrics.py
│   ├── monitoring/              # Live monitoring
│   │   ├── __init__.py
│   │   ├── live_monitor.py
│   │   ├── circuit_breaker.py
│   │   └── drift_detector.py
│   ├── data/                    # Data layer
│   │   ├── __init__.py
│   │   ├── mexc_client.py       # MEXC API wrapper
│   │   └── data_manager.py      # Data caching/storage
│   └── utils/                   # Utilities
│       ├── __init__.py
│       ├── indicators.py        # Technical indicators
│       └── helpers.py
└── v3_main.py                   # V3.2 main entry point
```

## Module Dependencies

- **Regime Module**: Independent, only needs price data
- **Universe Manager**: Depends on data layer
- **Scanner**: Depends on regime + universe + learning
- **Trader**: Depends on scanner + risk + execution
- **Risk Engine**: Depends on universe + regime
- **Execution Layer**: Independent, used by trader
- **Learning Module**: Depends on data + backtest results
- **Monitoring**: Depends on all modules for health checks

## Data Flow

1. Data Layer fetches MEXC data (OHLCV, orderbook, tickers)
2. Regime Detector analyzes BTC/TOTAL3, outputs regime state
3. Universe Manager filters symbols (liquidity, spread, delisting)
4. Scanner:
   - Computes features for each symbol
   - Runs ML scoring model
   - Generates ranked signals
5. Trader:
   - Checks portfolio risk limits
   - Sizes positions using Risk Engine
   - Executes via Execution Layer
6. Position Manager handles open trades (SL/TP/trailing)
7. Monitoring watches all metrics, can trigger circuit breakers

## Key Differences from V2.2

| Feature | V2.2 | V3.2 |
|---------|------|------|
| Regime Detection | None | Multi-signal with hysteresis |
| Symbol States | None | State machine (6 states) |
| Scanner Scoring | Hand-weighted | ML model (trained) |
| Parameter Selection | Manual | Optimized via walk-forward |
| Risk Sizing | Fixed % | Regime-adjusted dynamic |
| Execution Model | Optimistic | Realistic slippage/fees |
| Monitoring | Basic alerts | Circuit breakers + drift detection |
| Backtesting | Placeholder | Full PIT simulation |

