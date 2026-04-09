# AUDIT: OPTUNA-UTILITY-V1
Date: 2026-04-09
Auditor: Claude Code
Commit: 00f205d

## Verdict: MVP_DONE

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

## Acceptance Criteria — all met
| # | Deliverable | Result |
|---|---|---|
| #0 | SignalHealthError + check_signal_health() called in run_optimize_loop | PASS |
| #1 | _to_finite_float: +inf → 1e6 (not 0.0) | PASS |
| #2 | JournalStorage + load_if_exists + --optuna-storage-path CLI | PASS |
| #3 | Warm-start via enqueue_trial, opt-in via --warm-start-from-store | PASS |
| #4 | high_vol_leverage <= max_leverage in validate_param_vector | PASS |
| #5 | multivariate_tpe flag → TPESampler(multivariate=...) | PASS |
| #6 | study.set_metric_names + trial.set_user_attr (3 attrs) | PASS |
| #7 | _compute_funnel_summary in reporter, included in report output | PASS |
| — | 72/72 tests green | PASS |
| — | Zero changes in core/, backtest/, live/, data_loader/ | PASS |
| — | Optuna storage separate from research_lab.db | PASS |

## Critical Issues
None.

## Warnings (fix soon)
- warm_start_from_store filters by protocol_hash when provided (correct), but
  falls back to ALL non-rejected trials when protocol_hash is None. Operators
  using warm-start without a fixed study_name could accidentally seed from
  campaigns with different date ranges or strategy configs. Low risk today;
  worth documenting before warm-start becomes default policy.

## Observations (non-blocking)
- load_if_exists=True only when optuna_storage_path is not None — correct
  semantics. In-memory study (no storage path) always starts fresh.
- ACTIVE count is now 45 (sweep_proximity_atr added in SWEEP-RECLAIM-FIX-V1).
  Optuna budget for Run #4 should be >= 100 trials for meaningful convergence.
- _to_finite_float now: +inf → 1e6, -inf → 0.0, nan → 0.0. The asymmetry
  (+inf = best possible, -inf = worst) is correct for all three objectives.

## Recommended Next Step
Run #4 — first clean Optuna campaign on fixed signal (SWEEP-RECLAIM-FIX-V1)
with new infrastructure (OPTUNA-UTILITY-V1). Recommended: n_trials >= 100,
study_name="sweep-reclaim-v1-run4", --optuna-storage-path set.
