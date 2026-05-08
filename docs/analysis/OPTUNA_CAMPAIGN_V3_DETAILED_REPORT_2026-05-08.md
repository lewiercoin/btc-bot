# OPTUNA-CAMPAIGN-V3 Detailed Report

Generated: 2026-05-08 19:39:58 UTC

Builder note: this is a data report, not a promotion audit. Claude Code remains the evaluator for promotion verdicts.

## 1. Campaign Summary
| Field | Value |
| --- | --- |
| Study name | optuna-default-v3 |
| Target trials | 350 |
| Trials in research store | 350 |
| Optuna trial states | COMPLETE=350 |
| Recommendations saved | 4 |
| Walk-forward reports saved | 4 |
| Failed Optuna trials | 0 |
| Storage snapshot | C:/development/btc-bot/research_lab/research_lab.db.v3 |
| Optuna journal snapshot | C:/development/btc-bot/research_lab/optuna_default_v3.db |

Infrastructure attrs from Optuna study:
- `warm_start_mode`: `wf-winners-only`
- `multivariate_tpe_requested`: `True`
- `multivariate_tpe_effective`: `False`
- `multivariate_tpe_policy`: `disabled_dynamic_bounds:high_vol_leverage,tp2_atr_mult`

Warm-start seed verification:
| Trial | Accepted | Raw ER | Raw PF | DD | Trades | allow_uptrend_continuation | weight_sweep_detected |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 00000 | True | 0.761 | 2.584 | 9.85% | 610 | False | 2.100 |

## 2. Acceptance Statistics
| Metric | Count | Rate |
| --- | --- | --- |
| Accepted trials | 49 | 14.00% |
| Rejected trials | 301 | 86.00% |
| Credible accepted trials (positive ER/PF, trades > 0) | 40 | 11.43% |
| Penalty objective trials | 292 | 83.43% |

Detailed rejection category breakdown:
| Category | Count | Share of all trials | Share of rejected |
| --- | --- | --- | --- |
| low-trade: zero trades | 102 | 29.14% | 33.89% |
| constraint: uptrend participation threshold | 57 | 16.29% | 18.94% |
| constraint: long/uptrend-continuation conflict | 54 | 15.43% | 17.94% |
| low-trade: below threshold | 49 | 14.00% | 16.28% |
| other | 39 | 11.14% | 12.96% |

Top raw rejected reasons:
| Reason | Count |
| --- | --- |
| MIN_TRADES_HARD_BLOCK: trades_count=0 < hard_min_trades=80 | 102 |
| uptrend_continuation_participation_min must be >= direction_tfi_threshold | 57 |
| allow_long_in_uptrend and allow_uptrend_continuation cannot both be enabled | 38 |
| allow_long_in_uptrend and allow_uptrend_continuation cannot both be enabled; uptrend_continuation_participation_min must be >= direction_tfi_threshold | 16 |
| MIN_TRADES_HARD_BLOCK: trades_count=19 < hard_min_trades=80 | 6 |
| MIN_TRADES_HARD_BLOCK: trades_count=13 < hard_min_trades=80 | 4 |
| MIN_TRADES_HARD_BLOCK: trades_count=24 < hard_min_trades=80 | 4 |
| MIN_TRADES_HARD_BLOCK: trades_count=46 < hard_min_trades=80 | 3 |
| MIN_TRADES_HARD_BLOCK: trades_count=10 < hard_min_trades=80 | 3 |
| MIN_TRADES_HARD_BLOCK: trades_count=8 < hard_min_trades=80 | 3 |
| MIN_TRADES_HARD_BLOCK: trades_count=15 < hard_min_trades=80 | 3 |

## 3. Top Candidates Ranked
### By raw ER (top 20)
| Rank | Trial | Raw ER | Obj ER | Raw PF | Obj PF | DD | Trades | Sharpe | Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 00159 | 8.543 | 2.000 | 4.930 | 4.004 | 5.99% | 121 | 9.325 | 8.543 |
| 2 | 00241 | 3.490 | 1.890 | 8.206 | 4.040 | 4.77% | 104 | 11.836 | 3.490 |
| 3 | 00072 | 3.345 | 1.957 | 4.734 | 3.902 | 8.54% | 213 | 14.671 | 3.345 |
| 4 | 00261 | 3.299 | 1.709 | 4.987 | 4.033 | 6.07% | 132 | 12.157 | 3.299 |
| 5 | 00253 | 2.813 | 1.876 | 4.171 | 3.609 | 10.35% | 343 | 11.521 | 2.813 |
| 6 | 00303 | 2.802 | 2.000 | 3.229 | 3.119 | 12.31% | 108 | 7.208 | 2.802 |
| 7 | 00242 | 2.664 | 1.064 | 5.431 | 4.040 | 7.42% | 106 | 10.560 | 2.664 |
| 8 | 00148 | 2.307 | 1.212 | 4.368 | 3.711 | 11.17% | 243 | 9.345 | 2.307 |
| 9 | 00063 | 2.180 | 0.580 | 5.038 | 4.040 | 9.67% | 127 | 11.488 | 2.180 |
| 10 | 00095 | 2.129 | 0.799 | 4.662 | 3.864 | 6.51% | 271 | 11.933 | 2.129 |
| 11 | 00214 | 1.924 | 1.410 | 3.642 | 3.334 | 10.95% | 181 | 5.339 | 1.924 |
| 12 | 00348 | 1.585 | 0.324 | 4.576 | 3.820 | 7.94% | 251 | 12.062 | 1.585 |
| 13 | 00184 | 1.503 | 1.503 | 2.862 | 2.862 | 9.04% | 116 | 7.603 | 1.503 |
| 14 | 00332 | 1.429 | 1.055 | 3.468 | 3.243 | 7.13% | 242 | 6.951 | 1.429 |
| 15 | 00015 | 1.250 | 1.250 | 1.940 | 1.940 | 15.02% | 342 | 4.651 | 1.250 |
| 16 | 00146 | 1.219 | 1.219 | 2.380 | 2.380 | 5.36% | 139 | 6.828 | 1.219 |
| 17 | 00091 | 1.207 | 1.207 | 1.499 | 1.499 | 37.67% | 159 | 3.254 | 1.207 |
| 18 | 00211 | 1.105 | 1.105 | 2.177 | 2.177 | 13.99% | 467 | 5.697 | 1.105 |
| 19 | 00333 | 0.865 | 0.865 | 2.077 | 2.077 | 22.95% | 421 | 5.093 | 0.865 |
| 20 | 00141 | 0.864 | 0.864 | 2.306 | 2.306 | 4.57% | 140 | 7.056 | 0.864 |

### By balanced metrics: ER * PF / DD (top 20)
| Rank | Trial | Raw ER | Obj ER | Raw PF | Obj PF | DD | Trades | Sharpe | Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 00159 | 8.543 | 2.000 | 4.930 | 4.004 | 5.99% | 121 | 9.325 | 702.646 |
| 2 | 00241 | 3.490 | 1.890 | 8.206 | 4.040 | 4.77% | 104 | 11.836 | 601.049 |
| 3 | 00261 | 3.299 | 1.709 | 4.987 | 4.033 | 6.07% | 132 | 12.157 | 271.189 |
| 4 | 00242 | 2.664 | 1.064 | 5.431 | 4.040 | 7.42% | 106 | 10.560 | 194.906 |
| 5 | 00072 | 3.345 | 1.957 | 4.734 | 3.902 | 8.54% | 213 | 14.671 | 185.320 |
| 6 | 00095 | 2.129 | 0.799 | 4.662 | 3.864 | 6.51% | 271 | 11.933 | 152.470 |
| 7 | 00063 | 2.180 | 0.580 | 5.038 | 4.040 | 9.67% | 127 | 11.488 | 113.537 |
| 8 | 00253 | 2.813 | 1.876 | 4.171 | 3.609 | 10.35% | 343 | 11.521 | 113.342 |
| 9 | 00348 | 1.585 | 0.324 | 4.576 | 3.820 | 7.94% | 251 | 12.062 | 91.303 |
| 10 | 00148 | 2.307 | 1.212 | 4.368 | 3.711 | 11.17% | 243 | 9.345 | 90.214 |
| 11 | 00303 | 2.802 | 2.000 | 3.229 | 3.119 | 12.31% | 108 | 7.208 | 73.528 |
| 12 | 00332 | 1.429 | 1.055 | 3.468 | 3.243 | 7.13% | 242 | 6.951 | 69.456 |
| 13 | 00214 | 1.924 | 1.410 | 3.642 | 3.334 | 10.95% | 181 | 5.339 | 63.999 |
| 14 | 00146 | 1.219 | 1.219 | 2.380 | 2.380 | 5.36% | 139 | 6.828 | 54.099 |
| 15 | 00184 | 1.503 | 1.503 | 2.862 | 2.862 | 9.04% | 116 | 7.603 | 47.593 |
| 16 | 00141 | 0.864 | 0.864 | 2.306 | 2.306 | 4.57% | 140 | 7.056 | 43.564 |
| 17 | 00000 | 0.761 | 0.761 | 2.584 | 2.584 | 9.85% | 610 | 6.848 | 19.955 |
| 18 | 00211 | 1.105 | 1.105 | 2.177 | 2.177 | 13.99% | 467 | 5.697 | 17.202 |
| 19 | 00021 | 0.392 | 0.392 | 1.688 | 1.688 | 4.06% | 188 | 5.007 | 16.325 |
| 20 | 00015 | 1.250 | 1.250 | 1.940 | 1.940 | 15.02% | 342 | 4.651 | 16.143 |

### By trade count / statistical weight (top 20)
| Rank | Trial | Raw ER | Obj ER | Raw PF | Obj PF | DD | Trades | Sharpe | Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 00050 | 0.131 | 0.131 | 1.123 | 1.123 | 39.37% | 1003 | 1.022 | 1003.000 |
| 2 | 00323 | 0.281 | 0.281 | 1.465 | 1.465 | 25.30% | 989 | 2.852 | 989.000 |
| 3 | 00151 | 0.266 | 0.266 | 1.092 | 1.092 | 71.33% | 664 | 1.137 | 664.000 |
| 4 | 00000 | 0.761 | 0.761 | 2.584 | 2.584 | 9.85% | 610 | 6.848 | 610.000 |
| 5 | 00025 | 0.641 | 0.641 | 1.662 | 1.662 | 19.24% | 510 | 5.016 | 510.000 |
| 6 | 00209 | 0.724 | 0.724 | 2.152 | 2.152 | 10.09% | 487 | 5.753 | 487.000 |
| 7 | 00022 | 0.652 | 0.652 | 1.973 | 1.973 | 12.96% | 468 | 5.744 | 468.000 |
| 8 | 00211 | 1.105 | 1.105 | 2.177 | 2.177 | 13.99% | 467 | 5.697 | 467.000 |
| 9 | 00331 | 0.398 | 0.398 | 1.203 | 1.203 | 37.61% | 455 | 1.620 | 455.000 |
| 10 | 00333 | 0.865 | 0.865 | 2.077 | 2.077 | 22.95% | 421 | 5.093 | 421.000 |
| 11 | 00228 | 0.076 | 0.076 | 1.064 | 1.064 | 29.84% | 361 | 0.676 | 361.000 |
| 12 | 00253 | 2.813 | 1.876 | 4.171 | 3.609 | 10.35% | 343 | 11.521 | 343.000 |
| 13 | 00015 | 1.250 | 1.250 | 1.940 | 1.940 | 15.02% | 342 | 4.651 | 342.000 |
| 14 | 00095 | 2.129 | 0.799 | 4.662 | 3.864 | 6.51% | 271 | 11.933 | 271.000 |
| 15 | 00348 | 1.585 | 0.324 | 4.576 | 3.820 | 7.94% | 251 | 12.062 | 251.000 |
| 16 | 00148 | 2.307 | 1.212 | 4.368 | 3.711 | 11.17% | 243 | 9.345 | 243.000 |
| 17 | 00332 | 1.429 | 1.055 | 3.468 | 3.243 | 7.13% | 242 | 6.951 | 242.000 |
| 18 | 00072 | 3.345 | 1.957 | 4.734 | 3.902 | 8.54% | 213 | 14.671 | 213.000 |
| 19 | 00014 | 0.143 | 0.143 | 1.165 | 1.165 | 11.37% | 205 | 1.294 | 205.000 |
| 20 | 00168 | 0.486 | 0.486 | 1.688 | 1.688 | 8.23% | 198 | 4.275 | 198.000 |

### By OOS potential heuristic (top 20)
| Rank | Trial | Raw ER | Obj ER | Raw PF | Obj PF | DD | Trades | Sharpe | Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 00159 | 8.543 | 2.000 | 4.930 | 4.004 | 5.99% | 121 | 9.325 | 6384.932 |
| 2 | 00241 | 3.490 | 1.890 | 8.206 | 4.040 | 4.77% | 104 | 11.836 | 4034.877 |
| 3 | 00261 | 3.299 | 1.709 | 4.987 | 4.033 | 6.07% | 132 | 12.157 | 3232.785 |
| 4 | 00072 | 3.345 | 1.957 | 4.734 | 3.902 | 8.54% | 213 | 14.671 | 3081.795 |
| 5 | 00095 | 2.129 | 0.799 | 4.662 | 3.864 | 6.51% | 271 | 11.933 | 2187.453 |
| 6 | 00253 | 2.813 | 1.876 | 4.171 | 3.609 | 10.35% | 343 | 11.521 | 1828.259 |
| 7 | 00242 | 2.664 | 1.064 | 5.431 | 4.040 | 7.42% | 106 | 10.560 | 1770.947 |
| 8 | 00348 | 1.585 | 0.324 | 4.576 | 3.820 | 7.94% | 251 | 12.062 | 1330.723 |
| 9 | 00063 | 2.180 | 0.580 | 5.038 | 4.040 | 9.67% | 127 | 11.488 | 1256.148 |
| 10 | 00148 | 2.307 | 1.212 | 4.368 | 3.711 | 11.17% | 243 | 9.345 | 1061.073 |
| 11 | 00303 | 2.802 | 2.000 | 3.229 | 3.119 | 12.31% | 108 | 7.208 | 770.008 |
| 12 | 00146 | 1.219 | 1.219 | 2.380 | 2.380 | 5.36% | 139 | 6.828 | 766.931 |
| 13 | 00332 | 1.429 | 1.055 | 3.468 | 3.243 | 7.13% | 242 | 6.951 | 764.825 |
| 14 | 00141 | 0.864 | 0.864 | 2.306 | 2.306 | 4.57% | 140 | 7.056 | 659.695 |
| 15 | 00184 | 1.503 | 1.503 | 2.862 | 2.862 | 9.04% | 116 | 7.603 | 602.197 |
| 16 | 00214 | 1.924 | 1.410 | 3.642 | 3.334 | 10.95% | 181 | 5.339 | 488.285 |
| 17 | 00000 | 0.761 | 0.761 | 2.584 | 2.584 | 9.85% | 610 | 6.848 | 339.190 |
| 18 | 00211 | 1.105 | 1.105 | 2.177 | 2.177 | 13.99% | 467 | 5.697 | 276.761 |
| 19 | 00209 | 0.724 | 0.724 | 2.152 | 2.152 | 10.09% | 487 | 5.753 | 255.814 |
| 20 | 00021 | 0.392 | 0.392 | 1.688 | 1.688 | 4.06% | 188 | 5.007 | 253.761 |

Top 10 candidate detail:
### trial-00159
| Metric | Raw | Objective |
| --- | --- | --- |
| Expectancy R | 8.543 | 2.000 |
| Profit factor | 4.930 | 4.004 |
| Max drawdown | 5.99% | 5.99% |
| Trades | 121 | 121 |
| Sharpe | 9.325 | 9.325 |
| Win rate | 35.54% | 35.54% |
| pnl_abs | 310518.68 | 310518.68 |
Key params:
| Param | Value |
| --- | --- |
| allow_long_in_uptrend | True |
| allow_uptrend_continuation | False |
| weight_sweep_detected | 1.050 |
| weight_reclaim_confirmed | 3.800 |
| weight_tfi_impulse | 4.900 |
| weight_ema_trend_alignment | 0.000 |
| min_sweep_depth_pct | 0.008 |
| invalidation_offset_atr | 0.060 |
| entry_offset_atr | 0.030 |
| max_open_positions | 1 |
| max_trades_per_day | 3 |
| max_hold_hours | 42 |
| confluence_min | 3.200 |
Predicted safety flags: `oos_outperformance_review_required`
WF artifact: present in `walkforward_reports`.
Recommendation artifact: present in `recommendations`.
Audit priority: primary

### trial-00241
| Metric | Raw | Objective |
| --- | --- | --- |
| Expectancy R | 3.490 | 1.890 |
| Profit factor | 8.206 | 4.040 |
| Max drawdown | 4.77% | 4.77% |
| Trades | 104 | 104 |
| Sharpe | 11.836 | 11.836 |
| Win rate | 72.12% | 72.12% |
| pnl_abs | 248916.36 | 248916.36 |
Key params:
| Param | Value |
| --- | --- |
| allow_long_in_uptrend | True |
| allow_uptrend_continuation | False |
| weight_sweep_detected | 1.450 |
| weight_reclaim_confirmed | 4.100 |
| weight_tfi_impulse | 1.300 |
| weight_ema_trend_alignment | 4.300 |
| min_sweep_depth_pct | 0.009 |
| invalidation_offset_atr | 0.060 |
| entry_offset_atr | 0.090 |
| max_open_positions | 1 |
| max_trades_per_day | 2 |
| max_hold_hours | 21 |
| confluence_min | 4.100 |
Predicted safety flags: `oos_outperformance_review_required`, `low_oos_trade_count_review_required`
WF artifact: present in `walkforward_reports`.
Recommendation artifact: present in `recommendations`.
Audit priority: primary

### trial-00261
| Metric | Raw | Objective |
| --- | --- | --- |
| Expectancy R | 3.299 | 1.709 |
| Profit factor | 4.987 | 4.033 |
| Max drawdown | 6.07% | 6.07% |
| Trades | 132 | 132 |
| Sharpe | 12.157 | 12.157 |
| Win rate | 61.36% | 61.36% |
| pnl_abs | 268370.13 | 268370.13 |
Key params:
| Param | Value |
| --- | --- |
| allow_long_in_uptrend | True |
| allow_uptrend_continuation | False |
| weight_sweep_detected | 0.850 |
| weight_reclaim_confirmed | 4.600 |
| weight_tfi_impulse | 1.800 |
| weight_ema_trend_alignment | 3.850 |
| min_sweep_depth_pct | 0.007 |
| invalidation_offset_atr | 0.120 |
| entry_offset_atr | 0.120 |
| max_open_positions | 1 |
| max_trades_per_day | 3 |
| max_hold_hours | 30 |
| confluence_min | 4.300 |
Predicted safety flags: `oos_outperformance_review_required`
Audit priority: primary

### trial-00242
| Metric | Raw | Objective |
| --- | --- | --- |
| Expectancy R | 2.664 | 1.064 |
| Profit factor | 5.431 | 4.040 |
| Max drawdown | 7.42% | 7.42% |
| Trades | 106 | 106 |
| Sharpe | 10.560 | 10.560 |
| Win rate | 66.98% | 66.98% |
| pnl_abs | 117342.08 | 117342.08 |
Key params:
| Param | Value |
| --- | --- |
| allow_long_in_uptrend | True |
| allow_uptrend_continuation | False |
| weight_sweep_detected | 0.100 |
| weight_reclaim_confirmed | 4.100 |
| weight_tfi_impulse | 5.000 |
| weight_ema_trend_alignment | 4.900 |
| min_sweep_depth_pct | 0.008 |
| invalidation_offset_atr | 0.010 |
| entry_offset_atr | 0.090 |
| max_open_positions | 1 |
| max_trades_per_day | 3 |
| max_hold_hours | 34 |
| confluence_min | 3.800 |
Predicted safety flags: `low_oos_trade_count_review_required`
Audit priority: secondary/diagnosis

### trial-00072
| Metric | Raw | Objective |
| --- | --- | --- |
| Expectancy R | 3.345 | 1.957 |
| Profit factor | 4.734 | 3.902 |
| Max drawdown | 8.54% | 8.54% |
| Trades | 213 | 213 |
| Sharpe | 14.671 | 14.671 |
| Win rate | 62.91% | 62.91% |
| pnl_abs | 9941398.56 | 9941398.56 |
Key params:
| Param | Value |
| --- | --- |
| allow_long_in_uptrend | True |
| allow_uptrend_continuation | False |
| weight_sweep_detected | 4.250 |
| weight_reclaim_confirmed | 4.050 |
| weight_tfi_impulse | 4.400 |
| weight_ema_trend_alignment | 3.100 |
| min_sweep_depth_pct | 0.006 |
| invalidation_offset_atr | 0.030 |
| entry_offset_atr | 0.070 |
| max_open_positions | 1 |
| max_trades_per_day | 6 |
| max_hold_hours | 25 |
| confluence_min | 4.000 |
Predicted safety flags: `pnl_sanity_review_required`, `oos_outperformance_review_required`
Audit priority: secondary/diagnosis

### trial-00095
| Metric | Raw | Objective |
| --- | --- | --- |
| Expectancy R | 2.129 | 0.799 |
| Profit factor | 4.662 | 3.864 |
| Max drawdown | 6.51% | 6.51% |
| Trades | 271 | 271 |
| Sharpe | 11.933 | 11.933 |
| Win rate | 56.46% | 56.46% |
| pnl_abs | 92324.81 | 92324.81 |
Key params:
| Param | Value |
| --- | --- |
| allow_long_in_uptrend | True |
| allow_uptrend_continuation | False |
| weight_sweep_detected | 2.200 |
| weight_reclaim_confirmed | 2.150 |
| weight_tfi_impulse | 2.500 |
| weight_ema_trend_alignment | 3.350 |
| min_sweep_depth_pct | 0.006 |
| invalidation_offset_atr | 0.140 |
| entry_offset_atr | 0.070 |
| max_open_positions | 1 |
| max_trades_per_day | 5 |
| max_hold_hours | 34 |
| confluence_min | 3.900 |
Predicted safety flags: `clean_by_pre_audit_heuristic`
Audit priority: secondary/diagnosis

### trial-00063
| Metric | Raw | Objective |
| --- | --- | --- |
| Expectancy R | 2.180 | 0.580 |
| Profit factor | 5.038 | 4.040 |
| Max drawdown | 9.67% | 9.67% |
| Trades | 127 | 127 |
| Sharpe | 11.488 | 11.488 |
| Win rate | 65.35% | 65.35% |
| pnl_abs | 102111.75 | 102111.75 |
Key params:
| Param | Value |
| --- | --- |
| allow_long_in_uptrend | True |
| allow_uptrend_continuation | False |
| weight_sweep_detected | 0.150 |
| weight_reclaim_confirmed | 3.300 |
| weight_tfi_impulse | 4.900 |
| weight_ema_trend_alignment | 4.900 |
| min_sweep_depth_pct | 0.006 |
| invalidation_offset_atr | 0.100 |
| entry_offset_atr | 0.170 |
| max_open_positions | 3 |
| max_trades_per_day | 4 |
| max_hold_hours | 27 |
| confluence_min | 4.000 |
Predicted safety flags: `clean_by_pre_audit_heuristic`
Audit priority: secondary/diagnosis

### trial-00253
| Metric | Raw | Objective |
| --- | --- | --- |
| Expectancy R | 2.813 | 1.876 |
| Profit factor | 4.171 | 3.609 |
| Max drawdown | 10.35% | 10.35% |
| Trades | 343 | 343 |
| Sharpe | 11.521 | 11.521 |
| Win rate | 54.52% | 54.52% |
| pnl_abs | 216608466.72 | 216608466.72 |
Key params:
| Param | Value |
| --- | --- |
| allow_long_in_uptrend | True |
| allow_uptrend_continuation | False |
| weight_sweep_detected | 3.000 |
| weight_reclaim_confirmed | 3.300 |
| weight_tfi_impulse | 5.000 |
| weight_ema_trend_alignment | 4.750 |
| min_sweep_depth_pct | 0.005 |
| invalidation_offset_atr | 0.120 |
| entry_offset_atr | 0.140 |
| max_open_positions | 1 |
| max_trades_per_day | 3 |
| max_hold_hours | 34 |
| confluence_min | 3.400 |
Predicted safety flags: `pnl_sanity_review_required`
Audit priority: secondary/diagnosis

### trial-00348
| Metric | Raw | Objective |
| --- | --- | --- |
| Expectancy R | 1.585 | 0.324 |
| Profit factor | 4.576 | 3.820 |
| Max drawdown | 7.94% | 7.94% |
| Trades | 251 | 251 |
| Sharpe | 12.062 | 12.062 |
| Win rate | 65.34% | 65.34% |
| pnl_abs | 382907.05 | 382907.05 |
Key params:
| Param | Value |
| --- | --- |
| allow_long_in_uptrend | True |
| allow_uptrend_continuation | False |
| weight_sweep_detected | 0.150 |
| weight_reclaim_confirmed | 3.750 |
| weight_tfi_impulse | 4.900 |
| weight_ema_trend_alignment | 5.000 |
| min_sweep_depth_pct | 0.004 |
| invalidation_offset_atr | 0.180 |
| entry_offset_atr | 0.170 |
| max_open_positions | 1 |
| max_trades_per_day | 3 |
| max_hold_hours | 8 |
| confluence_min | 3.100 |
Predicted safety flags: `clean_by_pre_audit_heuristic`
Audit priority: secondary/diagnosis

### trial-00148
| Metric | Raw | Objective |
| --- | --- | --- |
| Expectancy R | 2.307 | 1.212 |
| Profit factor | 4.368 | 3.711 |
| Max drawdown | 11.17% | 11.17% |
| Trades | 243 | 243 |
| Sharpe | 9.345 | 9.345 |
| Win rate | 58.02% | 58.02% |
| pnl_abs | 1569675.33 | 1569675.33 |
Key params:
| Param | Value |
| --- | --- |
| allow_long_in_uptrend | True |
| allow_uptrend_continuation | False |
| weight_sweep_detected | 0.150 |
| weight_reclaim_confirmed | 0.650 |
| weight_tfi_impulse | 2.750 |
| weight_ema_trend_alignment | 5.000 |
| min_sweep_depth_pct | 0.007 |
| invalidation_offset_atr | 0.070 |
| entry_offset_atr | 0.240 |
| max_open_positions | 2 |
| max_trades_per_day | 3 |
| max_hold_hours | 41 |
| confluence_min | 2.900 |
Predicted safety flags: `pnl_sanity_review_required`
Audit priority: secondary/diagnosis

Saved recommendation and walk-forward artifacts:
| Trial | WF passed | Windows | Fragile | IS degradation | Validation trades | Safety flags |
| --- | --- | --- | --- | --- | --- | --- |
| 00021 | True | 2/2 | False | -5.00% | 63, 22 | low_oos_trade_count_review_required |
| 00141 | True | 2/2 | False | -78.99% | 60, 18 | low_oos_trade_count_review_required, oos_outperformance_review_required |
| 00159 | True | 2/2 | False | 5.71% | 57, 13 | low_oos_trade_count_review_required, pf_hard_review_required, pnl_sanity_review_required |
| 00241 | True | 2/2 | False | 19.01% | 46, 15 | low_oos_trade_count_review_required, pf_hard_review_required, pnl_sanity_review_required |

Artifact-level observation: all 4 saved WF candidates passed 2/2 windows, but every one has at least one safety flag. This report does not issue a promotion verdict; it marks these as first-pass audit targets because they are the candidates actually persisted by the post-hoc WF/recommendation pipeline.

## 4. Parameter Pattern Analysis
Pattern set: 20 unique top candidates from balanced/raw/OOS/trade rankings.

Categorical parameters in top set:
| Parameter | Top-set counts |
| --- | --- |
| allow_long_in_uptrend | True: 20 |
| allow_uptrend_continuation | False: 20 |

Continuous parameter distribution in top set:
| Parameter | n | min | Q1 | median | Q3 | max |
| --- | --- | --- | --- | --- | --- | --- |
| weight_sweep_detected | 20 | 0.00000 | 0.13750 | 0.52500 | 1.61250 | 4.25000 |
| weight_reclaim_confirmed | 20 | 0.65000 | 2.85000 | 3.52500 | 4.06250 | 4.60000 |
| weight_tfi_impulse | 20 | 0.60000 | 1.66250 | 3.57500 | 4.90000 | 5.00000 |
| weight_ema_trend_alignment | 20 | 0.00000 | 3.50000 | 4.65000 | 4.92500 | 5.00000 |
| weight_cvd_divergence | 20 | 1.20000 | 2.41250 | 3.00000 | 3.67500 | 5.00000 |
| min_sweep_depth_pct | 20 | 0.00211 | 0.00470 | 0.00623 | 0.00793 | 0.00853 |
| sweep_buf_atr | 20 | 0.17000 | 0.46000 | 0.53500 | 0.59250 | 1.00000 |
| wick_min_atr | 20 | 0.05000 | 0.15000 | 0.27500 | 0.42500 | 0.80000 |
| invalidation_offset_atr | 20 | 0.01000 | 0.02750 | 0.07000 | 0.12000 | 0.92000 |
| entry_offset_atr | 20 | 0.01000 | 0.06750 | 0.09000 | 0.17000 | 0.60000 |
| high_vol_stop_distance_pct | 20 | 0.01700 | 0.02325 | 0.02700 | 0.05150 | 0.10000 |
| max_open_positions | 20 | 1.00000 | 1.00000 | 1.00000 | 1.00000 | 3.00000 |
| max_trades_per_day | 20 | 1.00000 | 3.00000 | 3.00000 | 3.25000 | 6.00000 |
| max_hold_hours | 20 | 3.00000 | 26.50000 | 34.00000 | 35.00000 | 44.00000 |
| confluence_min | 20 | 2.90000 | 3.35000 | 3.95000 | 4.12500 | 4.50000 |
| direction_tfi_threshold | 20 | 0.08000 | 0.09000 | 0.09000 | 0.12000 | 0.25000 |
| uptrend_continuation_participation_min | 20 | 0.15000 | 0.20000 | 0.20000 | 0.31250 | 0.65000 |
| uptrend_continuation_confluence_multiplier | 20 | 1.10000 | 1.20000 | 1.20000 | 1.30000 | 1.80000 |
| uptrend_continuation_reclaim_strength_min | 20 | 0.10000 | 0.50000 | 0.60000 | 0.70000 | 1.40000 |

## 5. Architectural Validation
| Hypothesis | Prediction | V3 evidence | Assessment |
| --- | --- | --- | --- |
| Sweep as gate, not premium | weight_sweep_detected median < 1.0 | median=0.525 | PASS |
| Reclaim carries premium | weight_reclaim_confirmed median > 3.0 | median=3.525 | PASS |
| TFI carries premium | weight_tfi_impulse median > 3.0 | median=3.575 | PASS |
| Uptrend continuation dead in main search | 0 top-20 users | 0/20 top-set trials use it | PASS |

`allow_uptrend_continuation` appeared in 88/350 total sampled trials and was associated with 111 uptrend-related rejects. In this combined search space it behaves like an incompatible hypothesis branch, not like a useful local tuning parameter.

## 6. Search Space Efficiency
| Metric | V3 value | V2 baseline / note |
| --- | --- | --- |
| Acceptance rate | 14.00% | V2 acceptance baseline 24.30% |
| Effective credible-search rate | 11.43% | Accepted with positive ER/PF and trades > 0 |
| Low-trade rejects | 151 | Dead-zone cost |
| Constraint rejects | 111 | Mostly uptrend-continuation search cost |
| Estimated wasted budget | 262/350 (74.86%) | Low-trade + constraints + artifacts |
| Relative acceptance vs V2 | 57.61% | Lower rate; quality must be judged by WF/promotion audit |

Interpretation: V3 tightened the space and produced better-looking candidate clusters, but the budget is still leaking into low-trade regions and the uptrend-continuation branch.

## 7. Safety Flag Predictions
These are pre-audit heuristics for prioritization. They do not replace Claude Code safety flag evaluation.
| Trial | Raw ER | Raw PF | DD | Trades | pnl_abs | Predicted flags |
| --- | --- | --- | --- | --- | --- | --- |
| 00159 | 8.543 | 4.930 | 5.99% | 121 | 310518.68 | oos_outperformance_review_required |
| 00241 | 3.490 | 8.206 | 4.77% | 104 | 248916.36 | oos_outperformance_review_required, low_oos_trade_count_review_required |
| 00261 | 3.299 | 4.987 | 6.07% | 132 | 268370.13 | oos_outperformance_review_required |
| 00242 | 2.664 | 5.431 | 7.42% | 106 | 117342.08 | low_oos_trade_count_review_required |
| 00072 | 3.345 | 4.734 | 8.54% | 213 | 9941398.56 | pnl_sanity_review_required, oos_outperformance_review_required |
| 00095 | 2.129 | 4.662 | 6.51% | 271 | 92324.81 | clean_by_pre_audit_heuristic |
| 00063 | 2.180 | 5.038 | 9.67% | 127 | 102111.75 | clean_by_pre_audit_heuristic |
| 00253 | 2.813 | 4.171 | 10.35% | 343 | 216608466.72 | pnl_sanity_review_required |
| 00348 | 1.585 | 4.576 | 7.94% | 251 | 382907.05 | clean_by_pre_audit_heuristic |
| 00148 | 2.307 | 4.368 | 11.17% | 243 | 1569675.33 | pnl_sanity_review_required |

Clean pre-audit candidates: trial-00095, trial-00063, trial-00348

## 8. V4 Recommendations
Freeze from ACTIVE if V3 audit does not produce a clean paper-trading candidate, or use as non-blocking architecture cleanup after paper deployment:
| Parameter | Recommendation | Rationale |
| --- | --- | --- |
| allow_uptrend_continuation | freeze false | Dead branch in combined search; zero top-set usage expected/observed. |
| uptrend_continuation_participation_min | remove/freeze | Only meaningful when branch is active. |
| uptrend_continuation_confluence_multiplier | remove/freeze | Only meaningful when branch is active. |
| uptrend_continuation_reclaim_strength_min | remove/freeze | Only meaningful when branch is active. |
| weight_sweep_detected | freeze 0.5 | Hard-gated sweep makes this an intercept-like term, not an information weight. |

V4 strategy: 350-400 trials, seed 45, same V3 infrastructure, warm-start from V3 top 3-5 only if they pass WF/safety review. Search space size would fall from 35 to about 30 active params (-14%).

## 9. V1 / V2 / V3 Comparison
| Dimension | V1 | V2 | V3 |
| --- | --- | --- | --- |
| Promotion candidates | trial-00000 historically clean under V1 | 0 promotion-ready after audit | pending Claude Code audit of 4 WF/recommendation artifacts |
| Acceptance rate | n/a in this report | 24.30% baseline from prior audit | 14.00% |
| Infrastructure | Campaign V1 baseline | No raw/objective split; broader/noisier space | raw/objective split, WF-winners-only warm-start, TPE policy hardening |
| Key lesson | Found initial candidate | Operational workflow pass, candidate quality fail | Better candidate clusters and architecture diagnosis; still needs WF/safety verdict |

## 10. Audit Handoff Preparation
| Bucket | Candidates | Purpose |
| --- | --- | --- |
| Primary audit | trial-00021, trial-00141, trial-00159, trial-00241 | Persisted recommendation + WF artifacts; verify safety flags and promotion verdict. |
| Secondary audit | trial-00095, trial-00063, trial-00348, trial-00148 | Clean or historically important metric-ranked candidates not persisted as final recommendations. |
| Diagnosis audit | trial-00072, trial-00148, trial-00253 | pnl_abs / extreme ER / artifact review. |

Recommended workflow:
1. Verify the 4 saved recommendations and their WF reports first.
2. Cross-check top-ranked candidates that did not receive recommendations to understand filter exclusions.
3. Apply promotion gate strictly: WF 2/2, per-window trade counts, degradation, fragile flag, and safety flags.
4. If no candidate is promotion-ready, decide between V4 narrowed search and deeper signal archaeology.

## SQL Queries Used
```sql
select count(*) from trials where trial_id like 'optuna-default-v3-trial-%';
select trial_id, params_json, raw_metrics_json, objective_metrics_json, rejected_reason from trials where trial_id like 'optuna-default-v3-trial-%' order by trial_id;
select count(*) from recommendations where candidate_id like 'optuna-default-v3-trial-%';
select count(*) from walkforward_reports where candidate_id like 'optuna-default-v3-trial-%';
select rejected_reason, count(*) from trials where trial_id like 'optuna-default-v3-trial-%' group by rejected_reason order by count(*) desc;
```

## Anomaly Detection
| Check | Result |
| --- | --- |
| Duplicate trial IDs | none |
| Missing raw metrics | none |
| Missing objective metrics | none |
| Extreme ER candidates (>3.0) | trial-00072, trial-00159, trial-00241, trial-00261 |
| Suspicious pnl_abs candidates | trial-00072, trial-00148, trial-00253 |

## Acceptance Criteria
- [x] 350/350 trials present in research store
- [x] Optuna states are complete-only or no failures
- [x] Warm-start mode is wf-winners-only
- [x] Multivariate TPE requested was recorded
- [x] Effective multivariate TPE disabled for dynamic bounds
- [x] Raw metrics present for every trial
- [x] Objective metrics present for every trial
- [x] Recommendations artifact present
- [x] Walk-forward artifacts present
- [x] Candidate rankings generated from actual metrics
- [x] No promotion verdict issued by Codex

Final status: V3_REPORT_READY - awaiting Claude Code audit.
