# ETH Historical Backfill Dataset

**Milestone:** `ETH_HISTORICAL_BACKFILL_DATASET_V1`
**Status:** `PARTIAL_BACKFILL_IN_PROGRESS`
**Scope:** Research Lab data-engineering dataset only; separate SQLite snapshot; no runtime DB writes.

## Progress

- Range: 2022-01-01 to 2026-03-28 exclusive
- Expected days: 1547
- Done days: 430
- Failed days: 0
- Processed this run: 200
- DB path: `research_lab/snapshots/ethusdt_2022_2026_dataset_v1.db`
- DB size: 104.07 MB
- Free disk: 26.89 GB
- Disk guard: 12.0 GB

## Rows

| Dataset | Rows | Expected | Missing Rate |
|---|---:|---:|---:|
| `candles_15m` | 41280 | 41280 | 0.00% |
| `candles_4h` | 2580 | 2580 | 0.00% |
| `funding` | 1290 | 1290 | 0.00% |
| `open_interest` | 123840 | 123840 | 0.00% |
| `aggtrade_60s` | 619126 | 619200 | 0.01% |
| `aggtrade_15m` | 41277 | 41280 | 0.01% |

- OHLC/zero-volume errors: 3
- Duplicate groups: {'candles': 0, 'funding': 0, 'open_interest': 0, 'aggtrade_buckets': 0}

## Recent Processed Days

| Day | 15m | 4h | Funding | OI | AggTrades | 60s Buckets | 15m Buckets | Download MB | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2023-02-15 | 96 | 6 | 3 | 288 | 1008429 | 1440 | 96 | 14.00 | - |
| 2023-02-16 | 96 | 6 | 3 | 288 | 1459693 | 1440 | 96 | 20.08 | - |
| 2023-02-17 | 96 | 6 | 3 | 288 | 1097741 | 1440 | 96 | 15.23 | - |
| 2023-02-18 | 96 | 6 | 3 | 288 | 440218 | 1440 | 96 | 6.20 | - |
| 2023-02-19 | 96 | 6 | 3 | 288 | 695256 | 1440 | 96 | 9.67 | - |
| 2023-02-20 | 96 | 6 | 3 | 288 | 821255 | 1440 | 96 | 11.39 | - |
| 2023-02-21 | 96 | 6 | 3 | 288 | 927627 | 1440 | 96 | 12.92 | - |
| 2023-02-22 | 96 | 6 | 3 | 288 | 1014699 | 1440 | 96 | 14.17 | - |
| 2023-02-23 | 96 | 6 | 3 | 288 | 952073 | 1440 | 96 | 13.31 | - |
| 2023-02-24 | 96 | 6 | 3 | 288 | 920859 | 1440 | 96 | 12.83 | - |
| 2023-02-25 | 96 | 6 | 3 | 288 | 488458 | 1440 | 96 | 6.85 | - |
| 2023-02-26 | 96 | 6 | 3 | 288 | 515095 | 1440 | 96 | 7.25 | - |
| 2023-02-27 | 96 | 6 | 3 | 288 | 720835 | 1440 | 96 | 10.11 | - |
| 2023-02-28 | 96 | 6 | 3 | 288 | 627154 | 1440 | 96 | 8.86 | - |
| 2023-03-01 | 96 | 6 | 3 | 288 | 781466 | 1440 | 96 | 10.93 | - |
| 2023-03-02 | 96 | 6 | 3 | 288 | 661311 | 1440 | 96 | 9.36 | - |
| 2023-03-03 | 96 | 6 | 3 | 288 | 908769 | 1440 | 96 | 12.55 | - |
| 2023-03-04 | 96 | 6 | 3 | 288 | 339726 | 1440 | 96 | 4.78 | - |
| 2023-03-05 | 96 | 6 | 3 | 288 | 421676 | 1440 | 96 | 5.91 | - |
| 2023-03-06 | 96 | 6 | 3 | 288 | 460032 | 1440 | 96 | 6.48 | - |

## Failed Days

- None

## Audit Questions

1. Does the dataset live only in `research_lab/snapshots`?
2. Are daily checkpoints resumable and explicit?
3. Did disk guard remain active throughout the run?
4. Are missing rates, duplicates, OHLC errors, and failed days reported?
5. Does the report avoid ETH strategy or runtime approval claims?
