from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from research_lab import shadow_orchestrator
from research_lab.shadow_orchestrator import DISALLOWED_IMPORT_ROOTS, _import_roots_from_file
from research_lab.shadow_schema import SHADOW_DB_DEFAULT, connect_shadow_db, initialize_shadow_schema
from research_lab.shadow_signal_cycle import (
    ShadowCandle,
    ShadowMarketSnapshot,
    ShadowSymbolConfig,
    apply_shadow_portfolio_gate,
    default_symbol_configs,
    evaluate_shadow_symbol,
    run_real_shadow_cycle,
)


FIXED_NOW = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)


def candle(index: int, *, low: float = 100.0, close: float = 101.0) -> ShadowCandle:
    return ShadowCandle(
        open_time_utc=f"2026-05-20T{index:02d}:00:00Z",
        open=101.0,
        high=102.0,
        low=low,
        close=close,
        volume=10.0,
    )


def snapshot(symbol: str, *, trigger_low: float, trigger_close: float) -> ShadowMarketSnapshot:
    candles_15m = tuple(candle(i) for i in range(40)) + (
        candle(40, low=trigger_low, close=trigger_close),
    )
    candles_4h = tuple(
        ShadowCandle(
            open_time_utc=f"2026-05-{(i % 28) + 1:02d}T00:00:00Z",
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.0 + i,
            volume=100.0,
        )
        for i in range(60)
    )
    return ShadowMarketSnapshot(
        symbol=symbol,
        timestamp_utc="2026-05-20T12:00:00Z",
        candles_15m=candles_15m,
        candles_4h=candles_4h,
        open_interest=123.0,
        source="fake_provider",
    )


class FakeProvider:
    def __init__(self, payloads: dict[str, ShadowMarketSnapshot | None]):
        self.payloads = payloads

    def get_snapshot(self, symbol: str, now: datetime) -> ShadowMarketSnapshot | None:
        return self.payloads.get(symbol)


def create_production_db(repo_root: Path) -> Path:
    storage_dir = repo_root / "storage"
    storage_dir.mkdir()
    production_db = storage_dir / "btc_bot.db"
    with sqlite3.connect(production_db) as conn:
        conn.execute("CREATE TABLE sentinel (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO sentinel (value) VALUES ('before')")
        conn.commit()
    return production_db


def test_evaluate_shadow_symbol_detects_signal_near_miss_and_no_sweep() -> None:
    config = default_symbol_configs()[0]

    no_sweep = evaluate_shadow_symbol(config, snapshot("BTCUSDT", trigger_low=100.2, trigger_close=101.0))
    assert no_sweep.signal_generated is False
    assert no_sweep.signal_blocker == "no_sweep"

    near_miss = evaluate_shadow_symbol(config, snapshot("BTCUSDT", trigger_low=99.45, trigger_close=100.2))
    assert near_miss.signal_generated is False
    assert near_miss.signal_blocker == "sweep_too_shallow"
    assert near_miss.near_miss is True
    assert near_miss.sweep_depth_pct is not None
    assert near_miss.details["m4_source"] is False

    full_signal = evaluate_shadow_symbol(config, snapshot("BTCUSDT", trigger_low=99.2, trigger_close=100.2))
    assert full_signal.signal_generated is True
    assert full_signal.signal_blocker is None
    assert full_signal.candidate_direction_preview == "LONG"


def test_run_real_shadow_cycle_persists_symbol_rows_candidates_and_near_miss(tmp_path: Path) -> None:
    db_path = tmp_path / "research_lab" / "shadow" / "multi_asset_shadow.db"
    db_path.parent.mkdir(parents=True)
    provider = FakeProvider(
        {
            "BTCUSDT": snapshot("BTCUSDT", trigger_low=100.2, trigger_close=101.0),
            "ETHUSDT": snapshot("ETHUSDT", trigger_low=99.45, trigger_close=100.2),
            "SOLUSDT": snapshot("SOLUSDT", trigger_low=99.2, trigger_close=100.2),
        }
    )
    with connect_shadow_db(db_path, repo_root=tmp_path) as conn:
        initialize_shadow_schema(conn)
        conn.execute(
            """
            INSERT INTO shadow_runs (
                shadow_run_id, service_start_time_utc, git_commit, code_version,
                config_hash, dry_run, lock_path, db_path, created_at_utc
            )
            VALUES ('run-1', '2026-05-20T12:00:00Z', 'test', 'test', 'hash', 0, 'lock', ?, '2026-05-20T12:00:00Z')
            """,
            (db_path.as_posix(),),
        )
        result = run_real_shadow_cycle(
            conn,
            shadow_run_id="run-1",
            config_hash="hash",
            provider=provider,
            now=FIXED_NOW,
        )

        assert len(result.decisions) == 3
        assert result.signal_candidates == 1
        assert result.portfolio_decisions == 3
        assert result.near_miss_rows == 1
        assert conn.execute("SELECT COUNT(*) FROM shadow_decision_outcomes").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM shadow_signal_candidates").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM shadow_portfolio_decisions").fetchone()[0] == 3

        near_miss_payload = conn.execute(
            "SELECT near_miss_payload_json FROM shadow_near_miss_diagnostics"
        ).fetchone()[0]
        parsed = json.loads(near_miss_payload)
        assert parsed["near_miss_diagnostics"]["sweep_depth_pct"] > 0

        sol_row = conn.execute(
            "SELECT shadow_mode, signal_generated, portfolio_shadow_decision FROM shadow_decision_outcomes WHERE symbol = 'SOLUSDT'"
        ).fetchone()
        assert tuple(sol_row) == ("shadow_no_orders", 1, "approve_shadow")


def test_real_shadow_cycle_records_unavailable_symbol_without_crashing(tmp_path: Path) -> None:
    db_path = tmp_path / "research_lab" / "shadow" / "multi_asset_shadow.db"
    db_path.parent.mkdir(parents=True)
    configs = (
        ShadowSymbolConfig(
            symbol="SOLUSDT",
            risk_policy_profile="sol_015_shadow_candidate",
            shadow_mode="shadow_no_orders",
            candidate_risk_pct=0.0015,
        ),
    )
    with connect_shadow_db(db_path, repo_root=tmp_path) as conn:
        initialize_shadow_schema(conn)
        conn.execute(
            """
            INSERT INTO shadow_runs (
                shadow_run_id, service_start_time_utc, git_commit, code_version,
                config_hash, dry_run, lock_path, db_path, created_at_utc
            )
            VALUES ('run-2', '2026-05-20T12:00:00Z', 'test', 'test', 'hash', 0, 'lock', ?, '2026-05-20T12:00:00Z')
            """,
            (db_path.as_posix(),),
        )
        result = run_real_shadow_cycle(
            conn,
            shadow_run_id="run-2",
            config_hash="hash",
            provider=FakeProvider({"SOLUSDT": None}),
            now=FIXED_NOW,
            symbol_configs=configs,
        )

        assert result.signal_candidates == 0
        row = conn.execute(
            "SELECT signal_blocker, portfolio_veto_reason, details_json FROM shadow_decision_outcomes"
        ).fetchone()
        assert row[0] == "data_unavailable"
        assert row[1] == "data_unavailable"
        assert json.loads(row[2])["data_status"] == "unavailable"


def test_shadow_portfolio_gate_vetoes_third_signal_when_batch_risk_exceeds_cap() -> None:
    decisions = tuple(
        evaluate_shadow_symbol(config, snapshot(config.symbol, trigger_low=99.2, trigger_close=100.2))
        for config in default_symbol_configs()
    )
    gated = apply_shadow_portfolio_gate(decisions, max_portfolio_risk_pct=0.007)
    by_symbol = {decision.symbol: decision for decision in gated}

    assert by_symbol["BTCUSDT"].portfolio_shadow_decision == "approve_shadow"
    assert by_symbol["ETHUSDT"].portfolio_shadow_decision == "approve_shadow"
    assert by_symbol["SOLUSDT"].portfolio_shadow_decision == "veto_shadow"
    assert by_symbol["SOLUSDT"].portfolio_veto_reason == "portfolio_risk_cap_exceeded"


def test_real_cycle_once_cli_preserves_production_db_and_writes_real_rows(
    tmp_path: Path, monkeypatch
) -> None:
    production_db = create_production_db(tmp_path)
    before = production_db.read_bytes()

    class PatchedProvider:
        def get_snapshot(self, symbol: str, now: datetime) -> ShadowMarketSnapshot | None:
            if symbol == "BTCUSDT":
                return snapshot(symbol, trigger_low=100.2, trigger_close=101.0)
            if symbol == "ETHUSDT":
                return snapshot(symbol, trigger_low=99.45, trigger_close=100.2)
            return snapshot(symbol, trigger_low=99.2, trigger_close=100.2)

    import research_lab.shadow_signal_cycle as signal_cycle

    monkeypatch.setattr(signal_cycle, "BinanceRestShadowMarketProvider", PatchedProvider)
    exit_code = shadow_orchestrator.main(
        [
            "--real-cycle-once",
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

    assert exit_code == 0
    assert production_db.read_bytes() == before
    db_path = tmp_path / SHADOW_DB_DEFAULT
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM shadow_decision_outcomes").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM shadow_signal_candidates").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM shadow_near_miss_diagnostics").fetchone()[0] == 1


def test_real_signal_cycle_import_guard_has_no_forbidden_roots() -> None:
    roots = _import_roots_from_file(Path("research_lab/shadow_signal_cycle.py"))
    assert roots.isdisjoint(DISALLOWED_IMPORT_ROOTS)
