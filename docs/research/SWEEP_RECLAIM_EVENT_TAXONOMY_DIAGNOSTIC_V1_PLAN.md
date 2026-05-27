# SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1 Plan

## 1. Executive Verdict

Proceed with a research-only diagnostic milestone.

The milestone is not a new sweep/reclaim strategy, context filter, or live-bot change. It is an offline event taxonomy diagnostic to test whether the current `detect_sweep_reclaim` boolean model mixes structurally different market events with materially different forward-return, MAE, and MFE behavior.

Recommended implementation location, if approved after final audit: `research_lab/analysis_sweep_reclaim_event_taxonomy_diagnostic_v1.py`.

Do not implement anything yet. This document is the implementation plan for Claude's next audit.

## 2. Motivation: What Problem Does This Solve?

Trial-00095 remains the validated baseline. This milestone does not attempt to rescue, replace, or override trial-00095.

The current bot's sweep/reclaim logic is a single-bar boolean model in `core/feature_engine.py`:

- `sweep_detected`
- `reclaim_detected`
- `sweep_level`
- `sweep_depth_pct`
- `sweep_side`

That model may mix structurally different market events:

- wick liquidity take,
- close-based structure break,
- immediate reclaim,
- delayed reclaim,
- true breakout / no reclaim.

The diagnostic asks whether these event classes show materially different forward-return, MAE, and MFE behavior. If there is no expectancy separation, no FeatureEngine changes are justified.

This is NOT:

- regime/session filtering,
- parameter rescue,
- new entry logic,
- live strategy change,
- CHOCH/MSS implementation,
- TradingView/Pine port.

## 3. Current Bot Sweep/Reclaim Implementation Inventory

Relevant architecture files:

- `core/models.py`: contracts for `MarketSnapshot`, `Features`, `RegimeState`, `SignalCandidate`, `SignalDiagnostics`, `ExecutableSignal`, `MarketContext`.
- `core/feature_engine.py`: ATR, EMA, equal levels, current sweep/reclaim facts, funding/OI/CVD/TFI/force-order features.
- `core/regime_engine.py`: deterministic regime labels.
- `core/context_engine.py`: deterministic UTC session and volatility metadata.
- `core/signal_engine.py`: interprets `Features` into `SignalCandidate`; owns `min_sweep_depth_pct`, reclaim gate, direction inference, confluence scoring, and regime direction whitelist.
- `core/governance.py`: stateful runtime filters, including duplicate-level veto and session/no-trade/cooldown limits.
- `core/risk_engine.py`: hard risk gate, sizing, RR gate, max positions, drawdown, exit lifecycle.
- `orchestrator.py`: live/paper pipeline wiring, feature snapshots, signal diagnostics, decision outcomes, governance/risk/execution sequence.
- `settings.py`: frozen dataclass config/profile system and runtime overlay handling.
- `settings.json`: deployed runtime overlay for trial-00095 PAPER parameters.

Current equal-level detection:

- Implemented in `core/feature_engine.py` as `detect_equal_levels`.
- Uses recent highs/lows from `FeatureEngine.compute`.
- Sorts price levels, clusters values within `equal_level_tol_atr * atr_15m`, requires `min_hits`, and requires cluster age span `>= level_min_age_bars`.
- It is not a confirmed pivot/fractal system.
- It does not maintain active/untaken liquidity state.

Current sweep/reclaim detection:

- Implemented in `core/feature_engine.py` as `detect_sweep_reclaim`.
- Evaluates only the latest 15m candle.
- Low-side sweep:
  - latest open must be within `sweep_proximity_atr * atr_15m` of an equal low.
  - `low < level - sweep_buf_atr * atr_15m`.
  - reclaim requires `close > level + reclaim_buf_atr * atr_15m`.
  - wick quality requires lower wick/body distance `>= wick_min_atr * atr_15m`.
- High-side sweep:
  - latest open must be within proximity of an equal high.
  - `high > level + sweep_buf_atr * atr_15m`.
  - reclaim requires `close < level - reclaim_buf_atr * atr_15m`.
  - wick quality requires upper wick/body distance `>= wick_min_atr * atr_15m`.
- It returns `sweep_detected`, `reclaim_detected`, `sweep_level`, `sweep_depth_pct`, `sweep_side`, `close_vs_reclaim_buffer_atr`, `wick_vs_min_atr`, and `sweep_vs_buffer_atr`.
- It does not classify confirmed pivots, active liquidity lifecycle, close BoS, delayed reclaim, or true breakout separately.

Current thresholds and deployed values:

- Defaults live in `settings.py` `StrategyConfig`.
- Runtime overlay values live in `settings.json`.
- Current trial-00095 sweep/reclaim-relevant overlay values in `settings.json`:
  - `atr_period = 27`
  - `equal_level_lookback = 276`
  - `equal_level_tol_atr = 0.09`
  - `sweep_buf_atr = 0.46`
  - `reclaim_buf_atr = 0.07`
  - `wick_min_atr = 0.2`
  - `min_sweep_depth_pct = 0.00649`
  - `direction_tfi_threshold = 0.10`
  - `direction_tfi_threshold_inverse = -0.05`
  - `tfi_impulse_threshold = 0.31`
  - `duplicate_level_tolerance_pct = 0.0016`
  - `duplicate_level_window_hours = 123`

Current duplicate-level veto:

- Implemented in `core/governance.py`.
- `GovernanceLayer` keeps an in-memory deque of accepted entry references.
- `_is_duplicate_level` rejects a candidate when a prior accepted level within `duplicate_level_window_hours` is within `duplicate_level_tolerance_pct`.
- This is not the same as duplicate event inflation in research. The V1 diagnostic needs its own event identity and de-duplication rules.

Relevant persistence and DB access:

- `storage/schema.sql`: `candles`, `funding`, `open_interest`, `oi_samples`, `aggtrade_buckets`, `cvd_price_history`, `force_orders`, `signal_candidates`, `executable_signals`, `trade_log`, `decision_outcomes`, `market_snapshots`, `feature_snapshots`, `config_snapshots`.
- `storage/repositories.py`: persistence helpers, including `insert_feature_snapshot`, `insert_decision_outcome`, `save_signal_candidate`, `fetch_feature_snapshot`, `fetch_recent_feature_snapshots`, and `fetch_decision_outcome_counts`.
- `storage/state_store.py`: runtime wrapper and `record_feature_snapshot`, `record_decision_outcome`, `get_recent_feature_snapshots`.
- `backtest/replay_loader.py`: builds historical `MarketSnapshot` objects from SQLite `candles`, `funding`, OI, aggtrade buckets, and force orders.
- `backtest/backtest_runner.py`: official runtime-parity replay using core engines, but it does not persist the full rejected sweep population like live `decision_outcomes`.
- `docs/DATA_SOURCES.md`: production runtime data lives on the server, not local `storage/btc_bot.db`.

Relevant research and diagnostics files:

- `research_lab/analysis_btc_5m_sweep_reclaim_feasibility.py`
- `research_lab/analysis_btc_5m_multi_candle_event_setup_feasibility.py`
- `research_lab/analysis_sweep_acceptance_continuation.py`
- `research_lab/analysis_sweep_acceptance_retest_continuation.py`
- `research_lab/analysis_15m_signal_5m_energy_overlay.py`
- `research_lab/analysis_atr_relative_threshold_research.py`
- `scripts/report_near_miss_diagnostics.py`
- `scripts/diag_live_signal_funnel.py`
- `docs/analysis/SWEEP_RECLAIM_SINGULAR_EDGE_ASSESSMENT_2026-05-13.md`
- `docs/analysis/BTC_5M_SWEEP_RECLAIM_FEASIBILITY_2026-05-14.md`
- `docs/analysis/BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_2026-05-15.md`
- `docs/analysis/TRIAL_00095_CONDITIONAL_EDGE_ANALYSIS_2026-05-13.md`
- `docs/SWEEP_RECLAIM_PRELAUNCH_REPORT.md`

Relevant tests:

- `tests/test_feature_engine.py`
- `tests/test_signal_engine.py`
- `tests/test_context_engine.py`
- `tests/test_orchestrator_runtime_logging.py`
- `tests/test_near_miss_diagnostics.py`
- `tests/test_research_lab_multi_candle_events.py`
- `tests/test_sweep_acceptance_continuation.py`
- `tests/test_sweep_acceptance_retest_continuation.py`
- `tests/test_research_backtest_runner.py`
- `tests/test_dashboard_db_reader.py`
- `tests/test_dashboard_server.py`

## 4. External Research Synthesis

External indicators and GitHub packages are idea sources only.

Useful concepts:

- Wick/high-low crossing a level is different from close crossing a level.
- Wick crossing can be a liquidity take.
- Close crossing can be a structure break or acceptance candidate.
- Close back inside the level can be an immediate or delayed reclaim.
- No reclaim within a fixed window is the natural comparison class for delayed reclaim and close-based BoS.

Do not copy:

- proprietary Pine implementation details,
- TradingView execution behavior,
- repainting pivot logic,
- black-box SMC package behavior into production.

Optional benchmark:

- `joshyattridge/smart-money-concepts` or `coding-kitties/PyIndicators` may be used only as skipped/optional offline reference tests, not as production dependencies.

## 5. V1 Event Taxonomy

The classifier should create one row per unique level-event interaction.

Recommended event identity:

`symbol | timeframe | level_side | pivot_index | confirmed_at_index | level_price | detection_bar | event_type`

Required V1 diagnostic labels:

1. `confirmed_pivot`
   - A pivot high/low at index `i` is usable only after `i + right`.
   - Fields: `pivot_index`, `confirmed_at_index`, `left`, `right`, `level_side`, `level_price`.
   - No event may use a pivot before confirmation.

2. `active_liquidity_level`
   - A confirmed pivot becomes active at `confirmed_at_index`.
   - It remains active until taken.
   - High-side level taken when `high[current] > level_price`.
   - Low-side level taken when `low[current] < level_price`.

3. `equal_touch`
   - Equality or configured touch tolerance at the level.
   - Must not mark a level taken.
   - Strict `>` and `<` remain the default take rules.

4. `wick_crossed_liquidity`
   - High-side: `high > active_pivot_high`.
   - Low-side: `low < active_pivot_low`.
   - Market-structure fact only, not a signal.

5. `close_based_bos`
   - Bullish: `close > pivot_high`.
   - Bearish: `close < pivot_low`.
   - Must be separated from wick-cross logic.

6. `immediate_wick_sweep_reclaim`
   - Buy-side swept and rejected: `high > pivot_high AND close < pivot_high`.
   - Sell-side swept and rejected: `low < pivot_low AND close > pivot_low`.

7. `delayed_close_reclaim`
   - After a wick cross or close break, price closes back inside the level within `reclaim_window_bars`.
   - Record `reclaim_delay_bars`.

8. `true_breakout` / `no_reclaim_within_window`
   - Price crosses and closes beyond the level, and no reclaim occurs within the reclaim window.
   - This is a delayed label known only after the reclaim window closes.
   - It must never be treated as same-bar live input.

Deferred to V3 or later:

- `failed_sweep`
- `acceptance_proxy`
- CHOCH/MSS
- OB/FVG/RJB/PPDD
- retest-hold acceptance model

## 6. Explicit Timing Model

Every event row must separate detection time from label availability.

Required timing fields:

- `detection_bar`
- `label_available_bar`
- `return_start_bar_detection`
- `return_start_bar_label_available`

Rules:

- `wick_crossed_liquidity`, `close_based_bos`, and `immediate_wick_sweep_reclaim` are detectable at the event bar close.
- `delayed_close_reclaim` is detectable only when the reclaim close occurs.
- `true_breakout` / `no_reclaim_within_window` is available only after `reclaim_window_bars` has elapsed without reclaim.
- Forward returns must be reported from both:
  - detection bar,
  - label-available bar.

Purpose:

- Prevent delayed labels from creating fake edge by measuring returns from a bar where the label was not yet knowable.
- Allow fair comparison between immediately knowable event facts and delayed outcome labels.

## 7. Boundaries: Research Lab vs Production Layers

Research script only in this milestone:

- confirmed pivot detection,
- active liquidity level lifecycle,
- equal-touch classification,
- wick-cross vs close-BoS classification,
- immediate and delayed reclaim labels,
- true breakout / no-reclaim-within-window label,
- timing model fields,
- forward returns, MAE, MFE, and cohort summaries,
- optional metadata joins.

No production changes:

- No `core/feature_engine.py` changes.
- No `core/signal_engine.py` changes.
- No `core/governance.py` changes.
- No `core/risk_engine.py` changes.
- No `orchestrator.py` changes.
- No `settings.py` or `settings.json` changes.
- No DB schema migration.
- No execution changes.
- No Pine code copying.

Potential later FeatureEngine facts, only if diagnostic passes and audit approves:

- `wick_crossed_liquidity`
- `close_broke_structure`
- `close_reclaim`
- `reclaim_delay_bars`
- `liquidity_level_type`
- `level_age_bars`
- `sweep_depth_atr`
- `cluster_count_near_level`

Potential later SignalEngine interpretation, only after separate approval:

- Whether delayed reclaim deserves any entry interpretation.
- Whether `true_breakout` should block reversal candidates.
- Whether current `no_reclaim` diagnostics should split into more precise labels.

## 8. Regime/Session Handling

Regime/session segmentation is metadata only and is not a candidate for entry filtering in this milestone.

Do not make regime/session required decision cohorts. Prior research in `docs/analysis/SWEEP_RECLAIM_SINGULAR_EDGE_ASSESSMENT_2026-05-13.md` found context expansion degraded the validated edge.

If cheap to collect, the report may include metadata fields:

- `session` from `core/context_engine.py` rules,
- `weekday/weekend`,
- `regime` from `core/regime_engine.py` using reproducible offline features.

These fields must not be presented as proposed gates. They are for sanity checks only, such as identifying one-period concentration or data imbalance.

## 9. Data Requirements and DB Tables

Primary historical source:

- SQLite historical DB with `candles` for BTCUSDT 15m.
- The script should accept `--db-path`, `--symbol`, `--timeframe`, `--start`, `--end`.
- First pass should use 15m. 5m can be a later diagnostic if V1 produces meaningful separation.

Required table:

- `candles`: OHLCV and timestamps for pivot/event/forward-return calculation.

Optional tables:

- `aggtrade_buckets`: TFI/CVD metadata if available.
- `funding`: funding metadata if available.
- `open_interest` and `oi_samples`: OI metadata if available.
- `force_orders`: force-order metadata if available.
- `trade_log`: current bot baseline accepted-trade comparison.
- `signal_candidates`: current bot accepted candidate comparison.

Do not rely on:

- Local `storage/btc_bot.db` for runtime truth.
- Production `decision_outcomes` as the primary historical research source, because backtest rejected-sweep populations are not consistently persisted.

Data quality checks:

- Normalize timestamps to UTC.
- Assert monotonic candle times per symbol/timeframe.
- Count missing bars, duplicate bars, and OHLC violations.
- Refuse or clearly label runs with material gaps.
- Do not silently drop rows.
- Persist a data manifest in output JSON.

## 10. Proposed Research Script Design

Recommended path:

- `research_lab/analysis_sweep_reclaim_event_taxonomy_diagnostic_v1.py`

Recommended outputs:

- JSON artifact: `research_lab/analysis_output/sweep_reclaim_event_taxonomy_diagnostic_v1_<symbol>_<timeframe>_<start>_<end>.json`
- Markdown report: `docs/analysis/SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_<date>.md`
- Tests: `tests/test_research_lab_sweep_reclaim_event_taxonomy_diagnostic_v1.py`

Core pure dataclasses/functions:

- `PivotConfig(left, right, strict, touch_tolerance, tick_size)`
- `DiagnosticConfig(reclaim_window_bars, forward_windows, atr_period, cluster_tolerance_atr)`
- `Candle(index, open_time, open, high, low, close, volume)`
- `ConfirmedPivot(side, pivot_index, confirmed_at_index, level_price)`
- `ActiveLevel(level_id, side, level_price, pivot_index, confirmed_at_index, taken_at_index)`
- `TaxonomyEvent(...)`

Pipeline:

1. Load candles and optional metadata series from SQLite.
2. Validate data quality.
3. Compute ATR using only bars available at or before each event bar.
4. Detect pivots with right-side confirmation.
5. Activate levels only at `pivot_index + right`.
6. Maintain active untaken levels.
7. On each bar, evaluate active levels for equal touch, wick cross, close BoS, and immediate reclaim.
8. For wick/close break events, evaluate delayed reclaim and no-reclaim labels after the reclaim window.
9. Populate `detection_bar`, `label_available_bar`, `return_start_bar_detection`, and `return_start_bar_label_available`.
10. Compute forward returns and MAE/MFE from both return starts.
11. Summarize event cohorts and write JSON/Markdown.

Side-effect guardrails:

- No imports from `orchestrator.py`, `execution/*`, live clients, or production service code.
- No writes to production DB.
- Output only to research/report paths.

## 11. Metrics and Cohorts

Event-level fields:

- `event_id`
- `symbol`
- `timeframe`
- `event_time_utc`
- `detection_bar`
- `label_available_bar`
- `return_start_bar_detection`
- `return_start_bar_label_available`
- `level_side`
- `level_type`
- `level_price`
- `level_age_bars`
- `pivot_left`
- `pivot_right`
- `pivot_index`
- `confirmed_at_index`
- `touch_count_before_take`
- `cluster_count_near_level`
- `level_distance_atr_before_sweep`
- `sweep_depth_abs`
- `sweep_depth_pct`
- `sweep_depth_atr`
- `wick_ratio`
- `wick_crossed_liquidity`
- `close_based_bos`
- `immediate_wick_sweep_reclaim`
- `delayed_close_reclaim`
- `reclaim_delay_bars`
- `true_breakout`
- `no_reclaim_within_window`
- optional metadata: `session`, `weekday_weekend`, `regime`, `tfi`, `cvd`, `funding`, `oi_delta`

Forward outcome metrics:

- Forward returns after 3, 5, 10, and 20 bars from `return_start_bar_detection`.
- Forward returns after 3, 5, 10, and 20 bars from `return_start_bar_label_available`.
- MAE/MFE over the same windows from both starts.
- Median, mean, p25, p75, and sample count.
- Net expectancy proxy after fees/slippage assumptions.

Required decision cohorts:

- Raw wick cross of liquidity.
- Immediate close reclaim.
- Delayed close reclaim.
- Close-based BoS.
- True breakout / no reclaim within window.
- Shallow/medium/deep sweep by ATR.
- Sweep near clustered equal highs/lows vs isolated pivot.
- Current bot equal-level sweep/reclaim approximation vs V1 pivot taxonomy.
- Random/control cohort: random confirmed pivot touches or shuffled event timestamps.

Metadata-only cuts:

- Session.
- Weekday/weekend.
- Regime, if cheaply reproducible.

## 12. Test Plan

Minimum tests:

- Pivot confirmation: a pivot at `i` cannot be active before `i + right`.
- Active/taken level lifecycle: confirmed level activates once, remains active, then is taken once.
- Strict wick cross vs equal touch: `>` and `<` take; equality is touch.
- Wick cross vs close BoS separation.
- Immediate reclaim.
- Delayed reclaim and `reclaim_delay_bars`.
- True breakout / no-reclaim-within-window label.
- Timing model: delayed labels have later `label_available_bar`.
- Forward returns are computed from both detection and label-available starts.
- No duplicate event inflation around the same active level.
- Clustered vs isolated level tagging.
- Synthetic SQLite integration test with deterministic event rows.

Suggested commands:

- `python -m compileall research_lab tests -q`
- `pytest tests/test_research_lab_sweep_reclaim_event_taxonomy_diagnostic_v1.py -q -o addopts=`

## 13. Lookahead/Repainting Risk Analysis

Pivot confirmation:

- A pivot using `right` bars must not become active until the right-side window is complete.
- `pivot_high[i]` can only be used at `i + right`.
- Events before `confirmed_at_index` must ignore that pivot.

Delayed labels:

- `delayed_close_reclaim` and `true_breakout` / `no_reclaim_within_window` require future bars.
- They are valid research labels, not live same-bar features.
- Reports must split detection-bar returns from label-available-bar returns.

Data alignment:

- Candle time semantics must be explicit: open time vs close time.
- TFI/aggtrade metadata must be joined only to data available at or before the event close.
- ATR must use history ending at or before the event bar.

Duplicate inflation:

- A level can be taken once.
- Repeated bars around the same active level must not create repeated independent events.
- Equal/clustered levels are metadata unless explicitly used as a separate predeclared comparison source.

## 14. Feature Flag and Rollout Plan

Feature flag name for any future implementation:

- `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1=false`

For this milestone:

- No runtime flag is needed.
- No settings/profile changes are allowed.
- The research output can include this flag name as metadata only.

If a later production implementation is approved:

- Add a frozen dataclass field in `settings.py`, default false.
- Preserve config-hash behavior.
- Prefer extending `feature_snapshots.features_json` before DB schema migration.
- Prove false-flag behavior is unchanged with regression tests.

## 15. Explicit Non-Goals

Do not implement:

- live bot behavior changes,
- SignalEngine entry expansion,
- Governance veto changes,
- RiskEngine changes,
- execution changes,
- portfolio/risk sizing changes,
- DB schema migration,
- production settings changes,
- Pine/TradingView code copying,
- production dependency additions,
- CHOCH/MSS,
- OB/FVG/RJB/PPDD,
- retest-hold acceptance model,
- parameter optimization or threshold rescue,
- dashboard UI changes.

## 16. Invalidation Criteria

Kill or revise the idea if any of these occur:

- No expectancy separation versus random/control pivot touches.
- Immediate or delayed reclaim does not outperform raw wick cross.
- Close-based BoS and no-reclaim labels do not separate from wick-cross outcomes.
- Sweep depth does not stratify outcomes.
- Forward returns from label-available bars remove the apparent edge.
- Results work only in one short period or small sample.
- Median MFE/MAE does not improve versus current bot candidate baseline or generic pivot touches.
- Net expectancy fails after realistic fees/slippage assumptions.
- Apparent edge depends on pivot lookahead leakage or repainting.
- Duplicate-level artifacts inflate sample count.
- Sample size is too small for decision-grade comparison.
- The taxonomy mostly reproduces current `detect_sweep_reclaim` without adding explanatory separation.

## 17. Milestone Deliverables

For the implementation milestone, after final plan audit:

- `research_lab/analysis_sweep_reclaim_event_taxonomy_diagnostic_v1.py`
- `tests/test_research_lab_sweep_reclaim_event_taxonomy_diagnostic_v1.py`
- JSON output under `research_lab/analysis_output/`
- Markdown report under `docs/analysis/`
- Optional hypothesis/manifest entry if the Research Lab workflow requires it.
- `docs/MILESTONE_TRACKER.md` update only after the user opens the implementation milestone and acceptance criteria are finalized.

Acceptance criteria:

- Script is deterministic and reproducible from CLI.
- Synthetic SQLite integration test passes.
- Pivot confirmation leakage test passes.
- Timing model tests pass.
- Duplicate event inflation test passes.
- Report compares required event-taxonomy cohorts and includes invalidation verdict.
- `python -m compileall ...` and focused pytest pass locally.
- No live path files are modified.

## 18. Open Questions

- Which historical DB is canonical for the first diagnostic run: production backup, `research_lab/snapshots/replay-run13-regime-aware-trial-00063.db`, or a newer research snapshot?
- Which pivot parameters should be predeclared? Recommendation: small fixed set such as `(left=2,right=2)`, `(3,3)`, `(5,5)`, reported separately.
- Should equal-level clusters be a parallel level source or metadata only? Recommendation: metadata first.
- Should current bot equal-level sweep/reclaim be recomputed in the script for comparison? Recommendation: yes, as a comparison cohort only.
- Should official trial-00095 BacktestRunner trades be joined? Recommendation: yes for accepted-trade baseline, but do not require exact signal overlap unless timestamps are available.

## 19. Recommendation

Recommendation: proceed with the reduced event-taxonomy diagnostic plan.

This is a controlled diagnostic of whether the current sweep/reclaim boolean mixes different event classes. It should not become implementation work until Claude issues a final verdict on this revised plan.
