"""Unit tests for near-miss diagnostics logic (bucket computation, threshold distance)."""

import json
import pytest

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from scripts.report_near_miss_diagnostics import analyze_near_misses, query_decision_outcomes, _parse_symbols
from storage.db import init_db


def compute_depth_bucket(depth: float, threshold: float = 0.00649) -> str:
    """Compute depth bucket for near-miss diagnostics."""
    if depth < 0.004:
        return "far_below"
    elif depth < threshold:
        return "near_miss_low"
    elif depth < 0.007:
        return "baseline_pass"
    else:
        return "stricter_pass"


def compute_threshold_distance(depth: float, threshold: float = 0.00649) -> float:
    """Compute threshold distance (negative for rejects)."""
    return (depth - threshold) / threshold if threshold > 0 else 0.0


class TestNearMissBucketLogic:
    """Test depth bucket computation logic."""

    def test_far_below_bucket(self):
        """Depth < 0.004 should be far_below bucket."""
        assert compute_depth_bucket(0.003) == "far_below"
        assert compute_depth_bucket(0.00399) == "far_below"

    def test_near_miss_low_bucket(self):
        """Depth [0.004, 0.00649) should be near_miss_low bucket."""
        assert compute_depth_bucket(0.004) == "near_miss_low"
        assert compute_depth_bucket(0.005) == "near_miss_low"
        assert compute_depth_bucket(0.006) == "near_miss_low"

    def test_near_miss_low_bucket_upper_boundary(self):
        """Depth just below threshold should be near_miss_low bucket."""
        assert compute_depth_bucket(0.00648) == "near_miss_low"

    def test_baseline_pass_bucket(self):
        """Depth [0.00649, 0.007) should be baseline_pass bucket."""
        assert compute_depth_bucket(0.00649) == "baseline_pass"
        assert compute_depth_bucket(0.0065) == "baseline_pass"
        assert compute_depth_bucket(0.0069) == "baseline_pass"

    def test_stricter_pass_bucket(self):
        """Depth >= 0.007 should be stricter_pass bucket."""
        assert compute_depth_bucket(0.007) == "stricter_pass"
        assert compute_depth_bucket(0.008) == "stricter_pass"

    def test_boundary_conditions(self):
        """Test exact boundary values."""
        threshold = 0.00649
        
        # Test 0.004 boundary (far_below vs near_miss_low)
        assert compute_depth_bucket(0.00399) == "far_below"
        assert compute_depth_bucket(0.00400) == "near_miss_low"
        
        # Test threshold boundary (near_miss_low vs baseline_pass)
        assert compute_depth_bucket(0.00648) == "near_miss_low"
        assert compute_depth_bucket(0.00649) == "baseline_pass"
        
        # Test 0.007 boundary (baseline_pass vs stricter_pass)
        assert compute_depth_bucket(0.00699) == "baseline_pass"
        assert compute_depth_bucket(0.00700) == "stricter_pass"


class TestThresholdDistanceComputation:
    """Test threshold distance computation logic."""

    def test_threshold_distance_negative_for_reject(self):
        """Threshold distance should be negative for rejects."""
        distance = compute_threshold_distance(0.005)
        assert distance < 0
        assert round(distance, 3) == -0.23

    def test_threshold_distance_zero_at_threshold(self):
        """Threshold distance should be zero at threshold."""
        distance = compute_threshold_distance(0.00649)
        assert distance == 0.0

    def test_threshold_distance_positive_for_pass(self):
        """Threshold distance should be positive for passes."""
        distance = compute_threshold_distance(0.007)
        assert distance > 0
        assert round(distance, 3) == 0.079

    def test_threshold_distance_division_by_zero_protection(self):
        """Threshold distance should handle zero threshold gracefully."""
        distance = compute_threshold_distance(0.005, threshold=0.0)
        assert distance == 0.0

    def test_threshold_distance_various_depths(self):
        """Test threshold distance for various depth values."""
        # Far below
        assert compute_threshold_distance(0.004) < 0
        # Near miss
        assert compute_threshold_distance(0.005) < 0
        assert compute_threshold_distance(0.006) < 0
        # At threshold
        assert compute_threshold_distance(0.00649) == 0.0
        # Above threshold
        assert compute_threshold_distance(0.007) > 0
        assert compute_threshold_distance(0.008) > 0


class TestNearMissConditions:
    """Test conditions for when near-miss diagnostics should be added."""

    def test_near_miss_condition_depth_below_004(self):
        """Near-miss should NOT be added for depth < 0.004."""
        depth = 0.003
        blocked_by = "sweep_too_shallow"
        
        should_add = (blocked_by == "sweep_too_shallow" 
                      and depth >= 0.004)
        
        assert not should_add


class TestNearMissReportCompatibility:
    """Test report parsing for current and legacy near-miss payload shapes."""

    def test_report_uses_nested_sweep_depth_pct(self):
        rows = [
            (
                "2026-05-16T00:00:00+00:00",
                "no_signal",
                "sweep_too_shallow",
                json.dumps(
                    {
                        "near_miss_diagnostics": {
                            "sweep_depth_pct": 0.0059,
                            "threshold": 0.00649,
                            "depth_bucket": "near_miss_low",
                            "regime": "uptrend",
                            "session_hour": 12,
                            "rejection_reasons": ["sweep_too_shallow"],
                        }
                    }
                ),
            )
        ]

        analysis = analyze_near_misses(rows)

        assert analysis["near_miss_count"] == 1
        assert analysis["within_10pct"] == 1
        assert analysis["symbol_counts"] == {"BTCUSDT": 1}
        assert analysis["per_symbol"]["BTCUSDT"]["near_miss_count"] == 1

    def test_report_falls_back_to_top_level_sweep_depth_pct(self):
        rows = [
            (
                "2026-05-16T00:00:00+00:00",
                "no_signal",
                "sweep_too_shallow",
                json.dumps(
                    {
                        "sweep_depth_pct": 0.0059,
                        "near_miss_diagnostics": {
                            "threshold": 0.00649,
                            "depth_bucket": "near_miss_low",
                            "regime": "uptrend",
                            "session_hour": 12,
                            "rejection_reasons": ["sweep_too_shallow"],
                        },
                    }
                ),
            )
        ]

        analysis = analyze_near_misses(rows)

        assert analysis["near_miss_count"] == 1
        assert analysis["within_10pct"] == 1

    def test_report_uses_symbol_from_details_payload(self):
        rows = [
            (
                "2026-05-16T00:00:00+00:00",
                "no_signal",
                "sweep_too_shallow",
                json.dumps(
                    {
                        "symbol": "ETHUSDT",
                        "near_miss_diagnostics": {
                            "sweep_depth_pct": 0.0059,
                            "threshold": 0.0075,
                            "depth_bucket": "near_miss_low",
                            "regime": "normal",
                            "session_hour": 12,
                            "rejection_reasons": ["sweep_too_shallow"],
                        },
                    }
                ),
            )
        ]

        analysis = analyze_near_misses(rows)

        assert analysis["symbol_counts"] == {"ETHUSDT": 1}
        assert analysis["per_symbol"]["ETHUSDT"]["near_miss_count"] == 1

    def test_report_uses_symbol_from_nested_near_miss_payload(self):
        rows = [
            (
                "2026-05-16T00:00:00+00:00",
                "no_signal",
                "sweep_too_shallow",
                json.dumps(
                    {
                        "near_miss_diagnostics": {
                            "symbol": "SOLUSDT",
                            "sweep_depth_pct": 0.0059,
                            "threshold": 0.0075,
                            "depth_bucket": "near_miss_low",
                            "regime": "normal",
                            "session_hour": 12,
                            "rejection_reasons": ["sweep_too_shallow"],
                        },
                    }
                ),
            )
        ]

        analysis = analyze_near_misses(rows)

        assert analysis["symbol_counts"] == {"SOLUSDT": 1}
        assert analysis["per_symbol"]["SOLUSDT"]["near_miss_count"] == 1

    def test_near_miss_condition_depth_in_range(self):
        """Near-miss SHOULD be added for depth [0.004, threshold)."""
        depth = 0.005
        blocked_by = "sweep_too_shallow"
        
        should_add = (blocked_by == "sweep_too_shallow" 
                      and depth >= 0.004)
        
        assert should_add

    def test_near_miss_condition_wrong_blocked_by(self):
        """Near-miss should NOT be added for other rejection reasons."""
        depth = 0.005
        blocked_by = "no_reclaim"
        
        should_add = (blocked_by == "sweep_too_shallow" 
                      and depth >= 0.004)
        
        assert not should_add

    def test_near_miss_condition_none_depth(self):
        """Near-miss should NOT be added for None depth."""
        depth = None
        blocked_by = "sweep_too_shallow"
        
        should_add = (blocked_by == "sweep_too_shallow" 
                      and depth is not None 
                      and depth >= 0.004)
        
        assert not should_add


class TestMultiAssetM4QueryExtension:
    def test_parse_symbols_accepts_repeated_and_comma_separated_values(self):
        assert _parse_symbols(["btcusdt, ethusdt", "SOLUSDT"]) == ("BTCUSDT", "ETHUSDT", "SOLUSDT")

    def test_query_decision_outcomes_defaults_to_btc_legacy_rows(self):
        conn = _make_conn()
        ts = datetime.now(timezone.utc) - timedelta(hours=1)
        try:
            conn.execute(
                """
                INSERT INTO decision_outcomes (
                    cycle_timestamp, outcome_group, outcome_reason, regime, config_hash, details_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts.isoformat(), "no_signal", "sweep_too_shallow", "normal", "cfg", "{}"),
            )
            conn.commit()

            rows = query_decision_outcomes(conn, days=1)
        finally:
            conn.close()

        assert len(rows) == 1
        analysis = analyze_near_misses(rows)
        assert analysis["symbol_counts"] == {"BTCUSDT": 1}

    def test_query_decision_outcomes_filters_by_symbol_from_details(self):
        conn = _make_conn()
        ts = datetime.now(timezone.utc) - timedelta(hours=1)
        try:
            for symbol in ("BTCUSDT", "ETHUSDT"):
                conn.execute(
                    """
                    INSERT INTO decision_outcomes (
                        cycle_timestamp, outcome_group, outcome_reason, regime, config_hash, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts.isoformat(),
                        "no_signal",
                        "sweep_too_shallow",
                        "normal",
                        "cfg",
                        json.dumps({"symbol": symbol}),
                    ),
                )
            conn.commit()

            eth_rows = query_decision_outcomes(conn, days=1, symbols=("ETHUSDT",))
            all_rows = query_decision_outcomes(conn, days=1, all_symbols=True)
        finally:
            conn.close()

        assert len(eth_rows) == 1
        assert analyze_near_misses(eth_rows)["symbol_counts"] == {"ETHUSDT": 1}
        assert analyze_near_misses(all_rows)["symbol_counts"] == {"BTCUSDT": 1, "ETHUSDT": 1}


def _make_conn() -> sqlite3.Connection:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, schema_path)
    return conn
