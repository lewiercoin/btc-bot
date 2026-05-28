# LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1

## Executive Summary

Recommendation: **STOP**

This is a research-only timeframe accessibility check. The 15m STOP verdict remains final and is used only as an audited reference.

- Main cohort events: `10302`
- Main post-entry ER proxy: `-0.102252`
- Main profit factor proxy: `0.427068`
- Main win rate: `0.357989`
- Main median MFE consumed before entry: `1.000000`
- STOP reasons: `median_mfe_consumed_gt_70pct, post_entry_er_lt_0_5, control_cohort_outperforms_main`
- Interpretation: `mechanism invalidated on both 15m and 5m; close liquidation burst reversal family`

## Mechanism

- Mechanism is unchanged from the audited 15m diagnostic.
- Detect an equal-level sweep at bar `i` using completed 5m candles only.
- Sum expected-side force-order notional across bars `i` through `i+2`.
- Compare that notional to a pre-sweep rolling baseline ending at `i-1`.
- Enter at bar `i+3`; primary returns start at `i+3`.

## 5m Candle Source And Quality

- Source: `{'source': 'binance_fapi_klines_rest', 'symbol': 'BTCUSDT', 'timeframe': '5m', 'rows': '307008', 'start_time_utc': '2022-01-01T00:00:00+00:00', 'end_time_utc': '2024-12-01T23:55:00+00:00', 'created_at_utc': '2026-05-28T15:43:14.910852+00:00', 'path': 'research_lab\\data\\btcusdt_5m_klines_20220101_20241201.db', 'method': 'cache'}`
- Candles: `{'rows': 307008, 'start_time_utc': '2022-01-01T00:00:00+00:00', 'end_time_utc': '2024-12-01T23:55:00+00:00', 'duplicate_timestamps': 0, 'non_monotonic_timestamps': 0, 'ohlc_violations': 0, 'missing_bar_gaps': 0, 'inferred_step_seconds': 300}`
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
| `entry_delay_minutes` | `15` |

Primary returns are measured from `entry_candidate_bar`, not `detection_bar`. Detection-bar movement is used only for MFE-before-entry accessibility.

## Cohort Metrics

| Cohort | Count | ER | Median R | PF | Win Rate | Median MFE Consumed | Positive Folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `main_liquidation_burst_reversal` | 10302 | -0.102252 | -0.078871 | 0.427068 | 0.357989 | 1.000000 | 0 |
| `control_non_liquidation_sweeps` | 53727 | -0.099595 | -0.095351 | 0.310996 | 0.277012 | 0.783686 | 0 |
| `control_opposite_side_liquidations` | 2901 | -0.119855 | -0.119182 | 0.399361 | 0.306791 | 0.857406 | 0 |
| `control_shifted_entry` | 10302 | -0.095195 | -0.079461 | 0.447626 | 0.356533 | 1.000000 | 0 |
| `control_flow_only_ablation` | 31606 | -0.102300 | -0.083631 | 0.461496 | 0.360754 | 1.000000 | 0 |

## 15m vs 5m Comparison

| Metric | 15m result | 5m result |
| --- | ---: | ---: |
| Entry delay | 45 min | 15 min |
| Main events | 5412 | 10302 |
| Main ER | -0.100795 | -0.102252 |
| Main PF | 0.583975 | 0.427068 |
| Main win rate | 0.408906 | 0.357989 |
| Median MFE consumed | 1.000000 | 1.000000 |
| Control outperformers | 3 | 2 |
| Invalidation gate | STOP | STOP |

## MFE Accessibility

- Main median MFE before entry: `81.100000`
- Main median MFE after entry: `95.000000`
- Main median MAE after entry: `103.700000`
- 70% consumed threshold breached: `True`

## Control Cohorts

- Non-liquidation sweeps: sweep detected, expected-side liquidation below 0.5x baseline.
- Opposite-side liquidations: sweep detected, wrong-side liquidation burst.
- Shifted-entry: same main signal, but entry delayed from `i+3` to `i+5`.
- Flow-only ablation: liquidation burst without sweep requirement.

Control outperformers: `['control_non_liquidation_sweeps', 'control_shifted_entry']`

## Trial-00095 Benchmark Comparison

- Reference benchmark: `{'er': 2.1, 'profit_factor': 4.6, 'trades': 271, 'entry_timing': 'sweep + reclaim around 1-2 bars from sweep', 'source': 'approved planning document / milestone tracker reference'}`
- Exact `trial_trades` available: `False`
- Trade-log overlap: `{'available': True, 'note': 'Local trade_log is not an exact trial_trades table; use as rough timestamp overlap only.', 'trade_log_count': 74, 'main_event_count': 10302, 'overlap_count': 17, 'overlap_pct_of_main': 0.0016501650165016502}`

## Invalidation Criteria Evaluation

- Recommendation: `STOP`
- STOP reasons: `['median_mfe_consumed_gt_70pct', 'post_entry_er_lt_0_5', 'control_cohort_outperforms_main']`
- EXPLORE gate passed: `False`

## Artifact

- JSON path: `research_lab\reports\liquidation_burst_reversal_5m_feasibility_v1.json`
- JSON SHA256: `649879D60CF4FD95E58A0184E9CF0CFDE7A88C54B5218D40B1D4C2DD98F3DE78`

## Recommendation: STOP

**Reason:** median_mfe_consumed_gt_70pct; post_entry_er_lt_0_5; control_cohort_outperforms_main

**Family status:** Close this liquidation burst reversal direction if this STOP result is accepted by audit.

**Next:** Claude Code audits this 5m diagnostic implementation and result before any follow-up work.
