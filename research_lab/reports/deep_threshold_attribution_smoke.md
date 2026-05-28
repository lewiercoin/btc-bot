# Deep Historical Threshold Attribution V1

BTC-only runtime-parity backtest with realistic fees, slippage, and funding.

Important limitation: trade-level reclaim speed/depth is not yet persisted by the parity output, so this report attributes available entry features only.

## Threshold Summary

| threshold | trades | net_pnl_r | net_er | win_rate | profit_factor | median_r |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0035 | 8 | 20.3348 | 2.5418 | 0.875 | 13.08 | 2.8504 |
| 0.004 | 6 | 19.0171 | 3.1695 | 1.0 | inf | 2.8504 |
| 0.0045 | 5 | 15.5565 | 3.1113 | 1.0 | inf | 2.708 |
| 0.005 | 4 | 13.4567 | 3.3642 | 1.0 | inf | 2.8504 |
| 0.006 | 3 | 11.2911 | 3.7637 | 1.0 | inf | 2.9929 |
| 0.00649 | 3 | 11.2911 | 3.7637 | 1.0 | inf | 2.9929 |

## Overall Depth Buckets

| depth_bucket | trades | net_pnl_r | net_er | win_rate | profit_factor | median_r |
| --- | --- | --- | --- | --- | --- | --- |
| 0.70-1.00% | 18 | 67.7466 | 3.7637 | 1.0 | inf | 2.9929 |
| 0.50-0.60% | 4 | 8.6623 | 2.1656 | 1.0 | inf | 2.1656 |
| 0.45-0.50% | 3 | 6.2994 | 2.0998 | 1.0 | inf | 2.0998 |
| 0.40-0.45% | 2 | 6.9212 | 3.4606 | 1.0 | inf | 3.4606 |
| 0.35-0.40% | 2 | 1.3177 | 0.6588 | 0.5 | 1.78 | 0.6588 |

## Shallow Depth Buckets

| depth_bucket | trades | net_pnl_r | net_er | win_rate | profit_factor | median_r |
| --- | --- | --- | --- | --- | --- | --- |
| 0.45-0.50% | 3 | 6.2994 | 2.0998 | 1.0 | inf | 2.0998 |
| 0.40-0.45% | 2 | 6.9212 | 3.4606 | 1.0 | inf | 3.4606 |
| 0.35-0.40% | 2 | 1.3177 | 0.6588 | 0.5 | 1.78 | 0.6588 |

## Regime x Depth

| regime | depth_bucket | trades | net_pnl_r | net_er | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- | --- |
| uptrend | 0.70-1.00% | 18 | 67.7466 | 3.7637 | 1.0 | inf |
| uptrend | 0.50-0.60% | 4 | 8.6623 | 2.1656 | 1.0 | inf |
| uptrend | 0.45-0.50% | 3 | 6.2994 | 2.0998 | 1.0 | inf |

## Session x Depth

| session | depth_bucket | trades | net_pnl_r | net_er | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- | --- |
| Late | 0.70-1.00% | 12 | 34.2052 | 2.8504 | 1.0 | inf |
| US | 0.70-1.00% | 6 | 33.5413 | 5.5902 | 1.0 | inf |
| US | 0.50-0.60% | 4 | 8.6623 | 2.1656 | 1.0 | inf |
| US | 0.45-0.50% | 3 | 6.2994 | 2.0998 | 1.0 | inf |

## ATR Quartile x Depth

| atr_quartile | depth_bucket | trades | net_pnl_r | net_er | win_rate | profit_factor |
| --- | --- | --- | --- | --- | --- | --- |
| Q1_low | 0.70-1.00% | 8 | 23.3733 | 2.9217 | 1.0 | inf |
| Q3 | 0.70-1.00% | 5 | 27.9511 | 5.5902 | 1.0 | inf |
| Q2 | 0.70-1.00% | 5 | 16.4221 | 3.2844 | 1.0 | inf |
| Q4_high | 0.45-0.50% | 3 | 6.2994 | 2.0998 | 1.0 | inf |

## Shallow Feature Scores

Numeric scores combine simple correlation and quartile ER spread; this is discovery attribution, not a deployable ML model.

| feature | corr_net_pnl_r | corr_win | quartile_er_spread |
| --- | --- | --- | --- |
| mae | -0.9361 | -1.0 | 3.023 |
| mfe | 0.8207 | 0.9446 | 2.8018 |
| tfi_60s | -0.5794 | -0.6546 | 2.8018 |
| funding_pct_60d | 0.5399 | 0.7813 | 2.8018 |
| atr_4h_norm | -0.5296 | -0.238 | 2.8018 |
| sweep_depth_pct | 0.4305 | 0.5809 | 2.8018 |
| oi_zscore_60d | -0.4683 | -0.6748 | 2.5722 |
| confluence_score | -0.0623 | -0.3945 | 2.8018 |

Categorical scores show which buckets separate shallow winners from losers.

| feature | levels | er_spread | best_level | best_er | worst_level | worst_er |
| --- | --- | --- | --- | --- | --- | --- |
| exit_reason | 2 | 4.3874 | TP | 2.7037 | SL | -1.6837 |
| depth_bucket | 3 | 2.8018 | 0.40-0.45% | 3.4606 | 0.35-0.40% | 0.6588 |
| sweep_side | 2 | 1.9372 | LOW | 3.4606 | HIGH | 1.5234 |
| atr_quartile | 2 | 1.9372 | Q2 | 3.4606 | Q4_high | 1.5234 |

