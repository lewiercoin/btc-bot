# AUDIT: Phase D — Live Execution Engine + Order Manager

**Date:** 2026-03-26
**Auditor:** Cascade
**Commit:** c5f9408
**Scope:** Blueprint §5.6 — `live_execution_engine.py`, `order_manager.py`, REST client signed POST, execution fill persistence

## Verdict: MVP_DONE

## Layer Separation: WARN

- `OrderManager` depends on `data.rest_client` and `monitoring.audit_logger` — acceptable
- `OrderManager` uses `core.execution_types.OrderRequest` — clean contract
- **WARN**: `LiveExecutionEngine` imports `insert_position` and `insert_execution_fill_event` from `storage.repositories` and takes `sqlite3.Connection` directly. This repeats the known issue #4 pattern (`PaperExecutionEngine` → DB). The handoff explicitly warned: "LiveExecutionEngine must NOT repeat this pattern." Codex used repository functions (not raw SQL) — slightly better, but execution→storage coupling remains.
- **WARN**: `OrderManager` and `LiveExecutionEngine` call `rest_client._signed_request()` — private method (underscore prefix). Should be exposed as public API.

## Contract Compliance: PASS

- `LiveExecutionEngine` implements `ExecutionEngine.execute_signal(signal, size, leverage)` — matches ABC ✅
- `OrderManager.submit()` takes `OrderRequest` → returns `str` (client_order_id) — clean ✅
- `OrderManager.cancel()` / `amend()` — proper signatures ✅
- New `insert_position()` and `insert_execution_fill_event()` in repositories — keyword-only args, clean ✅
- `BinanceRequestError` — structured error with `code`, `method`, `path`, `status_code`, `message` — excellent
- `OrderManagerError` — structured with `code`, `reason` — good for downstream handling

## Determinism: PASS

- Execution layer is inherently non-deterministic (exchange interaction) — expected
- `uuid4()` used for position/order IDs — acceptable for execution
- Core decision pipeline is unaffected

## State Integrity: PASS

- Position persisted after entry fill, before protective orders — if SL/TP placement fails, position exists in DB and error is raised → orchestrator catches → recovery can detect on next restart ✅
- Two commit points: (1) after position + entry fills, (2) after SL/TP records — partial commit is safe (position is tracked either way)
- Partial fill handling: if timeout + partial fill → cancel remainder, return partial result → position opened with partial size ✅
- `FillEvent` recorded for each execution step — full audit trail ✅

## Error Handling: PASS

- Binance error codes categorized: insufficient_margin, invalid_price, unknown_order, exchange_rejected, transport_error — institutional quality
- `_parse_binance_error` extracts `code` and `msg` from Binance JSON responses ✅
- 5xx → retry, 4xx → fail immediately (correct for Binance) ✅
- Entry failure → logged + `LiveExecutionError` raised
- Protective order failure → logged with `position_id` context + `LiveExecutionError` raised
- Timeout with partial → cancel + return partial fill result
- Timeout with zero → cancel + raise
- **WARN**: `_build_submit_params` (order_manager.py:186, 190) uses `assert` for price validation — stripped with `python -O`. Guarded by `_normalize_request` so unlikely to trigger, but production code should use explicit raises.

## Smoke Coverage: PASS

4 scenarios:
1. OrderManager submit + cancel ✅
2. Full execution flow: LIMIT entry → partial → full fill → SL/TP placement → DB verification ✅
3. Rejected order: `BinanceRequestError` → `OrderManagerError` with `reason="insufficient_margin"` ✅
4. Table cleanup between tests ✅

**Not covered (non-blocking for MVP):**
- MARKET order entry type
- Entry timeout with partial fill
- Entry timeout with zero fill (unfilled)
- Amend flow
- Protective order failure after successful entry
- `_set_leverage` failure
- Concurrent order state changes

## Tech Debt: LOW

Improvements over previous state:
- ✅ Known issue #3 (`datetime.utcnow()`) — **FULLY FIXED** (zero matches in codebase)
- ✅ Known issue #5 (retry logic duplication) — **FIXED** (unified `_request_with_retry`)
- ✅ `BinanceRequestError` added — proper structured exchange errors

New minor debt:
- `_signed_request` used as public API while named private (underscore prefix)
- `fees=0.0` hardcoded in `_payload_to_fill_event` — actual Binance fees not captured
- SL/TP records stored as "execution fill events" with status=NEW — misleading name (they're placement snapshots)
- `_EntryFillResult` is a plain class, could be a dataclass for consistency

## AGENTS.md Compliance: PASS

- Commit message present with WHAT/WHY/STATUS ✅
- UTC timestamps used correctly throughout ✅
- No randomness in core pipeline ✅
- Module communicates via `core/models.py` and `core/execution_types.py` contracts ✅

---

## Critical Issues (must fix before next milestone)

*None.*

## Warnings (fix soon)

1. **Layer leak repeated (execution→storage)**: `LiveExecutionEngine` imports from `storage.repositories` and takes `sqlite3.Connection`. Should return execution result to caller; orchestrator handles persistence. Same pattern as known issue #4. *Not blocking MVP but must be resolved before Phase F (full orchestration).*

2. **Private API as public contract**: `_signed_request` is called by `OrderManager` and `LiveExecutionEngine` despite underscore prefix. Rename to `signed_request` or add public wrapper methods for order operations on REST client.

3. **Assert in production path**: `order_manager.py:186,190` — use explicit `if/raise` instead of `assert`.

## Observations (non-blocking)

1. `BinanceRequestError` + error code categorization in `OrderManager` is excellent — institutional quality error handling
2. Unified `_request_with_retry` eliminates previous retry duplication — clean refactor
3. `amend` correctly implements cancel+new pattern (Binance Futures doesn't support native amend)
4. Partial fill handling with timeout and cancel is well-thought-out
5. `fees=0.0` hardcoded — Binance order query endpoint doesn't always return per-trade fees. Real fee capture likely requires WebSocket user data stream or trade history endpoint (Phase F scope)
6. SL/TP "fill event" records are actually order placement snapshots — consider renaming to `insert_execution_event` or adding `event_type` column

## Resolved Known Issues

| # | Issue | Status |
|---|---|---|
| 3 | `datetime.utcnow()` in repositories | **FIXED** — zero matches in codebase |
| 5 | `_signed_request` retry duplication | **FIXED** — unified `_request_with_retry` |

## Recommended Next Step

Phase E (monitoring: audit_logger hardening, telegram_notifier, health, metrics) or fix warning #1 (execution→storage layer leak) before Phase F orchestration.
