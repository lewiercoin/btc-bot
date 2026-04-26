# Gate A Timing / Staleness Query Pack

This directory contains the read-only SQL pack for the Gate A timing and staleness supporting report.

## Files

- `gate_a_timing_staleness.sql`
  - `T1`: build timing between `cycle_timestamp`, `snapshot_build_*`, and `captured_at`
  - `T2`: exchange timestamp alignment to the cycle bucket
  - `T3`: per-input staleness summary
  - `T4`: per-input distribution metrics (`p50`, `p95`, `max`)
  - `T5`: websocket vs REST aggtrade staleness comparison
  - `T6`: null timestamp and missing-field detection

## Production usage

Run only against the production database in read-only mode.

On the server:

```bash
cd /home/btc-bot/btc-bot
sqlite3 -readonly storage/btc_bot.db < scripts/audit_queries/gate_a_timing_staleness.sql
```

Over SSH from the operator machine:

```bash
ssh root@204.168.146.253 "cd /home/btc-bot/btc-bot && sqlite3 -readonly storage/btc_bot.db < scripts/audit_queries/gate_a_timing_staleness.sql"
```

## Selection rule

The timing pack does not measure every raw DB row.

It first selects one canonical row per `15m` bucket using this deterministic priority:

1. full lineage present
2. all five quality keys are `ready`
3. latest `captured_at`
4. latest `feature_snapshot_id`

This avoids polluting timing metrics with duplicate rows from the same bucket.

## Interpretation order

1. `T1`
   Validate that build timing is positive and that build/capture lag is reasonable.
   Use `T1C` for `p50/p95/max` on build duration and capture lag.
2. `T2`
   Confirm that exchange timestamps are aligned with the cycle bucket and never in the future.
3. `T3`
   Review average and max staleness per input family.
4. `T4`
   Review `p50`, `p95`, and `max` for Gate A threshold discussion.
5. `T5`
   Compare websocket-backed vs REST-backed aggtrade timing.
6. `T6`
   Detect missing timestamp fields before writing the final report.

## Escalation rules

Treat the result as a blocker and escalate before writing `Timing/Staleness = PASS` if any of the following is true:

- `T1` reports negative build duration or build finish before cycle time.
- `T2` reports future exchange timestamps for any input family.
- `T4` shows unexplained `p95` or `max` staleness above the accepted Gate A threshold.
- `T6B` returns missing timestamp fields inside the post-fix canonical bucket set.

Treat the result as a warning or documented caveat, not an automatic blocker, if any of the following is true:

- the warm-up period immediately after deploy shows elevated lag, but is already excluded from Gate A counting
- REST-backed rows are slower than websocket-backed rows, but still within accepted timing limits
- isolated nulls or gaps are tied to a known outage and documented explicitly in the final audit

## Hardcoded window

The timing pack intentionally hardcodes:

- counting start: `2026-04-25 00:45 UTC`

The warm-up bucket `2026-04-25 00:30 UTC` should be discussed only as an edge case, not included in Gate A timing totals.
