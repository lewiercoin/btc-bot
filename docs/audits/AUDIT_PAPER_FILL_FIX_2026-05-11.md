# AUDIT: Paper Execution Fill Fix

Date: 2026-05-11  
Auditor: Claude Code  
Scope: Fix for paper execution bug where entry > TP resulted in negative PnL with exit_reason=TP  
Builder: Codex  
Commit: Uncommitted changes in working tree  

## Verdict: DONE

## Executive Summary

**Root Cause Identified:**  
Production paper trade showed `exit_reason=TP` with negative PnL (-0.14R). Analysis revealed:
- Signal planned: entry ~80,651.54 → TP 81,171.61 (profit for LONG)
- Actual trade: entry 81,279.95 → exit 81,171.61 (loss!)
- **Entry price was ABOVE take profit** - fundamentally invalid bracket

**Fix Implemented:**  
Three-part architectural fix ensuring bracket coherence and single source of truth for entry prices.

## Changes Audited

### 1. paper_execution_engine.py (Lines 43, 91-110)

**Added:** `_validate_bracket_after_fill()` method

**Logic:**
- LONG: `stop_loss < filled_price < take_profit_1 <= take_profit_2`
- SHORT: `take_profit_2 <= take_profit_1 < filled_price < stop_loss`
- Raises `ValueError` with detailed context if invalid

**Assessment:** ✅ PASS
- Validation occurs immediately after fill price determination, before any persistence
- Fail-fast pattern prevents invalid state from propagating
- Error message includes all bracket values for debugging
- Logic correctly handles both LONG and SHORT directions

### 2. orchestrator.py (Lines 564-569)

**Changed:** `record_trade_open()` now returns `filled_entry_price`

**Before:**
```python
self.state_store.record_trade_open(..., filled_entry_price=paper_fill_price)
filled_entry_price = paper_fill_price if paper_fill_price is not None else executable.entry_price
```

**After:**
```python
filled_entry_price = self.state_store.record_trade_open(...)
```

**Assessment:** ✅ PASS
- Eliminates parallel calculation of entry price in orchestrator
- Single source of truth: entry price comes from what was actually persisted
- Removes `filled_entry_price` parameter - no longer overrides position entry price
- Cleaner control flow, less room for discrepancy

### 3. state_store.py (Line 517, 553)

**Changed:** Return type from `None` to `float`, returns `entry_price`

**Logic:**
```python
entry_price = float(position["entry_price"] if filled_entry_price is None else filled_entry_price)
...
return entry_price
```

**Assessment:** ✅ PASS
- Reads entry_price from persisted position (written by execution engine)
- Returns exactly what was written to trade_log
- Maintains backward compatibility (filled_entry_price parameter optional)
- Consistent with existing state management pattern

### 4. Tests

**Added:** `test_paper_fill_fix.py`
- `test_paper_execution_rejects_long_fill_above_take_profit()`
- `test_paper_execution_rejects_short_fill_below_take_profit()`

**Updated:** `test_paper_execution_realism.py`
- Fixed `_make_executable()` to create valid SHORT brackets (SL > entry > TP1 > TP2)

**Validation Results:**
- 29/29 tests passed
- Coverage: paper_execution_engine.py at 93%
- Regression tests explicitly verify the bug cannot recur

**Assessment:** ✅ PASS
- Comprehensive coverage of the bug scenario
- Tests verify ValueError is raised with correct message
- Tests confirm no side effects (no positions/executions created on rejection)

## Architectural Impact

### Data Flow (Before Fix)
```
snapshot_price → orchestrator (paper_fill_price)
                 ↓
            state_store.record_trade_open(filled_entry_price=paper_fill_price)
                 ↓
            trade_log.entry_price ← overwritten with snapshot price
```

**Problem:** Execution engine could write different entry_price to position than what trade_log recorded.

### Data Flow (After Fix)
```
snapshot_price → execution_engine
                 ↓ (validates bracket)
            position.entry_price ← filled_price (after bid/ask spread, validation)
                 ↓
            state_store.record_trade_open() reads position.entry_price
                 ↓
            trade_log.entry_price ← same as position.entry_price
                 ↓
            returns entry_price to orchestrator
```

**Benefit:** Single source of truth. Entry price flows from execution → position → trade_log → orchestrator.

## Audit Criteria

### Layer Separation: PASS
- Execution engine owns fill price determination and bracket validation
- State store owns persistence and retrieval
- Orchestrator coordinates but does not override
- Clear responsibility boundaries

### Contract Compliance: PASS
- ExecutableSignal contract enforced: bracket must be valid after fill
- Return type change (`None` → `float`) is backward-compatible extension
- No breaking changes to existing interfaces

### Determinism: PASS
- Bracket validation is pure function (static method)
- Entry price is deterministic: comes from persisted position
- No hidden state mutations

### State Integrity: PASS
- Invalid fills are rejected before ANY persistence
- Position, execution, and trade_log remain consistent
- Single source of truth prevents divergence

### Error Handling: PASS
- ValueError with structured message for invalid bracket
- Error occurs before any side effects
- Message includes all relevant values for debugging

### Smoke Coverage: PASS
- 2 new regression tests for the exact bug scenario
- Existing tests updated to handle SHORT brackets correctly
- 29/29 tests passed, including risk_engine and execution_realism suites

### Tech Debt: LOW
- No new TODOs or NotImplementedError
- Actually reduces debt by removing parallel calculation
- Code is more maintainable (single source of truth)

## Critical Issues: NONE

## Warnings: NONE

## Observations

1. **Production Impact Verification Needed:**  
   The bug was discovered in production (trade 2026-05-10 22:15:22). After deployment, should verify:
   - Check if there are other trades in history with `exit_reason=TP` but negative PnL
   - Confirm the entry > TP scenario cannot happen going forward

2. **Root Cause - Snapshot Price vs Actual Fill:**  
   The original bug occurred because:
   - Signal was generated with reasonable bracket (entry 80,651 → TP 81,171)
   - By the time paper fill executed, snapshot price was 81,279 (above TP)
   - Old code blindly used snapshot price as entry
   - New code validates and rejects this scenario

3. **Improved Observability:**  
   Error message format `paper_fill_invalid_bracket:direction=LONG:filled_price=...` provides structured logging for monitoring. Consider adding alert on this error in production.

## Recommended Next Steps

1. **Immediate: Commit and deploy** (after user confirmation)
   ```bash
   git add execution/paper_execution_engine.py orchestrator.py storage/state_store.py tests/
   git commit -m "fix: reject paper fills with invalid bracket (entry beyond TP)
   
   - Add bracket validation in paper execution (SL < fill < TP for LONG)
   - Single source of truth: entry_price flows from position to trade_log
   - Add regression tests for LONG fill > TP and SHORT fill < TP
   
   Fixes production bug where LONG entry=81279.95 > TP=81171.61 resulted in
   exit_reason=TP with negative PnL. Now rejects such fills immediately.
   
   Co-Authored-By: Codex <noreply@anthropic.com>"
   ```

2. **Post-deployment verification:**
   - Monitor for `paper_fill_invalid_bracket` errors
   - Query production DB for historical trades with `exit_reason=TP` and `pnl_abs < 0`
   - Confirm bot generates signals and executes them without this error

3. **After verification, proceed with parameter optimization:**
   - Fix paper execution first (this PR)
   - Then run autoresearch/backtest-based parameter optimization
   - Then controlled paper experiment with adjusted parameters
   - Optimization on buggy execution would produce misleading results

## Related Context

This fix addresses the blocker identified by Codex before parameter optimization. Production bot statistics:
- Last 30 days: -2,167 USD (21 trades) in PAPER mode
- Last 24h: 74x sweep_too_shallow, 60x no_sweep, 1x signal_generated
- Parameter optimization (min_sweep_depth_pct, confluence_min) deferred until after this fix

Next milestone after deployment: Research Lab autoresearch for parameter grid search.