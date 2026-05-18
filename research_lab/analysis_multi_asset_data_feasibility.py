#!/usr/bin/env python3
"""Multi-asset data feasibility check.

Research Lab-only diagnostic that answers whether ETH/SOL data sources are
available and clean enough to justify a later full transfer backtest. It does
not persist market data and does not modify runtime behavior.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from data.rest_client import BinanceFuturesRestClient, RestClientConfig, RestClientError
from research_lab.evaluators.gate_evaluator import Gate, evaluate_gates
from scripts.bootstrap_history import build_aggtrade_buckets
from settings import load_settings


MARKET_DB_PATH = Path("research_lab/snapshots/replay-run13-regime-aware-trial-00063.db")
REPORT_PATH = Path("docs/analysis/MULTI_ASSET_DATA_FEASIBILITY_2026-05-18.md")
SYMBOLS = ("ETHUSDT",)
BASELINE_SYMBOL = "BTCUSDT"
REQUIRED_TABLES = {
    "candles": "open_time",
    "funding": "funding_time",
    "open_interest": "timestamp",
    "aggtrade_buckets": "bucket_time",
    "force_orders": "event_time",
}
BINANCE_VISION_BASE = "https://data.binance.vision/data/futures/um/daily"


@dataclass(frozen=True)
class QualityResult:
    dataset_id: str
    row_count: int
    expected_count: int
    missing_count: int
    missing_rate: float
    duplicate_count: int
    quality_errors: int
    zero_volume_count: int = 0
    date_start: str = ""
    date_end: str = ""
    error: str = ""


def _utc_now_floor() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(minute=0, second=0, microsecond=0)


def _to_ms(value: datetime) -> int:
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def _fmt_ts(value: datetime | None) -> str:
    return value.astimezone(timezone.utc).isoformat() if value else ""


def _day_for_archive_probe(now: datetime) -> date:
    return (now - timedelta(days=3)).date()


def build_rest_client() -> BinanceFuturesRestClient:
    settings = load_settings(profile="research")
    return BinanceFuturesRestClient(
        RestClientConfig(
            base_url=settings.exchange.futures_rest_base_url,
            timeout_seconds=settings.execution.rest_timeout_seconds,
            max_retries=1,
            retry_backoff_seconds=0.25,
        )
    )


def local_inventory(db_path: Path, symbols: tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {"db_path": str(db_path), "exists": db_path.exists(), "tables": {}}
    if not db_path.exists():
        return result
    conn = sqlite3.connect(db_path)
    try:
        for table, time_col in REQUIRED_TABLES.items():
            table_rows: dict[str, Any] = {}
            for symbol in (BASELINE_SYMBOL,) + symbols:
                try:
                    row = conn.execute(
                        f"SELECT COUNT(*), MIN({time_col}), MAX({time_col}) FROM {table} WHERE symbol = ?",
                        (symbol,),
                    ).fetchone()
                    table_rows[symbol] = {"row_count": int(row[0] or 0), "date_start": row[1], "date_end": row[2]}
                except sqlite3.Error as exc:
                    table_rows[symbol] = {"row_count": 0, "date_start": None, "date_end": None, "error": str(exc)}
            result["tables"][table] = table_rows
    finally:
        conn.close()
    return result


def fetch_symbol_sample(client: BinanceFuturesRestClient, symbol: str, now: datetime) -> dict[str, Any]:
    sample_end = now
    candle_start = sample_end - timedelta(days=7)
    agg_start = sample_end - timedelta(hours=1)
    archive_day = _day_for_archive_probe(now)
    sample: dict[str, Any] = {"symbol": symbol, "sample_start": _fmt_ts(candle_start), "sample_end": _fmt_ts(sample_end)}

    sample["candles_15m"] = _safe_fetch(
        lambda: client.fetch_klines(symbol, "15m", limit=700, start_time_ms=_to_ms(candle_start), end_time_ms=_to_ms(sample_end)),
        lambda rows: assess_candles(f"{symbol}_15m_klines", rows, interval_minutes=15, start=candle_start, end=sample_end),
    )
    sample["candles_4h"] = _safe_fetch(
        lambda: client.fetch_klines(symbol, "4h", limit=200, start_time_ms=_to_ms(candle_start - timedelta(days=23)), end_time_ms=_to_ms(sample_end)),
        lambda rows: assess_candles(f"{symbol}_4h_klines", rows, interval_minutes=240, start=candle_start - timedelta(days=23), end=sample_end),
    )
    sample["funding"] = _safe_fetch(
        lambda: client.fetch_funding_history(symbol, limit=100, start_time_ms=_to_ms(candle_start), end_time_ms=_to_ms(sample_end)),
        lambda rows: assess_timestamp_rows(f"{symbol}_funding", rows, "funding_time", expected_interval_minutes=480),
    )
    sample["open_interest_15m"] = _safe_fetch(
        lambda: client.fetch_open_interest_history(symbol, period="15m", limit=700, start_time_ms=_to_ms(candle_start), end_time_ms=_to_ms(sample_end)),
        lambda rows: assess_timestamp_rows(f"{symbol}_open_interest_15m", rows, "timestamp", expected_interval_minutes=15),
    )
    sample["aggtrade_60s"] = _safe_fetch(
        lambda: build_aggtrade_buckets(
            client.fetch_agg_trades_window(symbol=symbol, start_time=agg_start, end_time=sample_end, limit=1000),
            symbol,
            "60s",
        ),
        lambda rows: assess_timestamp_rows(f"{symbol}_aggtrade_60s", rows, "bucket_time", expected_interval_minutes=1, expected_count=60),
    )
    sample["book_ticker"] = _safe_fetch(
        lambda: [client.fetch_book_ticker(symbol)],
        assess_book_ticker,
    )
    sample["archive_probes"] = {
        "klines_15m_daily_zip": probe_url(
            f"{BINANCE_VISION_BASE}/klines/{symbol}/15m/{symbol}-15m-{archive_day.isoformat()}.zip"
        ),
        "metrics_daily_zip": probe_url(
            f"{BINANCE_VISION_BASE}/metrics/{symbol}/{symbol}-metrics-{archive_day.isoformat()}.zip"
        ),
        "aggtrades_daily_zip": probe_url(
            f"{BINANCE_VISION_BASE}/aggTrades/{symbol}/{symbol}-aggTrades-{archive_day.isoformat()}.zip"
        ),
        "liquidation_snapshot_daily_zip": probe_url(
            f"{BINANCE_VISION_BASE}/liquidationSnapshot/{symbol}/{symbol}-liquidationSnapshot-{archive_day.isoformat()}.zip"
        ),
    }
    sample["archive_probe_day"] = archive_day.isoformat()
    return sample


def _safe_fetch(fetch_fn, assess_fn) -> dict[str, Any]:
    try:
        rows = fetch_fn()
        quality = assess_fn(rows)
        return {"ok": True, "quality": quality.__dict__}
    except (RestClientError, urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
        return {"ok": False, "quality": QualityResult("unavailable", 0, 0, 0, 1.0, 0, 0, error=str(exc)).__dict__}


def assess_candles(dataset_id: str, rows: list[dict[str, Any]], *, interval_minutes: int, start: datetime, end: datetime) -> QualityResult:
    expected = max(0, int((end - start).total_seconds() // (interval_minutes * 60)))
    times = [row["open_time"] for row in rows]
    duplicate_count = len(times) - len(set(times))
    missing_count = max(0, expected - len(set(times)))
    errors = 0
    zero_volume = 0
    for row in rows:
        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])
        if not (l <= o <= h and l <= c <= h and l <= h):
            errors += 1
        if float(row.get("volume", 0.0)) <= 0:
            zero_volume += 1
        if row["open_time"].tzinfo is None:
            errors += 1
    return QualityResult(
        dataset_id=dataset_id,
        row_count=len(rows),
        expected_count=expected,
        missing_count=missing_count,
        missing_rate=missing_count / expected if expected else 0.0,
        duplicate_count=duplicate_count,
        quality_errors=errors,
        zero_volume_count=zero_volume,
        date_start=_fmt_ts(min(times) if times else None),
        date_end=_fmt_ts(max(times) if times else None),
    )


def assess_timestamp_rows(
    dataset_id: str,
    rows: list[dict[str, Any]],
    timestamp_field: str,
    *,
    expected_interval_minutes: int,
    expected_count: int | None = None,
) -> QualityResult:
    times = [row[timestamp_field] for row in rows]
    duplicate_count = len(times) - len(set(times))
    if expected_count is None and len(times) >= 2:
        expected_count = max(0, int((max(times) - min(times)).total_seconds() // (expected_interval_minutes * 60)) + 1)
    expected_count = int(expected_count or 0)
    missing_count = max(0, expected_count - len(set(times))) if expected_count else 0
    errors = sum(1 for ts in times if ts.tzinfo is None)
    return QualityResult(
        dataset_id=dataset_id,
        row_count=len(rows),
        expected_count=expected_count,
        missing_count=missing_count,
        missing_rate=missing_count / expected_count if expected_count else 0.0,
        duplicate_count=duplicate_count,
        quality_errors=errors,
        date_start=_fmt_ts(min(times) if times else None),
        date_end=_fmt_ts(max(times) if times else None),
    )


def assess_book_ticker(rows: list[dict[str, Any]]) -> QualityResult:
    if not rows:
        return QualityResult("book_ticker", 0, 1, 1, 1.0, 0, 1, error="empty book ticker")
    row = rows[0]
    bid = float(row["bid"])
    ask = float(row["ask"])
    errors = 0 if ask >= bid > 0 else 1
    spread_bps = ((ask - bid) / ((ask + bid) / 2) * 10000) if ask and bid else 999.0
    return QualityResult(
        dataset_id=f"{row['symbol']}_book_ticker_spread_bps={spread_bps:.3f}",
        row_count=1,
        expected_count=1,
        missing_count=0,
        missing_rate=0.0,
        duplicate_count=0,
        quality_errors=errors,
    )


def probe_url(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return {"ok": True, "status": int(response.status), "url": url}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": int(exc.code), "url": url}
    except urllib.error.URLError as exc:
        return {"ok": False, "status": None, "url": url, "error": str(exc.reason)}


def flatten_quality(sample: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    required = ["candles_15m", "candles_4h", "funding", "open_interest_15m", "aggtrade_60s", "book_ticker"]
    metrics["api_families_ok"] = sum(1 for key in required if sample.get(key, {}).get("ok")) / len(required)
    for key in required:
        q = sample.get(key, {}).get("quality", {})
        metrics[f"{key}_rows"] = float(q.get("row_count", 0))
        metrics[f"{key}_missing_rate"] = float(q.get("missing_rate", 1.0))
        metrics[f"{key}_duplicates"] = float(q.get("duplicate_count", 0))
        metrics[f"{key}_quality_errors"] = float(q.get("quality_errors", 0))
        metrics[f"{key}_zero_volume"] = float(q.get("zero_volume_count", 0))
    probes = sample.get("archive_probes", {})
    metrics["archive_families_ok"] = sum(1 for probe in probes.values() if probe.get("ok")) / max(len(probes), 1)
    return metrics


def evaluate_symbol(sample: dict[str, Any], inventory: dict[str, Any], symbol: str) -> dict[str, Any]:
    metrics = flatten_quality(sample)
    local_tables = inventory.get("tables", {})
    metrics["local_required_tables_present"] = sum(
        1 for table in REQUIRED_TABLES if local_tables.get(table, {}).get(symbol, {}).get("row_count", 0) > 0
    )
    gates = [
        Gate("api_families_ok", "==", 1.0, "api_families_ok", "REQUIRED"),
        Gate("candles_15m_missing_rate", "<=", 0.01, "candles_15m_missing_rate", "REQUIRED"),
        Gate("candles_15m_quality_errors", "==", 0, "candles_15m_quality_errors", "REQUIRED"),
        Gate("candles_15m_duplicates", "==", 0, "candles_15m_duplicates", "REQUIRED"),
        Gate("candles_4h_missing_rate", "<=", 0.01, "candles_4h_missing_rate", "REQUIRED"),
        Gate("funding_rows", ">=", 10, "funding_rows", "RECOMMENDED"),
        Gate("open_interest_rows", ">=", 100, "open_interest_15m_rows", "RECOMMENDED"),
        Gate("aggtrade_rows", ">=", 45, "aggtrade_60s_rows", "RECOMMENDED"),
        Gate("archive_families_ok", ">=", 0.75, "archive_families_ok", "RECOMMENDED"),
    ]
    result = evaluate_gates(metrics, gates, experiment_id=f"{symbol}_data_feasibility")
    verdict = "PASS_SAMPLE_SOURCE_FEASIBLE_FULL_BACKFILL_REQUIRED"
    if result.verdict == "FAIL":
        verdict = "FAIL_SAMPLE_SOURCE_OR_QUALITY"
    elif metrics["local_required_tables_present"] >= len(REQUIRED_TABLES):
        verdict = "PASS_LOCAL_DATA_READY_FOR_RESEARCH"
    elif metrics["archive_families_ok"] < 0.75:
        verdict = "INCONCLUSIVE_ARCHIVE_COVERAGE_RISK"
    return {
        "symbol": symbol,
        "metrics": metrics,
        "gate_verdict": result.verdict,
        "builder_verdict": verdict,
        "gates": [gate.to_dict() for gate in result.gate_results],
    }


def run_feasibility(symbols: tuple[str, ...], db_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or _utc_now_floor()
    inventory = local_inventory(db_path, symbols)
    client = build_rest_client()
    samples: dict[str, Any] = {}
    evaluations: dict[str, Any] = {}
    for symbol in symbols:
        sample = fetch_symbol_sample(client, symbol.upper(), now)
        samples[symbol.upper()] = sample
        evaluations[symbol.upper()] = evaluate_symbol(sample, inventory, symbol.upper())
    return {
        "milestone": "MULTI_ASSET_DATA_FEASIBILITY_V1",
        "generated_at": _fmt_ts(now),
        "symbols": list(symbols),
        "inventory": inventory,
        "samples": samples,
        "evaluations": evaluations,
    }


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    lines = [
        "# Multi-Asset Data Feasibility",
        "",
        "**Milestone:** `MULTI_ASSET_DATA_FEASIBILITY_V1`",
        "**Status:** READY_FOR_AUDIT",
        "**Scope:** Research Lab data-quality diagnostic only; no market data persisted; no runtime/core changes.",
        "",
        "## Purpose",
        "",
        "Check whether ETH/SOL-style multi-asset research is worth scheduling by validating source availability, sample cleanliness, archive paths, and local DB inventory before any full historical backfill.",
        "",
        "## Local Inventory",
        "",
        f"- Source DB: `{payload['inventory']['db_path']}`",
        f"- DB exists: `{payload['inventory']['exists']}`",
        "",
        "| Table | BTCUSDT Rows | ETHUSDT Rows | ETHUSDT Range |",
        "|---|---:|---:|---|",
    ]
    inventory_tables = payload["inventory"].get("tables", {})
    for table in REQUIRED_TABLES:
        btc = inventory_tables.get(table, {}).get(BASELINE_SYMBOL, {})
        eth = inventory_tables.get(table, {}).get("ETHUSDT", {})
        lines.append(
            f"| `{table}` | {btc.get('row_count', 0)} | {eth.get('row_count', 0)} | "
            f"{eth.get('date_start') or '-'} to {eth.get('date_end') or '-'} |"
        )
    lines += ["", "## Sample Source Results", ""]
    for symbol, evaluation in payload["evaluations"].items():
        sample = payload["samples"][symbol]
        m = evaluation["metrics"]
        lines += [
            f"### {symbol}",
            "",
            f"**Builder verdict:** `{evaluation['builder_verdict']}`",
            f"**Gate verdict:** `{evaluation['gate_verdict']}`",
            f"**Sample window:** {sample['sample_start']} to {sample['sample_end']}",
            f"**Archive probe day:** {sample['archive_probe_day']}",
            "",
            "| Dataset | OK | Rows | Expected | Missing Rate | Duplicates | Quality Errors |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for dataset in ["candles_15m", "candles_4h", "funding", "open_interest_15m", "aggtrade_60s", "book_ticker"]:
            result = sample[dataset]
            q = result["quality"]
            lines.append(
                f"| `{dataset}` | `{result['ok']}` | {q['row_count']} | {q['expected_count']} | "
                f"{q['missing_rate']:.2%} | {q['duplicate_count']} | {q['quality_errors']} |"
            )
        lines += [
            "",
            "| Archive Family | OK | Status |",
            "|---|---|---:|",
        ]
        for name, probe in sample["archive_probes"].items():
            lines.append(f"| `{name}` | `{probe.get('ok')}` | {probe.get('status')} |")
        lines += [
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
            "Key metrics:",
            f"- API families OK: {m['api_families_ok']:.0%}",
            f"- Archive families OK: {m['archive_families_ok']:.0%}",
            f"- Local required tables present: {int(m['local_required_tables_present'])}/{len(REQUIRED_TABLES)}",
            "",
        ]
    lines += [
        "## Builder Interpretation",
        "",
        "- Local research snapshot is BTC-only for the required trial-00095 data families.",
        "- A clean ETH sample can justify a later historical backfill milestone, but it is not itself enough for ETH strategy research.",
        "- Full transfer research should not start until 2022-2026 ETH 15m/4h candles, funding, OI, and aggtrade/TFI coverage are materialized and audited.",
        "- Force-order/liquidation data should remain diagnostic or disabled unless its archive coverage is proven separately.",
        "",
        "## Audit Questions",
        "",
        "1. Did the milestone avoid writing market data or modifying runtime/core/settings?",
        "2. Are local DB inventory results separated from external sample-source checks?",
        "3. Are ETH sample quality gates explicit and reproducible?",
        "4. Does the report avoid claiming ETH research is ready without a full historical backfill?",
        "5. Are archive coverage risks documented before scheduling a 2022-2026 backfill?",
    ]
    report = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", default=list(SYMBOLS))
    parser.add_argument("--db-path", type=Path, default=MARKET_DB_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    payload = run_feasibility(tuple(symbol.upper() for symbol in args.symbols), args.db_path)
    print(generate_report(payload, args.report))
    print("git_commit", subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip())


if __name__ == "__main__":
    main()
