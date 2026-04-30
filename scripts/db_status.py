#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(os.getenv("BTC_BOT_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from settings import load_settings  # noqa: E402


GATE_A_START = "2026-04-25T00:45:00+00:00"


@dataclass(frozen=True)
class TableStatus:
    name: str
    rows: int
    min_ts: str | None
    max_ts: str | None
    gaps: int | None


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_git(args: list[str]) -> str:
    git_candidates = [
        "git",
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
    ]
    last_error: Exception | None = None
    for git_bin in git_candidates:
        try:
            result = subprocess.run(
                [git_bin, *args],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() or "unknown"
        except (OSError, subprocess.SubprocessError) as exc:
            last_error = exc
            continue
    _ = last_error
    return "unknown"


def _open_readonly_db() -> sqlite3.Connection:
    profile = os.getenv("BOT_SETTINGS_PROFILE", "research")
    settings = load_settings(project_root=PROJECT_ROOT, profile=profile)
    if settings.storage is None:
        raise RuntimeError("settings.storage is required")
    db_path = settings.storage.db_path
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _scalar(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(query, params).fetchone()
    if row is None:
        return None
    return row[0]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(
        _scalar(
            conn,
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
    )


def _bounds(
    conn: sqlite3.Connection,
    *,
    table: str,
    ts_col: str,
    where_sql: str = "1=1",
    params: tuple[Any, ...] = (),
) -> tuple[int, str | None, str | None]:
    if not _table_exists(conn, table):
        return 0, None, None
    row = conn.execute(
        f"SELECT COUNT(*) AS rows, MIN({ts_col}) AS min_ts, MAX({ts_col}) AS max_ts "
        f"FROM {table} WHERE {where_sql}",
        params,
    ).fetchone()
    if row is None:
        return 0, None, None
    return int(row["rows"]), row["min_ts"], row["max_ts"]


def _gap_count(
    conn: sqlite3.Connection,
    *,
    table: str,
    ts_col: str,
    threshold_minutes: float,
    where_sql: str = "1=1",
    params: tuple[Any, ...] = (),
) -> int:
    if not _table_exists(conn, table):
        return 0
    row = conn.execute(
        f"""
        WITH ordered AS (
            SELECT {ts_col} AS ts,
                   LAG({ts_col}) OVER (ORDER BY {ts_col}) AS prev_ts
            FROM {table}
            WHERE {where_sql}
        )
        SELECT COUNT(*) AS gap_count
        FROM ordered
        WHERE prev_ts IS NOT NULL
          AND (julianday(ts) - julianday(prev_ts)) * 24.0 * 60.0 > ?
        """,
        (*params, float(threshold_minutes) + 0.01),
    ).fetchone()
    return int(row["gap_count"]) if row is not None else 0


def _replay_table_statuses(conn: sqlite3.Connection) -> list[TableStatus]:
    specs = (
        ("candles_15m", "candles", "open_time", "symbol='BTCUSDT' AND timeframe='15m'", (), 15.0),
        ("aggtrade_15m", "aggtrade_buckets", "bucket_time", "symbol='BTCUSDT' AND timeframe='15m'", (), 15.0),
        ("funding", "funding", "funding_time", "symbol='BTCUSDT'", (), 8.0 * 60.0),
        ("open_interest", "open_interest", "timestamp", "symbol='BTCUSDT'", (), 15.0),
    )
    statuses: list[TableStatus] = []
    for name, table, ts_col, where_sql, params, threshold in specs:
        rows, min_ts, max_ts = _bounds(conn, table=table, ts_col=ts_col, where_sql=where_sql, params=params)
        gaps = _gap_count(
            conn,
            table=table,
            ts_col=ts_col,
            threshold_minutes=threshold,
            where_sql=where_sql,
            params=params,
        )
        statuses.append(TableStatus(name=name, rows=rows, min_ts=min_ts, max_ts=max_ts, gaps=gaps))

    rows, min_ts, max_ts = _bounds(
        conn,
        table="force_orders",
        ts_col="event_time",
        where_sql="symbol='BTCUSDT'",
    )
    statuses.append(TableStatus(name="force_orders", rows=rows, min_ts=min_ts, max_ts=max_ts, gaps=None))
    return statuses


def _bot_mode(conn: sqlite3.Connection) -> str:
    if not _table_exists(conn, "bot_state"):
        return "unknown"
    value = _scalar(conn, "SELECT mode FROM bot_state ORDER BY timestamp DESC LIMIT 1")
    return str(value) if value is not None else "unknown"


def _trade_log(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "trade_log"):
        return {
            "closed": 0,
            "first_close": None,
            "last_close": None,
            "last_type": "none",
        }
    row = conn.execute(
        """
        SELECT COUNT(*) AS closed,
               MIN(closed_at) AS first_close,
               MAX(closed_at) AS last_close
        FROM trade_log
        WHERE closed_at IS NOT NULL
        """
    ).fetchone()
    last = conn.execute(
        """
        SELECT direction, exit_reason, pnl_r
        FROM trade_log
        WHERE closed_at IS NOT NULL
        ORDER BY closed_at DESC
        LIMIT 1
        """
    ).fetchone()
    last_type = "none"
    if last is not None:
        last_type = f"{last['direction']}, {last['exit_reason']}, {float(last['pnl_r']):.2f}R"
    return {
        "closed": int(row["closed"]) if row is not None else 0,
        "first_close": row["first_close"] if row is not None else None,
        "last_close": row["last_close"] if row is not None else None,
        "last_type": last_type,
    }


def _market_truth(conn: sqlite3.Connection) -> dict[str, Any]:
    required = {"market_snapshots", "feature_snapshots", "decision_outcomes"}
    if not all(_table_exists(conn, table) for table in required):
        return {
            "lineage_observed": 0,
            "lineage_expected": 0,
            "quality_ready": 0,
            "quality_total": 0,
            "degraded_from": "none",
            "degraded_reason": "none",
        }

    query = """
    WITH decision_links AS (
        SELECT feature_snapshot_id,
               snapshot_id,
               substr(cycle_timestamp, 1, 16) AS bucket_15m,
               COUNT(*) AS decision_outcome_count
        FROM decision_outcomes
        GROUP BY feature_snapshot_id, snapshot_id, substr(cycle_timestamp, 1, 16)
    ),
    per_row AS (
        SELECT substr(fs.cycle_timestamp, 1, 16) AS bucket_15m,
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
               END AS is_ready,
               COALESCE(json_extract(fs.quality_json, '$.flow_15m.reason'), '') AS flow_15m_reason,
               COALESCE(json_extract(fs.quality_json, '$.flow_60s.reason'), '') AS flow_60s_reason,
               COALESCE(json_extract(fs.quality_json, '$.funding_window.reason'), '') AS funding_reason,
               COALESCE(json_extract(fs.quality_json, '$.oi_baseline.reason'), '') AS oi_reason,
               COALESCE(json_extract(fs.quality_json, '$.cvd_divergence.reason'), '') AS cvd_reason
        FROM feature_snapshots fs
        JOIN market_snapshots ms
          ON ms.snapshot_id = fs.snapshot_id
        LEFT JOIN decision_links dl
          ON dl.feature_snapshot_id = fs.feature_snapshot_id
         AND dl.snapshot_id = fs.snapshot_id
        WHERE fs.cycle_timestamp >= ?
    ),
    per_bucket AS (
        SELECT bucket_15m,
               MAX(has_full_lineage) AS has_full_lineage,
               MAX(CASE WHEN has_full_lineage = 1 AND is_ready = 1 THEN 1 ELSE 0 END) AS quality_ready,
               GROUP_CONCAT(DISTINCT NULLIF(flow_15m_reason, '')) AS flow_15m_reasons,
               GROUP_CONCAT(DISTINCT NULLIF(flow_60s_reason, '')) AS flow_60s_reasons,
               GROUP_CONCAT(DISTINCT NULLIF(funding_reason, '')) AS funding_reasons,
               GROUP_CONCAT(DISTINCT NULLIF(oi_reason, '')) AS oi_reasons,
               GROUP_CONCAT(DISTINCT NULLIF(cvd_reason, '')) AS cvd_reasons
        FROM per_row
        GROUP BY bucket_15m
    )
    SELECT bucket_15m,
           has_full_lineage,
           quality_ready,
           TRIM(
               COALESCE(flow_15m_reasons, '') || ' ' ||
               COALESCE(flow_60s_reasons, '') || ' ' ||
               COALESCE(funding_reasons, '') || ' ' ||
               COALESCE(oi_reasons, '') || ' ' ||
               COALESCE(cvd_reasons, '')
           ) AS degraded_reason
    FROM per_bucket
    ORDER BY bucket_15m
    """
    rows = conn.execute(query, (GATE_A_START,)).fetchall()
    total = len(rows)
    lineage = sum(int(row["has_full_lineage"] or 0) for row in rows)
    ready = sum(int(row["quality_ready"] or 0) for row in rows)
    degraded_from = "none"
    degraded_reason = "none"
    if rows and int(rows[-1]["quality_ready"] or 0) == 0:
        start_index = len(rows) - 1
        while start_index > 0 and int(rows[start_index - 1]["quality_ready"] or 0) == 0:
            start_index -= 1
        degraded_from = str(rows[start_index]["bucket_15m"])
        reason = str(rows[-1]["degraded_reason"] or "").strip()
        degraded_reason = reason if reason else "unknown"
    return {
        "lineage_observed": lineage,
        "lineage_expected": total,
        "quality_ready": ready,
        "quality_total": total,
        "degraded_from": degraded_from,
        "degraded_reason": degraded_reason,
    }


def _external_bias(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "daily_external_bias"):
        return {"rows": 0, "min_date": None, "max_date": None, "etf_rows": 0}
    row = conn.execute(
        """
        SELECT COUNT(*) AS rows,
               MIN(date) AS min_date,
               MAX(date) AS max_date,
               SUM(CASE WHEN etf_bias_5d IS NOT NULL THEN 1 ELSE 0 END) AS etf_rows
        FROM daily_external_bias
        """
    ).fetchone()
    return {
        "rows": int(row["rows"] or 0),
        "min_date": row["min_date"],
        "max_date": row["max_date"],
        "etf_rows": int(row["etf_rows"] or 0),
    }


def _research_lab() -> dict[str, str]:
    store_path = PROJECT_ROOT / "research_lab" / "research_lab.db"
    if not store_path.exists():
        return {"last_study": "none", "last_candidate": "none", "open_blockers": "none"}
    uri = f"file:{store_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, "trials"):
            return {"last_study": "none", "last_candidate": "none", "open_blockers": "none"}
        last_trial = conn.execute(
            """
            SELECT trial_id, rejected_reason, created_at_utc
            FROM trials
            ORDER BY created_at_utc DESC, trial_id DESC
            LIMIT 1
            """
        ).fetchone()
        if last_trial is None:
            return {"last_study": "none", "last_candidate": "none", "open_blockers": "none"}
        candidate = str(last_trial["trial_id"])
        status = "accepted" if last_trial["rejected_reason"] is None else f"rejected: {last_trial['rejected_reason']}"
        return {
            "last_study": _infer_study_name(candidate),
            "last_candidate": f"{candidate} ({status})",
            "open_blockers": "none",
        }
    finally:
        conn.close()


def _infer_study_name(trial_id: str) -> str:
    if "-trial-" in trial_id:
        return trial_id.split("-trial-", maxsplit=1)[0]
    if trial_id.startswith("geometry-"):
        return "geometry_sensitivity"
    return "unknown"


def _format_range(min_ts: str | None, max_ts: str | None) -> str:
    if min_ts is None or max_ts is None:
        return "none -> none"
    return f"{min_ts} -> {max_ts}"


def _format_gaps(gaps: int | None) -> str:
    if gaps is None:
        return "n/a"
    return str(gaps)


def print_report() -> None:
    conn = _open_readonly_db()
    try:
        replay_statuses = _replay_table_statuses(conn)
        market_truth = _market_truth(conn)
        external_bias = _external_bias(conn)

        print("=== BTC-BOT DATABASE STATUS ===")
        print(f"Generated: {_now_utc()}")
        print(f"Branch: {_run_git(['rev-parse', '--abbrev-ref', 'HEAD'])}")
        print(f"Commit: {_run_git(['rev-parse', '--short', 'HEAD'])}")
        print(f"Bot mode: {_bot_mode(conn)}")

        print()
        print("REPLAY TABLES:")
        for status in replay_statuses:
            print(
                f"  {status.name:<15}: {_format_range(status.min_ts, status.max_ts)}  "
                f"[rows: {status.rows}, gaps: {_format_gaps(status.gaps)}]"
            )

        trade_log = _trade_log(conn)
        print()
        print("TRADE LOG:")
        print(f"  closed trades   : {trade_log['closed']}")
        print(f"  first close     : {trade_log['first_close'] or 'none'}")
        print(f"  last close      : {trade_log['last_close'] or 'none'}")
        print(f"  last trade type : {trade_log['last_type']}")

        print()
        print("MARKET TRUTH (Gate A):")
        print(f"  lineage buckets : {market_truth['lineage_observed']}/{market_truth['lineage_expected']}")
        print(f"  quality_ready   : {market_truth['quality_ready']}/{market_truth['quality_total']}")
        print(f"  degraded_from   : {market_truth['degraded_from']}")
        print(f"  degraded_reason : {market_truth['degraded_reason']}")

        etf_rows = external_bias["etf_rows"]
        etf_status = "empty" if int(etf_rows) == 0 else str(etf_rows)
        print()
        print("EXTERNAL BIAS:")
        print(
            "  daily_external_bias (DXY) : "
            f"{external_bias['rows']} rows, {external_bias['min_date'] or 'none'} -> {external_bias['max_date'] or 'none'}"
        )
        print(f"  etf_bias_5d               : {etf_rows} rows ({etf_status})")

        research = _research_lab()
        blockers = _open_blockers(
            replay_statuses=replay_statuses,
            market_truth=market_truth,
            external_bias=external_bias,
        )
        print()
        print("RESEARCH LAB:")
        print(f"  last study      : {research['last_study']}")
        print(f"  last candidate  : {research['last_candidate']}")
        print(f"  open blockers   : {blockers or research['open_blockers']}")
    finally:
        conn.close()


def _open_blockers(
    *,
    replay_statuses: list[TableStatus],
    market_truth: dict[str, Any],
    external_bias: dict[str, Any],
) -> str:
    blockers: list[str] = []
    for status in replay_statuses:
        if status.gaps is not None and status.gaps > 0:
            blockers.append(f"{status.name}_gaps={status.gaps}")
    if int(market_truth["quality_ready"]) < int(market_truth["quality_total"]):
        blockers.append(f"market_truth_degraded_from={market_truth['degraded_from']}")
    if int(external_bias["etf_rows"]) == 0:
        blockers.append("etf_bias_empty")
    return ", ".join(blockers)


def main() -> int:
    try:
        print_report()
    except Exception as exc:
        print(f"db_status failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
