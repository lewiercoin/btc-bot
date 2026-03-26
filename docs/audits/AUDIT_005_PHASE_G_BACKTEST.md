# AUDIT: Phase G — Backtest

**Date:** 2026-03-26
**Auditor:** Cascade
**Commit:** 26fe3d7
**Scope:** Blueprint §5.9, §13 — `backtest/replay_loader.py`, `backtest/fill_model.py`, `backtest/performance.py`, `backtest/backtest_runner.py`, `scripts/smoke_backtest.py`

## Verdict: MVP_DONE

---

## 1. Deliverable Checklist

| # | Deliverable | Status | Notes |
|---|---|---|---|
| 1 | ReplayLoader — reconstruct MarketSnapshot from SQLite | ✅ DONE | Generator + batch modes, date range filtering, all data sources loaded |
| 2 | FillModel — deterministic fill simulation | ✅ DONE | SimpleFillModel with configurable slippage/fees, LIMIT vs MARKET support |
| 3 | Performance metrics — extended PerformanceReport | ✅ DONE | 12 fields: win_rate, profit_factor, sharpe, max_consecutive_losses, etc. |
| 4 | BacktestRunner — full pipeline replay | ✅ DONE | Same core engines as live, internal state tracking, DB persistence |
| 5 | Smoke tests — smoke_backtest.py | ✅ DONE | 5 scenarios: replay_loader, fill_model, runner, empty dataset, single bar |
| 6 | Issue #2 documented (FeatureEngine warm-up) | ✅ DONE | Docstring in BacktestRunner, fresh instance per run |

## 2. Layer Separation: PASS

- `backtest/` imports ONLY from `core/` and `settings` — **no imports from `execution/`, `data/rest_client`, `data/websocket_client`, or `monitoring/`** ✅
- `replay_loader.py` imports only `core.models.MarketSnapshot` ✅
- `fill_model.py` imports nothing from other project modules ✅
- `performance.py` imports only `core.models.TradeLog` ✅
- `backtest_runner.py` imports from `core/` engines, `backtest/` siblings, and `settings` — all appropriate ✅
- DB persistence in `_persist_closed_trades` uses raw SQL (not `storage/repositories`) — avoids execution→storage coupling ✅

**One architectural note:** `backtest_runner.py` imports `GovernanceRuntimeState` and `RiskRuntimeState` from core engines directly. This mirrors the existing issue #1 (state_store does the same), but is acceptable for backtest since it needs to provide mock state to the engines.

## 3. ReplayLoader: PASS

**Snapshot reconstruction:**
- Iterates 15m candles from DB, computes `snapshot_ts = candle_open_time + 15m` (candle close time) ✅
- Loads lookback candles for 15m/1h/4h with configurable limits ✅
- Loads funding, OI (latest before timestamp), aggtrade buckets (exact match + fallback), force orders (60s window), external bias ✅
- Uses candle close as price/bid/ask proxy (documented limitation for backtest) ✅
- `_as_utc_datetime` handles `str`, `date`, `datetime` inputs with UTC normalization ✅
- Empty data returns empty dict/list/0.0 — no crashes ✅

**Performance concern (WARN):** For each 15m bar, `_load_candles` runs 3 separate SQL queries (15m, 1h, 4h) plus funding, OI, aggtrades, force_orders, bias — **8 queries per bar**. With 6-12 months of data (~17,500-35,000 bars), this is 140k-280k queries. This will be slow but functional for MVP. Consider batch-loading in a future optimization pass.

**15m candle lookback for current bar:**
- `up_to_time=candle_open_time` for 15m candles (line 84) — this means the current bar being processed is included in the lookback since `open_time <= candle_open_time` matches it. The current bar's OHLCV is fully formed (it's from DB history), so this is correct for backtest. ✅

## 4. FillModel: PASS

- `SimpleFillModel` is deterministic ✅
- Direction sign: BUY → +slippage (worse fill = higher price), SELL → -slippage (worse fill = lower price) ✅
- Fee calculation: `filled_price * qty * fee_rate` ✅
- Input validation: rejects non-positive price/qty, invalid order_type/side ✅
- Default fees 0.04% maker/taker — matches Binance futures standard tier ✅
- Base `FillModel` class preserved as abstract interface ✅

## 5. Performance Metrics: PASS

**PerformanceReport fields (12 total):**
- `trades_count`, `expectancy_r`, `pnl_abs`, `pnl_r_sum`, `max_drawdown_pct` (original) ✅
- `win_rate`, `avg_winner_r`, `avg_loser_r`, `profit_factor`, `max_consecutive_losses`, `sharpe_ratio`, `total_fees` (new) ✅

**Edge cases handled:**
- 0 trades → all zeros ✅
- All unclosed trades → treated as 0 trades ✅
- All winners → `profit_factor = inf` ✅
- All losers → `profit_factor = 0.0` ✅
- < 2 trading days → `sharpe_ratio = 0.0` ✅
- Division by zero guards (`max(..., 1e-8)`) throughout ✅

**Sharpe calculation:**
- Groups PnL by `closed_at.date()` → daily returns as % of running equity ✅
- Annualized: `(avg / stdev) * sqrt(365)` ✅
- Uses population variance (`/ len`) not sample variance (`/ (len-1)`) — slightly non-standard but acceptable for MVP

**Drawdown calculation:**
- Peak-to-trough equity drawdown, clamped to [0.0, 1.0] ✅

**`_max_consecutive_losses`:**
- Breakeven trades (pnl_abs == 0) don't reset the loss streak — they're neither counted as losses nor as wins. This means a sequence like [loss, breakeven, loss] counts as 1 consecutive loss, not 2. This is a defensible design choice.

## 6. BacktestRunner: PASS

**Pipeline correctness:**
```
For each 15m snapshot:
  1. Compute runtime state (trades_today, DD, consecutive_losses)
  2. Check exits on open positions (SL/TP/timeout via RiskEngine.evaluate_exit)
  3. Recompute runtime state after closes
  4. Features → Regime → Signal → Governance → Risk → Open position
  5. Record equity curve point
After loop: force-close remaining positions
Persist all trades to DB
Compute PerformanceReport
```

**Key design decisions verified:**
- **Same core engines as live**: FeatureEngine, RegimeEngine, SignalEngine, GovernanceLayer, RiskEngine — all instantiated with same configs from `settings` ✅
- **Fresh FeatureEngine per run**: prevents cross-run deque contamination (issue #2 documented) ✅
- **Internal state tracking**: `_RuntimeState` tracks trades_today, DD, consecutive_losses without DB — fast ✅
- **Governance/Risk state providers**: lambda closures that return `GovernanceRuntimeState`/`RiskRuntimeState` from `_RuntimeState` — clean DI ✅
- **Exit checking uses candle OHLC**: `latest_high`, `latest_low`, `latest_close` from last 15m candle ✅
- **MAE/MFE**: delegated to `risk_engine.build_settlement_metrics` which uses `candles_path` ✅
- **Force close at end**: remaining positions closed at last close price with "END_OF_BACKTEST" reason ✅
- **Net PnL**: `pnl_abs_net = settlement.pnl_abs - fees_total` (entry + exit fees deducted) ✅
- **PnL_R**: computed as `pnl_abs_net / risk_notional` where `risk_notional = |entry - SL| * size` ✅

**Exit priority observation:** The handoff specified "if both SL and TP hit in same bar, assume SL hit first (conservative)." This logic lives in `RiskEngine.evaluate_exit`, not in the backtest runner. The backtest correctly delegates exit decisions to the risk engine — the runner itself doesn't need to implement this. ✅

**`_append_candle` deduplication:**
- Prevents duplicate candle entries in `candles_path` by checking `open_time` — handles cases where the same bar is seen in sequential snapshots ✅

**DB persistence:**
- `_persist_closed_trades` writes to `signal_candidates`, `executable_signals`, `positions`, `trade_log` — full audit trail ✅
- Uses `INSERT OR REPLACE` — safe for re-runs ✅
- Single `conn.commit()` after all records — atomic ✅

## 7. `_compute_runtime_state`: PASS

- `trades_today`: counts entries on same UTC date ✅
- `consecutive_losses`: counts from most recent trade backwards ✅
- `daily_dd_pct` and `weekly_dd_pct`: computed from `closed_pnl_events` within period, using peak-to-trough method ✅
- `_compute_period_drawdown_pct` correctly uses starting equity = initial + all PnL before period start ✅

**Note:** Runtime state is recomputed twice per bar (before and after exits). This mirrors the live orchestrator's pattern. Acceptable for correctness over performance.

## 8. Smoke Test Coverage: PASS

| Test | What it verifies |
|---|---|
| `run_replay_loader_smoke` | 20 bars loaded, correct count, correct timestamp, price matches bid/ask |
| `run_fill_model_smoke` | MARKET BUY/LIMIT SELL fills, exact price and fee calculations |
| `run_backtest_runner_smoke` | Full run completes, PerformanceReport has all fields, equity curve populated, DB persistence matches trade count |
| `run_empty_dataset_smoke` | 0 trades, no crash on empty DB |
| `run_single_bar_smoke` | 1 bar, no crash, equity curve has entries |

**What's not covered (non-blocking for MVP):**
- Actual trade generation (synthetic data may not trigger signals)
- Exit logic (SL/TP hit verification)
- Force close at end of backtest
- Performance report accuracy with known trade outcomes
- Multiple concurrent positions
- Weekly DD calculation

## 9. Determinism: PASS

- No randomness anywhere in backtest code ✅
- FillModel uses static slippage/fee rates ✅
- Core engines are deterministic (per AGENTS.md) ✅
- Same input data → same output guaranteed ✅

## 10. Error Handling: PASS

- FillModel validates inputs (positive price/qty, valid order_type/side) ✅
- ReplayLoader handles missing data gracefully (0.0 for OI, empty dict for agg buckets, None for bias) ✅
- Performance handles 0 trades, all unclosed, all winners/losers ✅
- Division by zero guards throughout (`max(..., 1e-8)`) ✅
- BacktestRunner handles empty snapshots (no bars = empty result) ✅

## 11. Timestamps: PASS

- All timestamps normalized to UTC via `_to_utc()` and `_as_utc_datetime()` ✅
- Naive datetimes treated as UTC (`.replace(tzinfo=timezone.utc)`) ✅
- Period boundaries (day_start, week_start) computed in UTC ✅

## 12. AGENTS.md Compliance: PASS

- Commit message with WHAT/WHY/STATUS ✅
- Core pipeline determinism preserved ✅
- No cross-import shortcuts (backtest doesn't import execution or data layers) ✅
- Backtest completely separated from live ✅
- Issue #2 acknowledged and documented ✅

---

## Critical Issues (must fix before next milestone)

*None.*

## Warnings (fix soon)

1. **ReplayLoader N+1 query pattern**: 8 SQL queries per 15m bar. With 6-12 months data (~17,500-35,000 bars), this means 140k-280k queries. Functional but slow. Consider batch-loading candles/funding/OI for the entire date range upfront and indexing in memory.

2. **Sharpe uses population variance**: `_daily_sharpe_ratio` divides by `len(daily_returns)` instead of `len(daily_returns) - 1` (sample variance). Minor statistical difference with large N, but non-standard.

3. **Breakeven trades in `_max_consecutive_losses`**: Trades with `pnl_abs == 0` don't reset loss streaks but aren't counted as losses either. This creates a gap: `[loss, BE, loss]` = 1 consecutive loss. Documented behavior, not a bug, but may differ from live `_compute_consecutive_losses` in `state_store.py`.

## Observations (non-blocking)

1. `BacktestRunner` calls `signal_engine.generate(features, regime)` — correctly matches the live `SignalEngine.generate` signature (not `evaluate` as in the handoff typo).

2. `_persist_closed_trades` uses raw SQL instead of repository functions — this avoids the execution→storage layer leak (issue #4) but means schema changes must be updated in two places. Acceptable trade-off for layer purity.

3. `ReplayBatch` dataclass changed from `records: list[dict]` to `snapshots: list[MarketSnapshot]` — proper typing improvement over the original stub.

4. `backtest_runner.py` is 729 lines — the largest single module in the project. The internal helper functions (`_consecutive_losses`, `_compute_period_drawdown_pct`, `_append_candle`, etc.) could be extracted to a `backtest/utils.py` if the module grows further, but this is acceptable for MVP.

5. Equity curve records one point per bar (after exits + potential entry). Force-close at end adds a final point. This captures intra-run equity progression adequately.

## Recommended Next Step

Phase H — research (`analyze_trades.py`, `llm_post_trade_review.py`). This is the final implementation phase. After H, the system will be feature-complete per blueprint §12. The DoD (§13) can then be pursued: backtest on 6-12 months historical data, paper trading for 30 days / 40-60 trades.
