# Paper Trading Deployment: trial-00095

Date: 2026-05-08
Candidate: `optuna-default-v3-trial-00095`
Mode: PAPER TRADING
Server: `root@204.168.146.253`
Builder: Codex

## Deployment Summary

- Source audit: `docs/audits/AUDIT_WF_TRIAL_00095_2026-05-08.md`
- Deployment commit: `106c575b`
- Server path: `/home/btc-bot/btc-bot`
- Runtime profile: `experiment`
- Runtime mode: `PAPER`
- Runtime config hash after restart:
  `afbd2eb052af3be748950d6b639880ef05c33a03380d8e6ba9fb243170b747d5`
- Position sizing guardrail: `risk_per_trade_pct=0.005` (0.5% risk/trade)
- Monitoring timer: `btc-bot-trial-monitor.timer`, hourly
- Monitoring log: `logs/trial_00095_monitoring.json`

## Backups

Created before pulling deployment commit:

- `deployment_backups/pre_trial_00095_20260508T205449Z/settings.py`
- `deployment_backups/pre_trial_00095_20260508T205449Z/settings_json_absent.txt`
- `deployment_backups/pre_trial_00095_20260508T205449Z/btc_bot.db`

`settings.json` did not exist before this deployment. Runtime settings were
previously defined by `settings.py` plus systemd profile/env.

## Deployed Runtime Parameters

Parameters were extracted from production `research_lab/research_lab.db` for
`optuna-default-v3-trial-00095`, split into runtime `strategy` and `risk`
sections, then written to `settings.json`. `risk_per_trade_pct` was overridden
from the trial value `0.0055` to the mandatory paper guardrail `0.005`.

### Strategy

| Parameter | Value |
|---|---:|
| allow_long_in_uptrend | true |
| atr_period | 27 |
| compression_atr_norm_max | 0.0039 |
| confluence_min | 3.9000000000000004 |
| direction_tfi_threshold | 0.09999999999999999 |
| ema_trend_gap_pct | 0.017 |
| entry_offset_atr | 0.07 |
| equal_level_lookback | 276 |
| equal_level_tol_atr | 0.09 |
| funding_window_days | 130 |
| invalidation_offset_atr | 0.14 |
| min_stop_distance_pct | 0.0019000000000000002 |
| min_sweep_depth_pct | 0.00649 |
| oi_z_window_days | 35 |
| post_liq_tfi_abs_min | 0.78 |
| reclaim_buf_atr | 0.07 |
| sweep_buf_atr | 0.46 |
| tfi_impulse_threshold | 0.31 |
| tp1_atr_mult | 2.2 |
| tp2_atr_mult | 6.5 |
| weight_cvd_divergence | 3.2 |
| weight_ema_trend_alignment | 3.35 |
| weight_funding_supportive | 1.1 |
| weight_reclaim_confirmed | 2.15 |
| weight_regime_special | 1.8 |
| weight_sweep_detected | 2.2 |
| weight_tfi_impulse | 2.5 |
| wick_min_atr | 0.2 |

### Risk

| Parameter | Value |
|---|---:|
| cooldown_minutes_after_loss | 125 |
| daily_dd_limit | 0.10600000000000001 |
| duplicate_level_tolerance_pct | 0.0016 |
| duplicate_level_window_hours | 123 |
| high_vol_leverage | 1 |
| high_vol_stop_distance_pct | 0.085 |
| max_consecutive_losses | 7 |
| max_hold_hours | 34 |
| max_leverage | 2 |
| max_open_positions | 1 |
| max_trades_per_day | 5 |
| min_rr | 2.6500000000000004 |
| partial_exit_pct | 0.8200000000000001 |
| risk_per_trade_pct | 0.005 |
| trailing_atr_mult | 1.6 |
| weekly_dd_limit | 0.12 |

### Research-Only Params Not In Runtime Surface

These params are retained in `settings.json` for lineage but are not read by the
live bot runtime:

| Parameter | Value |
|---|---:|
| allow_uptrend_continuation | false |
| uptrend_continuation_confluence_multiplier | 1.2000000000000002 |
| uptrend_continuation_participation_min | 0.15000000000000002 |
| uptrend_continuation_reclaim_strength_min | 0.6 |

Lineage note: the deployment uses the production Research Lab database as the
source of truth. Some narrative key-param summaries in handoff/audit text differ
from the actual `params_json`; those summaries were not used for deployment.

## Monitoring Conditions

Mandatory guardrails are encoded in `settings.json` and enforced by
`scripts/monitor_trial_00095.py`.

1. Position sizing: `0.5%` risk/trade until at least 30 clean live paper trades.
2. Trade frequency: expected `2-5` trades/month; review if fewer than `2`
   trades/month for 2 consecutive complete months.
3. Benchmarks after 30 trades: ER `>1.5`, PF `>3.0`, DD `<10%`.
4. Benchmarks after 50 trades: ER `>2.0`, PF `>3.5`, DD `<10%`.
5. Early review: after `30-50` trades or `3-4` months, whichever comes first.
6. Hard stop: if ER `<1.0` after 30 trades, monitor writes safe mode to
   `storage/btc_bot.db`.
7. Review alerts: PF `<2.0` after 30 trades or DD `>12%`.

## Verification

- [x] Production DB/config backup created before deployment.
- [x] Server fast-forwarded to deployment commit `106c575b`.
- [x] `settings.json` deployed.
- [x] Effective runtime settings confirmed:
  - `mode=PAPER`
  - `risk_per_trade_pct=0.005`
  - `confluence_min=3.90`
  - `max_open_positions=1`
  - `max_trades_per_day=5`
  - `weight_sweep_detected=2.2`
- [x] `btc-bot.service` restarted successfully.
- [x] `btc-bot.service` active.
- [x] Startup log confirms PAPER mode and profile `experiment`.
- [x] Monitoring systemd timer installed and active.
- [x] Initial monitor run succeeded.
- [x] Initial monitor output has `trade_count=0`, `alerts=[]`,
  `hard_stop=false`, `mode=PAPER`.

## Current Runtime Status

At verification:

- `btc-bot.service`: active
- `btc-bot-trial-monitor.timer`: active
- Open positions: `0`
- Safe mode: `0`
- Current deployment trade count: `0`
- Current deployment alerts: none

## Next Steps

- Claude Code audit of this deployment checkpoint.
- Monitor `logs/trial_00095_monitoring.json` and `btc-bot-trial-monitor.timer`.
- Review after 30-50 paper trades or 3-4 months, whichever comes first.
- Stop/diagnose if monitor applies safe mode after ER `<1.0` at 30 trades.
