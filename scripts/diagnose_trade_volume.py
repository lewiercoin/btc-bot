#!/usr/bin/env python3
"""Check trade volume trend around degradation start"""
import sqlite3
from pathlib import Path

db = Path('/home/btc-bot/btc-bot/storage/btc_bot.db')
conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
conn.row_factory = sqlite3.Row

# Check aggtrade volume trend
query = """
SELECT
    date(bucket_time) as day,
    COUNT(*) as buckets,
    SUM(trade_count) as total_trades,
    AVG(trade_count) as avg_per_bucket,
    MAX(trade_count) as max_per_bucket
FROM aggtrade_buckets
WHERE bucket_time >= '2026-04-20' AND bucket_time < '2026-05-01'
  AND symbol = 'BTCUSDT' AND timeframe = '15m'
GROUP BY date(bucket_time)
ORDER BY day
"""

print("=== TRADE VOLUME TREND (15m buckets) ===")
rows = conn.execute(query).fetchall()
for row in rows:
    day = row[0]
    buckets = row[1]
    total = row[2] if row[2] else 0
    avg = row[3] if row[3] else 0
    max_val = row[4] if row[4] else 0
    print(f"{day}: {buckets:3d} buckets, {total:6d} trades ({avg:.0f} avg, {max_val:4d} max)")

# Check if aggtrade data exists for 2026-04-27+
query_coverage = """
SELECT
    date(bucket_time) as day,
    MIN(bucket_time) as first_bucket,
    MAX(bucket_time) as last_bucket,
    COUNT(*) as bucket_count
FROM aggtrade_buckets
WHERE bucket_time >= '2026-04-17' AND bucket_time < '2026-05-01'
  AND symbol = 'BTCUSDT' AND timeframe = '15m'
GROUP BY date(bucket_time)
ORDER BY day
"""

print("\n=== AGGTRADE BUCKET COVERAGE ===")
rows = conn.execute(query_coverage).fetchall()
for row in rows:
    print(f"{row[0]}: {row[3]:2d} buckets, {row[1]} -> {row[2]}")

conn.close()
