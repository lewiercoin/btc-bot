# AUDIT: MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1_PLAN

**Date:** 2026-05-27  
**Auditor:** Claude Code  
**Planning Document:** [MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1_PLAN.md](c:/development/btc-bot/docs/research/MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1_PLAN.md)  
**Scope:** Meta-diagnostic planning (NOT strategy implementation)

---

## VERDICT: ✅ **APPROVE PLAN**

**Score:** 12/12 criteria PASS

This planning document is **methodologically rigorous, precisely focused, and ready for implementation approval**.

---

## Audit Against 12-Point Framework

### 1. Focus on MFE Accessibility (Not SMC Rescue)

**✅ PASS - EXCELLENT**

**Evidence:**
- Section 1: "This milestone plans a meta-diagnostic, not a strategy"
- Core question: "Where is the earliest knowable state after a sweep where the remaining MFE is still tradable after costs?"
- Section 1 explicit NOT list: "new strategy implementation, SMC rescue, V1 taxonomy rescue, mitigation-entry rescue, FeatureEngine work"
- Section 19: 15+ explicit non-goals including "SMC sequence rescue", "mitigation-entry rescue", "CHOCH/FVG/OB additions as strategy logic"

**Assessment:** This is NOT about proving SMC works. It's about reverse-engineering WHERE (if anywhere) edge becomes accessible after a sweep.

---

### 2. Event Universe Clearly Defined

**✅ PASS - EXCELLENT**

**Evidence (Section 3):**

| Universe Layer | Purpose | Scope |
|----------------|---------|-------|
| **Primary:** All reconstructed equal-level sweeps | Broadest anchor where current bot edge begins | All sweeps (with/without reclaim, shallow/deep), deduplicated |
| **Secondary:** Current bot accepted candidates | Test whether trial-00095 captures earliest accessible state | trial-00095 candidate states from replay/historical data |
| **Rejected/Near-miss:** Pre-candidate rejections | Explain whether rejected buckets had accessible MFE | sweep_too_shallow, no_reclaim, direction_unresolved, confluence_below_min |
| **V1/SMC reference:** Event overlays | Timing reference only, not primary universe | V1 taxonomy events, SMC sequence phases |

**Assessment:** Clear hierarchy. Each layer answers a different question. Primary universe is sweep-anchored (current bot foundation), not SMC-specific.

---

### 3. Inspects Accepted AND Rejected Populations

**✅ PASS - EXCELLENT**

**Evidence:**

**Section 3 Rejected Universe:**
- "Include reconstructed pre-candidate rejection states: sweep_too_shallow, no_reclaim, direction_unresolved, confluence_below_min..."

**Section 9 Rejected Population Handling:**
- Problem identified: "BacktestRunner writes accepted candidates/trades, but not full decision_outcomes for rejected sweeps"
- Plan: "Historical reconstruction via research-only replay over historical candles. Compute features and call SignalEngine.diagnose for every bar."
- "Keep sweep_too_shallow near-miss as dedicated cohort"

**Section 12 Required Cohorts:**
- `sweep_too_shallow_reject`
- `no_reclaim_reject`
- `direction_unresolved_reject`
- `confluence_below_min_reject`

**Assessment:** The plan explicitly addresses the gap that standard BacktestRunner doesn't persist rejected populations. This is critical for answering: "Did trial-00095 discard accessible edge?"

---

### 4. Defines Bar-by-Bar Knowable States

**✅ PASS - EXCELLENT**

**Evidence:**

**Section 4: Bar-By-Bar Measurement Model**
- For every sweep, evaluate `T+k` where `k` ranges from 0 through 20-32 bars
- Each row asks: "What was knowable at this bar? If entry allowed only after this bar, what happened next?"

**Section 5: Knowable States To Test (20+ states defined)**

| State Category | Examples | Timestamp Definition |
|----------------|----------|---------------------|
| **Base States** | `raw_sweep_known`, `reclaim_known`, `no_reclaim_after_n_bars` | Known at detection/reclaim/delay bar close |
| **Price-Action States** | `displacement_known`, `structure_shift_proxy_known`, `fvg_created_known` | Known at displacement/break/FVG bar close |
| **Flow/Microstructure** | `tfi_aligned_known`, `cvd_divergence_known`, `force_order_burst_known`, `force_order_decay_known` | Known after 60s bucket closed and aligned |
| **Current Bot States** | `trial_00095_candidate_known`, `current_bot_reject_reason_known` | Known when SignalEngine produces candidate/rejection |

**Assessment:** Each state has explicit "Known at X" timestamp. No vague "could be useful" — every state is deterministic and timestamped.

---

### 5. Separates detection_bar, state_known_bar, entry_candidate_bar, return_start_bar

**✅ PASS - PERFECT**

**Evidence:**

**Section 6: Timing Model**

Ordering invariants:
```
detection_bar <= state_known_bar
state_known_bar <= entry_candidate_bar
entry_candidate_bar == return_start_bar (for primary results)
label_available_bar >= state_known_bar (for delayed labels)
```

**Concrete examples:**
- Raw sweep: `detection_bar = T`, `state_known_bar = T`, `entry_candidate_bar = T+1`
- Reclaim at T+2: `state_known_bar = T+2`, `entry_candidate_bar = T+3`
- Displacement at T+1: `state_known_bar = T+1`, `entry_candidate_bar = T+2`
- No reclaim within 4 bars: `state_known_bar = T+4`, `entry_candidate_bar = T+5`

**Section 4 row schema includes all four fields:**
- `detection_bar`
- `state_known_bar`
- `entry_candidate_bar`
- `return_start_bar`

**Assessment:** This is the core timing discipline that V1 and SMC diagnostics validated. Plan enforces it rigorously.

---

### 6. Avoids Detection-Bar Lookahead Claims

**✅ PASS - EXCELLENT**

**Evidence:**

**Section 13: Lookahead And Leakage Controls**
- ❌ "No delayed state may claim returns from detection_bar"
- ✅ "Primary returns start from entry_candidate_bar"
- ⚠️ "Detection-bar returns can be shown only as audit context"
- "FVG/structure/force-order-decay delayed states must prove remaining MFE after their own known bar"

**Section 14: Invalidation Criteria**
- **STOP** if: "apparent edge exists only from detection_bar, not from state_known_bar/entry_candidate_bar"

**Section 13: Mandatory timing assertions for implementation:**
```
detection_bar <= state_known_bar <= entry_candidate_bar
return_start_bar == entry_candidate_bar
no metric used for pass/fail starts before state_known_bar
delayed state rows must fail tests if state_known_bar == detection_bar
```

**Assessment:** The plan learns from V1's critical lesson: delayed labels from detection_bar = fake edge. This is hardwired into pass/fail criteria.

---

### 7. Measures MFE Before/After Each Candidate State

**✅ PASS - EXCELLENT**

**Evidence:**

**Section 4: Required row fields**
- `mfe_before_state`
- `mae_before_state`
- `remaining_mfe_3/5/10/20`
- `mfe_consumed_pct`
- `time_to_mfe_3/5/10/20`

**Section 7: Outcome Metrics**
- "median remaining MFE"
- "median MFE consumed before state"
- "MFE-before-state versus MFE-after-state ratio"

**Section 7: MFE consumed definition:**
```
mfe_consumed_pct = mfe_from_detection_to_state / max(total_mfe_from_detection_to_horizon, epsilon)

Interpretation:
- 0.0 = no favorable move consumed before state
- 0.5 = half the favorable move is already gone
- >= 0.7 = state is probably operationally late
```

**Section 14: Invalidation**
- **STOP** if: "median mfe_consumed_pct >= 0.70 before every positive-looking state"
- **STOP** if: "MFE-before-state is greater than or equal to MFE-after-state for all viable states"

**Assessment:** This is the CORE reverse-engineering metric. The plan quantifies exactly what SMC sequence observed: most MFE consumed before mitigation entry.

---

### 8. Compares Against Trial-00095 as Benchmark, Not Religion

**✅ PASS - EXCELLENT**

**Evidence:**

**Section 8: Trial-00095 Comparison Plan**

Opening statement:
> "Trial-00095 remains benchmark, not religion."

**Three comparison methods:**

1. **Accepted-trade benchmark:** Compare against historical PF 4.66, DD 6.51%, 271 trades
2. **Candidate-state overlap:** Mark rows where current SignalEngine would generate trial-00095 candidate. Measure whether any earlier state has positive net expectancy BEFORE trial-00095 candidate.
3. **Reject-population explanation:** For current bot rejects, measure whether rejected state has accessible MFE after its own state_known_bar.

**Required conclusion categories:**
- `trial_00095_captures_accessible_edge`
- `earlier_state_outperforms_trial_00095_candidate_state`
- `rejected_bucket_has_accessible_edge`
- `no_accessible_edge_before_decay`

**Section 14: Invalidation**
- **STOP** if: "best state does not beat relevant current bot candidate-state baseline"
- **STOP** if: "best state is simply the current trial-00095 candidate state with no earlier explanatory value"

**Assessment:** The plan allows THREE outcomes:
1. Trial-00095 is optimal (captures earliest accessible state) → continue PAPER validation
2. Earlier state beats trial-00095 → consider new strategy
3. Rejected bucket has accessible edge trial-00095 missed → consider expanding gates

This is benchmark treatment, not religion. Trial-00095 can be confirmed optimal OR challenged with evidence.

---

### 9. Includes Control/Random Cohorts

**✅ PASS - GOOD**

**Evidence:**

**Section 12: Required Cohorts**
- `deterministic_shift_control`

**Section 14: Invalidation**
- **STOP** if: "best state does not beat deterministic shifted control"

**Section 16: Test Plan**
- "Control cohort test: deterministic shifted control uses only valid future windows and does not overlap original event identity"

**Minor observation:** Could add random-entry cohort (enter at random bar after sweep) alongside deterministic control. But deterministic control is standard and sufficient for detecting fake patterns.

**Assessment:** PASS. Deterministic control is rigorous and used in both V1 and SMC diagnostics.

---

### 10. Defines Hard STOP Criteria

**✅ PASS - EXCELLENT**

**Evidence:**

**Section 14: Invalidation Criteria - 5 categories, 22 STOP conditions**

**A. Timing/Accessibility Failure (6 STOP conditions):**
- No early knowable state has positive median net return after costs
- Hit rate drops to ~50% from entry_candidate_bar
- Apparent edge exists only from detection_bar
- Median `mfe_consumed_pct >= 0.70` before every positive-looking state
- MFE-before-state >= MFE-after-state for all viable states

**B. Baseline Failure (5 STOP conditions):**
- Best state does not beat all_raw_sweeps
- Best state does not beat deterministic shifted control
- Best state does not beat current bot candidate-state baseline
- Best state is simply trial-00095 with no earlier value
- Best rejected bucket does not outperform trial-00095 after costs

**C. Sample/Stability Failure (6 STOP conditions):**
- Total events < 300
- OOS/test events < 100
- Any fold < 50 events
- Fewer than 2 of 4 folds have positive net median
- State appears < 1 event/month average
- Performance concentrated in one short period

**D. Novelty Failure (2 STOP conditions):**
- State >90% overlapping with trial-00095 candidates without improvement
- State is just tfi_impulse/confluence_threshold renamed

**E. Execution Realism Failure (3 STOP conditions):**
- Signal requires unrealistic bar-close entry
- Cost/slippage sensitivity turns median net negative
- Lower-TF/intrabar assumptions required but unavailable

**Assessment:** These are HARD gates with quantified thresholds. No wiggle room for "maybe it works." Either a state passes ALL checks or diagnostic recommends STOP.

---

### 11. Leads to One Next Decision, Not Menu

**✅ PASS - EXCELLENT**

**Evidence:**

**Section 18: Possible Next Decisions**

Opening statement:
> "The diagnostic must end with **exactly one of:**"

**5 mutually exclusive decision categories:**

1. `STOP_SMC_AND_SWEEP_SOURCE_RESEARCH` → No early knowable state survives → trial-00095 PAPER validation continues
2. `TRIAL_00095_CAPTURES_ACCESSIBLE_EDGE` → Current bot already enters at earliest viable point → Continue PAPER, do not add complexity
3. `PLAN_ONE_STRATEGY_FAMILY_DIAGNOSTIC` → Exactly ONE state shows timing-correct expectancy → Write new audited plan around that state ONLY
4. `ORDER_FLOW_LIQUIDATION_AFTER_SWEEP_IS_CANDIDATE` → Flow/force-order/OI states explain accessible MFE → Plan order-flow diagnostic (NOT SMC)
5. `INCONCLUSIVE_DATA_GAP` → Need better rejected population or 5m/1m data

**Assessment:** This is categorical exhaustiveness, NOT a menu of options. The diagnostic ends with ONE category, which leads to ONE next action. No "here are 5 ideas, pick one."

---

### 12. Small Enough for Research-Only Implementation

**✅ PASS - GOOD**

**Evidence:**

**Section 11: Proposed Research Script Shape**
- Single script: `research_lab/analysis_mfe_accessibility_earliest_knowable_signal_v1.py`
- Outputs: JSON + Markdown report
- No live services, no exchange API, no production DB writes

**Section 17: Deliverables**
- Research-only script under `research_lab/`
- Focused pytest under `tests/`
- JSON output under `research_lab/analysis_output/`
- Markdown report under `docs/analysis/`

**Section 19: Explicit Non-Goals (15+ items prevent scope creep):**
- ❌ Production code
- ❌ FeatureEngine facts
- ❌ SignalEngine entries
- ❌ Governance/Risk changes
- ❌ DB schema migrations
- ❌ Live service queries
- ❌ Lower-timeframe execution model
- ❌ Pine/TradingView porting

**Section 11: High-level flow (10 steps, all deterministic):**
1. Load historical candles + flow/funding/OI/force-orders
2. Validate data quality
3. Reconstruct all equal-level sweep events
4. Reconstruct current bot diagnostic state per bar
5. For each sweep and each k, build known-state row
6. Compute entry-timed forward returns, MAE, MFE, time-to-MFE, MFE consumed
7. Aggregate by state, k, direction, reject reason, depth bucket, trial-00095 overlap
8. Produce deterministic control rows
9. Produce invalidation verdict
10. Write JSON and Markdown report

**Assessment:** Scope is well-defined and bounded. Reasonable 1-2 week implementation estimate. All work stays in `research_lab/` with no production contamination.

---

## Overall Assessment

### Strengths

**1. Methodological Rigor**

The plan enforces the timing discipline learned from V1 and SMC:
- No detection-bar lookahead
- All states timestamped by knowability
- Primary returns from entry_candidate_bar only
- Mandatory timing assertions in implementation

**2. Precisely Focused Question**

NOT: "Can we make SMC work?"  
NOT: "What other patterns should we try?"  

YES: "Where (if anywhere) does the edge become accessible after a sweep, and how much MFE remains at that point?"

**3. Comprehensive Event Universe**

- Accepted trades (trial-00095 candidates)
- Rejected populations (sweep_too_shallow, no_reclaim, etc.)
- All raw sweeps (broadest anchor)
- V1/SMC reference overlays (timing markers)

Addresses the critical gap: standard BacktestRunner doesn't persist rejects.

**4. Hard Invalidation Gates**

22 STOP criteria across 5 categories. No soft passes. Either a state survives ALL checks (timing, cost, control, baseline, sample, novelty, execution) or diagnostic recommends STOP.

**5. Trial-00095 Treatment**

"Benchmark, not religion." Three comparison methods allow THREE outcomes:
- Trial-00095 is optimal → confirm and continue
- Earlier state beats trial-00095 → challenge with evidence
- Rejected bucket has edge → expand gates

**6. Decisive Output**

Ends with EXACTLY ONE of 5 mutually exclusive categories, each leading to ONE next action. No menus, no "further research needed on 10 ideas."

**7. MFE Accessibility Core**

The plan quantifies the SMC failure mode:
- `mfe_consumed_pct` formula
- MFE-before vs MFE-after ratio
- >= 0.70 consumed = operationally late
- STOP if all viable states have MFE-before >= MFE-after

This is TRUE reverse quant engineering: not "does pattern X exist?" but "is pattern X knowable early enough?"

---

### Minor Observations (Not Blockers)

**1. Random-Entry Cohort**

Could add random-entry cohort (enter at random bar after sweep) alongside deterministic control. But deterministic control is standard and sufficient.

**2. Data Staleness**

Plan uses same DB as SMC (`crowded_unwind_backtest.db`, ends 2026-03-28, 59 days stale). This is acceptable for invalidation testing. If a state PASSES, THEN rerun on fresh data before production.

Could explicitly state: "If PASS verdict, rerun on fresh data" in Section 18 decision categories.

**3. Cost Sensitivity**

Section 7 recommends cost sensitivity at 0.06%, 0.10%, 0.15%, 0.20%. Good. Could add: "If state passes at 0.10% but fails at 0.15%, mark as FRAGILE."

These are enhancements, not requirements. Plan is APPROVE-ready as written.

---

## Critical Issues: NONE

All 12 criteria PASS. No methodology violations. No scope creep. No lookahead traps.

---

## Warnings: NONE

---

## Required Changes: NONE

Plan is complete and ready for implementation approval.

---

## Recommended Next Steps

**If user approves implementation:**

1. **Codex implements diagnostic** (estimated 1-2 weeks)
   - `research_lab/analysis_mfe_accessibility_earliest_knowable_signal_v1.py`
   - `tests/test_research_lab_mfe_accessibility_earliest_knowable_signal_v1.py`
   - Outputs: JSON + Markdown report

2. **Claude Code audits implementation** against this planning document
   - Verify timing model enforced
   - Verify lookahead controls implemented
   - Verify all required cohorts present
   - Verify hard STOP criteria evaluated

3. **Codex runs diagnostic on historical data**
   - `research_lab/data/crowded_unwind_backtest.db`
   - BTCUSDT 15m, 2020-09-01 to 2026-03-28

4. **Claude Code audits results** against Section 14 invalidation criteria
   - Does any state survive all gates?
   - If yes: which one, and what's the timing?
   - If no: is it accessibility failure or baseline failure?

5. **Decision (exactly ONE of):**
   - STOP SMC research → trial-00095 PAPER validation only
   - Trial-00095 optimal → continue PAPER, no new strategy
   - Plan ONE strategy around viable state
   - Order-flow/liquidation is candidate → plan separate diagnostic
   - Inconclusive → need better data

---

## Audit Signature

**Auditor:** Claude Code  
**Date:** 2026-05-27  
**Verdict:** ✅ **APPROVE PLAN**  
**Score:** 12/12 criteria PASS  
**Critical issues:** None  
**Required changes:** None  
**Recommendation:** Approve for implementation if user approves

---

## Final Assessment

This planning document represents **exactly the kind of rigorous, focused, reverse-engineering research** that should follow the V1 and SMC invalidations.

**It does NOT ask:** "Can we make SMC work with more features?"

**It asks:** "Where does the edge become accessible, if anywhere? And is trial-00095 already capturing it?"

**The most likely outcome:** Trial-00095 already captures the earliest accessible state (sweep+reclaim+TFI at 1-2 bars), and later confirmations (mitigation at 8 bars) consume the move.

**If that's the finding:** STOP SMC research. Trial-00095 is optimal. Continue PAPER validation.

**If an earlier flow/liquidation state is found:** Plan ONE diagnostic around that state. NOT a menu of SMC patterns.

**This is how research should work:** test hypotheses to failure, learn where accessibility boundaries are, make decisive recommendations.

---

**APPROVE PLAN. Ready for implementation approval if user approves.**
