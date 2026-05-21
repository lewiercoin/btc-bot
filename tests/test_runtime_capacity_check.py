from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from scripts.runtime_capacity_check import (
    GB,
    MB,
    CapacitySnapshot,
    CapacityThresholds,
    _read_latest_shadow_resource,
    _read_runtime_metrics,
    _parse_latest_cycle_duration_from_log,
    evaluate_capacity,
)


def _snapshot(**overrides) -> CapacitySnapshot:
    values = {
        "timestamp_utc": "2026-05-21T14:45:00+00:00",
        "disk_total_bytes": 75 * GB,
        "disk_free_bytes": 17 * GB,
        "disk_used_pct": 78.0,
        "memory_total_bytes": 4 * GB,
        "memory_available_bytes": 3 * GB,
        "load1": 0.2,
        "cpu_count": 2,
        "bot_pid": 123,
        "bot_rss_bytes": 82 * MB,
        "last_cycle_duration_sec": 12.0,
        "last_decision_outcome": "no_signal",
        "last_decision_finished_at": "2026-05-21T14:45:12+00:00",
        "shadow_rss_bytes": 26 * MB,
        "shadow_guard_status": "pass",
        "shadow_sample_at": "2026-05-21T14:36:48Z",
    }
    values.update(overrides)
    return CapacitySnapshot(**values)


def test_evaluate_capacity_passes_current_server_like_snapshot() -> None:
    result = evaluate_capacity(_snapshot(), CapacityThresholds())

    assert result.status == "pass"
    assert result.failures == ()
    assert result.warnings == ()


def test_evaluate_capacity_fails_activation_blockers() -> None:
    result = evaluate_capacity(
        _snapshot(
            disk_used_pct=91.0,
            disk_free_bytes=4 * GB,
            memory_available_bytes=512 * MB,
            load1=4.0,
            cpu_count=2,
            bot_rss_bytes=700 * MB,
            last_cycle_duration_sec=75.0,
            shadow_rss_bytes=300 * MB,
            shadow_guard_status="fail",
        ),
        CapacityThresholds(),
    )

    assert result.status == "fail"
    assert any("disk_used_pct" in failure for failure in result.failures)
    assert any("disk_free_gb" in failure for failure in result.failures)
    assert any("memory_available_gb" in failure for failure in result.failures)
    assert any("load1_per_cpu" in failure for failure in result.failures)
    assert any("bot_rss_mb" in failure for failure in result.failures)
    assert any("last_cycle_duration_sec" in failure for failure in result.failures)
    assert any("shadow_rss_mb" in failure for failure in result.failures)
    assert "shadow_guard_status=fail" in result.failures


def test_read_runtime_metrics_derives_last_cycle_duration(tmp_path: Path) -> None:
    db_path = tmp_path / "bot.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE runtime_metrics (
            id INTEGER PRIMARY KEY,
            last_decision_cycle_started_at TEXT,
            last_decision_cycle_finished_at TEXT,
            last_decision_outcome TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO runtime_metrics (
            id, last_decision_cycle_started_at, last_decision_cycle_finished_at,
            last_decision_outcome
        ) VALUES (1, ?, ?, ?)
        """,
        (
            "2026-05-21T14:15:00+00:00",
            "2026-05-21T14:15:11+00:00",
            "no_signal",
        ),
    )
    conn.commit()
    conn.close()

    metrics = _read_runtime_metrics(
        db_path,
        now=datetime(2026, 5, 21, 14, 16, tzinfo=timezone.utc),
    )

    assert metrics["last_cycle_duration_sec"] == 11.0
    assert metrics["last_decision_outcome"] == "no_signal"


def test_runtime_metrics_ignores_equal_logical_cycle_timestamps(tmp_path: Path) -> None:
    db_path = tmp_path / "bot.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE runtime_metrics (
            id INTEGER PRIMARY KEY,
            last_decision_cycle_started_at TEXT,
            last_decision_cycle_finished_at TEXT,
            last_decision_outcome TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO runtime_metrics (
            id, last_decision_cycle_started_at, last_decision_cycle_finished_at,
            last_decision_outcome
        ) VALUES (1, ?, ?, ?)
        """,
        (
            "2026-05-21T14:15:00+00:00",
            "2026-05-21T14:15:00+00:00",
            "no_signal",
        ),
    )
    conn.commit()
    conn.close()

    metrics = _read_runtime_metrics(
        db_path,
        now=datetime(2026, 5, 21, 14, 16, tzinfo=timezone.utc),
    )

    assert metrics["last_cycle_duration_sec"] is None


def test_parse_latest_cycle_duration_from_journal_log() -> None:
    log_text = """
    May 21 14:15:11 host python[1]: Decision cycle finished | duration_ms=11079.4
    May 21 14:30:08 host python[1]: Decision cycle finished | duration_ms=8123.0
    """

    assert _parse_latest_cycle_duration_from_log(log_text) == 8.123


def test_read_latest_shadow_resource_returns_latest_sample(tmp_path: Path) -> None:
    db_path = tmp_path / "shadow.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE shadow_resource_samples (
            id INTEGER PRIMARY KEY,
            timestamp_utc TEXT NOT NULL,
            memory_rss_bytes INTEGER NOT NULL,
            guard_status TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO shadow_resource_samples (
            id, timestamp_utc, memory_rss_bytes, guard_status
        ) VALUES (1, 'old', 10, 'pass'), (2, 'new', 20, 'pass')
        """
    )
    conn.commit()
    conn.close()

    sample = _read_latest_shadow_resource(db_path)

    assert sample["timestamp_utc"] == "new"
    assert sample["memory_rss_bytes"] == 20
