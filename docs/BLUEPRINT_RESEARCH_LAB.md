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
| `research_lab/__main__.py` | Package entrypoint for `python -m research_lab` |
| `research_lab/main.py` | Compatibility entrypoint delegating to the CLI |
| `research_lab/cli.py` | Operator entrypoint for optimize, replay, autoresearch, report, and approval-bundle commands |
| `research_lab/autoresearch_loop.py` | Single-pass autoresearch loop: hypothesis generation, direct evaluation, deterministic ranking, and conditional approval bundle output |
| `research_lab/workflows/optimize_loop.py` | Orchestrates baseline gate, Optuna search, Pareto selection, walk-forward, and recommendation persistence |
| `research_lab/workflows/replay_candidate.py` | Re-evaluates a stored candidate and rebuilds walk-forward plus recommendation artifacts |
| `research_lab/types.py` | Frozen dataclass contracts for trials, walk-forward outputs, recommendations, and autoresearch loop reports |
| `research_lab/constants.py` | Shared thresholds, minimum-trade defaults, and promotion-blocking risk constants |
| `research_lab/param_registry.py` | Canonical optimization sandbox registry: ACTIVE, FROZEN, DEFERRED, and UNSUPPORTED parameters |
| `research_lab/constraints.py` | Dependency and domain checks for parameter vectors before evaluation |
| `research_lab/integrations/optuna_driver.py` | Optuna study integration and trial sampling for ACTIVE parameters only |
| `research_lab/objective.py` | Candidate evaluation contract and objective metrics extraction |
| `research_lab/funnel.py` | Instrumented backtest wrapper for signal funnel metrics |
| `research_lab/protocol.py` | Protocol loading and deterministic protocol-hash lineage helpers |
| `research_lab/walkforward.py` | Walk-forward window creation plus post-hoc and nested validation flows |
| `research_lab/pareto.py` | Multi-objective Pareto frontier computation and ranking |
| `research_lab/approval.py` | Recommendation drafting and approval bundle generation without auto-promotion |
| `research_lab/experiment_store.py` | SQLite persistence for trials, walk-forward reports, and recommendations |
| `research_lab/db_snapshot.py` | Per-trial source DB snapshot creation and required-table verification |
| `research_lab/baseline_gate.py` | Hard and soft baseline contracts: block broken baselines, warn on weak but evaluable baselines |
| `research_lab/reporter.py` | Offline experiment report generation from the experiment store |
| `research_lab/settings_adapter.py` | Immutable `AppSettings` candidate construction from flat parameter overrides |
| `research_lab/sensitivity.py` | Local perturbation analysis for selected candidate parameters |

## End-to-End Flow

Primary optimization flow:

1. `python -m research_lab optimize ...`
2. CLI loads baseline `AppSettings`, resolves source DB, store path, snapshots directory, and protocol configuration.
3. `baseline_gate` runs a read-only baseline backtest.
4. Hard baseline checks block the workflow if the baseline is broken or nonsensical.
5. Soft baseline checks keep the workflow running for weak but still evaluable baselines and persist warning-ready metrics in the summary.
6. Optuna samples ACTIVE parameters from `param_registry`.
7. Each trial is validated by `constraints.py`.
8. Each accepted trial runs against its own copied SQLite snapshot.
9. Trial metrics, signal funnel counts, and trial lineage are stored in the experiment store.
10. Pareto frontier is computed across accepted trials.
11. Each Pareto candidate runs through walk-forward validation.
12. Walk-forward report is persisted.
13. `approval.build_recommendation()` converts evaluation plus walk-forward output into a recommendation draft.
14. Recommendation draft is stored in the experiment store.
15. `build-approval-bundle` may write human-review artifacts only if blocking promotion risks are absent.

Two-phase staged workflow:

1. Phase 1 discovery: `optimize` is the canonical broad search stage. Warm-start history is filtered by `protocol_hash` plus `search_space_signature` by default, with an explicit unsafe bypass for operators.
2. Phase 2 refinement: `autoresearch` is the canonical refinement stage. It is not a peer alternative to Optuna discovery. It consumes prior store history and may be explicitly seeded from Phase 1 Pareto exports through `--seed-from-pareto`.
3. Promotion artifacts remain human-reviewed outputs only. Phase 2 may refine candidates; it may not bypass approval policy.

Replay flow:

1. `python -m research_lab replay-candidate ...`
2. Load a previously stored candidate from the experiment store.
3. Re-run candidate evaluation on a fresh snapshot.
4. Rebuild walk-forward report and recommendation draft.
5. Persist refreshed artifacts for human review.

Protocol operation:

- `walkforward_mode` is a protocol field, not a separate CLI command.
- Default protocol is `research_lab/configs/default_protocol.json` and currently sets `walkforward_mode` to `post_hoc`.
- Operators may activate nested mode by editing the protocol JSON or by providing an alternate protocol file through `--protocol-path`.
- `replay-candidate` supports `walkforward_mode=post_hoc` only and rejects nested mode explicitly.

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

Current methodology supports two explicit modes:

- `walkforward_mode=post_hoc` remains the default v2-compatible flow.
- Operators choose the mode through protocol JSON, either by editing the default protocol or by passing a custom file with `--protocol-path`.
- In `post_hoc` mode, Optuna sees the full optimization date range, Pareto frontier selection is based on `expectancy_r`, `profit_factor`, and `max_drawdown_pct`, and walk-forward is applied afterward as a stability gate.
- In `nested` mode, each walk-forward window runs its own train-only Optuna search, the train champion is evaluated on that window's validation slice, and final candidate selection is based on aggregated out-of-sample validation results.
- In both modes, walk-forward window pass/fail requires `min_trades_per_window` and enforces per-window protocol thresholds for `expectancy_r`, `profit_factor`, `max_drawdown_pct`, and `sharpe_ratio`.
- Fragility still uses expectancy degradation between train and validation segments.
- Methodology is staged, not forked: Optuna discovery is Phase 1, autoresearch refinement is Phase 2, and Pareto handoff is the supported bridge between them.

The remaining methodology limitation is narrower: `post_hoc` mode is intentionally not nested, and nested mode still requires honest language about its exact aggregation and selection contract.

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
- `search_space_signature`
- `trial_context_signature`
- `baseline_version`
- `config_hash`
- source DB path
- commit SHA
- date range

Current state:
- `config_hash` is first-class in `AppSettings`
- `seed` and `study_name` are first-class CLI inputs
- source DB path and date range are provided to workflow entrypoints
- `protocol_hash` is derived from canonical protocol JSON and persisted with trials, walk-forward reports, recommendations, and experiment reports
- `search_space_signature`, optional `regime_signature`, `trial_context_signature`, and `baseline_version` are persisted with trials for context-safe warm-start and replay lineage
- commit SHA is not yet persisted in the experiment store

Protocol lineage is now explicit for the current blueprint version, but full reproducibility is still incomplete until commit SHA is persisted.

## Data Isolation

Data isolation is a hard architectural requirement, not an implementation detail.

Required rules:
- every trial, replay, and walk-forward segment runs against its own copied SQLite snapshot
- source DB must not be mutated by optimization trials
- baseline gate must use a read-only source DB connection
- experiment metadata must be written to the dedicated research lab store, not to the source market DB
- missing required source tables must fail explicitly

Research Lab is allowed to create artifacts. It is not allowed to create side effects on the source market database.

## Autoresearch Agent Loop — v1 Contract

### Goal

Autoresearch v1 is a supervised offline loop that generates and evaluates
parameter hypotheses without human input between iterations, then delivers
a loop report and an optional approval bundle for human review and decision.

The agent is an analyst, not a decision-maker. It proposes, tests, and
reports. It does not promote, commit, or modify strategy code.

### Non-Goals (v1)

- No changes to strategy code (`feature_engine`, `signal_engine`,
  `regime_engine`, or any live-path module)
- No auto-promotion of any candidate to `settings.py`
- No git commits or pushes initiated by the agent
- No LLM as execution gate or ranking authority — LLM may generate
  hypothesis rationale and exploration priority, but all pass/fail
  decisions are made by the deterministic evaluation pipeline
- No unattended scheduling — every run is manually triggered by the operator
- No multi-iteration autonomous re-entry — v1 is single-pass only

### Write Scope

The autoresearch agent is permitted to read and write:

| Scope | Access |
|---|---|
| `research_lab/experiment_store` (via public API) | Read + Write |
| `research_lab/configs/` protocol files | Read only |
| Loop report output directory | Write (report only) |
| Approval bundle output directory | Write (artifacts only, if eligible) |
| `research_lab/param_registry.py` | Read only |

The agent must not touch:

| Scope | Reason |
|---|---|
| `settings.py` | Promotion channel — human-only |
| `core/**`, `execution/**`, `orchestrator.py` | Live path — out of bounds |
| `backtest/`, `walkforward.py`, `pareto.py` | Evaluation infrastructure |
| Any FROZEN, DEFERRED, or UNSUPPORTED parameter | Registry policy |
| Git index or working tree | Commits and pushes are operator actions |

### Input Data Sources

1. **Experiment store** — trial history, walk-forward reports,
   recommendation drafts, protocol hashes from previous runs
2. **param_registry** — canonical ACTIVE parameter space, bounds,
   constraints
3. **Last approval bundle** — params_diff and risks from most recent
   human-reviewed recommendation
4. **Protocol file** — current thresholds; v1 requires `walkforward_mode=post_hoc`
5. *(Optional)* **LLM advisory pass** — given metrics summary and param
   history, LLM suggests exploration priority and writes a hypothesis
   rationale string stored alongside the experiment record. Advisory only.

### Loop Flow

```
1. LOAD
   Read experiment store: last N recommendations, trial metrics,
   walk-forward results, known blocking risks.

2. HYPOTHESIZE
   Generate K explicit parameter vectors within ACTIVE bounds and
   constraints. Hypothesis sources (in priority order):
   a. Heuristics: perturb best known params toward unexplored regions
   b. Gradient-free search: exploit high-expectancy regions from store
   c. LLM advisory: optional rationale and reordering of K candidates
   Cap at MAX_CANDIDATES_PER_LOOP before evaluation.

3. FILTER
   Apply param_registry constraints. Drop invalid vectors silently.

4. EVALUATE
   v1 supports walkforward_mode=post_hoc only. nested is NOT SUPPORTED
   for autoresearch v1.
   For each candidate vector:
   - run deterministic full-period backtest using evaluate_candidate
   - run post-hoc walk-forward using run_walkforward
   - apply all existing gates: baseline_gate, WF multicriteria,
     promotion_gate
   The agent does not call run_optimize_loop or run_optuna_study.
   It evaluates pre-generated vectors directly.

5. RANK
   Sort all evaluated candidates by lexicographic key:
   - walkforward_passed desc
   - walkforward_fragile asc
   - expectancy_r desc
   - max_drawdown_pct asc
   - profit_factor desc
   - trades_count desc
   - candidate_id asc (deterministic tiebreak)

6. REPORT
   Always write a loop report to output directory. The loop report
   contains: hypothesis rationale per candidate, ranked results,
   blocking risks, loop stop reason.

   Approval bundle is written only for the top-ranked candidate that
   has no blocking risks (walkforward_not_passed or walkforward_fragile
   absent from risks). If all candidates are blocked, the loop report
   exists but no approval bundle is generated.

   Loop terminates. Human reviews loop report and optional approval
   bundle before any next action.
```

### Experiment Safety Limits

| Limit | Value | Notes |
|---|---|---|
| `MAX_CANDIDATES_PER_LOOP` | 10 (default) | Configurable in protocol; hard ceiling 50 |
| `MAX_LOOP_ITERATIONS` | 1 | Single-pass only in v1 |
| `walkforward_mode` | `post_hoc` only | nested not supported in v1 |
| Parameter bounds | Enforced by `param_registry` | Agent cannot exceed registered ranges |
| Constraint validation | `constraints.py` applied before every evaluation | Invalid vectors dropped, not patched |
| Source DB | Read-only snapshot isolation inherited from evaluate path | No side effects on market data |
| Promotion gate | Unchanged — blocking risks prevent approval bundle | Loop report always written regardless |

### Stop Criteria

The loop terminates when any of the following is true:

1. All K candidates evaluated (normal completion)
2. `MAX_CANDIDATES_PER_LOOP` reached
3. Baseline gate fails (data coverage insufficient)
4. Experiment store not writable

On stop: loop report written with completed results and stop reason.
No retry.

### Definition of DONE (v1)

| Criterion | Required |
|---|---|
| Loop runs end-to-end from CLI trigger | YES |
| Hypotheses bounded by param_registry ACTIVE space only | YES |
| v1 rejects `walkforward_mode=nested` explicitly | YES |
| Each candidate evaluated via `evaluate_candidate` + `run_walkforward` | YES |
| Ranking is lexicographic and fully deterministic | YES |
| Loop report always written (even if all candidates blocked) | YES |
| Approval bundle written only for top candidate without blocking risks | YES |
| LLM rationale stored as advisory text, not as a gate | YES |
| No strategy code modified | YES |
| No auto-promotion to `settings.py` | YES |
| No git commit or push | YES |
| Smoke test: single-pass with mocked evaluations → ranked loop report | YES |
| Smoke test: all candidates WF-blocked → loop report exists, no bundle | YES |

`MVP_DONE`: loop runs, gates respected, loop report and conditional
bundle produced, deterministic ranking verified.

`DONE`: reproducible (protocol_hash, seed, store lineage fully tracked),
loop stop reasons logged, LLM advisory path tested with mock LLM,
smoke coverage for all stop criteria.

### Explicit Out-of-Scope (v1)

- Multi-iteration autonomous loop
- `walkforward_mode=nested` support
- Strategy code or signal logic changes
- FROZEN, DEFERRED, UNSUPPORTED parameter changes
- LLM as execution gate or ranking authority
- Scheduled or event-triggered runs
- Auto-merge of results into live settings
- Per-hypothesis A/B comparison against live performance

---

## Known Debt Register

| ID | Type | Description | Target version |
|---|---|---|---|
| None | — | All known debt closed | — |

## Roadmap

| Version | Scope | Status |
|---|---|---|
| `v1` | Optimization harness plus hard promotion gate | CLOSED MVP_DONE |
| `v2` | Walk-forward multicriteria plus protocol lineage | CLOSED MVP_DONE |
| `v3` | Nested walk-forward optimization | CLOSED MVP_DONE |
| `hardening` | Store schema DDL + operator clarity | CLOSED DONE |
| `vFuture` | Autoresearch agent loop | CLOSED MVP_DONE |

## Definition of Done

| Status | Meaning |
|---|---|
| `MVP_DONE` | Offline workflow runs end-to-end, hard promotion gates exist, smoke coverage proves critical paths, and all known debt is explicit in blueprint and tracker |
| `DONE` | Workflow is fully reproducible for its blueprint version, lineage fields are enforced, promotion rules are canonicalized, and methodology matches the blueprint claims for that version |

Research Lab must not call itself `DONE` while methodology or lineage gaps required by the active blueprint version remain open.
