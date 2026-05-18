# ETH Historical Backfill Dataset

**Milestone:** `ETH_HISTORICAL_BACKFILL_DATASET_V1`
**Status:** `PARTIAL_BACKFILL_IN_PROGRESS`
**Scope:** Research Lab data-engineering dataset only; separate SQLite snapshot; no runtime DB writes.

## Progress

- Range: 2026-05-15 to 2026-05-18 exclusive
- Expected days: 3
- Done days: 1
- Failed days: 0
- Processed this run: 1
- DB path: `research_lab\snapshots\ethusdt_dataset_smoke.db`
- DB size: 0.30 MB
- Free disk: 25.72 GB
- Disk guard: 12.0 GB

## Rows

| Dataset | Rows | Expected | Missing Rate |
|---|---:|---:|---:|
| `candles_15m` | 96 | 96 | 0.00% |
| `candles_4h` | 6 | 6 | 0.00% |
| `funding` | 3 | 3 | 0.00% |
| `open_interest` | 288 | 288 | 0.00% |
| `aggtrade_60s` | 1440 | 1440 | 0.00% |
| `aggtrade_15m` | 96 | 96 | 0.00% |

- OHLC/zero-volume errors: 0
- Duplicate groups: {'candles': 0, 'funding': 0, 'open_interest': 0, 'aggtrade_buckets': 0}

## Recent Processed Days

| Day | 15m | 4h | Funding | OI | AggTrades | 60s Buckets | 15m Buckets | Download MB | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-05-15 | 96 | 6 | 3 | 288 | 1051188 | 1440 | 96 | 13.97 | - |

## Failed Days

- None

## Audit Questions

1. Does the dataset live only in `research_lab/snapshots`?
2. Are daily checkpoints resumable and explicit?
3. Did disk guard remain active throughout the run?
4. Are missing rates, duplicates, OHLC errors, and failed days reported?
5. Does the report avoid ETH strategy or runtime approval claims?
