from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_lab.diagnostics.oanda_ny_reversal_after_london_extension_feasibility_v1 import (
    CONTROL_COHORTS,
    PRIMARY_COHORT,
    Candle,
    DiagnosticConfig,
    build_cohorts,
    build_event,
    build_london_extensions,
    build_signals,
    cohort_metrics,
    compute_atr,
    evaluate_gates,
    fold_metrics,
    run_diagnostic,
    write_json,
    write_report,
)


def _ts(index: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * index)


def _candle(
    index: int,
    open_: float = 1.1000,
    high: float = 1.1010,
    low: float = 1.0990,
    close: float = 1.1000,
    volume: float = 100.0,
) -> Candle:
    return Candle(index=index, time=_ts(index), open=open_, high=high, low=low, close=close, volume=volume)


def _flat_day(start_index: int) -> list[Candle]:
    return [_candle(start_index + offset) for offset in range(96)]


def _extension_day(start_index: int, up: bool = True) -> list[Candle]:
    candles: list[Candle] = []
    for offset in range(96):
        idx = start_index + offset
        ts = _ts(idx)
        if 7 <= ts.hour < 12:
            if up:
                close = 1.1000 + 0.0002 * (offset - 28 + 1)
                candles.append(_candle(idx, open_=close - 0.0001, high=close + 0.0004, low=close - 0.0005, close=close))
            else:
                close = 1.1000 - 0.0002 * (offset - 28 + 1)
                candles.append(_candle(idx, open_=close + 0.0001, high=close + 0.0005, low=close - 0.0004, close=close))
        elif ts.hour == 13 and ts.minute == 0:
            if up:
                candles.append(_candle(idx, open_=1.1045, high=1.1050, low=1.1030, close=1.1035))
            else:
                candles.append(_candle(idx, open_=1.0955, high=1.0970, low=1.0950, close=1.0965))
        elif ts.hour == 13 and ts.minute == 15:
            if up:
                candles.append(_candle(idx, open_=1.1035, high=1.1040, low=1.1010, close=1.1015))
            else:
                candles.append(_candle(idx, open_=1.0965, high=1.0990, low=1.0960, close=1.0985))
        else:
            candles.append(_candle(idx))
    return candles


def _candles(days: int = 8) -> list[Candle]:
    raw: list[Candle] = []
    for day in range(days):
        start = day * 96
        if day == 2:
            raw.extend(_extension_day(start, up=True))
        else:
            raw.extend(_flat_day(start))
    return [
        Candle(index=index, time=candle.time, open=candle.open, high=candle.high, low=candle.low, close=candle.close, volume=candle.volume)
        for index, candle in enumerate(raw)
    ]


def _config() -> DiagnosticConfig:
    return DiagnosticConfig(
        atr_period=3,
        extension_atr_threshold=1.0,
        primary_horizon_bars=5,
        secondary_horizon_bars=8,
        tertiary_horizon_bars=10,
        random_offset_bars=13,
        weekday_shuffle_offset_bars=96,
    )


def test_atr_is_simple_true_range_average() -> None:
    candles = [
        _candle(0, open_=10, high=11, low=9, close=10),
        _candle(1, open_=10, high=13, low=9, close=12),
        _candle(2, open_=12, high=14, low=11, close=13),
        _candle(3, open_=13, high=15, low=12, close=14),
    ]

    assert compute_atr(candles, 3, 3) == 10.0 / 3.0


def test_london_extension_uses_completed_london_session_only() -> None:
    config = _config()
    candles = _candles(4)
    extensions, _, _ = build_london_extensions(candles, config)

    assert "2024-01-03" in extensions
    extension = extensions["2024-01-03"]
    assert extension.london_start_bar < extension.london_end_bar
    assert extension.london_known_bar == extension.london_end_bar + 1
    assert extension.direction == "UP"
    assert extension.extended is True


def test_signal_and_event_enforce_entry_at_i_plus_1() -> None:
    config = _config()
    candles = _candles(4)
    extensions, valid_days, _ = build_london_extensions(candles, config)
    signals = build_signals(candles, config, extensions, valid_days, PRIMARY_COHORT, config.ny_start, config.ny_end)

    assert len(signals) == 1
    signal = signals[0]
    event = build_event(PRIMARY_COHORT, candles, signal, config)

    assert event is not None
    assert event.direction == "SHORT"
    assert event.state_known_bar == event.detection_bar
    assert event.confirmation_bar == event.detection_bar
    assert event.entry_candidate_bar == event.detection_bar + 1
    assert event.return_start_bar == event.entry_candidate_bar
    assert event.label_available_bar == event.entry_candidate_bar + config.primary_horizon_bars


def test_mfe_accessibility_is_split_before_and_after_entry() -> None:
    config = _config()
    candles = _candles(4)
    extensions, valid_days, _ = build_london_extensions(candles, config)
    signal = build_signals(candles, config, extensions, valid_days, PRIMARY_COHORT, config.ny_start, config.ny_end)[0]
    event = build_event(PRIMARY_COHORT, candles, signal, config)

    assert event is not None
    assert event.mfe_before_entry >= 0
    assert event.mfe_after_entry >= 0
    assert event.total_mfe == event.mfe_before_entry + event.mfe_after_entry
    assert 0 <= event.mfe_consumed_pct <= 1


def test_build_cohorts_includes_all_eight_controls() -> None:
    config = _config()
    cohorts, _ = build_cohorts(_candles(8), config)

    assert PRIMARY_COHORT in cohorts
    for control in CONTROL_COHORTS:
        assert control in cohorts


def test_gate_logic_stops_small_sample() -> None:
    config = _config()
    candles = _candles(4)
    extensions, valid_days, _ = build_london_extensions(candles, config)
    signal = build_signals(candles, config, extensions, valid_days, PRIMARY_COHORT, config.ny_start, config.ny_end)[0]
    event = build_event(PRIMARY_COHORT, candles, signal, config)
    assert event is not None

    cohort_results = {PRIMARY_COHORT: cohort_metrics([event])}
    for control in CONTROL_COHORTS:
        cohort_results[control] = cohort_metrics([])
    gates = evaluate_gates(cohort_results, fold_metrics([event]))

    assert gates["recommendation"] == "STOP"
    assert any(reason.startswith("sample_size_lt_100") for reason in gates["stop_reasons"])


def test_report_generation_writes_json_sha(tmp_path: Path) -> None:
    data_path = tmp_path / "candles.json"
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"
    data_path.write_text(
        "["
        + ",".join(
            f'{{"time":"{candle.time.isoformat()}","open":{candle.open},"high":{candle.high},"low":{candle.low},"close":{candle.close},"volume":{candle.volume}}}'
            for candle in _candles(5)
        )
        + "]",
        encoding="utf-8",
    )

    payload = run_diagnostic(_config(), data_path)
    write_json(json_path, payload)
    write_report(md_path, payload, json_path)

    text = md_path.read_text(encoding="utf-8")
    assert "## 17. Recommendation" in text
    assert "JSON SHA256" in text
    assert json_path.exists()
