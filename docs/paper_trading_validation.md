# Paper Trading Validation (Binance LIVE data)

Date: 2026-03-28  
Mode: PAPER  
Symbol config: `BTCUSDT`

## Scope executed

1. Fixed issue #17 (`PaperExecutionEngine` symbol hardcode) and wired symbol from orchestrator config.
2. Ran live PAPER runtime against Binance futures websocket/REST.
3. Validated 15m decision boundary behavior.
4. Validated signal path outcomes:
   - branch with generated candidate and executed paper position,
   - branch with `No signal candidate`.
5. Validated cadence behavior (`position_monitor` 15s, `health_check` 30s).
6. Validated restart persistence behavior with open position present.
7. Validated signal-handler-driven graceful stop path (`SIGINT`, `SIGTERM`).

## Code changes

1. `execution/paper_execution_engine.py`
   - `__init__` now accepts `symbol: str` (keyword arg).
   - engine persists `self.symbol` (uppercased) instead of hardcoded `"BTCUSDT"`.

2. `orchestrator.py`
   - paper engine is now created with:
     - `symbol=settings.strategy.symbol.upper()`

## Validation evidence

## 1) Live startup + data connectivity (`scripts/run_paper.py`)

Evidence:
- websocket connected to Binance futures stream:
  - `Connected websocket stream: wss://fstream.binance.com/stream?streams=btcusdt@aggTrade/btcusdt@forceOrder`
- startup sequence present:
  - bot start, feed start, runtime loop start.

Artifacts:
- `logs/paper_validation/live_cycle_probe.stdout.log`
- `logs/paper_validation/validation_report.json` (run1)

## 2) 15m decision cycle

Observed in DB `alerts_errors`:
- `2026-03-28T22:15:01.700872+00:00` -> `decision::No signal candidate.`
- earlier run observed generated candidates at 15m boundary:
  - `2026-03-28T22:00:01.875628+00:00` -> `decision::Signal candidate generated.`
  - `2026-03-28T22:00:02.275393+00:00` -> `decision::Signal candidate generated.`

Artifacts:
- `logs/paper_validation/live_cycle_probe.stdout.log`
- `logs/paper_validation/validation_report.json`

## 3) Feature/Signal/Governance/Risk/Execution path

Observed:
- SignalEngine branch `None` confirmed (`No signal candidate`).
- Candidate branch confirmed (`Signal candidate generated`).
- Governance veto branch confirmed:
  - `governance::Candidate rejected by governance.`
- Risk allow branch inferred by successful execution path (position inserted):
  - `signal_candidates=2`, `executable_signals=1`, `positions=1`, `trade_log=1` (run1 snapshot).

Artifacts:
- `logs/paper_validation/validation_report.json`

## 4) Position symbol correctness (fix #17)

Direct engine probe with non-default symbol:
- `PaperExecutionEngine(connection=..., symbol="ethusdt")`
- inserted row symbol: `ETHUSDT`

This confirms symbol is no longer hardcoded in paper execution.

Probe result:
- `{'inserted_symbol': 'ETHUSDT'}`

## 5) Position monitor and health cadence

Instrumented live orchestrator runtime produced:
- `monitor_calls=5` with intervals:
  - `[15.016706, 15.325208, 15.03054, 15.271248]` seconds
- `health_calls=3` with intervals:
  - `[30.016405, 30.016803]` seconds

Result: cadence matches configured 15s / 30s.

Recorded output:
- `monitor_calls=5`, `health_calls=3`
- monitor intervals: `[15.016706, 15.325208, 15.03054, 15.271248]`
- health intervals: `[30.016405, 30.016803]`

## 6) State persistence + restart behavior

Restart probe with one seeded OPEN position:
- before: `['paper-rst-a9f6a9f207d9']`
- after run1: `['paper-rst-a9f6a9f207d9']`
- after restart/run2: `['paper-rst-a9f6a9f207d9']`
- duplicate IDs: none
- `bot_state` persisted and updated timestamps across restarts.

Result:
- open position survives restart,
- no duplicate positions created.

Recorded output:
- `seeded_survived_restart=True`
- `duplicates_found=[]`

## 7) Graceful shutdown handlers (`SIGINT` / `SIGTERM`)

In-process probe using `main.install_signal_handlers` and runtime orchestrator:
- both signals triggered stop flow:
  - `orchestrator::Stop requested.`
  - `orchestrator::Runtime loop stopped.`
- console logs:
  - `Received signal 2. Initiating graceful shutdown.`
  - `Received signal 15. Initiating graceful shutdown.`

Result: handler path is wired and performs clean stop sequence.

Recorded output:
- `contains_stop_requested=True` and `contains_runtime_stopped=True` for both `SIGINT` and `SIGTERM`.

## Issues found during validation

1. PAPER restart with local OPEN positions enters safe mode (`phantom_position`) because paper recovery uses `NoOpRecoverySyncSource` (no exchange positions).
   - Observed:
     - `recovery_inconsistency:phantom_position`
     - `safe_mode=1`, new entries blocked.
   - Impact:
     - Existing positions remain recoverable/monitorable, but new trading is blocked after restart when local open positions exist.

2. In this non-interactive subprocess harness, external termination produced process exit code `1` and did not emit graceful-stop logs in child stdout.
   - Dedicated in-process signal probe confirms handler logic itself is correct.

## Readiness assessment for extended paper run

Current status: **conditionally ready** with one operational caveat.

What works:
- live data connectivity,
- decision cycle scheduling,
- signal branches (candidate and none),
- governance/risk/execution path observed,
- symbol injection fix (#17),
- persistence and duplicate protection checks,
- signal handler stop path.

Caveat to resolve before unattended extended run:
- restart with local open PAPER positions currently forces safe mode (`phantom_position`) and blocks new entries until manual intervention or logic adjustment.
