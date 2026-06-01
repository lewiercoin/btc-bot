# OANDA_NY_REVERSAL_AFTER_LONDON_EXTENSION_FEASIBILITY_V1

**Date:** 2026-06-01T14:48:20.459673+00:00
**Type:** Research-only OANDA session mean-reversion diagnostic
**Recommendation:** STOP

## 1. Executive Summary

This diagnostic tests one OANDA-native session mechanism: fade extended London moves during NY overlap.
It preserves ASIA_RANGE STOP and sweep/reclaim STOP as closed prior context; it does not rescue or combine them.

- Main events: `516`
- Main ER: `4.4974`
- Main PF: `3.7048`
- Main win rate: `46.71%`
- Main median net return at 0.015% cost: `-0.0088%`
- Main median MFE consumed before entry: `16.31%`
- Positive folds: `0 / 4`
- STOP reasons: `median_net_return_lte_0_at_0_015pct_cost, walk_forward_fewer_than_2_positive_folds:0`

## 2. Prior OANDA Boundary Statement

- `ASIA_RANGE_LONDON_BREAKOUT` remains `STOP` due negative expectancy and control outperformance.
- `EUR_USD M15` sweep/reclaim remains `STOP` due negative expectancy.
- `XAU_USD H1` sweep/reclaim remains `STOP` due sample collapse.
- This is the final OANDA session diagnostic before returning to multi-asset crypto if it stops.

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
| London session | `07:00-12:00 UTC` |
| NY overlap | `13:00-16:00 UTC` |
| Extension threshold | `1.0 * ATR14` |
| Reversal confirmation | `first NY bar close opposite London direction` |
| Entry | `i+1 open` |
| Primary horizon | `5` bars |
| Secondary horizon | `8` bars |
| Tertiary horizon | `10` bars |
| Risk reference | `London continuation extreme + 0.1 * ATR14` |
| Primary cost | `0.0150%` |

## 5. Timing Model Verification

- `london_known_bar` is the first bar after completed 07:00-12:00 UTC London session.
- `state_known_bar = detection_bar` at first NY reversal bar close.
- `entry_candidate_bar = detection_bar + 1`.
- `return_start_bar = entry_candidate_bar`.
- Detection-bar movement is used only for MFE-before-entry audit metrics.

## 6. Main Cohort Metrics

| Cohort | Count | ER | PF | Win Rate | Median Net | Median MFE Consumed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `main_ny_reversal_after_london_extension` | 516 | 4.4974 | 3.7048 | 46.71% | -0.0088% | 16.31% |

## 7. Control Cohort Metrics

| Cohort | Count | ER | PF | Win Rate | Median Net | Median MFE Consumed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `control_random_session_timing_97` | 515 | -0.9341 | 0.8489 | 43.50% | -0.0184% | 29.55% |
| `control_opposite_direction_continuation` | 516 | -0.2675 | 0.6657 | 42.83% | -0.0212% | 39.17% |
| `control_same_reversal_outside_ny_tokyo` | 443 | -0.4223 | 0.2181 | 33.63% | -0.0125% | 18.18% |
| `control_reversal_without_extension` | 625 | 3.3491 | 2.6824 | 47.36% | -0.0076% | 16.30% |
| `control_extension_without_reversal_continuation` | 515 | 0.3471 | 1.3680 | 42.91% | -0.0185% | 16.81% |
| `control_shifted_entry_plus2` | 516 | -2.0236 | 0.5140 | 47.48% | -0.0086% | 38.80% |
| `control_weekday_shuffled` | 515 | -7.8123 | 0.2030 | 45.24% | -0.0159% | 27.54% |
| `control_previous_day_london_extension` | 624 | 4.4467 | 6.2312 | 42.31% | -0.0204% | 16.39% |

## 8. Direction Split

| Direction | Count | ER | PF | Win Rate | Median Net | Median MFE Consumed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `LONG` | 254 | -0.8930 | 0.5464 | 46.06% | -0.0113% | 15.76% |
| `SHORT` | 262 | 9.7233 | 8.1164 | 47.33% | -0.0044% | 16.99% |

## 9. Walk-Forward Folds

| Fold | Count | ER | PF | Median Net | Median MFE Consumed | Positive |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `fold_1_2024H1` | 110 | 0.1128 | 1.0776 | -0.0039% | 16.62% | False |
| `fold_2_2024H2` | 111 | 22.6481 | 12.4644 | -0.0150% | 14.56% | False |
| `fold_3_2025` | 213 | -0.6590 | 0.5821 | -0.0047% | 16.23% | False |
| `fold_4_2026` | 82 | -0.7964 | 0.5430 | -0.0278% | 18.69% | False |

## 10. Cost Sensitivity

| Round-trip Cost | Count | ER | PF | Win Rate | Median Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| `0.00010` | 516 | 5.0215 | 4.2170 | 49.22% | -0.0038% |
| `0.00015` | 516 | 4.4974 | 3.7048 | 46.71% | -0.0088% |
| `0.00020` | 516 | 3.9734 | 3.2451 | 44.38% | -0.0138% |

## 11. Horizon Sensitivity

| Horizon | Count | ER | PF | Win Rate | Median Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| `5_bars` | 516 | 4.4974 | 3.7048 | 46.71% | -0.0088% |
| `8_bars` | 516 | 7.8030 | 4.3880 | 50.19% | 0.0013% |
| `10_bars` | 516 | 5.6001 | 3.3800 | 50.19% | 0.0012% |

## 12. MFE Accessibility

- Median MFE consumed before entry: `16.31%`.
- Median post-entry MFE: `0.000965`.
- Median post-entry MAE: `0.000970`.
- STOP gate: median consumed > 70%. EXPLORE target: < 60%.

## 13. BTC Baseline Comparison

| Metric | BTC trial-00095 | OANDA NY Reversal |
| --- | ---: | ---: |
| ER | 2.121 | 4.4974 |
| PF | 4.216 | 3.7048 |
| Win rate | 56.57% | 46.71% |
| Trades/events | 274 | 516 |

## 14. Invalidation Gate Evaluation

- Recommendation: `STOP`
- STOP reasons: `['median_net_return_lte_0_at_0_015pct_cost', 'walk_forward_fewer_than_2_positive_folds:0']`
- EXPLORE reasons: `[]`
- Controls better than main: `[]`
- Positive folds: `0 / 4`
- Decision-grade control threshold: `25` events

## 15. Session Construction Notes

- Complete London sessions with extension: `516`.
- Complete London sessions all moves: `625`.
- Skipped incomplete London sessions: `130`.
- Valid extended days: `516`.
- Main signal days: `516`.
- Critical continuation control: `continuation control beats main -> STOP if decision-grade`.

## 16. Artifact

- JSON path: `C:/development/btc-bot/research_lab/reports/oanda_ny_reversal_after_london_extension_feasibility_v1.json`
- JSON SHA256: `2a813cffa701c97e1cc62f1e1c970aec1b19852b60c23757ac2a6253297770fe`

## 17. Recommendation

### Verdict: STOP

**Reason:** median_net_return_lte_0_at_0_015pct_cost; walk_forward_fewer_than_2_positive_folds:0

**Next:** Do not pursue OANDA V2 rescue attempts. Per the approved sequence, return to multi-asset crypto expansion unless the user explicitly opens a new research family.
