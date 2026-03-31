# Milestone Tracker

Last updated: 2026-03-31

## Next Milestone

**Milestone:** —
**Status:** AWAITING_DECISION
**Decision date:** —
**Scope:** Research Lab v0.1 complete. Candidate next steps: (A) first real parameter search run (20–50 trials, review Pareto frontier), (B) Known Issue #1 layer leak cleanup, (C) smoke gap #7 coverage.

## Previous Milestones

**Milestone:** Research Lab v0.1 — Offline Optimization Infrastructure
**Status:** MVP_DONE (commit dfafa26, audit passed)
**Scope:** Offline parameter optimization lab: param registry (49 active / 9 frozen params), immutable AppSettings adapter, SQLite snapshot isolation per trial, InstrumentedBacktestRunner with signal funnel, fixed walk-forward protocol, sensitivity analysis, Pareto frontier, experiment store, approval bundle generator, Optuna multi-objective driver, CLI. Deprecated stale `docs/autoresearch/` drafts.

**Milestone:** Tech Debt: CI + Test Infrastructure
**Status:** MVP_DONE (commits 86917df + a24e1e3, audit passed)
**Scope:** Added `.github/workflows/ci.yml` (compileall + pytest + smoke_phase_c), pytest foundation with 14 unit tests (performance, models, settings, feature_engine, settings_adapter), ruff config. Fixed Known Issue #2 (FeatureEngine statefulness — `reset()` added, reproducibility tests added).

**Milestone:** Strategy Optimization v1.1 — Kill SHORT signals + diagnostic funnel
**Status:** MVP_DONE (commit c1ea3cf, audit passed)
**Results:** PF 0.97→1.40, PnL -$289→+$2,932, WR 34.7%→43.6%, DD 18.8%→17.0%, Sharpe -0.12→4.37.

**Milestone:** Strategy Optimization v1 — Regime Gating + SL Redesign + Partial Exits
**Status:** MVP_DONE (commit 8e48bee, audit passed)
**Results:** PF 0.40→0.97, DD 47.8%→18.8%, WR 15%→34.7%. SHORT 0% WR persists.

**Milestone:** Tech Debt Cleanup
**Status:** PAUSED (deprioritized — strategy optimization takes precedence)
**Decision date:** 2026-03-29
**Scope:** Fix remaining open known issues (#1, #4, #8, #9, #10, #13, #14, #15). Zero regressions — all existing smoke tests must pass after each fix.

**Note:** All blueprint phases (A-H) are now MVP_DONE. Autoresearch (v2.0) deferred.

## Phase Status

| Phase | Scope | Status | Smoke Test | Audit |
|---|---|---|---|---|
| A — fundament | settings, models, schema, db, repositories, exchange_guard | MVP_DONE | N/A (structural) | Pending |
| B — dane | rest_client, websocket_client, market_data, bootstrap_history | MVP_DONE | data_audit_phase_b.py | Pending |
| C — logika | feature_engine, regime_engine, signal_engine, governance, risk_engine | MVP_DONE | smoke_phase_c.py | Pending |
| D — execution: recovery | recovery.py, orchestrator startup sync | MVP_DONE | smoke_recovery.py | AUDIT_001 ✅ |
| D — execution: live + orders | live_execution_engine.py, order_manager.py | MVP_DONE | smoke_live_execution.py | AUDIT_002 ✅ |
| E — monitoring | audit_logger, telegram, health, metrics | MVP_DONE | smoke_monitoring.py | AUDIT_003 ✅ |
| F — orchestracja | orchestrator, main, run_paper | MVP_DONE | smoke_orchestrator.py | AUDIT_004 ✅ |
| G — backtest | replay_loader, fill_model, performance, backtest_runner | MVP_DONE | smoke_backtest.py | AUDIT_005 ✅ |
| H — research | analyze_trades, llm_post_trade_review | MVP_DONE | smoke_research.py | AUDIT_006 ✅ |

## Cross-Cutting Milestones

| Milestone | Status | Smoke Test | Audit |
|---|---|---|---|
| Runtime state persistence | MVP_DONE | smoke_state_persistence.py | Pending |
| Trade lifecycle + PnL settlement | MVP_DONE | smoke_trade_lifecycle.py | Pending |
| Drawdown persistence | MVP_DONE | smoke_drawdown_persistence.py | Pending |
| Recovery startup sync | MVP_DONE | smoke_recovery.py | AUDIT_001 ✅ |

## Stub Inventory (NotImplementedError)

None — all blueprint stubs implemented.

## Known Issues

1. **Layer leak**: `storage/state_store.py` imports `GovernanceRuntimeState` and `RiskRuntimeState` directly from core engines — *tracked since initial audit*
2. ~~**Statefulness**: `FeatureEngine` internal deques break independent reproducibility (AGENTS.md violation)~~ — **FIXED in a24e1e3** (`FeatureEngine.reset()` added; backtest already creates fresh FeatureEngine per run; `tests/test_feature_engine.py` validates idempotency and reset-based fresh-instance reproducibility)
3. ~~**Deprecated API**: `repositories.py:57` uses `datetime.utcnow()`~~ — **FIXED in c5f9408** (zero matches in codebase)
4. ~~**Layer leak**: `PaperExecutionEngine` AND `LiveExecutionEngine` import from `storage.repositories` and take `sqlite3.Connection` (execution should not know storage)~~ — **FIXED in ba72c35** (PositionPersister protocol + DI injection into execution engines)
5. ~~**Tech debt**: `_signed_request` retry duplication~~ — **FIXED in c5f9408** (unified `_request_with_retry`)
6. ~~**Safe mode = exit**: orchestrator returns on safe_mode instead of managing existing positions~~ — **FIXED in 09a099f** (orchestrator continues event loop in safe mode, lifecycle monitoring active)
7. **Smoke gap**: `smoke_recovery.py` doesn't cover exchange_sync_failed, isolated_mode_mismatch, leverage_mismatch, combined issues — *identified in AUDIT_001*
8. ~~**Private API as public contract**: `_signed_request` called by OrderManager and LiveExecutionEngine despite underscore prefix~~ — **FIXED in 45c9d3d** (execution layer uses public `signed_request()`)
9. ~~**Assert in production path**: `order_manager.py:186,190` uses `assert` instead of explicit raises~~ — **FIXED in 5c7a882** (replaced with explicit `OrderManagerError` raises)
10. ~~**Fees not captured**: `fees=0.0` hardcoded in LiveExecutionEngine — actual Binance fees not extracted~~ — **FIXED in a325072** (fees parsed from exchange commission payload)
11. ~~**Private attribute coupling**: `health.py:44` accesses `websocket_client._thread`~~ — **FIXED in 09a099f** (public `is_connected` property added to `BinanceFuturesWebsocketClient`)
12. ~~**Defensive getattr**: `health.py:51` uses `getattr(..., "heartbeat_seconds", 30)`~~ — **FIXED in 09a099f** (direct attribute access via `int()` cast)
13. ~~**Double kill-switch evaluation**: `_evaluate_kill_switch` called both in `run_decision_cycle` finally block and in `_run_event_loop` — redundant `refresh_runtime_state` call~~ — **FIXED in 9dd99a2** (single kill-switch evaluation per event loop iteration)
14. ~~**ReplayLoader N+1 queries**: 8 SQL queries per 15m bar — ~140k-280k queries for 6-12 month backtest. Functional but slow. Consider batch-loading.~~ — **FIXED in 7c69bc0** (bulk preload + in-memory bisect indexing)
15. ~~**Sharpe population variance**: `_daily_sharpe_ratio` uses population variance (/ N) instead of sample variance (/ N-1). Minor statistical difference.~~ — **FIXED in 0b6463a** (uses sample variance `n-1`)
16. ~~**Config injection gap**: 27 dead parameters in orchestrator + backtest_runner + signal_engine~~ — **FIXED in AUDIT_006** (all parameters wired, smoke_config_injection.py validates)
17. ~~**Hardcoded symbol**: `PaperExecutionEngine` line 29 hardcodes `"BTCUSDT"` instead of using `settings.strategy.symbol`~~ — **FIXED in b1fb7f4** (symbol param added, orchestrator wired)
18. ~~**PAPER restart phantom_position**: `NoOpRecoverySyncSource` returns empty lists → `RecoveryCoordinator` sees local OPEN positions as phantoms → `safe_mode=True` → new entries blocked after restart~~ — **FIXED in 27a9270** (PAPER mode skips exchange consistency checks)

## Audit History

| ID | Milestone | Date | Commit | Verdict |
|---|---|---|---|---|
| AUDIT_001 | Recovery Startup Sync | 2026-03-26 | 436756b | MVP_DONE |
| AUDIT_002 | Phase D — Live Execution + Order Manager | 2026-03-26 | c5f9408 | MVP_DONE |
| AUDIT_003 | Phase E — Monitoring | 2026-03-26 | 2e31e33 | MVP_DONE |
| AUDIT_004 | Phase F — Orchestration | 2026-03-26 | 09a099f | MVP_DONE |
| AUDIT_005 | Phase G — Backtest | 2026-03-26 | 26fe3d7 | MVP_DONE |
| AUDIT_006 | Config Injection Bugfix + Phase H Research | 2026-03-26 | c072405 | MVP_DONE |
| AUDIT_007 | Daily Reset consecutive_losses + Trade Filtering | 2026-03-28 | 0e5f112 | MVP_DONE |
| AUDIT_008 | Paper Trading Validation | 2026-03-29 | b1fb7f4 | MVP_DONE |
| AUDIT_009 | Fix #18 — PAPER restart phantom_position | 2026-03-29 | 27a9270 | MVP_DONE |
| AUDIT_010 | Tech Debt: CI + pytest + ruff foundation | 2026-03-31 | 86917df | MVP_DONE |
| AUDIT_011 | Known Issue #2 — FeatureEngine statefulness | 2026-03-31 | a24e1e3 | MVP_DONE |
| AUDIT_012 | Research Lab v0.1 — architecture + implementation | 2026-03-31 | aa68c23 | MVP_DONE |
| AUDIT_013 | Research Lab v0.1 — optuna runtime validation | 2026-03-31 | dfafa26 | MVP_DONE |
