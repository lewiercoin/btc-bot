# Milestone Tracker

Last updated: 2026-04-08

## Baseline Checkpoint

| Field | Value |
|---|---|
| **Tag** | `v1.0-baseline` |
| **Commit** | `a1a82b5` |
| **Date** | 2026-04-01 |
| **How to restore** | `git checkout v1.0-baseline` |
| **What it contains** | Fazy A–H MVP_DONE · Research Lab RL-V1 do RL-FUTURE MVP_DONE · 18/18 Known Issues zamknięte · dokumentacja zsynchronizowana · 35/35 testów zielonych |
| **Strategy at tag** | PF 1.40 · WR 43.6% · Sharpe 4.37 · DD 17.0% |

## Next Milestone

**Milestone:** DASHBOARD-M1 — Read-Only Observability + WAL Patch
**Status:** MVP_DONE (audit 2026-04-02, 46/46 tests green)
**Decision date:** 2026-04-02
**Active builder:** Codex
**Scope:** WAL mode in `storage/db.py` + `connect_readonly()` helper + FastAPI dashboard (observability only: `/api/status`, `/api/positions`, `/api/trades`, `/api/logs/stream`). No start/stop. No terminal. Bind 127.0.0.1 only.
**Audit:** [docs/audits/AUDIT_DASHBOARD_M1_2026-04-02.md](audits/AUDIT_DASHBOARD_M1_2026-04-02.md)

## Next Milestone

**Milestone:** DASHBOARD-M3 — Managed Start/Stop
**Status:** MVP_DONE (audit 2026-04-02, 53/53 tests green)
**Decision date:** 2026-04-02
**Active builder:** Codex
**Scope:** `ProcessManager` (`CREATE_NEW_PROCESS_GROUP` + `CTRL_C_EVENT` + 10s timeout + hard fallback + operator audit log) + `/api/bot/start` + `/api/bot/stop` + `uptime_seconds` in `/api/status` + M1 carry-overs: `db_reader.py` OperationalError guard + `app.js` innerHTML → DOM fix.
**Audit:** [docs/audits/AUDIT_DASHBOARD_M3_2026-04-02.md](audits/AUDIT_DASHBOARD_M3_2026-04-02.md)

## Next Milestone

**Milestone:** SERVER-DEPLOY-V1 — Hetzner Research Lab Deployment
**Status:** DONE (audit 2026-04-02)
**Decision date:** 2026-04-02
**Active builder:** Codex
**Scope:** Deployment scripts for running Research Lab and Autoresearch on remote Hetzner server. No changes to existing Python logic. Artifacts: `scripts/server/setup.sh`, `scripts/server/refresh_data.sh`, `scripts/server/run_optimize.sh`, `scripts/server/run_autoresearch.sh`, `scripts/server/status.sh`, `scripts/server/cleanup_snapshots.sh`, `docs/SERVER_DEPLOYMENT.md`.

**Milestone:** SERVER-DEPLOY-V2 — Production Hetzner Deploy (Bot + Research Lab)
**Status:** DONE (audit 2026-04-08, commits 1343d3c + 5f51ded)
**Decision date:** 2026-04-08
**Active builder:** Cascade
**Scope:** Fix ProcessManager Linux signal bug (G1) · systemd unit files for bot + dashboard (G2) · SERVER_DEPLOYMENT.md hardening: user setup, chmod, sshd, rsync --ignore-existing (G3, G4, G7, G8) · run_dashboard.sh script (G5) · logrotate config for research lab logs (G6)
**Audit:** [docs/audits/AUDIT_SERVER_DEPLOY_V2_2026-04-08.md](audits/AUDIT_SERVER_DEPLOY_V2_2026-04-08.md)

## Research Lab

**Blueprint:** `docs/BLUEPRINT_RESEARCH_LAB.md`
**Boundary:** Offline-only; reads from `backtest/` and `settings` surfaces; no live path mutation; approval bundle ends with human-review artifacts

**Current active milestone:** None — all milestones closed
**Milestone status:** —
**Last audit verdict:** 2026-04-01 Claude audit - Tech Debt Cleanup MVP_DONE

### Milestone ladder

| ID | Name | Status | Implementation commit | Last audit | Blocking issues |
|---|---|---|---|---|---|
| RL-HARDENING | Store Schema + Operator Clarity | CLOSED | `8d47528` | - | none |
| RL-V3 | Nested Walk-Forward | CLOSED | `9849486` | 2026-04-01 Claude audit - MVP_DONE | none |
| RL-V2 | WF multicriteria + Protocol lineage | CLOSED | `00e7ada` | 2026-04-01 Claude audit - MVP_DONE | none |
| RL-CLEANUP-001 | Research Lab Cleanup: RL-004 + RL-005 | CLOSED | `df81334` | 2026-04-01 Claude audit - MVP_DONE | none |
| RL-GOV-FOUNDATION | Research Lab Governance Foundation | CLOSED | `6abaadf` | 2026-04-01 Claude audit - MVP_DONE | none |
| RL-V1 | Hard Promotion Gate | CLOSED | `10e4e87` | 2026-04-01 Claude audit - MVP_DONE | none |
| RL-FUTURE | Autoresearch agent loop | CLOSED | `d1ab0f1` | 2026-04-01 Claude audit - MVP_DONE | none |

### Known Out-Of-Scope For RL-FUTURE v1

| Type | Issue |
|---|---|
| vFuture | Multi-iteration autonomous loop |
| vFuture | `walkforward_mode=nested` support |
| vFuture | Scheduled/event-triggered runs |
| vFuture | LLM as gate or ranking authority |

### Open issues

#### BUG

None.

#### METHODOLOGY_DEBT

None.

#### ARCH_DEBT

None.

### Audit history

| Audit | Scope | Date | Verdict | Reference |
|---|---|---|---|---|
| `AUDIT_OPTIMIZATION_SYSTEM_REQUEST` | Optimization system audit request context | 2026-03-29 | Context report | [docs/audits/AUDIT_OPTIMIZATION_SYSTEM_REQUEST.md](audits/AUDIT_OPTIMIZATION_SYSTEM_REQUEST.md) |
| `AUDIT_012` | Research Lab v0.1 architecture + implementation | 2026-03-31 | MVP_DONE | Tracker record |
| `AUDIT_013` | Research Lab v0.1 optuna runtime validation | 2026-03-31 | MVP_DONE | Tracker record |
| `CLAUDE_2026-04-01_HARD_GATE` | Hard Promotion Gate | 2026-04-01 | MVP_DONE | Claude audit and handoff record |
| `CLAUDE_2026-04-01_GOVERNANCE_FOUNDATION` | Research Lab Governance Foundation | 2026-04-01 | MVP_DONE | Claude audit and handoff record |
| `AUDIT_RL_FUTURE_AUTORESEARCH_V1` | Autoresearch Agent Loop v1 | 2026-04-01 | MVP_DONE | [docs/audits/AUDIT_RL_FUTURE_AUTORESEARCH_V1_2026-04-01.md](audits/AUDIT_RL_FUTURE_AUTORESEARCH_V1_2026-04-01.md) |

## Previous Milestones

**Milestone:** Research Lab Governance Foundation
**Status:** MVP_DONE (commits `254f7c1` + `6abaadf`, audit passed)
**Scope:** Closed workflow document drift, added `docs/BLUEPRINT_RESEARCH_LAB.md`, extended `CLAUDE.md` with research lab audit rules, and codified research-lab-specific tracker and phase rules.

**Milestone:** Research Lab v1 - Hard Promotion Gate
**Status:** MVP_DONE (commit `10e4e87`, audit passed)
**Scope:** Added a hard CLI gate for `build-approval-bundle` so candidates with `walkforward_not_passed` or `walkforward_fragile` cannot produce approval artifacts. Added smoke coverage for blocked and clean approval bundle paths.

**Milestone:** Research Lab v0.1 - Offline Optimization Infrastructure
**Status:** MVP_DONE (commit `dfafa26`, audit passed)
**Scope:** Offline parameter optimization lab: param registry (49 active / 9 frozen params), immutable `AppSettings` adapter, SQLite snapshot isolation per trial, `InstrumentedBacktestRunner` with signal funnel, fixed walk-forward protocol, sensitivity analysis, Pareto frontier, experiment store, approval bundle generator, Optuna multi-objective driver, CLI. Deprecated stale `docs/autoresearch/` drafts.

**Milestone:** Tech Debt: CI + Test Infrastructure
**Status:** MVP_DONE (commits `86917df` + `a24e1e3`, audit passed)
**Scope:** Added `.github/workflows/ci.yml` (compileall + pytest + smoke_phase_c), pytest foundation with 14 unit tests (performance, models, settings, feature_engine, settings_adapter), ruff config. Fixed Known Issue #2 (FeatureEngine statefulness - `reset()` added, reproducibility tests added).

**Milestone:** Strategy Optimization v1.1 - Kill SHORT signals + diagnostic funnel
**Status:** MVP_DONE (commit `c1ea3cf`, audit passed)
**Results:** PF 0.97 -> 1.40, PnL -$289 -> +$2,932, WR 34.7% -> 43.6%, DD 18.8% -> 17.0%, Sharpe -0.12 -> 4.37.

**Milestone:** Strategy Optimization v1 - Regime Gating + SL Redesign + Partial Exits
**Status:** MVP_DONE (commit `8e48bee`, audit passed)
**Results:** PF 0.40 -> 0.97, DD 47.8% -> 18.8%, WR 15% -> 34.7%. SHORT 0% WR persists.

**Milestone:** Tech Debt Cleanup
**Status:** PAUSED (deprioritized - strategy optimization takes precedence)
**Decision date:** 2026-03-29
**Scope:** Fix remaining open known issues (#1, #4, #8, #9, #10, #13, #14, #15). Zero regressions - all existing smoke tests must pass after each fix.

**Note:** All blueprint phases (A-H), cross-cutting hardening work, and Research Lab milestones through RL-FUTURE are closed at `v1.0-baseline`. Only explicitly listed out-of-scope methodology items remain deferred.

## Optional Future Milestones (not scheduled)

| ID | Name | Trigger |
|---|---|---|
| DASHBOARD-M4 | Backtest/Research Job Runner (asyncio queue, job_id, SSE output, history) | After M3 has been in operator use and field-validated |
| DASHBOARD-M5 | Embedded terminal (admin-only, separate origin, ConPTY) | Only if terminal access from browser becomes a real need |

## Phase Status

| Phase | Scope | Status | Smoke Test | Audit |
|---|---|---|---|---|
| A - fundament | settings, models, schema, db, repositories, exchange_guard | MVP_DONE | N/A (structural) | Pending |
| B - dane | rest_client, websocket_client, market_data, bootstrap_history | MVP_DONE | data_audit_phase_b.py | Pending |
| C - logika | feature_engine, regime_engine, signal_engine, governance, risk_engine | MVP_DONE | smoke_phase_c.py | Pending |
| D - execution: recovery | recovery.py, orchestrator startup sync | MVP_DONE | smoke_recovery.py | AUDIT_001 |
| D - execution: live + orders | live_execution_engine.py, order_manager.py | MVP_DONE | smoke_live_execution.py | AUDIT_002 |
| E - monitoring | audit_logger, telegram, health, metrics | MVP_DONE | smoke_monitoring.py | AUDIT_003 |
| F - orchestracja | orchestrator, main, run_paper | MVP_DONE | smoke_orchestrator.py | AUDIT_004 |
| G - backtest | replay_loader, fill_model, performance, backtest_runner.py | MVP_DONE | smoke_backtest.py | AUDIT_005 |
| H - research | analyze_trades.py, llm_post_trade_review.py | MVP_DONE | smoke_research.py | AUDIT_006 |

## Cross-Cutting Milestones

| Milestone | Status | Smoke Test | Audit |
|---|---|---|---|
| Runtime state persistence | MVP_DONE | smoke_state_persistence.py | Pending |
| Trade lifecycle + PnL settlement | MVP_DONE | smoke_trade_lifecycle.py | Pending |
| Drawdown persistence | MVP_DONE | smoke_drawdown_persistence.py | Pending |
| Recovery startup sync | MVP_DONE | smoke_recovery.py | AUDIT_001 |

## Stub Inventory (NotImplementedError)

None - all blueprint stubs implemented.

## Known Issues

1. ~~**Layer leak**: `storage/state_store.py` imports `GovernanceRuntimeState` and `RiskRuntimeState` directly from core engines - tracked since initial audit~~ - **FIXED in `f93507c`** (`storage/state_store.py` now depends only on shared contracts from `core/models.py`; `SettlementMetrics` was moved out of `core/risk_engine.py` into the shared core model surface)
2. ~~**Statefulness**: `FeatureEngine` internal deques break independent reproducibility (AGENTS.md violation)~~ - **FIXED in `a24e1e3`** (`FeatureEngine.reset()` added; backtest already creates fresh `FeatureEngine` per run; `tests/test_feature_engine.py` validates idempotency and reset-based fresh-instance reproducibility)
3. ~~**Deprecated API**: `repositories.py:57` uses `datetime.utcnow()`~~ - **FIXED in `c5f9408`** (zero matches in codebase)
4. ~~**Layer leak**: `PaperExecutionEngine` and `LiveExecutionEngine` import from `storage.repositories` and take `sqlite3.Connection` (execution should not know storage)~~ - **FIXED in `ba72c35`** (`PositionPersister` protocol plus DI injection into execution engines)
5. ~~**Tech debt**: `_signed_request` retry duplication~~ - **FIXED in `c5f9408`** (unified `_request_with_retry`)
6. ~~**Safe mode = exit**: orchestrator returns on `safe_mode` instead of managing existing positions~~ - **FIXED in `09a099f`** (orchestrator continues event loop in safe mode, lifecycle monitoring active)
7. ~~**Smoke gap**: `smoke_recovery.py` does not cover `exchange_sync_failed`, `isolated_mode_mismatch`, `leverage_mismatch`, or combined issues - identified in `AUDIT_001`~~ - **FIXED in `8602727`** (`scripts/smoke_recovery.py` now runs on in-memory SQLite and asserts the missing recovery failure paths plus persisted recovery audit logs deterministically)
8. ~~**Private API as public contract**: `_signed_request` called by `OrderManager` and `LiveExecutionEngine` despite underscore prefix~~ - **FIXED in `45c9d3d`** (execution layer uses public `signed_request()`)
9. ~~**Assert in production path**: `order_manager.py` uses `assert` instead of explicit raises~~ - **FIXED in `5c7a882`** (replaced with explicit `OrderManagerError` raises)
10. ~~**Fees not captured**: `fees=0.0` hardcoded in `LiveExecutionEngine`; actual Binance fees not extracted~~ - **FIXED in `a325072`** (fees parsed from exchange commission payload)
11. ~~**Private attribute coupling**: `health.py:44` accesses `websocket_client._thread`~~ - **FIXED in `09a099f`** (public `is_connected` property added to `BinanceFuturesWebsocketClient`)
12. ~~**Defensive getattr**: `health.py:51` uses `getattr(..., "heartbeat_seconds", 30)`~~ - **FIXED in `09a099f`** (direct attribute access via `int()` cast)
13. ~~**Double kill-switch evaluation**: `_evaluate_kill_switch` called both in `run_decision_cycle` finally block and in `_run_event_loop`~~ - **FIXED in `9dd99a2`** (single kill-switch evaluation per event loop iteration)
14. ~~**ReplayLoader N+1 queries**: 8 SQL queries per 15m bar; functional but slow~~ - **FIXED in `7c69bc0`** (bulk preload plus in-memory bisect indexing)
15. ~~**Sharpe population variance**: `_daily_sharpe_ratio` used population variance instead of sample variance~~ - **FIXED in `0b6463a`** (uses sample variance `n-1`)
16. ~~**Config injection gap**: 27 dead parameters in orchestrator + backtest_runner + signal_engine~~ - **FIXED in `AUDIT_006`** (all parameters wired, `smoke_config_injection.py` validates)
17. ~~**Hardcoded symbol**: `PaperExecutionEngine` hardcoded `BTCUSDT` instead of using `settings.strategy.symbol`~~ - **FIXED in `b1fb7f4`** (symbol param added, orchestrator wired)
18. ~~**PAPER restart phantom_position**: `NoOpRecoverySyncSource` returns empty lists -> `RecoveryCoordinator` sees local OPEN positions as phantoms -> `safe_mode=True` -> new entries blocked after restart~~ - **FIXED in `27a9270`** (PAPER mode skips exchange consistency checks)
19. **ARCH_DEBT — ProcessManager in-memory state lost on dashboard restart**: `ProcessManager` holds bot PID and start timestamp in-memory only. If `btc-bot-dashboard.service` crashes and restarts, the new ProcessManager instance has no reference to the already-running bot process. Dashboard `/api/status` reports bot as not running and `/api/bot/stop` cannot stop it. Bot continues running unaffected; systemd manages it independently. Fix requires persisting PID + start timestamp to a lockfile or DB entry. Out-of-scope for SERVER-DEPLOY-V2 — requires persistence layer design decision. Workaround: `systemctl stop btc-bot` directly.
20. **GAP — `setup.sh` missing `python3-venv` pre-install**: On fresh Ubuntu 24.04 `python3 -m venv .venv` fails because `python3-venv` package is not installed by default. `setup.sh` should run `apt-get install -y python3-venv` before creating the venv. Low priority — candidate for next deploy tooling milestone.
21. **GAP — Deploy bundle must be regenerated after final push**: `btc-bot.bundle` committed in root repo was stale (pre SERVER-DEPLOY-V2 commits). `SERVER_DEPLOYMENT.md` must include an explicit step: regenerate bundle with `git bundle create btc-bot.bundle --all` immediately after the final push, before SCP to server. Low priority — candidate for next deploy tooling milestone.

## Audit History

| ID | Milestone | Date | Commit | Verdict |
|---|---|---|---|---|
| AUDIT_001 | Recovery Startup Sync | 2026-03-26 | `436756b` | MVP_DONE |
| AUDIT_002 | Phase D - Live Execution + Order Manager | 2026-03-26 | `c5f9408` | MVP_DONE |
| AUDIT_003 | Phase E - Monitoring | 2026-03-26 | `2e31e33` | MVP_DONE |
| AUDIT_004 | Phase F - Orchestration | 2026-03-26 | `09a099f` | MVP_DONE |
| AUDIT_005 | Phase G - Backtest | 2026-03-26 | `26fe3d7` | MVP_DONE |
| AUDIT_006 | Config Injection Bugfix + Phase H Research | 2026-03-26 | `c072405` | MVP_DONE |
| AUDIT_007 | Daily Reset consecutive_losses + Trade Filtering | 2026-03-28 | `0e5f112` | MVP_DONE |
| AUDIT_008 | Paper Trading Validation | 2026-03-29 | `b1fb7f4` | MVP_DONE |
| AUDIT_009 | Fix #18 - PAPER restart phantom_position | 2026-03-29 | `27a9270` | MVP_DONE |
| AUDIT_010 | Tech Debt: CI + pytest + ruff foundation | 2026-03-31 | `86917df` | MVP_DONE |
| AUDIT_011 | Known Issue #2 - FeatureEngine statefulness | 2026-03-31 | `a24e1e3` | MVP_DONE |
| AUDIT_012 | Research Lab v0.1 - architecture + implementation | 2026-03-31 | `aa68c23` | MVP_DONE |
| AUDIT_013 | Research Lab v0.1 - optuna runtime validation | 2026-03-31 | `dfafa26` | MVP_DONE |
| AUDIT_014 | Tech Debt Cleanup (Resumed) - Issues #1 + #7 | 2026-04-01 | `8602727` | MVP_DONE |
| AUDIT_015 | SERVER-DEPLOY-V2 — Hetzner cpx22 production deploy | 2026-04-08 | `713f826` | DONE |
