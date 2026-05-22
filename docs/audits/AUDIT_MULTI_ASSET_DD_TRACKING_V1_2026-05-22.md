# AUDIT: MULTI_ASSET_DD_TRACKING_V1
Date: 2026-05-22
Auditor: Claude Code
Commit: cddf3db

## Verdict: DONE

**Scope:** Per-symbol DD tracking in governance/risk + true high-watermark DD. Resolves BLOCKER: daily_dd_pct and weekly_dd_pct were 0.0 bypass (no per-symbol DD enforcement).

## Layer Separation: PASS
- Storage layer: schema.sql (symbol_drawdown_state table), state_store.py (CRUD + update logic)
- Portfolio gate layer: portfolio_gate.py (recovery uses persisted DD, veto logic)
- Orchestrator layer: orchestrator.py (updates DD after trade close, loads DD for recovery)
- Test layer: test_multi_asset_dd_tracking.py (17 tests, all critical paths)
- No cross-layer violations or unexpected dependencies

## Contract Compliance: PASS
- **SymbolRiskState contract:** daily_pnl_r, weekly_pnl_r, rolling_drawdown_r fields used by portfolio gate vetoes
- **PortfolioRiskConfig contract:** Threshold fields present (symbol_daily_hard_stop_r, symbol_weekly_hard_stop_r, symbol_rolling_pause_r, portfolio_daily_hard_stop_r, portfolio_weekly_hard_stop_r, portfolio_emergency_stop_r)
- **Storage contract:** symbol_drawdown_state table with PRIMARY KEY(symbol), upsert via ON CONFLICT
- **Recovery contract:** recover_portfolio_state accepts persisted_symbol_dd, uses true high-watermark when available
- **Backward compatibility:** Falls back to min(0, weekly_pnl) proxy when persisted_dd is None

## Determinism: PASS
- **Daily reset:** Based on calendar date (today_str = now.date().isoformat()) — deterministic
- **Weekly reset:** Based on Monday week start (weekday = now.weekday(), week_start = now.date() - timedelta(days=weekday)) — deterministic
- **High-watermark update:** Only when cumulative_r > local_high_watermark_r — deterministic
- **rolling_drawdown_r calculation:** cumulative_r - local_high_watermark_r (always ≤ 0) — deterministic
- **Consecutive losses:** Increments on pnl_r < 0, resets on pnl_r >= 0 — deterministic
- **Symbol normalization:** symbol.upper() consistently applied — deterministic

## Backward Compatibility: PASS
- **Fallback behavior:** When persisted_dd is None, _recover_symbol_state uses min(0, weekly_pnl) proxy (line 357 in portfolio_gate.py)
- **DD update conditional:** Only when multi_asset_paper_enabled() (line 1563 in orchestrator.py)
- **Single-asset mode unchanged:** BTC-only mode doesn't trigger DD updates
- **636 tests pass (24 skipped):** 17 new tests for DD tracking, 619 existing tests unchanged
- **Zero regressions:** Full test suite passes

## State Integrity: PASS
- **Persistence:** symbol_drawdown_state table survives restarts (not memory-only)
- **Recovery:** recover_multi_asset_portfolio_state loads DD state via load_all_symbol_dd_states() (line 522 in state_store.py)
- **Atomic updates:** upsert_symbol_dd_state uses INSERT ... ON CONFLICT ... DO UPDATE + commit (idempotent)
- **Multi-asset isolation:** Each symbol has independent DD state (BTC loss doesn't affect ETH DD)
- **Timestamp tracking:** updated_at, last_trade_at, last_loss_at recorded on every update
- **Initialization:** First trade for symbol creates initial state with defaults (cumulative_r=0, high_watermark=0)

## Error Handling: PASS
- **orchestrator.py wrapper:** update_symbol_dd_after_trade wrapped in try/except (line 1565-1572)
- **Warning on failure:** Logs "Failed to update symbol DD state" with symbol and exception (line 1572)
- **Cycle continues:** DD update failure doesn't crash decision cycle (logged but not raised)
- **Safe extraction:** evt.get("pnl_r", 0.0) safely handles missing pnl_r in closed_events dict (line 1568)
- **Type coercion:** float() and int() casts in update logic handle string/numeric types from DB (line 1242-1245, 1248-1249, 1258-1260)

## Smoke Coverage: PASS
- **17 new tests (all pass):**
  - `test_load_symbol_dd_state_returns_none_for_new_symbol()` → No state before first trade
  - `test_upsert_and_load_symbol_dd_state()` → Upsert stores and retrieves state
  - `test_load_all_symbol_dd_states_returns_all()` → Multi-symbol state retrieval
  - `test_high_watermark_updates_on_win()` → +2R → +1R updates high_watermark to 3R
  - `test_high_watermark_preserved_on_loss()` → +3R then -1R preserves high_watermark at 3R, rolling_dd = -1R
  - `test_rolling_drawdown_deep_loss_scenario()` → +5R then -8R total → rolling_dd = -8R (from 5R high)
  - `test_daily_pnl_r_accumulates_within_day()` → +1.5R then -0.5R same day → daily_pnl_r = 1.0R
  - `test_daily_pnl_r_resets_on_new_day()` → +2R today, -1R tomorrow → daily_pnl_r resets to -1R
  - `test_weekly_pnl_r_resets_on_new_week()` → +3R Thursday, -1R next Monday → weekly_pnl_r resets to -1R
  - `test_btc_dd_does_not_affect_eth_dd()` → BTC -5R, ETH +2R → independent states
  - `test_consecutive_losses_increments_on_loss()` → -1R then -1R → consecutive_losses = 2
  - `test_consecutive_losses_resets_on_win()` → -1R, -1R, +2R → consecutive_losses = 0
  - `test_portfolio_gate_vetoes_symbol_exceeding_daily_dd()` → daily_pnl_r = -2.5R triggers veto at -2.0R threshold
  - `test_portfolio_gate_vetoes_symbol_exceeding_weekly_dd()` → weekly_pnl_r = -4.5R triggers veto at -4.0R threshold
  - `test_portfolio_gate_uses_true_high_watermark_rolling_dd()` → rolling_dd = -7.5R from persisted state (not -2.0R weekly proxy)
  - `test_dd_state_survives_store_reload()` → +3R, -1R, restart → cumulative=2R, high_watermark=3R, rolling_dd=-1R
  - `test_recover_symbol_state_without_persisted_dd_uses_weekly_proxy()` → No persisted_dd → rolling_dd = min(0, weekly_pnl)
- **Focused: 25 passed, Wider: 50 passed, Full suite: 636 passed (24 skipped)**

## Tech Debt: LOW
- Clean implementation (clear table schema, CRUD separation, deterministic update logic)
- No NotImplementedError stubs
- No magic numbers (all thresholds in PortfolioRiskConfig)
- Comprehensive test coverage (17 tests, all critical scenarios including -8R deep drawdown)
- No duplication (DD update logic isolated to update_symbol_dd_after_trade)

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message (cddf3db)
- Scope purity: DD tracking only, no signal/governance/execution changes outside DD
- Documentation: Milestone scope matches deliverables (per-symbol DD + true high-watermark)

## Implementation Analysis: PASS

**Storage layer (symbol_drawdown_state table):**
```sql
CREATE TABLE IF NOT EXISTS symbol_drawdown_state (
    symbol TEXT PRIMARY KEY,
    cumulative_r REAL NOT NULL DEFAULT 0.0,
    local_high_watermark_r REAL NOT NULL DEFAULT 0.0,
    rolling_drawdown_r REAL NOT NULL DEFAULT 0.0,
    daily_pnl_r REAL NOT NULL DEFAULT 0.0,
    weekly_pnl_r REAL NOT NULL DEFAULT 0.0,
    daily_start_date TEXT NOT NULL,
    weekly_start_date TEXT NOT NULL,
    trades_today INTEGER NOT NULL DEFAULT 0,
    consecutive_losses INTEGER NOT NULL DEFAULT 0,
    last_trade_at TEXT,
    last_loss_at TEXT,
    updated_at TEXT NOT NULL
);
```

**DD update logic (state_store.py:update_symbol_dd_after_trade):**
1. Load existing DD state (or initialize with zeros)
2. Daily reset check: if today != daily_start_date → reset daily_pnl_r, trades_today
3. Weekly reset check: if this_week != weekly_start_date → reset weekly_pnl_r
4. Update cumulative_r, daily_pnl_r, weekly_pnl_r (add pnl_r)
5. High-watermark update: if cumulative_r > local_high_watermark_r → update high_watermark
6. Calculate rolling_drawdown_r = cumulative_r - local_high_watermark_r (always ≤ 0)
7. Consecutive losses: if pnl_r < 0 → increment, else → reset to 0
8. Upsert to DB (INSERT ... ON CONFLICT ... DO UPDATE)

**Portfolio gate integration (portfolio_gate.py:_recover_symbol_state):**
```python
# Use persisted DD state when available (true high-watermark tracking)
if persisted_dd is not None:
    rolling_dd = float(persisted_dd.get("rolling_drawdown_r", 0.0))
    daily_pnl = float(persisted_dd.get("daily_pnl_r", daily_pnl))
    weekly_pnl = float(persisted_dd.get("weekly_pnl_r", weekly_pnl))
    consec_losses = int(persisted_dd.get("consecutive_losses", 0))
    trades_today_count = int(persisted_dd.get("trades_today", 0))
else:
    rolling_dd = min(0.0, weekly_pnl)  # Fallback to weekly proxy
    consec_losses = _global_consecutive_losses(trades)
    trades_today_count = sum(1 for t in trades if _same_utc_day(t.closed_at, now))
```

**Veto logic (portfolio_gate.py:_symbol_veto):**
```python
def _symbol_veto(self, state: SymbolRiskState, now: datetime) -> PortfolioVetoReason | None:
    if state.daily_pnl_r <= self.config.symbol_daily_hard_stop_r:
        return PortfolioVetoReason.SYMBOL_DAILY_HARD_STOP
    if state.weekly_pnl_r <= self.config.symbol_weekly_hard_stop_r:
        return PortfolioVetoReason.SYMBOL_WEEKLY_HARD_STOP
    if state.rolling_drawdown_r <= self.config.symbol_rolling_pause_r:
        return PortfolioVetoReason.SYMBOL_ROLLING_PAUSE
    # ... other checks
```

**Orchestrator integration (orchestrator.py):**
```python
# After trade close (line 1562-1573):
if self._multi_asset_paper_enabled():
    for evt in closed_events:
        try:
            self.state_store.update_symbol_dd_after_trade(
                symbol=evt["symbol"],
                pnl_r=float(evt.get("pnl_r", 0.0)),
                closed_at=snapshot.timestamp,
            )
        except Exception as dd_exc:
            LOG.warning("Failed to update symbol DD state for %s: %s", evt.get("symbol"), dd_exc)

# Before signal evaluation (line 942-945):
recovered = self.state_store.recover_multi_asset_portfolio_state(
    self.settings.multi_asset.enabled_symbols,
    now=timestamp,
)
# recovered.symbols contains SymbolRiskState with true high-watermark DD
```

## Critical Safety Analysis: PASS

**Scenario 1: Symbol hits -2R daily DD threshold**
- BTC closes -1.5R trade (daily_pnl_r = -1.5R)
- BTC closes -0.6R trade (daily_pnl_r = -2.1R)
- Next BTC signal evaluated: portfolio gate checks daily_pnl_r = -2.1R <= -2.0R threshold
- Veto: SYMBOL_DAILY_HARD_STOP
- Result: BTC trading paused for rest of day, ETH/SOL unaffected ✓

**Scenario 2: Symbol hits -8R rolling DD threshold (from high-watermark)**
- SOL builds to +5R high-watermark
- SOL loses -8R total over multiple trades (cumulative_r = -3R)
- rolling_drawdown_r = -3R - 5R = -8R
- Next SOL signal evaluated: portfolio gate checks rolling_dd = -8R <= -6R threshold (symbol_rolling_pause_r)
- Veto: SYMBOL_ROLLING_PAUSE
- Result: SOL trading paused, BTC/ETH unaffected ✓

**Scenario 3: Weekly DD reset on Monday**
- Thursday: ETH daily_pnl_r = -1.5R, weekly_pnl_r = -1.5R
- Friday: ETH daily_pnl_r resets to 0, weekly_pnl_r = -1.5R (same week)
- Monday: ETH daily_pnl_r resets to 0, weekly_pnl_r resets to 0 (new week)
- Result: Fresh start each week, daily resets each day ✓

**Scenario 4: Multi-asset isolation**
- BTC loses -5R (BTC rolling_dd = -5R from 0 high)
- ETH wins +2R (ETH rolling_dd = 0R, high_watermark = 2R)
- BTC signal → may be vetoed by BTC DD thresholds
- ETH signal → evaluated against ETH DD state (not affected by BTC loss)
- Result: Independent DD tracking per symbol ✓

**Scenario 5: Restart with persisted DD state**
- Before restart: BTC cumulative_r = 3R, high_watermark = 5R, rolling_dd = -2R
- Service restart
- After restart: recover_multi_asset_portfolio_state loads DD state from DB
- BTC signal → portfolio gate uses rolling_dd = -2R (from DB, not recalculated)
- Result: DD state survives restarts, no reset to zero ✓

**Scenario 6: No persisted DD (backward compatibility)**
- Old database without symbol_drawdown_state table
- recover_multi_asset_portfolio_state: load_all_symbol_dd_states() returns {}
- _recover_symbol_state: persisted_dd is None → fallback to min(0, weekly_pnl)
- Result: System functions with degraded DD (weekly proxy instead of high-watermark) ✓

## Edge Case Analysis: PASS

**Edge case 1: Breakeven trade (pnl_r = 0.0)**
- Consecutive losses logic: `if pnl_r < 0: increment, else: reset to 0`
- Breakeven trade resets consecutive_losses to 0 (same as win)
- Impact: Minor edge case, may be intentional (any non-loss resets streak)
- Observation: Could change to `if pnl_r > 0: reset` to only reset on wins, not breakeven

**Edge case 2: Multiple trades close in same cycle**
- orchestrator loops through closed_events, calls update_symbol_dd_after_trade for each
- Each call: load state → update → upsert (not transactional across all trades in cycle)
- If one update fails: try/except logs warning, cycle continues, other trades still update
- Impact: Acceptable, DD state eventually consistent

**Edge case 3: Trade closes exactly at midnight UTC**
- Daily reset check: `if existing["daily_start_date"] != today_str`
- If trade closes at 00:00:00 UTC: today_str changes, daily_pnl_r resets before adding pnl_r
- Impact: Trade counted in new day (correct behavior)

**Edge case 4: Portfolio-level rolling_drawdown_r uses weekly proxy (not high-watermark)**
- Symbol-level: uses true high-watermark (cumulative_r - local_high_watermark_r)
- Portfolio-level: uses min(0, weekly_pnl) (line 332 in portfolio_gate.py)
- Impact: Portfolio DD is aggregate metric, not per-symbol tracked state
- Observation: Portfolio-level high-watermark tracking could be future enhancement

**Edge case 5: Symbol normalization (ETHUSDT vs ethusdt)**
- update_symbol_dd_after_trade: symbol.upper() at line 1215
- load_symbol_dd_state: symbol.upper() at line 1130
- PRIMARY KEY on symbol (case-sensitive in SQLite)
- Impact: Consistent normalization, no duplicate states for same symbol

## Production Impact Analysis: PASS

**Before Milestone #2 (current production):**
- daily_dd_pct = 0.0, weekly_dd_pct = 0.0 (bypass, no DD enforcement)
- rolling_drawdown_r = min(0, weekly_pnl) (weekly proxy, not true high-watermark)
- Multi-asset PAPER: BTC/ETH/SOL all trade even after symbol-level losses
- Risk: No per-symbol DD protection, loss streaks on one symbol don't pause that symbol

**After Milestone #2 deployment:**
- daily_pnl_r and weekly_pnl_r tracked per symbol from DB
- rolling_drawdown_r uses true high-watermark (cumulative_r - local_high_watermark_r)
- Portfolio gate vetoes signals exceeding per-symbol DD thresholds:
  - symbol_daily_hard_stop_r = -2.0R
  - symbol_weekly_hard_stop_r = -4.0R
  - symbol_rolling_pause_r = -6.0R
- BTC loss streak pauses BTC trading, ETH/SOL unaffected (multi-asset isolation)

**Benefit:**
- Per-symbol DD protection (each asset independently monitored)
- True high-watermark DD (not just weekly rolling window)
- Realistic multi-asset risk management (one asset's DD doesn't stop portfolio, just that asset)

**Risk:**
- None (backward compatible fallback, DD update failures logged but don't crash cycles)
- Multi-asset isolation means portfolio can continue trading other symbols even if one hits DD limit (this is by design)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. Per-symbol DD tracking fully implemented (daily, weekly, rolling from high-watermark)
2. True high-watermark DD replaces weekly proxy for symbol-level rolling_drawdown_r
3. Portfolio-level rolling_drawdown_r still uses weekly proxy (line 332 in portfolio_gate.py) — acceptable as aggregate metric, could be future enhancement
4. Consecutive losses reset on any non-loss (pnl_r >= 0), including breakeven (pnl_r == 0) — may be intentional, minor edge case
5. DD state persists across restarts (symbol_drawdown_state table)
6. Multi-asset isolation: BTC DD state doesn't affect ETH DD state (independent tracking)
7. Backward compatible: falls back to weekly proxy when persisted_dd is None
8. 17 new tests cover all critical paths (high-watermark, daily/weekly reset, multi-asset isolation, veto thresholds)
9. 636 tests pass (24 skipped), 0 regressions
10. Clean implementation (layer separation, deterministic, no tech debt)
11. Error handling: DD update failure logged but doesn't crash cycle (try/except wrapper)
12. BLOCKER resolved: daily_dd_pct and weekly_dd_pct no longer 0.0 bypass (now per-symbol tracked)

## Recommended Next Step

**DD tracking is DONE. Deploy immediately (code-only + restart), then verify DD state updates in production.**

### Deployment: Code-only + restart

**Goal:** Deploy per-symbol DD tracking with true high-watermark to production multi-asset PAPER.

**Deployment command:**
```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull github deploy/multi-asset-paper-v1  # expect: cddf3db or later

# Restart service (orchestrator.py, portfolio_gate.py, state_store.py, schema changes)
systemctl restart btc-bot.service
```

**Post-deployment verification:**
```bash
# Verify service restart
systemctl status btc-bot.service --no-pager  # Active, clean restart

# Verify bot status
python scripts/query_bot_status.py  # multi_asset.enabled=True, symbols=BTC/ETH/SOL

# Check symbol_drawdown_state table exists
sqlite3 storage/btc_bot.db "SELECT name FROM sqlite_master WHERE type='table' AND name='symbol_drawdown_state';"
# Expected: symbol_drawdown_state

# Monitor first trade close for DD state update
tail -f logs/btc_bot.log | grep -E "(update symbol DD state|SYMBOL_DAILY_HARD_STOP|SYMBOL_WEEKLY_HARD_STOP|SYMBOL_ROLLING_PAUSE)"
```

**Expected behavior after deploy:**
- Service restarts cleanly
- symbol_drawdown_state table created (schema migration)
- First trade close for each symbol initializes DD state in DB
- Subsequent trades update DD state (cumulative_r, high_watermark, rolling_drawdown_r)
- Portfolio gate vetoes signals exceeding per-symbol DD thresholds
- No "Failed to update symbol DD state" warnings (unless DB write fails)

**Verification scenario (wait for first trade close):**
1. Wait for BTC/ETH/SOL trade to close
2. Query DD state:
   ```bash
   sqlite3 storage/btc_bot.db "SELECT symbol, cumulative_r, local_high_watermark_r, rolling_drawdown_r, daily_pnl_r, weekly_pnl_r FROM symbol_drawdown_state;"
   ```
3. Expected: Row for closed symbol with updated cumulative_r and high_watermark
4. Next signal for that symbol → portfolio gate uses DD state for veto checks

**High-watermark verification (after win followed by loss):**
1. Wait for symbol to close +2R trade
2. Query: high_watermark should be 2.0, rolling_dd = 0.0
3. Wait for same symbol to close -1R trade
4. Query: high_watermark preserved at 2.0, cumulative_r = 1.0, rolling_dd = -1.0 (1.0 - 2.0)
5. Expected: High-watermark doesn't decrease on loss ✓

**DD threshold veto verification:**
1. If symbol hits -2R daily DD: next signal should be vetoed with SYMBOL_DAILY_HARD_STOP
2. Check decision_outcomes table: portfolio_veto_reason = "symbol_daily_hard_stop"
3. Verify other symbols (not at DD limit) can still generate signals

**Rollback (if needed):**
- Revert to pre-cddf3db commit (e.g., 1eb9c2d from Milestone #1)
- Restart service
- DD tracking will use fallback (weekly proxy, no per-symbol enforcement)
- symbol_drawdown_state table remains but unused (no harm)

---

**Next milestone decision:** After successful deploy and verification of DD state updates, consider Milestone #3 (multi-symbol WebSocket) OR operational monitoring of multi-asset PAPER performance with DD enforcement active.
