# OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1

**Date:** 2026-06-01T14:17:18.709575+00:00
**Type:** Research-only OANDA session edge diagnostic
**Recommendation:** STOP

## 1. Executive Summary

This diagnostic tests one OANDA-native session mechanism: `EUR_USD M15` Asia range to London breakout.
It does not rescue OANDA sweep/reclaim, does not use SMC logic, does not run Optuna, and does not modify production code.

- Main events: `422`
- Main ER: `-0.0953`
- Main PF: `0.6166`
- Main win rate: `43.13%`
- Main median net return at 0.015% cost: `-0.0203%`
- Main median MFE consumed before entry: `13.33%`
- Positive folds: `0 / 4`
- STOP reasons: `median_net_return_lte_0_at_0_015pct_cost, er_lt_1_0, profit_factor_lt_1_2, control_cohort_outperforms_main:control_random_session_timing_137,control_breakout_without_prior_asia_compression,control_weekday_shuffled,control_previous_day_range_breakout, walk_forward_fewer_than_2_positive_folds:0`

## 2. OANDA Sweep/Reclaim Boundary Statement

- `XAU_USD H1` sweep/reclaim remains `STOP` due sample collapse.
- `EUR_USD M15` sweep/reclaim remains `STOP` due negative expectancy and control outperformance.
- This diagnostic is session-driven forex structure only: Asia range -> London breakout.

## 3. Data Quality

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

## 4. Frozen Parameter Table

| Parameter | Value |
| --- | --- |
| Instrument | `EUR_USD` |
| Timeframe | `M15` |
| Asia range | `00:00-07:00 UTC` |
| London breakout | `07:00-09:00 UTC` |
| Breakout buffer | `0.05 * ATR14` |
| Entry | `i+1 open` |
| Primary horizon | `5` bars |
| Secondary horizon | `8` bars |
| Tertiary horizon | `10` bars |
| Primary cost | `0.0150%` |
| Compression filter | `None` |

## 5. Timing Model Verification

- `range_known_bar` is the first bar after the completed Asia range.
- `state_known_bar = detection_bar` at London breakout bar close.
- `entry_candidate_bar = detection_bar + 1`.
- `return_start_bar = entry_candidate_bar`.
- Detection-bar movement is used only for MFE-before-entry audit metrics.

## 6. Main Cohort Metrics

| Cohort | Count | ER | PF | Win Rate | Median Net | Median MFE Consumed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `main_asia_range_london_breakout` | 422 | -0.0953 | 0.6166 | 43.13% | -0.0203% | 13.33% |

## 7. Control Cohort Metrics

| Cohort | Count | ER | PF | Win Rate | Median Net | Median MFE Consumed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `control_random_session_timing_137` | 421 | -0.0469 | 0.7092 | 42.28% | -0.0096% | 29.17% |
| `control_opposite_direction` | 422 | -5.9064 | 0.4059 | 46.45% | -0.0097% | 50.00% |
| `control_same_breakout_outside_london_ny` | 588 | -0.0956 | 0.6040 | 41.84% | -0.0253% | 24.88% |
| `control_breakout_without_prior_asia_compression` | 183 | -0.0290 | 0.8343 | 45.90% | -0.0167% | 13.33% |
| `control_compression_without_breakout` | 73 | -0.2482 | 0.5728 | 34.25% | -0.0132% | 28.57% |
| `control_shifted_entry_plus2` | 422 | -0.7429 | 0.1812 | 44.31% | -0.0146% | 40.60% |
| `control_weekday_shuffled` | 421 | -0.0896 | 0.6472 | 42.04% | -0.0242% | 34.06% |
| `control_previous_day_range_breakout` | 308 | -0.0397 | 0.7619 | 40.58% | -0.0189% | 21.08% |

## 8. Direction Split

| Direction | Count | ER | PF | Win Rate | Median Net | Median MFE Consumed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `LONG` | 220 | -0.0899 | 0.6377 | 41.82% | -0.0199% | 14.33% |
| `SHORT` | 202 | -0.1013 | 0.5936 | 44.55% | -0.0222% | 12.16% |

## 9. Walk-Forward Folds

| Fold | Count | ER | PF | Median Net | Median MFE Consumed | Positive |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `fold_1_2024H1` | 96 | -0.2030 | 0.4071 | -0.0201% | 10.91% | False |
| `fold_2_2024H2` | 101 | -0.0364 | 0.8353 | -0.0007% | 11.76% | False |
| `fold_3_2025` | 160 | -0.0621 | 0.7152 | -0.0310% | 15.68% | False |
| `fold_4_2026` | 65 | -0.1097 | 0.5203 | -0.0287% | 14.38% | False |

## 10. Cost Sensitivity

| Round-trip Cost | Count | ER | PF | Win Rate | Median Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| `0.00010` | 422 | -0.0715 | 0.6963 | 45.73% | -0.0153% |
| `0.00015` | 422 | -0.0953 | 0.6166 | 43.13% | -0.0203% |
| `0.00020` | 422 | -0.1192 | 0.5459 | 41.47% | -0.0253% |

## 11. Horizon Sensitivity

| Horizon | Count | ER | PF | Win Rate | Median Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| `5_bars` | 422 | -0.0953 | 0.6166 | 43.13% | -0.0203% |
| `8_bars` | 422 | -0.0977 | 0.6640 | 43.36% | -0.0173% |
| `10_bars` | 422 | -0.0898 | 0.7111 | 46.45% | -0.0127% |

## 12. MFE Accessibility

- Median MFE consumed before entry: `13.33%`.
- Median post-entry MFE: `0.000740`.
- Median post-entry MAE: `0.000745`.
- STOP gate: median consumed > 70%. EXPLORE target: < 60%.

## 13. BTC Baseline Comparison

| Metric | BTC trial-00095 | OANDA Asia Range |
| --- | ---: | ---: |
| ER | 2.121 | -0.0953 |
| PF | 4.216 | 0.6166 |
| Win rate | 56.57% | 43.13% |
| Trades/events | 274 | 422 |

## 14. Invalidation Gate Evaluation

- Recommendation: `STOP`
- STOP reasons: `['median_net_return_lte_0_at_0_015pct_cost', 'er_lt_1_0', 'profit_factor_lt_1_2', 'control_cohort_outperforms_main:control_random_session_timing_137,control_breakout_without_prior_asia_compression,control_weekday_shuffled,control_previous_day_range_breakout', 'walk_forward_fewer_than_2_positive_folds:0']`
- EXPLORE reasons: `[]`
- Controls better than main: `['control_random_session_timing_137', 'control_breakout_without_prior_asia_compression', 'control_weekday_shuffled', 'control_previous_day_range_breakout']`
- Positive folds: `0 / 4`
- Decision-grade control threshold: `25` events

## 15. Session Construction Notes

- Complete Asia sessions: `625`.
- Skipped incomplete Asia sessions: `130`.
- Valid session days: `625`.
- Main signal days: `422`.
- Control 5 entry rule: `09:00 open after 08:45 close direction from London net move; no future bars used`.

## 16. Artifact

- JSON path: `C:/development/btc-bot/research_lab/reports/oanda_asia_range_london_breakout_feasibility_v1.json`
- JSON SHA256: `c11be36ee3aca6db802c52e1e4d3a034691cbafee51b4e88edd38020409afa42`

## 17. Recommendation

### Verdict: STOP

**Reason:** median_net_return_lte_0_at_0_015pct_cost; er_lt_1_0; profit_factor_lt_1_2; control_cohort_outperforms_main:control_random_session_timing_137,control_breakout_without_prior_asia_compression,control_weekday_shuffled,control_previous_day_range_breakout; walk_forward_fewer_than_2_positive_folds:0

**Next:** Do not port this OANDA session candidate to runtime. Consider the separately planned `NY_REVERSAL_AFTER_LONDON_EXTENSION` path or return to multi-asset crypto.
