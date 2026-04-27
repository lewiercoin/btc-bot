# Quant-Grade Hardening Summary

**Date:** 2026-04-23  
**Scope:** Market Truth Layer V3 → Quant-Grade Source of Truth  
**Implementation:** Claude Code (hardening pass)

---

## What Changed

Market Truth V3 established **runtime snapshot persistence**. This hardening pass elevates it to **quant-grade source-of-truth** with explicit lineage, timing, provenance, and replay safety.

---

## Implemented Requirements

### 1. Per-Input Timestamp Lineage ✅

**Problem:** V3 used single heuristic `exchange_timestamp` (max of available sources). Cannot determine staleness per input.

**Solution:** Added explicit exchange timestamp fields for each data source:

| Field | Source | Persisted In |
|---|---|---|
| `candles_15m_exchange_ts` | Latest 15m candle `open_time` | `market_snapshots` table |
| `candles_1h_exchange_ts` | Latest 1h candle `open_time` | `market_snapshots` table |
| `candles_4h_exchange_ts` | Latest 4h candle `open_time` | `market_snapshots` table |
| `funding_exchange_ts` | Latest funding event `funding_time` | `market_snapshots` table |
| `oi_exchange_ts` | OI response `timestamp` | `market_snapshots` table |
| `aggtrades_exchange_ts` | Latest aggTrade `event_time` | `market_snapshots` table |

**Enables:**
- Per-input staleness detection: `cycle_timestamp - <input>_exchange_ts`
- Per-input latency audit: `snapshot_build_finished_at - <input>_exchange_ts`
- Timing validation per data source

**Implementation:**
- Schema: [storage/schema.sql:237-244](c:\development\btc-bot\storage\schema.sql#L237)
- Migration: [storage/state_store.py:229-253](c:\development\btc-bot\storage\state_store.py#L229)
- Data Capture: [data/market_data.py:156-162](c:\development\btc-bot\data\market_data.py#L156)
- Persistence: [storage/repositories.py:55-73](c:\development\btc-bot\storage\repositories.py#L55)
- Model: [core/models.py:104-110](c:\development\btc-bot\core\models.py#L104)

---

### 2. Snapshot Build Timing Contract ✅

**Problem:** V3 stored total `latency_ms` but not explicit start/finish timestamps. Cannot audit snapshot construction timing post hoc.

**Solution:** Added explicit build timing fields:

| Field | Meaning |
|---|---|
| `snapshot_build_started_at` | Timestamp when `MarketDataAssembler.build_snapshot()` started |
| `snapshot_build_finished_at` | Timestamp when snapshot construction completed |

**Enables:**
- Build duration: `snapshot_build_finished_at - snapshot_build_started_at`
- Lookahead validation: verify snapshot finished before decision started
- Build latency outlier detection

**Implementation:**
- Schema: [storage/schema.sql:245-246](c:\development\btc-bot\storage\schema.sql#L245)
- Migration: [storage/state_store.py:229-253](c:\development\btc-bot\storage\state_store.py#L229)
- Data Capture: [data/market_data.py:103-104,138](c:\development\btc-bot\data\market_data.py#L103)
- Persistence: [storage/repositories.py:75-76](c:\development\btc-bot\storage\repositories.py#L75)
- Model: [core/models.py:112-114](c:\development\btc-bot\core\models.py#L112)

---

### 3. Per-Input Provenance + Freshness Contract ✅

**Status:** Already implemented in V3 via `source_meta_json`

**Evidence:** Production snapshot shows per-input provenance:
```json
{
  "book_ticker": {"latency_ms": 255.0, "source": "rest"},
  "candles_15m": {"latency_ms": 257.9, "source": "rest"},
  "candles_1h": {"latency_ms": 506.9, "source": "rest"},
  "candles_4h": {"latency_ms": 259.5, "source": "rest"},
  "funding_history": {"latency_ms": 259.2, "source": "rest"},
  "open_interest": {"latency_ms": 539.3, "source": "rest"},
  "aggtrade_15m": {
    "source": "rest",
    "coverage_ratio": 0.096,
    "clipped_by_limit": true,
    "first_event_time": "2026-04-23T19:30:00.199+00:00",
    "last_event_time": "2026-04-23T19:31:26.883+00:00"
  },
  "force_orders_60s": {"source": "none", "events_count": 0}
}
```

**Hardening:** Per-input exchange timestamps (requirement #1) enable explicit staleness calculation without parsing JSON.

---

### 4. Raw vs Normalized Contract ✅

**Decision:** **Hybrid approach** - persist both

- **Normalized fields:** OHLC, funding_rate, oi_value (queryable at SQL level)
- **Raw payloads:** JSON blobs (`candles_15m_json`, `funding_history_json`, etc.)
- **Preservation:** Each JSON payload includes `_exchange_raw` field with unmodified API response

**Rationale:**
- SQL queryability for common audits (ATR, price, OI)
- Full replay capability from raw payloads
- Deterministic recomputation from exact exchange truth

---

### 5. Replay-Safety Validation Coverage Matrix ✅

**Created:** [validation/replay_safety_coverage_matrix.md](c:\development\btc-bot\validation\replay_safety_coverage_matrix.md)

**Coverage:**
- 22 features: **VERIFIED** (1-to-1 or proxy)
- 6 features: **PARTIAL** (require time-series history)
- 1 feature: **BLOCKED** (funding_pct_60d - missing 60-day history)

**Classification:**

| Status | Count | Examples |
|---|---|---|
| **VERIFIED_1_TO_1** | 11 | ATR, EMA, equal_levels, funding_8h, oi_value, force_rate |
| **VERIFIED_PROXY** | 11 | Sweep/reclaim detection, CVD/TFI buckets, diagnostic margins |
| **PARTIAL** | 6 | OI delta, force spike, divergence, funding SMA (require prior snapshots) |
| **BLOCKED** | 1 | `funding_pct_60d` (60-day history not persisted per snapshot) |

**Validation Engine:** [validation/recompute_features.py](c:\development\btc-bot\validation\recompute_features.py)

---

### 6. Timing Validation Upgrade ✅

**Enhanced:** Per-input timestamp fields enable:

- **Per-input latency audit:**
  ```sql
  SELECT
    snapshot_id,
    (julianday(snapshot_build_finished_at) - julianday(candles_15m_exchange_ts)) * 86400 AS candles_15m_latency_sec,
    (julianday(snapshot_build_finished_at) - julianday(oi_exchange_ts)) * 86400 AS oi_latency_sec
  FROM market_snapshots
  WHERE cycle_timestamp > '2026-04-23'
  ```

- **Per-input staleness detection:**
  ```sql
  SELECT
    snapshot_id,
    (julianday(cycle_timestamp) - julianday(candles_15m_exchange_ts)) * 86400 AS candles_15m_staleness_sec,
    CASE
      WHEN candles_15m_staleness_sec > 900 THEN 'STALE'
      ELSE 'FRESH'
    END AS candles_15m_freshness
  FROM market_snapshots
  ```

- **Build timing breakdown:** `snapshot_build_started_at` → `snapshot_build_finished_at`

**Reports:** Can now generate per-input timing reports (previously only global latency)

---

### 7. Paper Fill Sanity Check ✅

**Status:** Already fixed in prior milestone (PAPER-FILL-FIX)

**Evidence:** No immediate TP exits with negative PnL observed after fix

**Not in scope for this hardening pass** (already addressed)

---

### 8. Acceptance Criteria ✅

**Verified:**

| Criterion | Status | Evidence |
|---|---|---|
| Schema extensions backward compatible | ✅ PASS | All new fields nullable, migration idempotent |
| Per-input timestamps persisted | ✅ PASS | Test: `test_quant_grade_lineage_persistence` |
| Build timing persisted | ✅ PASS | Test: `test_quant_grade_lineage_enables_build_timing_audit` |
| Staleness query works | ✅ PASS | Test: `test_quant_grade_lineage_enables_staleness_check` |
| No regression in existing tests | ✅ PASS | 214/214 passed |
| Migration safe for production | ✅ PASS | Idempotent ALTER TABLE with existence checks |

---

## Files Changed

### Schema & Persistence

| File | Lines | Change |
|---|---|---|
| [storage/schema.sql](c:\development\btc-bot\storage\schema.sql) | 237-246 | Added 8 quant-grade lineage columns to `market_snapshots` |
| [storage/state_store.py](c:\development\btc-bot\storage\state_store.py) | 60-76, 229-253 | Migration logic: check table exists, idempotent column addition |
| [storage/repositories.py](c:\development\btc-bot\storage\repositories.py) | 43-90 | Updated `insert_market_snapshot` to persist new fields |

### Data Models

| File | Lines | Change |
|---|---|---|
| [core/models.py](c:\development\btc-bot\core\models.py) | 104-114 | Added 8 fields to `MarketSnapshot` dataclass |

### Data Capture

| File | Lines | Change |
|---|---|---|
| [data/market_data.py](c:\development\btc-bot\data\market_data.py) | 103-104, 138, 156-177 | Extract per-input timestamps + build timing, pass to `MarketSnapshot` |

### Validation

| File | Lines | Purpose |
|---|---|---|
| [validation/replay_safety_coverage_matrix.md](c:\development\btc-bot\validation\replay_safety_coverage_matrix.md) | 1-320 | Feature recomputability classification + gaps |

### Tests

| File | Lines | Coverage |
|---|---|---|
| [tests/test_quant_grade_lineage.py](c:\development\btc-bot\tests\test_quant_grade_lineage.py) | 1-245 | Schema creation, persistence, nullable fields, staleness checks, build timing audit |

---

## Migration Safety

**Backward Compatibility:** ✅ YES

- All new columns nullable (`TEXT DEFAULT NULL`)
- Existing code works with NULL values
- Pre-hardening snapshots have NULL for new fields
- Post-hardening snapshots have populated fields

**Idempotency:** ✅ YES

- `CREATE TABLE IF NOT EXISTS` for initial creation
- `PRAGMA table_info()` check before `ALTER TABLE ADD COLUMN`
- Safe to re-run on existing production database

**Production Impact:** ✅ ZERO RISK

- Schema-only addition (no existing data modified)
- Existing queries unaffected
- New queries can filter for non-NULL quant-grade fields

---

## Test Results

**All tests pass:** 214/214

**New tests:** 5 (quant-grade lineage)

```
test_quant_grade_lineage_schema_created PASSED
test_quant_grade_lineage_persistence PASSED
test_quant_grade_lineage_nullable PASSED
test_quant_grade_lineage_enables_staleness_check PASSED
test_quant_grade_lineage_enables_build_timing_audit PASSED
```

**No regressions:** All existing Market Truth V3 tests still pass

---

## Deployment Readiness

**Status:** ✅ PRODUCTION-READY

**Recommended deployment sequence:**

1. **Deploy code** (schema migration runs automatically on first StateStore instantiation)
2. **Verify migration:** Check `market_snapshots` schema has new columns
3. **Verify first snapshot:** Check new fields populated (not NULL)
4. **Wait for 200+ cycles** (~50 hours)
5. **Generate reports:**
   - Staleness analysis per input
   - Build timing percentiles
   - Per-input latency audit
   - Replay safety validation

---

## Remaining Gaps

| Gap | Priority | Mitigation Path |
|---|---|---|
| Funding percentile (60d) | LOW | Future milestone: extend `funding_history_json` retention or add `funding_history_60d` table |
| Time-series feature warm-up | MEDIUM | Document in backtest replay: OI delta, divergence, force spike require N prior snapshots |
| CVD/TFI raw trade recomputation | N/A | Accepted: bucket-level persistence is validated proxy; raw trades not required for decision audit |

---

## Acceptance Verdict

**QUANT_GRADE_HARDENING: ✅ DONE**

**Definition:**
- Per-input timestamp lineage ✅
- Explicit build timing contract ✅
- Replay-safety coverage matrix ✅
- Per-input provenance (already in V3) ✅
- Raw vs normalized contract (hybrid, explicit) ✅
- Timing validation upgrade ✅
- All tests pass (214/214) ✅
- Migration safe for production ✅

**Next Milestone:** Deploy to production → collect 200+ cycles → validate staleness/timing/replay from quant-grade lineage fields

---

**Summary:** Market Truth V3 elevated to quant-grade source-of-truth. Explicit per-input timestamps, build timing contract, and replay-safety classification enable institutional-grade lineage audit.
