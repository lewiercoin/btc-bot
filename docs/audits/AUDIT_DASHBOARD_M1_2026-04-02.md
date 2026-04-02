# AUDIT: DASHBOARD-M1 — Read-Only Observability + WAL Patch
Date: 2026-04-02
Auditor: Claude Code
Commit: pre-commit (implementation delivered without git access)

## Verdict: MVP_DONE

## Layer Separation: PASS
`dashboard/` imports only `storage.db`, `storage.repositories`, and `settings`. No orchestrator, no engine, no live-path imports. Thin wrapper as specified.

## Contract Compliance: PASS
All four API contracts match handoff spec exactly: `/api/status`, `/api/positions`, `/api/trades`, `/api/logs/stream`. Field names, nullability, and `dashboard_version: "m1"` all match. `uptime_seconds: null` correct for M1.

## Determinism: PASS
`db_reader.py` has no hidden state. `DashboardReader` opens and closes a connection per call — no long-lived connection leaks. `log_streamer.py` is stateless between calls (file position tracked in local variable within generator).

## State Integrity: PASS
WAL pragma in `connect()` at [storage/db.py:13](storage/db.py#L13). `connect_readonly()` uses URI `?mode=ro` at [storage/db.py:18](storage/db.py#L18). Existing `init_db` / `transaction` untouched — no regressions.

## Error Handling: WARN
One issue: `DashboardReader` opens a new connection per call but has no protection if `connect_readonly()` raises (e.g., DB file doesn't exist yet — bot never started). Currently propagates as HTTP 500. Acceptable for M1 (local-only, operator context), but should be caught and returned as a structured `{"bot_state": null}` response before M3 when start/stop is added and the DB may not exist on first launch.

## Smoke Coverage: PASS
4 new tests, all pass. `test_dashboard_wal.py` verifies WAL pragma and read-only rejection. `test_dashboard_db_reader.py` exercises status/positions/trades against real schema on in-memory SQLite. Full suite: **46 passed** (was 35 + 7 from earlier sessions + 4 new = counts match).

## Tech Debt: LOW
- `app.js:111,131` — `innerHTML` used for table row injection from API data. API is local read-only (no user input, no external data injection path), so XSS risk is minimal. Still: should switch to DOM construction before M3 when control actions are added and error messages from the bot may contain user-visible strings.
- `log_streamer.py` keeps entire log history in client-side `logEntries` array (capped at 400). No issue for M1.

## AGENTS.md Compliance: PASS
New files in correct locations. No production code modified beyond the single WAL pragma addition.

## Boundary Coupling: PASS
Dashboard has no imports from `orchestrator`, `core/`, `execution/`, `monitoring/`, or `research_lab/`. Coupling is exactly `storage.db` + `storage.repositories` + `settings` — all read surfaces.

---

## Critical Issues (must fix before next milestone)
None blocking M1. One issue to fix before M3:

**[PRE-M3]** `DashboardReader` propagates `OperationalError` as HTTP 500 when DB doesn't exist. Before M3 adds start/stop (where DB may not exist at dashboard launch), wrap `connect_readonly()` in `db_reader.py` to return `{"bot_state": null}` when file is missing.

## Warnings (fix soon)
- `app.js` table rendering uses `innerHTML`. Safe now, revisit before M3 when bot error strings may appear in the UI.

## Observations (non-blocking)
- `server.py:20` — `load_settings(project_root=PROJECT_ROOT)` correctly passes project root so settings resolves paths relative to repo root, not CWD. Good defensive practice.
- `log_streamer.py` keepalive at 15s interval is correct for SSE proxies. `X-Accel-Buffering: no` header prevents nginx buffering — good operational detail.
- `run_dashboard.py` bind is `127.0.0.1` only. Confirmed.
- `data_age_seconds` in positions payload computed from `max(opened_at)`, not from `state_timestamp`. Correct — shows how stale the position data is relative to DB writes, not to bot heartbeat.

## Recommended Next Step
**Commit M2 + M1 as two separate commits**, then proceed to **M3: Managed Start/Stop**.

M3 scope reminder:
- `CREATE_NEW_PROCESS_GROUP` at subprocess launch (Windows: `CREATE_NEW_PROCESS_GROUP` flag)
- `os.kill(pid, signal.CTRL_C_EVENT)` for graceful stop
- Hard timeout (e.g. 10s) → `process.terminate()` fallback with audit log
- Single-instance guard (PID file or in-memory state)
- `uptime_seconds` computed from process launch timestamp
- Fix the `connect_readonly()` OperationalError guard in `db_reader.py` as part of M3 scope
