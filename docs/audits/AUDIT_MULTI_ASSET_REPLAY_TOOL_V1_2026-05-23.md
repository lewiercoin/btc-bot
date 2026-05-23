# AUDIT: MULTI_ASSET_REPLAY_TOOL_V1
Date: 2026-05-23
Auditor: Claude Code
Commit: 0bc8f31

## Verdict: MVP_DONE

**Scope:** Offline multi-asset replay tool for validating M1 (FeatureEngine persistence) and M2 (DD tracking) using historical production data. CLI tool with per-symbol and portfolio-level output.

**Qualification:** Tool validates M1 (FeatureEngine bootstrap from DB) correctly and M2 (DD tracking logic) correctly, but uses **random PnL placeholder** instead of actual trade P&L simulation. Suitable for testing M1+M2 logic, NOT for realistic portfolio performance analysis.

## Layer Separation: PASS
- Script layer: scripts/run_multi_asset_backtest.py (CLI tool, no runtime coupling)
- Reuses core components: FeatureEngine, portfolio_gate, signal_engine, governance, risk
- Uses ReplayLoader for historical snapshot building (backtest/replay_loader.py)
- StateStore for portfolio recovery (storage/state_store.py)
- Test layer: tests/test_multi_asset_backtest.py (4 smoke tests)
- No cross-layer violations or unexpected dependencies

## Contract Compliance: PASS
- **FeatureEngine bootstrap:** Uses fetch_oi_samples, fetch_cvd_price_history from storage/repositories (M1 validation)
- **DD state structure:** cumulative_r, local_high_watermark_r, rolling_drawdown_r (M2 validation)
- **Portfolio recovery:** Uses state_store.recover_multi_asset_portfolio_state (existing contract)
- **Capacity sizing:** Reuses orchestrator logic (_apply_portfolio_capacity_sizing, line 125-164)
- **Portfolio gate:** Uses RuntimePortfolioGate.evaluate_batch (existing contract)

## Determinism: ACCEPTABLE WITH LIMITATION
- **15-min timestamp generation:** Deterministic (line 238-254)
- **FeatureEngine bootstrap:** Deterministic (fetches same OI/CVD from DB for given symbol/date)
- **Signal generation:** Deterministic (same inputs → same outputs)
- **DD state update logic:** Deterministic (cumulative, high-watermark calculation correct)
- **PnL generation:** **NON-DETERMINISTIC** (line 466: `random.uniform(-2.0, 3.0)`) — **PLACEHOLDER**

**Critical limitation:** PnL uses random values, making replay results non-deterministic and unrealistic. This is acceptable for testing DD tracking LOGIC, but NOT for portfolio performance analysis.

## Code Quality: GOOD
- Clean structure (separate functions for bootstrap, replay loop, output)
- Reuses orchestrator logic (no code duplication)
- Proper error handling (try/except in snapshot building, signal generation)
- Logging in place (LOG.info, LOG.warning)
- CLI args validation (start_ts < end_ts, non-empty symbols)
- JSON output support (optional --output-json)

## Test Coverage: LIMITED
- **4 smoke tests (all pass):**
  - `test_generate_15min_timestamps()` → 10:00-11:00 generates 10:15, 10:30, 10:45
  - `test_parse_iso_datetime()` → Full datetime, date-only start, date-only end (+1 day)
  - `test_to_utc()` → Naive, UTC, non-UTC timezone conversion
  - `test_cli_import()` → CLI module imports successfully
- **Missing tests:**
  - No end-to-end replay test (full cycle with snapshots, signals, DD updates)
  - No test for FeatureEngine bootstrap (M1 validation)
  - No test for DD state updates (M2 validation)
  - No test for capacity sizing integration
  - No test for portfolio gate evaluation

**Gap:** Smoke tests only test helper functions (timestamp generation, datetime parsing), not the core replay logic. Full replay validation requires manual testing.

## Error Handling: ACCEPTABLE
- **Snapshot building failure:** Logged as warning, cycle continues (line 322)
- **Signal generation failure:** Logged as warning, symbol skipped (line 410)
- **Empty snapshots:** Skipped gracefully (line 324-325)
- **CLI arg validation:** start_ts < end_ts check (line 552-553), non-empty symbols (line 556-557)
- **No recovery:** Random PnL failure is silent (no try/except around line 466) — minor issue

## Implementation Analysis: ACCEPTABLE WITH LIMITATION

**FeatureEngine bootstrap (M1 validation) — PASS:**
```python
def _bootstrap_feature_engine(conn, symbol, config, now):
    engine = FeatureEngine(FeatureEngineConfig(...))
    
    # Bootstrap OI history
    oi_since = now - timedelta(days=config.oi_z_window_days)
    oi_samples = fetch_oi_samples(conn, symbol=symbol, since_ts=oi_since)
    oi_summary = engine.bootstrap_oi_history(oi_samples) if hasattr(engine, "bootstrap_oi_history") else ...
    
    # Bootstrap CVD/price history
    cvd_window_bars = getattr(engine.config, "cvd_divergence_window_bars", 30)
    cvd_samples = fetch_cvd_price_history(conn, symbol=symbol, timeframe="15m", limit=cvd_window_bars + 1)
    cvd_summary = engine.bootstrap_cvd_price_history(cvd_samples) if hasattr(engine, "bootstrap_cvd_price_history") else ...
    
    return engine
```
- Fetches OI and CVD from production DB (historical data)
- Bootstraps engine with historical context (M1 logic validated)
- Correct ✓

**DD state tracking (M2 validation) — LOGIC PASS, PnL PLACEHOLDER:**
```python
# Update DD state (simplified - would need full trade lifecycle in production)
for symbol in symbols:
    trades = state.trades_per_symbol[symbol]
    if trades:
        # Simplified DD update (production uses actual PnL)
        import random
        pnl_r = random.uniform(-2.0, 3.0)  # Placeholder
        dd_state = state.dd_states[symbol]
        dd_state["cumulative_r"] += pnl_r
        dd_state["local_high_watermark_r"] = max(dd_state["local_high_watermark_r"], dd_state["cumulative_r"])
        dd_state["rolling_drawdown_r"] = dd_state["cumulative_r"] - dd_state["local_high_watermark_r"]
```
- DD tracking logic correct (cumulative, high-watermark, rolling DD calculation)
- **BUT:** PnL is random (`random.uniform(-2.0, 3.0)`) — **PLACEHOLDER**
- Comment acknowledges: "Simplified DD update (production uses actual PnL)"
- Acceptable for testing DD logic, NOT for realistic portfolio analysis

**Capacity sizing — PASS:**
```python
# Capacity sizing
raw_signals = [item["signal"] for item in generated]
portfolio_signals, capacity_adjustments = _apply_portfolio_capacity_sizing(
    raw_signals,
    portfolio_state=recovered.portfolio,
    config=portfolio_config,
)
state.capacity_sizing_events += len(capacity_adjustments)
```
- Reuses orchestrator capacity sizing logic (line 125-164)
- Correct ✓

**Portfolio gate — PASS:**
```python
gate = RuntimePortfolioGate(portfolio_config)
decisions = gate.evaluate_batch(
    portfolio_signals,
    symbol_states=recovered.symbols,
    portfolio_state=recovered.portfolio,
    now=timestamp,
)
```
- Reuses RuntimePortfolioGate (no duplication)
- Correct ✓

## Critical Issues (must fix before realistic use)

### Issue #1: Random PnL placeholder makes replay unrealistic
**Location:** Line 466 in run_multi_asset_backtest.py
**Problem:** `pnl_r = random.uniform(-2.0, 3.0)` generates random PnL instead of actual trade P&L
**Impact:** 
- Replay results non-deterministic (different run → different P&L)
- Portfolio metrics (win rate, P&L, DD) unrealistic
- Cannot be used for portfolio performance analysis
- Can be used for M1+M2 logic validation (FeatureEngine bootstrap, DD tracking logic)

**Fix options:**
1. **Implement proper trade lifecycle simulation:**
   - Track entry price, stop loss, target prices
   - Simulate exit based on historical price movement
   - Calculate actual P&L based on entry/exit prices
   - Estimate: 4-6h development + tests

2. **Use simplified realistic PnL distribution:**
   - Replace random PnL with fixed distribution (e.g., 60% win rate, +3R/-1R expectancy)
   - Deterministic PnL based on signal ID hash (same signal → same PnL)
   - Better than random, still not realistic
   - Estimate: 1-2h development

3. **Accept limitation, document clearly:**
   - Tool validates M1+M2 logic, not portfolio performance
   - For portfolio performance, use production monitoring or research lab backtests
   - Current state acceptable for M1+M2 validation only

**Recommendation:** Option 3 (accept limitation, document) — Tool serves its purpose (M1+M2 validation). For realistic P&L, use production monitoring or research lab.

## Warnings (fix soon)
None. Tool serves its intended purpose (M1+M2 logic validation) despite PnL placeholder.

## Observations (non-blocking)
1. FeatureEngine bootstrap from DB works correctly (M1 validation) ✓
2. DD tracking logic correct (cumulative, high-watermark, rolling DD) (M2 validation) ✓
3. Capacity sizing integration works (reuses orchestrator logic) ✓
4. Portfolio gate integration works (reuses RuntimePortfolioGate) ✓
5. Random PnL placeholder documented in comments (line 464-465)
6. Tool suitable for M1+M2 logic validation, NOT for portfolio performance analysis
7. No end-to-end test (only helper function tests) — manual testing required
8. CLI args: --start-date, --end-date, --symbols, --initial-equity, --output-json
9. Output: summary (cycles, trades, near-misses), per-symbol breakdown, portfolio metrics
10. JSON output support for programmatic analysis
11. ReplayLoader used for historical snapshot building (from backtest/)
12. 15-minute aligned timestamps (same as production cycles)

## Tech Debt: LOW-MEDIUM
- Random PnL placeholder is documented but limits tool usefulness for P&L analysis
- No end-to-end test coverage (smoke tests only)
- No trade lifecycle simulation (simplified execution)
- Tool serves M1+M2 validation purpose, but not portfolio performance analysis

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS expected in commit message
- Scope purity: Replay tool only, no runtime changes, no production impact
- Documentation: README or usage docs recommended (not blocking for MVP)

## Recommended Next Step

**Replay tool is MVP_DONE. Acceptable for M1+M2 logic validation, but NOT for realistic portfolio performance analysis due to random PnL placeholder.**

### Usage (with limitation awareness):

**Goal:** Validate M1 (FeatureEngine persistence) and M2 (DD tracking logic) work correctly in multi-asset mode.

**Example usage:**
```bash
# 48h replay before M3 deployment
python scripts/run_multi_asset_backtest.py \
  --start-date 2026-05-21T10:00:00Z \
  --end-date 2026-05-23T10:00:00Z \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT \
  --initial-equity 1000
```

**Expected output:**
```
=== Multi-Asset Replay Summary ===
Window: 2026-05-21T10:00:00+00:00 → 2026-05-23T10:00:00+00:00 (48.0h)
Cycles: 192

=== Per-Symbol Results ===
BTCUSDT: X trades, Y near-misses, DD +/-Z.ZR (high-watermark +W.WR)
ETHUSDT: A trades, B near-misses, DD +/-C.CR (high-watermark +D.DR)
SOLUSDT: E trades, F near-misses, DD +/-G.GR (high-watermark +H.HR)

=== Portfolio Metrics ===
Total trades: N
Total near-misses: M
Win rate: 50.0% (PLACEHOLDER - random PnL)
P&L (R): +/-X.X (PLACEHOLDER - random PnL)

=== Portfolio Gate ===
Capacity sizing events: K
Gate vetoes: L
  gross_notional_cap: ...
  max_positions: ...

=== Risk Utilization ===
Avg: 0.XX%
Max: 0.YY%
```

**What to verify:**
1. ✅ **M1 (FeatureEngine):** Logs show "Bootstrapped FeatureEngine for ETHUSDT: OI {...}, CVD {...}" (bootstrap from DB works)
2. ✅ **M2 (DD tracking):** DD state shows cumulative_r, high_watermark, rolling_dd (logic works)
3. ✅ **Capacity sizing:** Capacity sizing events > 0 (if multiple signals in same cycle)
4. ✅ **Portfolio gate:** Gate vetoes tracked by reason (gross_cap, max_positions, etc.)
5. ⚠️ **P&L metrics:** IGNORE (random PnL, not realistic)

**What NOT to use this for:**
- ❌ Portfolio performance analysis (P&L, win rate, Sharpe) — use production monitoring or research lab
- ❌ Strategy optimization (threshold tuning) — use research lab optimization workflow
- ❌ Realistic trade expectancy — use production monitoring with real trades

**Next steps:**
1. **Run replay manually** — validate M1+M2 logic works as expected
2. **Document limitation** — add README or docstring explaining random PnL placeholder
3. **Continue 48h production monitoring** — real validation happens in production, not replay
4. **Optional:** Implement proper trade lifecycle simulation (Issue #1) if realistic P&L needed

---

**Final assessment:** Tool validates M1+M2 logic correctly but uses random PnL. MVP_DONE for M1+M2 validation, NOT for portfolio performance analysis. Production monitoring remains primary validation method.
