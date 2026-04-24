# AUDIT: Trade Lifecycle / PnL Accounting
Date: 2026-04-24
Auditor: Claude Code
Commit: 2be7a8c

## Verdict: MVP_DONE

## Trade Completeness: PASS
## PnL Calculation Integrity: PASS
## Commission Accounting: WARN
## Funding Fee Accounting: FAIL
## Unclosed Position Detection: PASS
## Double-Counting Prevention: PASS
## PnL Waterfall Auditability: WARN

## Findings

### Evidence reviewed
- `storage/schema.sql` — `trade_log`, `positions`, `executions` tables
- `storage/position_persister.py` — position and execution persistence
- `storage/repositories.py` — DB insertion logic
- `backtest/backtest_runner.py` — PnL calculation in backtest
- `backtest/fill_model.py` — fee and slippage model
- Production read-only evidence:
  - Unclosed positions query: 0 positions older than 24h
  - PnL reconciliation query: 20 recent trades with calculated raw_pnl vs stored pnl_abs
  - All paper trades (trd-*) show `fees_total = 0.0`
  - All backtest trades (bt-trd-*) show non-zero `fees_total` (range 42-53 USD)

### Assessment summary
- **Trade lifecycle is complete.** Every trade has entry_price, exit_price, opened_at, closed_at. Zero unclosed positions older than 24h.
- **PnL calculation is mathematically correct.** For all 20 sampled trades: `raw_pnl = (exit_price - entry_price) * size * direction` matches `pnl_abs` exactly when `fees_total = 0`, and matches `pnl_abs + fees_total` when fees exist.
- **Commission accounting exists in backtest but NOT in paper runtime.** Backtest trades use `SimpleFillModel` with `fee_rate_maker=0.0004`, `fee_rate_taker=0.0004`. Paper trades show `fees_total=0.0` universally.
- **Funding fees are NOT tracked anywhere.** Schema has no `funding_paid` column in `trade_log`. Binance perpetual futures charge funding fees every 8 hours. These are real costs not captured in PnL.
- **No double-counting detected.** Each `trade_id` appears once in the sample.
- **PnL waterfall is partially auditable.** `pnl_abs` = gross PnL - `fees_total`, but `fees_total` is a single lumped value with no breakdown (entry fee, exit fee, partial exit fees).

## Critical Issues (must fix before next milestone)
- **Funding fees are not accounted for in PnL calculation.** Binance perpetual futures funding rate is applied every 8 hours to open positions. For a multi-day LONG position during positive funding (longs pay shorts), this can be -0.01% to -0.03% per 8h, compounding to material cost. Schema has no `funding_paid` column; backtest does not simulate funding; paper runtime does not track it.
- **Paper runtime charges zero fees.** `PaperExecutionEngine` writes `fees=0.0` to executions table. This creates paper-vs-backtest methodology drift and overstates paper PnL relative to realistic trading costs.

## Warnings (fix soon)
- **Fee breakdown is not granular.** `trade_log.fees_total` is a single aggregate. For trades with partial exits (TP1 hit, then TP2 or SL), the audit trail cannot decompose which execution contributed which fee amount.
- **Executions table exists but is not fully utilized for PnL reconstruction.** Each execution has `fees`, but `trade_log` only stores `fees_total`. Post-trade forensics cannot reconstruct fee waterfall from execution level up.

## Observations (non-blocking)
- **Backtest PnL accounting is production-grade within its scope.** `SimpleFillModel` applies deterministic slippage and fees. PnL calculation in `backtest_runner.py` lines 518-553 properly deducts fees: `pnl_abs_net = total_gross_pnl_abs - fees_total`.
- **Trade schema supports rich audit metadata.** `trade_log` includes `mae`, `mfe`, `exit_reason`, `features_at_entry_json`, `config_hash`. This is excellent for post-trade analysis.
- **Production sample shows realistic slippage values.** Sample trades show `slippage_bps_avg` ranging from 12.4 to 423 bps, indicating execution realism modeling is active (though AUDIT-07 found paper fills are not realistic).

## Recommended Next Step
After Phase 0 audits complete, add funding fee tracking: (1) persist funding rate snapshots at position open/close times, (2) calculate cumulative funding cost for multi-period positions, (3) store `funding_paid` separately in `trade_log`, (4) deduct from `pnl_abs`. Also add fee breakdown to execution-level audit trail and reinstate realistic fee charges in paper runtime.
