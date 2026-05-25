#!/usr/bin/env python3
"""ATR-relative threshold research for runtime-parity backtest.

Research-only orchestration around scripts/run_runtime_parity_backtest.py.
It runs net-cost Q1 2026 variants and writes a compact gate report.
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
import subprocess
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_DB = Path("storage/btc_bot.db")
DEFAULT_OUTPUT = Path("research_lab/analysis_output/atr_relative_threshold_research_q1_2026.json")
DEFAULT_REPORT = Path("research_lab/reports/atr_relative_threshold_research_q1_2026.md")
BASELINE_NET_ER = 0.400
BASELINE_NET_PF = 1.20


@dataclass(frozen=True, slots=True)
class Variant:
    variant_id: str
    symbols: str
    mode: str = "fixed"
    atr_multiplier: float | None = None
    floor: float | None = None
    ceiling: float | None = None


def _run_command(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout


def _payload_metrics(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = payload["result"]
    trades = payload["trades"]
    return {
        "result": result,
        "trades": trades,
        "performance": result["performance"],
        "gross_performance": result["gross_performance"],
        "cost_breakdown": result["cost_breakdown"],
    }


def _monthly_net(trades: list[dict[str, Any]]) -> dict[str, float]:
    output: dict[str, float] = {}
    for trade in trades:
        month = str(trade["opened_at"])[:7]
        output[month] = output.get(month, 0.0) + float(trade["pnl_r"])
    return {key: round(value, 4) for key, value in sorted(output.items())}


def _symbol_net(trades: list[dict[str, Any]]) -> dict[str, float]:
    output: dict[str, float] = {}
    for trade in trades:
        features = trade.get("features_at_entry_json") or {}
        symbol = str(features.get("symbol") or "UNKNOWN")
        output[symbol] = output.get(symbol, 0.0) + float(trade["pnl_r"])
    return {key: round(value, 4) for key, value in sorted(output.items())}


def _weekly_net(trades: list[dict[str, Any]]) -> dict[str, float]:
    output: dict[str, float] = {}
    for trade in trades:
        opened = str(trade["opened_at"])
        key = opened[:10]
        output[key] = output.get(key, 0.0) + float(trade["pnl_r"])
    return {key: round(value, 4) for key, value in sorted(output.items())}


def _gate_summary(metrics: dict[str, Any], *, symbols: tuple[str, ...]) -> dict[str, Any]:
    perf = metrics["performance"]
    trades = metrics["trades"]
    monthly = _monthly_net(trades)
    symbol_net = _symbol_net(trades)
    weekly = _weekly_net(trades)
    pnl_r = float(perf.get("pnl_r_sum", 0.0))
    net_er = float(perf.get("expectancy_r", 0.0))
    net_pf = float(perf.get("profit_factor", 0.0))
    trade_count = int(perf.get("trades_count", 0))
    top_week = max(weekly.values()) if weekly else 0.0
    top_week_ratio = (top_week / pnl_r) if pnl_r > 0 else 999.0
    btc_net = float(symbol_net.get("BTCUSDT", 0.0))
    sol_net = float(symbol_net.get("SOLUSDT", 0.0))
    sol_dominated = "SOLUSDT" in symbols and pnl_r > 0 and sol_net / pnl_r > 0.40

    gates = {
        "net_er_ge_baseline": net_er >= BASELINE_NET_ER,
        "net_pf_ge_1_30": net_pf >= 1.30,
        "no_negative_month": bool(monthly) and all(value >= 0 for value in monthly.values()),
        "btc_not_negative": btc_net >= 0,
        "not_sol_dominated": not sol_dominated,
        "no_one_week_dependency": top_week_ratio <= 0.40,
        "trade_count_40_100": 40 <= trade_count <= 100,
    }
    return {
        "gates": gates,
        "passed": all(gates.values()),
        "monthly_net_pnl_r": monthly,
        "symbol_net_pnl_r": symbol_net,
        "top_week_pnl_r": round(top_week, 4),
        "top_week_ratio": round(top_week_ratio, 4),
    }


def _variant_output_path(output_dir: Path, variant: Variant) -> Path:
    return output_dir / f"{variant.variant_id}.json"


def run_variant(variant: Variant, *, db_path: Path, output_dir: Path) -> dict[str, Any]:
    output_path = _variant_output_path(output_dir, variant)
    command = [
        sys.executable,
        "scripts/run_runtime_parity_backtest.py",
        "--db",
        str(db_path),
        "--settings-profile",
        "live",
        "--start-date",
        "2026-01-01",
        "--end-date",
        "2026-03-31",
        "--symbols",
        variant.symbols,
        "--output-json",
        str(output_path),
    ]
    if variant.mode == "atr_4h_relative":
        command.extend([
            "--dynamic-threshold-mode",
            "atr_4h_relative",
            "--dynamic-threshold-atr-multiplier",
            str(variant.atr_multiplier),
            "--dynamic-threshold-floor",
            str(variant.floor),
            "--dynamic-threshold-ceiling",
            str(variant.ceiling),
        ])
    stdout = _run_command(command)
    metrics = _payload_metrics(output_path)
    symbol_tuple = tuple(item.strip().upper() for item in variant.symbols.split(",") if item.strip())
    gate = _gate_summary(metrics, symbols=symbol_tuple)
    perf = metrics["performance"]
    return {
        "variant": {
            "variant_id": variant.variant_id,
            "symbols": list(symbol_tuple),
            "mode": variant.mode,
            "atr_multiplier": variant.atr_multiplier,
            "floor": variant.floor,
            "ceiling": variant.ceiling,
        },
        "output_json": str(output_path),
        "stdout_tail": stdout.strip().splitlines()[-12:],
        "net_metrics": {
            "trades": int(perf.get("trades_count", 0)),
            "expectancy_r": round(float(perf.get("expectancy_r", 0.0)), 4),
            "pnl_r": round(float(perf.get("pnl_r_sum", 0.0)), 4),
            "profit_factor": round(float(perf.get("profit_factor", 0.0)), 4),
            "max_drawdown_pct": round(float(perf.get("max_drawdown_pct", 0.0)), 6),
        },
        "cost_breakdown": metrics["cost_breakdown"],
        "gate_summary": gate,
    }


def load_existing_variant(variant: Variant, *, output_dir: Path) -> dict[str, Any] | None:
    output_path = _variant_output_path(output_dir, variant)
    if not output_path.exists():
        return None
    metrics = _payload_metrics(output_path)
    symbol_tuple = tuple(item.strip().upper() for item in variant.symbols.split(",") if item.strip())
    gate = _gate_summary(metrics, symbols=symbol_tuple)
    perf = metrics["performance"]
    return {
        "variant": {
            "variant_id": variant.variant_id,
            "symbols": list(symbol_tuple),
            "mode": variant.mode,
            "atr_multiplier": variant.atr_multiplier,
            "floor": variant.floor,
            "ceiling": variant.ceiling,
        },
        "output_json": str(output_path),
        "stdout_tail": [],
        "net_metrics": {
            "trades": int(perf.get("trades_count", 0)),
            "expectancy_r": round(float(perf.get("expectancy_r", 0.0)), 4),
            "pnl_r": round(float(perf.get("pnl_r_sum", 0.0)), 4),
            "profit_factor": round(float(perf.get("profit_factor", 0.0)), 4),
            "max_drawdown_pct": round(float(perf.get("max_drawdown_pct", 0.0)), 6),
        },
        "cost_breakdown": metrics["cost_breakdown"],
        "gate_summary": gate,
    }


def variants(*, full_matrix: bool) -> list[Variant]:
    scopes = {
        "BTC": "BTCUSDT",
        "BTC_ETH": "BTCUSDT,ETHUSDT",
        "FULL": "BTCUSDT,ETHUSDT,SOLUSDT",
    }
    output = [
        Variant("BASELINE_FULL", scopes["FULL"]),
        Variant("BASELINE_BTC_ETH", scopes["BTC_ETH"]),
        Variant("BASELINE_BTC", scopes["BTC"]),
    ]
    multipliers = [0.20, 0.25, 0.30] if not full_matrix else [0.15, 0.20, 0.25, 0.30, 0.35]
    floors = [0.0025, 0.0030] if not full_matrix else [0.0025, 0.0030, 0.0035]
    ceilings = [0.0075] if not full_matrix else [0.0075, 0.0100]
    for scope_id, symbols in scopes.items():
        for multiplier in multipliers:
            for floor in floors:
                for ceiling in ceilings:
                    output.append(
                        Variant(
                            variant_id=f"ATR4H_{scope_id}_M{str(multiplier).replace('.', '')}_F{str(floor).replace('.', '')}_C{str(ceiling).replace('.', '')}",
                            symbols=symbols,
                            mode="atr_4h_relative",
                            atr_multiplier=multiplier,
                            floor=floor,
                            ceiling=ceiling,
                        )
                    )
    return output


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# ATR Relative Threshold Research Q1 2026",
        "",
        "Research-only runtime-parity net-cost sweep. No production settings changes.",
        "",
        f"Completed variants: `{payload.get('completed_variants', len(payload['runs']))}` of planned `{payload.get('planned_variants', len(payload['runs']))}`.",
        "",
        "Formula:",
        "",
        "`threshold = clamp(atr_4h_norm * multiplier, floor, ceiling)`",
        "",
        "## Gates",
        "",
        "- net ER >= baseline `+0.400R`",
        "- net PF >= `1.30`",
        "- no negative month in Q1",
        "- BTC net PnL not negative",
        "- not SOL dominated",
        "- top week <= 40% of total PnL",
        "- trade count between 40 and 100",
        "",
        "## Results",
        "",
        "| Variant | Symbols | Mode | M | Floor | Ceiling | Trades | Net ER | Net PnL R | Net PF | Gates |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for run in payload["runs"]:
        variant = run["variant"]
        metrics = run["net_metrics"]
        gates = run["gate_summary"]
        gate_text = "PASS" if gates["passed"] else "FAIL"
        lines.append(
            f"| `{variant['variant_id']}` | {','.join(variant['symbols'])} | `{variant['mode']}` | "
            f"{variant['atr_multiplier'] if variant['atr_multiplier'] is not None else ''} | "
            f"{variant['floor'] if variant['floor'] is not None else ''} | "
            f"{variant['ceiling'] if variant['ceiling'] is not None else ''} | "
            f"{metrics['trades']} | {metrics['expectancy_r']:.4f} | {metrics['pnl_r']:.2f} | "
            f"{metrics['profit_factor']:.2f} | {gate_text} |"
        )

    passing = [run for run in payload["runs"] if run["gate_summary"]["passed"]]
    best = max(payload["runs"], key=lambda item: (item["net_metrics"]["expectancy_r"], item["net_metrics"]["profit_factor"]))
    failure_counts: dict[str, int] = {}
    for run in payload["runs"]:
        for name, passed in run["gate_summary"]["gates"].items():
            if not passed:
                failure_counts[name] = failure_counts.get(name, 0) + 1
    lines.extend([
        "",
        "## Verdict",
        "",
        f"- Passing variants: `{len(passing)}`",
        f"- Best headline variant: `{best['variant']['variant_id']}` with ER `{best['net_metrics']['expectancy_r']:.4f}` and PF `{best['net_metrics']['profit_factor']:.2f}`.",
        f"- Most common failed gates: `{', '.join(f'{key}={value}' for key, value in sorted(failure_counts.items(), key=lambda item: (-item[1], item[0]))[:4])}`.",
    ])
    if not passing:
        lines.append("- No variant is deployment-ready under the predefined gates.")
    else:
        lines.append("- Passing variants require independent audit before any PAPER deployment.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--full-matrix", action="store_true")
    parser.add_argument("--from-existing", action="store_true", help="Aggregate already generated per-variant JSON files.")
    args = parser.parse_args()

    output_dir = args.output.parent / "atr_relative_threshold_runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    planned = variants(full_matrix=args.full_matrix)
    if args.from_existing:
        runs = [run for variant in planned if (run := load_existing_variant(variant, output_dir=output_dir)) is not None]
    else:
        runs = [run_variant(variant, db_path=args.db, output_dir=output_dir) for variant in planned]
    payload = {
        "milestone": "ATR_RELATIVE_THRESHOLD_RESEARCH_V1",
        "full_matrix": bool(args.full_matrix),
        "from_existing": bool(args.from_existing),
        "planned_variants": len(planned),
        "completed_variants": len(runs),
        "baseline": {"net_er": BASELINE_NET_ER, "net_pf": BASELINE_NET_PF},
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    args.report.write_text(render_report(payload), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "report": str(args.report),
        "variants": len(runs),
        "passing": sum(1 for run in runs if run["gate_summary"]["passed"]),
        "best": max(runs, key=lambda item: item["net_metrics"]["expectancy_r"])["variant"]["variant_id"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
