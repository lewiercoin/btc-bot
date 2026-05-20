# Multi-Asset Shadow Sidecar Design V1

**Milestone:** `MULTI_ASSET_SHADOW_SIDECAR_DESIGN_V1`  
**Status:** `READY_FOR_AUDIT_DESIGN_ONLY`  
**Scope:** Design only. No implementation, deployment, PAPER orders, LIVE orders,
runtime integration, or production service change.  
**Decision date:** 2026-05-20  
**Primary objective:** Allow early forward observation for BTC/ETH/SOL without
changing what BTC M4 measures.

## Executive Decision

The user wants to start multi-asset shadow observation before the BTC M4
checkpoint finishes. This is acceptable only if the shadow process is a
strictly isolated sidecar and not a change to the active BTC PAPER runtime.

The safe model is:

```text
btc-bot.service
  -> current BTC PAPER bot
  -> writes only to storage/btc_bot.db
  -> remains the only source for BTC M4

multi-asset-shadow.service
  -> future sidecar observer
  -> writes only to research_lab/shadow/multi_asset_shadow.db
  -> places zero orders
  -> cannot alter BTC PAPER state, config, locks, or database rows
```

This document does not approve sidecar implementation or deployment. It defines
the isolation contract that a future implementation milestone must satisfy.

## Non-Goals

This milestone explicitly does not:

- implement the sidecar;
- create or enable a systemd service;
- start ETH or SOL shadow collection;
- place PAPER or LIVE orders for any symbol;
- modify `core/**`, `execution/**`, `orchestrator.py`, `main.py`,
  `settings.py`, `storage/**`, production database schema, or BTC PAPER config;
- restart `btc-bot.service`;
- change BTC trial-00095 parameters;
- change `min_sweep_depth_pct`;
- change BTC M4 reporting, queries, parser behavior, or checkpoint rules;
- approve ETH or SOL PAPER;
- approve multi-asset runtime integration.

## Why A Sidecar Instead Of Runtime Integration

Runtime integration before M4 would contaminate the active experiment because
M4 is measuring the current BTC PAPER bot under a frozen trial-00095 config.

A sidecar can collect forward evidence without contamination because it:

- runs as a separate process;
- has a separate lock;
- has a separate database;
- has separate logs;
- has no execution engine;
- has no write path to `storage/btc_bot.db`;
- has no ability to alter BTC decisions, positions, risk state, or M4 rows.

The sidecar is therefore an observer, not a trader.

## Hard Isolation Contract

The future sidecar implementation must satisfy all of these boundaries.

| Boundary | Requirement |
|---|---|
| Process | Sidecar runs outside `btc-bot.service` under a distinct service/process name. |
| Lock | Sidecar uses its own lock path, not `/tmp/btc-bot-runtime.lock`. |
| Storage | Sidecar writes only under `research_lab/shadow/`. |
| Production DB | Sidecar may not open `storage/btc_bot.db` in write mode. |
| Orders | Sidecar has no order placement API and no execution engine dependency. |
| BTC runtime | Sidecar may not restart, signal, or mutate `btc-bot.service`. |
| Config | Sidecar may not mutate BTC PAPER config or active environment. |
| M4 | BTC M4 remains sourced only from the current BTC PAPER runtime DB rows. |
| Metrics | Shadow metrics are symbol-explicit and never aggregated into BTC M4 conclusions. |
| Resources | Sidecar has CPU, memory, and disk guards. |

Any violation of these boundaries is a release blocker.

## Service Shape

Future deployment should use a separate unit similar to:

```text
multi-asset-shadow.service
```

Required service properties:

- starts after network is online;
- does not require `btc-bot.service` restart;
- runs at lower priority with `nice` and `ionice`;
- has an explicit memory cap, recommended `MemoryMax=512M`;
- has an explicit CPU cap, recommended `CPUQuota=50%`;
- writes logs under a distinct unit name;
- uses `Restart=on-failure` only after implementation audit proves recovery is
  idempotent;
- fails closed if disk free space is below 12 GB.

The sidecar must not be enabled until a separate implementation audit passes.

## Storage Contract

Default sidecar database:

```text
research_lab/shadow/multi_asset_shadow.db
```

Required rules:

- create parent directories explicitly;
- reject paths outside `research_lab/shadow/`;
- write shadow rows only to the sidecar database;
- never attach or mutate `storage/btc_bot.db`;
- record `shadow_run_id`, `service_start_time_utc`, `git_commit`,
  `code_version`, and `config_hash` for every run;
- support safe restart without duplicating rows for the same
  `(shadow_run_id, symbol, timestamp_utc, strategy_profile)` key.

Recommended tables:

| Table | Purpose |
|---|---|
| `shadow_runs` | One row per sidecar process start. |
| `shadow_decision_outcomes` | Symbol-explicit decision cycle diagnostics. |
| `shadow_signal_candidates` | Signals that would have been generated. |
| `shadow_portfolio_decisions` | Portfolio gate approvals/vetoes in no-order mode. |
| `shadow_near_miss_diagnostics` | Sweep-depth near-miss rows with nested payload fields. |
| `shadow_resource_samples` | CPU/RAM/disk/process-health samples. |

## Symbol Scope

Initial sidecar observation may include:

| Symbol | Mode | Candidate risk | Notes |
|---|---|---:|---|
| `BTCUSDT` | `shadow_compare_only` | 0.35% | Optional mirror diagnostics only; not M4 source of truth. |
| `ETHUSDT` | `shadow_no_orders` | 0.35% | Uses audited ETH transfer evidence. |
| `SOLUSDT` | `shadow_no_orders` | 0.15% | Uses audited SOL risk-policy diagnostic. |

BTC sidecar rows must be labeled as shadow mirror rows and must not be used in
the M4 checkpoint. BTC M4 continues to use the active PAPER runtime rows only.

## Data Source Contract

The sidecar may use read-only market data access:

- public Binance futures market data;
- local research snapshots in read-only mode for warm-up or validation;
- existing feature calculation logic only if imported through a future audited
  shadow-safe adapter.

The sidecar may not:

- subscribe to or submit private order endpoints;
- read API keys required for trading;
- write to production storage;
- depend on in-memory state from the BTC PAPER process.

If live market data is unavailable or stale, the sidecar must record a
`data_stale` or `data_unavailable` outcome and skip signal simulation for that
symbol/cycle. It must not silently fill missing data.

## Diagnostic Payload Contract

Every shadow decision row must include:

- `shadow_run_id`
- `symbol`
- `timestamp_utc`
- `strategy_profile`
- `risk_policy_profile`
- `shadow_mode`
- `config_hash`
- `signal_generated`
- `signal_blocker`
- `sweep_detected`
- `reclaim_detected`
- `sweep_depth_pct`
- `min_sweep_depth_pct`
- `regime`
- `context_session`
- `confluence_score_preview`
- `candidate_direction_preview`
- `symbol_governance_shadow_decision`
- `symbol_risk_shadow_decision`
- `portfolio_shadow_decision`
- `portfolio_veto_reason`
- `candidate_risk_pct`
- `portfolio_risk_after_pct`
- `resource_guard_status`

Near-miss payloads must use the corrected nested contract:

```json
{
  "near_miss_diagnostics": {
    "symbol": "ETHUSDT",
    "sweep_depth_pct": 0.0,
    "threshold": 0.00649,
    "depth_gap_pct": 0.0,
    "depth_bucket": "near_miss_low",
    "regime": "uptrend",
    "session_hour": 0,
    "rejection_reasons": []
  }
}
```

The nested `near_miss_diagnostics.sweep_depth_pct` field is mandatory for every
shadow near-miss row.

## M4 Contamination Guard

The following statements are hard requirements:

1. M4 remains BTC-only.
2. M4 reads only rows written by the existing BTC PAPER runtime.
3. Sidecar rows are stored in a separate database and are never joined into M4
   checkpoint calculations.
4. Sidecar BTC mirror rows, if enabled, are diagnostic only and cannot replace
   production BTC M4 rows.
5. Any report that mentions M4 and sidecar results must present them as separate
   sections with separate data sources.
6. Any sidecar implementation that writes to `storage/btc_bot.db` is invalid.
7. Any sidecar implementation that restarts or changes `btc-bot.service` is
   invalid.

## Resource Guard

The implementation milestone must include resource controls:

| Guard | Requirement |
|---|---|
| Disk free | Refuse start or pause if free disk < 12 GB. |
| Memory | Recommended service cap 512 MB. |
| CPU | Recommended service cap 50% of host CPU. |
| Priority | Run with lower CPU and IO priority than BTC PAPER. |
| Raw data | Do not persist raw aggTrades; aggregate or discard. |
| API usage | Rate-limit REST calls and prefer batched/streaming data access. |
| Failure mode | Fail closed and log; do not degrade BTC PAPER. |

Current server resource checkpoint on 2026-05-20 showed enough headroom for a
light sidecar:

- 2 vCPU with near-zero load;
- 3.1 GiB memory available;
- 26 GiB disk free;
- BTC PAPER using about 0.5% CPU and 116 MB RSS.

These values are informational only. The implementation must re-check resource
guards at runtime.

## Checkpoints

### Day 0 Pre-Start Check

Required before the first sidecar process is started:

- `btc-bot.service` active;
- exactly one `main.py --mode PAPER` process;
- production config hash recorded;
- disk free >= 12 GB;
- sidecar DB path resolves under `research_lab/shadow/`;
- sidecar lock path is distinct from BTC runtime lock;
- service file reviewed and not enabled until audit approval;
- dry-run proves no order/execution import path.

Day 0 cannot approve PAPER orders.

### Day 3 Operational Check

Required checks:

- BTC PAPER process count remains one;
- BTC M4 config hash unchanged unless separately audited;
- sidecar wrote zero rows to `storage/btc_bot.db`;
- sidecar placed zero orders;
- sidecar DB has symbol-explicit rows for enabled symbols;
- near-miss rows have nested depth;
- resource samples remain within caps;
- no stale-data streak longer than four 15m cycles per symbol.

Day 3 can only approve continued shadow observation or require pause/fix.

### Day 14 Behavior Check

Required metrics:

- decision cycles per symbol;
- shadow signal count per symbol;
- portfolio-approved shadow signals per symbol;
- portfolio-vetoed shadow signals per symbol and veto reason;
- `sweep_too_shallow` count/share per symbol;
- near-miss distribution per symbol;
- same-bar BTC/ETH/SOL overlap;
- simulated risk exposure at candidate risk profiles;
- data-stale counts;
- resource guard events.

Day 14 can only approve continued shadow observation, extension, or pause.

### Day 30 Readiness Check

Required gates:

| Gate | Requirement |
|---|---|
| Runtime isolation | BTC PAPER and M4 metrics unaffected. |
| Order safety | Zero ETH/SOL/SOL-sidecar orders. |
| Storage isolation | Zero sidecar writes to production DB. |
| Payload integrity | 100% of near-miss rows have nested depth. |
| Symbol integrity | 100% of rows are symbol-explicit. |
| Resource safety | No unresolved disk, memory, CPU, or stale-data guard breach. |
| Portfolio diagnostics | Portfolio approvals/vetoes persisted with machine-readable reasons. |
| Paper block | No symbol can move to PAPER without a new milestone, audit, and user approval. |

If Day 30 passes, the next milestone may request PAPER consideration for a
specific symbol. Day 30 itself does not approve PAPER.

## Implementation Milestone Requirements

A future `MULTI_ASSET_SHADOW_SIDECAR_IMPLEMENTATION_V1` must include:

- sidecar entrypoint that is not `main.py`;
- sidecar-specific lock;
- sidecar-specific DB and schema;
- safe path guard for `research_lab/shadow/`;
- order-path import guard;
- resource guard;
- deterministic per-symbol cycle scheduler;
- symbol-explicit payload writer;
- near-miss nested payload tests;
- no-production-DB-write tests;
- no-runtime-import/execution tests;
- dry-run command for Day 0 validation;
- operator runbook.

Implementation must be audited before any server process is started.

## Audit Questions

Claude Code should verify:

1. Is this design-only and free of runtime approval?
2. Does it preserve BTC M4 as a clean BTC-only measurement?
3. Are process, lock, storage, order, and config isolation explicit enough to
   prevent sidecar contamination?
4. Are resource limits concrete and appropriate for the current server?
5. Are Day 0, Day 3, Day 14, and Day 30 gates measurable from logs/database
   queries?
6. Does the design block ETH/SOL PAPER until a separate audited milestone and
   user approval?

## Builder Verdict

`READY_FOR_AUDIT_DESIGN_ONLY`

This design supports early multi-asset forward observation through a sidecar,
but does not approve implementation, deployment, PAPER, LIVE, or any change to
the active BTC PAPER/M4 runtime.
