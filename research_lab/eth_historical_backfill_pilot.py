#!/usr/bin/env python3
"""ETH historical backfill pilot with disk guards.

Research Lab-only data engineering pilot. It creates a separate SQLite snapshot
for a short ETHUSDT window, streams Binance Vision ZIP files day-by-day, and
discards raw archives immediately after parsing.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import socket
import shutil
import sqlite3
import subprocess
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from data.rest_client import BinanceFuturesRestClient, RestClientConfig
from settings import load_settings


SYMBOL = "ETHUSDT"
BASE_URL = "https://data.binance.vision/data/futures/um/daily"
DEFAULT_START = date(2026, 5, 15)
DEFAULT_END = date(2026, 5, 18)  # exclusive
DEFAULT_DB = Path("research_lab/snapshots/ethusdt_backfill_pilot_2026-05-15_2026-05-18.db")
DEFAULT_REPORT = Path("docs/analysis/ETH_HISTORICAL_BACKFILL_PILOT_2026-05-18.md")
FULL_BACKFILL_START = date(2022, 1, 1)
FULL_BACKFILL_END = date(2026, 3, 28)


@dataclass(frozen=True)
class DayStats:
    day: date
    klines_15m: int = 0
    klines_4h: int = 0
    funding: int = 0
    open_interest: int = 0
    aggtrade_rows: int = 0
    aggtrade_buckets_60s: int = 0
    aggtrade_buckets_15m: int = 0
    downloaded_bytes: int = 0
    errors: tuple[str, ...] = ()


def _ms_to_utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _to_ms(value: datetime) -> int:
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def _date_range(start: date, end_exclusive: date) -> Iterable[date]:
    current = start
    while current < end_exclusive:
        yield current
        current += timedelta(days=1)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def assert_safe_output_path(path: Path) -> None:
    resolved = path.resolve()
    repo = Path.cwd().resolve()
    expected = (repo / "research_lab" / "snapshots").resolve()
    if expected not in resolved.parents:
        raise SystemExit(f"Refusing to write outside research_lab/snapshots: {resolved}")
    if "storage" in resolved.parts:
        raise SystemExit(f"Refusing to write pilot data under runtime storage path: {resolved}")


def ensure_disk_available(path: Path, min_free_gb: float) -> dict[str, float]:
    target = path.parent if path.suffix else path
    target.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(target)
    free_gb = usage.free / (1024**3)
    if free_gb < min_free_gb:
        raise SystemExit(f"Disk guard blocked pilot: free={free_gb:.2f}GB < required={min_free_gb:.2f}GB at {target}")
    return {
        "total_gb": usage.total / (1024**3),
        "used_gb": usage.used / (1024**3),
        "free_gb": free_gb,
    }


def init_pilot_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode = WAL;
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
        );
        CREATE TABLE IF NOT EXISTS funding (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            funding_time TEXT NOT NULL,
            funding_rate REAL NOT NULL,
            UNIQUE(symbol, funding_time)
        );
        CREATE TABLE IF NOT EXISTS open_interest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            oi_value REAL NOT NULL,
            UNIQUE(symbol, timestamp)
        );
        CREATE TABLE IF NOT EXISTS aggtrade_buckets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            bucket_time TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            taker_buy_volume REAL NOT NULL,
            taker_sell_volume REAL NOT NULL,
            tfi REAL NOT NULL,
            cvd REAL NOT NULL,
            UNIQUE(symbol, timeframe, bucket_time)
        );
        CREATE TABLE IF NOT EXISTS pilot_manifest (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    conn.commit()


def _download_zip(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def _read_zip_csv(zip_bytes: bytes) -> list[list[str]]:
    rows: list[list[str]] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for name in archive.namelist():
            if not name.endswith(".csv"):
                continue
            with archive.open(name) as handle:
                reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8"))
                rows.extend(list(reader))
    return rows


def _is_int_token(value: str) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def parse_klines(zip_bytes: bytes, *, symbol: str, timeframe: str) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for row in _read_zip_csv(zip_bytes):
        if len(row) < 6 or not _is_int_token(row[0]):
            continue
        parsed.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "open_time": _ms_to_utc(int(row[0])),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
        )
    return parsed


def parse_metrics_oi(zip_bytes: bytes, *, symbol: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for name in archive.namelist():
            if not name.endswith(".csv"):
                continue
            with archive.open(name) as handle:
                reader = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8"))
                for record in reader:
                    try:
                        ts = datetime.strptime(record["create_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                        rows.append({"symbol": symbol, "timestamp": ts, "oi_value": float(record["sum_open_interest"])})
                    except (KeyError, ValueError):
                        continue
    return rows


def aggregate_aggtrades(zip_bytes: bytes, *, symbol: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    buckets: dict[tuple[str, datetime], list[float]] = defaultdict(lambda: [0.0, 0.0])
    trade_count = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for name in archive.namelist():
            if not name.endswith(".csv"):
                continue
            with archive.open(name) as handle:
                reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8"))
                for row in reader:
                    if len(row) < 7 or not _is_int_token(row[0]):
                        continue
                    qty = float(row[2])
                    event_time = _ms_to_utc(int(row[5]))
                    is_buyer_maker = str(row[6]).strip().lower() == "true"
                    trade_count += 1
                    for timeframe, seconds in (("60s", 60), ("15m", 900)):
                        bucket_time = _bucket_floor(event_time, seconds)
                        slot = buckets[(timeframe, bucket_time)]
                        if is_buyer_maker:
                            slot[1] += qty
                        else:
                            slot[0] += qty
    rows_60s: list[dict[str, Any]] = []
    rows_15m: list[dict[str, Any]] = []
    for (timeframe, bucket_time), (buy, sell) in buckets.items():
        total = buy + sell
        row = {
            "symbol": symbol,
            "bucket_time": bucket_time,
            "timeframe": timeframe,
            "taker_buy_volume": buy,
            "taker_sell_volume": sell,
            "tfi": 0.0 if total == 0 else (buy - sell) / total,
            "cvd": buy - sell,
        }
        if timeframe == "60s":
            rows_60s.append(row)
        else:
            rows_15m.append(row)
    rows_60s.sort(key=lambda item: item["bucket_time"])
    rows_15m.sort(key=lambda item: item["bucket_time"])
    return rows_60s, rows_15m, trade_count


def _bucket_floor(ts: datetime, seconds: int) -> datetime:
    unix = int(ts.timestamp())
    return datetime.fromtimestamp(unix - (unix % seconds), tz=timezone.utc)


def fetch_funding_day(client: BinanceFuturesRestClient, *, symbol: str, day: date) -> list[dict[str, Any]]:
    start, end = _day_bounds(day)
    return client.fetch_funding_history(symbol, limit=100, start_time_ms=_to_ms(start), end_time_ms=_to_ms(end) - 1)


def upsert_candles(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    conn.executemany(
        """
        INSERT INTO candles(symbol, timeframe, open_time, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, timeframe, open_time) DO UPDATE SET
            open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, volume=excluded.volume
        """,
        [(r["symbol"], r["timeframe"], _iso(r["open_time"]), r["open"], r["high"], r["low"], r["close"], r["volume"]) for r in rows],
    )
    return len(rows)


def upsert_funding(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    conn.executemany(
        """
        INSERT INTO funding(symbol, funding_time, funding_rate)
        VALUES (?, ?, ?)
        ON CONFLICT(symbol, funding_time) DO UPDATE SET funding_rate=excluded.funding_rate
        """,
        [(r["symbol"], _iso(r["funding_time"]), r["funding_rate"]) for r in rows],
    )
    return len(rows)


def upsert_open_interest(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    conn.executemany(
        """
        INSERT INTO open_interest(symbol, timestamp, oi_value)
        VALUES (?, ?, ?)
        ON CONFLICT(symbol, timestamp) DO UPDATE SET oi_value=excluded.oi_value
        """,
        [(r["symbol"], _iso(r["timestamp"]), r["oi_value"]) for r in rows],
    )
    return len(rows)


def upsert_aggtrade_buckets(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    conn.executemany(
        """
        INSERT INTO aggtrade_buckets(symbol, bucket_time, timeframe, taker_buy_volume, taker_sell_volume, tfi, cvd)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, timeframe, bucket_time) DO UPDATE SET
            taker_buy_volume=excluded.taker_buy_volume,
            taker_sell_volume=excluded.taker_sell_volume,
            tfi=excluded.tfi,
            cvd=excluded.cvd
        """,
        [
            (
                r["symbol"],
                _iso(r["bucket_time"]),
                r["timeframe"],
                r["taker_buy_volume"],
                r["taker_sell_volume"],
                r["tfi"],
                r["cvd"],
            )
            for r in rows
        ],
    )
    return len(rows)


def _zip_url(family: str, symbol: str, suffix: str, day: date) -> str:
    stamp = day.isoformat()
    return f"{BASE_URL}/{family}/{symbol}/{suffix}/{symbol}-{suffix}-{stamp}.zip"


def process_day(
    conn: sqlite3.Connection,
    client: BinanceFuturesRestClient,
    *,
    symbol: str,
    day: date,
    min_free_gb: float,
    db_path: Path,
) -> DayStats:
    errors: list[str] = []
    downloaded = 0
    k15: list[dict[str, Any]] = []
    k4h: list[dict[str, Any]] = []
    funding: list[dict[str, Any]] = []
    oi: list[dict[str, Any]] = []
    buckets_60s: list[dict[str, Any]] = []
    buckets_15m: list[dict[str, Any]] = []
    agg_rows = 0

    try:
        ensure_disk_available(db_path, min_free_gb)
        blob = _download_zip(_zip_url("klines", symbol, "15m", day))
        downloaded += len(blob)
        k15 = parse_klines(blob, symbol=symbol, timeframe="15m")
        blob = b""
    except (urllib.error.URLError, zipfile.BadZipFile, ValueError) as exc:
        errors.append(f"15m_klines:{exc}")

    try:
        ensure_disk_available(db_path, min_free_gb)
        blob = _download_zip(_zip_url("klines", symbol, "4h", day))
        downloaded += len(blob)
        k4h = parse_klines(blob, symbol=symbol, timeframe="4h")
        blob = b""
    except (urllib.error.URLError, zipfile.BadZipFile, ValueError) as exc:
        errors.append(f"4h_klines:{exc}")

    try:
        funding = fetch_funding_day(client, symbol=symbol, day=day)
    except Exception as exc:  # noqa: BLE001 - diagnostic report must capture provider failure.
        errors.append(f"funding:{exc}")

    try:
        ensure_disk_available(db_path, min_free_gb)
        blob = _download_zip(f"{BASE_URL}/metrics/{symbol}/{symbol}-metrics-{day.isoformat()}.zip")
        downloaded += len(blob)
        oi = parse_metrics_oi(blob, symbol=symbol)
        blob = b""
    except (urllib.error.URLError, zipfile.BadZipFile, ValueError) as exc:
        errors.append(f"metrics_oi:{exc}")

    try:
        ensure_disk_available(db_path, min_free_gb)
        blob = _download_zip(f"{BASE_URL}/aggTrades/{symbol}/{symbol}-aggTrades-{day.isoformat()}.zip")
        downloaded += len(blob)
        buckets_60s, buckets_15m, agg_rows = aggregate_aggtrades(blob, symbol=symbol)
        blob = b""
    except (urllib.error.URLError, zipfile.BadZipFile, ValueError) as exc:
        errors.append(f"aggtrades:{exc}")

    upsert_candles(conn, k15)
    upsert_candles(conn, k4h)
    upsert_funding(conn, funding)
    upsert_open_interest(conn, oi)
    upsert_aggtrade_buckets(conn, buckets_60s + buckets_15m)
    conn.commit()
    return DayStats(
        day=day,
        klines_15m=len(k15),
        klines_4h=len(k4h),
        funding=len(funding),
        open_interest=len(oi),
        aggtrade_rows=agg_rows,
        aggtrade_buckets_60s=len(buckets_60s),
        aggtrade_buckets_15m=len(buckets_15m),
        downloaded_bytes=downloaded,
        errors=tuple(errors),
    )


def table_counts(conn: sqlite3.Connection, symbol: str) -> dict[str, int]:
    return {
        "candles_15m": conn.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND timeframe='15m'", (symbol,)).fetchone()[0],
        "candles_4h": conn.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND timeframe='4h'", (symbol,)).fetchone()[0],
        "funding": conn.execute("SELECT COUNT(*) FROM funding WHERE symbol=?", (symbol,)).fetchone()[0],
        "open_interest": conn.execute("SELECT COUNT(*) FROM open_interest WHERE symbol=?", (symbol,)).fetchone()[0],
        "aggtrade_60s": conn.execute("SELECT COUNT(*) FROM aggtrade_buckets WHERE symbol=? AND timeframe='60s'", (symbol,)).fetchone()[0],
        "aggtrade_15m": conn.execute("SELECT COUNT(*) FROM aggtrade_buckets WHERE symbol=? AND timeframe='15m'", (symbol,)).fetchone()[0],
    }


def quality_metrics(conn: sqlite3.Connection, symbol: str, start: date, end: date) -> dict[str, Any]:
    days = (end - start).days
    counts = table_counts(conn, symbol)
    expected = {
        "candles_15m": days * 96,
        "candles_4h": days * 6,
        "funding": days * 3,
        "open_interest": days * 288,
        "aggtrade_60s": days * 1440,
        "aggtrade_15m": days * 96,
    }
    ohlc_errors = conn.execute(
        """
        SELECT COUNT(*) FROM candles
        WHERE symbol=? AND (low > open OR open > high OR low > close OR close > high OR low > high OR volume <= 0)
        """,
        (symbol,),
    ).fetchone()[0]
    duplicates = {}
    for table, cols in {
        "candles": "symbol, timeframe, open_time",
        "funding": "symbol, funding_time",
        "open_interest": "symbol, timestamp",
        "aggtrade_buckets": "symbol, timeframe, bucket_time",
    }.items():
        duplicates[table] = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT {cols}, COUNT(*) c FROM {table} GROUP BY {cols} HAVING c > 1)"
        ).fetchone()[0]
    missing_rates = {
        key: max(0, expected[key] - counts.get(key, 0)) / expected[key] if expected[key] else 0.0
        for key in expected
    }
    return {"days": days, "counts": counts, "expected": expected, "missing_rates": missing_rates, "ohlc_errors": ohlc_errors, "duplicates": duplicates}


def run_pilot(
    *,
    symbol: str,
    start: date,
    end: date,
    db_path: Path,
    report_path: Path,
    min_free_gb: float,
    force: bool,
) -> dict[str, Any]:
    assert_safe_output_path(db_path)
    disk_before = ensure_disk_available(db_path, min_free_gb)
    if db_path.exists() and force:
        db_path.unlink()
        wal = db_path.with_name(db_path.name + "-wal")
        shm = db_path.with_name(db_path.name + "-shm")
        wal.unlink(missing_ok=True)
        shm.unlink(missing_ok=True)
    elif db_path.exists() and not force:
        raise SystemExit(f"Output DB already exists: {db_path}. Use --force to replace it.")

    settings = load_settings(profile="research")
    client = BinanceFuturesRestClient(
        RestClientConfig(
            base_url=settings.exchange.futures_rest_base_url,
            timeout_seconds=settings.execution.rest_timeout_seconds,
            max_retries=2,
            retry_backoff_seconds=0.75,
        )
    )
    conn = sqlite3.connect(db_path)
    try:
        init_pilot_db(conn)
        stats = [
            process_day(conn, client, symbol=symbol, day=day, min_free_gb=min_free_gb, db_path=db_path)
            for day in _date_range(start, end)
        ]
        metrics = quality_metrics(conn, symbol, start, end)
        conn.execute("INSERT OR REPLACE INTO pilot_manifest(key, value) VALUES (?, ?)", ("summary", json.dumps(metrics, sort_keys=True)))
        conn.commit()
    finally:
        conn.close()

    disk_after = ensure_disk_available(db_path, min_free_gb)
    db_size_bytes = db_path.stat().st_size if db_path.exists() else 0
    pilot_days = max(1, (end - start).days)
    full_days = (FULL_BACKFILL_END - FULL_BACKFILL_START).days
    estimated_full_db_gb = (db_size_bytes / pilot_days * full_days) / (1024**3)
    payload = {
        "milestone": "ETH_HISTORICAL_BACKFILL_PILOT_V1",
        "hostname": socket.gethostname(),
        "symbol": symbol,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "db_path": str(db_path),
        "db_size_bytes": db_size_bytes,
        "db_size_mb": db_size_bytes / (1024**2),
        "pilot_days": pilot_days,
        "estimated_full_db_gb": estimated_full_db_gb,
        "disk_before": disk_before,
        "disk_after": disk_after,
        "min_free_gb": min_free_gb,
        "day_stats": [s.__dict__ | {"day": s.day.isoformat()} for s in stats],
        "quality": metrics,
    }
    generate_report(payload, report_path)
    return payload


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    q = payload["quality"]
    lines = [
        "# ETH Historical Backfill Pilot",
        "",
        "**Milestone:** `ETH_HISTORICAL_BACKFILL_PILOT_V1`",
        "**Status:** READY_FOR_AUDIT",
        "**Scope:** Research Lab data-engineering pilot only; separate SQLite snapshot; no runtime DB writes.",
        "",
        "## Guardrails",
        "",
        f"- Hostname: `{payload['hostname']}`",
        f"- Output DB: `{payload['db_path']}`",
        f"- Disk guard minimum free space: {payload['min_free_gb']:.1f} GB",
        f"- Free disk before: {payload['disk_before']['free_gb']:.2f} GB",
        f"- Free disk after: {payload['disk_after']['free_gb']:.2f} GB",
        "- Raw ZIP files are streamed in memory per day and discarded after parsing.",
        "- Production `storage/btc_bot.db` and PAPER bot runtime are untouched.",
        "",
        "## Pilot Size",
        "",
        f"- Date range: {payload['start']} to {payload['end_exclusive']} exclusive ({payload['pilot_days']} days)",
        f"- Pilot DB size: {payload['db_size_mb']:.2f} MB",
        f"- Linear full 2022-2026 estimate: {payload['estimated_full_db_gb']:.2f} GB",
        "",
        "## Rows",
        "",
        "| Dataset | Rows | Expected | Missing Rate |",
        "|---|---:|---:|---:|",
    ]
    for key, count in q["counts"].items():
        lines.append(f"| `{key}` | {count} | {q['expected'][key]} | {q['missing_rates'][key]:.2%} |")
    lines += [
        "",
        f"- OHLC/zero-volume errors: {q['ohlc_errors']}",
        f"- Duplicate groups: {q['duplicates']}",
        "",
        "## Per-Day Download",
        "",
        "| Day | 15m | 4h | Funding | OI | AggTrades | 60s Buckets | 15m Buckets | Download MB | Errors |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["day_stats"]:
        lines.append(
            f"| {row['day']} | {row['klines_15m']} | {row['klines_4h']} | {row['funding']} | "
            f"{row['open_interest']} | {row['aggtrade_rows']} | {row['aggtrade_buckets_60s']} | "
            f"{row['aggtrade_buckets_15m']} | {row['downloaded_bytes'] / (1024**2):.2f} | "
            f"{'; '.join(row['errors']) or '-'} |"
        )
    lines += [
        "",
        "## Builder Interpretation",
        "",
        "This pilot validates the mechanics and storage slope for ETHUSDT historical data. It is not an ETH strategy backtest and does not approve multi-asset runtime work.",
        "",
        "## Audit Questions",
        "",
        "1. Did the pilot write only to the separate research snapshot path?",
        "2. Did the disk guard run before writes and preserve enough free space?",
        "3. Were raw archives discarded rather than persisted?",
        "4. Are row counts, missing rates, duplicates, and OHLC errors reported?",
        "5. Does the report avoid approving ETH strategy research or runtime changes?",
    ]
    report = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default=SYMBOL)
    parser.add_argument("--start-date", default=DEFAULT_START.isoformat())
    parser.add_argument("--end-date", default=DEFAULT_END.isoformat(), help="Exclusive end date.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--min-free-gb", type=float, default=12.0)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_pilot(
        symbol=str(args.symbol).upper(),
        start=date.fromisoformat(args.start_date),
        end=date.fromisoformat(args.end_date),
        db_path=args.db_path,
        report_path=args.report,
        min_free_gb=float(args.min_free_gb),
        force=bool(args.force),
    )
    print(Path(payload["db_path"]).as_posix())
    print(f"db_size_mb={payload['db_size_mb']:.2f}")
    print(f"estimated_full_db_gb={payload['estimated_full_db_gb']:.2f}")
    print("git_commit", subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip())


if __name__ == "__main__":
    main()
