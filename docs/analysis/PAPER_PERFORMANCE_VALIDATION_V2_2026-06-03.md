# PAPER_PERFORMANCE_VALIDATION_V2

**Date:** 2026-06-03  
**Builder:** Codex  
**Type:** Read-only production PAPER performance extraction  
**Scope:** Production DB query only; no production writes, no restarts, no settings changes  
**Candidate:** `experiment-profile-permissive-v1`  
**Window:** `cycle_timestamp >= 2026-06-02T04:28:26Z`  
**Data source:** `ssh root@204.168.146.253`, `/home/btc-bot/btc-bot/storage/btc_bot.db`

---

## Executive Summary

`NO_DATA` / `TIER_DEGRADATION`: all three active assets have `0` closed PAPER trades in the legalized V2 window, so realized ER/PF cannot be compared to WF reference and the immediate finding is structural no-trade investigation, not statistical validation.

---

## 1. Methodology

This milestone implements Path B staged validation from the handoff. Production
access followed `docs/DATA_SOURCES.md` and used read-only SSH queries against
SQLite URI `mode=ro`.

No production process was restarted. No production database rows were written.
No production settings were changed.

### Pre-Declared Tier Matrix

| Trades per active asset | Verdict tier | Confidence |
|---|---|---|
| >=10 | `STATISTICAL_SIGNIFICANCE` | High - standard promotion-quality evidence |
| >=5 and <10 | `DIRECTIONAL_CONFIRMATION` | Medium - strong signal but not conclusive |
| >=3 and <5 | `EARLY_SIGNAL` | Low - observed metrics reported, no claim of significance |
| 1 or 2 | `ANECDOTAL` | Insufficient - report metrics for transparency, no inference |
| 0 | `NO_DATA` | Investigate why bot isn't trading; structural issue likely |

Within each tier, the pre-declared matrix is:

- Realized ER >= 50% of WF reference and PF >= 1.5 -> `TIER_OK`
- Realized ER < 50% of reference or PF < 1.0 -> `TIER_DEGRADATION`
- Between -> `TIER_MIXED`

For `0` trades, ER and PF are undefined. This report classifies each asset as
`NO_DATA` and applies a fail-closed `TIER_DEGRADATION` operational label because
the no-trade condition itself is the structural concern called out by the
pre-declared `NO_DATA` tier.

---

## 2. Production Runtime State

| Field | Value |
|---|---|
| Server repo | `/home/btc-bot/btc-bot` |
| Branch | `deploy/multi-asset-paper-v1` |
| Production HEAD | `d3bee883 ops: make backup_production_db.sh executable` |
| Service | `btc-bot.service` |
| Service status | `active` |
| Service start time | `2026-06-02 04:29:34 UTC` |
| Mode | `PAPER` |
| Settings profile | `experiment` |
| Bot healthy | `1` |
| Safe mode | `0` |
| Open positions | `0` |
| Runtime config hash | `c01f7960984a256e8d720c2d27f27bb5cb35c2677dce53293bc4d41b1b7d40f7` |
| Candidate ID source | `settings.json -> deployment.candidate_id` |
| Candidate ID | `experiment-profile-permissive-v1` |
| Legacy candidate check | Not `optuna-default-v3-trial-00095` |

Note: the production `bot_state` table does not have a `candidate_id` column.
The candidate identity is stored in `settings.json` deployment metadata and is
therefore reported from that source.

Systemd runtime:

```text
ExecStart=/home/btc-bot/btc-bot/.venv/bin/python main.py --mode PAPER
Environment=BOT_SETTINGS_PROFILE=experiment
```

---

## 3. Config Lineage Check

Reference candidate spec:
`research_lab/candidates/experiment-profile-permissive-v1.json`

| Field | Frozen spec | Production runtime | Result |
|---|---:|---:|---|
| `candidate_id` | `experiment-profile-permissive-v1` | `experiment-profile-permissive-v1` | PASS |
| BTC `strategy.min_sweep_depth_pct` | `0.005` | `0.005` | PASS |
| ETH `min_sweep_depth_pct` override | `0.0075` | `0.0075` | PASS |
| SOL `min_sweep_depth_pct` override | `0.0075` | `0.0075` | PASS |
| `risk.risk_per_trade_pct` | `0.005` | `0.005` | PASS |
| Protocol hash | `023dc84c2cd8eff7e0226a1cb74cca24ce64a896aacac7f8c4a61199fac9e1b8` | A2 reference | PASS |
| Candidate config hash | `68fd6caf83ff549f1741d04585a06f6b758a87c40380bc15450d5e35b0319593` | A2 reference | PASS |

The active runtime config hash (`c01f7960...`) is not expected to equal the A2
research candidate config hash because the runtime hash includes production
runtime/config snapshot surfaces. The lineage check here is parameter identity
against the frozen spec, not hash equality across different config domains.

---

## 4. Production DB Coverage

| Table / field | Value |
|---|---:|
| `trade_log` total rows | `1` |
| `trade_log` opened in V2 window | `0` |
| `trade_log` closed in V2 window | `0` |
| `positions` total rows | `1` |
| `positions` opened in V2 window | `0` |
| `signal_candidates` total rows | `1` |
| `signal_candidates` in V2 window | `0` |
| `decision_outcomes` total rows | `2,721` |
| `decision_outcomes` in V2 window | `276` |
| `daily_metrics` total rows | `11` |
| `daily_metrics` in V2 window | `2` |
| `alerts_errors` total rows | `137` |
| `alerts_errors` in V2 window | `39` |

| Coverage field | Value |
|---|---|
| First decision cycle | `2026-06-02T04:30:00.002372+00:00` |
| Last decision cycle | `2026-06-03T03:15:00.001904+00:00` |
| First daily metric date | `2026-06-02` |
| Last daily metric date | `2026-06-03` |
| First trade open in window | `null` |
| Last trade open in window | `null` |
| First trade close in window | `null` |
| Last trade close in window | `null` |

---

## 5. PAPER Trade Metrics Per Asset

WF reference for `experiment-profile-permissive-v1`:

| Reference metric | Value |
|---|---:|
| Expectancy R | `1.6590` |
| Profit factor | `3.5310` |
| Win rate | `51.81%` |

Realized PAPER metrics in the V2 window:

| Asset | Trades | ER | Median R | Win rate | Profit factor | PnL R sum | MDD R |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | `0` | `n/a` | `n/a` | `n/a` | `n/a` | `0.0000` | `0.0000` |
| ETHUSDT | `0` | `n/a` | `n/a` | `n/a` | `n/a` | `0.0000` | `0.0000` |
| SOLUSDT | `0` | `n/a` | `n/a` | `n/a` | `n/a` | `0.0000` | `0.0000` |

No realized closed trades exist in the legalized V2 window. The report therefore
does not claim overfit, validation, or performance degradation from ER/PF.

---

## 6. Decision Funnel Per Symbol

| Symbol | signal_generated | no_sweep | sweep_too_shallow | no_reclaim | symbol_cycle_failed | Total cycles |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | `0` | `67` | `20` | `5` | `0` | `92` |
| ETHUSDT | `0` | `81` | `3` | `0` | `8` | `92` |
| SOLUSDT | `0` | `82` | `2` | `0` | `8` | `92` |

All assets are cycling. The no-trade result is therefore not explained by a
complete decision-loop absence. ETH/SOL also still show rate-limit failures in
the decision table.

---

## 7. Infrastructure Health

`alerts_errors` contains `39` rows in the V2 window.

| Severity / component / type | Count |
|---|---:|
| `critical` / `multi_asset` / `error` | `16` |
| `warning` / `health` / `audit` | `8` |
| `warning` / `telegram` / `audit` | `1` |
| `info` audit rows | `14` |

Critical multi-asset errors are all Binance HTTP 429 rate limits:

| Symbol | 429 errors |
|---|---:|
| ETHUSDT | `8` |
| SOLUSDT | `8` |

| Endpoint | 429 errors |
|---|---:|
| `/fapi/v1/aggTrades` | `8` |
| `/fapi/v1/klines` | `8` |

The 429 pattern from V1 persists in the legalized V2 window. This remains
in-scope for V2 because ETH/SOL have `0` trades and the failures are
concentrated on ETH/SOL.

---

## 8. Foundation Tier Classification

| Asset | Trades | Verdict tier | Matrix verdict | Basis |
|---|---:|---|---|---|
| BTCUSDT | `0` | `NO_DATA` | `TIER_DEGRADATION` | Fail-closed no-data condition; ER/PF undefined |
| ETHUSDT | `0` | `NO_DATA` | `TIER_DEGRADATION` | Fail-closed no-data condition; ER/PF undefined; 8 cycle failures |
| SOLUSDT | `0` | `NO_DATA` | `TIER_DEGRADATION` | Fail-closed no-data condition; ER/PF undefined; 8 cycle failures |

This is a structural observation, not a statistical performance conclusion.

---

## 9. Aggregate Verdict

Aggregate verdict uses the worst tier across active assets per AGENTS.md
fail-closed principle:

```text
NO_DATA / TIER_DEGRADATION
```

No active asset has enough data for `ANECDOTAL`, `EARLY_SIGNAL`,
`DIRECTIONAL_CONFIRMATION`, or `STATISTICAL_SIGNIFICANCE`. Because all three
assets have `0` trades, the only supported conclusion is to investigate why
legalized production PAPER is not generating signals/trades in the observed
window.

---

## 10. Recommended Next Step

Do not change candidate parameters from this report. This is a measurement
milestone, not a remediation milestone.

Recommended next step:

1. Investigate the V2 no-signal/no-trade condition, starting from the decision
   funnel (`no_sweep` dominance) and the absence of `signal_candidates`.
2. Treat ETH/SOL 429s as an active infrastructure sub-question because they
   persist in the legalized window and coincide with zero ETH/SOL trades.
3. Re-run `PAPER_PERFORMANCE_VALIDATION_V2` after new closed trades accumulate
   under the same `experiment-profile-permissive-v1` lineage.

---

## Footer

Companion JSON:
`docs/analysis/PAPER_PERFORMANCE_VALIDATION_V2_2026-06-03.json`

Companion JSON SHA256:
`b995f0b73f0a1d7f2de11684783f8b5a5fd6566093272403b270904277900bc2`
