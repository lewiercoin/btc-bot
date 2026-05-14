#!/usr/bin/env python3
"""
Backfill BTC 5m candles from Binance Futures API into a local SQLite database.

Usage:
    python -m research_lab.backfill_5m_candles

Source: Binance Futures API /fapi/v1/klines (interval=5m)
Target: research_lab/snapshots/btc_5m_2022_2026.db
Date range: 2022-01-01 to 2026-03-28
Symbol: BTCUSDT

This script is LOCAL RESEARCH ONLY:
- No production server modification
- No PAPER/runtime/settings changes
- No production DB writes

Quality checks performed after backfill:
- Timestamp UTC aligned to 5m boundaries
- No duplicate candles
- Expected 288 bars/day
- OHLC consistency: low <= open/close <= high
- Volume non-negative
- Missing gaps reported
"""

import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# ── Configuration ──────────────────────────────────────────────────────────────

SYMBOL = "BTCUSDT"
INTERVAL = "5m"
START_DATE = datetime(2022, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2026, 3, 28, 23, 55, tzinfo=timezone.utc)
DB_PATH = Path("research_lab/snapshots/btc_5m_2022_2026.db")
BARS_PER_REQUEST = 1500  # Binance max
RATE_LIMIT_SLEEP = 0.25  # seconds between requests
BASE_URL = "https://fapi.binance.com/fapi/v1/klines"

# Fallback range if full range fails
FALLBACK_START = datetime(2024, 1, 1, tzinfo=timezone.utc)


# ── Database ───────────────────────────────────────────────────────────────────

def create_db(db_path: Path) -> sqlite3.Connection:
    """Create SQLite database with candles table matching existing schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            open_time TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            UNIQUE(symbol, timeframe, open_time)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_candles_tf_time 
        ON candles(symbol, timeframe, open_time)
    """)
    conn.commit()
    return conn


def insert_candles(conn: sqlite3.Connection, candles: list[dict]) -> int:
    """Insert candles into database, skip duplicates."""
    inserted = 0
    for c in candles:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO candles 
                   (symbol, timeframe, open_time, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (c["symbol"], c["timeframe"], c["open_time"],
                 c["open"], c["high"], c["low"], c["close"], c["volume"]),
            )
            inserted += conn.total_changes  # approximate
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return inserted


# ── Binance API ────────────────────────────────────────────────────────────────

def fetch_klines(symbol: str, interval: str, start_ms: int, limit: int = 1500) -> list:
    """Fetch klines from Binance Futures API."""
    url = f"{BASE_URL}?symbol={symbol}&interval={interval}&startTime={start_ms}&limit={limit}"
    req = Request(url, headers={"User-Agent": "btc-bot-research/1.0"})
    
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                return data
        except HTTPError as e:
            if e.code == 429:
                wait = min(60, 2 ** (attempt + 2))
                print(f"  Rate limited (429), waiting {wait}s...")
                time.sleep(wait)
            elif e.code == 418:
                print(f"  IP banned (418), waiting 120s...")
                time.sleep(120)
            else:
                print(f"  HTTP error {e.code}: {e.reason}")
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise
        except URLError as e:
            print(f"  URL error: {e.reason}")
            if attempt < 2:
                time.sleep(2)
            else:
                raise
    return []


def parse_kline(raw: list, symbol: str) -> dict:
    """Parse Binance kline array into candle dict."""
    open_time_ms = int(raw[0])
    open_time = datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc)
    return {
        "symbol": symbol,
        "timeframe": "5m",
        "open_time": open_time.isoformat(),
        "open": float(raw[1]),
        "high": float(raw[2]),
        "low": float(raw[3]),
        "close": float(raw[4]),
        "volume": float(raw[5]),
    }


# ── Backfill ───────────────────────────────────────────────────────────────────

def backfill(conn: sqlite3.Connection, symbol: str, start: datetime, end: datetime):
    """Backfill 5m candles from Binance API."""
    current = start
    total_inserted = 0
    request_count = 0
    
    total_days = (end - start).days
    print(f"Backfilling {symbol} 5m candles: {start.date()} to {end.date()} ({total_days} days)")
    print(f"Estimated requests: ~{(total_days * 288) // BARS_PER_REQUEST + 1}")
    
    while current < end:
        start_ms = int(current.timestamp() * 1000)
        
        try:
            klines = fetch_klines(symbol, INTERVAL, start_ms, BARS_PER_REQUEST)
        except Exception as e:
            print(f"\n  FATAL: API error at {current.isoformat()}: {e}")
            print(f"  Inserted {total_inserted} candles so far. Stopping.")
            return total_inserted, current
        
        if not klines:
            print(f"\n  No data returned at {current.isoformat()}, advancing 1 day")
            current += timedelta(days=1)
            continue
        
        candles = [parse_kline(k, symbol) for k in klines]
        
        before = conn.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
        insert_candles(conn, candles)
        after = conn.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
        batch_inserted = after - before
        total_inserted += batch_inserted
        
        last_open_time_ms = int(klines[-1][0])
        last_open_time = datetime.fromtimestamp(last_open_time_ms / 1000, tz=timezone.utc)
        current = last_open_time + timedelta(minutes=5)
        
        request_count += 1
        if request_count % 20 == 0:
            progress_pct = min(100, (current - start).days / max(total_days, 1) * 100)
            print(f"  [{progress_pct:5.1f}%] {current.date()} | {total_inserted} candles | {request_count} requests")
        
        time.sleep(RATE_LIMIT_SLEEP)
    
    print(f"\nBackfill complete: {total_inserted} candles inserted in {request_count} requests")
    return total_inserted, end


# ── Quality Checks ─────────────────────────────────────────────────────────────

def run_quality_checks(conn: sqlite3.Connection, start: datetime, end: datetime) -> dict:
    """Run comprehensive quality checks on backfilled data."""
    results = {}
    
    # 1. Total count
    row = conn.execute("SELECT COUNT(*) FROM candles WHERE timeframe='5m'").fetchone()
    total_count = row[0]
    results["total_bars"] = total_count
    
    # 2. Date range
    row = conn.execute(
        "SELECT MIN(open_time), MAX(open_time) FROM candles WHERE timeframe='5m'"
    ).fetchone()
    results["min_date"] = row[0]
    results["max_date"] = row[1]
    
    # 3. Duplicate check
    row = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT symbol, timeframe, open_time, COUNT(*) as cnt
            FROM candles WHERE timeframe='5m'
            GROUP BY symbol, timeframe, open_time
            HAVING cnt > 1
        )
    """).fetchone()
    results["duplicate_count"] = row[0]
    
    # 4. OHLC consistency: low <= min(open, close) AND high >= max(open, close)
    row = conn.execute("""
        SELECT COUNT(*) FROM candles 
        WHERE timeframe='5m' 
        AND (low > open OR low > close OR high < open OR high < close)
    """).fetchone()
    results["ohlc_violations"] = row[0]
    
    # 5. Negative volume
    row = conn.execute("""
        SELECT COUNT(*) FROM candles 
        WHERE timeframe='5m' AND volume < 0
    """).fetchone()
    results["negative_volume"] = row[0]
    
    # 6. Zero volume (informational)
    row = conn.execute("""
        SELECT COUNT(*) FROM candles 
        WHERE timeframe='5m' AND volume = 0
    """).fetchone()
    results["zero_volume"] = row[0]
    
    # 7. Timestamp alignment check (5m boundaries: minute % 5 == 0)
    row = conn.execute("""
        SELECT COUNT(*) FROM candles 
        WHERE timeframe='5m' 
        AND CAST(strftime('%M', open_time) AS INTEGER) % 5 != 0
    """).fetchone()
    results["misaligned_timestamps"] = row[0]
    
    # 8. Expected vs actual bars per day
    total_days = (end - start).days
    expected_bars = total_days * 288
    results["expected_bars"] = expected_bars
    results["total_days"] = total_days
    results["coverage_pct"] = round(total_count / max(expected_bars, 1) * 100, 2)
    
    # 9. Gap analysis: find days with < 288 bars
    gap_rows = conn.execute("""
        SELECT date(open_time) as day, COUNT(*) as cnt
        FROM candles WHERE timeframe='5m'
        GROUP BY date(open_time)
        HAVING cnt < 280
        ORDER BY day
    """).fetchall()
    results["gap_days"] = [(r[0], r[1]) for r in gap_rows]
    results["gap_day_count"] = len(gap_rows)
    
    # 10. Days with exactly 0 bars (complete gaps)
    all_dates_with_data = set()
    for r in conn.execute("SELECT DISTINCT date(open_time) FROM candles WHERE timeframe='5m'").fetchall():
        all_dates_with_data.add(r[0])
    
    missing_dates = []
    current = start.date()
    end_date = end.date()
    while current <= end_date:
        if str(current) not in all_dates_with_data:
            missing_dates.append(str(current))
        current += timedelta(days=1)
    results["completely_missing_days"] = missing_dates
    results["completely_missing_day_count"] = len(missing_dates)
    
    return results


def print_quality_report(results: dict):
    """Print quality check results."""
    print("\n" + "=" * 60)
    print("5M DATA QUALITY REPORT")
    print("=" * 60)
    
    print(f"\nDate range: {results['min_date']} to {results['max_date']}")
    print(f"Total bars: {results['total_bars']}")
    print(f"Expected bars: {results['expected_bars']} ({results['total_days']} days × 288)")
    print(f"Coverage: {results['coverage_pct']}%")
    
    print(f"\nDuplicates: {results['duplicate_count']}")
    print(f"OHLC violations: {results['ohlc_violations']}")
    print(f"Negative volume: {results['negative_volume']}")
    print(f"Zero volume: {results['zero_volume']}")
    print(f"Misaligned timestamps: {results['misaligned_timestamps']}")
    
    print(f"\nGap days (< 280 bars): {results['gap_day_count']}")
    if results['gap_days']:
        for day, cnt in results['gap_days'][:20]:
            print(f"  {day}: {cnt} bars")
        if len(results['gap_days']) > 20:
            print(f"  ... and {len(results['gap_days']) - 20} more")
    
    print(f"\nCompletely missing days: {results['completely_missing_day_count']}")
    if results['completely_missing_days']:
        for d in results['completely_missing_days'][:20]:
            print(f"  {d}")
        if len(results['completely_missing_days']) > 20:
            print(f"  ... and {len(results['completely_missing_days']) - 20} more")
    
    # Verdict
    critical_failures = []
    if results['duplicate_count'] > 0:
        critical_failures.append(f"duplicates: {results['duplicate_count']}")
    if results['ohlc_violations'] > 0:
        critical_failures.append(f"OHLC violations: {results['ohlc_violations']}")
    if results['negative_volume'] > 0:
        critical_failures.append(f"negative volume: {results['negative_volume']}")
    if results['misaligned_timestamps'] > 0:
        critical_failures.append(f"misaligned timestamps: {results['misaligned_timestamps']}")
    if results['coverage_pct'] < 95.0:
        critical_failures.append(f"coverage below 95%: {results['coverage_pct']}%")
    
    print("\n" + "-" * 60)
    if critical_failures:
        print(f"VERDICT: DATA_QUALITY_FAIL")
        print(f"Critical issues: {', '.join(critical_failures)}")
    else:
        print(f"VERDICT: DATA_QUALITY_PASS")
        print(f"All quality checks passed. Data is suitable for feasibility analysis.")
    print("-" * 60)
    
    return len(critical_failures) == 0


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"Source: Binance Futures API ({BASE_URL})")
    print(f"Symbol: {SYMBOL}")
    print(f"Interval: {INTERVAL}")
    print(f"Target: {DB_PATH}")
    print(f"Range: {START_DATE.date()} to {END_DATE.date()}")
    print()
    
    conn = create_db(DB_PATH)
    
    # Check if already have data
    existing = conn.execute("SELECT COUNT(*) FROM candles WHERE timeframe='5m'").fetchone()[0]
    if existing > 0:
        print(f"Database already contains {existing} 5m candles.")
        row = conn.execute("SELECT MAX(open_time) FROM candles WHERE timeframe='5m'").fetchone()
        last_time = datetime.fromisoformat(row[0])
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        print(f"Last candle: {last_time.isoformat()}")
        print(f"Resuming from {last_time.isoformat()}...")
        resume_start = last_time + timedelta(minutes=5)
    else:
        resume_start = START_DATE
    
    # Backfill
    total_inserted, stopped_at = backfill(conn, SYMBOL, resume_start, END_DATE)
    
    # Quality checks
    quality = run_quality_checks(conn, START_DATE, END_DATE)
    passed = print_quality_report(quality)
    
    conn.close()
    
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
