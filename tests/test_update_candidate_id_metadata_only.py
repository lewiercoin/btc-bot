import json
import sqlite3

from scripts import update_candidate_id_metadata_only as updater


EXPECTED = updater.EXPECTED_ID
TARGET = updater.TARGET_ID


def _make_db(path, candidate_id=EXPECTED, extra_column=True):
    conn = sqlite3.connect(path)
    cols = "id INTEGER PRIMARY KEY, mode TEXT, candidate_id TEXT"
    if not extra_column:
        cols = "id INTEGER PRIMARY KEY, mode TEXT"
    conn.execute(f"CREATE TABLE bot_state ({cols})")
    if extra_column:
        conn.execute(
            "INSERT INTO bot_state (id, mode, candidate_id) VALUES (1, 'PAPER', ?)",
            (candidate_id,),
        )
    else:
        conn.execute("INSERT INTO bot_state (id, mode) VALUES (1, 'PAPER')")
    conn.commit()
    conn.close()


def _read_candidate(path):
    conn = sqlite3.connect(path)
    value = conn.execute("SELECT candidate_id FROM bot_state WHERE id = 1").fetchone()[0]
    conn.close()
    return value


def _make_settings(path, candidate_id=EXPECTED):
    path.write_text(
        json.dumps(
            {
                "deployment": {"candidate_id": candidate_id},
                "strategy": {"min_sweep_depth_pct": 0.005},
                "monitoring": {"candidate_id": candidate_id},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_sqlite_refuses_unexpected_prior(tmp_path):
    db = tmp_path / "state.db"
    _make_db(db, candidate_id="other")

    rc = updater.main(["--db", str(db)])

    assert rc == updater.EXIT_UNEXPECTED_STATE
    assert _read_candidate(db) == "other"


def test_sqlite_updates_when_prior_matches_expected(tmp_path, monkeypatch):
    db = tmp_path / "state.db"
    _make_db(db)
    monkeypatch.setattr(updater, "_operations_dir", lambda: tmp_path)

    rc = updater.main(["--db", str(db)])

    assert rc == updater.EXIT_OK
    assert _read_candidate(db) == TARGET


def test_sqlite_idempotent_on_rerun(tmp_path, monkeypatch):
    db = tmp_path / "state.db"
    _make_db(db, candidate_id=TARGET)
    monkeypatch.setattr(updater, "_operations_dir", lambda: tmp_path)

    rc = updater.main(["--db", str(db)])

    assert rc == updater.EXIT_OK
    assert _read_candidate(db) == TARGET


def test_sqlite_dry_run_writes_no_changes(tmp_path):
    db = tmp_path / "state.db"
    _make_db(db)

    rc = updater.main(["--db", str(db), "--dry-run"])

    assert rc == updater.EXIT_OK
    assert _read_candidate(db) == EXPECTED


def test_verify_only_exit_codes(tmp_path):
    db = tmp_path / "state.db"
    _make_db(db)

    assert updater.main(["--db", str(db), "--verify-only"]) == updater.EXIT_DRIFT_REMAINS

    conn = sqlite3.connect(db)
    conn.execute("UPDATE bot_state SET candidate_id = ? WHERE id = 1", (TARGET,))
    conn.commit()
    conn.close()

    assert updater.main(["--db", str(db), "--verify-only"]) == updater.EXIT_OK

    conn = sqlite3.connect(db)
    conn.execute("UPDATE bot_state SET candidate_id = ? WHERE id = 1", ("other",))
    conn.commit()
    conn.close()

    assert updater.main(["--db", str(db), "--verify-only"]) == updater.EXIT_UNEXPECTED_STATE


def test_sqlite_refuses_missing_candidate_id_column(tmp_path):
    db = tmp_path / "state.db"
    _make_db(db, extra_column=False)

    rc = updater.main(["--db", str(db)])

    assert rc == updater.EXIT_UNEXPECTED_STATE
    conn = sqlite3.connect(db)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(bot_state)").fetchall()]
    conn.close()
    assert cols == ["id", "mode"]


def test_json_updates_only_candidate_id_fields(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    _make_settings(settings)
    monkeypatch.setattr(updater, "_operations_dir", lambda: tmp_path)

    before = json.loads(settings.read_text(encoding="utf-8"))
    rc = updater.main(["--settings-json", str(settings)])
    after = json.loads(settings.read_text(encoding="utf-8"))

    assert rc == updater.EXIT_OK
    assert after["deployment"]["candidate_id"] == TARGET
    assert after["monitoring"]["candidate_id"] == TARGET
    assert after["strategy"] == before["strategy"]
