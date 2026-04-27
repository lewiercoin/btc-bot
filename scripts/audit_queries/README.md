# Gate A Market Truth Query Pack

This directory contains the read-only SQL pack for `AUDIT-01: Market Truth / Data Source Audit`.

## Files

- `gate_a_market_truth.sql`
  - Q1: post-fix quality-ready bucket count
  - Q2: bucket deduplication check
  - Q3: quality conflict detection inside the same bucket
  - Q4: time range summary and missing-bucket analysis
  - Q5: WS vs REST source distribution
  - Q6: edge-case checks (`00:30` warm-up, lineage breaks, non-ready lineage buckets)

## Production usage

Run only against the production database in read-only mode.

On the server:

```bash
cd /home/btc-bot/btc-bot
sqlite3 -readonly storage/btc_bot.db < scripts/audit_queries/gate_a_market_truth.sql
```

Over SSH from the operator machine:

```bash
ssh root@204.168.146.253 "cd /home/btc-bot/btc-bot && sqlite3 -readonly storage/btc_bot.db < scripts/audit_queries/gate_a_market_truth.sql"
```

## Interpretation order

Run and interpret the queries in this order:

1. `Q1`
   Confirms the current Gate A unlock count at the bucket level.
2. `Q2`
   Shows whether raw DB rows overcount buckets because of duplicates.
3. `Q3`
   Confirms whether the same bucket contains conflicting quality states.
4. `Q4`
   Detects missing 15m buckets or broken time continuity in the post-fix window.
5. `Q5`
   Confirms that quality-ready buckets are backed by websocket-driven flow and are not clipped by REST limits.
6. `Q6`
   Resolves known special cases before a final Gate A verdict is written.

## Escalation rules

Treat the result as a blocker and escalate before writing `Gate A = PASS` if any of the following is true:

- `Q1` shows fewer than `200` quality-ready buckets at formal Gate A time.
- `Q4` shows missing post-fix buckets that are not already explained by a known outage or documented maintenance event.
- `Q5` shows any quality-ready bucket still relying on `clipped_by_limit = true`.
- `Q6B` returns any lineage break inside the post-fix counting window.

Treat the result as a warning or documented caveat, not an automatic blocker, if any of the following is true:

- `Q2` shows duplicate raw rows, but `Q1` and `Q3` remain stable at the deduped bucket level.
- `Q3` shows conflict between duplicate rows, but at least one row in the bucket is fully quality-ready and lineage-complete.
- `Q6A` shows the `2026-04-25 00:30 UTC` warm-up bucket as degraded or unavailable.
- `Q6C` returns non-ready buckets outside the counted quality-ready subset, as long as the Gate A counter itself is based only on ready buckets.

## Export notes

The SQL file is optimized for manual review in `sqlite3`.

If a CSV is needed:

1. Copy a single query block from `gate_a_market_truth.sql`.
2. Run it with `sqlite3 -header -csv -readonly`.
3. Redirect the output into the target artifact file.

Example:

```bash
sqlite3 -header -csv -readonly storage/btc_bot.db "SELECT COUNT(*) AS rows FROM feature_snapshots;" > artifacts/example.csv
```

## Hardcoded window

The query pack intentionally hardcodes:

- counting start: `2026-04-25 00:45 UTC`
- warm-up exclusion window: `2026-04-25 00:30 UTC` to `2026-04-25 00:45 UTC`

Do not widen this window for Gate A. Pre-fix cycles are excluded by design.
