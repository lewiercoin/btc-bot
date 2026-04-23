from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage.db import connect_readonly

FEATURE_THRESHOLDS = {
    "atr_15m": 0.02,
    "atr_4h": 0.02,
    "atr_4h_norm": 0.02,
    "ema50_4h": 0.01,
    "ema200_4h": 0.01,
    "tfi_60s": 0.05,
    "force_order_rate_60s": 0.05,
    "close_vs_reclaim_buffer_atr": 0.02,
    "wick_vs_min_atr": 0.02,
    "sweep_vs_buffer_atr": 0.02,
}


@dataclass(slots=True)
class FieldComparison:
    field: str
    expected: float | bool | None
    actual: float | bool | None
    abs_diff: float | None
    rel_diff_pct: float | None
    threshold_rel_pct: float | None
    status: str


def compute_atr_reference(candles: list[dict[str, Any]], period: int) -> float:
    if len(candles) < 2:
        return 0.0
    trs: list[float] = []
    for idx in range(1, len(candles)):
        prev_close = float(candles[idx - 1]["close"])
        high = float(candles[idx]["high"])
        low = float(candles[idx]["low"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    if not trs:
        return 0.0
    window = trs[-period:] if len(trs) >= period else trs
    return sum(window) / len(window)


def compute_ema_reference(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    if period <= 1:
        return float(values[-1])
    multiplier = 2.0 / (period + 1)
    ema = float(values[0])
    for value in values[1:]:
        ema = ((float(value) - ema) * multiplier) + ema
    return ema


def detect_equal_levels_reference(levels: list[float], tolerance: float, min_hits: int = 3) -> list[float]:
    if not levels:
        return []
    sorted_levels = sorted(float(item) for item in levels)
    clusters: list[list[float]] = [[sorted_levels[0]]]
    for level in sorted_levels[1:]:
        if abs(level - clusters[-1][-1]) <= tolerance:
            clusters[-1].append(level)
        else:
            clusters.append([level])
    return [round(sum(cluster) / len(cluster), 2) for cluster in clusters if len(cluster) >= min_hits]


def recompute_distance_metrics(
    candles_15m: list[dict[str, Any]],
    atr_15m: float,
    strategy: dict[str, Any],
) -> dict[str, float | bool | None]:
    if len(candles_15m) < 2 or atr_15m <= 0:
        return {
            "sweep_detected": False,
            "reclaim_detected": False,
            "sweep_level": None,
            "sweep_depth_pct": None,
            "sweep_side": None,
            "close_vs_reclaim_buffer_atr": None,
            "wick_vs_min_atr": None,
            "sweep_vs_buffer_atr": None,
        }

    lookback = int(strategy.get("equal_level_lookback", 50))
    tol_atr = float(strategy.get("equal_level_tol_atr", 0.25))
    sweep_buf_atr = float(strategy.get("sweep_buf_atr", 0.15))
    reclaim_buf_atr = float(strategy.get("reclaim_buf_atr", 0.05))
    wick_min_atr = float(strategy.get("wick_min_atr", 0.4))

    recent = candles_15m[-lookback:] if candles_15m else []
    lows = [float(candle["low"]) for candle in recent]
    highs = [float(candle["high"]) for candle in recent]
    tolerance = atr_15m * tol_atr
    equal_lows = detect_equal_levels_reference(lows, tolerance=tolerance, min_hits=3)
    equal_highs = detect_equal_levels_reference(highs, tolerance=tolerance, min_hits=3)

    latest = candles_15m[-1]
    open_price = float(latest["open"])
    close_price = float(latest["close"])
    high_price = float(latest["high"])
    low_price = float(latest["low"])
    body_low = min(open_price, close_price)
    body_high = max(open_price, close_price)

    sweep_buffer = sweep_buf_atr * atr_15m
    reclaim_buffer = reclaim_buf_atr * atr_15m
    wick_min = wick_min_atr * atr_15m

    for level in equal_lows:
        swept = low_price < (level - sweep_buffer)
        reclaimed = close_price > (level + reclaim_buffer)
        wick_ok = (body_low - low_price) >= wick_min
        if swept:
            return {
                "sweep_detected": True,
                "reclaim_detected": bool(reclaimed and wick_ok),
                "sweep_level": float(level),
                "sweep_depth_pct": abs(level - low_price) / level if level else 0.0,
                "sweep_side": "LOW",
                "close_vs_reclaim_buffer_atr": (close_price - (level + reclaim_buffer)) / atr_15m,
                "wick_vs_min_atr": ((body_low - low_price) - wick_min) / atr_15m,
                "sweep_vs_buffer_atr": ((level - sweep_buffer) - low_price) / atr_15m,
            }

    for level in equal_highs:
        swept = high_price > (level + sweep_buffer)
        reclaimed = close_price < (level - reclaim_buffer)
        wick_ok = (high_price - body_high) >= wick_min
        if swept:
            return {
                "sweep_detected": True,
                "reclaim_detected": bool(reclaimed and wick_ok),
                "sweep_level": float(level),
                "sweep_depth_pct": abs(high_price - level) / level if level else 0.0,
                "sweep_side": "HIGH",
                "close_vs_reclaim_buffer_atr": ((level - reclaim_buffer) - close_price) / atr_15m,
                "wick_vs_min_atr": ((high_price - body_high) - wick_min) / atr_15m,
                "sweep_vs_buffer_atr": (high_price - (level + sweep_buffer)) / atr_15m,
            }

    return {
        "sweep_detected": False,
        "reclaim_detected": False,
        "sweep_level": None,
        "sweep_depth_pct": None,
        "sweep_side": None,
        "close_vs_reclaim_buffer_atr": None,
        "wick_vs_min_atr": None,
        "sweep_vs_buffer_atr": None,
    }


def compute_tfi_proxy(aggtrade_events_60s: list[dict[str, Any]], aggtrade_bucket_60s: dict[str, Any]) -> float:
    if aggtrade_events_60s:
        taker_buy = 0.0
        taker_sell = 0.0
        for event in aggtrade_events_60s:
            qty = float(event.get("qty", 0.0))
            if bool(event.get("is_buyer_maker")):
                taker_sell += qty
            else:
                taker_buy += qty
        total = taker_buy + taker_sell
        return 0.0 if total == 0 else (taker_buy - taker_sell) / total
    return float(aggtrade_bucket_60s.get("tfi", 0.0))


def compare_field(field: str, expected: Any, actual: Any) -> FieldComparison:
    threshold = FEATURE_THRESHOLDS.get(field)
    if expected is None or actual is None:
        status = "missing" if expected != actual else "ok"
        return FieldComparison(field, expected, actual, None, None, threshold, status)
    if isinstance(expected, bool) or isinstance(actual, bool):
        status = "ok" if bool(expected) == bool(actual) else "critical"
        return FieldComparison(field, bool(expected), bool(actual), None, None, threshold, status)
    expected_f = float(expected)
    actual_f = float(actual)
    abs_diff = abs(expected_f - actual_f)
    base = max(abs(actual_f), 1e-12)
    rel_diff = abs_diff / base
    if threshold is None or rel_diff <= threshold:
        status = "ok"
    elif rel_diff <= threshold * 2:
        status = "warning"
    else:
        status = "critical"
    return FieldComparison(
        field=field,
        expected=expected_f,
        actual=actual_f,
        abs_diff=abs_diff,
        rel_diff_pct=rel_diff * 100.0,
        threshold_rel_pct=threshold * 100.0 if threshold is not None else None,
        status=status,
    )


def load_snapshot_and_features(conn: sqlite3.Connection, snapshot_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot_row = conn.execute(
        "SELECT * FROM market_snapshots WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()
    if snapshot_row is None:
        raise KeyError(f"snapshot_id not found: {snapshot_id}")
    feature_row = conn.execute(
        """
        SELECT *
        FROM feature_snapshots
        WHERE snapshot_id = ?
        ORDER BY cycle_timestamp DESC
        LIMIT 1
        """,
        (snapshot_id,),
    ).fetchone()
    if feature_row is None:
        raise KeyError(f"feature snapshot not found for snapshot_id: {snapshot_id}")
    return dict(snapshot_row), dict(feature_row)


def load_strategy_config(conn: sqlite3.Connection, config_hash: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT strategy_json FROM config_snapshots WHERE config_hash = ?",
        (config_hash,),
    ).fetchone()
    if row is None or row["strategy_json"] is None:
        return {}
    return json.loads(row["strategy_json"])


def recompute_snapshot(conn: sqlite3.Connection, snapshot_id: str) -> dict[str, Any]:
    snapshot_row, feature_row = load_snapshot_and_features(conn, snapshot_id)
    feature_json = json.loads(feature_row["features_json"])
    strategy = load_strategy_config(conn, feature_row["config_hash"])

    candles_15m = json.loads(snapshot_row["candles_15m_json"])
    candles_4h = json.loads(snapshot_row["candles_4h_json"])
    aggtrade_events_60s = json.loads(snapshot_row["aggtrade_events_60s_json"])
    aggtrade_bucket_60s = json.loads(snapshot_row["aggtrade_bucket_60s_json"])
    force_orders_60s = json.loads(snapshot_row["force_order_events_60s_json"])

    atr_period = int(strategy.get("atr_period", 14))
    ema_fast = int(strategy.get("ema_fast", 50))
    ema_slow = int(strategy.get("ema_slow", 200))

    atr_15m = compute_atr_reference(candles_15m, atr_period)
    atr_4h = compute_atr_reference(candles_4h, atr_period)
    close_price = float(snapshot_row["close"])
    atr_4h_norm = 0.0 if close_price == 0 else atr_4h / close_price
    closes_4h = [float(candle["close"]) for candle in candles_4h]
    ema50_4h = compute_ema_reference(closes_4h, ema_fast)
    ema200_4h = compute_ema_reference(closes_4h, ema_slow)
    tfi_proxy = compute_tfi_proxy(aggtrade_events_60s, aggtrade_bucket_60s)
    force_order_rate_60s = len(force_orders_60s) / 60.0
    distance_metrics = recompute_distance_metrics(candles_15m, atr_15m, strategy)

    comparisons = [
        compare_field("atr_15m", atr_15m, feature_json.get("atr_15m")),
        compare_field("atr_4h", atr_4h, feature_json.get("atr_4h")),
        compare_field("atr_4h_norm", atr_4h_norm, feature_json.get("atr_4h_norm")),
        compare_field("ema50_4h", ema50_4h, feature_json.get("ema50_4h")),
        compare_field("ema200_4h", ema200_4h, feature_json.get("ema200_4h")),
        compare_field("tfi_60s", tfi_proxy, feature_json.get("tfi_60s")),
        compare_field("force_order_rate_60s", force_order_rate_60s, feature_json.get("force_order_rate_60s")),
        compare_field(
            "close_vs_reclaim_buffer_atr",
            distance_metrics["close_vs_reclaim_buffer_atr"],
            feature_json.get("close_vs_reclaim_buffer_atr"),
        ),
        compare_field(
            "wick_vs_min_atr",
            distance_metrics["wick_vs_min_atr"],
            feature_json.get("wick_vs_min_atr"),
        ),
        compare_field(
            "sweep_vs_buffer_atr",
            distance_metrics["sweep_vs_buffer_atr"],
            feature_json.get("sweep_vs_buffer_atr"),
        ),
    ]
    return {
        "snapshot_id": snapshot_id,
        "feature_snapshot_id": feature_row["feature_snapshot_id"],
        "cycle_timestamp": snapshot_row["cycle_timestamp"],
        "comparisons": [asdict(comparison) for comparison in comparisons],
    }


def summarize_recent(conn: sqlite3.Connection, limit: int = 200) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT snapshot_id
        FROM feature_snapshots
        ORDER BY cycle_timestamp DESC
        LIMIT ?
        """,
        (max(int(limit), 1),),
    ).fetchall()
    snapshot_ids = [row["snapshot_id"] for row in rows]
    reports = [recompute_snapshot(conn, snapshot_id) for snapshot_id in snapshot_ids]
    fields: dict[str, list[dict[str, Any]]] = {}
    for report in reports:
        for comparison in report["comparisons"]:
            fields.setdefault(comparison["field"], []).append(comparison)

    summary: dict[str, Any] = {"sample_size": len(reports), "fields": {}}
    for field, comparisons in fields.items():
        numeric = [item for item in comparisons if item["abs_diff"] is not None]
        if not numeric:
            continue
        summary["fields"][field] = {
            "avg_abs_diff": sum(item["abs_diff"] for item in numeric) / len(numeric),
            "max_abs_diff": max(item["abs_diff"] for item in numeric),
            "avg_rel_diff_pct": sum(item["rel_diff_pct"] for item in numeric if item["rel_diff_pct"] is not None) / len(numeric),
            "over_threshold_pct": (
                sum(
                    1
                    for item in numeric
                    if item["threshold_rel_pct"] is not None
                    and item["rel_diff_pct"] is not None
                    and item["rel_diff_pct"] > item["threshold_rel_pct"]
                )
                / len(numeric)
            )
            * 100.0,
            "status": _field_status(numeric),
        }
    return summary


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Feature Drift Report",
        "",
        f"- Sample size: {summary['sample_size']}",
        "- Thresholds:",
        "  - ATR fields: 2.0%",
        "  - EMA fields: 1.0%",
        "  - TFI / force-order rate / distance diagnostics: 5.0% or tighter where defined",
        "",
        "| Field | Avg abs diff | Max abs diff | Avg rel diff % | Over threshold % | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for field, metrics in sorted(summary["fields"].items()):
        lines.append(
            f"| {field} | {metrics['avg_abs_diff']:.8f} | {metrics['max_abs_diff']:.8f} | "
            f"{metrics['avg_rel_diff_pct']:.4f} | {metrics['over_threshold_pct']:.2f} | {metrics['status'].upper()} |"
        )
    return "\n".join(lines) + "\n"


def _field_status(comparisons: list[dict[str, Any]]) -> str:
    if any(item["status"] == "critical" for item in comparisons):
        return "critical"
    if any(item["status"] == "warning" for item in comparisons):
        return "warning"
    return "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute persisted feature snapshots from raw market truth.")
    parser.add_argument("--db", default="storage/btc_bot.db", help="SQLite database path")
    parser.add_argument("--snapshot-id", help="Single snapshot_id to recompute")
    parser.add_argument("--limit", type=int, default=200, help="Recent sample size for summary mode")
    parser.add_argument("--markdown-out", help="Optional markdown output path")
    args = parser.parse_args()

    conn = connect_readonly(Path(args.db))
    try:
        if args.snapshot_id:
            payload = recompute_snapshot(conn, args.snapshot_id)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0

        summary = summarize_recent(conn, limit=args.limit)
        markdown = render_markdown(summary)
        if args.markdown_out:
            Path(args.markdown_out).write_text(markdown, encoding="utf-8")
        print(markdown)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
