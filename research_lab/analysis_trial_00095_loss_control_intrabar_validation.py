#!/usr/bin/env python3
"""Trial-00095 loss-control intrabar validation.

Research Lab-only validation of the prior exit-surface diagnostic. This freezes
trial-00095 entries from a replay, then asks whether predeclared hard loss
controls would have triggered on 15m candles before the original baseline close.
It preserves baseline winners unless a loss-control threshold was touched first.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any

from research_lab.evaluators.gate_evaluator import Gate, evaluate_gates


TRIAL_00095_ID = "optuna-default-v3-trial-00095"
STORE_PATH = Path("research_lab/research_lab.db.v3")
MARKET_DB_PATH = Path("research_lab/snapshots/replay-run13-regime-aware-trial-00063.db")
REPORT_PATH = Path("docs/analysis/TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION_2026-05-18.md")
ENTRY_CACHE_PATH = Path("research_lab/analysis_output/trial_00095_intrabar_frozen_entries.json")
PRIOR_TRADES_PATH = Path("research_lab/analysis_output/trial_00095_trades.json")
SYMBOL = "BTCUSDT"
START_DATE = "2022-01-01"
END_DATE = "2026-03-28"
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
class FrozenTrade:
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
class LossControlVariant:
    variant_id: str
    loss_r: float | None


@dataclass(frozen=True)
class SimulatedTrade:
    entry: FrozenTrade
    variant_id: str
    pnl_r: float
    exit_reason: str
    duration_bars: int
    threshold_touched: bool
    missing_candles: bool = False


def _parse_ts(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _format_ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def variants() -> list[LossControlVariant]:
    return [
        LossControlVariant("BASELINE_REPLAY", None),
        LossControlVariant("HARD_STOP_0_75R", 0.75),
        LossControlVariant("HARD_STOP_0_90R", 0.90),
        LossControlVariant("HARD_STOP_1_00R", 1.00),
        LossControlVariant("HARD_STOP_1_10R", 1.10),
    ]


def replay_trial_00095_entries(store_path: Path, market_db_path: Path) -> list[FrozenTrade]:
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
    try:
        _prepare_replay_tables(conn)
        runner = BacktestRunner(conn, settings=settings)
        runner.run(BacktestConfig(start_date=START_DATE, end_date=END_DATE, initial_equity=10_000.0))
        rows = conn.execute(
            """
            SELECT t.trade_id, t.signal_id, t.opened_at, t.closed_at, t.direction, t.regime,
                   t.entry_price, t.pnl_r, t.exit_reason,
                   e.stop_loss, e.take_profit_1, e.take_profit_2
            FROM trade_log t
            JOIN executable_signals e ON e.signal_id = t.signal_id
            WHERE t.closed_at IS NOT NULL
            ORDER BY t.opened_at, t.trade_id
            """
        ).fetchall()
        return [
            FrozenTrade(
                trade_id=str(r["trade_id"]),
                signal_id=str(r["signal_id"]),
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
    finally:
        conn.close()
        tmp_path.unlink(missing_ok=True)


def _prepare_replay_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS signal_candidates (
        signal_id TEXT PRIMARY KEY, timestamp TEXT, direction TEXT,
        setup_type TEXT, confluence_score REAL, regime TEXT,
        reasons_json TEXT, features_json TEXT, schema_version TEXT, config_hash TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS executable_signals (
        signal_id TEXT PRIMARY KEY, timestamp TEXT, direction TEXT,
        entry_price REAL, stop_loss REAL, take_profit_1 REAL,
        take_profit_2 REAL, rr_ratio REAL, governance_notes_json TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS positions (
        position_id TEXT PRIMARY KEY, signal_id TEXT, symbol TEXT,
        direction TEXT, status TEXT, entry_price REAL, size REAL,
        leverage INTEGER, stop_loss REAL, take_profit_1 REAL,
        take_profit_2 REAL, opened_at TEXT, updated_at TEXT
    )"""
    )
    conn.execute("DROP TABLE IF EXISTS trade_log")
    conn.execute(
        """CREATE TABLE trade_log (
        trade_id TEXT PRIMARY KEY, signal_id TEXT, position_id TEXT,
        opened_at TEXT, closed_at TEXT, direction TEXT, regime TEXT,
        confluence_score REAL, entry_price REAL, exit_price REAL,
        size REAL, fees_total REAL, funding_paid REAL, slippage_bps_avg REAL,
        pnl_abs REAL, pnl_r REAL, mae REAL, mfe REAL, exit_reason TEXT,
        features_at_entry_json TEXT, schema_version TEXT, config_hash TEXT
    )"""
    )
    conn.execute("DELETE FROM signal_candidates")
    conn.execute("DELETE FROM executable_signals")
    conn.execute("DELETE FROM positions")
    conn.commit()


def load_or_replay_entries(
    store_path: Path,
    market_db_path: Path,
    cache_path: Path,
    *,
    refresh_replay: bool = False,
) -> list[FrozenTrade]:
    if cache_path.exists() and not refresh_replay:
        return load_entries_cache(cache_path)
    entries = replay_trial_00095_entries(store_path, market_db_path)
    save_entries_cache(entries, cache_path)
    return entries


def save_entries_cache(entries: list[FrozenTrade], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for entry in entries:
        item = asdict(entry)
        item["opened_at"] = _format_ts(entry.opened_at)
        item["closed_at"] = _format_ts(entry.closed_at)
        payload.append(item)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_entries_cache(path: Path) -> list[FrozenTrade]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        FrozenTrade(
            trade_id=str(item["trade_id"]),
            signal_id=str(item["signal_id"]),
            opened_at=_parse_ts(item["opened_at"]),
            closed_at=_parse_ts(item["closed_at"]),
            direction=str(item["direction"]),
            regime=str(item["regime"]),
            entry_price=float(item["entry_price"]),
            stop_loss=float(item["stop_loss"]),
            tp1=float(item["tp1"]),
            tp2=float(item["tp2"]),
            baseline_pnl_r=float(item["baseline_pnl_r"]),
            baseline_exit_reason=str(item["baseline_exit_reason"]),
        )
        for item in payload
    ]


def load_candles(market_db_path: Path, entries: list[FrozenTrade]) -> list[Candle]:
    if not entries:
        return []
    start = min(e.opened_at for e in entries) - timedelta(minutes=15)
    end = max(e.closed_at for e in entries) + timedelta(minutes=15)
    conn = sqlite3.connect(market_db_path)
    try:
        rows = conn.execute(
            """
            SELECT open_time, open, high, low, close
            FROM candles
            WHERE symbol = ? AND timeframe = '15m'
              AND open_time >= ? AND open_time <= ?
            ORDER BY open_time ASC
            """,
            (SYMBOL, _format_ts(start), _format_ts(end)),
        ).fetchall()
    finally:
        conn.close()
    return [Candle(_parse_ts(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in rows]


def simulate_variant(entry: FrozenTrade, candles_by_time: dict[datetime, Candle], variant: LossControlVariant) -> SimulatedTrade:
    duration = max(0, int((entry.closed_at - entry.opened_at).total_seconds() // 900))
    if variant.loss_r is None:
        return SimulatedTrade(entry, variant.variant_id, entry.baseline_pnl_r, entry.baseline_exit_reason, duration, False)
    if entry.risk <= 0:
        return SimulatedTrade(entry, variant.variant_id, entry.baseline_pnl_r, "invalid_risk", duration, False, True)

    threshold = loss_threshold_price(entry, variant.loss_r)
    missing = False
    current = entry.opened_at + timedelta(minutes=15)
    for offset in range(duration):
        candle = candles_by_time.get(current)
        if candle is None:
            missing = True
            current += timedelta(minutes=15)
            continue
        hit = candle.low <= threshold if entry.direction == "LONG" else candle.high >= threshold
        if hit:
            pnl_r = pnl_r_at_price(entry, threshold)
            return SimulatedTrade(
                entry=entry,
                variant_id=variant.variant_id,
                pnl_r=pnl_r,
                exit_reason=f"loss_control_{variant.loss_r:.2f}R",
                duration_bars=offset + 1,
                threshold_touched=True,
                missing_candles=missing,
            )
        current += timedelta(minutes=15)
    return SimulatedTrade(entry, variant.variant_id, entry.baseline_pnl_r, entry.baseline_exit_reason, duration, False, missing)


def loss_threshold_price(entry: FrozenTrade, loss_r: float) -> float:
    if entry.direction == "LONG":
        return entry.entry_price - loss_r * entry.risk
    return entry.entry_price + loss_r * entry.risk


def pnl_r_at_price(entry: FrozenTrade, exit_price: float, cost_mult: float = 1.0) -> float:
    raw = exit_price - entry.entry_price if entry.direction == "LONG" else entry.entry_price - exit_price
    fees = (entry.entry_price + exit_price) * FEE_RATE * cost_mult
    slippage = entry.entry_price * SLIPPAGE_BPS / 10000 * 2 * cost_mult
    return (raw - fees - slippage) / entry.risk if entry.risk else 0.0


def compute_metrics(trades: list[SimulatedTrade], baseline: list[SimulatedTrade], prior_artifact_count: int | None) -> dict[str, Any]:
    pnls = [t.pnl_r for t in trades]
    base_pnls = [t.pnl_r for t in baseline]
    deltas = [p - b for p, b in zip(pnls, base_pnls)]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    baseline_er = sum(base_pnls) / len(base_pnls) if base_pnls else 0.0
    er = sum(pnls) / len(pnls) if pnls else 0.0
    triggered = [t for t in trades if t.threshold_touched]
    stopped_winners = [t for t in triggered if t.entry.baseline_pnl_r > 0]
    saved_losers = [t for t in triggered if t.pnl_r > t.entry.baseline_pnl_r]
    harmed_trades = [t for t in triggered if t.pnl_r < t.entry.baseline_pnl_r]
    fold_deltas = fold_delta_er(trades, baseline)
    return {
        "trade_count": len(trades),
        "prior_artifact_count": prior_artifact_count or 0,
        "baseline_artifact_count_match": 1.0 if prior_artifact_count in (None, len(baseline)) else 0.0,
        "entry_count_match": 1.0 if len(trades) == len(baseline) else 0.0,
        "expectancy_r": er,
        "baseline_expectancy_r": baseline_er,
        "delta_er": er - baseline_er,
        "delta_er_pct": (er / baseline_er - 1.0) if baseline_er else 0.0,
        "profit_factor": profit_factor(pnls),
        "baseline_profit_factor": profit_factor(base_pnls),
        "pf_ratio_vs_baseline": profit_factor(pnls) / profit_factor(base_pnls) if profit_factor(base_pnls) else 0.0,
        "max_dd_r": max_drawdown(pnls),
        "baseline_max_dd_r": max_drawdown(base_pnls),
        "max_dd_ratio_vs_baseline": max_drawdown(pnls) / max_drawdown(base_pnls) if max_drawdown(base_pnls) else 999.0,
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
        "median_delta_r": median(deltas) if deltas else 0.0,
        "tail_10pct_r": tail_mean(pnls),
        "baseline_tail_10pct_r": tail_mean(base_pnls),
        "worst_trade_r": min(pnls) if pnls else 0.0,
        "baseline_worst_trade_r": min(base_pnls) if base_pnls else 0.0,
        "threshold_trigger_count": len(triggered),
        "threshold_trigger_share": len(triggered) / len(trades) if trades else 0.0,
        "saved_loser_count": len(saved_losers),
        "harmed_trade_count": len(harmed_trades),
        "stopped_winner_count": len(stopped_winners),
        "missing_candle_trade_count": sum(1 for t in trades if t.missing_candles),
        "folds_delta_er_positive": sum(1 for v in fold_deltas.values() if v > 0),
        "fold_count": len(fold_deltas),
        "top_trade_delta_share": top_delta_share(deltas),
        "er_at_2x_cost": cost_stress_er(trades, 2.0),
        "er_at_3x_cost": cost_stress_er(trades, 3.0),
        "exit_mix": dict(exit_mix(trades)),
    }


def profit_factor(pnls: list[float]) -> float:
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_loss = abs(sum(losses))
    return sum(wins) / gross_loss if gross_loss else 999.0


def max_drawdown(pnls: list[float]) -> float:
    peak = 0.0
    equity = 0.0
    drawdown = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown


def tail_mean(pnls: list[float]) -> float:
    if not pnls:
        return 0.0
    count = max(1, int(len(pnls) * 0.10))
    return sum(sorted(pnls)[:count]) / count


def fold_delta_er(trades: list[SimulatedTrade], baseline: list[SimulatedTrade]) -> dict[str, float]:
    folds: dict[str, list[float]] = defaultdict(list)
    base: dict[str, list[float]] = defaultdict(list)
    for trade, base_trade in zip(trades, baseline):
        dt = trade.entry.opened_at
        key = f"{dt.year}-H{1 if dt.month <= 6 else 2}"
        folds[key].append(trade.pnl_r)
        base[key].append(base_trade.pnl_r)
    return {key: (sum(vals) / len(vals)) - (sum(base[key]) / len(base[key])) for key, vals in folds.items() if base[key]}


def top_delta_share(deltas: list[float]) -> float:
    positives = [delta for delta in deltas if delta > 0]
    total = sum(positives)
    return max(positives) / total if positives and total > 0 else 0.0


def cost_stress_er(trades: list[SimulatedTrade], cost_mult: float) -> float:
    stressed = []
    for trade in trades:
        if trade.threshold_touched:
            threshold = loss_threshold_price(trade.entry, _loss_r_from_reason(trade.exit_reason))
            stressed.append(pnl_r_at_price(trade.entry, threshold, cost_mult))
        else:
            stressed.append(stress_existing_pnl(trade.entry, trade.pnl_r, cost_mult))
    return sum(stressed) / len(stressed) if stressed else 0.0


def _loss_r_from_reason(reason: str) -> float:
    # reason shape: loss_control_0.90R
    try:
        return float(reason.split("_")[-1].replace("R", ""))
    except (ValueError, IndexError):
        return 1.0


def stress_existing_pnl(entry: FrozenTrade, pnl_r: float, cost_mult: float) -> float:
    # Infer a gross-ish exit price from the reported R and reapply the cost model.
    sign = 1 if entry.direction == "LONG" else -1
    exit_price = entry.entry_price + sign * pnl_r * entry.risk
    return pnl_r_at_price(entry, exit_price, cost_mult)


def exit_mix(trades: list[SimulatedTrade]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for trade in trades:
        counts[trade.exit_reason] += 1
    return counts


def prior_artifact_count(path: Path) -> int | None:
    if not path.exists():
        return None
    return len(json.loads(path.read_text(encoding="utf-8")))


def run_validation(
    store_path: Path,
    market_db_path: Path,
    cache_path: Path,
    *,
    refresh_replay: bool = False,
) -> tuple[list[dict[str, Any]], list[FrozenTrade]]:
    entries = load_or_replay_entries(store_path, market_db_path, cache_path, refresh_replay=refresh_replay)
    candles = load_candles(market_db_path, entries)
    candles_by_time = {c.open_time: c for c in candles}
    baseline_variant = variants()[0]
    baseline_trades = [simulate_variant(entry, candles_by_time, baseline_variant) for entry in entries]
    expected_count = prior_artifact_count(PRIOR_TRADES_PATH)
    rows: list[dict[str, Any]] = []
    for variant in variants():
        trades = [simulate_variant(entry, candles_by_time, variant) for entry in entries]
        metrics = compute_metrics(trades, baseline_trades, expected_count)
        gates = [
            Gate("entry_count_match", "==", 1.0, "entry_count_match", "REQUIRED"),
            Gate("baseline_artifact_count_match", "==", 1.0, "baseline_artifact_count_match", "RECOMMENDED"),
            Gate("min_delta_er", ">=", 0.0, "delta_er", "RECOMMENDED"),
            Gate("pf_ratio", ">=", 1.0, "pf_ratio_vs_baseline", "RECOMMENDED"),
            Gate("max_dd_ratio", "<=", 1.0, "max_dd_ratio_vs_baseline", "RECOMMENDED"),
            Gate("folds_positive", ">=", 6, "folds_delta_er_positive", "RECOMMENDED"),
            Gate("top_delta_share", "<=", 0.35, "top_trade_delta_share", "RECOMMENDED"),
            Gate("cost_2x", ">=", 1.0, "er_at_2x_cost", "RECOMMENDED"),
            Gate("missing_candles", "==", 0, "missing_candle_trade_count", "REQUIRED"),
        ]
        evaluation = evaluate_gates(metrics, gates, experiment_id=variant.variant_id)
        rows.append(
            {
                "variant": variant,
                "trades": trades,
                "metrics": metrics,
                "gate_verdict": evaluation.verdict,
                "gates": [g.to_dict() for g in evaluation.gate_results],
            }
        )
    return rows, entries


def builder_verdict(rows: list[dict[str, Any]]) -> str:
    baseline = next(r for r in rows if r["variant"].variant_id == "BASELINE_REPLAY")
    if baseline["metrics"]["baseline_artifact_count_match"] != 1.0:
        return "INCONCLUSIVE_REPLAY_MISMATCH"
    candidates = [r for r in rows if r["variant"].variant_id != "BASELINE_REPLAY"]
    best = max(candidates, key=lambda r: r["metrics"]["delta_er"], default=None)
    if best is None or best["metrics"]["threshold_trigger_count"] == 0:
        return "FAIL_LOSS_CONTROL_NOT_EXECUTABLE"
    if (
        best["metrics"]["delta_er"] > 0
        and best["metrics"]["pf_ratio_vs_baseline"] >= 1.0
        and best["metrics"]["max_dd_ratio_vs_baseline"] <= 1.0
        and best["metrics"]["folds_delta_er_positive"] >= 6
        and best["metrics"]["er_at_2x_cost"] >= 1.0
    ):
        return "VALIDATION_PASS_FOR_FUTURE_EXIT_RESEARCH"
    return "FAIL_NO_ROBUST_IMPROVEMENT"


def generate_report(rows: list[dict[str, Any]], entries: list[FrozenTrade], report_path: Path) -> str:
    ranked = sorted(rows, key=lambda r: (r["metrics"]["delta_er"], -r["metrics"]["max_dd_ratio_vs_baseline"]), reverse=True)
    best = max([r for r in rows if r["variant"].variant_id != "BASELINE_REPLAY"], key=lambda r: r["metrics"]["delta_er"])
    verdict = builder_verdict(rows)
    baseline = next(r for r in rows if r["variant"].variant_id == "BASELINE_REPLAY")
    base_metrics = baseline["metrics"]
    lines = [
        "# Trial-00095 Loss-Control Intrabar Validation",
        "",
        "**Milestone:** `TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION_V1`",
        "**Status:** READY_FOR_AUDIT",
        f"**Builder verdict:** `{verdict}`",
        "**Scope:** Research Lab offline validation only; frozen trial-00095 entries; no runtime/core changes.",
        "",
        "## Methodology",
        "",
        "- Replays trial-00095 exact parameters to freeze baseline entries and original entry/stop geometry.",
        "- Applies predeclared loss-side hard stops to the same frozen entries only.",
        "- If a loss-control threshold is touched on any post-entry 15m candle before the original baseline close, the variant exits there.",
        "- The entry candle itself is excluded because BacktestRunner opens the position after close checks for that snapshot.",
        "- If the threshold is not touched, the original baseline trade outcome is preserved, including winner tail behavior.",
        "- This does not add entries, change entry filters, cap winners, alter TP logic, or approve deployment.",
        "- Intrabar assumption is conservative: a touched loss-control threshold is treated as executable before any later recovery inside the same candle.",
        "",
        "## Baseline Control",
        "",
        f"- Frozen replay entries: {len(entries)}",
        f"- Prior diagnostic artifact entries: {base_metrics['prior_artifact_count']}",
        f"- Baseline artifact count match: {base_metrics['baseline_artifact_count_match']:.0f}",
        f"- Baseline ER: {base_metrics['baseline_expectancy_r']:.3f}",
        f"- Baseline PF: {base_metrics['baseline_profit_factor']:.2f}",
        f"- Baseline max DD: {base_metrics['baseline_max_dd_r']:.2f}R",
        "",
        "## Variant Results",
        "",
        "| Variant | Gate Verdict | Trades | ER | Delta ER | Delta % | PF | DD Ratio | Triggered | Saved Losers | Stopped Winners | Folds+ | 2x ER | Missing Candles |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ranked:
        m = row["metrics"]
        lines.append(
            f"| `{row['variant'].variant_id}` | `{row['gate_verdict']}` | {m['trade_count']} | "
            f"{m['expectancy_r']:.3f} | {m['delta_er']:+.3f} | {m['delta_er_pct']:+.1%} | "
            f"{m['profit_factor']:.2f} | {m['max_dd_ratio_vs_baseline']:.2f} | "
            f"{m['threshold_trigger_count']} | {m['saved_loser_count']} | {m['stopped_winner_count']} | "
            f"{m['folds_delta_er_positive']}/{m['fold_count']} | {m['er_at_2x_cost']:.3f} | {m['missing_candle_trade_count']} |"
        )
    lines += [
        "",
        "## Builder Interpretation",
        "",
        f"Best loss-control variant by paired delta ER: `{best['variant'].variant_id}`.",
    ]
    if verdict == "VALIDATION_PASS_FOR_FUTURE_EXIT_RESEARCH":
        lines.append(
            "The loss-control effect survives this conservative 15m intrabar validation as a future exit-policy research hypothesis. "
            "It is still not promotion-ready; runtime design, exact execution semantics, paper validation, and Claude audit would be separate milestones."
        )
    elif verdict == "INCONCLUSIVE_REPLAY_MISMATCH":
        lines.append(
            "The replay entry population does not match the prior diagnostic artifact count. Variant results are reported for transparency, "
            "but the milestone should be treated as inconclusive until the baseline mismatch is resolved."
        )
    else:
        lines.append(
            "The executable intrabar validation does not provide robust enough evidence to continue toward exit-policy design."
        )
    lines += [
        "",
        "## Audit Questions",
        "",
        "1. Does baseline replay faithfully reconstruct trial-00095 entry count and entry/stop geometry?",
        "2. Are entries frozen before variants are applied?",
        "3. Is R computed from original entry/stop distance rather than realized loss?",
        "4. Does each variant preserve baseline winners unless the loss threshold was touched first?",
        "5. Are missing candles reported explicitly and treated as blocking if present?",
        "6. Are all artifacts Research Lab/docs only with no runtime/core/settings changes?",
        "7. Does the report avoid calling the result deployment-ready?",
    ]
    report = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=STORE_PATH)
    parser.add_argument("--market-db", type=Path, default=MARKET_DB_PATH)
    parser.add_argument("--entry-cache", type=Path, default=ENTRY_CACHE_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--refresh-replay", action="store_true")
    args = parser.parse_args()
    rows, entries = run_validation(args.store, args.market_db, args.entry_cache, refresh_replay=args.refresh_replay)
    print(generate_report(rows, entries, args.report))
    print("git_commit", subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip())


if __name__ == "__main__":
    main()
