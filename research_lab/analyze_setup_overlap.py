from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def calculate_overlap(
    absorption_signals: list[dict[str, Any]],
    sweep_signals: list[dict[str, Any]],
    *,
    tolerance_minutes: int = 15,
) -> dict[str, Any]:
    tolerance = timedelta(minutes=tolerance_minutes)
    absorption_times = [_parse_ts(signal["timestamp"]) for signal in absorption_signals if signal.get("timestamp")]
    sweep_times = [_parse_ts(signal["timestamp"]) for signal in sweep_signals if signal.get("timestamp")]
    matched_absorption: set[int] = set()
    matched_sweep: set[int] = set()

    for absorption_index, absorption_time in enumerate(absorption_times):
        for sweep_index, sweep_time in enumerate(sweep_times):
            if sweep_index in matched_sweep:
                continue
            if abs(absorption_time - sweep_time) <= tolerance:
                matched_absorption.add(absorption_index)
                matched_sweep.add(sweep_index)
                break

    either_count = len(absorption_times) + len(sweep_times) - len(matched_absorption)
    overlap_rate = (len(matched_absorption) / either_count) if either_count else 0.0
    return {
        "absorption_signal_count": len(absorption_times),
        "sweep_signal_count": len(sweep_times),
        "overlap_count": len(matched_absorption),
        "overlap_rate": round(overlap_rate, 6),
        "target": "<=0.20 preferred, <=0.30 acceptable, >0.50 reject",
        "verdict": _overlap_verdict(overlap_rate),
    }


def load_report_signals(path: Path, *, key: str = "signals") -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    signals = payload.get(key, [])
    if not isinstance(signals, list):
        raise ValueError(f"{path} field {key!r} must be a list.")
    return [signal for signal in signals if isinstance(signal, dict)]


def _overlap_verdict(rate: float) -> str:
    if rate <= 0.20:
        return "PASS_STRONG"
    if rate <= 0.30:
        return "PASS_ACCEPTABLE_WITH_COMMENT"
    if rate <= 0.50:
        return "ITERATE_HIGH_OVERLAP"
    return "REJECT_TOO_SIMILAR"


def _parse_ts(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure signal overlap between absorption and sweep-reclaim reports.")
    parser.add_argument("--absorption-report", type=Path, required=True)
    parser.add_argument("--sweep-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("research_lab/reports/absorption_vs_sweep_overlap.json"))
    parser.add_argument("--tolerance-minutes", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = calculate_overlap(
        load_report_signals(args.absorption_report),
        load_report_signals(args.sweep_report),
        tolerance_minutes=args.tolerance_minutes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
