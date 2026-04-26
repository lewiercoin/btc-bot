-- Gate A / timing-staleness query pack
-- Scope: post-fix window only, read-only execution against production SQLite
-- Window start: 2026-04-25 00:45 UTC (first post-fix quality-ready bucket)
-- Selection rule: one canonical row per 15m bucket
-- Canonical row priority:
--   1. full lineage
--   2. all five quality keys = ready
--   3. latest captured_at
--   4. latest feature_snapshot_id
--
-- How to run:
--   sqlite3 -readonly storage/btc_bot.db < scripts/audit_queries/gate_a_timing_staleness.sql

SELECT 'T1A: cycle vs snapshot build timing summary' AS query_name;
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
        fs.cycle_timestamp,
        fs.captured_at AS feature_captured_at,
        ms.snapshot_id,
        ms.captured_at AS snapshot_captured_at,
        ms.snapshot_build_started_at,
        ms.snapshot_build_finished_at,
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
    SELECT
        bucket_15m,
        cycle_timestamp,
        snapshot_build_started_at,
        snapshot_build_finished_at,
        snapshot_captured_at,
        has_full_lineage,
        all_five_ready,
        ROUND((julianday(snapshot_build_finished_at) - julianday(snapshot_build_started_at)) * 86400.0, 3) AS build_duration_seconds,
        ROUND((julianday(snapshot_build_started_at) - julianday(cycle_timestamp)) * 86400.0, 3) AS cycle_to_build_start_seconds,
        ROUND((julianday(snapshot_build_finished_at) - julianday(cycle_timestamp)) * 86400.0, 3) AS cycle_to_build_finish_seconds,
        ROUND((julianday(snapshot_captured_at) - julianday(snapshot_build_finished_at)) * 86400.0, 3) AS build_finish_to_capture_seconds
    FROM ranked_rows
    WHERE bucket_rank = 1
)
SELECT
    COUNT(*) AS canonical_bucket_count,
    SUM(CASE WHEN build_duration_seconds < 0 THEN 1 ELSE 0 END) AS negative_build_duration_count,
    SUM(CASE WHEN cycle_to_build_finish_seconds < 0 THEN 1 ELSE 0 END) AS build_finished_before_cycle_count,
    ROUND(MAX(build_duration_seconds), 3) AS max_build_duration_seconds,
    ROUND(AVG(build_duration_seconds), 3) AS avg_build_duration_seconds,
    ROUND(MAX(cycle_to_build_finish_seconds), 3) AS max_cycle_to_build_finish_seconds,
    ROUND(AVG(cycle_to_build_finish_seconds), 3) AS avg_cycle_to_build_finish_seconds,
    ROUND(MAX(build_finish_to_capture_seconds), 3) AS max_build_finish_to_capture_seconds,
    ROUND(AVG(build_finish_to_capture_seconds), 3) AS avg_build_finish_to_capture_seconds
FROM canonical_rows;

SELECT 'T1B: build timing anomalies in canonical post-fix buckets' AS query_name;
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
        fs.cycle_timestamp,
        ms.snapshot_id,
        ms.captured_at AS snapshot_captured_at,
        ms.snapshot_build_started_at,
        ms.snapshot_build_finished_at,
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
    SELECT
        bucket_15m,
        cycle_timestamp,
        snapshot_id,
        feature_snapshot_id,
        snapshot_build_started_at,
        snapshot_build_finished_at,
        ROUND((julianday(snapshot_build_finished_at) - julianday(snapshot_build_started_at)) * 86400.0, 3) AS build_duration_seconds,
        ROUND((julianday(snapshot_build_finished_at) - julianday(cycle_timestamp)) * 86400.0, 3) AS cycle_to_build_finish_seconds
    FROM ranked_rows
    WHERE bucket_rank = 1
)
SELECT
    bucket_15m,
    cycle_timestamp,
    snapshot_id,
    feature_snapshot_id,
    snapshot_build_started_at,
    snapshot_build_finished_at,
    build_duration_seconds,
    cycle_to_build_finish_seconds
FROM canonical_rows
WHERE build_duration_seconds < 0
   OR cycle_to_build_finish_seconds < 0
ORDER BY bucket_15m;

SELECT 'T1C: build timing distribution (p50/p95/max seconds)' AS query_name;
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
        fs.cycle_timestamp,
        ms.captured_at AS snapshot_captured_at,
        ms.snapshot_build_started_at,
        ms.snapshot_build_finished_at,
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
    SELECT
        ROUND((julianday(snapshot_build_finished_at) - julianday(snapshot_build_started_at)) * 86400.0, 3) AS build_duration_seconds,
        ROUND((julianday(snapshot_captured_at) - julianday(snapshot_build_finished_at)) * 86400.0, 3) AS capture_lag_seconds
    FROM ranked_rows
    WHERE bucket_rank = 1
      AND snapshot_build_started_at IS NOT NULL
      AND snapshot_build_finished_at IS NOT NULL
),
metrics AS (
    SELECT 'build_duration_seconds' AS metric_name, build_duration_seconds AS metric_value FROM canonical_rows
    UNION ALL
    SELECT 'capture_lag_seconds', capture_lag_seconds FROM canonical_rows
),
ordered AS (
    SELECT
        metric_name,
        metric_value,
        ROW_NUMBER() OVER (PARTITION BY metric_name ORDER BY metric_value) AS rn,
        COUNT(*) OVER (PARTITION BY metric_name) AS cnt
    FROM metrics
),
positions AS (
    SELECT
        metric_name,
        metric_value,
        rn,
        cnt,
        CAST((cnt + 1) / 2 AS INTEGER) AS median_pos_lo,
        CAST((cnt + 2) / 2 AS INTEGER) AS median_pos_hi,
        CAST(((cnt * 95) + 99) / 100 AS INTEGER) AS p95_pos
    FROM ordered
)
SELECT
    metric_name,
    MAX(cnt) AS sample_count,
    ROUND(AVG(CASE WHEN rn IN (median_pos_lo, median_pos_hi) THEN metric_value END), 3) AS p50_seconds,
    ROUND(MAX(CASE WHEN rn = p95_pos THEN metric_value END), 3) AS p95_seconds,
    ROUND(MAX(metric_value), 3) AS max_seconds
FROM positions
GROUP BY metric_name
ORDER BY metric_name;

SELECT 'T2: exchange timestamps vs cycle bucket alignment summary' AS query_name;
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
        fs.cycle_timestamp,
        ms.captured_at AS snapshot_captured_at,
        ms.candles_15m_exchange_ts,
        ms.candles_1h_exchange_ts,
        ms.candles_4h_exchange_ts,
        ms.funding_exchange_ts,
        ms.oi_exchange_ts,
        ms.aggtrades_exchange_ts,
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
    SELECT * FROM ranked_rows WHERE bucket_rank = 1
),
alignment_checks AS (
    SELECT
        'candles_15m' AS input_name,
        cycle_timestamp,
        candles_15m_exchange_ts AS exchange_ts,
        CASE WHEN candles_15m_exchange_ts IS NULL THEN 1 ELSE 0 END AS is_null,
        CASE
            WHEN candles_15m_exchange_ts IS NOT NULL
             AND julianday(candles_15m_exchange_ts) > julianday(cycle_timestamp)
            THEN 1 ELSE 0
        END AS is_future,
        CASE
            WHEN candles_15m_exchange_ts IS NOT NULL
             AND strftime('%Y-%m-%dT%H:%M', candles_15m_exchange_ts) = strftime('%Y-%m-%dT%H:%M', cycle_timestamp)
            THEN 1 ELSE 0
        END AS is_bucket_aligned
    FROM canonical_rows
    UNION ALL
    SELECT
        'candles_1h', cycle_timestamp, candles_1h_exchange_ts,
        CASE WHEN candles_1h_exchange_ts IS NULL THEN 1 ELSE 0 END,
        CASE WHEN candles_1h_exchange_ts IS NOT NULL AND julianday(candles_1h_exchange_ts) > julianday(cycle_timestamp) THEN 1 ELSE 0 END,
        CASE
            WHEN candles_1h_exchange_ts IS NOT NULL
             AND strftime('%Y-%m-%dT%H:00', candles_1h_exchange_ts) = strftime('%Y-%m-%dT%H:00', cycle_timestamp)
            THEN 1 ELSE 0
        END
    FROM canonical_rows
    UNION ALL
    SELECT
        'candles_4h', cycle_timestamp, candles_4h_exchange_ts,
        CASE WHEN candles_4h_exchange_ts IS NULL THEN 1 ELSE 0 END,
        CASE WHEN candles_4h_exchange_ts IS NOT NULL AND julianday(candles_4h_exchange_ts) > julianday(cycle_timestamp) THEN 1 ELSE 0 END,
        CASE
            WHEN candles_4h_exchange_ts IS NOT NULL
             AND strftime('%Y-%m-%d', candles_4h_exchange_ts) = strftime('%Y-%m-%d', cycle_timestamp)
             AND CAST(strftime('%H', candles_4h_exchange_ts) AS INTEGER) / 4 = CAST(strftime('%H', cycle_timestamp) AS INTEGER) / 4
            THEN 1 ELSE 0
        END
    FROM canonical_rows
    UNION ALL
    SELECT
        'funding', cycle_timestamp, funding_exchange_ts,
        CASE WHEN funding_exchange_ts IS NULL THEN 1 ELSE 0 END,
        CASE WHEN funding_exchange_ts IS NOT NULL AND julianday(funding_exchange_ts) > julianday(cycle_timestamp) THEN 1 ELSE 0 END,
        CASE WHEN funding_exchange_ts IS NOT NULL AND julianday(funding_exchange_ts) <= julianday(cycle_timestamp) THEN 1 ELSE 0 END
    FROM canonical_rows
    UNION ALL
    SELECT
        'oi', cycle_timestamp, oi_exchange_ts,
        CASE WHEN oi_exchange_ts IS NULL THEN 1 ELSE 0 END,
        CASE WHEN oi_exchange_ts IS NOT NULL AND julianday(oi_exchange_ts) > julianday(cycle_timestamp) THEN 1 ELSE 0 END,
        CASE WHEN oi_exchange_ts IS NOT NULL AND julianday(oi_exchange_ts) <= julianday(cycle_timestamp) THEN 1 ELSE 0 END
    FROM canonical_rows
    UNION ALL
    SELECT
        'aggtrade', cycle_timestamp, aggtrades_exchange_ts,
        CASE WHEN aggtrades_exchange_ts IS NULL THEN 1 ELSE 0 END,
        CASE WHEN aggtrades_exchange_ts IS NOT NULL AND julianday(aggtrades_exchange_ts) > julianday(cycle_timestamp) THEN 1 ELSE 0 END,
        CASE WHEN aggtrades_exchange_ts IS NOT NULL AND julianday(aggtrades_exchange_ts) <= julianday(cycle_timestamp) THEN 1 ELSE 0 END
    FROM canonical_rows
)
SELECT
    input_name,
    COUNT(*) AS canonical_bucket_count,
    SUM(is_null) AS null_exchange_ts_count,
    SUM(is_future) AS future_timestamp_count,
    SUM(CASE WHEN is_null = 0 AND is_bucket_aligned = 1 THEN 1 ELSE 0 END) AS aligned_count,
    SUM(CASE WHEN is_null = 0 AND is_bucket_aligned = 0 THEN 1 ELSE 0 END) AS misaligned_count
FROM alignment_checks
GROUP BY input_name
ORDER BY input_name;

SELECT 'T3: staleness per input summary (seconds)' AS query_name;
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
        fs.cycle_timestamp,
        ms.captured_at AS snapshot_captured_at,
        ms.candles_15m_exchange_ts,
        ms.candles_1h_exchange_ts,
        ms.candles_4h_exchange_ts,
        ms.funding_exchange_ts,
        ms.oi_exchange_ts,
        ms.aggtrades_exchange_ts,
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
    SELECT * FROM ranked_rows WHERE bucket_rank = 1
),
staleness_rows AS (
    SELECT 'candles_15m' AS input_name, bucket_15m, cycle_timestamp, candles_15m_exchange_ts AS exchange_ts,
           ROUND((julianday(cycle_timestamp) - julianday(candles_15m_exchange_ts)) * 86400.0, 3) AS stale_seconds
    FROM canonical_rows
    UNION ALL
    SELECT 'candles_1h', bucket_15m, cycle_timestamp, candles_1h_exchange_ts,
           ROUND((julianday(cycle_timestamp) - julianday(candles_1h_exchange_ts)) * 86400.0, 3)
    FROM canonical_rows
    UNION ALL
    SELECT 'candles_4h', bucket_15m, cycle_timestamp, candles_4h_exchange_ts,
           ROUND((julianday(cycle_timestamp) - julianday(candles_4h_exchange_ts)) * 86400.0, 3)
    FROM canonical_rows
    UNION ALL
    SELECT 'funding', bucket_15m, cycle_timestamp, funding_exchange_ts,
           ROUND((julianday(cycle_timestamp) - julianday(funding_exchange_ts)) * 86400.0, 3)
    FROM canonical_rows
    UNION ALL
    SELECT 'oi', bucket_15m, cycle_timestamp, oi_exchange_ts,
           ROUND((julianday(cycle_timestamp) - julianday(oi_exchange_ts)) * 86400.0, 3)
    FROM canonical_rows
    UNION ALL
    SELECT 'aggtrade', bucket_15m, cycle_timestamp, aggtrades_exchange_ts,
           ROUND((julianday(cycle_timestamp) - julianday(aggtrades_exchange_ts)) * 86400.0, 3)
    FROM canonical_rows
)
SELECT
    input_name,
    COUNT(*) AS canonical_bucket_count,
    SUM(CASE WHEN exchange_ts IS NULL THEN 1 ELSE 0 END) AS null_exchange_ts_count,
    SUM(CASE WHEN exchange_ts IS NOT NULL AND stale_seconds < 0 THEN 1 ELSE 0 END) AS future_timestamp_count,
    ROUND(MAX(CASE WHEN exchange_ts IS NOT NULL THEN stale_seconds END), 3) AS max_stale_seconds,
    ROUND(AVG(CASE WHEN exchange_ts IS NOT NULL THEN stale_seconds END), 3) AS avg_stale_seconds
FROM staleness_rows
GROUP BY input_name
ORDER BY input_name;

SELECT 'T4: staleness distribution by input (p50/p95/max seconds)' AS query_name;
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
        fs.cycle_timestamp,
        ms.captured_at AS snapshot_captured_at,
        ms.candles_15m_exchange_ts,
        ms.candles_1h_exchange_ts,
        ms.candles_4h_exchange_ts,
        ms.funding_exchange_ts,
        ms.oi_exchange_ts,
        ms.aggtrades_exchange_ts,
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
    SELECT * FROM ranked_rows WHERE bucket_rank = 1
),
staleness_rows AS (
    SELECT 'candles_15m' AS input_name, ROUND((julianday(cycle_timestamp) - julianday(candles_15m_exchange_ts)) * 86400.0, 3) AS stale_seconds
    FROM canonical_rows
    WHERE candles_15m_exchange_ts IS NOT NULL
    UNION ALL
    SELECT 'candles_1h', ROUND((julianday(cycle_timestamp) - julianday(candles_1h_exchange_ts)) * 86400.0, 3)
    FROM canonical_rows
    WHERE candles_1h_exchange_ts IS NOT NULL
    UNION ALL
    SELECT 'candles_4h', ROUND((julianday(cycle_timestamp) - julianday(candles_4h_exchange_ts)) * 86400.0, 3)
    FROM canonical_rows
    WHERE candles_4h_exchange_ts IS NOT NULL
    UNION ALL
    SELECT 'funding', ROUND((julianday(cycle_timestamp) - julianday(funding_exchange_ts)) * 86400.0, 3)
    FROM canonical_rows
    WHERE funding_exchange_ts IS NOT NULL
    UNION ALL
    SELECT 'oi', ROUND((julianday(cycle_timestamp) - julianday(oi_exchange_ts)) * 86400.0, 3)
    FROM canonical_rows
    WHERE oi_exchange_ts IS NOT NULL
    UNION ALL
    SELECT 'aggtrade', ROUND((julianday(cycle_timestamp) - julianday(aggtrades_exchange_ts)) * 86400.0, 3)
    FROM canonical_rows
    WHERE aggtrades_exchange_ts IS NOT NULL
),
ordered AS (
    SELECT
        input_name,
        stale_seconds,
        ROW_NUMBER() OVER (PARTITION BY input_name ORDER BY stale_seconds) AS rn,
        COUNT(*) OVER (PARTITION BY input_name) AS cnt
    FROM staleness_rows
),
positions AS (
    SELECT
        input_name,
        stale_seconds,
        rn,
        cnt,
        CAST((cnt + 1) / 2 AS INTEGER) AS median_pos_lo,
        CAST((cnt + 2) / 2 AS INTEGER) AS median_pos_hi,
        CAST(((cnt * 95) + 99) / 100 AS INTEGER) AS p95_pos
    FROM ordered
)
SELECT
    input_name,
    MAX(cnt) AS sample_count,
    ROUND(AVG(CASE WHEN rn IN (median_pos_lo, median_pos_hi) THEN stale_seconds END), 3) AS p50_stale_seconds,
    ROUND(MAX(CASE WHEN rn = p95_pos THEN stale_seconds END), 3) AS p95_stale_seconds,
    ROUND(MAX(stale_seconds), 3) AS max_stale_seconds
FROM positions
GROUP BY input_name
ORDER BY input_name;

SELECT 'T5: WS vs REST aggtrade staleness comparison' AS query_name;
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
        fs.cycle_timestamp,
        ms.captured_at AS snapshot_captured_at,
        ms.aggtrades_exchange_ts,
        COALESCE(json_extract(ms.source_meta_json, '$.aggtrade_15m.source'), 'missing') AS aggtrade_15m_source,
        COALESCE(json_extract(ms.source_meta_json, '$.aggtrade_60s.source'), 'missing') AS aggtrade_60s_source,
        json_extract(ms.source_meta_json, '$.ws_last_message_at') AS ws_last_message_at,
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
    SELECT
        bucket_15m,
        cycle_timestamp,
        aggtrades_exchange_ts,
        aggtrade_15m_source,
        aggtrade_60s_source,
        CASE WHEN ws_last_message_at IS NOT NULL THEN 1 ELSE 0 END AS has_ws_last_message,
        ROUND((julianday(cycle_timestamp) - julianday(aggtrades_exchange_ts)) * 86400.0, 3) AS aggtrade_stale_seconds
    FROM ranked_rows
    WHERE bucket_rank = 1
),
source_rows AS (
    SELECT
        CASE
            WHEN aggtrade_15m_source = 'ws' OR aggtrade_60s_source = 'ws' THEN 'ws'
            WHEN aggtrade_15m_source = 'rest' OR aggtrade_60s_source = 'rest' THEN 'rest'
            ELSE 'missing'
        END AS source_group,
        has_ws_last_message,
        aggtrade_stale_seconds
    FROM canonical_rows
    WHERE aggtrades_exchange_ts IS NOT NULL
),
ordered AS (
    SELECT
        source_group,
        has_ws_last_message,
        aggtrade_stale_seconds,
        ROW_NUMBER() OVER (PARTITION BY source_group ORDER BY aggtrade_stale_seconds) AS rn,
        COUNT(*) OVER (PARTITION BY source_group) AS cnt
    FROM source_rows
),
positions AS (
    SELECT
        source_group,
        has_ws_last_message,
        aggtrade_stale_seconds,
        rn,
        cnt,
        CAST((cnt + 1) / 2 AS INTEGER) AS median_pos_lo,
        CAST((cnt + 2) / 2 AS INTEGER) AS median_pos_hi,
        CAST(((cnt * 95) + 99) / 100 AS INTEGER) AS p95_pos
    FROM ordered
)
SELECT
    source_group,
    MAX(cnt) AS sample_count,
    SUM(has_ws_last_message) AS rows_with_ws_last_message,
    ROUND(AVG(CASE WHEN rn IN (median_pos_lo, median_pos_hi) THEN aggtrade_stale_seconds END), 3) AS p50_aggtrade_stale_seconds,
    ROUND(MAX(CASE WHEN rn = p95_pos THEN aggtrade_stale_seconds END), 3) AS p95_aggtrade_stale_seconds,
    ROUND(MAX(aggtrade_stale_seconds), 3) AS max_aggtrade_stale_seconds
FROM positions
GROUP BY source_group
ORDER BY source_group;

SELECT 'T6A: null or missing timestamp summary in canonical post-fix buckets' AS query_name;
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
        fs.cycle_timestamp,
        ms.captured_at AS snapshot_captured_at,
        ms.snapshot_build_started_at,
        ms.snapshot_build_finished_at,
        ms.candles_15m_exchange_ts,
        ms.candles_1h_exchange_ts,
        ms.candles_4h_exchange_ts,
        ms.funding_exchange_ts,
        ms.oi_exchange_ts,
        ms.aggtrades_exchange_ts,
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
    SELECT * FROM ranked_rows WHERE bucket_rank = 1
),
null_checks AS (
    SELECT 'snapshot_build_started_at' AS field_name, snapshot_build_started_at AS ts_value FROM canonical_rows
    UNION ALL SELECT 'snapshot_build_finished_at', snapshot_build_finished_at FROM canonical_rows
    UNION ALL SELECT 'candles_15m_exchange_ts', candles_15m_exchange_ts FROM canonical_rows
    UNION ALL SELECT 'candles_1h_exchange_ts', candles_1h_exchange_ts FROM canonical_rows
    UNION ALL SELECT 'candles_4h_exchange_ts', candles_4h_exchange_ts FROM canonical_rows
    UNION ALL SELECT 'funding_exchange_ts', funding_exchange_ts FROM canonical_rows
    UNION ALL SELECT 'oi_exchange_ts', oi_exchange_ts FROM canonical_rows
    UNION ALL SELECT 'aggtrades_exchange_ts', aggtrades_exchange_ts FROM canonical_rows
)
SELECT
    field_name,
    COUNT(*) AS canonical_bucket_count,
    SUM(CASE WHEN ts_value IS NULL THEN 1 ELSE 0 END) AS null_count
FROM null_checks
GROUP BY field_name
ORDER BY field_name;

SELECT 'T6B: canonical buckets with missing timestamps' AS query_name;
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
        fs.cycle_timestamp,
        ms.snapshot_id,
        ms.captured_at AS snapshot_captured_at,
        ms.snapshot_build_started_at,
        ms.snapshot_build_finished_at,
        ms.candles_15m_exchange_ts,
        ms.candles_1h_exchange_ts,
        ms.candles_4h_exchange_ts,
        ms.funding_exchange_ts,
        ms.oi_exchange_ts,
        ms.aggtrades_exchange_ts,
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
    SELECT * FROM ranked_rows WHERE bucket_rank = 1
)
SELECT
    bucket_15m,
    cycle_timestamp,
    snapshot_id,
    feature_snapshot_id,
    snapshot_build_started_at,
    snapshot_build_finished_at,
    candles_15m_exchange_ts,
    candles_1h_exchange_ts,
    candles_4h_exchange_ts,
    funding_exchange_ts,
    oi_exchange_ts,
    aggtrades_exchange_ts
FROM canonical_rows
WHERE snapshot_build_started_at IS NULL
   OR snapshot_build_finished_at IS NULL
   OR candles_15m_exchange_ts IS NULL
   OR candles_1h_exchange_ts IS NULL
   OR candles_4h_exchange_ts IS NULL
   OR funding_exchange_ts IS NULL
   OR oi_exchange_ts IS NULL
   OR aggtrades_exchange_ts IS NULL
ORDER BY bucket_15m;
