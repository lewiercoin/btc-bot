# EXPERIMENT_PROFILE_PERMISSIVE_V1_LINEAGE

**Date:** 2026-06-01  
**Candidate ID:** `experiment-profile-permissive-v1`  
**Status:** `WF_SCREENING_PASSED_AWAITING_AUDIT`  
**Type:** Lineage legalization bundle, repo-only phase A1.build  

---

## Executive Summary

`experiment-profile-permissive-v1` is the formal identity for the configuration
currently running on production PAPER after an out-of-chain production edit on
2026-05-25T23:16:48Z. The runtime strategy parameters are not the frozen
`optuna-default-v3-trial-00095` parameters because BTC
`min_sweep_depth_pct` is `0.005` instead of `0.00649`, while ETH/SOL use
`0.0075` overrides.

This document does not approve the profile and does not validate its edge. It
only records the lineage break, assigns a truthful candidate identity, and
defines the metadata-only deploy path needed before offline WF validation.

The prior path should not recur. Strategy and risk parameters must move through
commit -> audit -> deploy. A backup-and-edit pattern on production runtime
configuration is evidence of an anti-pattern, even when the parameter change is
strategically reasonable.

---

## 1. Candidate Identity

| Field | Value |
| --- | --- |
| New candidate ID | `experiment-profile-permissive-v1` |
| Parent candidate | `optuna-default-v3-trial-00095` |
| Runtime mode | PAPER |
| Runtime profile | `experiment` |
| Legalization status | `AWAITING_WF_VALIDATION` |
| Production behavior change in A1.build | None |

This candidate is a permissive-frequency derivative of trial-00095. It must not
be reported as frozen trial-00095 until it has passed its own validation chain.

---

## 2. Parameter Diff Against Frozen Trial-00095

All parameters are inherited from `optuna-default-v3-trial-00095` except the
rows below.

| Scope | Parameter | Frozen trial-00095 | Current runtime | Classification |
| --- | --- | ---: | ---: | --- |
| BTC default | `strategy.min_sweep_depth_pct` | `0.00649` | `0.005` | Permissive frequency change |
| ETH override | `multi_asset.symbol_overrides[].min_sweep_depth_pct` | N/A | `0.0075` | Asset-specific override |
| SOL override | `multi_asset.symbol_overrides[].min_sweep_depth_pct` | N/A | `0.0075` | Asset-specific override |
| Risk guardrail | `risk.risk_per_trade_pct` | `0.0055` trial param | `0.005` | Paper guardrail from 2026-05-08 deployment |

The ETH/SOL overrides are documented by multi-asset activation work. The BTC
`0.005` threshold is the lineage problem: it is present on production but not
in a committed promotion artifact for the active candidate label.

### Inherited Runtime Parameters

The following runtime parameters remain inherited from the 2026-05-08
trial-00095 deployment record unless listed in the diff table above.

| Group | Parameters inherited unchanged |
| --- | --- |
| Strategy toggles | `allow_long_in_uptrend` |
| ATR / volatility | `atr_period`, `compression_atr_norm_max`, `wick_min_atr` |
| Signal scoring | `confluence_min`, `weight_cvd_divergence`, `weight_ema_trend_alignment`, `weight_funding_supportive`, `weight_reclaim_confirmed`, `weight_regime_special`, `weight_sweep_detected`, `weight_tfi_impulse` |
| Direction / flow | `direction_tfi_threshold`, `tfi_impulse_threshold`, `post_liq_tfi_abs_min` |
| Trend / levels | `ema_trend_gap_pct`, `equal_level_lookback`, `equal_level_tol_atr`, `funding_window_days`, `oi_z_window_days` |
| Entry / invalidation | `entry_offset_atr`, `invalidation_offset_atr`, `reclaim_buf_atr`, `sweep_buf_atr`, `min_stop_distance_pct` |
| Targets | `tp1_atr_mult`, `tp2_atr_mult` |
| Risk | `cooldown_minutes_after_loss`, `daily_dd_limit`, `duplicate_level_tolerance_pct`, `duplicate_level_window_hours`, `high_vol_leverage`, `high_vol_stop_distance_pct`, `max_consecutive_losses`, `max_hold_hours`, `max_leverage`, `max_open_positions`, `max_trades_per_day`, `min_rr`, `partial_exit_pct`, `trailing_atr_mult`, `weekly_dd_limit` |
| Research-only lineage | `allow_uptrend_continuation`, `uptrend_continuation_confluence_multiplier`, `uptrend_continuation_participation_min`, `uptrend_continuation_reclaim_strength_min` |

Runtime additions from the multi-asset activation are retained as part of the
currently running profile: `multi_asset.enabled=true`, enabled symbols
`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, paper simulation enabled, and alerts metadata.
Those additions are not changed in Phase A1.

---

## 3. Drift Incident Timeline

| Time | Event | Evidence |
| --- | --- | --- |
| 2026-05-08 | trial-00095 paper deployment approved | `AUDIT_DEPLOYMENT_TRIAL_00095_2026-05-08.md` |
| 2026-05-24T16:44:42Z | Production config snapshot captured BTC threshold `0.00649` | `storage/btc_bot.db.config_snapshots` |
| 2026-05-25T23:16:48Z | Manual production edit changed BTC threshold to `0.005` | `settings.json` mtime and `settings.json.bak_btc_threshold_` |
| 2026-05-25T23:16:48Z | Service received SIGTERM | `journalctl -u btc-bot.service` |
| 2026-05-25T23:16:53Z | Service restarted | `journalctl -u btc-bot.service` |
| 2026-05-25T23:16:54Z | Production config snapshot captured BTC threshold `0.005` | `storage/btc_bot.db.config_snapshots` |
| 2026-06-01 | Drift discovered during `PAPER_PERFORMANCE_VALIDATION_V1` | `docs/analysis/PAPER_PERFORMANCE_VALIDATION_V1_2026-06-01.md` |

User-stated motivation: increase signal frequency at the cost of lower
historical ER. The motivation is product-rational; the deployment path was not
process-compliant.

---

## 4. Discovery Scan: False Candidate ID Locations

### Runtime-Effective Locations

| Location | Type | Current value | Runtime-effective? | A1.deploy action |
| --- | --- | --- | --- | --- |
| `/home/btc-bot/btc-bot/settings.json:deployment.candidate_id` | settings file | `optuna-default-v3-trial-00095` | Yes. Restart reads this file. | Update to `experiment-profile-permissive-v1` with audited metadata-only script. |
| `/home/btc-bot/btc-bot/settings.json:monitoring.candidate_id` | settings file | `optuna-default-v3-trial-00095` | Yes. Monitor/reporting uses this label. | Update to `experiment-profile-permissive-v1` with audited metadata-only script. |
| `/home/btc-bot/btc-bot/logs/trial_00095_monitoring.json` | runtime monitoring artifact | `optuna-default-v3-trial-00095` | Resolved in this follow-up commit by reading candidate_id from settings.json at runtime. | Next monitor run after A1.deploy will emit the new candidate ID. |

### Not Runtime-Effective / Historical Locations

| Location | Type | Classification | Action |
| --- | --- | --- | --- |
| `/home/btc-bot/btc-bot/settings.json.bak_btc_threshold_` | backup file | Evidence of pre-edit threshold `0.00649` | Preserve. Do not edit. |
| `storage/btc_bot.db.config_snapshots` | DB historical snapshots | Historical evidence of config hashes before and after drift | Preserve. Do not overwrite. |
| `docs/deployments/DEPLOYMENT_TRIAL_00095_PAPER_2026-05-08.md` | deployment record | Correct historical record for original deployment | Preserve. |
| `docs/audits/AUDIT_*TRIAL_00095*` | audit records | Historical references | Preserve. |
| `docs/analysis/*TRIAL_00095*` | analysis reports | Historical references | Preserve. |
| `research_lab/**trial_00095**` | research code/reports | Historical research references | Preserve. |
| `scripts/monitor_trial_00095.py` | monitor script | Script name is historical; candidate_id payload now reads from `monitoring.candidate_id` in settings.json at runtime (updated in A1.build follow-up) | No further action needed for candidate-id lineage. Script filename rename remains separate scope. |
| `tests/test_trial_00095_deployment.py` | tests | Historical trial-00095 deployment tests | Preserve. |

### Warning 2 Resolution

The Claude Code audit (commit `262506b`) raised Warning 2: `scripts/monitor_trial_00095.py`
line 144 hardcodes `{"candidate_id": "optuna-default-v3-trial-00095"}` in the
`_apply_safe_mode` payload written to `alerts_errors`. After A1.deploy,
`settings.json` would say `experiment-profile-permissive-v1` but the monitor
would continue writing the old identity.

**Resolution: Option A** — The monitor script was updated in this follow-up
commit to pass `candidate_id` dynamically from the monitoring config (already
loaded from `settings.json:monitoring.candidate_id`) into `_apply_safe_mode`.
The hardcoded literal was removed. If `candidate_id` is missing from the
monitoring config, the script exits with a non-zero code and clear error
message instead of silently falling back.

A dedicated test (`tests/test_monitor_trial_00095_candidate_id.py`) verifies
that the monitor reads candidate_id dynamically and fails loudly when the
field is absent.

Option B (defer to a separate milestone with monitor paused) was not chosen
because the fix is a one-parameter change with no design risk, and deferring
would leave the lineage leak open across all monitor runs between A1.deploy
and the deferred milestone.

### Production DB Schema Correction

The handoff assumed `bot_state.candidate_id` exists. Production discovery shows
that `bot_state` has no `candidate_id` column. Its columns are runtime health
fields only: `mode`, `healthy`, `safe_mode`, drawdown fields, `last_trade_at`,
and error/safe-mode timestamps.

Therefore A1.deploy must not attempt a DB write to `bot_state.candidate_id`.
The runtime-effective false identity is in `settings.json`, not in `bot_state`.

---

## 5. Production DB Coverage Gap

The 2026-05-08 to 2026-05-24 coverage gap remains unresolved in A1.build.
Observed production DB tables start decision coverage on 2026-05-24. The likely
classes of explanation are:

- DB rotation/reset around 2026-05-24;
- bot inactivity before 2026-05-24;
- earlier deployment using a different DB path.

This is not resolved by the candidate-id metadata update. It remains a parent
`CONFIG_LINEAGE_RECONCILIATION_V1` item before paper-performance conclusions
can be decision-grade.

---

## 6. Phase A1.deploy Implication

Phase A1.deploy is a metadata legalization step, not a strategy deployment.

It may update:

- candidate-id metadata in production `settings.json`;
- candidate-id metadata verification artifacts/logs.

It must not update:

- `strategy.*`;
- `risk.*`;
- `multi_asset.symbol_overrides`;
- `config_snapshots`;
- `trade_log`, `signal_candidates`, or any performance table;
- historical audit/report files on production.

If any runtime-effective location other than settings metadata is discovered
during deploy, stop and return for audit rather than editing manually.

---

## 7. Status And Next Step

`experiment-profile-permissive-v1` is now named and deployed.

Phase A1.deploy was executed on 2026-06-02. Phase A2 local PC offline WF
screening was executed on 2026-06-02 against the exact legalized BTC threshold
override (`min_sweep_depth_pct=0.005`) and passed the mechanical post-hoc WF
gate (`2/2` windows, `fragile=false`).

The A2 builder verdict is still `SCREENING_ONLY`, not promotion approval.
Claude Code audit is required. After the server key became available on this
PC, Codex reran A2 against the fetched server snapshot
`research_lab/snapshots/replay-optuna-default-v3-trial-00095.db`; server and
local SHA256 matched:
`ad8c5e7b4f541d5c34b2d6dde83aa0110f885a9eb4e0fa2d67c6705167363bca`.

---

## 8. A1.deploy Completion Record

**Deploy date:** 2026-06-02T04:28:26Z (restart timestamp)

### Audit Chain

| Item | Value |
|---|---|
| A1.build commit | `9d99dc7` |
| A1.build follow-up commit | `57c6cd3` |
| Claude audit hash (A1.build) | `3330e22` |
| Production HEAD after pull | `57c6cd37` |

### Backup

| Item | Value |
|---|---|
| Backup path | `/home/btc-bot/backups/database/btc_bot_20260601T174425Z.db` |
| Backup size | 7,075,704,832 bytes (7.07 GB) |
| SHA256 | `7fca1b224ab43ffb1925c9f8cf33f99fb0a603c14c66224bfdb675ae32515a92` |
| Integrity check | `ok` |
| trade_log cross-check | source=1, backup=1, diff=0 |
| decision_outcomes cross-check | source=2445, backup=2418, diff=27 (expected: 4h bot runtime after backup snapshot) |

### Metadata Update

| Item | Value |
|---|---|
| Update log | `docs/operations/CANDIDATE_ID_UPDATE_2026-06-02T042708Z0000.log` |
| deployment.candidate_id | `experiment-profile-permissive-v1` |
| monitoring.candidate_id | `experiment-profile-permissive-v1` |
| strategy.min_sweep_depth_pct | `0.005` (unchanged) |
| multi_asset ETH/SOL overrides | `0.0075` (unchanged) |

### Restart Evidence

| Item | Value |
|---|---|
| Pre-restart PID | 992005 |
| Post-restart PID | 1078902 |
| systemctl is-active | `active` |
| Old candidate ID in post-restart logs | 0 occurrences |
| First decision cycle | `2026-06-02T04:30:00` (no_signal) |
| config_hash | `c01f7960984a256e8d720c2d27f27bb5cb35c2677dce53293bc4d41b1b7d40f7` |

### Runbook Deviations

1. **Backup method:** `sqlite3 .backup` WAL live-locked for ~9 hours (started
   17:44 UTC Jun 1, completed ~02:15 UTC Jun 2). Root cause: bot actively
   writing to WAL while backup re-reads changed pages. Backup ultimately
   completed on its own and passed all three verification checks. See
   "Backup Incident 2026-06-01" appendix in the deploy runbook.

2. **Permission error on settings.json:** The `update_candidate_id_metadata_only.py`
   script ran as `root` via SSH, changing file ownership from `btc-bot:btc-bot`
   to `root:root` with mode `0600`. Bot service (running as `btc-bot` user)
   crashed 3 times with `PermissionError` before the issue was identified and
   fixed with `chown btc-bot:btc-bot && chmod 644`. Lesson: the metadata update
   script should preserve file ownership, or the runbook should include a
   post-update ownership verification step.

3. **Startup log pattern:** The runbook expected a log line
   `deployment.candidate_id = experiment-profile-permissive-v1` at startup.
   The bot does not emit this exact line. Adapted verification used: (a) positive
   check on settings.json values, (b) negative check for absence of old ID in
   logs, (c) service health + decision cycle confirmation.
