# AUDIT: Market Truth Timing / Staleness

**Date:** 2026-04-26  
**Branch:** `market-truth-v3`  
**Status:** PREPARED_TEMPLATE - execute after `200+` post-fix quality-ready buckets  
**Mode:** Read-only production validation  
**Primary source of truth:** production database on `root@204.168.146.253:/home/btc-bot/btc-bot/storage/btc_bot.db`

---

## Executive Summary

This document is the prepared timing/staleness template for Gate A supporting validation.

It does not contain final thresholds or a final verdict yet. The purpose of this template is to:

- standardize how staleness is measured per input family
- standardize how build timing is measured inside a canonical `15m` bucket view
- separate measurement from interpretation, so Gate A review does not improvise definitions at execution time

This report is a supporting condition for Gate A, not the primary unlock counter. The unlock counter remains:

- `200+ unique post-fix quality-ready 15m buckets`

This report validates whether those counted buckets were also built with acceptable timing and source freshness.

---

## Staleness Metrics Definition

### Counting window

- Measure only the post-fix window starting at `2026-04-25 00:45 UTC`
- Do not include pre-fix buckets
- Treat the `2026-04-25 00:30 UTC` warm-up bucket as an edge case, not as part of the formal Gate A sample

### Canonical row selection

Because raw DB rows may be duplicated inside the same `15m` bucket, this report must select one canonical row per bucket.

Deterministic selection priority:

1. row has full lineage
2. row has all five core quality keys equal to `ready`
3. latest `captured_at`
4. latest `feature_snapshot_id`

This keeps timing metrics stable even when duplicate rows exist.

### Core build metrics

For the canonical row in each bucket, measure:

- `build_duration_seconds`
  - `snapshot_build_finished_at - snapshot_build_started_at`
- `cycle_to_build_start_seconds`
  - `snapshot_build_started_at - cycle_timestamp`
- `cycle_to_build_finish_seconds`
  - `snapshot_build_finished_at - cycle_timestamp`
- `build_finish_to_capture_seconds`
  - `captured_at - snapshot_build_finished_at`

### Per-input staleness metrics

For each canonical bucket, compute:

- `candles_15m_stale_seconds`
  - `cycle_timestamp - candles_15m_exchange_ts`
- `candles_1h_stale_seconds`
  - `cycle_timestamp - candles_1h_exchange_ts`
- `candles_4h_stale_seconds`
  - `cycle_timestamp - candles_4h_exchange_ts`
- `funding_stale_seconds`
  - `cycle_timestamp - funding_exchange_ts`
- `oi_stale_seconds`
  - `cycle_timestamp - oi_exchange_ts`
- `aggtrade_stale_seconds`
  - `cycle_timestamp - aggtrades_exchange_ts`

### Null and future timestamp rules

- `NULL exchange_ts` means missing timestamp, not zero staleness
- negative staleness means future timestamp relative to the cycle and is always suspicious
- this report measures timing only; it does not explain causation

---

## Query Pack Reference

Source file: `scripts/audit_queries/gate_a_timing_staleness.sql`

### T1. Cycle timestamp vs snapshot build timing

**Purpose:**

- validate that build timing is positive
- measure build duration and post-build capture lag

**Outputs:**

- `T1A` summary
- `T1B` anomaly rows
- `T1C` build timing distribution

### T2. Exchange timestamps vs cycle bucket alignment

**Purpose:**

- confirm that exchange timestamps are not in the future
- confirm bucket-alignment logic for candle families
- separate null timestamps from real misalignment

### T3. Per-input staleness summary

**Purpose:**

- produce a per-input freshness breakdown
- surface null and future timestamps per input family

### T4. Distribution metrics

**Purpose:**

- provide `p50`, `p95`, and `max` staleness per input family
- support Gate A interpretation without relying only on averages

### T5. WS vs REST latency comparison

**Purpose:**

- compare aggtrade freshness for websocket-backed vs REST-backed canonical rows
- test the expectation that websocket-backed flow should be fresher

### T6. Missing timestamp detection

**Purpose:**

- make missing build/exchange timestamps explicit
- separate structural timestamp gaps from legitimate high-but-present staleness

---

## Interpretation Rules

These are proposed interpretation rules for Gate A review. They standardize discussion but do not by themselves set policy.

### Proposed `PASS`

- no negative build timing in `T1`
- no future exchange timestamps in `T2`
- all required timestamp fields present in `T6`
- `p95 build duration < 2s` once the final build distribution query is accepted
- most input families remain under `5 minutes` staleness at `p95`

### Proposed `DOCUMENTED`

- some inputs fall in the `5-30 minute` range, but the pattern is explainable
- REST-backed rows are slower than websocket-backed rows, but remain within an accepted operational envelope
- isolated timestamp nulls or gaps map to a known and documented runtime event

### Proposed `FAIL`

- negative build timing
- future exchange timestamps
- unexplained input staleness above `30 minutes`
- missing timestamp fields in canonical post-fix buckets
- timing anomalies large enough to cast doubt on source-of-truth freshness

---

## Edge Cases

### Warm-up bucket after deploy

- known special case: `2026-04-25 00:30 UTC`
- may show elevated lag because the websocket history was still warming up
- exclude from formal Gate A timing totals

### WS vs REST latency

- websocket-backed aggtrade inputs are expected to be fresher than REST-backed fallbacks
- slower REST rows are not automatically invalid, but they must be visible in `T5`

### Null exchange timestamps

- never treat `NULL` as `0 seconds stale`
- keep null handling explicit in `T2`, `T3`, and `T6`

### Gaps in time series

- if canonical buckets are present but timestamps are missing, that is a timestamp gap
- if buckets themselves are missing, that is handled by the Market Truth audit and must be cross-referenced

### Duplicate raw rows

- the same `15m` bucket may contain both a good and a degraded row
- timing metrics must use the canonical row selection, not raw row averages

---

## Appendix: Raw Output Placeholders

### T1A Output

| canonical_bucket_count | negative_build_duration_count | build_finished_before_cycle_count | max_build_duration_seconds | avg_build_duration_seconds | max_cycle_to_build_finish_seconds | avg_cycle_to_build_finish_seconds | max_build_finish_to_capture_seconds | avg_build_finish_to_capture_seconds |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### T1B Output

| bucket_15m | cycle_timestamp | snapshot_id | feature_snapshot_id | snapshot_build_started_at | snapshot_build_finished_at | build_duration_seconds | cycle_to_build_finish_seconds |
|---|---|---|---|---|---|---:|---:|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### T1C Output

| metric_name | sample_count | p50_seconds | p95_seconds | max_seconds |
|---|---:|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD |

### T2 Output

| input_name | canonical_bucket_count | null_exchange_ts_count | future_timestamp_count | aligned_count | misaligned_count |
|---|---:|---:|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD | TBD |

### T3 Output

| input_name | canonical_bucket_count | null_exchange_ts_count | future_timestamp_count | max_stale_seconds | avg_stale_seconds |
|---|---:|---:|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD | TBD |

### T4 Output

| input_name | sample_count | p50_stale_seconds | p95_stale_seconds | max_stale_seconds |
|---|---:|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD |

### T5 Output

| source_group | sample_count | rows_with_ws_last_message | p50_aggtrade_stale_seconds | p95_aggtrade_stale_seconds | max_aggtrade_stale_seconds |
|---|---:|---:|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD | TBD |

### T6A Output

| field_name | canonical_bucket_count | null_count |
|---|---:|---:|
| TBD | TBD | TBD |

### T6B Output

| bucket_15m | cycle_timestamp | snapshot_id | feature_snapshot_id | snapshot_build_started_at | snapshot_build_finished_at | candles_15m_exchange_ts | candles_1h_exchange_ts | candles_4h_exchange_ts | funding_exchange_ts | oi_exchange_ts | aggtrades_exchange_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
