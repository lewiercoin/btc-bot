"""
RESEARCH-DATA-INVENTORY — Read-only data coverage report for offline Optuna research.

Checks all tables used by ReplayLoader and the backtest pipeline:
  candles (15m/1h/4h), funding, open_interest, aggtrade_buckets,
  force_orders, daily_external_bias, market_snapshots, feature_snapshots,
  decision_outcomes, trade_log

Output: docs/analysis/RESEARCH_DATA_INVENTORY_YYYY-MM-DD.md
        docs/analysis/RESEARCH_DATA_INVENTORY_YYYY-MM-DD.json (optional)

NO runtime changes. NO optimization run. NO production config changes.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _q(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    try:
        return conn.execute(sql, params).fetchall()
    except Exception:
        return []


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple = (), default: Any = None) -> Any:
    rows = _q(conn, sql, params)
    if rows and rows[0][0] is not None:
        return rows[0][0]
    return default


def _fmt_ts(val: str | None) -> str:
    if not val:
        return "—"
    return str(val)[:19].replace("T", " ")


def _gap_count_candles(conn: sqlite3.Connection, symbol: str, timeframe: str,
                       interval_minutes: int) -> dict[str, Any]:
    """Count gaps larger than 2× expected interval using SQLite window functions."""
    threshold = interval_minutes * 2
    try:
        rows = conn.execute(f"""
            WITH ordered AS (
                SELECT open_time,
                       LAG(open_time) OVER (ORDER BY open_time) AS prev_time
                FROM candles
                WHERE symbol = ? AND timeframe = ?
            )
            SELECT
                COUNT(*) AS gap_count,
                MAX(ROUND((julianday(open_time) - julianday(prev_time)) * 1440)) AS max_gap_min
            FROM ordered
            WHERE prev_time IS NOT NULL
              AND (julianday(open_time) - julianday(prev_time)) * 1440 > ?
        """, (symbol, timeframe, threshold)).fetchone()
        if rows:
            return {
                "gap_count": int(rows[0] or 0),
                "max_gap_minutes": float(rows[1] or 0),
            }
    except Exception:
        pass
    return {"gap_count": -1, "max_gap_minutes": -1}


def _gap_count_aggtrade(conn: sqlite3.Connection, symbol: str, timeframe: str,
                        interval_minutes: int) -> dict[str, Any]:
    threshold = interval_minutes * 2
    try:
        rows = conn.execute(f"""
            WITH ordered AS (
                SELECT bucket_time,
                       LAG(bucket_time) OVER (ORDER BY bucket_time) AS prev_time
                FROM aggtrade_buckets
                WHERE symbol = ? AND timeframe = ?
            )
            SELECT
                COUNT(*) AS gap_count,
                MAX(ROUND((julianday(bucket_time) - julianday(prev_time)) * 1440)) AS max_gap_min
            FROM ordered
            WHERE prev_time IS NOT NULL
              AND (julianday(bucket_time) - julianday(prev_time)) * 1440 > ?
        """, (symbol, timeframe, threshold)).fetchone()
        if rows:
            return {
                "gap_count": int(rows[0] or 0),
                "max_gap_minutes": float(rows[1] or 0),
            }
    except Exception:
        pass
    return {"gap_count": -1, "max_gap_minutes": -1}


def _funding_gap_count(conn: sqlite3.Connection, symbol: str) -> dict[str, Any]:
    threshold_hours = 16
    try:
        rows = conn.execute("""
            WITH ordered AS (
                SELECT funding_time,
                       LAG(funding_time) OVER (ORDER BY funding_time) AS prev_time
                FROM funding
                WHERE symbol = ?
            )
            SELECT
                COUNT(*) AS gap_count,
                MAX(ROUND((julianday(funding_time) - julianday(prev_time)) * 24, 2)) AS max_gap_h
            FROM ordered
            WHERE prev_time IS NOT NULL
              AND (julianday(funding_time) - julianday(prev_time)) * 24 > ?
        """, (symbol, threshold_hours)).fetchone()
        if rows:
            return {
                "gap_count": int(rows[0] or 0),
                "max_gap_hours": float(rows[1] or 0),
            }
    except Exception:
        pass
    return {"gap_count": -1, "max_gap_hours": -1}


# ---------------------------------------------------------------------------
# Section collectors
# ---------------------------------------------------------------------------

def _candles_section(conn: sqlite3.Connection, symbol: str) -> dict[str, Any]:
    if not _table_exists(conn, "candles"):
        return {"available": False}

    total = _scalar(conn, "SELECT COUNT(*) FROM candles WHERE symbol=?", (symbol,), 0)
    result: dict[str, Any] = {"available": True, "symbol": symbol, "total": total, "by_timeframe": {}}

    for tf, interval_min in [("15m", 15), ("1h", 60), ("4h", 240)]:
        cnt = _scalar(conn, "SELECT COUNT(*) FROM candles WHERE symbol=? AND timeframe=?", (symbol, tf), 0)
        earliest = _scalar(conn, "SELECT MIN(open_time) FROM candles WHERE symbol=? AND timeframe=?", (symbol, tf))
        latest = _scalar(conn, "SELECT MAX(open_time) FROM candles WHERE symbol=? AND timeframe=?", (symbol, tf))
        gaps = _gap_count_candles(conn, symbol, tf, interval_min)

        if earliest and latest:
            earliest_dt = datetime.fromisoformat(str(earliest)).replace(tzinfo=timezone.utc) if "+" not in str(earliest) else datetime.fromisoformat(str(earliest))
            latest_dt = datetime.fromisoformat(str(latest)).replace(tzinfo=timezone.utc) if "+" not in str(latest) else datetime.fromisoformat(str(latest))
            span_days = (latest_dt - earliest_dt).days
            expected = max(1, int(span_days * 24 * 60 / interval_min))
            coverage_pct = round(cnt / expected * 100, 1) if expected > 0 else 0.0
        else:
            span_days = 0
            coverage_pct = 0.0

        result["by_timeframe"][tf] = {
            "count": int(cnt),
            "earliest": _fmt_ts(str(earliest) if earliest else None),
            "latest": _fmt_ts(str(latest) if latest else None),
            "span_days": span_days,
            "estimated_coverage_pct": coverage_pct,
            "gaps_over_2x_interval": gaps["gap_count"],
            "max_gap_minutes": gaps["max_gap_minutes"],
        }

    return result


def _funding_section(conn: sqlite3.Connection, symbol: str) -> dict[str, Any]:
    if not _table_exists(conn, "funding"):
        return {"available": False}
    cnt = _scalar(conn, "SELECT COUNT(*) FROM funding WHERE symbol=?", (symbol,), 0)
    earliest = _scalar(conn, "SELECT MIN(funding_time) FROM funding WHERE symbol=?", (symbol,))
    latest = _scalar(conn, "SELECT MAX(funding_time) FROM funding WHERE symbol=?", (symbol,))
    gaps = _funding_gap_count(conn, symbol)
    return {
        "available": True,
        "count": int(cnt),
        "earliest": _fmt_ts(str(earliest) if earliest else None),
        "latest": _fmt_ts(str(latest) if latest else None),
        "gaps_over_16h": gaps["gap_count"],
        "max_gap_hours": gaps["max_gap_hours"],
    }


def _oi_section(conn: sqlite3.Connection, symbol: str) -> dict[str, Any]:
    if not _table_exists(conn, "open_interest"):
        return {"available": False}
    cnt = _scalar(conn, "SELECT COUNT(*) FROM open_interest WHERE symbol=?", (symbol,), 0)
    earliest = _scalar(conn, "SELECT MIN(timestamp) FROM open_interest WHERE symbol=?", (symbol,))
    latest = _scalar(conn, "SELECT MAX(timestamp) FROM open_interest WHERE symbol=?", (symbol,))
    return {
        "available": True,
        "count": int(cnt),
        "earliest": _fmt_ts(str(earliest) if earliest else None),
        "latest": _fmt_ts(str(latest) if latest else None),
    }


def _cvd_section(conn: sqlite3.Connection, symbol: str) -> dict[str, Any]:
    if not _table_exists(conn, "aggtrade_buckets"):
        return {"available": False}
    result: dict[str, Any] = {"available": True, "by_timeframe": {}}
    for tf, interval_min in [("15m", 15), ("60s", 1)]:
        cnt = _scalar(conn, "SELECT COUNT(*) FROM aggtrade_buckets WHERE symbol=? AND timeframe=?", (symbol, tf), 0)
        earliest = _scalar(conn, "SELECT MIN(bucket_time) FROM aggtrade_buckets WHERE symbol=? AND timeframe=?", (symbol, tf))
        latest = _scalar(conn, "SELECT MAX(bucket_time) FROM aggtrade_buckets WHERE symbol=? AND timeframe=?", (symbol, tf))
        gaps = _gap_count_aggtrade(conn, symbol, tf, interval_min)
        result["by_timeframe"][tf] = {
            "count": int(cnt),
            "earliest": _fmt_ts(str(earliest) if earliest else None),
            "latest": _fmt_ts(str(latest) if latest else None),
            "gaps_over_2x_interval": gaps["gap_count"],
            "max_gap_minutes": gaps["max_gap_minutes"],
        }
    return result


def _market_truth_section(conn: sqlite3.Connection) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for table in ("market_snapshots", "feature_snapshots", "decision_outcomes"):
        if not _table_exists(conn, table):
            result[table] = {"available": False}
            continue
        cnt = _scalar(conn, f"SELECT COUNT(*) FROM {table}", default=0)
        ts_col = "cycle_timestamp" if table in ("feature_snapshots", "decision_outcomes") else "cycle_timestamp"
        try:
            earliest = _scalar(conn, f"SELECT MIN({ts_col}) FROM {table}")
            latest = _scalar(conn, f"SELECT MAX({ts_col}) FROM {table}")
        except Exception:
            earliest = latest = None
        entry: dict[str, Any] = {
            "available": True,
            "count": int(cnt),
            "earliest": _fmt_ts(str(earliest) if earliest else None),
            "latest": _fmt_ts(str(latest) if latest else None),
        }
        if table == "decision_outcomes":
            with_snap = _scalar(conn, "SELECT COUNT(*) FROM decision_outcomes WHERE snapshot_id IS NOT NULL", default=0)
            with_feat = _scalar(conn, "SELECT COUNT(*) FROM decision_outcomes WHERE feature_snapshot_id IS NOT NULL", default=0)
            entry["with_snapshot_id"] = int(with_snap)
            entry["with_feature_snapshot_id"] = int(with_feat)
        result[table] = entry
    return result


def _trade_log_section(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "trade_log"):
        return {"available": False}
    total = _scalar(conn, "SELECT COUNT(*) FROM trade_log", default=0)
    closed = _scalar(conn, "SELECT COUNT(*) FROM trade_log WHERE closed_at IS NOT NULL", default=0)
    earliest = _scalar(conn, "SELECT MIN(opened_at) FROM trade_log WHERE closed_at IS NOT NULL")
    latest = _scalar(conn, "SELECT MAX(opened_at) FROM trade_log WHERE closed_at IS NOT NULL")
    with_fees = _scalar(conn, "SELECT COUNT(*) FROM trade_log WHERE fees IS NOT NULL AND fees != 0", default=0)
    with_funding = _scalar(conn, "SELECT COUNT(*) FROM trade_log WHERE funding_paid IS NOT NULL AND funding_paid != 0", default=0)
    return {
        "available": True,
        "total": int(total),
        "closed": int(closed),
        "earliest_opened": _fmt_ts(str(earliest) if earliest else None),
        "latest_opened": _fmt_ts(str(latest) if latest else None),
        "with_nonzero_fees": int(with_fees),
        "with_nonzero_funding_paid": int(with_funding),
    }


def _force_orders_section(conn: sqlite3.Connection, symbol: str) -> dict[str, Any]:
    if not _table_exists(conn, "force_orders"):
        return {"available": False}
    cnt = _scalar(conn, "SELECT COUNT(*) FROM force_orders WHERE symbol=?", (symbol,), 0)
    earliest = _scalar(conn, "SELECT MIN(event_time) FROM force_orders WHERE symbol=?", (symbol,))
    latest = _scalar(conn, "SELECT MAX(event_time) FROM force_orders WHERE symbol=?", (symbol,))
    return {
        "available": True,
        "count": int(cnt),
        "earliest": _fmt_ts(str(earliest) if earliest else None),
        "latest": _fmt_ts(str(latest) if latest else None),
    }


def _bias_section(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "daily_external_bias"):
        return {"available": False}
    cnt = _scalar(conn, "SELECT COUNT(*) FROM daily_external_bias", default=0)
    earliest = _scalar(conn, "SELECT MIN(date) FROM daily_external_bias")
    latest = _scalar(conn, "SELECT MAX(date) FROM daily_external_bias")
    with_etf = _scalar(conn, "SELECT COUNT(*) FROM daily_external_bias WHERE etf_bias_5d IS NOT NULL", default=0)
    with_dxy = _scalar(conn, "SELECT COUNT(*) FROM daily_external_bias WHERE dxy_close IS NOT NULL", default=0)
    return {
        "available": True,
        "count": int(cnt),
        "earliest": _fmt_ts(str(earliest) if earliest else None),
        "latest": _fmt_ts(str(latest) if latest else None),
        "with_etf_bias": int(with_etf),
        "with_dxy_close": int(with_dxy),
    }


# ---------------------------------------------------------------------------
# Backtest readiness assessment
# ---------------------------------------------------------------------------

def _assess_backtest_readiness(
    *,
    candles: dict[str, Any],
    funding: dict[str, Any],
    oi: dict[str, Any],
    cvd: dict[str, Any],
    proposed_start: str = "2024-01-01",
    proposed_end: str = "2026-04-27",
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    recommended_start: str | None = None
    recommended_end: str | None = None

    def _parse(ts: str) -> datetime | None:
        if ts == "—" or not ts:
            return None
        try:
            dt = datetime.fromisoformat(ts.replace(" ", "T"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except Exception:
            return None

    prop_start = _parse(proposed_start + "T00:00:00")
    prop_end = _parse(proposed_end + "T00:00:00")

    starts: list[datetime] = []
    ends: list[datetime] = []

    tf_15m = candles.get("by_timeframe", {}).get("15m", {}) if candles.get("available") else {}
    if not tf_15m or tf_15m.get("count", 0) == 0:
        issues.append("candles[15m]: NO DATA — primary replay driver missing")
    else:
        c_start = _parse(tf_15m.get("earliest", ""))
        c_end = _parse(tf_15m.get("latest", ""))
        if c_start:
            starts.append(c_start)
        if c_end:
            ends.append(c_end)
        if c_start and prop_start and c_start > prop_start:
            warnings.append(f"candles[15m] start {tf_15m['earliest']} is after proposed start {proposed_start}")
        gaps = tf_15m.get("gaps_over_2x_interval", 0)
        if gaps > 50:
            warnings.append(f"candles[15m]: {gaps} gaps > 30min detected — data continuity may be impaired")
        elif gaps > 10:
            warnings.append(f"candles[15m]: {gaps} gaps > 30min — minor discontinuities present")

    tf_15m_cvd = cvd.get("by_timeframe", {}).get("15m", {}) if cvd.get("available") else {}
    if not tf_15m_cvd or tf_15m_cvd.get("count", 0) == 0:
        issues.append("aggtrade_buckets[15m]: NO DATA — CVD/TFI features will be zero for all bars")
    else:
        ag_start = _parse(tf_15m_cvd.get("earliest", ""))
        ag_end = _parse(tf_15m_cvd.get("latest", ""))
        if ag_start:
            starts.append(ag_start)
        if ag_end:
            ends.append(ag_end)
        if ag_start and prop_start and ag_start > prop_start:
            warnings.append(f"aggtrade_buckets[15m] start {tf_15m_cvd['earliest']} is after proposed start {proposed_start}")
        cvd_gaps = tf_15m_cvd.get("gaps_over_2x_interval", 0)
        if cvd_gaps > 50:
            warnings.append(f"aggtrade_buckets[15m]: {cvd_gaps} gaps — CVD feature may have zero-fill periods")

    if not funding.get("available") or funding.get("count", 0) == 0:
        issues.append("funding: NO DATA — funding feature will be zero for all bars")
    else:
        f_start = _parse(funding.get("earliest", ""))
        f_end = _parse(funding.get("latest", ""))
        if f_start:
            starts.append(f_start)
        if f_end:
            ends.append(f_end)
        f_gaps = funding.get("gaps_over_16h", 0)
        if f_gaps > 10:
            warnings.append(f"funding: {f_gaps} gaps > 16h detected (expected: every 8h)")

    if not oi.get("available") or oi.get("count", 0) == 0:
        warnings.append("open_interest: NO DATA — OI z-score feature will be zero for all bars")

    if starts and ends:
        actual_start = max(starts)
        actual_end = min(ends)
        actual_start_str = actual_start.strftime("%Y-%m-%d")
        actual_end_str = actual_end.strftime("%Y-%m-%d")
        recommended_start = actual_start_str
        recommended_end = actual_end_str

        if prop_start and actual_start > prop_start + timedelta(days=90):
            warnings.append(
                f"Proposed start {proposed_start} is significantly before actual data coverage "
                f"({actual_start_str}). Will result in sparse/empty early windows."
            )
        if prop_end and actual_end < prop_end - timedelta(days=30):
            warnings.append(
                f"Proposed end {proposed_end} exceeds data coverage ({actual_end_str}) by >30 days."
            )
    else:
        issues.append("Cannot determine coverage intersection — critical data sources missing")

    if issues:
        verdict = "NOT_READY"
        verdict_detail = "Critical data gaps prevent reliable backtest."
    elif warnings:
        verdict = "READY_WITH_WARNINGS"
        verdict_detail = "Backtest feasible but review warnings before running full Optuna."
    else:
        verdict = "READY"
        verdict_detail = "All required data sources present and coverage looks adequate."

    return {
        "proposed_range": f"{proposed_start} -> {proposed_end}",
        "recommended_range": f"{recommended_start} -> {recommended_end}" if recommended_start else "UNKNOWN",
        "recommended_start": recommended_start,
        "recommended_end": recommended_end,
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "issues": issues,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Markdown report builder
# ---------------------------------------------------------------------------

def _bool_icon(val: bool) -> str:
    return "✅" if val else "❌"


def _avail_icon(section: dict[str, Any]) -> str:
    return "✅" if section.get("available") else "❌ NOT FOUND"


def _build_markdown(
    *,
    run_date: str,
    db_path: str,
    symbol: str,
    candles: dict[str, Any],
    funding: dict[str, Any],
    oi: dict[str, Any],
    cvd: dict[str, Any],
    force_orders: dict[str, Any],
    bias: dict[str, Any],
    market_truth: dict[str, Any],
    trade_log: dict[str, Any],
    readiness: dict[str, Any],
) -> str:
    lines: list[str] = [
        "# RESEARCH-DATA-INVENTORY",
        "",
        "> Read-only data coverage report for offline Optuna research.",
        "> No optimization run. No production config changes.",
        "",
        f"**Date:** {run_date}",
        f"**DB:** `{db_path}`",
        f"**Symbol:** `{symbol}`",
        "",
        "---",
        "",
        "## 1. OHLCV Coverage (candles)",
        "",
        f"Table: `candles` — {_avail_icon(candles)}",
        "",
    ]

    if candles.get("available"):
        lines += [
            "| Timeframe | Count | Earliest | Latest | Span (d) | Coverage % | Gaps >2× |",
            "|-----------|-------|----------|--------|----------|------------|----------|",
        ]
        for tf in ("15m", "1h", "4h"):
            d = candles["by_timeframe"].get(tf, {})
            if d:
                gap_icon = "⚠️" if d["gaps_over_2x_interval"] > 10 else "✅"
                cov_icon = "⚠️" if d["estimated_coverage_pct"] < 90 else "✅"
                lines.append(
                    f"| {tf} | {d['count']:,} | {d['earliest']} | {d['latest']} "
                    f"| {d['span_days']} | {cov_icon} {d['estimated_coverage_pct']:.1f}% "
                    f"| {gap_icon} {d['gaps_over_2x_interval']} |"
                )
        lines.append("")
        lines.append(f"**Total candles (all TF):** {candles['total']:,}")
    else:
        lines.append("⚠️ Table not found.")

    lines += [
        "",
        "---",
        "",
        "## 2. Funding Coverage",
        "",
        f"Table: `funding` — {_avail_icon(funding)}",
        "",
    ]
    if funding.get("available"):
        gap_icon = "⚠️" if funding.get("gaps_over_16h", 0) > 5 else "✅"
        lines += [
            f"- **Count:** {funding['count']:,}",
            f"- **Earliest:** {funding['earliest']}",
            f"- **Latest:** {funding['latest']}",
            f"- **Gaps > 16h:** {gap_icon} {funding.get('gaps_over_16h', 0)} "
            f"(max gap: {funding.get('max_gap_hours', 0):.1f}h, expected ≤ 8h)",
        ]
    else:
        lines.append("⚠️ Table not found.")

    lines += [
        "",
        "---",
        "",
        "## 3. Open Interest Coverage",
        "",
        f"Table: `open_interest` — {_avail_icon(oi)}",
        "",
    ]
    if oi.get("available"):
        lines += [
            f"- **Count:** {oi['count']:,}",
            f"- **Earliest:** {oi['earliest']}",
            f"- **Latest:** {oi['latest']}",
        ]
    else:
        lines.append("⚠️ Table not found.")

    lines += [
        "",
        "---",
        "",
        "## 4. CVD / Flow Coverage (aggtrade_buckets)",
        "",
        f"Table: `aggtrade_buckets` — {_avail_icon(cvd)}",
        "",
    ]
    if cvd.get("available"):
        lines += [
            "| Timeframe | Count | Earliest | Latest | Gaps >2× |",
            "|-----------|-------|----------|--------|----------|",
        ]
        for tf in ("15m", "60s"):
            d = cvd["by_timeframe"].get(tf, {})
            if d:
                gap_icon = "⚠️" if d["gaps_over_2x_interval"] > 10 else "✅"
                lines.append(
                    f"| {tf} | {d['count']:,} | {d['earliest']} | {d['latest']} "
                    f"| {gap_icon} {d['gaps_over_2x_interval']} |"
                )
        lines.append("")
    else:
        lines.append("⚠️ Table not found.")

    lines += [
        "---",
        "",
        "## 5. Market Truth Snapshots",
        "",
    ]
    for tbl in ("market_snapshots", "feature_snapshots", "decision_outcomes"):
        sec = market_truth.get(tbl, {})
        avail = sec.get("available", False)
        icon = "✅" if avail else "❌"
        lines.append(f"**{tbl}** — {icon}")
        if avail:
            lines.append(f"- Count: {sec.get('count', 0):,} | {sec.get('earliest', '—')} → {sec.get('latest', '—')}")
            if tbl == "decision_outcomes":
                total = sec.get("count", 0)
                with_s = sec.get("with_snapshot_id", 0)
                with_f = sec.get("with_feature_snapshot_id", 0)
                s_pct = f"{with_s / total * 100:.1f}%" if total > 0 else "—"
                f_pct = f"{with_f / total * 100:.1f}%" if total > 0 else "—"
                lines.append(f"- With snapshot_id: {with_s:,} ({s_pct})")
                lines.append(f"- With feature_snapshot_id: {with_f:,} ({f_pct})")
        lines.append("")

    lines += [
        "---",
        "",
        "## 6. Trade Log",
        "",
        f"Table: `trade_log` — {_avail_icon(trade_log)}",
        "",
    ]
    if trade_log.get("available"):
        total = trade_log.get("total", 0)
        closed = trade_log.get("closed", 0)
        fees = trade_log.get("with_nonzero_fees", 0)
        funding_paid = trade_log.get("with_nonzero_funding_paid", 0)
        fee_pct = f"{fees / closed * 100:.1f}%" if closed > 0 else "—"
        fund_pct = f"{funding_paid / closed * 100:.1f}%" if closed > 0 else "—"
        lines += [
            f"- **Total trades:** {total:,} (closed: {closed:,})",
            f"- **Earliest opened:** {trade_log.get('earliest_opened', '—')}",
            f"- **Latest opened:** {trade_log.get('latest_opened', '—')}",
            f"- **With non-zero fees:** {fees:,} / {closed:,} ({fee_pct})",
            f"- **With non-zero funding_paid:** {funding_paid:,} / {closed:,} ({fund_pct})",
        ]
    else:
        lines.append("⚠️ Table not found.")

    lines += [
        "",
        "---",
        "",
        "## 7. Supplementary Tables",
        "",
        f"**force_orders** — {_avail_icon(force_orders)}",
    ]
    if force_orders.get("available"):
        lines.append(f"- Count: {force_orders.get('count', 0):,} | {force_orders.get('earliest', '—')} → {force_orders.get('latest', '—')}")
    lines.append("")
    lines.append(f"**daily_external_bias** — {_avail_icon(bias)}")
    if bias.get("available"):
        lines += [
            f"- Count: {bias.get('count', 0):,} | {bias.get('earliest', '—')} → {bias.get('latest', '—')}",
            f"- With ETF bias: {bias.get('with_etf_bias', 0):,} | With DXY close: {bias.get('with_dxy_close', 0):,}",
        ]

    r = readiness
    verdict_icon = {"READY": "✅", "READY_WITH_WARNINGS": "⚠️", "NOT_READY": "❌"}.get(r["verdict"], "?")
    lines += [
        "",
        "---",
        "",
        "## 8. Backtest Readiness Assessment",
        "",
        f"**Proposed range:** `{r['proposed_range']}`",
        f"**Recommended range:** `{r['recommended_range']}`",
        f"**Verdict:** {verdict_icon} **{r['verdict']}** — {r['verdict_detail']}",
        "",
    ]
    if r["issues"]:
        lines.append("### ❌ Critical Issues")
        lines.append("")
        for issue in r["issues"]:
            lines.append(f"- {issue}")
        lines.append("")
    if r["warnings"]:
        lines.append("### ⚠️ Warnings")
        lines.append("")
        for warn in r["warnings"]:
            lines.append(f"- {warn}")
        lines.append("")

    lines += [
        "### Next Steps",
        "",
        "Based on this report, choose:",
        "",
        "- **A)** Run Optuna on full recommended range ← only if READY or READY_WITH_WARNINGS",
        "- **B)** Narrow the search range to well-covered periods",
        "- **C)** Backfill missing data (funding, OI, aggtrade_buckets) before running",
        "- **D)** Smoke research only (1 window, 10 trials) to validate pipeline end-to-end",
        "",
        "**Do NOT run full Optuna until this report is reviewed.**",
        "",
        "---",
        "",
        f"*Generated: {run_date} UTC — read-only, no runtime changes.*",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RESEARCH-DATA-INVENTORY: read-only DB coverage report.")
    p.add_argument("--db", type=Path, required=True, help="Path to btc_bot.db (read-only).")
    p.add_argument("--symbol", type=str, default="BTCUSDT")
    p.add_argument("--output-dir", type=Path, default=Path("docs/analysis"))
    p.add_argument("--proposed-start", type=str, default="2024-01-01")
    p.add_argument("--proposed-end", type=str, default="2026-04-27")
    p.add_argument("--write-json", action="store_true", default=False)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if not args.db.exists():
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    print(f"[RESEARCH-DATA-INVENTORY] Opening DB (read-only): {args.db}")
    conn = _open_ro(args.db)

    try:
        print("  Scanning candles...")
        candles = _candles_section(conn, args.symbol)
        print("  Scanning funding...")
        funding = _funding_section(conn, args.symbol)
        print("  Scanning open_interest...")
        oi = _oi_section(conn, args.symbol)
        print("  Scanning aggtrade_buckets (CVD/flow)...")
        cvd = _cvd_section(conn, args.symbol)
        print("  Scanning force_orders...")
        force_orders = _force_orders_section(conn, args.symbol)
        print("  Scanning daily_external_bias...")
        bias = _bias_section(conn)
        print("  Scanning market/feature snapshots + decision_outcomes...")
        market_truth = _market_truth_section(conn)
        print("  Scanning trade_log...")
        trade_log = _trade_log_section(conn)
    finally:
        conn.close()

    readiness = _assess_backtest_readiness(
        candles=candles,
        funding=funding,
        oi=oi,
        cvd=cvd,
        proposed_start=args.proposed_start,
        proposed_end=args.proposed_end,
    )

    run_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    md = _build_markdown(
        run_date=run_date,
        db_path=str(args.db),
        symbol=args.symbol,
        candles=candles,
        funding=funding,
        oi=oi,
        cvd=cvd,
        force_orders=force_orders,
        bias=bias,
        market_truth=market_truth,
        trade_log=trade_log,
        readiness=readiness,
    )
    md_path = args.output_dir / f"RESEARCH_DATA_INVENTORY_{run_date}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"\n[RESEARCH-DATA-INVENTORY] Report: {md_path}")

    if args.write_json:
        payload = {
            "run_date": run_date,
            "symbol": args.symbol,
            "candles": candles,
            "funding": funding,
            "open_interest": oi,
            "cvd_flow": cvd,
            "force_orders": force_orders,
            "daily_external_bias": bias,
            "market_truth": market_truth,
            "trade_log": trade_log,
            "backtest_readiness": readiness,
        }
        json_path = args.output_dir / f"RESEARCH_DATA_INVENTORY_{run_date}.json"
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"[RESEARCH-DATA-INVENTORY] JSON:   {json_path}")

    print()
    print(f"  Verdict:             {readiness['verdict']}")
    print(f"  Proposed range:      {readiness['proposed_range']}")
    print(f"  Recommended range:   {readiness['recommended_range']}")
    if readiness["issues"]:
        print(f"  [ISSUES] ({len(readiness['issues'])}):")
        for i in readiness["issues"]:
            print(f"     - {i}")
    if readiness["warnings"]:
        print(f"  [WARNINGS] ({len(readiness['warnings'])}):")
        for w in readiness["warnings"]:
            print(f"     - {w}")


if __name__ == "__main__":
    main()
