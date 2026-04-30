#!/usr/bin/env python3
"""Diagnose flow_window_rest_limit_clipped degradation timeline"""
import sqlite3
from pathlib import Path

db_path = Path('/home/btc-bot/btc-bot/storage/btc_bot.db')
conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
conn.row_factory = sqlite3.Row

# First occurrence of clipping
query_first = """
SELECT
    substr(fs.cycle_timestamp, 1, 19) as cycle_time,
    json_extract(fs.quality_json, '$.flow_15m.status') as flow_15m_status,
    json_extract(fs.quality_json, '$.flow_15m.reason') as flow_15m_reason,
    json_extract(fs.quality_json, '$.flow_60s.status') as flow_60s_status,
    json_extract(fs.quality_json, '$.flow_60s.reason') as flow_60s_reason
FROM feature_snapshots fs
WHERE fs.cycle_timestamp >= '2026-04-27T00:00:00'
  AND (json_extract(fs.quality_json, '$.flow_15m.reason') LIKE '%clipped%'
    OR json_extract(fs.quality_json, '$.flow_60s.reason') LIKE '%clipped%')
ORDER BY fs.cycle_timestamp
LIMIT 10
"""

print("=== FIRST 10 BUCKETS WITH FLOW CLIPPING ===")
rows = conn.execute(query_first).fetchall()
for row in rows:
    f15 = f"{row['flow_15m_status']}({row['flow_15m_reason']})"
    f60 = f"{row['flow_60s_status']}({row['flow_60s_reason']})"
    print(f"{row['cycle_time']}: flow_15m={f15}, flow_60s={f60}")

# Count by hour
query_hourly = """
SELECT
    substr(fs.cycle_timestamp, 1, 13) || ':00' as hour,
    COUNT(*) as total_buckets,
    SUM(CASE WHEN json_extract(fs.quality_json, '$.flow_15m.reason') LIKE '%clipped%'
             THEN 1 ELSE 0 END) as flow_15m_clipped,
    SUM(CASE WHEN json_extract(fs.quality_json, '$.flow_60s.reason') LIKE '%clipped%'
             THEN 1 ELSE 0 END) as flow_60s_clipped
FROM feature_snapshots fs
WHERE fs.cycle_timestamp >= '2026-04-27T00:00:00'
GROUP BY substr(fs.cycle_timestamp, 1, 13)
HAVING flow_15m_clipped > 0 OR flow_60s_clipped > 0
ORDER BY hour
LIMIT 20
"""

print("\n=== CLIPPING FREQUENCY BY HOUR ===")
rows = conn.execute(query_hourly).fetchall()
for row in rows:
    print(f"{row['hour']}: {row['flow_15m_clipped']}/4 flow_15m, {row['flow_60s_clipped']}/4 flow_60s (total {row['total_buckets']} buckets)")

conn.close()
