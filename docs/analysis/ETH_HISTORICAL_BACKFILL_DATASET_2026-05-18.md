# ETH Historical Backfill Dataset

**Milestone:** `ETH_HISTORICAL_BACKFILL_DATASET_V1`
**Status:** `DATASET_COMPLETE_READY_FOR_AUDIT`
**Scope:** Research Lab data-engineering dataset only; separate SQLite snapshot; no runtime DB writes.

## Progress

- Range: 2022-01-01 to 2026-03-28 exclusive
- Expected days: 1547
- Done days: 1547
- Failed days: 0
- Processed this run: 1117
- DB path: `research_lab/snapshots/ethusdt_2022_2026_dataset_v1.db`
- DB size: 374.81 MB
- Free disk: 26.49 GB
- Disk guard: 12.0 GB

## Rows

| Dataset | Rows | Expected | Missing Rate |
|---|---:|---:|---:|
| `candles_15m` | 148512 | 148512 | 0.00% |
| `candles_4h` | 9282 | 9282 | 0.00% |
| `funding` | 4641 | 4641 | 0.00% |
| `open_interest` | 445403 | 445536 | 0.03% |
| `aggtrade_60s` | 2227553 | 2227680 | 0.01% |
| `aggtrade_15m` | 148509 | 148512 | 0.00% |

- OHLC/zero-volume errors: 7
- Duplicate groups: {'candles': 0, 'funding': 0, 'open_interest': 0, 'aggtrade_buckets': 0}

## Data Quality Notes

- The 7 candle quality flags are all zero-volume 15m candles with valid price geometry (`open=high=low=close`), not OHLC ordering violations.
- Zero-volume candle timestamps:
  - 2022-05-01T22:30:00+00:00
  - 2022-05-28T16:45:00+00:00
  - 2022-05-28T17:00:00+00:00
  - 2024-10-28T20:00:00+00:00
  - 2024-10-28T20:15:00+00:00
  - 2024-10-28T20:30:00+00:00
  - 2024-10-28T20:45:00+00:00
- Open interest missingness is 0.03% and concentrated in five historical days plus one boundary row on 2026-03-28.
- Aggtrade bucket missingness is 0.01% for 60s buckets and 0.00% for 15m buckets, concentrated in six historical days.
- These notes do not approve ETH strategy research; they document issues Claude Code should audit before transfer testing.

## Recent Processed Days

| Day | 15m | 4h | Funding | OI | AggTrades | 60s Buckets | 15m Buckets | Download MB | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-03-08 | 96 | 6 | 3 | 288 | 1456251 | 1440 | 96 | 19.05 | - |
| 2026-03-09 | 96 | 6 | 3 | 288 | 2526668 | 1440 | 96 | 32.53 | - |
| 2026-03-10 | 96 | 6 | 3 | 288 | 2285825 | 1440 | 96 | 29.48 | - |
| 2026-03-11 | 96 | 6 | 3 | 288 | 1807471 | 1440 | 96 | 23.41 | - |
| 2026-03-12 | 96 | 6 | 3 | 288 | 1753088 | 1440 | 96 | 22.87 | - |
| 2026-03-13 | 96 | 6 | 3 | 288 | 2493715 | 1440 | 96 | 32.29 | - |
| 2026-03-14 | 96 | 6 | 3 | 288 | 652321 | 1440 | 96 | 8.74 | - |
| 2026-03-15 | 96 | 6 | 3 | 288 | 1148595 | 1440 | 96 | 15.15 | - |
| 2026-03-16 | 96 | 6 | 3 | 288 | 2945725 | 1440 | 96 | 38.04 | - |
| 2026-03-17 | 96 | 6 | 3 | 288 | 2190838 | 1440 | 96 | 28.16 | - |
| 2026-03-18 | 96 | 6 | 3 | 288 | 2235226 | 1440 | 96 | 28.91 | - |
| 2026-03-19 | 96 | 6 | 3 | 288 | 2234911 | 1440 | 96 | 28.81 | - |
| 2026-03-20 | 96 | 6 | 3 | 288 | 1719929 | 1440 | 96 | 22.24 | - |
| 2026-03-21 | 96 | 6 | 3 | 288 | 638581 | 1440 | 96 | 8.43 | - |
| 2026-03-22 | 96 | 6 | 3 | 288 | 1613611 | 1440 | 96 | 20.82 | - |
| 2026-03-23 | 96 | 6 | 3 | 288 | 3226309 | 1440 | 96 | 40.95 | - |
| 2026-03-24 | 96 | 6 | 3 | 288 | 1822905 | 1440 | 96 | 23.57 | - |
| 2026-03-25 | 96 | 6 | 3 | 288 | 1437696 | 1440 | 96 | 18.73 | - |
| 2026-03-26 | 96 | 6 | 3 | 288 | 1551542 | 1440 | 96 | 20.34 | - |
| 2026-03-27 | 96 | 6 | 3 | 288 | 1517062 | 1440 | 96 | 19.93 | - |

## Failed Days

- None

## Audit Questions

1. Does the dataset live only in `research_lab/snapshots`?
2. Are daily checkpoints resumable and explicit?
3. Did disk guard remain active throughout the run?
4. Are missing rates, duplicates, OHLC errors, and failed days reported?
5. Does the report avoid ETH strategy or runtime approval claims?
