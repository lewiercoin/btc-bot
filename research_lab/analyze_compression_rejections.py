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
from research_lab.setups import CompressionBreakoutLong
from settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = Path("research_lab/reports/compression_rejection_analysis_2022_2026.json")
DEFAULT_MARKDOWN_PATH = Path("research_lab/reports/compression_rejection_analysis_2022_2026.md")


def analyze_compression_rejections(
    *,
    source_db_path: Path,
    start_date: str,
    end_date: str,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    markdown_path: Path = DEFAULT_MARKDOWN_PATH,
) -> dict[str, Any]:
    conn = sqlite3.connect(source_db_path)
    conn.row_factory = sqlite3.Row
    regime_counts: Counter[str] = Counter()
    candidate_counts: Counter[str] = Counter()
    rejection_counts: dict[str, Counter[str]] = {}
    compression_metric_rows: list[dict[str, Any]] = []
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
        setup = CompressionBreakoutLong()
        atr_history: list[float] = []
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
            if float(features.atr_4h_norm) > 0:
                atr_history.append(float(features.atr_4h_norm))
            if len(atr_history) > 500:
                atr_history = atr_history[-500:]
            snapshot.source_meta["research_atr_4h_norm_history"] = list(atr_history)

            regime = regime_engine.classify(features).value
            regime_counts[regime] += 1
            evaluation = setup.evaluate_structure(
                features=features,
                snapshot=snapshot,
                regime=regime,
                config=settings.strategy,
            )
            if evaluation.accepted:
                candidate_counts[regime] += 1
            else:
                rejection_counts.setdefault(regime, Counter()).update(evaluation.reasons)
            if regime == "compression":
                compression_metric_rows.append(
                    {
                        "atr_percentile": evaluation.metrics.get("atr_percentile"),
                        "range_width_atr": evaluation.metrics.get("range_width_atr"),
                        "compression_duration_bars": evaluation.metrics.get("compression_duration_bars"),
                        "breakout_size_atr": evaluation.metrics.get("breakout_size_atr"),
                        "accepted": evaluation.accepted,
                    }
                )
    finally:
        conn.close()

    report = build_report(
        regime_counts=regime_counts,
        candidate_counts=candidate_counts,
        rejection_counts=rejection_counts,
        compression_metric_rows=compression_metric_rows,
        source_db_path=source_db_path,
        start_date=start_date,
        end_date=end_date,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown_report(report, markdown_path)
    return report


def build_report(
    *,
    regime_counts: Counter[str],
    candidate_counts: Counter[str],
    rejection_counts: dict[str, Counter[str]],
    compression_metric_rows: list[dict[str, Any]],
    source_db_path: Path,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    regimes = sorted(regime_counts)
    return {
        "source_db_path": str(source_db_path),
        "date_range": {"start": start_date, "end": end_date},
        "regime_counts": {regime: int(regime_counts[regime]) for regime in regimes},
        "candidate_counts": {regime: int(candidate_counts.get(regime, 0)) for regime in regimes},
        "candidate_rates": {
            regime: _round(candidate_counts.get(regime, 0) / regime_counts[regime]) if regime_counts[regime] else 0.0
            for regime in regimes
        },
        "top_rejection_reasons_by_regime": {
            regime: dict(counter.most_common(15))
            for regime, counter in sorted(rejection_counts.items())
        },
        "compression_metrics": {
            "atr_percentile": _summary(row["atr_percentile"] for row in compression_metric_rows),
            "range_width_atr": _summary(row["range_width_atr"] for row in compression_metric_rows),
            "compression_duration_bars": _summary(row["compression_duration_bars"] for row in compression_metric_rows),
            "breakout_size_atr": _summary(row["breakout_size_atr"] for row in compression_metric_rows),
        },
        "interpretation": _interpret(rejection_counts.get("compression", Counter())),
    }


def write_markdown_report(report: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# Compression Rejection Analysis",
        "",
        f"Source DB: `{report['source_db_path']}`",
        f"Date range: `{report['date_range']['start']}` to `{report['date_range']['end']}`",
        "",
        "## Candidate Rates By Regime",
        "",
        "| Regime | Cycles | Candidates | Candidate Rate |",
        "|---|---:|---:|---:|",
    ]
    for regime, count in report["regime_counts"].items():
        lines.append(
            f"| {regime} | `{count}` | `{report['candidate_counts'][regime]}` | "
            f"`{report['candidate_rates'][regime]}` |"
        )
    lines.extend(["", "## Top Rejection Reasons By Regime", ""])
    for regime, reasons in report["top_rejection_reasons_by_regime"].items():
        lines.extend([f"### {regime}", "", "| Reason | Count |", "|---|---:|"])
        for reason, count in reasons.items():
            lines.append(f"| {reason} | `{count}` |")
        lines.append("")
    lines.extend(
        [
            "## Compression Metrics",
            "",
            "| Metric | Count | Mean | P50 | P95 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for metric, summary in report["compression_metrics"].items():
        lines.append(
            f"| {metric} | `{summary['count']}` | `{summary['mean']}` | "
            f"`{summary['p50']}` | `{summary['p95']}` |"
        )
    lines.extend(["", "## Interpretation", "", report["interpretation"]])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _interpret(compression_rejections: Counter[str]) -> str:
    if not compression_rejections:
        return "Compression-labeled cycles generated candidates; inspect trade outcomes."
    top = compression_rejections.most_common(3)
    return "Compression-labeled cycles are primarily blocked by: " + ", ".join(
        f"{reason}={count}" for reason, count in top
    )


def _summary(values: Any) -> dict[str, Any]:
    cleaned = [float(value) for value in values if value is not None]
    ordered = sorted(cleaned)
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
    parser = argparse.ArgumentParser(description="Analyze compression_breakout rejection reasons by regime.")
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-03-29")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    analyze_compression_rejections(
        source_db_path=args.source_db,
        start_date=args.start_date,
        end_date=args.end_date,
        output_path=args.output,
        markdown_path=args.markdown_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
