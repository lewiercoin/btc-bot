from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from math import isclose
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.governance import GovernanceConfig, GovernanceLayer
from core.models import ExecutableSignal, RegimeState, SignalCandidate
from core.risk_engine import RiskConfig, RiskEngine
from settings import load_settings
from storage.db import connect, init_db
from storage.repositories import save_executable_signal, save_signal_candidate
from storage.state_store import StateStore

REFERENCE_EQUITY = 10_000.0


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


def expected_max_drawdown(pnls: list[float], reference_equity: float) -> float:
    equity = reference_equity
    peak = reference_equity
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        if equity > peak:
            peak = equity
        dd = (peak - equity) / max(peak, 1e-8)
        if dd > max_dd:
            max_dd = dd
    return min(max(max_dd, 0.0), 1.0)


def open_and_settle_trade(
    *,
    conn,
    state_store: StateStore,
    risk_engine: RiskEngine,
    settings,
    index: int,
    opened_at: datetime,
    pnl_abs_target: float,
) -> datetime:
    entry_price = 100.0 + float(index)
    size = 1.0
    stop_loss = entry_price - 5.0
    tp1 = entry_price + 10.0
    tp2 = entry_price + 15.0

    signal_id = f"sig-dd-{uuid4().hex[:10]}"
    position_id = f"pos-dd-{uuid4().hex[:10]}"
    candidate = SignalCandidate(
        signal_id=signal_id,
        timestamp=opened_at,
        direction="LONG",
        setup_type="drawdown_smoke",
        entry_reference=entry_price,
        invalidation_level=stop_loss,
        tp_reference_1=tp1,
        tp_reference_2=tp2,
        confluence_score=4.0,
        regime=RegimeState.NORMAL,
        reasons=["drawdown-smoke"],
        features_json={"smoke": "drawdown"},
    )
    executable = ExecutableSignal(
        signal_id=signal_id,
        timestamp=opened_at,
        direction="LONG",
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit_1=tp1,
        take_profit_2=tp2,
        rr_ratio=2.0,
        approved_by_governance=True,
        governance_notes=["drawdown-smoke"],
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
            settings.strategy.symbol,
            "LONG",
            "OPEN",
            entry_price,
            size,
            3,
            stop_loss,
            tp1,
            tp2,
            opened_at.isoformat(),
            opened_at.isoformat(),
        ),
    )
    conn.commit()

    state_store.record_trade_open(
        candidate=candidate,
        executable=executable,
        schema_version=settings.schema_version,
        config_hash=settings.config_hash,
    )

    open_record = next((r for r in state_store.get_open_trade_records() if r.position.position_id == position_id), None)
    if open_record is None:
        raise RuntimeError(f"Missing open trade record for position_id={position_id}")

    exit_price = entry_price + pnl_abs_target / size
    closed_at = opened_at + timedelta(minutes=30)
    candles_path = [
        {
            "open_time": opened_at,
            "high": max(entry_price, exit_price) + 0.5,
            "low": min(entry_price, exit_price) - 0.5,
            "close": exit_price,
        }
    ]
    settlement = risk_engine.build_settlement_metrics(
        open_record.position,
        exit_price=exit_price,
        exit_reason="TP" if pnl_abs_target > 0 else "SL",
        candles_15m=candles_path,
    )
    state_store.settle_trade_close(
        position_id=position_id,
        settlement=settlement,
        closed_at=closed_at,
    )
    return closed_at


def main() -> None:
    settings = load_settings()
    assert settings.storage is not None

    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)
    reset_runtime_tables(conn)

    state_store = StateStore(
        connection=conn,
        mode=settings.mode.value,
        reference_equity=REFERENCE_EQUITY,
    )
    state_store.ensure_initialized()
    risk_engine = RiskEngine()

    start = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    pnls = [-100.0, 40.0, -250.0]
    closed_at = start
    for idx, pnl in enumerate(pnls):
        opened_at = start + timedelta(hours=idx)
        closed_at = open_and_settle_trade(
            conn=conn,
            state_store=state_store,
            risk_engine=risk_engine,
            settings=settings,
            index=idx,
            opened_at=opened_at,
            pnl_abs_target=pnl,
        )

    refreshed = state_store.refresh_runtime_state(closed_at + timedelta(minutes=1))
    expected_dd = expected_max_drawdown(pnls, REFERENCE_EQUITY)

    print("expected_dd:", expected_dd)
    print("bot_state_dd:", refreshed.daily_dd_pct, refreshed.weekly_dd_pct)
    print("bot_state_consecutive_losses:", refreshed.consecutive_losses)

    assert isclose(refreshed.daily_dd_pct, expected_dd, rel_tol=0.0, abs_tol=1e-9)
    assert isclose(refreshed.weekly_dd_pct, expected_dd, rel_tol=0.0, abs_tol=1e-9)
    assert refreshed.consecutive_losses == 1
    assert refreshed.open_positions_count == 0

    test_ts = closed_at + timedelta(minutes=5)
    governance = GovernanceLayer(
        GovernanceConfig(
            daily_dd_limit=0.03,
            weekly_dd_limit=0.06,
            max_trades_per_day=10,
            max_consecutive_losses=10,
        ),
        state_provider=lambda: state_store.get_governance_state(now=test_ts),
    )
    blocked_candidate = SignalCandidate(
        signal_id=f"sig-dd-check-{uuid4().hex[:10]}",
        timestamp=test_ts,
        direction="LONG",
        setup_type="drawdown_gate_check",
        entry_reference=120.0,
        invalidation_level=115.0,
        tp_reference_1=130.0,
        tp_reference_2=135.0,
        confluence_score=4.2,
        regime=RegimeState.NORMAL,
        reasons=["dd-check"],
        features_json={"dd_check": True},
    )
    governance_decision = governance.evaluate(blocked_candidate)
    print("governance_decision:", governance_decision.approved, governance_decision.notes)
    assert not governance_decision.approved
    assert any("daily_dd_exceeded" in note for note in governance_decision.notes)

    risk_for_check = RiskEngine(
        RiskConfig(
            min_rr=1.0,
            daily_dd_limit=0.03,
            weekly_dd_limit=0.06,
        ),
        state_provider=state_store.get_risk_state,
    )
    blocked_signal = ExecutableSignal(
        signal_id=f"exe-dd-check-{uuid4().hex[:10]}",
        timestamp=test_ts,
        direction="LONG",
        entry_price=120.0,
        stop_loss=116.0,
        take_profit_1=132.0,
        take_profit_2=136.0,
        rr_ratio=3.0,
        approved_by_governance=True,
        governance_notes=["dd-check"],
    )
    risk_decision = risk_for_check.evaluate(blocked_signal, equity=REFERENCE_EQUITY, open_positions=0)
    print("risk_decision:", risk_decision.allowed, risk_decision.reason)
    assert not risk_decision.allowed
    assert risk_decision.reason in {"daily_dd_limit", "weekly_dd_limit"}

    # Restart smoke: values must be available from SQLite after reconnect.
    conn.close()
    conn = connect(settings.storage.db_path)
    restarted_store = StateStore(
        connection=conn,
        mode=settings.mode.value,
        reference_equity=REFERENCE_EQUITY,
    )
    loaded = restarted_store.load()
    assert loaded is not None
    print("loaded_after_restart:", loaded.daily_dd_pct, loaded.weekly_dd_pct, loaded.consecutive_losses)
    assert isclose(loaded.daily_dd_pct, expected_dd, rel_tol=0.0, abs_tol=1e-9)
    assert isclose(loaded.weekly_dd_pct, expected_dd, rel_tol=0.0, abs_tol=1e-9)
    assert loaded.consecutive_losses == 1

    restarted_state = restarted_store.get_risk_state()
    assert isclose(restarted_state.daily_dd_pct, expected_dd, rel_tol=0.0, abs_tol=1e-9)
    assert isclose(restarted_state.weekly_dd_pct, expected_dd, rel_tol=0.0, abs_tol=1e-9)
    assert restarted_state.consecutive_losses == 1

    print("drawdown persistence smoke: OK")


if __name__ == "__main__":
    main()
