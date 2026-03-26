# AUDIT: Phase E — Monitoring

**Date:** 2026-03-26
**Auditor:** Cascade
**Commit:** 2e31e33
**Scope:** Blueprint §5.8 — `audit_logger.py`, `telegram_notifier.py`, `health.py`, `metrics.py`, orchestrator metrics integration

## Verdict: MVP_DONE

## Layer Separation: PASS

- `audit_logger.py` — depends only on `sqlite3` and stdlib. No cross-layer imports. ✅
- `telegram_notifier.py` — imports `AuditLogger` (same layer). Uses `requests` for HTTP. ✅
- `health.py` — imports `BinanceFuturesRestClient` and `BinanceFuturesWebsocketClient` from data layer. Acceptable: monitoring needs to observe data components.
- `metrics.py` — pure dataclass + dict, zero imports beyond stdlib. ✅
- `orchestrator.py` — imports metric constants and `MetricsRegistry` from monitoring. Acceptable: orchestrator is the integration layer.
- **WARN**: `health.py:44` accesses `self.websocket_client._thread` — private attribute. Should be exposed via a public `is_alive` / `connected` property on the websocket client.

## Contract Compliance: PASS

- `AuditLogger` — 5 severity levels as class constants (`info`, `warning`, `decision`, `trade`, `critical`). `query_recent(component, severity, limit)` → `list[dict]`. ✅
- `TelegramNotifier` — `send(text) → bool`, `send_alert(alert_type, payload) → bool`. 5 alert types matching blueprint (entry, exit, kill_switch, critical_error, daily_summary). DI-friendly via optional `session` and `audit_logger`. ✅
- `HealthMonitor` — `check() → HealthStatus`. Constructor takes keyword-only args. Matches original stub contract. ✅
- `MetricsRegistry` — `snapshot() → dict[str, dict]`. 7 standard metric constants at module level. ✅
- `BinanceFuturesRestClient.ping() → bool` — new public method, uses `_request` (unsigned). ✅

## Determinism: PASS

- Monitoring is inherently non-deterministic (timestamps, HTTP). Expected.
- Core decision pipeline unaffected.

## State Integrity: PASS

- `_write_alert` commits after each log entry — ensures audit trail durability. ✅
- `health.py` uses `CREATE TEMP TABLE` for DB probe — doesn't pollute production tables. ✅
- `telegram_notifier` doesn't write to DB directly — delegates to `audit_logger`. ✅

## Error Handling: PASS

- **Telegram**: missing token/chat_id → log warning, return False. HTTP errors → log, return False. Transport exceptions → catch, log, return False. Never crashes the bot. ✅
- **Health**: each check wrapped in `try/except` → returns `False` on failure. `websocket_client is None` → `False`. Clean degradation. ✅
- **AuditLogger**: `query_recent` handles `JSONDecodeError`. `max(int(limit), 1)` prevents invalid limits. ✅
- **Rate limiting**: `_respect_rate_limit` uses `time.monotonic()` — correct clock choice for interval measurement. ✅

## Smoke Coverage: PASS

5 test areas:
1. **Audit logger**: all 5 severity levels written + query_recent with component/severity filters ✅
2. **Telegram disabled**: no-op verified (no HTTP calls made) ✅
3. **Telegram enabled**: success (200 + ok=True), verified URL/payload format ✅
4. **Telegram failure**: 500 response → returns False ✅
5. **Health**: healthy (all pass) + unhealthy (ws dead, exchange down) ✅
6. **Metrics**: all 7 constants, inc/set_gauge/snapshot ✅

**Not covered (non-blocking for MVP):**
- `send_alert` for all 5 alert types (only "entry" tested)
- Telegram with missing token/chat_id path
- Health with stale `last_message_at` (old timestamp → `websocket_alive=False`)
- `query_recent` with zero results

## Orchestrator Integration: PASS

- `MetricsRegistry` instantiated as `self.metrics` on `BotOrchestrator`. ✅
- `time.perf_counter()` for cycle duration — correct timer choice. ✅
- `try/finally` ensures `CYCLE_DURATION_MS` always recorded. ✅
- Metric instrumentation at all key decision points:
  - `SIGNALS_GENERATED` after candidate generated ✅
  - `GOVERNANCE_VETOES` after governance rejection ✅
  - `RISK_BLOCKS` after risk rejection ✅
  - `TRADES_OPENED` after successful execution ✅
  - `TRADES_CLOSED` after lifecycle processing ✅
  - `ERRORS_TOTAL` on snapshot/lifecycle/execution failures ✅
- Audit logger semantic upgrade: `log_info` → `log_decision` / `log_trade` for appropriate events — improves audit trail quality. ✅
- Decision payloads enriched with structured data (signal_id, direction, confluence_score, governance notes, risk reason). ✅

## Tech Debt: LOW

- **WARN**: `health.py:44` accesses `websocket_client._thread` — private attribute. Add a public `is_connected` property to websocket client.
- **WARN**: `health.py:51` uses `getattr(self.websocket_client.config, "heartbeat_seconds", 30)` — defensive but unnecessary given the type annotation is `BinanceFuturesWebsocketClient`.
- `ping()` return logic (rest_client.py:331-333): `if isinstance(payload, dict): return True` already catches `{}`, making the fallback `return payload == {}` redundant. Harmless.
- `TelegramNotifier` and `HealthMonitor` are not yet integrated into orchestrator's runtime loop — correct, this is Phase F scope.

## AGENTS.md Compliance: PASS

- Commit message present with WHAT/WHY/STATUS. ✅
- UTC timestamps used throughout. ✅
- Core pipeline determinism unaffected. ✅
- No cross-import shortcuts. ✅

---

## Critical Issues (must fix before next milestone)

*None.*

## Warnings (fix soon)

1. **Private attribute coupling**: `health.py:44` accesses `websocket_client._thread`. Add a public property (e.g. `is_connected`) to `BinanceFuturesWebsocketClient` and use it instead.

2. **Defensive getattr**: `health.py:51` uses `getattr(..., "heartbeat_seconds", 30)` despite type being known. Minor — replace with direct attribute access.

## Observations (non-blocking)

1. Rate limiting via `time.monotonic()` is solid — correct clock for measuring intervals
2. `TelegramNotifier` accepts injectable `session` and `audit_logger` — excellent testability
3. Orchestrator metrics integration is clean — `try/finally` pattern, all key points instrumented
4. Audit logger semantic upgrade (`log_decision`, `log_trade`) with enriched payloads significantly improves the audit trail
5. `TelegramNotifier` and `HealthMonitor` integration into orchestrator loop is Phase F scope — correct separation
6. Known issue #8 partially addressed: `ping()` is now public API. `_signed_request` still called by OrderManager/LiveExecutionEngine — those are outside Phase E scope.

## Resolved / Addressed Known Issues

| # | Issue | Status |
|---|---|---|
| 8 | `_signed_request` private API as public | **PARTIALLY ADDRESSED** — `ping()` added as public API for health check. OrderManager/LiveExecEngine usage remains (Phase D debt). |

## Recommended Next Step

Phase F (orchestration: full event loop, health/telegram integration, run_paper.py) — now that monitoring modules exist, the orchestrator can be completed with observability built in.
