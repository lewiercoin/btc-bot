from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from research_lab import shadow_orchestrator
from research_lab.shadow_orchestrator import DISALLOWED_IMPORT_ROOTS, _import_roots_from_file, run_cycle_once
from research_lab.shadow_schema import SHADOW_DB_DEFAULT


def create_production_db(repo_root: Path) -> Path:
    storage_dir = repo_root / "storage"
    storage_dir.mkdir()
    production_db = storage_dir / "btc_bot.db"
    with sqlite3.connect(production_db) as conn:
        conn.execute("CREATE TABLE sentinel (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO sentinel (value) VALUES ('before')")
        conn.commit()
    return production_db


def test_cycle_once_operational_heartbeat(tmp_path: Path) -> None:
    production_db = create_production_db(tmp_path)
    before = production_db.read_bytes()

    result = run_cycle_once(
        db_path=SHADOW_DB_DEFAULT,
        lock_path=tmp_path / "multi-asset-shadow.lock",
        repo_root=tmp_path,
        min_disk_free_bytes=1,
    )

    assert result.operational_mode == "operational_heartbeat"
    assert result.production_db_touched is False
    assert result.production_db_signature_changed is False
    assert production_db.read_bytes() == before
    assert result.decision_rows == 3
    assert result.near_miss_rows == 0
    assert result.resource_rows == 1

    with sqlite3.connect(result.db_path) as conn:
        run_row = conn.execute(
            "SELECT dry_run FROM shadow_runs WHERE shadow_run_id = ?",
            (result.shadow_run_id,),
        ).fetchone()
        assert run_row == (0,)

        blockers = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT signal_blocker FROM shadow_decision_outcomes"
            ).fetchall()
        }
        assert blockers == {"operational_heartbeat"}


def test_cycle_once_resource_guard_enforced(tmp_path: Path) -> None:
    create_production_db(tmp_path)

    exit_code = shadow_orchestrator.main(
        [
            "--cycle-once",
            "--repo-root",
            str(tmp_path),
            "--db-path",
            SHADOW_DB_DEFAULT.as_posix(),
            "--lock-path",
            str(tmp_path / "multi-asset-shadow.lock"),
            "--min-disk-free-gb",
            "999999999",
        ]
    )

    assert exit_code == 1


def test_cycle_once_exits_nonzero_if_production_touched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    create_production_db(tmp_path)
    monkeypatch.setattr(shadow_orchestrator, "production_db_opened_by_process", lambda _root: True)

    exit_code = shadow_orchestrator.main(
        [
            "--cycle-once",
            "--repo-root",
            str(tmp_path),
            "--db-path",
            SHADOW_DB_DEFAULT.as_posix(),
            "--lock-path",
            str(tmp_path / "multi-asset-shadow.lock"),
            "--min-disk-free-gb",
            "0.000001",
        ]
    )

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert exit_code == 1
    assert payload["production_db_touched"] is True


def test_cycle_once_signature_change_is_warning_not_touch_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    create_production_db(tmp_path)
    signatures = iter(
        [
            (True, 100, 1.0),
            (True, 101, 2.0),
        ]
    )
    monkeypatch.setattr(shadow_orchestrator, "production_db_signature", lambda _root: next(signatures))
    monkeypatch.setattr(shadow_orchestrator, "production_db_opened_by_process", lambda _root: False)

    exit_code = shadow_orchestrator.main(
        [
            "--cycle-once",
            "--repo-root",
            str(tmp_path),
            "--db-path",
            SHADOW_DB_DEFAULT.as_posix(),
            "--lock-path",
            str(tmp_path / "multi-asset-shadow.lock"),
            "--min-disk-free-gb",
            "0.000001",
        ]
    )

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert exit_code == 0
    assert payload["production_db_touched"] is False
    assert payload["production_db_signature_changed"] is True


def test_cycle_once_import_guard_has_no_market_or_signal_generation_imports() -> None:
    source_paths = (
        Path("sidecar_main.py"),
        Path("research_lab/shadow_orchestrator.py"),
        Path("research_lab/shadow_schema.py"),
    )
    for path in source_paths:
        roots = _import_roots_from_file(path)
        assert roots.isdisjoint(DISALLOWED_IMPORT_ROOTS)


def test_systemd_units_use_oneshot_cycle_once_and_resource_caps() -> None:
    service = Path("multi-asset-shadow.service").read_text(encoding="utf-8")
    timer = Path("multi-asset-shadow.timer").read_text(encoding="utf-8")

    assert "Type=oneshot" in service
    assert "sidecar_main.py --cycle-once" in service
    assert "User=btc-bot" in service
    assert "Nice=10" in service
    assert "MemoryMax=512M" in service
    assert "CPUQuota=50%" in service
    assert "OnUnitActiveSec=15min" in timer
    assert "Requires=btc-bot.service" in timer


def test_deployment_scripts_preserve_btc_service_boundaries() -> None:
    deploy = Path("scripts/deploy_shadow_sidecar.sh").read_text(encoding="utf-8")
    status = Path("scripts/shadow_sidecar_status.sh").read_text(encoding="utf-8")

    assert "systemctl is-active --quiet btc-bot" in deploy
    assert "systemctl start \"${TIMER_NAME}\"" in deploy
    assert "systemctl start \"${SERVICE_NAME}\"" in deploy
    assert "systemctl restart btc-bot" not in deploy
    assert "systemctl stop btc-bot" not in deploy
    assert "production DB signature changed" in deploy
    assert "journalctl -u multi-asset-shadow.service" in status
    assert "main.py --mode PAPER" in status
