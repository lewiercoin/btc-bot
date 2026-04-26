# AUDIT: Feature Engine Drift

**Date:** 2026-04-26  
**Branch:** `market-truth-v3`  
**Status:** PREPARED_TEMPLATE - execute after `200+` post-fix quality-ready buckets  
**Mode:** Read-only production validation  
**Primary source of truth:** production database on `root@204.168.146.253:/home/btc-bot/btc-bot/storage/btc_bot.db`

---

## Executive Summary

This document is the prepared feature drift template for Gate A supporting validation.

It does not contain the final verdict yet. Its purpose is to:

- standardize which persisted features are measured for Phase 1 drift review
- separate scalar distribution checks from boolean prevalence checks
- force drift interpretation to operate on `post-fix quality-ready canonical 15m buckets`, not raw duplicated rows

This report supports Gate A but does not replace the Market Truth unlock counter.

---

## Drift Sample Definition

### Counting window

- Measure only the post-fix window starting at `2026-04-25 00:45 UTC`
- Exclude all pre-fix buckets
- Keep the `2026-04-25 00:30 UTC` warm-up bucket outside the formal drift sample

### Canonical row selection

Because raw DB rows may be duplicated inside the same `15m` bucket, drift metrics must select one canonical row per bucket.

Deterministic selection priority:

1. row has full lineage
2. row has all five quality keys equal to `ready`
3. latest `captured_at`
4. latest `feature_snapshot_id`

### Bucket eligibility

Only buckets that satisfy all of the following are included in the formal drift sample:

- full lineage:
  - `market_snapshot -> feature_snapshot -> decision_outcome`
- all five quality keys are `ready`:
  - `flow_15m`
  - `flow_60s`
  - `funding_window`
  - `oi_baseline`
  - `cvd_divergence`

---

## Feature Set Under Review

### Scalar features

- `atr_15m`
- `atr_4h`
- `atr_4h_norm`
- `ema50_4h`
- `ema200_4h`
- `funding_8h`
- `funding_sma3`
- `funding_sma9`
- `funding_pct_60d`
- `oi_value`
- `oi_zscore_60d`
- `oi_delta_pct`
- `cvd_15m`
- `tfi_60s`
- `force_order_rate_60s`
- `sweep_depth_pct`

### Boolean diagnostic features

- `force_order_spike`
- `force_order_decreasing`
- `cvd_bullish_divergence`
- `cvd_bearish_divergence`
- `sweep_detected`
- `reclaim_detected`

---

## Query Pack Reference

Source file: `scripts/audit_queries/gate_a_feature_drift.sql`

### D1. Canonical bucket inventory and feature availability

**Purpose:**

- confirm the effective drift sample size
- confirm which scalar features are present or missing in canonical quality-ready buckets

### D2. Scalar summary statistics

**Purpose:**

- compute `null_count`, `min`, `max`, `mean`, and `stddev`
- surface impossible values or suspiciously flat distributions

### D3. Scalar percentiles

**Purpose:**

- provide `p10`, `p50`, and `p90`
- reduce over-reliance on mean values when the sample is skewed

### D4. Duplicate-row feature conflicts

**Purpose:**

- detect same-bucket feature disagreements across duplicated raw rows
- keep canonical drift stats separate from duplicate-row pathology

### D5. Boolean prevalence

**Purpose:**

- report how often boolean diagnostic features fire in the sampled window
- distinguish sparse-but-valid signals from missing fields

### D6. Edge-case checks

**Purpose:**

- detect missing critical scalar fields in canonical buckets
- inspect the warm-up bucket outside the formal sample

---

## Interpretation Rules

These are proposed interpretation rules for Gate A review. They standardize discussion but do not by themselves set policy.

### Proposed `PASS`

- no missing critical scalar features in canonical quality-ready buckets
- scalar features show plausible, finite distributions
- duplicate-row conflicts do not undermine the canonical sample
- boolean features are either observed at plausible rates or are sparse for explainable market reasons

### Proposed `DOCUMENTED`

- some diagnostic booleans are rare or absent in the sample window
- duplicate rows exist, but the canonical selection remains stable
- warm-up bucket shows outlier values, but it is excluded from the formal drift sample

### Proposed `FAIL`

- critical scalar fields missing in canonical quality-ready buckets
- impossible or clearly broken distributions in core scalar features
- duplicate-row conflicts severe enough to make canonical drift interpretation unreliable
- evidence that the post-fix sample is still contaminated by pre-fix or degraded rows

---

## Edge Cases

### Warm-up bucket after deploy

- known special case: `2026-04-25 00:30 UTC`
- may contain outlier feature values during collection warm-up
- inspect separately in `D6B`

### Duplicate raw rows

- the same `15m` bucket may contain multiple raw rows with different feature values
- drift statistics must use canonical rows only
- conflicts stay visible in `D4`

### Sparse boolean features

- `force_order_spike`, `reclaim_detected`, or divergence flags may legitimately be rare
- rarity alone is not a drift failure

### Missing scalar fields

- `NULL` means missing persistence or malformed payload, not zero
- critical scalar nulls in canonical quality-ready buckets are blocker candidates

---

## Appendix: Raw Output Placeholders

### D1 Output

| feature_name | canonical_quality_ready_bucket_count | null_count | non_null_count |
|---|---:|---:|---:|
| TBD | TBD | TBD | TBD |

### D2 Output

| feature_name | row_count | null_count | non_null_count | min_value | max_value | mean_value | stddev_value |
|---|---:|---:|---:|---:|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### D3 Output

| feature_name | sample_count | p10_value | p50_value | p90_value |
|---|---:|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD |

### D4 Output

| bucket_15m | raw_rows_in_bucket | full_lineage_rows | distinct_feature_signatures | observed_signatures |
|---|---:|---:|---:|---|
| TBD | TBD | TBD | TBD | TBD |

### D5 Output

| feature_name | row_count | null_count | true_count | true_rate_pct |
|---|---:|---:|---:|---:|
| TBD | TBD | TBD | TBD | TBD |

### D6A Output

| bucket_15m | feature_snapshot_id | tfi_60s_type | funding_pct_60d_type | oi_zscore_60d_type | cvd_15m_type | force_order_rate_60s_type |
|---|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### D6B Output

| cycle_timestamp | feature_snapshot_id | tfi_60s | funding_pct_60d | oi_zscore_60d | cvd_15m | force_order_rate_60s | force_order_spike |
|---|---|---:|---:|---:|---:|---:|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
