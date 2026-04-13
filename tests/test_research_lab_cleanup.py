from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_lab.artifact_cleanup import cleanup_artifacts, collect_artifact_cleanup_candidates


def _write_file(path: Path, *, contents: bytes, modified_at_utc: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    timestamp = modified_at_utc.timestamp()
    os.utime(path, (timestamp, timestamp))


def test_collect_artifact_cleanup_candidates_only_targets_known_artifacts(tmp_path: Path) -> None:
    now_utc = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    old_utc = now_utc - timedelta(days=10)
    recent_utc = now_utc - timedelta(days=1)

    _write_file(tmp_path / "research_lab" / "snapshots" / "trial-old.db", contents=b"a" * 10, modified_at_utc=old_utc)
    _write_file(tmp_path / "research_lab" / "snapshots" / "trial-fresh.db", contents=b"b" * 11, modified_at_utc=recent_utc)
    _write_file(
        tmp_path / "research_lab_runs" / "baseline" / "snapshots" / "wf-old.db",
        contents=b"c" * 12,
        modified_at_utc=old_utc,
    )
    _write_file(
        tmp_path / "research_lab_runs" / "snapshot_benchmark" / "bench-001.db",
        contents=b"d" * 13,
        modified_at_utc=old_utc,
    )
    _write_file(tmp_path / "research_lab" / "research_lab.db", contents=b"e" * 14, modified_at_utc=old_utc)
    _write_file(tmp_path / "storage" / "btc_bot.db", contents=b"f" * 15, modified_at_utc=old_utc)
    _write_file(tmp_path / "research_lab_runs" / "search-v1" / "store.db", contents=b"g" * 16, modified_at_utc=old_utc)

    _, candidates = collect_artifact_cleanup_candidates(
        tmp_path,
        older_than_days=7,
        now_utc=now_utc,
    )

    assert [candidate.path.relative_to(tmp_path).as_posix() for candidate in candidates] == [
        "research_lab/snapshots/trial-old.db",
        "research_lab_runs/baseline/snapshots/wf-old.db",
        "research_lab_runs/snapshot_benchmark/bench-001.db",
    ]


def test_cleanup_artifacts_dry_run_reports_space_without_deleting(tmp_path: Path) -> None:
    now_utc = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    old_utc = now_utc - timedelta(days=14)

    target = tmp_path / "research_lab" / "snapshots" / "trial-old.db"
    _write_file(target, contents=b"x" * 21, modified_at_utc=old_utc)

    summary = cleanup_artifacts(
        tmp_path,
        older_than_days=7,
        dry_run=True,
        now_utc=now_utc,
    )

    assert target.exists()
    assert summary["dry_run"] is True
    assert summary["matched_files"] == 1
    assert summary["matched_bytes"] == 21
    assert summary["deleted_files"] == 0
    assert summary["deleted_bytes"] == 0


def test_cleanup_artifacts_deletes_only_stale_generated_files(tmp_path: Path) -> None:
    now_utc = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    old_utc = now_utc - timedelta(days=10)
    recent_utc = now_utc - timedelta(hours=6)

    stale_trial = tmp_path / "research_lab" / "snapshots" / "trial-old.db"
    stale_run = tmp_path / "research_lab_runs" / "baseline" / "snapshots" / "wf-old.db"
    keep_runtime = tmp_path / "storage" / "btc_bot.db"
    keep_recent = tmp_path / "research_lab" / "snapshots" / "trial-fresh.db"

    _write_file(stale_trial, contents=b"a" * 31, modified_at_utc=old_utc)
    _write_file(stale_run, contents=b"b" * 32, modified_at_utc=old_utc)
    _write_file(keep_runtime, contents=b"c" * 33, modified_at_utc=old_utc)
    _write_file(keep_recent, contents=b"d" * 34, modified_at_utc=recent_utc)

    summary = cleanup_artifacts(
        tmp_path,
        older_than_days=7,
        dry_run=False,
        now_utc=now_utc,
    )

    assert not stale_trial.exists()
    assert not stale_run.exists()
    assert keep_runtime.exists()
    assert keep_recent.exists()
    assert summary["deleted_files"] == 2
    assert summary["deleted_bytes"] == 63
