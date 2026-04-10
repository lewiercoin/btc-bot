# DIRECTION_AUDIT_V1 — Direction-Dependent Logic Audit

Milestone: SIGNAL-INVERSION-V1 (D3)
Builder: Cascade
Date: 2026-04-10

---

## Context

SIGNAL-ANALYSIS-V1 showed the sweep+reclaim signal is counter-predictive:
- LONG on LOW sweep: 25–29% win rate, negative mean forward return in all 6 regime segments
- Inverted (SHORT on LOW sweep): positive expectancy in 6/6 segments (+0.057 to +0.153)

This audit identifies all direction-dependent logic in the execution stack and
determines what needs updating for the inversion.

---

## Audit Results

### 1. `_infer_direction()` — signal_engine.py:95-110

**CHANGED (D1)**

Original:
- LONG requires `sweep_side == "LOW"` (support swept → go long)
- SHORT requires `sweep_side == "HIGH"` (resistance swept → go short)

Inverted:
- LONG requires `sweep_side == "HIGH"` (resistance reclaim failed → price continues up)
- SHORT requires `sweep_side == "LOW"` (support reclaim failed → price continues down)

CVD/TFI direction inference is unchanged — these are microstructure indicators
independent of the sweep direction thesis.

### 2. `regime_direction_whitelist` — signal_engine.py:10-18, settings.py:17-25

**CHANGED (D3)**

Original (LONG-biased, calibrated for LOW sweep → LONG):
```
NORMAL:           ("LONG",)           ← blocked inverted SHORT
COMPRESSION:      ("LONG",)           ← blocked inverted SHORT
DOWNTREND:        ("LONG", "SHORT")   ← OK
UPTREND:          ()                  ← blocked everything
CROWDED_LEVERAGE: ("SHORT",)          ← OK for inverted
POST_LIQUIDATION: ("LONG",)           ← blocked inverted SHORT
```

Updated (symmetric, allows inverted signals):
```
NORMAL:           ("LONG", "SHORT")   ← allows inverted SHORT on LOW sweep
COMPRESSION:      ("LONG", "SHORT")   ← allows inverted SHORT on LOW sweep
DOWNTREND:        ("LONG", "SHORT")   ← unchanged
UPTREND:          ()                  ← unchanged (no signals in uptrend)
CROWDED_LEVERAGE: ("SHORT",)          ← unchanged (already correct for inverted)
POST_LIQUIDATION: ("LONG", "SHORT")   ← allows inverted SHORT
```

Rationale: The whitelist should not encode sweep direction assumptions. Direction
filtering should come from CVD/TFI inference + confluence scoring, not from
blanket regime blocks. The `_is_regime_special_supportive` bonus already provides
directional preference per regime.

### 3. `_confluence_score()` — signal_engine.py:112-150

**NO CHANGE NEEDED**

All direction-dependent scoring is based on microstructure (CVD divergence, TFI
impulse, EMA trend alignment, funding), not on sweep direction. These indicators
correctly inform whether LONG or SHORT has microstructure support:

- CVD bullish divergence → LONG bonus (correct: bullish flow supports long)
- TFI impulse positive → LONG bonus (correct: buying pressure supports long)
- EMA50 > EMA200 → LONG bonus (correct: uptrend supports long)
- Funding negative → LONG bonus (correct: shorts paying longs = bullish)

These are independent of whether the sweep was HIGH or LOW.

### 4. `_is_regime_special_supportive()` — signal_engine.py:152-159

**NO CHANGE NEEDED**

- SHORT bonus in DOWNTREND/CROWDED_LEVERAGE: correct regardless of sweep direction
- LONG bonus in POST_LIQUIDATION: correct regardless of sweep direction

### 5. `_build_levels()` — signal_engine.py:161-185

**NO CHANGE NEEDED**

Entry/SL/TP placement is direction-based, not sweep-side-based:
- LONG: entry above level, SL below, TP above
- SHORT: entry below level, SL above, TP below

With inversion (SHORT on LOW sweep level): entry below support → SL above support →
TP below. This is correct for the "failed reclaim" thesis.

### 6. `GovernanceLayer` — governance.py

**NO CHANGE NEEDED**

All checks are direction-agnostic: drawdown limits, consecutive losses, cooldown,
duplicate level detection, session windows.

### 7. `RiskEngine` — risk_engine.py

**NO CHANGE NEEDED**

Size calculation, leverage selection, and exit evaluation are all direction-aware
but direction-agnostic in implementation. They use `position.direction` to determine
SL/TP comparison direction, which works correctly for both LONG and SHORT.

### 8. `allow_long_in_uptrend` — settings.py:90

**FLAG FOR FUTURE**

This flag adds LONG to the UPTREND whitelist. With inversion, a corresponding
`allow_short_in_downtrend` or more general mechanism might be needed. However,
DOWNTREND already allows both directions, so this is not blocking. Tracked as
future consideration, not required for SIGNAL-INVERSION-V1.

### 9. `direction_tfi_threshold` / `direction_tfi_threshold_inverse` — settings.py:87-88

**NO CHANGE NEEDED**

These thresholds control TFI-based direction inference:
- TFI > 0.05 → LONG (buying pressure)
- TFI < -0.05 → SHORT (selling pressure)

These are microstructure thresholds, not sweep-direction-dependent. They correctly
infer market direction from orderflow regardless of sweep side.

---

## Summary

| Component | Status | Change |
|---|---|---|
| `_infer_direction` sweep validation | **CHANGED** | D1: swap LOW↔HIGH |
| `regime_direction_whitelist` | **CHANGED** | D3: LONG-only → symmetric |
| `_confluence_score` | No change | Microstructure-based |
| `_is_regime_special_supportive` | No change | Regime-based |
| `_build_levels` | No change | Direction-agnostic |
| `GovernanceLayer` | No change | Direction-agnostic |
| `RiskEngine` | No change | Direction-agnostic |
| `allow_long_in_uptrend` | Flag for future | Not blocking |
| TFI thresholds | No change | Microstructure-based |

**Total changes: 2 files, 2 functions. Rest of stack is direction-agnostic.**

---

## D2 Backtest Results — Inverted Direction, Default Params

```
Period:          2022-01-01 -> 2026-03-01
Total trades:    563  (507 SHORT, 56 LONG)
Win rate:        10.5%
Expectancy R:    -0.9399
Profit factor:   0.2783
Total PnL:       -9,951.60

Per regime:
  compression        7  ExpR=-1.11  WR=14.3%  PF=0.196
  crowded_leverage  91  ExpR=-0.82  WR=13.2%  PF=0.405
  downtrend        447  ExpR=-0.94  WR=10.3%  PF=0.276
  normal            18  ExpR=-1.40  WR= 0.0%  PF=0.000
```

**Result: NEGATIVE. Inverse edge does NOT survive the full execution stack.**

### Discrepancy Analysis: Event Study vs Backtest

| Metric | Event Study (D2 from SIGNAL-ANALYSIS-V1) | Full Backtest |
|---|---|---|
| Events/trades | 11,841 | 563 (95% filtered out) |
| Original WIN rate | 25–29% | N/A |
| Implied inverse WIN rate | 62–66% | 10.5% |
| Exit model | Fixed: SL=1.0×ATR, TP=2.0×ATR, max_hold=16 bars | Full stack: SL≈0.75×ATR, TP=2.5×ATR, max_hold=24h |

### Root cause: `_infer_direction` is the bottleneck

The event study counted ALL sweep+reclaim events. The full backtest filters through:

1. **`_infer_direction` (CVD/TFI gate)** — requires CVD divergence or TFI impulse to
   AGREE with the trade direction. For inverted SHORT on LOW sweep, this means
   CVD bearish divergence or TFI < -0.05 must be present. Most LOW sweep events
   have neutral or bullish CVD (since the market swept support — sellers are active),
   so most events are rejected at this gate.

2. **Confluence scoring** — requires confluence_min=0.75. With fewer matching
   microstructure indicators (because CVD/TFI was designed for the original
   direction thesis), fewer signals reach the threshold.

3. **Exit model differences** — tighter SL (0.75×ATR vs 1.0×ATR) and farther TP
   (2.5×ATR vs 2.0×ATR) makes individual trades harder to win.

### The fundamental incompatibility

The original `_infer_direction` logic assumes:
- CVD bullish + LOW sweep → "smart money buying at support" → LONG
- CVD bearish + HIGH sweep → "smart money selling at resistance" → SHORT

The inverted thesis is:
- LOW sweep + reclaim → "support failed, reclaim is fake" → SHORT
- HIGH sweep + reclaim → "resistance failed, reclaim is fake" → LONG

These are contradictory. The CVD/TFI filters select events where microstructure
AGREES with the inverted direction, but the inverse edge exists across ALL events
regardless of microstructure alignment. The filter selects a biased subset (events
with aligned microstructure) that does not carry the same edge.

### Architectural implication

To capture the inverse edge, direction should be derived FROM sweep_side
(LOW→SHORT, HIGH→LONG) rather than from CVD/TFI. CVD/TFI should become
confluence factors, not direction determinants. This is a larger architectural
change than the 2-line flip — it means rearchitecting `_infer_direction` to
use sweep_side as the primary direction source.

This is beyond SIGNAL-INVERSION-V1 scope. Tracked as architectural finding
for Claude Code's strategic decision.

---

## SIGNAL-ENGINE-REARCH-V1: Rearchitected _infer_direction Results

### Change

```python
# Before (CVD/TFI as direction source):
def _infer_direction(self, features):
    if features.cvd_bullish_divergence and not features.cvd_bearish_divergence:
        inferred_direction = "LONG"
    elif features.cvd_bearish_divergence and not features.cvd_bullish_divergence:
        inferred_direction = "SHORT"
    elif features.tfi_60s > threshold: inferred_direction = "LONG"
    elif features.tfi_60s < -threshold: inferred_direction = "SHORT"
    # + sweep_side validation → filtered 95% of events

# After (sweep_side as direction source):
def _infer_direction(self, features):
    if features.sweep_side == "LOW": return "SHORT"
    if features.sweep_side == "HIGH": return "LONG"
    return None
```

### D2 Backtest — Rearchitected Direction, Default Params

```
Period:          2022-01-01 -> 2026-03-01
Total trades:    750  (715 SHORT, 35 LONG)
Win rate:        12.0%
Expectancy R:    -0.8740
Profit factor:   0.2546
Total PnL:       -9,986.70

Per regime:
  compression        7  ExpR=-1.09  WR=14.3%  PF=0.185
  crowded_leverage 100  ExpR=-0.99  WR= 9.0%  PF=0.276
  downtrend        629  ExpR=-0.84  WR=12.7%  PF=0.263
  normal            14  ExpR=-1.40  WR= 0.0%  PF=0.000

Per direction:
  LONG              35  ExpR=-1.08  WR= 8.6%
  SHORT            715  ExpR=-0.86  WR=12.2%

ACCEPTANCE CRITERIA:
  Trade count >= 3000:  FAIL (750)
  ExpR > 0:             FAIL (-0.8740)
```

### Analysis: Bottleneck Shifted, Not Removed

| Metric | SIGNAL-INVERSION-V1 (CVD/TFI gate) | REARCH-V1 (sweep_side) |
|---|---|---|
| Total trades | 563 | 750 (+33%) |
| Win rate | 10.5% | 12.0% |
| ExpR | -0.9399 | -0.8740 |
| Events reaching confluence | ~563 | ~all 11,841 |
| Events passing confluence | 563 | 750 |

Trade count increased only 33% (563 → 750), not the expected 10-20x.
The bottleneck moved from `_infer_direction` to two downstream gates:

**Gate 1: Confluence scoring (confluence_min=0.75)**

The confluence weights were calibrated for the original direction thesis where
CVD/TFI alignment was a prerequisite. With sweep-side-derived direction:

- CVD bearish divergence on LOW sweep (SHORT): structurally rare — most LOW sweeps
  have bullish or neutral CVD (sellers just swept support)
- CVD weight = 0.75 (the single largest weight). Without it, max reachable score is:
  force_order_spike(0.40) + regime_special(0.35) + ema_trend(0.25) + funding(0.20) = 1.20
- But commonly only ema_trend(0.25) + funding(0.20) = 0.45 < 0.75 threshold

So the confluence gate effectively re-implements the CVD/TFI filter, just at a
different layer. Most events without matching CVD/TFI still fail.

**Gate 2: SL/TP parameters**

The event study used SL=1.0×ATR, TP=2.0×ATR. The full stack uses:
- SL ≈ 0.75×ATR (invalidation_offset_atr) — 25% tighter
- TP = 2.5×ATR (tp1_atr_mult) — 25% farther
- min_rr = 2.8

Tighter SL + farther TP = lower win rate. Event study implied ~62-66% inverse WR.
Full stack delivers 12% WR — the SL/TP geometry is fundamentally different.

### Conclusion

The `_infer_direction` rearchitecture is architecturally correct — sweep_side
is now the sole direction source, CVD/TFI are confluence factors only. But the
acceptance criteria are not met because:

1. **Confluence weights** need recalibration for inverted direction (CVD weight
   dominance makes confluence gate equivalent to old CVD/TFI gate)
2. **SL/TP parameters** need adjustment to match the exit geometry that shows
   edge in the event study (wider SL, tighter TP)

Both are parameter calibration issues, not architecture issues. The rearch is the
correct foundation — parameters need tuning on top of it.

### Strategic Options for Claude Code

1. **Run Optuna campaign** on rearchitected engine — let optimizer find SL/TP and
   confluence weights that capture the inverse edge
2. **Manual parameter adjustment** — set SL=1.0×ATR, TP=2.0×ATR, lower
   confluence_min to 0.45, then backtest
3. **Restructure confluence weights** — reduce CVD weight, increase direction-
   independent weights (force_order_spike, regime_special, funding)
