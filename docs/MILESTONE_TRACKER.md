# Milestone Tracker

Last updated: 2026-03-26

## Next Milestone

**Status:** ACTIVE
**Milestone:** Phase D — Execution (live_execution_engine + order_manager)
**Decision date:** 2026-03-26
**Decided by:** User (product owner)
**Scope:** `docs/BLUEPRINT_V1.md` §5.6 — `live_execution_engine.py`, `order_manager.py`
**Handoff:** See Cascade handoff below or in chat history

## Phase Status

| Phase | Scope | Status | Smoke Test | Audit |
|---|---|---|---|---|
| A — fundament | settings, models, schema, db, repositories, exchange_guard | MVP_DONE | N/A (structural) | Pending |
| B — dane | rest_client, websocket_client, market_data, bootstrap_history | MVP_DONE | data_audit_phase_b.py | Pending |
| C — logika | feature_engine, regime_engine, signal_engine, governance, risk_engine | MVP_DONE | smoke_phase_c.py | Pending |
| D — execution: recovery | recovery.py, orchestrator startup sync | MVP_DONE | smoke_recovery.py | AUDIT_001 ✅ |
| D — execution: live + orders | live_execution_engine.py, order_manager.py | IN_PROGRESS | — | — |
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
| execution/live_execution_engine.py | LiveExecutionEngine.execute_signal | D |
| execution/order_manager.py | OrderManager.submit/cancel/amend | D |
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
3. **Deprecated API**: `repositories.py:57` uses `datetime.utcnow()` instead of `datetime.now(timezone.utc)` — *tracked since initial audit*
4. **Layer leak**: `PaperExecutionEngine` writes directly to DB (execution should not know DB schema) — *tracked since initial audit*
5. **Tech debt**: `rest_client.py` `_signed_request` duplicates retry logic from `_request` — *identified in AUDIT_001*
6. **Safe mode = exit**: orchestrator returns on safe_mode instead of managing existing positions (Phase F scope) — *identified in AUDIT_001*
7. **Smoke gap**: `smoke_recovery.py` doesn't cover exchange_sync_failed, isolated_mode_mismatch, leverage_mismatch, combined issues — *identified in AUDIT_001*

## Audit History

| ID | Milestone | Date | Commit | Verdict |
|---|---|---|---|---|
| AUDIT_001 | Recovery Startup Sync | 2026-03-26 | 436756b | MVP_DONE |
