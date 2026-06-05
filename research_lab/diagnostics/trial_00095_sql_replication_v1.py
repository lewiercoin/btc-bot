"""Independent SQL replication for trial-00095 accepted trades.

This module intentionally does not import strategy, execution, core, or the
prior trial-00095 attribution diagnostic. It consumes frozen accepted-trade
artifacts and BTCUSDT 15m candles, then computes a mechanical stratified
reproduction verdict.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRADES_PATH = PROJECT_ROOT / "research_lab" / "analysis_output" / "trial_00095_trades.json"
DEFAULT_ENTRIES_PATH = PROJECT_ROOT / "research_lab" / "analysis_output" / "trial_00095_intrabar_frozen_entries.json"
DEFAULT_SNAPSHOT_DB_PATH = PROJECT_ROOT / "research_lab" / "snapshots" / "replay-run13-regime-aware-trial-00063.db"
DEFAULT_JSON_PATH = PROJECT_ROOT / "research_lab" / "reports" / "trial_00095_sql_replication_v1.json"

SYMBOL = "BTCUSDT"
TIMEFRAME = "15m"
ROUND_TRIP_COST_PCT = 0.0011
PEARSON_GATE = 0.95

BASELINE = {
    "count": 274,
    "expectancy_r": 2.1211338666525608,
    "profit_factor": 4.216455510596996,
    "win_rate": 0.5656934306569343,
}


@dataclass(frozen=True, slots=True)
class Candle:
    index: int
    open_time: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True, slots=True)
class TradeRecord:
    trade_id: str
    opened_at: datetime
    direction: str
    regime: str
    pnl_r: float
    exit_reason: str


@dataclass(frozen=True, slots=True)
class EntryRecord:
    trade_id: str
    signal_id: str
    opened_at: datetime
    closed_at: datetime | None
    direction: str
    regime: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    baseline_pnl_r: float
    baseline_exit_reason: str

    @property
    def risk_abs(self) -> float:
        return abs(self.entry_price - self.stop_loss)

    @property
    def risk_pct(self) -> float:
        return self.risk_abs / self.entry_price if self.entry_price else 0.0


@dataclass(frozen=True, slots=True)
class ReplicatedTrade:
    trade_id: str
    opened_at: str
    direction: str
    baseline_exit_reason: str
    replicated_exit_reason: str
    baseline_pnl_r: float
    replicated_pnl_r: float | None
    absolute_delta_r: float | None
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    exit_time: str | None
    exit_price: float | None
    simulation_note: str


def parse_ts(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_trades(path: Path) -> list[TradeRecord]:
    rows = _read_json(path)
    return [
        TradeRecord(
            trade_id=str(row["trade_id"]),
            opened_at=parse_ts(row["opened_at"]),
            direction=str(row["direction"]).upper(),
            regime=str(row.get("regime", "")),
            pnl_r=float(row["pnl_r"]),
            exit_reason=str(row.get("exit_reason", "")).upper(),
        )
        for row in rows
    ]


def load_entries(path: Path) -> dict[str, EntryRecord]:
    rows = _read_json(path)
    return {
        str(row["trade_id"]): EntryRecord(
            trade_id=str(row["trade_id"]),
            signal_id=str(row["signal_id"]),
            opened_at=parse_ts(row["opened_at"]),
            closed_at=parse_ts(row["closed_at"]) if row.get("closed_at") else None,
            direction=str(row["direction"]).upper(),
            regime=str(row.get("regime", "")),
            entry_price=float(row["entry_price"]),
            stop_loss=float(row["stop_loss"]),
            tp1=float(row["tp1"]),
            tp2=float(row["tp2"]),
            baseline_pnl_r=float(row["baseline_pnl_r"]),
            baseline_exit_reason=str(row["baseline_exit_reason"]).upper(),
        )
        for row in rows
    }


def inspect_artifact_fields(trades_path: Path, entries_path: Path) -> dict[str, Any]:
    trade_rows = _read_json(trades_path)
    entry_rows = _read_json(entries_path)
    trade_keys = sorted({key for row in trade_rows for key in row})
    entry_keys = sorted({key for row in entry_rows for key in row})
    all_keys = set(trade_keys) | set(entry_keys)
    trail_like = sorted(key for key in all_keys if "trail" in key.lower())
    required_closed_form = {
        "trail_activation_price",
        "trail_distance",
        "trail_step",
        "partial_fill_fraction",
    }
    present_required = sorted(required_closed_form & all_keys)
    missing_required = sorted(required_closed_form - all_keys)
    derivable = bool(required_closed_form <= all_keys)
    return {
        "trade_count": len(trade_rows),
        "entry_count": len(entry_rows),
        "trade_fields": trade_keys,
        "entry_fields": entry_keys,
        "trail_like_fields": trail_like,
        "required_closed_form_trail_fields": sorted(required_closed_form),
        "present_closed_form_trail_fields": present_required,
        "missing_closed_form_trail_fields": missing_required,
        "closed_form_trail_rule_derivable": derivable,
        "classification": "DERIVABLE" if derivable else "NOT_DERIVABLE_FROM_FROZEN_ARTIFACT",
        "note": (
            "Closed-form TP_TRAIL reproduction requires explicit activation, distance, step, "
            "and sizing fields; absent fields force stratified verdict handling."
        ),
    }


def load_candles(db_path: Path, *, symbol: str = SYMBOL, timeframe: str = TIMEFRAME) -> list[Candle]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            """
            SELECT open_time, open, high, low, close
            FROM candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY open_time ASC
            """,
            (symbol, timeframe),
        ).fetchall()
    return [
        Candle(
            index=idx,
            open_time=parse_ts(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
        )
        for idx, row in enumerate(rows)
    ]


def _r_value(entry: EntryRecord, exit_price: float, direction: str) -> float:
    if entry.risk_abs <= 0 or entry.risk_pct <= 0:
        raise ValueError(f"Invalid risk for {entry.trade_id}")
    if direction == "LONG":
        price_r = (exit_price - entry.entry_price) / entry.risk_abs
    else:
        price_r = (entry.entry_price - exit_price) / entry.risk_abs
    return price_r - (ROUND_TRIP_COST_PCT / entry.risk_pct)


def _hit_stop(candle: Candle, entry: EntryRecord, direction: str) -> bool:
    return candle.low <= entry.stop_loss if direction == "LONG" else candle.high >= entry.stop_loss


def _hit_tp2(candle: Candle, entry: EntryRecord, direction: str) -> bool:
    return candle.high >= entry.tp2 if direction == "LONG" else candle.low <= entry.tp2


def simulate_trade(
    trade: TradeRecord,
    entry: EntryRecord,
    candles: list[Candle],
    by_time: dict[datetime, int],
) -> ReplicatedTrade:
    entry_idx = by_time.get(entry.opened_at)
    if entry_idx is None:
        return _failed_trade(trade, entry, "ENTRY_TIMESTAMP_NOT_FOUND")
    close_idx = by_time.get(entry.closed_at) if entry.closed_at is not None else None
    end_idx = close_idx if close_idx is not None else len(candles) - 1
    direction = trade.direction
    # `opened_at` is the frozen execution timestamp, so the entry candle's
    # high/low belongs to the post-entry trade path.
    for idx in range(entry_idx, min(end_idx, len(candles) - 1) + 1):
        candle = candles[idx]
        stop_hit = _hit_stop(candle, entry, direction)
        tp2_hit = _hit_tp2(candle, entry, direction)
        if stop_hit:
            return _replicated_trade(
                trade,
                entry,
                replicated_exit_reason="SL",
                exit_time=candle.open_time,
                exit_price=entry.stop_loss,
                note="STOP_LOSS_CROSSING; pessimistic order if stop and TP2 hit same candle",
            )
        if tp2_hit:
            return _replicated_trade(
                trade,
                entry,
                replicated_exit_reason="TP2_PROXY",
                exit_time=candle.open_time,
                exit_price=entry.tp2,
                note="TP2_PROXY_USED; closed-form TP_TRAIL rule not available in frozen artifact",
            )
    if close_idx is not None and 0 <= close_idx < len(candles):
        candle = candles[close_idx]
        return _replicated_trade(
            trade,
            entry,
            replicated_exit_reason="CLOSE_TIME_PROXY",
            exit_time=candle.open_time,
            exit_price=candle.close,
            note="CLOSED_AT_CANDLE_CLOSE_PROXY; no SL/TP2 crossing before recorded close",
        )
    return _failed_trade(trade, entry, "NO_EXIT_CONDITION_FOUND")


def _replicated_trade(
    trade: TradeRecord,
    entry: EntryRecord,
    *,
    replicated_exit_reason: str,
    exit_time: datetime,
    exit_price: float,
    note: str,
) -> ReplicatedTrade:
    replicated = _r_value(entry, exit_price, trade.direction)
    return ReplicatedTrade(
        trade_id=trade.trade_id,
        opened_at=trade.opened_at.isoformat(),
        direction=trade.direction,
        baseline_exit_reason=trade.exit_reason,
        replicated_exit_reason=replicated_exit_reason,
        baseline_pnl_r=trade.pnl_r,
        replicated_pnl_r=replicated,
        absolute_delta_r=abs(trade.pnl_r - replicated),
        entry_price=entry.entry_price,
        stop_loss=entry.stop_loss,
        tp1=entry.tp1,
        tp2=entry.tp2,
        exit_time=exit_time.isoformat(),
        exit_price=exit_price,
        simulation_note=note,
    )


def _failed_trade(trade: TradeRecord, entry: EntryRecord, note: str) -> ReplicatedTrade:
    return ReplicatedTrade(
        trade_id=trade.trade_id,
        opened_at=trade.opened_at.isoformat(),
        direction=trade.direction,
        baseline_exit_reason=trade.exit_reason,
        replicated_exit_reason="NOT_REPLICATED",
        baseline_pnl_r=trade.pnl_r,
        replicated_pnl_r=None,
        absolute_delta_r=None,
        entry_price=entry.entry_price,
        stop_loss=entry.stop_loss,
        tp1=entry.tp1,
        tp2=entry.tp2,
        exit_time=None,
        exit_price=None,
        simulation_note=note,
    )


def profit_factor(values: Iterable[float]) -> float:
    vals = list(values)
    gross_profit = sum(value for value in vals if value > 0)
    gross_loss = abs(sum(value for value in vals if value < 0))
    if gross_loss == 0:
        return 999.0 if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def max_drawdown(values: Iterable[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def metrics(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "expectancy_r": None,
            "profit_factor": None,
            "win_rate": None,
            "median_r": None,
            "total_r": 0.0,
            "max_drawdown_r": 0.0,
        }
    return {
        "count": len(values),
        "expectancy_r": mean(values),
        "profit_factor": profit_factor(values),
        "win_rate": sum(1 for value in values if value > 0) / len(values),
        "median_r": median(values),
        "total_r": sum(values),
        "max_drawdown_r": max_drawdown(values),
    }


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mx = mean(xs)
    my = mean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return 1.0 if all(abs(x - y) < 1e-12 for x, y in zip(xs, ys)) else None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(vx * vy)


def correlation_for(rows: list[ReplicatedTrade], exit_reason: str | None = None) -> dict[str, Any]:
    subset = [
        row
        for row in rows
        if row.replicated_pnl_r is not None
        and (exit_reason is None or row.baseline_exit_reason == exit_reason)
    ]
    baseline = [row.baseline_pnl_r for row in subset]
    replicated = [float(row.replicated_pnl_r) for row in subset if row.replicated_pnl_r is not None]
    return {
        "exit_reason": exit_reason or "ALL",
        "count": len(subset),
        "pearson": pearson(baseline, replicated),
    }


def acceptance_failures(metrics_row: dict[str, Any], full_corr: float | None) -> list[str]:
    failures: list[str] = []
    if abs((metrics_row.get("count") or 0) - BASELINE["count"]) > 2:
        failures.append("count_outside_plus_minus_2")
    er = metrics_row.get("expectancy_r")
    if er is None or not (1.965 <= float(er) <= 2.227):
        failures.append("er_outside_plus_minus_5pct")
    pf = metrics_row.get("profit_factor")
    if pf is None or not (4.005 <= float(pf) <= 4.427):
        failures.append("pf_outside_plus_minus_5pct")
    wr = metrics_row.get("win_rate")
    if wr is None or not (0.535 <= float(wr) <= 0.595):
        failures.append("wr_outside_plus_minus_3pp")
    if full_corr is None or full_corr < PEARSON_GATE:
        failures.append("full_pearson_below_0_95")
    return failures


def stratified_verdict(
    *,
    metrics_row: dict[str, Any],
    full_corr: float | None,
    sl_corr: float | None,
    trail_corr: float | None,
) -> dict[str, Any]:
    failures = acceptance_failures(metrics_row, full_corr)
    if sl_corr is None or sl_corr < PEARSON_GATE:
        return {
            "verdict": "VALIDATED_EDGE_NOT_REPRODUCIBLE",
            "reason": "SL-subset Pearson below 0.95; unambiguous stop-loss trades failed.",
            "failing_checks": sorted(set(failures + ["sl_subset_pearson_below_0_95"])),
        }
    if trail_corr is None or trail_corr < PEARSON_GATE:
        return {
            "verdict": "PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL",
            "reason": "SL subset reproduced but TP_TRAIL subset did not; frozen artifact lacks closed-form trail rule.",
            "failing_checks": sorted(set(failures + ["tp_trail_subset_pearson_below_0_95"])),
        }
    if failures:
        return {
            "verdict": "VALIDATED_EDGE_NOT_REPRODUCIBLE",
            "reason": "Population metrics failed despite passing subset correlations.",
            "failing_checks": failures,
        }
    return {
        "verdict": "FULL_REPRODUCTION",
        "reason": "Full, SL, and TP_TRAIL correlations pass and population metrics are inside frozen bounds.",
        "failing_checks": [],
    }


def run_single_database(
    *,
    db_path: Path,
    trades: list[TradeRecord],
    entries: dict[str, EntryRecord],
    db_role: str,
) -> dict[str, Any]:
    candles = load_candles(db_path)
    by_time = {candle.open_time: candle.index for candle in candles}
    replicated: list[ReplicatedTrade] = []
    missing_entries: list[str] = []
    for trade in sorted(trades, key=lambda t: (t.opened_at, t.trade_id)):
        entry = entries.get(trade.trade_id)
        if entry is None:
            missing_entries.append(trade.trade_id)
            continue
        replicated.append(simulate_trade(trade, entry, candles, by_time))
    replicated_values = [row.replicated_pnl_r for row in replicated if row.replicated_pnl_r is not None]
    result_metrics = metrics([float(value) for value in replicated_values])
    correlations = {
        "full": correlation_for(replicated),
        "sl": correlation_for(replicated, "SL"),
        "tp_trail": correlation_for(replicated, "TP_TRAIL"),
    }
    verdict = stratified_verdict(
        metrics_row=result_metrics,
        full_corr=correlations["full"]["pearson"],
        sl_corr=correlations["sl"]["pearson"],
        trail_corr=correlations["tp_trail"]["pearson"],
    )
    divergences = [
        asdict(row)
        for row in replicated
        if row.absolute_delta_r is None or row.absolute_delta_r > 0.05
    ]
    divergences.sort(key=lambda row: (row["baseline_exit_reason"], row["trade_id"]))
    return {
        "db_role": db_role,
        "db_path": str(db_path),
        "candles": {
            "count": len(candles),
            "start": candles[0].open_time.isoformat() if candles else None,
            "end": candles[-1].open_time.isoformat() if candles else None,
        },
        "missing_entries": missing_entries,
        "metrics": result_metrics,
        "correlations": correlations,
        "verdict": verdict,
        "per_trade_results": [asdict(row) for row in replicated],
        "divergences": divergences,
    }


def bind_database_verdict(canonical: dict[str, Any], snapshot: dict[str, Any] | None) -> dict[str, Any]:
    canonical_verdict = canonical["verdict"]["verdict"]
    if (
        snapshot is not None
        and canonical_verdict == "VALIDATED_EDGE_NOT_REPRODUCIBLE"
        and snapshot["verdict"]["verdict"] == "FULL_REPRODUCTION"
    ):
        return {
            "verdict": "DATABASE_LINEAGE_MISMATCH",
            "reason": "Canonical DB failed while comparison snapshot passed; canonical result still binds M6.",
            "canonical_binds": True,
        }
    return {
        "verdict": canonical_verdict,
        "reason": "Canonical DB result binds Part B verdict.",
        "canonical_binds": True,
    }


def run_replication(
    *,
    canonical_db_path: Path,
    trades_path: Path = DEFAULT_TRADES_PATH,
    entries_path: Path = DEFAULT_ENTRIES_PATH,
    snapshot_db_path: Path | None = DEFAULT_SNAPSHOT_DB_PATH,
) -> dict[str, Any]:
    reconnaissance = inspect_artifact_fields(trades_path, entries_path)
    trades = load_trades(trades_path)
    entries = load_entries(entries_path)
    canonical = run_single_database(
        db_path=canonical_db_path,
        trades=trades,
        entries=entries,
        db_role="canonical",
    )
    snapshot = None
    if snapshot_db_path is not None and snapshot_db_path.exists():
        snapshot = run_single_database(
            db_path=snapshot_db_path,
            trades=trades,
            entries=entries,
            db_role="comparison_snapshot",
        )
    database_binding = bind_database_verdict(canonical, snapshot)
    return {
        "manifest": {
            "diagnostic": "TRIAL_00095_SQL_REPLICATION_V1",
            "generated_at_utc": "DETERMINISTIC_NO_WALL_CLOCK",
            "research_only": True,
            "production_changes": False,
            "symbol": SYMBOL,
            "timeframe": TIMEFRAME,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "canonical_db_path": str(canonical_db_path),
            "snapshot_db_path": str(snapshot_db_path) if snapshot_db_path else None,
        },
        "trail_rule_reconnaissance": reconnaissance,
        "baseline_reference": BASELINE,
        "database_binding": database_binding,
        "canonical_result": canonical,
        "snapshot_comparison": snapshot,
    }


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--trades-path", type=Path, default=DEFAULT_TRADES_PATH)
    parser.add_argument("--entries-path", type=Path, default=DEFAULT_ENTRIES_PATH)
    parser.add_argument("--snapshot-db-path", type=Path, default=DEFAULT_SNAPSHOT_DB_PATH)
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--no-snapshot", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_replication(
        canonical_db_path=args.db_path,
        trades_path=args.trades_path,
        entries_path=args.entries_path,
        snapshot_db_path=None if args.no_snapshot else args.snapshot_db_path,
    )
    write_json(payload, args.json_path)
    print(json.dumps({
        "json_path": str(args.json_path),
        "part_b_verdict": payload["database_binding"]["verdict"],
        "canonical_db_path": payload["manifest"]["canonical_db_path"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
