# Alert Coverage Matrix
Date: 2026-04-24

| Failure Mode | Detection Surface Present? | Alert / Escalation Proven? | Notes |
|---|---|---|---|
| Bot process down | Partial | No | systemd restart policy exists; no independent crash paging evidence found |
| Dashboard process down | Partial | No | systemd restart policy exists; no independent crash paging evidence found |
| Safe mode entered | Yes | Partial | audit log + Telegram kill-switch hook exist; production delivery not independently proven |
| Health check degradation | Yes | No | `HealthMonitor` + audit logging exist; no escalation workflow proven |
| Websocket stale | Yes | No | `/api/runtime-freshness` exposes websocket age; no dedicated alert threshold proven |
| Runtime snapshot stale | Yes | No | runtime panel exposes ages; no automatic alert proven |
| Risk/DD near limits | Yes | Partial | dashboard risk panel shows warning state; no out-of-band operator escalation proven |
| Repeated no-signal cycles | Yes | No | visible in alerts/journal, but no anomaly threshold or alerting policy |
| Recovery inconsistency (unknown/phantom/orphan) | Yes | Partial | recovery sets safe mode and audit logs; manual operator guidance is stale |
| Public dashboard exposure | Yes | No | exposure was detectable immediately via public `/api/status`; no alert/control-plane protection |
