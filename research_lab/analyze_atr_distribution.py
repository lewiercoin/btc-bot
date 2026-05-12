from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from backtest.backtest_runner import BacktestConfig
from backtest.replay_loader import ReplayLoader, ReplayLoaderConfig
from core.feature_engine import FeatureEngine, FeatureEngineConfig
from settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = Path("research_lab/reports/atr_norm_distribution_2022_2026.json")
DEFAULT_MARKDOWN_PATH = Path("research_lab/reports/atr_norm_distribution_2022_2026.md")


@dataclass(slots=True)
class AtrDistributionConfig:
    source_db_path: Path
    start_date: str = "2022-01-01"
    end_date: str = "2026-03-29"
    output_path: Path = DEFAULT_OUTPUT_PATH
    markdown_path: Path = DEFAULT_MARKDOWN_PATH


def analyze_atr_norm_distribution(config: AtrDistributionConfig) -> dict[str, Any]:
    conn = sqlite3.connect(config.source_db_path)
    conn.row_factory = sqlite3.Row
    values: list[float] = []
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
            start_date=config.start_date,
            end_date=config.end_date,
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
            if features.atr_4h_norm > 0:
                values.append(float(features.atr_4h_norm))
    finally:
        conn.close()

    report = build_atr_distribution_report(
        values=values,
        source_db_path=config.source_db_path,
        start_date=config.start_date,
        end_date=config.end_date,
    )
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    config.output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown_report(report, config.markdown_path)
    return report


def build_atr_distribution_report(
    *,
    values: list[float],
    source_db_path: Path,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    ordered = sorted(values)
    percentiles = {
        "p50": _percentile(ordered, 50),
        "p75": _percentile(ordered, 75),
        "p90": _percentile(ordered, 90),
        "p95": _percentile(ordered, 95),
        "p99": _percentile(ordered, 99),
    }
    return {
        "source_db_path": str(source_db_path),
        "date_range": {"start": start_date, "end": end_date},
        "sample_count": len(ordered),
        "mean": _round(mean(ordered)) if ordered else None,
        "std": _round(pstdev(ordered)) if len(ordered) > 1 else None,
        "min": _round(ordered[0]) if ordered else None,
        "max": _round(ordered[-1]) if ordered else None,
        "percentiles": percentiles,
        "recommended_threshold": {
            "policy": "p95",
            "value": percentiles["p95"],
            "reason": "Volatility panic should be rare; p95 avoids rejecting normal BTC volatility.",
        },
    }


def write_markdown_report(report: dict[str, Any], output_path: Path) -> None:
    pct = report["percentiles"]
    lines = [
        "# ATR 4H Norm Distribution",
        "",
        f"Source DB: `{report['source_db_path']}`",
        f"Date range: `{report['date_range']['start']}` -> `{report['date_range']['end']}`",
        f"Sample count: `{report['sample_count']}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| mean | `{report['mean']}` |",
        f"| std | `{report['std']}` |",
        f"| min | `{report['min']}` |",
        f"| p50 | `{pct['p50']}` |",
        f"| p75 | `{pct['p75']}` |",
        f"| p90 | `{pct['p90']}` |",
        f"| p95 | `{pct['p95']}` |",
        f"| p99 | `{pct['p99']}` |",
        f"| max | `{report['max']}` |",
        "",
        "Recommended volatility panic threshold: "
        f"`{report['recommended_threshold']['value']}` ({report['recommended_threshold']['policy']}).",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _percentile(ordered: list[float], percentile: float) -> float | None:
    if not ordered:
        return None
    if len(ordered) == 1:
        return _round(ordered[0])
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    value = ordered[lower] * (1.0 - weight) + ordered[upper] * weight
    return _round(value)


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 8)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze empirical atr_4h_norm distribution.")
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-03-29")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_PATH)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    analyze_atr_norm_distribution(
        AtrDistributionConfig(
            source_db_path=args.source_db,
            start_date=args.start_date,
            end_date=args.end_date,
            output_path=args.output,
            markdown_path=args.markdown_output,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
