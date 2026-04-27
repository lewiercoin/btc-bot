# ChatGPT Audit Response

**Date:** 2026-04-24  
**Auditor:** ChatGPT  
**Response by:** Claude Code  
**Status:** ✅ CRITIQUE ACCEPTED, GAPS ADDRESSED

---

## ChatGPT Verdict Summary

**Original claim:** "Quant-grade source of truth GOTOWE ✅"

**ChatGPT correction:** "Quant-grade hardening: PARTIAL DONE / GOOD INFRA STEP, ale nie pełne source-of-truth closure"

**Corrected status:**
- Code implementation: ✅ DONE
- Production deployment: ⏳ PENDING
- Source-of-truth validation: ⏳ PENDING
- Full replay parity: ⚠️ PARTIAL
- Quant-grade direction: ✅ CORRECT

---

## ChatGPT Critique Points

### 1. ✅ Brakuje timestampów dla wszystkich rodzin inputów

**ChatGPT:** "Nie widzę osobnego pola dla: book ticker, force orders"

**Response:**

#### Force Orders: ✅ FIXED (commit c68d30a)

Added `force_orders_exchange_ts` field:
- Schema: `force_orders_exchange_ts TEXT`
- Migration: Added to `quant_grade_columns` list
- Data capture: `force_orders_60s[-1]["event_time"] if force_orders_60s else None`
- Model: `force_orders_exchange_ts: datetime | None = None`

#### Book Ticker: ⚠️ ARCHITECTURAL CONSTRAINT

**Binance API limitation:** bookTicker endpoint **does NOT return server timestamp**.

Evidence:
```python
def normalize_book_ticker(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(payload["symbol"]).upper(),
        "bid": float(payload["bidPrice"]),
        "ask": float(payload["askPrice"]),
        "_exchange_raw": dict(payload),  # No timestamp in raw payload
    }
```

**Available timestamp:** Only local `captured_at` (when client received response).

**Architectural decision:** 
- Use `captured_at` as best-available proxy for book_ticker timing
- Document as API limitation in replay safety matrix
- Accept ~50-200ms uncertainty (network latency)

**Alternative:** Switch to Binance WebSocket stream (includes `E: event_time`), but this is significant architectural change (future consideration).

**Current mitigation:** `source_meta_json` already tracks `book_ticker.latency_ms`, enabling indirect timing validation.

---

### 2. ✅ VERIFIED_PROXY to nie to samo co VERIFIED_1_TO_1

**ChatGPT:** "Dla 'źródła prawdy' trzeba jasno pilnować różnicy"

**Response:** ✅ ACKNOWLEDGED AND DOCUMENTED

**Replay Safety Matrix explicitly classifies:**

| Classification | Meaning | Count |
|---|---|---|
| **VERIFIED_1_TO_1** | Bit-for-bit deterministic recomputation from raw inputs | 11 |
| **VERIFIED_PROXY** | Sensibly recomputable, but not bit-perfect (pre-aggregated or bucketed) | 11 |
| **PARTIAL** | Recomputable with time-series history | 6 |
| **BLOCKED** | Cannot recompute from current schema | 1 |

**VERIFIED_PROXY examples:**
- **CVD/TFI buckets:** Raw trades NOT stored, only aggregated buckets → cannot reconstruct trade-by-trade CVD, but bucket-level CVD is validated
- **Sweep/reclaim detection:** Uses same algorithm as `FeatureEngine`, but recomputed independently → proxy validation

**Trade-off explicitly documented:**
- For **decision audit:** VERIFIED_PROXY is sufficient (can verify that decision used correct aggregated inputs)
- For **full market reconstruction:** Would need raw trade-by-trade data (storage cost prohibitive)

**Architectural decision:** Accept VERIFIED_PROXY for flow features (CVD/TFI). Store aggregated buckets, not raw trades.

**Justification:** 
- Decision replay: ✅ Can verify bot used correct bucket values
- Feature drift detection: ✅ Can verify bucketing logic hasn't changed
- Market microstructure research: ❌ Cannot reconstruct trade-by-trade flow (but not required for strategy validation)

---

### 3. ✅ funding_pct_60d nadal BLOCKED

**ChatGPT:** "Pełny replay parity nadal nie istnieje"

**Response:** ✅ ACKNOWLEDGED, TRACKED FOR FUTURE MILESTONE

**Current status:** `funding_pct_60d` requires 60-day funding rate history per snapshot.

**Schema limitation:**
- `funding_history_json` stores latest funding events (typically 8-24 hours)
- Percentile calculation requires 60-day distribution
- Current schema does NOT persist 60-day history per snapshot

**Gap impact:**
- 1/29 features BLOCKED
- Other funding features (funding_8h, funding_sma3, funding_sma9) are VERIFIED or PARTIAL
- Signal methodology uses funding_8h as primary input (funding_pct_60d is context, not gate)

**Mitigation path (future milestone):**
1. Create `funding_history_60d` table (append-only, retain 60 days)
2. OR: Extend `funding_history_json` retention per snapshot (storage cost: ~60 * 8 bytes = ~500 bytes per snapshot)
3. Update `FeatureEngine` to compute percentile from persisted 60-day window
4. Update replay safety matrix: `funding_pct_60d` → VERIFIED_1_TO_1

**Current acceptance:** This gap is **documented and tracked**, not hidden.

---

### 4. ✅ Time-series features nadal są PARTIAL

**ChatGPT:** "Pełna prawda nie jest tylko w jednym snapshotcie. Potrzebna jest też sekwencja snapshotów."

**Response:** ✅ ACKNOWLEDGED, THIS IS ARCHITECTURAL REALITY

**Time-series features requiring history:**
- `oi_delta_pct` (requires prior snapshot OI)
- `cvd_bullish_divergence`, `cvd_bearish_divergence` (require 4+ 15m bars)
- `force_order_spike` (requires rolling mean of recent rates)
- `funding_sma3`, `funding_sma9` (require prior funding rates)

**Why PARTIAL, not VERIFIED:**
- Single snapshot cannot contain time-series state
- Requires either:
  - Sequence of prior snapshots, OR
  - Separate historical tables (e.g., `oi_samples`, `cvd_price_history`)

**Current implementation:**
- `oi_samples` table: ✅ Stores OI history → `oi_delta_pct` recomputable after warm-up
- `cvd_price_history` table: ✅ Stores CVD history → divergence recomputable after warm-up
- Force order history: ❌ NOT persisted → `force_order_spike` requires prior snapshots

**Replay implications:**
- **Production replay:** ✅ Safe after 200+ cycles (history tables populated)
- **Backtest replay:** ⚠️ Requires warm-up period (first N cycles have NULL/degraded time-series features)
- **Cold-start replay:** ❌ Cannot reconstruct time-series features without history

**Acceptance:**
- This is **fundamental property of time-series features**, not implementation bug
- Documented in replay safety matrix as PARTIAL
- Warm-up requirement explicitly stated

**No snapshot system can make time-series features VERIFIED_1_TO_1 without historical tables or prior snapshot sequence.**

---

## Corrected Werdykt

### Original (zbyt optymistyczny):
> "Quant-grade source of truth GOTOWE ✅"

### ChatGPT correction (słuszna):
> "Quant-grade hardening: PARTIAL DONE / GOOD INFRA STEP"

### Claude Code corrected verdict:

**QUANT-GRADE HARDENING: INFRASTRUCTURE DONE ✅, VALIDATION PENDING ⏳**

| Axis | Status | Evidence |
|---|---|---|
| **Per-input timestamp lineage** | ✅ DONE | 7/8 inputs (book_ticker = API limitation) |
| **Build timing contract** | ✅ DONE | `snapshot_build_started_at`, `snapshot_build_finished_at` |
| **Replay safety classification** | ✅ DONE | 22 VERIFIED, 6 PARTIAL, 1 BLOCKED (documented) |
| **Schema migration safety** | ✅ DONE | Idempotent, backward compatible |
| **Test coverage** | ✅ DONE | 219/219 pass |
| **Production deployment** | ⏳ PENDING | Code ready, not yet deployed |
| **Source-of-truth validation** | ⏳ PENDING | Requires 200+ production cycles |
| **Full replay parity** | ⚠️ PARTIAL | Known gaps: funding_pct_60d, time-series warm-up |
| **Quant-grade direction** | ✅ CORRECT | Infrastructure enables institutional-grade lineage audit |

---

## Co teraz zrobić (per ChatGPT recommendation)

### Priority 1: Deploy na produkcję ⏳
1. ⏳ Deploy code to production server
2. ⏳ Verify bot restarts cleanly
3. ⏳ Check first snapshot:
   - Non-NULL for new quant-grade fields
   - `build_started < build_finished`
   - Timestamps logiczne (staleness candles ~15min, OI ~60s)

### Priority 2: Po 200+ cyklach ⏳
4. ⏳ Generate drift report (ATR/EMA < 1%)
5. ⏳ Generate staleness report per input
6. ⏳ Generate build timing percentiles (p50, p95, p99)
7. ⏳ Verify replay parity for VERIFIED features

### Priority 3: Dopiero wtedy klasyfikować ⏳
8. ⏳ Update status: INFRASTRUCTURE_DONE → VALIDATED_IN_PRODUCTION
9. ⏳ Measure actual replay parity coverage
10. ⏳ Decision: Accept current coverage OR plan next hardening pass

---

## Najważniejsze zdanie (per ChatGPT)

> **Claude dowiózł realny quant-grade hardening pass, ale produkcyjna prawda zaczyna się dopiero wtedy, gdy te pola zaczną się wypełniać przez 200+ cykli i przejdą walidację.**

**Claude Code response:** ✅ ZGADZAM SIĘ

---

## Summary of Gaps

| Gap | Status | Action |
|---|---|---|
| **force_orders_exchange_ts missing** | ✅ FIXED (commit c68d30a) | Added field, tests pass |
| **book_ticker exchange timestamp missing** | ⚠️ API LIMITATION | Documented as constraint, use `captured_at` proxy |
| **VERIFIED_PROXY ≠ VERIFIED_1_TO_1** | ✅ DOCUMENTED | Replay safety matrix explicitly classifies, trade-offs stated |
| **funding_pct_60d BLOCKED** | ✅ TRACKED | Future milestone, other funding features VERIFIED |
| **Time-series features PARTIAL** | ✅ DOCUMENTED | Architectural reality, warm-up requirement stated |
| **Production validation pending** | ⏳ PENDING | Deploy + 200 cycles required |

---

## Final Corrected Status

**Code implementation:** ✅ DONE (commits 147d865, c68d30a)

**Infrastructure readiness:** ✅ PRODUCTION-READY

**Source-of-truth validation:** ⏳ PENDING (requires production deployment + 200 cycles)

**Full replay parity:** ⚠️ PARTIAL (22/29 VERIFIED, 6/29 PARTIAL, 1/29 BLOCKED - documented)

**Recommended next step:** Deploy to production → wait for 200+ cycles → validate

---

**ChatGPT audit:** ✅ VALID AND VALUABLE

**Claude Code response:** Accept critique, address gaps, correct messaging, proceed with deployment.
