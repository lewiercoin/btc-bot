"""
event_study_v1.py — Raw sweep+reclaim event study over full historical dataset.

Deliverable D2 of SIGNAL-ANALYSIS-V1 milestone.

What it does:
  1. Runs feature engine on full dataset 2022-01-01 -> 2026-03-01 using exact
     default parameters specified in the SIGNAL-ANALYSIS-V1 handoff.
     No confluence, no governance, no risk gates, no execution filters.
  2. Identifies all bars where sweep_detected=True AND reclaim_confirmed=True.
  3. Applies fixed exit model (uniform across all events):
       Stop loss:   1.0 x ATR (at event bar)
       Take profit: 2.0 x ATR (at event bar)
       Max hold:    16 bars (4h at 15m TF)
  4. Computes per-event: side, level_type, proximity_atr, level_age_bars, hit_count,
     ATR-normalised forward returns (bar+1/4/16/96), MFE, MAE, fixed-exit outcome.
  5. Decomposes by 6 regime segments and proximity/structure buckets.
  6. Per bucket/segment: n_events, mean/median fwd return, hit_rate, t-stat, p-value.
     Buckets with n < 30 are marked INSUFFICIENT_SAMPLE.

Usage:
    python -m research_lab.diagnostics.event_study_v1
    python -m research_lab.diagnostics.event_study_v1 --db-path storage/btc_bot.db
    python -m research_lab.diagnostics.event_study_v1 --output research_lab/runs/event_study_v1.json
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backtest.replay_loader import ReplayLoader, ReplayLoaderConfig
from core.feature_engine import FeatureEngine, FeatureEngineConfig

_STUDY_START = "2022-01-01"
_STUDY_END = "2026-03-01"
_SYMBOL = "BTCUSDT"
_MIN_SAMPLE = 30

# Authoritative default parameters — do NOT infer from code, override if needed.
_FEATURE_CONFIG = FeatureEngineConfig(
    sweep_proximity_atr=0.4,
    level_min_age_bars=5,
    min_hits=3,
    equal_level_lookback=50,
    equal_level_tol_atr=0.25,
    wick_min_atr=0.3,
)

# Fixed exit model constants
_SL_ATR_MULT = 1.0
_TP_ATR_MULT = 2.0
_MAX_HOLD_BARS = 16

# Regime segments
_SEGMENTS: dict[str, tuple[str, str, str]] = {
    "S1": ("2022-01-01", "2022-06-30", "bear collapse"),
    "S2": ("2022-07-01", "2023-03-31", "bear range / bottoming"),
    "S3": ("2023-04-01", "2024-01-31", "recovery / pre-ETF"),
    "S4": ("2024-02-01", "2024-09-30", "ETF launch / halving"),
    "S5": ("2024-10-01", "2025-06-30", "rally to ATH / distribution"),
    "S6": ("2025-07-01", "2026-03-01", "recent regime"),
}

# Precompute segment boundaries as UTC datetime for fast lookup
_SEG_BOUNDS: list[tuple[str, datetime, datetime]] = []
for _seg_id, (_s, _e, _desc) in _SEGMENTS.items():
    _SEG_BOUNDS.append((
        _seg_id,
        datetime.fromisoformat(_s).replace(tzinfo=timezone.utc),
        datetime.fromisoformat(_e + "T23:59:59").replace(tzinfo=timezone.utc),
    ))


def _segment_for_ts(ts: datetime) -> str | None:
    for seg_id, seg_start, seg_end in _SEG_BOUNDS:
        if seg_start <= ts <= seg_end:
            return seg_id
    return None


def _proximity_bucket(proximity_atr: float) -> str:
    if proximity_atr <= 0.4:
        return "P1"
    if proximity_atr <= 0.8:
        return "P2"
    if proximity_atr <= 1.2:
        return "P3"
    return "P4"


def _structure_bucket(level_age_bars: int, hit_count: int) -> str:
    if level_age_bars >= _FEATURE_CONFIG.level_min_age_bars and hit_count >= _FEATURE_CONFIG.min_hits:
        return "MATURE"
    return "IMMATURE"


def _cluster_metadata_for_level(
    candles_lookback: list[dict[str, Any]],
    level_price: float,
    sweep_side: str,
    tolerance: float,
    min_hits: int,
    lookback: int,
) -> tuple[int, int]:
    """Return (hit_count, age_bars) for the cluster that produced level_price.

    Mirrors the clustering logic in detect_equal_levels but preserves per-cluster
    metadata that the merged output discards.
    """
    recent = candles_lookback[-lookback:] if len(candles_lookback) > lookback else candles_lookback
    if not recent:
        return 0, 0

    if sweep_side == "LOW":
        points = [(i, float(c["low"])) for i, c in enumerate(recent)]
    else:
        points = [(i, float(c["high"])) for i, c in enumerate(recent)]

    sorted_pts = sorted(points, key=lambda x: x[1])
    clusters: list[list[tuple[int, float]]] = []
    current: list[tuple[int, float]] = [sorted_pts[0]]
    for item in sorted_pts[1:]:
        if abs(item[1] - current[-1][1]) <= tolerance:
            current.append(item)
        else:
            clusters.append(current)
            current = [item]
    clusters.append(current)

    best_cluster: list[tuple[int, float]] | None = None
    best_dist = float("inf")
    for cluster in clusters:
        if len(cluster) < min_hits:
            continue
        cluster_mean = sum(p for _, p in cluster) / len(cluster)
        dist = abs(cluster_mean - level_price)
        if dist < best_dist:
            best_dist = dist
            best_cluster = cluster

    if best_cluster is None:
        return 0, 0

    indices = [idx for idx, _ in best_cluster]
    age_bars = max(indices) - min(indices)
    return len(best_cluster), age_bars


def _normal_sf(z: float) -> float:
    """Survival function of standard normal (1 - CDF(z))."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _t_test_1samp(values: list[float]) -> tuple[float, float]:
    """Two-tailed one-sample t-test against null mean=0. Returns (t_stat, p_value)."""
    n = len(values)
    if n < 2:
        return float("nan"), float("nan")
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    std = math.sqrt(max(var, 0.0))
    if std == 0.0:
        if mean == 0.0:
            return float("nan"), float("nan")
        return float("inf"), 0.0
    t = mean / (std / math.sqrt(n))
    p = 2.0 * _normal_sf(abs(t))
    return t, p


def _median(values: list[float]) -> float:
    if not values:
        return float("nan")
    sorted_v = sorted(values)
    n = len(sorted_v)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_v[mid - 1] + sorted_v[mid]) / 2.0
    return sorted_v[mid]


def _compute_fixed_exit(
    bar_idx: int,
    all_bars: list[tuple[float, float, float, float]],
    close: float,
    atr: float,
    side: str,
) -> tuple[float, float, str]:
    """Apply fixed exit model. Returns (mfe_atr, mae_atr, outcome).

    mfe_atr and mae_atr are ATR-normalised. mae_atr is negative = adverse.
    Outcome: 'WIN' | 'LOSS' | 'TIMEOUT'
    """
    if atr <= 0:
        return 0.0, 0.0, "TIMEOUT"

    sl_dist = _SL_ATR_MULT * atr
    tp_dist = _TP_ATR_MULT * atr

    if side == "LONG":
        sl = close - sl_dist
        tp = close + tp_dist
    else:
        sl = close + sl_dist
        tp = close - tp_dist

    mfe = 0.0
    mae = 0.0
    outcome = "TIMEOUT"

    for k in range(1, _MAX_HOLD_BARS + 1):
        future_idx = bar_idx + k
        if future_idx >= len(all_bars):
            break
        _, fh, fl, _ = all_bars[future_idx]

        if side == "LONG":
            favorable = (fh - close) / atr
            adverse = (fl - close) / atr
            mfe = max(mfe, favorable)
            mae = min(mae, adverse)
            if fl <= sl:
                outcome = "LOSS"
                break
            if fh >= tp:
                outcome = "WIN"
                break
        else:
            favorable = (close - fl) / atr
            adverse = (close - fh) / atr
            mfe = max(mfe, favorable)
            mae = min(mae, adverse)
            if fh >= sl:
                outcome = "LOSS"
                break
            if fl <= tp:
                outcome = "WIN"
                break

    return mfe, mae, outcome


def _bucket_stats(events_in_bucket: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregated stats for a bucket. Returns INSUFFICIENT_SAMPLE if n < 30."""
    n = len(events_in_bucket)
    if n < _MIN_SAMPLE:
        return {"status": "INSUFFICIENT_SAMPLE", "n_events": n}

    fwd4 = [e["fwd_ret_bar4"] for e in events_in_bucket if e.get("fwd_ret_bar4") is not None]
    wins = sum(1 for e in events_in_bucket if e.get("fixed_exit_outcome") == "WIN")

    t_stat, p_value = _t_test_1samp(fwd4)

    return {
        "status": "OK",
        "n_events": n,
        "mean_forward_return_bar4": sum(fwd4) / len(fwd4) if fwd4 else float("nan"),
        "median_forward_return_bar4": _median(fwd4),
        "hit_rate": wins / n,
        "t_statistic": t_stat,
        "p_value": p_value,
        "n_fwd4_observations": len(fwd4),
    }


def _fwd_ret(bar_idx: int, k: int, all_bars: list[tuple[float, float, float, float]], close: float, atr: float, side: str) -> float | None:
    future_idx = bar_idx + k
    if future_idx >= len(all_bars) or atr <= 0:
        return None
    future_close = all_bars[future_idx][0]
    if side == "LONG":
        return (future_close - close) / atr
    return (close - future_close) / atr


def run_event_study(db_path: Path, output_path: Path) -> dict[str, Any]:
    """Run the full event study and return the results dict."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    loader = ReplayLoader(
        conn,
        ReplayLoaderConfig(
            candles_15m_lookback=300,
            candles_1h_lookback=100,
            candles_4h_lookback=100,
            funding_lookback=100,
        ),
    )
    engine = FeatureEngine(_FEATURE_CONFIG)

    # Pass 1: collect compact bar data and detect events
    # all_bars[i] = (close, high, low, atr_15m)
    all_bars: list[tuple[float, float, float, float]] = []
    events: list[dict[str, Any]] = []

    tolerance_abs: float = 0.0  # computed per bar from ATR

    print(f"[event_study_v1] Loading snapshots {_STUDY_START} -> {_STUDY_END} ...")
    bar_count = 0

    for snapshot in loader.iter_snapshots(
        start_date=_STUDY_START,
        end_date=_STUDY_END,
        symbol=_SYMBOL,
    ):
        features = engine.compute(snapshot, "v1.0", "event_study_v1")

        latest_15m = snapshot.candles_15m[-1] if snapshot.candles_15m else None
        close = float(latest_15m["close"]) if latest_15m else snapshot.price
        high = float(latest_15m["high"]) if latest_15m else snapshot.price
        low = float(latest_15m["low"]) if latest_15m else snapshot.price
        open_price = float(latest_15m["open"]) if latest_15m else snapshot.price

        atr = features.atr_15m
        bar_idx = len(all_bars)
        all_bars.append((close, high, low, atr))
        bar_count += 1

        if not (features.sweep_detected and features.reclaim_detected):
            continue
        if features.sweep_level is None or features.sweep_side is None:
            continue

        level_price = float(features.sweep_level)
        sweep_side = features.sweep_side  # "LOW" or "HIGH"
        side = "LONG" if sweep_side == "LOW" else "SHORT"

        proximity_atr = abs(open_price - level_price) / atr if atr > 0 else 0.0

        tolerance_abs = atr * _FEATURE_CONFIG.equal_level_tol_atr if atr > 0 else 0.0
        hit_count, level_age_bars = _cluster_metadata_for_level(
            candles_lookback=snapshot.candles_15m,
            level_price=level_price,
            sweep_side=sweep_side,
            tolerance=tolerance_abs,
            min_hits=_FEATURE_CONFIG.min_hits,
            lookback=_FEATURE_CONFIG.equal_level_lookback,
        )

        ts_utc = snapshot.timestamp.astimezone(timezone.utc)
        segment = _segment_for_ts(ts_utc)

        events.append({
            "bar_idx": bar_idx,
            "timestamp": ts_utc.isoformat(),
            "segment": segment,
            "side": side,
            "level_type": sweep_side,
            "level_price": level_price,
            "proximity_atr": round(proximity_atr, 4),
            "level_age_bars": level_age_bars,
            "hit_count": hit_count,
            "sweep_depth_pct": round(features.sweep_depth_pct or 0.0, 6),
            "atr_at_event": round(atr, 4),
            "proximity_bucket": _proximity_bucket(proximity_atr),
            "structure_bucket": _structure_bucket(level_age_bars, hit_count),
        })

    print(f"[event_study_v1] Processed {bar_count} bars, found {len(events)} events.")
    print("[event_study_v1] Computing forward returns and exit model ...")

    # Pass 2: forward returns and fixed exit
    for event in events:
        bar_idx = event["bar_idx"]
        close, _, _, atr = all_bars[bar_idx]
        side = event["side"]

        for k in [1, 4, 16, 96]:
            ret = _fwd_ret(bar_idx, k, all_bars, close, atr, side)
            event[f"fwd_ret_bar{k}"] = round(ret, 6) if ret is not None else None

        mfe, mae, outcome = _compute_fixed_exit(bar_idx, all_bars, close, atr, side)
        event["mfe_atr"] = round(mfe, 4)
        event["mae_atr"] = round(mae, 4)
        event["fixed_exit_outcome"] = outcome

    # Aggregate by segment x proximity_bucket x structure_bucket
    by_segment: dict[str, Any] = {}
    for seg_id, (seg_start, seg_end, seg_desc) in _SEGMENTS.items():
        seg_events = [e for e in events if e.get("segment") == seg_id]
        by_bucket: dict[str, Any] = {}
        for prox in ["P1", "P2", "P3", "P4"]:
            for struct in ["MATURE", "IMMATURE"]:
                bucket_key = f"{prox}_{struct}"
                bucket_events = [
                    e for e in seg_events
                    if e["proximity_bucket"] == prox and e["structure_bucket"] == struct
                ]
                by_bucket[bucket_key] = _bucket_stats(bucket_events)
        by_segment[seg_id] = {
            "description": seg_desc,
            "date_range": f"{seg_start} to {seg_end}",
            "total_events": len(seg_events),
            "by_bucket": by_bucket,
        }

    # Cross-segment summary for P1+MATURE (the primary decision bucket)
    p1_mature_summary: dict[str, Any] = {}
    edge_count = 0
    for seg_id in _SEGMENTS:
        stats = by_segment[seg_id]["by_bucket"].get("P1_MATURE", {})
        p1_mature_summary[seg_id] = stats
        if (
            stats.get("status") == "OK"
            and stats.get("mean_forward_return_bar4", float("nan")) > 0
            and stats.get("p_value", 1.0) < 0.10
            and stats.get("n_events", 0) >= _MIN_SAMPLE
        ):
            edge_count += 1

    results: dict[str, Any] = {
        "meta": {
            "study_start": _STUDY_START,
            "study_end": _STUDY_END,
            "symbol": _SYMBOL,
            "feature_config": {
                "sweep_proximity_atr": _FEATURE_CONFIG.sweep_proximity_atr,
                "level_min_age_bars": _FEATURE_CONFIG.level_min_age_bars,
                "min_hits": _FEATURE_CONFIG.min_hits,
                "equal_level_lookback": _FEATURE_CONFIG.equal_level_lookback,
                "equal_level_tol_atr": _FEATURE_CONFIG.equal_level_tol_atr,
                "wick_min_atr": _FEATURE_CONFIG.wick_min_atr,
                "min_sweep_depth_pct": 0.0,
            },
            "fixed_exit": {
                "sl_atr_mult": _SL_ATR_MULT,
                "tp_atr_mult": _TP_ATR_MULT,
                "max_hold_bars": _MAX_HOLD_BARS,
            },
            "total_bars": bar_count,
            "total_events": len(events),
            "min_sample_threshold": _MIN_SAMPLE,
        },
        "p1_mature_edge_count": edge_count,
        "p1_mature_summary": p1_mature_summary,
        "by_segment": by_segment,
        "events": events,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    conn.close()

    # Console summary
    _print_summary(results)

    return results


def _print_summary(results: dict[str, Any]) -> None:
    meta = results["meta"]
    print(f"\n{'=' * 70}")
    print("EVENT STUDY V1 — SUMMARY")
    print(f"{'=' * 70}")
    print(f"Period:         {meta['study_start']} -> {meta['study_end']}")
    print(f"Total bars:     {meta['total_bars']:,}")
    print(f"Total events:   {meta['total_events']:,}")
    print(f"P1+MATURE edge segments: {results['p1_mature_edge_count']}/6 "
          f"(threshold: mean_fwd_ret_bar4 > 0, p < 0.10, n >= 30)")
    print()
    print(f"{'Seg':<4} {'Events':>6}  {'P1+MATURE Stats':}")
    print(f"{'---':<4} {'------':>6}  {'-' * 50}")
    for seg_id, seg_data in results["by_segment"].items():
        n_seg = seg_data["total_events"]
        p1m = seg_data["by_bucket"].get("P1_MATURE", {})
        if p1m.get("status") == "OK":
            mean_r = p1m.get("mean_forward_return_bar4", float("nan"))
            p_val = p1m.get("p_value", float("nan"))
            n_b = p1m.get("n_events", 0)
            hit = p1m.get("hit_rate", float("nan"))
            print(
                f"{seg_id:<4} {n_seg:>6}  "
                f"n={n_b:<4} mean_fwd4={mean_r:+.3f}  p={p_val:.3f}  hit={hit:.1%}"
                f"  [{seg_data['description']}]"
            )
        else:
            status = p1m.get("status", "NO_DATA")
            n_b = p1m.get("n_events", 0)
            print(f"{seg_id:<4} {n_seg:>6}  {status} (n={n_b})  [{seg_data['description']}]")
    print(f"{'=' * 70}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Event study v1 — sweep+reclaim raw signal analysis")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("storage/btc_bot.db"),
        help="Path to the source SQLite market database",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research_lab/runs/event_study_v1.json"),
        help="Output path for results JSON",
    )
    args = parser.parse_args()

    run_event_study(db_path=args.db_path, output_path=args.output)


if __name__ == "__main__":
    main()
