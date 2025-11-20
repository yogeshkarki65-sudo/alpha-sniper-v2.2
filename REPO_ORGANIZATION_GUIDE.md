# Repository Organization Guide

## Current Situation

You have **multiple bot versions** in a single repository:

- **V2.2** (Original) - `main.py`, `scanner/`, `trader/`, `database/` directories
- **V4 (V3.2)** - `v3/` directory, `v3_main.py`
- Multiple feature branches with different experiments

### Current Challenges:

1. **Version Confusion**: Two different systems in same repo with overlapping names
2. **Mixed Codebases**: V2.2 files coexist with V4 files, causing confusion
3. **Different Data Stores**: V2.2 uses SQLite (`data/trades.db`), V4 uses JSON (`sim_performance.json`)
4. **Branch Complexity**: Many experimental branches make it hard to track production versions

---

## Recommendation: Keep Single Repo with Better Organization

### ✅ **RECOMMENDED: Reorganize Current Repo**

**Why keep single repo:**
- Easier to track all versions in one place
- Can compare performance between versions
- Simpler deployment (single repo to clone)
- Unified issue tracking and documentation

**Proposed Structure:**

```
alpha-sniper/
├── README.md                          # Main readme pointing to versions
├── .gitignore
├── requirements.txt                   # Common requirements
│
├── v2/                                # V2.2 codebase
│   ├── README.md                      # V2-specific docs
│   ├── main.py
│   ├── config/
│   ├── scanner/
│   ├── trader/
│   ├── database/
│   ├── risk/
│   ├── learning/
│   ├── monitoring/
│   ├── deployment/
│   ├── requirements.txt               # V2-specific requirements
│   └── generate_performance_report.py
│
├── v4/                                # V4 codebase (currently v3/)
│   ├── README.md                      # V4-specific docs
│   ├── v4_main.py                     # Renamed from v3_main.py
│   ├── core/                          # Renamed from v3/
│   │   ├── regime/
│   │   ├── universe/
│   │   ├── scanner/
│   │   ├── trader/
│   │   ├── risk/
│   │   ├── execution/
│   │   ├── learning/
│   │   ├── backtest/
│   │   ├── monitoring/
│   │   ├── data/
│   │   └── utils/
│   ├── requirements.txt               # V4-specific requirements
│   ├── generate_performance_report.py
│   └── V4_ARCHITECTURE.md
│
├── docs/                              # Shared documentation
│   ├── deployment.md
│   ├── configuration.md
│   ├── comparison-v2-vs-v4.md
│   └── troubleshooting.md
│
├── scripts/                           # Shared utility scripts
│   ├── backup_data.sh
│   ├── check_health.sh
│   └── compare_versions.py
│
└── data/                              # Data directory (gitignored)
    ├── v2/
    │   └── trades.db
    └── v4/
        └── sim_performance.json
```

---

## Alternative: Separate Repositories

### ⚠️ **ALTERNATIVE: Split into Multiple Repos**

**Only if:**
- You're deploying versions to different servers permanently
- Teams are working independently on each version
- You want to version them completely separately

**Structure:**

```
alpha-sniper-v2/           # Separate repo
└── (all V2 code)

alpha-sniper-v4/           # Separate repo
└── (all V4 code)
```

**Downsides:**
- Harder to compare versions
- Duplicate documentation
- More complex to maintain
- Loses shared history

---

## Migration Plan (Recommended Approach)

### Step 1: Create Branch for Reorganization

```bash
git checkout -b reorganize-repo
```

### Step 2: Reorganize V2 Files

```bash
# Create v2 directory
mkdir v2

# Move V2 files
mv main.py v2/
mv scanner v2/
mv trader v2/
mv database v2/
mv risk v2/
mv learning v2/
mv monitoring v2/
mv deployment v2/
mv config v2/
mv generate_performance_report.py v2/

# Copy requirements for V2
cp requirements.txt v2/requirements.txt
```

### Step 3: Reorganize V4 Files

```bash
# Rename v3 to v4
mv v3 v4_temp
mkdir v4
mv v4_temp v4/core

# Move V4 files
mv v3_main.py v4/v4_main.py
mv v3_architecture.md v4/V4_ARCHITECTURE.md
mv V3_BUILD_STATUS.md v4/V4_BUILD_STATUS.md
mv requirements_v3.txt v4/requirements.txt
mv test_v3_integration.py v4/
mv generate_v4_performance_report.py v4/
```

### Step 4: Update Import Paths

In all V4 files, update imports:
```python
# Old
from v3.regime.detector import regime_detector

# New
from v4.core.regime.detector import regime_detector
```

### Step 5: Update Documentation

Create main README.md explaining both versions.

### Step 6: Test Both Versions

```bash
# Test V2
cd v2 && python3 main.py --help

# Test V4
cd v4 && python3 v4_main.py --help
```

### Step 7: Commit and Deploy

```bash
git add .
git commit -m "Reorganize repo: separate V2 and V4 into distinct directories"
git push
```

---

## Performance Report Usage After Reorganization

### For V2:
```bash
cd v2
python3 generate_performance_report.py
```

### For V4:
```bash
cd v4
python3 generate_performance_report.py
```

---

## Version Comparison Table

| Feature | V2.2 | V4 |
|---------|------|-----|
| **Data Store** | SQLite (trades.db) | JSON (sim_performance.json) |
| **Main Entry** | `main.py` | `v4_main.py` |
| **Regime Detection** | None | Multi-signal with hysteresis |
| **Symbol States** | None | 6-state machine |
| **Scanner Scoring** | Hand-weighted | ML-based + regime-adaptive |
| **Position Sizing** | Fixed % | Regime-adaptive dynamic |
| **Exit Strategy** | Basic SL/TP | Multi-level TP + trailing + NFT |
| **Execution Model** | Optimistic | Realistic cost modeling |
| **Monitoring** | Basic alerts | Confidence tracking + circuit breakers |
| **Best For** | Simple momentum trading | Advanced regime-aware trading |

---

## Deployment Strategy

### Option A: Run Both Versions (Different Capitals)

```bash
# Server 1: V2.2 with $500 capital
cd /opt/alpha-sniper/v2
MODE=SIM python3 main.py

# Server 2: V4 with $500 capital
cd /opt/alpha-sniper/v4
python3 v4_main.py --mode SIM
```

### Option B: Migrate from V2 to V4

1. Run V2 for 1-2 more weeks, collect data
2. Run V4 in parallel (SIM mode)
3. Compare performance reports
4. Gradually move capital to better performer
5. Retire underperformer

---

## Recommendation Summary

### ✅ DO THIS:

1. **Keep single repo** (easier to manage)
2. **Reorganize into v2/ and v4/ directories**
3. **Update import paths** (one-time effort)
4. **Separate data/ subdirectories**
5. **Keep both performance report scripts**

### ❌ DON'T DO THIS:

1. Don't create separate repos unless absolutely necessary
2. Don't mix V2 and V4 code in same directory structure
3. Don't delete V2 code until V4 proves superior
4. Don't run both versions with same data files (will conflict)

---

## Next Steps

1. **Review this document**
2. **Decide: reorganize or split repos**
3. **If reorganizing: follow migration plan above**
4. **Update deployment scripts**
5. **Test both versions after migration**
6. **Document any issues**

---

## Questions?

If you need help with:
- Import path updates
- Deployment configuration
- Data migration
- Performance comparison

Just ask!
