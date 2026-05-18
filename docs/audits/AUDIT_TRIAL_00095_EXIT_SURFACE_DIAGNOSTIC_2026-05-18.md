# AUDIT: TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_V1

Date: 2026-05-18
Auditor: Claude Code
Commit: 9f88e3a
Branch: research/sweep-family-expansion-v1
Builder: Codex
Milestone: TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_V1

## Verdict: PASS

Milestone approved for closure with builder verdict **HYPOTHESIS_FOR_FUTURE_VALIDATION**. Do not promote exit changes to runtime. Distribution diagnostic correctly identifies loss-clipping sensitivity, but cannot approve executable exit policy without full intrabar replay validation.

---

## Assessment

Implementation is methodologically sound and correctly scoped as distribution clipping diagnostic (not executable exit evidence). Limitations clearly stated in hypothesis card, report, and documentation.

### 1. Scope & Layer Separation: PASS

**Files changed (commit 9f88e3a):**
- ✓ `docs/DECISIONS_LOG.md` - decision recorded
- ✓ `docs/MILESTONE_TRACKER.md` - milestone status
- ✓ `docs/analysis/TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_2026-05-18.md` - report
- ✓ `research_lab/analysis_trial_00095_exit_surface_diagnostic.py` - diagnostic runner
- ✓ `research_lab/hypotheses/active/trial_00095_exit_surface_diagnostic.json` - hypothesis card
- ✓ `tests/test_research_lab_exit_surface_diagnostic.py` - tests

**No forbidden files modified:**
```
$ git diff --name-only 9f88e3a^..9f88e3a | grep -E "^(core/|orchestrator\.py|settings\.py|execution/|main\.py)"
No forbidden files modified
```

**Layer boundary respected:**
- No imports from core/, orchestrator, settings, execution
- No production/PAPER/LIVE behavior changes
- Pure research_lab/ + docs/ + tests/ scope
- Correct builder discipline

### 2. Methodology Integrity: PASS

**Hypothesis card limitations (trial_00095_exit_surface_diagnostic.json):**

✓ **Line 66:** "This V1 uses existing realized-R trade artifacts and is not a full intrabar exit replay."

✓ **Line 67:** "Winner and loser clipping are diagnostic transformations, not executable exit policies."

✓ **Line 69:** "At most a hypothesis_for_future_validation verdict is allowed; no promotion-ready verdict."

✓ **Frozen assumptions explicit** (line 60-69):
- "Entry population is frozen by replaying trial-00095 exact params"
- "No signal thresholds, entry filters, regime eligibility, governance, or risk gates may change"
- "Baseline control must be reported beside every diagnostic variant"
- "MAE/MFE are diagnostics only and cannot approve a variant post hoc"

✓ **Out of scope explicit** (line 96-102):
- Changing entry logic
- Changing trial-00095 params in settings.py
- Runtime, PAPER, or LIVE deployment
- Approval bundle generation

**Report methodology statement (line 7):**

✓ "Methodology limit: this first diagnostic uses the existing `trial_00095_trades.json` realized-R artifact. It is a distribution clipping study, not a full intrabar exit replay. It can identify whether simple winner/loser clipping is worth future validation, but it cannot approve an exit policy."

**Builder interpretation (report line 30):**

✓ "This diagnostic cannot produce a promotion-ready verdict."

**DECISIONS_LOG.md (commit 9f88e3a):**

✓ "Do not promote exit changes from this diagnostic. A future milestone would need full frozen-entry intrabar replay with adverse-first fills, exact entry/stop/TP reconstruction, cost stress, and audit."

**MILESTONE_TRACKER.md (commit 9f88e3a):**

✓ "Methodology limit: V1 is a distribution-clipping diagnostic... not a full intrabar exit replay. It can propose a future validation hypothesis, but it cannot approve an exit policy."

✓ "not deployable evidence"

**Assessment:** Limitations are clearly, consistently, and repeatedly stated across all artifacts. Methodology integrity is excellent.

### 3. Baseline Control & Frozen Entries: PASS

**Baseline control variant (line 174 of runner):**

```python
items = [ExitVariant("BASELINE_CONTROL", "baseline")]
```

First variant is baseline control, ensuring frozen entries are preserved.

**Baseline control simulation (line 185-186):**

```python
if variant.family == "baseline":
    return ExitTrade(entry, variant.variant_id, entry.baseline_pnl_r, entry.baseline_exit_reason, 0, 0)
```

Returns exact baseline PNL and exit reason. No modifications.

**Frozen entry loading (line 360-379):**

Uses existing `trial_00095_trades.json` artifact, loads frozen baseline_pnl_r values. Entry population is immutable across all variants.

**Test verification (test_research_lab_exit_surface_diagnostic.py line 56-64):**

```python
def test_baseline_control_keeps_frozen_entry_population_and_pnl():
    entries = [_entry("LONG"), _entry("SHORT")]
    trades = [simulate_variant(entry, [], ExitVariant("BASELINE_CONTROL", "baseline")) for entry in entries]
    metrics = compute_metrics(trades, trades)
    
    assert metrics["trade_count"] == 2
    assert metrics["entry_count_match"] == 1.0
    assert metrics["delta_er"] == 0.0
```

Verifies:
- Trade count unchanged
- Entry count match = 1.0 (100% match)
- Delta ER = 0.0 (no change from baseline)

**Assessment:** Baseline control correctly preserves frozen entry population and PNL.

### 4. Distribution Clipping Methodology: PASS

**Implementation (line 187-197):**

✓ **Win cap (line 187-189):**
```python
if variant.family == "win_cap":
    pnl = min(entry.baseline_pnl_r, variant.target_r or entry.baseline_pnl_r)
    return ExitTrade(entry, variant.variant_id, pnl, "win_cap" if pnl != entry.baseline_pnl_r else entry.baseline_exit_reason, 0, 0)
```

Clips winners at target_r. Does not replay intrabar mechanics.

✓ **Loss cap (line 190-193):**
```python
if variant.family == "loss_cap":
    cap = -(variant.target_r or 1.5)
    pnl = max(entry.baseline_pnl_r, cap)
    return ExitTrade(entry, variant.variant_id, pnl, "loss_cap" if pnl != entry.baseline_pnl_r else entry.baseline_exit_reason, 0, 0)
```

Clips losses at -target_r. Does not replay intrabar mechanics.

✓ **Symmetric cap (line 194-197):**
```python
if variant.family == "symmetric_cap":
    cap = variant.target_r or 2.5
    pnl = min(max(entry.baseline_pnl_r, -1.5), cap)
    return ExitTrade(entry, variant.variant_id, pnl, "symmetric_cap" if pnl != entry.baseline_pnl_r else entry.baseline_exit_reason, 0, 0)
```

Clips both winners and losers. Does not replay intrabar mechanics.

**What this methodology CAN do:**
- Test sensitivity to distribution shape (fat-tail vs truncated)
- Identify whether edge is winner-driven or loser-driven
- Propose directional hypotheses for future validation

**What this methodology CANNOT do:**
- Approve executable exit logic (no intrabar path simulation)
- Determine optimal exit timing (uses frozen realized outcomes)
- Validate stop/target placement (no reconstruction of actual fills)

**Assessment:** Methodology correctly implements distribution clipping and does not overreach into executable exit validation.

### 5. Result Interpretation: PASS

**Best variant (report line 29):**
- LOSS_CAP_1.00R
- Trades: 274
- ER: 2.346 (baseline 2.121, delta +0.225, +10.6%)
- PF: 6.40 (baseline 4.22)
- DD ratio: 0.68 (vs baseline 1.00, improvement)
- Folds+: 9 (of 9, all folds positive)
- 2x cost ER: 2.064 (> 1.0, passes cost stress)
- Top trade delta share: 1.2% (< 35%, not outlier-driven)

**Gates assessment:**
- ✓ min_delta_er_pct: +10.6% > 10% (PASS)
- ✓ min_pf_ratio_vs_baseline: 6.40/4.22 = 1.52 > 1.0 (PASS)
- ✓ max_dd_ratio_vs_baseline: 0.68 < 1.0 (PASS, improvement)
- ✓ min_folds_delta_er_positive: 9 > 3 (PASS)
- ✓ max_top_trade_delta_share: 1.2% < 35% (PASS, not outlier-driven)
- ✓ min_er_at_2x_cost: 2.064 > 1.0 (PASS, cost-robust)

**Winner cap results (report line 20-25):**
- WIN_CAP_3.0R: ER 0.987 (delta -1.134, -53.5%)
- WIN_CAP_2.5R: ER 0.746 (delta -1.375, -64.8%)
- WIN_CAP_2.0R: ER 0.472 (delta -1.649, -77.8%)
- WIN_CAP_1.5R: ER 0.189 (delta -1.932, -91.1%)

Winner caps destroy expectancy. Edge is winner-driven, do not cap winners.

**Interpretation:**
1. **LOSS_CAP_1.00R passes all gates** → loss-clipping sensitivity detected
2. **Winner caps fail catastrophically** → edge requires full winner tail
3. **Fold-stable** → 9/9 folds positive, not in-sample overfit
4. **Cost-robust** → ER 2.064 at 2x cost, edge survives stress
5. **Not outlier-driven** → top trade delta share 1.2%, distributed improvement

**Builder verdict: HYPOTHESIS_FOR_FUTURE_VALIDATION**

✓ Correct. This diagnostic suggests tighter loss control around -1R is worth investigating, but cannot approve runtime changes without full intrabar replay validation.

**Assessment:** Result interpretation is sound and appropriately conservative.

### 6. Tests: PASS

**Test results (per user):**
```
18 passed
compileall clean
```

**Critical tests present:**
1. `test_adverse_first_intrabar_conflict_uses_stop_before_target` (line 45-53) - verifies intrabar conflicts handled adverse-first
2. `test_baseline_control_keeps_frozen_entry_population_and_pnl` (line 56-64) - verifies baseline control preserves entries and PNL
3. `test_exit_surface_hypothesis_spec_is_valid` (line 66-71) - verifies hypothesis card loads correctly

**Coverage assessment:**
- ✓ Baseline control tested (entry count match, delta ER = 0)
- ✓ Adverse-first intrabar handling tested (stop before target in ambiguous bar)
- ✓ Hypothesis spec validation tested
- ✓ No missing critical tests identified

**Assessment:** Tests adequate for distribution diagnostic scope.

---

## Summary

| Aspect | Status | Notes |
|---|---|---|
| Scope / layer separation | ✓ PASS | Research-only, no runtime/core/orchestrator/settings/execution changes |
| Methodology integrity | ✓ PASS | Limitations clearly, consistently, repeatedly stated across all artifacts |
| Baseline control | ✓ PASS | Preserves frozen entry population, delta ER = 0, entry count match = 1.0 |
| Distribution clipping | ✓ PASS | Correctly implements clipping, does not overreach into executable exit validation |
| Result interpretation | ✓ PASS | HYPOTHESIS_FOR_FUTURE_VALIDATION correct, loss-clipping sensitivity detected, winner caps fail |
| Tests | ✓ PASS | 18/18 passed, adverse-first tested, baseline control tested, compileall clean |

**Final result:**
- Best diagnostic: LOSS_CAP_1.00R
- ER: 2.121 → 2.346 (+10.6%)
- PF: 4.22 → 6.40
- DD ratio: 0.68 (improvement)
- Folds+: 9/9 (all positive)
- 2x cost ER: 2.064 (cost-robust)
- Verdict: HYPOTHESIS_FOR_FUTURE_VALIDATION

**Implication:** Trial-00095 appears sensitive to loss clipping near -1R. This is a directional finding suggesting tighter loss control is worth investigating, but is not deployable evidence. Next step (if pursued) requires full frozen-entry intrabar replay with adverse-first fills, exact stop/TP reconstruction, cost stress, and audit.

**Do not promote exit changes to runtime from this diagnostic.**

---

## Critical Issues

None.

## Warnings

None.

## Observations

### Winner Caps Destroy Expectancy

All winner cap variants (WIN_CAP_3.0R, 2.5R, 2.0R, 1.5R) show catastrophic expectancy degradation:
- WIN_CAP_3.0R: ER 0.987 (delta -53.5%)
- WIN_CAP_1.5R: ER 0.189 (delta -91.1%)

This confirms trial-00095 edge is winner-driven. Full winner tail is required for positive expectancy. Do not cap winners.

### Loss-Clipping Sensitivity Detected

LOSS_CAP_1.00R passes all gates with +10.6% ER improvement, fold-stable (9/9), cost-robust (2.064 at 2x), not outlier-driven (1.2% top trade share).

This suggests tighter loss control around -1R is worth future validation, but this diagnostic cannot approve executable exit logic.

### Symmetric Caps Fail

SYMMETRIC_CAP variants (cap both winners and losers) all show negative expectancy:
- SYMMETRIC_CAP_3.0R: ER 1.006 (delta -52.6%)
- SYMMETRIC_CAP_2.0R: ER 0.491 (delta -76.9%)

Winner cap component dominates, destroying edge despite loss-cap benefit.

### Methodology Discipline

Builder correctly labels this as distribution clipping diagnostic throughout:
- Hypothesis card: "not a full intrabar exit replay"
- Report: "cannot approve an exit policy"
- DECISIONS_LOG: "do not promote exit changes from this diagnostic"
- MILESTONE_TRACKER: "not deployable evidence"

Excellent methodology discipline and limitation awareness.

---

## Recommended Next Step

**APPROVE milestone closure with HYPOTHESIS_FOR_FUTURE_VALIDATION verdict.**

Trial-00095 exit surface diagnostic is complete. Loss-clipping sensitivity detected at -1R (+10.6% ER, fold-stable, cost-robust). Winner caps destroy expectancy. Do not promote to runtime.

**If loss-control hypothesis is pursued later:**
1. Create new milestone: TRIAL_00095_LOSS_CONTROL_VALIDATION_V1
2. Scope: full frozen-entry intrabar replay with adverse-first fills
3. Reconstruct exact entry, stop, TP from trial-00095 params
4. Test tighter stop variants (stop 0.75x, 0.85x, 0.90x baseline) or early loss-cap exits
5. Walk-forward validation, cost stress, audit
6. Only then: consider promotion if passes gates

**Current milestone:** Close as diagnostic complete, hypothesis for future validation identified.

**Strategic context:** This is the first attempt to investigate whether trial-00095 entry edge is under-monetized by exits. Finding is directional (loss-clipping beneficial, winner-caps harmful) but not executable without intrabar replay validation.

---

**Audit status:** DONE
**Milestone verdict:** HYPOTHESIS_FOR_FUTURE_VALIDATION (builder verdict confirmed)
**Deployment verdict:** N/A (research-only, no promotion)
**Close milestone:** YES
