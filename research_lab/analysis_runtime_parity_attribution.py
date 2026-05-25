"""Attribute runtime-parity backtest results by simple entry dimensions."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from statistics import median
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True)
class BucketStats:
    trades: int
    pnl_r: float
    expectancy_r: float
    median_r: float
    win_rate: float
    profit_factor: float
    avg_mae: float
    avg_mfe: float
    mfe_mae_ratio: float | str
    avg_confluence: float


def _parse_ts(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _profit_factor(values: list[float]) -> float:
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def _stats(trades: list[dict[str, Any]]) -> BucketStats:
    pnl_r_values = [float(trade["pnl_r"]) for trade in trades]
    confluence = [float(trade["confluence_score"]) for trade in trades]
    mae_values = [abs(float(trade.get("mae") or 0.0)) for trade in trades]
    mfe_values = [float(trade.get("mfe") or 0.0) for trade in trades]
    count = len(trades)
    pnl_r = sum(pnl_r_values)
    avg_mae = sum(mae_values) / count if count else 0.0
    avg_mfe = sum(mfe_values) / count if count else 0.0
    return BucketStats(
        trades=count,
        pnl_r=pnl_r,
        expectancy_r=pnl_r / count if count else 0.0,
        median_r=median(pnl_r_values) if pnl_r_values else 0.0,
        win_rate=sum(1 for value in pnl_r_values if value > 0) / count if count else 0.0,
        profit_factor=_profit_factor(pnl_r_values),
        avg_mae=avg_mae,
        avg_mfe=avg_mfe,
        mfe_mae_ratio=(avg_mfe / avg_mae) if avg_mae > 0 else ("inf" if avg_mfe > 0 else 0.0),
        avg_confluence=sum(confluence) / count if count else 0.0,
    )


def _bucket_sweep_depth(value: Any) -> str:
    if value is None:
        return "unknown"
    depth = float(value)
    if depth < 0.0025:
        return "<0.25%"
    if depth < 0.005:
        return "0.25-0.50%"
    if depth < 0.01:
        return "0.50-1.00%"
    return ">=1.00%"


def _bucket_confluence(value: float) -> str:
    if value < 8:
        return "<8"
    if value < 12:
        return "8-12"
    if value < 16:
        return "12-16"
    return ">=16"


def _session(hour: int) -> str:
    if 0 <= hour < 8:
        return "asia_00_08"
    if 8 <= hour < 13:
        return "eu_08_13"
    if 13 <= hour < 21:
        return "us_13_21"
    return "late_21_24"


def _group_by(trades: Iterable[dict[str, Any]], dimension: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        features = trade.get("features_at_entry_json") or {}
        opened = _parse_ts(str(trade["opened_at"]))
        if dimension == "symbol":
            key = str(features.get("symbol") or "unknown")
        elif dimension == "regime":
            key = str(trade.get("regime") or "unknown")
        elif dimension == "direction":
            key = str(trade.get("direction") or "unknown")
        elif dimension == "sweep_side":
            key = str(features.get("sweep_side") or "unknown")
        elif dimension == "sweep_depth":
            key = _bucket_sweep_depth(features.get("sweep_depth_pct"))
        elif dimension == "confluence":
            key = _bucket_confluence(float(trade.get("confluence_score") or 0.0))
        elif dimension == "session":
            key = _session(opened.hour)
        elif dimension == "month":
            key = opened.strftime("%Y-%m")
        elif dimension == "weekday":
            key = opened.strftime("%A")
        elif dimension == "exit_reason":
            key = str(trade.get("exit_reason") or "unknown")
        else:
            raise ValueError(f"Unsupported dimension: {dimension}")
        grouped[key].append(trade)
    return dict(grouped)


def _table_for(trades: list[dict[str, Any]], dimension: str, min_trades: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, bucket in _group_by(trades, dimension).items():
        stats = _stats(bucket)
        if stats.trades < min_trades:
            continue
        rows.append(
            {
                "bucket": key,
                "trades": stats.trades,
                "pnl_r": round(stats.pnl_r, 6),
                "expectancy_r": round(stats.expectancy_r, 6),
                "median_r": round(stats.median_r, 6),
                "win_rate": round(stats.win_rate, 6),
                "profit_factor": round(stats.profit_factor, 6) if stats.profit_factor != float("inf") else "inf",
                "avg_mae": round(stats.avg_mae, 6),
                "avg_mfe": round(stats.avg_mfe, 6),
                "mfe_mae_ratio": round(stats.mfe_mae_ratio, 6) if isinstance(stats.mfe_mae_ratio, float) else stats.mfe_mae_ratio,
                "avg_confluence": round(stats.avg_confluence, 6),
            }
        )
    return sorted(rows, key=lambda row: (float(row["pnl_r"]) if row["pnl_r"] != "inf" else 1e9), reverse=True)


def build_report(input_path: Path, *, min_trades: int) -> dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    trades = list(payload.get("trades") or [])
    dimensions = [
        "symbol",
        "regime",
        "direction",
        "sweep_side",
        "sweep_depth",
        "confluence",
        "session",
        "month",
        "weekday",
        "exit_reason",
    ]
    return {
        "source": str(input_path),
        "overall": asdict(_stats(trades)),
        "min_trades_per_bucket": min_trades,
        "dimensions": {dimension: _table_for(trades, dimension, min_trades) for dimension in dimensions},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build attribution report from runtime-parity backtest JSON.")
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--min-trades", type=int, default=3)
    args = parser.parse_args()

    report = build_report(args.input_json, min_trades=max(int(args.min_trades), 1))
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Wrote attribution report: {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
