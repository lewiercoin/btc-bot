-- Gate A / feature-drift query pack
-- Scope: post-fix quality-ready canonical 15m buckets only
-- Window start: 2026-04-25 00:45 UTC
-- Selection rule: one canonical row per 15m bucket
-- Canonical row priority:
--   1. full lineage
--   2. all five quality keys = ready
--   3. latest captured_at
--   4. latest feature_snapshot_id
--
-- How to run:
--   sqlite3 -readonly storage/btc_bot.db < scripts/audit_queries/gate_a_feature_drift.sql

SELECT 'D1: canonical quality-ready bucket inventory and feature availability' AS query_name;
WITH decision_links AS (
    SELECT
        feature_snapshot_id,
        snapshot_id,
        substr(cycle_timestamp, 1, 16) AS bucket_15m,
        COUNT(*) AS decision_outcome_count
    FROM decision_outcomes
    GROUP BY feature_snapshot_id, snapshot_id, substr(cycle_timestamp, 1, 16)
),
per_row AS (
    SELECT
        substr(fs.cycle_timestamp, 1, 16) AS bucket_15m,
        fs.feature_snapshot_id,
        fs.features_json,
        fs.captured_at AS feature_captured_at,
        ms.captured_at AS snapshot_captured_at,
        CASE
            WHEN dl.decision_outcome_count IS NOT NULL
             AND substr(ms.cycle_timestamp, 1, 16) = substr(fs.cycle_timestamp, 1, 16)
             AND dl.bucket_15m = substr(fs.cycle_timestamp, 1, 16)
            THEN 1 ELSE 0
        END AS has_full_lineage,
        CASE
            WHEN json_extract(fs.quality_json, '$.flow_15m.status') = 'ready'
             AND json_extract(fs.quality_json, '$.flow_60s.status') = 'ready'
             AND json_extract(fs.quality_json, '$.funding_window.status') = 'ready'
             AND json_extract(fs.quality_json, '$.oi_baseline.status') = 'ready'
             AND json_extract(fs.quality_json, '$.cvd_divergence.status') = 'ready'
            THEN 1 ELSE 0
        END AS all_five_ready
    FROM feature_snapshots fs
    JOIN market_snapshots ms
      ON ms.snapshot_id = fs.snapshot_id
    LEFT JOIN decision_links dl
      ON dl.feature_snapshot_id = fs.feature_snapshot_id
     AND dl.snapshot_id = fs.snapshot_id
    WHERE fs.cycle_timestamp >= '2026-04-25T00:45:00+00:00'
),
ranked_rows AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY bucket_15m
            ORDER BY has_full_lineage DESC, all_five_ready DESC, snapshot_captured_at DESC, feature_snapshot_id DESC
        ) AS bucket_rank
    FROM per_row
),
canonical_rows AS (
    SELECT * FROM ranked_rows WHERE bucket_rank = 1 AND has_full_lineage = 1 AND all_five_ready = 1
),
feature_presence AS (
    SELECT 'atr_15m' AS feature_name, json_type(features_json, '$.atr_15m') AS feature_type FROM canonical_rows
    UNION ALL SELECT 'atr_4h', json_type(features_json, '$.atr_4h') FROM canonical_rows
    UNION ALL SELECT 'atr_4h_norm', json_type(features_json, '$.atr_4h_norm') FROM canonical_rows
    UNION ALL SELECT 'ema50_4h', json_type(features_json, '$.ema50_4h') FROM canonical_rows
    UNION ALL SELECT 'ema200_4h', json_type(features_json, '$.ema200_4h') FROM canonical_rows
    UNION ALL SELECT 'funding_8h', json_type(features_json, '$.funding_8h') FROM canonical_rows
    UNION ALL SELECT 'funding_sma3', json_type(features_json, '$.funding_sma3') FROM canonical_rows
    UNION ALL SELECT 'funding_sma9', json_type(features_json, '$.funding_sma9') FROM canonical_rows
    UNION ALL SELECT 'funding_pct_60d', json_type(features_json, '$.funding_pct_60d') FROM canonical_rows
    UNION ALL SELECT 'oi_value', json_type(features_json, '$.oi_value') FROM canonical_rows
    UNION ALL SELECT 'oi_zscore_60d', json_type(features_json, '$.oi_zscore_60d') FROM canonical_rows
    UNION ALL SELECT 'oi_delta_pct', json_type(features_json, '$.oi_delta_pct') FROM canonical_rows
    UNION ALL SELECT 'cvd_15m', json_type(features_json, '$.cvd_15m') FROM canonical_rows
    UNION ALL SELECT 'tfi_60s', json_type(features_json, '$.tfi_60s') FROM canonical_rows
    UNION ALL SELECT 'force_order_rate_60s', json_type(features_json, '$.force_order_rate_60s') FROM canonical_rows
    UNION ALL SELECT 'sweep_depth_pct', json_type(features_json, '$.sweep_depth_pct') FROM canonical_rows
)
SELECT
    feature_name,
    (SELECT COUNT(*) FROM canonical_rows) AS canonical_quality_ready_bucket_count,
    SUM(CASE WHEN feature_type IS NULL THEN 1 ELSE 0 END) AS null_count,
    SUM(CASE WHEN feature_type IS NOT NULL THEN 1 ELSE 0 END) AS non_null_count
FROM feature_presence
GROUP BY feature_name
ORDER BY feature_name;

SELECT 'D2: scalar feature summary statistics' AS query_name;
WITH decision_links AS (
    SELECT
        feature_snapshot_id,
        snapshot_id,
        substr(cycle_timestamp, 1, 16) AS bucket_15m,
        COUNT(*) AS decision_outcome_count
    FROM decision_outcomes
    GROUP BY feature_snapshot_id, snapshot_id, substr(cycle_timestamp, 1, 16)
),
per_row AS (
    SELECT
        substr(fs.cycle_timestamp, 1, 16) AS bucket_15m,
        fs.feature_snapshot_id,
        fs.features_json,
        ms.captured_at AS snapshot_captured_at,
        CASE
            WHEN dl.decision_outcome_count IS NOT NULL
             AND substr(ms.cycle_timestamp, 1, 16) = substr(fs.cycle_timestamp, 1, 16)
             AND dl.bucket_15m = substr(fs.cycle_timestamp, 1, 16)
            THEN 1 ELSE 0
        END AS has_full_lineage,
        CASE
            WHEN json_extract(fs.quality_json, '$.flow_15m.status') = 'ready'
             AND json_extract(fs.quality_json, '$.flow_60s.status') = 'ready'
             AND json_extract(fs.quality_json, '$.funding_window.status') = 'ready'
             AND json_extract(fs.quality_json, '$.oi_baseline.status') = 'ready'
             AND json_extract(fs.quality_json, '$.cvd_divergence.status') = 'ready'
            THEN 1 ELSE 0
        END AS all_five_ready
    FROM feature_snapshots fs
    JOIN market_snapshots ms
      ON ms.snapshot_id = fs.snapshot_id
    LEFT JOIN decision_links dl
      ON dl.feature_snapshot_id = fs.feature_snapshot_id
     AND dl.snapshot_id = fs.snapshot_id
    WHERE fs.cycle_timestamp >= '2026-04-25T00:45:00+00:00'
),
ranked_rows AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY bucket_15m
            ORDER BY has_full_lineage DESC, all_five_ready DESC, snapshot_captured_at DESC, feature_snapshot_id DESC
        ) AS bucket_rank
    FROM per_row
),
canonical_rows AS (
    SELECT * FROM ranked_rows WHERE bucket_rank = 1 AND has_full_lineage = 1 AND all_five_ready = 1
),
scalar_rows AS (
    SELECT 'atr_15m' AS feature_name, CAST(json_extract(features_json, '$.atr_15m') AS REAL) AS feature_value FROM canonical_rows
    UNION ALL SELECT 'atr_4h', CAST(json_extract(features_json, '$.atr_4h') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'atr_4h_norm', CAST(json_extract(features_json, '$.atr_4h_norm') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'ema50_4h', CAST(json_extract(features_json, '$.ema50_4h') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'ema200_4h', CAST(json_extract(features_json, '$.ema200_4h') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'funding_8h', CAST(json_extract(features_json, '$.funding_8h') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'funding_sma3', CAST(json_extract(features_json, '$.funding_sma3') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'funding_sma9', CAST(json_extract(features_json, '$.funding_sma9') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'funding_pct_60d', CAST(json_extract(features_json, '$.funding_pct_60d') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'oi_value', CAST(json_extract(features_json, '$.oi_value') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'oi_zscore_60d', CAST(json_extract(features_json, '$.oi_zscore_60d') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'oi_delta_pct', CAST(json_extract(features_json, '$.oi_delta_pct') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'cvd_15m', CAST(json_extract(features_json, '$.cvd_15m') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'tfi_60s', CAST(json_extract(features_json, '$.tfi_60s') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'force_order_rate_60s', CAST(json_extract(features_json, '$.force_order_rate_60s') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'sweep_depth_pct', CAST(json_extract(features_json, '$.sweep_depth_pct') AS REAL) FROM canonical_rows
),
stats AS (
    SELECT
        feature_name,
        COUNT(*) AS row_count,
        SUM(CASE WHEN feature_value IS NULL THEN 1 ELSE 0 END) AS null_count,
        COUNT(feature_value) AS non_null_count,
        MIN(feature_value) AS min_value,
        MAX(feature_value) AS max_value,
        AVG(feature_value) AS mean_value,
        CASE
            WHEN COUNT(feature_value) > 1
            THEN sqrt(AVG(feature_value * feature_value) - AVG(feature_value) * AVG(feature_value))
            ELSE NULL
        END AS stddev_value
    FROM scalar_rows
    GROUP BY feature_name
)
SELECT
    feature_name,
    row_count,
    null_count,
    non_null_count,
    ROUND(min_value, 6) AS min_value,
    ROUND(max_value, 6) AS max_value,
    ROUND(mean_value, 6) AS mean_value,
    ROUND(stddev_value, 6) AS stddev_value
FROM stats
ORDER BY feature_name;

SELECT 'D3: scalar feature percentile summary (p10/p50/p90)' AS query_name;
WITH decision_links AS (
    SELECT
        feature_snapshot_id,
        snapshot_id,
        substr(cycle_timestamp, 1, 16) AS bucket_15m,
        COUNT(*) AS decision_outcome_count
    FROM decision_outcomes
    GROUP BY feature_snapshot_id, snapshot_id, substr(cycle_timestamp, 1, 16)
),
per_row AS (
    SELECT
        substr(fs.cycle_timestamp, 1, 16) AS bucket_15m,
        fs.feature_snapshot_id,
        fs.features_json,
        ms.captured_at AS snapshot_captured_at,
        CASE
            WHEN dl.decision_outcome_count IS NOT NULL
             AND substr(ms.cycle_timestamp, 1, 16) = substr(fs.cycle_timestamp, 1, 16)
             AND dl.bucket_15m = substr(fs.cycle_timestamp, 1, 16)
            THEN 1 ELSE 0
        END AS has_full_lineage,
        CASE
            WHEN json_extract(fs.quality_json, '$.flow_15m.status') = 'ready'
             AND json_extract(fs.quality_json, '$.flow_60s.status') = 'ready'
             AND json_extract(fs.quality_json, '$.funding_window.status') = 'ready'
             AND json_extract(fs.quality_json, '$.oi_baseline.status') = 'ready'
             AND json_extract(fs.quality_json, '$.cvd_divergence.status') = 'ready'
            THEN 1 ELSE 0
        END AS all_five_ready
    FROM feature_snapshots fs
    JOIN market_snapshots ms
      ON ms.snapshot_id = fs.snapshot_id
    LEFT JOIN decision_links dl
      ON dl.feature_snapshot_id = fs.feature_snapshot_id
     AND dl.snapshot_id = fs.snapshot_id
    WHERE fs.cycle_timestamp >= '2026-04-25T00:45:00+00:00'
),
ranked_rows AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY bucket_15m
            ORDER BY has_full_lineage DESC, all_five_ready DESC, snapshot_captured_at DESC, feature_snapshot_id DESC
        ) AS bucket_rank
    FROM per_row
),
canonical_rows AS (
    SELECT * FROM ranked_rows WHERE bucket_rank = 1 AND has_full_lineage = 1 AND all_five_ready = 1
),
scalar_rows AS (
    SELECT 'atr_15m' AS feature_name, CAST(json_extract(features_json, '$.atr_15m') AS REAL) AS feature_value FROM canonical_rows
    UNION ALL SELECT 'atr_4h', CAST(json_extract(features_json, '$.atr_4h') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'atr_4h_norm', CAST(json_extract(features_json, '$.atr_4h_norm') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'ema50_4h', CAST(json_extract(features_json, '$.ema50_4h') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'ema200_4h', CAST(json_extract(features_json, '$.ema200_4h') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'funding_8h', CAST(json_extract(features_json, '$.funding_8h') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'funding_sma3', CAST(json_extract(features_json, '$.funding_sma3') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'funding_sma9', CAST(json_extract(features_json, '$.funding_sma9') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'funding_pct_60d', CAST(json_extract(features_json, '$.funding_pct_60d') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'oi_value', CAST(json_extract(features_json, '$.oi_value') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'oi_zscore_60d', CAST(json_extract(features_json, '$.oi_zscore_60d') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'oi_delta_pct', CAST(json_extract(features_json, '$.oi_delta_pct') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'cvd_15m', CAST(json_extract(features_json, '$.cvd_15m') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'tfi_60s', CAST(json_extract(features_json, '$.tfi_60s') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'force_order_rate_60s', CAST(json_extract(features_json, '$.force_order_rate_60s') AS REAL) FROM canonical_rows
    UNION ALL SELECT 'sweep_depth_pct', CAST(json_extract(features_json, '$.sweep_depth_pct') AS REAL) FROM canonical_rows
),
filtered AS (
    SELECT feature_name, feature_value
    FROM scalar_rows
    WHERE feature_value IS NOT NULL
),
ordered AS (
    SELECT
        feature_name,
        feature_value,
        ROW_NUMBER() OVER (PARTITION BY feature_name ORDER BY feature_value) AS rn,
        COUNT(*) OVER (PARTITION BY feature_name) AS cnt
    FROM filtered
),
positions AS (
    SELECT
        feature_name,
        feature_value,
        rn,
        cnt,
        CAST(((cnt * 10) + 99) / 100 AS INTEGER) AS p10_pos,
        CAST((cnt + 1) / 2 AS INTEGER) AS p50_pos_lo,
        CAST((cnt + 2) / 2 AS INTEGER) AS p50_pos_hi,
        CAST(((cnt * 90) + 99) / 100 AS INTEGER) AS p90_pos
    FROM ordered
)
SELECT
    feature_name,
    MAX(cnt) AS sample_count,
    ROUND(MAX(CASE WHEN rn = p10_pos THEN feature_value END), 6) AS p10_value,
    ROUND(AVG(CASE WHEN rn IN (p50_pos_lo, p50_pos_hi) THEN feature_value END), 6) AS p50_value,
    ROUND(MAX(CASE WHEN rn = p90_pos THEN feature_value END), 6) AS p90_value
FROM positions
GROUP BY feature_name
ORDER BY feature_name;

SELECT 'D4: duplicate-row feature conflicts inside the same 15m bucket' AS query_name;
WITH decision_links AS (
    SELECT
        feature_snapshot_id,
        snapshot_id,
        substr(cycle_timestamp, 1, 16) AS bucket_15m,
        COUNT(*) AS decision_outcome_count
    FROM decision_outcomes
    GROUP BY feature_snapshot_id, snapshot_id, substr(cycle_timestamp, 1, 16)
),
per_row AS (
    SELECT
        substr(fs.cycle_timestamp, 1, 16) AS bucket_15m,
        fs.feature_snapshot_id,
        CASE
            WHEN dl.decision_outcome_count IS NOT NULL
             AND substr(ms.cycle_timestamp, 1, 16) = substr(fs.cycle_timestamp, 1, 16)
             AND dl.bucket_15m = substr(fs.cycle_timestamp, 1, 16)
            THEN 1 ELSE 0
        END AS has_full_lineage,
        COALESCE(CAST(json_extract(fs.features_json, '$.tfi_60s') AS TEXT), 'null') || '/' ||
        COALESCE(CAST(json_extract(fs.features_json, '$.funding_pct_60d') AS TEXT), 'null') || '/' ||
        COALESCE(CAST(json_extract(fs.features_json, '$.oi_zscore_60d') AS TEXT), 'null') || '/' ||
        COALESCE(CAST(json_extract(fs.features_json, '$.cvd_15m') AS TEXT), 'null') || '/' ||
        COALESCE(CAST(json_extract(fs.features_json, '$.force_order_rate_60s') AS TEXT), 'null') AS drift_signature
    FROM feature_snapshots fs
    JOIN market_snapshots ms
      ON ms.snapshot_id = fs.snapshot_id
    LEFT JOIN decision_links dl
      ON dl.feature_snapshot_id = fs.feature_snapshot_id
     AND dl.snapshot_id = fs.snapshot_id
    WHERE fs.cycle_timestamp >= '2026-04-25T00:45:00+00:00'
)
SELECT
    bucket_15m,
    COUNT(*) AS raw_rows_in_bucket,
    SUM(has_full_lineage) AS full_lineage_rows,
    COUNT(DISTINCT drift_signature) AS distinct_feature_signatures,
    GROUP_CONCAT(drift_signature, ' | ') AS observed_signatures
FROM per_row
GROUP BY bucket_15m
HAVING COUNT(*) > 1 AND COUNT(DISTINCT drift_signature) > 1
ORDER BY bucket_15m;

SELECT 'D5: boolean feature prevalence on canonical quality-ready buckets' AS query_name;
WITH decision_links AS (
    SELECT
        feature_snapshot_id,
        snapshot_id,
        substr(cycle_timestamp, 1, 16) AS bucket_15m,
        COUNT(*) AS decision_outcome_count
    FROM decision_outcomes
    GROUP BY feature_snapshot_id, snapshot_id, substr(cycle_timestamp, 1, 16)
),
per_row AS (
    SELECT
        substr(fs.cycle_timestamp, 1, 16) AS bucket_15m,
        fs.feature_snapshot_id,
        fs.features_json,
        ms.captured_at AS snapshot_captured_at,
        CASE
            WHEN dl.decision_outcome_count IS NOT NULL
             AND substr(ms.cycle_timestamp, 1, 16) = substr(fs.cycle_timestamp, 1, 16)
             AND dl.bucket_15m = substr(fs.cycle_timestamp, 1, 16)
            THEN 1 ELSE 0
        END AS has_full_lineage,
        CASE
            WHEN json_extract(fs.quality_json, '$.flow_15m.status') = 'ready'
             AND json_extract(fs.quality_json, '$.flow_60s.status') = 'ready'
             AND json_extract(fs.quality_json, '$.funding_window.status') = 'ready'
             AND json_extract(fs.quality_json, '$.oi_baseline.status') = 'ready'
             AND json_extract(fs.quality_json, '$.cvd_divergence.status') = 'ready'
            THEN 1 ELSE 0
        END AS all_five_ready
    FROM feature_snapshots fs
    JOIN market_snapshots ms
      ON ms.snapshot_id = fs.snapshot_id
    LEFT JOIN decision_links dl
      ON dl.feature_snapshot_id = fs.feature_snapshot_id
     AND dl.snapshot_id = fs.snapshot_id
    WHERE fs.cycle_timestamp >= '2026-04-25T00:45:00+00:00'
),
ranked_rows AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY bucket_15m
            ORDER BY has_full_lineage DESC, all_five_ready DESC, snapshot_captured_at DESC, feature_snapshot_id DESC
        ) AS bucket_rank
    FROM per_row
),
canonical_rows AS (
    SELECT * FROM ranked_rows WHERE bucket_rank = 1 AND has_full_lineage = 1 AND all_five_ready = 1
),
boolean_rows AS (
    SELECT 'force_order_spike' AS feature_name, CAST(json_extract(features_json, '$.force_order_spike') AS INTEGER) AS feature_value FROM canonical_rows
    UNION ALL SELECT 'force_order_decreasing', CAST(json_extract(features_json, '$.force_order_decreasing') AS INTEGER) FROM canonical_rows
    UNION ALL SELECT 'cvd_bullish_divergence', CAST(json_extract(features_json, '$.cvd_bullish_divergence') AS INTEGER) FROM canonical_rows
    UNION ALL SELECT 'cvd_bearish_divergence', CAST(json_extract(features_json, '$.cvd_bearish_divergence') AS INTEGER) FROM canonical_rows
    UNION ALL SELECT 'sweep_detected', CAST(json_extract(features_json, '$.sweep_detected') AS INTEGER) FROM canonical_rows
    UNION ALL SELECT 'reclaim_detected', CAST(json_extract(features_json, '$.reclaim_detected') AS INTEGER) FROM canonical_rows
)
SELECT
    feature_name,
    COUNT(*) AS row_count,
    SUM(CASE WHEN feature_value IS NULL THEN 1 ELSE 0 END) AS null_count,
    SUM(CASE WHEN feature_value = 1 THEN 1 ELSE 0 END) AS true_count,
    ROUND(100.0 * SUM(CASE WHEN feature_value = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS true_rate_pct
FROM boolean_rows
GROUP BY feature_name
ORDER BY feature_name;

SELECT 'D6A: canonical quality-ready buckets with missing critical scalar features' AS query_name;
WITH decision_links AS (
    SELECT
        feature_snapshot_id,
        snapshot_id,
        substr(cycle_timestamp, 1, 16) AS bucket_15m,
        COUNT(*) AS decision_outcome_count
    FROM decision_outcomes
    GROUP BY feature_snapshot_id, snapshot_id, substr(cycle_timestamp, 1, 16)
),
per_row AS (
    SELECT
        substr(fs.cycle_timestamp, 1, 16) AS bucket_15m,
        fs.feature_snapshot_id,
        fs.features_json,
        ms.captured_at AS snapshot_captured_at,
        CASE
            WHEN dl.decision_outcome_count IS NOT NULL
             AND substr(ms.cycle_timestamp, 1, 16) = substr(fs.cycle_timestamp, 1, 16)
             AND dl.bucket_15m = substr(fs.cycle_timestamp, 1, 16)
            THEN 1 ELSE 0
        END AS has_full_lineage,
        CASE
            WHEN json_extract(fs.quality_json, '$.flow_15m.status') = 'ready'
             AND json_extract(fs.quality_json, '$.flow_60s.status') = 'ready'
             AND json_extract(fs.quality_json, '$.funding_window.status') = 'ready'
             AND json_extract(fs.quality_json, '$.oi_baseline.status') = 'ready'
             AND json_extract(fs.quality_json, '$.cvd_divergence.status') = 'ready'
            THEN 1 ELSE 0
        END AS all_five_ready
    FROM feature_snapshots fs
    JOIN market_snapshots ms
      ON ms.snapshot_id = fs.snapshot_id
    LEFT JOIN decision_links dl
      ON dl.feature_snapshot_id = fs.feature_snapshot_id
     AND dl.snapshot_id = fs.snapshot_id
    WHERE fs.cycle_timestamp >= '2026-04-25T00:45:00+00:00'
),
ranked_rows AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY bucket_15m
            ORDER BY has_full_lineage DESC, all_five_ready DESC, snapshot_captured_at DESC, feature_snapshot_id DESC
        ) AS bucket_rank
    FROM per_row
),
canonical_rows AS (
    SELECT * FROM ranked_rows WHERE bucket_rank = 1 AND has_full_lineage = 1 AND all_five_ready = 1
)
SELECT
    bucket_15m,
    feature_snapshot_id,
    json_type(features_json, '$.tfi_60s') AS tfi_60s_type,
    json_type(features_json, '$.funding_pct_60d') AS funding_pct_60d_type,
    json_type(features_json, '$.oi_zscore_60d') AS oi_zscore_60d_type,
    json_type(features_json, '$.cvd_15m') AS cvd_15m_type,
    json_type(features_json, '$.force_order_rate_60s') AS force_order_rate_60s_type
FROM canonical_rows
WHERE json_type(features_json, '$.tfi_60s') IS NULL
   OR json_type(features_json, '$.funding_pct_60d') IS NULL
   OR json_type(features_json, '$.oi_zscore_60d') IS NULL
   OR json_type(features_json, '$.cvd_15m') IS NULL
   OR json_type(features_json, '$.force_order_rate_60s') IS NULL
ORDER BY bucket_15m;

SELECT 'D6B: warm-up bucket feature snapshot inspection' AS query_name;
SELECT
    fs.cycle_timestamp,
    fs.feature_snapshot_id,
    json_extract(fs.features_json, '$.tfi_60s') AS tfi_60s,
    json_extract(fs.features_json, '$.funding_pct_60d') AS funding_pct_60d,
    json_extract(fs.features_json, '$.oi_zscore_60d') AS oi_zscore_60d,
    json_extract(fs.features_json, '$.cvd_15m') AS cvd_15m,
    json_extract(fs.features_json, '$.force_order_rate_60s') AS force_order_rate_60s,
    json_extract(fs.features_json, '$.force_order_spike') AS force_order_spike
FROM feature_snapshots fs
WHERE fs.cycle_timestamp >= '2026-04-25T00:30:00+00:00'
  AND fs.cycle_timestamp < '2026-04-25T00:45:00+00:00'
ORDER BY fs.cycle_timestamp, fs.feature_snapshot_id;
