# AUDIT: Risk Engine
Date: 2026-04-24
Auditor: Claude Code
Commit: 9f00457

## Verdict: DONE

## Position Sizing Logic: PASS
## Drawdown Limit Enforcement: PASS
## Leverage Selection: PASS
## Exit Logic (TP/SL/Timeout): PASS
## PnL/MAE/MFE Calculation: PASS
## State Provider Pattern: PASS

## Findings

### Evidence reviewed
- `core/risk_engine.py` — complete risk engine implementation (234 lines)
- `core/models.py` — `RiskRuntimeState`, `ExecutableSignal`, `Position`, `SettlementMetrics` contracts
- `backtest/backtest_runner.py` — risk engine usage in backtest
- `tests/test_signal_engine.py`, `tests/test_feature_engine.py` — indirect risk engine testing
- Production evidence: `MILESTONE_TRACKER.md` references to risk limits (daily_dd_limit=0.20, weekly_dd_limit=0.30 in tuning phase)

### Assessment summary
- **Position sizing is mathematically correct.** Formula: `size = min(risk_capital / stop_distance, equity * leverage / entry_price)`. Respects both risk budget and leverage constraint.
- **Drawdown limits are enforced.** `evaluate()` checks `daily_dd_pct >= daily_dd_limit` and `weekly_dd_pct >= weekly_dd_limit` before allowing new positions. Returns `RiskDecision(False, reason="daily_dd_limit")` on breach.
- **Leverage selection is dynamic.** High-volatility positions (stop_distance_pct >= 0.01) get `high_vol_leverage` (default 3). Otherwise `max_leverage` (default 5).
- **Exit logic is comprehensive.** `evaluate_exit()` handles: stop loss, take profit (TP1), partial exits, trailing stops, timeout (max_hold_hours). Conservative ordering: SL before TP on ambiguous candles.
- **PnL calculation is correct.** `_compute_pnl_abs()`: `(exit_price - entry_price) * size * direction_multiplier`. `_compute_pnl_r()`: `pnl_abs / risk_notional`. MAE/MFE computed from candle extremes.
- **State provider pattern enables testing.** Risk engine accepts `state_provider: Callable[[], RiskRuntimeState]`, allowing backtest to inject synthetic state without DB dependency.

## Critical Issues (must fix before next milestone)
None identified. Risk engine logic is production-grade.

## Warnings (fix soon)
- **No explicit position size sanity check.** `evaluate()` returns `RiskDecision(False, reason="non_positive_size")` if `size <= 0`, but no upper bound check (e.g., size > 10 BTC). Unlikely but worth adding.
- **Leverage calculation assumes entry_price > 0.** Uses `max(signal.entry_price, 1e-8)` to prevent division by zero, but does not explicitly validate `entry_price > 0` before calculation.

## Observations (non-blocking)
- **Risk per trade is configurable.** Default `risk_per_trade_pct=0.01` (1% of equity). Production tuning uses relaxed limits for paper trading validation.
- **Partial exit logic is well-implemented.** `evaluate_exit()` supports partial TP at 50% size, then trailing stop for remaining 50%. Exit reasons: `TP_PARTIAL`, `TP_TRAIL`, `SL`, `TP`, `TIMEOUT`.
- **Timeout protection exists.** `max_hold_hours=24` default prevents positions from being held indefinitely. Exit at `latest_close` on timeout.
- **Conservative SL ordering.** On candles where `latest_low <= stop_loss` AND `latest_high >= take_profit_1`, SL is triggered (not TP). This prevents overly optimistic PnL in backtest.
- **MAE/MFE calculation traverses full candle path.** `_compute_mae_mfe()` iterates `candles_15m` from entry to exit, tracking min/max price excursion. This is accurate for intra-trade drawdown analysis.
- **No race conditions.** Risk engine is stateless except for `state_provider` callback. No internal mutable state, no thread-safety issues.

## Recommended Next Step
Risk engine is production-ready. Optional: add upper bound check on position size (e.g., `size > 0.5 * equity` → warning) to catch extreme edge cases. Current implementation is sound.
