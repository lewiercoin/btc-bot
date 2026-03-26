# AUDIT: Phase F — Orchestration

**Date:** 2026-03-26
**Auditor:** Cascade
**Commit:** 09a099f
**Scope:** Blueprint §10.1-10.3, §11 — `orchestrator.py`, `main.py`, `scripts/run_paper.py`, `scripts/smoke_orchestrator.py`, `settings.py`, `data/websocket_client.py`, `monitoring/health.py`, `scripts/smoke_monitoring.py`

## Verdict: MVP_DONE

---

## 1. Deliverable Checklist

| # | Deliverable | Status | Notes |
|---|---|---|---|
| 1 | Event loop with 15m decision cycle | ✅ DONE | `_run_event_loop` with `_next_decision_at` aligned to 15m boundaries |
| 2 | Position monitoring between cycles | ✅ DONE | `_run_position_monitor_cycle` at `position_monitor_interval_seconds` |
| 3 | Health check integration | ✅ DONE | `_run_health_check` with consecutive failure threshold → safe_mode |
| 4 | Telegram integration | ✅ DONE | Alerts on entry, exit, kill-switch, critical errors, daily summary |
| 5 | Kill-switch guards (§11) | ✅ DONE | daily DD, weekly DD, consecutive losses, critical exec errors |
| 6 | Safe mode continues lifecycle (issue #6) | ✅ DONE | `run_decision_cycle` processes lifecycle before checking safe_mode |
| 7 | Graceful shutdown | ✅ DONE | Signal handlers + `_shutdown()` stops feeds, flushes state |
| 8 | `main.py` hardening | ✅ DONE | CLI args, logging (file + console), signal handlers |
| 9 | `run_paper.py` update | ✅ DONE | Banner, graceful Ctrl+C handling |
| 10 | Daily summary (§10.2) | ✅ DONE | `_handle_daily_rollover` triggers `send_daily_summary` at UTC midnight |
| 11 | Smoke tests | ✅ DONE | 4 scenarios: event loop, safe mode lifecycle, kill-switch, daily summary |
| 12 | Issue #11 fix (private attribute) | ✅ DONE | `is_connected` property added to `BinanceFuturesWebsocketClient` |

## 2. Layer Separation: PASS

- `orchestrator.py` is the integration layer — imports from all layers are architecturally correct
- New imports: `HealthMonitor`, `TelegramNotifier`, `TelegramConfig`, `get_daily_metrics` — all appropriate for the orchestration layer
- No new cross-layer leaks introduced
- `health.py` now uses public `is_connected` property instead of `_thread` — **issue #11 resolved** ✅

## 3. Event Loop Design: PASS

**Schedule-based approach:**
- `_initialize_runtime_schedule(now)` sets initial deadlines for decision, monitor, health
- `_run_event_loop` polls deadlines in a `while not _stop_event.is_set()` loop
- `_compute_sleep_seconds` picks the minimum of next deadline deltas, clamped to `loop_idle_sleep_seconds` (default 0.5s) with floor at 0.05s

**15m boundary logic:**
- `_next_15m_boundary(now)` correctly computes next :00/:15/:30/:45 boundary
- `_advance_decision_deadline(current, now)` advances by 15m increments until past `now` — handles missed cycles correctly ✅
- `_is_15m_boundary` is strict (second=0, microsecond=0) — startup at exact boundary gets immediate cycle ✅

**DI for testability:**
- `now_provider` and `sleep_fn` injected via constructor — enables deterministic `FakeClock` in smoke tests ✅
- `health_monitor` and `telegram_notifier` injectable — enables fakes in tests ✅

## 4. Kill-Switch Implementation: PASS

`_evaluate_kill_switch(now)` checks 4 conditions per blueprint §11:

1. `daily_dd_pct > daily_dd_limit` ✅
2. `weekly_dd_pct > weekly_dd_limit` ✅
3. `consecutive_losses > max_consecutive_losses` ✅
4. `_critical_execution_errors > kill_switch_max_exec_errors` ✅

**Observations:**
- Uses `>` (strict greater than) — consistent with existing governance/risk thresholds
- `_activate_safe_mode` is idempotent — checks `current.safe_mode` before activating ✅
- Kill-switch sends Telegram alert with full payload (reason, DD%, positions, losses) ✅
- Called in `finally` block of `run_decision_cycle` AND in event loop body — double-check is safe but slightly redundant

**WARN:** `_evaluate_kill_switch` is called twice per decision cycle — once in the `finally` block of `run_decision_cycle` (line 381), and once in `_run_event_loop` (line 415). The idempotency guard in `_activate_safe_mode` prevents double-activation, but `refresh_runtime_state` is called an extra time unnecessarily. Low impact but worth noting for performance awareness.

## 5. Safe Mode Lifecycle (Issue #6 Fix): PASS

**Before (Phase E):** `start()` returned immediately on `recovery_report.safe_mode` — no lifecycle monitoring, no event loop.

**After (Phase F):**
- `start()` no longer returns on safe mode — it logs a warning and proceeds to `_run_event_loop` ✅
- `run_decision_cycle` processes trade lifecycle BEFORE checking safe_mode (lines 270-285) ✅
- Safe mode only blocks new trade decisions (lines 287-294), not lifecycle management ✅
- `_run_position_monitor_cycle` runs regardless of safe_mode status ✅
- Smoke test `run_safe_mode_lifecycle_smoke` verifies: trade closes, no new executions, no signal generation ✅

**Issue #6 is RESOLVED.**

## 6. Health Check Integration: PASS

- `_run_health_check` runs at `health_check_interval_seconds` (default 30s)
- `_consecutive_health_failures` tracks sequential failures
- After `health_failures_before_safe_mode` (default 3) consecutive failures → `_activate_safe_mode` ✅
- Resets counter on healthy check ✅
- Payload includes all probe results + failure count ✅

## 7. Telegram Integration: PASS

All 5 alert types wired:
- `ALERT_ENTRY` — on successful trade open (line 371) ✅
- `ALERT_EXIT` — on each trade close via `_notify_closed_trades` (line 494) ✅
- `ALERT_KILL_SWITCH` — on safe mode activation (line 490) ✅
- `ALERT_CRITICAL_ERROR` — on snapshot/lifecycle/execution failures (lines 267, 284, 377) ✅
- `ALERT_DAILY_SUMMARY` — on daily rollover (line 396) ✅

**Error isolation:** `_send_telegram_alert` wraps `send_alert` in `try/except` — telegram failure never crashes the bot ✅

## 8. Daily Summary: PASS

- `_handle_daily_rollover(now)` detects UTC day boundary change
- Calls `send_daily_summary(summary_day)` for the completed day
- `send_daily_summary` calls `state_store.sync_daily_metrics` then `get_daily_metrics` to fetch computed stats
- Sends via Telegram and logs to audit trail ✅
- Handles missing metrics gracefully (defaults to 0) ✅

## 9. Graceful Shutdown: PASS

- `threading.Event` for `_stop_event` — thread-safe stop signaling ✅
- `stop(reason)` sets event, logs reason, idempotent ✅
- `install_signal_handlers` captures `SIGINT` + `SIGTERM` (with Windows compatibility check) ✅
- `_shutdown()` stops data feeds, refreshes state, logs final metrics snapshot ✅
- `main()` catches `KeyboardInterrupt` as backup, closes DB connection in `finally` ✅

## 10. `main.py` Hardening: PASS

- `argparse` for `--mode` and `--log-level` CLI args ✅
- `configure_logging`: `RotatingFileHandler` (5MB, 5 backups) + `StreamHandler`, both with timestamped formatter ✅
- Root logger handlers cleared before setup — prevents duplicate handlers on restart ✅
- Startup banner log with mode, symbol, config_hash ✅

## 11. `run_paper.py` Update: PASS

- Prints startup banner (mode, symbol, config_hash) before calling `main()` ✅
- Passes `--mode PAPER` via `argv` ✅
- `KeyboardInterrupt` caught for graceful exit message ✅
- **Note:** `load_settings()` is called twice — once for banner, once inside `main()`. Minor inefficiency, non-blocking.

## 12. Settings Additions: PASS

New fields in `ExecutionConfig`:
- `health_check_interval_seconds: int = 30` ✅
- `health_failures_before_safe_mode: int = 3` ✅
- `kill_switch_max_exec_errors: int = 2` ✅
- `loop_idle_sleep_seconds: float = 0.5` ✅

All frozen dataclass defaults, no side effects. ✅

## 13. `websocket_client.py` Changes: PASS

- Added public `is_connected` property (line 90-91): `bool(self._thread and self._thread.is_alive() and not self._stop_event.is_set())` ✅
- More robust than previous `_thread.is_alive()` alone — also checks `_stop_event` ✅
- **Issue #11 RESOLVED** — `health.py` now uses `is_connected` instead of `_thread`

## 14. `smoke_monitoring.py` Changes: PASS

- `FakeWebsocketClient` updated to use `is_connected` property instead of `_thread` attribute ✅
- Backwards compatible with health.py changes ✅

## 15. Smoke Test Coverage: PASS

4 orchestrator smoke scenarios:

| Test | What it verifies |
|---|---|
| `run_event_loop_smoke` | Event loop starts, 15m cycle fires, signal generated, trade executed, WS started/stopped, Telegram ENTRY alert sent |
| `run_safe_mode_lifecycle_smoke` | Safe mode blocks new trades but closes existing position (TP hit), Telegram EXIT alert sent, zero signal generation |
| `run_kill_switch_smoke` | Seeded loss → daily DD > 3% → safe_mode activated, Telegram KILL_SWITCH alert sent |
| `run_daily_summary_smoke` | Clock crosses UTC midnight → daily summary generated, Telegram DAILY_SUMMARY alert sent |

**What's not covered (non-blocking for MVP):**
- Health check failure → safe mode (consecutive threshold)
- Multiple 15m cycles in sequence
- Execution failure → `_critical_execution_errors` increment → kill-switch
- `_advance_decision_deadline` with missed cycles
- Graceful shutdown via signal handler
- Position monitor cycle independent of decision cycle

## 16. Error Handling: PASS

- Every external call wrapped in try/except ✅
- Telegram failures isolated — never crash bot ✅
- Snapshot build failure → mark_error + return (no crash) ✅
- Lifecycle failure → mark_error + return ✅
- Execution failure → increment `_critical_execution_errors` + mark_error ✅
- Feed start failure → safe_mode + critical alert ✅
- Feed stop failure → warning only (appropriate) ✅
- Shutdown state refresh failure → silently ignored (appropriate — shutting down) ✅

## 17. Determinism: PASS

- Core pipeline (features → regime → signal → governance → risk) unchanged ✅
- Event loop timing is inherently non-deterministic but injectable via `now_provider` / `sleep_fn` ✅
- No randomness in decision path ✅

## 18. State Integrity: PASS

- `refresh_runtime_state` called at cycle start — ensures DD/losses are fresh ✅
- `_evaluate_kill_switch` also calls `refresh_runtime_state` — double refresh is redundant but safe ✅
- `_process_trade_lifecycle` now returns `list[dict]` with closed event details — richer audit trail ✅
- Daily metrics synced on rollover ✅

## 19. AGENTS.md Compliance: PASS

- Commit message present with WHAT/WHY/STATUS ✅
- UTC timestamps used throughout ✅
- Core pipeline determinism unaffected ✅
- No cross-import shortcuts ✅
- Signal quality rules maintained ✅

---

## Critical Issues (must fix before next milestone)

*None.*

## Warnings (fix soon)

1. **Double kill-switch evaluation**: `_evaluate_kill_switch` called in `run_decision_cycle` `finally` block (line 381) AND in `_run_event_loop` (line 415). Both call `refresh_runtime_state`. The idempotency guard prevents double-activation but wastes a DB round-trip. Consider removing the one in `_run_event_loop` since decision cycles already evaluate it.

2. **Double `load_settings` in `run_paper.py`**: `_print_banner()` calls `load_settings()`, then `main()` calls it again. Minor inefficiency.

## Resolved Known Issues

| # | Issue | Status |
|---|---|---|
| 6 | Safe mode = exit (orchestrator returns instead of monitoring) | **RESOLVED** — orchestrator now continues event loop in safe mode, lifecycle monitoring active |
| 11 | `health.py` accesses `websocket_client._thread` | **RESOLVED** — public `is_connected` property added to `BinanceFuturesWebsocketClient` |
| 12 | Defensive `getattr` in health.py | **RESOLVED** — `health.py:50` now uses direct attribute access `self.websocket_client.config.heartbeat_seconds` (via `int()` cast) |

## Observations (non-blocking)

1. `_process_trade_lifecycle` return type changed from `int` (count) to `list[dict]` (closed event details) — richer data for Telegram notifications and audit logging
2. `_critical_execution_errors` is in-memory only — resets on restart. This is acceptable for MVP but means a restart resets the exec error counter. Consider persisting if needed later.
3. `_compute_sleep_seconds` uses `min(min(deltas), idle_sleep)` — in practice, `idle_sleep` (0.5s) will almost always be the minimum since next deadlines are typically 5-900s away. This means the loop polls at ~2Hz which is reasonable.
4. Event loop does NOT separate 15m candle close detection from calendar time — it assumes 15m boundaries align with candle closes. This is correct for Binance which uses calendar-aligned candle boundaries.
5. `FakeTelegramNotifier` extends `TelegramNotifier` but overrides `send_alert` without calling `super().__init__` — works because only `send_alert` is called in tests, but the object has no `config`/`session` attributes. Acceptable for smoke test scope.

## Recommended Next Step

Phase G — backtest (replay_loader, fill_model, performance, backtest_runner). The orchestrator is now feature-complete for live/paper operation. Backtesting enables strategy validation before going live, per blueprint §13 (DoD: 6-12 months backtest with positive expectancy).
