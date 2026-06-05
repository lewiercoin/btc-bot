from __future__ import annotations

from datetime import datetime, timedelta, timezone

from research_lab.diagnostics import trial_00095_sql_replication_v1 as rep


def _ts(idx: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * idx)


def _candle(idx: int, open_: float, high: float, low: float, close: float) -> rep.Candle:
    return rep.Candle(index=idx, open_time=_ts(idx), open=open_, high=high, low=low, close=close)


def _entry(direction: str = "LONG") -> rep.EntryRecord:
    if direction == "LONG":
        return rep.EntryRecord("t-1", "s-1", _ts(0), _ts(1), "LONG", "uptrend", 100.0, 99.0, 102.0, 104.0, 0.0, "SL")
    return rep.EntryRecord("t-1", "s-1", _ts(0), _ts(1), "SHORT", "downtrend", 100.0, 101.0, 98.0, 96.0, 0.0, "SL")


def _trade(direction: str = "LONG", exit_reason: str = "SL", pnl_r: float = -1.11) -> rep.TradeRecord:
    return rep.TradeRecord("t-1", _ts(0), direction, "uptrend", pnl_r, exit_reason)


def test_long_stop_loss_replay_reports_negative_r() -> None:
    candles = [_candle(0, 100, 100.5, 99.5, 100), _candle(1, 100, 100.2, 98.8, 99)]

    row = rep.simulate_trade(_trade("LONG"), _entry("LONG"), candles, {_ts(0): 0, _ts(1): 1})

    assert row.replicated_exit_reason == "SL"
    assert row.replicated_pnl_r == -1.11


def test_long_tp2_proxy_replay_reports_positive_r() -> None:
    candles = [_candle(0, 100, 100.5, 99.5, 100), _candle(1, 100, 104.2, 99.8, 104)]

    row = rep.simulate_trade(_trade("LONG", "TP_TRAIL", 3.89), _entry("LONG"), candles, {_ts(0): 0, _ts(1): 1})

    assert row.replicated_exit_reason == "TP2_PROXY"
    assert round(float(row.replicated_pnl_r), 8) == 3.89


def test_short_stop_loss_replay_mirrors_long_logic() -> None:
    candles = [_candle(0, 100, 100.5, 99.5, 100), _candle(1, 100, 101.2, 99.8, 101)]

    row = rep.simulate_trade(_trade("SHORT"), _entry("SHORT"), candles, {_ts(0): 0, _ts(1): 1})

    assert row.replicated_exit_reason == "SL"
    assert row.replicated_pnl_r == -1.11


def test_both_hit_intrabar_uses_pessimistic_stop_first_ordering() -> None:
    candles = [_candle(0, 100, 100.5, 99.5, 100), _candle(1, 100, 104.2, 98.8, 100)]

    row = rep.simulate_trade(_trade("LONG"), _entry("LONG"), candles, {_ts(0): 0, _ts(1): 1})

    assert row.replicated_exit_reason == "SL"


def test_missing_entry_is_reported_explicitly_in_database_run(tmp_path) -> None:
    db_path = tmp_path / "market.db"
    with rep.sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE candles (symbol TEXT, timeframe TEXT, open_time TEXT, open REAL, high REAL, low REAL, close REAL)")
        conn.execute("INSERT INTO candles VALUES (?, ?, ?, ?, ?, ?, ?)", ("BTCUSDT", "15m", _ts(0).isoformat(), 100, 101, 99, 100))

    result = rep.run_single_database(db_path=db_path, trades=[_trade()], entries={}, db_role="canonical")

    assert result["missing_entries"] == ["t-1"]


def test_acceptance_evaluator_passes_inside_frozen_bounds() -> None:
    verdict = rep.stratified_verdict(
        metrics_row={"count": 274, "expectancy_r": 2.1, "profit_factor": 4.2, "win_rate": 0.56},
        full_corr=0.99,
        sl_corr=0.99,
        trail_corr=0.99,
    )

    assert verdict["verdict"] == "FULL_REPRODUCTION"


def test_acceptance_evaluator_fails_population_metrics() -> None:
    verdict = rep.stratified_verdict(
        metrics_row={"count": 274, "expectancy_r": 0.0, "profit_factor": 4.2, "win_rate": 0.56},
        full_corr=0.99,
        sl_corr=0.99,
        trail_corr=0.99,
    )

    assert verdict["verdict"] == "VALIDATED_EDGE_NOT_REPRODUCIBLE"
    assert "er_outside_plus_minus_5pct" in verdict["failing_checks"]


def test_pearson_handles_exact_and_divergent_reproduction() -> None:
    assert rep.pearson([1, 2, 3], [1, 2, 3]) == 1.0
    assert rep.pearson([1, 2, 3], [3, 2, 1]) == -1.0


def test_subset_pearsons_are_computed_independently() -> None:
    rows = [
        rep.ReplicatedTrade("s1", _ts(1).isoformat(), "LONG", "SL", "SL", -1, -1, 0, 100, 99, 102, 104, _ts(2).isoformat(), 99, ""),
        rep.ReplicatedTrade("s2", _ts(2).isoformat(), "LONG", "SL", "SL", -2, -2, 0, 100, 99, 102, 104, _ts(3).isoformat(), 99, ""),
        rep.ReplicatedTrade("t1", _ts(3).isoformat(), "LONG", "TP_TRAIL", "TP2_PROXY", 1, 2, 1, 100, 99, 102, 104, _ts(4).isoformat(), 104, ""),
        rep.ReplicatedTrade("t2", _ts(4).isoformat(), "LONG", "TP_TRAIL", "TP2_PROXY", 2, 1, 1, 100, 99, 102, 104, _ts(5).isoformat(), 104, ""),
    ]

    assert rep.correlation_for(rows, "SL")["pearson"] == 1.0
    assert rep.correlation_for(rows, "TP_TRAIL")["pearson"] == -1.0


def test_stratified_verdict_returns_trail_insufficient_when_sl_passes_and_trail_fails() -> None:
    verdict = rep.stratified_verdict(
        metrics_row={"count": 274, "expectancy_r": 2.1, "profit_factor": 4.2, "win_rate": 0.56},
        full_corr=0.1,
        sl_corr=0.99,
        trail_corr=0.1,
    )

    assert verdict["verdict"] == "PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL"


def test_stratified_verdict_returns_edge_not_reproducible_when_sl_fails() -> None:
    verdict = rep.stratified_verdict(
        metrics_row={"count": 274, "expectancy_r": 2.1, "profit_factor": 4.2, "win_rate": 0.56},
        full_corr=0.1,
        sl_corr=0.1,
        trail_corr=0.99,
    )

    assert verdict["verdict"] == "VALIDATED_EDGE_NOT_REPRODUCIBLE"


def test_db_binding_uses_canonical_result_and_snapshot_only_comparison() -> None:
    canonical = {"verdict": {"verdict": "VALIDATED_EDGE_NOT_REPRODUCIBLE"}}
    snapshot = {"verdict": {"verdict": "FULL_REPRODUCTION"}}

    verdict = rep.bind_database_verdict(canonical, snapshot)

    assert verdict["verdict"] == "DATABASE_LINEAGE_MISMATCH"
    assert verdict["canonical_binds"] is True
