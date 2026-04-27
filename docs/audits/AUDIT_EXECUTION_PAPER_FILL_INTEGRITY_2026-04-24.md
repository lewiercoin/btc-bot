# AUDIT: Execution / Paper Fill Integrity
Date: 2026-04-24
Auditor: Cascade (Builder Mode)
Commit: 5712fbd

## Verdict: NOT_DONE

## Fill Realism (Latency): FAIL
## Fill Price Realism (Spread): FAIL
## Slippage Model: FAIL
## Partial Fill Simulation: FAIL
## Paper-Live Gap Risk: HIGH
## Execution Audit Trail: PASS

## Findings

### Evidence reviewed
- `execution/paper_execution_engine.py`
- `execution/live_execution_engine.py`
- `execution/order_manager.py`
- `execution/execution_engine.py`
- `orchestrator.py`
- `storage/schema.sql`
- `storage/position_persister.py`
- `core/execution_types.py`
- `backtest/fill_model.py`
- `backtest/backtest_runner.py`
- `tests/test_paper_fill_fix.py`
- `scripts/smoke_live_execution.py`
- Production read-only evidence:
  - `executions` sample rows
  - `market_snapshots` sample rows
  - deployed bot service showing `PAPER` mode

### Assessment summary
- Paper runtime has an execution audit trail: positions and fill events are persisted with `requested_price`, `filled_price`, `slippage_bps`, `qty`, and `executed_at`.
- Paper fill realism is still inadequate for live-readiness purposes.
- `PaperExecutionEngine` always writes a fully-filled market execution with:
  - `filled_price = snapshot_price`
  - `fees = 0.0`
  - `status = FILLED`
  - full `qty`
  - no order book, no spread logic, no queueing, no rejection path, no partial-fill path
- `orchestrator.py` passes `snapshot.price` from the decision cycle into the paper engine. This means the recorded `fill_ts` can be later than the signal timestamp while the paper fill price still comes from the decision snapshot rather than a later market price.
- Production sample timings from `executions` showed non-zero `signal_ts -> fill_ts` delays (`1.698s` to `5.534s` across the sampled rows), but those delays do not imply realistic broker/exchange simulation because price formation is still anchored to the decision-cycle snapshot.
- Recent `market_snapshots` rows store `bid_price` and `ask_price`, but executions do not link to a snapshot/book record, so spread-at-fill cannot be reconstructed directly from the execution audit trail.
- Backtest path already has a deterministic slippage/fee model (`SimpleFillModel`), but paper runtime does not reuse an equivalent realism model.

## Critical Issues (must fix before next milestone)
- Paper execution price formation is not realistic. The engine fills at `snapshot.price` with no bid/ask spread handling, no book-side selection, and no time-aligned repricing despite observed signal-to-fill delay.
- There is no explicit slippage model in paper runtime. `slippage_bps` is only a bookkeeping delta between `signal.entry_price` and the passed snapshot price, not a simulated market-impact or spread-cost model.
- Partial fills are not simulated in paper runtime at all. Every paper execution is recorded as immediately `FILLED` for full size.
- Execution records are not linked to the source `market_snapshot`, so per-fill spread validation and post-trade replay of exact execution conditions are incomplete.

## Warnings (fix soon)
- Paper runtime charges zero fees, while backtest `SimpleFillModel` applies static maker/taker fees. This creates paper-vs-backtest methodology drift.
- Live execution supports polling, partial fills, and order-state transitions; paper runtime bypasses these behaviors entirely, increasing paper-to-live gap risk.
- Production sample slippage values were materially non-zero (`12.417` bps to `423.087` bps), but the current audit trail cannot decompose how much came from snapshot drift, reference-price mismatch, or missing spread logic.

## Observations (non-blocking)
- `tests/test_paper_fill_fix.py` verifies that paper execution uses `snapshot_price`, persists execution rows, and exposes signal reference vs fill entry in the dashboard.
- `scripts/smoke_live_execution.py` demonstrates that live-path support for partial fills and multiple execution events exists in the codebase.
- Recent production `market_snapshots` sampled during the audit contained both `bid_price` and `ask_price` (for example `78257.2 / 78257.3`), so the repo already persists enough market microstructure data to support a future paper-fill realism upgrade.

## Recommended Next Step
After Phase 0 audits complete, implement a paper execution realism layer that uses persisted bid/ask data, explicit latency rules, fees, and partial-fill/timeout behavior, and link each execution record to its originating `market_snapshot` for replay-grade auditability.
