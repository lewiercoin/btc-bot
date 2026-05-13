"""
TRIAL_00095_CONDITIONAL_EDGE_ANALYSIS_V1

Offline analysis to determine whether min_sweep_depth_pct = 0.00649 is a natural
edge boundary or an overfitted cliff.

Two-phase analysis:
  Phase 1: Cross-trial depth sensitivity from research_lab.db.v3
  Phase 2: Per-trade replay of trial-00095 with full feature capture

Usage:
  python -m research_lab.analysis_trial_00095_conditional_edge \
      --store research_lab/research_lab.db.v3 \
      --market-db research_lab/snapshots/replay-run13-regime-aware-trial-00063.db \
      --output-dir research_lab/analysis_output

Read-only on store DB. Replay writes to a temporary in-memory or tempfile DB only.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
import sys
import tempfile
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Phase 1: Cross-trial depth sensitivity
# ---------------------------------------------------------------------------

TRIAL_00095_ID = "optuna-default-v3-trial-00095"
TRIAL_00095_DEPTH = 0.00649


@dataclass(slots=True)
class TrialPoint:
    trial_id: str
    min_sweep_depth_pct: float
    expectancy_r: float
    profit_factor: float
    trades_count: int
    win_rate: float
    max_drawdown_pct: float
    sharpe_ratio: float


def load_cross_trial_data(store_path: Path) -> list[TrialPoint]:
    conn = sqlite3.connect(str(store_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT trial_id, params_json, metrics_json FROM trials"
    ).fetchall()
    conn.close()

    points: list[TrialPoint] = []
    for r in rows:
        try:
            params = json.loads(r["params_json"])
            metrics = json.loads(r["metrics_json"])
        except (json.JSONDecodeError, TypeError):
            continue

        depth = params.get("min_sweep_depth_pct")
        tc = metrics.get("trades_count", 0)
        if depth is None or tc == 0:
            continue

        points.append(TrialPoint(
            trial_id=r["trial_id"],
            min_sweep_depth_pct=depth,
            expectancy_r=metrics.get("expectancy_r", 0.0),
            profit_factor=metrics.get("profit_factor", 0.0),
            trades_count=tc,
            win_rate=metrics.get("win_rate", 0.0),
            max_drawdown_pct=metrics.get("max_drawdown_pct", 0.0),
            sharpe_ratio=metrics.get("sharpe_ratio", 0.0),
        ))
    return points


def analyze_cross_trial(points: list[TrialPoint]) -> dict[str, Any]:
    """Bin trials by depth and compute aggregate metrics per bin."""
    bins = [
        ("< 0.001", 0.0, 0.001),
        ("0.001 - 0.003", 0.001, 0.003),
        ("0.003 - 0.005", 0.003, 0.005),
        ("0.005 - 0.007", 0.005, 0.007),
        ("0.007 - 0.010", 0.007, 0.010),
        ("0.010 - 0.015", 0.010, 0.015),
        ("> 0.015", 0.015, 1.0),
    ]

    results: list[dict[str, Any]] = []
    for label, lo, hi in bins:
        subset = [p for p in points if lo <= p.min_sweep_depth_pct < hi]
        if not subset:
            results.append({"bin": label, "n_trials": 0})
            continue

        ers = [p.expectancy_r for p in subset]
        tcs = [p.trades_count for p in subset]
        pfs = [p.profit_factor for p in subset]
        wrs = [p.win_rate for p in subset]

        results.append({
            "bin": label,
            "n_trials": len(subset),
            "er_mean": statistics.mean(ers),
            "er_median": statistics.median(ers),
            "er_max": max(ers),
            "pf_mean": statistics.mean(pfs),
            "trades_mean": statistics.mean(tcs),
            "trades_median": statistics.median(tcs),
            "wr_mean": statistics.mean(wrs),
        })

    # Top-10 trials by ER (min 30 trades)
    qualified = [p for p in points if p.trades_count >= 30]
    top10 = sorted(qualified, key=lambda p: p.expectancy_r, reverse=True)[:10]

    return {
        "total_trials_with_trades": len(points),
        "bins": results,
        "top10_by_er": [
            {
                "trial_id": p.trial_id,
                "depth": p.min_sweep_depth_pct,
                "er": p.expectancy_r,
                "pf": p.profit_factor,
                "trades": p.trades_count,
                "wr": p.win_rate,
            }
            for p in top10
        ],
        "trial_00095": {
            "depth": TRIAL_00095_DEPTH,
            "bin": "0.005 - 0.007",
        },
    }


# ---------------------------------------------------------------------------
# Phase 2: Per-trade replay
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TradeRecord:
    trade_id: str
    opened_at: str
    closed_at: str
    direction: str
    regime: str
    confluence_score: float
    entry_price: float
    exit_price: float
    pnl_r: float
    pnl_abs: float
    mae: float
    mfe: float
    exit_reason: str
    sweep_depth_pct: float | None
    sweep_side: str | None
    atr_15m: float | None
    atr_4h: float | None
    funding_pct_60d: float | None
    tfi_60s: float | None
    session_hour: int | None


def run_replay(market_db_path: Path, store_path: Path) -> list[TradeRecord]:
    """Run BacktestRunner with trial-00095 params and capture per-trade data."""

    # Import here to avoid import errors if backtest not available
    from backtest.backtest_runner import BacktestConfig, BacktestRunner
    from research_lab.settings_adapter import build_candidate_settings
    from settings import load_settings

    # Load trial-00095 params from store
    store_conn = sqlite3.connect(str(store_path))
    store_conn.row_factory = sqlite3.Row
    row = store_conn.execute(
        "SELECT params_json FROM trials WHERE trial_id = ?",
        (TRIAL_00095_ID,),
    ).fetchone()
    store_conn.close()

    if not row:
        raise RuntimeError(f"Trial {TRIAL_00095_ID} not found in {store_path}")

    params = json.loads(row["params_json"])

    # Build settings from trial-00095 params
    base_settings = load_settings(profile="research")
    candidate_settings = build_candidate_settings(base_settings, params)

    print(f"  Replay settings: min_sweep_depth_pct={candidate_settings.strategy.min_sweep_depth_pct}")
    print(f"  Replay settings: confluence_min={candidate_settings.strategy.confluence_min}")
    print(f"  Replay settings: config_hash={candidate_settings.config_hash}")

    # Copy market DB to temp file to avoid mutating the snapshot
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    tmp_path = Path(tmp.name)
    print(f"  Copying market DB to {tmp_path} ...")
    shutil.copy2(str(market_db_path), str(tmp_path))

    conn = sqlite3.connect(str(tmp_path))
    conn.row_factory = sqlite3.Row
    # Ensure schema tables exist for backtest persistence
    conn.execute("""CREATE TABLE IF NOT EXISTS signal_candidates (
        signal_id TEXT PRIMARY KEY, timestamp TEXT, direction TEXT,
        setup_type TEXT, confluence_score REAL, regime TEXT,
        reasons_json TEXT, features_json TEXT, schema_version TEXT, config_hash TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS executable_signals (
        signal_id TEXT PRIMARY KEY, timestamp TEXT, direction TEXT,
        entry_price REAL, stop_loss REAL, take_profit_1 REAL,
        take_profit_2 REAL, rr_ratio REAL, governance_notes_json TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS positions (
        position_id TEXT PRIMARY KEY, signal_id TEXT, symbol TEXT,
        direction TEXT, status TEXT, entry_price REAL, size REAL,
        leverage INTEGER, stop_loss REAL, take_profit_1 REAL,
        take_profit_2 REAL, opened_at TEXT, updated_at TEXT
    )""")
    conn.execute("""DROP TABLE IF EXISTS trade_log""")
    conn.execute("""CREATE TABLE IF NOT EXISTS trade_log (
        trade_id TEXT PRIMARY KEY, signal_id TEXT, position_id TEXT,
        opened_at TEXT, closed_at TEXT, direction TEXT, regime TEXT,
        confluence_score REAL, entry_price REAL, exit_price REAL,
        size REAL, fees_total REAL, funding_paid REAL, slippage_bps_avg REAL,
        pnl_abs REAL, pnl_r REAL, mae REAL, mfe REAL, exit_reason TEXT,
        features_at_entry_json TEXT, schema_version TEXT, config_hash TEXT
    )""")
    conn.commit()

    runner = BacktestRunner(conn, settings=candidate_settings)
    bt_config = BacktestConfig(
        start_date="2022-01-01",
        end_date="2026-03-28",
        initial_equity=10_000.0,
    )

    print("  Running backtest replay ...")
    result = runner.run(bt_config)
    print(f"  Replay complete: {len(result.trades)} trades")

    # Extract per-trade data from trade_log in temp DB
    records: list[TradeRecord] = []
    rows = conn.execute(
        "SELECT * FROM trade_log ORDER BY opened_at"
    ).fetchall()

    for r in rows:
        features: dict[str, Any] = {}
        try:
            features = json.loads(r["features_at_entry_json"]) if r["features_at_entry_json"] else {}
        except (json.JSONDecodeError, TypeError):
            pass

        opened_str = r["opened_at"]
        hour: int | None = None
        try:
            dt = datetime.fromisoformat(opened_str)
            hour = dt.hour
        except (ValueError, TypeError):
            pass

        records.append(TradeRecord(
            trade_id=r["trade_id"],
            opened_at=r["opened_at"],
            closed_at=r["closed_at"] or "",
            direction=r["direction"],
            regime=r["regime"],
            confluence_score=float(r["confluence_score"]),
            entry_price=float(r["entry_price"]),
            exit_price=float(r["exit_price"]) if r["exit_price"] else 0.0,
            pnl_r=float(r["pnl_r"]),
            pnl_abs=float(r["pnl_abs"]),
            mae=float(r["mae"]),
            mfe=float(r["mfe"]),
            exit_reason=r["exit_reason"] or "",
            sweep_depth_pct=features.get("sweep_depth_pct"),
            sweep_side=features.get("sweep_side"),
            atr_15m=features.get("atr_15m"),
            atr_4h=features.get("atr_4h"),
            funding_pct_60d=features.get("funding_pct_60d"),
            tfi_60s=features.get("tfi_60s"),
            session_hour=hour,
        ))

    conn.close()
    # Clean up temp file
    try:
        tmp_path.unlink()
    except OSError:
        pass

    return records


# ---------------------------------------------------------------------------
# Phase 2 analyses
# ---------------------------------------------------------------------------

def _safe_median(vals: list[float]) -> float:
    return statistics.median(vals) if vals else 0.0


def _safe_mean(vals: list[float]) -> float:
    return statistics.mean(vals) if vals else 0.0


def _percentile(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    idx = p / 100.0 * (len(s) - 1)
    lo = int(math.floor(idx))
    hi = min(lo + 1, len(s) - 1)
    frac = idx - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def analyze_per_trade(trades: list[TradeRecord]) -> dict[str, Any]:
    """Full per-trade analysis suite."""
    if not trades:
        return {"error": "no trades"}

    depths = [t.sweep_depth_pct for t in trades if t.sweep_depth_pct is not None]
    wins = [t for t in trades if t.pnl_r > 0]
    losses = [t for t in trades if t.pnl_r <= 0]
    win_depths = [t.sweep_depth_pct for t in wins if t.sweep_depth_pct is not None]
    loss_depths = [t.sweep_depth_pct for t in losses if t.sweep_depth_pct is not None]

    # 1. Depth distribution
    depth_stats = {}
    if depths:
        depth_stats = {
            "count": len(depths),
            "min": min(depths),
            "max": max(depths),
            "mean": _safe_mean(depths),
            "median": _safe_median(depths),
            "p25": _percentile(depths, 25),
            "p75": _percentile(depths, 75),
            "p10": _percentile(depths, 10),
            "p90": _percentile(depths, 90),
            "std": statistics.stdev(depths) if len(depths) > 1 else 0.0,
        }

    # 2. Conditional ER by depth quartile
    quartile_analysis = _conditional_er_by_quartile(trades)

    # 3. Win vs loss depth comparison
    win_loss_comparison = {
        "wins": {
            "count": len(wins),
            "depth_mean": _safe_mean(win_depths),
            "depth_median": _safe_median(win_depths),
        },
        "losses": {
            "count": len(losses),
            "depth_mean": _safe_mean(loss_depths),
            "depth_median": _safe_median(loss_depths),
        },
    }
    # Mann-Whitney U approximation (simplified z-test for large samples)
    if len(win_depths) >= 5 and len(loss_depths) >= 5:
        win_loss_comparison["depth_difference_significant"] = _mann_whitney_approx(win_depths, loss_depths)

    # 4. MAE/MFE vs depth correlation
    mae_mfe_analysis = _mae_mfe_vs_depth(trades)

    # 5. Regime × depth breakdown
    regime_depth = _regime_depth_breakdown(trades)

    # 6. Session hour × depth breakdown
    session_depth = _session_depth_breakdown(trades)

    # 7. Feature importance (simplified: correlation matrix)
    feature_importance = _feature_importance(trades)

    # 8. Depth histogram buckets
    histogram = _depth_histogram(depths)

    return {
        "total_trades": len(trades),
        "total_with_depth": len(depths),
        "depth_stats": depth_stats,
        "quartile_analysis": quartile_analysis,
        "win_loss_comparison": win_loss_comparison,
        "mae_mfe_analysis": mae_mfe_analysis,
        "regime_depth": regime_depth,
        "session_depth": session_depth,
        "feature_importance": feature_importance,
        "depth_histogram": histogram,
    }


def _conditional_er_by_quartile(trades: list[TradeRecord]) -> list[dict[str, Any]]:
    """Split trades by sweep_depth quartile and compute ER per group."""
    with_depth = [(t, t.sweep_depth_pct) for t in trades if t.sweep_depth_pct is not None]
    if len(with_depth) < 4:
        return []

    depths_sorted = sorted(d for _, d in with_depth)
    q1 = _percentile(depths_sorted, 25)
    q2 = _percentile(depths_sorted, 50)
    q3 = _percentile(depths_sorted, 75)

    quartiles = [
        (f"Q1 (< {q1:.5f})", lambda d: d < q1),
        (f"Q2 ({q1:.5f} - {q2:.5f})", lambda d: q1 <= d < q2),
        (f"Q3 ({q2:.5f} - {q3:.5f})", lambda d: q2 <= d < q3),
        (f"Q4 (>= {q3:.5f})", lambda d: d >= q3),
    ]

    # Also add custom bins around the threshold
    custom_bins = [
        ("< 0.003", lambda d: d < 0.003),
        ("0.003 - 0.0065", lambda d: 0.003 <= d < 0.0065),
        ("0.0065 - 0.010", lambda d: 0.0065 <= d < 0.010),
        ("0.010 - 0.015", lambda d: 0.010 <= d < 0.015),
        (">= 0.015", lambda d: d >= 0.015),
    ]

    results = []
    for label, pred in quartiles + custom_bins:
        subset = [t for t, d in with_depth if pred(d)]
        if not subset:
            results.append({"label": label, "n": 0})
            continue
        pnl_rs = [t.pnl_r for t in subset]
        results.append({
            "label": label,
            "n": len(subset),
            "er_mean": _safe_mean(pnl_rs),
            "er_median": _safe_median(pnl_rs),
            "win_rate": sum(1 for p in pnl_rs if p > 0) / len(pnl_rs),
            "pnl_r_sum": sum(pnl_rs),
            "depth_mean": _safe_mean([d for _, d in with_depth if pred(d)]),
        })
    return results


def _mann_whitney_approx(a: list[float], b: list[float]) -> dict[str, Any]:
    """Simplified Mann-Whitney U test via normal approximation."""
    combined = [(v, "a") for v in a] + [(v, "b") for v in b]
    combined.sort(key=lambda x: x[0])

    # Assign ranks
    ranks: dict[str, list[float]] = {"a": [], "b": []}
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2.0  # 1-indexed average rank
        for k in range(i, j):
            ranks[combined[k][1]].append(avg_rank)
        i = j

    n1, n2 = len(a), len(b)
    r1 = sum(ranks["a"])
    u1 = r1 - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2
    sigma = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    z = (u1 - mu) / max(sigma, 1e-10)
    # Two-tailed p-value approximation
    p_approx = 2 * (1 - _normal_cdf(abs(z)))
    return {
        "z_statistic": round(z, 4),
        "p_value_approx": round(p_approx, 6),
        "significant_at_005": p_approx < 0.05,
        "significant_at_001": p_approx < 0.01,
    }


def _normal_cdf(x: float) -> float:
    """Standard normal CDF approximation (Abramowitz & Stegun)."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _mae_mfe_vs_depth(trades: list[TradeRecord]) -> dict[str, Any]:
    """Correlation between sweep_depth and MAE/MFE."""
    pairs_mae = [(t.sweep_depth_pct, t.mae) for t in trades if t.sweep_depth_pct is not None]
    pairs_mfe = [(t.sweep_depth_pct, t.mfe) for t in trades if t.sweep_depth_pct is not None]

    result: dict[str, Any] = {"n": len(pairs_mae)}
    if len(pairs_mae) >= 3:
        result["depth_mae_correlation"] = _pearson_r([d for d, _ in pairs_mae], [m for _, m in pairs_mae])
        result["depth_mfe_correlation"] = _pearson_r([d for d, _ in pairs_mfe], [m for _, m in pairs_mfe])
        result["depth_pnlr_correlation"] = _pearson_r(
            [t.sweep_depth_pct for t in trades if t.sweep_depth_pct is not None],
            [t.pnl_r for t in trades if t.sweep_depth_pct is not None],
        )
    return result


def _pearson_r(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient."""
    n = len(x)
    if n < 2:
        return 0.0
    mx, my = _safe_mean(x), _safe_mean(y)
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    sx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    sy = math.sqrt(sum((yi - my) ** 2 for yi in y))
    denom = sx * sy
    return cov / denom if denom > 1e-12 else 0.0


def _regime_depth_breakdown(trades: list[TradeRecord]) -> list[dict[str, Any]]:
    """ER by regime with depth stats."""
    by_regime: dict[str, list[TradeRecord]] = defaultdict(list)
    for t in trades:
        by_regime[t.regime].append(t)

    results = []
    for regime, ts in sorted(by_regime.items()):
        pnl_rs = [t.pnl_r for t in ts]
        depths = [t.sweep_depth_pct for t in ts if t.sweep_depth_pct is not None]
        results.append({
            "regime": regime,
            "n": len(ts),
            "er": _safe_mean(pnl_rs),
            "wr": sum(1 for p in pnl_rs if p > 0) / max(len(pnl_rs), 1),
            "depth_mean": _safe_mean(depths) if depths else None,
            "depth_median": _safe_median(depths) if depths else None,
        })
    return results


def _session_depth_breakdown(trades: list[TradeRecord]) -> list[dict[str, Any]]:
    """ER by session hour bucket with depth stats."""
    session_buckets = [
        ("Asia (0-8)", range(0, 8)),
        ("Europe (8-16)", range(8, 16)),
        ("US (16-24)", range(16, 24)),
    ]
    results = []
    for label, hours in session_buckets:
        subset = [t for t in trades if t.session_hour is not None and t.session_hour in hours]
        if not subset:
            results.append({"session": label, "n": 0})
            continue
        pnl_rs = [t.pnl_r for t in subset]
        depths = [t.sweep_depth_pct for t in subset if t.sweep_depth_pct is not None]
        results.append({
            "session": label,
            "n": len(subset),
            "er": _safe_mean(pnl_rs),
            "wr": sum(1 for p in pnl_rs if p > 0) / max(len(pnl_rs), 1),
            "depth_mean": _safe_mean(depths) if depths else None,
        })
    return results


def _feature_importance(trades: list[TradeRecord]) -> list[dict[str, Any]]:
    """Rank features by absolute Pearson correlation with pnl_r."""
    features_to_check = [
        ("sweep_depth_pct", lambda t: t.sweep_depth_pct),
        ("atr_15m", lambda t: t.atr_15m),
        ("atr_4h", lambda t: t.atr_4h),
        ("funding_pct_60d", lambda t: t.funding_pct_60d),
        ("tfi_60s", lambda t: t.tfi_60s),
        ("confluence_score", lambda t: t.confluence_score),
        ("session_hour", lambda t: float(t.session_hour) if t.session_hour is not None else None),
    ]

    results = []
    pnl_rs_all = [t.pnl_r for t in trades]

    for name, extractor in features_to_check:
        pairs = [(extractor(t), t.pnl_r) for t in trades if extractor(t) is not None]
        if len(pairs) < 10:
            continue
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        corr = _pearson_r(xs, ys)
        results.append({
            "feature": name,
            "correlation_with_pnl_r": round(corr, 4),
            "abs_correlation": round(abs(corr), 4),
            "n_samples": len(pairs),
        })

    results.sort(key=lambda r: r["abs_correlation"], reverse=True)
    return results


def _depth_histogram(depths: list[float], n_bins: int = 20) -> list[dict[str, Any]]:
    """Create histogram buckets for depth distribution."""
    if not depths:
        return []

    lo, hi = min(depths), max(depths)
    if hi <= lo:
        return [{"bin_start": lo, "bin_end": hi, "count": len(depths)}]

    step = (hi - lo) / n_bins
    buckets: list[dict[str, Any]] = []
    for i in range(n_bins):
        b_lo = lo + i * step
        b_hi = lo + (i + 1) * step if i < n_bins - 1 else hi + 1e-10
        cnt = sum(1 for d in depths if b_lo <= d < b_hi)
        buckets.append({
            "bin_start": round(b_lo, 6),
            "bin_end": round(b_hi, 6),
            "count": cnt,
        })
    return buckets


# ---------------------------------------------------------------------------
# Live comparison data (requires SSH output file or direct data)
# ---------------------------------------------------------------------------

def load_live_depths_from_file(path: Path) -> list[float]:
    """Load live sweep depths from a JSON file produced by diag script."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def compare_live_vs_backtest(
    backtest_depths: list[float],
    live_depths: list[float],
) -> dict[str, Any]:
    """Compare depth distributions between backtest trades and live rejected sweeps."""
    if not backtest_depths or not live_depths:
        return {"error": "insufficient data for comparison"}

    result: dict[str, Any] = {
        "backtest": {
            "n": len(backtest_depths),
            "mean": _safe_mean(backtest_depths),
            "median": _safe_median(backtest_depths),
            "p25": _percentile(backtest_depths, 25),
            "p75": _percentile(backtest_depths, 75),
        },
        "live_rejected": {
            "n": len(live_depths),
            "mean": _safe_mean(live_depths),
            "median": _safe_median(live_depths),
            "p25": _percentile(live_depths, 25),
            "p75": _percentile(live_depths, 75),
        },
    }

    # How many live rejected would have been accepted if threshold were lower?
    for threshold in [0.003, 0.004, 0.005, 0.006, 0.00649]:
        pct_above = sum(1 for d in live_depths if d >= threshold) / len(live_depths) * 100
        result[f"live_pct_above_{threshold}"] = round(pct_above, 1)

    return result


# ---------------------------------------------------------------------------
# Verdict determination
# ---------------------------------------------------------------------------

def determine_verdict(
    cross_trial: dict[str, Any],
    per_trade: dict[str, Any],
) -> dict[str, str]:
    """Determine verdict based on analysis results.

    Primary signal: cross-trial ER gradient across depth bins (746 trials).
    Secondary signals: per-trade quartile ER, win/loss depth, feature importance.

    Note: per-trade bins below the threshold are empty by design (threshold
    enforces a minimum), so cross-trial data is the only source for
    below-vs-above threshold comparison.
    """
    verdict = "INSUFFICIENT_DATA"
    reasoning = []

    win_loss = per_trade.get("win_loss_comparison", {})
    feature_imp = per_trade.get("feature_importance", [])
    quartiles = per_trade.get("quartile_analysis", [])

    # ---- Check 1: Cross-trial ER gradient (primary signal) ----
    ct_bins = cross_trial.get("bins", [])
    ct_by_label = {b["bin"]: b for b in ct_bins if b.get("n_trials", 0) > 0}

    below_labels = ["< 0.001", "0.001 - 0.003", "0.003 - 0.005"]
    above_labels = ["0.005 - 0.007", "0.007 - 0.010", "0.010 - 0.015", "> 0.015"]

    below_ers = [ct_by_label[l]["er_mean"] for l in below_labels if l in ct_by_label]
    above_ers = [ct_by_label[l]["er_mean"] for l in above_labels if l in ct_by_label]

    if below_ers and above_ers:
        mean_below = _safe_mean(below_ers)
        mean_above = _safe_mean(above_ers)
        reasoning.append(
            f"Cross-trial ER: below-threshold bins mean={mean_below:.3f} "
            f"({len(below_ers)} bins), above-threshold bins mean={mean_above:.3f} "
            f"({len(above_ers)} bins)"
        )

        # Check monotonicity across all bins
        all_bin_ers = [
            ct_by_label[l]["er_mean"]
            for l in below_labels + above_labels
            if l in ct_by_label
        ]
        monotonic_pairs = sum(
            1 for i in range(len(all_bin_ers) - 1)
            if all_bin_ers[i + 1] > all_bin_ers[i]
        )
        total_pairs = max(len(all_bin_ers) - 1, 1)
        monotonic_ratio = monotonic_pairs / total_pairs
        reasoning.append(
            f"Cross-trial monotonicity: {monotonic_pairs}/{total_pairs} "
            f"consecutive bins show increasing ER ({monotonic_ratio:.0%})"
        )

        if mean_above > 0.5 and mean_above > mean_below * 2:
            verdict = "THRESHOLD_NATURAL"
            reasoning.append(
                "Strong gradient: above-threshold ER > 2x below-threshold ER"
            )
        elif mean_above > mean_below * 1.3 and monotonic_ratio >= 0.6:
            verdict = "THRESHOLD_NATURAL"
            reasoning.append(
                "Moderate gradient with consistent monotonic trend"
            )
        elif monotonic_ratio < 0.4:
            verdict = "THRESHOLD_OVERFITTED"
            reasoning.append("No consistent monotonic ER trend across depth bins")
        else:
            verdict = "THRESHOLD_NATURAL"
            reasoning.append("Gradient present but modest; threshold is defensible")

    # ---- Check 2: Per-trade quartile ER within accepted trades ----
    q_labels = [q for q in quartiles if q.get("label", "").startswith("Q") and q.get("n", 0) > 0]
    if len(q_labels) >= 4:
        q1_er = q_labels[0].get("er_mean", 0)
        q4_er = q_labels[-1].get("er_mean", 0)
        reasoning.append(
            f"Per-trade: Q1 (shallowest accepted) ER={q1_er:.3f}, "
            f"Q4 (deepest) ER={q4_er:.3f}"
        )
        if q4_er > q1_er * 1.3:
            reasoning.append(
                "Within accepted trades, deeper sweeps still produce higher ER — "
                "depth is a continuous quality signal, not just a binary filter"
            )

    # ---- Check 3: Win/loss depth separation ----
    win_depth_mean = win_loss.get("wins", {}).get("depth_mean", 0)
    loss_depth_mean = win_loss.get("losses", {}).get("depth_mean", 0)
    if win_depth_mean > 0 and loss_depth_mean > 0:
        sig = win_loss.get("depth_difference_significant", {})
        p_val = sig.get("p_value_approx", 1.0) if sig else 1.0
        if win_depth_mean > loss_depth_mean * 1.05:
            reasoning.append(
                f"Winners have deeper sweeps (mean {win_depth_mean:.5f}) vs "
                f"losers ({loss_depth_mean:.5f}), p={p_val:.4f}"
            )
        else:
            reasoning.append(
                f"Winners/losers have similar depth "
                f"(win {win_depth_mean:.5f} vs loss {loss_depth_mean:.5f}), p={p_val:.4f}"
            )

    # ---- Check 4: Feature importance ----
    if feature_imp:
        depth_rank = next(
            (i for i, f in enumerate(feature_imp) if f["feature"] == "sweep_depth_pct"),
            len(feature_imp),
        )
        top_feature = feature_imp[0]["feature"] if feature_imp else "?"
        reasoning.append(
            f"Feature importance: sweep_depth_pct is #{depth_rank + 1} "
            f"(top feature: {top_feature})"
        )

    return {
        "verdict": verdict,
        "reasoning": reasoning,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def print_report(
    cross_trial: dict[str, Any],
    per_trade: dict[str, Any],
    verdict_info: dict[str, Any],
    live_comparison: dict[str, Any] | None = None,
) -> str:
    """Generate full text report."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("TRIAL_00095_CONDITIONAL_EDGE_ANALYSIS")
    lines.append("=" * 70)
    lines.append("")

    # Verdict
    lines.append(f"VERDICT: {verdict_info['verdict']}")
    for r in verdict_info.get("reasoning", []):
        lines.append(f"  - {r}")
    lines.append("")

    # Phase 1: Cross-trial
    lines.append("=" * 70)
    lines.append("PHASE 1: CROSS-TRIAL DEPTH SENSITIVITY")
    lines.append(f"Total trials with trades: {cross_trial['total_trials_with_trades']}")
    lines.append("")
    lines.append(f"{'Bin':<20} {'N':>5} {'ER mean':>8} {'ER med':>8} {'ER max':>8} {'PF mean':>8} {'Trades':>8}")
    lines.append("-" * 70)
    for b in cross_trial.get("bins", []):
        if b.get("n_trials", 0) == 0:
            lines.append(f"{b['bin']:<20} {0:>5}")
            continue
        lines.append(
            f"{b['bin']:<20} {b['n_trials']:>5} {b['er_mean']:>8.3f} {b['er_median']:>8.3f} "
            f"{b['er_max']:>8.3f} {b['pf_mean']:>8.3f} {b['trades_mean']:>8.0f}"
        )
    lines.append(f"\n  trial-00095 depth={TRIAL_00095_DEPTH} falls in bin: {cross_trial['trial_00095']['bin']}")

    lines.append("\nTop-10 trials by ER (min 30 trades):")
    for t in cross_trial.get("top10_by_er", []):
        marker = " <-- trial-00095" if t["trial_id"] == TRIAL_00095_ID else ""
        lines.append(
            f"  {t['trial_id']:<45} depth={t['depth']:.5f} ER={t['er']:.3f} "
            f"PF={t['pf']:.3f} trades={t['trades']}{marker}"
        )

    # Phase 2: Per-trade
    lines.append("")
    lines.append("=" * 70)
    lines.append("PHASE 2: PER-TRADE ANALYSIS")
    lines.append(f"Total trades: {per_trade.get('total_trades', 0)}")
    lines.append(f"Trades with depth data: {per_trade.get('total_with_depth', 0)}")

    ds = per_trade.get("depth_stats", {})
    if ds:
        lines.append(f"\nSweep depth distribution (backtest trades):")
        lines.append(f"  min={ds['min']:.5f}  p10={ds['p10']:.5f}  p25={ds['p25']:.5f}  "
                      f"median={ds['median']:.5f}  p75={ds['p75']:.5f}  p90={ds['p90']:.5f}  max={ds['max']:.5f}")
        lines.append(f"  mean={ds['mean']:.5f}  std={ds['std']:.5f}")

    lines.append(f"\nConditional ER by depth group:")
    lines.append(f"{'Group':<30} {'N':>5} {'ER mean':>8} {'ER med':>8} {'WR':>6} {'depth mean':>10}")
    lines.append("-" * 70)
    for q in per_trade.get("quartile_analysis", []):
        if q.get("n", 0) == 0:
            lines.append(f"{q.get('label', '?'):<30} {0:>5}")
            continue
        lines.append(
            f"{q['label']:<30} {q['n']:>5} {q.get('er_mean', 0):>8.3f} {q.get('er_median', 0):>8.3f} "
            f"{q.get('win_rate', 0):>5.1%} {q.get('depth_mean', 0):>10.5f}"
        )

    wl = per_trade.get("win_loss_comparison", {})
    if wl:
        lines.append(f"\nWin vs Loss depth comparison:")
        w = wl.get("wins", {})
        l = wl.get("losses", {})
        lines.append(f"  Winners (n={w.get('count', 0)}): mean depth={w.get('depth_mean', 0):.5f}, median={w.get('depth_median', 0):.5f}")
        lines.append(f"  Losers  (n={l.get('count', 0)}): mean depth={l.get('depth_mean', 0):.5f}, median={l.get('depth_median', 0):.5f}")
        sig = wl.get("depth_difference_significant", {})
        if sig:
            lines.append(f"  Mann-Whitney U: z={sig.get('z_statistic', 0):.4f}, p={sig.get('p_value_approx', 1):.6f}, significant@0.05={sig.get('significant_at_005', False)}")

    mae_mfe = per_trade.get("mae_mfe_analysis", {})
    if mae_mfe and mae_mfe.get("n", 0) > 0:
        lines.append(f"\nMAE/MFE correlation with depth (n={mae_mfe['n']}):")
        lines.append(f"  depth <-> MAE:  r={mae_mfe.get('depth_mae_correlation', 0):.4f}")
        lines.append(f"  depth <-> MFE:  r={mae_mfe.get('depth_mfe_correlation', 0):.4f}")
        lines.append(f"  depth <-> pnl_r: r={mae_mfe.get('depth_pnlr_correlation', 0):.4f}")

    lines.append(f"\nFeature importance (|correlation| with pnl_r):")
    for f in per_trade.get("feature_importance", []):
        lines.append(f"  {f['feature']:<25} r={f['correlation_with_pnl_r']:>7.4f}  |r|={f['abs_correlation']:.4f}  n={f['n_samples']}")

    lines.append(f"\nRegime × depth breakdown:")
    for rd in per_trade.get("regime_depth", []):
        depth_str = f"depth_mean={rd['depth_mean']:.5f}" if rd.get("depth_mean") else "depth=N/A"
        lines.append(f"  {rd['regime']:<25} n={rd['n']:>4}  ER={rd['er']:.3f}  WR={rd['wr']:.1%}  {depth_str}")

    lines.append(f"\nSession × depth breakdown:")
    for sd in per_trade.get("session_depth", []):
        if sd.get("n", 0) == 0:
            continue
        depth_str = f"depth_mean={sd['depth_mean']:.5f}" if sd.get("depth_mean") else "depth=N/A"
        lines.append(f"  {sd['session']:<25} n={sd['n']:>4}  ER={sd['er']:.3f}  WR={sd['wr']:.1%}  {depth_str}")

    # Live comparison
    if live_comparison and "error" not in live_comparison:
        lines.append("")
        lines.append("=" * 70)
        lines.append("LIVE vs BACKTEST DEPTH COMPARISON")
        bt = live_comparison.get("backtest", {})
        lv = live_comparison.get("live_rejected", {})
        lines.append(f"  Backtest accepted trades (n={bt.get('n', 0)}): mean={bt.get('mean', 0):.5f}, median={bt.get('median', 0):.5f}")
        lines.append(f"  Live rejected sweeps (n={lv.get('n', 0)}): mean={lv.get('mean', 0):.5f}, median={lv.get('median', 0):.5f}")
        for k, v in live_comparison.items():
            if k.startswith("live_pct_above_"):
                threshold = k.replace("live_pct_above_", "")
                lines.append(f"  Live sweeps >= {threshold}: {v}%")

    lines.append("")
    lines.append("=" * 70)
    lines.append("END ANALYSIS")
    lines.append("=" * 70)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Trial-00095 Conditional Edge Analysis")
    parser.add_argument("--store", default="research_lab/research_lab.db.v3",
                        help="Path to research lab store DB")
    parser.add_argument("--market-db", default="research_lab/snapshots/replay-run13-regime-aware-trial-00063.db",
                        help="Path to market data DB for replay")
    parser.add_argument("--live-depths", default=None,
                        help="Path to JSON file with live sweep depth samples")
    parser.add_argument("--output-dir", default="research_lab/analysis_output",
                        help="Output directory for results")
    parser.add_argument("--skip-replay", action="store_true",
                        help="Skip Phase 2 replay (cross-trial only)")
    args = parser.parse_args(argv)

    store_path = Path(args.store)
    market_db_path = Path(args.market_db)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1
    print("Phase 1: Cross-trial depth sensitivity ...")
    points = load_cross_trial_data(store_path)
    cross_trial = analyze_cross_trial(points)
    print(f"  Loaded {len(points)} trials with trades")

    # Phase 2
    per_trade: dict[str, Any] = {}
    if not args.skip_replay:
        print("\nPhase 2: Per-trade replay ...")
        if not market_db_path.exists():
            print(f"  WARNING: Market DB not found: {market_db_path}")
            print("  Skipping replay. Use --skip-replay to suppress this warning.")
        else:
            trades = run_replay(market_db_path, store_path)
            per_trade = analyze_per_trade(trades)

            # Save per-trade data as JSON for later use
            trades_json = [
                {
                    "trade_id": t.trade_id,
                    "opened_at": t.opened_at,
                    "direction": t.direction,
                    "regime": t.regime,
                    "pnl_r": t.pnl_r,
                    "sweep_depth_pct": t.sweep_depth_pct,
                    "exit_reason": t.exit_reason,
                    "mae": t.mae,
                    "mfe": t.mfe,
                    "session_hour": t.session_hour,
                }
                for t in trades
            ]
            (output_dir / "trial_00095_trades.json").write_text(
                json.dumps(trades_json, indent=2), encoding="utf-8"
            )
    else:
        print("\nPhase 2: SKIPPED (--skip-replay)")

    # Live comparison
    live_comparison: dict[str, Any] | None = None
    if args.live_depths:
        live_depths = load_live_depths_from_file(Path(args.live_depths))
        backtest_depths = [t.sweep_depth_pct for t in trades if t.sweep_depth_pct is not None] if not args.skip_replay else []
        if live_depths:
            live_comparison = compare_live_vs_backtest(backtest_depths, live_depths)

    # Verdict
    verdict_info = determine_verdict(cross_trial, per_trade)

    # Report
    report_text = print_report(cross_trial, per_trade, verdict_info, live_comparison)
    print(report_text)

    # Save outputs
    (output_dir / "cross_trial_analysis.json").write_text(
        json.dumps(cross_trial, indent=2, default=str), encoding="utf-8"
    )
    if per_trade:
        (output_dir / "per_trade_analysis.json").write_text(
            json.dumps(per_trade, indent=2, default=str), encoding="utf-8"
        )
    (output_dir / "verdict.json").write_text(
        json.dumps(verdict_info, indent=2), encoding="utf-8"
    )
    (output_dir / "report.txt").write_text(report_text, encoding="utf-8")
    print(f"\nOutputs saved to {output_dir}/")


if __name__ == "__main__":
    main()
