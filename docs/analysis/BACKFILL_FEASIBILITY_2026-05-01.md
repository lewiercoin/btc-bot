# DATA-BACKFILL-V1: Step 0 Feasibility Report

**Date:** 2026-05-01  
**Builder:** Cascade  
**Milestone:** DATA-BACKFILL-V1  
**Step:** 0 (research only — no import code)

---

## Summary

**Verdict: GO**

Both data types (aggtrades and open interest) are fully available on `data.binance.vision`
at no cost. No paid sources required. Backfill of all known gaps is feasible.

---

## Gaps to Fill (from DECISIONS_LOG.md 2026-04-30)

| Data type | Gap | Size |
|---|---|---|
| `aggtrade_15m` | 2026-03-28 → 2026-04-17 | 20 days |
| `aggtrade_15m` | 7 smaller gaps (pre-2026-03) | Various |
| `open_interest` | 2025-06-05 → 2026-01-01 | ~210 days |
| `open_interest` | Later April gaps | Small |

---

## Source 1: AggTrades

### URL checked
`https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=data/futures/um/monthly/aggTrades/BTCUSDT/`

### Availability: YES

Monthly files confirmed present:

| File | Size | Uploaded |
|---|---|---|
| `BTCUSDT-aggTrades-2026-01.zip` | 543 MB | 2026-02-01 |
| `BTCUSDT-aggTrades-2026-02.zip` | 1007 MB | 2026-03-01 |
| `BTCUSDT-aggTrades-2026-03.zip` | 799 MB | 2026-04-01 |
| `BTCUSDT-aggTrades-2026-04.zip` | 508 MB | 2026-05-01 |

**Note:** 2026-04 monthly file was uploaded 2026-05-01 (today) — all of April is available.

### Format
CSV with columns (USD-M Futures `/fapi/v1/aggTrades` format):

| AggTradeId | Price | Quantity | FirstTradeId | LastTradeId | Timestamp | WasBuyerMaker |
|---|---|---|---|---|---|---|

- `Timestamp`: Unix milliseconds
- `WasBuyerMaker`: `true` = taker is seller, `false` = taker is buyer
- No header row in file

### Gap coverage

| Gap | Files needed | Status |
|---|---|---|
| 2026-03-28 → 2026-03-31 | `2026-03.zip` | ✅ covered |
| 2026-04-01 → 2026-04-17 | `2026-04.zip` | ✅ covered |
| Pre-2026 smaller gaps | Earlier monthly files (available back to 2020-09) | ✅ covered |

### Granularity fit assessment
- Source: individual trades (raw tick data)
- Target: `aggtrade_buckets` (15m, columns: `taker_buy_volume`, `taker_sell_volume`, `tfi`, `cvd`)
- Fit: **REQUIRES BUCKETING** — raw trades must be aggregated into 15m windows
- Bucketing logic:
  - `taker_buy_volume` = sum of `Quantity` where `WasBuyerMaker = false`
  - `taker_sell_volume` = sum of `Quantity` where `WasBuyerMaker = true`
  - `tfi` = `(taker_buy - taker_sell) / (taker_buy + taker_sell)` (zero if no trades)
  - `cvd` = running `(taker_buy - taker_sell)` within backfill window (see caveat below)
- CVD caveat: CVD is cumulative. Backfill window CVD will be self-contained (starts from 0
  at window start). The feature engine uses `cvd_price_history` for divergence detection,
  which is built from per-bucket CVD values. This is sufficient for replay purposes.

### Download size warning
Files are large (500MB–1GB each compressed). Processing should happen on the production
server (or a machine with the DB), not locally.

---

## Source 2: Open Interest

### URL checked
`https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=data/futures/um/daily/metrics/BTCUSDT/`

### Availability: YES (daily path only)

**Critical note:** The monthly metrics path
(`data/futures/um/monthly/metrics/BTCUSDT/`) is **EMPTY** — no files.
Must use **daily** path.

Daily files confirmed present:

- Start: `BTCUSDT-metrics-2020-09-01.zip` (uploaded 2026-03-18)
- End: `BTCUSDT-metrics-2026-04-30.zip` (uploaded 2026-05-01)
- Continuous daily coverage from 2020-09-01 to 2026-04-30 ✅
- File size: ~11 KB per file (~2.3 MB total for the 7-month OI gap)

### Format
CSV from Binance futures metrics endpoint. Based on Binance API documentation
(`/futures/data/openInterestHist`), columns are:

| create_time | symbol | sum_open_interest | sum_open_interest_value | count_toptrader_long_short_ratio | sum_toptrader_long_short_ratio | count_long_short_ratio | sum_taker_long_short_vol_ratio |
|---|---|---|---|---|---|---|---|

- `create_time`: Unix milliseconds
- `sum_open_interest`: OI in contracts (matches `oi_value` units in bot DB)
- Granularity: **5 minutes** per row (288 rows per day)

**Verification required before Step 1:** Actual column names must be confirmed by
inspecting one downloaded file. The column mapping above is based on Binance API
documentation; the CSV header in the zip may differ slightly (e.g. no header row,
different order). This MUST be verified before writing import code.

### Gap coverage

| Gap | Files needed | Count | Status |
|---|---|---|---|
| 2025-06-05 → 2025-12-31 | Daily files per day | ~210 files | ✅ covered |
| 2026-04 gaps | 2026-04-xx daily files | Per day | ✅ covered |

### Granularity fit assessment
- Source: 5-minute OI snapshots (288 rows/day)
- Target: `open_interest` table (15m gap threshold in `db_status.py`)
- Fit: **COMPATIBLE** — two options for Step 1:
  - Option A: Import all 5m rows (288/day). Gap detection at 15m threshold will show 0 gaps.
    Extra resolution is harmless; the feature engine uses the latest value before cycle time.
  - Option B: Sample every 3rd row (take :00, :15, :30, :45 aligned rows). Matches live
    collection cadence exactly.
  - **Recommendation for Step 1: Option A** (simpler, no alignment logic, no data loss)
- Units: `sum_open_interest` in contracts = same as live-collected `oi_value` ✅

---

## Plan B Assessment (if data.binance.vision unavailable)

Plan B was not needed — both data types are available. Documented for completeness:

- **CoinGecko API (free)**: Does not provide historical futures OI at sub-daily granularity.
  Not suitable.
- **alternative.me**: BTC Fear & Greed only. Not relevant.
- **Binance REST API `/futures/data/openInterestHist`**: Only 30 days of history. Confirmed
  insufficient for the 7-month gap.
- **Conclusion**: No viable free Plan B exists. `data.binance.vision` is the only
  feasible free source.

---

## Schema Compatibility

### `open_interest` table
```sql
CREATE TABLE IF NOT EXISTS open_interest (
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,   -- ISO-8601 UTC
    oi_value REAL NOT NULL,    -- contracts
    UNIQUE(symbol, timestamp)
);
```
Mapping from metrics CSV:
- `symbol` → `'BTCUSDT'` (constant)
- `timestamp` → `create_time` converted from Unix ms to ISO-8601 UTC
- `oi_value` → `sum_open_interest` (contracts, same units as live collection)

### `aggtrade_buckets` table
```sql
CREATE TABLE IF NOT EXISTS aggtrade_buckets (
    symbol TEXT NOT NULL,
    bucket_time TEXT NOT NULL,   -- ISO-8601 UTC, start of 15m window
    timeframe TEXT NOT NULL,     -- '15m'
    taker_buy_volume REAL NOT NULL,
    taker_sell_volume REAL NOT NULL,
    tfi REAL NOT NULL,
    cvd REAL NOT NULL,
    UNIQUE(symbol, timeframe, bucket_time)
);
```
Derivable from raw aggTrades by bucketing per 15m window.

---

## Idempotency Note

Both imports must be safe to re-run:
- `open_interest`: `UNIQUE(symbol, timestamp)` → `INSERT OR IGNORE` is sufficient
- `aggtrade_buckets`: `UNIQUE(symbol, timeframe, bucket_time)` → `INSERT OR IGNORE` is sufficient
- Overlap with existing data (e.g. 2026-03 file contains days already in DB) handled
  automatically by `INSERT OR IGNORE`

---

## Step 0 Verdict

| Data type | Source | Available | Format fit | Verdict |
|---|---|---|---|---|
| `aggtrade_15m` | `data.binance.vision` monthly aggTrades | ✅ YES (2026-03, 2026-04) | Requires bucketing (straightforward) | **GO** |
| `open_interest` | `data.binance.vision` daily metrics | ✅ YES (2020-09-01 → 2026-04-30) | Compatible (5m → direct import) | **GO** |

**Overall Verdict: GO**

Pre-conditions for Step 1:
1. Verify actual CSV column names by inspecting one metrics zip file before writing
   import code (column `sum_open_interest` assumed, must confirm)
2. Verify aggTrades file has no header row (confirmed by Binance README format spec)
3. Step 1 implementation must be idempotent and include post-import gap check

---

## References

- S3 listing: `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision`
- Monthly aggTrades: `data/futures/um/monthly/aggTrades/BTCUSDT/`
- Daily metrics: `data/futures/um/daily/metrics/BTCUSDT/`
- Monthly metrics: `data/futures/um/monthly/metrics/BTCUSDT/` — **EMPTY, do not use**
- Binance public data README: `https://github.com/binance/binance-public-data/`
- Known gaps source: `docs/DECISIONS_LOG.md` entry 2026-04-30 (NEW_BASELINE_DATE_OPTUNA)
- Bot schema: `storage/schema.sql`
