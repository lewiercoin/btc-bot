from __future__ import annotations

import os
import sys

if __package__ in {None, ""}:
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    if _script_dir in sys.path:
        sys.path.remove(_script_dir)
    _project_root = os.path.dirname(_script_dir)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig
from backtest.replay_loader import ReplayLoader, ReplayLoaderConfig
from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.regime_engine import RegimeEngine
from settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = Path("research_lab/reports/regime_distribution_2022_2026.json")
DEFAULT_MARKDOWN_PATH = Path("research_lab/reports/regime_distribution_2022_2026.md")


def analyze_regime_distribution(
    *,
    source_db_path: Path,
    start_date: str,
    end_date: str,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    markdown_path: Path = DEFAULT_MARKDOWN_PATH,
) -> dict[str, Any]:
    conn = sqlite3.connect(source_db_path)
    conn.row_factory = sqlite3.Row
    counts: Counter[str] = Counter()
    atr_by_regime: dict[str, list[float]] = {}
    try:
        settings = load_settings(project_root=PROJECT_ROOT, profile="research")
        strategy = settings.strategy
        feature_engine = FeatureEngine(
            FeatureEngineConfig(
                atr_period=strategy.atr_period,
                ema_fast=strategy.ema_fast,
                ema_slow=strategy.ema_slow,
                equal_level_lookback=strategy.equal_level_lookback,
                equal_level_tol_atr=strategy.equal_level_tol_atr,
                sweep_buf_atr=strategy.sweep_buf_atr,
                sweep_proximity_atr=strategy.sweep_proximity_atr,
                reclaim_buf_atr=strategy.reclaim_buf_atr,
                wick_min_atr=strategy.wick_min_atr,
                level_min_age_bars=strategy.level_min_age_bars,
                min_hits=strategy.min_hits,
                funding_window_days=strategy.funding_window_days,
                oi_z_window_days=strategy.oi_z_window_days,
            )
        )
        regime_engine = RegimeEngine()
        replay_loader = ReplayLoader(
            conn,
            ReplayLoaderConfig(
                candles_15m_lookback=300,
                candles_1h_lookback=300,
                candles_4h_lookback=300,
                funding_lookback=200,
            ),
        )
        backtest_config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            symbol=strategy.symbol,
        )
        for snapshot in replay_loader.iter_snapshots(
            start_date=backtest_config.start_date,
            end_date=backtest_config.end_date,
            symbol=backtest_config.symbol,
        ):
            features = feature_engine.compute(
                snapshot=snapshot,
                schema_version=settings.schema_version,
                config_hash=settings.config_hash,
            )
            regime = regime_engine.classify(features)
            regime_value = regime.value
            counts[regime_value] += 1
            atr_by_regime.setdefault(regime_value, []).append(float(features.atr_4h_norm))
    finally:
        conn.close()

    report = build_regime_distribution_report(
        counts=counts,
        atr_by_regime=atr_by_regime,
        source_db_path=source_db_path,
        start_date=start_date,
        end_date=end_date,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown_report(report, markdown_path)
    return report


def build_regime_distribution_report(
    *,
    counts: Counter[str],
    atr_by_regime: dict[str, list[float]],
    source_db_path: Path,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    total = sum(counts.values())
    regimes = ["normal", "uptrend", "downtrend", "compression", "crowded_leverage", "post_liquidation"]
    regime_counts = {regime: int(counts.get(regime, 0)) for regime in regimes}
    percentages = {
        regime: _round((count / total) if total else 0.0)
        for regime, count in regime_counts.items()
    }
    return {
        "source_db_path": str(source_db_path),
        "date_range": {"start": start_date, "end": end_date},
        "total_cycles": total,
        "regime_counts": regime_counts,
        "regime_percentages": percentages,
        "atr_4h_norm_by_regime": {
            regime: _summary(values)
            for regime, values in sorted(atr_by_regime.items())
        },
        "interpretation": _interpret(percentages.get("compression", 0.0)),
    }


def write_markdown_report(report: dict[str, Any], output_path: Path) -> None:
    counts = report["regime_counts"]
    pct = report["regime_percentages"]
    lines = [
        "# Regime Distribution Analysis",
        "",
        f"Source DB: `{report['source_db_path']}`",
        f"Date range: `{report['date_range']['start']}` to `{report['date_range']['end']}`",
        f"Total cycles: `{report['total_cycles']}`",
        "",
        "## Regime Counts",
        "",
        "| Regime | Count | Percentage |",
        "|---|---:|---:|",
    ]
    for regime, count in counts.items():
        lines.append(f"| {regime} | `{count}` | `{pct[regime]}` |")
    lines.extend(
        [
            "",
            "## ATR 4H Norm By Regime",
            "",
            "| Regime | Count | Mean | P50 | P95 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for regime, summary in sorted(report["atr_4h_norm_by_regime"].items()):
        lines.append(
            f"| {regime} | `{summary['count']}` | `{summary['mean']}` | "
            f"`{summary['p50']}` | `{summary['p95']}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            report["interpretation"],
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _interpret(compression_pct: float) -> str:
    if compression_pct < 0.01:
        return (
            "COMPRESSION labels are rare (<1%). Treating RegimeEngine as the primary trigger "
            "is likely a measurement bottleneck; use regime as a research-only veto and rely on "
            "internal ATR/range compression detection."
        )
    if compression_pct > 0.05:
        return (
            "COMPRESSION labels are present (>5%). If setup activation remains sparse, inspect "
            "setup rejection reasons inside COMPRESSION-labeled cycles before changing regime logic."
        )
    return (
        "COMPRESSION labels are present but uncommon (1-5%). Regime may remain useful as context, "
        "but setup-level compression detection should be compared against RegimeEngine labels."
    )


def _summary(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "mean": _round(sum(ordered) / len(ordered)) if ordered else None,
        "p50": _percentile(ordered, 50),
        "p95": _percentile(ordered, 95),
    }


def _percentile(ordered: list[float], percentile: float) -> float | None:
    if not ordered:
        return None
    if len(ordered) == 1:
        return _round(ordered[0])
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return _round(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 8)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze empirical regime distribution.")
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-03-29")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    analyze_regime_distribution(
        source_db_path=args.source_db,
        start_date=args.start_date,
        end_date=args.end_date,
        output_path=args.output,
        markdown_path=args.markdown_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
