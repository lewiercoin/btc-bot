# OANDA_XAUUSD_SWEEP_RECLAIM_TRANSFER_FEASIBILITY_V1

**Date:** 2026-05-31T19:07:47.303035+00:00
**Type:** Research-only OANDA sweep/reclaim transfer diagnostic
**Recommendation:** STOP

## Executive Summary

This diagnostic tests whether the OHLC-only sweep/reclaim core from `btc-bot` transfers to OANDA `XAU_USD` H1.
It does not validate SMC, does not use OB/FVG/mitigation logic, and does not modify production code.

- Main events: `11`
- Main ER proxy: `0.6581`
- Main PF proxy: `16.6979`
- Main win rate: `72.73%`
- Main median net return at 0.05% cost: `0.2868%`
- Main median MFE consumed before entry: `16.54%`
- Positive folds: `1 / 4`
- STOP reasons: `sample_size_lt_100:11, er_lt_1_0, walk_forward_fewer_than_2_positive_folds:1`

## Data Quality

| Field | Value |
| --- | ---: |
| Candle count | 14260 |
| First candle | 2024-01-01T23:00:00+00:00 |
| Last candle | 2026-05-29T20:00:00+00:00 |
| OHLC bad rows | 0 |
| Gaps > 24h | 129 |
| Gaps > 72h | 3 |
| Max gap hours | 74.0 |
| Data gate | PASS |

## Timing Model Verification

- `level_known_bar = detection_bar - 1`.
- `state_known_bar = detection_bar` at bar close.
- `entry_candidate_bar = detection_bar + 1` for main events.
- `return_start_bar = entry_candidate_bar`.
- Detection-bar movement is used only for MFE-before-entry audit metrics.

## Cohort Metrics

| Cohort | Count | ER | PF | Win Rate | Median Net | Median MFE Consumed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `main_sweep_reclaim` | 11 | 0.6581 | 16.6979 | 72.73% | 0.2868% | 16.54% |
| `control_sweep_without_reclaim` | 4651 | -0.0545 | 0.7751 | 45.54% | -0.0399% | 38.29% |
| `control_reclaim_without_equal_level_sweep` | 0 | N/A | N/A | N/A | N/A | N/A |
| `control_random_offset_137` | 11 | 0.2204 | 4.3771 | 63.64% | 0.0935% | 86.70% |
| `control_shifted_entry_plus2` | 11 | 0.0675 | 1.1635 | 54.55% | 0.0900% | 28.89% |
| `control_shifted_entry_plus3` | 11 | 0.0900 | 1.2487 | 45.45% | -0.0239% | 35.45% |
| `control_opposite_direction` | 11 | -0.7581 | 0.0233 | 18.18% | -0.3868% | 68.71% |
| `control_shallow_sweep` | 246 | -0.1165 | 0.6398 | 45.93% | -0.0440% | 19.47% |
| `control_wide_range_high_volatility` | 9 | 0.7793 | 18.5666 | 77.78% | 0.5190% | 16.54% |

## Direction Split

| Direction | Count | ER | PF | Win Rate | Median Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| `LONG` | 7 | 0.3112 | 10.9883 | 71.43% | 0.1616% |
| `SHORT` | 4 | 1.2650 | 21.8229 | 75.00% | 1.2928% |

## Walk-Forward Folds

| Fold | Count | ER | PF | Median Net | Positive |
| --- | ---: | ---: | ---: | ---: | --- |
| `fold_1_2024H1` | 1 | 1.3988 | 999.0000 | 1.3988% | True |
| `fold_2_2024H2` | 1 | 0.2868 | 999.0000 | 0.2868% | False |
| `fold_3_2025` | 2 | 0.4991 | 5.1077 | 0.4991% | False |
| `fold_4_2026` | 7 | 0.6507 | 21.8822 | 0.1616% | False |

## Cost Sensitivity

| Round-trip Cost | Count | ER | PF | Win Rate | Median Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| `0.0300%` | 11 | 0.6781 | 19.5944 | 72.73% | 0.3068% |
| `0.0500%` | 11 | 0.6581 | 16.6979 | 72.73% | 0.2868% |
| `0.1000%` | 11 | 0.6081 | 11.6073 | 63.64% | 0.2368% |

## Baseline Comparison

| Metric | BTC trial-00095 | OANDA XAU main |
| --- | ---: | ---: |
| ER | 2.121 | 0.6581 |
| PF | 4.216 | 16.6979 |
| Win rate | 56.57% | 72.73% |
| Trades / events | 274 | 11 |

## Invalidation Criteria Evaluation

- Recommendation: `STOP`
- STOP reasons: `['sample_size_lt_100:11', 'er_lt_1_0', 'walk_forward_fewer_than_2_positive_folds:1']`
- EXPLORE reasons: `[]`
- Controls better than main: `[]`
- Control outperformance gate minimum sample: `25` events
- Smaller control cohorts are reported for inspection but are not decision-grade STOP gates.

## Artifact

- JSON path: `C:/development/btc-bot/research_lab/reports/oanda_xauusd_sweep_reclaim_transfer_feasibility_v1.json`
- JSON SHA256: `797880fbe4c99cc274eef43b6c98bbcb90baaeec3172f9584a82db84b05a9d59`

## Recommendation

### Verdict: STOP

**Reason:** sample_size_lt_100:11; er_lt_1_0; walk_forward_fewer_than_2_positive_folds:1

**Next:** Do not port this OANDA sweep/reclaim transfer to runtime. Return to multi-asset crypto scaling or a separately planned OANDA hypothesis.
