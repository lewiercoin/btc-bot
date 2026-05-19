from __future__ import annotations

import sqlite3
from pathlib import Path

from backtest.performance import PerformanceReport
from research_lab.eth_trial_00095_transfer_feasibility import (
    TransferGates,
    _derive_1h_candles,
    builder_verdict,
    evaluate_gates,
    fold_windows,
)
from research_lab.hypotheses.spec import load_hypothesis_spec


def _perf(
    *,
    trades: int,
    er: float,
    pf: float,
    dd: float,
    wr: float = 0.5,
) -> PerformanceReport:
    return PerformanceReport(
        trades_count=trades,
        expectancy_r=er,
        pnl_abs=0.0,
        pnl_r_sum=er * trades,
        max_drawdown_pct=dd,
        win_rate=wr,
        avg_winner_r=2.0,
        avg_loser_r=-1.0,
        profit_factor=pf,
        max_consecutive_losses=3,
        sharpe_ratio=1.0,
        total_fees=1.0,
    )


def test_builder_verdict_passes_when_all_transfer_gates_pass() -> None:
    folds = [
        type("Fold", (), {"expectancy_r": 1.2, "trades": 5})(),
        type("Fold", (), {"expectancy_r": 1.1, "trades": 5})(),
        type("Fold", (), {"expectancy_r": 0.2, "trades": 5})(),
        type("Fold", (), {"expectancy_r": -0.1, "trades": 5})(),
    ]
    gates = evaluate_gates(
        full=_perf(trades=30, er=1.3, pf=2.0, dd=0.05),
        cost_2x=_perf(trades=30, er=0.8, pf=1.7, dd=0.06),
        folds=folds,
        gates=TransferGates(),
    )

    assert builder_verdict(gates, full_trades=30) == "PASS_TRANSFER_CANDIDATE_FOR_AUDIT"


def test_builder_verdict_distinguishes_low_frequency_only() -> None:
    folds = [
        type("Fold", (), {"expectancy_r": 1.2, "trades": 5})(),
        type("Fold", (), {"expectancy_r": 1.1, "trades": 5})(),
    ]
    gates = evaluate_gates(
        full=_perf(trades=10, er=1.3, pf=2.0, dd=0.05),
        cost_2x=_perf(trades=10, er=0.8, pf=1.7, dd=0.06),
        folds=folds,
        gates=TransferGates(),
    )

    assert builder_verdict(gates, full_trades=10) == "INCONCLUSIVE_LOW_FREQUENCY"


def test_derive_1h_candles_uses_complete_four_bar_groups(tmp_path: Path) -> None:
    db_path = tmp_path / "sample.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            open_time TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            UNIQUE(symbol, timeframe, open_time)
        )
        """
    )
    rows = [
        ("ETHUSDT", "15m", "2024-01-01T00:00:00+00:00", 100, 101, 99, 100.5, 10),
        ("ETHUSDT", "15m", "2024-01-01T00:15:00+00:00", 100.5, 102, 100, 101, 11),
        ("ETHUSDT", "15m", "2024-01-01T00:30:00+00:00", 101, 103, 100.5, 102, 12),
        ("ETHUSDT", "15m", "2024-01-01T00:45:00+00:00", 102, 104, 101, 103, 13),
        ("ETHUSDT", "15m", "2024-01-01T01:00:00+00:00", 103, 105, 102, 104, 14),
    ]
    conn.executemany(
        "INSERT INTO candles(symbol, timeframe, open_time, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )

    inserted = _derive_1h_candles(conn, symbol="ETHUSDT")
    one_hour = conn.execute("SELECT open, high, low, close, volume FROM candles WHERE timeframe='1h'").fetchone()
    conn.close()

    assert inserted == 1
    assert one_hour == (100.0, 104.0, 99.0, 103.0, 46.0)


def test_fold_windows_cover_expected_chronology() -> None:
    labels = [item[0] for item in fold_windows()]

    assert labels == ["2022", "2023", "2024", "2025_to_2026Q1"]


def test_eth_transfer_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/eth_trial_00095_transfer_feasibility.json"))

    assert spec.hypothesis_id == "eth_trial_00095_transfer_feasibility_v1"
    assert spec.status == "ACTIVE"
    assert "ETH parameter optimization." in spec.out_of_scope
