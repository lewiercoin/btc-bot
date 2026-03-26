# Milestone Tracker

Last updated: 2026-03-26

## Phase Status

| Phase | Scope | Status | Smoke Test | Audit |
|---|---|---|---|---|
| A — fundament | settings, models, schema, db, repositories, exchange_guard | MVP_DONE | N/A (structural) | Pending |
| B — dane | rest_client, websocket_client, market_data, bootstrap_history | MVP_DONE | data_audit_phase_b.py | Pending |
| C — logika | feature_engine, regime_engine, signal_engine, governance, risk_engine | MVP_DONE | smoke_phase_c.py | Pending |
| D — execution | paper/live execution, order_manager, recovery | IN_PROGRESS | — | — |
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
| Recovery startup sync | PENDING | — | — |

## Stub Inventory (NotImplementedError)

| File | Class/Method | Target Phase |
|---|---|---|
| execution/live_execution_engine.py | LiveExecutionEngine.execute_signal | D |
| execution/order_manager.py | OrderManager.submit/cancel/amend | D |
| execution/recovery.py | RecoveryCoordinator.run_startup_sync | D |
| monitoring/health.py | HealthMonitor.check | E |
| monitoring/telegram_notifier.py | TelegramNotifier.send | E |
| backtest/backtest_runner.py | BacktestRunner.run | G |
| backtest/fill_model.py | (stub file) | G |
| backtest/performance.py | (stub file) | G |
| backtest/replay_loader.py | (stub file) | G |
| research/analyze_trades.py | (stub file) | H |
| research/llm_post_trade_review.py | (stub file) | H |

## Known Issues (from initial Cascade audit, 2026-03-26)

1. **Layer leak**: `storage/state_store.py` imports `GovernanceRuntimeState` and `RiskRuntimeState` directly from core engines
2. **Statefulness**: `FeatureEngine` internal deques break independent reproducibility (AGENTS.md violation)
3. **Deprecated API**: `repositories.py:57` uses `datetime.utcnow()` instead of `datetime.now(timezone.utc)`
4. **Layer leak**: `PaperExecutionEngine` writes directly to DB (execution should not know DB schema)

## Next Steps

1. **Organizational**: Blueprint, CASCADE.md, and tracker committed to repo (this session)
2. **Technical**: Recovery startup sync (next milestone)
