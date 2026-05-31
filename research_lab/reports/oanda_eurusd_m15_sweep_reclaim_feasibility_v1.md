# OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1

**Date:** 2026-05-31T20:13:25.115896+00:00
**Type:** Research-only OANDA sweep/reclaim transfer diagnostic
**Recommendation:** STOP

## Executive Summary

This diagnostic tests whether the OHLC-only sweep/reclaim core from `btc-bot` transfers to OANDA `EUR_USD` M15.
It does not validate SMC, does not use OB/FVG/mitigation logic, and does not modify production code.
The prior `XAU_USD H1` strict transfer remains STOP; this diagnostic tests one separately approved `EUR_USD M15` candidate.

- Main events: `1547`
- Main ER: `-0.2226`
- Main PF: `0.7146`
- Main win rate: `42.79%`
- Main median net return at 0.015% cost: `-0.0159%`
- Main median MFE consumed before entry: `11.63%`
- Positive folds: `0 / 4`
- STOP reasons: `median_net_return_lte_0_at_0_015pct_cost, er_lt_1_0, profit_factor_lt_1_2, control_cohort_outperforms_main:control_opposite_direction,control_wide_range_high_volatility, walk_forward_fewer_than_2_positive_folds:0`

## Data Quality

| Field | Value |
| --- | ---: |
| Candle count | 59989 |
| First candle | 2024-01-01T22:00:00+00:00 |
| Last candle | 2026-05-29T20:45:00+00:00 |
| OHLC bad rows | 0 |
| Duplicate timestamps | 0 |
| Gaps > 24h | 129 |
| Gaps > 72h | 0 |
| Max gap hours | 49.25 |
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
| `main_sweep_reclaim` | 1547 | -0.2226 | 0.7146 | 42.79% | -0.0159% | 11.63% |
| `control_sweep_without_reclaim` | 20503 | -2.0280 | 0.5988 | 41.26% | -0.0141% | 38.26% |
| `control_reclaim_without_equal_level_sweep` | 0 | N/A | N/A | N/A | N/A | N/A |
| `control_random_offset_137` | 1544 | -1.3387 | 0.5276 | 40.93% | -0.0141% | 28.79% |
| `control_shifted_entry_plus2` | 1547 | -1.7467 | 0.4306 | 44.73% | -0.0115% | 38.89% |
| `control_shifted_entry_plus3` | 1547 | -2.4349 | 0.3920 | 45.77% | -0.0083% | 44.16% |
| `control_opposite_direction` | 1547 | -0.0926 | 0.9842 | 44.09% | -0.0141% | 49.68% |
| `control_shallow_sweep` | 1814 | -0.4719 | 0.5630 | 40.30% | -0.0141% | 12.28% |
| `control_wide_range_high_volatility` | 348 | -0.1719 | 0.7685 | 40.52% | -0.0169% | 11.02% |

## Direction Split

| Direction | Count | ER | PF | Win Rate | Median Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| `LONG` | 1037 | -0.2490 | 0.6823 | 41.56% | -0.0159% |
| `SHORT` | 510 | -0.1689 | 0.7812 | 45.29% | -0.0136% |

## Walk-Forward Folds

| Fold | Count | ER | PF | Median Net | Positive |
| --- | ---: | ---: | ---: | ---: | --- |
| `fold_1_2024H1` | 215 | -0.2185 | 0.6690 | -0.0076% | False |
| `fold_2_2024H2` | 266 | -0.0820 | 0.8887 | -0.0094% | False |
| `fold_3_2025` | 806 | -0.2531 | 0.6939 | -0.0202% | False |
| `fold_4_2026` | 260 | -0.2752 | 0.6457 | -0.0163% | False |

## Cost Sensitivity

| Round-trip Cost | Count | ER | PF | Win Rate | Median Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| `0.0100%` | 1547 | -0.1501 | 0.7970 | 44.86% | -0.0109% |
| `0.0150%` | 1547 | -0.2226 | 0.7146 | 42.79% | -0.0159% |
| `0.0250%` | 1547 | -0.3676 | 0.5758 | 38.72% | -0.0259% |

## Baseline Comparison

| Metric | BTC trial-00095 | OANDA EUR_USD M15 main |
| --- | ---: | ---: |
| ER | 2.121 | -0.2226 |
| PF | 4.216 | 0.7146 |
| Win rate | 56.57% | 42.79% |
| Trades / events | 274 | 1547 |

## Invalidation Criteria Evaluation

- Recommendation: `STOP`
- STOP reasons: `['median_net_return_lte_0_at_0_015pct_cost', 'er_lt_1_0', 'profit_factor_lt_1_2', 'control_cohort_outperforms_main:control_opposite_direction,control_wide_range_high_volatility', 'walk_forward_fewer_than_2_positive_folds:0']`
- EXPLORE reasons: `[]`
- Controls better than main: `['control_opposite_direction', 'control_wide_range_high_volatility']`
- Control outperformance gate minimum sample: `25` events
- Smaller control cohorts are reported for inspection but are not decision-grade STOP gates.

## Artifact

- JSON path: `C:/development/btc-bot/research_lab/reports/oanda_eurusd_m15_sweep_reclaim_feasibility_v1.json`
- JSON SHA256: `ea592327ced64afc316a57381149b5e7afcd23b9ba8e26efce7465be5e6a8750`

## Recommendation

### Verdict: STOP

**Reason:** median_net_return_lte_0_at_0_015pct_cost; er_lt_1_0; profit_factor_lt_1_2; control_cohort_outperforms_main:control_opposite_direction,control_wide_range_high_volatility; walk_forward_fewer_than_2_positive_folds:0

**Next:** Do not port this OANDA sweep/reclaim transfer to runtime. Return to multi-asset crypto scaling or a separately planned OANDA hypothesis.
