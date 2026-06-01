"""Tests that monitor_trial_00095.py reads candidate_id dynamically from settings.json."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from scripts.monitor_trial_00095 import _load_monitoring_config, evaluate, main


def _make_settings(path, candidate_id="test-candidate-xyz"):
    """Create a minimal settings.json with the given candidate_id."""
    payload = {
        "deployment": {"candidate_id": candidate_id},
        "monitoring": {
            "candidate_id": candidate_id,
            "deployment_start_utc": "2026-01-01T00:00:00Z",
            "hard_stop_after_trades": 30,
            "hard_stop_min_expectancy_r": 1.0,
            "review_pf_after_30_trades_below": 3.0,
            "review_drawdown_pct_above": 0.10,
            "frequency_review_consecutive_months": 3,
            "frequency_review_min_trades_per_month": 1,
            "early_review_min_trades": 10,
            "early_review_months_min": 3.0,
            "paper_only": True,
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _make_settings_missing_candidate_id(path):
    """Create a settings.json without monitoring.candidate_id."""
    payload = {
        "deployment": {"candidate_id": "test-candidate-xyz"},
        "monitoring": {
            "deployment_start_utc": "2026-01-01T00:00:00Z",
            "hard_stop_after_trades": 30,
            "hard_stop_min_expectancy_r": 1.0,
            "review_pf_after_30_trades_below": 3.0,
            "review_drawdown_pct_above": 0.10,
            "frequency_review_consecutive_months": 3,
            "frequency_review_min_trades_per_month": 1,
            "early_review_min_trades": 10,
            "early_review_months_min": 3.0,
            "paper_only": True,
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _make_db(path):
    """Create a minimal SQLite DB with the tables the monitor needs."""
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE trade_log (
            trade_id TEXT PRIMARY KEY,
            opened_at TEXT,
            closed_at TEXT,
            pnl_abs REAL,
            pnl_r REAL,
            exit_reason TEXT,
            config_hash TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE bot_state (
            id INTEGER PRIMARY KEY,
            mode TEXT,
            healthy INTEGER DEFAULT 1,
            safe_mode INTEGER DEFAULT 0,
            last_error TEXT,
            safe_mode_entry_at TEXT,
            timestamp TEXT
        )
        """
    )
    conn.execute("INSERT INTO bot_state (id, mode) VALUES (1, 'PAPER')")
    conn.commit()
    conn.close()


def test_evaluate_reads_candidate_id_from_config(tmp_path):
    """evaluate() returns the candidate_id from the monitoring config, not a hardcoded value."""
    settings_path = tmp_path / "settings.json"
    _make_settings(settings_path, candidate_id="test-candidate-xyz")
    db_path = tmp_path / "test.db"
    _make_db(db_path)

    config = _load_monitoring_config(settings_path)
    conn = sqlite3.connect(str(db_path))
    try:
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = evaluate(conn, config, now=now)
    finally:
        conn.close()

    assert result["candidate_id"] == "test-candidate-xyz"


def test_evaluate_uses_different_candidate_id(tmp_path):
    """evaluate() uses whatever candidate_id is in monitoring config — not a static literal."""
    settings_path = tmp_path / "settings.json"
    _make_settings(settings_path, candidate_id="experiment-profile-permissive-v1")
    db_path = tmp_path / "test.db"
    _make_db(db_path)

    config = _load_monitoring_config(settings_path)
    conn = sqlite3.connect(str(db_path))
    try:
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = evaluate(conn, config, now=now)
    finally:
        conn.close()

    assert result["candidate_id"] == "experiment-profile-permissive-v1"


def test_main_fails_loudly_when_candidate_id_missing(tmp_path, monkeypatch, capsys):
    """main() exits non-zero with a clear error when monitoring.candidate_id is absent."""
    settings_path = tmp_path / "settings.json"
    _make_settings_missing_candidate_id(settings_path)
    db_path = tmp_path / "test.db"
    _make_db(db_path)

    monkeypatch.setattr(
        "sys.argv",
        [
            "monitor_trial_00095.py",
            "--db", str(db_path),
            "--settings", str(settings_path),
            "--output-json", str(tmp_path / "out.json"),
        ],
    )

    rc = main()

    assert rc != 0
    captured = capsys.readouterr()
    assert "candidate_id" in captured.err.lower() or "candidate_id" in captured.err


def test_main_writes_dynamic_candidate_id_to_output(tmp_path, monkeypatch):
    """main() writes the dynamic candidate_id into the output JSON file."""
    settings_path = tmp_path / "settings.json"
    _make_settings(settings_path, candidate_id="test-candidate-xyz")
    db_path = tmp_path / "test.db"
    _make_db(db_path)
    output_path = tmp_path / "monitoring_output.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "monitor_trial_00095.py",
            "--db", str(db_path),
            "--settings", str(settings_path),
            "--output-json", str(output_path),
        ],
    )

    rc = main()

    assert rc == 0
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["candidate_id"] == "test-candidate-xyz"
