#!/usr/bin/env python3
"""Generate a read-only multi-asset shadow evidence checkpoint."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


@dataclass(frozen=True, slots=True)
class SymbolEvidence:
    symbol: str
    decision_rows: int
    signal_generated_rows: int
    near_miss_rows: int
    portfolio_approved_rows: int
    portfolio_veto_rows: int
    blocker_counts: dict[str, int]
    min_sweep_depth_pct_min: float | None
    min_sweep_depth_pct_max: float | None


@dataclass(frozen=True, slots=True)
class ShadowEvidenceCheckpoint:
    status: str
    window_start_utc: str
    window_end_utc: str
    expected_min_cycles: int
    observed_shadow_runs: int
    observed_complete_cycles: int
    production_db_touched_true_count: int | None
    resource_guard_failures: int
    latest_resource_guard_status: str | None
    max_shadow_rss_mb: float | None
    min_disk_free_gb: float | None
    production_open_positions: int | None
    production_eth_sol_positions: int | None
    production_multi_asset_tables: tuple[str, ...]
    symbol_evidence: tuple[SymbolEvidence, ...]
    failures: tuple[str, ...]
    warnings: tuple[str, ...]


def build_checkpoint(
    *,
    shadow_db_path: Path,
    production_db_path: Path | None,
    days: int | None = None,
    hours: int | None = None,
    expected_min_cycles: int | None = None,
    now: datetime | None = None,
    journal_unit: str | None = "multi-asset-shadow.service",
) -> ShadowEvidenceCheckpoint:
    end = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if hours is not None:
        start = end - timedelta(hours=hours)
        default_expected = hours * 4
    else:
        window_days = days if days is not None else 3
        start = end - timedelta(days=window_days)
        default_expected = window_days * 24 * 4
    expected = expected_min_cycles if expected_min_cycles is not None else default_expected

    shadow = _collect_shadow_evidence(shadow_db_path, start=start, end=end)
    production = _collect_production_evidence(production_db_path) if production_db_path else {}
    production_touch_count = _count_production_db_touched_true(journal_unit, since=start) if journal_unit else None

    failures: list[str] = []
    warnings: list[str] = []
    if shadow["complete_cycles"] < expected:
        failures.append(f"complete_cycles {shadow['complete_cycles']} < expected_min_cycles {expected}")
    if shadow["resource_guard_failures"] > 0:
        failures.append(f"resource_guard_failures={shadow['resource_guard_failures']}")
    if production_touch_count is None:
        warnings.append("production_db_touched_journal_unavailable")
    elif production_touch_count > 0:
        failures.append(f"production_db_touched_true_count={production_touch_count}")
    if production.get("eth_sol_positions") not in (None, 0):
        failures.append(f"production_eth_sol_positions={production['eth_sol_positions']}")
    if production.get("open_positions") not in (None, 0):
        warnings.append(f"production_open_positions={production['open_positions']}")
    if production.get("multi_asset_tables"):
        failures.append("production_multi_asset_tables_present")

    for symbol in SYMBOLS:
        if shadow["symbol_rows"].get(symbol, 0) == 0:
            failures.append(f"{symbol}_shadow_rows=0")

    status = "fail" if failures else "warn" if warnings else "pass"
    return ShadowEvidenceCheckpoint(
        status=status,
        window_start_utc=_to_z(start),
        window_end_utc=_to_z(end),
        expected_min_cycles=expected,
        observed_shadow_runs=shadow["runs"],
        observed_complete_cycles=shadow["complete_cycles"],
        production_db_touched_true_count=production_touch_count,
        resource_guard_failures=shadow["resource_guard_failures"],
        latest_resource_guard_status=shadow["latest_resource_guard_status"],
        max_shadow_rss_mb=shadow["max_shadow_rss_mb"],
        min_disk_free_gb=shadow["min_disk_free_gb"],
        production_open_positions=production.get("open_positions"),
        production_eth_sol_positions=production.get("eth_sol_positions"),
        production_multi_asset_tables=tuple(production.get("multi_asset_tables", ())),
        symbol_evidence=tuple(shadow["symbols"]),
        failures=tuple(failures),
        warnings=tuple(warnings),
    )


def render_markdown(checkpoint: ShadowEvidenceCheckpoint) -> str:
    lines = [
        "# Multi-Asset Shadow Evidence Checkpoint",
        "",
        f"**Status:** {checkpoint.status.upper()}",
        f"**Window:** {checkpoint.window_start_utc} -> {checkpoint.window_end_utc}",
        "",
        "## Summary",
        "",
        f"- Expected minimum complete cycles: {checkpoint.expected_min_cycles}",
        f"- Observed shadow runs: {checkpoint.observed_shadow_runs}",
        f"- Observed complete BTC/ETH/SOL cycles: {checkpoint.observed_complete_cycles}",
        f"- production_db_touched=true count: {checkpoint.production_db_touched_true_count}",
        f"- Resource guard failures: {checkpoint.resource_guard_failures}",
        f"- Latest resource guard: {checkpoint.latest_resource_guard_status}",
        f"- Max shadow RSS MB: {_fmt(checkpoint.max_shadow_rss_mb)}",
        f"- Min disk free GB: {_fmt(checkpoint.min_disk_free_gb)}",
        f"- Production open positions: {checkpoint.production_open_positions}",
        f"- Production ETH/SOL positions: {checkpoint.production_eth_sol_positions}",
        f"- Production multi-asset tables: {', '.join(checkpoint.production_multi_asset_tables) or 'none'}",
        "",
        "## Per Symbol",
        "",
        "| Symbol | Decisions | Signals | Near-Miss | Portfolio Approved | Portfolio Veto | Threshold Min | Threshold Max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in checkpoint.symbol_evidence:
        lines.append(
            f"| {item.symbol} | {item.decision_rows} | {item.signal_generated_rows} | "
            f"{item.near_miss_rows} | {item.portfolio_approved_rows} | {item.portfolio_veto_rows} | "
            f"{_fmt(item.min_sweep_depth_pct_min)} | {_fmt(item.min_sweep_depth_pct_max)} |"
        )
    lines.extend(["", "## Blockers", ""])
    for item in checkpoint.symbol_evidence:
        blockers = ", ".join(f"{key}={value}" for key, value in sorted(item.blocker_counts.items())) or "none"
        lines.append(f"- {item.symbol}: {blockers}")
    lines.extend(["", "## Failures", ""])
    lines.extend(f"- {failure}" for failure in checkpoint.failures)
    if not checkpoint.failures:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in checkpoint.warnings)
    if not checkpoint.warnings:
        lines.append("- none")
    lines.extend(["", "*Read-only checkpoint. No trading activation implied.*"])
    return "\n".join(lines) + "\n"


def _collect_shadow_evidence(shadow_db_path: Path, *, start: datetime, end: datetime) -> dict[str, Any]:
    conn = _connect_readonly(shadow_db_path)
    start_s = _to_z(start)
    end_s = _to_z(end)
    try:
        runs = _count(
            conn,
            """
            SELECT COUNT(*) FROM shadow_runs
            WHERE created_at_utc >= ? AND created_at_utc <= ? AND dry_run = 0
            """,
            (start_s, end_s),
        )
        complete_cycles = _count(
            conn,
            """
            SELECT COUNT(*) FROM (
                SELECT shadow_run_id
                FROM shadow_decision_outcomes
                WHERE timestamp_utc >= ? AND timestamp_utc <= ?
                GROUP BY shadow_run_id
                HAVING COUNT(DISTINCT symbol) >= 3
            )
            """,
            (start_s, end_s),
        )
        resource_guard_failures = _count(
            conn,
            """
            SELECT COUNT(*) FROM shadow_resource_samples
            WHERE timestamp_utc >= ? AND timestamp_utc <= ? AND guard_status != 'pass'
            """,
            (start_s, end_s),
        )
        latest_resource = conn.execute(
            """
            SELECT guard_status
            FROM shadow_resource_samples
            WHERE timestamp_utc >= ? AND timestamp_utc <= ?
            ORDER BY id DESC LIMIT 1
            """,
            (start_s, end_s),
        ).fetchone()
        max_rss = conn.execute(
            """
            SELECT MAX(memory_rss_bytes) FROM shadow_resource_samples
            WHERE timestamp_utc >= ? AND timestamp_utc <= ?
            """,
            (start_s, end_s),
        ).fetchone()[0]
        min_disk = conn.execute(
            """
            SELECT MIN(disk_free_bytes) FROM shadow_resource_samples
            WHERE timestamp_utc >= ? AND timestamp_utc <= ?
            """,
            (start_s, end_s),
        ).fetchone()[0]
        symbols = tuple(_symbol_evidence(conn, symbol, start=start, end=end) for symbol in SYMBOLS)
        return {
            "runs": runs,
            "complete_cycles": complete_cycles,
            "resource_guard_failures": resource_guard_failures,
            "latest_resource_guard_status": latest_resource["guard_status"] if latest_resource else None,
            "max_shadow_rss_mb": (float(max_rss) / 1024 / 1024) if max_rss is not None else None,
            "min_disk_free_gb": (float(min_disk) / 1024 / 1024 / 1024) if min_disk is not None else None,
            "symbols": symbols,
            "symbol_rows": {item.symbol: item.decision_rows for item in symbols},
        }
    finally:
        conn.close()


def _symbol_evidence(conn: sqlite3.Connection, symbol: str, *, start: datetime, end: datetime) -> SymbolEvidence:
    params = (symbol, _to_z(start), _to_z(end))
    decision_rows = _count(
        conn,
        """
        SELECT COUNT(*) FROM shadow_decision_outcomes
        WHERE symbol = ? AND timestamp_utc >= ? AND timestamp_utc <= ?
        """,
        params,
    )
    signal_rows = _count(
        conn,
        """
        SELECT COUNT(*) FROM shadow_decision_outcomes
        WHERE symbol = ? AND timestamp_utc >= ? AND timestamp_utc <= ? AND signal_generated = 1
        """,
        params,
    )
    near_miss_rows = _count(
        conn,
        """
        SELECT COUNT(*) FROM shadow_near_miss_diagnostics
        WHERE symbol = ? AND timestamp_utc >= ? AND timestamp_utc <= ?
        """,
        params,
    )
    approved_rows = _count(
        conn,
        """
        SELECT COUNT(*) FROM shadow_portfolio_decisions
        WHERE symbol = ? AND timestamp_utc >= ? AND timestamp_utc <= ?
          AND portfolio_shadow_decision = 'approve_shadow'
        """,
        params,
    )
    veto_rows = _count(
        conn,
        """
        SELECT COUNT(*) FROM shadow_portfolio_decisions
        WHERE symbol = ? AND timestamp_utc >= ? AND timestamp_utc <= ?
          AND portfolio_shadow_decision != 'approve_shadow'
        """,
        params,
    )
    threshold_row = conn.execute(
        """
        SELECT MIN(min_sweep_depth_pct), MAX(min_sweep_depth_pct)
        FROM shadow_decision_outcomes
        WHERE symbol = ? AND timestamp_utc >= ? AND timestamp_utc <= ?
        """,
        params,
    ).fetchone()
    blocker_counts = {
        str(row["signal_blocker"] or "none"): int(row["count"])
        for row in conn.execute(
            """
            SELECT signal_blocker, COUNT(*) AS count
            FROM shadow_decision_outcomes
            WHERE symbol = ? AND timestamp_utc >= ? AND timestamp_utc <= ?
            GROUP BY signal_blocker
            """,
            params,
        )
    }
    return SymbolEvidence(
        symbol=symbol,
        decision_rows=decision_rows,
        signal_generated_rows=signal_rows,
        near_miss_rows=near_miss_rows,
        portfolio_approved_rows=approved_rows,
        portfolio_veto_rows=veto_rows,
        blocker_counts=blocker_counts,
        min_sweep_depth_pct_min=threshold_row[0] if threshold_row else None,
        min_sweep_depth_pct_max=threshold_row[1] if threshold_row else None,
    )


def _collect_production_evidence(production_db_path: Path | None) -> dict[str, Any]:
    if production_db_path is None or not production_db_path.exists():
        return {}
    conn = _connect_readonly(production_db_path)
    try:
        open_positions = _count(conn, "SELECT COUNT(*) FROM positions WHERE status='OPEN'", ())
        eth_sol_positions = _count(
            conn,
            "SELECT COUNT(*) FROM positions WHERE symbol IN ('ETHUSDT','SOLUSDT')",
            (),
        )
        tables = tuple(
            row["name"]
            for row in conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('symbol_state', 'portfolio_state')
                ORDER BY name
                """
            )
        )
        return {
            "open_positions": open_positions,
            "eth_sol_positions": eth_sol_positions,
            "multi_asset_tables": tables,
        }
    finally:
        conn.close()


def _count_production_db_touched_true(journal_unit: str | None, *, since: datetime) -> int | None:
    if not journal_unit:
        return None
    try:
        proc = subprocess.run(
            ["journalctl", "-u", journal_unit, "--since", since.isoformat(), "--no-pager"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.count('"production_db_touched": true') + proc.stdout.count('"production_db_touched":true')


def _connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _count(conn: sqlite3.Connection, query: str, params: tuple[object, ...]) -> int:
    return int(conn.execute(query, params).fetchone()[0])


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _to_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate multi-asset shadow evidence checkpoint.")
    parser.add_argument("--shadow-db-path", type=Path, default=Path("research_lab/shadow/multi_asset_shadow.db"))
    parser.add_argument("--production-db-path", type=Path, default=Path("storage/btc_bot.db"))
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--hours", type=int, help="Override --days with an hour-based window.")
    parser.add_argument("--expected-min-cycles", type=int)
    parser.add_argument("--journal-unit", default="multi-asset-shadow.service")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    checkpoint = build_checkpoint(
        shadow_db_path=args.shadow_db_path,
        production_db_path=args.production_db_path,
        days=args.days,
        hours=args.hours,
        expected_min_cycles=args.expected_min_cycles,
        journal_unit=args.journal_unit,
    )
    if args.json:
        content = json.dumps(_checkpoint_to_dict(checkpoint), indent=2, sort_keys=True)
    else:
        content = render_markdown(checkpoint)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)
    return 2 if checkpoint.status == "fail" else 0


def _checkpoint_to_dict(checkpoint: ShadowEvidenceCheckpoint) -> dict[str, Any]:
    payload = asdict(checkpoint)
    payload["symbol_evidence"] = [asdict(item) for item in checkpoint.symbol_evidence]
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
