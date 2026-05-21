from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from research_lab.shadow_orchestrator import (
    BTC_RUNTIME_LOCK_PATH,
    SIDECAR_LOCK_DEFAULT,
    ShadowGuardError,
    assert_no_order_path_imports,
    ensure_lock_separation,
    run_dry_run,
)
from research_lab.shadow_schema import SHADOW_DB_DEFAULT, ShadowPathError, resolve_shadow_db_path


def test_sidecar_lock_is_distinct_from_btc_runtime_lock() -> None:
    assert SIDECAR_LOCK_DEFAULT != BTC_RUNTIME_LOCK_PATH
    ensure_lock_separation(SIDECAR_LOCK_DEFAULT)


def test_sidecar_lock_rejects_btc_runtime_lock() -> None:
    with pytest.raises(ShadowGuardError):
        ensure_lock_separation(BTC_RUNTIME_LOCK_PATH)


def test_shadow_db_path_must_stay_under_research_lab_shadow(tmp_path: Path) -> None:
    allowed = resolve_shadow_db_path(SHADOW_DB_DEFAULT, repo_root=tmp_path)
    assert allowed == tmp_path / "research_lab" / "shadow" / "multi_asset_shadow.db"

    with pytest.raises(ShadowPathError):
        resolve_shadow_db_path(tmp_path / "storage" / "btc_bot.db", repo_root=tmp_path)

    with pytest.raises(ShadowPathError):
        resolve_shadow_db_path(tmp_path / "research_lab" / "snapshots" / "shadow.db", repo_root=tmp_path)


def test_order_path_import_guard_rejects_execution_import(tmp_path: Path) -> None:
    bad_source = tmp_path / "bad_sidecar.py"
    bad_source.write_text("from execution.paper_execution_engine import PaperExecutionEngine\n", encoding="utf-8")

    with pytest.raises(ShadowGuardError):
        assert_no_order_path_imports((bad_source,))


def test_dry_run_writes_shadow_db_only_and_leaves_production_db_untouched(tmp_path: Path) -> None:
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    production_db = storage_dir / "btc_bot.db"
    with sqlite3.connect(production_db) as conn:
        conn.execute("CREATE TABLE sentinel (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO sentinel (value) VALUES ('before')")
        conn.commit()
    before = production_db.read_bytes()

    result = run_dry_run(
        db_path=SHADOW_DB_DEFAULT,
        lock_path=tmp_path / "multi-asset-shadow.lock",
        repo_root=tmp_path,
        min_disk_free_bytes=1,
    )

    assert result.production_db_touched is False
    assert result.production_db_signature_changed is False
    assert production_db.read_bytes() == before
    assert result.db_path == tmp_path / "research_lab" / "shadow" / "multi_asset_shadow.db"
    assert result.decision_rows == 3
    assert result.near_miss_rows == 1
    assert result.resource_rows == 1

    with sqlite3.connect(result.db_path) as conn:
        with sqlite3.connect(production_db) as prod_conn:
            prod_tables = prod_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        assert prod_tables == [("sentinel",)]
        shadow_tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert "shadow_decision_outcomes" in shadow_tables
    assert "sentinel" not in shadow_tables
