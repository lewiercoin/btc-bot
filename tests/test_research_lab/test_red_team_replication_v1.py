from __future__ import annotations

from datetime import datetime, timedelta, timezone

from research_lab import analysis_smc_sequence_edge_feasibility_v1 as smc
from research_lab.diagnostics import red_team_replication_v1 as m6


def _candle(idx: int, open_: float, high: float, low: float, close: float) -> smc.Candle:
    return smc.Candle(
        index=idx,
        open_time=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * idx),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


def test_perturbations_each_mutate_exactly_one_config_field() -> None:
    base = smc.DiagnosticConfig()
    isolation = m6.verify_single_parameter_isolation(base)

    assert all(row["is_isolated"] for row in isolation.values())
    assert set(isolation["P1"]["changed_fields"]) == {"sweep_proximity_atr"}
    assert set(isolation["P2"]["changed_fields"]) == {"sweep_proximity_atr"}
    assert set(isolation["P3"]["changed_fields"]) == {"mitigation_window_bars"}
    assert set(isolation["P4"]["changed_fields"]) == {"displacement_body_atr"}
    assert set(isolation["P5"]["changed_fields"]) == {"round_trip_cost_pct"}


def test_build_run_configs_preserves_declared_order_and_defaults() -> None:
    configs = m6.build_run_configs()

    assert list(configs) == ["A1_BASELINE", "P1", "P2", "P3", "P4", "P5"]
    assert configs["A1_BASELINE"] == smc.DiagnosticConfig()
    assert configs["P1"].sweep_proximity_atr == 0.20
    assert configs["P5"].round_trip_cost_pct == 0.0


def test_raw_sweep_reclaim_ablation_uses_reclaim_entry_without_smc_gates() -> None:
    candles = [
        _candle(0, 100, 101, 99, 100),
        _candle(1, 100, 101, 99, 100),
        _candle(2, 100, 101, 98, 99),
        _candle(3, 99, 101, 98.5, 100.5),
        _candle(4, 100.5, 102, 100, 101),
        _candle(5, 101, 103, 100.5, 102),
    ]
    sweep = smc.SweepEvent(
        symbol="BTCUSDT",
        timeframe="15m",
        detection_bar=2,
        direction="LONG",
        sweep_side="LOW",
        level=100.0,
        atr=2.0,
        sweep_depth_atr=1.0,
    )
    config = smc.DiagnosticConfig(forward_windows=(1,), round_trip_cost_pct=0.0)

    events = m6.build_raw_sweep_reclaim_events(candles, [sweep], config)

    assert len(events) == 1
    event = events[0]
    assert event.sequence_source == "RAW_SWEEP_RECLAIM"
    assert event.entry_candidate_bar == 3
    assert event.displacement_bar == 3
    assert event.structure_shift_bar == 3
    assert event.fvg_created_bar == 3
    assert event.mitigation_bar == 3


def test_part_a_verdict_flags_metric_hypersensitive_when_p1_and_p2_flip() -> None:
    rows = [
        {"run_id": "A1_BASELINE", "m6_flip_gate_passed": False},
        {"run_id": "P1", "m6_flip_gate_passed": True},
        {"run_id": "P2", "m6_flip_gate_passed": True},
        {"run_id": "P3", "m6_flip_gate_passed": False},
        {"run_id": "P4", "m6_flip_gate_passed": False},
        {"run_id": "P5", "m6_flip_gate_passed": False},
        {"run_id": "A3_RAW_SWEEP_RECLAIM", "m6_flip_gate_passed": False},
    ]

    verdict = m6.evaluate_part_a(rows, baseline_sha_match=True)

    assert verdict["verdict"] == "SMC_SEQUENCE_VERDICT_NOT_ROBUST"
    assert "METRIC_HYPERSENSITIVE" in verdict["diagnostic_notes"]


def test_part_a_verdict_returns_gross_only_when_only_p5_flips() -> None:
    rows = [
        {"run_id": "A1_BASELINE", "m6_flip_gate_passed": False},
        {"run_id": "P1", "m6_flip_gate_passed": False},
        {"run_id": "P2", "m6_flip_gate_passed": False},
        {"run_id": "P3", "m6_flip_gate_passed": False},
        {"run_id": "P4", "m6_flip_gate_passed": False},
        {"run_id": "P5", "m6_flip_gate_passed": True},
        {"run_id": "A3_RAW_SWEEP_RECLAIM", "m6_flip_gate_passed": False},
    ]

    assert m6.evaluate_part_a(rows, baseline_sha_match=True)["verdict"] == "SMC_SEQUENCE_EDGE_IS_GROSS_ONLY"


def test_part_a_verdict_returns_raw_edge_when_only_a3_flips() -> None:
    rows = [
        {"run_id": "A1_BASELINE", "m6_flip_gate_passed": False},
        {"run_id": "P1", "m6_flip_gate_passed": False},
        {"run_id": "P2", "m6_flip_gate_passed": False},
        {"run_id": "P3", "m6_flip_gate_passed": False},
        {"run_id": "P4", "m6_flip_gate_passed": False},
        {"run_id": "P5", "m6_flip_gate_passed": False},
        {"run_id": "A3_RAW_SWEEP_RECLAIM", "m6_flip_gate_passed": True},
    ]

    assert m6.evaluate_part_a(rows, baseline_sha_match=True)["verdict"] == "SMC_GATES_DESTROYED_RAW_EDGE"


def test_part_a_baseline_sha_mismatch_hard_stops_verdict() -> None:
    rows = [{"run_id": "A1_BASELINE", "m6_flip_gate_passed": False}]

    assert m6.evaluate_part_a(rows, baseline_sha_match=False)["verdict"] == "BASELINE_NOT_REPRODUCIBLE"


def test_stable_sha_is_deterministic_for_same_payload() -> None:
    payload = {"b": [2, 1], "a": {"x": 1}}

    assert m6.stable_sha(payload) == m6.stable_sha({"a": {"x": 1}, "b": [2, 1]})
