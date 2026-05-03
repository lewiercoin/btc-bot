# FORCE-ORDERS-BACKFILL-FEASIBILITY — Phase 1 Results

**Date:** 2026-05-03  
**Branch:** `claude/audit-wf-light-protocol-ZXDA9`  
**Milestone:** FORCE-ORDERS-BACKFILL-FEASIBILITY  
**Phase:** 1 (data source verification — read-only)  
**Status:** ⛔ BLOCKED — data source does not exist  

---

## Phase 1 Objective

Verify that `https://data.binance.vision` provides historical liquidation snapshot
files for BTCUSDT perpetual futures, as referenced in the milestone handoff:

> `https://data.binance.vision/?prefix=data/futures/um/daily/liquidationSnapshot/BTCUSDT/`

---

## Step 1.1 — HTTP Availability Checks

All requests returned **404**:

| File | HTTP Status |
|---|---|
| `BTCUSDT-liquidationSnapshot-2024-01-15.zip` | 404 |
| `BTCUSDT-liquidationSnapshot-2023-06-01.zip` | 404 |
| `BTCUSDT-liquidationSnapshot-2022-01-01.zip` | 404 |
| `BTCUSDT-liquidationSnapshot-2020-01-01.zip` | 404 |
| `BTCUSDT-liquidationSnapshot-2019-09-01.zip` | 404 |

---

## Step 1.1a — S3 Directory Listing (Root Cause)

S3 bucket listing confirmed: `liquidationSnapshot` **does not exist** as a data type
on data.binance.vision — neither under `daily/` nor `monthly/`.

**Available data types under `data/futures/um/daily/`:**

```
aggTrades
bookDepth
bookTicker
indexPriceKlines
klines
markPriceKlines
metrics
premiumIndexKlines
trades
```

**Available data types under `data/futures/um/monthly/`:**

```
aggTrades
bookTicker
fundingRate
indexPriceKlines
klines
markPriceKlines
premiumIndexKlines
trades
```

`liquidationSnapshot` is absent from both paths. No alternate spelling
(e.g., `forceOrder`, `liquidation`) was found in either listing.

---

## Step 1.2 — CSV Schema Inspection

**NOT APPLICABLE** — no files exist to download. Schema cannot be determined
from this source.

---

## Step 1.3 — Backfill Cutoff (force_orders live collector baseline)

Live collector started: **2026-04-17T14:13:16.521000+00:00 UTC**

Any historical backfill would need to end **before** this timestamp.

| Field | Value |
|---|---|
| `MIN(event_time)` (BTCUSDT) | `2026-04-17T14:13:16.521000+00:00` |
| `MAX(event_time)` (BTCUSDT) | `2026-04-23T17:02:10.586000+00:00` |
| `btcusdt_count` | 7,129 |

---

## Step 1.4 — Existing Row Count

```
total_rows: 7129
```

All 7,129 rows are BTCUSDT. No other symbols present.

---

## Known Issue #1 Assessment — UNIQUE Constraint

The `force_orders` table has **no UNIQUE constraint**:

```sql
CREATE TABLE IF NOT EXISTS force_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    event_time TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
    qty REAL NOT NULL,
    price REAL NOT NULL
);
```

Only an index exists: `idx_force_orders_symbol_time ON force_orders(symbol, event_time)`

**Impact if Phase 2 were to proceed:**
- `INSERT OR IGNORE` (idempotent pattern from `backfill_aggtrades.py`) would NOT work —
  no UNIQUE constraint to trigger the IGNORE.
- Duplicate inserts possible on re-run.
- Claude Code must decide: add UNIQUE constraint via migration, or use
  "check MAX(event_time) and only insert rows after last known" approach.

---

## Verdict

**Phase 1 = BLOCKED (CRITICAL)**

The proposed data source does not exist. `data.binance.vision` does not provide
historical liquidation/force-order snapshots for any date range.

**Phase 2 cannot proceed** until an alternative data source is identified and
confirmed by Claude Code.

---

## Questions for Claude Code

1. **Primary blocker:** `liquidationSnapshot` is absent from data.binance.vision.
   What is the alternative data source for historical force orders?  
   Known alternatives (not evaluated):
   - Binance REST API `/fapi/v1/forceOrders` (historical, but rate-limited and may have limited depth)
   - Third-party providers (CryptoQuant, Coinalyze — likely paid)
   - `data.binance.vision/data/futures/um/daily/trades/` (raw trades, not liquidations)
   - Accept that `force_order_spike` feature remains frozen for backtest

2. **UNIQUE constraint:** If a new data source is found and Phase 2 approved,
   which deduplication approach should be used?
   - Option A: Schema migration — add `UNIQUE(symbol, event_time, side)` constraint
   - Option B: Watermark approach — only insert rows where `event_time > MAX(event_time)` in DB
   - Claude Code must approve before schema changes.

3. **Scope re-evaluation:** Given that the data source assumption was incorrect,
   should this milestone be re-scoped to document `force_order_spike` as permanently
   frozen for backtest (no historical source available), or should alternative
   sources be investigated?

---

## Evidence

All checks performed on production server `root@204.168.146.253` (read-only, no DB mutations).

S3 listing URL used:
```
https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/daily/
https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/
```
