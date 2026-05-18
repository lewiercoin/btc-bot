# ETH Historical Backfill Pilot

**Milestone:** `ETH_HISTORICAL_BACKFILL_PILOT_V1`
**Status:** READY_FOR_AUDIT
**Scope:** Research Lab data-engineering pilot only; separate SQLite snapshot; no runtime DB writes.

## Guardrails

- Hostname: `DESKTOP-OK55MBG`
- Output DB: `research_lab\snapshots\ethusdt_backfill_pilot_2026-05-15_2026-05-18.db`
- Disk guard minimum free space: 12.0 GB
- Free disk before: 25.72 GB
- Free disk after: 25.72 GB
- Raw ZIP files are streamed in memory per day and discarded after parsing.
- Production `storage/btc_bot.db` and PAPER bot runtime are untouched.

## Pilot Size

- Date range: 2026-05-15 to 2026-05-18 exclusive (3 days)
- Pilot DB size: 0.77 MB
- Linear full 2022-2026 estimate: 0.39 GB

## Rows

| Dataset | Rows | Expected | Missing Rate |
|---|---:|---:|---:|
| `candles_15m` | 288 | 288 | 0.00% |
| `candles_4h` | 18 | 18 | 0.00% |
| `funding` | 9 | 9 | 0.00% |
| `open_interest` | 864 | 864 | 0.00% |
| `aggtrade_60s` | 4320 | 4320 | 0.00% |
| `aggtrade_15m` | 288 | 288 | 0.00% |

- OHLC/zero-volume errors: 0
- Duplicate groups: {'candles': 0, 'funding': 0, 'open_interest': 0, 'aggtrade_buckets': 0}

## Per-Day Download

| Day | 15m | 4h | Funding | OI | AggTrades | 60s Buckets | 15m Buckets | Download MB | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-05-15 | 96 | 6 | 3 | 288 | 1051188 | 1440 | 96 | 13.97 | - |
| 2026-05-16 | 96 | 6 | 3 | 288 | 647282 | 1440 | 96 | 8.66 | - |
| 2026-05-17 | 96 | 6 | 3 | 288 | 700247 | 1440 | 96 | 9.23 | - |

## Builder Interpretation

This pilot validates the mechanics and storage slope for ETHUSDT historical data. It is not an ETH strategy backtest and does not approve multi-asset runtime work.

## Audit Questions

1. Did the pilot write only to the separate research snapshot path?
2. Did the disk guard run before writes and preserve enough free space?
3. Were raw archives discarded rather than persisted?
4. Are row counts, missing rates, duplicates, and OHLC errors reported?
5. Does the report avoid approving ETH strategy research or runtime changes?
