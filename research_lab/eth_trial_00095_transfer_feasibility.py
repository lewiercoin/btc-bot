#!/usr/bin/env python3
"""ETH transfer feasibility replay for frozen trial-00095 parameters."""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import sqlite3
import statistics
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig, BacktestRunner
from backtest.performance import PerformanceReport
from research_lab.settings_adapter import build_candidate_settings
from settings import AppSettings, load_settings


TRIAL_00095_ID = "optuna-default-v3-trial-00095"
SYMBOL = "ETHUSDT"
START = "2022-01-01"
END = "2026-03-28"
DEFAULT_ETH_DB = Path("research_lab/snapshots/ethusdt_2022_2026_dataset_v1.db")
DEFAULT_STORE = Path("research_lab/research_lab.db.v3")
DEFAULT_REPORT = Path("docs/analysis/ETH_TRIAL_00095_TRANSFER_FEASIBILITY_2026-05-19.md")


@dataclass(slots=True, frozen=True)
class TransferGates:
    min_trades: int = 20
    min_expectancy_r: float = 1.0
    min_profit_factor: float = 1.5
    max_drawdown_pct: float = 0.12
    min_positive_folds: int = 2
    min_2x_cost_expectancy_r: float = 0.75


@dataclass(slots=True)
class FoldResult:
    label: str
    start: str
    end: str
    trades: int
    expectancy_r: float
    profit_factor: float
    max_drawdown_pct: float
    win_rate: float


def load_trial_params(store_path: Path, trial_id: str = TRIAL_00095_ID) -> dict[str, Any]:
    conn = sqlite3.connect(str(store_path))
    try:
        row = conn.execute("SELECT params_json FROM trials WHERE trial_id = ?", (trial_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise RuntimeError(f"Trial {trial_id!r} not found in {store_path}")
    payload = json.loads(row[0])
    if not isinstance(payload, dict):
        raise RuntimeError(f"Trial {trial_id!r} params_json is not an object")
    return payload


def build_eth_trial_settings(base_settings: AppSettings, trial_params: dict[str, Any]) -> AppSettings:
    """Build trial-00095 settings with symbol changed only inside research."""

    candidate = build_candidate_settings(base_settings, trial_params)
    strategy = dataclasses.replace(candidate.strategy, symbol=SYMBOL)
    return dataclasses.replace(candidate, strategy=strategy)


def prepare_replay_db(source_db: Path, target_db: Path) -> None:
    """Copy ETH dataset and add replay-only compatibility tables.

    The source dataset remains read-only. The temp DB receives derived 1h candles
    from 15m bars plus empty optional-context tables expected by ReplayLoader.
    """

    shutil.copy2(str(source_db), str(target_db))
    conn = sqlite3.connect(str(target_db))
    try:
        _ensure_runtime_tables(conn)
        _derive_1h_candles(conn, symbol=SYMBOL)
        conn.commit()
    finally:
        conn.close()


def _ensure_runtime_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS force_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            event_time TEXT NOT NULL,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            price REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS daily_external_bias (
            date TEXT PRIMARY KEY,
            etf_bias_5d REAL,
            dxy_close REAL
        );
        CREATE TABLE IF NOT EXISTS signal_candidates (
            signal_id TEXT PRIMARY KEY,
            timestamp TEXT,
            direction TEXT,
            setup_type TEXT,
            confluence_score REAL,
            regime TEXT,
            reasons_json TEXT,
            features_json TEXT,
            schema_version TEXT,
            config_hash TEXT
        );
        CREATE TABLE IF NOT EXISTS executable_signals (
            signal_id TEXT PRIMARY KEY,
            timestamp TEXT,
            direction TEXT,
            entry_price REAL,
            stop_loss REAL,
            take_profit_1 REAL,
            take_profit_2 REAL,
            rr_ratio REAL,
            governance_notes_json TEXT
        );
        CREATE TABLE IF NOT EXISTS positions (
            position_id TEXT PRIMARY KEY,
            signal_id TEXT,
            symbol TEXT,
            direction TEXT,
            status TEXT,
            entry_price REAL,
            size REAL,
            leverage INTEGER,
            stop_loss REAL,
            take_profit_1 REAL,
            take_profit_2 REAL,
            opened_at TEXT,
            updated_at TEXT
        );
        DROP TABLE IF EXISTS trade_log;
        CREATE TABLE trade_log (
            trade_id TEXT PRIMARY KEY,
            signal_id TEXT,
            position_id TEXT,
            opened_at TEXT,
            closed_at TEXT,
            direction TEXT,
            regime TEXT,
            confluence_score REAL,
            entry_price REAL,
            exit_price REAL,
            size REAL,
            fees_total REAL,
            funding_paid REAL,
            slippage_bps_avg REAL,
            pnl_abs REAL,
            pnl_r REAL,
            mae REAL,
            mfe REAL,
            exit_reason TEXT,
            features_at_entry_json TEXT,
            schema_version TEXT,
            config_hash TEXT
        );
        """
    )


def _derive_1h_candles(conn: sqlite3.Connection, *, symbol: str) -> int:
    conn.execute("DELETE FROM candles WHERE symbol = ? AND timeframe = '1h'", (symbol,))
    rows = conn.execute(
        """
        SELECT
            substr(open_time, 1, 13) || ':00:00+00:00' AS bucket,
            COUNT(*) AS n,
            MIN(open_time) AS first_time,
            MAX(open_time) AS last_time,
            MAX(high) AS high,
            MIN(low) AS low,
            SUM(volume) AS volume
        FROM candles
        WHERE symbol = ? AND timeframe = '15m'
        GROUP BY bucket
        HAVING n = 4
        ORDER BY bucket
        """,
        (symbol,),
    ).fetchall()
    payload: list[tuple[Any, ...]] = []
    for bucket, _n, first_time, last_time, high, low, volume in rows:
        open_row = conn.execute(
            "SELECT open FROM candles WHERE symbol=? AND timeframe='15m' AND open_time=?",
            (symbol, first_time),
        ).fetchone()
        close_row = conn.execute(
            "SELECT close FROM candles WHERE symbol=? AND timeframe='15m' AND open_time=?",
            (symbol, last_time),
        ).fetchone()
        if not open_row or not close_row:
            continue
        payload.append((symbol, "1h", bucket, float(open_row[0]), float(high), float(low), float(close_row[0]), float(volume)))
    conn.executemany(
        """
        INSERT OR REPLACE INTO candles(symbol, timeframe, open_time, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        payload,
    )
    return len(payload)


def run_replay(
    *,
    source_db: Path,
    store_path: Path,
    start: str,
    end: str,
    fee_multiplier: float,
) -> tuple[PerformanceReport, list[Any], str]:
    trial_params = load_trial_params(store_path)
    settings = build_eth_trial_settings(load_settings(profile="research"), trial_params)
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        prepare_replay_db(source_db, tmp_path)
        conn = sqlite3.connect(str(tmp_path))
        conn.row_factory = sqlite3.Row
        try:
            runner = BacktestRunner(conn, settings=settings)
            config = BacktestConfig(
                start_date=start,
                end_date=end,
                symbol=SYMBOL,
                initial_equity=10_000.0,
                fee_rate_maker=0.0004 * fee_multiplier,
                fee_rate_taker=0.0004 * fee_multiplier,
            )
            result = runner.run(config)
            return result.performance, result.trades, settings.config_hash
        finally:
            conn.close()
    finally:
        tmp_path.unlink(missing_ok=True)
        tmp_path.with_name(tmp_path.name + "-wal").unlink(missing_ok=True)
        tmp_path.with_name(tmp_path.name + "-shm").unlink(missing_ok=True)


def fold_windows() -> list[tuple[str, str, str]]:
    return [
        ("2022", "2022-01-01", "2023-01-01"),
        ("2023", "2023-01-01", "2024-01-01"),
        ("2024", "2024-01-01", "2025-01-01"),
        ("2025_to_2026Q1", "2025-01-01", END),
    ]


def build_fold_result(label: str, start: str, end: str, performance: PerformanceReport) -> FoldResult:
    return FoldResult(
        label=label,
        start=start,
        end=end,
        trades=int(performance.trades_count),
        expectancy_r=float(performance.expectancy_r),
        profit_factor=float(performance.profit_factor),
        max_drawdown_pct=float(performance.max_drawdown_pct),
        win_rate=float(performance.win_rate),
    )


def evaluate_gates(
    *,
    full: PerformanceReport,
    cost_2x: PerformanceReport,
    folds: list[FoldResult],
    gates: TransferGates,
) -> dict[str, dict[str, Any]]:
    positive_folds = sum(1 for fold in folds if fold.expectancy_r > 1.0 and fold.trades >= 3)
    return {
        "min_trades": {"value": full.trades_count, "threshold": gates.min_trades, "pass": full.trades_count >= gates.min_trades},
        "min_er": {"value": full.expectancy_r, "threshold": gates.min_expectancy_r, "pass": full.expectancy_r >= gates.min_expectancy_r},
        "min_pf": {"value": full.profit_factor, "threshold": gates.min_profit_factor, "pass": full.profit_factor >= gates.min_profit_factor},
        "max_dd": {"value": full.max_drawdown_pct, "threshold": gates.max_drawdown_pct, "pass": full.max_drawdown_pct <= gates.max_drawdown_pct},
        "wf_positive_folds": {"value": positive_folds, "threshold": gates.min_positive_folds, "pass": positive_folds >= gates.min_positive_folds},
        "cost_2x_er": {"value": cost_2x.expectancy_r, "threshold": gates.min_2x_cost_expectancy_r, "pass": cost_2x.expectancy_r >= gates.min_2x_cost_expectancy_r},
    }


def builder_verdict(gates: dict[str, dict[str, Any]], *, full_trades: int) -> str:
    if full_trades == 0:
        return "HYPOTHESIS_FAILED_NO_SIGNALS"
    if all(item["pass"] for item in gates.values()):
        return "PASS_TRANSFER_CANDIDATE_FOR_AUDIT"
    failed = [name for name, item in gates.items() if not item["pass"]]
    if "min_trades" in failed and len(failed) == 1:
        return "INCONCLUSIVE_LOW_FREQUENCY"
    return "HYPOTHESIS_FAILED"


def direction_breakdown(trades: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trade in trades:
        counts[trade.direction] = counts.get(trade.direction, 0) + 1
    return counts


def regime_breakdown(trades: list[Any]) -> dict[str, dict[str, float]]:
    by_regime: dict[str, list[float]] = {}
    for trade in trades:
        by_regime.setdefault(str(trade.regime), []).append(float(trade.pnl_r))
    return {
        regime: {
            "trades": len(values),
            "er": statistics.mean(values) if values else 0.0,
            "win_rate": sum(1 for value in values if value > 0) / max(len(values), 1),
        }
        for regime, values in sorted(by_regime.items())
    }


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    full = payload["full"]
    gates = payload["gates"]
    folds = payload["folds"]
    cost = payload["cost_sensitivity"]
    verdict = payload["builder_verdict"]

    lines = [
        "# ETH Trial-00095 Transfer Feasibility",
        "",
        "**Milestone:** `ETH_TRIAL_00095_TRANSFER_FEASIBILITY_V1`",
        f"**Status:** `{verdict}`",
        "**Scope:** Research Lab strategy transfer only; frozen BTC trial-00095 parameters replayed on audited ETH dataset; no runtime/core changes.",
        "",
        "## Methodology",
        "",
        f"- Symbol: `{payload['symbol']}`",
        f"- Dataset: `{payload['source_db']}`",
        f"- Trial params: `{payload['trial_id']}` from `{payload['store_path']}`",
        f"- Window: {payload['start']} to {payload['end']} exclusive",
        "- 1h candles are derived inside a temporary replay DB from complete 15m ETH candles.",
        "- `force_orders` and `daily_external_bias` are empty optional-context compatibility tables for this replay.",
        "- No parameter search, no threshold tuning, no post-hoc rescue.",
        "",
        "## Full Replay",
        "",
        "| Trades | ER | PF | Win Rate | Max DD | PnL R Sum | Fees |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {full['trades_count']} | {full['expectancy_r']:.3f} | {full['profit_factor']:.2f} | "
            f"{full['win_rate']:.1%} | {full['max_drawdown_pct']:.2%} | "
            f"{full['pnl_r_sum']:.2f} | {full['total_fees']:.2f} |"
        ),
        "",
        "## Gates",
        "",
        "| Gate | Value | Threshold | Result |",
        "|---|---:|---:|---|",
    ]
    for name, item in gates.items():
        result = "PASS" if item["pass"] else "FAIL"
        lines.append(f"| {name} | {item['value']:.4g} | {item['threshold']:.4g} | {result} |")

    lines.extend(
        [
            "",
            "## Walk-Forward Stability",
            "",
            "| Fold | Window | Trades | ER | PF | Win Rate | Max DD |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for fold in folds:
        lines.append(
            f"| {fold['label']} | {fold['start']} to {fold['end']} | {fold['trades']} | "
            f"{fold['expectancy_r']:.3f} | {fold['profit_factor']:.2f} | "
            f"{fold['win_rate']:.1%} | {fold['max_drawdown_pct']:.2%} |"
        )

    lines.extend(
        [
            "",
            "## Cost Sensitivity",
            "",
            "| Cost Multiplier | Trades | ER | PF | Max DD |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for label, metrics in cost.items():
        lines.append(
            f"| {label} | {metrics['trades_count']} | {metrics['expectancy_r']:.3f} | "
            f"{metrics['profit_factor']:.2f} | {metrics['max_drawdown_pct']:.2%} |"
        )

    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            f"- Direction breakdown: `{json.dumps(payload['direction_breakdown'], sort_keys=True)}`",
            f"- Regime breakdown: `{json.dumps(payload['regime_breakdown'], sort_keys=True)}`",
            "",
            "## Interpretation",
            "",
            _interpretation(verdict),
            "",
            "## Audit Questions",
            "",
            "1. Did the milestone preserve research-only scope and avoid runtime/core/settings changes?",
            "2. Were BTC trial-00095 parameters frozen except for the research-only symbol transfer to ETHUSDT?",
            "3. Is temporary replay DB preparation deterministic and non-mutating for the source ETH dataset?",
            "4. Are gates and walk-forward windows predeclared and not relaxed after results?",
            "5. Is the builder verdict supported by the metrics?",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    report_path.write_text(text, encoding="utf-8")
    return text


def _interpretation(verdict: str) -> str:
    if verdict == "PASS_TRANSFER_CANDIDATE_FOR_AUDIT":
        return (
            "Frozen trial-00095 shows decision-grade transfer evidence on ETH. "
            "This is not runtime approval; it only supports a later audited multi-asset research path."
        )
    if verdict == "INCONCLUSIVE_LOW_FREQUENCY":
        return "ETH generated too few signals for a decision-grade transfer conclusion."
    if verdict == "HYPOTHESIS_FAILED_NO_SIGNALS":
        return "The BTC sweep/reclaim configuration did not generate ETH signals in the replay window."
    return "Frozen trial-00095 did not transfer to ETH under the predeclared gates. Do not tune thresholds inside this milestone."


def _perf_dict(report: PerformanceReport) -> dict[str, Any]:
    return asdict(report)


def run_analysis(
    *,
    source_db: Path,
    store_path: Path,
    report_path: Path,
    start: str,
    end: str,
) -> dict[str, Any]:
    full_perf, full_trades, config_hash = run_replay(
        source_db=source_db,
        store_path=store_path,
        start=start,
        end=end,
        fee_multiplier=1.0,
    )
    cost_15_perf, _cost_15_trades, _ = run_replay(
        source_db=source_db,
        store_path=store_path,
        start=start,
        end=end,
        fee_multiplier=1.5,
    )
    cost_2_perf, _cost_2_trades, _ = run_replay(
        source_db=source_db,
        store_path=store_path,
        start=start,
        end=end,
        fee_multiplier=2.0,
    )

    fold_results: list[FoldResult] = []
    for label, fold_start, fold_end in fold_windows():
        perf, _trades, _ = run_replay(
            source_db=source_db,
            store_path=store_path,
            start=fold_start,
            end=fold_end,
            fee_multiplier=1.0,
        )
        fold_results.append(build_fold_result(label, fold_start, fold_end, perf))

    gates = TransferGates()
    gate_results = evaluate_gates(full=full_perf, cost_2x=cost_2_perf, folds=fold_results, gates=gates)
    verdict = builder_verdict(gate_results, full_trades=int(full_perf.trades_count))
    payload = {
        "milestone": "ETH_TRIAL_00095_TRANSFER_FEASIBILITY_V1",
        "builder_verdict": verdict,
        "symbol": SYMBOL,
        "source_db": str(source_db),
        "store_path": str(store_path),
        "trial_id": TRIAL_00095_ID,
        "config_hash": config_hash,
        "start": start,
        "end": end,
        "full": _perf_dict(full_perf),
        "cost_sensitivity": {
            "1.0x": _perf_dict(full_perf),
            "1.5x": _perf_dict(cost_15_perf),
            "2.0x": _perf_dict(cost_2_perf),
        },
        "folds": [asdict(fold) for fold in fold_results],
        "gates": gate_results,
        "direction_breakdown": direction_breakdown(full_trades),
        "regime_breakdown": regime_breakdown(full_trades),
        "gate_contract": asdict(gates),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    generate_report(payload, report_path)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, default=DEFAULT_ETH_DB)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--start", default=START)
    parser.add_argument("--end", default=END)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_analysis(
        source_db=args.source_db,
        store_path=args.store,
        report_path=args.report,
        start=args.start,
        end=args.end,
    )
    print(json.dumps({"verdict": payload["builder_verdict"], "full": payload["full"], "report": str(args.report)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
