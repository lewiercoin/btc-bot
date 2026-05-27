# MFE Accessibility Earliest Knowable Signal V1 Plan

**Milestone:** `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1`  
**Status:** planning only, not approved for implementation  
**Date:** 2026-05-27  
**Scope:** research-lab diagnostic design only  
**Production impact:** none  

## 1. Executive Summary

This milestone plans a meta-diagnostic, not a strategy.

Core question:

`Where is the earliest knowable state after a sweep where the remaining MFE is still tradable after costs?`

The previous two diagnostics established the failure mode:

- `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1` showed delayed labels create
  fake edge if measured from `detection_bar`.
- `SMC_SEQUENCE_EDGE_FEASIBILITY_V1` showed the SMC sequence located real
  movement, but `entry_candidate_bar = mitigation_bar + 1` arrived too late.
  Median MFE before entry was larger than post-entry MFE.

This plan asks a different question. It does not ask whether another label or
SMC sequence works. It asks, bar by bar after a sweep, what facts were knowable
and how much tradable excursion remained after those facts became knowable.

This is not:

- new strategy implementation;
- SMC rescue;
- V1 taxonomy rescue;
- mitigation-entry rescue;
- FeatureEngine work;
- SignalEngine work;
- Governance/Risk change;
- production setting change;
- DB schema migration.

This is:

- accessibility study;
- post-sweep MFE/MAE timing map;
- earliest-knowable-signal investigation;
- decision point before any future strategy family.

Recommendation for implementation, if this plan passes audit: one
research-only script plus focused tests under `research_lab/**` and
`tests/test_research_lab_*`, with no live-path imports that create side
effects.

## 2. Repository Inventory

Current sweep and feature surfaces:

- `core/feature_engine.py`
  - `detect_equal_levels` at lines around `125-153`.
  - `detect_sweep_reclaim` at lines around `156-223`.
  - Equal highs/lows are built from the 15m lookback around `291-306`.
  - Sweep/reclaim facts are computed around `308-317`.
  - Funding/OI/CVD/TFI/force-order features are computed around `329-356`.
  - CVD divergence is computed by `_compute_cvd_divergence`.
  - Force-order spike/decreasing flags are computed by
    `_is_force_order_spike` and `_is_force_order_decreasing`.

- `core/signal_engine.py`
  - `diagnose` gates candidates around `83-120`:
    `no_sweep`, `missing_sweep_level`, `sweep_too_shallow`,
    `no_reclaim`, `direction_unresolved`, `regime_direction_whitelist`,
    `confluence_below_min`, `uptrend_pullback_weak`.
  - Direction inference uses CVD divergence and TFI around `218-233`.
  - Confluence scoring uses sweep, reclaim, CVD, TFI, force-order, regime,
    EMA trend, and funding around `248-293`.

- `core/regime_engine.py`
  - Regimes include `POST_LIQUIDATION`, `CROWDED_LEVERAGE`, `COMPRESSION`,
    `UPTREND`, `DOWNTREND`, `NORMAL`.
  - Post-liquidation currently depends on force-order spike, absolute TFI, and
    force-order decreasing.

- `core/context_engine.py`
  - Session/volatility context exists, but prior research showed
    session/regime filtering degraded edge. Treat this as metadata only.

- `core/governance.py`
  - Duplicate-level veto occurs in `_is_duplicate_level`.
  - This is not the primary target because recent evidence shows most events
    die before governance.

- `core/risk_engine.py`
  - Min RR, sizing, max positions, drawdown gates.
  - Useful for baseline comparison, not part of this diagnostic.

Runtime persistence surfaces:

- `orchestrator.py`
  - Records market snapshots, feature snapshots, and decision outcomes in the
    live/PAPER decision cycle.
  - No-signal diagnostics are persisted with `outcome_reason` and details.
  - Near-miss payload enrichment exists for `sweep_too_shallow` when depth is
    at least `0.004`.

- `storage/schema.sql`
  - Historical/data tables: `candles`, `funding`, `open_interest`,
    `aggtrade_buckets`, `force_orders`.
  - Runtime decision tables: `decision_outcomes`, `market_snapshots`,
    `feature_snapshots`, `signal_candidates`, `trade_log`.

- `storage/repositories.py`
  - Helpers exist for feature snapshots, decision outcomes, signal candidates,
    trade log, and recent snapshot fetches.

Backtest and research surfaces:

- `backtest/replay_loader.py`
  - Builds historical `MarketSnapshot` objects from SQLite data.

- `backtest/backtest_runner.py`
  - Reuses core engines and writes accepted candidates/trades.
  - Limitation: it does not persist the full rejected sweep population like
    live/PAPER `decision_outcomes`.

- `research_lab/research_backtest_runner.py`
  - Extends replay patterns for research variants, but still is not the full
    rejected-population event study needed here.

- Existing relevant diagnostics:
  - `research_lab/analysis_sweep_reclaim_event_taxonomy_diagnostic_v1.py`
  - `research_lab/analysis_smc_sequence_edge_feasibility_v1.py`
  - `research_lab/analysis_trial_00095_conditional_edge.py`
  - `docs/analysis/SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27.md`
  - `docs/analysis/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md`
  - `docs/analysis/WF_VALIDATION_TRIAL_00095_2026-05-08.md`
  - `docs/analysis/TRIAL_00095_CONDITIONAL_EDGE_ANALYSIS_2026-05-13.md`
  - `docs/research/REVERSE_QUANT_EDGE_REVIEW_2026-05-27.md`

## 3. Event Universe

The diagnostic should treat the event universe as layered. Each layer answers a
different question.

### Primary Universe: All Reconstructed Equal-Level Sweeps

Use historical BTCUSDT 15m candles and the current equal-level sweep definition
as the primary event anchor:

- equal levels from current bot logic or exact research-only equivalent;
- low-side sweep -> candidate long accessibility path;
- high-side sweep -> candidate short accessibility path;
- include sweeps whether or not reclaim happened;
- include shallow, medium, and deep sweeps;
- deduplicate repeated bars around the same level to avoid sample inflation.

Why: this is the broadest universe where the current bot's edge begins.

### Secondary Universe: Current Bot Accepted Candidate States

Reconstruct current trial-00095 candidate state by running the current
FeatureEngine/RegimeEngine/SignalEngine logic in research-only replay, or by
joining available `signal_candidates`/`trade_log` where available.

This cohort answers whether trial-00095 already captures the earliest
accessible part of the move.

### Rejected / Near-Miss Universe

Include reconstructed pre-candidate rejection states:

- `sweep_too_shallow`;
- `no_reclaim`;
- `direction_unresolved`;
- `confluence_below_min`;
- `uptrend_continuation_weak`;
- `uptrend_pullback_weak`;
- `regime_direction_whitelist`.

Live/PAPER `decision_outcomes` can provide recent real runtime samples, but
historical coverage should be reconstructed offline because standard
`BacktestRunner` does not persist rejected populations.

### V1 / SMC Reference Universe

Use V1 taxonomy and SMC sequence event outputs only as reference overlays:

- V1 raw wick cross, immediate reclaim, delayed reclaim, true breakout;
- SMC sequence phases: sweep, displacement, structure, FVG, mitigation, entry.

They should not define the primary universe. They are timing reference points
for accessibility curves.

## 4. Bar-By-Bar Measurement Model

For every sweep event, evaluate post-detection bars:

`T + k`, where `T = detection_bar` and `k` ranges from `0` through a configured
maximum such as `20` or `32` 15m bars.

At each `T+k`, record a state row. Each row asks:

1. What was knowable at this bar?
2. If entry were allowed only after this bar was known, what happened next?
3. How much of the move was already consumed?

Required row fields:

- `event_id`
- `symbol`
- `timeframe`
- `direction`
- `sweep_side`
- `sweep_level`
- `sweep_depth_pct`
- `detection_bar`
- `detection_time_utc`
- `k`
- `state_known_bar`
- `state_known_time_utc`
- `entry_candidate_bar`
- `entry_candidate_time_utc`
- `return_start_bar`
- `return_start_time_utc`
- `known_state_flags`
- `blocked_by_current_bot`
- `current_bot_candidate_generated`
- `trial_00095_candidate_state`
- `remaining_mfe_3/5/10/20`
- `remaining_mae_3/5/10/20`
- `net_return_3/5/10/20`
- `gross_return_3/5/10/20`
- `hit_3/5/10/20`
- `time_to_mfe_3/5/10/20`
- `mfe_consumed_pct`
- `mae_before_state`
- `mfe_before_state`
- `quality_flags`

Entry timing rule:

- If a state is knowable only at the close of `T+k`, primary
  `entry_candidate_bar = T+k+1`.
- Optional sensitivity: `entry_candidate_bar = T+k` close-to-close returns,
  but this is audit-only unless execution at that close is realistic.
- Success claims must use the conservative next-bar entry model unless a later
  implementation plan justifies a different execution model.

## 5. Knowable States To Test

Each state must be deterministic and timestamped by when it becomes knowable.

### Base States

- `raw_sweep_known`
  - Known at `detection_bar` close.
  - Tests sweep-only accessibility.

- `equal_level_cluster_quality_known`
  - Known before detection if level already existed.
  - Includes level age, touch count, cluster count, distance from level before
    sweep, and ATR distance.

- `reclaim_known`
  - Known at the bar close where reclaim is true.
  - Must be measured from reclaim-known timing, not sweep detection.

- `no_reclaim_after_n_bars`
  - Known only after `n` bars elapse without reclaim.
  - Tests whether no-reclaim is usable or simply late.

### Price-Action States

- `displacement_known`
  - ATR-normalized body/range expansion after sweep.
  - Known at displacement bar close.

- `close_beyond_level_known`
  - Close-based continuation/BoS-like condition.
  - Known at close bar.

- `structure_shift_proxy_known`
  - Local swing break after sweep.
  - Known at break close; no unconfirmed future pivots.

- `fvg_created_known`
  - Three-candle FVG/imbalance known after the third candle closes.
  - Include only as accessibility marker, not mitigation-entry strategy.

### Flow / Microstructure States

- `tfi_aligned_known`
  - 60s TFI sign and magnitude supports candidate direction.
  - Known only after the relevant 60s bucket is closed and aligned to the
    15m event timestamp.

- `cvd_divergence_known`
  - Current FeatureEngine CVD divergence flags.
  - Known when sufficient prior CVD/price history exists at the current bar.

- `cvd_absorption_proxy_known`
  - Research-only proxy: price makes sweep extreme but CVD fails to confirm
    the extreme, or CVD reverses within a closed bucket.
  - Must be explicitly timestamped; no future bucket use.

- `force_order_burst_known`
  - Force-order rate/spike around sweep.
  - Known after force-order events are timestamped within the closed interval.

- `force_order_decay_known`
  - Force-order rate decreases after spike.
  - Delayed state; must prove remaining MFE is not already consumed.

- `oi_funding_crowding_known`
  - OI z-score, OI delta, funding percentile / funding sign support crowding
    or unwind.
  - Known at or before event bar depending on data timestamp.

### Current Bot States

- `direction_resolved_known`
  - Current SignalEngine direction inference is non-null.

- `confluence_threshold_known`
  - Current confluence preview crosses configured threshold.

- `trial_00095_candidate_known`
  - Current bot would generate a candidate.

- `current_bot_reject_reason_known`
  - Current bot rejects, with `blocked_by` reason.

These current-bot states are critical because the diagnostic must answer
whether trial-00095 already captures the earliest accessible state.

## 6. Timing Model

Every state row must separate:

- `detection_bar`
- `state_known_bar`
- `entry_candidate_bar`
- `return_start_bar`
- `label_available_bar` if a delayed label is present

Ordering invariants:

- `detection_bar <= state_known_bar`
- `state_known_bar <= entry_candidate_bar`
- `entry_candidate_bar == return_start_bar` for primary results
- `label_available_bar >= state_known_bar` for delayed labels

Examples:

- Raw sweep:
  - `detection_bar = T`
  - `state_known_bar = T`
  - `entry_candidate_bar = T + 1`

- Reclaim at `T+2`:
  - `state_known_bar = T + 2`
  - `entry_candidate_bar = T + 3`
  - No result from `T` can be claimed for this state.

- Displacement at `T+1`:
  - `state_known_bar = T + 1`
  - `entry_candidate_bar = T + 2`

- No reclaim within 4 bars:
  - `state_known_bar = T + 4`
  - `entry_candidate_bar = T + 5`

- Trial-00095 candidate at sweep bar close:
  - `state_known_bar = candidate bar`
  - `entry_candidate_bar = next bar` for conservative diagnostic comparison.

## 7. Outcome Metrics

Primary metrics by state and by `k`:

- sample count;
- median and mean gross forward return;
- median and mean net forward return after costs;
- hit rate above zero;
- hit rate above a cost-adjusted threshold;
- median MAE;
- median MFE;
- median remaining MFE;
- median MFE consumed before state;
- time-to-MFE after state;
- MFE-before-state versus MFE-after-state ratio;
- profit-factor proxy from net returns;
- max drawdown proxy from event-return sequence;
- event frequency per month;
- walk-forward fold stability.

Recommended forward windows:

- 3 bars;
- 5 bars;
- 10 bars;
- 20 bars.

Recommended cost model for first pass:

- 0.10% round-trip cost baseline, matching recent diagnostics;
- sensitivity at 0.06%, 0.15%, and 0.20% if cheap.

MFE consumed definition:

`mfe_consumed_pct = mfe_from_detection_to_state / max(total_mfe_from_detection_to_horizon, epsilon)`

Interpretation:

- `0.0` means no favorable move consumed before the state.
- `0.5` means half the favorable move is already gone.
- `>= 0.7` means the state is probably operationally late.

## 8. Trial-00095 Comparison Plan

Trial-00095 remains benchmark, not religion.

The diagnostic should compare against trial-00095 in three ways:

1. Accepted-trade benchmark
   - Use existing trial-00095 reports and replay artifacts:
     `docs/analysis/WF_VALIDATION_TRIAL_00095_2026-05-08.md`,
     `docs/analysis/TRIAL_00095_CONDITIONAL_EDGE_ANALYSIS_2026-05-13.md`.
   - Baseline references: PF around `4.66`, max drawdown around `6.51%`,
     roughly `271` historical trades.

2. Candidate-state overlap
   - Mark rows where current SignalEngine would generate a trial-00095-style
     candidate.
   - Measure whether any earlier knowable state has positive net expectancy
     before trial-00095 candidate state.

3. Reject-population explanation
   - For current bot rejects, measure whether a rejected state has accessible
     MFE after its own `state_known_bar`.
   - If no rejected bucket has positive entry-timed net expectancy, trial-00095
     likely already captures the accessible part.

Required conclusion categories:

- `trial_00095_captures_accessible_edge`
- `earlier_state_outperforms_trial_00095_candidate_state`
- `rejected_bucket_has_accessible_edge`
- `no_accessible_edge_before_decay`
- `inconclusive_due_to_sample_or_data`

No future strategy plan is justified unless a state beats sweep-only,
deterministic control, and relevant trial-00095 candidate/baseline comparisons.

## 9. Rejected Population Handling

Problem:

`BacktestRunner` writes accepted candidates and trades, but not the full
`decision_outcomes` population for historical rejected sweeps. Live/PAPER
runtime does persist `decision_outcomes`, but production history is short and
market-regime-specific.

Plan:

1. Historical reconstruction
   - Research-only replay over historical candles.
   - Compute features and call `SignalEngine.diagnose` for every bar.
   - Persist diagnostic rows to JSON/Parquet-like output, not production DB.
   - Do not alter `BacktestRunner` in this planning milestone.

2. Runtime sanity overlay
   - Optionally join production `decision_outcomes`, `feature_snapshots`, and
     `market_snapshots` if a safe exported copy is available.
   - Use only for sanity checks: live reject mix, shallow sweep prevalence,
     payload availability.

3. Near-miss specificity
   - Keep `sweep_too_shallow` near-miss as a dedicated cohort.
   - Include `no_reclaim`, `direction_unresolved`, and `confluence_below_min`
     because they represent different timing/fact failures.

4. No schema migration
   - Generated rows belong in research output files only.
   - No production DB writes.

## 10. Data Requirements

Preferred canonical source:

- `research_lab/data/crowded_unwind_backtest.db`
  - BTCUSDT 15m/1h/4h data.
  - Includes `candles`, `aggtrade_buckets`, `funding`, `open_interest`,
    `force_orders`, `trade_log`, `signal_candidates`.
  - Already used by SMC sequence diagnostic, so comparison is clean.

Optional sources:

- production DB export / backup:
  - use only for runtime sanity overlay;
  - never query live production from the research script by default.

- 5m snapshot:
  - defer unless 15m accessibility shows a plausible early state that may need
    lower-timeframe execution.

Data quality checks required in implementation plan:

- monotonic timestamps;
- no duplicate candles;
- OHLC integrity;
- gap count by timeframe;
- coverage for `aggtrade_buckets`;
- coverage for `force_orders`;
- funding/OI coverage;
- feature-quality status rates;
- event count by year/fold.

## 11. Proposed Research Script Shape

This is not implementation approval, but the future implementation should be
small and isolated.

Recommended path if approved later:

`research_lab/analysis_mfe_accessibility_earliest_knowable_signal_v1.py`

Expected outputs:

- `research_lab/analysis_output/mfe_accessibility_earliest_knowable_signal_v1_<date>.json`
- `docs/analysis/MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1_<date>.md`

High-level flow:

1. Load historical candles and optional flow/funding/OI/force-order series.
2. Validate data quality.
3. Reconstruct all equal-level sweep events.
4. Reconstruct current bot diagnostic state per bar using research-only core
   engine calls or equivalent deterministic wrappers.
5. For each sweep and each `k`, build known-state row.
6. Compute entry-timed forward returns, MAE, MFE, time-to-MFE, and MFE
   consumed.
7. Aggregate by state, `k`, direction, reject reason, depth bucket, and
   trial-00095 candidate overlap.
8. Produce deterministic control rows from shifted timestamps.
9. Produce invalidation verdict.
10. Write JSON and Markdown report.

No live services, no exchange API calls, no production DB writes.

## 12. Required Cohorts

Decision cohorts:

- `all_raw_sweeps`
- `sweep_only_no_additional_state`
- `sweep_plus_reclaim`
- `sweep_plus_displacement`
- `sweep_plus_tfi_alignment`
- `sweep_plus_cvd_divergence`
- `sweep_plus_cvd_absorption_proxy`
- `sweep_plus_force_order_burst`
- `sweep_plus_force_order_decay`
- `sweep_plus_oi_funding_crowding`
- `sweep_plus_direction_resolved`
- `sweep_plus_confluence_threshold`
- `trial_00095_candidate_state`
- `sweep_too_shallow_reject`
- `no_reclaim_reject`
- `direction_unresolved_reject`
- `confluence_below_min_reject`
- `deterministic_shift_control`

Metadata-only cuts:

- regime;
- session/hour;
- weekday/weekend;
- year/fold;
- symbol if multi-asset data is used later.

Regime/session must not be presented as entry-filter proposals in this
milestone.

## 13. Lookahead And Leakage Controls

Rules:

- A state can only be true when all required inputs are closed and timestamped.
- No delayed state may claim returns from `detection_bar`.
- Primary returns start from `entry_candidate_bar`.
- Detection-bar returns can be shown only as audit context.
- FVG/structure/force-order-decay style delayed states must prove remaining
  MFE after their own known bar.
- CVD/TFI/force-order buckets must align to closed exchange intervals.
- Funding/OI samples must use timestamps not later than `state_known_time_utc`.
- No unconfirmed right-side pivot or recursive fractal may be used.
- Duplicate sweeps around the same level must be deduplicated or explicitly
  clustered.

Mandatory timing assertions for implementation:

- `detection_bar <= state_known_bar <= entry_candidate_bar`
- `return_start_bar == entry_candidate_bar`
- no metric used for pass/fail starts before `state_known_bar`
- delayed state rows must fail tests if `state_known_bar == detection_bar`
  without a same-bar knowability reason.

## 14. Invalidation Criteria

The diagnostic should STOP future strategy-family work if any decisive failure
applies.

### Timing / Accessibility Failure

STOP if:

- no early knowable state has positive median net return after costs;
- hit rate drops to approximately 50% from `entry_candidate_bar`;
- apparent edge exists only from `detection_bar`, not from
  `state_known_bar` / `entry_candidate_bar`;
- median `mfe_consumed_pct >= 0.70` before every positive-looking state;
- MFE-before-state is greater than or equal to MFE-after-state for all viable
  states.

### Baseline Failure

STOP if:

- best state does not beat `all_raw_sweeps`;
- best state does not beat deterministic shifted control;
- best state does not beat relevant current bot candidate-state baseline;
- best state is simply the current trial-00095 candidate state with no earlier
  explanatory value;
- best rejected bucket does not outperform trial-00095 candidate state after
  costs.

### Sample / Stability Failure

STOP or mark inconclusive if:

- total usable events for a candidate state are below 300;
- OOS/test events are below 100;
- any walk-forward fold has below 50 events for a claimed state;
- fewer than 2 of 4 folds have positive net median return;
- state appears less than 1 event/month on average;
- performance is concentrated in one short period.

### Novelty Failure

STOP if:

- the state is more than 90% overlapping with trial-00095 accepted candidates
  and does not improve outcome metrics;
- the state is just `tfi_impulse` or `confluence_threshold` under a new name
  without adding timing or rejected-population insight.

### Execution Realism Failure

STOP if:

- signal requires entry on a bar close that is not realistically executable;
- costs/slippage sensitivity turns median net return negative;
- lower-timeframe or intrabar assumptions are required to pass but unavailable
  in the data.

## 15. Pass / Fail / Inconclusive Definitions

PASS requires all of:

- at least one state has positive median net return after costs;
- that state is known before most MFE is consumed;
- primary returns from `entry_candidate_bar` beat raw sweep and control;
- comparison to trial-00095 is favorable or explains a meaningful failure mode;
- sample size and fold stability are decision-grade;
- no lookahead or duplicate inflation issue.

FAIL means:

- no accessible state survives timing, cost, control, and baseline checks.

INCONCLUSIVE means:

- data coverage, sample count, or timestamp alignment prevents a reliable
  decision.

## 16. Test Plan For Future Implementation

Required tests before implementation completion:

- Unit test state timing:
  - delayed state cannot have `state_known_bar < required confirmation bar`.

- Unit test entry timing:
  - primary `entry_candidate_bar` is after `state_known_bar`.

- Unit test MFE consumed:
  - synthetic path computes MFE-before-state and MFE-after-state correctly.

- Unit test remaining MFE / MAE:
  - long and short cases use correct favorable/adverse direction.

- Unit test no detection-bar leakage:
  - delayed reclaim/displacement/force-order-decay cannot report primary
    returns from detection.

- Unit test rejected-state reconstruction:
  - synthetic FeatureEngine/SignalEngine diagnostics produce expected
    `blocked_by` categories.

- Unit test duplicate sweep clustering:
  - repeated bars around the same level do not inflate event count.

- Integration test with synthetic SQLite:
  - deterministic sweep path with known TFI/CVD/force-order rows;
  - expected state rows and exact event count.

- Control cohort test:
  - deterministic shifted control uses only valid future windows and does not
    overlap original event identity.

## 17. Deliverables If Implementation Is Later Approved

Implementation deliverables would be:

- research-only script under `research_lab/`;
- focused pytest file under `tests/`;
- JSON output under `research_lab/analysis_output/`;
- Markdown report under `docs/analysis/`;
- optional audit memo under `docs/audits/` after Claude review.

No implementation deliverables are approved by this plan.

## 18. Possible Next Decisions

The diagnostic must end with exactly one of:

1. `STOP_SMC_AND_SWEEP_SOURCE_RESEARCH`
   - No early knowable state survives.
   - trial-00095 PAPER validation continues.

2. `TRIAL_00095_CAPTURES_ACCESSIBLE_EDGE`
   - Current bot already enters at the earliest viable point.
   - Continue live/PAPER validation; do not add strategy complexity.

3. `PLAN_ONE_STRATEGY_FAMILY_DIAGNOSTIC`
   - Exactly one state shows timing-correct, cost-adjusted expectancy.
   - Write a new audited plan around that state only.

4. `ORDER_FLOW_LIQUIDATION_AFTER_SWEEP_IS_CANDIDATE`
   - Flow/force-order/OI states specifically explain accessible MFE.
   - Plan a separate order-flow/liquidation diagnostic, not SMC.

5. `INCONCLUSIVE_DATA_GAP`
   - Need better rejected population, 5m/1m execution data, or production
     export before deciding.

## 19. Explicit Non-Goals

Do not implement in this milestone:

- production code;
- FeatureEngine facts;
- SignalEngine entries;
- Governance/Risk changes;
- settings/profile changes;
- DB schema migrations;
- live service queries in research script defaults;
- SMC sequence rescue;
- V1 taxonomy rescue;
- mitigation-entry rescue;
- CHOCH/FVG/OB/RJB additions as strategy logic;
- lower-timeframe execution model;
- session/regime entry filtering;
- Pine/TradingView porting;
- parameter relaxation to force a pass.

## 20. Recommendation

Proceed with this plan for Claude audit.

If approved later, implementation should be one research-only diagnostic that
maps all sweep and near-miss events into a bar-by-bar accessibility surface.
The implementation should not propose a trade entry. It should answer whether
any candidate entry timing is worth a future strategy-family plan.

The most likely valuable finding, if any, is not classical SMC. It is an early
flow/liquidation state after sweep. The most likely negative finding is that
trial-00095 already captures the accessible part of the edge and that later
confirmation consumes the move.

