# Research Lab Blueprint v1.0

## Goal & Non-Goals

Research Lab is the offline optimization system for the BTC bot.

Its goals are:
- run deterministic offline parameter searches against historical data
- evaluate candidate parameter sets with explicit audit artifacts
- preserve strict separation from the live trading path
- support human review before any candidate can influence production settings

Research Lab explicitly does NOT:
- auto-promote candidates into `settings.py`
- mutate live execution, orchestration, or runtime state
- place orders or participate in the live decision loop
- hide methodology changes inside bugfix milestones
- claim nested optimization when the workflow is still post-hoc walk-forward validation

## System Boundary

Research Lab is offline-only.

Allowed dependencies:
- `backtest/` for historical replay and evaluation
- `settings.py` for immutable baseline configuration loading
- source SQLite market database as read input

Allowed outputs:
- trial snapshots in `research_lab/snapshots/`
- experiment metadata in `research_lab/research_lab.db`
- offline reports and approval bundle artifacts for human review

Disallowed behavior:
- mutating live path modules as part of a research-lab-only milestone
- writing candidate parameters into `settings.py`
- bypassing approval artifacts and human review
- treating approval bundle generation as automatic promotion

Approval bundle is the end of the automated path. Human review and manual application are separate steps.

## Module Map

| Module | Role |
|---|---|
| `research_lab/cli.py` | Operator entrypoint for optimize, replay, report, and approval-bundle commands |
| `research_lab/workflows/optimize_loop.py` | Orchestrates baseline gate, Optuna search, Pareto selection, walk-forward, and recommendation persistence |
| `research_lab/workflows/replay_candidate.py` | Re-evaluates a stored candidate and rebuilds walk-forward plus recommendation artifacts |
| `research_lab/param_registry.py` | Canonical optimization sandbox registry: ACTIVE, FROZEN, DEFERRED, and UNSUPPORTED parameters |
| `research_lab/constraints.py` | Dependency and domain checks for parameter vectors before evaluation |
| `research_lab/integrations/optuna_driver.py` | Optuna study integration and trial sampling for ACTIVE parameters only |
| `research_lab/objective.py` | Candidate evaluation contract and objective metrics extraction |
| `research_lab/funnel.py` | Instrumented backtest wrapper for signal funnel metrics |
| `research_lab/walkforward.py` | Walk-forward window creation and post-hoc stability evaluation |
| `research_lab/pareto.py` | Multi-objective Pareto frontier computation and ranking |
| `research_lab/approval.py` | Recommendation drafting and approval bundle generation without auto-promotion |
| `research_lab/experiment_store.py` | SQLite persistence for trials, walk-forward reports, and recommendations |
| `research_lab/db_snapshot.py` | Per-trial source DB snapshot creation and required-table verification |
| `research_lab/baseline_gate.py` | Hard baseline contract: block optimization if the base settings do not generate enough trades |
| `research_lab/reporter.py` | Offline experiment report generation from the experiment store |
| `research_lab/settings_adapter.py` | Immutable `AppSettings` candidate construction from flat parameter overrides |
| `research_lab/sensitivity.py` | Local perturbation analysis for selected candidate parameters |

## End-to-End Flow

Primary optimization flow:

1. `python -m research_lab optimize ...`
2. CLI loads baseline `AppSettings`, resolves source DB, store path, and snapshots directory.
3. `baseline_gate` runs a read-only baseline backtest and blocks the workflow if the baseline contract fails.
4. Optuna samples ACTIVE parameters from `param_registry`.
5. Each trial is validated by `constraints.py`.
6. Each accepted trial runs against its own copied SQLite snapshot.
7. Trial metrics and signal funnel counts are stored in the experiment store.
8. Pareto frontier is computed across accepted trials.
9. Each Pareto candidate runs through walk-forward validation.
10. Walk-forward report is persisted.
11. `approval.build_recommendation()` converts evaluation plus walk-forward output into a recommendation draft.
12. Recommendation draft is stored in the experiment store.
13. `build-approval-bundle` may write human-review artifacts only if blocking promotion risks are absent.

Replay flow:

1. `python -m research_lab replay-candidate ...`
2. Load a previously stored candidate from the experiment store.
3. Re-run candidate evaluation on a fresh snapshot.
4. Rebuild walk-forward report and recommendation draft.
5. Persist refreshed artifacts for human review.

## Optimization Sandbox

Canonical source of truth: `research_lab/param_registry.py`

Sandbox rules:
- only parameters marked `ACTIVE` may be sampled by Optuna
- `FROZEN` parameters remain fixed at their baseline defaults
- `DEFERRED` parameters are intentionally excluded until a later version opens them
- `UNSUPPORTED` parameters are not reachable through the current `AppSettings` adapter

| Parameter or group | Status | Reason |
|---|---|---|
| All registry parameters not listed below | ACTIVE | Search-eligible within registry bounds and constraints |
| `weight_force_order_spike` | FROZEN | `force_orders` table currently has zero rows; feature unavailable |
| `ema_fast` | FROZEN | Architectural EMA-50 feature parameter frozen in v0.1 |
| `ema_slow` | FROZEN | Architectural EMA-200 feature parameter frozen in v0.1 |
| `ema_trend_gap_pct` | FROZEN | Regime threshold frozen at baseline-calibrated value in v0.1 |
| `compression_atr_norm_max` | FROZEN | Regime threshold frozen at baseline-calibrated value in v0.1 |
| `crowded_funding_extreme_pct` | FROZEN | Regime threshold frozen at baseline-calibrated value in v0.1 |
| `crowded_oi_zscore_min` | FROZEN | Regime threshold frozen at baseline-calibrated value in v0.1 |
| `regime_direction_whitelist` | FROZEN | Composite dict type; SHORT remains disabled in v1.1 baseline |
| `direction_tfi_threshold_inverse` | FROZEN | Derived constraint tied to `direction_tfi_threshold` |
| `no_trade_windows_utc` | FROZEN | Composite tuple structure frozen in v0.1 |
| `session_start_hour_utc` | FROZEN | Correlated pair with `session_end_hour_utc`; independent sampling creates many invalid combinations |
| `session_end_hour_utc` | FROZEN | Correlated pair with `session_start_hour_utc`; independent sampling creates many invalid combinations |
| `symbol` | FROZEN | Infrastructure parameter; not a strategy optimization target |
| `tf_setup` | FROZEN | Infrastructure parameter; not a strategy optimization target |
| `tf_context` | FROZEN | Infrastructure parameter; not a strategy optimization target |
| `tf_bias` | FROZEN | Infrastructure parameter; not a strategy optimization target |
| `flow_bucket_tf` | FROZEN | Infrastructure parameter; not a strategy optimization target |
| No current registry entries | DEFERRED | Deferred bucket exists for future versions but is empty in v0.1 |
| `force_order_history_points` | UNSUPPORTED | Exists outside the current `AppSettings` surface; cannot be set through the current adapter |

## Methodology Level

Current methodology level is intentionally limited:

- Optuna sees the full optimization date range.
- Pareto frontier selection is based on `expectancy_r`, `profit_factor`, and `max_drawdown_pct`.
- Walk-forward is applied after candidate search as a stability gate on Pareto candidates.
- Walk-forward window pass/fail currently uses `expectancy_r` plus degradation/fragility logic only.
- `profit_factor`, `max_drawdown_pct`, and `sharpe_ratio` are recorded metrics, but they do not yet drive per-window walk-forward decisions.

This means the current workflow is a post-hoc stability gate, not true nested optimization.

That limitation is accepted in v1 and tracked as explicit methodology debt. It must not be hidden behind marketing language such as "fully robust walk-forward optimization."

## Promotion Policy

Canonical blocking promotion risks in v1:
- `walkforward_not_passed`
- `walkforward_fragile`

Promotion rules:
- if a recommendation contains a blocking promotion risk, `build-approval-bundle` must fail hard
- approval bundle writes artifacts for a human reviewer only
- approval bundle does not edit `settings.py`
- a human applies any approved parameter changes manually

The workflow may recommend a candidate. It may not self-promote a candidate.

## Lineage & Reproducibility

Full reproducibility requires the following fields:
- `seed`
- `study_name`
- `protocol_hash`
- `config_hash`
- source DB path
- commit SHA
- date range

Current state:
- `config_hash` is first-class in `AppSettings`
- `seed` and `study_name` are first-class CLI inputs
- source DB path and date range are provided to workflow entrypoints
- `protocol_hash` is not yet persisted or enforced
- commit SHA is not yet persisted in the experiment store

Until protocol lineage is hashed and persisted, cross-experiment comparability is incomplete by design.

## Data Isolation

Data isolation is a hard architectural requirement, not an implementation detail.

Required rules:
- every trial, replay, and walk-forward segment runs against its own copied SQLite snapshot
- source DB must not be mutated by optimization trials
- baseline gate must use a read-only source DB connection
- experiment metadata must be written to the dedicated research lab store, not to the source market DB
- missing required source tables must fail explicitly

Research Lab is allowed to create artifacts. It is not allowed to create side effects on the source market database.

## Known Debt Register

| ID | Type | Description | Target version |
|---|---|---|---|
| `RL-001` | METHODOLOGY_DEBT | Walk-forward window decisions use `expectancy_r` only; drawdown, profit factor, and sharpe are not part of window pass/fail | v2 |
| `RL-002` | ARCH_DEBT | Protocol lineage is not hashed or enforced; `protocol_hash` is missing from experiment identity | v2 |
| `RL-003` | METHODOLOGY_DEBT | Walk-forward is post-hoc stability checking, not true nested optimization | v3 |
| `RL-004` | BUG | `min_trades_full_candidate` exists in `research_lab/configs/default_protocol.json` but is not consumed by the workflow | v2 |
| `RL-005` | ARCH_DEBT | `_PROMOTION_BLOCKING_RISKS` is defined in `cli.py` instead of a canonical shared contract location | v2 |

## Roadmap

| Version | Scope | Status |
|---|---|---|
| `v1` | Optimization harness plus hard promotion gate | DONE (`MVP_DONE`) |
| `v2` | Walk-forward multicriteria plus protocol lineage | PLANNED |
| `v3` | Nested walk-forward optimization | PLANNED |
| `vFuture` | Autoresearch agent loop | DEFERRED until lineage and nested walk-forward are closed |

## Definition of Done

| Status | Meaning |
|---|---|
| `MVP_DONE` | Offline workflow runs end-to-end, hard promotion gates exist, smoke coverage proves critical paths, and all known debt is explicit in blueprint and tracker |
| `DONE` | Workflow is fully reproducible for its blueprint version, lineage fields are enforced, promotion rules are canonicalized, and methodology matches the blueprint claims for that version |

Research Lab must not call itself `DONE` while methodology or lineage gaps required by the active blueprint version remain open.
