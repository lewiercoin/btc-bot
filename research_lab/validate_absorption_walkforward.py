from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_lab.backtest_absorption_continuation import run_absorption_backtest


DEFAULT_WINDOWS = [
    {
        "window_id": "wf-2024-2025",
        "train_start": "2022-01-01",
        "train_end": "2024-01-01",
        "validation_start": "2024-01-01",
        "validation_end": "2025-01-01",
    },
    {
        "window_id": "wf-2025-2026",
        "train_start": "2022-01-01",
        "train_end": "2025-01-01",
        "validation_start": "2025-01-01",
        "validation_end": "2026-03-29",
    },
]


def run_absorption_walkforward(
    *,
    source_db_path: Path,
    output_path: Path,
    initial_equity: float = 10_000.0,
    windows: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    resolved_windows = list(windows or DEFAULT_WINDOWS)
    reports: list[dict[str, Any]] = []
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    for window in resolved_windows:
        validation_report_path = output_dir / f"absorption_{window['window_id']}_validation.json"
        report = run_absorption_backtest(
            source_db_path=source_db_path,
            start_date=window["validation_start"],
            end_date=window["validation_end"],
            output_path=validation_report_path,
            initial_equity=initial_equity,
        )
        reports.append(
            {
                "window_id": window["window_id"],
                "train_range": {"start": window["train_start"], "end": window["train_end"]},
                "validation_range": {"start": window["validation_start"], "end": window["validation_end"]},
                "validation_report_path": str(validation_report_path),
                "validation_performance": report["performance"],
                "validation_per_regime": report["per_regime"],
                "passed": _window_passed(report),
            }
        )
    summary = {
        "milestone": "ABSORPTION-CONTINUATION-RESEARCH-V1",
        "mode": "post_hoc_walkforward_validation",
        "windows_total": len(reports),
        "windows_passed": sum(1 for report in reports if report["passed"]),
        "windows": reports,
        "pass_rule": "all validation windows must pass uptrend ER/trade minimum and no obvious range bleed",
    }
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _window_passed(report: dict[str, Any]) -> bool:
    uptrend = report.get("per_regime", {}).get("uptrend", {})
    range_regime = report.get("per_regime", {}).get("range", {})
    uptrend_er = _float(uptrend.get("expectancy_r"))
    uptrend_trades = int(uptrend.get("trades_count", 0) or 0)
    range_er = _float(range_regime.get("expectancy_r"))
    if uptrend_er is None or uptrend_er <= 1.5:
        return False
    if uptrend_trades < 20:
        return False
    if range_er is not None and range_er < -1.0:
        return False
    return True


def _float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.lower() in {"inf", "nan"}:
        return None
    return float(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run absorption_continuation walk-forward validation.")
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("research_lab/reports/absorption_walkforward_report.json"))
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    run_absorption_walkforward(
        source_db_path=args.source_db,
        output_path=args.output,
        initial_equity=args.initial_equity,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
