#!/usr/bin/env python3
"""SOL historical backfill pilot with disk guards.

Research Lab-only data engineering pilot. It creates a separate SQLite snapshot
for a short SOLUSDT window, streams Binance Vision ZIP files day-by-day, and
discards raw archives immediately after parsing.
"""

from __future__ import annotations

import argparse
import json
import socket
import sqlite3
import subprocess
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from data.rest_client import BinanceFuturesRestClient, RestClientConfig
from research_lab.eth_historical_backfill_pilot import (
    DayStats,
    _date_range,
    assert_safe_output_path,
    ensure_disk_available,
    init_pilot_db,
    process_day,
    quality_metrics,
)
from settings import load_settings


SYMBOL = "SOLUSDT"
DEFAULT_START = date(2026, 5, 15)
DEFAULT_END = date(2026, 5, 18)  # exclusive
DEFAULT_DB = Path("research_lab/snapshots/replay-run-sol-backfill-pilot-2026-05-15_2026-05-18.db")
DEFAULT_REPORT = Path("docs/analysis/SOL_HISTORICAL_BACKFILL_PILOT_2026-05-19.md")
DATASET_DB = Path("research_lab/snapshots/replay-run-sol-historical-2022-2026.db")
DATASET_REPORT = Path("docs/analysis/SOL_HISTORICAL_BACKFILL_DATASET_2026-05-19.md")
FULL_BACKFILL_START = date(2022, 1, 1)
FULL_BACKFILL_END = date(2026, 3, 28)


def init_sol_pilot_db(conn: sqlite3.Connection) -> None:
    init_pilot_db(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS backfill_checkpoints (
            day TEXT PRIMARY KEY,
            status TEXT NOT NULL,
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


def mark_checkpoint(conn: sqlite3.Connection, stats: DayStats) -> None:
    status = "FAILED" if stats.errors else "DONE"
    conn.execute(
        """
        INSERT OR REPLACE INTO backfill_checkpoints(
            day, status, klines_15m, klines_4h, funding, open_interest,
            aggtrade_rows, aggtrade_buckets_60s, aggtrade_buckets_15m,
            downloaded_bytes, errors_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stats.day.isoformat(),
            status,
            stats.klines_15m,
            stats.klines_4h,
            stats.funding,
            stats.open_interest,
            stats.aggtrade_rows,
            stats.aggtrade_buckets_60s,
            stats.aggtrade_buckets_15m,
            stats.downloaded_bytes,
            json.dumps(list(stats.errors), sort_keys=True),
        ),
    )
    conn.commit()


def checkpoint_status(conn: sqlite3.Connection, day: date) -> str | None:
    row = conn.execute("SELECT status FROM backfill_checkpoints WHERE day = ?", (day.isoformat(),)).fetchone()
    return str(row[0]) if row else None


def checkpoint_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("SELECT status, COUNT(*) FROM backfill_checkpoints GROUP BY status").fetchall()
    summary = {str(row[0]): int(row[1]) for row in rows}
    failed = conn.execute(
        "SELECT day, errors_json FROM backfill_checkpoints WHERE status='FAILED' ORDER BY day"
    ).fetchall()
    summary["failed_days"] = [{"day": row[0], "errors": json.loads(row[1])} for row in failed]
    return summary


def expected_days(start: date, end: date) -> int:
    return max(0, (end - start).days)


def last_completed_exclusive(conn: sqlite3.Connection, start: date) -> date:
    row = conn.execute("SELECT MAX(day) FROM backfill_checkpoints WHERE status = 'DONE'").fetchone()
    if not row or not row[0]:
        return start
    return date.fromisoformat(str(row[0])) + timedelta(days=1)


def build_client() -> BinanceFuturesRestClient:
    settings = load_settings(profile="research")
    return BinanceFuturesRestClient(
        RestClientConfig(
            base_url=settings.exchange.futures_rest_base_url,
            timeout_seconds=settings.execution.rest_timeout_seconds,
            max_retries=2,
            retry_backoff_seconds=0.75,
        )
    )


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
        db_path.with_name(db_path.name + "-wal").unlink(missing_ok=True)
        db_path.with_name(db_path.name + "-shm").unlink(missing_ok=True)
    elif db_path.exists() and not force:
        raise SystemExit(f"Output DB already exists: {db_path}. Use --force to replace it.")

    client = build_client()
    conn = sqlite3.connect(db_path)
    try:
        init_sol_pilot_db(conn)
        stats: list[DayStats] = []
        for day in _date_range(start, end):
            ensure_disk_available(db_path, min_free_gb)
            day_stats = process_day(conn, client, symbol=symbol, day=day, min_free_gb=min_free_gb, db_path=db_path)
            mark_checkpoint(conn, day_stats)
            stats.append(day_stats)
        metrics = quality_metrics(conn, symbol, start, end)
        checkpoints = checkpoint_summary(conn)
        conn.execute(
            "INSERT OR REPLACE INTO pilot_manifest(key, value) VALUES (?, ?)",
            (
                "summary",
                json.dumps(
                    {
                        "milestone": "SOL_HISTORICAL_BACKFILL_PILOT_V1",
                        "quality": metrics,
                        "checkpoints": checkpoints,
                    },
                    sort_keys=True,
                ),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    disk_after = ensure_disk_available(db_path, min_free_gb)
    db_size_bytes = db_path.stat().st_size if db_path.exists() else 0
    pilot_days = max(1, (end - start).days)
    full_days = (FULL_BACKFILL_END - FULL_BACKFILL_START).days
    payload: dict[str, Any] = {
        "milestone": "SOL_HISTORICAL_BACKFILL_PILOT_V1",
        "status": builder_verdict(metrics, checkpoints),
        "hostname": socket.gethostname(),
        "symbol": symbol,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "db_path": str(db_path),
        "db_size_bytes": db_size_bytes,
        "db_size_mb": db_size_bytes / (1024**2),
        "pilot_days": pilot_days,
        "estimated_full_db_gb": (db_size_bytes / pilot_days * full_days) / (1024**3),
        "disk_before": disk_before,
        "disk_after": disk_after,
        "min_free_gb": min_free_gb,
        "day_stats": [asdict(s) | {"day": s.day.isoformat()} for s in stats],
        "quality": metrics,
        "checkpoints": checkpoints,
    }
    generate_report(payload, report_path)
    return payload


def run_dataset_backfill(
    *,
    symbol: str,
    start: date,
    end: date,
    db_path: Path,
    report_path: Path,
    min_free_gb: float,
    force: bool,
    max_days: int | None = None,
) -> dict[str, Any]:
    assert_safe_output_path(db_path)
    disk_before = ensure_disk_available(db_path, min_free_gb)
    if db_path.exists() and force:
        db_path.unlink()
        db_path.with_name(db_path.name + "-wal").unlink(missing_ok=True)
        db_path.with_name(db_path.name + "-shm").unlink(missing_ok=True)

    client = build_client()
    processed = 0
    day_stats: list[DayStats] = []
    conn = sqlite3.connect(db_path)
    try:
        init_sol_pilot_db(conn)
        for day in _date_range(start, end):
            if max_days is not None and processed >= max_days:
                break
            if checkpoint_status(conn, day) == "DONE":
                continue
            ensure_disk_available(db_path, min_free_gb)
            stats = process_day(conn, client, symbol=symbol, day=day, min_free_gb=min_free_gb, db_path=db_path)
            mark_checkpoint(conn, stats)
            day_stats.append(stats)
            processed += 1

        quality_end = min(end, last_completed_exclusive(conn, start))
        metrics = quality_metrics(conn, symbol, start, quality_end)
        checkpoints = checkpoint_summary(conn)
        conn.execute(
            "INSERT OR REPLACE INTO pilot_manifest(key, value) VALUES (?, ?)",
            (
                "dataset_summary",
                json.dumps(
                    {
                        "milestone": "SOL_HISTORICAL_BACKFILL_DATASET_V1",
                        "quality": metrics,
                        "checkpoints": checkpoints,
                    },
                    sort_keys=True,
                ),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    disk_after = ensure_disk_available(db_path, min_free_gb)
    done_days = int(checkpoints.get("DONE", 0))
    failed_days = int(checkpoints.get("FAILED", 0))
    complete = done_days == expected_days(start, end) and failed_days == 0
    db_size_bytes = db_path.stat().st_size if db_path.exists() else 0
    full_days = expected_days(start, end)
    estimated_full_db_gb = (db_size_bytes / max(done_days, 1) * full_days) / (1024**3)
    payload: dict[str, Any] = {
        "milestone": "SOL_HISTORICAL_BACKFILL_DATASET_V1",
        "status": dataset_verdict(metrics, checkpoints, complete=complete),
        "hostname": socket.gethostname(),
        "symbol": symbol,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "expected_days": expected_days(start, end),
        "done_days": done_days,
        "failed_days": failed_days,
        "processed_this_run": processed,
        "complete": complete,
        "db_path": str(db_path),
        "db_size_mb": db_size_bytes / (1024**2),
        "estimated_full_db_gb": estimated_full_db_gb,
        "disk_before": disk_before,
        "disk_after": disk_after,
        "min_free_gb": min_free_gb,
        "day_stats": [asdict(s) | {"day": s.day.isoformat()} for s in day_stats],
        "quality": metrics,
        "checkpoints": checkpoints,
    }
    generate_dataset_report(payload, report_path)
    return payload


def builder_verdict(quality: dict[str, Any], checkpoints: dict[str, Any]) -> str:
    if checkpoints.get("FAILED", 0):
        return "NEEDS_FIX_BACKFILL_DAY_FAILURE"
    if quality.get("ohlc_errors", 0):
        return "NEEDS_FIX_QUALITY_ERRORS"
    missing = quality.get("missing_rates", {})
    required_keys = ("candles_15m", "candles_4h", "funding", "open_interest", "aggtrade_60s", "aggtrade_15m")
    if any(float(missing.get(key, 1.0)) > 0.01 for key in required_keys):
        return "NEEDS_FIX_MISSINGNESS_ABOVE_GATE"
    return "PASS_SOL_BACKFILL_PILOT_FULL_BACKFILL_READY"


def dataset_verdict(quality: dict[str, Any], checkpoints: dict[str, Any], *, complete: bool) -> str:
    base = builder_verdict(quality, checkpoints)
    if base != "PASS_SOL_BACKFILL_PILOT_FULL_BACKFILL_READY":
        return base.replace("PILOT_FULL_BACKFILL_READY", "DATASET_NEEDS_FIX")
    if not complete:
        return "PARTIAL_SOL_BACKFILL_IN_PROGRESS"
    return "DATASET_COMPLETE_READY_FOR_AUDIT"


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    q = payload["quality"]
    lines = [
        "# SOL Historical Backfill Pilot",
        "",
        "**Milestone:** `SOL_HISTORICAL_BACKFILL_PILOT_V1`",
        f"**Status:** `{payload['status']}`",
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
        f"- Symbol: `{payload['symbol']}`",
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
        f"- Checkpoints: `{json.dumps(payload['checkpoints'], sort_keys=True)}`",
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
        "This pilot validates SOLUSDT archive ingestion mechanics, storage slope, and quality metrics. It is not a SOL strategy backtest and does not approve SOL shadow, PAPER, or runtime work.",
        "",
        "## Audit Questions",
        "",
        "1. Did the pilot write only to a separate `research_lab/snapshots` path?",
        "2. Did the disk guard run before writes and preserve enough free space?",
        "3. Were raw archives streamed per day and discarded rather than persisted?",
        "4. Are row counts, missing rates, duplicates, OHLC errors, and failed days reported?",
        "5. Does the report avoid approving SOL strategy research, SOL shadow, or runtime changes?",
    ]
    text = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    return text


def generate_dataset_report(payload: dict[str, Any], report_path: Path) -> str:
    q = payload["quality"]
    lines = [
        "# SOL Historical Backfill Dataset",
        "",
        "**Milestone:** `SOL_HISTORICAL_BACKFILL_DATASET_V1`",
        f"**Status:** `{payload['status']}`",
        "**Scope:** Research Lab data-engineering dataset only; separate SQLite snapshot; no runtime DB writes.",
        "",
        "## Progress",
        "",
        f"- Symbol: `{payload['symbol']}`",
        f"- Range: {payload['start']} to {payload['end_exclusive']} exclusive",
        f"- Expected days: {payload['expected_days']}",
        f"- Done days: {payload['done_days']}",
        f"- Failed days: {payload['failed_days']}",
        f"- Processed this run: {payload['processed_this_run']}",
        f"- Complete: `{payload['complete']}`",
        f"- DB path: `{payload['db_path']}`",
        f"- DB size: {payload['db_size_mb']:.2f} MB",
        f"- Linear full-size estimate from completed days: {payload['estimated_full_db_gb']:.2f} GB",
        f"- Disk guard: {payload['min_free_gb']:.1f} GB",
        f"- Free disk before: {payload['disk_before']['free_gb']:.2f} GB",
        f"- Free disk after: {payload['disk_after']['free_gb']:.2f} GB",
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
        f"- Checkpoints: `{json.dumps(payload['checkpoints'], sort_keys=True)}`",
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
    failed = payload["checkpoints"].get("failed_days", [])
    if failed:
        for item in failed:
            lines.append(f"- {item['day']}: {item['errors']}")
    else:
        lines.append("- None")
    lines += [
        "",
        "## Builder Interpretation",
        "",
        "This dataset materializes SOLUSDT historical research data for later audited strategy transfer research. It is not a SOL strategy backtest and does not approve SOL shadow, PAPER, or runtime work.",
        "",
        "## Audit Questions",
        "",
        "1. Does the dataset live only in `research_lab/snapshots` and avoid production DB writes?",
        "2. Are daily checkpoints resumable and explicit?",
        "3. Did disk guard remain active throughout the run?",
        "4. Are missing rates, duplicates, OHLC errors, and failed days reported?",
        "5. Does the report avoid SOL strategy or runtime approval claims?",
    ]
    text = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default=SYMBOL)
    parser.add_argument("--start-date", default=DEFAULT_START.isoformat())
    parser.add_argument("--end-date", default=DEFAULT_END.isoformat(), help="Exclusive end date.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--min-free-gb", type=float, default=12.0)
    parser.add_argument("--dataset", action="store_true", help="Run resumable full dataset mode.")
    parser.add_argument("--max-days", type=int, default=None, help="Optional cap for resumable dataset runs.")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dataset:
        db_path = DATASET_DB if args.db_path == DEFAULT_DB else args.db_path
        report_path = DATASET_REPORT if args.report == DEFAULT_REPORT else args.report
        start = FULL_BACKFILL_START if args.start_date == DEFAULT_START.isoformat() else date.fromisoformat(args.start_date)
        end = FULL_BACKFILL_END if args.end_date == DEFAULT_END.isoformat() else date.fromisoformat(args.end_date)
        payload = run_dataset_backfill(
            symbol=str(args.symbol).upper(),
            start=start,
            end=end,
            db_path=db_path,
            report_path=report_path,
            min_free_gb=float(args.min_free_gb),
            force=bool(args.force),
            max_days=args.max_days,
        )
    else:
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
    print(f"status={payload['status']}")
    print(f"db_size_mb={payload['db_size_mb']:.2f}")
    if "estimated_full_db_gb" in payload:
        print(f"estimated_full_db_gb={payload['estimated_full_db_gb']:.2f}")
    print("git_commit", subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip())


if __name__ == "__main__":
    main()
