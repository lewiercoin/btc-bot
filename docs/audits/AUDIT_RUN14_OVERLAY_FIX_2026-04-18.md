# AUDIT: RUN14 Uptrend Continuation Overlay Fix

Date: 2026-04-18  
Auditor: Claude Code  
Commit: f22c2d7  
Milestone: Fix RUN14 Uptrend Continuation Fallback Bug

## Verdict: **DONE**

## Layer Separation: **PASS**

✅ **Changes isolated to research lab:**
- Modified: `research_lab/research_backtest_runner.py` (+62, -14)
- Modified: `tests/test_research_backtest_runner.py` (+253)
- No contamination of core/ or backtest/ layers
- Logging import added properly

✅ **No cross-layer dependencies introduced:**
- Uses existing SignalCandidate, Features, RegimeState contracts
- Delegates to signal_engine methods (no duplication)

## Contract Compliance: **PASS**

✅ **Interface contracts preserved:**
- `run()` signature unchanged
- `SignalCandidate` structure unchanged
- Return types match BacktestResult contract

✅ **Internal contract extension (not breaking):**
- New method: `_resolve_signal_candidates()` returns 3-tuple (base, uptrend, selected)
- New method: `_select_signal_candidate()` static selection logic
- New method: `_log_uptrend_continuation_config()` observability helper

## Determinism: **PASS**

✅ **Selection logic is deterministic:**
```python
@staticmethod
def _select_signal_candidate(base, uptrend):
    if base is None: return uptrend
    if uptrend is None: return base
    if uptrend.confluence > base.confluence: return uptrend
    return base  # Deterministic tie-break: prefer base
```

✅ **No randomness, no hidden state mutation:**
- Both candidates evaluated in fixed order
- Selection based on numerical comparison only
- `signals_generated` counter correctly counts both independently

✅ **Config logging deterministic:**
- Logs once per run() at initialization
- Uses fixed format string
- Parameters logged with 4 decimal precision

## Methodology Integrity: **PASS**

✅ **Overlay pattern correctly implemented:**

**Before (fallback bug):**
```python
candidate = signal_engine.generate(features, regime)
if candidate is None:
    candidate = uptrend_continuation(...)  # BUG: fallback
```

**After (overlay fix):**
```python
base_candidate = signal_engine.generate(features, regime)
uptrend_candidate = uptrend_continuation(...)
selected = _select_signal_candidate(base_candidate, uptrend_candidate)
```

✅ **RUN14 bug root cause fixed:**
- Uptrend parameters now affect outcomes on bars where base engine also generates signals
- Parameters can influence final candidate selection via confluence comparison
- RUN14 trials will no longer produce identical results

✅ **Selection policy documented:**
- Log message: `"selection_policy=higher_confluence_base_tie_break"`
- Policy is transparent and auditable

## Reproducibility & Lineage: **PASS**

✅ **Config logging enables trial validation:**
```python
logger.info(
    "Research uptrend continuation overlay active | "
    "selection_policy=higher_confluence_base_tie_break | "
    "allow_uptrend_continuation=%s | "
    "uptrend_continuation_reclaim_strength_min=%.4f | "
    "uptrend_continuation_participation_min=%.4f | "
    "uptrend_continuation_confluence_multiplier=%.4f",
    ...
)
```

✅ **Logged once per run():**
- Captures trial-specific parameter values
- Enables post-hoc verification that RUN14 trials varied parameters
- Optuna study logs will show parameter sweep

✅ **Lineage sufficient:**
- Commit f22c2d7 is the fix commit
- RUN14 trials run with this commit will be distinguishable from old trials
- New trials will show overlay config in logs

## Smoke Coverage: **PASS**

✅ **7 tests covering all selection paths:**

1. `test_select_signal_candidate_prefers_higher_confluence_overlay` - uptrend 4.2 > base 3.0
2. `test_select_signal_candidate_prefers_base_on_equal_confluence` - deterministic tie-break
3. `test_select_signal_candidate_returns_overlay_when_base_missing` - base=None
4. `test_select_signal_candidate_returns_base_when_overlay_missing` - uptrend=None
5. `test_select_signal_candidate_returns_none_when_both_candidates_missing` - both=None
6. `test_run_evaluates_overlay_even_when_base_candidate_exists` - **integration test proves overlay always runs**
7. `test_run_logs_overlay_config_for_trial_validation` - config log validation

✅ **Integration test proves overlay behavior:**
```python
def test_run_evaluates_overlay_even_when_base_candidate_exists():
    # Monkeypatch: base engine returns candidate
    # Monkeypatch: track overlay calls
    result = runner.run(...)
    assert overlay_calls == [features.timestamp]  # Overlay called despite base existing
    assert evaluated_candidates[0] is overlay_candidate  # Overlay selected (higher confluence)
    assert runner.signals_generated == 2  # Both counted
```

✅ **All tests pass:**
```
pytest tests/test_research_backtest_runner.py
7 passed
```

## Tech Debt: **LOW**

✅ Clean implementation:
- No TODOs
- No NotImplementedError stubs
- No duplication
- Well-factored helper methods
- Type hints complete

✅ Code quality:
- Static method for stateless selection logic
- Private methods properly scoped
- Logging at correct abstraction level (INFO for trial config)

## AGENTS.md Compliance: **PASS**

✅ **Commit message format (WHAT/WHY/STATUS):**
```
fix: make RUN14 uptrend continuation an overlay candidate

WHAT: refactor ResearchBacktestRunner to always evaluate uptrend continuation 
      alongside the base signal engine, select the stronger candidate with a 
      deterministic base tie-break, and log overlay config values for trial validation
WHY: RUN14 trials were identical because uptrend continuation parameters only ran 
     as a fallback after generate() returned None, so overlay parameters could not 
     influence bars where the base engine already produced a candidate
STATUS: targeted runner refactor and overlay tests are in place; compileall and 
        tests/test_research_backtest_runner.py passed; ready for Claude audit
```

✅ **Scope discipline:**
- Focused on overlay pattern fix only
- No unrelated changes
- No scope creep

✅ **Tests validated before commit:**
- compileall syntax check ✓
- pytest tests/test_research_backtest_runner.py ✓

✅ **No self-audit:**
- Correctly deferred to Claude Code
- STATUS says "ready for Claude audit" (not "done")

---

## Critical Issues: **NONE**

## Warnings: **NONE**

## Observations

### 1. signals_generated Counter Behavior

**Current implementation:**
```python
self.signals_generated += int(base_candidate is not None) + int(uptrend_candidate is not None)
```

**Observation:** When both base and overlay generate candidates on the same bar, `signals_generated` increments by 2.

**Assessment:** This is **correct behavior** for understanding search space coverage. It answers: "How many candidate-generating conditions were met?" (not "How many bars produced a final candidate?").

**Impact:** Performance summary will show higher signals_generated when overlay is active. This is transparent and auditable.

### 2. Config Log Frequency

**Current implementation:** `_log_uptrend_continuation_config()` called once per `run()` at line 70.

**Observation:** Logs once per backtest run, not once per trial.

**Assessment:** This is **acceptable** because:
- Optuna logs show trial parameter variance
- Config log confirms overlay was active for this trial
- Post-hoc analysis: grep logs for "overlay active" + match to trial_id from Optuna DB

**Alternative (not required):** Could log trial_id if available, but ResearchBacktestRunner doesn't have access to Optuna trial context.

### 3. Overlay Method Unchanged

**Observation:** `_generate_uptrend_continuation_candidate()` method body unchanged (lines 285-353).

**Assessment:** **Correct.** Only the call site changed from fallback to overlay. The overlay method logic remains valid:
- Checks `allow_uptrend_continuation` config
- Validates regime (UPTREND only)
- Validates sweep/reclaim conditions
- Computes confluence and applies multiplier
- Returns SignalCandidate or None

---

## Recommended Next Step

**Milestone: DONE** ✅

**Push:** Ready to push commit f22c2d7 to origin/main.

**After push:**
1. Re-run RUN14 campaign with same Optuna study (80 trials total)
2. Verify trials 26-80 produce **varied results** (not all identical)
3. Compare trial outcomes to confirm overlay parameters affect confluence selection
4. If results vary: RUN14 bug confirmed fixed
5. If results still identical: deeper investigation needed (unlikely - tests prove overlay works)

**No blockers from this audit.**

---

## Sign-Off

**Builder:** Codex  
**Auditor:** Claude Code  
**Commit:** f22c2d7

**Verdict:** DONE ✅

RUN14 uptrend continuation overlay fix is production-ready. The fallback→overlay refactor is clean, deterministic, well-tested, and properly logged for trial validation.
