# FUNDING_TILT_FINAL_EXPERIMENT - NUMERIC VALIDATION REPORT

generated_at_utc: `2026-06-05T14:21:16.526234+00:00`
db_path: `storage\btc_bot.db`
verdict: `FAIL`

## Selected Cell

W: `60`
Z: `2.5`
H: `14`
selection_mean_oos_er_folds_1_3: `0.757333`
selection_trades_folds_1_3: `76`

## Frozen Gates

stop_reasons: `['fold_3_er_lte_0:-0.372029', 'degradation_gte_40pct:0.956234', 'main_does_not_beat_all_controls:3_failures']`

| measurement | value |
| --- | ---: |
| `oos_trades` | `104` |
| `overall_er` | `0.5515001782317643` |
| `overall_profit_factor` | `1.6499053595598865` |
| `selection_mean_oos_er_folds_1_3` | `0.757333043002353` |
| `confirmation_fold_4_er` | `0.03314533105305275` |
| `degradation_pct` | `0.9562341411624505` |
| `positive_grid_cells_folds_1_3` | `27` |
| `failed_control_comparisons` | `3` |

## Main vs Controls Per Fold

| fold | control | main_trades | control_trades | main_er | control_er | main_beats |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `fold_1` | `control_random_entry` | 25 | 25 | 1.589467 | 1.647404 | `False` |
| `fold_1` | `control_time_shifted_funding` | 25 | 25 | 1.589467 | -1.525269 | `True` |
| `fold_1` | `control_inverse_signal` | 25 | 28 | 1.589467 | -0.784692 | `True` |
| `fold_2` | `control_random_entry` | 25 | 25 | 1.054561 | -0.055291 | `True` |
| `fold_2` | `control_time_shifted_funding` | 25 | 25 | 1.054561 | 0.519504 | `True` |
| `fold_2` | `control_inverse_signal` | 25 | 44 | 1.054561 | -0.201570 | `True` |
| `fold_3` | `control_random_entry` | 26 | 26 | -0.372029 | -0.513351 | `True` |
| `fold_3` | `control_time_shifted_funding` | 26 | 26 | -0.372029 | -0.494697 | `True` |
| `fold_3` | `control_inverse_signal` | 26 | 37 | -0.372029 | -0.004767 | `False` |
| `fold_4` | `control_random_entry` | 28 | 28 | 0.033145 | -0.662064 | `True` |
| `fold_4` | `control_time_shifted_funding` | 28 | 29 | 0.033145 | -0.024330 | `True` |
| `fold_4` | `control_inverse_signal` | 28 | 34 | 0.033145 | 0.116820 | `False` |

## Cohort Overall Metrics

| cohort | trades | ER | PF | worst_R | max_DD_R | mean_funding_credit_pct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `main_funding_tilt` | 104 | 0.551500 | 1.649905 | -18.539480 | 22.077290 | 0.00026954 |
| `control_inverse_signal` | 143 | -0.189126 | 0.730362 | -6.554774 | 36.320236 | -0.00008079 |
| `control_time_shifted_funding` | 105 | -0.368684 | 0.712192 | -10.561041 | 51.479562 | 0.00014881 |
| `control_random_entry` | 104 | 0.076134 | 1.069577 | -9.349564 | 45.067895 | -0.00003234 |

## Full 27 Cell Table

| cell | W | Z | H | mean_OOS_ER_folds_1_3 | trades_folds_1_3 | PF_folds_1_3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `W30_Z1.5_H3` | 30 | 1.5 | 3 | 0.175041 | 279 | 1.224253 |
| `W30_Z1.5_H7` | 30 | 1.5 | 7 | 0.283531 | 235 | 1.342856 |
| `W30_Z1.5_H14` | 30 | 1.5 | 14 | 0.384218 | 220 | 1.429631 |
| `W30_Z2_H3` | 30 | 2.0 | 3 | 0.173562 | 158 | 1.207805 |
| `W30_Z2_H7` | 30 | 2.0 | 7 | 0.244223 | 144 | 1.277173 |
| `W30_Z2_H14` | 30 | 2.0 | 14 | 0.324686 | 138 | 1.343299 |
| `W30_Z2.5_H3` | 30 | 2.5 | 3 | 0.412497 | 97 | 1.520026 |
| `W30_Z2.5_H7` | 30 | 2.5 | 7 | 0.499072 | 90 | 1.672622 |
| `W30_Z2.5_H14` | 30 | 2.5 | 14 | 0.605944 | 87 | 1.750299 |
| `W60_Z1.5_H3` | 60 | 1.5 | 3 | 0.128946 | 248 | 1.149843 |
| `W60_Z1.5_H7` | 60 | 1.5 | 7 | 0.294252 | 204 | 1.315580 |
| `W60_Z1.5_H14` | 60 | 1.5 | 14 | 0.339958 | 187 | 1.341872 |
| `W60_Z2_H3` | 60 | 2.0 | 3 | 0.217646 | 138 | 1.249220 |
| `W60_Z2_H7` | 60 | 2.0 | 7 | 0.326362 | 116 | 1.301665 |
| `W60_Z2_H14` | 60 | 2.0 | 14 | 0.490898 | 104 | 1.450807 |
| `W60_Z2.5_H3` | 60 | 2.5 | 3 | 0.601501 | 94 | 1.676390 |
| `W60_Z2.5_H7` | 60 | 2.5 | 7 | 0.727935 | 84 | 1.852717 |
| `W60_Z2.5_H14` | 60 | 2.5 | 14 | 0.757333 | 76 | 1.835107 |
| `W90_Z1.5_H3` | 90 | 1.5 | 3 | 0.104864 | 244 | 1.120765 |
| `W90_Z1.5_H7` | 90 | 1.5 | 7 | 0.179968 | 189 | 1.196506 |
| `W90_Z1.5_H14` | 90 | 1.5 | 14 | 0.273800 | 166 | 1.273274 |
| `W90_Z2_H3` | 90 | 2.0 | 3 | 0.284361 | 129 | 1.310496 |
| `W90_Z2_H7` | 90 | 2.0 | 7 | 0.320406 | 109 | 1.274814 |
| `W90_Z2_H14` | 90 | 2.0 | 14 | 0.306386 | 97 | 1.255614 |
| `W90_Z2.5_H3` | 90 | 2.5 | 3 | 0.474459 | 86 | 1.495490 |
| `W90_Z2.5_H7` | 90 | 2.5 | 7 | 0.469361 | 71 | 1.364769 |
| `W90_Z2.5_H14` | 90 | 2.5 | 14 | 0.289967 | 63 | 1.215356 |

## Per Fold Main Distribution

| fold | trades | ER | PF | worst_R | max_DD_R | p10_R | median_R | p90_R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `fold_1` | 25 | 1.589467 | 2.879350 | -8.687924 | 8.687924 | -2.322306 | 0.590073 | 6.980248 |
| `fold_2` | 25 | 1.054561 | 3.549069 | -1.855676 | 2.793768 | -1.294095 | 0.666714 | 3.739004 |
| `fold_3` | 26 | -0.372029 | 0.731933 | -18.539480 | 22.077290 | -2.746666 | -0.095018 | 2.935199 |
| `fold_4` | 28 | 0.033145 | 1.044871 | -6.998700 | 12.485409 | -1.736173 | -0.242469 | 2.489528 |

## Control Matching

random_seed: `20260605`
time_shift_funding_intervals: `17`
fee_rate_taker: `0.0004`
market_slippage_bps: `3.0`
risk_unit_pct: `0.01`

## Verdict: FAIL
