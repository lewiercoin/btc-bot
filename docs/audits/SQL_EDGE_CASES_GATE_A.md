# SQL Edge Cases Gate A

**Date:** 2026-04-26  
**Branch:** `market-truth-v3`  
**Status:** RULEBOOK - use during Gate A execution  
**Mode:** Read-only production validation

---

## Purpose

This document is the execution rulebook for Gate A.

It exists to remove ambiguity when the three prepared packages are run on production:

- `AUDIT-01: Market Truth / Data Source Audit`
- `Market Truth Timing / Staleness`
- `Feature Engine Drift`

This file does not add new queries. It defines how to interpret known edge cases using the existing query packs.

---

## Core Counting Rules

These rules are mandatory for every Gate A conclusion.

1. Count at the `unique 15m bucket` level, never per raw database row.
2. Count only the post-fix window starting at `2026-04-25 00:45 UTC`.
3. Exclude the warm-up bucket `2026-04-25 00:30 UTC` from formal Gate A counting.
4. A bucket passes the primary unlock rule if at least one row in that bucket is:
   - lineage-complete: `market_snapshot -> feature_snapshot -> decision_outcome`
   - `quality-ready`: all five quality keys are `ready`
5. Deduplication is mandatory before any conclusion is written.
6. If duplicate rows exist, use canonical row selection for timing and drift interpretation.

### Canonical Row Selection

Canonical row priority:

1. row has full lineage
2. row has all five quality keys equal to `ready`
3. latest `captured_at`
4. latest `feature_snapshot_id`

This rule is already used in the timing and drift packs. It is repeated here so Gate A execution is self-contained.

---

## Edge Case Catalog

### 1. Duplicate raw rows in the same 15m bucket

**What exists**

- multiple raw DB rows for a single logical `15m` bucket

**Why it matters**

- raw row counts can overstate the real number of cycles
- timing and drift can be polluted by counting both a good and a bad row

**Handling rule**

- always deduplicate to one logical bucket before counting
- do not treat duplicates alone as a blocker

**Default classification**

- `DOCUMENTED` if deduped bucket-level result stays stable
- `BLOCKER` only if duplication makes the bucket-level outcome ambiguous

**Query references**

- Market Truth: `Q2`
- Drift: `D4`

---

### 2. Quality conflicts inside the same 15m bucket

**What exists**

- one row in the bucket is `ready`, another is `degraded` or `unavailable`

**Why it matters**

- the bucket may still be usable, but raw rows disagree about quality state

**Handling rule**

- bucket counts as passing only if at least one row is full-lineage and all-five-ready
- keep the conflict visible in the report

**Default classification**

- `DOCUMENTED` if at least one row is valid and counted
- `BLOCKER` if conflicting rows exist and no row meets the full Gate A quality-ready definition

**Query references**

- Market Truth: `Q3`
- Drift: `D4`

---

### 3. Warm-up bucket after deploy

**What exists**

- bucket `2026-04-25 00:30 UTC` may show degraded quality or elevated lag immediately after restart

**Why it matters**

- it is a real post-deploy artifact but not part of the formal clean post-fix sample

**Handling rule**

- inspect it
- document it
- exclude it from the formal unlock count and formal timing/drift sample

**Default classification**

- `DOCUMENTED`

**Query references**

- Market Truth: `Q6A`
- Timing: `README_TIMING` notes, warm-up handled by window definition
- Drift: `D6B`

---

### 4. Lineage breaks in the post-fix window

**What exists**

- missing or broken `market_snapshot -> feature_snapshot -> decision_outcome` link

**Why it matters**

- bucket is not auditable as source-of-truth
- breaks the formal Gate A contract

**Handling rule**

- any unresolved lineage break in the counted post-fix window is disqualifying

**Default classification**

- `BLOCKER`

**Query references**

- Market Truth: `Q6B`

---

### 5. Lineage-complete but non-quality-ready buckets

**What exists**

- bucket has full lineage but one or more of the five quality keys is not `ready`

**Why it matters**

- structurally useful
- not eligible for the Gate A primary unlock counter

**Handling rule**

- keep visible
- do not add to the `200+` unlock count

**Default classification**

- `DOCUMENTED`

**Query references**

- Market Truth: `Q6C`

---

### 6. WS vs REST fallback in the same window

**What exists**

- post-fix rows may still show mixed websocket vs REST provenance

**Why it matters**

- after the collection fix, counted quality-ready buckets should not rely on clipped fallback behavior

**Handling rule**

- websocket-backed rows are preferred
- REST presence alone is not an automatic blocker
- clipped fallback inside counted buckets is a blocker candidate

**Default classification**

- `DOCUMENTED` if REST rows exist but counted buckets remain valid and unclipped
- `BLOCKER` if counted buckets still depend on `clipped_by_limit = true`

**Query references**

- Market Truth: `Q5`
- Timing: `T5`

---

### 7. Null exchange timestamps

**What exists**

- one or more `*_exchange_ts` fields are `NULL`

**Why it matters**

- missing timestamp means timing/staleness cannot be trusted for that input

**Handling rule**

- never interpret `NULL` as zero staleness
- any missing critical timestamp in canonical counted buckets must be escalated

**Default classification**

- `DOCUMENTED` only if outside the counted sample or tied to an explicitly excluded case
- `BLOCKER` if present in canonical post-fix counted buckets

**Query references**

- Timing: `T2`
- Timing: `T6A`
- Timing: `T6B`

---

### 8. Future timestamps / negative staleness

**What exists**

- exchange timestamp or build timestamp appears to be later than the cycle in a logically impossible way

**Why it matters**

- indicates clock, parsing, or lineage defect

**Handling rule**

- any unresolved future timestamp inside counted canonical buckets is disqualifying

**Default classification**

- `BLOCKER`

**Query references**

- Timing: `T1A`
- Timing: `T1B`
- Timing: `T2`
- Timing: `T3`

---

### 9. Missing critical scalar features in canonical quality-ready buckets

**What exists**

- core scalar features such as `tfi_60s`, `funding_pct_60d`, `oi_zscore_60d`, `cvd_15m`, `force_order_rate_60s` are absent in counted canonical rows

**Why it matters**

- drift validation cannot be trusted if the canonical sample is incomplete

**Handling rule**

- treat as data integrity problem, not as “sparse market behavior”

**Default classification**

- `BLOCKER`

**Query references**

- Drift: `D1`
- Drift: `D6A`

---

### 10. Sparse boolean diagnostic features

**What exists**

- boolean features such as `force_order_spike`, `reclaim_detected`, or divergence flags may fire rarely

**Why it matters**

- can look suspicious if interpreted like scalar fields, but may simply reflect market conditions

**Handling rule**

- rarity alone is not failure
- evaluate only for plausibility, not for required minimum hit count

**Default classification**

- `DOCUMENTED`

**Query references**

- Drift: `D5`

---

## Blocker vs Documented Matrix

| Edge Case | Status If Observed | Rule |
|---|---|---|
| Duplicate rows, same effective outcome after dedupe | `DOCUMENTED` | Dedupe and continue |
| Duplicate rows, ambiguous bucket-level outcome | `BLOCKER` | Cannot trust count |
| Mixed quality rows, at least one row qualifies | `DOCUMENTED` | Count bucket once |
| Mixed quality rows, no qualifying row | `BLOCKER` | Bucket fails |
| Warm-up bucket degraded | `DOCUMENTED` | Excluded by design |
| Lineage break in post-fix counted window | `BLOCKER` | Source-of-truth broken |
| Lineage break only in excluded pre-fix window | `PASS` | Outside Gate A sample |
| Lineage-complete but non-ready bucket | `DOCUMENTED` | Visible, not counted |
| REST present but counted buckets unclipped | `DOCUMENTED` | Provenance note only |
| Counted bucket still clipped by limit | `BLOCKER` | Fix not fully validated |
| Null exchange timestamp in canonical counted bucket | `BLOCKER` | Timing invalid |
| Null timestamp only in excluded warm-up or non-counted rows | `DOCUMENTED` | Record and continue |
| Future timestamp / negative staleness | `BLOCKER` | Temporal inconsistency |
| Missing critical scalar features in counted canonical rows | `BLOCKER` | Drift invalid |
| Sparse boolean diagnostics | `DOCUMENTED` | Not a failure by itself |

---

## Query Cross-Reference

| Edge Case | Primary Queries |
|---|---|
| Duplicate raw rows | `Q2`, `D4` |
| Quality conflicts | `Q3`, `D4` |
| Warm-up bucket | `Q6A`, `D6B` |
| Lineage breaks | `Q6B` |
| Lineage-complete but non-ready buckets | `Q6C` |
| WS vs REST fallback | `Q5`, `T5` |
| Null exchange timestamps | `T2`, `T6A`, `T6B` |
| Future timestamps / negative staleness | `T1A`, `T1B`, `T2`, `T3` |
| Missing critical scalar features | `D1`, `D6A` |
| Sparse boolean diagnostics | `D5` |

---

## Final Gate A Verdict Logic

Use this exact decision tree.

### Step 1. Primary unlock counter

Check:

- `Q1.quality_ready_buckets >= 200`

If `NO`:

- Gate A = `NOT_PASS`
- reason: unlock threshold not reached

If `YES`:

- continue to Step 2

### Step 2. Edge-case blockers

Check all blocker-class conditions from this document.

If any unresolved blocker exists:

- Gate A = `NOT_PASS`
- manual remediation required

If no unresolved blocker exists:

- continue to Step 3

### Step 3. Timing / Staleness result

Check final timing interpretation.

Allowed:

- `PASS`
- `DOCUMENTED`

Disallowed:

- `FAIL`

If timing is `FAIL`:

- Gate A = `NOT_PASS`

If timing is `PASS` or `DOCUMENTED`:

- continue to Step 4

### Step 4. Feature Drift result

Check final drift interpretation.

Allowed:

- `PASS`
- `DOCUMENTED`

Disallowed:

- `FAIL`

If drift is `FAIL`:

- Gate A = `NOT_PASS`

If drift is `PASS` or `DOCUMENTED`:

- continue to Step 5

### Step 5. Final verdict

If all of the following are true:

- `Q1.quality_ready_buckets >= 200`
- no unresolved blockers
- Timing/Staleness = `PASS` or `DOCUMENTED`
- Feature Drift = `PASS` or `DOCUMENTED`

Then:

- Gate A = `PASS`

Otherwise:

- Gate A = `NOT_PASS`

---

## Operator Checklist

During Gate A execution:

1. Run the Market Truth pack.
2. Run the Timing/Staleness pack.
3. Run the Feature Drift pack.
4. Fill the `TBD` placeholders in the three prepared audit documents.
5. Resolve edge cases using this rulebook, not ad hoc judgment.
6. Mark each observed edge case as `PASS`, `DOCUMENTED`, or `BLOCKER`.
7. Apply the final verdict tree exactly.

---

## Bottom Line

This document defines the non-negotiable rule set for Gate A execution.

The key principle is:

- `unlock count is bucket-level`
- `dedupe before interpretation`
- `document benign artifacts`
- `block on anything that breaks source-of-truth, timing integrity, or canonical feature completeness`
