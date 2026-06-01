# PAPER_PERFORMANCE_VALIDATION_V1

**Date:** 2026-06-01  
**Builder:** Codex  
**Type:** Read-only production PAPER performance extraction  
**Scope:** Production DB query only; no production changes, no settings changes, no code changes  
**Data source:** `ssh root@204.168.146.253`, `/home/btc-bot/btc-bot/storage/btc_bot.db`

---

## Executive Summary

This report was created after the blueprint foundations concern: before continuing
offline multi-asset transfer work, validate whether real PAPER performance supports
or challenges the historical trial-00095 foundation.

The production PAPER dataset is not decision-grade yet. The production database
contains only `1` closed trade across the current captured window
(`2026-05-24` to `2026-06-01`). Under the pre-declared foundation audit rule,
fewer than 10 trades per asset is `INCONCLUSIVE_WAIT`, not evidence of overfit
and not evidence that the blueprint is validated.

There is also a config-lineage blocker: the running service uses
`BOT_SETTINGS_PROFILE=experiment`, not a pure frozen trial-00095 profile. Current
experiment settings include BTC `min_sweep_depth_pct=0.005` and ETH/SOL symbol
overrides at `0.0075`, while frozen trial-00095 has `min_sweep_depth_pct=0.00649`.
Therefore current PAPER performance cannot be used as a direct validation of
frozen trial-00095 without first documenting the active profile lineage.

**Recommendation:** `INCONCLUSIVE_WAIT_WITH_CONFIG_LINEAGE_BLOCKER`.

---

## 1. Query Scope

Production access followed `docs/DATA_SOURCES.md`.

Commands were read-only:

- inspect SQLite schema and counts;
- query `trade_log`, `signal_candidates`, `decision_outcomes`, `daily_metrics`,
  `bot_state`, and recent alerts;
- inspect systemd unit only for non-secret runtime profile information;
- inspect active settings profile values without printing credentials.

No production process was restarted. No production DB was written. No local
runtime files were modified.

---

## 2. Production Runtime State

| Field | Value |
| --- | --- |
| Server repo | `/home/btc-bot/btc-bot` |
| Branch | `deploy/multi-asset-paper-v1` |
| Server commit | `1797a209bf6b42ab697dd3947d1cfa13a943bd58` |
| Service | `btc-bot.service` |
| Service status | `active` |
| Mode | `PAPER` |
| Settings profile | `experiment` |
| Bot healthy | `1` |
| Safe mode | `0` |
| Open positions | `0` |
| Last trade at | `2026-05-28T14:15:41.008608+00:00` |

Systemd unit:

```text
Environment="BOT_SETTINGS_PROFILE=experiment"
ExecStart=/home/btc-bot/btc-bot/.venv/bin/python main.py --mode PAPER
```

---

## 3. Config Lineage Check

The active profile queried on production is `experiment`.

| Parameter | Active experiment value | Frozen trial-00095 reference |
| --- | ---: | ---: |
| `min_sweep_depth_pct` BTC default | `0.005` | `0.00649` |
| `confluence_min` | `3.9` | `3.9` |
| `direction_tfi_threshold` | `0.10` | `0.10` |
| `sweep_buf_atr` | `0.46` | `0.46` |
| `reclaim_buf_atr` | `0.07` | `0.07` |
| `entry_offset_atr` | `0.07` | `0.07` |
| `invalidation_offset_atr` | `0.14` | `0.14` |
| `tp1_atr_mult` | `2.2` | `2.2` |
| `tp2_atr_mult` | `6.5` | `6.5` |
| `max_hold_hours` | `34` | `34` |
| `risk_per_trade_pct` | `0.005` | `0.0055` |
| `multi_asset.enabled` | `True` | N/A |
| `enabled_symbols` | `BTCUSDT, ETHUSDT, SOLUSDT` | BTC-only baseline |
| ETH override | `min_sweep_depth_pct=0.0075` | N/A |
| SOL override | `min_sweep_depth_pct=0.0075` | N/A |

This explains why the single BTC trade had `sweep_depth_pct=0.005148`, below the
frozen trial-00095 `0.00649` threshold but above the active experiment profile
BTC threshold of `0.005`.

**Implication:** this production PAPER sample validates the current experiment
profile only. It cannot be used as direct frozen trial-00095 proof without a
separate lineage statement.

---

## 4. Production DB Coverage

| Table | Rows |
| --- | ---: |
| `trade_log` | 1 |
| `positions` | 1 |
| `signal_candidates` | 1 |
| `decision_outcomes` | 2,289 |
| `daily_metrics` | 9 |
| `alerts_errors` | 95 |
| `bot_state` | 1 |

| Coverage field | Value |
| --- | --- |
| First decision cycle | `2026-05-24T16:45:00.002867+00:00` |
| Last decision cycle | `2026-06-01T15:15:00.001784+00:00` |
| First daily metric date | `2026-05-24` |
| Last daily metric date | `2026-06-01` |
| First trade open | `2026-05-28T14:15:41.008608+00:00` |
| Last trade close | `2026-05-28T14:17:06.817670+00:00` |

The database coverage starts on `2026-05-24`, so it does not provide a complete
record back to the initial BTC PAPER deployment date referenced in earlier
foundation discussion.

---

## 5. PAPER Trade Metrics

Closed trades: `1`

| Metric | Value |
| --- | ---: |
| Expectancy R | `0.2229` |
| Median R | `0.2229` |
| Win rate | `100.00%` |
| Profit factor | `inf` |
| PnL R sum | `0.2229` |
| Max drawdown R | `0.0` |

This is not statistically meaningful. It does not validate or invalidate
trial-00095, ETH transfer, SOL transfer, or the blueprint.

### Only Closed Trade

| Field | Value |
| --- | --- |
| Symbol inference | BTCUSDT from active BTC signal context |
| Opened | `2026-05-28T14:15:41.008608+00:00` |
| Closed | `2026-05-28T14:17:06.817670+00:00` |
| Direction | `LONG` |
| Regime | `normal` |
| Confluence | `6.85` |
| Entry | `73280.1` |
| Exit | `73385.5757` |
| PnL R | `0.2229` |
| Exit reason | `TP` |
| Sweep depth | `0.0051487` |
| TFI 60s | `0.5902` |
| OI z-score | `3.9254` |
| Funding percentile | `84.8718` |

---

## 6. Decision Funnel

| Outcome group | Count |
| --- | ---: |
| `no_signal` | 2,274 |
| `symbol_cycle_failed` | 14 |
| `signal_generated` | 1 |

Per-symbol cycle counts are balanced:

| Symbol | Decision rows |
| --- | ---: |
| BTCUSDT | 763 |
| ETHUSDT | 763 |
| SOLUSDT | 763 |

Per-symbol reasons:

| Symbol | Reason | Count |
| --- | --- | ---: |
| BTCUSDT | `no_sweep` | 318 |
| BTCUSDT | `sweep_too_shallow` | 432 |
| BTCUSDT | `no_reclaim` | 12 |
| BTCUSDT | `signal_generated` | 1 |
| ETHUSDT | `no_sweep` | 647 |
| ETHUSDT | `sweep_too_shallow` | 110 |
| ETHUSDT | `symbol_cycle_failed` | 6 |
| SOLUSDT | `no_sweep` | 713 |
| SOLUSDT | `sweep_too_shallow` | 42 |
| SOLUSDT | `symbol_cycle_failed` | 8 |

The multi-asset runtime is cycling all three symbols. ETH/SOL scarcity is mainly
`no_sweep` or `sweep_too_shallow`, not governance/risk vetoes in this sample.

---

## 7. Infrastructure Health Finding

There are `14` symbol-cycle failures in the production DB, all from Binance HTTP
429 rate limits.

| Symbol | Failures |
| --- | ---: |
| ETHUSDT | 6 |
| SOLUSDT | 8 |

Observed endpoints:

- `/fapi/v1/aggTrades`
- `/fapi/v1/klines`

Example error class:

```text
BinanceRequestError(... http=429, code=-1003,
msg=Too many requests; current limit of IP(204.168.146.253) is 2400 requests per minute.
Please use the websocket for live updates to avoid polling the API.)
```

This does not explain the low trade count by itself, but it is a production
confidence blocker for multi-asset scaling because missed cycles occur on ETH
and SOL.

---

## 8. Foundation Decision Rule

Pre-declared rule from the blueprint foundation discussion:

| Condition | Verdict |
| --- | --- |
| Real ER >= 50% historical and PF >= 1.5 | `BLUEPRINT_OK` |
| Real ER < 50% historical or PF < 1.0 | `OVERFIT_RISK_REVIEW` |
| Fewer than 10 trades per asset | `INCONCLUSIVE_WAIT` |

Actual:

- BTC closed trades: `1`
- ETH closed trades: `0`
- SOL closed trades: `0`

Therefore the only valid verdict under this rule is:

```text
INCONCLUSIVE_WAIT
```

Because config lineage does not match pure frozen trial-00095, the operational
recommendation is stricter:

```text
INCONCLUSIVE_WAIT_WITH_CONFIG_LINEAGE_BLOCKER
```

---

## 9. Comparison To Historical References

Historical reference values remain useful as context but cannot be statistically
tested against one production trade.

| Reference | Historical sample | ER | PF | Notes |
| --- | ---: | ---: | ---: | --- |
| BTC trial-00095 WF/full reference | 271-274 | ~2.12 | ~4.2-4.7 | Frozen BTC baseline |
| ETH frozen transfer | 544 | 1.804 | 2.81 | Passed transfer audit |
| SOL standalone transfer | 1201 | 2.141 | 3.42 | Standalone DD gate failed |
| BTC+ETH+SOL portfolio replay | 1545 | 2.056 | 3.49 | Portfolio gates passed |
| Current production PAPER | 1 | 0.223 | inf | Not decision-grade |

The current sample is too small and not pure frozen trial-00095 lineage, so no
overfit conclusion is warranted.

---

## 10. Recommendation

### Verdict: INCONCLUSIVE_WAIT_WITH_CONFIG_LINEAGE_BLOCKER

Do not proceed with `TRIAL_00095_MULTI_ASSET_TRANSFER_FEASIBILITY_V1` as if
production has already validated the blueprint. Production PAPER evidence is too
small.

Before more offline transfer work, resolve two items:

1. **Config lineage:** decide whether the foundation being monitored is frozen
   trial-00095 (`min_sweep_depth_pct=0.00649`) or the current experiment profile
   (`BTC=0.005`, ETH/SOL=`0.0075`). Reports must stop mixing those two as if
   they were identical.
2. **Runtime data health:** investigate HTTP 429 failures and WebSocket/REST
   fallback behavior before treating ETH/SOL PAPER scarcity as strategy-only
   evidence.

After that:

- continue PAPER observation until at least 10 closed trades per active symbol,
  or a pre-agreed minimum portfolio sample if per-symbol trading remains sparse;
- then re-run this validation with the same pre-declared rule;
- only after `BLUEPRINT_OK` or a consciously accepted `INCONCLUSIVE_WAIT` should
  the offline multi-asset transfer diagnostic resume.

