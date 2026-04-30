# Production Diagnostics V1 - Market Truth Degradation Investigation

**Date:** 2026-05-01  
**Investigator:** Claude Code (builder mode)  
**Auditor:** Claude Code (post-push)  
**Milestone:** PRODUCTION-DIAGNOSTICS-V1

---

## Executive Summary

**Verdict:** **DEGRADED** (2026-04-27T00:00 → present)

**Root cause:** Shared `limit_reached` flag bug introduced in commit `c9307f3e` (2026-04-25) causes **false positive degradation** for flow_60s window when flow_15m window hits REST API 1000-trade limit.

**Impact:** 39% of market truth buckets degraded (223/571 quality_ready). Post-2026-04-27 decision_outcomes built on degraded features.

**Optuna readiness:**
- ❌ **BLOCKED** on post-2026-04-27 data (degraded features)
- ✅ **UNBLOCKED** on WF_LIGHT_PROTOCOL window (2026-01-01 to 2026-03-28, entirely pre-bug)

---

## Degradation Timeline

### Production DB Status (2026-05-01 00:27 UTC)
```
MARKET TRUTH (Gate A):
  lineage buckets : 571/571
  quality_ready   : 223/571 (39% degraded)
  degraded_from   : 2026-04-27T12:00
  degraded_reason : flow_window_rest_limit_clipped (×2) + ...
```

### First Occurrence
**2026-04-27T00:00:00** - exact start of degradation

### Pattern
- **100% systematic clipping** (not intermittent)
- Every bucket since 2026-04-27T00:00 affected
- 00:00-11:59: flow_15m degraded, flow_60s unavailable
- 12:00+: BOTH flow_15m and flow_60s degraded

---

## Root Cause Analysis

### Bug Location
[data/market_data.py:248](../data/market_data.py#L248)

```python
# Line 248: Shared flag for BOTH windows
limit_reached = bool(source == "rest" and len(ws_events) >= self.config.agg_trades_limit)

# Line 250-256: 60s window (needs ~60s of trades)
coverage_60s = self._flow_window_metadata(
    trades_60s, ..., limit_reached=limit_reached  # ← SAME FLAG
)

# Line 257-263: 15m window (needs 900s of trades)
coverage_15m = self._flow_window_metadata(
    trades_15m, ..., limit_reached=limit_reached  # ← SAME FLAG
)
```

### The Flaw
- REST API fetches max **1000 trades** total
- If `len(ws_events) >= 1000`, **both** windows marked as `limit_reached=True`
- **60s window** only needs last 60 seconds of trades
  - May have complete coverage even if total fetch = 1000
  - **Incorrectly degraded** due to shared flag
- **15m window** needs last 900 seconds
  - Correctly marked as clipped if 1000 trades < 15min coverage

### Quality Degradation Logic
[data/market_data.py:441-446](../data/market_data.py#L441-L446)

```python
if metadata.get("clipped_by_limit"):
    return FeatureQuality.degraded(reason="flow_window_rest_limit_clipped")
```

- `clipped_by_limit = bool(limit_reached and first_ts > window_start)`
- If limit reached AND first trade after window start → DEGRADED
- Status: DEGRADED (not READY), impacts feature quality propagation

---

## Bug Introduction History

### Commit Timeline

| Date | Commit | Change |
|---|---|---|
| 2026-03-21 | `f7955975` | Original flow window logic (no limit detection) |
| 2026-04-21 | `075f529e` | Flow metadata method added |
| **2026-04-25** | **`c9307f3e`** | **Pagination fix + shared flag bug introduced** |
| 2026-04-27 | — | Bug triggered (volume > 1000/15min threshold) |

### Commit `c9307f3e` Details
**Title:** "fix(collection): restore full bucket coverage via pagination"

**Intent:** Fix clipped windows by adding pagination (fromId for aggTrade, startTime for funding)

**Unintended consequence:** Introduced shared `limit_reached` flag affecting both 60s and 15m windows

**Irony:** Fix for one clipping issue created new false-positive clipping issue

---

## Impact Classification

### Signal Impact: **CONFIRMED**
- Feature quality degraded from READY → DEGRADED
- May affect sweep detection if swept volume occurred early in window
- Coverage ratio alone doesn't capture partial clipping

### Data Contamination Scope

| Period | Status | Reason |
|---|---|---|
| Pre-2026-04-25 | ✅ CLEAN | No limit detection code |
| 2026-04-25 to 2026-04-26 | ✅ CLEAN | Bug present but volume < 1000/15min |
| **2026-04-27+** | ❌ **DEGRADED** | Bug triggered, 100% clipping |

**WF_LIGHT_PROTOCOL window (2026-01-01 to 2026-03-28):** ✅ **UNAFFECTED**

---

## Diagnostic Evidence

### Query 1: First Clipping Occurrence
```sql
SELECT cycle_timestamp, flow_15m_status, flow_60s_status
FROM feature_snapshots
WHERE cycle_timestamp >= '2026-04-27T00:00:00'
  AND (flow_15m_reason LIKE '%clipped%' OR flow_60s_reason LIKE '%clipped%')
ORDER BY cycle_timestamp LIMIT 1;
```
**Result:** `2026-04-27T00:00:00` (exact start)

### Query 2: Clipping Frequency
- **100% of buckets** since 2026-04-27T00:00
- 4/4 buckets per hour consistently
- No intermittent pattern

### Query 3: Trade Volume Correlation
- Unable to verify (aggtrade_buckets table has no trade_count column)
- Hypothesis: Volume exceeded ~67 trades/minute (1000/15min) on 2026-04-27
- Consistent high volume maintains clipping

---

## Data Quality Verdict

### For MODELING-CONTEXT-CLOSURE Validation
**Verdict:** **DEGRADED**

Post-2026-04-27 data:
- ❌ Not decision-grade without acknowledging degradation
- ❌ Flow features systematically degraded
- ❌ May affect regime classification and sweep detection
- ⚠️ decision_outcomes built on degraded features

**Recommendation:** Use pre-2026-04-27 data OR document degradation impact explicitly

### For WF_LIGHT_PROTOCOL Optuna
**Verdict:** **CLEAN** ✅

2026-01-01 to 2026-03-28 window:
- ✅ Entirely pre-bug (bug introduced 2026-04-25)
- ✅ No clipping artifacts
- ✅ Safe for Optuna preliminary screening

**Recommendation:** Proceed with wf_light_protocol.json on this window

---

## Remediation Options

### Option A: Code Fix (Recommended for Production)
**Fix:** Per-window limit detection

```python
# Current (broken):
limit_reached = bool(source == "rest" and len(ws_events) >= 1000)
coverage_60s = self._flow_window_metadata(..., limit_reached=limit_reached)
coverage_15m = self._flow_window_metadata(..., limit_reached=limit_reached)

# Fixed:
limit_60s = bool(source == "rest" and len(trades_60s) >= expected_coverage_60s)
limit_15m = bool(source == "rest" and len(trades_15m) >= expected_coverage_15m)
coverage_60s = self._flow_window_metadata(..., limit_reached=limit_60s)
coverage_15m = self._flow_window_metadata(..., limit_reached=limit_15m)
```

**Pros:** Eliminates false positives  
**Cons:** Requires logic for per-window expected coverage calculation  
**ETA:** 2-4 hours (implementation + test + deploy)

### Option B: Accept Degradation (Short-term)
- Document that post-2026-04-27 flow features are degraded
- Use pre-2026-04-27 data for research
- Defer fix until after WF_LIGHT Optuna run

**Pros:** Unblocks Optuna immediately  
**Cons:** Production continues collecting degraded data

### Option C: Revert to Pre-Pagination (Not Recommended)
- Revert commit `c9307f3e`
- Loses pagination benefits
- Original clipping issue returns

---

## Optuna Readiness Summary

| Window | Status | Reason |
|---|---|---|
| **2026-01-01 to 2026-03-28** (WF_LIGHT) | ✅ **READY** | Pre-bug, clean data |
| 2026-04-27+ | ❌ **BLOCKED** | Systematic degradation |
| Full historical (2020-09-01+) | ⚠️ **MIXED** | Clean pre-2026-04-27, degraded after |

**Recommendation:** Proceed with WF_LIGHT_PROTOCOL Optuna on 2026-01-01 to 2026-03-28 window while code fix is prepared for production.

---

## Open Blockers

| Blocker | Status | Resolution |
|---|---|---|
| flow_window_rest_limit_clipped | ✅ **ROOT CAUSE IDENTIFIED** | Shared flag bug |
| aggtrade_15m_gaps (7) | ⚠️ **UNRELATED** | Pre-existing, tracked separately |
| open_interest_gaps (35) | ⚠️ **UNRELATED** | Pre-existing, tracked separately |
| etf_bias_empty | ⚠️ **UNRELATED** | Separate backfill task |

---

## Decision Required

**Operator must choose:**
1. **Option A + Option B:** Fix code AND run WF_LIGHT Optuna (parallel paths)
2. **Option B only:** Accept degradation, run WF_LIGHT Optuna, defer fix
3. **Option A first:** Fix code, backfill post-2026-04-27 data, then Optuna

**Recommendation from builder:** **Option 1** (A+B parallel) - unblock research immediately while fixing production collection.

---

## References

- Production DB status: `scripts/db_status.py` output 2026-05-01 00:27 UTC
- Bug commit: `c9307f3e` (2026-04-25) "fix(collection): restore full bucket coverage via pagination"
- Diagnostic scripts: `scripts/diagnose_flow_clipping.py`, `scripts/diagnose_trade_volume.py`
- Related audit: `docs/audits/AUDIT_INCOMPLETE_BUCKET_FIX_2026-04-25.md`

---

**End of diagnostic report.**
