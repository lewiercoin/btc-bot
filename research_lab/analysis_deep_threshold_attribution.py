#!/usr/bin/env python3
"""Deep historical BTC threshold attribution.

Research-only orchestration around scripts/run_runtime_parity_backtest.py.
It runs fixed BTC sweep-depth variants over a long historical window and
aggregates which market/setup dimensions explain shallow sweep profitability.
"""

from __future__ import annotations

import os
import sys

if __name__ == "__main__" and sys.path:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.abspath(sys.path[0]) == script_dir:
        sys.path.pop(0)
        sys.path.insert(0, os.path.dirname(script_dir))

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path("storage/btc_bot.db")
DEFAULT_OUTPUT = Path("research_lab/analysis_output/deep_threshold_attribution_btc_2022_2026.json")
DEFAULT_REPORT = Path("research_lab/reports/deep_threshold_attribution_btc_2022_2026.md")
RUN_DIR = Path("research_lab/analysis_output/deep_threshold_attribution_runs")

THRESHOLDS = (0.0035, 0.0040, 0.0045, 0.0050, 0.0060, 0.00649)
DEPTH_BINS = (0.0, 0.0035, 0.0040, 0.0045, 0.0050, 0.0060, 0.0070, 0.0100, math.inf)
DEPTH_LABELS = (
    "<0.35%",
    "0.35-0.40%",
    "0.40-0.45%",
    "0.45-0.50%",
    "0.50-0.60%",
    "0.60-0.70%",
    "0.70-1.00%",
    ">=1.00%",
)
ATR_LABELS = ("Q1_low", "Q2", "Q3", "Q4_high")


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout


def _variant_id(threshold: float) -> str:
    return f"BTC_FIXED_{threshold:.5f}".replace(".", "p")


def _run_backtest(
    *,
    db: Path,
    threshold: float,
    start_date: str,
    end_date: str,
    force: bool,
) -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    output = RUN_DIR / f"{_variant_id(threshold)}_{start_date}_{end_date}.json".replace("-", "")
    if output.exists() and not force:
        return output
    command = [
        sys.executable,
        "scripts/run_runtime_parity_backtest.py",
        "--db",
        str(db),
        "--settings-profile",
        "live",
        "--start-date",
        start_date,
        "--end-date",
        end_date,
        "--symbols",
        "BTCUSDT",
        "--symbol-min-sweep-depth-pct",
        f"BTCUSDT={threshold}",
        "--output-json",
        str(output),
    ]
    print(f"running {_variant_id(threshold)}", flush=True)
    print(_run(command), flush=True)
    return output


def _session(opened_at: pd.Timestamp) -> str:
    hour = int(opened_at.hour)
    if 0 <= hour < 8:
        return "Asia"
    if 8 <= hour < 13:
        return "Europe"
    if 13 <= hour < 21:
        return "US"
    return "Late"


def _flatten_trades(path: Path, threshold: float) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for trade in payload["trades"]:
        features = trade.get("features_at_entry_json") or {}
        cost = features.get("cost_breakdown") or {}
        opened_at = pd.Timestamp(trade["opened_at"])
        rows.append(
            {
                "variant_threshold": threshold,
                "opened_at": opened_at,
                "closed_at": pd.Timestamp(trade["closed_at"]),
                "year": int(opened_at.year),
                "quarter": f"{opened_at.year}Q{opened_at.quarter}",
                "month": str(opened_at)[:7],
                "session": _session(opened_at),
                "direction": trade.get("direction"),
                "regime": trade.get("regime"),
                "confluence_score": float(trade.get("confluence_score") or 0.0),
                "net_pnl_r": float(trade.get("pnl_r") or 0.0),
                "gross_pnl_r": float(cost.get("gross_pnl_r", trade.get("pnl_r") or 0.0)),
                "win": 1 if float(trade.get("pnl_r") or 0.0) > 0 else 0,
                "mae": float(trade.get("mae") or 0.0),
                "mfe": float(trade.get("mfe") or 0.0),
                "exit_reason": trade.get("exit_reason"),
                "sweep_depth_pct": float(features.get("sweep_depth_pct") or 0.0),
                "sweep_side": features.get("sweep_side"),
                "atr_4h_norm": float(features.get("atr_4h_norm") or 0.0),
                "oi_zscore_60d": float(features.get("oi_zscore_60d") or 0.0),
                "tfi_60s": float(features.get("tfi_60s") or 0.0),
                "funding_pct_60d": float(features.get("funding_pct_60d") or 0.0),
                "force_order_rate_60s": float(features.get("force_order_rate_60s") or 0.0),
                "fees_r": float(cost.get("fees_total", 0.0)) / max(float(cost.get("risk_abs", 0.0)), 1e-12),
                "slippage_r": float(cost.get("slippage_total", 0.0)) / max(float(cost.get("risk_abs", 0.0)), 1e-12),
                "funding_r": float(cost.get("funding_paid", 0.0)) / max(float(cost.get("risk_abs", 0.0)), 1e-12),
            }
        )
    return rows


def _profit_factor(series: pd.Series) -> float | str:
    wins = float(series[series > 0].sum())
    losses = float(-series[series < 0].sum())
    if losses == 0:
        return "inf" if wins > 0 else 0.0
    return wins / losses


def _summary(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "trades": 0,
            "net_pnl_r": 0.0,
            "net_er": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "median_r": 0.0,
        }
    pnl = df["net_pnl_r"]
    return {
        "trades": int(len(df)),
        "net_pnl_r": round(float(pnl.sum()), 4),
        "net_er": round(float(pnl.mean()), 4),
        "win_rate": round(float(df["win"].mean()), 4),
        "profit_factor": _profit_factor(pnl),
        "median_r": round(float(pnl.median()), 4),
        "avg_mfe": round(float(df["mfe"].mean()), 4),
        "avg_mae": round(float(df["mae"].mean()), 4),
    }


def _group_summary(df: pd.DataFrame, keys: list[str], *, min_trades: int = 1) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if df.empty:
        return rows
    for group_key, group in df.groupby(keys, observed=False):
        if len(group) < min_trades:
            continue
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        item = {key: str(value) for key, value in zip(keys, group_key)}
        item.update(_summary(group))
        rows.append(item)
    rows.sort(key=lambda item: (int(item["trades"]), float(item["net_pnl_r"])), reverse=True)
    return rows


def _numeric_feature_scores(df: pd.DataFrame) -> list[dict[str, Any]]:
    features = [
        "sweep_depth_pct",
        "confluence_score",
        "atr_4h_norm",
        "oi_zscore_60d",
        "tfi_60s",
        "funding_pct_60d",
        "force_order_rate_60s",
        "mfe",
        "mae",
    ]
    rows: list[dict[str, Any]] = []
    for feature in features:
        if feature not in df or df[feature].nunique(dropna=True) < 2:
            continue
        corr_pnl = float(df[feature].corr(df["net_pnl_r"]))
        corr_win = float(df[feature].corr(df["win"]))
        quantiles = pd.qcut(df[feature].rank(method="first"), 4, labels=ATR_LABELS)
        grouped = df.assign(_q=quantiles).groupby("_q", observed=False)["net_pnl_r"].mean()
        spread = float(grouped.max() - grouped.min()) if not grouped.empty else 0.0
        rows.append(
            {
                "feature": feature,
                "corr_net_pnl_r": round(corr_pnl, 4),
                "corr_win": round(corr_win, 4),
                "quartile_er_spread": round(spread, 4),
            }
        )
    rows.sort(key=lambda item: abs(float(item["corr_net_pnl_r"])) + float(item["quartile_er_spread"]), reverse=True)
    return rows


def _categorical_feature_scores(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature in ["regime", "session", "sweep_side", "direction", "exit_reason", "depth_bucket", "atr_quartile"]:
        if feature not in df or df[feature].nunique(dropna=True) < 2:
            continue
        grouped = df.groupby(feature, observed=False)["net_pnl_r"].mean()
        rows.append(
            {
                "feature": feature,
                "levels": int(df[feature].nunique(dropna=True)),
                "er_spread": round(float(grouped.max() - grouped.min()), 4),
                "best_level": str(grouped.idxmax()),
                "best_er": round(float(grouped.max()), 4),
                "worst_level": str(grouped.idxmin()),
                "worst_er": round(float(grouped.min()), 4),
            }
        )
    rows.sort(key=lambda item: float(item["er_spread"]), reverse=True)
    return rows


def _prepare_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        df["shallow"] = pd.Series(dtype=bool)
        return df
    df["depth_bucket"] = pd.cut(
        df["sweep_depth_pct"],
        bins=DEPTH_BINS,
        labels=DEPTH_LABELS,
        right=False,
    )
    df["atr_quartile"] = pd.qcut(df["atr_4h_norm"].rank(method="first"), 4, labels=ATR_LABELS)
    df["confluence_bucket"] = pd.cut(
        df["confluence_score"],
        bins=(0, 4, 5, 6, 7, math.inf),
        labels=("<4", "4-5", "5-6", "6-7", ">=7"),
        right=False,
    )
    df["shallow"] = df["sweep_depth_pct"].between(0.0035, 0.0050, inclusive="left")
    return df


def _payload(df: pd.DataFrame, run_paths: dict[str, str]) -> dict[str, Any]:
    shallow = df[df["shallow"]].copy()
    fixed_rows = []
    for threshold, group in df.groupby("variant_threshold", observed=False):
        fixed_rows.append({"threshold": float(threshold), **_summary(group)})
    fixed_rows.sort(key=lambda item: item["threshold"])
    return {
        "meta": {
            "symbol": "BTCUSDT",
            "thresholds": list(THRESHOLDS),
            "run_paths": run_paths,
            "note": "Runtime-parity net-cost trade attribution. Trade-level reclaim speed is not currently persisted.",
        },
        "threshold_summary": fixed_rows,
        "overall_depth_bucket": _group_summary(df, ["depth_bucket"]),
        "shallow_depth_bucket": _group_summary(shallow, ["depth_bucket"]),
        "depth_by_year": _group_summary(df, ["year", "depth_bucket"], min_trades=3),
        "depth_by_quarter": _group_summary(df, ["quarter", "depth_bucket"], min_trades=3),
        "regime_by_depth": _group_summary(df, ["regime", "depth_bucket"], min_trades=3),
        "session_by_depth": _group_summary(df, ["session", "depth_bucket"], min_trades=3),
        "atr_by_depth": _group_summary(df, ["atr_quartile", "depth_bucket"], min_trades=3),
        "confluence_by_depth": _group_summary(df, ["confluence_bucket", "depth_bucket"], min_trades=3),
        "shallow_regime_session": _group_summary(shallow, ["regime", "session"], min_trades=3),
        "shallow_feature_scores_numeric": _numeric_feature_scores(shallow),
        "shallow_feature_scores_categorical": _categorical_feature_scores(shallow),
    }


def _format_pf(value: Any) -> str:
    if isinstance(value, str):
        return value
    return f"{float(value):.2f}"


def _table(rows: list[dict[str, Any]], columns: list[str], *, limit: int | None = None) -> list[str]:
    selected = rows[:limit] if limit else rows
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in selected:
        values = []
        for col in columns:
            value = row.get(col, "")
            if col == "profit_factor":
                value = _format_pf(value)
            values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _write_report(payload: dict[str, Any], report: Path) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Deep Historical Threshold Attribution V1",
        "",
        "BTC-only runtime-parity backtest with realistic fees, slippage, and funding.",
        "",
        "Important limitation: trade-level reclaim speed/depth is not yet persisted by the parity output, so this report attributes available entry features only.",
        "",
        "## Threshold Summary",
        "",
        *_table(payload["threshold_summary"], ["threshold", "trades", "net_pnl_r", "net_er", "win_rate", "profit_factor", "median_r"]),
        "",
        "## Overall Depth Buckets",
        "",
        *_table(payload["overall_depth_bucket"], ["depth_bucket", "trades", "net_pnl_r", "net_er", "win_rate", "profit_factor", "median_r"]),
        "",
        "## Shallow Depth Buckets",
        "",
        *_table(payload["shallow_depth_bucket"], ["depth_bucket", "trades", "net_pnl_r", "net_er", "win_rate", "profit_factor", "median_r"]),
        "",
        "## Regime x Depth",
        "",
        *_table(payload["regime_by_depth"], ["regime", "depth_bucket", "trades", "net_pnl_r", "net_er", "win_rate", "profit_factor"], limit=30),
        "",
        "## Session x Depth",
        "",
        *_table(payload["session_by_depth"], ["session", "depth_bucket", "trades", "net_pnl_r", "net_er", "win_rate", "profit_factor"], limit=30),
        "",
        "## ATR Quartile x Depth",
        "",
        *_table(payload["atr_by_depth"], ["atr_quartile", "depth_bucket", "trades", "net_pnl_r", "net_er", "win_rate", "profit_factor"], limit=30),
        "",
        "## Shallow Feature Scores",
        "",
        "Numeric scores combine simple correlation and quartile ER spread; this is discovery attribution, not a deployable ML model.",
        "",
        *_table(payload["shallow_feature_scores_numeric"], ["feature", "corr_net_pnl_r", "corr_win", "quartile_er_spread"]),
        "",
        "Categorical scores show which buckets separate shallow winners from losers.",
        "",
        *_table(payload["shallow_feature_scores_categorical"], ["feature", "levels", "er_spread", "best_level", "best_er", "worst_level", "worst_er"]),
        "",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deep historical BTC threshold attribution.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-05-24")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    all_rows: list[dict[str, Any]] = []
    run_paths: dict[str, str] = {}
    for threshold in THRESHOLDS:
        path = _run_backtest(
            db=args.db,
            threshold=threshold,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            force=bool(args.force),
        )
        run_paths[_variant_id(threshold)] = str(path)
        all_rows.extend(_flatten_trades(path, threshold))

    df = _prepare_frame(all_rows)
    payload = _payload(df, run_paths)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_report(payload, args.report)
    print(f"JSON: {args.output_json}")
    print(f"REPORT: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
