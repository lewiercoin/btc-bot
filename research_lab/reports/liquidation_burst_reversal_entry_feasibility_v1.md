# LIQUIDATION_BURST_REVERSAL_ENTRY_FEASIBILITY_V1

## Executive Summary

Recommendation: **STOP**

This is a research-only diagnostic. It did not modify production code, settings, trial-00095, execution, FeatureEngine, SignalEngine, Governance, or Risk.

- Main cohort events: `5412`
- Main post-entry ER proxy: `-0.100795`
- Main profit factor proxy: `0.583975`
- Main win rate: `0.408906`
- Main median MFE consumed before entry: `1.000000`
- STOP reasons: `median_mfe_consumed_gt_70pct, post_entry_er_lt_0_5, control_cohort_outperforms_main`

## Mechanism

- Detect an equal-level sweep at bar `i` using completed 15m candles only.
- Sum expected-side force-order notional across bars `i` through `i+2`.
- Compare that notional to a pre-sweep rolling baseline ending at `i-1`.
- Enter at bar `i+3`; primary returns start at `i+3`.

## Schema Pre-Flight

- Required schema missing: `{}`
- Provisional table names present: `{'ohlcv_1h': False, 'features_1h': False, 'trials': False, 'trial_trades': False, 'aggtrade': False, 'funding_rate': False}`
- Adapted schema: `{'price_action': 'candles', 'liquidations': 'force_orders', 'aggtrade': 'aggtrade_buckets', 'funding': 'funding', 'open_interest': 'open_interest', 'benchmark_trades': None}`

## Data Quality

- Candles: `{'rows': 195347, 'start_time_utc': '2020-09-01T00:00:00+00:00', 'end_time_utc': '2026-03-28T20:30:00+00:00', 'duplicate_timestamps': 0, 'non_monotonic_timestamps': 0, 'ohlc_violations': 0, 'missing_bar_gaps': 0, 'inferred_step_seconds': 900}`
- Force orders: `{'rows': 146864, 'mapped_rows': 146864, 'start_time_utc': '2022-01-01T00:02:07.244000+00:00', 'end_time_utc': '2024-12-01T23:58:59.379000+00:00', 'buy_rows': 61539, 'sell_rows': 85325, 'buy_notional': 709434600.49158, 'sell_notional': 1248871934.20612}`

## Timing Model Verification

| Bar | Value |
| --- | --- |
| `detection_bar` | `i` |
| `state_known_bar` | `i+2` |
| `confirmation_bar` | `i+2` |
| `entry_candidate_bar` | `i+3` |
| `label_available_bar` | `i+3` |
| `return_start_bar` | `i+3` |
| `primary_returns_from_detection_bar` | `False` |

Primary returns are measured from `entry_candidate_bar`, not `detection_bar`. Detection-bar movement is used only for MFE-before-entry accessibility.

## Cohort Metrics

| Cohort | Count | ER | Median R | PF | Win Rate | Median MFE Consumed | Positive Folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `main_liquidation_burst_reversal` | 5412 | -0.100795 | -0.072107 | 0.583975 | 0.408906 | 1.000000 | 0 |
| `control_non_liquidation_sweeps` | 16877 | -0.097797 | -0.095220 | 0.489054 | 0.340997 | 0.767511 | 0 |
| `control_opposite_side_liquidations` | 1848 | -0.081948 | -0.113990 | 0.651116 | 0.367424 | 0.834601 | 0 |
| `control_shifted_entry` | 5412 | -0.086169 | -0.075984 | 0.621412 | 0.404287 | 1.000000 | 0 |
| `control_flow_only_ablation` | 17568 | -0.103654 | -0.078610 | 0.595824 | 0.410291 | 1.000000 | 0 |

## MFE Accessibility

- Main median MFE before entry: `124.050000`
- Main median MFE after entry: `145.550000`
- Main median MAE after entry: `159.850000`
- 70% consumed threshold breached: `True`

## Control Cohorts

- Non-liquidation sweeps: sweep detected, expected-side liquidation below 0.5x baseline.
- Opposite-side liquidations: sweep detected, wrong-side liquidation burst.
- Shifted-entry: same main signal, but entry delayed from `i+3` to `i+5`.
- Flow-only ablation: liquidation burst without sweep requirement.

Control outperformers: `['control_non_liquidation_sweeps', 'control_opposite_side_liquidations', 'control_shifted_entry']`

## Trial-00095 Benchmark Comparison

- Reference benchmark: `{'er': 2.1, 'profit_factor': 4.6, 'trades': 271, 'entry_timing': 'sweep + reclaim around 1-2 bars from sweep', 'source': 'approved planning document / milestone tracker reference'}`
- Exact `trial_trades` available: `False`
- Trial trade schema status: `missing in inspected databases`
- Store metrics discovered: `True`
- Trade-log overlap: `{'available': True, 'note': 'Local trade_log is not an exact trial_trades table; use as rough timestamp overlap only.', 'trade_log_count': 74, 'main_event_count': 5412, 'overlap_count': 17, 'overlap_pct_of_main': 0.003141167775314117}`

The inspected market database does not contain `trial_trades`; exact trade-overlap analysis is therefore schema-blocked for this artifact. The report uses the approved trial-00095 reference metrics and documents any available store-level trial metrics separately.

## Invalidation Criteria Evaluation

- Recommendation: `STOP`
- STOP reasons: `['median_mfe_consumed_gt_70pct', 'post_entry_er_lt_0_5', 'control_cohort_outperforms_main']`
- EXPLORE gate passed: `False`

## Artifact

- JSON path: `research_lab\reports\liquidation_burst_reversal_entry_feasibility_v1.json`
- JSON SHA256: `ADCBCCDCAED53CE1E3BBAD496B3608712862ABC539558AFEB7B0A0B3D6C7EB41`

## Recommendation: STOP

**Reason:** median_mfe_consumed_gt_70pct; post_entry_er_lt_0_5; control_cohort_outperforms_main

**Next:** Claude Code audits this diagnostic implementation and result before any follow-up work.
