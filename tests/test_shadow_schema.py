from __future__ import annotations

import json
import sqlite3

import pytest

from research_lab.shadow_schema import initialize_shadow_schema, insert_near_miss, validate_near_miss_payload


REQUIRED_TABLES = {
    "shadow_runs",
    "shadow_decision_outcomes",
    "shadow_signal_candidates",
    "shadow_portfolio_decisions",
    "shadow_near_miss_diagnostics",
    "shadow_resource_samples",
}


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_shadow_schema_creates_all_required_tables() -> None:
    with sqlite3.connect(":memory:") as conn:
        initialize_shadow_schema(conn)

        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert REQUIRED_TABLES <= tables


def test_shadow_decision_outcomes_has_required_payload_fields() -> None:
    with sqlite3.connect(":memory:") as conn:
        initialize_shadow_schema(conn)

        columns = table_columns(conn, "shadow_decision_outcomes")
    required = {
        "shadow_run_id",
        "symbol",
        "timestamp_utc",
        "strategy_profile",
        "risk_policy_profile",
        "shadow_mode",
        "config_hash",
        "signal_generated",
        "signal_blocker",
        "sweep_detected",
        "reclaim_detected",
        "sweep_depth_pct",
        "min_sweep_depth_pct",
        "regime",
        "context_session",
        "confluence_score_preview",
        "candidate_direction_preview",
        "symbol_governance_shadow_decision",
        "symbol_risk_shadow_decision",
        "portfolio_shadow_decision",
        "portfolio_veto_reason",
        "candidate_risk_pct",
        "portfolio_risk_after_pct",
        "resource_guard_status",
        "details_json",
    }
    assert required <= columns


def test_near_miss_payload_requires_nested_sweep_depth_pct() -> None:
    with pytest.raises(ValueError):
        validate_near_miss_payload({"near_miss_diagnostics": {"symbol": "ETHUSDT"}})

    validate_near_miss_payload(
        {"near_miss_diagnostics": {"symbol": "ETHUSDT", "sweep_depth_pct": 0.00584}}
    )


def test_insert_near_miss_persists_nested_depth_payload() -> None:
    with sqlite3.connect(":memory:") as conn:
        initialize_shadow_schema(conn)

        insert_near_miss(
            conn,
            shadow_run_id="run-1",
            symbol="SOLUSDT",
            timestamp_utc="2026-05-20T00:00:00Z",
            sweep_depth_pct=0.00584,
            threshold=0.00649,
            depth_bucket="near_miss_high",
            regime="uptrend",
            session_hour=12,
            rejection_reasons=["sweep_too_shallow"],
            created_at_utc="2026-05-20T00:00:01Z",
        )

        row = conn.execute(
            "SELECT near_miss_payload_json FROM shadow_near_miss_diagnostics"
        ).fetchone()
    payload = json.loads(row[0])
    assert payload["near_miss_diagnostics"]["symbol"] == "SOLUSDT"
    assert payload["near_miss_diagnostics"]["sweep_depth_pct"] == 0.00584
