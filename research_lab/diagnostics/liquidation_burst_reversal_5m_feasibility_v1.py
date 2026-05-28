"""Research-only 5m liquidation burst reversal timeframe diagnostic.

This is a timeframe accessibility check for the audited 15m liquidation burst
diagnostic. The mechanism and bar-unit timing are unchanged:

    detection_bar = i
    state_known_bar = i+2
    entry_candidate_bar = i+3
    return_start_bar = i+3

Only the candle timeframe changes from 15m to 5m, reducing real-time entry
delay from 45 minutes to 15 minutes. The 15m STOP verdict remains final.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from research_lab.diagnostics.liquidation_burst_reversal_entry_feasibility_v1 import (
    Candle,
    DiagnosticConfig,
    apply_gates,
    build_flow_only_control,
    build_sweep_cohorts,
    compute_atr_series,
    data_quality,
    detect_sweep_events,
    event_overlap_with_trade_log,
    fmt_float,
    inspect_schema,
    iso,
    load_force_buckets,
    load_trial_00095_benchmark,
    metric_summary,
    parse_ts,
    serialize_events,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "research_lab" / "data" / "crowded_unwind_backtest.db"
DEFAULT_5M_CACHE_PATH = PROJECT_ROOT / "research_lab" / "data" / "btcusdt_5m_klines_20220101_20241201.db"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "research_lab" / "reports" / "liquidation_burst_reversal_5m_feasibility_v1.md"
DEFAULT_JSON_PATH = PROJECT_ROOT / "research_lab" / "reports" / "liquidation_burst_reversal_5m_feasibility_v1.json"

FORCE_ORDER_START = datetime(2022, 1, 1, tzinfo=timezone.utc)
FORCE_ORDER_END = datetime(2024, 12, 1, 23, 55, tzinfo=timezone.utc)
BINANCE_FAPI_KLINES = "https://fapi.binance.com/fapi/v1/klines"

FIFTEEN_MIN_REFERENCE = {
    "entry_delay_minutes": 45,
    "main_events": 5412,
    "main_er": -0.100795,
    "main_profit_factor": 0.583975,
    "main_win_rate": 0.408906,
    "median_mfe_consumed_pct": 1.0,
    "control_outperformers": 3,
    "recommendation": "STOP",
    "status": "final_audited_reference",
}


def five_min_config() -> DiagnosticConfig:
    return DiagnosticConfig(
        timeframe="5m",
        max_serialized_events_per_cohort=200,
    )


def ms(dt: datetime) -> int:
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def dt_from_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def fetch_binance_5m_klines(
    *,
    symbol: str,
    start: datetime,
    end: datetime,
    sleep_seconds: float = 0.02,
) -> list[Candle]:
    """Fetch exact Binance USD-M 5m klines for the force-order overlap window."""
    candles: list[Candle] = []
    current_ms = ms(start)
    end_ms = ms(end)
    while current_ms <= end_ms:
        params = urllib.parse.urlencode(
            {
                "symbol": symbol,
                "interval": "5m",
                "startTime": current_ms,
                "endTime": end_ms,
                "limit": 1500,
            }
        )
        with urllib.request.urlopen(f"{BINANCE_FAPI_KLINES}?{params}", timeout=30) as response:
            rows = json.loads(response.read().decode("utf-8"))
        if not isinstance(rows, list):
            raise RuntimeError(f"Unexpected Binance response: {rows!r}")
        if not rows:
            break
        for row in rows:
            open_time = dt_from_ms(int(row[0]))
            if open_time > end:
                continue
            candles.append(
                Candle(
                    index=len(candles),
                    open_time=open_time,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        next_ms = int(rows[-1][0]) + 5 * 60 * 1000
        if next_ms <= current_ms:
            break
        current_ms = next_ms
        time.sleep(sleep_seconds)
    return candles


def save_5m_cache(path: Path, candles: list[Candle], *, source: str, symbol: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE IF EXISTS candles")
        conn.execute("DROP TABLE IF EXISTS source_metadata")
        conn.execute(
            """
            CREATE TABLE candles (
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                open_time TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                UNIQUE(symbol, timeframe, open_time)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE source_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO candles (symbol, timeframe, open_time, open, high, low, close, volume)
            VALUES (?, '5m', ?, ?, ?, ?, ?, ?)
            """,
            [
                (symbol, iso(c.open_time), c.open, c.high, c.low, c.close, c.volume)
                for c in candles
            ],
        )
        metadata = {
            "source": source,
            "symbol": symbol,
            "timeframe": "5m",
            "rows": str(len(candles)),
            "start_time_utc": iso(candles[0].open_time) if candles else "",
            "end_time_utc": iso(candles[-1].open_time) if candles else "",
            "created_at_utc": iso(datetime.now(timezone.utc)),
        }
        conn.executemany("INSERT INTO source_metadata VALUES (?, ?)", metadata.items())


def load_5m_cache(path: Path, *, symbol: str) -> tuple[list[Candle], dict[str, Any]]:
    if not path.exists():
        return [], {"source": "missing_cache", "path": str(path)}
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            """
            SELECT open_time, open, high, low, close, volume
            FROM candles
            WHERE symbol = ? AND timeframe = '5m'
            ORDER BY open_time ASC
            """,
            (symbol,),
        ).fetchall()
        metadata = {
            row[0]: row[1]
            for row in conn.execute("SELECT key, value FROM source_metadata").fetchall()
        }
    candles = [
        Candle(
            index=idx,
            open_time=parse_ts(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5] or 0.0),
        )
        for idx, row in enumerate(rows)
    ]
    metadata["path"] = str(path)
    return candles, metadata


def interpolate_5m_from_15m(conn: sqlite3.Connection, config: DiagnosticConfig) -> list[Candle]:
    """Fallback approximation only when exact Binance 5m klines are unavailable."""
    rows = conn.execute(
        """
        SELECT open_time, open, high, low, close, volume
        FROM candles
        WHERE symbol = ? AND timeframe = '15m'
          AND open_time >= ? AND open_time <= ?
        ORDER BY open_time ASC
        """,
        (config.symbol, iso(FORCE_ORDER_START), iso(FORCE_ORDER_END)),
    ).fetchall()
    candles: list[Candle] = []
    for row in rows:
        start = parse_ts(row[0])
        open_price = float(row[1])
        high = float(row[2])
        low = float(row[3])
        close = float(row[4])
        volume = float(row[5] or 0.0) / 3.0
        mid1 = open_price + (close - open_price) / 3.0
        mid2 = open_price + 2.0 * (close - open_price) / 3.0
        parts = [
            (open_price, max(open_price, mid1, high), min(open_price, mid1, low), mid1),
            (mid1, max(mid1, mid2), min(mid1, mid2), mid2),
            (mid2, max(mid2, close), min(mid2, close), close),
        ]
        for offset, (o, h, l, c) in enumerate(parts):
            candles.append(
                Candle(
                    index=len(candles),
                    open_time=start + timedelta(minutes=5 * offset),
                    open=o,
                    high=h,
                    low=l,
                    close=c,
                    volume=volume,
                )
            )
    return candles


def get_5m_candles(
    conn: sqlite3.Connection,
    *,
    cache_path: Path,
    config: DiagnosticConfig,
    allow_fetch: bool,
) -> tuple[list[Candle], dict[str, Any]]:
    candles, metadata = load_5m_cache(cache_path, symbol=config.symbol)
    quality = data_quality(candles)
    if candles and quality["missing_bar_gaps"] == 0:
        return candles, {**metadata, "method": "cache"}

    if allow_fetch:
        try:
            fetched = fetch_binance_5m_klines(
                symbol=config.symbol,
                start=FORCE_ORDER_START,
                end=FORCE_ORDER_END,
            )
            if fetched:
                save_5m_cache(cache_path, fetched, source="binance_fapi_klines_rest", symbol=config.symbol)
                candles, metadata = load_5m_cache(cache_path, symbol=config.symbol)
                return candles, {**metadata, "method": "binance_fapi_fetch"}
        except Exception as exc:
            fallback = interpolate_5m_from_15m(conn, config)
            return fallback, {
                "method": "15m_interpolation_fallback",
                "source": "local_15m_candles",
                "fetch_error": str(exc),
                "limitation": "approximate_5m_ohlcv_not_exact",
            }

    fallback = interpolate_5m_from_15m(conn, config)
    return fallback, {
        "method": "15m_interpolation_fallback",
        "source": "local_15m_candles",
        "limitation": "approximate_5m_ohlcv_not_exact",
    }


def run_5m_diagnostic(
    *,
    db_path: Path,
    cache_path: Path,
    report_path: Path,
    json_path: Path,
    config: DiagnosticConfig,
    allow_fetch: bool = True,
) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    schema = inspect_schema(conn)
    if schema["missing_required"]:
        raise RuntimeError(f"Required schema missing: {schema['missing_required']}")

    candles, candle_source = get_5m_candles(
        conn,
        cache_path=cache_path,
        config=config,
        allow_fetch=allow_fetch,
    )
    candle_quality = data_quality(candles)
    buckets, force_quality = load_force_buckets(conn, candles, config)
    atr = compute_atr_series(candles, config.atr_period)
    sweeps = detect_sweep_events(candles, atr, config)
    cohorts = build_sweep_cohorts(candles, sweeps, buckets, config)
    cohorts["control_flow_only_ablation"] = build_flow_only_control(candles, buckets, config)
    metrics = {name: metric_summary(events) for name, events in cohorts.items()}
    gates = apply_gates(metrics)
    benchmark = load_trial_00095_benchmark()
    benchmark["trade_log_overlap"] = event_overlap_with_trade_log(
        conn,
        cohorts["main_liquidation_burst_reversal"],
    )
    conn.close()

    comparison = build_15m_5m_comparison(metrics, gates)
    payload = {
        "manifest": {
            "diagnostic": "LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1",
            "research_only": True,
            "production_changes": False,
            "db_path": str(db_path),
            "cache_path": str(cache_path),
            "report_path": str(report_path),
            "json_path": str(json_path),
            "generated_at_utc": iso(datetime.now(timezone.utc)),
        },
        "config": asdict(config),
        "schema": schema,
        "data_quality": {
            "candles_5m": candle_quality,
            "candle_source": candle_source,
            "force_orders": force_quality,
        },
        "timing_model": {
            "detection_bar": "i",
            "state_known_bar": "i+2",
            "confirmation_bar": "i+2",
            "entry_candidate_bar": "i+3",
            "label_available_bar": "i+3",
            "return_start_bar": "i+3",
            "primary_returns_from_detection_bar": False,
            "entry_delay_minutes": 15,
        },
        "sweep_events_total": len(sweeps),
        "cohort_metrics": metrics,
        "fifteen_min_reference": FIFTEEN_MIN_REFERENCE,
        "comparison_15m_vs_5m": comparison,
        "benchmark_comparison": benchmark,
        "invalidation_gates": gates,
        "events_sample": {
            name: serialize_events(events, config.max_serialized_events_per_cohort)
            for name, events in cohorts.items()
        },
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    sha = hashlib.sha256(json_path.read_bytes()).hexdigest().upper()
    payload["manifest"]["json_sha256"] = sha

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_5m_report(payload), encoding="utf-8")
    return payload


def build_15m_5m_comparison(
    metrics: dict[str, dict[str, Any]],
    gates: dict[str, Any],
) -> dict[str, Any]:
    main = metrics["main_liquidation_burst_reversal"]
    control_count = len(gates["control_outperformers"])
    return {
        "entry_delay_minutes": {"15m": 45, "5m": 15},
        "main_events": {"15m": FIFTEEN_MIN_REFERENCE["main_events"], "5m": main["count"]},
        "main_er": {"15m": FIFTEEN_MIN_REFERENCE["main_er"], "5m": main["er"]},
        "main_profit_factor": {"15m": FIFTEEN_MIN_REFERENCE["main_profit_factor"], "5m": main["profit_factor"]},
        "main_win_rate": {"15m": FIFTEEN_MIN_REFERENCE["main_win_rate"], "5m": main["win_rate"]},
        "median_mfe_consumed_pct": {
            "15m": FIFTEEN_MIN_REFERENCE["median_mfe_consumed_pct"],
            "5m": main["median_mfe_consumed_pct"],
        },
        "control_outperformers": {"15m": FIFTEEN_MIN_REFERENCE["control_outperformers"], "5m": control_count},
        "recommendation": {"15m": FIFTEEN_MIN_REFERENCE["recommendation"], "5m": gates["recommendation"]},
        "interpretation": (
            "mechanism_fully_invalidated_on_5m"
            if gates["recommendation"] == "STOP"
            else "timeframe_accessibility_not_stopped"
        ),
    }


def render_5m_report(payload: dict[str, Any]) -> str:
    recommendation = payload["invalidation_gates"]["recommendation"]
    metrics = payload["cohort_metrics"]
    main = metrics["main_liquidation_burst_reversal"]
    comparison = payload["comparison_15m_vs_5m"]
    lines = [
        "# LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1",
        "",
        "## Executive Summary",
        "",
        f"Recommendation: **{recommendation}**",
        "",
        "This is a research-only timeframe accessibility check. The 15m STOP verdict remains final and is used only as an audited reference.",
        "",
        f"- Main cohort events: `{main['count']}`",
        f"- Main post-entry ER proxy: `{fmt_float(main['er'])}`",
        f"- Main profit factor proxy: `{fmt_float(main['profit_factor'])}`",
        f"- Main win rate: `{fmt_float(main['win_rate'])}`",
        f"- Main median MFE consumed before entry: `{fmt_float(main['median_mfe_consumed_pct'])}`",
        f"- STOP reasons: `{', '.join(payload['invalidation_gates']['stop_reasons']) or 'none'}`",
        "- Interpretation: `mechanism invalidated on both 15m and 5m; close liquidation burst reversal family`"
        if recommendation == "STOP"
        else "- Interpretation: `5m did not trigger STOP`",
        "",
        "## Mechanism",
        "",
        "- Mechanism is unchanged from the audited 15m diagnostic.",
        "- Detect an equal-level sweep at bar `i` using completed 5m candles only.",
        "- Sum expected-side force-order notional across bars `i` through `i+2`.",
        "- Compare that notional to a pre-sweep rolling baseline ending at `i-1`.",
        "- Enter at bar `i+3`; primary returns start at `i+3`.",
        "",
        "## 5m Candle Source And Quality",
        "",
        f"- Source: `{payload['data_quality']['candle_source']}`",
        f"- Candles: `{payload['data_quality']['candles_5m']}`",
        f"- Force orders: `{payload['data_quality']['force_orders']}`",
        "",
        "## Timing Model Verification",
        "",
        "| Bar | Value |",
        "| --- | --- |",
    ]
    for key, value in payload["timing_model"].items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "Primary returns are measured from `entry_candidate_bar`, not `detection_bar`. Detection-bar movement is used only for MFE-before-entry accessibility.",
            "",
            "## Cohort Metrics",
            "",
            "| Cohort | Count | ER | Median R | PF | Win Rate | Median MFE Consumed | Positive Folds |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, row in metrics.items():
        lines.append(
            f"| `{name}` | {row['count']} | {fmt_float(row['er'])} | {fmt_float(row['median_r'])} | "
            f"{fmt_float(row['profit_factor'])} | {fmt_float(row['win_rate'])} | "
            f"{fmt_float(row['median_mfe_consumed_pct'])} | {row['positive_folds']} |"
        )
    lines.extend(
        [
            "",
            "## 15m vs 5m Comparison",
            "",
            "| Metric | 15m result | 5m result |",
            "| --- | ---: | ---: |",
            f"| Entry delay | {comparison['entry_delay_minutes']['15m']} min | {comparison['entry_delay_minutes']['5m']} min |",
            f"| Main events | {comparison['main_events']['15m']} | {comparison['main_events']['5m']} |",
            f"| Main ER | {fmt_float(comparison['main_er']['15m'])} | {fmt_float(comparison['main_er']['5m'])} |",
            f"| Main PF | {fmt_float(comparison['main_profit_factor']['15m'])} | {fmt_float(comparison['main_profit_factor']['5m'])} |",
            f"| Main win rate | {fmt_float(comparison['main_win_rate']['15m'])} | {fmt_float(comparison['main_win_rate']['5m'])} |",
            f"| Median MFE consumed | {fmt_float(comparison['median_mfe_consumed_pct']['15m'])} | {fmt_float(comparison['median_mfe_consumed_pct']['5m'])} |",
            f"| Control outperformers | {comparison['control_outperformers']['15m']} | {comparison['control_outperformers']['5m']} |",
            f"| Invalidation gate | {comparison['recommendation']['15m']} | {comparison['recommendation']['5m']} |",
            "",
            "## MFE Accessibility",
            "",
            f"- Main median MFE before entry: `{fmt_float(main['median_mfe_before_entry'])}`",
            f"- Main median MFE after entry: `{fmt_float(main['median_mfe_after_entry'])}`",
            f"- Main median MAE after entry: `{fmt_float(main['median_mae_after_entry'])}`",
            f"- 70% consumed threshold breached: `{main['median_mfe_consumed_pct'] is not None and main['median_mfe_consumed_pct'] > 0.70}`",
            "",
            "## Control Cohorts",
            "",
            "- Non-liquidation sweeps: sweep detected, expected-side liquidation below 0.5x baseline.",
            "- Opposite-side liquidations: sweep detected, wrong-side liquidation burst.",
            "- Shifted-entry: same main signal, but entry delayed from `i+3` to `i+5`.",
            "- Flow-only ablation: liquidation burst without sweep requirement.",
            "",
            f"Control outperformers: `{payload['invalidation_gates']['control_outperformers']}`",
            "",
            "## Trial-00095 Benchmark Comparison",
            "",
            f"- Reference benchmark: `{payload['benchmark_comparison']['reference']}`",
            f"- Exact `trial_trades` available: `{payload['benchmark_comparison']['exact_trial_trades_available']}`",
            f"- Trade-log overlap: `{payload['benchmark_comparison']['trade_log_overlap']}`",
            "",
            "## Invalidation Criteria Evaluation",
            "",
            f"- Recommendation: `{recommendation}`",
            f"- STOP reasons: `{payload['invalidation_gates']['stop_reasons']}`",
            f"- EXPLORE gate passed: `{payload['invalidation_gates']['explore_gate_passed']}`",
            "",
            "## Artifact",
            "",
            f"- JSON path: `{payload['manifest']['json_path']}`",
            f"- JSON SHA256: `{payload['manifest']['json_sha256']}`",
            "",
            f"## Recommendation: {recommendation}",
            "",
            f"**Reason:** {'; '.join(payload['invalidation_gates']['stop_reasons']) if recommendation == 'STOP' else 'Gate evaluation did not trigger STOP and determines the next research status.'}",
            "",
            "**Family status:** Close this liquidation burst reversal direction if this STOP result is accepted by audit."
            if recommendation == "STOP"
            else "**Family status:** Await audit before any follow-up decision.",
            "",
            "**Next:** Claude Code audits this 5m diagnostic implementation and result before any follow-up work.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_5M_CACHE_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--no-fetch", action="store_true", help="Use cache or interpolation fallback only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_5m_diagnostic(
        db_path=args.db_path,
        cache_path=args.cache_path,
        report_path=args.report_path,
        json_path=args.json_path,
        config=five_min_config(),
        allow_fetch=not args.no_fetch,
    )
    print(json.dumps(payload["invalidation_gates"], indent=2, sort_keys=True))
    print(f"report={args.report_path}")
    print(f"json={args.json_path}")


if __name__ == "__main__":
    main()
