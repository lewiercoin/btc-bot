# MODELING DATA AUDIT 2026-04-22

Status: read-only production data audit  
Date: 2026-04-22  
Server: `root@204.168.146.253`  
Repo path on server: `/home/btc-bot/btc-bot`  
Database: `storage/btc_bot.db`  
Production branch at audit time: `experiment-v2`  
Production commit at audit time: `601e7771` (`merge: HISTORICAL-DATA-BACKFILL -> experiment-v2`)

This audit answers whether the project currently has the data needed to move
into `MODELING-V1`, and what data work is required before implementation or
activation.

No database writes were performed.

---

## 1. Executive verdict

We should not start full `MODELING-V1` implementation yet.

The technical foundation from `DATA-INTEGRITY-V1` exists and is deployed on
the `experiment-v2` production branch. The bot is running in paper mode,
healthy, and out of safe mode.

However, the modeling dataset is not yet ready for active context eligibility
rules because:

1. Current production config has only a tiny sample.
2. The production database mixes multiple historical/config contexts.
3. Recent trade/signal payloads do not persist `atr_4h_norm`.
4. Runtime fetches current candles/funding for decisions, but does not persist
   those refreshed candles/funding/aggtrade history into the historical replay
   tables.
5. `EXPERIMENT-V2` is still the active validation milestone, and the tracker
   explicitly blocks `MODELING-V1` until it validates `DATA-INTEGRITY`.

Safe next step: keep collecting `EXPERIMENT-V2` data and prepare the
`MODELING-V1` handoff/query plan. Do not activate context whitelist rules yet.

---

## 2. Production runtime state

Audit snapshot:

- branch: `experiment-v2`
- commit: `601e7771`
- bot service: active
- dashboard service: active
- mode: `PAPER`
- healthy: `1`
- safe mode: `0`
- open positions: `0`
- current `config_hash`: `037822f1ddeffc1d3cf9e818c2974b59ffdf36fec8f3f352adf32df91b01b2ba`
- latest runtime snapshot: `2026-04-22T20:00:00.003233+00:00`
- latest 15m candle in runtime snapshot: `2026-04-22T19:45:00+00:00`
- latest 1h candle in runtime snapshot: `2026-04-22T19:00:00+00:00`
- latest 4h candle in runtime snapshot: `2026-04-22T16:00:00+00:00`

The bot is alive and building fresh snapshots. The issue is not runtime
staleness.

---

## 3. Database inventory

Production table counts:

| Table | Rows |
|---|---:|
| `aggtrade_buckets` | 3,122,658 |
| `alerts_errors` | 2,215 |
| `bot_state` | 1 |
| `candles` | 258,901 |
| `config_snapshots` | 3 |
| `cvd_price_history` | 126+ |
| `daily_external_bias` | 1,418 |
| `daily_metrics` | 16 |
| `decision_outcomes` | 231+ |
| `executable_signals` | 2,092 |
| `executions` | 2 |
| `force_orders` | 6,166+ |
| `funding` | 6,164 |
| `oi_samples` | 12,544+ |
| `open_interest` | 526,496 |
| `positions` | 783 |
| `runtime_metrics` | 1 |
| `safe_mode_events` | 25 |
| `signal_candidates` | 2,110 |
| `trade_log` | 783 |

SQLite integrity check:

- `PRAGMA integrity_check`: `ok`
- `PRAGMA foreign_key_check`: no violations returned

Conclusion: the database is structurally healthy. The problem is dataset
selection, not corruption.

---

## 4. Time coverage by table

| Table | Earliest | Latest |
|---|---|---|
| `candles` | `2020-09-01T00:00:00+00:00` | `2026-04-17T19:15:00+00:00` |
| `funding` | `2020-09-01T00:00:00+00:00` | `2026-04-17T08:00:00.011000+00:00` |
| `open_interest` | `2020-09-01T00:00:00+00:00` | `2026-04-17T14:00:00+00:00` |
| `aggtrade_buckets` | `2020-09-01T00:00:00+00:00` | `2026-04-17T14:04:00+00:00` |
| `oi_samples` | `2026-02-19T00:00:00+00:00` | `2026-04-22T19:59:53.847000+00:00` |
| `cvd_price_history` | `2026-04-21T12:30:00+00:00` | `2026-04-22T20:00:00.003233+00:00` |
| `force_orders` | `2026-04-17T14:13:16.521000+00:00` | `2026-04-22T20:01:05.699000+00:00` |
| `decision_outcomes` | `2026-04-20T10:00:00.002987+00:00` | `2026-04-22T20:00:00.003233+00:00` |
| `trade_log` | `2022-03-09T18:30:00+00:00` | `2026-04-22T19:15:05.538290+00:00` |

Important interpretation:

- Historical replay tables (`candles`, `funding`, `open_interest`,
  `aggtrade_buckets`) are rich through 2026-04-17.
- Post-2026-04-17 runtime persistence is partial:
  - `oi_samples` is current.
  - `cvd_price_history` is current.
  - `force_orders` is current.
  - `decision_outcomes` is current.
  - historical `candles`, `funding`, `open_interest`, and `aggtrade_buckets`
    are not being continuously extended by paper runtime.

This matters because replay/modeling needs reproducible historical inputs, not
only live snapshot fetches.

---

## 5. Config hash taxonomy

`trade_log` is not one homogeneous experiment. It contains multiple
config-hash populations:

| Config hash | Trades | Range | Avg pnl_r | Wins |
|---|---:|---|---:|---:|
| `037822...` | 1 | `2026-04-22` | -0.7945 | 0 |
| `5a835...` | 7 | `2026-04-20` to `2026-04-22` | 1.0069 | 4 |
| `f925...` | 1 | `2026-04-19` | -1.0000 | 0 |
| `778678...` | 557 | `2022-03-09` to `2026-03-29` | -0.2161 | 164 |
| `f807b...` | 217 | `2024-01-19` to `2025-01-01` | 0.1073 | 79 |

Current runtime hash:

```text
037822f1ddeffc1d3cf9e818c2974b59ffdf36fec8f3f352adf32df91b01b2ba
```

Current hash sample:

- `decision_outcomes`: 7 cycles
- `trade_log`: 1 trade

Conclusion: use of all `trade_log` rows as one modeling dataset would be
incorrect. Any modeling analysis must filter by `config_hash` and time period.

---

## 6. Session distribution

Recent post-2026-04-19 trade sample by session:

| Session | Trades | Wins | Losses | Win rate | Avg pnl_r |
|---|---:|---:|---:|---:|---:|
| ASIA | 1 | 0 | 1 | 0% | -0.715 |
| EU | 2 | 2 | 0 | 100% | 2.063 |
| EU_US | 4 | 1 | 3 | 25% | 0.016 |
| US | 2 | 1 | 1 | 50% | 0.890 |

This sample is too small for context-rule activation.

Session distribution across older major hashes is larger:

| Config hash | Session | Trades | Wins | Avg pnl_r |
|---|---|---:|---:|---:|
| `f807b...` | ASIA | 71 | 31 | 0.384 |
| `f807b...` | EU | 81 | 27 | -0.060 |
| `f807b...` | EU_US | 26 | 11 | 0.408 |
| `f807b...` | US | 39 | 10 | -0.251 |
| `778678...` | ASIA | 211 | 71 | -0.023 |
| `778678...` | EU | 191 | 52 | -0.360 |
| `778678...` | EU_US | 53 | 15 | -0.170 |
| `778678...` | US | 102 | 26 | -0.370 |

These older hashes may be useful for offline research, but they should not be
used as direct proof for activating current production context rules because
they represent older configurations and possibly older execution assumptions.

---

## 7. Volatility data problem

`MODELING-V1` wants volatility buckets based on:

```text
features.atr_4h_norm
```

Current persisted runtime payloads do not contain `atr_4h_norm`.

Observed keys in recent `signal_candidates.features_json` and
`trade_log.features_at_entry_json`:

```text
atr_15m
cvd_15m
force_order_rate_60s
force_order_spike
funding_pct_60d
oi_zscore_60d
sweep_depth_pct
sweep_side
tfi_60s
```

Missing:

```text
atr_4h_norm
quality
context labels
```

This means:

- We cannot reliably compute historical volatility buckets from current
  `trade_log` or `signal_candidates` payloads alone.
- We can compute volatility buckets by replaying raw candles through
  `FeatureEngine`.
- We can collect volatility buckets prospectively once `MODELING-V1`
  neutral-mode instrumentation persists context labels.

This is a data availability issue, not a reason to fetch an external
volatility data source.

---

## 8. Does replay dataset solve the data problem?

Partially.

Replay can produce the needed `Features`, including `atr_4h_norm`, if the
underlying historical inputs exist for the replay period.

For periods up to 2026-04-17:

- candles are available across `15m`, `1h`, `4h`
- funding exists
- open interest exists
- aggtrade buckets exist

Therefore a replay dataset can compute:

- session bucket
- volatility bucket
- regime
- base signal diagnostics
- candidate sequence
- context labels in neutral mode

For periods after 2026-04-17:

- runtime is fetching fresh candles and funding for live decisions
- but the historical replay tables are not fully updated with those same
  inputs
- `oi_samples` and `cvd_price_history` are current, but `candles`, `funding`,
  `open_interest`, and `aggtrade_buckets` are stale

Therefore, replay after 2026-04-17 requires either:

1. Backfilling the stale historical input tables through the relevant scripts,
   or
2. Waiting and collecting context labels prospectively in runtime.

Replay is enough to validate implementation mechanics and neutral-mode parity.
Replay is not enough by itself to justify active context gating unless the
selected replay period and config are analytically valid.

---

## 9. Does paper mode collect all data needed by the trading philosophy?

For live decision-making: mostly yes.

Paper runtime currently builds fresh snapshots with:

- current ticker price
- recent `15m`, `1h`, `4h` candles from REST
- recent funding history from REST
- current open interest from REST
- recent aggTrades from websocket or REST fallback
- force orders from websocket
- external daily bias from DB
- OI samples persisted to `oi_samples`
- CVD/price history persisted to `cvd_price_history`
- feature quality persisted to `runtime_metrics.feature_quality_json`
- decisions persisted to `decision_outcomes`
- trades persisted to `trade_log`
- executions persisted to `executions` for new realistic fills

For replay/modeling research: not fully.

Paper runtime does not currently persist every fetched snapshot ingredient back
into the historical replay tables:

- `candles` is stale after 2026-04-17.
- `funding` is stale after 2026-04-17.
- `open_interest` is stale after 2026-04-17, although `oi_samples` is current.
- `aggtrade_buckets` is stale after 2026-04-17, although
  `cvd_price_history` is current.

So paper mode is good enough to trade and diagnose live cycles, but not yet a
complete continuous replay dataset generator.

This distinction is important:

```text
runtime decision data != replay research dataset
```

The runtime path is current. The replay tables need explicit backfill/sync if
we want recent runtime periods to be replayable.

---

## 10. Feature quality assessment

Latest `runtime_metrics.feature_quality_json`:

| Quality key | Status | Meaning |
|---|---|---|
| `oi_baseline` | ready | 60+ days covered |
| `cvd_divergence` | ready | 30+ bars loaded |
| `flow_15m` | degraded | coverage high, but clipped by limit |
| `flow_60s` | degraded | coverage high, but clipped by limit |
| `funding_window` | degraded | partial funding coverage |

This is acceptable for continued paper validation and diagnostics, but not yet
strong enough to claim all modeling inputs are fully clean.

`MODELING-V1` V1 does not consume quality for gating, but quality matters for
data interpretation and for deciding whether empirical findings are trustworthy.

---

## 11. What is missing before MODELING-V1

### Required before implementation

1. `EXPERIMENT-V2` validation checkpoint must be closed or explicitly
   unblocked.
2. Current production `config_hash` should accumulate enough cycles/trades to
   be meaningful.
3. Builder handoff for `MODELING-V1` should be created from
   `docs/blueprints/BLUEPRINT_MODELING_V1.md`.

### Required before active context gating

1. Larger sample under a stable config hash.
2. Session distribution with enough trades/candidates per bucket.
3. Volatility bucket reconstruction via replay or prospective context logging.
4. Validation report:
   `docs/analysis/MODELING_V1_VALIDATION_<date>.md`
5. Dual activation criteria:
   - win-rate delta >= 10 percentage points
   - chi-square p < 0.05

### Required for recent replay after 2026-04-17

1. Backfill/sync recent `candles`.
2. Backfill/sync recent `funding`.
3. Decide whether `open_interest` historical table should also be synced from
   `oi_samples` or kept as legacy history.
4. Decide whether `aggtrade_buckets` should be backfilled from stored data or
   whether `cvd_price_history` is the new canonical source for CVD readiness.

---

## 12. Recommended data plan

### Step 1: Freeze dataset definitions

Create explicit dataset labels instead of using raw tables directly:

- `historical_replay_pre_v2`
  - source: historical candles/funding/OI/aggtrades
  - range: up to 2026-04-17
  - purpose: replay mechanics, context label simulation

- `experiment_v2_runtime_current_hash`
  - source: production runtime
  - config_hash: `037822...`
  - range: starts 2026-04-22 18:30 UTC
  - purpose: live paper validation after current config

- `experiment_v2_mixed_runtime`
  - source: production runtime after 2026-04-20
  - multiple config hashes
  - purpose: operational diagnostics only, not activation proof

### Step 2: Add prospective context observability

The cleanest way to collect modeling data is to implement `MODELING-V1` in
`neutral_mode=True` after `EXPERIMENT-V2` is unblocked. It would persist:

- `context_session_label`
- `context_volatility_label`
- `context_policy_version`
- `context_eligible=True`
- `context_neutral_mode_active=True`

This creates a clean prospective dataset without changing the edge.

### Step 3: Backfill replay tables if recent replay is required

If we want to replay recent paper runtime after 2026-04-17, run or extend the
existing backfill/sync tooling for:

- candles
- funding
- open interest / OI samples reconciliation
- aggtrade/CVD history as needed

This should be a separate data maintenance task, not hidden inside
`MODELING-V1`.

### Step 4: Do not clean or delete old data

Old rows are valuable. The issue is not that they exist. The issue is that
queries must filter by:

- time range
- `config_hash`
- source table
- experiment label

No destructive cleanup is recommended.

---

## 13. Direct answers to operator questions

### Are the data messy?

They are mixed, not corrupted.

The database contains historical backtest/replay data, old paper data, and
fresh `experiment-v2` runtime data. That is normal for this project, but
modeling queries must not treat all rows as one dataset.

### What does `config_hash` mean here?

It identifies the exact strategy/risk/execution/data-quality configuration
used for a run or cycle. Different hashes mean different behavioral conditions.

For modeling, `config_hash` is a boundary. Do not merge trade outcomes across
hashes unless the analysis explicitly says it is doing cross-config research.

### Do we need to fetch volatility?

No external volatility source is needed.

Volatility bucket should come from `Features.atr_4h_norm`, computed from 4h
candles. The problem is that `atr_4h_norm` is not currently persisted in recent
trade/signal payloads. We either compute it through replay or persist context
labels going forward.

### After replay dataset, will all needed data be ready?

For historical periods with complete inputs, yes for implementation and replay
testing.

For recent post-2026-04-17 paper runtime, not yet. The historical replay input
tables need backfill/sync, or we need to collect context labels prospectively.

### Does paper mode collect and update all data needed by the trading philosophy?

For making paper trading decisions now: yes, mostly.

For creating a complete replayable modeling dataset automatically: no.

Paper mode fetches live candles/funding/flow for decisions, but only persists a
subset of that data to long-lived replay tables. That is the gap to close if we
want recent runtime periods to be fully replayable.

---

## 14. Final recommendation

Do not implement active `MODELING-V1` yet.

Recommended next milestone order:

1. Finish/validate `EXPERIMENT-V2` under the current config hash.
2. Decide whether recent replay after 2026-04-17 is required.
3. If yes, run a focused data-sync/backfill task for replay tables.
4. Generate `MODELING-V1` builder handoff.
5. Implement `MODELING-V1` with `neutral_mode=True` only.
6. Collect prospective context labels.
7. Only after enough stable data exists, run
   `MODELING_V1_VALIDATION_<date>.md` and decide whether to activate
   whitelist gating.

The safest near-term path is:

```text
EXPERIMENT-V2 validation
  -> data-sync decision for replay completeness
  -> MODELING-V1 neutral-mode implementation
  -> prospective context-labeled dataset
  -> activation analysis
```

