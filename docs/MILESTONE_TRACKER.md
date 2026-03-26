# Milestone Tracker

Last updated: 2026-03-26

## Next Milestone

**Status:** ACTIVE
**Milestone:** Phase E — Monitoring (audit_logger, telegram_notifier, health, metrics)
**Decision date:** 2026-03-26
**Decided by:** User (product owner)
**Scope:** `docs/BLUEPRINT_V1.md` §5.8 — `audit_logger.py`, `telegram_notifier.py`, `health.py`, `metrics.py`
**Handoff:** See Cascade handoff in chat history

## Phase Status

| Phase | Scope | Status | Smoke Test | Audit |
|---|---|---|---|---|
| A — fundament | settings, models, schema, db, repositories, exchange_guard | MVP_DONE | N/A (structural) | Pending |
| B — dane | rest_client, websocket_client, market_data, bootstrap_history | MVP_DONE | data_audit_phase_b.py | Pending |
| C — logika | feature_engine, regime_engine, signal_engine, governance, risk_engine | MVP_DONE | smoke_phase_c.py | Pending |
| D — execution: recovery | recovery.py, orchestrator startup sync | MVP_DONE | smoke_recovery.py | AUDIT_001 ✅ |
| D — execution: live + orders | live_execution_engine.py, order_manager.py | MVP_DONE | smoke_live_execution.py | AUDIT_002 ✅ |
| E — monitoring | audit_logger, telegram, health, metrics | NOT_STARTED | — | — |
| F — orchestracja | orchestrator, main, run_paper | NOT_STARTED | — | — |
| G — backtest | replay_loader, fill_model, performance, backtest_runner | NOT_STARTED | — | — |
| H — research | analyze_trades, llm_post_trade_review | NOT_STARTED | — | — |

## Cross-Cutting Milestones

| Milestone | Status | Smoke Test | Audit |
|---|---|---|---|
| Runtime state persistence | MVP_DONE | smoke_state_persistence.py | Pending |
| Trade lifecycle + PnL settlement | MVP_DONE | smoke_trade_lifecycle.py | Pending |
| Drawdown persistence | MVP_DONE | smoke_drawdown_persistence.py | Pending |
| Recovery startup sync | MVP_DONE | smoke_recovery.py | AUDIT_001 ✅ |

## Stub Inventory (NotImplementedError)

| File | Class/Method | Target Phase |
|---|---|---|
| monitoring/health.py | HealthMonitor.check | E |
| monitoring/telegram_notifier.py | TelegramNotifier.send | E |
| backtest/backtest_runner.py | BacktestRunner.run | G |
| backtest/fill_model.py | (stub file) | G |
| backtest/performance.py | (stub file) | G |
| backtest/replay_loader.py | (stub file) | G |
| research/analyze_trades.py | (stub file) | H |
| research/llm_post_trade_review.py | (stub file) | H |

## Known Issues

1. **Layer leak**: `storage/state_store.py` imports `GovernanceRuntimeState` and `RiskRuntimeState` directly from core engines — *tracked since initial audit*
2. **Statefulness**: `FeatureEngine` internal deques break independent reproducibility (AGENTS.md violation) — *tracked since initial audit*
3. ~~**Deprecated API**: `repositories.py:57` uses `datetime.utcnow()`~~ — **FIXED in c5f9408** (zero matches in codebase)
4. **Layer leak**: `PaperExecutionEngine` AND `LiveExecutionEngine` import from `storage.repositories` and take `sqlite3.Connection` (execution should not know storage) — *tracked since initial audit, repeated in AUDIT_002*
5. ~~**Tech debt**: `_signed_request` retry duplication~~ — **FIXED in c5f9408** (unified `_request_with_retry`)
6. **Safe mode = exit**: orchestrator returns on safe_mode instead of managing existing positions (Phase F scope) — *identified in AUDIT_001*
7. **Smoke gap**: `smoke_recovery.py` doesn't cover exchange_sync_failed, isolated_mode_mismatch, leverage_mismatch, combined issues — *identified in AUDIT_001*
8. **Private API as public contract**: `_signed_request` called by OrderManager and LiveExecutionEngine despite underscore prefix — *identified in AUDIT_002*
9. **Assert in production path**: `order_manager.py:186,190` uses `assert` instead of explicit raises — *identified in AUDIT_002*
10. **Fees not captured**: `fees=0.0` hardcoded in LiveExecutionEngine — actual Binance fees not extracted — *identified in AUDIT_002*

## Audit History

| ID | Milestone | Date | Commit | Verdict |
|---|---|---|---|---|
| AUDIT_001 | Recovery Startup Sync | 2026-03-26 | 436756b | MVP_DONE |
| AUDIT_002 | Phase D — Live Execution + Order Manager | 2026-03-26 | c5f9408 | MVP_DONE |
