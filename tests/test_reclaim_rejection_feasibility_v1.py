from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

import research_lab.diagnostics.reclaim_rejection_feasibility_v1 as rr
from research_lab.diagnostics.reclaim_rejection_feasibility_v1 import (
    Candle,
    DiagnosticConfig,
    FlowBar,
    RejectionEvent,
    aligned_monthly_correlation,
    attach_metrics,
    confluence_passes,
    detect_rejection_candidates,
    event_id,
    find_entry_candidate,
    find_level_provenance,
    fixed_exit_return,
    load_flow_15m,
    resolve_default_db,
    run_diagnostic,
)


def _candles_for_rejection() -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows: list[Candle] = []
    for idx in range(12):
        rows.append(
            Candle(
                index=idx,
                open_time=start + timedelta(minutes=15 * idx),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=10.0,
            )
        )
    rows[4] = Candle(4, rows[4].open_time, 100.0, 100.2, 90.0, 99.0, 10.0)
    rows[5] = Candle(5, rows[5].open_time, 100.0, 101.0, 99.5, 100.5, 10.0)
    rows[6] = Candle(6, rows[6].open_time, 99.2, 100.4, 99.0, 100.1, 10.0)
    rows[7] = Candle(7, rows[7].open_time, 100.1, 103.0, 100.0, 102.0, 10.0)
    return rows


def _atr(candles: list[Candle], value: float = 2.0) -> list[float | None]:
    return [value for _ in candles]


def test_rejection_detection_requires_wick_to_body_threshold() -> None:
    candles = _candles_for_rejection()
    config = DiagnosticConfig(swing_left_bars=1, swing_right_bars=1, wick_to_body_min=20.0)

    assert detect_rejection_candidates(candles, _atr(candles), config) == []


def test_rejection_detection_requires_swing_extreme_confirmation() -> None:
    candles = _candles_for_rejection()
    config = DiagnosticConfig(swing_left_bars=1, swing_right_bars=2)

    assert detect_rejection_candidates(candles, _atr(candles), config) == []


def test_state_known_bar_is_detection_plus_one() -> None:
    candles = _candles_for_rejection()
    config = DiagnosticConfig(swing_left_bars=1, swing_right_bars=1)

    candidates = detect_rejection_candidates(candles, _atr(candles), config)

    assert len(candidates) == 1
    assert candidates[0].state_known_bar == candidates[0].detection_bar + 1


def test_entry_candidate_bar_requires_reclaim_AND_confluence() -> None:
    candles = _candles_for_rejection()
    candidate = detect_rejection_candidates(candles, _atr(candles), DiagnosticConfig(swing_left_bars=1, swing_right_bars=1))[0]
    flow = {
        candles[6].open_time: FlowBar(candles[6].open_time, 1.0, 5.0, -0.5, -10.0, 15),
        candles[7].open_time: FlowBar(candles[7].open_time, 5.0, 1.0, 0.5, 10.0, 15),
    }

    entry = find_entry_candidate(candidate, candles, flow)

    assert entry is not None
    assert entry[0] == 7
    assert confluence_passes("LONG", flow[candles[7].open_time])


def test_returns_measured_from_return_start_bar_not_detection_bar() -> None:
    candles = _candles_for_rejection()
    event = RejectionEvent(
        event_id="e1",
        cohort_source="test",
        direction="LONG",
        detection_bar=4,
        state_known_bar=5,
        entry_candidate_bar=6,
        return_start_bar=7,
        label_available_bar=11,
        detection_time_utc=candles[4].open_time.isoformat(),
        state_known_time_utc=candles[5].open_time.isoformat(),
        entry_candidate_time_utc=candles[6].open_time.isoformat(),
        return_start_time_utc=candles[7].open_time.isoformat(),
        zone_bottom=90.0,
        zone_top=99.0,
        atr_at_detection=2.0,
        atr_at_entry_candidate=2.0,
    )

    attach_metrics([event], candles, _atr(candles), DiagnosticConfig(fixed_exit_max_hold_bars=2))

    primary = event.metrics["primary_fixed_exit"]
    detection = event.metrics["detection_bar_fixed_exit_audit_only"]
    assert primary["gross_return"] != detection["gross_return"]
    assert event.return_start_bar == 7


def test_level_provenance_lookup_uses_only_available_levels() -> None:
    candles = _candles_for_rejection()
    event = RejectionEvent(
        event_id="e1",
        cohort_source="test",
        direction="LONG",
        detection_bar=4,
        state_known_bar=5,
        entry_candidate_bar=6,
        return_start_bar=7,
        label_available_bar=11,
        detection_time_utc=candles[4].open_time.isoformat(),
        state_known_time_utc=candles[5].open_time.isoformat(),
        entry_candidate_time_utc=candles[6].open_time.isoformat(),
        return_start_time_utc=candles[7].open_time.isoformat(),
        zone_bottom=90.0,
        zone_top=99.0,
        atr_at_detection=2.0,
        atr_at_entry_candidate=2.0,
    )
    levels = pd.DataFrame(
        [
            {
                "level_id": "future",
                "category": "equal_cluster",
                "side": "LOW",
                "top": 98.0,
                "bottom": 97.0,
                "available_at": pd.Timestamp(candles[8].open_time),
            },
            {
                "level_id": "known",
                "category": "equal_cluster",
                "side": "LOW",
                "top": 98.0,
                "bottom": 97.0,
                "available_at": pd.Timestamp(candles[5].open_time),
            },
        ]
    )

    provenance = find_level_provenance(event, levels)

    assert provenance is not None
    assert provenance["level_id"] == "known"


def test_mfe_before_entry_uses_high_low_in_window_after_detection_before_entry() -> None:
    candles = _candles_for_rejection()
    event = RejectionEvent(
        event_id="e1",
        cohort_source="test",
        direction="LONG",
        detection_bar=4,
        state_known_bar=5,
        entry_candidate_bar=6,
        return_start_bar=7,
        label_available_bar=11,
        detection_time_utc=candles[4].open_time.isoformat(),
        state_known_time_utc=candles[5].open_time.isoformat(),
        entry_candidate_time_utc=candles[6].open_time.isoformat(),
        return_start_time_utc=candles[7].open_time.isoformat(),
        zone_bottom=90.0,
        zone_top=99.0,
        atr_at_detection=2.0,
        atr_at_entry_candidate=2.0,
    )

    attach_metrics([event], candles, _atr(candles), DiagnosticConfig())

    expected = (101.0 - candles[4].close) / candles[4].close
    assert event.metrics["mfe_before_entry"] == expected


def test_control_cohort_random_wicks_does_not_match_primary_cohort() -> None:
    primary = event_id("reclaim_rejection", "LONG", "2025-01-01T01:00:00+00:00")
    control = event_id("control_random_wicks", "LONG", "2025-01-01T01:00:00+00:00")

    assert primary != control


def test_correlation_calculation_uses_aligned_monthly_buckets() -> None:
    result = aligned_monthly_correlation({"2025-01": 1.0, "2025-03": 2.0}, {"2025-02": 3.0, "2025-03": 4.0})

    assert result["months"] == ["2025-01", "2025-02", "2025-03"]
    assert result["primary_series"]["2025-02"] == 0.0
    assert result["baseline_series"]["2025-01"] == 0.0


def test_deterministic_output_two_runs_produce_identical_json_sha256(tmp_path: Path) -> None:
    db_path = tmp_path / "mini.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE candles (symbol TEXT, timeframe TEXT, open_time TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL)"
    )
    conn.execute(
        "CREATE TABLE aggtrade_buckets (symbol TEXT, timeframe TEXT, bucket_time TEXT, taker_buy_volume REAL, taker_sell_volume REAL, tfi REAL, cvd REAL)"
    )
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for idx in range(40):
        ts = start + timedelta(minutes=15 * idx)
        conn.execute(
            "INSERT INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("BTCUSDT", "15m", ts.isoformat(), 100.0, 101.0, 99.0, 100.0, 10.0),
        )
        for minute in range(15):
            mts = ts + timedelta(minutes=minute)
            conn.execute(
                "INSERT INTO aggtrade_buckets VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("BTCUSDT", "60s", mts.isoformat(), 5.0, 4.0, 0.1, float(idx * 15 + minute)),
            )
    conn.commit()
    conn.close()

    config = DiagnosticConfig(study_start="2025-01-01", study_end="2025-01-01T09:45:00+00:00", swing_left_bars=1, swing_right_bars=1)
    first_json = tmp_path / "first.json"
    second_json = tmp_path / "second.json"
    run_diagnostic(
        db_path=db_path,
        output_json=first_json,
        output_sha=tmp_path / "first.sha256",
        report_path=tmp_path / "first.md",
        config=config,
    )
    run_diagnostic(
        db_path=db_path,
        output_json=second_json,
        output_sha=tmp_path / "second.sha256",
        report_path=tmp_path / "second.md",
        config=config,
    )

    assert hashlib.sha256(first_json.read_bytes()).hexdigest() == hashlib.sha256(second_json.read_bytes()).hexdigest()
    assert json.loads(first_json.read_text(encoding="utf-8")) == json.loads(second_json.read_text(encoding="utf-8"))


def test_default_db_resolution_hard_fails_when_canonical_db_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rr, "CANONICAL_DB_PATH", tmp_path / "missing_canonical.db")
    monkeypatch.setattr(rr, "FALLBACK_RESEARCH_SNAPSHOT", tmp_path / "fallback.db")

    with pytest.raises(SystemExit, match="CANONICAL_DB_MISSING"):
        resolve_default_db()


def test_default_db_resolution_uses_fallback_only_when_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fallback = tmp_path / "fallback.db"
    fallback.write_bytes(b"placeholder")
    monkeypatch.setattr(rr, "CANONICAL_DB_PATH", tmp_path / "missing_canonical.db")
    monkeypatch.setattr(rr, "FALLBACK_RESEARCH_SNAPSHOT", fallback)

    resolved, metadata = resolve_default_db(allow_fallback=True)

    assert resolved == fallback
    assert metadata["fallback_used"] is True
    assert metadata["fallback_allowed"] is True


def test_fixed_exit_uses_supplied_entry_price() -> None:
    candles = _candles_for_rejection()

    result = fixed_exit_return(
        candles,
        entry_bar=7,
        entry_price=candles[7].open,
        atr_value=2.0,
        direction="LONG",
        config=DiagnosticConfig(fixed_exit_max_hold_bars=1),
    )

    assert result["gross_return"] is not None
