# Gate A Feature Drift Query Pack

This directory contains the read-only SQL pack for the Gate A feature drift supporting report.

## Files

- `gate_a_feature_drift.sql`
  - `D1`: canonical quality-ready bucket inventory and scalar feature availability
  - `D2`: scalar feature summary statistics
  - `D3`: scalar feature percentiles (`p10`, `p50`, `p90`)
  - `D4`: duplicate-row feature conflict detection
  - `D5`: boolean feature prevalence
  - `D6`: edge-case checks for missing fields and warm-up bucket inspection

## Production usage

Run only against the production database in read-only mode.

On the server:

```bash
cd /home/btc-bot/btc-bot
sqlite3 -readonly storage/btc_bot.db < scripts/audit_queries/gate_a_feature_drift.sql
```

Over SSH from the operator machine:

```bash
ssh root@204.168.146.253 "cd /home/btc-bot/btc-bot && sqlite3 -readonly storage/btc_bot.db < scripts/audit_queries/gate_a_feature_drift.sql"
```

## Selection rule

The drift pack measures only `post-fix quality-ready canonical 15m buckets`.

Canonical row selection priority:

1. full lineage present
2. all five quality keys are `ready`
3. latest `captured_at`
4. latest `feature_snapshot_id`

This keeps drift statistics stable even when duplicate rows exist inside the same bucket.

## Interpretation order

1. `D1`
   Confirm sample size and feature availability.
2. `D2`
   Review null counts, range, mean, and stddev for scalar features.
3. `D3`
   Review percentile bands for drift-safe interpretation.
4. `D4`
   Detect same-bucket feature conflicts before trusting summary stats.
5. `D5`
   Review prevalence of boolean diagnostic features.
6. `D6`
   Resolve missing-field and warm-up edge cases.

## Escalation rules

Treat the result as a blocker and escalate before writing `Feature Drift = PASS` if any of the following is true:

- `D1` or `D6A` shows missing critical scalar features in canonical quality-ready buckets.
- `D4` shows unresolved duplicate-row feature conflicts that materially change the canonical interpretation.
- `D2` or `D3` shows impossible values, pervasive nulls, or clearly broken distributions for core features.

Treat the result as a warning or documented caveat, not an automatic blocker, if any of the following is true:

- boolean features are sparse because the market simply did not trigger those setups in the sampled window.
- the warm-up bucket shows outlier values but remains outside the counted post-fix window.
- duplicate rows exist, but the canonical bucket selection remains stable.

## Hardcoded window

The drift pack intentionally hardcodes:

- counting start: `2026-04-25 00:45 UTC`
- warm-up inspection window: `2026-04-25 00:30 UTC` to `2026-04-25 00:45 UTC`

Do not widen this window for Gate A.
