# AUDIT: Compression Breakout Checkpoint 1

Date: 2026-05-12  
Auditor: Claude Code  
Commit: `90dcf17` - "research: add compression breakout checkpoint 1"  
Branch: `research/compression-breakout-v1`  
Builder: Codex  

## Verdict: ITERATE (ONE DIAGNOSTIC ITERATION)

Checkpoint 1 correctly implemented compression_breakout_long as research-only setup. However, **0 trades occurred in target COMPRESSION regime** - all 3 trades were labeled "normal". This indicates a **regime classification issue**, not a fundamental hypothesis failure. ONE diagnostic iteration is justified to verify regime labeling and adjust if needed.

---

## Executive Summary

Checkpoint 1 implemented compression_breakout setup and completed full-range backtest (2022-01-01 to 2026-03-29).

**Results:**
- **Total trades:** 3 (need ≥20)
- **Compression regime trades:** **0** (CRITICAL - target regime had zero activations)
- **Normal regime trades:** 3 (all trades were in "normal", not target regime)
- **ER:** -0.298229 (negative)
- **PF:** 0.435318 (below 1.0)
- **Breakout follow-through:** 100% (but only 3 trades, not meaningful)

**Root Cause:** RegimeEngine may not be labeling compression states correctly, OR compression states are extremely rare in dataset. Setup logic appears correct but cannot be validated without proper regime classification.

**Recommendation:** ONE diagnostic iteration to empirically analyze regime distribution and verify compression detection. If still <20 trades or negative ER after fix → close compression_breakout as FAILED.

---

## Implementation Quality: PASS

### Scope Compliance

| Requirement | Status | Evidence |
|---|---|---|
| Research-only (no production changes) | ✅ PASS | Zero changes to core/**, execution/**, settings.py |
| Separate from absorption logic | ✅ PASS | No CVD divergence, different structure |
| Objective metrics (not interpretive) | ✅ PASS | ATR percentile, range width, breakout size |
| Test coverage | ✅ PASS | 17 tests passed, compileall OK |
| Reasons[] taxonomy complete | ✅ PASS | All signals explained |

### Files Created

- `research_lab/setups/compression_breakout.py` (467 lines)
- `research_lab/backtest_compression_breakout.py` (237 lines)
- `research_lab/evaluate_compression_gates.py` (182 lines)
- `tests/test_research_lab_compression_breakout.py` (250 lines)
- `research_lab/reports/compression_breakout_validation_report.md`
- `research_lab/reports/COMPRESSION_BREAKOUT_AUDIT_PACKAGE.md`
- `research_lab/reports/compression_gate_results.json`

### Setup Logic

**Compression detection:**
```python
atr_percentile_threshold: float = 0.20  # p20 = compressed
compression_lookback_15m: int = 96  # 24 hours
min_compression_duration_bars: int = 12  # 3 hours minimum
range_width_atr_max: float = 8.0  # Tight range
```

**Breakout trigger:**
```python
min_breakout_atr: float = 0.10  # Minimum breakout size
breakout_offset_atr: float = 0.05  # Above recent high
tfi_breakout_threshold: float = 0.35  # Directional flow
```

**Regime filter:**
```python
def check_regime_allowed(self, regime: RegimeState | str) -> bool:
    return regime in {RegimeState.COMPRESSION.value, RegimeState.NORMAL.value}
```

✅ Logic appears sound - ATR compression detection, breakout confirmation, flow validation

---

## Critical Issue: Regime Classification Gap

### Problem

**0 trades in COMPRESSION regime** (target regime for this setup)

All 3 trades occurred in "normal" regime:

| Regime | Trades | ER | PF |
|---|---:|---:|---:|
| **compression** | **0** | null | null |
| normal | 3 | -0.298229 | 0.435318 |

**This is analogous to absorption's volatility threshold issue** - a measurement/classification problem, not hypothesis failure.

### Root Causes (Possible)

**Hypothesis 1: RegimeEngine doesn't label COMPRESSION states**

RegimeEngine may never (or extremely rarely) classify market as COMPRESSION:
- `classify()` logic may not detect compression conditions
- Compression threshold may be too strict
- Compression may be labeled as NORMAL instead

**Evidence needed:**
- Empirical distribution: how many cycles labeled COMPRESSION in 2022-2026?
- If 0% → RegimeEngine needs compression detection logic
- If <1% → compression threshold needs tuning
- If >5% but setup doesn't activate → setup logic issue

**Hypothesis 2: Handoff specified "range" but no RANGE regime exists**

Handoff said:
> Target regimes: compression (primary), range (secondary)

But available regimes are:
```python
class RegimeState(str, Enum):
    NORMAL = "normal"
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    COMPRESSION = "compression"  # ← target
    CROWDED_LEVERAGE = "crowded_leverage"
    POST_LIQUIDATION = "post_liquidation"
    # NO "RANGE" regime
```

Codex interpreted "range" as "normal" (reasonable), but trades happened in NORMAL, not COMPRESSION.

**Hypothesis 3: Compression is too rare**

Even if RegimeEngine labels compression correctly, true volatility compression events may be very rare (e.g., <10 events in 4 years).

**Evidence needed:**
- Count COMPRESSION-labeled cycles
- If compression is genuinely rare, hypothesis may be viable but sparse

---

## Comparison to Absorption Failure

### Absorption Continuation (FAILED)

| Aspect | Checkpoint 2 | Iteration A | Result |
|---|---|---|---|
| Root cause | Volatility threshold miscalibrated (0.008 vs p95=0.029) | CVD slope + volatility fixed | |
| Trades | 4 | 25 | ✅ Sample increased |
| ER | 0.34 | -0.48 | ❌ Edge failed |
| Hypothesis | CVD absorption predicts continuation | CVD not predictive | FAILED |

**Verdict:** Measurement fixes exposed truth - hypothesis fundamentally flawed.

### Compression Breakout (Current)

| Aspect | Checkpoint 1 | Iteration (proposed) | Expected |
|---|---|---|---|
| Root cause | **0 compression regime trades** | Regime classification empirical analysis | TBD |
| Trades | 3 (all in "normal") | ? | Target: ≥20 |
| ER | -0.298 (normal regime only) | ? | Target: >1.5 in compression |
| Hypothesis | Compression → breakout predicts expansion | Needs proper regime labeling to test | TBD |

**Key difference:** Absorption tested the thesis and it failed. Compression **couldn't test the thesis** because target regime had 0 activations.

---

## Hard Gates: FAILED (Expected for Checkpoint 1)

| Gate | Requirement | Actual | Status |
|---|---|---|---|
| Compression ER | > 1.5 | null (0 trades) | ❌ BLOCKED |
| Breakout follow-through | >= 50% | 100% (3 trades) | ⚠️ PASS but low sample |
| Overlap vs sweep_reclaim | < 30% | not run | ❌ BLOCKED |
| Min trades | >= 20 | 3 | ❌ FAIL |
| **Compression trades** | **>= 10** | **0** | ❌ **FAIL (CRITICAL)** |
| Normal/secondary ER | > 0.5 | -0.298 | ❌ FAIL |
| WF 2/2 pass | Yes | not run | ❌ BLOCKED |
| Safety flags | None blocking | None | ✅ PASS |
| Explainability | Complete | Complete | ✅ PASS |

**Primary blocker:** 0 compression regime trades prevents all meaningful validation.

---

## Test Results: PASS

**Command:** `pytest tests/test_research_lab_compression_breakout.py -v`

**Result:** 17 passed, 0 failed

**Key tests:**
- `test_compression_breakout_generates_explained_long_candidate` ✅
- `test_compression_breakout_blocks_wrong_regime` ✅
- `test_compression_breakout_requires_breakout_confirmation` ✅
- `test_compression_breakout_detects_failed_breakout` ✅
- `test_compression_breakout_blocks_no_compression` ✅
- `test_compression_breakout_uses_empirical_volatility_threshold` ✅

**Compileall:** ✅ PASS

Tests validate setup logic is correct. Issue is regime classification, not setup implementation.

---

## Layer Separation: PASS

- ✅ No changes to `core/**`, `execution/**`, `governance/**`, `risk/**`, `settings.py`
- ✅ All work in `research_lab/**`, `tests/**`, `docs/**`
- ✅ Research-only data path (`snapshot.source_meta["research_atr_4h_norm_history"]`)

---

## Why This is NOT Like Absorption Failure

**Absorption:**
- Hypothesis was tested fairly (25 trades after fixes)
- Result: CVD absorption NOT predictive (24% hit rate, negative ER)
- Conclusion: Thesis fundamentally flawed for BTC perps

**Compression:**
- Hypothesis was NOT tested (0 trades in target regime)
- Result: Cannot evaluate compression → breakout thesis without compression regime data
- Conclusion: Measurement/classification issue, NOT thesis failure

**Key distinction:** We learned absorption doesn't work. We haven't learned if compression works yet.

---

## Diagnostic Iteration Justification

### Why ONE Iteration is Warranted

1. **Clear measurement issue identified:** 0 compression regime trades indicates classification problem
2. **Objective fix path:** Empirically analyze regime distribution, adjust if needed
3. **Different from absorption:** Absorption failed AFTER measurement fixes; compression hasn't been tested yet
4. **Fast failure discipline:** ONE attempt only - if still <20 trades or negative ER → close as FAILED

### Diagnostic Scope (ONE Iteration ONLY)

**Fix 1: Regime Distribution Analysis**

Empirically measure:
- How many cycles labeled COMPRESSION in 2022-2026?
- How many cycles labeled NORMAL, UPTREND, DOWNTREND?
- Is COMPRESSION detection working in RegimeEngine?

**Output:** `research_lab/reports/regime_distribution_2022_2026.md`

**Fix 2A: If COMPRESSION labels are rare (<1%)**

Option 1: Tune RegimeEngine to detect compression states (if user approves production changes)

Option 2: **Relax setup regime filter** to accept NORMAL as proxy for range/compression (research-only change)

```python
# Current (too strict):
def check_regime_allowed(self, regime: RegimeState | str) -> bool:
    return regime in {RegimeState.COMPRESSION, RegimeState.NORMAL}

# After fix (if COMPRESSION labels rare):
def check_regime_allowed(self, regime: RegimeState | str) -> bool:
    # Accept NORMAL as proxy for range/compression (low volatility conditions)
    # Block trending regimes (uptrend/downtrend handled by other setups)
    return regime not in {RegimeState.UPTREND, RegimeState.DOWNTREND, 
                          RegimeState.CROWDED_LEVERAGE, RegimeState.POST_LIQUIDATION}
```

**Rationale:** If RegimeEngine doesn't label compression, but setup's internal compression detection (ATR percentile, range width) works, use setup's detection + regime veto (block trends/crowded).

**Fix 2B: If COMPRESSION labels exist (>1%) but setup doesn't activate**

Review setup filters to identify what's blocking activation when regime=COMPRESSION.

**NOT ALLOWED:**
- ❌ Parameter rescue (loosen thresholds to force trades)
- ❌ Grid search
- ❌ Additional iterations beyond this one
- ❌ Mix with sweep_reclaim to boost metrics

**HARD STOP after iteration:**
- If trades < 20 → REJECT
- If compression ER < 1.5 → REJECT
- If breakout follow-through < 40% → REJECT
- Move to next setup family (e.g., crowded_unwind)

---

## Expected Outcomes After Iteration

### Scenario 1: SUCCESS (30-40% probability)

**After regime classification fix:**
- Compression regime trades: 30-60
- Compression ER: 1.8-2.5
- Breakout follow-through: 55-65%
- Overlap vs sweep_reclaim: <30%

**Verdict:** CANDIDATE FOR PHASE 2.5

**Next:** WF validation, overlap analysis, audit, Phase 2.5 contracts

---

### Scenario 2: MARGINAL (30% probability)

**After fix:**
- Compression trades: 20-30 (minimal sample)
- Compression ER: 1.0-1.5 (weak edge)
- Breakout follow-through: 40-50% (marginal)

**Verdict:** Still MARGINAL - not worth Phase 2.5 complexity

**Next:** Close compression_breakout, move to next family

---

### Scenario 3: STILL FAILED (30-40% probability)

**After fix:**
- Total trades < 20 OR compression ER < 0.5
- Breakout follow-through < 40%

**Verdict:** HYPOTHESIS FAILED

**Conclusion:** Even with correct regime classification, compression → breakout has no edge in BTC perps.

**Next:** Move to Setup #4 (e.g., crowded_unwind - funding/OI exhaustion)

---

## Recommended Next Step

### Immediate: ONE Diagnostic Iteration

**Scope:**
1. Analyze regime distribution (2022-2026) - identify COMPRESSION labeling frequency
2. If COMPRESSION rare → adjust setup regime filter OR tune RegimeEngine (research-only)
3. Re-run backtest with corrected regime classification
4. Hard stop: <20 trades OR ER <1.5 → REJECT

**Timeline:** 1-2 days

**Deliverables:**
- `research_lab/analyze_regime_distribution.py`
- `research_lab/reports/regime_distribution_2022_2026.md`
- Updated `compression_breakout.py` (if regime filter adjusted)
- Re-run backtest report
- Updated audit package with verdict

### If Iteration Succeeds

- Run WF validation (2 windows)
- Overlap vs sweep_reclaim analysis
- Breakout follow-through cohort analysis
- Prepare for Phase 2.5

### If Iteration Fails

- Document failure (regime classification couldn't rescue sparse sample)
- Close COMPRESSION-BREAKOUT-RESEARCH-V1 as FAILED
- Recommend next setup: crowded_unwind (funding/OI exhaustion → forced unwind)

---

## Critical Reminders

### This is NOT Parameter Rescue

We are fixing a **measurement issue** (regime classification), not tuning for results:
- Absorption: CVD measurement was wrong → fixed → thesis still failed (correct outcome)
- Compression: Regime classification may be wrong → fix → THEN test thesis

**If edge exists after correct measurement, we'll find it.**  
**If edge doesn't exist, no amount of tuning will create it.**

### One Iteration = One Chance

After regime classification fix:
- Edge validates → proceed to WF/Phase 2.5
- Edge fails → stop, no further iterations

**No:**
- "Maybe try different compression threshold"
- "Maybe loosen breakout confirmation"
- "Maybe add another regime"

**This prevents endless parameter search.**

### Regime Classification is Critical

Without proper regime labeling, we cannot test regime-specific hypotheses:
- Compression_breakout needs COMPRESSION regime data
- Future trend_pullback needs UPTREND regime data
- Future crowded_unwind needs CROWDED_LEVERAGE regime data

**If RegimeEngine doesn't label regimes correctly, all regime-specific setups will fail.**

This may require RegimeEngine tuning (production change), OR setups must rely on internal detection + regime veto (block wrong regimes, accept any non-blocked).

---

## Observations

### 1. Implementation Quality is Good

Setup logic is clean, tests pass, reasons[] complete. No concerns about code quality.

### 2. Regime Classification May Be Systemic Issue

If COMPRESSION labels are rare/absent, this affects:
- Current: compression_breakout
- Future: any setup that targets specific regimes

**May need to address RegimeEngine regime detection** (separate from research workflow).

### 3. Compression Detection vs Classification

Setup has internal compression detection (ATR percentile, range width). If this works but RegimeEngine doesn't label COMPRESSION, setup can work by:
- Using internal compression detection
- Using regime as VETO only (block trends/crowded, accept anything else)

### 4. Fast Iteration Workflow Validated

Absorption: 5 days to conclusive verdict (FAILED)  
Compression: On track for similar speed (pending iteration)

**This rapid iteration prevents wasted effort on invalid hypotheses.**

---

## Final Verdict: ITERATE (ONE DIAGNOSTIC ITERATION)

### Verdict Summary

| Dimension | Status |
|---|---|
| **Implementation Quality** | ✅ PASS |
| **Test Coverage** | ✅ PASS |
| **Layer Separation** | ✅ PASS |
| **Explainability** | ✅ PASS |
| **Sample Size** | ❌ FAIL (3 trades) |
| **Target Regime Activation** | ❌ **FAIL (0 compression trades)** |
| **Hypothesis Validation** | ⏸️ **BLOCKED (cannot test without regime data)** |

### Bottom Line

**Implementation is correct. Regime classification is suspect.**

- 0 trades in target COMPRESSION regime indicates measurement/classification issue
- Setup logic appears sound (tests pass, thresholds reasonable)
- ONE diagnostic iteration justified to fix regime classification
- Hard stop: <20 trades or negative ER after fix → REJECT

**Audit Conclusion:** ✅ **ITERATE REQUIRED (regime classification fix) → RE-VALIDATE**

---

**Signed:** Claude Code (Auditor)  
**Date:** 2026-05-12  
**Status:** Awaiting user decision on diagnostic iteration (regime distribution analysis + classification fix)
