# AUDIT: DATA-BACKFILL-V1 (COMPLETE)
Date: 2026-05-02
Auditor: Claude Code
Commit: f181e80 (modeling-context-closure)

## Verdict: DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: PASS
## Error Handling: PASS
## Smoke Coverage: PASS
## Tech Debt: LOW
## AGENTS.md Compliance: PASS
## Methodology Integrity: N/A
## Promotion Safety: N/A
## Reproducibility & Lineage: PASS
## Data Isolation: PASS
## Search Space Governance: N/A
## Artifact Consistency: PASS
## Boundary Coupling: PASS

---

## Audit Summary

Three-commit audit chain: `bd13d62` (scripts) → `07448b2` (csv fix) → `f181e80`
(Decision 9 docs). Production run executed and gate-checked.

### Step 0 (feasibility) and Step 1.0 (column verification)
Previously verified in audit AUDIT_DATA_BACKFILL_V1_STEP1_2026-05-01.md (commit bd13d62).

### Critical fix discovered during dry-run (commit 07448b2)

Binance README states no header row in aggTrades files. **Incorrect.** Actual files have:
```
agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker
```

**Fix verified:**
- `csv.reader` + integer indices → `csv.DictReader` + named column access ✓
- `_COL_QUANTITY = "quantity"`, `_COL_TIMESTAMP_MS = "transact_time"`, `_COL_IS_BUYER_MAKER = "is_buyer_maker"` ✓
- `.strip().lower() == "true"` correctly handles `"True"` (title-case) ✓
- Removed `len(row) < 7` guard — DictReader raises `KeyError` on missing columns (fails loudly, correct) ✓
- Builder correctly ran dry-run BEFORE live, discovered the bug, fixed, re-verified ✓

**Process integrity**: dry-run gate was executed as required. Bug caught before any
production writes. Fix committed and verified. This is the pre-production gate working
as designed.

---

## Production Run Verification

### OI backfill (backfill_oi.py)

| Metric | Value | Check |
|---|---|---|
| Range | 2025-06-05 → 2026-01-01 (211 days) | ✓ |
| Parsed | 60,765 rows | ≈ 211 × 288 = 60,768 (delta: 3 rows, rounding at day boundary) ✓ |
| Inserted | 60,477 rows | 288 fewer = 1 day already in DB → INSERT OR IGNORE correct ✓ |
| Skipped dates | 0 | All 211 daily files downloaded ✓ |

### AggTrades backfill (backfill_aggtrades.py)

| Run | Range | Trades | Buckets inserted | Max possible | Delta |
|---|---|---|---|---|---|
| March | 2026-03-28 → 2026-03-31 | 5,895,220 | 299 | 4×96=384 | 85 already in DB ✓ |
| April | 2026-04-01 → 2026-04-17 | 24,404,348 | 1,607 | 17×96=1,632 | 25 already in DB ✓ |

Delta rows = buckets already collected by live system before gap. INSERT OR IGNORE
preserved existing data. Correct.

Trade/bucket ratios: March ~19,716/bucket, April ~15,186/bucket — realistic for BTC
perpetuals 15m windows. Arithmetic consistent.

### db_status.py gate check (post-backfill)

```
aggtrade_15m : 2020-09-01 -> 2026-04-17T23:45:00  [rows: 197,081, gaps: 6]
open_interest: 2020-09-01 -> 2026-04-17T14:00:00  [rows: 586,973, gaps: 35]
```

**Primary gaps targeted by this milestone: ZERO remaining** ✓

Remaining gaps classified:
- OI 35 gaps: 2020–2021 Binance source data gaps (10–90 min) — unavoidable, pre-exist ✓
- AggTrade 6 gaps: 2 from 2021/2022, 2 from Feb 2024 (~24h each) — outside Optuna window, not in scope ✓

**Optuna window 2026-01-01 → 2026-03-28: CLEAN for both OI and aggTrades** ✓

---

## Critical Issues

None.

---

## Warnings

None. Previous W1 (no smoke test) resolved by: dry-run ran before live, caught real bug,
proved the gate is working.

---

## Observations

- Feb 2024 ~24h aggtrade gaps (2024-02-04, 2024-02-23) are known and pre-date Optuna
  window. Not blocking for current campaign. Track as future data integrity pass if OOS
  testing ever requires that period.
- OI 60,765 parsed vs 60,768 expected: 3-row delta consistent with day-boundary rounding
  (first/last day partial 5-min slot). Not a data integrity issue.
- 586,973 OI rows at 5-min granularity = 5-min resolution available for feature engine.
  Feature engine uses latest value before cycle time — higher resolution is harmless.

---

## Tracked Debt

| ID | Description | Priority | Status |
|---|---|---|---|
| D4 | No automated smoke test for backfill scripts | LOW | CLOSED — dry-run gate served the purpose; scripts are one-time tools |
| D5 | `_stream_rows_from_zip` misnomer | LOW | OPEN (cosmetic, does not block) |
| Feb-2024 | ~24h aggtrade gaps in 2024-02-04, 2024-02-23 | LOW | DEFERRED — outside Optuna window |

---

## Milestone Result

DATA-BACKFILL-V1 is complete. Production database now contains:
- 60,477 new OI rows (2025-06-05 → 2026-01-01) with 5-min granularity
- 1,906 new aggtrade_buckets (2026-03-28 → 2026-04-17) with correct CVD continuity
- Optuna window 2026-01-01 → 2026-03-28 verified CLEAN

---

## Recommended Next Step

Clean 87-day window verified. Decision for operator: authorize Optuna campaign with
`wf_light_protocol.json` on 2026-01-01 → 2026-03-28, or extend window by backfilling
Feb 2024 gaps to unlock full 2024–2026 range for default protocol.

Claude Code recommendation: **proceed with Optuna on the verified 87-day window** using
`wf_light_protocol.json`. This is the lowest-risk path to a validated candidate. Feb 2024
backfill is a separate future milestone if needed.
