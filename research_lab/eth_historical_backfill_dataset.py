#!/usr/bin/env python3
"""Full ETH historical dataset backfill with resumable daily checkpoints."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from research_lab.eth_historical_backfill_pilot import (
    DEFAULT_REPORT,
    FULL_BACKFILL_END,
    FULL_BACKFILL_START,
    SYMBOL,
    DayStats,
    _date_range,
    ensure_disk_available,
    init_pilot_db,
    process_day,
    quality_metrics,
    table_counts,
)
from data.rest_client import BinanceFuturesRestClient, RestClientConfig
from settings import load_settings


DEFAULT_DB = Path("research_lab/snapshots/ethusdt_2022_2026_dataset_v1.db")
REPORT_PATH = Path("docs/analysis/ETH_HISTORICAL_BACKFILL_DATASET_2026-05-18.md")


def init_dataset_tables(conn: sqlite3.Connection) -> None:
    init_pilot_db(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS backfill_checkpoints (
            day TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            klines_15m INTEGER NOT NULL DEFAULT 0,
            klines_4h INTEGER NOT NULL DEFAULT 0,
            funding INTEGER NOT NULL DEFAULT 0,
            open_interest INTEGER NOT NULL DEFAULT 0,
            aggtrade_rows INTEGER NOT NULL DEFAULT 0,
            aggtrade_buckets_60s INTEGER NOT NULL DEFAULT 0,
            aggtrade_buckets_15m INTEGER NOT NULL DEFAULT 0,
            downloaded_bytes INTEGER NOT NULL DEFAULT 0,
            errors_json TEXT NOT NULL DEFAULT '[]'
        );
        """
    )
    conn.commit()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def checkpoint_status(conn: sqlite3.Connection, day: date) -> str | None:
    row = conn.execute("SELECT status FROM backfill_checkpoints WHERE day = ?", (day.isoformat(),)).fetchone()
    return str(row[0]) if row else None


def mark_started(conn: sqlite3.Connection, day: date) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO backfill_checkpoints(day, status, started_at, errors_json)
        VALUES (?, 'RUNNING', ?, '[]')
        """,
        (day.isoformat(), _now_iso()),
    )
    conn.commit()


def mark_finished(conn: sqlite3.Connection, stats: DayStats) -> None:
    status = "FAILED" if stats.errors else "DONE"
    conn.execute(
        """
        UPDATE backfill_checkpoints
        SET status = ?, finished_at = ?, klines_15m = ?, klines_4h = ?,
            funding = ?, open_interest = ?, aggtrade_rows = ?,
            aggtrade_buckets_60s = ?, aggtrade_buckets_15m = ?,
            downloaded_bytes = ?, errors_json = ?
        WHERE day = ?
        """,
        (
            status,
            _now_iso(),
            stats.klines_15m,
            stats.klines_4h,
            stats.funding,
            stats.open_interest,
            stats.aggtrade_rows,
            stats.aggtrade_buckets_60s,
            stats.aggtrade_buckets_15m,
            stats.downloaded_bytes,
            json.dumps(list(stats.errors), sort_keys=True),
            stats.day.isoformat(),
        ),
    )
    conn.commit()


def checkpoint_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT status, COUNT(*) count, COALESCE(SUM(downloaded_bytes), 0) downloaded_bytes
        FROM backfill_checkpoints
        GROUP BY status
        """
    ).fetchall()
    summary = {str(row[0]): {"count": int(row[1]), "downloaded_bytes": int(row[2])} for row in rows}
    failed = conn.execute(
        "SELECT day, errors_json FROM backfill_checkpoints WHERE status = 'FAILED' ORDER BY day LIMIT 20"
    ).fetchall()
    summary["failed_days"] = [{"day": row[0], "errors": json.loads(row[1])} for row in failed]
    return summary


def expected_days(start: date, end: date) -> int:
    return max(0, (end - start).days)


def run_dataset_backfill(
    *,
    symbol: str,
    start: date,
    end: date,
    db_path: Path,
    report_path: Path,
    min_free_gb: float,
    max_days: int | None,
    force: bool,
) -> dict[str, Any]:
    from research_lab.eth_historical_backfill_pilot import assert_safe_output_path

    assert_safe_output_path(db_path)
    ensure_disk_available(db_path, min_free_gb)
    if db_path.exists() and force:
        db_path.unlink()
        db_path.with_name(db_path.name + "-wal").unlink(missing_ok=True)
        db_path.with_name(db_path.name + "-shm").unlink(missing_ok=True)

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
    processed = 0
    day_stats: list[DayStats] = []
    try:
        init_dataset_tables(conn)
        for day in _date_range(start, end):
            if max_days is not None and processed >= max_days:
                break
            if checkpoint_status(conn, day) == "DONE":
                continue
            ensure_disk_available(db_path, min_free_gb)
            mark_started(conn, day)
            stats = process_day(conn, client, symbol=symbol, day=day, min_free_gb=min_free_gb, db_path=db_path)
            mark_finished(conn, stats)
            day_stats.append(stats)
            processed += 1
        q = quality_metrics(conn, symbol, start, min(end, _last_completed_exclusive(conn, start)))
        counts = table_counts(conn, symbol)
        checkpoints = checkpoint_summary(conn)
        conn.execute(
            "INSERT OR REPLACE INTO pilot_manifest(key, value) VALUES (?, ?)",
            ("dataset_summary", json.dumps({"quality": q, "checkpoints": checkpoints}, sort_keys=True)),
        )
        conn.commit()
    finally:
        conn.close()

    disk = ensure_disk_available(db_path, min_free_gb)
    payload = {
        "milestone": "ETH_HISTORICAL_BACKFILL_DATASET_V1",
        "symbol": symbol,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "expected_days": expected_days(start, end),
        "processed_this_run": processed,
        "db_path": str(db_path),
        "db_size_mb": db_path.stat().st_size / (1024**2) if db_path.exists() else 0.0,
        "disk_free_gb": disk["free_gb"],
        "min_free_gb": min_free_gb,
        "counts": counts,
        "quality": q,
        "checkpoints": checkpoints,
        "day_stats": [asdict(s) | {"day": s.day.isoformat()} for s in day_stats],
        "complete": int(checkpoints.get("DONE", {}).get("count", 0)) == expected_days(start, end)
        and not checkpoints.get("FAILED", {}).get("count", 0),
    }
    generate_report(payload, report_path)
    return payload


def _last_completed_exclusive(conn: sqlite3.Connection, start: date) -> date:
    row = conn.execute("SELECT MAX(day) FROM backfill_checkpoints WHERE status = 'DONE'").fetchone()
    if not row or not row[0]:
        return start
    return date.fromisoformat(str(row[0])) + timedelta(days=1)


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    q = payload["quality"]
    checkpoints = payload["checkpoints"]
    done = checkpoints.get("DONE", {}).get("count", 0)
    failed = checkpoints.get("FAILED", {}).get("count", 0)
    status = "DATASET_COMPLETE_READY_FOR_AUDIT" if payload["complete"] else "PARTIAL_BACKFILL_IN_PROGRESS"
    lines = [
        "# ETH Historical Backfill Dataset",
        "",
        "**Milestone:** `ETH_HISTORICAL_BACKFILL_DATASET_V1`",
        f"**Status:** `{status}`",
        "**Scope:** Research Lab data-engineering dataset only; separate SQLite snapshot; no runtime DB writes.",
        "",
        "## Progress",
        "",
        f"- Range: {payload['start']} to {payload['end_exclusive']} exclusive",
        f"- Expected days: {payload['expected_days']}",
        f"- Done days: {done}",
        f"- Failed days: {failed}",
        f"- Processed this run: {payload['processed_this_run']}",
        f"- DB path: `{payload['db_path']}`",
        f"- DB size: {payload['db_size_mb']:.2f} MB",
        f"- Free disk: {payload['disk_free_gb']:.2f} GB",
        f"- Disk guard: {payload['min_free_gb']:.1f} GB",
        "",
        "## Rows",
        "",
        "| Dataset | Rows | Expected | Missing Rate |",
        "|---|---:|---:|---:|",
    ]
    for key, count in q.get("counts", {}).items():
        lines.append(f"| `{key}` | {count} | {q['expected'][key]} | {q['missing_rates'][key]:.2%} |")
    lines += [
        "",
        f"- OHLC/zero-volume errors: {q.get('ohlc_errors', 0)}",
        f"- Duplicate groups: {q.get('duplicates', {})}",
        "",
        "## Recent Processed Days",
        "",
        "| Day | 15m | 4h | Funding | OI | AggTrades | 60s Buckets | 15m Buckets | Download MB | Errors |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["day_stats"][-20:]:
        lines.append(
            f"| {row['day']} | {row['klines_15m']} | {row['klines_4h']} | {row['funding']} | "
            f"{row['open_interest']} | {row['aggtrade_rows']} | {row['aggtrade_buckets_60s']} | "
            f"{row['aggtrade_buckets_15m']} | {row['downloaded_bytes'] / (1024**2):.2f} | "
            f"{'; '.join(row['errors']) or '-'} |"
        )
    lines += [
        "",
        "## Failed Days",
        "",
    ]
    if checkpoints.get("failed_days"):
        for item in checkpoints["failed_days"]:
            lines.append(f"- {item['day']}: {item['errors']}")
    else:
        lines.append("- None")
    lines += [
        "",
        "## Audit Questions",
        "",
        "1. Does the dataset live only in `research_lab/snapshots`?",
        "2. Are daily checkpoints resumable and explicit?",
        "3. Did disk guard remain active throughout the run?",
        "4. Are missing rates, duplicates, OHLC errors, and failed days reported?",
        "5. Does the report avoid ETH strategy or runtime approval claims?",
    ]
    report = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default=SYMBOL)
    parser.add_argument("--start-date", default=FULL_BACKFILL_START.isoformat())
    parser.add_argument("--end-date", default=FULL_BACKFILL_END.isoformat(), help="Exclusive end date.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--min-free-gb", type=float, default=12.0)
    parser.add_argument("--max-days", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_dataset_backfill(
        symbol=str(args.symbol).upper(),
        start=date.fromisoformat(args.start_date),
        end=date.fromisoformat(args.end_date),
        db_path=args.db_path,
        report_path=args.report,
        min_free_gb=float(args.min_free_gb),
        max_days=args.max_days,
        force=bool(args.force),
    )
    print(f"complete={payload['complete']}")
    print(f"processed_this_run={payload['processed_this_run']}")
    print(f"db_size_mb={payload['db_size_mb']:.2f}")
    print("git_commit", subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip())


if __name__ == "__main__":
    main()
