# TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1

## Executive Summary

Recommendation: **STOP**

This is a research-only diagnostic. It did not modify production code, settings, trial-00095, execution, FeatureEngine, SignalEngine, Governance, or Risk.

- Main cohort events: `321`
- Main post-entry ER: `-0.026757`
- Main profit factor: `0.953841`
- Main win rate: `0.429907`
- Main median net return: `-0.001811`
- Main median MFE consumed before entry: `0.215248`
- STOP reasons: `median_net_return_lte_0, post_entry_er_lt_1_2, profit_factor_lt_1_2, weak_win_rate_and_payoff, walk_forward_fewer_than_2_positive_folds`

## Mechanism

- Latched range state: ADX <= 20 AND CHOP >= 61.8
- Explicit trend state: ADX >= 25 AND CHOP <= 38.2 AND |+DI - -DI| >= 5
- Direction from +DI/-DI at transition bar
- Hysteresis: latched state machine with 12-bar staleness limit
- Entry at bar i+1; primary returns start at i+1
- 150-candle warmup for Wilder smoothing stability

## ADX Lag Audit

- Median ADX lag bars: `6.00`
- Mean ADX lag bars: `5.72`
- Median lag-adjusted MFE consumed: `0.695586`
- Mean lag-adjusted MFE consumed: `0.678300`
- Lag STOP triggered: `False`

## Data Quality

- Candles: `{'rows': 195347, 'start_time_utc': '2020-09-01T00:00:00+00:00', 'end_time_utc': '2026-03-28T20:30:00+00:00', 'duplicate_timestamps': 0, 'non_monotonic_timestamps': 0, 'ohlc_violations': 0, 'missing_bar_gaps': 0, 'inferred_step_seconds': 900, 'zero_volume_bars': 10}`

## Timing Model Verification

| Bar | Value |
| --- | --- |
| `detection_bar` | `i` |
| `state_known_bar` | `i (at close)` |
| `confirmation_bar` | `i` |
| `entry_candidate_bar` | `i+1` |
| `return_start_bar` | `i+1` |
| `primary_returns_from_detection_bar` | `False` |

Primary returns are measured from `entry_candidate_bar = i+1`, not from `detection_bar` or `raw_move_start_bar`.

## Cohort Metrics

| Cohort | Count | ER | Median R | PF | Win Rate | Median Net | Median MFE Consumed | Positive Folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `main_range_to_trend` | 321 | -0.026757 | -0.181082 | 0.953841 | 0.429907 | -0.001811 | 0.215248 | 0 |
| `control_simple_volatility` | 2853 | -0.094113 | -0.154060 | 0.843015 | 0.424465 | -0.001541 | 0.219343 | 0 |
| `control_adx_only` | 2202 | -0.055384 | -0.157116 | 0.892198 | 0.413715 | -0.001571 | 0.200217 | 0 |
| `control_chop_only` | 1188 | -0.070692 | -0.181073 | 0.876296 | 0.431818 | -0.001811 | 0.242581 | 0 |
| `control_shifted_entry` | 321 | -0.087133 | -0.156355 | 0.849104 | 0.417445 | -0.001564 | 0.367315 | 0 |
| `control_same_state_non_transition` | 13793 | -0.051937 | -0.128210 | 0.900797 | 0.438411 | -0.001282 | 0.206501 | 0 |
| `control_opposite_regime` | 33 | -0.087971 | -0.095335 | 0.807497 | 0.454545 | -0.000953 | 0.137146 | 1 |
| `control_random_offset` | 320 | -0.204148 | -0.187109 | 0.654067 | 0.418750 | -0.001871 | 0.169026 | 1 |

## MFE Accessibility

- Main median MFE before entry: `109.350000`
- Main median MFE after entry: `382.500000`
- Main median MAE after entry: `371.640000`
- Main median entry-to-MFE bars: `6.000000`
- 70% consumed threshold breached: `False`

## Control Cohorts

- Simple volatility: 14-bar vol rising from <35th to >65th percentile, direction from 20-bar momentum.
- ADX-only: latched ADX<=20 to ADX>=25, no CHOP. Direction from +DI/-DI.
- CHOP-only: latched CHOP>=61.8 to CHOP<=38.2, no ADX. Direction from 20-bar momentum.
- Shifted-entry: same main signal, entry delayed from i+1 to i+3.
- Same-state non-transition: explicit trend state but prior latched state was NOT range.
- Opposite-regime: trend-to-range transition, continuation in prior trend direction.
- Random-offset: main events shifted by deterministic +137 bars.

Control outperformers: `[]`

## Trial-00095 Benchmark Comparison

- Reference benchmark: `{'er': 2.1, 'profit_factor': 4.6, 'trades': 271, 'win_rate': 0.56, 'source': 'approved planning document / milestone tracker reference'}`

## Walk-Forward Metrics

| Fold | Count | ER | Median Net | Win Rate | Positive Median Net |
| --- | ---: | ---: | ---: | ---: | --- |
| `fold_1` | 89 | 0.025666 | -0.002427 | 0.415730 | `False` |
| `fold_2` | 77 | 0.121480 | -0.001811 | 0.454545 | `False` |
| `fold_3` | 84 | -0.125268 | -0.001585 | 0.440476 | `False` |
| `fold_4` | 71 | -0.136688 | -0.001887 | 0.408451 | `False` |

## Invalidation Criteria Evaluation

- Recommendation: `STOP`
- STOP reasons: `['median_net_return_lte_0', 'post_entry_er_lt_1_2', 'profit_factor_lt_1_2', 'weak_win_rate_and_payoff', 'walk_forward_fewer_than_2_positive_folds']`
- EXPLORE gate passed: `False`

## Artifact

- JSON path: `C:\development\btc-bot\research_lab\reports\trend_range_state_shift_feasibility_v1.json`
- JSON SHA256: `87656B8D01BDA90C6E227B57B7B9D9A04B5AA79E9ADAD4184E8F9C6F6EFFD006`

## Recommendation: STOP

**Reason:** median_net_return_lte_0; post_entry_er_lt_1_2; profit_factor_lt_1_2; weak_win_rate_and_payoff; walk_forward_fewer_than_2_positive_folds

**Next:** Claude Code audits this diagnostic implementation and result before any follow-up work.
