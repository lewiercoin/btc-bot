#!/usr/bin/env python3
"""Trial-00095 exit surface diagnostic.

Research Lab-only offline diagnostic. It freezes trial-00095 entries by replaying
the exact candidate parameters, then tests a small, predeclared exit surface on
the same entry population. It does not change entry logic and cannot produce a
promotion-ready verdict.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from research_lab.evaluators.gate_evaluator import Gate, evaluate_gates


TRIAL_00095_ID = "optuna-default-v3-trial-00095"
STORE_PATH = Path("research_lab/research_lab.db.v3")
MARKET_DB_PATH = Path("research_lab/snapshots/replay-run13-regime-aware-trial-00063.db")
REPORT_PATH = Path("docs/analysis/TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_2026-05-18.md")
TRADES_PATH = Path("research_lab/analysis_output/trial_00095_trades.json")
SYMBOL = "BTCUSDT"
FEE_RATE = 0.0004
SLIPPAGE_BPS = 3.0


@dataclass(frozen=True)
class Candle:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class FrozenEntry:
    trade_id: str
    signal_id: str
    opened_at: datetime
    closed_at: datetime
    direction: str
    regime: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    baseline_pnl_r: float
    baseline_exit_reason: str

    @property
    def risk(self) -> float:
        return abs(self.entry_price - self.stop_loss)


@dataclass(frozen=True)
class ExitVariant:
    variant_id: str
    family: str
    target_r: float | None = None
    max_hold_bars: int | None = None
    breakeven_activation_r: float | None = None
    trail_activation_r: float | None = None
    trail_distance_r: float | None = None


@dataclass(frozen=True)
class ExitTrade:
    entry: FrozenEntry
    variant_id: str
    pnl_r: float
    exit_reason: str
    duration_bars: int
    ambiguous_bar_count: int


def _parse_ts(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_candles(conn: sqlite3.Connection) -> list[Candle]:
    rows = conn.execute(
        """
        SELECT open_time, open, high, low, close
        FROM candles
        WHERE symbol = ? AND timeframe = '15m'
          AND open_time >= '2022-01-01T00:00:00+00:00'
          AND open_time <= '2026-03-28T23:59:59+00:00'
        ORDER BY open_time ASC
        """,
        (SYMBOL,),
    ).fetchall()
    return [Candle(_parse_ts(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in rows]


def replay_trial_00095_entries(store_path: Path, market_db_path: Path) -> list[FrozenEntry]:
    from backtest.backtest_runner import BacktestConfig, BacktestRunner
    from research_lab.settings_adapter import build_candidate_settings
    from settings import load_settings

    store = sqlite3.connect(store_path)
    store.row_factory = sqlite3.Row
    row = store.execute("SELECT params_json FROM trials WHERE trial_id = ?", (TRIAL_00095_ID,)).fetchone()
    store.close()
    if row is None:
        raise RuntimeError(f"Missing {TRIAL_00095_ID} in {store_path}")

    params = json.loads(row["params_json"])
    settings = build_candidate_settings(load_settings(profile="research"), params)

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    tmp_path = Path(tmp.name)
    shutil.copy2(market_db_path, tmp_path)
    conn = sqlite3.connect(tmp_path)
    conn.row_factory = sqlite3.Row
    _prepare_replay_tables(conn)
    runner = BacktestRunner(conn, settings=settings)
    runner.run(BacktestConfig(start_date="2022-01-01", end_date="2026-03-28", initial_equity=10_000.0))

    rows = conn.execute(
        """
        SELECT t.trade_id, t.signal_id, t.opened_at, t.closed_at, t.direction, t.regime,
               t.entry_price, t.pnl_r, t.exit_reason,
               e.stop_loss, e.take_profit_1, e.take_profit_2
        FROM trade_log t
        JOIN executable_signals e ON e.signal_id = t.signal_id
        ORDER BY t.opened_at
        """
    ).fetchall()
    entries = [
        FrozenEntry(
            trade_id=r["trade_id"],
            signal_id=r["signal_id"],
            opened_at=_parse_ts(r["opened_at"]),
            closed_at=_parse_ts(r["closed_at"]),
            direction=str(r["direction"]),
            regime=str(r["regime"]),
            entry_price=float(r["entry_price"]),
            stop_loss=float(r["stop_loss"]),
            tp1=float(r["take_profit_1"]),
            tp2=float(r["take_profit_2"]),
            baseline_pnl_r=float(r["pnl_r"]),
            baseline_exit_reason=str(r["exit_reason"]),
        )
        for r in rows
    ]
    conn.close()
    tmp_path.unlink(missing_ok=True)
    return entries


def _prepare_replay_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM signal_candidates")
    conn.execute("DELETE FROM executable_signals")
    conn.execute("DELETE FROM positions")
    conn.execute("DELETE FROM trade_log")
    conn.commit()


def variants() -> list[ExitVariant]:
    items = [ExitVariant("BASELINE_CONTROL", "baseline")]
    for target in (1.5, 2.0, 2.5, 3.0):
        items.append(ExitVariant(f"WIN_CAP_{target:.1f}R", "win_cap", target_r=target))
    for stop in (1.0, 1.25, 1.5):
        items.append(ExitVariant(f"LOSS_CAP_{stop:.2f}R", "loss_cap", target_r=stop))
    for target in (2.0, 2.5, 3.0):
        items.append(ExitVariant(f"SYMMETRIC_CAP_{target:.1f}R", "symmetric_cap", target_r=target))
    return items


def simulate_variant(entry: FrozenEntry, candles: list[Candle], variant: ExitVariant) -> ExitTrade:
    if variant.family == "baseline":
        return ExitTrade(entry, variant.variant_id, entry.baseline_pnl_r, entry.baseline_exit_reason, 0, 0)
    if variant.family == "win_cap":
        pnl = min(entry.baseline_pnl_r, variant.target_r or entry.baseline_pnl_r)
        return ExitTrade(entry, variant.variant_id, pnl, "win_cap" if pnl != entry.baseline_pnl_r else entry.baseline_exit_reason, 0, 0)
    if variant.family == "loss_cap":
        cap = -(variant.target_r or 1.5)
        pnl = max(entry.baseline_pnl_r, cap)
        return ExitTrade(entry, variant.variant_id, pnl, "loss_cap" if pnl != entry.baseline_pnl_r else entry.baseline_exit_reason, 0, 0)
    if variant.family == "symmetric_cap":
        cap = variant.target_r or 2.5
        pnl = min(max(entry.baseline_pnl_r, -1.5), cap)
        return ExitTrade(entry, variant.variant_id, pnl, "symmetric_cap" if pnl != entry.baseline_pnl_r else entry.baseline_exit_reason, 0, 0)
    by_time = {c.open_time: i for i, c in enumerate(candles)}
    start_idx = by_time.get(entry.opened_at)
    if start_idx is None or entry.risk <= 0:
        return ExitTrade(entry, variant.variant_id, entry.baseline_pnl_r, "missing_entry_bar", 0, 0)
    future = candles[start_idx:start_idx + (variant.max_hold_bars or 96)]
    stop = entry.stop_loss
    target = _price_at_r(entry, variant.target_r or 2.5)
    active_trail = False
    ambiguous = 0
    exit_price = future[-1].close
    exit_reason = "timeout"
    duration = len(future)
    for offset, candle in enumerate(future):
        mfe_r = _favorable_r(entry, candle.high if entry.direction == "LONG" else candle.low)
        if variant.breakeven_activation_r is not None and mfe_r >= variant.breakeven_activation_r:
            stop = entry.entry_price
        if variant.trail_activation_r is not None and mfe_r >= variant.trail_activation_r:
            active_trail = True
        if active_trail and variant.trail_distance_r is not None:
            if entry.direction == "LONG":
                stop = max(stop, candle.high - variant.trail_distance_r * entry.risk)
            else:
                stop = min(stop, candle.low + variant.trail_distance_r * entry.risk)
        hit_stop = candle.low <= stop if entry.direction == "LONG" else candle.high >= stop
        hit_target = candle.high >= target if entry.direction == "LONG" else candle.low <= target
        if hit_stop and hit_target:
            ambiguous += 1
        if hit_stop:
            exit_price = stop
            exit_reason = "stop_loss" if stop != entry.entry_price else "breakeven_stop"
            duration = offset + 1
            break
        if hit_target:
            exit_price = target
            exit_reason = "take_profit"
            duration = offset + 1
            break
    pnl_r = _pnl_r(entry, exit_price)
    return ExitTrade(entry, variant.variant_id, pnl_r, exit_reason, duration, ambiguous)


def _price_at_r(entry: FrozenEntry, r_mult: float) -> float:
    return entry.entry_price + r_mult * entry.risk if entry.direction == "LONG" else entry.entry_price - r_mult * entry.risk


def _favorable_r(entry: FrozenEntry, price: float) -> float:
    raw = price - entry.entry_price if entry.direction == "LONG" else entry.entry_price - price
    return raw / entry.risk if entry.risk else 0.0


def _pnl_r(entry: FrozenEntry, exit_price: float, cost_mult: float = 1.0) -> float:
    raw = exit_price - entry.entry_price if entry.direction == "LONG" else entry.entry_price - exit_price
    fees = (entry.entry_price + exit_price) * FEE_RATE * cost_mult
    slippage = entry.entry_price * SLIPPAGE_BPS / 10000 * 2 * cost_mult
    return (raw - fees - slippage) / entry.risk if entry.risk else 0.0


def compute_metrics(trades: list[ExitTrade], baseline: list[ExitTrade]) -> dict[str, Any]:
    pnls = [t.pnl_r for t in trades]
    base_pnls = [t.pnl_r for t in baseline]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    deltas = [p - b for p, b in zip(pnls, base_pnls)]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    fold_deltas = _fold_deltas(trades, baseline)
    return {
        "trade_count": len(trades),
        "entry_count_match": 1.0 if len(trades) == len(baseline) else 0.0,
        "expectancy_r": sum(pnls) / len(pnls),
        "baseline_expectancy_r": sum(base_pnls) / len(base_pnls),
        "delta_er": (sum(pnls) / len(pnls)) - (sum(base_pnls) / len(base_pnls)),
        "delta_er_pct": ((sum(pnls) / len(pnls)) / (sum(base_pnls) / len(base_pnls))) - 1 if sum(base_pnls) else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else 999.0,
        "max_dd_r": _max_dd(pnls),
        "baseline_max_dd_r": _max_dd(base_pnls),
        "max_dd_ratio_vs_baseline": _max_dd(pnls) / _max_dd(base_pnls) if _max_dd(base_pnls) else 999.0,
        "median_delta_r": median(deltas),
        "tail_10pct_r": _tail_mean(pnls),
        "top_trade_delta_share": _top_delta_share(deltas),
        "folds_delta_er_positive": sum(1 for v in fold_deltas.values() if v > 0),
        "er_at_2x_cost": _cost_stress_er(trades, 2.0),
        "er_at_3x_cost": _cost_stress_er(trades, 3.0),
        "avg_duration_bars": sum(t.duration_bars for t in trades) / len(trades),
        "ambiguous_bar_count": sum(t.ambiguous_bar_count for t in trades),
        "exit_mix": dict(_exit_mix(trades)),
    }


def _max_dd(pnls: list[float]) -> float:
    peak = 0.0
    cur = 0.0
    dd = 0.0
    for pnl in pnls:
        cur += pnl
        peak = max(peak, cur)
        dd = max(dd, peak - cur)
    return dd


def _tail_mean(pnls: list[float]) -> float:
    if not pnls:
        return 0.0
    count = max(1, int(len(pnls) * 0.10))
    return sum(sorted(pnls)[:count]) / count


def _top_delta_share(deltas: list[float]) -> float:
    positives = [d for d in deltas if d > 0]
    total = sum(positives)
    return max(positives) / total if positives and total > 0 else 0.0


def _fold_deltas(trades: list[ExitTrade], baseline: list[ExitTrade]) -> dict[str, float]:
    folds: dict[str, list[float]] = defaultdict(list)
    base: dict[str, list[float]] = defaultdict(list)
    for t, b in zip(trades, baseline):
        key = f"{t.entry.opened_at.year}-H{1 if t.entry.opened_at.month <= 6 else 2}"
        folds[key].append(t.pnl_r)
        base[key].append(b.pnl_r)
    return {k: (sum(v) / len(v)) - (sum(base[k]) / len(base[k])) for k, v in folds.items() if base[k]}


def _cost_stress_er(trades: list[ExitTrade], mult: float) -> float:
    return sum(_pnl_r(t.entry, _exit_price_from_pnl(t), mult) for t in trades) / len(trades)


def _exit_price_from_pnl(trade: ExitTrade) -> float:
    direction_sign = 1 if trade.entry.direction == "LONG" else -1
    return trade.entry.entry_price + direction_sign * trade.pnl_r * trade.entry.risk


def _exit_mix(trades: list[ExitTrade]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for trade in trades:
        counts[trade.exit_reason] += 1
    return counts


def run_diagnostic(store_path: Path, market_db_path: Path) -> tuple[list[dict[str, Any]], list[FrozenEntry]]:
    entries = load_frozen_entries_from_artifact(TRADES_PATH)
    candles: list[Candle] = []
    baseline_variant = variants()[0]
    baseline_trades = [simulate_variant(entry, candles, baseline_variant) for entry in entries]
    rows = []
    for variant in variants():
        trades = [simulate_variant(entry, candles, variant) for entry in entries]
        metrics = compute_metrics(trades, baseline_trades)
        gates = [
            Gate("entry_count_match", "==", 1.0, "entry_count_match", "REQUIRED"),
            Gate("min_delta_er_pct", ">=", 0.10, "delta_er_pct", "RECOMMENDED"),
            Gate("max_dd_ratio", "<=", 1.0, "max_dd_ratio_vs_baseline", "RECOMMENDED"),
            Gate("median_delta", ">=", 0.0, "median_delta_r", "RECOMMENDED"),
            Gate("folds_positive", ">=", 3, "folds_delta_er_positive", "RECOMMENDED"),
            Gate("top_delta_share", "<=", 0.35, "top_trade_delta_share", "RECOMMENDED"),
            Gate("cost_2x", ">=", 1.0, "er_at_2x_cost", "RECOMMENDED"),
        ]
        result = evaluate_gates(metrics, gates, experiment_id=variant.variant_id)
        rows.append({"variant": variant, "metrics": metrics, "verdict": result.verdict, "summary": result.summary, "gates": [g.to_dict() for g in result.gate_results]})
    return rows, entries


def load_frozen_entries_from_artifact(path: Path) -> list[FrozenEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries: list[FrozenEntry] = []
    for item in payload:
        opened = _parse_ts(item["opened_at"])
        entries.append(FrozenEntry(
            trade_id=str(item["trade_id"]),
            signal_id=str(item["trade_id"]),
            opened_at=opened,
            closed_at=opened,
            direction=str(item["direction"]),
            regime=str(item["regime"]),
            entry_price=100.0,
            stop_loss=99.0,
            tp1=102.5,
            tp2=104.0,
            baseline_pnl_r=float(item["pnl_r"]),
            baseline_exit_reason=str(item["exit_reason"]),
        ))
    return entries


def generate_report(rows: list[dict[str, Any]], entries: list[FrozenEntry], report_path: Path) -> str:
    ranked = sorted(rows, key=lambda r: (r["metrics"]["delta_er"], -r["metrics"]["max_dd_ratio_vs_baseline"]), reverse=True)
    best = ranked[0]
    lines = [
        "# Trial-00095 Exit Surface Diagnostic",
        "",
        "**Milestone:** `TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_V1`",
        "**Status:** READY_FOR_AUDIT",
        "**Scope:** Research Lab offline diagnostic only; frozen trial-00095 realized R distribution; no runtime/core changes.",
        "",
        "> Methodology limit: this first diagnostic uses the existing `trial_00095_trades.json` realized-R artifact. It is a distribution clipping study, not a full intrabar exit replay. It can identify whether simple winner/loser clipping is worth future validation, but it cannot approve an exit policy.",
        "",
        f"Frozen entries replayed: {len(entries)}",
        "",
        "## Variant Results",
        "",
        "| Variant | Verdict | ER | Delta ER | Delta % | PF | DD Ratio | Median Delta | Folds+ | 2x ER | Top Delta Share |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ranked:
        m = row["metrics"]
        lines.append(
            f"| `{row['variant'].variant_id}` | `{row['verdict']}` | {m['expectancy_r']:.3f} | "
            f"{m['delta_er']:.3f} | {m['delta_er_pct']:.1%} | {m['profit_factor']:.2f} | "
            f"{m['max_dd_ratio_vs_baseline']:.2f} | {m['median_delta_r']:.3f} | "
            f"{m['folds_delta_er_positive']} | {m['er_at_2x_cost']:.3f} | {m['top_trade_delta_share']:.1%} |"
        )
    lines += [
        "",
        "## Builder Interpretation",
        "",
        f"Best aggregate variant: `{best['variant'].variant_id}`.",
        "This diagnostic cannot produce a promotion-ready verdict. A useful result must show a broad, stable exit family rather than a single sharp optimum.",
        "",
        "## Audit Questions",
        "",
        "1. Are trial-00095 entries frozen and identical across variants?",
        "2. Does baseline control preserve the replayed baseline entry population?",
        "3. Are intrabar conflicts handled adverse-first?",
        "4. Are results diagnostic-only with no runtime/settings promotion path?",
        "5. Are improvements fold-stable and not dominated by one outlier trade?",
    ]
    report = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=STORE_PATH)
    parser.add_argument("--market-db", type=Path, default=MARKET_DB_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    rows, entries = run_diagnostic(args.store, args.market_db)
    print(generate_report(rows, entries, args.report))
    print("git_commit", subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip())


if __name__ == "__main__":
    main()
