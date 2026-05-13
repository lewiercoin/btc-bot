# AUDIT: TREND SWEEP SPECIALIST — CHECKPOINT 2

**Date:** 2026-05-13  
**Auditor:** Claude Code  
**Builder:** Cascade  
**Milestone:** SWEEP-RECLAIM-FAMILY-EXPANSION-V1  
**Variant:** trend_sweep_specialist (Variant 2)  
**Branch:** `research/sweep-family-expansion-v1`  
**Commit:** `d03473d`

---

## Verdict: **HYPOTHESIS FAILED**

**ER 0.63 with 159 trades (adequate sample). Hard stop triggered. Novel component (uptrend SHORT) has zero edge.**

---

## Executive Summary

The Trend Sweep Specialist hypothesis — that sweeps in trending regimes have higher reversion probability due to exhaustion dynamics — has been **disproven**.

**Critical finding:** The novel/independent component (uptrend SHORT) has **zero edge** (ER 0.09). The component with moderate edge (downtrend LONG, ER 0.76) **fully overlaps** with trial-00095's existing behavior. No independent alpha available.

**Emerging pattern (V1 + V2):**
- **SHORT sweep_reclaim fails universally** (normal: ER -0.92, uptrend: ER 0.09)
- **LONG has varying edge** (downtrend: ER 0.76, normal: ER 0.02)
- **Regime filtering alone cannot create independent alpha**
- **trial-00095's ER 2.1 is parameter-driven, not context-driven**

**Strategic implication:** Context-based family expansion through regime filtering is proving non-viable. Two consecutive HYPOTHESIS_FAILED with consistent pattern: novel components have zero/negative edge, existing components overlap with trial-00095.

---

## Audit Dimensions

### Layer Separation: **PASS**
- Clean setup isolation in `research_lab/setups/trend_sweep_specialist.py`
- No modifications to core pipeline or trial-00095
- Reused Variant 1 infrastructure pattern effectively

### Contract Compliance: **PASS**
- Config dataclass with typed fields
- Filter functions return explicit tuples
- Decision records include regime + direction context

### Determinism: **PASS**
- Regime filter deterministic (regime from snapshot)
- Direction logic explicit (downtrend→LONG, uptrend→SHORT)
- Min trend cycles filter stateless
- Reproducible results

### State Integrity: **PASS**
- No persistent state
- Stateless filters (regime, trend duration)
- Replay data sufficient

### Error Handling: **PASS**
- Edge cases handled (unknown regime → empty directions)
- No exceptions in 148,609 cycle replay

### Smoke Coverage: **PASS**
- 19 tests, all passing
- Regime filtering: all 6 regimes tested
- Direction logic: downtrend/uptrend/normal/unknown
- Volatility filter: enabled/disabled/boundaries
- Decision records: default/rejection cases

### Tech Debt: **LOW**
- Clean implementation
- No stubs or TODOs
- Proper code reuse (V1 pattern)

### AGENTS.md Compliance: **PASS**
- Commit message: WHAT/WHY/STATUS format
- Builder did NOT self-audit
- Fast failure discipline applied
- Research branch used

---

## Methodology Integrity: **PASS**

**Hypothesis tested:** Sweeps in trending regimes have higher reversion due to exhaustion dynamics.

**Test design:**
- Regime filter: downtrend OR uptrend (79.7% of cycles pass)
- Direction: Counter-trend (downtrend→LONG, uptrend→SHORT)
- Optional: Min trend cycles (disabled for Run 1)

**Sample adequacy:** 159 trades (far exceeds min 20 gate)

**Independence mechanism:**
- uptrend SHORT: Novel (trial-00095 blocks uptrend entirely)
- downtrend LONG: Overlaps (trial-00095 allows LONG in downtrend)

**Conclusion:** Hypothesis disproven. Novel component has zero edge (ER 0.09), overlapping component has moderate but sub-threshold edge (ER 0.76).

---

## Validation Gates

| Gate | Threshold | Result | Status |
|---|---|---|---|
| ER > 1.5 | Required | 0.63 | ❌ FAIL |
| ER > 1.0 | Hard stop | 0.63 | ❌ FAIL (hard stop triggered) |
| Min trades ≥ 20 | Required | 159 | ✅ PASS |
| Overlap < 30% | Required | ~100% | ❌ FAIL (downtrend LONG fully overlaps) |
| Win rate ≥ 50% | Target | 47.8% | ❌ FAIL |
| PF ≥ 2.5 | Target | 1.89 | ❌ FAIL |

**Verdict:** REJECT (hard stop). Only sample size gate passed.

---

## Critical Findings

### 1. **Novel component (uptrend SHORT) has zero edge** (most critical)

| Context | Trades | ER | PF | Sharpe | Assessment |
|---|---:|---:|---:|---:|---|
| **Uptrend → SHORT** | **32** | **0.09** | **1.09** | **0.92** | **Zero edge (novel)** |
| Downtrend → LONG | 127 | 0.76 | 2.10 | 5.34 | Moderate (overlaps trial-00095) |
| **Combined** | **159** | **0.63** | **1.89** | **4.75** | **Sub-threshold** |

**Implication:** Counter-trend SHORT in uptrend produces essentially random outcomes. Exhaustion dynamic hypothesis does NOT hold for SHORT. Trends persist more than they reverse from sweeps.

### 2. **Downtrend LONG overlaps 100% with trial-00095**

trial-00095 default whitelist:
- `downtrend`: `("LONG", "SHORT")` — allows both directions
- `uptrend`: `()` — blocks all directions

**Therefore:**
- All 127 downtrend LONG trades in Variant 2 would also be taken by trial-00095
- Only the 32 uptrend SHORT trades are independent
- But uptrend SHORT has zero edge (ER 0.09)

**Implication:** No independent alpha available. The novel component fails, the existing component overlaps.

### 3. **Emerging pattern: SHORT fails universally** (cross-variant insight)

| Variant | Context | Direction | Trades | ER | Assessment |
|---|---|---|---:|---:|---|
| V1 | Normal | SHORT | 5 | **-0.92** | **Destructive** |
| V1 | Normal | LONG | 16 | 0.02 | Zero edge |
| V2 | Uptrend | SHORT | 32 | **0.09** | **Zero edge** |
| V2 | Downtrend | LONG | 127 | 0.76 | Moderate (overlaps) |

**Pattern conclusive:** SHORT sweep_reclaim signals fail in ALL tested regimes (normal: -0.92, uptrend: 0.09). The edge is **LONG-only**.

### 4. **Regime filtering alone cannot create independent alpha**

Two consecutive HYPOTHESIS_FAILED with consistent pattern:
- V1: Normal regime specialization → ER -0.20 (novel SHORT component destructive)
- V2: Trending regime specialization → ER 0.63 (novel SHORT component zero edge)

**Implication:** trial-00095's ER 2.1 is **parameter-driven** (Optuna-optimized sweep/TFI/flow thresholds), NOT **context-driven** (regime filtering). Family expansion through regime context alone is proving non-viable.

---

## Strategic Implications

### What Two Failures Tell Us

**V1 + V2 pattern reveals:**
1. **SHORT direction consistently fails** — Edge is LONG-biased, not bidirectional
2. **Novel components have zero/negative edge** — Independent entries don't work
3. **Regime filtering removes edge** — trial-00095's regime-agnostic approach superior
4. **Parameter optimization >> context filtering** — Edge comes from threshold tuning, not regime specialization

### Why Trending Regime Hypothesis Failed

**Hypothesis (exhaustion dynamic):**
- Trend overextends → sweep → no follow-through → snap-back
- Counter-trend reversion after failed continuation

**Reality (trends persist):**
- Uptrend sweeps HIGH don't reverse (ER 0.09 = random)
- Downtrend sweeps LOW do reverse (ER 0.76) but already captured by trial-00095
- Exhaustion dynamic insufficient to create tradeable edge at 15m frequency

**Pattern:** Similar to 15m multi-setup portfolio failures — timing incompatibility. Trend exhaustion signals may require faster frequency (5m/1m) to catch reversal before trend resumes.

---

## Implementation Quality: **EXCELLENT**

### Code Quality
- Clean config dataclass
- Explicit regime + direction logic
- Proper reuse of V1 infrastructure pattern
- Edge cases handled (unknown regime)

### Test Coverage
- 19 tests, all passing
- Regime filtering: all 6 regimes
- Direction logic: all cases
- Volatility filter: boundaries
- Decision records: default/rejection

### Documentation
- Validation report: comprehensive metrics, emerging pattern analysis
- Audit package: per-regime/direction breakdown, overlap assessment
- Cross-variant comparison table (V1 vs V2)

---

## Deliverables: **COMPLETE**

- ✅ `research_lab/setups/trend_sweep_specialist.py`
- ✅ `research_lab/backtest_trend_sweep.py`
- ✅ `tests/test_research_lab_trend_sweep.py` — 19 tests (all pass)
- ✅ `research_lab/reports/trend_sweep_specialist_validation_report.md`
- ✅ `research_lab/reports/TREND_SWEEP_SPECIALIST_AUDIT_PACKAGE.md`

---

## Recommended Next Step

### Option 1: Variant 3 (Special Regime Sweep) — FINAL REGIME TEST

**Modified hypothesis (learning from V1 + V2):**

Sweeps in **special regimes** (crowded_leverage + post_liquidation) have higher reversion probability due to **forced positioning pressure**, not exhaustion dynamics.

**Key design changes based on V1 + V2 learnings:**
1. **LONG ONLY** — Drop SHORT direction entirely (0/2 pattern: SHORT fails universally)
2. **crowded_leverage + post_liquidation** — Forced positioning contexts (funding extremes, liquidation aftermath)
3. **No bidirectional hypothesis** — Asymmetric whitelist (LONG only)

**Rationale:**
- Special regimes = asymmetric pressure (funding extremes, forced liquidations)
- Different mechanism than normal (no edge) or trending (exhaustion failed)
- Final regime test before concluding regime-based expansion non-viable

**Expected outcome:**
- If ER > 1.5: Edge concentrates in forced positioning contexts ✅
- If ER < 1.0: 3/3 regime failures → regime-based family expansion not viable

**If V3 fails (3/3), then strategic pivot to:**

### Option 2: Parameter-Based Variants (Not Context-Based)

Since trial-00095's ER 2.1 is parameter-driven (Optuna thresholds), test parameter variations:
- **Conservative Sweep:** Higher sweep distance threshold (fewer but cleaner sweeps)
- **Aggressive TFI:** Lower TFI threshold (more forced positioning entries)
- **Confluence Specialist:** Require all 4 signals (sweep + reclaim + TFI + flow) vs current 3-of-4

**Independence mechanism:** Different threshold configurations → different opportunity sets

### Option 3: Microstructure-Based Variants

Test liquidity/microstructure contexts (not regime):
- **Session Sweep:** Asia hours only (lower liquidity = sweeps more effective?)
- **Thin Liquidity Sweep:** Order book depth < percentile threshold
- **Fresh Sweep:** Time since last sweep > X hours (stop accumulation)

**Independence mechanism:** Timing/liquidity context, not regime

### Option 4: Conclude Family Expansion Saturated

After 3 regime failures, conclude:
- sweep_reclaim edge is singular (parameter-optimized, regime-agnostic)
- Family expansion through context variations not viable
- Recommend 5m frequency upgrade assessment (faster timing may unlock new contexts)

---

## My Recommendation

**Test Variant 3 (Special Regime Sweep, LONG only) as final regime test.**

**Rationale:**
1. **Complete the regime search space** — Special regimes (forced positioning) are mechanistically different from normal/trending
2. **Apply learnings** — LONG only (drop SHORT), asymmetric pressure hypothesis
3. **Fast failure discipline** — If V3 fails, 3/3 regime failures = conclusive evidence

**If V3 succeeds (ER > 1.5, overlap < 30%):** Edge found in forced positioning contexts → continue family expansion

**If V3 fails (ER < 1.0):** Regime-based expansion exhausted → pivot to Option 2 (parameter variants) or Option 3 (microstructure variants)

**Timeline:** 2-3 weeks for V3 (same as V1/V2)

---

## Exit Criteria Check (from original handoff)

**Original criteria:** "After 3 variants, if 0-1 succeed OR overlap > 50% → pivot to 5m assessment"

**Current status:** 2 variants tested, 0 succeed, 1 remaining in original plan

**Recommendation:** Test V3 (special regimes) as 3rd variant. If 0/3 succeed, then per exit criteria → either pivot to non-regime variants (parameter/microstructure) OR assess 5m upgrade.

---

## Observations (Non-Blocking)

### 1. **PF 1.89 and positive PnL are misleading**
- Raw PnL +$9,915 because downtrend LONG winners are large (avg 3.01R)
- But losers frequent enough (52.2% loss rate) that ER sub-threshold
- Reminds: ER and overlap gates are correct rejection criteria (PF alone insufficient)

### 2. **Downtrend LONG (ER 0.76) is real but insufficient**
- PF 2.10, Sharpe 5.34 — statistically significant edge
- But ER 0.76 < 1.0 hard stop, and 100% overlap with trial-00095
- This suggests trial-00095's downtrend performance may be **carrying** overall ER 2.1
- Implication: trial-00095 likely performs BEST in downtrend (test this hypothesis if needed)

### 3. **Volatility filter disabled for Run 1**
- Same as V1 strategy (find adequate sample first, iterate if needed)
- Correct approach — volatility filtering in V1 blocked sample without improving edge
- No iteration needed (hard stop triggered with adequate 159 trades)

---

## Audit Summary

| Dimension | Status | Notes |
|---|---|---|
| Layer Separation | ✅ PASS | Clean research isolation |
| Contract Compliance | ✅ PASS | Typed configs, explicit tuples |
| Determinism | ✅ PASS | Reproducible results |
| State Integrity | ✅ PASS | Stateless filters |
| Error Handling | ✅ PASS | Edge cases handled |
| Smoke Coverage | ✅ PASS | 19 tests, all pass |
| Tech Debt | ✅ LOW | Clean implementation |
| AGENTS.md Compliance | ✅ PASS | Correct discipline |
| Methodology Integrity | ✅ PASS | Hypothesis properly tested |
| Implementation Quality | ✅ EXCELLENT | Clean, tested, documented |

---

## Final Verdict: **HYPOTHESIS FAILED — RECOMMEND VARIANT 3 (MODIFIED)**

**Scientific assessment:** Hypothesis disproven. Novel component (uptrend SHORT) has zero edge (ER 0.09), overlapping component (downtrend LONG) has moderate but sub-threshold edge (ER 0.76). Two consecutive failures with consistent pattern: SHORT fails universally, regime filtering alone cannot create independent alpha.

**Strategic assessment:** Regime-based family expansion is proving non-viable. trial-00095's ER 2.1 is parameter-driven (Optuna optimization), not context-driven (regime specialization). However, special regimes (crowded_leverage, post_liquidation) remain untested and are mechanistically different (forced positioning vs exhaustion dynamics).

**Implementation assessment:** Excellent work by Cascade. Clean code, proper tests, comprehensive analysis, cross-variant pattern recognition.

**Next milestone:** VARIANT 3: SPECIAL REGIME SWEEP SPECIALIST

**Hypothesis:** Sweeps in forced positioning regimes (crowded_leverage, post_liquidation) have higher reversion probability due to asymmetric pressure.

**Key modifications:** LONG ONLY (drop SHORT based on 0/2 pattern), forced positioning contexts (not exhaustion dynamics).

**Approval:** Proceed to Variant 3 (modified scope: LONG only, special regimes). This is the final regime test. If V3 fails (3/3), conclude regime-based expansion not viable and pivot to parameter-based or microstructure-based variants.

---

**Audit complete. Cascade: You are approved to proceed to Variant 3 with modified scope (LONG only, crowded_leverage + post_liquidation). This is the final regime test before strategic pivot.**
