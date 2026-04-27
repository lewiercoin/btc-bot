"""
Tests for RESEARCH-OPTUNA-V1:
- context_diagnostics: session classification, volatility extraction, bucket stats
- reclaim_edge_v1.json protocol: loads, has required fields, active_params are all ACTIVE
- objective gates: min_trades rejection, max_trades rejection
- promotion gate: walkforward_not_passed blocks approval
- config lineage: search_space_signature and trial_context_signature deterministic
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from research_lab.constants import PARAM_STATUS_ACTIVE, PROMOTION_BLOCKING_RISKS
from research_lab.context_diagnostics import (
    _classify_session,
    _classify_volatility,
    _extract_atr_4h_norm,
    compute_context_diagnostics,
)
from research_lab.objective import (
    build_search_space_signature,
    build_trial_context_signature,
)
from research_lab.param_registry import build_param_registry
from research_lab.protocol import hash_protocol, load_protocol
from research_lab.types import ObjectiveMetrics, SignalFunnel, TrialEvaluation, WalkForwardReport


_PROTOCOL_PATH = Path(__file__).resolve().parents[1] / "research_lab" / "configs" / "reclaim_edge_v1.json"


def _make_trade(opened_at: datetime, pnl_r: float, features_json: str | None = None) -> Any:
    return SimpleNamespace(
        opened_at=opened_at,
        pnl_r=pnl_r,
        features_at_entry_json=features_json,
    )


def _make_trial(
    trial_id: str = "test-trial",
    trades_count: int = 50,
    rejected_reason: str | None = None,
) -> TrialEvaluation:
    return TrialEvaluation(
        trial_id=trial_id,
        params={"confluence_min": 3.6, "min_rr": 1.6},
        metrics=ObjectiveMetrics(
            expectancy_r=0.3,
            profit_factor=1.5,
            max_drawdown_pct=0.15,
            trades_count=trades_count,
            sharpe_ratio=1.2,
            pnl_abs=500.0,
            win_rate=0.55,
        ),
        funnel=SignalFunnel(
            signals_generated=100,
            signals_regime_blocked=10,
            signals_governance_rejected=5,
            signals_risk_rejected=5,
            signals_executed=80,
        ),
        rejected_reason=rejected_reason,
    )


class TestSessionClassification:
    def test_asia_late_night(self) -> None:
        dt = datetime(2026, 4, 27, 23, 30, tzinfo=timezone.utc)
        assert _classify_session(dt) == "ASIA"

    def test_asia_early_morning(self) -> None:
        dt = datetime(2026, 4, 27, 4, 0, tzinfo=timezone.utc)
        assert _classify_session(dt) == "ASIA"

    def test_asia_boundary_22(self) -> None:
        dt = datetime(2026, 4, 27, 22, 0, tzinfo=timezone.utc)
        assert _classify_session(dt) == "ASIA"

    def test_eu_session(self) -> None:
        dt = datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc)
        assert _classify_session(dt) == "EU"

    def test_eu_boundary_start(self) -> None:
        dt = datetime(2026, 4, 27, 7, 0, tzinfo=timezone.utc)
        assert _classify_session(dt) == "EU"

    def test_eu_boundary_end(self) -> None:
        dt = datetime(2026, 4, 27, 13, 59, tzinfo=timezone.utc)
        assert _classify_session(dt) == "EU"

    def test_eu_us_session(self) -> None:
        dt = datetime(2026, 4, 27, 14, 30, tzinfo=timezone.utc)
        assert _classify_session(dt) == "EU_US"

    def test_us_session(self) -> None:
        dt = datetime(2026, 4, 27, 18, 0, tzinfo=timezone.utc)
        assert _classify_session(dt) == "US"

    def test_naive_treated_as_utc(self) -> None:
        dt_naive = datetime(2026, 4, 27, 10, 0)
        assert _classify_session(dt_naive) == "EU"

    def test_non_utc_tz_converted(self) -> None:
        from datetime import timedelta
        tz_plus2 = timezone(timedelta(hours=2))
        dt_local = datetime(2026, 4, 27, 12, 0, tzinfo=tz_plus2)
        assert _classify_session(dt_local) == "EU"


class TestVolatilityClassification:
    def test_low_volatility(self) -> None:
        assert _classify_volatility(0.001) == "LOW"

    def test_normal_volatility(self) -> None:
        assert _classify_volatility(0.003) == "NORMAL"

    def test_high_volatility(self) -> None:
        assert _classify_volatility(0.005) == "HIGH"

    def test_boundary_low_is_normal(self) -> None:
        assert _classify_volatility(0.002) == "NORMAL"

    def test_boundary_high_is_high(self) -> None:
        assert _classify_volatility(0.004) == "NORMAL"

    def test_none_is_unknown(self) -> None:
        assert _classify_volatility(None) == "UNKNOWN"

    def test_atr_extraction_present(self) -> None:
        features = json.dumps({"atr_4h_norm": 0.003, "other": 1.0})
        assert _extract_atr_4h_norm(features) == pytest.approx(0.003)

    def test_atr_extraction_missing(self) -> None:
        features = json.dumps({"some_other_feature": 0.5})
        assert _extract_atr_4h_norm(features) is None

    def test_atr_extraction_none_input(self) -> None:
        assert _extract_atr_4h_norm(None) is None

    def test_atr_extraction_malformed_json(self) -> None:
        assert _extract_atr_4h_norm("{not-valid-json") is None


class TestComputeContextDiagnostics:
    def test_empty_trades(self) -> None:
        result = compute_context_diagnostics([])
        assert result["trades_total"] == 0
        assert result["grade"] == "EMPTY"
        assert "RESEARCH_ONLY" in result["note"]

    def test_session_buckets_present(self) -> None:
        trades = [
            _make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), 0.5),
            _make_trade(datetime(2026, 4, 27, 10, 30, tzinfo=timezone.utc), -0.3),
            _make_trade(datetime(2026, 4, 27, 18, 0, tzinfo=timezone.utc), 0.8),
        ]
        result = compute_context_diagnostics(trades)
        assert "EU" in result["session_buckets"]
        assert "US" in result["session_buckets"]
        eu = result["session_buckets"]["EU"]
        assert eu["n"] == 2
        assert eu["win_rate"] == pytest.approx(0.5)

    def test_partial_grade_when_high_unknown(self) -> None:
        trades = [
            _make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), 0.5, None),
            _make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), 0.3, None),
            _make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), -0.2, None),
        ]
        result = compute_context_diagnostics(trades)
        assert result["grade"] == "PARTIAL"
        assert result["unknown_volatility_pct"] == pytest.approx(100.0)

    def test_full_grade_when_low_unknown(self) -> None:
        atr_high = json.dumps({"atr_4h_norm": 0.006})
        trades = [
            _make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), 0.5, atr_high),
            _make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), 0.3, atr_high),
            _make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), -0.2, atr_high),
            _make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), 0.4, atr_high),
            _make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), 0.1, atr_high),
        ]
        result = compute_context_diagnostics(trades)
        assert result["grade"] == "FULL"
        assert result["unknown_volatility_pct"] == pytest.approx(0.0)

    def test_note_contains_research_only(self) -> None:
        trades = [_make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), 0.5)]
        result = compute_context_diagnostics(trades)
        assert "RESEARCH_ONLY" in result["note"]

    def test_profit_factor_none_when_no_losses(self) -> None:
        trades = [
            _make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), 0.5),
            _make_trade(datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc), 0.3),
        ]
        result = compute_context_diagnostics(trades)
        eu = result["session_buckets"]["EU"]
        assert eu["profit_factor"] is None


class TestReclaimEdgeV1Protocol:
    def test_protocol_file_exists(self) -> None:
        assert _PROTOCOL_PATH.exists(), f"Protocol file not found: {_PROTOCOL_PATH}"

    def test_protocol_loads(self) -> None:
        protocol = load_protocol(_PROTOCOL_PATH)
        assert isinstance(protocol, dict)

    def test_required_fields_present(self) -> None:
        protocol = load_protocol(_PROTOCOL_PATH)
        required = [
            "walkforward_mode", "window_mode", "train_days", "validation_days",
            "step_days", "min_trades_per_window", "min_trades_full_candidate",
            "max_trades_full_candidate", "fragility_degradation_threshold_pct",
            "promotion_requires_all_windows_pass", "active_params_whitelist",
        ]
        for field in required:
            assert field in protocol, f"Missing required protocol field: {field!r}"

    def test_active_params_whitelist_not_empty(self) -> None:
        protocol = load_protocol(_PROTOCOL_PATH)
        whitelist = protocol.get("active_params_whitelist", [])
        assert len(whitelist) >= 5, "active_params_whitelist should contain at least 5 params"

    def test_all_whitelisted_params_are_active_in_registry(self) -> None:
        protocol = load_protocol(_PROTOCOL_PATH)
        registry = build_param_registry()
        for param_name in protocol.get("active_params_whitelist", []):
            assert param_name in registry, f"Param {param_name!r} not in registry"
            assert registry[param_name].status == PARAM_STATUS_ACTIVE, (
                f"Param {param_name!r} is not ACTIVE in registry (status={registry[param_name].status})"
            )

    def test_min_trades_full_candidate_gte_30(self) -> None:
        protocol = load_protocol(_PROTOCOL_PATH)
        assert int(protocol["min_trades_full_candidate"]) >= 30

    def test_promotion_requires_all_windows_pass(self) -> None:
        protocol = load_protocol(_PROTOCOL_PATH)
        assert protocol["promotion_requires_all_windows_pass"] is True

    def test_protocol_hash_is_deterministic(self) -> None:
        h1 = hash_protocol(load_protocol(_PROTOCOL_PATH))
        h2 = hash_protocol(load_protocol(_PROTOCOL_PATH))
        assert h1 == h2

    def test_walkforward_mode_is_post_hoc(self) -> None:
        protocol = load_protocol(_PROTOCOL_PATH)
        assert protocol["walkforward_mode"] == "post_hoc"

    def test_window_mode_is_rolling(self) -> None:
        protocol = load_protocol(_PROTOCOL_PATH)
        assert protocol["window_mode"] == "rolling"


class TestObjectiveGates:
    def test_min_trades_rejection_flagged(self) -> None:
        trial = _make_trial(trades_count=5, rejected_reason="MIN_TRADES_NOT_MET: trades_count=5 < min_trades=30")
        assert trial.rejected_reason is not None
        assert "MIN_TRADES_NOT_MET" in trial.rejected_reason

    def test_max_trades_rejection_flagged(self) -> None:
        trial = _make_trial(trades_count=9999, rejected_reason="MAX_TRADES_VOLUME_CONSTRAINT: trades_count=9999 > max_trades=5000")
        assert trial.rejected_reason is not None
        assert "MAX_TRADES_VOLUME_CONSTRAINT" in trial.rejected_reason

    def test_valid_trial_has_no_rejection(self) -> None:
        trial = _make_trial(trades_count=50)
        assert trial.rejected_reason is None


class TestPromotionGates:
    def test_walkforward_not_passed_is_blocking(self) -> None:
        assert "walkforward_not_passed" in PROMOTION_BLOCKING_RISKS

    def test_walkforward_fragile_is_blocking(self) -> None:
        assert "walkforward_fragile" in PROMOTION_BLOCKING_RISKS

    def test_failed_walkforward_has_blocking_risk(self) -> None:
        report = WalkForwardReport(
            passed=False,
            windows_total=3,
            windows_passed=1,
            is_degradation_pct=40.0,
            fragile=False,
            reasons=("window 2 failed: min_trades not met",),
        )
        blocking = [r for r in ("walkforward_not_passed",) if r in PROMOTION_BLOCKING_RISKS]
        assert len(blocking) > 0

    def test_fragile_walkforward_has_blocking_risk(self) -> None:
        report = WalkForwardReport(
            passed=True,
            windows_total=3,
            windows_passed=3,
            is_degradation_pct=35.0,
            fragile=True,
            reasons=("fragile: degradation 35% > threshold 30%",),
        )
        blocking = [r for r in ("walkforward_fragile",) if r in PROMOTION_BLOCKING_RISKS]
        assert len(blocking) > 0


class TestConfigLineage:
    def test_search_space_signature_deterministic(self) -> None:
        params = ["confluence_min", "min_rr", "sweep_buf_atr"]
        sig1 = build_search_space_signature(params)
        sig2 = build_search_space_signature(params)
        assert sig1 == sig2
        assert len(sig1) == 16

    def test_search_space_signature_order_independent(self) -> None:
        params_a = ["confluence_min", "min_rr", "sweep_buf_atr"]
        params_b = ["sweep_buf_atr", "confluence_min", "min_rr"]
        assert build_search_space_signature(params_a) == build_search_space_signature(params_b)

    def test_search_space_signature_differs_on_different_params(self) -> None:
        sig_a = build_search_space_signature(["confluence_min", "min_rr"])
        sig_b = build_search_space_signature(["confluence_min", "tp1_atr_mult"])
        assert sig_a != sig_b

    def test_trial_context_signature_deterministic(self) -> None:
        sig1 = build_trial_context_signature(
            protocol_hash="abc123",
            search_space_signature="def456",
            start_date="2024-01-01",
            end_date="2026-04-01",
            baseline_version="baseline-v1",
        )
        sig2 = build_trial_context_signature(
            protocol_hash="abc123",
            search_space_signature="def456",
            start_date="2024-01-01",
            end_date="2026-04-01",
            baseline_version="baseline-v1",
        )
        assert sig1 == sig2
        assert len(sig1) == 16

    def test_trial_context_signature_differs_on_date_range(self) -> None:
        common = {
            "protocol_hash": "abc",
            "search_space_signature": "def",
            "baseline_version": "v1",
        }
        sig_a = build_trial_context_signature(**common, start_date="2024-01-01", end_date="2026-01-01")
        sig_b = build_trial_context_signature(**common, start_date="2024-01-01", end_date="2025-01-01")
        assert sig_a != sig_b
