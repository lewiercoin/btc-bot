# AUDIT: Observability / Dashboard
Date: 2026-04-24
Auditor: Cascade (Builder Mode)
Commit: 2b59bb5

## Verdict: MVP_DONE

## Runtime Freshness Coverage: PASS
## Dashboard Staleness / Real-Time Fidelity: PASS
## Alert Coverage: WARN
## Anomaly Detection Capability: FAIL
## Critical Failure Mode Coverage: WARN
## Operator Safety / Exposure: FAIL

## Critical Issues (must fix before next milestone)
- The dashboard is publicly reachable and includes unauthenticated control endpoints.
  - This is primarily a security issue, but it also corrupts the observability boundary because the monitoring surface doubles as an unauthenticated control plane.

## Warnings (fix soon)
- Alert coverage is shallow relative to failure modes:
  - dashboard reads only the latest 24h of `alerts_errors`
  - no dedicated crash-alerting evidence was found
  - no anomaly scoring, threshold engine, or incident escalation workflow was found
- `scripts/query_bot_status.py` is partially out of sync with current schema/contracts:
  - `query_recent_signals()` expects `signal_candidates.promoted` and `block_reason`, which are not present in `storage/schema.sql`
  - `query_bot_state()` looks for `safe_mode_events.event_type = 'ENTRY'`, while current state store writes `entered` / `cleared`
- Frontend/server observability is strong for runtime freshness, but not for control-plane safety.

## Observations (non-blocking)
- Runtime freshness implementation is solid and materially improves operator truth:
  - `runtime_metrics` table separates runtime truth from stale SQLite collector truth
  - `/api/runtime-freshness` exposes decision-cycle timestamps, snapshot age, and websocket age
  - dashboard refresh cadence is appropriate for runtime visibility:
    - status: 5s
    - positions / egress / risk / runtime freshness: 10s
    - alerts / signals: 60s
    - metrics: 120s
- The dashboard exposes useful high-value views:
  - bot status
  - positions
  - trades
  - signals
  - alerts
  - risk panel
  - egress panel
  - runtime freshness panel
  - server resources
- Current public `/api/status` output confirms live runtime state and therefore proves the dashboard is reading current production data, not stale local workspace data.
- Existing observability milestone docs support that runtime-vs-DB separation was intentionally designed and previously audited as correct.

## Recommended Next Step
Keep the runtime freshness architecture, but separate observability from control by removing public unauthenticated dashboard access and then add explicit crash/anomaly alerting for service down, stale websocket, and repeated safe-mode entries.
