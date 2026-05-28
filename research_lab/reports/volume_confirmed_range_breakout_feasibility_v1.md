# VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1

## Executive Summary

Recommendation: **STOP**

This is a research-only diagnostic. It did not modify production code, settings, trial-00095, execution, FeatureEngine, SignalEngine, Governance, or Risk.

- Main cohort events: `2562`
- Main post-entry ER proxy: `-0.092049`
- Main profit factor proxy: `0.856828`
- Main win rate: `0.414130`
- Main median net return: `-0.002133`
- Main median MFE consumed before entry: `0.149534`
- STOP reasons: `median_net_return_lte_0, post_entry_er_lt_1_2, profit_factor_lt_1_2, weak_win_rate_and_payoff, control_cohort_outperforms_main, walk_forward_fewer_than_2_positive_folds`

## Mechanism

- Define compressed range from prior 20 completed 15m bars.
- Detect completed close outside prior range at bar `i`.
- Require breakout-bar volume >= 1.5x prior 20-bar median volume.
- Require aligned 15m TFI direction.
- Enter at bar `i+1`; primary returns start at `i+1`.

## Schema Pre-Flight

- Required schema missing: `{}`
- Provisional table names present: `{'ohlcv_1h': False, 'features_1h': False, 'trials': False, 'trial_trades': False, 'aggtrade': False, 'funding_rate': False}`
- Adapted schema: `{'price_action': 'candles', 'volume_flow': 'aggtrade_buckets', 'aggtrade': 'aggtrade_buckets', 'funding': 'funding', 'open_interest': 'open_interest', 'benchmark_trades': None}`

## Data Quality

- Candles: `{'rows': 195347, 'start_time_utc': '2020-09-01T00:00:00+00:00', 'end_time_utc': '2026-03-28T20:30:00+00:00', 'duplicate_timestamps': 0, 'non_monotonic_timestamps': 0, 'ohlc_violations': 0, 'missing_bar_gaps': 0, 'inferred_step_seconds': 900, 'zero_volume_bars': 10}`
- Aggtrade buckets: `{'rows': 195150, 'aligned_15m_candle_rows': 195148, 'missing_aligned_candle_rows': 199, 'alignment_pct': 0.9989812999431781}`

## Timing Model Verification

| Bar | Value |
| --- | --- |
| `range_detection_bar` | `i-1` |
| `detection_bar` | `i` |
| `state_known_bar` | `i` |
| `confirmation_bar` | `i` |
| `entry_candidate_bar` | `i+1` |
| `label_available_bar` | `i+1` |
| `return_start_bar` | `i+1` |
| `primary_returns_from_detection_bar` | `False` |

Primary returns are measured from `entry_candidate_bar`, not `detection_bar` or intrabar breakout price.

## Cohort Metrics

| Cohort | Count | ER | Median R | PF | Win Rate | Median Net | Median MFE Consumed | Positive Folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `main_volume_confirmed_range_breakout` | 2562 | -0.092049 | -0.213301 | 0.856828 | 0.414130 | -0.002133 | 0.149534 | 0 |
| `control_price_only_range_breakouts` | 2756 | -0.100998 | -0.212370 | 0.846560 | 0.415820 | -0.002124 | 0.141250 | 0 |
| `control_breakout_without_volume_spike` | 22 | 0.320244 | 0.420516 | 1.791826 | 0.681818 | 0.004205 | 0.029609 | 3 |
| `control_opposite_flow_breakout` | 33 | -0.387986 | -0.035784 | 0.532436 | 0.484848 | -0.000358 | 0.113990 | 1 |
| `control_shifted_entry` | 2562 | -0.067614 | -0.157758 | 0.886406 | 0.432475 | -0.001578 | 0.145379 | 0 |
| `control_random_offset` | 2528 | -0.085789 | -0.105231 | 0.846375 | 0.447785 | -0.001052 | 0.174139 | 0 |
| `control_wide_range_breakout` | 2620 | -0.165903 | -0.230137 | 0.780315 | 0.424809 | -0.002301 | 0.171151 | 0 |

## MFE Accessibility

- Main median MFE before entry: `61.485000`
- Main median MFE after entry: `361.285000`
- Main median MAE after entry: `359.830000`
- Main median entry-to-MFE bars: `5.000000`
- 70% consumed threshold breached: `False`

## Control Cohorts

- Price-only range breakouts: same compressed range and breakout, no volume/TFI requirements.
- Breakout without volume spike: aligned TFI but low breakout-bar volume.
- Opposite-flow breakout: volume spike but TFI points opposite breakout direction.
- Shifted-entry: same main signal, entry delayed from `i+1` to `i+3`.
- Random-offset: main events shifted by deterministic +137 bars.
- Wide-range breakout: same breakout/volume/TFI requirements but prior range above 65th percentile.

Control outperformers: `['control_breakout_without_volume_spike', 'control_shifted_entry', 'control_random_offset']`

## Trial-00095 Benchmark Comparison

- Reference benchmark: `{'er': 2.1, 'profit_factor': 4.6, 'trades': 271, 'win_rate': 0.56, 'source': 'approved planning document / milestone tracker reference'}`
- Exact `trial_trades` available: `False`
- Trial trade schema status: `missing in inspected databases`
- Store metrics discovered: `True`
- Trade-log overlap: `{'available': True, 'note': 'Local trade_log is not an exact trial_trades table; use as rough timestamp overlap only.', 'trade_log_count': 74, 'main_event_count': 2562, 'overlap_count': 7, 'overlap_pct_of_main': 0.00273224043715847}`

Exact `trial_trades` are not assumed. Any local `trade_log` overlap is documented as rough timestamp overlap only.

## Walk-Forward Metrics

| Fold | Count | ER | Median Net | Win Rate | Positive Median Net |
| --- | ---: | ---: | ---: | ---: | --- |
| `fold_1` | 904 | -0.173341 | -0.002549 | 0.423673 | `False` |
| `fold_2` | 669 | -0.125384 | -0.003057 | 0.367713 | `False` |
| `fold_3` | 556 | 0.043113 | -0.001577 | 0.442446 | `False` |
| `fold_4` | 433 | -0.044382 | -0.001537 | 0.429561 | `False` |

## Invalidation Criteria Evaluation

- Recommendation: `STOP`
- STOP reasons: `['median_net_return_lte_0', 'post_entry_er_lt_1_2', 'profit_factor_lt_1_2', 'weak_win_rate_and_payoff', 'control_cohort_outperforms_main', 'walk_forward_fewer_than_2_positive_folds']`
- EXPLORE gate passed: `False`

## Artifact

- JSON path: `C:\development\btc-bot\research_lab\reports\volume_confirmed_range_breakout_feasibility_v1.json`
- JSON SHA256: `53C27E016D7E39C343D6C7A0F6F889A00C870BA32394EBD445BCB933906E49E8`

## Recommendation: STOP

**Reason:** median_net_return_lte_0; post_entry_er_lt_1_2; profit_factor_lt_1_2; weak_win_rate_and_payoff; control_cohort_outperforms_main; walk_forward_fewer_than_2_positive_folds

**Next:** Claude Code audits this diagnostic implementation and result before any follow-up work.
