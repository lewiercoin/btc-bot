# Optuna V3 Range Tightening Evidence

Date: 2026-05-07
Source: Campaign V2 production store (`optuna_default_v2`, 350 trials)

This note documents the conservative range changes applied before Campaign V3.
Ranges were tightened only where V2 accepted trials sat well below the old upper
bound and rejected trials concentrated in the same high-value tail.

| Parameter | Old high | New high | V2 evidence |
|---|---:|---:|---|
| `compression_atr_norm_max` | 0.0500 | 0.0200 | accepted p90=0.0170, rejected p90=0.0253 |
| `post_liq_tfi_abs_min` | 1.00 | 0.85 | accepted p90=0.77, rejected p90=0.83 |
| `min_sweep_depth_pct` | 0.0200 | 0.0100 | accepted p90=0.00825, rejected p75=0.01081 |
| `entry_offset_atr` | 2.00 | 0.80 | accepted p90=0.55, rejected p90=0.69 |
| `min_stop_distance_pct` | 0.0200 | 0.0100 | accepted p90=0.0059, rejected p90=0.0081 |
| `risk_per_trade_pct` | 0.0500 | 0.0200 | accepted p90=0.0155, rejected p90=0.0180 |
| `trailing_atr_mult` | 5.0 | 4.0 | accepted p90=2.9, rejected p90=3.6 |

The change intentionally avoids tightening ranges merely because Optuna rarely
visited them. The retained upper bounds still cover the V2 accepted high
percentile band while removing tails associated with rejection and low confidence.
