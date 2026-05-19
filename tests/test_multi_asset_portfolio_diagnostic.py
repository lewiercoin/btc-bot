from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from research_lab.hypotheses.spec import load_hypothesis_spec
from research_lab.multi_asset_portfolio_diagnostic import (
    PortfolioGates,
    TradeRecord,
    builder_verdict,
    compute_metrics,
    daily_correlation,
    evaluate_gates,
    same_bar_overlap,
)


def _trade(symbol: str, day: int, pnl_r: float, minute: int = 0) -> TradeRecord:
    return TradeRecord(
        symbol=symbol,
        trade_id=f"{symbol}-{day}-{minute}",
        opened_at=datetime(2024, 1, day, 12, minute, tzinfo=timezone.utc),
        direction="LONG",
        regime="uptrend",
        pnl_r=pnl_r,
    )


def test_compute_metrics_uses_r_drawdown_and_profit_factor() -> None:
    metrics = compute_metrics([
        _trade("BTCUSDT", 1, 2.0),
        _trade("BTCUSDT", 2, -1.0),
        _trade("BTCUSDT", 3, -1.0),
        _trade("BTCUSDT", 4, 4.0),
    ])

    assert metrics["trades"] == 4
    assert metrics["er"] == 1.0
    assert metrics["pf"] == 3.0
    assert metrics["max_drawdown_r"] == 2.0


def test_daily_correlation_zero_fills_inactive_days() -> None:
    btc = [_trade("BTCUSDT", 1, 1.0), _trade("BTCUSDT", 2, -1.0)]
    eth = [_trade("ETHUSDT", 1, 1.0), _trade("ETHUSDT", 3, -1.0)]

    result = daily_correlation(btc, eth)

    assert result["days"] == 3
    assert result["both_active_days"] == 1


def test_same_bar_overlap_counts_15m_signal_collisions() -> None:
    btc = [_trade("BTCUSDT", 1, 1.0, minute=0), _trade("BTCUSDT", 2, 1.0, minute=15)]
    eth = [_trade("ETHUSDT", 1, 1.0, minute=5), _trade("ETHUSDT", 3, 1.0, minute=30)]

    result = same_bar_overlap(btc, eth)

    assert result["same_15m_bars"] == 1
    assert result["unique_signal_bars"] == 3


def test_builder_verdict_passes_when_all_gates_pass() -> None:
    payload = {
        "policies": {"allow_both": {"trades": 400, "er": 1.7, "pf": 2.4, "max_drawdown_r": 20.0}},
        "daily_correlation": {"correlation": 0.2},
        "same_bar_overlap": {"overlap_share": 0.03},
        "concentration": {"top_month_share": 0.08},
    }
    gates = evaluate_gates(payload, PortfolioGates())

    assert builder_verdict(gates) == "PASS_PORTFOLIO_DIAGNOSTIC_FOR_ARCHITECTURE_DESIGN"


def test_multi_asset_portfolio_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/multi_asset_portfolio_diagnostic.json"))

    assert spec.hypothesis_id == "multi_asset_portfolio_diagnostic_v1"
    assert spec.status == "ACTIVE"
    assert "Runtime multi-asset implementation." in spec.out_of_scope
