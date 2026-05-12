# Regime Distribution Analysis

Source DB: `storage\btc_bot.db`
Date range: `2022-01-01` to `2026-03-29`
Total cycles: `148596`

## Regime Counts

| Regime | Count | Percentage |
|---|---:|---:|
| normal | `4199` | `0.02825783` |
| uptrend | `63891` | `0.42996447` |
| downtrend | `63598` | `0.42799268` |
| compression | `2938` | `0.01977173` |
| crowded_leverage | `13970` | `0.0940133` |
| post_liquidation | `0` | `0.0` |

## ATR 4H Norm By Regime

| Regime | Count | Mean | P50 | P95 |
|---|---:|---:|---:|---:|
| compression | `2938` | `0.00467765` | `0.00485836` | `0.00545251` |
| crowded_leverage | `13970` | `0.01661275` | `0.01543973` | `0.02957243` |
| downtrend | `63598` | `0.0169078` | `0.01517801` | `0.03146028` |
| normal | `4199` | `0.01344948` | `0.01247089` | `0.02337397` |
| uptrend | `63891` | `0.01453626` | `0.01349997` | `0.02614845` |

## Interpretation

COMPRESSION labels are present but uncommon (1-5%). Regime may remain useful as context, but setup-level compression detection should be compared against RegimeEngine labels.
