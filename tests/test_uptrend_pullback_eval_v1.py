from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from core.models import TradeLog
from research_lab.diagnostics import uptrend_pullback_eval_v1 as module
from settings import load_settings


def _record(
    *,
    event_id: str,
    candidate_generated: bool = False,
    pre_candidate_blocked_by: str | None = None,
    signal_id: str | None = None,
    confluence_score: float | None = None,
    tfi_60s: float = 0.15,
    sweep_depth_pct: float | None = 0.004,
    ema_gap_pct: float = 0.02,
    governance_veto_reason: str | None = None,
    risk_block_reason: str | None = None,
    trade_opened: bool = False,
    trade_closed: bool = False,
    pnl_abs: float | None = None,
    pnl_r: float | None = None,
    outcome_bucket: str | None = None,
    exit_reason: str | None = None,
) -> module.PullbackEventRecord:
    return module.PullbackEventRecord(
        event_id=event_id,
        timestamp=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
        candidate_generated=candidate_generated,
        pre_candidate_blocked_by=pre_candidate_blocked_by,
        signal_id=signal_id,
        candidate_reasons=[],
        confluence_score=confluence_score,
        tfi_60s=tfi_60s,
        sweep_depth_pct=sweep_depth_pct,
        ema_gap_pct=ema_gap_pct,
        funding_8h=0.0,
        governance_veto_reason=governance_veto_reason,
        risk_block_reason=risk_block_reason,
        trade_opened=trade_opened,
        trade_closed=trade_closed,
        trade_id=None,
        pnl_abs=pnl_abs,
        pnl_r=pnl_r,
        exit_reason=exit_reason,
        outcome_bucket=outcome_bucket,
    )


def test_build_stage_counts_tracks_funnel_breakdown() -> None:
    records = [
        _record(event_id="evt-1", pre_candidate_blocked_by="uptrend_pullback_weak"),
        _record(
            event_id="evt-2",
            candidate_generated=True,
            signal_id="sig-2",
            confluence_score=8.4,
            governance_veto_reason="duplicate_level",
        ),
        _record(
            event_id="evt-3",
            candidate_generated=True,
            signal_id="sig-3",
            confluence_score=9.1,
            risk_block_reason="rr_below_min:1.500",
        ),
        _record(
            event_id="evt-4",
            candidate_generated=True,
            signal_id="sig-4",
            confluence_score=10.2,
            trade_opened=True,
            trade_closed=True,
            pnl_abs=120.0,
            pnl_r=1.2,
            outcome_bucket="win_1R_to_2R",
        ),
    ]

    stage_counts = module._build_stage_counts(records)

    assert stage_counts["detected"]["count"] == 4
    assert stage_counts["candidate_generated"]["count"] == 3
    assert stage_counts["pre_candidate_filtered"]["by_reason"] == {"uptrend_pullback_weak": 1}
    assert stage_counts["governance_veto"]["by_reason"] == {"duplicate_level": 1}
    assert stage_counts["risk_block"]["by_reason"] == {"rr_below_min:1.500": 1}
    assert stage_counts["trade_opened"]["count"] == 1
    assert stage_counts["trade_closed"]["count"] == 1
    assert stage_counts["pnl_outcome_buckets"] == {"win_1R_to_2R": 1}


def test_build_feature_segments_buckets_candidate_quality() -> None:
    records = [
        _record(
            event_id="evt-1",
            candidate_generated=True,
            confluence_score=8.4,
            tfi_60s=0.15,
            sweep_depth_pct=0.0035,
            ema_gap_pct=0.012,
            governance_veto_reason="duplicate_level",
        ),
        _record(
            event_id="evt-2",
            candidate_generated=True,
            confluence_score=9.6,
            tfi_60s=0.24,
            sweep_depth_pct=0.0055,
            ema_gap_pct=0.025,
            trade_opened=True,
            trade_closed=True,
            pnl_abs=110.0,
            pnl_r=1.1,
            outcome_bucket="win_1R_to_2R",
        ),
        _record(
            event_id="evt-3",
            candidate_generated=True,
            confluence_score=9.7,
            tfi_60s=0.24,
            sweep_depth_pct=0.0055,
            ema_gap_pct=0.025,
            trade_opened=True,
            trade_closed=True,
            pnl_abs=-70.0,
            pnl_r=-0.7,
            outcome_bucket="loss_lt_1R",
        ),
    ]

    feature_segments = module._build_feature_segments(records)
    confluence_rows = {row["bucket"]: row for row in feature_segments["confluence_score"]}
    tfi_rows = {row["bucket"]: row for row in feature_segments["tfi_60s"]}

    assert confluence_rows["8.00-9.00"]["candidate_count"] == 1
    assert confluence_rows["8.00-9.00"]["governance_veto_count"] == 1
    assert confluence_rows["9.00-10.00"]["trade_count"] == 2
    assert confluence_rows["9.00-10.00"]["win_rate"] == 0.5
    assert tfi_rows["0.20-0.30"]["avg_pnl_r"] == 0.2


def test_build_cohort_comparison_prefers_positive_trades_when_available() -> None:
    records = [
        _record(
            event_id="evt-win",
            candidate_generated=True,
            confluence_score=10.0,
            tfi_60s=0.32,
            trade_opened=True,
            trade_closed=True,
            pnl_abs=100.0,
            pnl_r=1.0,
            outcome_bucket="win_1R_to_2R",
        ),
        _record(
            event_id="evt-loss",
            candidate_generated=True,
            confluence_score=8.5,
            tfi_60s=0.14,
            trade_opened=True,
            trade_closed=True,
            pnl_abs=-50.0,
            pnl_r=-0.5,
            outcome_bucket="loss_lt_1R",
            exit_reason="SL",
        ),
        _record(
            event_id="evt-gov",
            candidate_generated=True,
            confluence_score=8.8,
            tfi_60s=0.18,
            governance_veto_reason="duplicate_level",
        ),
        _record(
            event_id="evt-risk",
            candidate_generated=True,
            confluence_score=9.0,
            tfi_60s=0.19,
            risk_block_reason="rr_below_min:1.500",
        ),
    ]

    comparison = module._build_cohort_comparison(records)

    assert comparison["viable_definition"] == "closed trade with pnl_r > 0"
    assert comparison["viable_count"] == 1
    assert comparison["junk_count"] == 3
    assert comparison["junk_reason_mix"]["governance:duplicate_level"] == 1
    assert comparison["junk_reason_mix"]["risk:rr_below_min:1.500"] == 1
    assert comparison["junk_reason_mix"]["trade:SL"] == 1
    assert comparison["feature_stats"]["confluence_score"]["delta_mean"] == 1.2333


def test_run_uptrend_pullback_evaluation_writes_report(tmp_path, monkeypatch) -> None:
    source_db = tmp_path / "source.db"
    source_db.touch()
    snapshot_db = tmp_path / "snapshot.db"
    sqlite3.connect(snapshot_db).close()

    monkeypatch.setattr(module, "create_trial_snapshot", lambda **kwargs: snapshot_db)
    monkeypatch.setattr(module, "verify_required_tables", lambda conn: None)
    monkeypatch.setattr(module, "init_db", lambda conn, schema_path: None)

    def _open_snapshot_connection(path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(module, "open_snapshot_connection", _open_snapshot_connection)

    settings = load_settings(project_root=tmp_path, profile="research")
    monkeypatch.setattr(module, "load_settings", lambda project_root=None, profile="research": settings)

    captured: dict[str, object] = {}

    class FakeRunner:
        def __init__(self, conn, settings):  # type: ignore[no-untyped-def]
            _ = conn
            _ = settings
            self.pullback_events = [
                _record(
                    event_id="evt-1",
                    candidate_generated=True,
                    signal_id="sig-1",
                    confluence_score=9.4,
                    trade_opened=True,
                    trade_closed=True,
                    pnl_abs=90.0,
                    pnl_r=0.9,
                    outcome_bucket="win_lt_1R",
                )
            ]

        def run(self, config):  # type: ignore[no-untyped-def]
            captured["initial_equity"] = config.initial_equity
            return SimpleNamespace(
                trades=[
                    TradeLog(
                        trade_id="trade-1",
                        signal_id="sig-1",
                        opened_at=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
                        closed_at=datetime(2026, 3, 1, 1, 0, tzinfo=timezone.utc),
                        direction="LONG",
                        regime="uptrend",
                        confluence_score=9.4,
                        entry_price=100.0,
                        exit_price=101.0,
                        size=1.0,
                        fees=0.0,
                        slippage_bps=0.0,
                        pnl_abs=90.0,
                        pnl_r=0.9,
                        mae=0.0,
                        mfe=0.0,
                        exit_reason="TP",
                        features_at_entry_json={},
                    )
                ],
                performance=SimpleNamespace(
                    pnl_abs=90.0,
                    pnl_r_sum=0.9,
                    expectancy_r=0.9,
                    profit_factor=1.8,
                )
            )

    monkeypatch.setattr(module, "UptrendPullbackEvaluationRunner", FakeRunner)

    output_path = tmp_path / "report.json"
    report = module.run_uptrend_pullback_evaluation(
        source_db_path=source_db,
        start_ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end_ts=datetime(2026, 4, 1, tzinfo=timezone.utc),
        output_path=output_path,
        initial_equity=12_345.0,
    )

    assert captured["initial_equity"] == 12_345.0
    assert output_path.exists()
    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded["meta"]["allow_uptrend_pullback"] is True
    assert loaded["meta"]["sample_size"]["detected"] == 1
    assert loaded["funnel"]["trade_closed"]["count"] == 1
    assert report["meta"]["performance"]["expectancy_r"] == 0.9
