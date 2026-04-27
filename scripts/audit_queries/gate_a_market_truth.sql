-- Gate A / AUDIT-01 Market Truth query pack
-- Scope: post-fix window only, read-only execution against production SQLite
-- Window start: 2026-04-25 00:45 UTC (first post-fix quality-ready bucket)
-- Counting rule: unique 15m bucket, not raw database row
--
-- How to run:
--   sqlite3 -readonly storage/btc_bot.db < scripts/audit_queries/gate_a_market_truth.sql
--
-- Note:
--   Each query is self-contained. Copy individual query blocks if CSV export is needed.

SELECT 'Q1: post-fix quality-ready bucket count' AS query_name;
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
        ms.snapshot_id,
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
per_bucket AS (
    SELECT
        bucket_15m,
        MAX(has_full_lineage) AS has_full_lineage,
        MAX(CASE WHEN has_full_lineage = 1 AND all_five_ready = 1 THEN 1 ELSE 0 END) AS is_quality_ready
    FROM per_row
    GROUP BY bucket_15m
)
SELECT
    COUNT(*) AS total_postfix_buckets,
    SUM(has_full_lineage) AS full_lineage_buckets,
    SUM(is_quality_ready) AS quality_ready_buckets,
    CASE
        WHEN SUM(is_quality_ready) >= 200 THEN 0
        ELSE 200 - SUM(is_quality_ready)
    END AS remaining_to_gate_a,
    ROUND(100.0 * SUM(is_quality_ready) / 200.0, 1) AS pct_to_gate_a,
    MIN(CASE WHEN is_quality_ready = 1 THEN bucket_15m END) AS first_quality_ready_bucket,
    MAX(CASE WHEN is_quality_ready = 1 THEN bucket_15m END) AS last_quality_ready_bucket
FROM per_bucket;

SELECT 'Q2: bucket deduplication check (raw rows per 15m bucket)' AS query_name;
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
        fs.snapshot_id AS feature_snapshot_parent_id,
        ms.snapshot_id AS market_snapshot_id,
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
)
SELECT
    bucket_15m,
    COUNT(*) AS raw_rows_in_bucket,
    SUM(has_full_lineage) AS full_lineage_rows,
    SUM(CASE WHEN has_full_lineage = 1 AND all_five_ready = 1 THEN 1 ELSE 0 END) AS quality_ready_rows,
    COUNT(DISTINCT market_snapshot_id) AS distinct_market_snapshots,
    COUNT(DISTINCT feature_snapshot_id) AS distinct_feature_snapshots
FROM per_row
GROUP BY bucket_15m
HAVING COUNT(*) > 1
ORDER BY bucket_15m;

SELECT 'Q3: quality conflict detection inside the same 15m bucket' AS query_name;
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
        COALESCE(json_extract(fs.quality_json, '$.flow_15m.status'), 'missing') AS flow_15m_status,
        COALESCE(json_extract(fs.quality_json, '$.flow_60s.status'), 'missing') AS flow_60s_status,
        COALESCE(json_extract(fs.quality_json, '$.funding_window.status'), 'missing') AS funding_window_status,
        COALESCE(json_extract(fs.quality_json, '$.oi_baseline.status'), 'missing') AS oi_baseline_status,
        COALESCE(json_extract(fs.quality_json, '$.cvd_divergence.status'), 'missing') AS cvd_divergence_status
    FROM feature_snapshots fs
    JOIN market_snapshots ms
      ON ms.snapshot_id = fs.snapshot_id
    LEFT JOIN decision_links dl
      ON dl.feature_snapshot_id = fs.feature_snapshot_id
     AND dl.snapshot_id = fs.snapshot_id
    WHERE fs.cycle_timestamp >= '2026-04-25T00:45:00+00:00'
),
bucket_signatures AS (
    SELECT
        bucket_15m,
        feature_snapshot_id,
        has_full_lineage,
        flow_15m_status || '/' || flow_60s_status || '/' ||
        funding_window_status || '/' || oi_baseline_status || '/' ||
        cvd_divergence_status AS quality_signature
    FROM per_row
)
SELECT
    bucket_15m,
    COUNT(*) AS raw_rows_in_bucket,
    COUNT(DISTINCT quality_signature) AS distinct_quality_signatures,
    SUM(has_full_lineage) AS full_lineage_rows,
    GROUP_CONCAT(quality_signature, ' | ') AS observed_signatures
FROM bucket_signatures
GROUP BY bucket_15m
HAVING COUNT(DISTINCT quality_signature) > 1
ORDER BY bucket_15m;

SELECT 'Q4A: time range summary and expected-vs-observed bucket coverage' AS query_name;
WITH decision_links AS (
    SELECT
        feature_snapshot_id,
        snapshot_id,
        substr(cycle_timestamp, 1, 16) AS bucket_15m
    FROM decision_outcomes
    GROUP BY feature_snapshot_id, snapshot_id, substr(cycle_timestamp, 1, 16)
),
observed AS (
    SELECT DISTINCT
        substr(fs.cycle_timestamp, 1, 16) AS bucket_15m
    FROM feature_snapshots fs
    JOIN market_snapshots ms
      ON ms.snapshot_id = fs.snapshot_id
    LEFT JOIN decision_links dl
      ON dl.feature_snapshot_id = fs.feature_snapshot_id
     AND dl.snapshot_id = fs.snapshot_id
    WHERE fs.cycle_timestamp >= '2026-04-25T00:45:00+00:00'
      AND dl.bucket_15m = substr(fs.cycle_timestamp, 1, 16)
      AND substr(ms.cycle_timestamp, 1, 16) = substr(fs.cycle_timestamp, 1, 16)
),
bounds AS (
    SELECT
        '2026-04-25T00:45' AS expected_start_bucket,
        MAX(bucket_15m) AS expected_end_bucket
    FROM observed
),
expected AS (
    WITH RECURSIVE series(bucket_15m) AS (
        SELECT expected_start_bucket FROM bounds
        UNION ALL
        SELECT strftime('%Y-%m-%dT%H:%M', datetime(bucket_15m || ':00+00:00', '+15 minutes'))
        FROM series
        WHERE bucket_15m < (SELECT expected_end_bucket FROM bounds)
    )
    SELECT bucket_15m FROM series
)
SELECT
    (SELECT expected_start_bucket FROM bounds) AS expected_start_bucket,
    (SELECT expected_end_bucket FROM bounds) AS expected_end_bucket,
    COUNT(*) AS expected_bucket_count,
    SUM(CASE WHEN observed.bucket_15m IS NOT NULL THEN 1 ELSE 0 END) AS observed_bucket_count,
    SUM(CASE WHEN observed.bucket_15m IS NULL THEN 1 ELSE 0 END) AS missing_bucket_count
FROM expected
LEFT JOIN observed
  ON observed.bucket_15m = expected.bucket_15m;

SELECT 'Q4B: missing 15m buckets in the post-fix lineage-complete window' AS query_name;
WITH decision_links AS (
    SELECT
        feature_snapshot_id,
        snapshot_id,
        substr(cycle_timestamp, 1, 16) AS bucket_15m
    FROM decision_outcomes
    GROUP BY feature_snapshot_id, snapshot_id, substr(cycle_timestamp, 1, 16)
),
observed AS (
    SELECT DISTINCT
        substr(fs.cycle_timestamp, 1, 16) AS bucket_15m
    FROM feature_snapshots fs
    JOIN market_snapshots ms
      ON ms.snapshot_id = fs.snapshot_id
    LEFT JOIN decision_links dl
      ON dl.feature_snapshot_id = fs.feature_snapshot_id
     AND dl.snapshot_id = fs.snapshot_id
    WHERE fs.cycle_timestamp >= '2026-04-25T00:45:00+00:00'
      AND dl.bucket_15m = substr(fs.cycle_timestamp, 1, 16)
      AND substr(ms.cycle_timestamp, 1, 16) = substr(fs.cycle_timestamp, 1, 16)
),
bounds AS (
    SELECT
        '2026-04-25T00:45' AS expected_start_bucket,
        MAX(bucket_15m) AS expected_end_bucket
    FROM observed
),
expected AS (
    WITH RECURSIVE series(bucket_15m) AS (
        SELECT expected_start_bucket FROM bounds
        UNION ALL
        SELECT strftime('%Y-%m-%dT%H:%M', datetime(bucket_15m || ':00+00:00', '+15 minutes'))
        FROM series
        WHERE bucket_15m < (SELECT expected_end_bucket FROM bounds)
    )
    SELECT bucket_15m FROM series
)
SELECT
    expected.bucket_15m AS missing_bucket_15m
FROM expected
LEFT JOIN observed
  ON observed.bucket_15m = expected.bucket_15m
WHERE observed.bucket_15m IS NULL
ORDER BY expected.bucket_15m;

SELECT 'Q5: WS vs REST source distribution for post-fix quality-ready buckets' AS query_name;
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
        CASE
            WHEN dl.decision_outcome_count IS NOT NULL
             AND substr(ms.cycle_timestamp, 1, 16) = substr(fs.cycle_timestamp, 1, 16)
             AND dl.bucket_15m = substr(fs.cycle_timestamp, 1, 16)
             AND json_extract(fs.quality_json, '$.flow_15m.status') = 'ready'
             AND json_extract(fs.quality_json, '$.flow_60s.status') = 'ready'
             AND json_extract(fs.quality_json, '$.funding_window.status') = 'ready'
             AND json_extract(fs.quality_json, '$.oi_baseline.status') = 'ready'
             AND json_extract(fs.quality_json, '$.cvd_divergence.status') = 'ready'
            THEN 1 ELSE 0
        END AS is_quality_ready,
        COALESCE(json_extract(ms.source_meta_json, '$.aggtrade_15m.source'), 'missing') AS aggtrade_15m_source,
        COALESCE(json_extract(ms.source_meta_json, '$.aggtrade_60s.source'), 'missing') AS aggtrade_60s_source,
        CASE
            WHEN json_extract(ms.source_meta_json, '$.ws_last_message_at') IS NOT NULL
            THEN 1 ELSE 0
        END AS has_ws_last_message,
        CASE
            WHEN COALESCE(json_extract(ms.source_meta_json, '$.aggtrade_15m.clipped_by_limit'), 0) = 1
              OR COALESCE(json_extract(ms.source_meta_json, '$.aggtrade_60s.clipped_by_limit'), 0) = 1
            THEN 1 ELSE 0
        END AS any_clipped_by_limit
    FROM feature_snapshots fs
    JOIN market_snapshots ms
      ON ms.snapshot_id = fs.snapshot_id
    LEFT JOIN decision_links dl
      ON dl.feature_snapshot_id = fs.feature_snapshot_id
     AND dl.snapshot_id = fs.snapshot_id
    WHERE fs.cycle_timestamp >= '2026-04-25T00:45:00+00:00'
),
per_bucket AS (
    SELECT
        bucket_15m,
        MAX(CASE WHEN is_quality_ready = 1 THEN 1 ELSE 0 END) AS is_quality_ready_bucket,
        MAX(CASE WHEN is_quality_ready = 1 AND aggtrade_15m_source = 'ws' THEN 1 ELSE 0 END) AS has_ready_ws_15m,
        MAX(CASE WHEN is_quality_ready = 1 AND aggtrade_15m_source = 'rest' THEN 1 ELSE 0 END) AS has_ready_rest_15m,
        MAX(CASE WHEN is_quality_ready = 1 AND aggtrade_60s_source = 'ws' THEN 1 ELSE 0 END) AS has_ready_ws_60s,
        MAX(CASE WHEN is_quality_ready = 1 AND aggtrade_60s_source = 'rest' THEN 1 ELSE 0 END) AS has_ready_rest_60s,
        MAX(CASE WHEN is_quality_ready = 1 AND has_ws_last_message = 1 THEN 1 ELSE 0 END) AS has_ready_ws_last_message,
        MAX(CASE WHEN is_quality_ready = 1 AND any_clipped_by_limit = 1 THEN 1 ELSE 0 END) AS has_ready_clipped_row
    FROM per_row
    GROUP BY bucket_15m
)
SELECT
    SUM(is_quality_ready_bucket) AS quality_ready_buckets,
    SUM(has_ready_ws_15m) AS quality_ready_buckets_with_ws_15m,
    SUM(has_ready_rest_15m) AS quality_ready_buckets_with_rest_15m,
    SUM(has_ready_ws_60s) AS quality_ready_buckets_with_ws_60s,
    SUM(has_ready_rest_60s) AS quality_ready_buckets_with_rest_60s,
    SUM(has_ready_ws_last_message) AS quality_ready_buckets_with_ws_message,
    SUM(has_ready_clipped_row) AS quality_ready_buckets_with_clipped_limit
FROM per_bucket;

SELECT 'Q6A: warm-up bucket immediately after deploy (should stay outside Gate A counter)' AS query_name;
WITH decision_links AS (
    SELECT
        feature_snapshot_id,
        snapshot_id,
        substr(cycle_timestamp, 1, 16) AS bucket_15m,
        COUNT(*) AS decision_outcome_count
    FROM decision_outcomes
    GROUP BY feature_snapshot_id, snapshot_id, substr(cycle_timestamp, 1, 16)
)
SELECT
    fs.cycle_timestamp,
    fs.feature_snapshot_id,
    ms.snapshot_id,
    CASE
        WHEN dl.decision_outcome_count IS NOT NULL
         AND substr(ms.cycle_timestamp, 1, 16) = substr(fs.cycle_timestamp, 1, 16)
         AND dl.bucket_15m = substr(fs.cycle_timestamp, 1, 16)
        THEN 1 ELSE 0
    END AS has_full_lineage,
    json_extract(fs.quality_json, '$.flow_15m.status') AS flow_15m_status,
    json_extract(fs.quality_json, '$.flow_60s.status') AS flow_60s_status,
    json_extract(fs.quality_json, '$.funding_window.status') AS funding_window_status,
    json_extract(fs.quality_json, '$.oi_baseline.status') AS oi_baseline_status,
    json_extract(fs.quality_json, '$.cvd_divergence.status') AS cvd_divergence_status,
    json_extract(ms.source_meta_json, '$.aggtrade_15m.source') AS aggtrade_15m_source,
    json_extract(ms.source_meta_json, '$.aggtrade_60s.source') AS aggtrade_60s_source,
    json_extract(ms.source_meta_json, '$.ws_last_message_at') AS ws_last_message_at
FROM feature_snapshots fs
JOIN market_snapshots ms
  ON ms.snapshot_id = fs.snapshot_id
LEFT JOIN decision_links dl
  ON dl.feature_snapshot_id = fs.feature_snapshot_id
 AND dl.snapshot_id = fs.snapshot_id
WHERE fs.cycle_timestamp >= '2026-04-25T00:30:00+00:00'
  AND fs.cycle_timestamp < '2026-04-25T00:45:00+00:00'
ORDER BY fs.cycle_timestamp, fs.feature_snapshot_id;

SELECT 'Q6B: lineage breaks in the post-fix counting window' AS query_name;
WITH decision_links AS (
    SELECT
        feature_snapshot_id,
        snapshot_id,
        substr(cycle_timestamp, 1, 16) AS bucket_15m,
        COUNT(*) AS decision_outcome_count
    FROM decision_outcomes
    GROUP BY feature_snapshot_id, snapshot_id, substr(cycle_timestamp, 1, 16)
)
SELECT
    fs.cycle_timestamp,
    fs.feature_snapshot_id,
    fs.snapshot_id AS feature_snapshot_parent_id,
    ms.snapshot_id AS market_snapshot_id,
    dl.decision_outcome_count,
    ms.snapshot_build_started_at,
    ms.snapshot_build_finished_at
FROM feature_snapshots fs
JOIN market_snapshots ms
  ON ms.snapshot_id = fs.snapshot_id
LEFT JOIN decision_links dl
  ON dl.feature_snapshot_id = fs.feature_snapshot_id
 AND dl.snapshot_id = fs.snapshot_id
WHERE fs.cycle_timestamp >= '2026-04-25T00:45:00+00:00'
  AND (
        dl.decision_outcome_count IS NULL
     OR substr(ms.cycle_timestamp, 1, 16) <> substr(fs.cycle_timestamp, 1, 16)
     OR dl.bucket_15m <> substr(fs.cycle_timestamp, 1, 16)
  )
ORDER BY fs.cycle_timestamp, fs.feature_snapshot_id;

SELECT 'Q6C: post-fix buckets with full lineage but zero quality-ready rows' AS query_name;
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
per_bucket AS (
    SELECT
        bucket_15m,
        MAX(has_full_lineage) AS has_full_lineage,
        MAX(CASE WHEN has_full_lineage = 1 AND all_five_ready = 1 THEN 1 ELSE 0 END) AS is_quality_ready
    FROM per_row
    GROUP BY bucket_15m
)
SELECT
    bucket_15m
FROM per_bucket
WHERE has_full_lineage = 1
  AND is_quality_ready = 0
ORDER BY bucket_15m;
