# Observability Runtime vs DB Plan

Date: 2026-04-18

Status: PLAN_READY_FOR_APPROVAL

Scope: One milestone, three independently deployable components:

1. Dashboard Runtime Freshness Metrics
2. Decision Diagnostics Logging
3. Candles Collector Service

## Problem Statement

The current dashboard mixes two different truths:

- Runtime decision data, which is built directly from REST snapshots and websocket buffers in `data/market_data.py:73-113`
- SQLite historical candles, which are refreshed by separate operator workflows and are not on the live decision path

This caused a false alarm during production diagnosis: stale SQLite candles looked like a dead websocket even though the live bot remained healthy and continued decision cycles. That mismatch is already contradicted by the existing strategy diagnosis, which explicitly states that market data was fresh and the runtime was healthy in the analyzed `no_signal` window (`docs/analysis/STRATEGY_ASSESSMENT_2026-04-17.md:129-130,160,169`).

## Architecture Decision

Decision: separate runtime observability from collector observability.

Why:

- Runtime freshness answers: "Can the bot make a live decision right now?"
- Collector freshness answers: "Is the offline/dashboard SQLite cache being maintained?"
- These are different failure domains and must not share a single green/red indicator.

How this prevents false alarms:

- A stale collector will no longer imply runtime starvation.
- A healthy collector will no longer mask runtime issues such as stale websocket state.
- Operators will see two panels with different ownership:
  - `Runtime Data` = trading path critical
  - `DB Collector` = informational / support path

Persistence choice:

- Use a new single-row `runtime_metrics` table instead of extending `bot_state`.
- `bot_state` already carries operational governance/risk state and is written via `storage/repositories.py:57` and exposed through `dashboard/db_reader.py:75-101`.
- Freshness metrics are higher-churn observability data and should not overload the risk/state contract defined around `bot_state` in `storage/schema.sql:136`.

## Current Hook Points

These are the concrete attachment points for the milestone:

- Runtime cycle start/finish and `no_signal` handling: `orchestrator.py:325-461`
- Runtime event loop and health scheduling: `orchestrator.py:482-523`
- Snapshot construction entry point: `orchestrator.py:596-599`
- Data-feed startup: `orchestrator.py:661`
- REST snapshot assembly: `data/market_data.py:73-79`
- Agg-trade REST fallback: `data/market_data.py:113`
- Websocket heartbeat source: `data/websocket_client.py:61,87-88,152`
- Current websocket health check: `monitoring/health.py:22,36-41,47-52,55,75`
- Current dashboard API surface: `dashboard/server.py:129,149,183,189,194,216,262,345`
- Current dashboard DB reader surface: `dashboard/db_reader.py:75,130,170,281,303,335,352`
- Current dashboard frontend entry points: `dashboard/static/app.js:314,454,558,591,607,615,645`
- Current signal gating logic: `core/signal_engine.py:44,48,61,112,194-195`
- Current feature-level sweep/reclaim computation: `core/feature_engine.py:108,184,217-218`
- Existing operator-side historical refresh workflow: `scripts/server/refresh_all_data.sh:68,75`

## Component 1: Dashboard Runtime Freshness

Effort: Medium

### Goal

Expose the freshness of the data actually used by the live decision loop, not the freshness of the SQLite candle cache.

### Proposed Data Model

Create a new SQLite table `runtime_metrics` with a single active row keyed by `id = 1`.

Recommended fields:

- `id`
- `updated_at`
- `last_decision_cycle_started_at`
- `last_decision_cycle_finished_at`
- `last_decision_outcome`
- `decision_cycle_status`
- `last_snapshot_built_at`
- `last_snapshot_symbol`
- `last_15m_candle_open_at`
- `last_1h_candle_open_at`
- `last_4h_candle_open_at`
- `last_ws_message_at`
- `last_health_check_at`
- `last_runtime_warning`
- `config_hash`

Rationale:

- The dashboard is a separate process and cannot safely introspect in-memory bot state from `MarketDataAssembler` or `websocket_client`.
- Persisting one summarized row per cycle keeps write volume low and avoids a DB write on every websocket message.
- `last_ws_message_at` should be copied from `websocket_client.last_message_at` during decision cycles and health checks, not updated directly by the websocket thread.

### Write Path

Bot-side write responsibility:

- At decision-cycle start in `orchestrator.py:329`, persist:
  - `last_decision_cycle_started_at`
  - `decision_cycle_status=running`
- After `_build_snapshot()` returns in `orchestrator.py:333` and `orchestrator.py:596-599`, persist:
  - `last_snapshot_built_at`
  - latest open times from `snapshot.candles_15m`, `snapshot.candles_1h`, `snapshot.candles_4h`
  - `last_ws_message_at` copied from `websocket_client.last_message_at`
- At decision-cycle finish in `orchestrator.py:461`, persist:
  - `last_decision_cycle_finished_at`
  - `last_decision_outcome`
  - `decision_cycle_status=idle`
- During `_run_health_check()` in `orchestrator.py:523` and `monitoring/health.py:41-52`, refresh:
  - `last_health_check_at`
  - `last_ws_message_at`
  - `last_runtime_warning` when health degrades without entering safe mode yet

### API Contract

Preferred endpoint: `GET /api/runtime-freshness`

Reason:

- Keeps `/api/status` backward-compatible.
- Avoids mixing legacy M1/M3 status payload with new observability payload.
- Lets the frontend load runtime observability independently of older dashboard surfaces.

Response shape:

```json
{
  "runtime_available": true,
  "process": {
    "running": true,
    "pid": 238905,
    "uptime_seconds": 14321
  },
  "decision_cycle": {
    "status": "idle",
    "last_started_at": "2026-04-18T10:15:00+00:00",
    "last_finished_at": "2026-04-18T10:15:01+00:00",
    "last_outcome": "no_signal",
    "last_snapshot_age_seconds": 2.1
  },
  "rest_snapshot": {
    "built_at": "2026-04-18T10:15:00+00:00",
    "symbol": "BTCUSDT",
    "timeframes": {
      "15m": { "last_candle_open_at": "2026-04-18T10:15:00+00:00", "age_seconds": 0 },
      "1h": { "last_candle_open_at": "2026-04-18T10:00:00+00:00", "age_seconds": 900 },
      "4h": { "last_candle_open_at": "2026-04-18T08:00:00+00:00", "age_seconds": 8100 }
    }
  },
  "websocket": {
    "last_message_at": "2026-04-18T10:14:58+00:00",
    "message_age_seconds": 2,
    "healthy": true
  },
  "collector": null
}
```

Reader integration:

- Add a dedicated reader path in `dashboard/db_reader.py` next to the existing `read_status_from_conn`, `read_trades_from_conn`, and `read_signals_from_conn` functions at `:75`, `:130`, and `:170`.
- Do not overload `read_status_from_conn`; add a separate read function and method on `DashboardReader` near `dashboard/db_reader.py:281-352`.

Server integration:

- Add the endpoint beside existing observability routes in `dashboard/server.py:189-262`.
- Keep `/api/status` unchanged at `dashboard/server.py:129`.

### Frontend Mockup

Add a dedicated `Runtime Data` panel near current status/risk cards rendered from `dashboard/static/app.js:314,558,615`.

Panel content:

- `Runtime: OK / Warning / Stale`
- `Decision cycle: idle / running / blocked`
- `Last outcome: no_signal / signal_generated / snapshot_failed / health_blocked`
- `Snapshot built: 12s ago`
- `15m candle: 0s old`
- `1h candle: 12m old`
- `4h candle: 2h 12m old`
- `Websocket last message: 2s ago`

Panel rules:

- Red only when runtime data is stale or process is down.
- Yellow when websocket heartbeat is degraded but process is still running.
- No dependency on the SQLite `candles` table.

### Backward Compatibility

- Old dashboards continue to work because `/api/status` is unchanged.
- New dashboard should treat missing `runtime_metrics` table as `runtime_available=false`, not as HTTP 500.
- Migration order should allow bot deploy first or dashboard deploy first.

## Component 2: Decision Diagnostics

Effort: Small to Medium

### Goal

When `outcome=no_signal`, show exactly why the candidate was rejected without changing the deterministic decision path.

### Current Constraint

Today the runtime logs start and finish of the cycle in `orchestrator.py:329` and `:461`, but the rejection reason collapses to a generic `No signal candidate.` at `orchestrator.py:379`.

At the same time, the actual gating logic is explicit and deterministic:

- `sweep_detected` gate at `core/signal_engine.py:49`
- `reclaim_detected` gate at `core/signal_engine.py:51`
- direction/regime whitelist gate at `core/signal_engine.py:61` and `:194-195`
- feature computation source for sweep/reclaim at `core/feature_engine.py:108,184,217-218`

### Recommended Design

Introduce a diagnostic object owned by the signal layer and emitted by the orchestrator.

Why this shape:

- The orchestrator owns logging.
- The signal layer owns rejection semantics.
- This avoids duplicating signal rules inside the orchestrator.

Recommended internal contract:

- `SignalEngine` exposes a read-only diagnostic method or trace object that mirrors the same gate order as `generate()`.
- The diagnostic object is built from already-computed `features` and `regime`.
- The core execution result remains unchanged: diagnostics must never affect candidate generation.

### Required Log Format

Emit one structured summary line per cycle when `candidate is None`.

Preferred format:

```text
Decision diagnostics | timestamp=2026-04-18T10:15:00+00:00 | outcome=no_signal | blocked_by=reclaim_missing | sweep_detected=true | reclaim_detected=false | sweep_side=high | sweep_depth_pct=0.31 | direction_inferred=LONG | regime=UPTREND | direction_allowed=false | confluence_preview=2.35
```

Required fields:

- `timestamp`
- `outcome`
- `blocked_by`
- `sweep_detected`
- `reclaim_detected`
- `sweep_side`
- `sweep_depth_pct`
- `direction_inferred`
- `regime`
- `direction_allowed`

Optional but useful:

- `sweep_level`
- `confluence_preview`
- `candidate_reasons_preview`
- `config_hash`

Recommended `blocked_by` vocabulary:

- `no_sweep`
- `no_reclaim`
- `sweep_too_shallow`
- `direction_unresolved`
- `regime_direction_whitelist`
- `confluence_below_min`

### Optional Persistence

Optional table: `decision_diagnostics`

Suggested fields:

- `id`
- `timestamp`
- `outcome`
- `blocked_by`
- `sweep_detected`
- `reclaim_detected`
- `sweep_side`
- `sweep_depth_pct`
- `direction_inferred`
- `regime`
- `direction_allowed`
- `config_hash`

Recommendation:

- MVP for this component should be structured logs first.
- The table should be added only if the dashboard needs a trend view of rejection reasons.

### Dashboard Integration

If persistence is added, expose:

- `GET /api/decision-diagnostics?limit=100`

Frontend usage:

- A compact trend widget under runtime data:
  - `Last 20 no-signal reasons`
  - `no_reclaim: 13`
  - `regime_direction_whitelist: 7`

This directly supports the current strategy diagnosis rather than replacing it. The operator should still be able to validate that `no_signal` is expected when the market lacks reclaim or when regime policy forbids entries, as already documented in `docs/analysis/STRATEGY_ASSESSMENT_2026-04-17.md:55,68-69,134,163`.

## Component 3: Candles Collector Service

Effort: Medium

### Goal

Refresh SQLite candles automatically outside the critical trading path so that dashboard and research views stay useful without implying runtime health.

### Service Design

Add a dedicated systemd timer pair:

- `btc-bot-candles-collector.service`
- `btc-bot-candles-collector.timer`

Cadence:

- Hourly is the default.
- `Persistent=true` on the timer so missed runs recover after reboot.

Execution model:

- Run a dedicated collector command that refreshes only dashboard-support data.
- Keep runtime trading loop unchanged.
- Reuse the existing historical refresh pattern rather than bolting writes into the live orchestrator.

Recommended invocation:

- `python scripts/refresh_candles.py --symbol BTCUSDT --timeframes 15m 1h 4h`

The existing server-side refresh flow already treats historical sync as a separate operator path in `scripts/server/refresh_all_data.sh:68,75`. This component formalizes that path as a scheduled service.

### Collector State

Add a separate single-row table `collector_state` or append-only `collector_runs`.

Recommended fields:

- `collector_name`
- `last_started_at`
- `last_finished_at`
- `last_success_at`
- `last_status`
- `last_error`
- `timeframes`
- `symbol`
- `updated_at`

Recommendation:

- Prefer `collector_state` for simple dashboard health.
- Add `collector_runs` only if operators want history and failure trend analysis.

### Logging Strategy

Collector logs go to `/var/log/btc-bot-collector.log`.

Requirements:

- Separate log file from the bot runtime log
- UTC timestamps
- one line per run start
- one line per run finish
- explicit error line with command and exception summary on failure

Rotation:

- Add logrotate policy
- keep size-bounded history
- do not rely on the bot service log for collector observability

### Dashboard Health Integration

Extend `GET /api/runtime-freshness` to include a `collector` block once this component lands:

```json
{
  "collector": {
    "configured": true,
    "last_success_at": "2026-04-18T09:00:03+00:00",
    "last_run_age_minutes": 45,
    "last_status": "success",
    "warning": null
  }
}
```

Frontend panel:

- `DB Collector: OK / Warning / Failed`
- `Last success: 45 min ago`
- `Scope: 15m, 1h, 4h`
- `Failure does not affect live runtime`

Failure semantics:

- Collector failure must never activate bot safe mode.
- Dashboard should show: `DB data stale, runtime OK` when runtime metrics are healthy and collector is not.

## Implementation Order

Recommended order:

1. Decision Diagnostics
2. Dashboard Runtime Freshness
3. Candles Collector Service

Reasoning:

- Diagnostics is the smallest, safest win and immediately reduces wasted strategy debugging time.
- Runtime freshness then fixes the core false-alarm path at the dashboard level.
- Collector service is useful, but it should be added only after runtime truth is already clearly separated from DB truth.

Dependencies:

- Component 2 has no hard dependency on Components 1 or 3.
- Component 1 depends on a persistence decision for `runtime_metrics`.
- Component 3 is operationally independent, but its dashboard panel should reuse the same observability surface introduced in Component 1.

## Rollout Strategy

### Component 2

- Deploy bot code with new diagnostics logging.
- Restart bot once during a controlled window.
- No dashboard deploy required if logs are the only output.

Rollback:

- Revert bot code only.
- No schema rollback if persistence is not added.

### Component 1

- Deploy schema migration first.
- Deploy bot writer second.
- Deploy dashboard reader/frontend third.

Compatibility rules:

- New dashboard must tolerate missing `runtime_metrics`.
- New bot must tolerate an older dashboard.

Rollback:

- Dashboard can roll back independently.
- Bot can stop writing the table without breaking current status/trades/signals endpoints.
- Keep table in schema; do not try to drop it during rollback.

### Component 3

- Deploy service and timer independently of the bot runtime.
- Start timer without restarting `btc-bot.service`.
- Dashboard collector panel can ship before or after the timer; if before, it should render `configured=false`.

Rollback:

- Stop and disable the timer.
- Leave collector tables in place.
- Runtime trading remains unaffected.

## Testing Strategy

### Component 2: Decision Diagnostics

Smoke tests:

- Run a deterministic orchestrator cycle that produces `no_signal`.
- Assert the log contains `blocked_by=...` and the expected sweep/reclaim/regime fields.
- Run a deterministic cycle that produces a candidate and assert no rejection diagnostic is emitted.

Determinism checks:

- Existing decision outputs must not change for the same fixed fixtures.
- Compare pre-change and post-change `SignalCandidate` outputs for representative markets.

### Component 1: Runtime Freshness

Smoke tests:

- Run one decision cycle and confirm `runtime_metrics` row is created.
- Confirm endpoint returns:
  - last decision timestamps
  - 15m/1h/4h last candle open times
  - websocket last message timestamp
  - derived age fields

False-alarm regression test:

- Make SQLite candles stale while runtime metrics are fresh.
- Confirm the UI shows:
  - `Runtime Data: OK`
  - `DB Collector: Warning`
- This is the key proof that the original confusion cannot recur.

Failure-path test:

- Simulate stale websocket heartbeat while collector remains current.
- Confirm the UI shows runtime degradation even though DB cache is fresh.

### Component 3: Collector Service

Smoke tests:

- Trigger the collector service manually once.
- Confirm `collector_state` is updated.
- Confirm the log file contains start and finish entries.
- Confirm dashboard panel shows collector freshness without changing runtime status.

Operational tests:

- Stop the timer and let collector age exceed threshold.
- Confirm dashboard shows `DB data stale, runtime OK`.
- Re-enable timer and confirm warning clears on the next successful run.

## Acceptance Criteria

The milestone should be considered implementation-ready only if all of the following are true:

- Runtime and DB collector health are displayed separately.
- A stale SQLite candle cache cannot be misread as a dead websocket.
- `no_signal` cycles expose rejection reason(s) without changing decision behavior.
- Collector failures remain outside the trading critical path.
- Dashboard remains backward-compatible during staggered deploys.

## Recommended Next Implementation Milestone

Single milestone is acceptable, but execution should still be split into three audited checkpoints:

1. `Decision Diagnostics Logging`
2. `Runtime Freshness Endpoint + Panel`
3. `Candles Collector Service + Collector Health`

This keeps the rollback surface small while still treating the work as one coherent observability fix.
