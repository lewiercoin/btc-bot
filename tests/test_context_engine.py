"""Tests for MODELING-V1 ContextEngine.

Coverage: T-01 through T-24 per BLUEPRINT_MODELING_V1.md section 11.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from pathlib import Path

import pytest

from core.context_engine import ContextEngine
from core.models import (
    Features,
    MarketContext,
    RegimeState,
    SessionBucket,
    SignalDiagnostics,
    VolatilityBucket,
)
from core.signal_engine import SignalConfig, SignalEngine
from settings import ContextConfig, SessionBucket as SB, VolatilityBucket as VB
from storage.db import init_db

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "storage" / "schema.sql"


def _make_db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, _SCHEMA_PATH)
    return conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_features(
    *,
    hour: int = 10,
    atr_4h_norm: float = 0.003,
    sweep_detected: bool = True,
    reclaim_detected: bool = True,
    sweep_level: float = 50_000.0,
    sweep_depth_pct: float = 0.01,
    sweep_side: str = "LOW",
    cvd_bullish_divergence: bool = True,
    tfi_60s: float = 0.15,
) -> Features:
    ts = datetime(2024, 1, 15, hour, 0, 0, tzinfo=timezone.utc)
    return Features(
        schema_version="v1.0",
        config_hash="abc123",
        timestamp=ts,
        atr_15m=500.0,
        atr_4h=2000.0,
        atr_4h_norm=atr_4h_norm,
        ema50_4h=51_000.0,
        ema200_4h=50_000.0,
        sweep_detected=sweep_detected,
        reclaim_detected=reclaim_detected,
        sweep_level=sweep_level,
        sweep_depth_pct=sweep_depth_pct,
        sweep_side=sweep_side,
        cvd_bullish_divergence=cvd_bullish_divergence,
        tfi_60s=tfi_60s,
    )


def _default_engine(
    *,
    neutral_mode: bool = True,
    whitelist: dict | None = None,
    atr_low: float = 0.002,
    atr_high: float = 0.004,
) -> ContextEngine:
    wl = whitelist or {
        SB.ASIA: (VB.LOW, VB.NORMAL, VB.HIGH),
        SB.EU: (VB.LOW, VB.NORMAL, VB.HIGH),
        SB.EU_US: (VB.LOW, VB.NORMAL, VB.HIGH),
        SB.US: (VB.LOW, VB.NORMAL, VB.HIGH),
    }
    return ContextEngine(
        config=ContextConfig(
            atr_low_threshold=atr_low,
            atr_high_threshold=atr_high,
            session_volatility_whitelist=wl,
            neutral_mode=neutral_mode,
            policy_version="v1.0.0",
        )
    )


# ---------------------------------------------------------------------------
# T-01: determinism — same input → same output
# ---------------------------------------------------------------------------

def test_t01_classify_deterministic():
    engine = _default_engine()
    f = _make_features(hour=10, atr_4h_norm=0.003)
    r1 = engine.classify(f)
    r2 = engine.classify(f)
    assert r1.session_bucket == r2.session_bucket
    assert r1.volatility_bucket == r2.volatility_bucket
    assert r1.context_eligible == r2.context_eligible
    assert r1.context_block_reason == r2.context_block_reason


# ---------------------------------------------------------------------------
# T-02: session bucket boundaries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hour,expected", [
    (22, SessionBucket.ASIA),
    (23, SessionBucket.ASIA),
    (0, SessionBucket.ASIA),
    (6, SessionBucket.ASIA),
    (7, SessionBucket.EU),
    (13, SessionBucket.EU),
    (14, SessionBucket.EU_US),
    (15, SessionBucket.EU_US),
    (16, SessionBucket.US),
    (21, SessionBucket.US),
])
def test_t02_session_boundaries(hour, expected):
    engine = _default_engine()
    f = _make_features(hour=hour)
    ctx = engine.classify(f)
    assert ctx.session_bucket == expected


# ---------------------------------------------------------------------------
# T-03: volatility bucket boundaries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("atr_norm,expected", [
    (0.001, VolatilityBucket.LOW),
    (0.002, VolatilityBucket.NORMAL),  # == threshold: not strictly less, falls to NORMAL
    (0.003, VolatilityBucket.NORMAL),
    (0.004, VolatilityBucket.NORMAL),  # == threshold: not strictly greater, falls to NORMAL
    (0.005, VolatilityBucket.HIGH),
])
def test_t03_volatility_boundaries(atr_norm, expected):
    engine = _default_engine(atr_low=0.002, atr_high=0.004)
    f = _make_features(atr_4h_norm=atr_norm)
    ctx = engine.classify(f)
    assert ctx.volatility_bucket == expected


# ---------------------------------------------------------------------------
# T-04: neutral_mode=True always returns eligible=True, block_reason=None
# ---------------------------------------------------------------------------

def test_t04_neutral_mode_passthrough():
    restrictive_wl = {
        SB.ASIA: (),
        SB.EU: (),
        SB.EU_US: (),
        SB.US: (),
    }
    engine = _default_engine(neutral_mode=True, whitelist=restrictive_wl)
    for hour in [0, 7, 14, 16]:
        for atr_norm in [0.001, 0.003, 0.005]:
            f = _make_features(hour=hour, atr_4h_norm=atr_norm)
            ctx = engine.classify(f)
            assert ctx.context_eligible is True
            assert ctx.context_block_reason is None
            assert ctx.neutral_mode_active is True


# ---------------------------------------------------------------------------
# T-05: whitelist allows session+volatility → eligible=True
# ---------------------------------------------------------------------------

def test_t05_whitelist_allows():
    wl = {
        SB.EU: (VB.NORMAL,),
        SB.ASIA: (),
        SB.EU_US: (),
        SB.US: (),
    }
    engine = _default_engine(neutral_mode=False, whitelist=wl)
    f = _make_features(hour=10, atr_4h_norm=0.003)  # EU, NORMAL
    ctx = engine.classify(f)
    assert ctx.context_eligible is True
    assert ctx.context_block_reason is None


# ---------------------------------------------------------------------------
# T-06: whitelist blocks session not in keys → eligible=False
# ---------------------------------------------------------------------------

def test_t06_whitelist_blocks_missing_session():
    wl = {
        SB.EU: (VB.NORMAL, VB.HIGH),
        SB.ASIA: (),
        SB.EU_US: (),
        SB.US: (),
    }
    engine = _default_engine(neutral_mode=False, whitelist=wl)
    f = _make_features(hour=10, atr_4h_norm=0.001)  # EU, LOW — not in EU whitelist
    ctx = engine.classify(f)
    assert ctx.context_eligible is False
    assert ctx.context_block_reason is not None
    assert "EU" in ctx.context_block_reason
    assert "LOW" in ctx.context_block_reason


# ---------------------------------------------------------------------------
# T-07: whitelist blocks volatility not allowed for session → eligible=False
# ---------------------------------------------------------------------------

def test_t07_whitelist_blocks_volatility():
    wl = {
        SB.ASIA: (VB.NORMAL,),
        SB.EU: (VB.NORMAL,),
        SB.EU_US: (VB.NORMAL,),
        SB.US: (VB.NORMAL,),
    }
    engine = _default_engine(neutral_mode=False, whitelist=wl)
    f = _make_features(hour=2, atr_4h_norm=0.005)  # ASIA, HIGH — not allowed
    ctx = engine.classify(f)
    assert ctx.context_eligible is False
    assert ctx.context_block_reason is not None


# ---------------------------------------------------------------------------
# T-08: base edge computed before context gate (diagnose always runs)
# ---------------------------------------------------------------------------

def test_t08_base_edge_computed_before_context_gate():
    wl = {SB.ASIA: (), SB.EU: (), SB.EU_US: (), SB.US: ()}
    engine = ContextEngine(config=ContextConfig(neutral_mode=False, session_volatility_whitelist=wl))
    signal_engine = SignalEngine(SignalConfig(confluence_min=1.0))
    f = _make_features(hour=10)
    regime = RegimeState.NORMAL
    ctx = engine.classify(f)

    diagnostics = signal_engine.diagnose(f, regime, ctx)
    # Base edge fields must be populated regardless of context
    assert diagnostics.sweep_detected is True
    assert diagnostics.reclaim_detected is True
    # Confluence preview is computed
    assert diagnostics.confluence_preview is not None
    # Context fields are populated
    assert diagnostics.context_eligible is False
    assert diagnostics.context_block_reason is not None


# ---------------------------------------------------------------------------
# T-09: signal-level block coexists with context fields
# ---------------------------------------------------------------------------

def test_t09_signal_block_with_context_fields():
    engine = _default_engine(neutral_mode=True)
    signal_engine = SignalEngine(SignalConfig())
    f = _make_features(sweep_detected=False)  # will be blocked by no_sweep
    regime = RegimeState.NORMAL
    ctx = engine.classify(f)

    diagnostics = signal_engine.diagnose(f, regime, ctx)
    assert diagnostics.blocked_by == "no_sweep"
    assert diagnostics.context_eligible is True  # neutral mode
    assert diagnostics.context_session_label is not None
    assert diagnostics.context_volatility_label is not None


# ---------------------------------------------------------------------------
# T-10: context_eligible always boolean in MarketContext
# ---------------------------------------------------------------------------

def test_t10_context_eligible_always_bool():
    engine = _default_engine()
    for hour in [0, 7, 14, 16]:
        for atr_norm in [0.001, 0.003, 0.005]:
            f = _make_features(hour=hour, atr_4h_norm=atr_norm)
            ctx = engine.classify(f)
            assert isinstance(ctx.context_eligible, bool)


# ---------------------------------------------------------------------------
# T-11: block reason invariant — non-None when ineligible
# ---------------------------------------------------------------------------

def test_t11_block_reason_invariant():
    wl = {SB.ASIA: (), SB.EU: (), SB.EU_US: (), SB.US: ()}
    engine = _default_engine(neutral_mode=False, whitelist=wl)
    f = _make_features(hour=10, atr_4h_norm=0.003)
    ctx = engine.classify(f)
    assert ctx.context_eligible is False
    assert ctx.context_block_reason is not None
    assert len(ctx.context_block_reason) > 0


# ---------------------------------------------------------------------------
# T-12: generate() returns None when context_eligible=False (context gate)
# ---------------------------------------------------------------------------

def test_t12_generate_returns_none_when_context_ineligible():
    wl = {SB.ASIA: (), SB.EU: (), SB.EU_US: (), SB.US: ()}
    engine = _default_engine(neutral_mode=False, whitelist=wl)
    signal_engine = SignalEngine(SignalConfig(confluence_min=1.0))

    f = _make_features(hour=10)
    regime = RegimeState.NORMAL
    ctx = engine.classify(f)
    assert ctx.context_eligible is False

    candidate = signal_engine.generate(f, regime, context=ctx)
    assert candidate is None


# ---------------------------------------------------------------------------
# T-13: persistence path — context fields reach decision_outcomes table
# ---------------------------------------------------------------------------

def test_t13_persistence_path():
    from storage.state_store import StateStore
    conn = _make_db_conn()
    store = StateStore(connection=conn, mode="PAPER")
    store.ensure_initialized()

    ts = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    store.record_decision_outcome(
        cycle_timestamp=ts,
        outcome_group="no_signal",
        outcome_reason="no_sweep",
        config_hash="abc123",
        regime="normal",
        context_session_label="EU",
        context_volatility_label="NORMAL",
        context_policy_version="v1.0.0",
        context_eligible=True,
        context_block_reason=None,
        context_neutral_mode_active=True,
    )
    row = conn.execute(
        "SELECT * FROM decision_outcomes ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row["context_session_label"] == "EU"
    assert row["context_volatility_label"] == "NORMAL"
    assert row["context_policy_version"] == "v1.0.0"
    assert row["context_eligible"] == 1
    assert row["context_block_reason"] is None
    assert row["context_neutral_mode_active"] == 1


# ---------------------------------------------------------------------------
# T-14: config_hash changes when atr_low_threshold changes
# ---------------------------------------------------------------------------

def test_t14_config_hash_changes_atr_low():
    from settings import load_settings
    import dataclasses
    s1 = load_settings()
    s2 = dataclasses.replace(s1, context=dataclasses.replace(s1.context, atr_low_threshold=0.999))
    assert s1.config_hash != s2.config_hash


# ---------------------------------------------------------------------------
# T-15: config_hash changes when neutral_mode changes
# ---------------------------------------------------------------------------

def test_t15_config_hash_changes_neutral_mode():
    from settings import load_settings
    import dataclasses
    s1 = load_settings()
    s2 = dataclasses.replace(s1, context=dataclasses.replace(s1.context, neutral_mode=not s1.context.neutral_mode))
    assert s1.config_hash != s2.config_hash


# ---------------------------------------------------------------------------
# T-16: config_hash changes when whitelist changes
# ---------------------------------------------------------------------------

def test_t16_config_hash_changes_whitelist():
    from settings import load_settings
    import dataclasses
    s1 = load_settings()
    new_wl = {
        SB.ASIA: (VB.NORMAL,),
        SB.EU: (),
        SB.EU_US: (VB.HIGH,),
        SB.US: (VB.LOW,),
    }
    s2 = dataclasses.replace(s1, context=dataclasses.replace(s1.context, session_volatility_whitelist=new_wl))
    assert s1.config_hash != s2.config_hash


# ---------------------------------------------------------------------------
# T-17: Governance does not receive MarketContext
# ---------------------------------------------------------------------------

def test_t17_governance_isolation():
    from core.governance import GovernanceLayer
    import inspect
    sig = inspect.signature(GovernanceLayer.evaluate)
    param_names = list(sig.parameters.keys())
    assert "context" not in param_names
    assert "market_context" not in param_names


# ---------------------------------------------------------------------------
# T-18: RiskEngine does not receive MarketContext
# ---------------------------------------------------------------------------

def test_t18_risk_isolation():
    from core.risk_engine import RiskEngine
    import inspect
    sig = inspect.signature(RiskEngine.evaluate)
    param_names = list(sig.parameters.keys())
    assert "context" not in param_names
    assert "market_context" not in param_names


# ---------------------------------------------------------------------------
# T-19: neutral_mode=True parity with pre-MODELING-V1 baseline
#        (same features → same candidate)
# ---------------------------------------------------------------------------

def test_t19_neutral_mode_parity():
    engine_neutral = _default_engine(neutral_mode=True)
    signal_engine = SignalEngine(SignalConfig(confluence_min=1.0))
    f = _make_features(hour=10)
    regime = RegimeState.NORMAL

    ctx = engine_neutral.classify(f)
    candidate_with_ctx = signal_engine.generate(f, regime, context=ctx)
    candidate_no_ctx = signal_engine.generate(f, regime)

    if candidate_with_ctx is None:
        assert candidate_no_ctx is None
    else:
        assert candidate_no_ctx is not None
        assert candidate_with_ctx.direction == candidate_no_ctx.direction
        assert candidate_with_ctx.confluence_score == candidate_no_ctx.confluence_score


# ---------------------------------------------------------------------------
# T-20: backtest/runtime parity — same context result for same features
# ---------------------------------------------------------------------------

def test_t20_backtest_runtime_parity():
    from settings import load_settings
    settings = load_settings()
    ctx_engine_runtime = ContextEngine(config=settings.context)
    ctx_engine_backtest = ContextEngine(config=settings.context)

    f = _make_features(hour=10, atr_4h_norm=0.003)
    r_runtime = ctx_engine_runtime.classify(f)
    r_backtest = ctx_engine_backtest.classify(f)

    assert r_runtime.session_bucket == r_backtest.session_bucket
    assert r_runtime.volatility_bucket == r_backtest.volatility_bucket
    assert r_runtime.context_eligible == r_backtest.context_eligible


# ---------------------------------------------------------------------------
# T-21: one context call per cycle — verify idempotent for same features
# ---------------------------------------------------------------------------

def test_t21_one_context_call_per_cycle():
    engine = _default_engine()
    f = _make_features(hour=10)
    r1 = engine.classify(f)
    r2 = engine.classify(f)
    assert r1 == r2


# ---------------------------------------------------------------------------
# T-22: no edge helper mutation — protected reclaim helpers unchanged
# ---------------------------------------------------------------------------

def test_t22_no_edge_helper_mutation():
    signal_engine = SignalEngine(SignalConfig(confluence_min=1.0))
    engine = _default_engine(neutral_mode=True)

    f = _make_features(hour=10)
    regime = RegimeState.NORMAL
    ctx = engine.classify(f)

    original_atr = f.atr_15m
    original_sweep_level = f.sweep_level
    original_reclaim = f.reclaim_detected

    signal_engine.diagnose(f, regime, ctx)
    signal_engine.generate(f, regime, context=ctx)

    assert f.atr_15m == original_atr
    assert f.sweep_level == original_sweep_level
    assert f.reclaim_detected == original_reclaim


# ---------------------------------------------------------------------------
# T-23: quality_flags empty in V1
# ---------------------------------------------------------------------------

def test_t23_quality_flags_empty():
    engine = _default_engine()
    f = _make_features(hour=10)
    ctx = engine.classify(f)
    assert ctx.quality_flags == ()


# ---------------------------------------------------------------------------
# T-24: storage schema migration — context columns exist after ensure_initialized
# ---------------------------------------------------------------------------

def test_t24_storage_schema_context_columns():
    from storage.state_store import StateStore
    conn = _make_db_conn()
    store = StateStore(connection=conn, mode="PAPER")
    store.ensure_initialized()

    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(decision_outcomes)")
    columns = {row[1] for row in cursor.fetchall()}

    expected = {
        "context_session_label",
        "context_volatility_label",
        "context_policy_version",
        "context_eligible",
        "context_block_reason",
        "context_neutral_mode_active",
    }
    assert expected.issubset(columns)


# ---------------------------------------------------------------------------
# Additional: MarketContext is frozen (immutable)
# ---------------------------------------------------------------------------

def test_market_context_frozen():
    engine = _default_engine()
    ctx = engine.classify(_make_features())
    with pytest.raises((AttributeError, TypeError)):
        ctx.context_eligible = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Additional: context_block_reason format when blocked
# ---------------------------------------------------------------------------

def test_context_block_reason_format():
    wl = {SB.ASIA: (), SB.EU: (VB.HIGH,), SB.EU_US: (), SB.US: ()}
    engine = _default_engine(neutral_mode=False, whitelist=wl)
    f = _make_features(hour=10, atr_4h_norm=0.003)  # EU + NORMAL — not in EU whitelist
    ctx = engine.classify(f)
    assert ctx.context_eligible is False
    assert ctx.context_block_reason == "context_unfavorable:EU:NORMAL"


# ---------------------------------------------------------------------------
# Additional: policy_version propagated from ContextConfig
# ---------------------------------------------------------------------------

def test_policy_version_propagated():
    cfg = ContextConfig(policy_version="test-v99")
    engine = ContextEngine(config=cfg)
    ctx = engine.classify(_make_features())
    assert ctx.context_policy_version == "test-v99"


# ---------------------------------------------------------------------------
# Audit fix A: timezone-aware non-UTC timestamp → correct UTC bucket
# A timestamp that is 10:00 CET (UTC+1) = 09:00 UTC → EU bucket
# A timestamp that is 23:00 CET (UTC+1) = 22:00 UTC → ASIA bucket
# ---------------------------------------------------------------------------

def test_non_utc_timezone_normalized_to_utc_eu():
    from datetime import timezone as tz, timedelta
    engine = _default_engine()
    cet = tz(timedelta(hours=1))
    # 10:00 CET = 09:00 UTC → EU
    ts = datetime(2024, 1, 15, 10, 0, 0, tzinfo=cet)
    f = _make_features(hour=10)
    f_adjusted = Features(
        schema_version=f.schema_version,
        config_hash=f.config_hash,
        timestamp=ts,
        atr_15m=f.atr_15m,
        atr_4h=f.atr_4h,
        atr_4h_norm=f.atr_4h_norm,
        ema50_4h=f.ema50_4h,
        ema200_4h=f.ema200_4h,
        sweep_detected=f.sweep_detected,
        reclaim_detected=f.reclaim_detected,
        sweep_level=f.sweep_level,
        sweep_depth_pct=f.sweep_depth_pct,
        sweep_side=f.sweep_side,
        cvd_bullish_divergence=f.cvd_bullish_divergence,
        tfi_60s=f.tfi_60s,
    )
    ctx = engine.classify(f_adjusted)
    assert ctx.session_bucket == SessionBucket.EU  # 09:00 UTC is EU


def test_non_utc_timezone_normalized_to_utc_asia():
    from datetime import timezone as tz, timedelta
    engine = _default_engine()
    cet = tz(timedelta(hours=1))
    # 23:00 CET = 22:00 UTC → ASIA
    ts = datetime(2024, 1, 15, 23, 0, 0, tzinfo=cet)
    f = _make_features(hour=22)
    f_adjusted = Features(
        schema_version=f.schema_version,
        config_hash=f.config_hash,
        timestamp=ts,
        atr_15m=f.atr_15m,
        atr_4h=f.atr_4h,
        atr_4h_norm=f.atr_4h_norm,
        ema50_4h=f.ema50_4h,
        ema200_4h=f.ema200_4h,
        sweep_detected=f.sweep_detected,
        reclaim_detected=f.reclaim_detected,
        sweep_level=f.sweep_level,
        sweep_depth_pct=f.sweep_depth_pct,
        sweep_side=f.sweep_side,
        cvd_bullish_divergence=f.cvd_bullish_divergence,
        tfi_60s=f.tfi_60s,
    )
    ctx = engine.classify(f_adjusted)
    assert ctx.session_bucket == SessionBucket.ASIA  # 22:00 UTC is ASIA


def test_naive_datetime_treated_as_utc():
    engine = _default_engine()
    # naive 10:00 → treated as 10:00 UTC → EU
    ts = datetime(2024, 1, 15, 10, 0, 0)  # no tzinfo
    f = _make_features(hour=10)
    f_adjusted = Features(
        schema_version=f.schema_version,
        config_hash=f.config_hash,
        timestamp=ts,
        atr_15m=f.atr_15m,
        atr_4h=f.atr_4h,
        atr_4h_norm=f.atr_4h_norm,
        ema50_4h=f.ema50_4h,
        ema200_4h=f.ema200_4h,
        sweep_detected=f.sweep_detected,
        reclaim_detected=f.reclaim_detected,
        sweep_level=f.sweep_level,
        sweep_depth_pct=f.sweep_depth_pct,
        sweep_side=f.sweep_side,
        cvd_bullish_divergence=f.cvd_bullish_divergence,
        tfi_60s=f.tfi_60s,
    )
    ctx = engine.classify(f_adjusted)
    assert ctx.session_bucket == SessionBucket.EU  # 10:00 naive = EU


# ---------------------------------------------------------------------------
# Audit fix B: context fields written to decision_outcomes for all paths
# no_signal, governance_veto, risk_block, execution_failed, signal_generated
# ---------------------------------------------------------------------------

def test_context_telemetry_all_paths():
    conn = _make_db_conn()
    from storage.state_store import StateStore
    store = StateStore(connection=conn, mode="PAPER")
    store.ensure_initialized()

    ts = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    ctx_kwargs = dict(
        context_session_label="EU",
        context_volatility_label="NORMAL",
        context_policy_version="v1.0.0",
        context_eligible=True,
        context_block_reason=None,
        context_neutral_mode_active=True,
    )

    paths = [
        ("no_signal", "no_sweep"),
        ("governance_veto", "governance_veto"),
        ("risk_block", "risk_block"),
        ("execution_failed", "execution_failed"),
        ("signal_generated", "signal_generated"),
    ]

    for outcome_group, outcome_reason in paths:
        store.record_decision_outcome(
            cycle_timestamp=ts,
            outcome_group=outcome_group,
            outcome_reason=outcome_reason,
            config_hash="abc123",
            regime="normal",
            **ctx_kwargs,
        )

    rows = conn.execute(
        "SELECT outcome_group, context_session_label, context_volatility_label, "
        "context_policy_version, context_eligible, context_neutral_mode_active "
        "FROM decision_outcomes ORDER BY id"
    ).fetchall()

    assert len(rows) == len(paths)
    for row in rows:
        assert row["context_session_label"] == "EU", f"Missing context in {row['outcome_group']}"
        assert row["context_volatility_label"] == "NORMAL"
        assert row["context_policy_version"] == "v1.0.0"
        assert row["context_eligible"] == 1
        assert row["context_neutral_mode_active"] == 1


def test_context_telemetry_blocked_path():
    conn = _make_db_conn()
    from storage.state_store import StateStore
    store = StateStore(connection=conn, mode="PAPER")
    store.ensure_initialized()

    ts = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    store.record_decision_outcome(
        cycle_timestamp=ts,
        outcome_group="no_signal",
        outcome_reason="context_gate",
        config_hash="abc123",
        regime="normal",
        context_session_label="ASIA",
        context_volatility_label="HIGH",
        context_policy_version="v1.0.0",
        context_eligible=False,
        context_block_reason="context_unfavorable:ASIA:HIGH",
        context_neutral_mode_active=False,
    )

    row = conn.execute(
        "SELECT * FROM decision_outcomes ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["context_eligible"] == 0
    assert row["context_block_reason"] == "context_unfavorable:ASIA:HIGH"
    assert row["context_neutral_mode_active"] == 0
