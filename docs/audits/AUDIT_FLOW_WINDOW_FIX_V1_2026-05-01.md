# AUDIT: FLOW-WINDOW-FIX-V1

**Date:** 2026-05-01  
**Auditor:** Claude Code (self-audit, exception mode)  
**Builder:** Claude Code (exception mode, user requested)  
**Commit:** `b8e5ba0bc33fb0b56b4f713a0126fce4ba477ad7`  
**Branch:** `modeling-context-closure`

---

## Verdict: DONE ✅

Fix deployed to production, verified with first post-fix bucket showing both windows READY.

---

## Audit Summary

| Axis | Status | Notes |
|---|---|---|
| **Layer Separation** | PASS | Changes isolated to data layer |
| **Contract Compliance** | PASS | Private method signature change, all callers updated |
| **Determinism** | PASS | Removed shared state, independent window evaluation |
| **State Integrity** | PASS | Backward compatible with historical data |
| **Error Handling** | PASS | Simplified logic, fewer error paths |
| **Smoke Coverage** | PASS | 3/3 tests pass, regression test added |
| **Tech Debt** | LOW | Code simplified, no new debt |
| **AGENTS.md Compliance** | PASS | Commit discipline followed |

---

## Implementation Review

### Scope Delivered
✅ Removed shared `limit_reached` flag  
✅ Removed `limit_reached` parameter from `_flow_window_metadata()`  
✅ Removed `clipped_by_limit` logic from `_quality_from_flow_metadata()`  
✅ Updated existing tests  
✅ Added regression test for high-volume scenario  
✅ Deployed to production  
✅ Verified with first post-fix bucket

### Code Changes
**[data/market_data.py](../data/market_data.py)**
- Line 248: Removed `limit_reached = bool(source == "rest" and len(ws_events) >= 1000)`
- `_flow_window_metadata()`: Removed `limit_reached` parameter
- `_flow_window_metadata()`: Removed `clipped_by_limit` and `limit_reached` from metadata return
- `_quality_from_flow_metadata()`: Removed clipped_by_limit check

**[tests/test_flow_completeness.py](../tests/test_flow_completeness.py)**
- Updated `test_partial_flow_window_is_not_labeled_ready()`: removed limit_reached parameter
- Added `test_flow_60s_ready_despite_high_volume_15m()`: regression test for shared flag bug

### Test Coverage
```
3/3 tests PASSED:
✅ test_flow_quality_thresholds_are_config_driven_and_ordered
✅ test_partial_flow_window_is_not_labeled_ready
✅ test_flow_60s_ready_despite_high_volume_15m (NEW - regression test)
```

### Contract Compliance
- Method signature changed: `_flow_window_metadata()` removed `limit_reached` parameter
- Method is private (`_` prefix), so no external contract violation
- All internal callers updated (2 in production code, 3 in tests)
- FeatureQuality return type unchanged
- Metadata schema evolved: removed `clipped_by_limit` and `limit_reached` fields
- Consumers are defensive: SQL queries use `COALESCE(json_extract(...), 0)`
- No Python code reads these fields from database

### Determinism & State Integrity
- **Before:** Shared `limit_reached` flag caused non-deterministic quality assessment (60s window degraded due to 15m window state)
- **After:** Each window evaluated independently based on its own coverage_ratio
- **Backward compatibility:** Old buckets in DB have clipped_by_limit field, new ones don't. SQL queries handle both cases safely (COALESCE).

### Production Verification
**Deployment:** 2026-05-01 16:00:22 UTC (systemctl restart btc-bot.service)

**Baseline (pre-fix, last 5 buckets):**
```
2026-05-01T16:00:00 | flow_60s: degraded (flow_window_rest_limit_clipped)
2026-05-01T15:45:00 | flow_60s: degraded (flow_window_rest_limit_clipped)
2026-05-01T15:30:00 | flow_60s: degraded (flow_window_rest_limit_clipped)
2026-05-01T15:15:00 | flow_60s: degraded (flow_window_rest_limit_clipped)
2026-05-01T15:00:00 | flow_60s: degraded (flow_window_rest_limit_clipped)
```

**Post-fix (first bucket after deployment):**
```
2026-05-01T16:15:00 | flow_60s: ready (flow_window_complete) ✅
                    | flow_15m: ready (flow_window_complete) ✅
```

**Fix confirmed:** Both windows READY, false positive degradation eliminated.

---

## Critical Issues
None.

---

## Warnings
None.

---

## Observations

### 1. Simplification beats complexity
External auditor recommended "Path 1: Remove limit_reached entirely" over "Path 2: Per-window limit calculation". The simpler approach worked because `_load_rest_agg_trade_window()` already paginates successfully (fromId cursor), so reaching fetch limit ≠ incomplete data.

### 2. Metadata field removal is safe
Removing `clipped_by_limit` from source_meta_json is backward compatible:
- Old buckets retain the field (historical)
- New buckets omit it
- SQL queries use `COALESCE(..., 0)` for safe default
- No Python code reads this field

### 3. Regression test design
Test simulates exact bug scenario:
- 100 trades densely packed in last 90 seconds (high volume)
- 60s window: full coverage (90s > 60s) → READY
- 15m window: partial coverage (90s < 900s) → degraded/unavailable
- Verifies independent evaluation, no shared state

### 4. Historical degradation artifact
Pre-fix buckets (2026-04-27 to 2026-05-01T16:00) remain degraded in database. No backfill planned - they are marked as degraded and excluded from decision-grade datasets per existing quality filters.

---

## Recommended Next Step

**FLOW-WINDOW-FIX-V1 is DONE.**

Update MILESTONE_TRACKER.md to mark this milestone complete and proceed with parallel track: **WF_LIGHT_PROTOCOL Optuna** (Tor 1).

---

## References

- Root cause analysis: [PRODUCTION_DIAGNOSTICS_V1_2026-05-01.md](../analysis/PRODUCTION_DIAGNOSTICS_V1_2026-05-01.md)
- Bug commit: `c9307f3e` (2026-04-25)
- Fix commit: `b8e5ba0` (2026-05-01)
- Decision log: [DECISIONS_LOG.md](../DECISIONS_LOG.md) - Decision 7 & 8
- Test file: [tests/test_flow_completeness.py](../../tests/test_flow_completeness.py)
- Production data: `/home/btc-bot/btc-bot/storage/btc_bot.db` (verified 2026-05-01 16:16 UTC)

---

**End of audit.**
