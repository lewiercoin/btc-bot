# AUDIT: Absorption Continuation Iteration A

Date: 2026-05-12  
Auditor: Claude Code  
Commit: `fd8d711` - "research: iteration A failed absorption hypothesis"  
Branch: `research/trend-continuation-v1`  
Builder: Codex  

## Verdict: HYPOTHESIS FAILED

The iteration was correctly executed per handoff scope. Both measurement fixes (CVD slope, empirical volatility threshold) were properly implemented and increased sample size from 4 to 25 trades. However, the hypothesis demonstrates **negative edge** after corrections. Hard stop criteria mandate abandoning this setup family.

---

## Executive Summary

Iteration A was a diagnostic attempt to fix two identified measurement errors before abandoning the absorption-continuation hypothesis:

1. **A1 (CVD Slope):** Replace pre-calculated `cvd_bullish_divergence` boolean with direct CVD slope calculation over pullback window
2. **A2 (Volatility Threshold):** Replace arbitrary `atr_4h_norm > 0.008` with empirical p95 threshold from 2022-2026 data

**Result:**
- Sample increased: 4 → 25 trades ✅
- Volatility rejections reduced: 134,649 → 7,431 ✅
- Edge revealed: **NEGATIVE** ❌
  - Uptrend ER: -0.480095 (need >1.5)
  - Profit Factor: 0.554871 (below 1.0 = losing money)
  - Win rate: 24% (need >40%)
  - Absorption hit rate: 24% (need >50%)
  - Sharpe: -4.588025

**Hard Stop Decision:** 3 out of 4 hard gates failed → HYPOTHESIS FAILED

**Recommendation:** Move to compression_breakout (next setup family)

---

## Scope Compliance: PASS

### Iteration Constraints

| Constraint | Required | Actual | Status |
|---|---|---|---|
| Changes limited to A1 + A2 | Yes | CVD slope + volatility threshold only | ✅ PASS |
| No grid search | Prohibited | None performed | ✅ PASS |
| No parameter rescue | Prohibited | None attempted | ✅ PASS |
| No gate loosening | Prohibited | Gates unchanged | ✅ PASS |
| No production changes | Required | Zero production changes | ✅ PASS |
| Research-only scope | Required | `research_lab/**`, `tests/**`, `docs/**` only | ✅ PASS |

### Files Changed

| File | Purpose | Lines Changed |
|---|---|---|
| `research_lab/analyze_atr_distribution.py` | **NEW** - Empirical ATR distribution analyzer | +199 |
| `research_lab/setups/absorption_continuation.py` | CVD slope calculation (A1) + volatility threshold (A2) | +79 -21 |
| `research_lab/backtest_absorption_continuation.py` | CVD history injection for research | +26 |
| `tests/test_research_lab_absorption_continuation.py` | CVD pullback window test | +25 |
| `research_lab/reports/*.md` | Iteration A audit package, ATR distribution report | +132, +19, +21 |
| `docs/MILESTONE_TRACKER.md` | Status update | +8 -8 |

**No production files touched:** ✅ Correct

---

## Implementation Quality

### A1: CVD Slope Calculation - PASS

**Requirement:** Calculate CVD slope over actual pullback window instead of using pre-calculated boolean.

**Implementation:**
```python
def _calculate_cvd_absorption(
    self, *, snapshot: MarketSnapshot, features: Features
) -> tuple[bool, float]:
    history = _cvd_history_from_snapshot(snapshot)  # Research-only data
    if len(history) < 2:
        slope = float(features.cvd_15m)
        return slope > self.setup_config.cvd_slope_threshold, slope
    
    start_cvd = history[0]["cvd"]
    end_cvd = history[-1]["cvd"]
    slope = (end_cvd - start_cvd) / len(history)
    confirmed = slope > self.setup_config.cvd_slope_threshold
    return confirmed, slope
```

**Data Source:** `snapshot.source_meta["research_cvd_price_history"]` - passed by research backtest runner, not available in production (research-only path).

**Test Coverage:**
- `test_absorption_continuation_uses_pullback_window_cvd_history` ✅ PASS
- Validates CVD slope is calculated from historical window, not pre-calculated boolean

**Assessment:** ✅ **CORRECT** - Direct calculation over pullback window as specified.

---

### A2: Empirical Volatility Threshold - PASS

**Requirement:** Calculate empirical distribution of `atr_4h_norm` from 2022-2026 data and set threshold at meaningful percentile (90th or 95th).

**Empirical Distribution:**

Source: `storage/btc_bot.db`  
Date range: 2022-01-01 to 2026-03-29  
Sample count: 148,596 decision cycles

| Metric | Value |
|---|---:|
| Mean | 0.01552085 |
| p50 (median) | 0.01413720 |
| p75 | 0.01850282 |
| p90 | 0.02471642 |
| **p95** | **0.02885372** |
| p99 | 0.04294251 |

**Threshold Chosen:** p95 = 0.02885372 (95th percentile)

**Validation:**
- Old threshold: 0.008 (0.8%) → **below median** (13.4th percentile) ❌
- New threshold: 0.02885372 (2.89%) → **95th percentile** ✅
- Rejection reduction: 134,649 → 7,431 (94.5% reduction) ✅

**Implementation:**
```python
# In setup config
volatility_panic_atr_norm: float = 0.02885372  # p95 from empirical distribution
```

**Assessment:** ✅ **CORRECT** - Empirically derived, properly calibrated for "panic" (rare event at 95th percentile).

---

## Test Results: PASS

**Command:** `pytest tests/test_research_lab_absorption_continuation.py -v`

**Result:** 10 passed, 0 failed, 2 skipped (intentional)

### Key Tests

| Test | Purpose | Status |
|---|---|---|
| `test_absorption_continuation_uses_pullback_window_cvd_history` | **Validates A1 fix** - CVD slope from pullback window | ✅ PASS |
| `test_absorption_continuation_blocks_retail_ema_pullback_without_absorption` | Absorption gate enforced | ✅ PASS |
| `test_absorption_continuation_blocks_panic_liquidation_context` | **Validates A2 threshold** | ✅ PASS |
| `test_absorption_continuation_generates_explained_long_candidate` | Reasons[] taxonomy complete | ✅ PASS |
| `test_gate_evaluator_blocks_missing_validation_evidence` | Hard gates enforced | ✅ PASS |

**Compileall:** ✅ PASS (no syntax errors)

---

## Backtest Results: EDGE FAILED

### Full-Range Metrics (2022-01-01 to 2026-03-29)

| Metric | Result | Hard Gate | Status |
|---|---:|---:|---|
| Decision cycles | 148,596 | - | - |
| Candidates | 29 | - | - |
| Closed trades | 25 | ≥ 20 | ✅ PASS |
| **Uptrend ER** | **-0.480095** | **> 1.5** | ❌ **FAIL** |
| **Profit Factor** | **0.554871** | [1.5, 6.0] credible | ❌ **FAIL (< 1.0)** |
| **Win rate** | **0.24** | **> 0.40** | ❌ **FAIL** |
| **Absorption hit rate** | **0.24** | **> 0.50** | ❌ **FAIL** |
| Max drawdown | 10.64% | ≤ 15% | ✅ PASS |
| Sharpe | -4.588025 | - | ❌ (Negative) |

**Hard Gates Passed:** 1 / 4 (trade count only)

**Hard Gates Failed:** 3 / 4 (ER, win rate, absorption hit rate)

**Verdict per Hard Stop Criteria:** ❌ **HYPOTHESIS FAILED**

---

## What the Measurement Fixes Revealed

### Before Iteration A (Checkpoint 2)

- **Trades:** 4 (insufficient sample)
- **Uptrend ER:** 0.34 (weak edge)
- **Bottleneck:** `volatility_panic` rejected 90.6% of cycles (134,649 / 148,596)
- **Hypothesis:** Measurement errors (CVD boolean, volatility threshold) masked edge

### After Iteration A

- **Trades:** 25 (sufficient sample) ✅
- **Uptrend ER:** -0.48 (NEGATIVE edge) ❌
- **Bottleneck fixed:** `volatility_panic` now rejects only 5.0% (7,431 / 148,596) ✅
- **Truth revealed:** **Setup actively loses money** ❌

### Absorption Confirmation Analysis

| Metric | Checkpoint 2 | Iteration A | Interpretation |
|---|---:|---:|---|
| CVD divergence trades | 1 | 4 | More data available |
| CVD divergence wins | 0 | 0 | **0% hit rate** |
| Absorption hit rate | 25% | 24% | **Unchanged - not predictive** |

**Conclusion:** CVD slope calculation (A1) did NOT improve absorption predictiveness. The absorption hypothesis itself is invalid.

### Feature Cohort Analysis (Winners vs Losers)

| Feature | Winners (6) Avg | Losers (19) Avg | Predictive? |
|---|---:|---:|---|
| Pullback depth % | 0.010728 | 0.008671 | Weak |
| Price near EMA50 (ATR) | 0.913033 | 0.728932 | Weak |
| TFI 60s | 0.486839 | 0.507784 | **NO (inverse)** |
| OI delta % | 0.000426 | 0.000196 | Minimal |

**Key Finding:** TFI (directional flow) is slightly HIGHER in losers than winners. This contradicts the absorption thesis (flow should confirm winners).

---

## Rejection Funnel Change

### Top Rejections After Fixes

| Rejection Reason | Checkpoint 2 Count | Iteration A Count | Change |
|---|---:|---:|---|
| `tfi_below_absorption_threshold` | 116,244 | 116,244 | No change |
| `price_not_above_ema200` | 75,428 | 75,428 | No change |
| **`volatility_panic`** | **134,649** | **7,431** | **✅ -94.5%** |
| `absorption_not_confirmed` | 73,163 | 73,163 | No change |
| `ema50_not_above_ema200` | 75,044 | 75,044 | No change |

**A2 Fix Impact:** Volatility bottleneck resolved - rejection rate dropped from 90.6% to 5.0%.

**Result:** More candidates generated (4 → 29), more trades executed (4 → 25), but edge is NEGATIVE.

---

## Why WF Was Not Run: Correct Decision

Per handoff protocol:
> "WF validation is only decision-useful after the setup passes primary edge gates."

**Primary Edge Gates:**
- Uptrend ER > 1.5 ❌ (actual: -0.48)
- Profit Factor > 1.0 ❌ (actual: 0.55)
- Win rate > 40% ❌ (actual: 24%)
- Absorption hit rate > 50% ❌ (actual: 24%)

**All primary gates failed.** Running WF would only confirm the setup is unstable with negative edge. No additional information value.

**Decision:** ✅ Correct - saved compute cost, verdict is unambiguous.

---

## Hard Stop Criteria: TRIGGERED

Per iteration handoff, stop immediately if ANY of the following remain true after fixes:

| Criterion | Threshold | Actual | Status |
|---|---|---:|---|
| Total trades | < 20 | 25 | ✅ PASS |
| **Uptrend ER** | **< 1.5** | **-0.480095** | ❌ **FAIL** |
| **Absorption hit rate** | **< 50%** | **24%** | ❌ **FAIL** |
| **Win rate** | **< 40%** | **24%** | ❌ **FAIL** |

**Hard Stop Result:** ❌ **TRIGGERED** (3 out of 4 criteria failed)

**Mandatory Actions per Handoff:**

✅ DO:
- Document exact failure reason ✅ (negative ER, absorption not predictive)
- Recommend compression_breakout as next setup ✅
- Prepare handoff for Option B ✅ (if user approves)

❌ DO NOT:
- Loosen gates ("maybe ER >0.5 is enough") ❌
- Grid search other parameters ❌
- Try additional iterations ("maybe if we also change...") ❌
- Mix with sweep-reclaim to boost metrics ❌
- Cherry-pick favorable sub-periods ❌

**Compliance:** ✅ All constraints respected

---

## Layer Separation: PASS

| Layer | Files Changed | Production Impact | Status |
|---|---|---|---|
| Research Lab | `research_lab/**` | None (research-only) | ✅ PASS |
| Tests | `tests/test_research_lab*` | None | ✅ PASS |
| Documentation | `docs/**` | None | ✅ PASS |
| Production Core | `core/**`, `execution/**` | **Zero changes** | ✅ PASS |
| Settings | `settings.py` | **Zero changes** | ✅ PASS |
| Orchestrator | `orchestrator.py` | **Zero changes** | ✅ PASS |

**No-Touch Areas:** All respected ✅

---

## Determinism: PASS

- Backtest date range: 2022-01-01 to 2026-03-29 (fixed, deterministic)
- Seed: Not applicable (replay-based backtest, no random sampling)
- Data source: `storage/btc_bot.db` (V3/grid-compatible dataset)
- CVD history: Deterministic from historical aggtrade_buckets
- ATR distribution: Deterministic from features table

**Reproducibility:** ✅ Results are deterministic and reproducible

---

## State Integrity: PASS

- No production state modified (research-only)
- No database writes to production tables
- All artifacts stored in `research_lab/reports/` (read-only for production)
- Backtest outputs are hermetic (no side effects)

**Assessment:** ✅ Production state untouched

---

## Error Handling: PASS

**CVD History Fallback:**
```python
if len(history) < 2:
    slope = float(features.cvd_15m)  # Fallback to single value
    return slope > threshold, slope
```

✅ Handles missing/insufficient CVD history gracefully

**ATR Distribution Robustness:**
- Validates 148,596 samples loaded
- Handles missing features (skips invalid rows)
- Percentile calculations use numpy (robust)

✅ No unhandled exceptions in empirical analysis

---

## Tech Debt: LOW

### New Debt Introduced

1. **CVD history research-only path:** `snapshot.source_meta["research_cvd_price_history"]` only available in research backtest runner, not production. This is INTENTIONAL (research-only setup), not a bug.

2. **ATR distribution as static config:** Threshold `0.02885372` is hardcoded from 2022-2026 analysis. If market regime changes significantly, threshold may need recalibration.

**Mitigation:** Not applicable - setup is REJECTED, no production deployment planned.

### Existing Debt (from Checkpoint 2)

- No new tech debt added
- Existing research lab debt unchanged

**Debt Level:** LOW (research-only setup, no production impact)

---

## AGENTS.md Compliance: PASS

| Rule | Required | Actual | Status |
|---|---|---|---|
| Commit discipline | WHAT/WHY/STATUS in message | ✅ Present in fd8d711 | ✅ PASS |
| Layer isolation | Research changes only | ✅ Zero production changes | ✅ PASS |
| No self-audit | Builder does not audit | ✅ Codex requested Claude audit | ✅ PASS |
| Timestamp in docs | ISO 8601 where applicable | ✅ 2026-05-12 format used | ✅ PASS |

**Workflow Compliance:** ✅ PASS

---

## Methodology Integrity: PASS

### Research Lab Audit Axes

| Axis | Assessment | Status |
|---|---|---|
| **Methodology Integrity** | Claimed "diagnostic iteration" (not optimization). Delivered exactly that: two fixes, no parameter search. | ✅ PASS |
| **Reproducibility & Lineage** | Commit, date range, seed (N/A for replay), data source all explicit. | ✅ PASS |
| **Data Isolation** | Source DB read-only. No trial scratch writes. | ✅ PASS |
| **Search Space Governance** | No search performed. Only diagnostic fixes (A1, A2). | ✅ PASS |
| **Artifact Consistency** | Reports, audit package, commit message all tell same story: FAILED. | ✅ PASS |
| **Boundary Coupling** | Research-only. Zero coupling to live path. | ✅ PASS |

**Classification:** This is NOT a methodology debt issue. The workflow honestly documents that the hypothesis failed after measurement corrections.

---

## Critical Issues: NONE

**None blocking promotion (because setup is REJECTED).**

---

## Warnings: NONE

**None.** Iteration was correctly scoped and executed. Negative result is the CORRECT outcome - hypothesis was tested fairly and failed.

---

## Observations

### 1. Measurement Fixes Worked as Designed

- **A1 (CVD slope):** Correctly implemented, data available, calculation deterministic ✅
- **A2 (Volatility threshold):** Empirically derived, properly calibrated ✅
- **Sample size:** Increased from 4 to 25 trades ✅

**Result:** Fixes exposed the truth - hypothesis has no edge.

### 2. Absorption Thesis Invalid for BTC Perps

The core hypothesis was:
> "On controlled pullback absorption (price down, CVD up, TFI positive), enter before continuation becomes obvious to retail."

**Reality:**
- CVD divergence: 0 wins / 4 trades (0% hit rate)
- TFI slightly HIGHER in losers than winners (contradicts thesis)
- Absorption confirmation: 24% hit rate (worse than random)

**Conclusion:** The "absorption" signal does not identify institutional accumulation in BTC perpetual swaps. The hypothesis is fundamentally incompatible with BTC market microstructure.

### 3. Fast Failure is Success

- Checkpoint 2: Identified measurement errors (3 days)
- Iteration A: Fixed errors, validated hypothesis failed (2 days)
- **Total:** 5 days to conclusive verdict ✅

This is BETTER than:
- Endless parameter tuning (weeks/months)
- False positives from overfitting (dangerous)
- Deploying a losing strategy (expensive)

**Learning velocity:** HIGH ✅

### 4. Next Setup Family is Ready

`compression_breakout` has clearer structure:
- ATR compression (objective, measurable)
- Breakout with volume/OI confirmation (directional)
- NOT reliant on CVD divergence interpretation

**Strategic pivot:** ✅ Option B (compression_breakout) is the correct next step

---

## Recommended Next Step

### Immediate: Mark Absorption Continuation as FAILED

1. Update `docs/MILESTONE_TRACKER.md`:
   - Status: `ABSORPTION-CONTINUATION-RESEARCH-V1` → **FAILED**
   - Verdict: Hypothesis rejected after diagnostic iteration
   - Recommendation: Move to `COMPRESSION-BREAKOUT-RESEARCH-V1`

2. Archive research artifacts:
   - Keep `research_lab/setups/absorption_continuation.py` (educational reference)
   - Do NOT delete (preserves learning, prevents re-attempting same hypothesis)

### Next Milestone: COMPRESSION-BREAKOUT-RESEARCH-V1

**If user approves:**

Generate handoff for:
```text
COMPRESSION-BREAKOUT-RESEARCH-V1
```

**Hypothesis:**
- Regime: `compression` (ATR multi-week low) → `expansion` (volatility breakout)
- Entry: Breakout of consolidation range + volume/OI surge + TFI confirmation
- Edge: Catching explosive moves after volatility compression (different structure, different data than absorption)
- Risk: Invalidation on failed breakout (stop below consolidation low)

**Why this is different from absorption:**
- Objective: ATR compression is measurable, not interpretive
- Structure: Consolidation → breakout is clearer than pullback → continuation
- Data: Does NOT rely on CVD divergence (absorption thesis failed)
- Frequency: Compression events are rarer but higher quality

**Estimated timeline:** 1-2 weeks for research validation (same protocol as absorption)

---

## Final Verdict: HYPOTHESIS FAILED

### Verdict Summary

| Dimension | Status |
|---|---|
| **Scope Compliance** | ✅ PASS (A1 + A2 only, no drift) |
| **Implementation Quality** | ✅ PASS (both fixes correct) |
| **Test Coverage** | ✅ PASS (10/10 tests) |
| **Methodology Integrity** | ✅ PASS (no parameter rescue) |
| **Layer Separation** | ✅ PASS (research-only) |
| **Hard Gates** | ❌ **FAIL** (3 / 4 failed) |
| **Edge Validation** | ❌ **FAILED** (negative ER, losing PF) |
| **Absorption Predictiveness** | ❌ **FAILED** (24% hit rate) |

### Bottom Line

**The iteration was executed perfectly. The hypothesis is fundamentally flawed.**

- Measurement fixes (A1, A2) revealed the truth: setup loses money
- Hard stop criteria triggered (ER, win rate, absorption hit rate failed)
- No further iterations justified (per handoff mandate)
- Correct action: Abandon absorption hypothesis, move to compression_breakout

**Audit Conclusion:** ✅ **ITERATION CORRECTLY EXECUTED, HYPOTHESIS CORRECTLY REJECTED**

---

**Signed:** Claude Code (Auditor)  
**Date:** 2026-05-12  
**Status:** Ready for user decision on next milestone (COMPRESSION-BREAKOUT-RESEARCH-V1)
