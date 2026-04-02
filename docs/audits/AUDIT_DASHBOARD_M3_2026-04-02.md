# AUDIT: DASHBOARD-M3 — Managed Start/Stop
Date: 2026-04-02
Auditor: Claude Code
Commit: pre-commit (implementation delivered without git access)

## Verdict: MVP_DONE

## Layer Separation: PASS
`dashboard/process_manager.py` imports only stdlib (`subprocess`, `os`, `signal`, `threading`, `json`). No bot internals. `server.py` wires `ProcessManager` in lifespan — no direct orchestrator dependency. Layer boundary clean.

## Contract Compliance: PASS
All API contracts match handoff spec:
- `POST /api/bot/start` — idempotent, returns `started: false` when already running
- `POST /api/bot/stop` — idempotent, returns `stopped: false` when not running
- `GET /api/status` — `uptime_seconds`, `process` block (`running`, `pid`, `mode`, `exit_code`) all present. `dashboard_version: "m3"` correct.
- M1 carry-overs: `db_reader.py` returns safe fallbacks, `app.js` zero `innerHTML` confirmed.

## Determinism: PASS
`ProcessManager` state is guarded by `threading.Lock` throughout. `_status_locked()` called inside lock in both `start()` and `stop()` — no TOCTOU on zombie detection. `_clear_locked()` only called under lock.

## State Integrity: PASS
Zombie detection: `_status_locked()` calls `process.poll()` before reading state, auto-clears on exit. Confirmed in `test_status_reports_uptime_and_clears_exited_process`.

Operator audit log (`dashboard_operator.jsonl`) appended atomically per-event with `sort_keys=True`. Parent dir created if missing. Graceful path: `start` + `stop` events. Hard path: `start` + `stop_hard` + `stop` events — order verified in test.

## Error Handling: PASS
`_is_missing_db_error(exc)` checks `"unable to open" in str(exc).lower()` — catches SQLite URI `mode=ro` file-not-found correctly, re-raises all other `OperationalError`. All three `DashboardReader` methods protected.

`stop()` handles `OSError` from `os.kill()` — if process already dead, swallowed; if alive, re-raised. Correct.

`process.terminate()` after `TimeoutExpired` has a second `wait(timeout=5)` with `TimeoutExpired` swallowed — prevents indefinite block on hard-killed process.

## Smoke Coverage: PASS
7 new tests, all pass. Test coverage: start/launch, already-running idempotency, graceful stop, hard fallback, stop-when-idle, zombie auto-clear + uptime, invalid mode.
Full suite: **53/53 passed**.

## Tech Debt: LOW
One minor issue worth tracking:

**`stop()` race: `CTRL_C_EVENT` to already-dead process.** If the process dies between `_status_locked()` check and `os.kill()`, the `OSError` is caught only when `process.poll() is None` returns False. If `poll()` returns non-None (process dead), the `OSError` is swallowed — correct. If `poll()` returns `None` but OS says process dead — unlikely but theoretically possible on Windows. Not blocking for M3; acceptable for local operator use.

**`app.js:311-325` double `refreshStatus()` call.** `handleStart()` calls `refreshStatus()` inside the `try` block AND in `finally`. This means two status polls on success (harmless) and one on error. Not a bug — just redundant. Non-blocking.

## AGENTS.md Compliance: PASS
New files only in `dashboard/` and `tests/`. No changes to bot logic, orchestrator, or settings.

## Boundary Coupling: PASS
`process_manager.py` has no imports from bot internals. Subprocess is launched as an external OS process — clean boundary. `ProcessManager` is unaware of DB or settings.

---

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
- `getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)` at [process_manager.py:54](dashboard/process_manager.py#L54) — defensive fallback for non-Windows. Correct.
- `setControlEnabled(false)` called on page init at [app.js:363](dashboard/static/app.js#L363) — buttons disabled until first `/api/status` poll resolves. Correct UX default.
- `controlBusy` flag at [app.js:32](dashboard/static/app.js#L32) prevents double-click during async POST. Correct.
- LIVE confirmation dialog at [app.js:305](dashboard/static/app.js#L305) — `window.confirm()` before POST. Satisfies handoff requirement.
- `botModeSelect` disabled while process running — prevents mode change confusion during live session. Good.

---

## Recommended Next Step
M1 + M3 changes are uncommitted. **Commit both** (two separate commits: M1 files, then M3 files) before starting M4.

Next milestone options (user decides):
- **DASHBOARD-M4** — Job runner for backtest/research (asyncio job queue, `job_id`, history, concurrency limit)
- Hold at M3 and use dashboard in production first
