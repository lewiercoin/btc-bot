from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def calculate_trend_day_capture(
    signals: list[dict[str, Any]],
    trend_days: list[str],
) -> dict[str, Any]:
    signal_dates = {_parse_ts(signal["timestamp"]).date().isoformat() for signal in signals if signal.get("timestamp")}
    clean_trend_days = sorted(set(trend_days))
    captured = [day for day in clean_trend_days if day in signal_dates]
    missed = [day for day in clean_trend_days if day not in signal_dates]
    capture_rate = (len(captured) / len(clean_trend_days)) if clean_trend_days else 0.0
    return {
        "trend_days_total": len(clean_trend_days),
        "trend_days_captured": len(captured),
        "capture_rate": round(capture_rate, 6),
        "captured_days": captured,
        "missed_days": missed,
        "target": ">=0.50 pass, <0.30 reject",
        "verdict": _capture_verdict(capture_rate),
    }


def load_report_signals(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    signals = payload.get("signals", [])
    if not isinstance(signals, list):
        raise ValueError(f"{path} field 'signals' must be a list.")
    return [signal for signal in signals if isinstance(signal, dict)]


def _capture_verdict(rate: float) -> str:
    if rate >= 0.50:
        return "PASS"
    if rate < 0.30:
        return "REJECT_MISSES_TARGET_STRUCTURE"
    return "ITERATE_LOW_CAPTURE"


def _parse_ts(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure absorption_continuation trend day capture.")
    parser.add_argument("--absorption-report", type=Path, required=True)
    parser.add_argument("--trend-days-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("research_lab/reports/absorption_trend_day_capture.json"))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    trend_days_payload = json.loads(args.trend_days_json.read_text(encoding="utf-8"))
    trend_days = trend_days_payload.get("trend_days", trend_days_payload)
    if not isinstance(trend_days, list):
        raise ValueError("trend days input must be a list or an object with trend_days list.")
    result = calculate_trend_day_capture(load_report_signals(args.absorption_report), [str(day) for day in trend_days])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
