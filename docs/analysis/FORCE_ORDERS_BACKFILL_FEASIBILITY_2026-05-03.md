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

## Step 1.1 — HTTP Availability Checks (run twice — same result both times)

All requests returned **404** for all years and all specific dates tested:

| File | HTTP Status |
|---|---|
| `BTCUSDT-liquidationSnapshot-2024-01-15.zip` | 404 |
| `BTCUSDT-liquidationSnapshot-2023-06-01.zip` | 404 |
| `BTCUSDT-liquidationSnapshot-2022-06-15.zip` | 404 |
| `BTCUSDT-liquidationSnapshot-2022-01-01.zip` | 404 |
| `BTCUSDT-liquidationSnapshot-2021-01-01.zip` | 404 |
| `BTCUSDT-liquidationSnapshot-2020-09-01.zip` | 404 |
| `BTCUSDT-liquidationSnapshot-2020-01-01.zip` | 404 |
| `BTCUSDT-liquidationSnapshot-2019-09-01.zip` | 404 |

Verbose curl for `2022-06-15.zip` confirms the S3-level error (not a proxy/CDN artefact):

```
< HTTP/2 404
< server: AmazonS3
< x-cache: Error from cloudfront
<Error><Code>NoSuchKey</Code>
  <Message>The specified key does not exist.</Message>
  <Key>data/futures/um/daily/liquidationSnapshot/BTCUSDT/
       BTCUSDT-liquidationSnapshot-2022-06-15.zip</Key>
</Error>
```

This is a definitive S3 `NoSuchKey` — the object does not exist in the bucket.

---

## Step 1.1a — S3 Directory Listing (Root Cause)

S3 bucket listing (max-keys=200, `IsTruncated=false`) confirmed: `liquidationSnapshot`
**does not exist** as a data type on data.binance.vision — neither under `daily/`
nor `monthly/`. The complete list of all types is:

**`data/futures/um/daily/` (complete — 9 types, IsTruncated=false):**

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

**`data/futures/um/monthly/` (complete — 8 types, IsTruncated=false):**

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
(`forceOrder`, `liquidation`, `forceOrders`) was found in either listing.

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

## Step 1.2 (additional) — Binance REST API `/fapi/v1/forceOrders`

As part of Phase 3 pre-investigation (to give Claude Code complete information
for re-scope adjudication), the REST endpoint was tested:

| Target | URL | Result |
|---|---|---|
| Recent (no date filter) | `/fapi/v1/forceOrders?symbol=BTCUSDT&limit=5` | **401 Unauthorized** |
| April 2024 | `...&startTime=2024-04-01ms&endTime=2024-04-02ms` | **401 Unauthorized** |
| January 2022 | `...&startTime=2022-01-01ms&endTime=2022-01-02ms` | **401 Unauthorized** |

`/fapi/v1/forceOrders` **requires API key authentication** for all requests.
This endpoint cannot be used without the bot's FAPI credentials.

Note: Even with authentication, Binance FAPI historical depth for this endpoint
is typically 30 days. It would not cover 2022–2024 regardless.

---

## Verdict

**Phase 1 = BLOCKED (CRITICAL) — confirmed in two separate handoffs**

Both available Binance data sources for historical force orders are unavailable:

| Source | Status | Reason |
|---|---|---|
| `data.binance.vision/liquidationSnapshot` | ❌ DOES NOT EXIST | S3 `NoSuchKey` for all dates; directory absent from S3 listing |
| Binance REST `/fapi/v1/forceOrders` | ❌ REQUIRES AUTH | 401 Unauthorized; and historical depth ~30 days anyway |

**Phase 2 cannot proceed.** No free public data source for historical force orders
has been identified.

---

## Questions for Claude Code

1. **Primary blocker (requires adjudication):**
   `liquidationSnapshot` is definitively absent from data.binance.vision
   (S3 `NoSuchKey`, directory listing absent, tested across 8 dates spanning
   2019–2024 in two separate verification runs).
   The GitHub issue #337 reference in the handoff appears to describe planned/requested
   data that was never published, or data that has since been removed.

   Options for milestone re-scope:
   - **A. Accept `force_order_spike` frozen for backtest** — document as permanently
     unavailable for historical replay. Feature remains active in live/paper runtime
     (live collector running since 2026-04-17). Backtest simply uses the frozen default.
   - **B. Use authenticated REST** — requires bot's FAPI API key; limited to ~30 days
     history; would not cover 2022–2024 range. Not recommended.
   - **C. Third-party provider** — CryptoQuant / Coinalyze historical liquidation data;
     likely paid. Out of scope per prior operator decision (Coinglass rejected).

2. **UNIQUE constraint (relevant when/if source is found):**
   - Handoff-specified watermark approach is correct given no UNIQUE constraint.
   - No schema migration needed if watermark approach is used.

3. **Recommended re-scope:** Close FORCE-ORDERS-BACKFILL-FEASIBILITY as
   `INFEASIBLE` with documented rationale, and open a separate decision about
   whether to formally freeze `force_order_spike` in the param registry
   or defer to a future milestone when a data source is identified.

---

## Evidence

All checks performed on production server `root@204.168.146.253` (read-only, no DB mutations).

S3 listing URL used:
```
https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/daily/
https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/
```
