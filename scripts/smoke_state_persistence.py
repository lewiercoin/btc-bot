from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.models import ExecutableSignal, RegimeState, SignalCandidate
from settings import load_settings
from storage.db import connect, init_db
from storage.state_store import StateStore


def reset_runtime_tables(conn) -> None:
    for table in (
        "executions",
        "trade_log",
        "positions",
        "executable_signals",
        "signal_candidates",
        "daily_metrics",
        "bot_state",
    ):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


def main() -> None:
    settings = load_settings()
    assert settings.storage is not None

    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)
    reset_runtime_tables(conn)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    signal_id = f"sig-{uuid4().hex[:12]}"
    position_id = f"pos-{uuid4().hex[:12]}"

    candidate = SignalCandidate(
        signal_id=signal_id,
        timestamp=now,
        direction="LONG",
        setup_type="liquidity_sweep_reclaim_long",
        entry_reference=80000.0,
        invalidation_level=79800.0,
        tp_reference_1=80600.0,
        tp_reference_2=81000.0,
        confluence_score=3.6,
        regime=RegimeState.NORMAL,
        reasons=["smoke"],
        features_json={"smoke": True},
    )
    executable = ExecutableSignal(
        signal_id=signal_id,
        timestamp=now,
        direction="LONG",
        entry_price=80000.0,
        stop_loss=79800.0,
        take_profit_1=80600.0,
        take_profit_2=81000.0,
        rr_ratio=3.0,
        approved_by_governance=True,
        governance_notes=["smoke"],
    )

    conn.execute(
        """
        INSERT INTO signal_candidates (
            signal_id, timestamp, direction, setup_type, confluence_score, regime,
            reasons_json, features_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            now.isoformat(),
            "LONG",
            "smoke",
            3.5,
            "normal",
            "[]",
            "{}",
            settings.schema_version,
            settings.config_hash,
        ),
    )
    conn.execute(
        """
        INSERT INTO executable_signals (
            signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1, take_profit_2, rr_ratio, governance_notes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            now.isoformat(),
            "LONG",
            80000.0,
            79800.0,
            80600.0,
            81000.0,
            3.0,
            "[]",
        ),
    )
    conn.execute(
        """
        INSERT INTO positions (
            position_id, signal_id, symbol, direction, status, entry_price, size, leverage,
            stop_loss, take_profit_1, take_profit_2, opened_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            position_id,
            signal_id,
            "BTCUSDT",
            "LONG",
            "OPEN",
            80000.0,
            0.1,
            3,
            79800.0,
            80600.0,
            81000.0,
            now.isoformat(),
            now.isoformat(),
        ),
    )
    conn.commit()

    state_store = StateStore(connection=conn, mode=settings.mode.value)
    state_store.ensure_initialized()
    state_store.record_trade_open(
        candidate=candidate,
        executable=executable,
        schema_version=settings.schema_version,
        config_hash=settings.config_hash,
    )

    bot_state = conn.execute("SELECT * FROM bot_state WHERE id = 1").fetchone()
    daily_metrics = conn.execute("SELECT * FROM daily_metrics WHERE date = ?", (now.date().isoformat(),)).fetchone()
    trade_log_count = conn.execute("SELECT COUNT(*) FROM trade_log WHERE signal_id = ?", (signal_id,)).fetchone()[0]

    print("bot_state:", dict(bot_state) if bot_state else None)
    print("daily_metrics:", dict(daily_metrics) if daily_metrics else None)
    print("trade_log_count:", trade_log_count)

    assert bot_state is not None
    assert int(bot_state["open_positions_count"]) >= 1
    assert daily_metrics is not None
    assert int(daily_metrics["trades_count"]) >= 1
    assert trade_log_count >= 1
    print("state persistence smoke: OK")


if __name__ == "__main__":
    main()
