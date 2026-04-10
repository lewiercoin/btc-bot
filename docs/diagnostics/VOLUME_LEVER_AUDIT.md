# Volume Lever Audit — SIGNAL-ANALYSIS-V1

Generated: 2026-04-10
Milestone: SIGNAL-ANALYSIS-V1
Purpose: Classify all ACTIVE parameters as volume levers or non-levers prior to Run #5.

A **volume lever** is a parameter where moving it in one direction monotonically
increases trade count without requiring improved signal quality. Optimizers exploit
these as free fitness proxies.

---

## Summary

| Category | Count |
|---|---|
| ACTIVE volume levers | 26 |
| ACTIVE non-levers | 19 |
| FROZEN volume levers | 3 |
| FROZEN non-levers | 12 |
| DEFERRED | 0 |
| UNSUPPORTED | 1 |

**Confirmed minimum set (from handoff):** 14 parameters
**Additional identified during implementation:** 12 parameters
**Total ACTIVE volume levers:** 26 of ~45 ACTIVE parameters

---

## Full Parameter Table

| Parameter | volume_lever | volume_direction | Mechanism | Status |
|---|---|---|---|---|
| **Signal Generation Levers** | | | | |
| `sweep_proximity_atr` | YES | up | Wider proximity → more bars classified as near a level | ACTIVE |
| `level_min_age_bars` | YES | down | Lower bar span → more clusters qualify as levels | ACTIVE |
| `min_hits` | YES | down | Fewer required touches → more clusters qualify as levels | ACTIVE |
| `equal_level_lookback` | YES | up | Longer lookback window → more level candidates detected | ACTIVE |
| `equal_level_tol_atr` | YES | up | Wider tolerance → more bars merge into a cluster | ACTIVE |
| `wick_min_atr` | YES | down | Smaller required wick → more reclaim bars qualify | ACTIVE |
| `min_sweep_depth_pct` | YES | down | Shallower required depth → more sweeps qualify (signal engine filter) | ACTIVE |
| `sweep_buf_atr` | YES | down | Lower sweep buffer → easier to satisfy sweep condition | ACTIVE |
| `reclaim_buf_atr` | YES | down | Lower reclaim buffer → easier to satisfy reclaim condition | ACTIVE |
| **Filter Levers (confirmed)** | | | | |
| `confluence_min` | YES | down | Lower threshold → more signals exceed minimum confluence score | ACTIVE |
| `direction_tfi_threshold` | YES | up | Higher threshold reduces directional strictness in filter logic | ACTIVE |
| `weight_cvd_divergence` | YES | up | Higher weight inflates confluence score for CVD-divergence events | ACTIVE |
| `weight_tfi_impulse` | YES | up | Higher weight inflates confluence score for TFI-impulse events | ACTIVE |
| `weight_regime_special` | YES | up | Higher weight inflates confluence score for special-regime events | ACTIVE |
| `weight_ema_trend_alignment` | YES | up | Higher weight inflates confluence score for trend-aligned events | ACTIVE |
| `weight_funding_supportive` | YES | up | Higher weight inflates confluence score for funding-supported events | ACTIVE |
| **Filter Levers (additional)** | | | | |
| `tfi_impulse_threshold` | YES | down | Lower threshold → more TFI-impulse signals pass qualification | ACTIVE |
| `post_liq_tfi_abs_min` | YES | down | Lower threshold → more post-liquidation signals pass regime gate | ACTIVE |
| `allow_long_in_uptrend` | YES | up | True opens LONG trading in uptrend regime (direction expansion) | ACTIVE |
| **Execution Levers (confirmed)** | | | | |
| `max_trades_per_day` | YES | up | Higher daily cap → more trades allowed before governance veto | ACTIVE |
| `max_open_positions` | YES | up | Higher cap → more concurrent positions allowed | ACTIVE |
| `max_consecutive_losses` | YES | up | Longer loss streak allowed before governance pause | ACTIVE |
| `cooldown_minutes_after_loss` | YES | down | Shorter cooldown → trading resumes sooner after a loss | ACTIVE |
| **Risk Gate Levers (additional)** | | | | |
| `min_rr` | YES | down | Lower minimum R:R → more signals clear the risk gate | ACTIVE |
| `daily_dd_limit` | YES | up | Higher daily DD limit → more trades before drawdown stop | ACTIVE |
| `weekly_dd_limit` | YES | up | Higher weekly DD limit → more trades before drawdown stop | ACTIVE |
| **Non-Levers (ACTIVE)** | | | | |
| `atr_period` | NO | — | Affects ATR value quality; no monotonic volume effect | ACTIVE |
| `entry_offset_atr` | NO | — | Affects entry price; no effect on signal count | ACTIVE |
| `invalidation_offset_atr` | NO | — | Affects stop-loss distance; no effect on signal count | ACTIVE |
| `tp1_atr_mult` | NO | — | Affects take-profit distance; no effect on signal count | ACTIVE |
| `tp2_atr_mult` | NO | — | Affects take-profit distance; no effect on signal count | ACTIVE |
| `ema_trend_gap_pct` | NO | — | Regime threshold; indirect and bidirectional volume effect | ACTIVE |
| `compression_atr_norm_max` | NO | — | Regime threshold; indirect and bidirectional volume effect | ACTIVE |
| `funding_window_days` | NO | — | Data window for funding features; no monotonic volume effect | ACTIVE |
| `oi_z_window_days` | NO | — | Data window for OI z-score; no monotonic volume effect | ACTIVE |
| `risk_per_trade_pct` | NO | — | Position sizing only; no effect on signal count | ACTIVE |
| `max_leverage` | NO | — | Leverage cap; no effect on signal count | ACTIVE |
| `high_vol_leverage` | NO | — | High-vol leverage cap; no effect on signal count | ACTIVE |
| `high_vol_stop_distance_pct` | NO | — | Stop sizing in high-vol; no effect on signal count | ACTIVE |
| `partial_exit_pct` | NO | — | Exit management; no effect on signal count | ACTIVE |
| `trailing_atr_mult` | NO | — | Trailing stop management; no effect on signal count | ACTIVE |
| `max_hold_hours` | NO | — | Force-close timing only; does not generate new entries | ACTIVE |
| `duplicate_level_tolerance_pct` | NO | — | Dedup window; nuanced and non-monotonic | ACTIVE |
| `duplicate_level_window_hours` | NO | — | Dedup window; nuanced and non-monotonic | ACTIVE |
| `min_stop_distance_pct` | NO | — | Minimum stop distance filter; removes invalid setups only | ACTIVE |
| **FROZEN Volume Levers** | | | | |
| `weight_sweep_detected` | YES | up | Raises confluence score for all sweep events; FROZEN: always-true intercept | FROZEN |
| `weight_reclaim_confirmed` | YES | up | Raises confluence score for all reclaim events; FROZEN: always-true intercept | FROZEN |
| `weight_force_order_spike` | YES | up | Raises confluence score for force-order events; FROZEN: feature unavailable | FROZEN |
| **FROZEN Non-Levers** | | | | |
| `ema_fast` | NO | — | Architecture EMA-50 parameter | FROZEN |
| `ema_slow` | NO | — | Architecture EMA-200 parameter | FROZEN |
| `crowded_funding_extreme_pct` | NO | — | Regime crowded-leverage threshold | FROZEN |
| `crowded_oi_zscore_min` | NO | — | Regime crowded-leverage OI threshold | FROZEN |
| `regime_direction_whitelist` | NO | — | Composite dict; SHORT disabled | FROZEN |
| `direction_tfi_threshold_inverse` | NO | — | Derived constraint from direction_tfi_threshold | FROZEN |
| `no_trade_windows_utc` | NO | — | Composite tuple; infrastructure | FROZEN |
| `session_start_hour_utc` | NO | — | Correlated pair; frozen to prevent invalid combos | FROZEN |
| `session_end_hour_utc` | NO | — | Correlated pair; frozen to prevent invalid combos | FROZEN |
| `symbol` | NO | — | Infrastructure parameter | FROZEN |
| `tf_setup` | NO | — | Infrastructure parameter | FROZEN |
| `tf_context` | NO | — | Infrastructure parameter | FROZEN |
| `tf_bias` | NO | — | Infrastructure parameter | FROZEN |
| `flow_bucket_tf` | NO | — | Infrastructure parameter | FROZEN |
| **UNSUPPORTED** | | | | |
| `force_order_history_points` | NO | — | Not reachable through AppSettings adapter | UNSUPPORTED |

---

## Structural Implication

26 of ~45 ACTIVE parameters are volume levers. This means Optuna can always find
a path to higher trade count by exploiting any one of these dimensions. The optimizer
has demonstrated this pattern across three consecutive runs:
- Run #3: selected `weight_sweep_detected=4.95` (volume lever, since frozen)
- Run #4: selected `sweep_proximity_atr=1.8` (volume lever, "up" direction)

**Required action before Run #5:** freeze confirmed volume levers or add a selectivity
constraint to the objective function. See `SIGNAL_ANALYSIS_V1.md` for the decision tree.

---

## Open Item: Objective Function Vulnerability

OPEN: Optuna multi-objective does not penalize volume inflation. A configuration
with 800 trades at PF 1.01 can dominate 200 trades at PF 1.15 on the drawdown axis.
Structural fix required before Run #5: either minimum selectivity constraint or
trade-quality objective. Separate milestone.
