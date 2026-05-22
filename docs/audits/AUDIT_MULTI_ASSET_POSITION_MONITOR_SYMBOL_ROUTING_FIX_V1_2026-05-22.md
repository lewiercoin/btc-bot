# AUDIT: MULTI_ASSET_POSITION_MONITOR_SYMBOL_ROUTING_FIX_V1
Date: 2026-05-22
Auditor: Claude Code
Commit: 721ac65

## Verdict: DONE

**CRITICAL HOTFIX:** Position monitor was BTC-only after multi-asset activation. ETH/SOL open positions would have been evaluated with BTC prices between decision cycles. Fixed before first ETH/SOL trade.

## Critical Safety Issue: RESOLVED

**Bug description:**
- 15-minute decision cycle: ✓ processed lifecycle per symbol correctly
- 15-second position monitor: ✗ built BTC-only snapshot for all open positions
- **Impact if unfixed:** Open ETH position at $3000 evaluated with BTC price $65000
- **Actual impact:** None (caught before first ETH/SOL position opened)

**Root cause:**
`_run_position_monitor_cycle()` was not updated during multi-asset orchestrator implementation. Decision cycle got per-symbol routing, fast monitor did not.

**Fix scope:**
- Position monitor now builds symbol-specific snapshots for each open position symbol
- Calls lifecycle with `symbol=symbol` parameter
- BTC-only path unchanged (backward compatible)
- No changes to strategy, risk, execution, or settings

## Layer Separation: PASS
- Change isolated to orchestrator.py (runtime loop layer)
- Uses existing `_build_symbol_snapshot()` and `_process_trade_lifecycle(symbol=)` contracts
- No new imports or cross-layer coupling
- Test added to test_multi_asset_orchestrator_dispatch.py (correct test layer)

## Contract Compliance: PASS
- Position monitor must evaluate positions with correct symbol prices
- Multi-asset mode: per-symbol snapshot → per-symbol lifecycle
- BTC-only mode: unchanged (single snapshot → single lifecycle)
- Lifecycle contract unchanged (symbol parameter already existed)
- Snapshot contract unchanged (symbol routing already existed)

## Determinism: PASS
- Symbol extraction deterministic (`dict.fromkeys` preserves insertion order)
- Per-symbol snapshot building deterministic
- Per-symbol lifecycle evaluation deterministic
- Closed events collection deterministic (extend in symbol order)

## Backward Compatibility: PASS
- BTC-only path unchanged (`else` branch preserved exactly)
- Monitor frequency unchanged (15 seconds)
- Lifecycle logic unchanged (only routing improved)
- 612 tests pass (24 skipped) — 1 new regression test
- No changes to production settings or multi-asset contract

## State Integrity: PASS
- Position monitoring is read-only (no state mutation risk)
- Closed events collected across all symbols
- Metrics counting unchanged (total closed events)
- No race conditions (sequential symbol processing)

## Error Handling: PASS
- Snapshot building failure propagates (same as before)
- Lifecycle failure propagates (same as before)
- Exception caught by existing try-except block
- Error logged and alerted via existing error path
- No partial lifecycle evaluation (fail-fast on error)

## Smoke Coverage: PASS
- **Critical regression test added:**
  - `test_multi_asset_position_monitor_routes_lifecycle_by_position_symbol()`
  - Mock open ETH and SOL positions
  - Assert BTC-only snapshot is NOT called (fail_btc_snapshot raises AssertionError)
  - Verify symbol-specific snapshots built for ETH and SOL
  - Verify lifecycle called with symbol parameter for each
  - Verify snapshot matches symbol in lifecycle call
- **Test would have caught the bug:** BTC-only path triggers assertion failure
- **Focused tests: 11 passed**
- **Full suite: 612 passed (24 skipped)**

## Tech Debt: LOW
- Clean fix (extends existing per-symbol contracts)
- No duplication (reuses _build_symbol_snapshot and lifecycle routing)
- Regression test prevents future breakage
- No NotImplementedError stubs

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message (721ac65)
- Scope purity: hotfix only, no scope creep
- Documentation: DECISIONS_LOG and MILESTONE_TRACKER updated with finding context

## Critical Safety Analysis: PASS

**Scenario if bug not fixed:**
1. Multi-asset PAPER activated (BTC/ETH/SOL enabled)
2. ETH signal generated and executed → open ETH position at entry $3000
3. 15-second position monitor runs:
   - Builds BTC snapshot (BTC price $65000, high/low/close for BTC)
   - Calls `_process_trade_lifecycle(btc_snapshot)` without symbol parameter
   - Lifecycle evaluates ETH position with BTC prices
   - Stop-loss/take-profit calculated with wrong prices
   - Position potentially closed at wrong level or missed exit

**Actual outcome:**
- Bug found during post-activation M4 quality audit
- No ETH/SOL positions existed yet (activation was 2026-05-21 21:00 UTC)
- No trades affected
- Fix implemented before first ETH/SOL signal execution

**Fix validation:**
- Regression test explicitly fails if BTC-only snapshot used in multi-asset mode
- Symbol routing verified via monkeypatch assertions
- Full test suite passes with fix

## Edge Case Analysis: PASS

**Mixed symbol positions (BTC + ETH):**
- symbols = ("BTCUSDT", "ETHUSDT") via dict.fromkeys deduplication
- Builds BTC snapshot → lifecycle for BTC positions
- Builds ETH snapshot → lifecycle for ETH positions
- Both closed_events collected
- Correct ✓

**Multiple positions same symbol:**
- Open records contain 2 ETH positions
- symbols = ("ETHUSDT",) via deduplication
- Builds ETH snapshot once
- Lifecycle evaluates all ETH positions with same snapshot
- Correct ✓ (existing lifecycle logic handles multiple positions)

**Empty open positions:**
- Returns early (no change from before)
- Correct ✓

**Multi-asset disabled:**
- Falls through to else branch (BTC-only path)
- Backward compatible ✓

## Critical Issues (must fix before next milestone)
None. Hotfix is complete and tested.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. Critical safety bug caught before first ETH/SOL position (excellent timing)
2. Decision cycle had correct per-symbol lifecycle routing (only monitor missed)
3. Regression test prevents future breakage (fail_btc_snapshot assertion)
4. Symbol deduplication via dict.fromkeys is clean (Python 3.7+ preserves order)
5. Per-symbol snapshot building already existed (_build_symbol_snapshot)
6. Lifecycle symbol parameter already existed (decision cycle used it)
7. Fix isolated to orchestrator.py (no cross-layer changes)
8. BTC-only path unchanged (zero regression risk)
9. Error handling unchanged (fail-fast on snapshot or lifecycle error)
10. Found during M4 quality audit (audit process working as designed)

## Recommended Next Step

**Hotfix is DONE. Deploy immediately before relying on ETH/SOL position lifecycle.**

### Deployment: Code-only + restart required

**Goal:** Deploy position monitor fix to production, restart service to load new orchestrator.

**Deployment command:**
```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull origin deploy/multi-asset-paper-v1  # expect: 721ac65 or later

# Restart service (orchestrator.py change requires reload)
systemctl restart btc-bot.service
```

**Post-deployment verification:**
```bash
# Verify service restart
systemctl status btc-bot.service --no-pager  # Active, no restart loop

# Verify bot status (multi-asset still enabled)
python scripts/query_bot_status.py  # enabled=True, symbols=BTC/ETH/SOL

# Monitor first cycle after restart
tail -f logs/btc_bot.log | grep -E "(multi_asset|lifecycle|position_monitor)"
```

**Expected first state:**
- Service active with clean restart
- Multi-asset PAPER still enabled (settings.json unchanged)
- Position monitor routes by symbol (will be visible when first ETH/SOL position opens)
- No runtime errors or lifecycle failures

**Safety validation:**
- If ETH or SOL position opens, monitor will use ETH/SOL snapshot (not BTC)
- Lifecycle evaluation will use correct symbol prices
- Stop-loss and take-profit levels calculated with correct prices

---

**Next milestone decision:** Deploy hotfix → verify clean restart → resume monitoring for first ETH/SOL signal → generate clean M4 quality report.
