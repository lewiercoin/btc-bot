#!/usr/bin/env python3
"""Check runtime capacity guardrails before multi-asset PAPER activation."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GB = 1024**3
MB = 1024**2


@dataclass(frozen=True, slots=True)
class CapacityThresholds:
    max_disk_used_pct: float = 85.0
    min_disk_free_gb: float = 12.0
    min_memory_available_gb: float = 1.0
    max_load1_per_cpu: float = 0.75
    max_bot_rss_mb: float = 512.0
    max_shadow_rss_mb: float = 256.0
    max_last_cycle_duration_sec: float = 60.0


DEFAULT_THRESHOLDS = CapacityThresholds()


@dataclass(frozen=True, slots=True)
class CapacitySnapshot:
    timestamp_utc: str
    disk_total_bytes: int
    disk_free_bytes: int
    disk_used_pct: float
    memory_total_bytes: int | None
    memory_available_bytes: int | None
    load1: float | None
    cpu_count: int
    bot_pid: int | None
    bot_rss_bytes: int | None
    last_cycle_duration_sec: float | None
    last_decision_outcome: str | None
    last_decision_finished_at: str | None
    shadow_rss_bytes: int | None
    shadow_guard_status: str | None
    shadow_sample_at: str | None


@dataclass(frozen=True, slots=True)
class CapacityEvaluation:
    status: str
    failures: tuple[str, ...]
    warnings: tuple[str, ...]


def collect_capacity_snapshot(
    *,
    disk_path: Path,
    db_path: Path,
    shadow_db_path: Path,
    bot_pid: int | None = None,
    journal_unit: str | None = "btc-bot.service",
    now: datetime | None = None,
) -> CapacitySnapshot:
    ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    disk = shutil.disk_usage(disk_path)
    memory = _read_meminfo()
    load1 = _load1()
    runtime = _read_runtime_metrics(db_path, now=ts)
    journal_cycle_duration = _read_latest_cycle_duration_from_journal(journal_unit) if journal_unit else None
    shadow = _read_latest_shadow_resource(shadow_db_path)
    rss = _read_process_rss(bot_pid) if bot_pid else None

    return CapacitySnapshot(
        timestamp_utc=ts.isoformat(),
        disk_total_bytes=int(disk.total),
        disk_free_bytes=int(disk.free),
        disk_used_pct=(float(disk.used) / float(disk.total)) * 100.0 if disk.total else 100.0,
        memory_total_bytes=memory.get("MemTotal"),
        memory_available_bytes=memory.get("MemAvailable"),
        load1=load1,
        cpu_count=max(os.cpu_count() or 1, 1),
        bot_pid=bot_pid,
        bot_rss_bytes=rss,
        last_cycle_duration_sec=journal_cycle_duration or runtime.get("last_cycle_duration_sec"),
        last_decision_outcome=runtime.get("last_decision_outcome"),
        last_decision_finished_at=runtime.get("last_decision_finished_at"),
        shadow_rss_bytes=shadow.get("memory_rss_bytes"),
        shadow_guard_status=shadow.get("guard_status"),
        shadow_sample_at=shadow.get("timestamp_utc"),
    )


def evaluate_capacity(snapshot: CapacitySnapshot, thresholds: CapacityThresholds) -> CapacityEvaluation:
    failures: list[str] = []
    warnings: list[str] = []

    if snapshot.disk_used_pct > thresholds.max_disk_used_pct:
        failures.append(
            f"disk_used_pct {snapshot.disk_used_pct:.1f} > {thresholds.max_disk_used_pct:.1f}"
        )
    if snapshot.disk_free_bytes < thresholds.min_disk_free_gb * GB:
        failures.append(
            f"disk_free_gb {snapshot.disk_free_bytes / GB:.1f} < {thresholds.min_disk_free_gb:.1f}"
        )
    if snapshot.memory_available_bytes is None:
        warnings.append("memory_available_unavailable")
    elif snapshot.memory_available_bytes < thresholds.min_memory_available_gb * GB:
        failures.append(
            "memory_available_gb "
            f"{snapshot.memory_available_bytes / GB:.1f} < {thresholds.min_memory_available_gb:.1f}"
        )
    if snapshot.load1 is None:
        warnings.append("load1_unavailable")
    else:
        load_per_cpu = snapshot.load1 / max(snapshot.cpu_count, 1)
        if load_per_cpu > thresholds.max_load1_per_cpu:
            failures.append(
                f"load1_per_cpu {load_per_cpu:.2f} > {thresholds.max_load1_per_cpu:.2f}"
            )
    if snapshot.bot_pid is None:
        warnings.append("bot_pid_not_provided")
    elif snapshot.bot_rss_bytes is None:
        warnings.append("bot_rss_unavailable")
    elif snapshot.bot_rss_bytes > thresholds.max_bot_rss_mb * MB:
        failures.append(f"bot_rss_mb {snapshot.bot_rss_bytes / MB:.1f} > {thresholds.max_bot_rss_mb:.1f}")
    if snapshot.last_cycle_duration_sec is None:
        warnings.append("last_cycle_duration_unavailable")
    elif snapshot.last_cycle_duration_sec > thresholds.max_last_cycle_duration_sec:
        failures.append(
            "last_cycle_duration_sec "
            f"{snapshot.last_cycle_duration_sec:.1f} > {thresholds.max_last_cycle_duration_sec:.1f}"
        )
    if snapshot.shadow_rss_bytes is None:
        warnings.append("shadow_resource_sample_unavailable")
    elif snapshot.shadow_rss_bytes > thresholds.max_shadow_rss_mb * MB:
        failures.append(f"shadow_rss_mb {snapshot.shadow_rss_bytes / MB:.1f} > {thresholds.max_shadow_rss_mb:.1f}")
    if snapshot.shadow_guard_status not in (None, "pass"):
        failures.append(f"shadow_guard_status={snapshot.shadow_guard_status}")

    status = "fail" if failures else "warn" if warnings else "pass"
    return CapacityEvaluation(status=status, failures=tuple(failures), warnings=tuple(warnings))


def _read_runtime_metrics(db_path: Path, *, now: datetime) -> dict[str, Any]:
    if not db_path.exists():
        return {}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """
                SELECT last_decision_cycle_started_at, last_decision_cycle_finished_at,
                       last_decision_outcome
                FROM runtime_metrics
                WHERE id = 1
                """
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return {}
    if row is None:
        return {}
    started = _parse_dt(row["last_decision_cycle_started_at"])
    finished = _parse_dt(row["last_decision_cycle_finished_at"])
    duration = None
    if started and finished and finished > started:
        duration = (finished - started).total_seconds()
    elif started and not finished:
        duration = (now - started).total_seconds()
    return {
        "last_cycle_duration_sec": duration,
        "last_decision_outcome": row["last_decision_outcome"],
        "last_decision_finished_at": row["last_decision_cycle_finished_at"],
    }


def _read_latest_shadow_resource(shadow_db_path: Path) -> dict[str, Any]:
    if not shadow_db_path.exists():
        return {}
    try:
        conn = sqlite3.connect(shadow_db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """
                SELECT timestamp_utc, memory_rss_bytes, guard_status
                FROM shadow_resource_samples
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return {}
    return dict(row) if row else {}


def _parse_latest_cycle_duration_from_log(log_text: str) -> float | None:
    latest: float | None = None
    for line in log_text.splitlines():
        if "Decision cycle finished" not in line:
            continue
        match = re.search(r"duration_ms=([0-9]+(?:\.[0-9]+)?)", line)
        if match:
            latest = float(match.group(1)) / 1000.0
    return latest


def _read_latest_cycle_duration_from_journal(unit: str | None) -> float | None:
    if not unit:
        return None
    try:
        proc = subprocess.run(
            ["journalctl", "-u", unit, "-n", "200", "--no-pager"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return _parse_latest_cycle_duration_from_log(proc.stdout)


def _read_meminfo(path: Path = Path("/proc/meminfo")) -> dict[str, int]:
    if not path.exists():
        return {}
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            key = parts[0].rstrip(":")
            try:
                values[key] = int(parts[1]) * 1024
            except ValueError:
                continue
    return values


def _read_process_rss(pid: int | None) -> int | None:
    if not pid:
        return None
    status_path = Path("/proc") / str(pid) / "status"
    if not status_path.exists():
        return None
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2:
                return int(parts[1]) * 1024
    return None


def _load1() -> float | None:
    try:
        return float(os.getloadavg()[0])
    except (AttributeError, OSError):
        return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check runtime capacity guardrails.")
    parser.add_argument("--db-path", type=Path, default=Path("storage/btc_bot.db"))
    parser.add_argument("--shadow-db-path", type=Path, default=Path("research_lab/shadow/multi_asset_shadow.db"))
    parser.add_argument("--disk-path", type=Path, default=Path("."))
    parser.add_argument("--bot-pid", type=int, default=None)
    parser.add_argument("--journal-unit", default="btc-bot.service")
    parser.add_argument("--max-disk-used-pct", type=float, default=DEFAULT_THRESHOLDS.max_disk_used_pct)
    parser.add_argument("--min-disk-free-gb", type=float, default=DEFAULT_THRESHOLDS.min_disk_free_gb)
    parser.add_argument("--min-memory-available-gb", type=float, default=DEFAULT_THRESHOLDS.min_memory_available_gb)
    parser.add_argument("--max-load1-per-cpu", type=float, default=DEFAULT_THRESHOLDS.max_load1_per_cpu)
    parser.add_argument("--max-bot-rss-mb", type=float, default=DEFAULT_THRESHOLDS.max_bot_rss_mb)
    parser.add_argument("--max-shadow-rss-mb", type=float, default=DEFAULT_THRESHOLDS.max_shadow_rss_mb)
    parser.add_argument(
        "--max-last-cycle-duration-sec",
        type=float,
        default=DEFAULT_THRESHOLDS.max_last_cycle_duration_sec,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    thresholds = CapacityThresholds(
        max_disk_used_pct=args.max_disk_used_pct,
        min_disk_free_gb=args.min_disk_free_gb,
        min_memory_available_gb=args.min_memory_available_gb,
        max_load1_per_cpu=args.max_load1_per_cpu,
        max_bot_rss_mb=args.max_bot_rss_mb,
        max_shadow_rss_mb=args.max_shadow_rss_mb,
        max_last_cycle_duration_sec=args.max_last_cycle_duration_sec,
    )
    snapshot = collect_capacity_snapshot(
        disk_path=args.disk_path,
        db_path=args.db_path,
        shadow_db_path=args.shadow_db_path,
        bot_pid=args.bot_pid,
        journal_unit=args.journal_unit,
    )
    evaluation = evaluate_capacity(snapshot, thresholds)
    print(
        json.dumps(
            {
                "status": evaluation.status,
                "failures": list(evaluation.failures),
                "warnings": list(evaluation.warnings),
                "thresholds": asdict(thresholds),
                "snapshot": asdict(snapshot),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 2 if evaluation.status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
