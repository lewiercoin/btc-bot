# Data Quality Milestone (2026-04-21)

## Classification

**Milestone Type:** Infrastructure - Data Quality Foundation

**Status:** COMPLETE - Ready for validation via EXPERIMENT-V2

**Date:** 2026-04-21

**Significance:** First time bot has complete, correct, restart-safe data contracts.

---

## Problem Statement (Historical Context)

Prior to this milestone, the bot suffered from **two critical data quality gaps**:

### Gap 1: Ephemeral Data (No Persistence)
- OI baseline reset on every restart → artificial "cold start" penalty
- CVD divergence lost history after restart → detection unreliable
- Feature quality invisible → no distinction between mature/degraded/unavailable data
- **Impact:** Restart = throw away days of accumulated state

### Gap 2: Paper Execution Corruption
- Paper fills used `signal.entry_price` (reference level) instead of `snapshot.price` (actual market)
- No execution records → zero audit trail
- PnL metrics corrupted by unrealistic fill assumptions
- **Impact:** Paper results not comparable to live, optimization misleading

---

## Solution: Two Integrated Fixes

### Fix 1: DATA-INTEGRITY-V1 (Commit 7ebf2d2)

**What was implemented:**

1. **Persistent OI samples** (`oi_samples` table)
   - Append-only storage
   - Bootstrap on restart from DB
   - Config-driven horizon (60 days default)
   - **Result:** OI baseline survives restart

2. **Persistent CVD/price history** (`cvd_price_history` table)
   - Bar-level storage (price + CVD + TFI)
   - Bootstrap on restart from DB
   - Config-driven requirement (30 bars default)
   - **Result:** CVD divergence detection survives restart

3. **Feature quality contracts** (`FeatureQuality` model)
   - Status: ready | degraded | unavailable
   - Reason codes + metadata + provenance
   - Propagates through `MarketSnapshot` → `Features`
   - **Result:** Explicit visibility into data maturity

4. **Operational visibility**
   - Bootstrap summary at startup
   - Per-cycle quality logging
   - Dashboard endpoint: `/api/feature-quality`
   - **Result:** Observable data state

**Architecture principle:**
> Persistence + bootstrap > restart-from-zero warmup

**Files changed:** 28 files, +1709 insertions

**Tests:** 20 new tests, all pass

**Audit:** `docs/audits/AUDIT_DATA_INTEGRITY_V1_2026-04-21.md` (verdict: DONE)

---

### Fix 2: Paper Execution Realism (Commit df30615)

**What was fixed:**

1. **Fill price correction**
   - Before: `fill_price = signal.entry_price` (reference level)
   - After: `fill_price = snapshot.price` (actual market price)
   - **Result:** Paper fills realistic

2. **Execution audit trail**
   - Before: No execution records
   - After: `executions` table populated with `requested_price` + `filled_price`
   - **Result:** Complete audit trail for paper positions

3. **PnL integrity**
   - Before: Corrupted by unrealistic fills
   - After: Correct entry_price from actual snapshot
   - **Result:** Paper PnL comparable to live

4. **Dashboard visibility**
   - New fields: `signal_entry_reference`, `has_execution_record`
   - Labels: "Signal Reference" vs "Fill Entry"
   - Flag: trades without execution records (pre-fix legacy)
   - **Result:** Observable fill realism

**Files changed:** 11 files, +499 insertions

**Tests:** 5 new tests (`test_paper_fill_fix.py`), all pass

---

## Combined Impact

These two fixes together create **the first complete data quality foundation**:

| Aspect | Before | After (2026-04-21) |
|--------|--------|-------------------|
| **OI baseline** | Lost on restart | Persistent, restart-safe |
| **CVD divergence** | Lost on restart | Persistent, restart-safe |
| **Feature quality** | Invisible | Explicit (ready/degraded/unavailable) |
| **Paper fills** | Reference levels (wrong) | Snapshot prices (correct) |
| **Execution trail** | Missing | Complete audit records |
| **PnL metrics** | Corrupted | Realistic |
| **Bootstrap** | None | Automatic from DB |
| **Observability** | Logs only | Dashboard + structured quality |

---

## Expected Validation via EXPERIMENT-V2

**EXPERIMENT-V2 composition:**
- Base: `main` with both fixes (DATA-INTEGRITY + paper execution)
- Profile: `experiment` (relaxed filters from v1)
- Purpose: Validate data quality improvements under same throughput config

**Comparison baseline:**
- EXPERIMENT-V1: throughput validated, but corrupted data (no persistence, wrong fills)
- EXPERIMENT-V2: same throughput config, clean data

**What we will observe:**

1. **Restart behavior**
   - v1: OI/CVD reset → "unavailable" quality after restart
   - v2: OI/CVD bootstrap → "ready" quality immediately after restart with sufficient history

2. **Fill realism**
   - v1: fills at signal.entry_price (optimistic)
   - v2: fills at snapshot.price (realistic)

3. **PnL comparability**
   - v1: paper PnL not comparable to live (corrupted fills)
   - v2: paper PnL comparable to live (realistic fills)

4. **Diagnostic clarity**
   - v1: no visibility into data maturity
   - v2: explicit quality states in logs + dashboard

---

## Hypothesis

**Before these fixes:**
- Restart = penalty (lose accumulated state)
- Paper results = optimistic (unrealistic fills)
- Impossible to distinguish "bad setup" from "immature data"

**After these fixes:**
- Restart = continuity (restore accumulated state)
- Paper results = realistic (actual market fills)
- Explicit visibility: ready vs degraded vs unavailable

**Expected outcome in EXPERIMENT-V2:**
- More stable performance across restarts
- More realistic paper PnL (likely lower due to realistic fills, but comparable to live)
- Clearer diagnostics (reject "unavailable" data explicitly, not silently)

---

## Significance for Future Milestones

### MODELING-V1 (Next)
- Builds on clean data foundation
- Context-aware filters depend on reliable OI/CVD/feature quality
- Session/volatility classification requires mature data contracts

### EXECUTION-REALISM-V1 (After MODELING)
- Spread/slippage modeling builds on correct fill prices
- Paper execution already realistic at base level
- Only need to add spread cost + slippage assumptions

### OPTUNA-RECALIBRATION-V1 (After EXECUTION-REALISM)
- Parameter tuning on clean data
- Walk-forward validation with realistic costs
- No hidden data quality gaps

---

## Risk Assessment

**What could go wrong in EXPERIMENT-V2:**

1. **Bootstrap overhead**
   - Risk: Startup slower due to loading OI/CVD history
   - Mitigation: Tested in smoke tests, <1s overhead expected

2. **Lower paper PnL**
   - Risk: Realistic fills show lower PnL than v1 (wrong fills)
   - Mitigation: This is EXPECTED and CORRECT - v1 PnL was artificially inflated

3. **Quality "degraded" states**
   - Risk: More explicit rejections due to quality awareness
   - Mitigation: This is TRANSPARENCY, not regression - previously silent

**None of these are bugs - they are correct behavior.**

---

## Historical Marker

**This commit (experiment-v2 0607b3e) is the dividing line:**

- **Before 2026-04-21:** Bot with ephemeral data + corrupted paper execution
- **After 2026-04-21:** Bot with persistent data + realistic paper execution

All future work builds on this foundation.

**Validation checkpoint:** EXPERIMENT-V2 deployment and comparison vs v1.

**Documentation:**
- Audit: `docs/audits/AUDIT_DATA_INTEGRITY_V1_2026-04-21.md`
- Analysis: `docs/analysis/DATA_QUALITY_MILESTONE_2026-04-21.md` (this file)
- Tracker: `docs/MILESTONE_TRACKER.md` (updated)

---

## Bottom Line

**Question:** Is the bot ready for production after these fixes?

**Answer:** The data foundation is ready. The bot now has:
- ✅ Restart-safe persistence
- ✅ Realistic paper execution
- ✅ Quality contracts
- ✅ Audit trail
- ✅ Observable state

**But:** Filters are still globally relaxed (experiment profile). MODELING-V1 will add context-aware filters (session/volatility) to replace global relaxation.

**Timeline:**
1. **Now (2026-04-21):** Data quality foundation complete
2. **EXPERIMENT-V2:** Validate data quality improvements
3. **MODELING-V1:** Add context-aware filters
4. **Production-ready:** After MODELING-V1 + validation

This milestone is the **necessary foundation** for all future improvements.
