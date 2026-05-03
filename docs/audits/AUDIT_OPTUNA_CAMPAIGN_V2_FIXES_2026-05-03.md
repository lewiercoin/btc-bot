# AUDIT: OPTUNA-CAMPAIGN-V2-FIXES
Date: 2026-05-03
Auditor: Claude Code
Commit: 6c8ec66 (fix: harden optuna campaign artifacts)
Builder: Codex

## Verdict: DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: PASS
## Error Handling: PASS
## Smoke Coverage: PASS
## Tech Debt: LOW
## AGENTS.md Compliance: PASS
## Methodology Integrity: PASS
## Promotion Safety: PASS
## Reproducibility & Lineage: PASS
## Data Isolation: PASS
## Search Space Governance: PASS
## Artifact Consistency: PASS
## Boundary Coupling: PASS

---

## Audit Summary

4 targeted changes to harden Optuna campaign architecture against the artifact patterns
identified in OPTUNA-DEFAULT-V1 (WR=96-99%, PF=351B). All changes implemented correctly
with dedicated test coverage. 303 tests pass, no regressions. 3 new tests added.

---

## Change 1 — Hard artifact block in objective() — PASS

**File:** `research_lab/integrations/optuna_driver.py`

Checks raw `evaluation.metrics.win_rate > 0.85` and `evaluation.metrics.profit_factor > 50.0`
BEFORE any capping. Returns `(-2.0, 0.1, 1.0)` and sets `constraint_violations = [1.0]`.

Critical distinction correctly implemented: the check uses `evaluation.metrics.profit_factor`
(raw backtest value, e.g. 351B) not the local `pf` variable (already capped to 5.0 by
`_to_finite_float`). Without this, the block would never fire.

TPE effect: `constraint_violations = [1.0]` is consumed by `_constraints_func` which feeds
the TPE `constraints_func` parameter. TPE learns the artifact region is infeasible and
actively avoids it in future trials — not just penalizes it.

**Test:** `test_run_optuna_study_hard_blocks_artifact_metrics` — injects WR=0.96, PF=351B,
asserts return `(-2.0, 0.1, 1.0)`, verifies `rejection_reason` string and that raw PF
is preserved in saved trial. PASS.

---

## Change 2 — Joint sampling for high_vol_leverage — PASS

**File:** `research_lab/integrations/optuna_driver.py`

Reorders `active_items` so `max_leverage` is sampled immediately before `high_vol_leverage`:

```python
active_items = sorted(...)
active_names = [name for name, _ in active_items]
if "max_leverage" in active_names and "high_vol_leverage" in active_names:
    max_item = active_items.pop(active_names.index("max_leverage"))
    high_vol_index = [name for name, _ in active_items].index("high_vol_leverage")
    active_items.insert(high_vol_index, max_item)
```

Pop-then-reinsert logic is correct: `active_names` holds original sorted indices (used
only for the pop), `high_vol_index` is computed on the post-pop list (correct position).
The `high_vol_leverage` handler uses `sampled.get("max_leverage", int(spec.high))` with
safe fallback — handles edge case where max_leverage is frozen/inactive.

**Test:** `test_optuna_sampling_caps_high_vol_leverage_to_sampled_max_leverage` — injects
`max_leverage=4`, asserts suggestion order `["max_leverage", "high_vol_leverage"]` and
that high_vol_leverage is suggested with `high=4`. PASS.

---

## Change 3 — Sum-of-weights constraint — PASS

**File:** `research_lab/constraints.py`

```python
present_weights = [params.get(w) for w in _SIGNAL_WEIGHT_PARAMS if params.get(w) is not None]
if present_weights and sum(float(w) for w in present_weights) < 0.5:
    violations.append("sum of signal weights must be >= 0.5 ...")
```

`is not None` check correctly includes `0.0` values (which are falsy but valid).
`if present_weights` guard prevents false firing when no weight params are in the vector
(e.g. unit test with partial param set).

`_SIGNAL_WEIGHT_PARAMS` defined at module level — clean, consistent with file style.

**Test:** `test_constraints_rejects_degenerate_signal_weight_sum` — all 7 weights at 0.05
(sum=0.35 < 0.5), asserts violation message present. PASS.

---

## Change 4 — Parameter range narrowing — PASS

**File:** `research_lab/param_registry.py`

| Parameter | Old high | New high | Rationale |
|---|---|---|---|
| `invalidation_offset_atr` | 5.0 | 3.0 | Eliminates ultra-wide stop region |
| `max_hold_hours` | 72 | 48 | Eliminates ultra-long hold region |

Exact values as specified. No other ranges touched.

---

## Smoke Coverage — PASS

Codex added 3 dedicated tests covering all 3 code-level changes:
- `test_run_optuna_study_hard_blocks_artifact_metrics`
- `test_constraints_rejects_degenerate_signal_weight_sum`
- `test_optuna_sampling_caps_high_vol_leverage_to_sampled_max_leverage`

Full suite: 303 passed, 24 skipped. Research lab smoke: 34 passed, 2 skipped.

Note: `tests\smoke\` path not found on Windows (Codex's environment) — pre-existing
environment issue, not introduced by this commit. Research lab tests used as equivalent.

---

## Observations

- Multi-objective (3 directions: maximize ER, maximize PF, minimize MDD) was already
  implemented in the previous campaign. No change needed there.
- The existing soft anti-overfitting guard (PF capped at 5.0, overfit_penalty for PF>3.0)
  remains in place and complements the new hard block.
- Warm-start from WF winners not included — WF still running. Deferred to campaign 2
  launch, where WF winners can be seeded as the top warm-start candidates.
- CMA-ES sampler deferred to campaign 3 (experiment). Correct scope discipline.

---

## Campaign 2 Readiness Checklist

Before launching campaign 2, confirm:
- [ ] WF results available → use WF PASS trials as warm-start seeds
- [ ] New study_name (e.g. `optuna-default-v2`) to prevent Optuna storage contamination
- [ ] n_trials: 300-400
- [ ] seed: new seed (e.g. 43) or same 42 — document choice
- [ ] Confirm `weight_force_order_spike` remains FROZEN (pending Boon Chuan Lim response)

---

## Tracked Debt

| ID | Description | Priority | Status |
|---|---|---|---|
| D6 | 35-param active search space — high trial failure rate | MEDIUM | PARTIALLY MITIGATED: sum-of-weights constraint reduces zero-trade rate; joint sampling reduces constraint violation rate |
| D7 | WF protocol gates too loose for artifact detection | MEDIUM | CLOSED — hard filter in objective makes artifact detection moot for campaign 2 |
| D13 | Warm-start from WF winners not yet wired | LOW | OPEN — add before campaign 2 launch |
