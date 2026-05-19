# SOL Historical Backfill Pilot

**Milestone:** `SOL_HISTORICAL_BACKFILL_PILOT_V1`
**Status:** `PASS_SOL_BACKFILL_PILOT_FULL_BACKFILL_READY`
**Scope:** Research Lab data-engineering pilot only; separate SQLite snapshot; no runtime DB writes.

## Guardrails

- Hostname: `DESKTOP-OK55MBG`
- Output DB: `research_lab\snapshots\replay-run-sol-backfill-pilot-2026-05-15_2026-05-18.db`
- Disk guard minimum free space: 12.0 GB
- Free disk before: 25.58 GB
- Free disk after: 25.58 GB
- Raw ZIP files are streamed in memory per day and discarded after parsing.
- Production `storage/btc_bot.db` and PAPER bot runtime are untouched.

## Pilot Size

- Symbol: `SOLUSDT`
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
- Checkpoints: `{"DONE": 3, "failed_days": []}`

## Per-Day Download

| Day | 15m | 4h | Funding | OI | AggTrades | 60s Buckets | 15m Buckets | Download MB | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-05-15 | 96 | 6 | 3 | 288 | 263757 | 1440 | 96 | 3.67 | - |
| 2026-05-16 | 96 | 6 | 3 | 288 | 231499 | 1440 | 96 | 3.16 | - |
| 2026-05-17 | 96 | 6 | 3 | 288 | 210630 | 1440 | 96 | 2.89 | - |

## Builder Interpretation

This pilot validates SOLUSDT archive ingestion mechanics, storage slope, and quality metrics. It is not a SOL strategy backtest and does not approve SOL shadow, PAPER, or runtime work.

## Audit Questions

1. Did the pilot write only to a separate `research_lab/snapshots` path?
2. Did the disk guard run before writes and preserve enough free space?
3. Were raw archives streamed per day and discarded rather than persisted?
4. Are row counts, missing rates, duplicates, OHLC errors, and failed days reported?
5. Does the report avoid approving SOL strategy research, SOL shadow, or runtime changes?
