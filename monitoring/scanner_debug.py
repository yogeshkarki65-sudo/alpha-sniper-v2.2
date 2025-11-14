#!/usr/bin/env python3
import sys
sys.path.insert(0, '/app')

from scanner.scanner import get_usdt_pairs, compute_features
from scanner.scorer import calculate_score
from config.config import config

print("Fetching market data...")
pairs = get_usdt_pairs()

if not pairs:
    print("❌ No pairs found!")
    sys.exit(1)

scores = []
print(f"Analyzing top {min(20, len(pairs))} coins...")

for t in pairs[:20]:
    try:
        f = compute_features(t)
        if f:
            score = calculate_score(
                f["rvol"],
                f["velocity"],
                f["trend"],
                f["orderbook_imbalance"]
            )
            scores.append({
                'symbol': f["symbol"],
                'score': score,
                'velocity': f["velocity"],
                'rvol': f["rvol"],
                'trend': f["trend"],
                'ob_imb': f["orderbook_imbalance"]
            })
    except Exception as e:
        print(f"Error analyzing {t.get('symbol', 'unknown')}: {e}")
        continue

if not scores:
    print("❌ Could not analyze any coins!")
    sys.exit(1)

scores.sort(key=lambda x: x['score'], reverse=True)

print("\n" + "="*80)
print(f"{'SYMBOL':<12} {'SCORE':<8} {'VEL%':<8} {'RVOL':<8} {'TREND':<8} {'OB_IMB':<8}")
print("="*80)

for s in scores[:10]:
    symbol = s['symbol'][:12]
    score = s['score']
    vel = s['velocity']
    rvol = s['rvol']
    trend = s['trend']
    ob = s['ob_imb']

    # Highlight if score is good
    marker = "🟢" if score >= config.MIN_SIGNAL_SCORE else "  "

    print(f"{marker} {symbol:<10} {score:>6.1f}  {vel:>6.2f}%  {rvol:>6.2f}  {trend:>6.2f}  {ob:>6.2f}")

print("="*80)
print(f"\nSignal threshold: {config.MIN_SIGNAL_SCORE}")
print(f"Coins above threshold: {sum(1 for s in scores if s['score'] >= config.MIN_SIGNAL_SCORE)}")
print("\n🟢 = Signal would trigger")
