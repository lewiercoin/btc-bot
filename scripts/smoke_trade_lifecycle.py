from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.models import ExecutableSignal, RegimeState, SignalCandidate
from core.risk_engine import RiskEngine
from settings import load_settings
from storage.db import connect, init_db
from storage.repositories import save_executable_signal, save_signal_candidate
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
        setup_type="lifecycle_smoke",
        entry_reference=80000.0,
        invalidation_level=79750.0,
        tp_reference_1=80500.0,
        tp_reference_2=80800.0,
        confluence_score=3.8,
        regime=RegimeState.NORMAL,
        reasons=["smoke-lifecycle"],
        features_json={"smoke": "lifecycle"},
    )
    executable = ExecutableSignal(
        signal_id=signal_id,
        timestamp=now,
        direction="LONG",
        entry_price=80000.0,
        stop_loss=79750.0,
        take_profit_1=80500.0,
        take_profit_2=80800.0,
        rr_ratio=2.0,
        approved_by_governance=True,
        governance_notes=["smoke"],
    )

    save_signal_candidate(conn, candidate, settings.schema_version, settings.config_hash)
    save_executable_signal(conn, executable)
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
            0.2,
            3,
            79750.0,
            80500.0,
            80800.0,
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

    risk_engine = RiskEngine()
    open_records = state_store.get_open_trade_records()
    assert len(open_records) == 1
    record = open_records[0]

    decision = risk_engine.evaluate_exit(
        record.position,
        now=now + timedelta(minutes=20),
        latest_high=80650.0,
        latest_low=79920.0,
        latest_close=80510.0,
    )
    assert decision.should_close and decision.exit_price is not None and decision.reason == "TP"

    candles_path = [
        {"open_time": now, "high": 80400.0, "low": 79980.0, "close": 80350.0},
        {"open_time": now + timedelta(minutes=15), "high": 80650.0, "low": 79900.0, "close": 80510.0},
    ]
    settlement = risk_engine.build_settlement_metrics(
        record.position,
        exit_price=decision.exit_price,
        exit_reason=decision.reason,
        candles_15m=candles_path,
    )
    state_store.settle_trade_close(
        position_id=record.position.position_id,
        settlement=settlement,
        closed_at=now + timedelta(minutes=20),
    )

    trade = conn.execute(
        """
        SELECT closed_at, exit_price, pnl_abs, pnl_r, mae, mfe, exit_reason
        FROM trade_log
        WHERE signal_id = ?
        ORDER BY opened_at DESC
        LIMIT 1
        """,
        (signal_id,),
    ).fetchone()
    metrics = conn.execute(
        "SELECT trades_count, wins, losses, pnl_abs, pnl_r_sum FROM daily_metrics WHERE date = ?",
        (now.date().isoformat(),),
    ).fetchone()
    bot_state = conn.execute(
        "SELECT open_positions_count, consecutive_losses FROM bot_state WHERE id = 1"
    ).fetchone()

    print("trade_log:", dict(trade) if trade else None)
    print("daily_metrics:", dict(metrics) if metrics else None)
    print("bot_state:", dict(bot_state) if bot_state else None)

    assert trade is not None
    assert trade["closed_at"] is not None
    assert float(trade["exit_price"]) == 80500.0
    assert float(trade["pnl_abs"]) > 0
    assert float(trade["pnl_r"]) > 0
    assert float(trade["mae"]) >= 0
    assert float(trade["mfe"]) >= 0
    assert trade["exit_reason"] == "TP"

    assert metrics is not None
    assert int(metrics["trades_count"]) >= 1
    assert int(metrics["wins"]) >= 1
    assert int(metrics["losses"]) == 0
    assert float(metrics["pnl_abs"]) > 0

    assert bot_state is not None
    assert int(bot_state["open_positions_count"]) == 0
    assert int(bot_state["consecutive_losses"]) == 0

    print("trade lifecycle smoke: OK")


if __name__ == "__main__":
    main()
