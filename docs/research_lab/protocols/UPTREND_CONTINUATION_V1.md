# UPTREND_CONTINUATION_V1

## Scope

This protocol defines a local-only research-lab study for selective BTC uptrend continuation entries.

The objective is to test whether a tightly gated continuation overlay can add expectancy during uptrend regimes without degrading the validated Trial #63 reversal baseline.

This protocol does not authorize:

- live config changes
- core pipeline changes
- parameter promotion
- deployment changes

## Baseline

Reference baseline:

- Trial #63 / Run #13
- reversal-first behavior
- no broad uptrend participation
- anchored expanding walk-forward reference

Baseline reference metrics from the current tracker context:

- expectancy_r: +0.994
- profit_factor: 2.486
- max_drawdown_pct: 5.4%
- trades: 183

## Hypothesis

A narrow uptrend continuation overlay may improve total expectancy if it only activates when all of the following are true:

- regime is `uptrend`
- a high-side sweep is followed by reclaim confirmation
- reclaim strength above the swept level is materially positive
- short-term participation / imbalance is stronger than the default directional threshold
- confluence requirement is stricter than the baseline reversal threshold

The overlay must behave as an additive research-only surface. It must not convert the strategy into a general "allow long in uptrend" relaxation.

## Research Surface

Sample only these research-lab parameters:

- `allow_uptrend_continuation`
- `uptrend_continuation_reclaim_strength_min`
- `uptrend_continuation_participation_min`
- `uptrend_continuation_confluence_multiplier`

All existing Trial #63 reversal parameters remain frozen for this run.

## Parameter Semantics

- `allow_uptrend_continuation`
  - enables the research-only continuation overlay
  - default: `false`

- `uptrend_continuation_reclaim_strength_min`
  - minimum ATR-normalized close above the swept high-side level after reclaim
  - tighter values imply stronger post-sweep acceptance

- `uptrend_continuation_participation_min`
  - minimum positive participation threshold using `tfi_60s`
  - must remain at or above `direction_tfi_threshold`

- `uptrend_continuation_confluence_multiplier`
  - multiplier applied to baseline `confluence_min`
  - must remain greater than `1.0`

## Walk-Forward Method

Use anchored expanding windows aligned to the run14 config:

- train_days: 730
- validation_days: 365
- step_days: 365
- window_mode: `anchored_expanding`
- walkforward_mode: `post_hoc`

Candidate acceptance thresholds:

- min_trades_full_candidate: 120
- max_trades_full_candidate: 300
- min_trades_per_window: 10
- min_expectancy_r_per_window: 0.0
- min_profit_factor_per_window: 1.0
- max_drawdown_pct_per_window: 50.0
- min_sharpe_ratio_per_window: 0.0
- fragility_degradation_threshold_pct: 55.0
- all validation windows must pass

## Success Criteria

A candidate is interesting only if all of the following hold:

- total walk-forward passes under the run14 protocol
- overall expectancy is not worse than the baseline by more than the accepted degradation budget
- no evidence that baseline reversal behavior is broadly degraded
- uptrend long trades are present and isolated in analysis
- uptrend long contribution is additive rather than replacing the legacy edge

## Failure Criteria

Treat the study as a reject / no-promotion outcome if any of the following occur:

- walk-forward failure
- fragility threshold exceeded
- broad degradation of non-uptrend performance
- continuation contribution exists but total expectancy quality deteriorates materially
- trade count increase comes from loose gating rather than selective continuation quality

## Execution Notes

Run locally against the standard source database and research-lab store.

Expected config file:

- `research_lab/configs/run14_uptrend_continuation.json`

Expected outputs:

- experiment-store trials for run14
- walk-forward reports
- run report in `docs/research_lab/runs/RUN14_UPTREND_CONTINUATION.md`
- tracker update in `docs/MILESTONE_TRACKER.md`
