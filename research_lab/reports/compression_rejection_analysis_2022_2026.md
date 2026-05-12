# Compression Rejection Analysis

Source DB: `storage\btc_bot.db`
Date range: `2022-01-01` to `2026-03-29`

## Candidate Rates By Regime

| Regime | Cycles | Candidates | Candidate Rate |
|---|---:|---:|---:|
| compression | `2938` | `7` | `0.00238257` |
| crowded_leverage | `13970` | `0` | `0.0` |
| downtrend | `63598` | `0` | `0.0` |
| normal | `4199` | `0` | `0.0` |
| uptrend | `63891` | `0` | `0.0` |

## Top Rejection Reasons By Regime

### compression

| Reason | Count |
|---|---:|
| breakout_too_small | `2862` |
| no_breakout_detected | `2856` |
| tfi_below_breakout_threshold | `2180` |
| range_width_not_compressed | `1907` |
| confluence_too_low | `1287` |
| oi_unwind_not_participation | `1032` |
| compression_duration_too_short | `678` |
| atr_not_compressed | `559` |
| rr_below_minimum | `33` |

### crowded_leverage

| Reason | Count |
|---|---:|
| regime_blocked:crowded_leverage | `13970` |
| breakout_too_small | `13669` |
| no_breakout_detected | `13652` |
| confluence_too_low | `12158` |
| tfi_below_breakout_threshold | `11579` |
| range_width_not_compressed | `11171` |
| compression_duration_too_short | `11102` |
| atr_not_compressed | `10728` |
| oi_unwind_not_participation | `6398` |
| oi_crowded | `1701` |
| volatility_panic | `794` |
| rr_below_minimum | `159` |

### downtrend

| Reason | Count |
|---|---:|
| regime_blocked:downtrend | `63598` |
| breakout_too_small | `62400` |
| no_breakout_detected | `62303` |
| confluence_too_low | `53194` |
| tfi_below_breakout_threshold | `52503` |
| range_width_not_compressed | `49419` |
| compression_duration_too_short | `47619` |
| atr_not_compressed | `45739` |
| oi_unwind_not_participation | `24341` |
| volatility_panic | `4705` |
| rr_below_minimum | `1127` |
| oi_crowded | `886` |
| atr_history_insufficient | `79` |

### normal

| Reason | Count |
|---|---:|
| breakout_too_small | `4130` |
| no_breakout_detected | `4127` |
| confluence_too_low | `3591` |
| tfi_below_breakout_threshold | `3319` |
| compression_duration_too_short | `3164` |
| range_width_not_compressed | `3089` |
| atr_not_compressed | `2998` |
| oi_unwind_not_participation | `1548` |
| oi_crowded | `94` |
| volatility_panic | `80` |
| rr_below_minimum | `58` |

### uptrend

| Reason | Count |
|---|---:|
| regime_blocked:uptrend | `63891` |
| breakout_too_small | `62447` |
| no_breakout_detected | `62339` |
| confluence_too_low | `53862` |
| tfi_below_breakout_threshold | `52223` |
| range_width_not_compressed | `49051` |
| compression_duration_too_short | `48319` |
| atr_not_compressed | `46379` |
| oi_unwind_not_participation | `25846` |
| volatility_panic | `1852` |
| rr_below_minimum | `969` |
| oi_crowded | `801` |
| funding_crowded_long | `64` |

## Compression Metrics

| Metric | Count | Mean | P50 | P95 |
|---|---:|---:|---:|---:|
| atr_percentile | `2938` | `0.10906739` | `0.039` | `0.43` |
| range_width_atr | `2938` | `11.25637112` | `9.47588634` | `24.12778716` |
| compression_duration_bars | `2938` | `66.10142954` | `89.0` | `102.0` |
| breakout_size_atr | `2938` | `-3.76881907` | `-3.3864141` | `-0.33368697` |

## Interpretation

Compression-labeled cycles are primarily blocked by: breakout_too_small=2862, no_breakout_detected=2856, tfi_below_breakout_threshold=2180
