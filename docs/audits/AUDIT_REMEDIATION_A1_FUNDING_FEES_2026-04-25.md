# AUDIT: REMEDIATION-A1-FUNDING-FEES
Date: 2026-04-25
Auditor: Claude Code
Builder: Codex
Commit: 40a9338

## Verdict: DONE

## Schema Migration: PASS
## Funding Calculation Logic: PASS
## Backtest Integration: PASS
## Paper Runtime Integration: PASS
## PnL Accounting: PASS
## Test Coverage: PASS
## Production Readiness: PASS

## Findings

### Evidence reviewed
- `storage/schema.sql` — `funding_paid REAL NOT NULL DEFAULT 0` added to `trade_log` table
- `storage/migrations/add_trade_log_funding_paid.sql` — clean ALTER TABLE migration (2 lines)
- `core/funding.py` — deterministic funding calculator shared by backtest and paper runtime (74 lines)
- `backtest/fill_model.py` — `FillModel.calculate_funding()` interface + `SimpleFillModel` implementation
- `backtest/backtest_runner.py` — incremental funding accrual via `_accrue_funding()`, PnL deduction: `pnl_abs_net = gross_pnl - fees - funding_paid`
- `orchestrator.py` — paper runtime funding calculation via `_compute_position_funding_paid()`, deducts from PnL before settlement
- `storage/state_store.py` — auto-migration (detects missing column, applies ALTER TABLE safely), persists `funding_paid` in `settle_trade_close()`
- `storage/repositories.py` — `fetch_funding_rates()` queries production `funding` table (6,164 BTCUSDT samples, 2020-09-01 to 2026-04-17)
- `core/models.py` — `SettlementMetrics.funding_paid: float = 0.0` added
- `tests/test_funding_fees.py` — comprehensive test coverage (499 lines, 5 tests, all passing)
- Production validation: `funding` table exists with 6,164 historical samples for BTCUSDT

### Assessment summary
- **Schema migration is production-safe.** ALTER TABLE with NOT NULL DEFAULT 0.0 applies safely to existing rows. Auto-migration in `StateStore` detects missing column and applies migration on startup.
- **Funding calculation is deterministic and direction-aware.** `core/funding.py` implements: `notional * sum(funding_rates) * direction_multiplier`. LONG pays positive rate, SHORT receives (negative multiplier). Only counts funding events where `opened_at < funding_time <= closed_at`.
- **Backtest integration is comprehensive.** Incremental funding accrual via `_accrue_funding()` called every snapshot. Tracks `last_funding_accrual_at` to avoid double-counting. Handles multi-period positions and partial exits correctly. Final PnL: `pnl_abs_net = gross_pnl - fees - funding_paid` (line 535, 668).
- **Paper runtime integration is correct.** Orchestrator computes funding at position close via `_compute_position_funding_paid()`. Fetches funding rates from DB via `fetch_funding_rates()`. Deducts from PnL before settlement: `settlement = replace(settlement, pnl_abs=settlement.pnl_abs - funding_paid, funding_paid=funding_paid)`.
- **Backtest-paper parity maintained.** Both backtest and paper runtime use same `core.funding.compute_funding_paid()` utility. Same deterministic calculation, no drift risk.
- **Production data available.** `funding` table has 6,164 BTCUSDT samples (2020-09-01 to 2026-04-17). Sufficient for historical backtest and ongoing paper runtime.
- **Test coverage excellent.** 5 focused tests covering: directional calculation, schema migration, backtest integration, paper runtime integration, persistence. All 5 passing. Codex also ran 38 additional tests (all passing).
- **All acceptance criteria met:**
  - ✅ `trade_log` schema has `funding_paid REAL NOT NULL DEFAULT 0.0` column
  - ✅ Backtest fills include funding simulation (via `_accrue_funding()` + `fill_model.calculate_funding()`)
  - ✅ Paper runtime tracks funding (via `_compute_position_funding_paid()` + `fetch_funding_rates()`)
  - ✅ PnL calculation includes funding deduction: `pnl_abs_net = gross_pnl - fees - funding`
  - ✅ Existing trades migrated safely (auto-migration with DEFAULT 0.0)
  - ✅ Tests pass (43 total: 5 funding-specific + 38 regression)
  - ✅ Backtest-paper parity maintained (shared `compute_funding_paid()` utility)

## Critical Issues (must fix before next milestone)
None identified. Funding fee tracking is production-ready.

## Warnings (fix soon)
- **Missing funding data for recent period.** Last funding sample: 2026-04-17 08:00. Current date: 2026-04-25. 8-day gap in funding data. Paper runtime will compute zero funding for positions opened/closed after 2026-04-17. Impact: Paper PnL slightly overstated for recent trades until funding data backfill completes.
- **Funding fetch failure is silent.** `fetch_funding_rates()` returns empty list if `funding` table missing or query fails. No warning logged. Paper runtime will compute zero funding without alerting operator. Recommend: add warning log if funding fetch returns empty for non-zero time window.

## Observations (non-blocking)
- **Incremental accrual is efficient.** Backtest calls `_accrue_funding()` every snapshot, but only computes funding for delta period (`last_funding_accrual_at` to `accrued_until`). Avoids recomputing full position history every tick.
- **Direction multiplier is correct.** LONG positions pay positive funding rate (cost), SHORT positions receive positive funding rate (income). Matches Binance perpetual futures convention.
- **UTC normalization is robust.** `core/funding.py` handles timezone-naive and timezone-aware datetimes via `_to_utc()` helper. Prevents timestamp comparison bugs.
- **Partial exits handled correctly.** Backtest tracks `funding_paid` at position level (not per partial exit). Final settlement deducts total accumulated funding from net PnL. This is correct: funding accrues on full position until fully closed.
- **Migration is idempotent.** `StateStore` checks `PRAGMA table_info(trade_log)` before applying migration. Safe to run multiple times.
- **Tests use `SimpleFillModel`.** Real backtest may use different fill model, but all must implement `calculate_funding()` interface. `SimpleFillModel` implementation delegates to `compute_funding_paid()`, which is correct.
- **Funding samples sorted.** `normalize_funding_samples()` sorts by `funding_time` ASC. Ensures deterministic ordering even if DB query returns unsorted rows.
- **Zero-notional guard exists.** `compute_funding_paid()` returns 0.0 if `notional <= 0`. Prevents division-by-zero or negative-notional edge cases.

## Recommended Next Step
REMEDIATION-A1-FUNDING-FEES is DONE. Push immediately. Next milestone: **REMEDIATION-A2-PAPER-EXECUTION-REALISM** (add fees, spread, partial fills to paper runtime).

**Post-push action:** Backfill missing funding data (2026-04-17 to 2026-04-25) to avoid zero-funding gap for recent paper trades.
