# Optuna Utility Report
Date: 2026-04-09
Analyst: Codex

## Executive Summary
Current Optuna usage is clean, deterministic, and architecturally conservative: an in-memory, sequential, multi-objective TPE study drives candidate generation, while durable artifacts are written to the custom experiment store rather than to Optuna storage. The largest utility gap is not an obviously wrong sampler choice, but the combination of ephemeral studies, no warm-starting, and a 44-parameter ACTIVE search space that is large relative to the default 50-trial operating budget.

TPE remains a defensible default for the current space, especially after Optuna's multi-objective TPE improvements, but the implementation leaves value on the table in three places: no resumeable study history, no reuse of already-known good configurations, and no multivariate modeling of correlated parameters. The highest-ROI priorities are therefore: introduce explicit Optuna persistence with resume semantics, warm-start studies from baseline and prior winners, and test `TPESampler(multivariate=True)` before considering sampler-family changes.

Two adjacent findings materially affect how Optuna results are interpreted downstream. First, a missing leverage constraint allows different sampled vectors to collapse to identical runtime behavior, which wastes search budget. Second, the walk-forward drawdown threshold appears to use percentage-style values against a `0..1` drawdown metric, which weakens the practical influence of the third optimization objective and should be resolved before over-tuning sampler strategy.

## Current State Map
| Area | Current implementation | Evidence |
| --- | --- | --- |
| Study entrypoint | Optuna integration is centralized in `run_optuna_study()`. | `research_lab/integrations/optuna_driver.py:107` |
| Study initialization | `optuna.create_study()` is called once per run with explicit multi-objective directions. | `research_lab/integrations/optuna_driver.py:125-128` |
| Sampler | Explicit `TPESampler(seed=seed)`; no extra TPE options enabled. | `research_lab/integrations/optuna_driver.py:124` |
| Pruner | No pruner is configured; no pruning API is used anywhere in the Research Lab codepath. | `research_lab/integrations/optuna_driver.py:125`; repo search found no `pruner`, `TrialPruned`, `trial.report`, or `should_prune` usage under `research_lab/**` |
| Objective structure | Objective samples ACTIVE params, validates them, builds candidate settings, clones the runtime DB snapshot, runs a full backtest funnel, persists a summary, then returns `(expectancy_r, profit_factor, max_drawdown_pct)`. | `research_lab/integrations/optuna_driver.py:130-168`; `research_lab/objective.py:46-79` |
| Objective return semantics | Multi-objective tuple is `(maximize expectancy_r, maximize profit_factor, minimize max_drawdown_pct)`. | `research_lab/integrations/optuna_driver.py:128`; `research_lab/objective.py:31-42` |
| Study storage | No `storage=` argument is passed, so the study is in-memory only. Durable trial records live in the custom SQLite experiment store, not in Optuna storage. | `research_lab/integrations/optuna_driver.py:125`; `research_lab/experiment_store.py:18-114` |
| Resume behavior | None at Optuna level. A rerun with the same `study_name` starts a new in-memory study. | `research_lab/integrations/optuna_driver.py:125-176` |
| Parallelism | `study.optimize()` is called without `n_jobs`; CLI exposes no parallelism flag. Execution is sequential. | `research_lab/integrations/optuna_driver.py:176`; `research_lab/cli.py:93-95` |
| Callbacks | No Optuna callbacks are registered. | `research_lab/integrations/optuna_driver.py:176`; repo search found no `callbacks=` usage |
| `trial.report()` / intermediate values | Not used. Objective is one-shot and does not emit partial metrics. | repo search found no `trial.report` usage under `research_lab/**` |
| Trial metadata | No `trial.set_user_attr()` or `study.set_metric_names()` usage. | repo search found no `set_user_attr` or `set_metric_names` usage |
| Search-space source of truth | Registry-driven governance via `build_param_registry()`, filtered to ACTIVE params only. | `research_lab/param_registry.py:165-190`; blueprint policy in `docs/BLUEPRINT_RESEARCH_LAB.md:108-115` |
| Search-space status mix | 60 params in registry: 44 ACTIVE, 15 FROZEN, 0 DEFERRED, 1 UNSUPPORTED. ACTIVE mix is mostly numeric: 12 ints, 31 floats, 1 bool. | `research_lab/param_registry.py:165-190`; `settings.py` defaults and types |
| Range overrides | ACTIVE ranges are explicitly curated in `_RANGE_OVERRIDES`. | `research_lab/param_registry.py:38-99` |
| Frozen governance | FROZEN params have documented reasons, e.g. unavailable features, architecture locks, or composite surfaces. | `research_lab/param_registry.py:18-36` |
| Coupled parameter sampling | Two ordering constraints are encoded during sampling: `ema_slow > ema_fast` and `tp2_atr_mult > tp1_atr_mult`. | `research_lab/integrations/optuna_driver.py:37-54` |
| Hard constraints | Additional validation runs after sampling via `assert_valid()`. | `research_lab/integrations/optuna_driver.py:142`; `research_lab/constraints.py:6-52` |
| Missing hard constraint | No explicit validation enforces `high_vol_leverage <= max_leverage`, so distinct trial vectors can collapse to the same runtime leverage. | `research_lab/constraints.py:6-52`; runtime clamp in `core/risk_engine.py:82-85` |
| Data isolation | Every trial copies the runtime SQLite DB to a per-trial snapshot before evaluation. | `research_lab/db_snapshot.py:10-25`; `research_lab/integrations/optuna_driver.py:145-160` |
| Snapshot cleanup | Per-trial snapshot cleanup now occurs in the Optuna objective `finally` block. | `research_lab/integrations/optuna_driver.py:158` |
| Runtime DB size pressure | The runtime DB is large enough that per-trial cloning is materially expensive. Recent tracker notes describe prior `665MB x N_trials` accumulation. | `docs/MILESTONE_TRACKER.md`; local `storage/btc_bot.db` size inspection |
| Baseline gate | Baseline validation runs before optimization and uses read-only access to source data, with trade persistence disabled in the runner. | `research_lab/workflows/optimize_loop.py:47`; `research_lab/baseline_gate.py:24-44` |
| Downstream consumption | Completed trial summaries are stored in `research_lab.db`, then custom Pareto ranking selects candidates for walk-forward, recommendation, and reporting. | `research_lab/workflows/optimize_loop.py:100-133`; `research_lab/pareto.py:27-61`; `research_lab/reporter.py:33-140` |
| Pareto policy | Pareto frontier is computed from non-rejected trials, then ranked lexicographically by expectancy, profit factor, drawdown, trades, and trial id. | `research_lab/pareto.py:31-61` |
| Walk-forward integration | Post-hoc mode optimizes once, then evaluates Pareto-front candidates; nested mode runs Optuna inside each train window. | `research_lab/workflows/optimize_loop.py:59-124`; `research_lab/walkforward.py:315-387` |
| Reproducibility controls | `study_name`, `seed`, `protocol_hash`, and config hash are central to the workflow, but only some of them are persisted outside runtime logs/store rows. | `research_lab/cli.py:93-95`; `docs/BLUEPRINT_RESEARCH_LAB.md:166-181`; `research_lab/experiment_store.py:29-32` |
| LLM boundary | LLM is outside the core Optuna loop. Existing advisory logic may reorder proposals but cannot mutate the candidate set. | `research_lab/autoresearch_loop.py:358-372`; `docs/BLUEPRINT_RESEARCH_LAB.md:249-266` |

## Gap Analysis
### A. Sampler Selection
The current default sampler is `TPESampler(seed=seed)`, with no multivariate modeling, no grouping, no constraint callback, no warm-start, and no reuse of prior trials. For the actual search space, TPE is not an obviously poor choice. The active space is high-dimensional, mostly numeric, includes conditional coupling, and is run under relatively small trial budgets in common operator flows (`50` trials in the server script). Official Optuna documentation also notes that multi-objective TPE has become substantially faster in modern Optuna and can now be preferred over NSGA-II in many cases.

The main missed opportunity inside the current sampler family is not "switch away from TPE," but "use more of TPE." In particular, correlated parameters exist across trend filters, target ladders, invalidation distances, leverage caps, and compression thresholds, yet the current configuration leaves TPE in its simplest independent mode. `multivariate=True` is the first missing capability worth testing because it addresses actual structure in the space without changing architecture or decision semantics.

Alternative samplers are currently lower-priority:

- `NSGAIISampler`: historically a standard multi-objective choice, but less compelling here because Optuna's own documentation now positions modern multi-objective TPE as faster, and NSGA-II does not solve the larger issues of ephemeral studies, no warm-start, and a tight trial budget.
- `RandomSampler`: useful as a baseline or brief diversification phase, but not as the default for a 44-dimensional search where each trial is expensive.
- `CmaEsSampler`: mismatched to the current space because it does not naturally fit the project's mixed and partially discrete parameter structure. It is more appropriate for dense continuous spaces with fewer categorical or stepped dimensions.
- `GPSampler`: potentially attractive only when evaluation is very expensive and dimensionality is modest. The present space is too wide and heterogeneous for GP modeling to be the first change to make, and its dependency surface is heavier.

Warm-starting is the most credible sampler-adjacent gap. Optuna supports `enqueue_trial()` and adding prior trials; the current workflow already has a baseline configuration plus persisted winners in `research_lab.db`, but none of that prior information is fed back into new studies. That is a real omission, not an architectural necessity.

Assessment: sampler-family change is not justified yet. Enhanced TPE plus warm-starting is the correct next step.

### B. Pruner Strategy
No pruner is configured, and the current objective is not instrumented for pruning. That absence looks deliberate by consequence, even if it was not explicitly documented as a conscious design choice. The Research Lab objective performs a full backtest funnel and only produces meaningful metrics at the end of the run. There is no staged loop inside the objective that emits intermediate values or naturally checkpoints partial fidelity.

This matters because Optuna's pruning APIs are built around intermediate reporting. Official Optuna documentation also notes a harder limitation for this project: `trial.report()` and `trial.should_prune()` are not supported for multi-objective optimization. The current study is three-objective. As a result, "just add MedianPruner" is not available as an implementation-detail improvement.

Optuna offers a rich pruner set, including Median, Percentile, Patient, Threshold, Successive Halving, Hyperband, Wilcoxon, and no-op behavior. However, these are practical only when the objective is both prune-able and compatible with single-objective pruning semantics. The current pipeline is neither.

Realistic time savings at the current design are therefore near zero. To unlock pruning, the methodology would have to change in one of two ways:

- Introduce a staged or partial-fidelity objective that reports meaningful intermediate scalar progress.
- Add a separate single-objective pre-screen before the full multi-objective evaluation.

Assessment: lack of pruner is not the main gap today. It becomes relevant only after an objective redesign and likely a methodology decision.

### C. Study Persistence
The study is created without `storage=`, so Optuna uses in-memory storage. This means there is no resume, no cross-run study comparison inside Optuna, no persistent trial history, and no first-class Optuna dashboard integration. If a process dies mid-run, Optuna state is lost even though summarized trial outputs may already have been written to `research_lab.db`.

The custom experiment store does not remove the need for Optuna persistence because it stores post-evaluation artifacts, not the internal search process. It captures enough to audit results, but not enough to resume a study faithfully, inspect sampler behavior through Optuna-native tooling, or accumulate study state across repeated campaigns under the same hypothesis.

Persistent Optuna storage does not inherently conflict with `experiment_store` if responsibilities stay separate:

- Optuna storage: sampler state, trial lifecycle, study metadata, dashboard support, resume semantics.
- Experiment store: project-specific summaries, Pareto candidates, walk-forward reports, recommendations, protocol lineage.

For this architecture, the most plausible storage choices are:

- `JournalStorage` on a single host if safe local resume/history is the first priority.
- `RDBStorage` if dashboard-first workflows or stronger multi-worker infrastructure become the priority.

Optuna's own storage guidance warns against SQLite-based `RDBStorage` for parallel optimization. That warning does not block using persistence in sequential mode, but it does matter for future `n_jobs` or multi-process expansion. If persistence is added now, the storage choice should be made with that future boundary in mind.

Assessment: this is the largest immediate utility gap in the current integration.

### D. Parallelism
The current implementation is sequential. No `n_jobs` is passed to `study.optimize()`, and the CLI does not expose any parallelism controls. In isolation, that is conservative but sensible.

Turning on `n_jobs > 1` is not safe by default in this architecture. The objective is CPU-heavy Python work around backtest replay and metric computation, so Optuna's thread-based `n_jobs` path is unlikely to scale well because of the GIL. Official Optuna documentation also notes that sampler reproducibility degrades when `n_jobs != 1` because samplers reseed under parallel execution. That directly conflicts with the Research Lab's determinism and auditability bias.

There are also project-specific concurrency risks:

- Every trial copies a large SQLite database to a snapshot file.
- `experiment_store.py` uses plain SQLite connections with no visible WAL, busy timeout, or parallel hardening.
- Persistent Optuna storage is not yet configured.
- The runtime workload is I/O and disk heavy enough that snapshot contention can become a bottleneck even before compute saturation.

The likely real speed gain from naive `n_jobs > 1` is therefore modest to poor on the current design, while operational risk rises materially. If parallelism is ever pursued, process-based workers plus hardened storage boundaries are more credible than thread-based `n_jobs`.

Assessment: no parallelism is a justified conservative choice for now, not an urgent omission.

### E. Multi-objective Setup
The three objectives being optimized are `expectancy_r`, `profit_factor`, and `max_drawdown_pct`, with the first two maximized and the last minimized. At a high level, this is a sensible trio for a strategy-search phase: one return-quality metric, one efficiency/stability metric, and one downside control metric.

The stronger issue is not objective selection, but downstream interpretation. The custom Pareto ranker is lexicographic and gives expectancy first priority, then profit factor, then drawdown, then trade count. That means the pipeline is not treating the three objectives as equally important in final candidate ordering even though the study itself is multi-objective. This may be acceptable, but it should be acknowledged as policy rather than assumed neutrality.

There are two concrete distortions in the current setup:

- The walk-forward protocol appears to compare a `0..1` drawdown metric to a threshold configured as `50.0`, which makes the drawdown gate effectively non-binding unless the unit convention is different from what the performance code indicates.
- `profit_factor` can become `inf` in performance computation when there is no gross loss, but `_to_finite_float()` collapses non-finite values to `0.0` before Optuna/store consumption. This avoids non-finite storage problems, but it also turns a rare strong edge case into the worst possible value.

On sampler choice, NSGA-II is not currently more compelling than TPE for this multi-objective setup. The objectives themselves are reasonable; the bigger improvements are constraint quality, persistence, and downstream unit alignment.

Assessment: keep the current three-objective shape, but fix downstream metric semantics before reconsidering objective strategy.

### F. Search Space Governance
Search-space governance is one of the stronger parts of the implementation. There is a clear registry, only ACTIVE params are sampled, FROZEN params have explicit reasons, and the blueprint's governance model is reflected in code. That is good architecture and should be preserved.

The problem is not lack of governance but search efficiency. Forty-four ACTIVE parameters is a large surface for the default operational budget, and several active ranges are broad enough that the study can spend many expensive trials mapping low-value regions. This is where more ROI likely exists than in a sampler swap.

The most concrete governance gap is constraint placement and completeness:

- Some ordering constraints are enforced during sampling.
- Additional hard constraints are enforced afterward in `assert_valid()`.
- No Optuna-native `constraints_func` is used.
- One runtime-relevant constraint is missing entirely: `high_vol_leverage <= max_leverage`.

This creates a waste pattern where Optuna may explore distinct parameter vectors that the runtime later collapses to the same executed leverage behavior. That is not only inefficient; it also weakens trial comparability.

On frozen parameters, the current freezes mostly look justified:

- EMA architecture parameters are frozen consistently with the declared strategy shape.
- Session/no-trade window composites are correctly treated as non-trivial surfaces, not casually opened.
- `weight_force_order_spike` is frozen because the underlying feature is documented as unavailable.

Possible future unlocks exist, especially around crowded-market thresholds, but they are not the first move. Range tightening and missing-constraint cleanup should come first.

Assessment: governance structure is sound; efficiency and completeness of constraints are the main gaps.

### G. Callbacks and Observability
Optuna-side observability is minimal. There are no callbacks, no intermediate values, no metric names, no trial user attributes, and no persistent study backend. As a result, most of Optuna's diagnostic value disappears at process exit even though the project is otherwise strongly audit-oriented.

Several low-cost additions are available even without changing methodology:

- `study.set_metric_names()` to label the three objectives explicitly.
- `trial.set_user_attr()` for protocol hash, config hash, source DB path, date range, wall-clock duration, rejection reason, and possibly baseline status.
- A simple callback to log run-level summaries or emit additional audit metadata.

These additions do not change optimization results, but they materially improve traceability. They become significantly more valuable once persistent Optuna storage exists, because then the metadata survives beyond the current process.

`trial.report()` is not the right missing piece here because the current study is multi-objective and the objective is one-shot. Similarly, `optuna-dashboard` is only justified after persistent Optuna storage is introduced. Right now, there is nothing durable for the dashboard to inspect.

Assessment: observability is an underused Optuna capability and a good secondary improvement after persistence.

### H. LLM Augmentation
The current project already keeps LLM outside the deterministic optimization core, which is the correct default under both AGENTS.md and the research blueprint. Existing LLM advisory logic can reorder proposals but cannot mutate them, preserving auditability.

There is room for LLM augmentation around the Optuna workflow, but not inside the per-trial decision loop:

- Plausible use: pre-campaign hypothesis generation, range review, or campaign design assistance.
- Plausible use: post-processing Pareto or walk-forward outputs into operator-facing summaries and follow-up hypotheses.
- Weak fit: LLM as a custom sampler or per-trial parameter proposer inside the optimization loop.

The weak-fit cases fail for practical reasons, not just policy. Latency would reduce `n_trials/min`, trial-to-trial stochasticity would complicate reproducibility, and any hidden prompt drift would be operationally hard to audit. Even if technically possible, it would be misaligned with the system philosophy for the core search path.

Assessment: keep LLM outside the trial loop. Use it, if at all, at campaign boundaries.

## Prioritized Recommendations
Scoring heuristic used: `[Gain] x [Ease of implementation] / [Architectural risk]`, expressed qualitatively to support ordering rather than false precision.

| Rank | Recommendation | Gain | Ease | Risk | Blueprint impact |
| --- | --- | --- | --- | --- | --- |
| 1 | Add explicit persistent Optuna storage with resume semantics, separate from `research_lab.db`. | High | Medium | Low-Medium | Implementation detail unless storage policy is standardized in blueprint |
| 2 | Warm-start studies from baseline settings and prior winning candidates via Optuna-native enqueue/history mechanisms. | High | Medium | Low | Implementation detail |
| 3 | Tighten broad ACTIVE ranges and add missing constraints, especially `high_vol_leverage <= max_leverage`. | High | Medium | Medium | Mostly implementation detail; range-policy changes may merit tracker/blueprint note |
| 4 | Keep TPE as default but A/B test `multivariate=True` on representative campaigns. | Medium-High | High | Low | Implementation detail |
| 5 | Add Optuna-side observability: metric names, trial user attrs, and lightweight callbacks. | Medium | High | Low | Implementation detail |
| 6 | Resolve drawdown unit alignment between optimization metrics and walk-forward thresholding. | Medium-High | Medium | Medium-High | Likely methodology/blueprint-sensitive because it affects promotion semantics |
| 7 | Do not enable `n_jobs > 1` yet; revisit only after storage/store hardening and process-level design. | Risk avoidance | High | Low | No blueprint change needed to defer |
| 8 | Defer pruner adoption unless the objective is redesigned into a prune-able scalar or staged form. | Risk avoidance | High | Low | Methodology decision required before implementation |
| 9 | Do not switch default sampler family yet; revisit NSGA-II, GP, or CMA-ES only after persistence, warm-start, and range cleanup. | Risk avoidance | High | Low | No blueprint change needed to defer |

### 1. Add explicit persistent Optuna storage with resume semantics
What to change: introduce a dedicated Optuna storage path/config at study creation time in `research_lab/integrations/optuna_driver.py:124-128`, expose it through the CLI path defaults in `research_lab/cli.py:41-49`, and treat study resume (`load_if_exists=True` or equivalent storage semantics) as part of the standard run contract.

Expected gain: resume after interruption, persistent sampler state, true cross-run study continuity, richer diagnostics, and the option to use Optuna-native tooling such as dashboards or trial history inspection. This is the highest utility unlock because it improves both operator ergonomics and optimization efficiency without changing the search problem itself.

Risk/dependencies: storage choice matters. For safe single-host sequential use, journal-style persistence is the lowest-risk fit. If dashboard-first workflows are the priority, an RDB-backed design may be preferable. This should remain separate from `research_lab.db`; merging responsibilities would blur layers.

Blueprint impact: likely implementation detail unless the project wants to codify a canonical storage mode for all campaigns.

### 2. Warm-start studies from baseline and prior winners
What to change: before `study.optimize()` in `research_lab/integrations/optuna_driver.py:125-176`, seed the study with the known baseline configuration and selected prior winners from the experiment store using Optuna's warm-start APIs.

Expected gain: fewer wasted early trials, faster convergence toward relevant regions, and better reuse of the project-specific knowledge already persisted in `research_lab.db`. This is especially valuable under the project's frequent 50-trial budget.

Risk/dependencies: requires a policy for which historical candidates are eligible to seed a new study. Care is needed to avoid contaminating a materially different protocol or date-range campaign with stale priors.

Blueprint impact: implementation detail if warm-start remains optional; methodology-level if it becomes mandatory campaign policy.

### 3. Tighten ranges and complete hard constraints
What to change: review ACTIVE overrides in `research_lab/param_registry.py:38-99` and add missing runtime-relevant validation in `research_lab/constraints.py:6-52`, starting with `high_vol_leverage <= max_leverage`. Also review whether some broad floats can be narrowed based on baseline, prior winners, and strategy intent.

Expected gain: better sample efficiency, fewer semantically redundant trials, faster useful convergence, and cleaner interpretation of the Pareto frontier. In a 44-dimensional search, range quality is often more valuable than sampler novelty.

Risk/dependencies: overtightening can hide true optima. Constraint additions are low-risk when they encode behavior already implicit in runtime logic; range narrowing is medium-risk and should be evidence-led.

Blueprint impact: constraint completion is implementation detail. Significant range-policy changes may deserve tracker or blueprint documentation because they affect methodology.

### 4. A/B test multivariate TPE while keeping TPE as the default family
What to change: modify sampler initialization in `research_lab/integrations/optuna_driver.py:124` to allow an experiment branch using `TPESampler(seed=seed, multivariate=True)`.

Expected gain: better modeling of correlated parameters without changing the study's architectural role or objective definitions. This is the first sampler-level change worth testing because it matches the actual structure of the search space.

Risk/dependencies: low. The main dependency is having representative benchmark campaigns to compare against the current TPE baseline.

Blueprint impact: implementation detail.

### 5. Add Optuna-side metadata and naming
What to change: enrich `run_optuna_study()` with `study.set_metric_names(...)`, `trial.set_user_attr(...)`, and a simple callback/logging hook around `study.optimize()` in `research_lab/integrations/optuna_driver.py:125-176`.

Expected gain: better auditability, easier post-run forensics, and stronger traceability between Optuna study state and the existing experiment store. The gain is modest on its own but compounds once persistence exists.

Risk/dependencies: very low. The main dependency is deciding which metadata fields are canonical.

Blueprint impact: implementation detail.

### 6. Resolve drawdown unit alignment before further Optuna tuning
What to change: reconcile the metric definition in `backtest/performance.py:117-128` with the walk-forward gate in `research_lab/configs/default_protocol.json:9` and the corresponding comparison in `research_lab/walkforward.py:139-141`.

Expected gain: better alignment between optimization and promotion semantics. If the current threshold is effectively non-binding, then the third objective is carrying less practical weight downstream than the study definition suggests.

Risk/dependencies: medium to high because this changes candidate acceptance semantics, not just optimization mechanics. Historical comparisons may need reinterpretation.

Blueprint impact: likely yes, or at minimum an explicit methodology note.

### 7. Keep `n_jobs = 1` for now
What to change: nothing immediately. Treat parallelism as deferred until persistent Optuna storage, experiment-store concurrency hardening, and an explicit process-level execution design exist.

Expected gain: avoids introducing nondeterminism, storage races, and disappointing scaling. This is a recommendation to preserve system quality, not to add functionality.

Risk/dependencies: none immediately; the cost is only forgone speculative speedup.

Blueprint impact: none.

### 8. Defer pruner adoption until the objective shape changes
What to change: nothing immediately in code. If the project later wants pruning, redesign the objective into staged or scalar intermediate checkpoints first.

Expected gain: avoids spending implementation effort on a feature that the current multi-objective, one-shot design cannot exploit meaningfully.

Risk/dependencies: requires a methodology decision and probably a blueprint update if pursued.

Blueprint impact: yes, if adopted later.

### 9. Keep sampler-family change off the critical path
What to change: explicitly retain TPE as the default family and revisit NSGA-II, GP, or CMA-ES only after persistence, warm-starting, and range cleanup have been tested.

Expected gain: preserves focus on the biggest bottlenecks first and avoids low-yield experimentation.

Risk/dependencies: none beyond discipline.

Blueprint impact: none.

## Implementation Risk Map
### Safe to implement now
- Add dedicated Optuna persistence and resume semantics while keeping sequential execution.
- Add warm-start from baseline and selected historical winners.
- Add `study.set_metric_names()`, `trial.set_user_attr()`, and lightweight callbacks.
- A/B test multivariate TPE without changing the sampler family.
- Add missing deterministic constraints that already reflect runtime behavior, especially leverage-cap consistency.

### Requires caution but is still tractable
- Narrowing ACTIVE ranges: high upside, but only if backed by evidence from prior runs and strategy intent.
- Choosing between journal-style persistence and RDB-backed persistence: the correct answer depends on whether the immediate priority is safe local resume or broader study tooling/dashboard access.
- Changing drawdown threshold units or interpretation: this can alter promotion behavior and invalidate comparisons to prior campaigns.
- Revisiting frozen crowded-market parameters: possible future upside, but not before the current search surface is made more efficient.

### Requires architectural or methodology decision
- Making parallel optimization a standard operating mode.
- Introducing pruners into the current multi-objective, one-shot objective.
- Switching the default sampler family away from TPE.
- Allowing LLM inside the trial loop as a sampler or parameter proposer.
- Unfreezing composite/session/EMA architecture parameters that currently encode strategy shape, not just numeric tuning.

## Open Questions for Claude Code / User
1. Is `max_drawdown_pct_per_window: 50.0` intentionally expressed against a `0..1` drawdown metric, or is this an unnoticed unit mismatch in the walk-forward gate?
2. Is the next priority safe single-host resume/history, or immediate Optuna dashboard visibility? The storage recommendation depends on that choice.
3. Is the common `50`-trial operating budget a temporary operator default or a long-term campaign constraint? The answer affects how aggressively search ranges should be narrowed.
4. Should warm-starting from prior winners become canonical campaign policy, or remain an optional optimization mode?
5. Is `force_orders` still effectively unavailable in current production data, or has that freeze rationale gone stale since the last review?
6. Should `study_name`, `seed`, `config_hash`, protocol hash, source DB path, and commit SHA become first-class mandatory audit fields in persistent Optuna storage, the custom experiment store, or both?

---

## Sweep/Reclaim Analysis — Session 2026-04-09
Analysts: Codex (diagnosis) + Claude Code (audit/correction)

### Confirmed Root Cause

Primary driver: permissive level creation in `feature_engine.py:177-182`. With ATR≈$200 and tolerance=ATR×0.25=$50, a typical 50-bar 15m BTC window ($1,000-$1,500 range) produces 4-8 merged low clusters and 4-8 merged high clusters. The early-return architecture at `feature_engine.py:130` turns this dense cluster set into `sweep_detected=True` on 99.49% of bars.

Root cause is both: loose level definition (dominant) + early-return amplifier (secondary).

### Scenario Decision: B (restore sweep as rare event)

Scenario A rejected. `reclaim_detected=7.16%` (~7 bars/day) is semantically diluted — it represents "rejection candle near a noisy local cluster," not a blueprint-style stop hunt. The blueprint (`BLUEPRINT_V1.md:60`) defines the edge as liquidity sweep + reclaim + context, not generic cluster rejection.

Optuna evidence: `baseline-v3-smoke` did not naturally converge toward rare-sweep semantics (`equal_level_tol_atr=0.21`, `equal_level_lookback=105`, `weight_sweep_detected=3.8`). Optuna learns a threshold offset, not sweep quality, because `weight_sweep_detected` and `weight_reclaim_confirmed` are constant intercepts once scoring runs.

### Corrected Plan: SWEEP-RECLAIM-FIX-V1

Status: **AWAITING RUN3_DONE** — do not start until Cascade reports run #3 complete.

**Scope (confirmed):**
1. Add `level_min_age_bars: int` to `FeatureEngineConfig` — level only counts if N bars elapsed between first and last hit in the cluster (B5, architectural)
2. Make `min_hits` configurable in `FeatureEngineConfig` — raise default from 2 to 3; expose in `StrategyConfig` (B3, architectural)
3. Add both params to `param_registry.py` as ACTIVE with curated ranges
4. Keep B1 (`equal_level_tol_atr`), B2 (`equal_level_lookback`), B4 (`sweep_buf_atr`) searchable — already are
5. Do NOT remove `weight_sweep_detected` / `weight_reclaim_confirmed` from confluence — see open decision below
6. After fix: clean baseline run + new Optuna campaign

**What this milestone does NOT do:** It does not resolve the gate-vs-score architectural question. That is an explicit open decision.

**Run #3 artifact interpretation note:** When evaluating Run #3 Pareto candidates, flag any candidate with `weight_sweep_detected > 2.0` as a threshold-chaser, not a real strategy discovery. High sweep weight in a degraded-sweep regime signals the optimizer compensating for a constant, not learning signal quality.

### Corrected Codex Note on Weight Semantics

Claude Code's initial statement — "after B5+B3, `weight_sweep_detected` becomes valid evidence again" — was incorrect. Codex correctly identified: because `signal_engine.py:49-52` gates on both flags *before* `_confluence_score()` runs, both weights are **constant intercepts on every scored candidate**, regardless of how rare sweep becomes. Making sweep rare changes how often we enter scoring, not what happens inside it. The weights do not become discriminating by fixing the feature.

### Open Methodological Decisions (explicit, not deferred silently)

**Decision 1 — Gate-vs-Score architecture**

Current state: `weight_sweep_detected=1.25` and `weight_reclaim_confirmed=1.25` are added unconditionally inside `_confluence_score()` because both are hard-gated before scoring. They are threshold offsets, not evidence weights.

Options:
- **Option A:** Remove both from confluence scoring. Hard gates remain. Confluence threshold drops by 2.50 max; lower `confluence_min` accordingly. Optuna no longer wastes search budget on two constant parameters.
- **Option B:** Keep in confluence, replace with quality-based scoring. E.g., replace binary `weight_sweep_detected` with a continuous `sweep_depth_pct`-derived score. This requires objective redesign.
- **Option C:** Keep current architecture — accept that they are offsets, freeze their weights at 0.0 in Optuna search to reduce dimensionality.

**This decision requires user approval before implementation.** Claude Code recommends Option A as the lowest-risk cleanup consistent with blueprint intent, but it alters confluence semantics and requires `confluence_min` recalibration.

**Decision 2 — force_orders data gap**

`force_orders` table has 0 rows in production DB. Consequences:
- `force_order_spike` = always False → `POST_LIQUIDATION` regime never fires
- `weight_force_order_spike=0.40` is permanently locked out of confluence scoring
- `weight_regime_special=0.35` for LONG (POST_LIQ bonus) is permanently locked

`weight_force_order_spike` is already frozen in `param_registry.py`, but the wasted confluence ceiling (~0.75 points) affects what `confluence_min=3.0` means in practice. Verify: does `market_data.py` populate `force_order_events_60s` from WS feed, or is it always empty because `force_orders` DB table is unpopulated?

**Decision 3 — B6 HTF levels (deferred, not discarded)**

Using 4h/1h candles for level detection would produce structurally rarer, more meaningful levels. Strong semantic alignment with blueprint intent. Not in SWEEP-RECLAIM-FIX-V1 scope because it is a larger redesign with high trade-count risk. Revisit after B5+B3 are in place and a new campaign produces enough trades to evaluate.

### Proposed Handoff: SWEEP-RECLAIM-FIX-V1

To be issued after Run #3 completes and artifacts are evaluated.

```
## CLAUDE HANDOFF -> CODEX

### Checkpoint
- Last commit: [to be filled after RUN3_DONE]
- Branch: main
- Working tree: clean

### Before you code
Read these files (mandatory):
1. docs/BLUEPRINT_V1.md — section 3.3 (core edge definition)
2. docs/OPTUNA_UTILITY_REPORT.md — section "Sweep/Reclaim Analysis 2026-04-09"
3. AGENTS.md — discipline + workflow rules
4. docs/MILESTONE_TRACKER.md — current status

### Milestone: SWEEP-RECLAIM-FIX-V1
Scope: feature_engine.py, settings.py, research_lab/param_registry.py

Deliverables:
1. Add `level_min_age_bars: int = 5` to FeatureEngineConfig (feature_engine.py)
   - A cluster of prices qualifies as a level only if the time span between
     first and last candle in the cluster is >= level_min_age_bars bars
   - Modify detect_equal_levels() or detect_sweep_reclaim() to enforce this
2. Make `min_hits: int = 3` configurable in FeatureEngineConfig (was hardcoded at 2)
   - Pass through from StrategyConfig or FeatureEngineConfig consistently
3. Add both to param_registry.py as ACTIVE:
   - level_min_age_bars: int, range 2-20, step 1
   - min_hits: int (or expose existing equal_level param), range 2-5, step 1
4. Smoke test: verify sweep_detected rate drops below 50% on any historical
   dataset with default parameters (level_min_age_bars=5, min_hits=3,
   equal_level_tol_atr=0.25, equal_level_lookback=50)

Target files: core/feature_engine.py, settings.py, research_lab/param_registry.py

### Known Issues
| # | Issue | Blocking for this milestone? |
|---|---|---|
| 1 | weight_sweep_detected / weight_reclaim_confirmed are constant intercepts | NO — open decision, do not touch |
| 2 | force_orders table 0 rows | NO — separate investigation |
| 3 | gate-vs-score architecture decision pending | NO — explicitly deferred |

-> Do not touch signal_engine.py confluence weights in this milestone.
-> Do not touch walkforward protocol or Optuna driver in this milestone.

### Commit discipline
- WHAT / WHY / STATUS in every commit message
- Do NOT self-mark as done. Claude Code audits after push.
```
