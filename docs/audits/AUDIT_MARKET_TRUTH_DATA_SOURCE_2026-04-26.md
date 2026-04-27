# AUDIT-01: Market Truth / Data Source Audit

**Date:** 2026-04-26  
**Branch:** `market-truth-v3`  
**Status:** PREPARED_TEMPLATE - execute after `200+` post-fix quality-ready buckets  
**Mode:** Read-only production validation  
**Primary source of truth:** production database on `root@204.168.146.253:/home/btc-bot/btc-bot/storage/btc_bot.db`

---

## Executive Summary

This document is the prepared execution template for Gate A Market Truth validation.

It does not contain the final verdict yet. The final verdict is written only after:

- the primary unlock counter reaches `200+ unique post-fix quality-ready 15m buckets`
- the query pack in `scripts/audit_queries/gate_a_market_truth.sql` is executed on production
- timing/staleness and drift supporting reports are reviewed alongside this audit

The purpose of this template is to remove ambiguity before Gate A:

- counting is done at the `15m bucket` level, not per raw database row
- post-fix means `2026-04-25 00:45 UTC` onward
- pre-fix cycles are excluded from the unlock counter by design
- duplicate raw rows are expected and must be deduplicated before any conclusion is written

---

## Counting Methodology

### Gate A primary unlock counter

**Definition:** `200+ unique post-fix quality-ready 15m buckets`

### Bucket-level counting rules

- Count at the `15m bucket` level, not per raw row from `market_snapshots` or `feature_snapshots`
- Use `cycle_timestamp` truncated to `YYYY-MM-DDTHH:MM`
- A bucket counts once if at least one row in that bucket satisfies the Gate A quality-ready definition

### Post-fix window

- Count only buckets from `2026-04-25 00:45 UTC` onward
- Exclude the warm-up bucket `2026-04-25 00:30 UTC`
- Exclude all pre-fix buckets

### Quality-ready definition

A bucket is `quality-ready` if at least one row in that bucket has:

- full lineage:
  - `market_snapshot -> feature_snapshot -> decision_outcome`
  - aligned on the same `15m` bucket
- all five core quality keys equal to `ready`:
  - `flow_15m`
  - `flow_60s`
  - `funding_window`
  - `oi_baseline`
  - `cvd_divergence`

### Supporting Gate A conditions

The counter alone does not close Gate A. The following conditions still apply:

- timing/staleness report = `PASS` or `DOCUMENTED`
- no critical source-of-truth gaps = `CONFIRMED`
- final `AUDIT-01` verdict = `DONE` or accepted `PARTIAL`

---

## SQL Query Pack

Source file: `scripts/audit_queries/gate_a_market_truth.sql`

### Q1. Post-fix quality-ready bucket count

**Purpose:**

- compute the primary Gate A unlock count
- report progress to `200`
- confirm first and last counted buckets

**Expected output fields:**

- `total_postfix_buckets`
- `full_lineage_buckets`
- `quality_ready_buckets`
- `remaining_to_gate_a`
- `pct_to_gate_a`
- `first_quality_ready_bucket`
- `last_quality_ready_bucket`

### Q2. Bucket deduplication check

**Purpose:**

- show where raw DB rows would overcount true `15m` buckets
- make duplicate pressure explicit before any CSV or markdown summary is written

**Expected output fields:**

- `bucket_15m`
- `raw_rows_in_bucket`
- `full_lineage_rows`
- `quality_ready_rows`
- `distinct_market_snapshots`
- `distinct_feature_snapshots`

### Q3. Quality conflict detection

**Purpose:**

- detect buckets where duplicate rows disagree on quality state
- prove that `at least one row ready` is not the same thing as `all rows ready`

**Expected output fields:**

- `bucket_15m`
- `raw_rows_in_bucket`
- `distinct_quality_signatures`
- `full_lineage_rows`
- `observed_signatures`

### Q4. Time range and gaps analysis

**Purpose:**

- verify continuity of the post-fix counting window
- surface missing `15m` buckets before timing/staleness conclusions are written

**Expected output fields:**

- summary:
  - `expected_start_bucket`
  - `expected_end_bucket`
  - `expected_bucket_count`
  - `observed_bucket_count`
  - `missing_bucket_count`
- detail:
  - `missing_bucket_15m`

### Q5. WS vs REST source distribution

**Purpose:**

- confirm that quality-ready buckets are backed by websocket-driven flow
- confirm that clipped REST fallback no longer contaminates counted buckets

**Expected output fields:**

- `quality_ready_buckets`
- `quality_ready_buckets_with_ws_15m`
- `quality_ready_buckets_with_rest_15m`
- `quality_ready_buckets_with_ws_60s`
- `quality_ready_buckets_with_rest_60s`
- `quality_ready_buckets_with_ws_message`
- `quality_ready_buckets_with_clipped_limit`

### Q6. Edge-case checks

**Purpose:**

- make known special cases explicit instead of burying them in narrative

**Subqueries:**

- `Q6A`
  - inspect the `2026-04-25 00:30 UTC` warm-up bucket
- `Q6B`
  - detect lineage breaks inside the counted post-fix window
- `Q6C`
  - list buckets that are lineage-complete but not quality-ready

---

## Results Interpretation

### Gate A counter interpretation

- `PASS`
  - `Q1.quality_ready_buckets >= 200`
- `WAIT`
  - `Q1.quality_ready_buckets < 200`
- `FAIL`
  - counting logic cannot be reproduced at the bucket level, or the query output is internally inconsistent

### Timing and continuity interpretation

- `PASS`
  - `Q4.missing_bucket_count = 0`
- `DOCUMENTED`
  - missing buckets exist, but every gap is tied to a known and accepted runtime event
- `FAIL`
  - unexplained missing buckets or broken continuity in the post-fix window

### Source-of-truth interpretation

- `PASS`
  - `Q5.quality_ready_buckets_with_clipped_limit = 0`
  - websocket-backed flow dominates counted buckets
- `DOCUMENTED`
  - a minority of counted buckets still show mixed WS/REST evidence, but no clipped-limit contamination remains
- `FAIL`
  - counted quality-ready buckets still depend on clipped fallback data, or lineage breaks remain unresolved

### Duplicate-row interpretation

- `DOCUMENTED`
  - `Q2` and `Q3` show duplicate raw rows, but the bucket-level counter remains stable and deduped
- `FAIL`
  - duplicates make the bucket-level count ambiguous or hide unresolved lineage defects

---

## Edge Cases Handling

### Duplicate raw rows in the same 15m bucket

- Expected current behavior: duplicates may exist
- Handling rule:
  - never count raw rows directly
  - always deduplicate to one logical `15m` bucket
  - a bucket passes only once, even if multiple rows inside it are `ready`

### Same bucket with `ready` and `degraded` rows

- Expected current behavior: possible due to parallel or repeated writes
- Handling rule:
  - do not treat this as an automatic blocker
  - the bucket still counts if at least one row is lineage-complete and all five quality keys are `ready`
  - keep the conflict visible via `Q3`

### Warm-up bucket after deploy

- Known special case:
  - `2026-04-25 00:30 UTC`
- Handling rule:
  - exclude from Gate A unlock counting
  - review only as a documented deployment warm-up case

### WS vs REST fallback

- Expected current behavior after the fix:
  - counted buckets should be websocket-backed
  - `clipped_by_limit = false` for counted buckets
- Handling rule:
  - any counted bucket with clipped fallback evidence is a blocker candidate and must be escalated

### Lineage-complete but not quality-ready buckets

- Expected current behavior:
  - possible during recovery or non-counted buckets
- Handling rule:
  - keep visible in `Q6C`
  - do not add them to the Gate A counter

---

## Appendix: Raw Query Output Placeholders

### Q1 Output

| total_postfix_buckets | full_lineage_buckets | quality_ready_buckets | remaining_to_gate_a | pct_to_gate_a | first_quality_ready_bucket | last_quality_ready_bucket |
|---:|---:|---:|---:|---:|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### Q2 Output

| bucket_15m | raw_rows_in_bucket | full_lineage_rows | quality_ready_rows | distinct_market_snapshots | distinct_feature_snapshots |
|---|---:|---:|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD | TBD |

### Q3 Output

| bucket_15m | raw_rows_in_bucket | distinct_quality_signatures | full_lineage_rows | observed_signatures |
|---|---:|---:|---:|---|
| TBD | TBD | TBD | TBD | TBD |

### Q4 Summary Output

| expected_start_bucket | expected_end_bucket | expected_bucket_count | observed_bucket_count | missing_bucket_count |
|---|---|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD |

### Q4 Missing Buckets Output

| missing_bucket_15m |
|---|
| TBD |

### Q5 Output

| quality_ready_buckets | quality_ready_buckets_with_ws_15m | quality_ready_buckets_with_rest_15m | quality_ready_buckets_with_ws_60s | quality_ready_buckets_with_rest_60s | quality_ready_buckets_with_ws_message | quality_ready_buckets_with_clipped_limit |
|---:|---:|---:|---:|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### Q6A Output

| cycle_timestamp | feature_snapshot_id | snapshot_id | has_full_lineage | flow_15m_status | flow_60s_status | funding_window_status | oi_baseline_status | cvd_divergence_status | aggtrade_15m_source | aggtrade_60s_source | ws_last_message_at |
|---|---|---|---:|---|---|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### Q6B Output

| cycle_timestamp | feature_snapshot_id | feature_snapshot_parent_id | market_snapshot_id | decision_outcome_count | snapshot_build_started_at | snapshot_build_finished_at |
|---|---|---|---|---:|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### Q6C Output

| bucket_15m |
|---|
| TBD |
