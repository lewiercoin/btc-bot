# AUDIT: Compression Breakout Iteration A

Date: 2026-05-12  
Auditor: Claude Code  
Commit: `e1a5f1f` - "research: complete compression breakout iteration A"  
Branch: `research/compression-breakout-v1`  
Builder: Codex  

## Verdict: HYPOTHESIS FAILED

Iteration A correctly identified that COMPRESSION labels exist (1.98% of cycles) but revealed the fundamental flaw: **compression states and executable breakouts are sequential, not concurrent**. Breakouts occur AFTER compression ends, not during. Setup generated only 3 trades with negative ER. Hard stop criteria triggered. Hypothesis is fundamentally incompatible with BTC perps market microstructure.

---

## Executive Summary

Iteration A was a diagnostic attempt to fix suspected regime classification issue from Checkpoint 1 (0 compression regime trades).

**Findings:**
- **COMPRESSION labels exist:** 2,938 / 148,596 cycles = 1.98% (not absent, just uncommon as expected)
- **Root cause identified:** Problem is NOT missing labels - it's that **compression-labeled cycles don't have executable breakouts**
- **Compression metrics:** Mean breakout_size_atr = **-3.77** (NEGATIVE - price below recent high, not breaking out)
- **Rejection analysis:** 97.4% of compression cycles blocked by `breakout_too_small` or `no_breakout_detected`

**Results after regime adjustment:**
- Total trades: 3 (same as Checkpoint 1)
- ER: -0.298229 (negative, losing money)
- PF: 0.435318 (below 1.0)
- Breakout follow-through: 100% (but 3 trades only, not meaningful)

**Hard Stop Triggered:** 3 gates failed (trades <20, ER <1.5, internal compression trades <10)

**Verdict:** HYPOTHESIS FAILED - compression → breakout hypothesis is fundamentally flawed for BTC perps.

---

## Implementation Quality: PASS

### A1: Regime Distribution Analysis - CORRECT

**Analysis:** `research_lab/analyze_regime_distribution.py`

**Findings:**

| Regime | Count | Percentage |
|---|---:|---:|
| uptrend | 63,891 | 43.0% |
| downtrend | 63,598 | 42.8% |
| crowded_leverage | 13,970 | 9.4% |
| normal | 4,199 | 2.8% |
| **compression** | **2,938** | **2.0%** |
| post_liquidation | 0 | 0.0% |

**Interpretation:** ✅ COMPRESSION labels are present but uncommon (2%), as expected for rare volatility compression events.

**ATR 4H Norm by Regime:**

| Regime | Mean | P50 | P95 |
|---|---:|---:|---:|
| **compression** | **0.00468** | **0.00486** | **0.00545** |
| normal | 0.01345 | 0.01247 | 0.02337 |
| uptrend | 0.01454 | 0.01350 | 0.02615 |
| downtrend | 0.01691 | 0.01518 | 0.03146 |
| crowded_leverage | 0.01661 | 0.01544 | 0.02957 |

✅ **Validation:** COMPRESSION-labeled cycles have LOWEST ATR (mean 0.00468 vs 0.0135-0.0169 for other regimes). RegimeEngine is correctly identifying low-volatility compression states.

---

### A2: Regime as Veto - IMPLEMENTED

**Change:** `research_lab/setups/compression_breakout.py`

**Before:**
```python
def check_regime_allowed(self, regime):
    return regime in {COMPRESSION, NORMAL}  # Strict trigger
```

**After:**
```python
def check_regime_allowed(self, regime):
    # Regime as veto: block trending/crowded, accept others
    blocked = {UPTREND, DOWNTREND, CROWDED_LEVERAGE, POST_LIQUIDATION}
    return regime not in blocked
```

✅ **Correct implementation** - Regime used as safety veto, internal compression detection (ATR percentile, range width) is primary trigger.

**Impact:** None - setup already allowed NORMAL + COMPRESSION in Checkpoint 1, so expanding to "any non-trending" didn't change the allowed set.

---

## Test Results: PASS

**Command:** `pytest tests/test_research_lab_compression_breakout.py -v`

**Result:** 8 passed, 0 failed

**Key tests:**
- `test_compression_breakout_generates_explained_long_candidate` ✅
- `test_compression_breakout_blocks_wrong_regime_and_absorption_retry` ✅
- `test_compression_breakout_accepts_normal_when_internally_compressed` ✅ (Iteration A feature)
- `test_compression_breakout_requires_objective_compression_history` ✅
- `test_compression_breakout_rejects_no_breakout` ✅
- `test_compression_breakout_blocks_crowded_or_panic_context` ✅
- `test_compression_gate_evaluator_blocks_missing_validation_evidence` ✅
- `test_compression_gate_evaluator_rejects_failed_breakout_thesis` ✅

**Compileall:** ✅ PASS

---

## Critical Finding: Sequential vs Concurrent Events

### The Fundamental Flaw

**Hypothesis assumed:** Compression (coiling) and breakout (expansion) occur **simultaneously** → enter at breakout while still in compression state

**Reality:** Compression and breakout are **sequential events**:
1. **Compression phase:** ATR contracts, range narrows, price coils
2. **Transition:** Volatility begins to expand, regime may shift
3. **Breakout phase:** Price breaks range, ATR expands, directional move

**Evidence from rejection analysis:**

In COMPRESSION-labeled cycles (2,938 total):
- Candidates generated: **7** (0.24%)
- Primary blockers:
  - `breakout_too_small`: 2,862 (97.4%)
  - `no_breakout_detected`: 2,856 (97.2%)
  - `tfi_below_breakout_threshold`: 2,180 (74.2%)

**Compression metrics during compression-labeled cycles:**

| Metric | Mean | P50 | P95 | Interpretation |
|---|---:|---:|---:|---|
| atr_percentile | 0.109 | 0.039 | 0.43 | ✅ Low percentile (compressed) |
| range_width_atr | 11.26 | 9.48 | 24.13 | ⚠️ Wide range (not tight coiling?) |
| compression_duration_bars | 66.1 | 89.0 | 102.0 | ✅ Long compression |
| **breakout_size_atr** | **-3.77** | **-3.39** | **-0.33** | ❌ **NEGATIVE** |

**Critical:** `breakout_size_atr` is **NEGATIVE** (mean -3.77, median -3.39, p95 -0.33).

This means:
- During compression, price is typically **BELOW recent high** (not breaking out)
- Price is in the MIDDLE of consolidation range
- Breakouts occur AFTER compression ends (when regime transitions away from COMPRESSION)

**Timing incompatibility:**
- Setup looks for: `regime=COMPRESSION` + `breakout confirmed`
- Reality: Compression → (transition) → Breakout
- These are sequential, not concurrent

**This is analogous to absorption's failure:**
- Absorption: CVD divergence during pullback → continuation (NOT predictive)
- Compression: Coiling during compression → breakout (NOT concurrent, sequential)

---

## Backtest Results After Iteration A

### Full-Range Metrics (2022-01-01 to 2026-03-29)

| Metric | Result | Hard Gate | Status |
|---|---:|---:|---|
| Total cycles | 148,596 | - | - |
| COMPRESSION cycles | 2,938 (2.0%) | - | ✅ Labels exist |
| Candidates | 7 (compression) + 0 (other) | - | |
| Closed trades | 3 | ≥ 20 | ❌ **FAIL** |
| **Internal compression trades** | **3** | **≥ 10** | ❌ **FAIL** |
| **ER** | **-0.298229** | **> 1.5** | ❌ **FAIL** |
| **PF** | **0.435318** | > 1.0 | ❌ **FAIL (< 1.0)** |
| Breakout follow-through | 100% | ≥ 40% | ⚠️ PASS (but 3 trades) |
| Win rate | 0.33 (1 win / 3 trades) | > 35% | ⚠️ Low sample |
| WF | not run | 2/2 | ❌ BLOCKED |
| Overlap | not run | <30% | ❌ BLOCKED |

**Hard Gates Passed:** 0 / 8 (only explainability passed)

**Hard Gates Failed:** 3 critical gates (trades, internal compression trades, ER)

**Verdict per Hard Stop Criteria:** ❌ **HYPOTHESIS FAILED**

---

## Rejection Analysis: Why Compression Doesn't Generate Breakouts

### Compression-Labeled Cycles

**Total:** 2,938 cycles labeled as `regime=compression`

**Candidate rate:** 7 / 2,938 = 0.24% (0.0024)

**Top rejection reasons in compression cycles:**

| Reason | Count | % of Compression Cycles | Interpretation |
|---|---:|---:|---|
| `breakout_too_small` | 2,862 | 97.4% | Price hasn't broken out significantly |
| `no_breakout_detected` | 2,856 | 97.2% | Price still within range |
| `tfi_below_breakout_threshold` | 2,180 | 74.2% | No directional flow surge |
| `range_width_not_compressed` | 1,907 | 64.9% | Range not tight enough |
| `confluence_too_low` | 1,287 | 43.8% | Not enough confirmation |

**Key insight:** During compression, price is **IN THE RANGE**, not breaking out. Breakouts happen **AFTER** compression ends.

### All Regimes Comparison

| Regime | Cycles | Candidates | Rate | Why blocked? |
|---|---:|---:|---:|---|
| **compression** | 2,938 | 7 | 0.24% | **No breakout during coiling** |
| uptrend | 63,891 | 0 | 0.0% | Regime blocked (trending) |
| downtrend | 63,598 | 0 | 0.0% | Regime blocked (trending) |
| crowded_leverage | 13,970 | 0 | 0.0% | Regime blocked (crowded) |
| normal | 4,199 | 0 | 0.0% | No compression detected |

Only 7 candidates across entire dataset → 3 closed trades → negative ER.

---

## Comparison to Absorption Failure

| Aspect | Absorption (FAILED) | Compression (FAILED) |
|---|---|---|
| **Checkpoint 2** | 4 trades, ER 0.34 | 3 trades, ER -0.30 |
| **Measurement issue** | Volatility threshold (0.008 vs p95=0.029) | Regime classification (suspected) |
| **Iteration A fix** | CVD slope + empirical volatility | Regime distribution + regime as veto |
| **Post-fix sample** | 25 trades | 3 trades (no change) |
| **Post-fix ER** | -0.48 (negative) | -0.30 (negative, unchanged) |
| **Root cause** | CVD not predictive (24% hit rate) | Compression/breakout sequential, not concurrent |
| **Thesis status** | TESTED → FAILED | TESTED → FAILED |
| **Timeline** | 5 days (Checkpoint 2 → Iteration A verdict) | 2 days (Checkpoint 1 → Iteration A verdict) |

**Common pattern:**
- Both had measurement issues suspected
- Both were given ONE diagnostic iteration to fix measurement
- Both still failed after measurement fixes
- Both revealed fundamental hypothesis flaws (not just measurement errors)

**Learning:**
- Absorption: CVD divergence during pullback doesn't predict continuation
- Compression: Compression and breakout are sequential events, not concurrent

---

## Hard Stop Criteria: TRIGGERED

Per iteration handoff, stop immediately if ANY of the following after re-run:

| Criterion | Threshold | Actual | Status |
|---|---|---:|---|
| Total trades | < 20 | **3** | ❌ **FAIL** |
| Internal compression trades | < 10 | **3** | ❌ **FAIL** |
| Compression ER | < 1.5 | **-0.298** | ❌ **FAIL** |
| Breakout follow-through | < 40% | 100% (3 trades) | ⚠️ PASS (invalid sample) |
| Win rate | < 35% | 33% (1/3) | ⚠️ MARGINAL |

**Hard Stop Result:** ❌ **TRIGGERED** (3 out of 5 criteria failed)

**Mandatory Action per Handoff:** Close COMPRESSION-BREAKOUT-RESEARCH-V1 as FAILED, recommend crowded_unwind (Option B)

---

## Why WF Was Not Run: Correct Decision

Per handoff protocol:
> "WF validation is required only after sample gate passes."

**Sample gates:**
- Total trades ≥ 20 ❌ (actual: 3)
- Internal compression trades ≥ 10 ❌ (actual: 3)
- Compression ER > 1.5 ❌ (actual: -0.30)

**All sample gates failed.** Running WF would only confirm the setup is unstable with negative edge. No additional information value.

**Decision:** ✅ Correct - saved compute cost, verdict is unambiguous.

---

## Layer Separation: PASS

- ✅ No changes to `core/**`, `execution/**`, `governance/**`, `risk/**`, `settings.py`
- ✅ RegimeEngine untouched (production component)
- ✅ All work in `research_lab/**`, `tests/**`, `docs/**`
- ✅ Research-only data paths

---

## Determinism: PASS

- Regime distribution analysis: deterministic query of decision_outcomes table
- Re-run backtest: same date range (2022-2026), deterministic
- Results are reproducible

---

## Tech Debt: LOW

No new tech debt introduced. Setup is REJECTED, no production deployment planned.

---

## AGENTS.md Compliance: PASS

| Rule | Required | Actual | Status |
|---|---|---|---|
| Commit discipline | WHAT/WHY/STATUS | ✅ Present in e1a5f1f | ✅ PASS |
| Layer isolation | Research changes only | ✅ Zero production changes | ✅ PASS |
| No self-audit | Builder requests Claude audit | ✅ Builder verdict: HYPOTHESIS FAILED | ✅ PASS |

---

## Critical Issues: NONE

**None blocking promotion (because setup is REJECTED).**

---

## Warnings: NONE

**None.** Iteration was correctly scoped and executed. Negative result is the CORRECT outcome - hypothesis was tested fairly and failed.

---

## Observations

### 1. Regime Classification Was Working Correctly

RegimeEngine correctly identifies compression states (2% of cycles with lowest ATR). The problem wasn't classification - it was that **compression doesn't coincide with executable breakouts**.

### 2. Timing Incompatibility is Fundamental

Compression → breakout is a **sequential process**, not a concurrent state:
- Phase 1: Volatility compresses, range narrows (COMPRESSION regime)
- Phase 2: Transition begins, volatility starts expanding
- Phase 3: Breakout occurs, directional move (regime may shift to UPTREND/DOWNTREND)

Setup tried to catch Phase 1 + Phase 3 simultaneously → impossible.

### 3. Fast Failure Discipline Validated Again

**Absorption:** 5 days to conclusive verdict (FAILED)  
**Compression:** 2 days to conclusive verdict (FAILED)

Both setups were tested fairly, found lacking, and rejected quickly without wasted parameter tuning.

**This rapid iteration prevents months of unproductive work on invalid hypotheses.**

### 4. Two Portfolio Setups Failed, Lessons Clear

**Setup #1: sweep_reclaim** → DEPLOYED ✅ (ER 2.13, 271 trades, production-ready)  
**Setup #2: absorption_continuation** → FAILED ❌ (CVD not predictive, -0.48 ER)  
**Setup #3: compression_breakout** → FAILED ❌ (compression/breakout sequential, -0.30 ER)

**Lessons learned:**
- Liquidity-hunt structure (sweep-reclaim) works for BTC perps
- Interpretive signals (CVD divergence) don't work
- Sequential event timing (compression → breakout) doesn't work
- Need structures where entry trigger and edge thesis coincide

---

## Recommended Next Step

### Immediate: Close Compression Breakout as FAILED

**Update `docs/MILESTONE_TRACKER.md`:**
- Status: `COMPRESSION-BREAKOUT-RESEARCH-V1` → **FAILED**
- Verdict: Hypothesis rejected after diagnostic iteration
- Timeline: 2 days (Checkpoint 1 → Iteration A verdict)
- Reason: Compression and breakout are sequential events, not concurrent. Cannot generate executable sample.

### Next Milestone: CROWDED-UNWIND-RESEARCH-V1

**If user approves:**

Generate handoff for:
```text
CROWDED-UNWIND-RESEARCH-V1
```

**Hypothesis:**
- **Structure:** Funding/OI extremes (crowded positioning) → forced unwind → reversal/retracement
- **Entry:** Funding > p95 threshold + OI peak + force order spike begins → enter opposite direction
- **Edge:** Catching forced liquidations and position unwinds when leverage becomes unsustainable
- **Counterparty:** Crowded longs (on funding extremes) forced to close/liquidate

**Why this is different from absorption/compression:**
- **Not interpretive:** Funding rate, OI levels, force orders are objective metrics
- **Not sequential:** Crowding and unwind happen together (concurrent, not sequential)
- **Proven edge:** Liquidation cascades are real, measurable events in crypto
- **Clear counterparty:** Overleveraged traders forced to exit

**Data available:**
- Funding rate (8h, SMAs, percentiles)
- OI (value, Z-score 60d, delta)
- Force orders (rate_60s, spike detection)
- TFI (directional flow confirmation)

**Estimated timeline:** 1-2 weeks for research validation (same protocol)

---

### Alternative Paths

**Option 1: Pause portfolio research**
- Two consecutive setup failures (absorption, compression)
- May want to reassess portfolio strategy before continuing
- Review lessons learned, adjust hypothesis generation process

**Option 2: Skip to different setup family**
- **Trend pullback** (different from absorption - focus on EMA bounce timing, not CVD)
- **Mean reversion extreme** (price > 2-3 ATR from mean + funding extreme)
- **Post-liquidation recovery** (after cascade settles, fade the panic)

**Option 3: Proceed with crowded_unwind (recommended)**
- Strongest hypothesis remaining (proven edge in crypto liquidations)
- Objective metrics (not interpretive like CVD)
- Concurrent timing (crowding + unwind happen together)

---

## Final Verdict: HYPOTHESIS FAILED

### Verdict Summary

| Dimension | Status |
|---|---|
| **Implementation Quality** | ✅ PASS |
| **Regime Analysis** | ✅ PASS (labels exist, classification correct) |
| **Test Coverage** | ✅ PASS (8/8 tests) |
| **Layer Separation** | ✅ PASS (zero production changes) |
| **Sample Size** | ❌ FAIL (3 trades, <20 required) |
| **Edge Validation** | ❌ **FAILED** (ER -0.30, negative) |
| **Timing Compatibility** | ❌ **FAILED** (compression/breakout sequential) |

### Bottom Line

**The iteration was executed correctly. The hypothesis is fundamentally flawed.**

- Regime classification was NOT the problem (COMPRESSION labels exist and are correctly assigned)
- Measurement fixes revealed the truth: **compression and breakout are sequential, not concurrent**
- Setup generated only 3 trades with negative ER across 4 years
- Hard stop criteria triggered (3/5 gates failed)
- No further iterations justified

**Audit Conclusion:** ✅ **HYPOTHESIS FAILED - CLOSE COMPRESSION_BREAKOUT, RECOMMEND CROWDED_UNWIND**

---

**Signed:** Claude Code (Auditor)  
**Date:** 2026-05-12  
**Status:** Awaiting user decision on next setup (crowded_unwind recommended)
