# SOL Historical Backfill Dataset

**Milestone:** `SOL_HISTORICAL_BACKFILL_DATASET_V1`
**Status:** `DATASET_COMPLETE_READY_FOR_AUDIT`
**Scope:** Research Lab data-engineering dataset only; separate SQLite snapshot; no runtime DB writes.

## Progress

- Symbol: `SOLUSDT`
- Range: 2022-01-01 to 2026-03-28 exclusive
- Expected days: 1547
- Done days: 1547
- Failed days: 0
- Processed this run: 47
- Complete: `True`
- DB path: `research_lab/snapshots/replay-run-sol-historical-2022-2026.db`
- DB size: 340.27 MB
- Linear full-size estimate from completed days: 0.33 GB
- Disk guard: 12.0 GB
- Free disk before: 25.72 GB
- Free disk after: 25.71 GB

## Rows

| Dataset | Rows | Expected | Missing Rate |
|---|---:|---:|---:|
| `candles_15m` | 148512 | 148512 | 0.00% |
| `candles_4h` | 9282 | 9282 | 0.00% |
| `funding` | 4716 | 4641 | 0.00% |
| `open_interest` | 445386 | 445536 | 0.03% |
| `aggtrade_60s` | 2227553 | 2227680 | 0.01% |
| `aggtrade_15m` | 148509 | 148512 | 0.00% |

- OHLC corruptions: 0
- Price violations: 0
- Valid zero-volume flat candles: 7
- Zero-volume non-flat candles: 0
- Duplicate groups: {'candles': 0, 'funding': 0, 'open_interest': 0, 'aggtrade_buckets': 0}
- Checkpoints: `{"DONE": 1547, "failed_days": []}`

## Recent Processed Days

| Day | 15m | 4h | Funding | OI | AggTrades | 60s Buckets | 15m Buckets | Download MB | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-03-08 | 96 | 6 | 3 | 288 | 298367 | 1440 | 96 | 4.17 | - |
| 2026-03-09 | 96 | 6 | 3 | 288 | 373595 | 1440 | 96 | 5.34 | - |
| 2026-03-10 | 96 | 6 | 3 | 288 | 372994 | 1440 | 96 | 5.31 | - |
| 2026-03-11 | 96 | 6 | 3 | 288 | 334061 | 1440 | 96 | 4.75 | - |
| 2026-03-12 | 96 | 6 | 3 | 288 | 332486 | 1440 | 96 | 4.69 | - |
| 2026-03-13 | 96 | 6 | 3 | 288 | 452311 | 1440 | 96 | 6.40 | - |
| 2026-03-14 | 96 | 6 | 3 | 288 | 232953 | 1440 | 96 | 3.15 | - |
| 2026-03-15 | 96 | 6 | 3 | 288 | 304664 | 1440 | 96 | 4.21 | - |
| 2026-03-16 | 96 | 6 | 3 | 288 | 470002 | 1440 | 96 | 6.64 | - |
| 2026-03-17 | 96 | 6 | 3 | 288 | 337575 | 1440 | 96 | 4.79 | - |
| 2026-03-18 | 96 | 6 | 3 | 288 | 361844 | 1440 | 96 | 5.12 | - |
| 2026-03-19 | 96 | 6 | 3 | 288 | 371656 | 1440 | 96 | 5.24 | - |
| 2026-03-20 | 96 | 6 | 3 | 288 | 272714 | 1440 | 96 | 3.86 | - |
| 2026-03-21 | 96 | 6 | 3 | 288 | 215826 | 1440 | 96 | 2.93 | - |
| 2026-03-22 | 96 | 6 | 3 | 288 | 291462 | 1440 | 96 | 4.06 | - |
| 2026-03-23 | 96 | 6 | 3 | 288 | 447724 | 1440 | 96 | 6.36 | - |
| 2026-03-24 | 96 | 6 | 3 | 288 | 354048 | 1440 | 96 | 4.97 | - |
| 2026-03-25 | 96 | 6 | 3 | 288 | 337181 | 1440 | 96 | 4.64 | - |
| 2026-03-26 | 96 | 6 | 3 | 288 | 374524 | 1440 | 96 | 5.16 | - |
| 2026-03-27 | 96 | 6 | 3 | 288 | 339088 | 1440 | 96 | 4.69 | - |

## Failed Days

- None

## Builder Interpretation

This dataset materializes SOLUSDT historical research data for later audited strategy transfer research. It is not a SOL strategy backtest and does not approve SOL shadow, PAPER, or runtime work.

## Audit Questions

1. Does the dataset live only in `research_lab/snapshots` and avoid production DB writes?
2. Are daily checkpoints resumable and explicit?
3. Did disk guard remain active throughout the run?
4. Are missing rates, duplicates, OHLC errors, and failed days reported?
5. Does the report avoid SOL strategy or runtime approval claims?
