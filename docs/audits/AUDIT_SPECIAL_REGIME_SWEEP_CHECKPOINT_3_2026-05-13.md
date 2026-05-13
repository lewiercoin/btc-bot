# AUDIT: SPECIAL REGIME SWEEP SPECIALIST — CHECKPOINT 3 (FINAL)

**Date:** 2026-05-13  
**Auditor:** Claude Code  
**Builder:** Cascade  
**Milestone:** SWEEP-RECLAIM-FAMILY-EXPANSION-V1  
**Variant:** special_regime_sweep_specialist (Variant 3 — FINAL REGIME TEST)  
**Branch:** `research/sweep-family-expansion-v1`  
**Commit:** `cf2330d`

---

## Verdict: **HYPOTHESIS FAILED (3/3 — REGIME-BASED EXPANSION NOT VIABLE)**

**ER 0.30 with 34 trades (adequate sample). Hard stop triggered. Regime-based family expansion conclusively exhausted.**

---

## Executive Summary

The Special Regime Sweep Specialist hypothesis — that sweeps in forced positioning regimes (crowded_leverage, post_liquidation) have higher reversion probability — has been **disproven**.

**Results:** ER 0.30 (< 1.0 hard stop), 34 trades, all in crowded_leverage (post_liquidation = 0 cycles).

**Cross-variant conclusion (3/3 failures):**
- **V1 (Normal):** LONG ER 0.02, SHORT ER -0.92
- **V2 (Trending):** Downtrend LONG ER 0.76 (overlaps), Uptrend SHORT ER 0.09
- **V3 (Special):** Crowded_leverage LONG ER 0.30

**Pattern definitive:**
1. **No regime reaches ER 1.0 independently**
2. **SHORT universally unprofitable** (normal: -0.92, uptrend: 0.09)
3. **Regime filtering removes edge** (subsets existing trades, no new alpha)
4. **trial-00095 ER 2.1 is parameter-driven**, not context-driven (Optuna optimization across ALL regimes)

**Strategic conclusion:** Regime-based family expansion NOT viable at 15m frequency. Context filtering alone cannot create independent alpha from sweep_reclaim edge.

---

## Audit Dimensions

### Layer Separation: **PASS**
- Clean setup isolation
- No modifications to core pipeline
- Consistent pattern reuse from V1/V2

### Contract Compliance: **PASS**
- Typed config, explicit filters
- Decision records include regime context

### Determinism: **PASS**
- Regime filter deterministic
- LONG-only whitelist explicit
- Reproducible results

### State Integrity: **PASS**
- Stateless filters
- No persistent state between cycles

### Error Handling: **PASS**
- Edge cases handled (post_liquidation absence)
- No exceptions in full replay

### Smoke Coverage: **PASS**
- 16 tests, all passing
- Regime filtering logic
- Direction whitelist
- Decision records

### Tech Debt: **LOW**
- Clean implementation
- Consistent with V1/V2 quality

### AGENTS.md Compliance: **PASS**
- Proper commit discipline
- Builder did NOT self-audit
- Fast failure applied
- Research branch used

---

## Methodology Integrity: **PASS**

**Hypothesis tested:** Sweeps in forced positioning regimes have higher reversion due to asymmetric pressure.

**Test design:**
- Regime filter: crowded_leverage OR post_liquidation
- Direction: LONG only (SHORT dropped per V1+V2 evidence)
- Minimal filters (regime only, no structure/volatility)

**Sample adequacy:** 34 trades (exceeds min 20 gate)

**Infrastructure gap:** post_liquidation = 0 cycles in 4-year window (regime never classified)

**Conclusion:** Hypothesis disproven. Crowded_leverage LONG has ER 0.30 (<< 1.0 hard stop). Forced positioning pressure insufficient to create tradeable edge.

---

## Validation Gates

| Gate | Threshold | Result | Status |
|---|---|---|---|
| ER > 1.5 | Required | 0.30 | ❌ FAIL |
| ER > 1.0 | Hard stop | 0.30 | ❌ FAIL (hard stop triggered) |
| Min trades ≥ 20 | Required | 34 | ✅ PASS |
| Overlap < 30% | Required | ~100% | ❌ FAIL (crowded_leverage LONG overlaps trial-00095) |
| Win rate ≥ 50% | Target | 38.2% | ❌ FAIL |
| PF ≥ 2.5 | Target | 1.33 | ❌ FAIL |

**Verdict:** REJECT (hard stop). Only sample size gate passed.

---

## Critical Findings

### 1. **V3 standalone: Crowded leverage has weak edge**

| Metric | Value | Assessment |
|---|---|---|
| Trades | 34 | Adequate sample |
| ER | 0.30 | Way below 1.0 hard stop |
| PF | 1.33 | Barely positive |
| Win Rate | 38.2% | Too many losers |
| Max DD | 8.36% | Moderate |

**Implication:** Forced positioning pressure (funding extremes) does NOT create strong reversion edge. Sweeps in crowded_leverage produce marginal outcomes (ER 0.30) insufficient for promotion.

### 2. **post_liquidation infrastructure gap confirmed**

- 0 cycles in 4-year window (2022-01-01 to 2026-03-29)
- Regime engine never classifies post_liquidation
- Likely cause: force_orders data not integrated OR thresholds never met
- Prior research (post_cascade_momentum) also hit this gap

**Implication:** Special regimes (crowded_leverage only) insufficient. post_liquidation untestable due to infrastructure limitation.

### 3. **Cross-variant: No regime reaches ER 1.0**

| Regime | Trades | ER | PF | Assessment |
|---|---:|---:|---:|---|
| downtrend | 127 | **0.76** | 2.10 | **Best (but < 1.0)** |
| crowded_leverage | 34 | 0.30 | 1.33 | Weak |
| normal | 16 | 0.02 | 1.00 | Zero edge |
| uptrend | 0 | — | — | Blocked |
| post_liquidation | 0 | — | — | Absent |

**Critical insight:** trial-00095's ER 2.1 is NOT driven by any single regime. It comes from the **COMBINED effect** across ALL regimes (primarily downtrend, normal, crowded_leverage) with **Optuna-optimized parameters** (confluence thresholds, TFI, risk management).

**Implication:** Regime filtering **subsets** the existing trade set (removes regimes) rather than creating **new independent entries**. Context filtering alone cannot produce alpha.

### 4. **SHORT universally unprofitable (cross-variant)**

| Context | Direction | Trades | ER | Verdict |
|---|---|---:|---:|---|
| Normal | SHORT | 5 | **-0.92** | **Destructive** |
| Uptrend | SHORT | 32 | **0.09** | **Zero edge** |
| Downtrend | SHORT | — | — | Not tested in V2 |
| Crowded_leverage | SHORT | — | — | Not tested in V3 (LONG only) |

**Pattern:** 0/2 SHORT tests passed. SHORT sweep_reclaim signals consistently fail.

**Implication:** sweep_reclaim edge is **LONG-biased**. Directional asymmetry fundamental to the pattern (sweep LOW → LONG reversion works, sweep HIGH → SHORT reversion does not).

---

## Strategic Implications

### Regime-Based Family Expansion: CONCLUSIVELY NOT VIABLE

**Evidence (3/3 failures):**

| Variant | Context | Novel Component | Trades | ER | Result |
|---|---|---|---:|---:|---|
| V1 | Normal | SHORT in normal | 5 | -0.92 | Destructive |
| V2 | Trending | SHORT in uptrend | 32 | 0.09 | Zero edge |
| V3 | Special | LONG in crowded_leverage | 34 | 0.30 | Weak |

**All novel/independent components failed:**
- V1: SHORT in normal (destructive)
- V2: SHORT in uptrend (zero edge)
- V3: Crowded_leverage LONG (weak, < 1.0)

**All moderate-edge components overlap trial-00095:**
- V2: Downtrend LONG (ER 0.76, overlaps 100%)

**Conclusion:** Context filtering (regime specialization) cannot create independent alpha. It only subsets the existing trade set, removing regimes and degrading overall ER.

### Why Regime Filtering Fails

**Hypothesis (context-based edge concentration):**
- Different regimes have different edge magnitudes
- Filtering to high-edge regime creates independent specialist
- Combined specialists > single generalist

**Reality (parameter-based edge optimization):**
- trial-00095 ER 2.1 = Optuna-optimized parameters across ALL regimes
- No single regime reaches ER 1.0 independently
- Regime filtering removes low-edge AND high-edge cycles
- Net effect: Degrades overall ER

**Analogy:** Like removing half the notes from a symphony and expecting louder music. You just get less music.

### What trial-00095 Actually Is

**Not:** A context-agnostic strategy waiting to be specialized by regime filtering

**Actually:** A **parameter-optimized** strategy that achieves ER 2.1 through:
1. Confluence thresholds (sweep distance, reclaim confirmation, TFI alignment, flow strength)
2. Risk management (TP/SL distances, position sizing)
3. Governance gates (safety flags, regime direction whitelists)
4. Operating across ALL regimes (downtrend contributes most, normal/crowded_leverage contribute moderately)

**Implication:** sweep_reclaim is a **singular edge** at 15m, not a family of context-based edges.

---

## Implementation Quality: **EXCELLENT**

### V3 Code Quality
- Clean, minimal config
- LONG-only whitelist explicit
- Proper regime filtering
- Consistent with V1/V2 pattern

### V3 Test Coverage
- 16 tests, all passing
- Regime logic coverage
- Direction whitelist
- Decision records

### Full Milestone Quality
- **3 variants, 214 trades tested, 58 unit tests (all pass)**
- **358 project-wide tests pass, 24 skipped**
- **6 validation reports + audit packages**
- **Clean commit history** (3 builder checkpoints + 3 audit checkpoints)
- **Comprehensive cross-variant analysis**

**Assessment:** Cascade delivered excellent execution across all 3 variants. Fast failure discipline applied correctly. Pattern recognition strong (identified SHORT failure early, modified V3 to LONG-only).

---

## Deliverables: **COMPLETE**

**Per-variant:**
- ✅ V1: Range Sweep Specialist (21 trades, ER -0.20)
- ✅ V2: Trend Sweep Specialist (159 trades, ER 0.63)
- ✅ V3: Special Regime Sweep Specialist (34 trades, ER 0.30)

**Infrastructure:**
- ✅ 3 setup configs, 3 backtest runners, 3 test files
- ✅ 58 unit tests across variants (all pass)
- ✅ 6 validation reports + audit packages
- ✅ Cross-variant analysis tables

**Strategic documentation:** (required before closing milestone)
- ⏳ Update MILESTONE_TRACKER.md (close sweep family expansion, verdict)
- ⏳ Update DECISIONS_LOG.md (regime-based expansion not viable decision)
- ⏳ Strategic assessment document (next steps recommendation)

---

## Recommended Next Steps

### Context: Exit Criteria Triggered

**Original handoff criteria:** "After 3 variants, if 0-1 succeed OR overlap > 50% → pivot to 5m assessment"

**Current status:** 3 variants tested, **0 succeed**, overlap ~100% (all LONG trades subset trial-00095)

**Exit criteria: MET** → Strategic pivot required

---

### Option 1: ONE Microstructure Variant (RECOMMENDED)

**Test Session Sweep Specialist (Asia hours) as final 15m test before accepting singular edge.**

**Hypothesis:** Sweeps during low-liquidity sessions (Asia hours, 00:00-08:00 UTC) have higher reversion probability due to thinner order books and lower participation.

**Why this is different from regime variants:**
- **Mechanism:** Liquidity depth (microstructure), not market structure (regime)
- **Measurable:** Session timestamp (objective), order book depth (if available)
- **Independence:** trial-00095 time-agnostic → session filter creates new opportunity set

**Entry conditions:**
- Time filter: Asia hours (00:00-08:00 UTC)
- Direction: LONG only (proven from V1-V3)
- No regime filter (keep regime-agnostic like trial-00095)
- Optional: Order book depth filter (if data available)

**Expected outcome:**
- If ER > 1.5, overlap < 30%: Microstructure context viable → continue expansion (US hours, fresh sweep, etc.)
- If ER < 1.0: 4/4 failures (3 regime + 1 microstructure) → accept singular edge

**Timeline:** 1-2 weeks (simpler than regime variants - timestamp filter only)

**Rationale:**
- One final 15m test (low cost, high learning value)
- Microstructure != regime (different mechanism)
- If fails: Conclusive evidence 15m context expansion not viable
- If succeeds: Opens microstructure family (session, fresh sweep, order book)

---

### Option 2: Accept Singular Edge, Focus on Live Validation (IF Option 1 fails)

**Decision:** trial-00095 is THE sweep_reclaim edge at 15m. No context-based variants viable. Focus on live performance validation.

**Actions:**
1. **Monitor live performance** (current: 1 trade in 5 days, need 30-50 trades per guardrails)
2. **Validate edge stability** over 6-10 months
3. **Track ER convergence** (backtest ER 2.1 vs live ER)
4. **Assess degradation triggers** (if live ER < 1.0 → edge decay, reassess)

**Exit criteria for live validation:**
- After 30-50 trades: Review ER, PF, safety flags
- After 6 months: If live ER < 1.0 → edge degrading, strategic reassessment
- If stable: Proceed to 5m frequency upgrade assessment

**Rationale:**
- sweep_reclaim proven in backtest (ER 2.1, WF 2/2)
- Context expansion exhausted (4/4 failures if Option 1 fails)
- Live validation prerequisite for further investment (5m upgrade expensive)

---

### Option 3: 5m Frequency Upgrade Assessment (DEFER until live validation)

**Hypothesis:** 5m decision frequency enables timing precision for regime transitions, exhaustion signals, and phase timing that 15m misses.

**Why 15m context expansion failed:**
- Detection latency (volatility breakout: enters mid-phase)
- Event timescale incompatibility (cascades too fast)
- Phase timing (exhaustion signals require faster response)

**Why 5m might work:**
- 3x faster cycle (5min vs 15min) → earlier phase entry
- Cascade detection (seconds-to-minutes events) becomes viable
- Regime transition windows (currently missed) become catchable

**Infrastructure cost (HIGH):**
- Rebuild decision engine (900s → 300s cycles)
- Rebuild data pipeline (15m candles → 5m candles)
- Rebuild state management (3x state updates/hour)
- Rebuild replay tooling (3x data volume)
- Revalidate feature quality (OI, CVD, funding at 5m resolution)

**Timeline:** 6-8 weeks minimum

**Risk:** May hit NEW timing constraints at 5m (e.g., 1m events still too fast). Expensive to discover.

**Recommendation:** DEFER until trial-00095 live performance validates edge stability (6-10 months). If live ER stable ≥1.5 → assess 5m upgrade. If live ER degrades → edge decay, not frequency issue.

---

### Option 4: Parameter-Based Variants (LOWER PRIORITY)

**Hypothesis:** Different parameter configurations (conservative/aggressive thresholds) create independent alpha.

**Variants:**
- **Conservative Sweep:** Higher sweep distance threshold (fewer but cleaner sweeps)
- **Aggressive TFI:** Lower TFI threshold (more forced positioning entries)
- **Confluence Specialist:** Require all 4 signals (sweep + reclaim + TFI + flow) vs current 3-of-4

**Why lower priority:**
- trial-00095 already Optuna-optimized (ER 2.1, WF 2/2 validated)
- Parameter variants risk overfitting (unstable out-of-sample)
- Overlap likely high (different thresholds → overlapping opportunity set)

**When to consider:**
- After live validation (if trial-00095 stable, test parameter variants as portfolio expansion)
- If microstructure variants succeed (parameter + microstructure combinations)

**Not recommended as next step** (context expansion exhausted, parameter expansion risky without live validation).

---

### My Recommendation: OPTION 1 → OPTION 2

**Step 1: Test Session Sweep Specialist (Asia hours) — 1-2 weeks**
- Final 15m context test (microstructure, not regime)
- Low cost, high learning value
- If succeeds: Opens microstructure family
- If fails: Conclusive evidence (4/4 failures)

**Step 2: If Session Sweep fails → Accept Singular Edge — 6-10 months**
- trial-00095 is THE sweep_reclaim edge at 15m
- Focus on live validation (30-50 trades, ER convergence)
- Monitor for degradation triggers

**Step 3: After live validation → 5m upgrade assessment**
- If live ER stable ≥1.5: Assess 5m frequency upgrade
- If live ER degrades: Edge decay, strategic reassessment

**Rationale:**
- One final low-cost 15m test (microstructure mechanistically different from regime)
- If fails: Exhaust 15m completely before expensive 5m investment
- Live validation prerequisite for further capital allocation

---

## Observations (Non-Blocking)

### 1. **post_liquidation infrastructure gap persistent**
- 0 cycles in 4-year window (V3 confirmed)
- Prior research (post_cascade_momentum) also hit this
- Regime engine definition may be too strict OR force_orders data incomplete
- Not critical (crowded_leverage tested, failed independently)

### 2. **Downtrend LONG (ER 0.76) is trial-00095's strongest component**
- 127 trades, PF 2.10, Sharpe 5.34
- Likely drives majority of trial-00095's ER 2.1
- Suggests trial-00095 performs BEST in downtrend (asymmetric regime contribution)
- Could test: Run trial-00095 on downtrend-only → estimate downtrend ER contribution

### 3. **Win rate pattern across variants**
- V1 (normal): 28.6%
- V2 (trending): 47.8%
- V3 (crowded_leverage): 38.2%
- trial-00095 overall: ~50-55% (estimated from WF reports)

**Implication:** trial-00095's win rate comes from regime diversity (downtrend lifts win rate, normal drags down, overall balanced). Regime filtering skews win rate distribution.

---

## Audit Summary

| Dimension | Status | Notes |
|---|---|---|
| Layer Separation | ✅ PASS | Clean isolation |
| Contract Compliance | ✅ PASS | Typed configs |
| Determinism | ✅ PASS | Reproducible |
| State Integrity | ✅ PASS | Stateless |
| Error Handling | ✅ PASS | Edge cases handled |
| Smoke Coverage | ✅ PASS | 16 tests pass |
| Tech Debt | ✅ LOW | Clean code |
| AGENTS.md Compliance | ✅ PASS | Correct discipline |
| Methodology Integrity | ✅ PASS | Hypothesis properly tested |
| Implementation Quality | ✅ EXCELLENT | Consistent V1-V3 |

---

## Final Verdict: **REGIME-BASED FAMILY EXPANSION NOT VIABLE**

**Scientific assessment:** 3/3 regime variants failed (V1: ER -0.20, V2: ER 0.63, V3: ER 0.30). No regime reaches ER 1.0 independently. Regime filtering subsets existing trades rather than creating new alpha. Context-based expansion through regime specialization conclusively disproven.

**Strategic assessment:** trial-00095 is a **singular edge** (parameter-optimized, regime-agnostic), not a family of context-based edges. sweep_reclaim achieves ER 2.1 through Optuna optimization across ALL regimes, not through regime concentration.

**Implementation assessment:** Excellent work by Cascade across all 3 variants. Fast failure discipline, pattern recognition, comprehensive analysis, clean code, proper tests. Milestone executed with institutional discipline.

**Next milestone:** OPTION 1: Test Session Sweep Specialist (Asia hours, microstructure context) as final 15m test. If fails → OPTION 2: Accept singular edge, focus on live validation.

**Strategic decision required:** User (product owner) must approve next direction before proceeding.

---

**Audit complete. Milestone SWEEP-RECLAIM-FAMILY-EXPANSION-V1 verdict: REGIME-BASED EXPANSION NOT VIABLE (3/3 failures). Awaiting user approval for next milestone (Session Sweep OR accept singular edge).**
