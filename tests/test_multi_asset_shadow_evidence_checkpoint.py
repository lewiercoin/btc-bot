from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from research_lab.shadow_schema import initialize_shadow_schema
from scripts.multi_asset_shadow_evidence_checkpoint import build_checkpoint, render_markdown
from storage.db import init_db


def test_shadow_evidence_checkpoint_passes_complete_window(tmp_path: Path) -> None:
    shadow_db = tmp_path / "shadow.db"
    production_db = tmp_path / "prod.db"
    _seed_shadow_db(shadow_db)
    _seed_production_db(production_db)

    checkpoint = build_checkpoint(
        shadow_db_path=shadow_db,
        production_db_path=production_db,
        days=1,
        expected_min_cycles=2,
        now=datetime(2026, 5, 21, 13, 0, tzinfo=timezone.utc),
        journal_unit=None,
    )

    assert checkpoint.status == "warn"
    assert checkpoint.observed_shadow_runs == 2
    assert checkpoint.observed_complete_cycles == 2
    assert checkpoint.production_eth_sol_positions == 0
    assert checkpoint.production_multi_asset_tables == ()
    assert checkpoint.symbol_evidence[0].symbol == "BTCUSDT"
    assert checkpoint.symbol_evidence[0].decision_rows == 2
    assert checkpoint.symbol_evidence[1].symbol == "ETHUSDT"
    assert checkpoint.symbol_evidence[1].min_sweep_depth_pct_min == 0.0075
    assert checkpoint.failures == ()
    assert checkpoint.warnings == ("production_db_touched_journal_unavailable",)


def test_shadow_evidence_checkpoint_fails_missing_cycles_and_eth_position(tmp_path: Path) -> None:
    shadow_db = tmp_path / "shadow.db"
    production_db = tmp_path / "prod.db"
    _seed_shadow_db(shadow_db, complete_cycles=1)
    _seed_production_db(production_db, eth_position=True)

    checkpoint = build_checkpoint(
        shadow_db_path=shadow_db,
        production_db_path=production_db,
        days=1,
        expected_min_cycles=2,
        now=datetime(2026, 5, 21, 13, 0, tzinfo=timezone.utc),
        journal_unit=None,
    )

    assert checkpoint.status == "fail"
    assert "complete_cycles 1 < expected_min_cycles 2" in checkpoint.failures
    assert "production_eth_sol_positions=1" in checkpoint.failures


def test_render_markdown_includes_per_symbol_table(tmp_path: Path) -> None:
    shadow_db = tmp_path / "shadow.db"
    production_db = tmp_path / "prod.db"
    _seed_shadow_db(shadow_db)
    _seed_production_db(production_db)

    checkpoint = build_checkpoint(
        shadow_db_path=shadow_db,
        production_db_path=production_db,
        days=1,
        expected_min_cycles=2,
        now=datetime(2026, 5, 21, 13, 0, tzinfo=timezone.utc),
        journal_unit=None,
    )

    report = render_markdown(checkpoint)

    assert "# Multi-Asset Shadow Evidence Checkpoint" in report
    assert "| BTCUSDT | 2 | 0 | 0 | 0 | 2 | 0.0065 | 0.0065 |" in report
    assert "| ETHUSDT | 2 | 0 | 0 | 0 | 2 | 0.0075 | 0.0075 |" in report
    assert "Read-only checkpoint" in report


def test_shadow_evidence_checkpoint_supports_hour_window(tmp_path: Path) -> None:
    shadow_db = tmp_path / "shadow.db"
    production_db = tmp_path / "prod.db"
    _seed_shadow_db(shadow_db)
    _seed_production_db(production_db)

    checkpoint = build_checkpoint(
        shadow_db_path=shadow_db,
        production_db_path=production_db,
        hours=2,
        expected_min_cycles=2,
        now=datetime(2026, 5, 21, 13, 0, tzinfo=timezone.utc),
        journal_unit=None,
    )

    assert checkpoint.window_start_utc == "2026-05-21T11:00:00Z"
    assert checkpoint.observed_complete_cycles == 2


def _seed_shadow_db(path: Path, *, complete_cycles: int = 2) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    initialize_shadow_schema(conn)
    timestamps = ("2026-05-21T11:00:00Z", "2026-05-21T12:00:00Z")[:complete_cycles]
    for index, ts in enumerate(timestamps, start=1):
        run_id = f"run-{index}"
        conn.execute(
            """
            INSERT INTO shadow_runs (
                shadow_run_id, service_start_time_utc, git_commit, code_version,
                config_hash, dry_run, lock_path, db_path, created_at_utc
            ) VALUES (?, ?, 'abc', 'test', 'cfg', 0, '/tmp/lock', ?, ?)
            """,
            (run_id, ts, str(path), ts),
        )
        conn.execute(
            """
            INSERT INTO shadow_resource_samples (
                shadow_run_id, timestamp_utc, disk_free_bytes, disk_total_bytes,
                memory_rss_bytes, cpu_user_seconds, cpu_system_seconds, process_id,
                guard_status, details_json
            ) VALUES (?, ?, ?, ?, ?, 0.1, 0.1, 123, 'pass', '{}')
            """,
            (run_id, ts, 20 * 1024**3, 75 * 1024**3, 26 * 1024**2),
        )
        for symbol, threshold in (
            ("BTCUSDT", 0.00649),
            ("ETHUSDT", 0.0075),
            ("SOLUSDT", 0.0075),
        ):
            conn.execute(
                """
                INSERT INTO shadow_decision_outcomes (
                    shadow_run_id, symbol, timestamp_utc, strategy_profile,
                    risk_policy_profile, shadow_mode, config_hash, signal_generated,
                    signal_blocker, sweep_detected, reclaim_detected, sweep_depth_pct,
                    min_sweep_depth_pct, regime, context_session,
                    confluence_score_preview, candidate_direction_preview,
                    symbol_governance_shadow_decision, symbol_risk_shadow_decision,
                    portfolio_shadow_decision, portfolio_veto_reason, candidate_risk_pct,
                    portfolio_risk_after_pct, resource_guard_status, details_json,
                    created_at_utc
                ) VALUES (?, ?, ?, 'trial', 'risk', 'shadow_no_orders', 'cfg', 0,
                    'no_reclaim', 1, 0, 0.001, ?, 'normal', 'new_york',
                    0.0, NULL, 'no_candidate', 'no_candidate', 'not_evaluated',
                    'no_reclaim', 0.0035, 0.0, 'pass', '{}', ?)
                """,
                (run_id, symbol, ts, threshold, ts),
            )
            conn.execute(
                """
                INSERT INTO shadow_portfolio_decisions (
                    shadow_run_id, symbol, timestamp_utc, signal_id,
                    portfolio_shadow_decision, portfolio_veto_reason,
                    candidate_risk_pct, portfolio_risk_before_pct,
                    portfolio_risk_after_pct, gross_notional_after_pct,
                    directional_notional_after_pct, details_json, created_at_utc
                ) VALUES (?, ?, ?, NULL, 'not_evaluated', 'no_reclaim',
                    0.0035, 0.0, 0.0, 0.0, 0.0, '{}', ?)
                """,
                (run_id, symbol, ts, ts),
            )
    conn.commit()
    conn.close()


def _seed_production_db(path: Path, *, eth_position: bool = False) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn, schema_path)
    if eth_position:
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score,
                regime, reasons_json, features_json, schema_version, config_hash
            ) VALUES ('sig-eth', '2026-05-21T12:00:00Z', 'LONG', 'test',
                1.0, 'normal', '[]', '{}', 'test', 'cfg')
            """
        )
        conn.execute(
            """
            INSERT INTO executable_signals (
                signal_id, timestamp, direction, entry_price, stop_loss,
                take_profit_1, take_profit_2, rr_ratio, governance_notes_json
            ) VALUES ('sig-eth', '2026-05-21T12:00:00Z', 'LONG',
                100.0, 90.0, 110.0, 120.0, 2.0, '[]')
            """
        )
        conn.execute(
            """
            INSERT INTO positions (
                position_id, signal_id, symbol, opened_at, direction, entry_price,
                size, leverage, stop_loss, take_profit_1, take_profit_2, status,
                updated_at
            ) VALUES ('pos-eth', 'sig-eth', 'ETHUSDT', '2026-05-21T12:00:00Z',
                'LONG', 100.0, 1.0, 1, 90.0, 110.0, 120.0, 'OPEN',
                '2026-05-21T12:00:00Z')
            """
        )
    conn.commit()
    conn.close()
