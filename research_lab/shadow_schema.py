"""SQLite schema and safe-path guards for the multi-asset shadow sidecar."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SHADOW_DB_DEFAULT = Path("research_lab/shadow/multi_asset_shadow.db")


class ShadowPathError(ValueError):
    """Raised when a sidecar path would escape the shadow storage boundary."""


def shadow_root(repo_root: Path | None = None) -> Path:
    root = (repo_root or Path.cwd()).resolve()
    return root / "research_lab" / "shadow"


def resolve_shadow_db_path(db_path: str | Path, repo_root: Path | None = None) -> Path:
    """Resolve and validate a sidecar DB path under research_lab/shadow."""

    root = shadow_root(repo_root)
    candidate = Path(db_path)
    if not candidate.is_absolute():
        candidate = (repo_root or Path.cwd()) / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ShadowPathError(
            f"Shadow DB path must stay under {root}; got {resolved}"
        ) from exc
    if resolved.name in {"", ".", ".."}:
        raise ShadowPathError(f"Shadow DB path must be a file path; got {resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def connect_shadow_db(db_path: str | Path, repo_root: Path | None = None) -> sqlite3.Connection:
    path = resolve_shadow_db_path(db_path, repo_root=repo_root)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def initialize_shadow_schema(conn: sqlite3.Connection) -> None:
    """Create all sidecar tables without touching production storage."""

    conn.executescript(
        """
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS shadow_runs (
            shadow_run_id TEXT PRIMARY KEY,
            service_start_time_utc TEXT NOT NULL,
            git_commit TEXT NOT NULL,
            code_version TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            dry_run INTEGER NOT NULL DEFAULT 0,
            lock_path TEXT NOT NULL,
            db_path TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shadow_decision_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shadow_run_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timestamp_utc TEXT NOT NULL,
            strategy_profile TEXT NOT NULL,
            risk_policy_profile TEXT NOT NULL,
            shadow_mode TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            signal_generated INTEGER NOT NULL,
            signal_blocker TEXT,
            sweep_detected INTEGER NOT NULL,
            reclaim_detected INTEGER NOT NULL,
            sweep_depth_pct REAL,
            min_sweep_depth_pct REAL NOT NULL,
            regime TEXT,
            context_session TEXT,
            confluence_score_preview REAL,
            candidate_direction_preview TEXT,
            symbol_governance_shadow_decision TEXT NOT NULL,
            symbol_risk_shadow_decision TEXT NOT NULL,
            portfolio_shadow_decision TEXT NOT NULL,
            portfolio_veto_reason TEXT,
            candidate_risk_pct REAL NOT NULL,
            portfolio_risk_after_pct REAL NOT NULL,
            resource_guard_status TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            UNIQUE(shadow_run_id, symbol, timestamp_utc, strategy_profile)
        );

        CREATE TABLE IF NOT EXISTS shadow_signal_candidates (
            signal_id TEXT PRIMARY KEY,
            shadow_run_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timestamp_utc TEXT NOT NULL,
            direction TEXT,
            setup_type TEXT NOT NULL,
            confluence_score REAL NOT NULL,
            strategy_profile TEXT NOT NULL,
            risk_policy_profile TEXT NOT NULL,
            reasons_json TEXT NOT NULL,
            features_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shadow_portfolio_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shadow_run_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timestamp_utc TEXT NOT NULL,
            signal_id TEXT,
            portfolio_shadow_decision TEXT NOT NULL,
            portfolio_veto_reason TEXT,
            candidate_risk_pct REAL NOT NULL,
            portfolio_risk_before_pct REAL NOT NULL,
            portfolio_risk_after_pct REAL NOT NULL,
            gross_notional_after_pct REAL,
            directional_notional_after_pct REAL,
            details_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shadow_near_miss_diagnostics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shadow_run_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timestamp_utc TEXT NOT NULL,
            sweep_depth_pct REAL NOT NULL,
            threshold REAL NOT NULL,
            depth_gap_pct REAL NOT NULL,
            depth_bucket TEXT NOT NULL,
            regime TEXT,
            session_hour INTEGER,
            rejection_reasons_json TEXT NOT NULL,
            near_miss_payload_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shadow_resource_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shadow_run_id TEXT NOT NULL,
            timestamp_utc TEXT NOT NULL,
            disk_free_bytes INTEGER NOT NULL,
            disk_total_bytes INTEGER NOT NULL,
            memory_rss_bytes INTEGER,
            cpu_user_seconds REAL,
            cpu_system_seconds REAL,
            process_id INTEGER NOT NULL,
            guard_status TEXT NOT NULL,
            details_json TEXT NOT NULL
        );
        """
    )
    conn.commit()


def validate_near_miss_payload(payload: dict[str, Any]) -> None:
    diagnostics = payload.get("near_miss_diagnostics")
    if not isinstance(diagnostics, dict):
        raise ValueError("near_miss_diagnostics object is required")
    if diagnostics.get("sweep_depth_pct") is None:
        raise ValueError("near_miss_diagnostics.sweep_depth_pct is required")


def insert_near_miss(
    conn: sqlite3.Connection,
    *,
    shadow_run_id: str,
    symbol: str,
    timestamp_utc: str,
    sweep_depth_pct: float,
    threshold: float,
    depth_bucket: str,
    regime: str | None,
    session_hour: int | None,
    rejection_reasons: list[str],
    created_at_utc: str,
) -> None:
    payload = {
        "near_miss_diagnostics": {
            "symbol": symbol,
            "sweep_depth_pct": sweep_depth_pct,
            "threshold": threshold,
            "depth_gap_pct": threshold - sweep_depth_pct,
            "depth_bucket": depth_bucket,
            "regime": regime,
            "session_hour": session_hour,
            "rejection_reasons": rejection_reasons,
        }
    }
    validate_near_miss_payload(payload)
    conn.execute(
        """
        INSERT INTO shadow_near_miss_diagnostics (
            shadow_run_id, symbol, timestamp_utc, sweep_depth_pct, threshold,
            depth_gap_pct, depth_bucket, regime, session_hour,
            rejection_reasons_json, near_miss_payload_json, created_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            shadow_run_id,
            symbol,
            timestamp_utc,
            sweep_depth_pct,
            threshold,
            threshold - sweep_depth_pct,
            depth_bucket,
            regime,
            session_hour,
            json.dumps(rejection_reasons, sort_keys=True),
            json.dumps(payload, sort_keys=True),
            created_at_utc,
        ),
    )
    conn.commit()
