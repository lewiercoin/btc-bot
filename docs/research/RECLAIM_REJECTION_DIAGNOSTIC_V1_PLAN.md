# RECLAIM_REJECTION_DIAGNOSTIC_V1 Plan

## 1. Executive Summary

This is a planning document for `RECLAIM_REJECTION_DIAGNOSTIC_V1`. It is
research-only and is not approval to modify production strategy code.

Research question:

Does an earliest-knowable wick-rejection event at a confirmed swing extreme,
combined with reclaim, existing TFI/CVD confluence, and level provenance from
`level_scanner`, produce timing-correct expectancy that beats the
`reclaim_swing` baseline, beats deterministic controls, and remains
diversifying versus `reclaim_swing` P&L?

Scope:

- Implement one offline diagnostic after this plan is audited.
- Use local research data only: `research_lab/data/crowded_unwind_backtest.db`.
- Use `research_lab/level_scanner.py` as the level-fact factory.
- Measure primary returns from realistic timing, not from detection.
- Apply hard falsification rules before any result is known.

This is not:

- a production setup implementation;
- a `signal_engine.py` change;
- a `FeatureEngine` or `RegimeEngine` change;
- a trial-00095 threshold rescue;
- a session/regime filter;
- a parameter grid or optimization campaign;
- a live/PAPER production query.

Builder verdict after implementation may be `HYPOTHESIS_INVALIDATED`. Negative
results are valid if timing, controls, and falsification gates are honored.

## 2. Why This Is Different From Prior Research

`SMC_SEQUENCE_EDGE_FEASIBILITY_V1` tested a delayed sequence:

`liquidity sweep -> displacement -> structure shift -> FVG/imbalance -> mitigation/retest -> entry_candidate_bar`

That sequence was invalidated because realistic mitigation entry arrived too
late. The report found median MFE before entry of `0.011565` versus post-entry
5-bar MFE of `0.004916`; detection-bar returns looked better than
entry-timed returns.

`MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` then showed the decisive
research question is not whether a pattern exists, but whether enough movement
remains after the state is knowable.

`reclaim_rejection` tests a different and earlier mechanism:

- The rejection wick is observable at the close of the rejection candle.
- The state is known one bar later, avoiding intra-bar lookahead.
- Entry waits for reclaim plus TFI/CVD confluence, but does not wait for
  mitigation/OTE/FVG retest.
- The rejection zone itself becomes the structure, rather than a late retest
  of a downstream zone.

This milestone exists because prior institutional memory says rejection is the
highest-priority new candidate, not because it is empirically proven. Audit
finding F017 applies: candidate confidence is methodological. M3 converts that
3/5 methodological confidence into measured PASS/FAIL evidence.

## 3. Repository Inventory

Existing primitives reused:

- `research_lab/level_scanner.py`
  - emits level facts with `level_id`, `category`, `side`, `price`, `top`,
    `bottom`, `available_at`, and provenance fields.
  - V1 level categories: session extremes, PDH/PDL/PWH/PWL, EQH/EQL clusters,
    anchored VWAP, round numbers, liquidation placeholder.
- `research_lab/diagnostics/event_study_v1.py`
  - event-study style, fixed exit model, ATR-normalized returns, deterministic
    JSON output pattern.
- `docs/research/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_PLAN.md`
  - timing discipline, control cohorts, label availability, no-rescue rule.
- `docs/research/MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1_PLAN.md`
  - MFE before/after entry measurement model and 70% accessibility gate.
- `docs/analysis/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md`
  - late mitigation invalidation reference.
- `docs/DECISIONS_LOG.md`
  - setup scarcity confirmed and portfolio correlation gate approved:
    `max_correlation_with_reclaim_swing_pnl = 0.5`.

Data source:

- `research_lab/data/crowded_unwind_backtest.db`
  - `candles`: BTCUSDT 15m/1h/4h OHLCV.
  - `aggtrade_buckets`: 60s taker buy/sell volume, `tfi`, and `cvd`.
  - `funding`, `open_interest`, `force_orders`, `signal_candidates`,
    `trade_log`.
  - `cvd_price_history` exists but is empty in this local DB; the diagnostic
    must use `aggtrade_buckets.cvd` for the CVD confluence proxy unless audit
    rejects that interpretation.

New research primitives planned:

- deterministic wick rejection detection;
- confirmed swing-extreme check without future leakage beyond the declared
  confirmation bars;
- rejection-zone reclaim test;
- level-provenance lookup with `available_at <= state_known_bar`;
- monthly P&L correlation against `reclaim_swing_baseline`;
- deterministic negative-control cohort.

No production module is modified.

## 4. Hypothesis Specification

### Mechanism

A `reclaim_rejection` candidate is valid when all are true:

1. A 15m candle has a large rejection wick at a confirmed swing extreme.
2. The rejection state becomes knowable at `detection_bar + 1`.
3. A later bar reclaims the rejection zone.
4. TFI and CVD direction align with the rejection direction at the known state
   or entry state, using only already available `aggtrade_buckets` rows.
5. The rejection zone overlaps a level fact from `level_scanner` that was
   available no later than `state_known_bar`.

### Timing Model

| Bar | Definition |
|---|---|
| `detection_bar` | The candle that creates the large wick rejection. |
| `state_known_bar` | `detection_bar + 1`; the rejection candle has closed and can be inspected. |
| `confirmation_bar` | Same as `state_known_bar` for wick existence; reclaim may occur later. |
| `entry_candidate_bar` | First bar at or after `state_known_bar + 1` where reclaim and confluence both hold. |
| `label_available_bar` | First bar where the fixed-exit outcome is known; audit/report field only. |
| `return_start_bar` | `entry_candidate_bar + 1`; primary returns use next open after entry candidate. |

Primary metrics must use `return_start_bar`. Detection-bar returns are audit
metrics only for F-6 lookahead detection.

### Rejection Detection Pseudocode

```text
for each completed 15m candle i in the study window:
    body = abs(close_i - open_i)
    body_for_ratio = max(body, tick_epsilon)
    candle_range = high_i - low_i
    if candle_range <= 0: continue

    upper_wick = high_i - max(open_i, close_i)
    lower_wick = min(open_i, close_i) - low_i
    atr_i = ATR(14) known at candle i close

    confirmed_swing_high = i is a pivot high with fixed left/right bars
    confirmed_swing_low = i is a pivot low with fixed left/right bars

    short rejection if:
        confirmed_swing_high
        upper_wick / body_for_ratio >= 2.0
        upper_wick / candle_range >= 0.6
        upper_wick / atr_i >= 1.0

    long rejection if:
        confirmed_swing_low
        lower_wick / body_for_ratio >= 2.0
        lower_wick / candle_range >= 0.6
        lower_wick / atr_i >= 1.0

    detection_bar = i
    state_known_bar = i + 1
```

The implementation must make swing confirmation timing explicit. If the
configured swing-right confirmation would make the swing unavailable after
`state_known_bar`, the event is either delayed until the swing is known or
excluded from the primary cohort. The plan preference is exclusion for M3,
because the research question is an earliest-knowable rejection, not a delayed
pivot label.

### Rejection Zone and Reclaim

For long candidates:

- zone bottom = `low[detection_bar]`
- zone top = `min(open[detection_bar], close[detection_bar])`
- reclaim = later close re-enters above `zone_top`

For short candidates:

- zone bottom = `max(open[detection_bar], close[detection_bar])`
- zone top = `high[detection_bar]`
- reclaim = later close re-enters below `zone_bottom`

### Confluence

Use 60s `aggtrade_buckets` aggregated into the relevant 15m bar:

- Long confluence: TFI positive and CVD delta/proxy non-negative.
- Short confluence: TFI negative and CVD delta/proxy non-positive.

If CVD semantics are ambiguous, implementation must document the exact choice
and include a data-quality field. Do not tune confluence thresholds after
seeing results.

### Forbidden Patterns

- Do not measure primary returns from `detection_bar`.
- Do not use `level_scanner` levels with `available_at > state_known_bar`.
- Do not use future bars to declare a swing extreme without carrying that
  confirmation delay into timing.
- Do not relax wick thresholds after seeing results.
- Do not add regime/session filters to rescue a failed result.
- Do not modify `core/signal_engine.py`, `core/feature_engine.py`,
  governance, risk, settings, schema, or dependency manifests.

## 5. Falsification Criteria

If any rule fails on the full historical sample, final verdict is
`HYPOTHESIS_INVALIDATED`. Stop. Do not rescue.

| Rule | Measurement | Invalidate if | Rationale |
|---|---|---:|---|
| F-1 | Timing-correct PF from `return_start_bar` fixed-exit P&L | `< 1.5` | Weak trade management edge is not enough for a new setup family. |
| F-2 | Median net expectancy after 0.10% round-trip cost | `< 0` | Positive gross movement is irrelevant if costs erase it. |
| F-3 | `median_mfe_before_entry / median_mfe_post_entry_5bar` | `> 0.70` | Entry is too late if pre-entry opportunity dominates post-entry opportunity. |
| F-4 | Throughput increase versus `reclaim_swing_baseline` | `< 0.2 trades/day` | M1 proved throughput is the bottleneck; tiny throughput does not solve it. |
| F-5 | Pearson monthly P&L correlation with `reclaim_swing_baseline` | `> 0.5` | High correlation means no diversification benefit. |
| F-6 | Detection-bar PF or return edge versus timing-correct PF/return edge | `> 30% better` | Apparent edge is likely timing/lookahead leakage. |

The report must output PASS/FAIL for F-1 through F-6 with measured values and
thresholds.

## 6. Cohort Design

Primary cohort:

- `reclaim_rejection_with_level_provenance`
- wick rejection + reclaim + TFI/CVD confluence + overlapping available level
  from `level_scanner`.

Ablation cohort:

- `reclaim_rejection_without_level_provenance`
- same rules but does not require level overlap.
- Purpose: determine whether provenance is load-bearing or only decorative.

Baseline cohort:

- `reclaim_swing_baseline`
- deterministic sweep+reclaim baseline reconstructed over the same study
  window using event-study/current feature rules, not live production DB.
- Purpose: compare throughput and monthly P&L correlation.

Control cohort:

- `control_random_wicks`
- deterministic calendar-matched and side-matched wick events at non-extremes,
  excluding primary event IDs.
- Fixed seed or deterministic hash ordering only in research code.
- Purpose: verify rejection-at-extreme adds information beyond ordinary wick
  movement.

Monthly correlation strategy:

1. Compute fixed-exit P&L per event.
2. Bucket P&L by UTC calendar month and cohort.
3. Align primary and baseline monthly series.
4. Missing months are filled with 0 only after alignment and documented.
5. Compute Pearson correlation. If fewer than 3 aligned months have non-zero
   observations, mark F-5 `INCONCLUSIVE_DATA_GAP`.

## 7. Data and Replay Primitives

Canonical DB:

```text
research_lab/data/crowded_unwind_backtest.db
```

Study window:

```text
2022-01-01 <= timestamp < 2026-03-01
```

Required tables:

- `candles` for BTCUSDT 15m OHLCV.
- `aggtrade_buckets` for 60s TFI/CVD confluence.
- Optional metadata: `funding`, `open_interest`, `force_orders`.
- `signal_candidates` and `trade_log` are reference surfaces only, not the
  primary event source.

Data validation before event generation:

- verify required tables exist;
- verify BTCUSDT 15m candle coverage over the study window;
- verify no duplicate candle timestamps;
- verify no OHLC violations;
- verify ATR is computable after warmup;
- verify `aggtrade_buckets` coverage can map to 15m bars;
- fail closed or report `INCONCLUSIVE_DATA_GAP` if confluence data coverage is
  insufficient.

No production database or SSH production query is needed for this diagnostic.

## 8. Test Plan

Unit tests:

- `test_rejection_detection_requires_wick_to_body_threshold`
- `test_rejection_detection_requires_swing_extreme_confirmation`
- `test_state_known_bar_is_detection_plus_one`
- `test_entry_candidate_bar_requires_reclaim_AND_confluence`
- `test_returns_measured_from_return_start_bar_not_detection_bar`
- `test_level_provenance_lookup_uses_only_available_levels`
- `test_mfe_before_entry_uses_high_low_in_window_after_detection_before_entry`
- `test_control_cohort_random_wicks_does_not_match_primary_cohort`
- `test_correlation_calculation_uses_aligned_monthly_buckets`
- `test_deterministic_output_two_runs_produce_identical_json_sha256`

Integration tests:

- Load a small synthetic OHLCV DataFrame, scan levels, generate one known
  primary event, and verify all timing timestamps.
- Run deterministic output generation twice and compare SHA256.
- Verify no generated event uses a level with `available_at` after
  `state_known_bar`.

Validation commands for implementation commit:

```text
python -m pytest -o addopts= tests/test_reclaim_rejection_feasibility_v1.py -q
python -m compileall research_lab/diagnostics/reclaim_rejection_feasibility_v1.py tests/test_reclaim_rejection_feasibility_v1.py
python -m research_lab.diagnostics.reclaim_rejection_feasibility_v1
```

## 9. Acceptance Criteria For Diagnostic Completion

Completion does not require the hypothesis to pass. Completion requires:

- plan approved before implementation;
- diagnostic writes deterministic event rows and cohort summaries;
- JSON output exists at
  `research_lab/analysis_output/reclaim_rejection_feasibility_v1.json`;
- SHA256 output exists at
  `research_lab/analysis_output/reclaim_rejection_feasibility_v1.sha256`;
- markdown report exists at
  `research_lab/analysis_output/reclaim_rejection_feasibility_v1_report.md`;
- F-1 through F-6 verdict table exists;
- all required cohorts are present or data-gap reasons are explicit;
- primary returns use `return_start_bar`, never `detection_bar`;
- MFE before/after entry is reported;
- baseline comparison and monthly correlation are reported;
- tests pass;
- compile validation passes;
- no production modules are modified;
- no parameter tuning or rescue is performed after results.

## 10. Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| Swing confirmation quietly introduces delayed labels | 3/5 | 5/5 | Exclude events whose swing confirmation is not known by `state_known_bar`, and test this explicitly. |
| CVD interpretation from `aggtrade_buckets.cvd` is wrong | 3/5 | 4/5 | Document exact CVD proxy, add coverage stats, and let audit decide before implementation. |
| Level provenance becomes a hidden future-data leak | 2/5 | 5/5 | Require `level.available_at <= state_known_bar`; unit test unavailable future level exclusion. |
| Primary edge appears only from detection-bar returns | 4/5 | 4/5 | F-6 invalidates if detection-bar edge is >30% better. |
| Control cohort is too weak or mismatched | 3/5 | 3/5 | Calendar/side-match controls and document matching logic. |
| Monthly correlation is unstable with sparse events | 3/5 | 3/5 | Mark F-5 `INCONCLUSIVE_DATA_GAP` when aligned monthly support is insufficient. |
| Throughput increases but quality collapses | 3/5 | 4/5 | F-1/F-2 gate quality before any promotion discussion. |
| Scope creep into production setup implementation | 2/5 | 5/5 | Write scope limited to research diagnostics, analysis output, docs/research, and tests. |

## 11. Open Questions For Operator

1. Should F-3 use `mfe_before / mfe_post_entry_5bar` exactly as handed off, or
   the operating-model consumed-share formula
   `mfe_before / (mfe_before + mfe_after)`? This plan follows the handoff
   threshold for M3 but will report both if implemented.
2. Is `aggtrade_buckets.cvd` accepted as the CVD confluence source given
   `cvd_price_history` is empty in the canonical DB?
3. Should `reclaim_swing_baseline` use the current `FeatureEngine` event-study
   defaults or the frozen trial-00095 parameter set if those diverge?
4. If F-5 is `INCONCLUSIVE_DATA_GAP` due sparse monthly overlap, should the
   overall verdict fail closed or remain inconclusive pending longer/multi-asset
   sample?

None of these block writing this plan. They should be resolved in Claude audit
or before implementation commit.
