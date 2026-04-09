# Sweep-Reclaim Pre-Launch Research Report
Date: 2026-04-09
Analyst: Codex

## Executive Summary
The current Research Lab pipeline does not have a pre-campaign signal-health gate. Before `study.optimize()` starts, the only hard stop is the baseline gate, and that gate checks only baseline trade count, not feature distributions such as `sweep_detected` or `reclaim_detected`.

The current search space is broad relative to the default Optuna budget: 44 ACTIVE parameters versus a default 50-trial CLI run. That is workable for smoke and rough scouting, but it is thin for meaningful convergence in a mixed int/float space, especially when many trials are later rejected by candidate-level constraints.

`SWEEP-RECLAIM-FIX-V1` improves search-space quality because it replaces two non-discriminatory score offsets with two feature-shape knobs, but it does not by itself add an enforced validation checkpoint between code fix and campaign start. Today that sequence is process guidance in tracker/handoff documents, not a runtime-enforced rule.

## Q1 - Signal Health Gate
### Current state
Operator flow for `python -m research_lab optimize` is:

1. `research_lab/cli.py` parses CLI arguments and calls `run_optimize_loop()`.
2. `research_lab/workflows/optimize_loop.py` loads protocol, hashes it, calls `check_baseline()`, builds walk-forward windows, and then calls `run_optuna_study()`.
3. `research_lab/integrations/optuna_driver.py` constructs the Optuna study and calls `study.optimize(...)`.

There is no feature-distribution check anywhere in that pre-Optuna path.

The existing baseline gate in `research_lab/baseline_gate.py` runs one baseline backtest and only checks:

- `trades_count >= min_trades`

It does not inspect:

- `sweep_detected` rate
- `reclaim_detected` rate
- `sweep_detected && reclaim_detected` rate
- feature histogram drift
- signal funnel composition
- expectancy, PF, DD, or any other baseline metric

There is an additional candidate-level gate later in the flow:

- `run_optimize_loop()` passes `protocol["min_trades_full_candidate"]` into `run_optuna_study()`
- `research_lab/objective.py` rejects a trial if the evaluated candidate does not meet `min_trades`

That is still not a signal-health gate. It only rejects after a trial has already been sampled and backtested.

### What happens on current code
If someone launches a new Optuna campaign on the current pre-fix code, the system will not detect a degraded sweep regime before optimization begins.

What it will do:

- allow the campaign to start as long as the baseline backtest produces at least 5 trades
- sample ACTIVE parameters
- validate parameter vector consistency
- run backtests and reject some candidates later on trade-count or walk-forward criteria

What it will not do:

- stop the campaign because `sweep_detected` is abnormally frequent
- stop the campaign because the feature distribution has drifted away from strategy intent
- warn that Optuna is calibrating around a degraded signal source

### Is this deliberate design or an omission?
This looks like an omission by scope, not a deliberate methodological choice.

Evidence:

- `docs/BLUEPRINT_RESEARCH_LAB.md` documents baseline gate, Optuna search, Pareto, walk-forward, recommendation, and approval bundle
- the documented gates are backtest/trial/promotion gates, not feature-health gates
- neither code nor docs define a pre-campaign feature-distribution checkpoint

The system is designed to protect promotion quality, not input-signal quality. Those are different safeguards.

### Consequences
The practical consequence is that Optuna can spend full campaign budget learning thresholds around a broken or degraded semantic input. In the sweep/reclaim case, that means:

- search budget is consumed on compensation behavior rather than discovery
- Pareto candidates may look numerically acceptable while being based on distorted signal frequency
- campaign-to-campaign comparability degrades because the optimizer is solving a different effective problem than the intended strategy

There is also a visibility gap: `experiment_store.py` persists `funnel_json` for each trial, but `research_lab/reporter.py` does not surface funnel data in the standard experiment report. Even the post-trial signal funnel is therefore not prominent in the operator workflow.

## Q2 - Search Space Efficiency
### Current ACTIVE registry
`research_lab/param_registry.py` currently exposes:

| Status | Count |
|---|---:|
| ACTIVE | 44 |
| FROZEN | 15 |
| UNSUPPORTED | 1 |
| DEFERRED | 0 |

ACTIVE parameter type mix:

| Type | Count |
|---|---:|
| int | 12 |
| float | 31 |
| bool | 1 |
| categorical | 0 |

The single ACTIVE bool is `allow_long_in_uptrend`. There are no ACTIVE categoricals because infra/config identity fields such as symbol and timeframes are frozen.

### Trial budgets in code and in practice
Current budgets found in code and repository artifacts:

- CLI default in `research_lab/cli.py`: `--n-trials = 50`
- operator script default in `scripts/server/run_optimize.sh`: `50`
- smoke/test usage: usually `1` trial; audit smoke evidence uses `3` trials as a lightweight validation run
- current server context from the handoff: Run #3 is using `200` trials
- local experiment artifact `research_lab/runs/latest_report.json`: `50` total, `9` accepted, `41` rejected

This matters because rejection-heavy objectives shrink the effective search budget. A 50-trial request is not the same as 50 informative candidates if most of the sampled vectors later fail candidate-level or walk-forward gates.

### Statistical efficiency assessment
There is no hard universal rule for TPE convergence, but a practical rule of thumb is:

- trial count should be several multiples of active dimensions, not roughly equal to them
- mixed int/float spaces need more budget than a small smooth float-only space
- rejection-heavy objectives need more budget because many sampled vectors do not produce useful signal about the frontier

Against that standard:

- 44 ACTIVE params vs 50 default trials is underpowered
- 44 ACTIVE params vs 200 trials is much better, but still moderate rather than generous
- 9 accepted trials out of a 50-trial run is extremely thin for a 44-dimensional search space

The current default budget is therefore suitable for smoke or exploratory scouting, not for strong claims of convergence.

### Which ACTIVE params matter most to core edge
Highest leverage on sweep/reclaim edge quality:

- `atr_period`
- `equal_level_lookback`
- `equal_level_tol_atr`
- `sweep_buf_atr`
- `reclaim_buf_atr`
- `wick_min_atr`
- `min_sweep_depth_pct`

High leverage on direction, regime access, and signal admission:

- `direction_tfi_threshold`
- `tfi_impulse_threshold`
- `confluence_min`
- `ema_trend_gap_pct`
- `compression_atr_norm_max`
- `post_liq_tfi_abs_min`
- `allow_long_in_uptrend`
- active evidence weights in `_confluence_score()`

Mostly downstream or secondary relative to core edge formation:

- `entry_offset_atr`
- `invalidation_offset_atr`
- `tp1_atr_mult`
- `tp2_atr_mult`
- `min_stop_distance_pct`
- leverage and position limits
- DD limits
- cooldown and duplicate-level governance knobs
- partial exit and trailing controls

These downstream parameters still matter to final PnL, but they do not define whether the sweep/reclaim edge itself is semantically healthy.

### Effect of SWEEP-RECLAIM-FIX-V1 on registry quality
According to the current tracker scope, the milestone changes the registry as follows:

- enters ACTIVE: `level_min_age_bars`, `min_hits`
- leaves ACTIVE and becomes FROZEN: `weight_sweep_detected`, `weight_reclaim_confirmed`

Net effect on ACTIVE count:

- before fix: 44 ACTIVE
- after fix: 44 ACTIVE

Net effect on type mix:

- before fix: 12 int, 31 float, 1 bool
- after fix: 14 int, 29 float, 1 bool

This is a quality improvement even though dimensionality stays flat.

Why it is better:

- two constant score offsets stop consuming search budget
- two discrete knobs that directly shape level semantics and sweep rarity become searchable
- the optimizer gets parameters that affect feature meaning, not just threshold compensation

### Should ACTIVE be reduced further before the first post-fix campaign?
There is some justification, but it is not strictly required.

Reasonable argument for further reduction:

- if the first post-fix campaign is meant to re-baseline the restored core edge, temporarily freezing some downstream governance/risk knobs would make attribution cleaner
- duplicate-level and other governance controls can still distort campaign outcomes even if sweep semantics are fixed

Reasonable argument against reducing more right now:

- `SWEEP-RECLAIM-FIX-V1` already improves search efficiency materially without changing total dimension count
- additional pruning would be a methodology decision, not a necessary prerequisite for the first clean campaign
- extra freezes would expand decision scope beyond the currently approved milestone

Recommendation: run the first post-fix campaign with the milestone changes as planned, but treat it as a re-baselining campaign. Only add further freezes if Claude Code or the user wants a deliberately narrower "diagnostic" search.

## Q3 - Fix-to-Campaign Sequencing
### What is enforced today
There is no code-level enforcement of:

- fix feature semantics
- validate the resulting feature distribution
- only then start a campaign

What is enforced today:

- baseline backtest must produce at least 5 trades
- parameter vectors must satisfy relation constraints
- candidate evaluation must meet `min_trades_full_candidate`
- walk-forward and approval bundle gates protect promotion

What is not enforced:

- post-fix feature sanity before `optimize`
- explicit replay/distribution validation after touching `feature_engine.py`
- search-space integrity verification after touching `param_registry.py`
- operator acknowledgment that a clean post-fix baseline was produced before a new campaign starts

### What the documentation says
`docs/BLUEPRINT_RESEARCH_LAB.md` defines the campaign lifecycle as:

- optimize
- baseline gate
- Optuna search
- Pareto
- walk-forward
- recommendation
- approval bundle

That blueprint does not contain an explicit "post-code sanity check before campaign" stage.

The closest thing to a fix-to-campaign checkpoint is in `docs/MILESTONE_TRACKER.md` under the active milestone acceptance criteria:

- `sweep_detected < 50%` on replay with new defaults
- pytest green
- Optuna sees A+B as ACTIVE

That is important, but it is process guidance in tracker state, not a runtime-enforced gate.

### Typical project cycle
The current project cycle is best described as:

1. implement milestone
2. run smoke/tests
3. start campaign
4. build report
5. review Pareto and walk-forward outputs
6. optionally build approval bundle

There is no standardized operator-visible "sanity check after code, before Optuna" artifact in the normal CLI/report workflow.

### What should be validated after SWEEP-RECLAIM-FIX-V1 and before the first new campaign
Recommended checkpoint list:

1. Wiring and regression gate
   - `compileall` passes
   - relevant pytest suite passes
   - `smoke_phase_c.py` passes
   - `smoke_config_injection.py` confirms A+B are wired end-to-end

2. Feature-semantic gate on a fixed replay slice
   - `sweep_detected` is materially below the old degraded regime
   - milestone target from tracker is met: `sweep_detected < 50%`
   - `reclaim_detected` remains non-zero and interpretable
   - `sweep_detected && reclaim_detected` remains non-zero
   - signal generation does not collapse to zero after C2a and the lower `confluence_min`

3. Baseline campaign-readiness gate
   - one full-period baseline replay is run on the new defaults
   - `trades_count` clears not only the current baseline-gate floor of 5, but also the protocol-level full-candidate floor of 30
   - baseline funnel shows non-zero `signals_generated` and non-zero `signals_executed`

4. Search-space integrity gate
   - `level_min_age_bars` and `min_hits` are ACTIVE in registry
   - `weight_sweep_detected` and `weight_reclaim_confirmed` are FROZEN in registry
   - the confluence path no longer relies on those two constant offsets
   - `confluence_min` default/range matches the milestone decision

5. Campaign smoke gate
   - a short local optimize run completes after the fix
   - at least one trial is accepted
   - experiment report builds successfully

Only after those checks should the first full post-fix campaign be considered clean.

## Recommendations
- Add an explicit pre-campaign signal-health checkpoint to the operator workflow. This can be a small report or a documented command sequence; it does not need to be part of `SWEEP-RECLAIM-FIX-V1` implementation scope.
- Surface `funnel_json` in the standard experiment report, or provide a dedicated companion report/query. The data already exists in the store but is not operator-visible enough.
- Decide whether the first post-fix campaign is a normal optimize run or a deliberately narrower diagnostic campaign. That decision determines whether temporary extra freezes are worth the complexity.
- Document or fix the gap between the baseline gate threshold (`5`) and the protocol full-candidate threshold (`30`). Today a campaign can start on a baseline that is far weaker than the objective's own acceptance floor.
- Treat the tracker acceptance criteria as mandatory launch criteria for Run #4, not just milestone notes.

## Open Questions for Claude Code / User
- Should the first post-fix campaign use the full 44-parameter ACTIVE space, or should some downstream governance/risk knobs be temporarily frozen for a cleaner re-baseline?
- Should the baseline gate stay intentionally permissive at 5 trades, or should it be aligned with `min_trades_full_candidate` for campaign launch?
- Should signal-health validation become a code-level gate in Research Lab, or remain an operator-run checklist/report outside the main optimize command?
- Should the standard experiment report expose funnel metrics by default, so campaign degradation is visible without direct DB inspection?
