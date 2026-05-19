from __future__ import annotations

from datetime import datetime, timedelta, timezone

from research_lab.portfolio_replay_harness import (
    ArtifactTrade,
    compute_metrics,
    run_artifact_portfolio_replay,
    veto_breakdown,
)


NOW = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


def _trade(
    symbol: str,
    trade_id: str,
    minute: int,
    pnl_r: float = 1.0,
    direction: str = "LONG",
) -> ArtifactTrade:
    return ArtifactTrade(
        symbol=symbol,
        trade_id=trade_id,
        opened_at=NOW + timedelta(minutes=minute),
        direction=direction,
        pnl_r=pnl_r,
    )


def test_replay_is_deterministic_for_same_inputs() -> None:
    trades = [_trade("ETHUSDT", "e1", 0), _trade("BTCUSDT", "b1", 0)]

    first = run_artifact_portfolio_replay(trades, hold_minutes=30)
    second = run_artifact_portfolio_replay(list(reversed(trades)), hold_minutes=30)

    assert [t.trade_id for t in first.approved_trades] == [t.trade_id for t in second.approved_trades]
    assert [v.trade_id for v in first.vetoes] == [v.trade_id for v in second.vetoes]


def test_replay_tracks_open_position_caps_over_time() -> None:
    trades = [
        _trade("BTCUSDT", "b1", 0),
        _trade("BTCUSDT", "b2", 15),
        _trade("BTCUSDT", "b3", 45),
    ]

    result = run_artifact_portfolio_replay(trades, hold_minutes=30)

    assert [trade.trade_id for trade in result.approved_trades] == ["b1", "b3"]
    assert [veto.trade_id for veto in result.vetoes] == ["b2"]
    assert veto_breakdown(result.vetoes)["symbol_position_cap_exceeded"] == 1


def test_replay_applies_symbol_cooldown_after_loss_close() -> None:
    trades = [
        _trade("BTCUSDT", "b1", 0, pnl_r=-1.0),
        _trade("BTCUSDT", "b2", 45, pnl_r=1.0),
        _trade("ETHUSDT", "e1", 45, pnl_r=1.0),
    ]

    result = run_artifact_portfolio_replay(trades, hold_minutes=30)

    assert [trade.trade_id for trade in result.approved_trades] == ["b1", "e1"]
    assert [veto.trade_id for veto in result.vetoes] == ["b2"]
    assert veto_breakdown(result.vetoes)["symbol_cooldown_active"] == 1


def test_replay_vetoes_second_same_bar_signal_when_risk_cap_full() -> None:
    trades = [_trade("BTCUSDT", "b1", 0), _trade("ETHUSDT", "e1", 0), _trade("BTCUSDT", "b2", 15)]

    result = run_artifact_portfolio_replay(trades, hold_minutes=60)

    assert [trade.trade_id for trade in result.approved_trades] == ["b1", "e1"]
    assert [veto.trade_id for veto in result.vetoes] == ["b2"]
    assert veto_breakdown(result.vetoes)["symbol_position_cap_exceeded"] == 1
    assert result.max_total_risk_pct == 0.007


def test_compute_metrics_uses_closed_order_drawdown() -> None:
    result = run_artifact_portfolio_replay(
        [
            _trade("BTCUSDT", "b1", 0, pnl_r=2.0),
            _trade("ETHUSDT", "e1", 45, pnl_r=-1.0),
            _trade("BTCUSDT", "b2", 90, pnl_r=3.0),
        ],
        hold_minutes=30,
    )

    metrics = compute_metrics(result.approved_trades)

    assert metrics["trades"] == 3
    assert metrics["er"] == 4.0 / 3.0
    assert metrics["max_drawdown_r"] == 1.0
