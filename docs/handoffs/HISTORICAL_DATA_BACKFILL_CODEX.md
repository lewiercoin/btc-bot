# CLAUDE HANDOFF -> CODEX

## Checkpoint

- Last commit: `d8fdf76` (milestone: DATA QUALITY FOUNDATION)
- Branch: `experiment-v2` (ready for deployment, but needs backfill first)
- Working tree: clean
- **BLOCKER:** oi_samples and cvd_price_history tables don't exist on production yet - bot will start with "unavailable" quality

## Production inspection results (2026-04-21)

**Current production state:**
- Branch: `experiment-v1-unblock-filters` (commit c9a4064)
- Schema: NO oi_samples, NO cvd_price_history tables yet
- **Action required:** Deploy experiment-v2 code/schema FIRST, then run backfill

**Available historical data on production:**

| Table | Records | Date Range | Freshness |
|-------|---------|------------|-----------|
| `open_interest` | 526,496 | 2020-09-01 → 2026-04-17 14:00 UTC | Stale (4 days) |
| `candles` (15m) | 197,262 | 2020-09-01 → 2026-04-17 19:15 UTC | Stale (4 days) |
| `aggtrade_buckets` (15m) | 195,175 | 2020-09-01 → 2026-04-17 14:00 UTC | Stale (4 days) |

**Conclusion:** Historical data IS available, but slightly stale. Backfill strategy: use historical tables as base + REST API to refresh last 4 days.

---

## Before you code

Read these files (mandatory):
1. `docs/analysis/DATA_QUALITY_MILESTONE_2026-04-21.md` - context
2. `storage/schema.sql` - table definitions (oi_samples, cvd_price_history)
3. `storage/repositories.py` - save_oi_sample(), save_cvd_price_bar()
4. `storage/state_store.py` - init_db() method (creates tables)
5. `data/rest_client.py` - Binance REST API methods
6. `settings.py` - DataQualityConfig (oi_baseline_days=60, cvd_divergence_bars=30)
7. `AGENTS.md` - discipline

---

## Milestone: HISTORICAL-DATA-BACKFILL

### Goal
Populate oi_samples and cvd_price_history tables with historical exchange data so bot starts with "ready" feature quality immediately after deployment.

### Why
DATA-INTEGRITY-V1 added persistence, but tables don't exist on production yet. Without backfill, bot will have "unavailable" quality for 60+ days until enough data accumulates naturally.

### Scope
One-time backfill scripts that:
1. Create tables if missing (via init_db())
2. Copy historical data from existing tables (open_interest, aggtrade_buckets)
3. Refresh stale data via REST API
4. Are idempotent and safe to run multiple times

---

## Implementation plan (based on inspection)

### Branch strategy
Create new branch from experiment-v2:
```bash
git checkout experiment-v2
git checkout -b historical-data-backfill
```

This ensures backfill code has access to new schema definitions.

---

## Task 1: OI Historical Backfill Script

**File:** `scripts/backfill_oi_samples.py`

**Algorithm (based on inspection findings):**

```python
1. Connect to DB (from settings.storage.db_path)
2. Run init_db() to create oi_samples table if missing
3. Calculate horizon: now - oi_baseline_days (default 60)
4. Query open_interest table for records >= horizon
5. For each record:
   INSERT OR IGNORE INTO oi_samples (symbol, timestamp, oi_value, source, captured_at)
   VALUES (?, ?, ?, 'historical_backfill', ?)
6. Fetch current OI from REST: /fapi/v1/openInterest
7. INSERT current OI with source='rest_current_backfill'
8. Report:
   - Samples inserted from open_interest
   - Current sample added from REST
   - Date range covered (oldest → newest)
   - Days covered (should be >= 60)
```

**Key details:**
- `INSERT OR IGNORE` handles duplicates safely (UNIQUE constraint on symbol+timestamp)
- Two sources: 'historical_backfill' (from open_interest table) + 'rest_current_backfill' (fresh from API)
- Respects DataQualityConfig.oi_baseline_days
- Logs summary clearly

**Acceptance criteria:**
- ✅ Creates oi_samples table if missing (via init_db())
- ✅ Copies historical data from open_interest (filtered by horizon)
- ✅ Adds fresh current snapshot from REST
- ✅ No duplicates (INSERT OR IGNORE)
- ✅ Idempotent (safe to run multiple times)
- ✅ Logs: samples inserted, date range, days covered
- ✅ Exit 0 on success, non-zero on failure

---

## Task 2: CVD Historical Backfill Script

**File:** `scripts/backfill_cvd_history.py`

**Algorithm (based on inspection findings):**

```python
1. Connect to DB (from settings.storage.db_path)
2. Run init_db() to create cvd_price_history table if missing
3. Calculate requirement: cvd_divergence_bars (default 30 bars of 15m)
4. Fetch last 30 klines (15m) from REST: /fapi/v1/klines
   - symbol=BTCUSDT, interval=15m, limit=30
5. For each kline:
   a. bar_time = open_time
   b. price_close = close price from kline
   c. Query aggtrade_buckets for matching bar (symbol, timeframe='15m', bucket_time=bar_time)
   d. If match found:
      cvd = aggtrade_buckets.cvd
      tfi = aggtrade_buckets.tfi
   e. Else (fresh data or gap):
      cvd = 0.0  # placeholder
      tfi = None
   f. INSERT OR IGNORE INTO cvd_price_history
      (symbol, timeframe, bar_time, price_close, cvd, tfi, source, captured_at)
      VALUES (?, '15m', ?, ?, ?, ?, 'historical_backfill', ?)
6. Report:
   - Bars inserted
   - Bars with real CVD (from aggtrade_buckets)
   - Bars with placeholder CVD (fresh data)
   - Date range covered
```

**Key details:**
- **Always fetch from REST klines** (ensures fresh price data for last 30 bars)
- Match with aggtrade_buckets for real CVD/TFI when available
- Use cvd=0.0 placeholder for fresh bars (acceptable - will accumulate going forward)
- Price data is CRITICAL (from klines, always fresh)
- CVD data is NICE-TO-HAVE (from aggtrade_buckets if available, else placeholder)

**Acceptance criteria:**
- ✅ Creates cvd_price_history table if missing (via init_db())
- ✅ Fetches last 30 klines (15m) from REST
- ✅ Matches with aggtrade_buckets for real CVD when available
- ✅ Uses cvd=0.0 placeholder for gaps
- ✅ No duplicates (INSERT OR IGNORE on bar_time)
- ✅ Idempotent (safe to run multiple times)
- ✅ Logs: bars inserted, real CVD count, placeholder count, date range
- ✅ Exit 0 on success, non-zero on failure

---

## Task 3: Backfill Orchestration Script

**File:** `scripts/run_backfill.py`

**Algorithm:**

```python
1. Connect to DB
2. Print: "Starting historical data backfill..."
3. Run backfill_oi_samples.py
   - Capture stdout/stderr
   - Check exit code
   - If non-zero: abort with error
4. Run backfill_cvd_history.py
   - Capture stdout/stderr
   - Check exit code
   - If non-zero: abort with error
5. Verify data completeness:
   a. Query oi_samples:
      - Count samples
      - Calculate days_covered (max(timestamp) - min(timestamp))
      - Required: days_covered >= 60 AND count >= 2
   b. Query cvd_price_history (timeframe='15m'):
      - Count bars
      - Required: count >= 30
6. Report status:
   ✅ READY: OI={days_covered} days ({count} samples), CVD={count} bars
   ⚠️ PARTIAL: OI or CVD below threshold (degraded quality expected)
   ❌ INSUFFICIENT: Critical gaps (unavailable quality expected)
7. Exit:
   - 0 if READY
   - 1 if PARTIAL or INSUFFICIENT
```

**Acceptance criteria:**
- ✅ Runs both backfills sequentially
- ✅ Aborts on error from either script
- ✅ Verifies completeness (60 days OI, 30 bars CVD)
- ✅ Reports clear status (READY/PARTIAL/INSUFFICIENT)
- ✅ Exit code reflects status (0=ready, 1=not ready)
- ✅ Logs clear instructions for operator

---

## Task 4: Backfill Verification Tests

**File:** `tests/test_backfill.py`

**Test cases:**

1. `test_backfill_oi_on_empty_table()`
   - Empty oi_samples table
   - Run backfill_oi_samples
   - Assert: samples inserted, days_covered >= 60

2. `test_backfill_oi_idempotent()`
   - Populated oi_samples table
   - Run backfill_oi_samples TWICE
   - Assert: count unchanged (no duplicates)

3. `test_backfill_cvd_on_empty_table()`
   - Empty cvd_price_history table
   - Run backfill_cvd_history
   - Assert: bars inserted, count >= 30, price_close present

4. `test_backfill_cvd_idempotent()`
   - Populated cvd_price_history table
   - Run backfill_cvd_history TWICE
   - Assert: count unchanged (no duplicates)

5. `test_backfill_cvd_uses_placeholder_for_gaps()`
   - Mock: aggtrade_buckets has gap
   - Run backfill_cvd_history
   - Assert: cvd=0.0 for gap, price_close present

6. `test_bootstrap_after_backfill_gives_ready_quality()`
   - Run full backfill
   - Create FeatureEngine
   - Call bootstrap_oi_history() and bootstrap_cvd_price_history()
   - Call compute() with fresh snapshot
   - Assert: features.quality["oi_baseline"].status == "ready"
   - Assert: features.quality["cvd_divergence"].status == "ready"

**Acceptance criteria:**
- ✅ 6+ tests pass
- ✅ Idempotency verified
- ✅ Placeholder CVD handling verified
- ✅ Bootstrap integration verified (quality "ready" after backfill)

---

## Critical implementation notes

### 1. Schema initialization
**MUST call init_db() in each backfill script:**
```python
from storage.state_store import StateStore

conn = sqlite3.connect(db_path)
state_store = StateStore(connection=conn, mode="PAPER", reference_equity=10000.0)
# This creates all missing tables including oi_samples, cvd_price_history
```

**Why:** Production doesn't have new tables yet. Backfill scripts must be deployment-safe.

### 2. Data freshness strategy
- **OI:** Historical from open_interest + current from REST (hybrid)
- **CVD:** Fresh klines from REST + historical CVD from aggtrade_buckets (best effort)

**Rationale:** Price must be fresh (last 4 days stale). CVD can be placeholder - will accumulate going forward.

### 3. Idempotency
**Use INSERT OR IGNORE everywhere:**
```sql
INSERT OR IGNORE INTO oi_samples (symbol, timestamp, oi_value, source, captured_at)
VALUES (?, ?, ?, ?, ?)
```

**Why:** UNIQUE constraints on (symbol, timestamp) and (symbol, timeframe, bar_time) prevent duplicates automatically.

### 4. Error handling
**Each script must:**
- Try/except DB operations
- Log errors clearly
- Exit with non-zero code on failure
- NOT leave partial/corrupted data

### 5. Logging
**Use structured logs:**
```python
LOG.info("OI backfill complete | samples=%d, oldest=%s, newest=%s, days_covered=%d",
         count, oldest_ts, newest_ts, days)
```

**Why:** Operator needs clear visibility into what was backfilled.

---

## Deployment workflow (after backfill complete)

### Step 1: Deploy experiment-v2 code to production
```bash
# On production server
cd /home/btc-bot/btc-bot
git fetch origin
git checkout experiment-v2
git pull origin experiment-v2
```

This creates the new schema (oi_samples, cvd_price_history tables).

### Step 2: Run backfill (ONE TIME)
```bash
# Still on production server
python scripts/run_backfill.py

# Expected output:
# Starting historical data backfill...
# OI backfill complete | samples=60, oldest=2026-02-20, newest=2026-04-21, days_covered=60
# CVD backfill complete | bars=30, real_cvd=26, placeholder=4, oldest=2026-04-21 13:00
# ✅ READY: OI=60 days (60 samples), CVD=30 bars
```

### Step 3: Restart bot
```bash
systemctl restart btc-bot
```

### Step 4: Verify bootstrap in logs
```bash
journalctl -u btc-bot -n 100 | grep "bootstrap"

# Expected output:
# Feature bootstrap summary | {"oi_summary": {"loaded_samples": 60, "oldest_timestamp": "2026-02-20T..."}, "cvd_summary": {"loaded_bars": 30, "oldest_timestamp": "2026-04-21T13:00..."}}
```

### Step 5: Check feature quality
```bash
# Via dashboard or logs
curl http://localhost:8080/api/feature-quality

# Expected:
# {"oi_baseline": {"status": "ready", ...}, "cvd_divergence": {"status": "ready", ...}}
```

---

## Constraints and risks

### Constraint 1: One-time execution
- Backfill is ONE-TIME before deployment
- NOT continuous (bot accumulates data naturally after deploy)
- If re-run: idempotent (no harm, no duplicates)

### Constraint 2: API rate limits
- Binance REST has rate limits (1200 requests/minute)
- Backfill uses 2 requests (current OI + 30 klines)
- Safe, well below limit

### Constraint 3: Data gaps
- If open_interest or aggtrade_buckets have gaps, backfill will too
- Acceptable: feature quality will be "degraded" for gaps, not "unavailable"
- Bot will fill gaps naturally going forward

### Risk 1: Stale data
- Current data is 4 days stale (2026-04-17 → 2026-04-21)
- Mitigation: REST API fetches fresh current snapshot
- Result: Last 60 days mostly historical + last 4 days fresh

### Risk 2: Schema not deployed
- If backfill runs before experiment-v2 deploy → tables don't exist
- Mitigation: init_db() creates tables automatically
- Result: Safe to run anytime after experiment-v2 checkout

### Risk 3: CVD placeholders
- Fresh bars may have cvd=0.0 placeholder
- Impact: CVD divergence detection starts from backfill point, accumulates forward
- Acceptable: Price data is correct (critical), CVD will mature naturally

---

## Acceptance criteria (full milestone)

**Milestone DONE when:**
1. ✅ All 3 scripts exist and run without errors
2. ✅ oi_samples table has >= 60 days of data after backfill
3. ✅ cvd_price_history table has >= 30 bars (15m) after backfill
4. ✅ Idempotency verified (can run multiple times safely)
5. ✅ Bootstrap test passes: quality "ready" after backfill
6. ✅ run_backfill.py reports "✅ READY" status
7. ✅ Tests pass (6+ tests in test_backfill.py)
8. ✅ Documentation: README section on backfill usage
9. ✅ Smoke test on production: deploy → backfill → restart → verify logs

---

## Commit discipline

**Commit message format:**
```
feat(backfill): add historical data backfill for OI/CVD

WHAT: One-time backfill scripts to populate oi_samples + cvd_price_history
WHY: DATA-INTEGRITY-V1 persistence tables empty, bot would start with "unavailable" quality
STATUS: [Task 1/2/3/4 done] - [specific achievement]

Details:
- Copies historical data from open_interest, aggtrade_buckets
- Refreshes stale data via REST API (current OI, fresh klines)
- Idempotent (INSERT OR IGNORE)
- Reports deployment readiness

Related: DATA-QUALITY-FOUNDATION (2026-04-21)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

Do NOT:
- Modify core pipeline (feature_engine, signal_engine, orchestrator)
- Add continuous backfill (this is one-time)
- Skip idempotency checks
- Merge to experiment-v2 before testing locally

---

## Your first response must contain

1. Confirmation you understand the inspection findings
2. Restatement of the algorithm for each backfill script
3. Questions about edge cases:
   - What if open_interest table has < 60 days?
   - What if REST API fails during backfill?
   - Should backfill abort or continue with partial data?
4. Implementation plan (ordered steps with file/test pairs)
5. Estimate: how many commits, approximate LOC

---

## Handoff summary

- **Builder:** Codex
- **Auditor:** Claude Code
- **Milestone:** HISTORICAL-DATA-BACKFILL
- **Branch:** Create from experiment-v2: `historical-data-backfill`
- **Merge gate:** Backfill works, tables populated, bootstrap verified, tests pass
- **Deployment blocker:** YES - must complete before experiment-v2 deployment

**This is CRITICAL for experiment-v2 deployment.** Without backfill, bot starts with "unavailable" quality and takes 60+ days to reach "ready" status.

---

## Open questions (answer in first response)

1. **Partial data acceptable?**
   - If open_interest has only 30 days (not 60), should backfill:
     a) Abort with error?
     b) Continue with warning (degraded quality)?
     c) Fetch remaining from REST (if available)?

2. **REST API failure handling?**
   - If /fapi/v1/openInterest fails, should backfill:
     a) Abort completely?
     b) Continue with historical data only (stale but better than nothing)?

3. **aggtrade_buckets gap handling?**
   - If 10/30 bars have no matching aggtrade_buckets, should:
     a) All 10 get cvd=0.0 placeholder?
     b) Try to fetch fresh aggTrades from REST (if possible)?

Answer these, then implement with your answers encoded in script behavior.
