# BTC Bot Decisions Log

This file records operator decisions and their rationale. It is not a live status
document. Runtime facts live in the production database and should be checked with
`python scripts/db_status.py` on the production server.

## 2026-05-20 - Prepare ETH shadow depth update from audited optimization
**Decision:** Prepare `ETH_SHADOW_DEPTH_PARAMETER_UPDATE_V1` as a small
sidecar-only checkpoint for Claude Code audit.

**Reason:** `ETH_ASSET_SPECIFIC_OPTIMIZATION_V1` passed audit and selected
`ETH_OPT_D0.00750`. Because ETH is still `shadow_no_orders`, applying the
threshold only to sidecar diagnostics improves forward evidence quality without
touching BTC PAPER, M4, execution, or production storage.

**Result:** `default_symbol_configs()` now sets ETH `min_sweep_depth_pct` to
`0.0075`. BTC and SOL remain at the frozen trial-00095 transfer value
`0.00649`. Tests explicitly enforce this split.

**Consequences:**
- No PAPER, LIVE, execution, runtime, M4, or production DB change is approved.
- Server sidecar behavior changes only after Claude Code audit PASS and a later
  operator pull.
- SOL remains unchanged until a separate audited SOL parameter milestone exists.

**Related:** `research_lab/shadow_signal_cycle.py`;
`research_lab/hypotheses/active/eth_shadow_depth_parameter_update.json`;
`docs/analysis/ETH_ASSET_SPECIFIC_OPTIMIZATION_2026-05-20.md`.

## 2026-05-20 - Run ETH depth-only asset-specific optimization offline
**Decision:** Mark `ETH_ASSET_SPECIFIC_OPTIMIZATION_V1` ready for Claude Code
audit as an offline Research Lab checkpoint.

**Reason:** Frozen BTC trial-00095 transferred strongly to ETH, but ETH may
prefer a different sweep-depth threshold. The first ETH-specific pass should be
small and auditable: depth-only, fixed grid, train-only selection, OOS gates,
and no runtime/sidecar/M4 changes.

**Result:** Three depth variants were evaluated against the audited ETH dataset.
The train-selected champion is `ETH_OPT_D0.00750`, changing only
`min_sweep_depth_pct` to `0.0075`. OOS improved from baseline ER `1.766` and
PF `2.73` to ER `2.190` and PF `3.50`, with max DD improving from `6.04%` to
`4.88%`. 2x-cost OOS ER is `1.808`, and all four yearly folds remain positive.

**Consequences:**
- This is an offline candidate for audit, not a parameter promotion.
- No change to BTC PAPER, M4, sidecar, runtime, `settings.py`, or production DB.
- A later audited milestone is required before any ETH-specific parameter can
  affect shadow, PAPER, or runtime behavior.

**Related:** `research_lab/eth_asset_specific_optimization.py`;
`docs/analysis/ETH_ASSET_SPECIFIC_OPTIMIZATION_2026-05-20.md`;
`research_lab/hypotheses/active/eth_asset_specific_optimization.json`.

## 2026-05-20 - Move real-shadow portfolio decisions onto audited gate contract
**Decision:** Prepare `MULTI_ASSET_SHADOW_PORTFOLIO_GATE_V1` as a code-only
checkpoint that makes real-shadow BTC/ETH/SOL decisions use
`ResearchPortfolioGate`.

**Reason:** The experimental multi-asset branch should approach runtime
integration gradually. Reusing the audited Research Lab portfolio gate is safer
than maintaining separate ad hoc gating in the sidecar. This aligns the shadow
path with the future runtime shape without promoting anything into `core/`,
`orchestrator.py`, `settings.py`, production storage, or execution.

**Result:** The sidecar real-shadow cycle now adapts generated shadow candidates
to `PortfolioSignal` and evaluates them through the research-only portfolio
contract. BTC/ETH/SOL ordering is deterministic, SOL remains `shadow_no_orders`
at 0.15% candidate risk, and order placement remains impossible.

**Consequences:**
- No systemd change or deployment is included in this checkpoint.
- No ETH/SOL PAPER or LIVE approval.
- No change to BTC PAPER or M4 source data.
- Claude Code audit is required before production can pull and use this
  updated real-shadow gate.

**Related:** `research_lab/models/portfolio_state.py`;
`research_lab/shadow_signal_cycle.py`;
`tests/test_portfolio_state.py`;
`tests/test_shadow_real_signal_cycle.py`.

## 2026-05-20 - Prepare real shadow signal cycle before heartbeat checkpoint
**Decision:** Start coding `MULTI_ASSET_SHADOW_REAL_SIGNAL_CYCLE_V1` before the
24h heartbeat checkpoint, but keep it code-only and disconnected from the
deployed systemd timer.

**Reason:** The user wants to avoid passive waiting while the operational
heartbeat continues. Internal consultation agreed this is safe only if Phase 2
adds a separate manual/auditable mode and does not replace `--cycle-once`,
change `multi-asset-shadow.service`, touch BTC PAPER, or alter what BTC M4
measures.

**Result:** Phase 2 introduces a self-contained real-shadow diagnostic path
under `research_lab/` with a fake-provider test harness and a separate CLI flag.
The active production timer remains on `sidecar_main.py --cycle-once`, which
continues to write heartbeat rows only.

**Consequences:**
- No deployment change is approved.
- No market-data shadow mode is connected to systemd.
- No orders, execution imports, runtime DB writes, or M4 query changes are in
  scope.
- Phase 2 must be audited before any timer/service command can be changed.

**Related:** `research_lab/shadow_signal_cycle.py`;
`research_lab/shadow_orchestrator.py`;
`docs/operations/MULTI_ASSET_SHADOW_SIDECAR_RUNBOOK.md`.

## 2026-05-20 - Design isolated multi-asset shadow sidecar before M4 completes
**Decision:** Create `MULTI_ASSET_SHADOW_SIDECAR_DESIGN_V1` as a design-only
milestone. The sidecar direction is allowed only as an isolated observer that
cannot change what BTC M4 measures.

**Reason:** The user wants early forward evidence for multi-asset behavior
before the BTC M4 checkpoint finishes. Direct runtime integration would
contaminate M4 because M4 is measuring the current BTC PAPER trial-00095 runtime
under a frozen config. A sidecar can preserve M4 integrity if it runs as a
separate process, writes to a separate database, places zero orders, and has no
write path to production storage.

**Consequences:**
- BTC M4 remains BTC-only and sourced from the existing BTC PAPER runtime rows.
- Sidecar design requires a separate service/process, separate lock, separate
  DB under `research_lab/shadow/`, separate logs, and symbol-explicit rows.
- Sidecar may not write to `storage/btc_bot.db`, restart `btc-bot.service`, read
  trading keys, or import an order/execution path.
- ETH/SOL/BTC shadow rows cannot be aggregated into BTC M4 conclusions.
- Resource guards are mandatory: 12 GB disk floor, lower priority, recommended
  memory and CPU caps.
- This decision does not approve sidecar implementation, server deployment,
  ETH/SOL PAPER, LIVE, runtime integration, or threshold changes.

**Related:** `docs/BLUEPRINT_MULTI_ASSET_SHADOW_SIDECAR.md`;
`docs/MILESTONE_TRACKER.md`; BTC M4 checkpoint planned for 2026-06-13.

## 2026-05-20 - Implement dry-run-only multi-asset shadow sidecar infrastructure
**Decision:** Mark `MULTI_ASSET_SHADOW_SIDECAR_IMPLEMENTATION_V1` ready for
Claude Code audit as an implementation checkpoint, limited to dry-run
infrastructure.

**Reason:** The audited sidecar design allows early forward observation only if
the implementation proves hard isolation first. This checkpoint builds the
minimum auditable infrastructure before any service deployment: separate
entrypoint, separate lock, separate DB, safe path guard, schema, order-path
guard, resource guard, dry-run, and tests.

**Result:** The implementation adds `sidecar_main.py`,
`research_lab/shadow_orchestrator.py`, `research_lab/shadow_schema.py`,
`docs/operations/MULTI_ASSET_SHADOW_SIDECAR_RUNBOOK.md`, and focused tests.
Dry-run writes only to a DB under `research_lab/shadow/`, inserts symbol-explicit
stub decisions and a nested near-miss payload, records a resource sample, and
returns `production_db_touched=false`.

**Validation:** Focused tests passed (`9 passed` with `--no-cov`), compileall
passed for the new modules/tests, and a temporary dry-run produced 3 decision
rows, 1 near-miss row, and 1 resource row without touching production storage.

**Consequences:** This still does not approve systemd deployment, a long-running
sidecar process, ETH/SOL PAPER, LIVE trading, runtime integration, threshold
changes, or any change to BTC PAPER/M4. A separate deployment milestone and
audit remain required before a server-side sidecar can run continuously.

**Related:** `sidecar_main.py`; `research_lab/shadow_orchestrator.py`;
`research_lab/shadow_schema.py`;
`docs/operations/MULTI_ASSET_SHADOW_SIDECAR_RUNBOOK.md`;
`docs/MILESTONE_TRACKER.md`.

## 2026-05-20 - Prepare one-shot timer deployment files for sidecar heartbeat
**Decision:** Mark `MULTI_ASSET_SHADOW_SIDECAR_DEPLOYMENT_V1` ready for Claude
Code audit as Phase 1 operational heartbeat implementation. This prepares
deployment artifacts but does not deploy them.

**Reason:** The safest pre-M4 deployment shape is a systemd timer that runs a
fresh one-shot process every 15 minutes. This validates process isolation,
resource guards, production DB non-contamination, and operator monitoring before
adding market data or real signal generation.

**Result:** `--cycle-once` now performs one operational heartbeat cycle:
sidecar lock, resource guard, production DB before/after signature check,
sidecar DB writes only, three BTC/ETH/SOL stub decision rows, and exit. The
systemd unit/timer, deploy script, status script, and runbook are prepared for
audit.

**Validation:** Focused sidecar tests passed (`15 passed` with `--no-cov`),
compileall passed for the sidecar modules/tests, and a temporary manual
`--cycle-once` returned `production_db_touched=false`, `decision_rows=3`,
`near_miss_rows=0`, and `resource_rows=1`.

**Consequences:** This checkpoint still does not install or start the timer on
the production server. Real market data, signal generation, sweep/reclaim
detection, near-miss diagnostics from live data, ETH/SOL PAPER, and runtime
integration remain deferred to later audited milestones.

**Related:** `multi-asset-shadow.service`; `multi-asset-shadow.timer`;
`scripts/deploy_shadow_sidecar.sh`; `scripts/shadow_sidecar_status.sh`;
`research_lab/shadow_orchestrator.py`;
`docs/operations/MULTI_ASSET_SHADOW_SIDECAR_RUNBOOK.md`.

## 2026-05-20 - Design SOL shadow contract before any implementation
**Decision:** Mark `SOL_SHADOW_CONTRACT_DESIGN_V1` ready for Claude Code audit
as a design-only milestone.

**Reason:** SOL transfer, forensic, and risk-policy diagnostics now support SOL
as a promising but smaller risk sleeve. Before any implementation or shadow
deployment, the project needs a contract that defines SOL setup isolation,
candidate risk cap, diagnostics, checkpoints, and promotion blocks.

**Design result:** The blueprint requires SOL to start as `shadow_no_orders`,
keeps SOL setup-isolated with `strategy_profile = trial_00095_transfer`, sets
the candidate risk policy to 0.15% equity per trade, requires symbol-explicit
diagnostics and nested near-miss depth, and defines Day 3, Day 14, and Day 30
shadow checkpoints. SOL PAPER remains blocked until future shadow evidence,
audit, and user approval.

**Consequences:** No runtime behavior changes. No SOL shadow deployment. No SOL
PAPER approval. No threshold change. A future implementation milestone may use
this blueprint only after audit and user approval.

**Related:** `docs/BLUEPRINT_SOL_SHADOW_CONTRACT.md`.

## 2026-05-20 - Test SOL risk-policy frontier before any shadow design
**Decision:** Mark `SOL_RISK_POLICY_DIAGNOSTIC_V1` ready for Claude Code audit.

**Reason:** SOL drawdown forensic analysis showed that the edge is real but
needs smaller sizing than BTC/ETH. The next safe step is to test predeclared
SOL risk caps while keeping trial-00095 entries, exits, thresholds, and BTC/ETH
risk unchanged.

**Result:** SOL risk caps 0.15%, 0.20%, and 0.25% pass all 6 risk-policy gates.
0.30% fails the 6% capital DD gate, and 0.35% fails both capital DD and
DD-increase gates. The predeclared selection rule chooses 0.15% because it has
the lowest capital DD among passing variants. All variants preserve the same
entry population and R-space metrics: 1,545 approved portfolio trades, 905 SOL
trades, ER 2.056, PF 3.49.

**Consequences:** Builder verdict is `SOL_APPROVED_AT_RISK_0.0015` for offline
research policy only. This does not approve SOL shadow, SOL PAPER, runtime
integration, or any production setting change. If Claude Code audit passes, the
next work can be a design-only SOL shadow/risk-policy contract.

**Related:** `research_lab/sol_risk_policy_diagnostic.py`;
`research_lab/hypotheses/active/sol_risk_policy_diagnostic.json`;
`docs/analysis/SOL_RISK_POLICY_DIAGNOSTIC_2026-05-20.md`.

## 2026-05-20 - Diagnose SOL drawdown before any shadow design
**Decision:** Mark `SOL_DRAWDOWN_FORENSIC_DIAGNOSTIC_V1` ready for Claude Code
audit as a research-only diagnostic.

**Reason:** `SOL_TRIAL_00095_TRANSFER_FEASIBILITY_V1` confirmed a strong SOL
edge but failed the standalone drawdown gate. Before considering SOL shadow or
runtime design, the project needs to know whether the drawdown is crash/regime
specific, whether portfolio vetoes already control it, and whether a
SOL-specific risk cap could reduce capital drawdown without changing entries.

**Result:** SOL standalone max DD is 32.72R with a 21-loss max streak. The
offline portfolio gate reduces SOL to 905 approved trades with ER 2.120, PF
3.41, max DD 21.31R, and max loss streak 15. Risk is concentrated in 2022 and
in downtrend/crowded/normal regimes; uptrend SOL is strong. Daily R correlation
with BTC and ETH remains low. SOL risk-cap sensitivity does not change R-space
trade count but reduces capital drawdown from 6.81% at 0.35% risk to 5.32% at
0.20% risk.

**Consequences:** No SOL shadow or runtime approval. No entry/threshold tuning.
If audit passes, the next safe work is a separately predeclared SOL risk-policy
diagnostic/design milestone, not a deployment milestone.

**Related:** `research_lab/sol_drawdown_forensic_diagnostic.py`;
`research_lab/hypotheses/active/sol_drawdown_forensic_diagnostic.json`;
`docs/analysis/SOL_DRAWDOWN_FORENSIC_DIAGNOSTIC_2026-05-20.md`.

## 2026-05-20 - Run SOL trial-00095 transfer feasibility
**Decision:** Mark `SOL_TRIAL_00095_TRANSFER_FEASIBILITY_V1` ready for Claude
Code audit after offline replay with frozen `optuna-default-v3-trial-00095`
parameters.

**Reason:** SOL data feasibility, pilot backfill, and full dataset audit all
passed. The next safe question is whether the existing BTC/ETH sweep-reclaim
edge transfers to SOL and whether SOL improves the existing BTC+ETH offline
portfolio, before any SOL shadow or runtime design is considered.

**Result:** SOL standalone produced 1,201 trades with ER 2.141, PF 3.42, and
4/4 positive walk-forward folds. However, the predeclared standalone max
drawdown gate failed at 15.46% versus the 12% threshold. BTC+ETH+SOL portfolio
replay passed portfolio gates with 1,545 approved trades, ER 2.056, PF 3.49,
max DD 19.47R, and 905 approved SOL trades.

**Consequences:** Builder verdict is `SOL_TRANSFER_HYPOTHESIS_FAILED` because
the standalone transfer protocol failed one hard gate. Do not tune SOL
thresholds or relax drawdown gates inside this milestone. Claude Code audit
should decide whether to close as failed, classify as promising/inconclusive
for a separate risk-framed follow-up, or request fixes. No SOL shadow, SOL
PAPER, runtime integration, production DB change, or threshold change is
approved.

**Related:** `research_lab/sol_trial_00095_transfer_feasibility.py`;
`research_lab/hypotheses/active/sol_trial_00095_transfer_feasibility.json`;
`docs/analysis/SOL_TRIAL_00095_TRANSFER_FEASIBILITY_2026-05-20.md`.

## 2026-05-19 - Complete SOL historical backfill pilot
**Decision:** Mark `SOL_HISTORICAL_BACKFILL_PILOT_V1` ready for Claude Code
audit.

**Reason:** SOL data feasibility passed, but a full SOL backfill should not be
scheduled until archive ingestion mechanics, disk slope, aggTrade streaming,
and quality checks are validated on a short separate research snapshot.

**Result:** The 3-day SOL pilot completed with 0.00% missingness across 15m
candles, 4h candles, funding, open interest, aggtrade 60s buckets, and aggtrade
15m buckets. Duplicate groups were 0, OHLC/zero-volume errors were 0, failed
days were 0, and disk guard stayed above the 12 GB minimum. Pilot DB size was
0.77 MB, implying a linear full 2022-2026 estimate of about 0.39 GB.

**Consequences:** SOL strategy transfer research is still not approved. The
next step, if audit passes, is a full `SOL_HISTORICAL_BACKFILL_DATASET_V1`
milestone with resumable checkpoints and a separate audit. No runtime, SOL
shadow, SOL PAPER, production DB, or threshold change is approved.

**Related:** `research_lab/backfill_sol_historical_data.py`;
`research_lab/hypotheses/active/sol_historical_backfill_pilot.json`;
`docs/analysis/SOL_HISTORICAL_BACKFILL_PILOT_2026-05-19.md`.

## 2026-05-19 - Start SOL data feasibility
**Decision:** Start `SOL_DATA_FEASIBILITY_V1` as a Research Lab data-quality
diagnostic while BTC PAPER, BTC M4, and ETH design remain unchanged.

**Reason:** SOLUSDT is the strongest next candidate after ETH for testing
trial-00095 transfer because it is liquid, volatile, and likely to produce
meaningful sweep/reclaim behavior. Before any backfill or strategy test, the
project must verify SOL source availability and sample quality.

**Result:** Recent SOL candles, funding, open interest, book ticker, and archive
probes are available and clean enough to justify a guarded backfill pilot.
Historical archive probes for 2022-2025 pass for klines, metrics, and
aggTrades. REST aggTrades recent sampling is limited for SOL activity, so the
future backfill must rely on daily aggTrades archives rather than REST window
sampling.

**Consequences:** No SOL strategy research is approved yet. No market data was
persisted. No runtime, SOL shadow, SOL PAPER, threshold change, or production DB
change is approved. If Claude Code audit passes, the next step can be
`SOL_HISTORICAL_BACKFILL_PILOT_V1`.

**Related:** `research_lab/analysis_sol_data_feasibility.py`;
`research_lab/hypotheses/active/sol_data_feasibility.json`;
`docs/analysis/SOL_DATA_FEASIBILITY_2026-05-19.md`.

## 2026-05-19 - Define ETH near-miss monitoring before ETH PAPER
**Decision:** Create `ETH_NEAR_MISS_MONITORING_DESIGN_V1` as a design-only
contract for future ETH shadow/no-order monitoring.

**Reason:** BTC M4 answers a BTC-specific threshold stability question. ETH has
audited offline transfer and portfolio evidence, but its live sweep-depth
distribution and near-miss behavior must be observed separately before ETH
PAPER orders are considered. ETH monitoring must not contaminate BTC M4
conclusions.

**Design result:** Future ETH runtime starts as `shadow_no_orders`; it collects
symbol-explicit ETH decision outcomes, near-miss diagnostics, governance shadow
decisions, and portfolio shadow decisions while placing zero ETH orders. The
design requires Day 3, Day 14, and Day 30 checkpoints and blocks ETH threshold
changes behind a separate offline `ETH_SWEEP_DEPTH_THRESHOLD_STABILITY_V1`
milestone.

**Consequences:** No runtime behavior changes. No ETH PAPER approval. No
threshold change. BTC M4 remains the deployment blocker for multi-asset runtime
changes through the 2026-06-13 checkpoint.

**Related:** `docs/blueprints/ETH_NEAR_MISS_MONITORING_DESIGN_V1_2026-05-19.md`;
`research_lab/hypotheses/active/eth_near_miss_monitoring_design.json`.

## 2026-05-19 - Run offline full-pipeline BTC+ETH replay before M4
**Decision:** Continue with `MULTI_ASSET_FULL_PIPELINE_REPLAY_V1` as an
offline-only Path B checkpoint while M4 monitoring and BTC PAPER continue
unchanged.

**Reason:** Phase 2 artifact-driven portfolio replay passed audit, but a
source-pipeline regeneration checkpoint further reduces dependency on frozen
trade artifacts. This validates that the current single-symbol replay pipeline
can regenerate BTC and ETH trial-00095 trade lists, then feed them into the
same audited offline portfolio gate.

**Result:** The pipeline regenerated 274 BTC trades and 544 ETH trades. The
portfolio gate approved 696 trades with ER 1.955, PF 3.60, max DD 13.74R, and
50.7% win rate. This matches the Phase 2 stateful replay result and supports
the builder verdict `PASS_FULL_PIPELINE_REPLAY_FOR_RUNTIME_SCOPING`.

**Consequences:** No production behavior changes. No ETH PAPER approval. No
runtime implementation approval. Runtime integration remains blocked until M4
checkpoint and later audited runtime milestones.

**Related:** `research_lab/multi_asset_full_pipeline_replay.py`;
`docs/analysis/MULTI_ASSET_FULL_PIPELINE_REPLAY_2026-05-19.md`;
`tests/test_multi_asset_full_pipeline_replay.py`.

## 2026-05-19 - Start offline multi-asset state and backtest implementation
**Decision:** Start `MULTI_ASSET_STATE_AND_BACKTEST_IMPLEMENTATION_V1` in
offline-only mode while BTC PAPER and M4 monitoring continue unchanged.

**Reason:** Claude Code confirmed that parallel offline implementation is safe
if state models stay under `research_lab/models` and no runtime path is touched.
The first implementation checkpoint should prove state isolation and portfolio
gate behavior before building a full replay harness.

**Phase 1 result:** Added research-only `SymbolRiskState`,
`PortfolioRiskState`, `PortfolioRiskConfig`, `ResearchPortfolioGate`,
deterministic same-bar ordering, cap/veto logic, and recovery-state simulation.
Tests cover same-bar `allow_both`, risk cap veto, directional notional veto,
symbol loss-streak isolation, symbol cooldown isolation, portfolio emergency
stop, and recovery reconstruction.

**Consequences:** No production behavior changes. No ETH PAPER approval. No
runtime implementation approval. Next work may add an offline portfolio replay
harness only.

**Related:** `research_lab/models/portfolio_state.py`;
`tests/test_portfolio_state.py`;
`research_lab/hypotheses/active/multi_asset_state_and_backtest_implementation.json`.

## 2026-05-19 - Complete offline portfolio replay Phase 2 checkpoint
**Decision:** Mark the artifact-driven `PORTFOLIO_REPLAY_V1` harness as ready
for Claude Code audit under `MULTI_ASSET_STATE_AND_BACKTEST_IMPLEMENTATION_V1`.

**Reason:** Phase 2 validates the offline `SymbolRiskState`,
`PortfolioRiskState`, and `ResearchPortfolioGate` contracts against frozen BTC
and ETH trial-00095 trade artifacts with stateful cap, cooldown, loss-streak,
and drawdown veto behavior. This is the required bridge between simple artifact
stitching and any later full pipeline replay or runtime implementation.

**Result:** Stateful replay approved 696 trades with ER 1.955, PF 3.60, max DD
13.74R, and 50.7% win rate. It vetoed 122 signals through machine-readable
reasons, mostly symbol weekly hard stops, position caps, daily hard stops, and
cooldowns. Compared with the prior stitching diagnostic, the replay has fewer
trades but slightly higher ER/PF and materially lower max DD.

**Important refinement:** Initial replay showed that permanent loss-streak
vetoes could lock the portfolio indefinitely. The research contract now treats
loss-streak pauses as timed pauses using the configured 125-minute pause window,
matching the intended cooldown-style safety behavior.

**Consequences:** No production behavior changes. No ETH PAPER approval. No
runtime implementation approval. Full feature/regime/signal replay and any
runtime integration remain future milestones after audit and M4 checkpoint
decision.

**Related:** `research_lab/portfolio_replay_harness.py`;
`research_lab/models/portfolio_state.py`;
`tests/test_portfolio_replay_harness.py`;
`docs/analysis/PORTFOLIO_REPLAY_V1_2026-05-19.md`.

## 2026-05-19 - Define multi-asset portfolio architecture before implementation
**Decision:** Complete `MULTI_ASSET_PORTFOLIO_ARCHITECTURE_V1` as a design-only
milestone after internal consultation and the audited portfolio diagnostic.

**Reason:** BTC+ETH trial-00095 has validated portfolio evidence, but the
current runtime was built as a single-symbol system. Implementation requires
explicit contracts for per-symbol pipelines, portfolio risk, persistent
symbol/portfolio state, recovery, same-bar conflict handling, and backtest
parity. Skipping design would risk hidden global-state coupling or layer leaks.

**Consequences:** No runtime code is changed. No ETH PAPER or multi-asset PAPER
is approved. The design sets conservative defaults for a future implementation:
0.35% risk per trade per symbol, 0.70% total open risk, max 2 open positions
globally, max 1 per symbol, and `allow_both` only when portfolio caps pass.
Future implementation remains blocked until Claude Code audit and the M4
checkpoint decision.

**Related:** `docs/blueprints/MULTI_ASSET_PORTFOLIO_ARCHITECTURE_V1_2026-05-19.md`;
`docs/analysis/MULTI_ASSET_PORTFOLIO_DIAGNOSTIC_2026-05-19.md`.

## 2026-05-19 - Start BTC+ETH portfolio diagnostic before architecture design
**Decision:** Start `MULTI_ASSET_PORTFOLIO_DIAGNOSTIC_V1` after Claude Code
passed the ETH transfer feasibility audit.

**Reason:** ETH transfer evidence is strong, but runtime architecture should not
be designed from standalone metrics alone. The next research-only step is to
measure BTC+ETH interaction: daily PnL correlation, same-15m signal overlap,
combined R drawdown, concentration, and simple conflict policies.

**Consequences:** This milestone may recommend a later multi-asset architecture
design if gates pass. It does not approve ETH runtime trading, multi-asset PAPER,
portfolio execution, or any runtime code change.

**Result:** The `allow_both` offline portfolio combined 274 BTC full-replay
trades with 544 ETH transfer trades for 818 total trades, ER 1.910, PF 3.49,
max DD 19.22R, daily PnL correlation 0.051, same-15m overlap 2.8%, and top
month concentration 7.0%. Builder verdict:
`PASS_PORTFOLIO_DIAGNOSTIC_FOR_ARCHITECTURE_DESIGN`.

**Next:** Request Claude Code audit. If audit passes, schedule architecture
design for aggregate portfolio risk and conflict handling, not runtime
deployment.

**Related:** `research_lab/multi_asset_portfolio_diagnostic.py`;
`research_lab/hypotheses/active/multi_asset_portfolio_diagnostic.json`;
`docs/analysis/MULTI_ASSET_PORTFOLIO_DIAGNOSTIC_2026-05-19.md`.

## 2026-05-19 - Start ETH trial-00095 transfer feasibility
**Decision:** Start `ETH_TRIAL_00095_TRANSFER_FEASIBILITY_V1` after Claude Code
passed the ETH historical dataset audit.

**Reason:** ETHUSDT now has an audited 2022-2026 research snapshot with complete
15m/4h candles, funding, OI, and aggregated flow. The safest next question is
whether the already-known BTC sweep/reclaim edge transfers to ETH using frozen
`optuna-default-v3-trial-00095` parameters, before considering any ETH-specific
optimization or multi-asset runtime design.

**Consequences:** This milestone is research-only. It changes only the
research-only symbol setting to `ETHUSDT`, derives 1h replay candles from 15m
inside a temporary DB, and does not touch BTC PAPER, M4 monitoring, runtime,
`core/**`, `execution/**`, `orchestrator.py`, or `settings.py`.

**Result:** Server replay produced 544 ETH trades from 2022-01-01 through
2026-03-28 with ER 1.804, PF 2.81, max DD 6.72%, 4/4 positive chronological
folds, and ER 1.422 at 2x cost. Builder verdict:
`PASS_TRANSFER_CANDIDATE_FOR_AUDIT`.

**Next:** Request Claude Code audit before treating this as decision-grade
evidence for any follow-up multi-asset research or architecture work.

**Related:** `research_lab/eth_trial_00095_transfer_feasibility.py`;
`research_lab/hypotheses/active/eth_trial_00095_transfer_feasibility.json`;
`docs/analysis/ETH_TRIAL_00095_TRANSFER_FEASIBILITY_2026-05-19.md`.

## 2026-05-19 - Complete ETH historical dataset backfill
**Decision:** Mark `ETH_HISTORICAL_BACKFILL_DATASET_V1` as complete and ready for Claude Code dataset audit.

**Reason:** The guarded server backfill completed all 1547 daily checkpoints from 2022-01-01 through 2026-03-27 with 0 failed days. The final separate research snapshot is 374.81 MB, disk remained safely above the 12 GB guard, duplicate groups are 0, candle missingness is 0.00%, OI missingness is 0.03%, and aggtrade 60s missingness is 0.01%.

**Consequences:** ETH strategy transfer research is still not approved. The next step is Claude Code audit of the dataset. If audit passes, schedule a separate `ETH_TRIAL_00095_TRANSFER_FEASIBILITY_V1` milestone.

**Related:** `docs/analysis/ETH_HISTORICAL_BACKFILL_DATASET_2026-05-18.md`; `research_lab/snapshots/ethusdt_2022_2026_dataset_v1.db` on the production server.

## 2026-05-18 - Prepare ETH full dataset backfill as resumable guarded job
**Decision:** Implement `ETH_HISTORICAL_BACKFILL_DATASET_V1` as a resumable daily-checkpoint runner before starting the full 2022-2026 ETH dataset job.

**Reason:** The pilot proved storage footprint is small after aggregation, but full historical ingestion is still a long-running data job. Daily checkpoints, disk guards, separate research snapshot output, and explicit partial/final reports are required so the job can be run safely in chunks without touching the production runtime database.

**Consequences:** ETH strategy transfer research remains blocked until the full dataset is materialized and audited. Running the dataset job should use `nice`/`ionice` on the server and can be resumed with `--max-days` chunks.

**Related:** `research_lab/eth_historical_backfill_dataset.py`; `research_lab/hypotheses/active/eth_historical_backfill_dataset.json`.

## 2026-05-18 - ETH full backfill is operationally plausible with streaming archives
**Decision:** Complete `ETH_HISTORICAL_BACKFILL_PILOT_V1` as a Research Lab data-engineering pilot, not an ETH strategy research approval.

**Reason:** The pilot wrote a separate ETHUSDT SQLite snapshot for 2026-05-15 to 2026-05-18, streamed daily Binance Vision ZIPs, discarded raw archives, and enforced a free-disk guard. The resulting aggregated DB was small (0.77 MB for 3 days, linear full-window estimate ~0.39 GB) with 0% missing 15m/4h candles, OI, and aggtrade buckets in the pilot window.

**Consequences:** A full ETH 2022-2026 backfill is operationally plausible if implemented as a resumable daily streaming job with disk guards and no raw archive retention. ETH strategy transfer research remains blocked until the full dataset is materialized and audited.

**Related:** `research_lab/eth_historical_backfill_pilot.py`; `docs/analysis/ETH_HISTORICAL_BACKFILL_PILOT_2026-05-18.md`.

## 2026-05-18 - Treat ETH multi-asset work as data-first, not strategy-first
**Decision:** Run `MULTI_ASSET_DATA_FEASIBILITY_V1` before any ETH/SOL transfer backtest.

**Reason:** The local research snapshot is BTC-only, so testing trial-00095 on ETH without first proving data availability would mix strategy research with data engineering risk. The ETH sample check found clean recent 15m/4h candles, funding, OI, and book ticker data, and confirmed Binance Vision archives for klines, metrics/OI, and aggTrades. ETHUSDT liquidation snapshots were not available at the probed archive path.

**Consequences:** Do not start ETH strategy research yet. If this direction continues, the next milestone should be a full ETH historical backfill and dataset audit for 2022-2026 candles, funding, OI, and aggtrade-derived flow. Force-order/liquidation context should remain disabled or diagnostic unless a separate provider is validated.

**Related:** `research_lab/analysis_multi_asset_data_feasibility.py`; `docs/analysis/MULTI_ASSET_DATA_FEASIBILITY_2026-05-18.md`.

## 2026-05-18 - Reject trial-00095 hard loss-control after intrabar validation
**Decision:** Close `TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION_V1` with builder verdict `FAIL_NO_ROBUST_IMPROVEMENT`, pending Claude Code audit.

**Reason:** The prior realized-R clipping diagnostic was promising but not executable evidence. The intrabar validation froze trial-00095 entries from exact replay, computed R from original entry/stop geometry, excluded the entry candle, and tested predeclared 15m post-entry hard stops around -1R. All tested hard-stop variants reduced expectancy by roughly 21-23%; the best (`HARD_STOP_0_90R`) stopped 19 eventual winners and improved no chronological fold.

**Consequences:** Do not promote hard loss-control, tighter stop, or -1R clipping into runtime. Do not continue exit-policy design from this result unless Claude Code finds a methodology defect. Trial-00095 baseline exits remain unchanged while M4 monitoring continues.

**Related:** `research_lab/analysis_trial_00095_loss_control_intrabar_validation.py`; `docs/analysis/TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION_2026-05-18.md`.

## 2026-05-18 - Treat trial-00095 exit surface as diagnostic only
**Decision:** Run `TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_V1` as an offline distribution diagnostic, not as an exit optimization or promotion candidate.

**Reason:** Internal consultation flagged the small sample and intrabar-path limitations. The first safe step is to examine frozen trial-00095 realized-R outcomes for broad sensitivity, while preserving the entry population and leaving runtime untouched.

**Result:** The diagnostic found that capping realized losses near -1R would improve ER by approximately +10.6%, PF to 6.40, and max DD ratio to 0.68 on the replay artifact. Winner caps degraded expectancy sharply. This supports only a future validation hypothesis around tighter loss control; it does not approve a runtime exit change.

**Consequences:** Do not promote exit changes from this diagnostic. A future milestone would need full frozen-entry intrabar replay with adverse-first fills, exact entry/stop/TP reconstruction, cost stress, and audit.

**Related:** `research_lab/analysis_trial_00095_exit_surface_diagnostic.py`; `docs/analysis/TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_2026-05-18.md`.

## 2026-05-18 - Test trend pullback reaccept only as offline research
**Decision:** Approve `TREND_PULLBACK_REACCEPT_FEASIBILITY_V1` as a Research Lab-only feasibility milestone after external model consultation narrowed the broader Precision Flow Entry idea.

**Reason:** Claude, Perplexity, DeepSeek, and internal sub-agent consultation converged on the same conclusion: the naive Precision Flow Entry score stack was not falsifiable and repeated prior failed CVD/flow/crowded paths. The narrowed test had a concrete trigger: BTC LONG-only 15m reacceptance of a pre-frozen equal-low support level inside a completed 4h EMA uptrend.

**Consequences:** The milestone may write only Research Lab artifacts and reports. CVD, OI, funding, and force orders remain diagnostic-only. Runtime, `core/**`, `orchestrator.py`, `settings.py`, `execution/**`, and PAPER/LIVE behavior remain unchanged.

**Result:** Offline feasibility failed quality gates decisively despite high frequency. Best variant produced 1257 trades with ER -0.392, PF 0.59, max DD 500.57R, and 0/4 WF folds with ER > 1. Do not rescue by widening or retuning thresholds.

**Related:** `research_lab/hypotheses/active/trend_pullback_reaccept.json`; `docs/analysis/TREND_PULLBACK_REACCEPT_FEASIBILITY_2026-05-18.md`.

## 2026-04-09 — Preserve the restored signal-engine edge
**Decision:** Keep the restored signal architecture as the baseline edge and do not casually rewrite `core/signal_engine.py`.

**Reason:** `docs/MILESTONE_TRACKER.md` records that later signal rearchitecture broke the observed edge and that the system was restored to the `8f2c6f2` signal-era behavior with `min_hits=3`. The important architectural decision was to preserve the sweep/reclaim confluence model where direction comes from flow/regime context rather than from sweep side alone.

**Consequences:** Future strategy work must be research-only first. Changes to signal semantics require explicit evidence and audit, not threshold tuning or opportunistic edits.

**Related:** `docs/MILESTONE_TRACKER.md` SIGNAL-REVERT-V1 notes; `8f2c6f2` is referenced there as the restored signal-era baseline. The literal commit `8f2c6f2` in git is a later walk-forward snapshot cleanup commit, so this reference should be treated as historical project shorthand and rechecked before any code revert.

## 2026-04-13 — Trial #63 approved for paper, not permanently canonical
**Decision:** Trial #63 was approved for paper trading as a candidate at that time, but it is not a permanent source of truth for future optimization.

**Reason:** `docs/MILESTONE_TRACKER.md` records Trial #63 as approved for paper trading on 2026-04-13, with positive walk-forward results. Later data-integrity and market-truth work changed the data contract and exposed that old candidate results should not be conflated with current runtime profiles.

**Consequences:** Trial #63 remains useful for lineage and comparison, but fresh campaigns must explicitly state their data window and protocol. Exact Trial #63 replay must rebuild settings from stored candidate params rather than current `settings.py`.

**Related:** `docs/research_lab/TRIAL_63_FEASIBILITY.md`; trial id `run13-regime-aware-trial-00063`; commit `d245617` referenced as applying Trial #63 params.

## 2026-04-21 — DATA-INTEGRITY-V1 becomes prerequisite for new research
**Decision:** New modeling and optimization work must build on the post-DATA-INTEGRITY data contract.

**Reason:** DATA-INTEGRITY-V1 made decision-path data restart-safe, coverage-aware, and quality-explicit. The milestone added persistent OI/CVD state, feature-quality propagation, and operational visibility, which changed what counts as trustworthy data.

**Consequences:** Research results from before DATA-INTEGRITY are not automatically invalid, but they need revalidation before being used as decision evidence. Future Optuna campaigns must declare whether their source data is pre- or post-DATA-INTEGRITY.

**Related:** `docs/audits/AUDIT_DATA_INTEGRITY_V1_2026-04-21.md`; commit `7ebf2d2`; `docs/MILESTONE_TRACKER.md`.

## 2026-04-27 — Gate A validates Market Truth, not strategy edge
**Decision:** Treat Gate A as validation of the market-truth data layer only.

**Reason:** `AUDIT_GATE_A_VERDICT_2026-04-27.md` records Gate A PASS with 206 quality-ready buckets and complete lineage from market snapshots to feature snapshots to decision outcomes. The same report explicitly states that Gate A validates data infrastructure, not the trading strategy.

**Consequences:** Gate A unlocks further audits and modeling work, but it does not approve a strategy change, a live deployment, or a new parameter campaign by itself.

**Related:** `docs/audits/AUDIT_GATE_A_VERDICT_2026-04-27.md`; branch `market-truth-v3`; commit `e06a3dd` in the audit report.

## 2026-04-27 — MODELING-V1 remains neutral until validation evidence is decision-grade
**Decision:** Keep context filtering in neutral/validation mode until modeling validation produces decision-grade evidence.

**Reason:** `docs/MILESTONE_TRACKER.md` records that MODELING-V1 was implemented after Gate A, but active context blocking was not approved. The later validation checkpoint was partial because volatility telemetry had too much UNKNOWN leakage and the trade sample was too thin for activation.

**Consequences:** Context telemetry can be collected and analyzed, but it must not silently become a live gating layer without a separate activation verdict.

**Related:** `docs/analysis/MODELING_V1_VALIDATION_2026-04-27.md`; `docs/MILESTONE_TRACKER.md`; commit `2dc3112`.

## 2026-04-30 — Reject `min_stop_relief_only` as a promotion candidate
**Decision:** Do not promote `min_stop_relief_only` to paper/live configuration.

**Reason:** The geometry sensitivity Tier 1 runs showed that lowering `min_stop_distance_pct` improved raw expectancy and trade count, but worsened drawdown-normalized performance versus baseline in all tested windows. Slippage stress also showed fragility: at 3x slippage, one tested window collapsed to approximately flat expectancy with materially higher drawdown and longer loss streaks.

**Consequences:** `min_stop_relief_only` remains a research hypothesis only. Any future geometry change must include drawdown-normalized metrics, slippage stress, and audit before promotion.

**Related:** `research_lab/geometry_sensitivity.py`; local generated reports under ignored `research_lab/runs/`; operator/Codex/Claude audit discussion on 2026-04-30. [wymaga weryfikacji operatora]

## 2026-04-30 — NEW_BASELINE_DATE_OPTUNA remains open
**Decision:** Do not start Optuna until the replay data window and protocol are explicitly approved.

**Reason:** Production diagnostics found that the replay tables are not gap-free from 2022-03-09 to 2026-04-17. `aggtrade_15m` has gaps, including a large gap from 2026-03-28 to 2026-04-17, and `open_interest` has a large gap from 2025-06-05 to 2026-01-01 plus later April gaps. The current clean candidate window is `2026-01-01T00:15:00+00:00` to `2026-03-28T21:00:00+00:00`, but that is too short for the default 730/365/365 protocol.

**Consequences:** Optuna must either wait for backfilled/longer data, use an explicitly labeled light protocol, or be deferred until more clean data accumulates. The default protocol must not be applied blindly to an 87-day window.

**Related:** `scripts/db_status.py`; `research_lab/configs/default_protocol.json`; 2026-04-30 production DB diagnostics. [wymaga weryfikacji operatora]

## 2026-04-30 — Runtime state lives in `db_status.py`, decisions live in this log
**Decision:** Do not manually maintain a status document as the source of runtime truth.

**Reason:** Documentation state drifts quickly. Recent diagnostics showed this directly: remembered branch/status context differed from the production server. Runtime facts should be queried from the production database on demand, while documents should preserve stable decisions and rationale.

**Consequences:** Operators and agents should run `python scripts/db_status.py` on production for current facts. This log records why decisions were made, not whether the bot is currently healthy, which branch is deployed, or how many rows are in the database today.

**Related:** `scripts/db_status.py`; `docs/DATA_SOURCES.md`; DOCS-FOUNDATION-V1. [wymaga weryfikacji operatora]

## 2026-05-12 - Keep sweep-reclaim baseline and move to multi-setup research
**Decision:** Keep `optuna-default-v3-trial-00095` as the active PAPER sweep-reclaim baseline. Do not promote any candidate from the constrained grid. Start the next work as research-only `TREND-CONTINUATION-RESEARCH-V1`, with no production behavior change.

**Reason:** The constrained grid around trial-00095 tested 60 combinations and increased trade frequency in several candidates, but every meaningful frequency improvement degraded ER/PF and triggered blocking safety concerns, especially `pnl_sanity_review_required`. This confirms that sweep-reclaim is a bounded liquidity-reclaim / mean-reversion setup, not a clean-trend continuation setup.

**Consequences:** Future work should not try to force sweep-reclaim to trade every market structure. The bot should evolve toward a portfolio of independent, context-specific setups. Each setup must prove edge independently through explicit market-structure hypothesis, deterministic logic, `reasons[]`, standalone backtest, walk-forward validation, safety gates, and audit before it can be integrated through a deterministic multi-setup arbiter.

**Related:** `docs/audits/AUDIT_GRID_SEARCH_TRIAL00095_2026-05-12.md`; `docs/analysis/POST_GRID_PORTFOLIO_PLAN_2026-05-12.md`; `docs/ROADMAP_MULTI_SETUP_ARCHITECTURE.md`; `docs/MILESTONE_TRACKER.md` Multi-Setup Portfolio Architecture section.

## 2026-05-13 - Close 15m multi-setup portfolio research, pivot to sweep-reclaim family expansion
**Decision:** Close 15m multi-setup portfolio research as conclusively NOT VIABLE. Pivot to sweep-reclaim family expansion (structure context variations). No new independent setup families will be tested at 15m without separate architectural decision. Defer 5m/1m frequency upgrade for future evaluation.

**Context:** Six-day research cycle tested 6 independent setup families: absorption_continuation (25 trades, ER -0.48), compression_breakout (3 trades, ER -0.30), crowded_unwind (71 trades, ER -0.35), post_cascade_momentum (0 trades, blocked by infrastructure), volatility_breakout (63 trades, ER 0.52), regime_reversal (11 trades, ER 0.11). Success rate: 0/6 (0%). No candidates reached ER > 1.5 gate (volatility_breakout came closest at ER 0.52, still below 1.0 hard stop).

**Reason:** Three-layer timing incompatibility pattern proven across all 6 families:
1. **Event timescale incompatibility** (crowded_unwind, post_cascade_momentum): Profitable events occur on seconds-to-minutes scale, too fast for 15m decision cycles
2. **Detection latency within states** (volatility_breakout): State classification correct but 15m enters mid-phase, missing early high-profit phase
3. **Edge absence** (absorption_continuation, compression_breakout, regime_reversal): Even with correct timing/state detection, no tradeable edge exists

Only sweep_reclaim works at 15m because: state-independent logic (no regime phase timing needed), mean-reversion edge (not momentum-following), edge persists 15-60 min (compatible with 15m latency), objective measurable signals (sweep/reclaim detection).

**Consequences:**
- Proven edge expansion (sweep_reclaim family, ER 2.1 baseline) prioritized over new unknown edges (0% success rate in 6 families)
- Family expansion validates structure context variations: range specialist, trend specialist, post-liquidation specialist, volume specialist
- Each variant must prove independence (overlap < 30%), meet validation gates (ER > 1.5, WF 2/2), and preserve institutional character
- First variant: Range Sweep Specialist (liquidity sweeps in normal regime, horizontal structure, highest mean-reversion probability hypothesis)
- Exit criteria: After 3 variants, if 0-1 succeed OR overlap > 50% → pivot to 5m frequency assessment
- After 6 months: If trial-00095 live ER < 1.0 → edge degrading, strategic reassessment
- No new setup families rule: No independent setup families tested at 15m without explicit architectural decision

**Alternatives considered and rejected:**
- Continue testing more 15m setups: 0% success rate after 6 families proves 15m timing incompatibility, not sampling issue
- Immediate 5m upgrade: High infrastructure cost (rebuild decision engine, data pipeline, state management, replay tooling) with uncertain benefit (may hit new timing constraints). Exhaust 15m proven edge first.
- Hybrid approach (mixing family expansion + new families): Violates scope discipline, dilutes focus, complicates audit trail

**Related:** `docs/analysis/STRATEGIC_15M_PORTFOLIO_ASSESSMENT_2026-05-13.md` (comprehensive analysis); 6 research branches (absorption, compression, crowded_unwind, post_cascade, volatility, regime_reversal); 6 audit reports; `docs/MILESTONE_TRACKER.md` updated; next milestone `SWEEP-RECLAIM-FAMILY-EXPANSION-V1`.

## 2026-05-13 — Context expansion NOT viable, accept singular sweep_reclaim edge
**Decision:** Close SWEEP-RECLAIM-FAMILY-EXPANSION-V1 (verdict: NOT_VIABLE, 4/4 failures). Accept trial-00095 as the singular sweep_reclaim edge at 15m. Transition to live validation phase. Defer 5m frequency upgrade and parameter-based variants.

**Context:** One-day research cycle tested 4 context expansion variants across 340 trades:
- V1 Range Sweep (normal regime, LONG): 16 trades, ER 0.02 — zero edge
- V2 Trend Sweep (downtrend LONG + uptrend SHORT): 159 trades, ER 0.63 — below threshold
- V3 Special Regime (crowded_leverage, LONG): 34 trades, ER 0.30 — below threshold
- V4 Session Sweep (Asia 00:00-08:00 UTC, LONG): 126 trades, ER 0.78 — best variant, still < 1.0
- Best single micro-context: Asia + Uptrend LONG (90 trades, ER 0.89, PF 2.85) — still < 1.0

**Reason:** Four independent mechanisms tested (3 regime-based + 1 microstructure-based). All failed ER 1.0 hard stop. Evidence conclusive:
1. **Context filtering cannot create edge.** It can only subset trial-00095's trade set, degrading ER vs the full parameter-optimized set.
2. **sweep_reclaim edge is parameter-dependent, not context-dependent.** ER 2.1 comes from Optuna-tuned confluence/TFI/risk thresholds across ALL regimes and ALL sessions.
3. **SHORT universally destructive.** Normal SHORT ER -0.92, Uptrend SHORT ER 0.09. LONG-only bias is fundamental, not tunable.
4. **No further 15m context variants justified.** 10 hypotheses tested (6 setup families + 4 context variants), 0% success rate.

**Consequences:**
- trial-00095 IS the edge — no further context specialization attempts
- Live validation focus: collect 30-50 paper trades over 6-10 months
- Decision points: After 30 trades (preliminary ER check), after 50 trades (final validation)
- If live ER > 1.5 after 50 trades → promote to LIVE (with restored kill-switch limits)
- If live ER < 1.0 after 30 trades → reassess edge viability
- 5m frequency upgrade deferred until live ER stability confirmed (estimated 6-8 weeks cost if undertaken)
- No new research milestones until live validation produces decision-grade evidence

**Alternatives considered and rejected:**
- More 15m context variants: 0/10 success rate proves this is not a sampling problem
- Immediate 5m upgrade: High cost (6-8 weeks), uncertain benefit, premature without live validation
- Parameter-based variants (re-optimize with context constraints): Context filtering degrades ER; Optuna already found global optimum
- New edge families at 15m: 0/6 success rate in portfolio research; timing incompatibility proven

**Related:** `research/sweep-family-expansion-v1` branch (commits efd9ef3..61a8aaa); `docs/MILESTONE_TRACKER.md`; `docs/analysis/SWEEP_RECLAIM_SINGULAR_EDGE_ASSESSMENT_2026-05-13.md`; 4 audit packages in `research_lab/reports/` and `docs/audits/`.

## 2026-05-14 - Reject standalone 5m sweep/reclaim runtime migration
**Decision:** Close `BTC_5M_SWEEP_RECLAIM_FEASIBILITY_V1` as `5M_FREQUENCY_FAIL_QUALITY_PASS`. Do not migrate the live decision runtime from 15m to standalone 5m sweep/reclaim based on this evidence.

**Reason:** The standalone 5m harness improved quality metrics versus its matched 15m comparison (ER 2.351 vs 2.110, PF 6.63 vs 3.95, WR 72.1% vs 51.1%, MAE improved by roughly 40%), but it only increased trade count by 1.30x against a required >=2x gate. The structural bottleneck is reclaim detection: 5m bars detect more raw sweeps but are less likely to sweep and reclaim inside a single bar.

**Consequences:**
- Full 5m runtime migration remains unjustified.
- 5m may be studied only as an offline timing/quality layer until separately validated.
- Results are not directly comparable to official BacktestRunner metrics because the study used a standalone harness with simplified fills.

**Related:** `docs/analysis/BTC_5M_SWEEP_RECLAIM_FEASIBILITY_2026-05-14.md`; `docs/MILESTONE_TRACKER.md`.

## 2026-05-15 - Reject 15m signal plus 5m energy confirmation overlay
**Decision:** Close `15M_SIGNAL_5M_ENERGY_OVERLAY_FEASIBILITY` as `HYBRID_FAIL`.

**Reason:** Waiting for a 5m high-energy candle after a 15m signal produced timeout rates of 78-91%. SKIP mode left too few trades for decision-grade evidence, while FALLBACK mode preserved count but degraded ER from the 15m baseline and did not improve MAE. The evidence indicates 5m energy confirms the move too late rather than improving the entry.

**Consequences:**
- Do not add 5m energy confirmation to the 15m execution path.
- The standalone 5m quality improvement should not be interpreted as proof that post-signal 5m confirmation improves 15m entries.

**Related:** `docs/analysis/15M_SIGNAL_5M_ENERGY_OVERLAY_2026-05-15.md`; `docs/MILESTONE_TRACKER.md`.

## 2026-05-15 - Mark 5m multi-candle event setups ready for audit, not rescue
**Decision:** `BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_V1` is `READY_FOR_AUDIT` with builder verdict `MULTI_CANDLE_FAIL`. Do not rescue failed variants by expanding the grid unless Claude Code identifies a methodology issue.

**Reason:** Both tested setup families increased event counts but failed required quality gates. Compression fakeout reclaim best variant produced 73 trades but negative ER and weak PF. Crowded unwind reversal produced 174 trades but also negative ER, weak PF, and severe drawdown.

**Consequences:**
- Claude Code audit is required before scheduling follow-up research.
- The result does not approve any production, PAPER, settings, core, execution, or orchestrator change.
- The failure supports the current stance that 5m geometry alone does not solve the BTC frequency problem without quality degradation.

**Related:** `docs/analysis/BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_2026-05-15.md`; `docs/MILESTONE_TRACKER.md`.

## 2026-05-15 - Add research automation foundation as audit-pending infrastructure
**Decision:** `RESEARCH_AUTOMATION_FOUNDATION_LITE_V1` is `READY_FOR_AUDIT`. Treat it as research-lab-only infrastructure, not an autonomous research agent and not a production integration.

**Reason:** The milestone standardizes hypothesis specs, experiment registry records, data manifest hashes, deterministic gate evaluation, and markdown reporting after several manual research scripts. It intentionally avoids LLM-generated code execution, automatic experiment execution, external repositories, and runtime coupling.

**Consequences:**
- Claude Code audit must pass before relying on the framework as the standard research workflow.
- `research_lab/autoresearch_loop.py` remains separate and unchanged.
- Hypothesis specs must remain declarative data and must not become a code execution channel.

**Related:** `docs/analysis/RESEARCH_AUTOMATION_FOUNDATION_LITE_2026-05-15.md`; `docs/MILESTONE_TRACKER.md`.

## 2026-05-17 - Add runtime single-instance guard after duplicate PAPER bot incident
**Decision:** Implement `M4-RUNTIME-SINGLE-INSTANCE-GUARD` immediately as operational hardening. The guard prevents a second `main.py --mode PAPER` or `main.py --mode LIVE` runtime from starting, regardless of whether it is launched by systemd or manually with `nohup`.

**Reason:** A second manual PAPER runtime ran from 2026-05-14 to 2026-05-17 alongside the managed systemd bot, creating duplicate `decision_outcomes` rows and a second active config hash. This was the second duplicate-runtime incident in recent history. A systemd PIDFile alone would not prevent manual launches; an application-level file lock protects all launch paths.

**Consequences:**
- The guard applies only to `main.py` runtime startup.
- One-shot scripts, diagnostics, dashboard, collectors, and research harnesses remain unaffected.
- Lock path defaults to `/tmp/btc-bot-runtime.lock` and can be overridden with `BTC_BOT_RUNTIME_LOCK_PATH`.
- Claude Code audit is required before deploying this guard to PAPER production.

**Related:** `docs/operations/RUNTIME_INSTANCE_CONTROL.md`; `docs/MILESTONE_TRACKER.md`; M4 deploy verification on 2026-05-17.

## 2026-05-16 - Close 5m multi-candle research path after three failures
**Decision:** Close `BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_V1` as `MULTI_CANDLE_FAIL` (audit verdict: ACCEPT). Implementation correct, hypothesis decisively falsified. 5m research path exhausted after three major attempts.

**Reason:** Audit confirmed methodology integrity (no-lookahead discipline, one-position constraint, proper force-orders data integration) and verified that both tested setup families produced catastrophically negative results:
- Compression Fakeout Reclaim (CFR_V3): 73 trades, ER -0.192, PF 0.371, DD 14.0R (3.1x baseline)
- Crowded Unwind Reversal (CUR_V1): 174 trades, ER -0.415, PF 0.224, DD 72.4R (16.1x baseline)

Both setups achieved frequency goals (1.55x, 3.70x vs baseline) but failed 4 of 6 required quality gates. Direction split shows both LONG and SHORT negative (not a direction bias issue). Force-orders correction was material (integrated 146,864 historical force-order rows from 2022-2024) but did not create edge.

Combined 5m research evidence:
1. **M5 (BTC_5M_SWEEP_RECLAIM_FEASIBILITY):** Frequency fail (1.30x < 2.0x gate) — sweep/reclaim detection less efficient at 5m
2. **M6 (15M_SIGNAL_5M_ENERGY_OVERLAY):** Quality fail (ER degrades, 78-91% timeout) — 5m confirmation too late
3. **M7 (BTC_5M_MULTI_CANDLE_EVENT_SETUP):** Quality catastrophic fail (negative ER, DD 3-16x baseline) — multi-candle patterns have no edge

Conclusion: **5m resolution does not solve BTC frequency problem.** Multi-candle event windows increased detection frequency but destroyed edge quality.

**Consequences:**
- Do not attempt to rescue 5m multi-candle setups by expanding parameter grid
- Three research paths now exhausted: threshold optimization (degrades quality), 5m resolution (all variants failed), context expansion (0% success rate)
- Wait for M4 near-miss monitoring checkpoint (2026-06-13, 29 days), then decide strategic direction:
  - **Option A:** Continue monitoring if M4 reveals actionable sweep-depth regime shift
  - **Option B:** ETH multi-asset feasibility study (test if low-frequency issue is BTC-specific)
  - **Option C:** Accept current frequency, focus on live validation of trial-00095

**Related:** `docs/audits/AUDIT_BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_2026-05-16.md`; `docs/analysis/BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_2026-05-15.md`; `docs/MILESTONE_TRACKER.md`; commit 2e0679b (implementation), commit 74ef7a8 (audit closure).

## 2026-05-16 - Approve research automation foundation framework for production use
**Decision:** Approve `RESEARCH_AUTOMATION_FOUNDATION_LITE_V1` for production use in research context (audit verdict: DONE). Framework is production-grade research infrastructure.

**Reason:** Audit verified all safety boundaries, comprehensive test coverage (15/15 passed), and complete implementation:
- **Zero production coupling:** No imports from core/, execution/, data/, orchestrator, settings. Framework is self-contained.
- **Append-only registry:** No delete API (verified by test). Experiment records are permanent audit trail.
- **Safe hypothesis specs:** Recursive validation rejects executable field names (python_code, code, module_path, function_name, import, eval, exec, shell_command). No code execution channel from JSON specs.
- **Deterministic gate evaluator:** Pure function, no randomness, verdict logic (BLOCKED > INCONCLUSIVE > FAIL > MARGINAL > PASS) is explicit and testable.
- **Reproducibility:** Experiment fingerprints, data manifest hashes, combined manifest hashing for multi-dataset experiments, full lineage capture (hypothesis_id, config_hash, data_manifest_hash, git_commit, runner_name, date_range, baseline_reference).
- **Standard report contract:** All required sections generated, test validates presence.

Framework standardizes the repeatable workflow: `hypothesis -> experiment -> evaluation -> report`. Designed for Karpathy-style loop patterns without vendoring external code, adding LLM agents, or touching production runtime.

**Consequences:**
- Use framework for all future offline research programs (ETH feasibility, exit studies, diagnostic analyses)
- Hypothesis specs must be authored by builder, reviewed by Claude Code before experiment execution
- Experiment registry is single source of truth for offline research results
- Standard report generator replaces manual report formatting
- Gate evaluator provides deterministic pass/fail evaluation (no subjective judgment)
- Framework is complementary to existing Optuna integration (autoresearch_loop.py remains unchanged)
- Framework does NOT execute backtests (by design) — backtest execution is separate concern

**Usage scope:**
- **In scope:** Offline research programs, hypothesis tracking, experiment registry, gate evaluation, report generation
- **Out of scope:** Production runtime changes, PAPER deployment, automatic experiment execution, LLM code generation, parameter optimization (use Optuna for that)
- **Not a promotion channel:** Framework stores results, does not auto-promote to production. Separate approval workflow required for live deployment.

**Related:** `docs/audits/AUDIT_RESEARCH_AUTOMATION_FOUNDATION_LITE_2026-05-16.md`; `docs/analysis/RESEARCH_AUTOMATION_FOUNDATION_LITE_2026-05-15.md`; `docs/MILESTONE_TRACKER.md`; commit 35d78f2 (implementation), commit cbe4ad2 (audit closure).

## 2026-05-17 - M4 near-miss payload contract fix deployed, rogue process incident resolved
**Decision:** Deploy M4 near-miss payload contract fix (commit 33a0df1) to PAPER production. Do not quarantine the 305 duplicate decision_outcomes created by rogue process during May 14-17 overlap period.

**Reason:** Production database showed `sweep_depth_pct` only at top-level `details_json`, not inside nested `near_miss_diagnostics`. This conflicted with documented M4 query contract and required backward-compatible fix.

During deploy verification, Codex discovered a second bot instance running via manual `nohup` launch (started 2026-05-14 15:15 UTC). This created 305 duplicate decision_outcomes with different config_hash across ~3 days overlap.

**Payload fix details:**
- Added nested `sweep_depth_pct` to `near_miss_diagnostics` payload in orchestrator.py
- Report parser made backward-compatible (fallback to top-level if nested missing)
- Nested payload only added for near-misses (depth >= 0.004), not all sweep_too_shallow rejections (by design)
- Tests verify both old and new payload shapes work (24/24 passed)

**Rogue process incident:**
- **Scope:** 2026-05-14 15:15 to 2026-05-17 19:15 UTC (~3 days 4 hours)
- **Impact:** 305 rogue records, only 4 exact timestamp duplicates (LOW severity)
- **Root cause:** Manual `nohup .venv/bin/python main.py --mode PAPER` launched alongside systemd bot
- **Detection:** Codex noticed two active config_hash values during deploy verification
- **Resolution:** Rogue process killed, only systemd bot (PID 790301) remains
- **Data integrity:** No execution conflicts (PAPER mode), both bots used same M4 parameters, most timestamps unique due to microsecond drift

**Comparison to April 24-27 dual-runtime incident:**
- April incident: 344 exact duplicates over 3.5 days
- May incident: 305 total rogue records, only 4 exact duplicates
- May incident less severe due to timing drift between processes

**Consequences:**
- M4 monitoring continues unchanged (no parameter changes)
- Near-miss counts in May 14-17 period slightly inflated but usable
- M4 checkpoint analysis should filter by `config_hash = 'afbd2eb...'` or use data after 2026-05-17 19:15 UTC for clean sample
- No database cleanup required (diagnostics-only data, PAPER mode, historical record of incident useful)
- **Hardening needed:** Single-instance runtime guard to prevent future manual bot launches

**Next operational fix:** Implement file-lock-based single-instance guard in main.py to prevent both manual nohup launches and systemd race conditions. This should be separate hardening milestone, not mixed with research work.

**Related:** `docs/audits/AUDIT_M4_NEAR_MISS_PAYLOAD_FIX_2026-05-16.md`; `docs/diagnostics/M4_NEAR_MISS_MONITORING_CHECKPOINT_2026-05-16.md`; commit 33a0df1 (implementation), commit d4ab073 (audit); incident detected and resolved by Codex on 2026-05-17.
