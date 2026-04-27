# Dashboard Gap Analysis
Date: 2026-04-24

## Strengths
- Runtime freshness separated from stale DB collector truth
- High-value operational panels exist: status, positions, trades, signals, alerts, risk, egress, runtime, server resources
- Auto-refresh cadence is reasonable for human monitoring
- Dashboard reads live production state successfully

## Gaps
- Dashboard is both observability surface and unauthenticated control plane
- Public exposure on `0.0.0.0:8080` plus open firewall contradicts the intended SSH-tunnel-only model
- No auth on `/api/bot/start` and `/api/bot/stop`
- No anomaly detection layer for repetitive `no_signal`, repeated safe-mode entries, or stale websocket degradation
- Alerts view is shallow and recent-only; no incident history / acknowledgement workflow
- `scripts/query_bot_status.py` is partially out of sync with current schema, which weakens trust in some auxiliary operator workflows

## Net Assessment
The runtime observability architecture is materially useful and much better than the earlier stale-DB model, but it is not production-hardened because visibility is mixed with publicly reachable process control and weak escalation coverage.
