from __future__ import annotations

from datetime import datetime, timezone

from core.models import TradeLog
from research_lab.multi_asset_full_pipeline_replay import (
    FullPipelineGates,
    builder_verdict,
    evaluate_gates,
    trade_log_to_artifact,
)


NOW = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_trade_log_to_artifact_preserves_required_fields() -> None:
    trade = TradeLog(
        trade_id="t-1",
        signal_id="s-1",
        opened_at=NOW,
        closed_at=NOW,
        direction="LONG",
        regime="uptrend",
        confluence_score=4.0,
        entry_price=100.0,
        exit_price=110.0,
        size=1.0,
        fees=0.1,
        slippage_bps=1.0,
        pnl_abs=10.0,
        pnl_r=2.0,
        mae=0.1,
        mfe=0.2,
        exit_reason="tp",
    )

    artifact = trade_log_to_artifact(trade, symbol="ethusdt")

    assert artifact.symbol == "ETHUSDT"
    assert artifact.trade_id == "t-1"
    assert artifact.opened_at == NOW
    assert artifact.direction == "LONG"
    assert artifact.pnl_r == 2.0
    assert artifact.regime == "uptrend"


def test_evaluate_gates_passes_decision_grade_payload() -> None:
    metrics = {"trades": 700, "er": 1.8, "pf": 3.0, "max_drawdown_r": 12.0}
    per_symbol = {"BTCUSDT": {"trades": 240}, "ETHUSDT": {"trades": 460}}

    gates = evaluate_gates(metrics, per_symbol, FullPipelineGates())

    assert all(item["pass"] for item in gates.values())
    assert builder_verdict(gates) == "PASS_FULL_PIPELINE_REPLAY_FOR_RUNTIME_SCOPING"


def test_evaluate_gates_blocks_low_eth_count() -> None:
    metrics = {"trades": 400, "er": 1.8, "pf": 3.0, "max_drawdown_r": 12.0}
    per_symbol = {"BTCUSDT": {"trades": 240}, "ETHUSDT": {"trades": 100}}

    gates = evaluate_gates(metrics, per_symbol, FullPipelineGates())

    assert gates["min_eth_trades"]["pass"] is False
    assert builder_verdict(gates) == "NEEDS_FIX_OR_RUNTIME_SCOPING_BLOCKED"
