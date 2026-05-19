#!/usr/bin/env python3
"""SOLUSDT data feasibility check for trial-00095 transfer research.

Research Lab-only diagnostic. It performs REST/API reads and archive HEAD
probes, writes only a markdown report, and does not persist market data.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from research_lab.analysis_multi_asset_data_feasibility import (
    BASELINE_SYMBOL,
    BINANCE_VISION_BASE,
    MARKET_DB_PATH,
    REQUIRED_TABLES,
    evaluate_symbol,
    fetch_symbol_sample,
    local_inventory,
    probe_url,
    build_rest_client,
    _fmt_ts,
    _utc_now_floor,
)


SYMBOL = "SOLUSDT"
REPORT_PATH = Path("docs/analysis/SOL_DATA_FEASIBILITY_2026-05-19.md")


def run_feasibility(*, db_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or _utc_now_floor()
    inventory = local_inventory(db_path, (SYMBOL,))
    client = build_rest_client()
    sample = fetch_symbol_sample(client, SYMBOL, now)
    sample["historical_archive_probes"] = historical_archive_probes(SYMBOL)
    evaluation = evaluate_symbol(sample, inventory, SYMBOL)
    return {
        "milestone": "SOL_DATA_FEASIBILITY_V1",
        "symbol": SYMBOL,
        "generated_at": _fmt_ts(now),
        "inventory": inventory,
        "sample": sample,
        "evaluation": evaluation,
    }


def historical_archive_probes(symbol: str) -> dict[str, dict[str, Any]]:
    """Probe representative historical days before any full backfill milestone."""

    days = (date(2022, 1, 1), date(2023, 1, 1), date(2024, 1, 1), date(2025, 1, 1))
    result: dict[str, dict[str, Any]] = {}
    for day in days:
        prefix = day.isoformat()
        result[f"{prefix}_klines_15m"] = probe_url(
            f"{BINANCE_VISION_BASE}/klines/{symbol}/15m/{symbol}-15m-{prefix}.zip"
        )
        result[f"{prefix}_metrics"] = probe_url(
            f"{BINANCE_VISION_BASE}/metrics/{symbol}/{symbol}-metrics-{prefix}.zip"
        )
        result[f"{prefix}_aggtrades"] = probe_url(
            f"{BINANCE_VISION_BASE}/aggTrades/{symbol}/{symbol}-aggTrades-{prefix}.zip"
        )
    return result


def historical_archive_ok_share(probes: dict[str, dict[str, Any]]) -> float:
    return sum(1 for probe in probes.values() if probe.get("ok")) / max(len(probes), 1)


def builder_verdict(payload: dict[str, Any]) -> str:
    evaluation = payload["evaluation"]
    recent_verdict = str(evaluation["builder_verdict"])
    historical_ok = historical_archive_ok_share(payload["sample"]["historical_archive_probes"])
    aggtrade_rows = float(evaluation["metrics"].get("aggtrade_60s_rows", 0.0))
    if recent_verdict.startswith("FAIL"):
        return "FAIL_SOL_SAMPLE_SOURCE_OR_QUALITY"
    if historical_ok < 0.75:
        return "INCONCLUSIVE_SOL_HISTORICAL_ARCHIVE_COVERAGE"
    if aggtrade_rows < 45:
        return "PASS_SOL_ARCHIVE_SOURCE_FEASIBLE_REST_AGGTRADE_SAMPLE_LIMIT_FULL_BACKFILL_REQUIRED"
    return "PASS_SOL_SAMPLE_SOURCE_FEASIBLE_FULL_BACKFILL_REQUIRED"


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    sample = payload["sample"]
    evaluation = payload["evaluation"]
    metrics = evaluation["metrics"]
    final_verdict = builder_verdict(payload)
    lines = [
        "# SOL Data Feasibility",
        "",
        "**Milestone:** `SOL_DATA_FEASIBILITY_V1`",
        f"**Status:** `{final_verdict}`",
        "**Scope:** Research Lab data-quality diagnostic only; no market data persisted; no runtime/core changes.",
        "",
        "## Purpose",
        "",
        "Check whether SOLUSDT has enough source availability and sample quality to justify a later full historical backfill and frozen trial-00095 transfer test.",
        "",
        "## Local Inventory",
        "",
        f"- Source DB: `{payload['inventory']['db_path']}`",
        f"- DB exists: `{payload['inventory']['exists']}`",
        "",
        "| Table | BTCUSDT Rows | SOLUSDT Rows | SOLUSDT Range |",
        "|---|---:|---:|---|",
    ]
    inventory_tables = payload["inventory"].get("tables", {})
    for table in REQUIRED_TABLES:
        btc = inventory_tables.get(table, {}).get(BASELINE_SYMBOL, {})
        sol = inventory_tables.get(table, {}).get(SYMBOL, {})
        lines.append(
            f"| `{table}` | {btc.get('row_count', 0)} | {sol.get('row_count', 0)} | "
            f"{sol.get('date_start') or '-'} to {sol.get('date_end') or '-'} |"
        )

    lines += [
        "",
        "## Recent Sample Source Results",
        "",
        f"**Symbol:** `{SYMBOL}`",
        f"**Builder verdict:** `{final_verdict}`",
        f"**Sample gate verdict:** `{evaluation['gate_verdict']}`",
        f"**Sample window:** {sample['sample_start']} to {sample['sample_end']}",
        f"**Recent archive probe day:** {sample['archive_probe_day']}",
        "",
        "| Dataset | OK | Rows | Expected | Missing Rate | Duplicates | Quality Errors | Zero Volume |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for dataset in ["candles_15m", "candles_4h", "funding", "open_interest_15m", "aggtrade_60s", "book_ticker"]:
        result = sample[dataset]
        q = result["quality"]
        lines.append(
            f"| `{dataset}` | `{result['ok']}` | {q['row_count']} | {q['expected_count']} | "
            f"{q['missing_rate']:.2%} | {q['duplicate_count']} | {q['quality_errors']} | {q.get('zero_volume_count', 0)} |"
        )

    lines += [
        "",
        "## Recent Archive Probes",
        "",
        "| Archive Family | OK | Status |",
        "|---|---|---:|",
    ]
    for name, probe in sample["archive_probes"].items():
        lines.append(f"| `{name}` | `{probe.get('ok')}` | {probe.get('status')} |")

    lines += [
        "",
        "## Historical Archive Probes",
        "",
        f"**Historical archive OK share:** {historical_archive_ok_share(sample['historical_archive_probes']):.1%}",
        "",
        "| Probe | OK | Status |",
        "|---|---|---:|",
    ]
    for name, probe in sample["historical_archive_probes"].items():
        lines.append(f"| `{name}` | `{probe.get('ok')}` | {probe.get('status')} |")

    lines += [
        "",
        "## Gates",
        "",
        "| Gate | Threshold | Actual | Status | Severity |",
        "|---|---:|---:|---|---|",
    ]
    for gate in evaluation["gates"]:
        status = "PASS" if gate.get("passed") else "FAIL"
        threshold = f"{gate.get('operator', '')} {gate.get('threshold', '')}"
        lines.append(
            f"| {gate.get('name')} | {threshold} | {gate.get('actual_value')} | {status} | {gate.get('severity')} |"
        )

    lines += [
        "",
        "## Builder Interpretation",
        "",
        f"- Recent API families OK: {metrics['api_families_ok']:.0%}",
        f"- Recent archive families OK: {metrics['archive_families_ok']:.0%}",
        f"- Historical archive families OK: {historical_archive_ok_share(sample['historical_archive_probes']):.0%}",
        f"- Local required SOL tables present: {int(metrics['local_required_tables_present'])}/{len(REQUIRED_TABLES)}",
        "- REST aggtrade sample is limited for SOL activity; daily aggTrades archive availability is the relevant full-backfill signal.",
        "- A clean sample does not approve SOL strategy research.",
        "- Full SOL backfill is required before any SOL trial-00095 transfer test.",
        "- SOL runtime, shadow, PAPER, and threshold changes are out of scope.",
        "",
        "## Audit Questions",
        "",
        "1. Did the milestone avoid writing market data or modifying runtime/core/settings?",
        "2. Are local DB inventory results separated from external source checks?",
        "3. Are SOL recent sample quality gates explicit and reproducible?",
        "4. Are historical archive probes sufficient to decide whether full SOL backfill is worth scheduling?",
        "5. Does the report avoid claiming SOL research or runtime readiness before full backfill and audit?",
    ]
    text = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=MARKET_DB_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    payload = run_feasibility(db_path=args.db_path)
    print(generate_report(payload, args.report))
    print("payload", json.dumps({"verdict": builder_verdict(payload), "report": str(args.report)}, indent=2))
    print("git_commit", subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip())


if __name__ == "__main__":
    main()
