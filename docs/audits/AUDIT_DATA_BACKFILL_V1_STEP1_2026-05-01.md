# AUDIT: DATA-BACKFILL-V1 STEP 1
Date: 2026-05-01
Auditor: Claude Code
Commit: bd13d62 (modeling-context-closure)

## Verdict: MVP_DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: PASS
## Error Handling: PASS
## Smoke Coverage: WARN
## Tech Debt: LOW
## AGENTS.md Compliance: PASS
## Methodology Integrity: N/A
## Promotion Safety: N/A
## Reproducibility & Lineage: N/A
## Data Isolation: PASS
## Search Space Governance: N/A
## Artifact Consistency: N/A
## Boundary Coupling: PASS

---

## Audit Summary

Two scripts audited: `scripts/backfill_oi.py` and `scripts/backfill_aggtrades.py`.
Pre-condition from Step 1.0 verification (commit f2344e5) confirmed:
- `create_time` format: `YYYY-MM-DD HH:MM:SS` (UTC string, NOT Unix ms) ✓
- `sum_open_interest` column name confirmed ✓
- Metrics CSV has header row — `csv.DictReader` correct ✓
- AggTrades has no header row — `csv.reader` with column indices correct ✓

Both scripts independently verified against schema.sql, feasibility report, and Step 1.0
column verification.

---

### backfill_oi.py — line-by-line verification

| Check | Result |
|---|---|
| `create_time` parsed as `%Y-%m-%d %H:%M:%S` | ✓ `_parse_create_time()` uses strptime with correct format |
| Converts to ISO-8601 UTC | ✓ `.replace(tzinfo=timezone.utc).isoformat()` |
| `sum_open_interest → oi_value` | ✓ `float(raw_row["sum_open_interest"])` inserted as `oi_value` |
| Schema match (`symbol`, `timestamp`, `oi_value`) | ✓ matches `storage/schema.sql` exactly |
| INSERT OR IGNORE | ✓ respects `UNIQUE(symbol, timestamp)` |
| Retry 3×, sleep 5s | ✓ `_RETRY_COUNT=3`, `_RETRY_SLEEP_S=5.0` |
| Rate limiting 0.5s between dates | ✓ `_REQUEST_SLEEP_S=0.5` after each date |
| `--dry-run` no writes | ✓ `_insert_chunk` returns 0 in dry-run |
| CLI args | ✓ `--dry-run`, `--start-date`, `--end-date`, `--symbol`, `--db-path` |
| End < start guard | ✓ `LOG.error` + return 1 |
| DB connection closed on error | ✓ `finally: conn.close()` |
| WAL mode | ✓ `PRAGMA journal_mode=WAL` |

**Schema-level idempotency**: `UNIQUE(symbol, timestamp)` + `INSERT OR IGNORE`. Running
twice on the same date range is safe.

---

### backfill_aggtrades.py — line-by-line verification

| Check | Result |
|---|---|
| Monthly zip streamed to temp file (1MB chunks) | ✓ `_DOWNLOAD_CHUNK_BYTES = 1024*1024`, writes to tempfile |
| CSV processed row-by-row (zero RAM for raw data) | ✓ `zipfile.ZipFile(tmp_path)` → `zf.open()` → `TextIOWrapper` → `csv.reader` |
| Column indices correct | ✓ qty=2, ts_ms=5, is_buyer_maker=6 — matches Binance aggTrades format |
| WasBuyerMaker logic | ✓ `true` → sell_vol (taker is seller), `false` → buy_vol (taker is buyer) |
| TFI formula | ✓ `(buy - sell) / (buy + sell)`, 0.0 if no trades |
| CVD formula | ✓ `running_cvd + (buy_vol - sell_vol)` per bucket |
| CVD initialized from last DB value before gap | ✓ `_query_last_cvd(conn, symbol, first_bucket_iso)` using `bucket_time < ?` |
| `_query_last_cvd` WHERE clause | ✓ `bucket_time < first_bucket_iso` (strict less-than, correct) |
| Early stop after `--end-date` | ✓ `if end_ms is not None and ts_ms >= end_ms: break` |
| Chunk flushes at 10k buckets | ✓ `_CHUNK_SIZE = 10_000`, `len(pending_buckets) >= _CHUNK_SIZE or force` |
| Final force-flush | ✓ `_flush_pending(force=True)` after loop |
| INSERT OR IGNORE | ✓ respects `UNIQUE(symbol, timeframe, bucket_time)` |
| Schema match | ✓ `(symbol, bucket_time, timeframe, taker_buy_volume, taker_sell_volume, tfi, cvd)` matches schema.sql |
| Temp file deleted on exit | ✓ `finally: tmp_path.unlink()` |
| Retry 3×, sleep 5s | ✓ `_RETRY_COUNT=3`, `_RETRY_SLEEP_S=5.0` |
| `--dry-run` no writes | ✓ `_insert_buckets` returns 0 in dry-run, `_query_last_cvd` skipped |
| CLI args | ✓ `--dry-run`, `--year-month`, `--start-date`, `--end-date`, `--symbol`, `--db-path` |
| DB connection closed on error | ✓ `finally: conn.close()` |
| WAL mode | ✓ `PRAGMA journal_mode=WAL` |

**Chunk flush design**: `pending_buckets` accumulates completed 15m buckets (not raw trades).
For 20-30 day runs (~1920 buckets), all fit in memory before the final force-flush. RAM cost
is negligible (~250KB for 30 days). Correct and safe.

---

## Critical Issues

None.

---

## Warnings

**W1 — Smoke Coverage: no automated smoke test**
Neither script has a `scripts/smoke_backfill_*.py`. `--dry-run` serves as the manual
pre-production gate. For data migration scripts touching production DB this is acceptable
MVP scope. Operator MUST run `--dry-run` on the production server before live writes and
verify logged parsed-row counts (288 rows/day expected for OI; ~5760–15360 buckets/month
expected for aggTrades).

**W2 — backfill_oi.py: in-memory zip bytes (minor)**
`_download_zip()` uses `resp.read()` — loads the entire response into memory before
processing. For 11KB daily OI files this is irrelevant. Function name `_stream_rows_from_zip`
is a misnomer (it returns a list, not a generator). Non-blocking cosmetic issue. If this
function is ever repurposed for large files, it must be converted to the `_download_to_tempfile`
pattern used in backfill_aggtrades.

---

## Observations

- CVD in `--dry-run` starts at 0.0 (DB not queried). Expected behavior; dry-run CVD values
  do not represent what will be inserted in a live run. Not documented in `--help` text.
  Non-blocking for pre-production validation purposes.
- `cur.rowcount` from `executemany` with `INSERT OR IGNORE` may return -1 on some SQLite
  builds (implementation-defined). Used only for log output. Does not affect correctness.
- Short date range runs (< 104 days) in backfill_aggtrades will accumulate all buckets in
  `pending_buckets` before the final force-flush. Memory cost is trivial (~250KB for 30 days).

---

## Tracked Debt

| ID | Description | Priority |
|---|---|---|
| D4 | No automated smoke test for backfill scripts | LOW |
| D5 | `_stream_rows_from_zip` misnomer (loads into list, not streamed) | LOW (cosmetic) |

---

## Pre-Production Gate (mandatory before live writes)

Builder must execute the following sequence on the production server before running live:

```bash
# OI dry-run: verify 288 parsed rows/day, no errors
python scripts/backfill_oi.py \
    --db-path /home/btc-bot/btc-bot/storage/btc_bot.db \
    --start-date 2025-06-05 --end-date 2025-06-07 \
    --dry-run

# AggTrades dry-run: verify bucket counts for test range, no errors  
python scripts/backfill_aggtrades.py \
    --db-path /home/btc-bot/btc-bot/storage/btc_bot.db \
    --year-month 2026-03 \
    --start-date 2026-03-28 --end-date 2026-03-31 \
    --dry-run
```

Only after dry-run confirms expected parsed counts: proceed with live run.
Post-import gate check via `scripts/db_status.py`. Update `docs/DECISIONS_LOG.md`.

---

## Recommended Next Step

Scripts are production-ready. Authorize builder to execute:

1. `--dry-run` gate on production server (mandatory, see above)
2. Live OI backfill: 2025-06-05 → 2026-01-01 (~210 days, ~2.3MB total)
3. Live aggTrades backfill: 2026-03 and 2026-04 monthly files (20-day gap)
4. Post-import: run `db_status.py`, verify gap-free window, update DECISIONS_LOG.md
5. Report clean window length back to Claude Code for Optuna scope decision
