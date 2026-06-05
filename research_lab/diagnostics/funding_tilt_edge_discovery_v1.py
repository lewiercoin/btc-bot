#!/usr/bin/env python3
"""Research-only FUNDING_TILT_FINAL_EXPERIMENT diagnostic.

Frozen pre-result contract, 2026-06-05:
- Branch of record: deploy/multi-asset-paper-v1.
- Grid, hard cap 3 strategy parameters:
  W in {30, 60, 90}; Z in {1.5, 2.0, 2.5}; H in {3, 7, 14}.
- Signal: current funding rate z-score vs the previous W funding samples.
  SHORT if z > +Z, LONG if z < -Z.
- Exit: next funding observation where z-score returns to/past 0, or after H
  funding intervals, whichever comes first. This is z-score mean reversion, not
  absolute 0% funding.
- Walk-forward:
  fold_1 train 2020-09-01..2021-12-31, OOS 2022-01-01..2022-12-31.
  fold_2 train 2020-09-01..2022-12-31, OOS 2023-01-01..2023-12-31.
  fold_3 train 2020-09-01..2023-12-31, OOS 2024-01-01..2024-12-31.
  fold_4 train 2020-09-01..2024-12-31, OOS 2025-01-01..min(DB max, 2026-06-05).
- Nested selection: choose the best cell by mean OOS ER on folds 1-3 only.
  Fold 4 is untouched confirmation and is not used for selection.
- Controls matched to selected W/Z/H and the same cost model:
  random-entry, time-shifted funding, inverse signal.
- PASS requires all frozen gates; any miss returns FAIL.

This module reads SQLite market data in read-only mode and writes research
artifacts only. It does not import or modify live strategy code.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import os
import random
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

if __name__ == "__main__" and sys.path:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.abspath(sys.path[0]) == script_dir:
        sys.path.pop(0)
        sys.path.insert(0, os.path.dirname(os.path.dirname(script_dir)))

from backtest.fill_model import FillModelConfig, SimpleFillModel
from core.funding import FundingRateSample, compute_funding_paid
from core.models import Direction


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_DB_PATH = PROJECT_ROOT / "research_lab" / "data" / "crowded_unwind_backtest.db"
STORAGE_DB_PATH = PROJECT_ROOT / "storage" / "btc_bot.db"
SNAPSHOT_DB_PATH = PROJECT_ROOT / "research_lab" / "snapshots" / "replay-optuna-default-v3-trial-00095.db"
DEFAULT_JSON_PATH = PROJECT_ROOT / "research_lab" / "analysis_output" / "funding_tilt_edge_discovery_v1.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "research_lab" / "validation_report_funding_tilt_v1.md"

GRID_W = (30, 60, 90)
GRID_Z = (1.5, 2.0, 2.5)
GRID_H = (3, 7, 14)
RISK_UNIT_PCT = 0.01
SYMBOL = "BTCUSDT"
TIMEFRAME = "15m"
RANDOM_SEED = 20260605
TIME_SHIFT_FUNDING_INTERVALS = 17
CONFIRMATION_CAP = datetime(2026, 6, 5, 23, 59, 59, tzinfo=timezone.utc)

FOLD_WINDOWS = (
    (
        "fold_1",
        datetime(2020, 9, 1, tzinfo=timezone.utc),
        datetime(2021, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        datetime(2022, 1, 1, tzinfo=timezone.utc),
        datetime(2022, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
    ),
    (
        "fold_2",
        datetime(2020, 9, 1, tzinfo=timezone.utc),
        datetime(2022, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        datetime(2023, 1, 1, tzinfo=timezone.utc),
        datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
    ),
    (
        "fold_3",
        datetime(2020, 9, 1, tzinfo=timezone.utc),
        datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
    ),
    (
        "fold_4",
        datetime(2020, 9, 1, tzinfo=timezone.utc),
        datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        CONFIRMATION_CAP,
    ),
)


@dataclass(frozen=True, slots=True)
class Candle:
    index: int
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class FundingPoint:
    index: int
    funding_time: datetime
    funding_rate: float
    zscore: float | None = None


@dataclass(frozen=True, slots=True)
class Cell:
    W: int
    Z: float
    H: int

    @property
    def key(self) -> str:
        return f"W{self.W}_Z{self.Z:g}_H{self.H}"


@dataclass(frozen=True, slots=True)
class Trade:
    cohort: str
    fold: str
    cell_key: str
    direction: Direction
    signal_funding_index: int
    exit_funding_index: int
    signal_time_utc: str
    entry_time_utc: str
    exit_time_utc: str
    entry_requested_price: float
    exit_requested_price: float
    entry_fill_price: float
    exit_fill_price: float
    hold_funding_intervals: int
    exit_reason: str
    gross_return_pct: float
    fee_return_pct: float
    funding_paid_pct: float
    funding_credit_pct: float
    net_return_pct: float
    r_return: float


@dataclass(frozen=True, slots=True)
class FoldWindow:
    name: str
    train_start: datetime
    train_end: datetime
    oos_start: datetime
    oos_end: datetime


def parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        parsed = raw
    else:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def resolve_db_path(explicit: Path | None) -> tuple[Path, dict[str, Any]]:
    if explicit is not None:
        return explicit, {
            "operator_supplied_db": True,
            "canonical_db_present": CANONICAL_DB_PATH.exists(),
            "fallback_used": False,
        }
    if CANONICAL_DB_PATH.exists():
        return CANONICAL_DB_PATH, {
            "operator_supplied_db": False,
            "canonical_db_present": True,
            "fallback_used": False,
        }
    if STORAGE_DB_PATH.exists():
        return STORAGE_DB_PATH, {
            "operator_supplied_db": False,
            "canonical_db_present": False,
            "fallback_used": True,
            "fallback_reason": "canonical research DB missing; used local storage/btc_bot.db market snapshot",
        }
    if SNAPSHOT_DB_PATH.exists():
        return SNAPSHOT_DB_PATH, {
            "operator_supplied_db": False,
            "canonical_db_present": False,
            "fallback_used": True,
            "fallback_reason": "canonical research DB and storage DB missing; used replay snapshot",
        }
    raise FileNotFoundError("No usable DB found; pass --db-path explicitly.")


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def inspect_schema(conn: sqlite3.Connection) -> dict[str, Any]:
    names = table_names(conn)
    required = {
        "candles": {"symbol", "timeframe", "open_time", "open", "high", "low", "close", "volume"},
        "funding": {"symbol", "funding_time", "funding_rate"},
    }
    missing: dict[str, list[str]] = {}
    for table, columns in required.items():
        if table not in names:
            missing[table] = sorted(columns)
            continue
        absent = columns - table_columns(conn, table)
        if absent:
            missing[table] = sorted(absent)
    return {
        "tables_present": sorted(names),
        "required_tables": sorted(required),
        "missing_required": missing,
    }


def load_candles(conn: sqlite3.Connection) -> list[Candle]:
    rows = conn.execute(
        """
        SELECT open_time, open, high, low, close, volume
        FROM candles
        WHERE symbol = ? AND timeframe = ?
        ORDER BY open_time ASC
        """,
        (SYMBOL, TIMEFRAME),
    ).fetchall()
    return [
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


def load_funding(conn: sqlite3.Connection) -> list[FundingPoint]:
    rows = conn.execute(
        """
        SELECT funding_time, funding_rate
        FROM funding
        WHERE symbol = ?
        ORDER BY funding_time ASC
        """,
        (SYMBOL,),
    ).fetchall()
    return [
        FundingPoint(
            index=idx,
            funding_time=parse_ts(row[0]),
            funding_rate=float(row[1] or 0.0),
        )
        for idx, row in enumerate(rows)
    ]


def data_quality(candles: list[Candle], funding: list[FundingPoint]) -> dict[str, Any]:
    candle_gaps = 0
    non_monotonic_candles = 0
    if len(candles) >= 2:
        for left, right in zip(candles, candles[1:]):
            delta = int((right.open_time - left.open_time).total_seconds())
            if delta <= 0:
                non_monotonic_candles += 1
            elif delta > 15 * 60:
                candle_gaps += max(0, round(delta / (15 * 60)) - 1)
    funding_gaps = 0
    non_monotonic_funding = 0
    if len(funding) >= 2:
        for left, right in zip(funding, funding[1:]):
            delta = int((right.funding_time - left.funding_time).total_seconds())
            if delta <= 0:
                non_monotonic_funding += 1
            elif delta > 8 * 60 * 60 + 60:
                funding_gaps += max(0, round(delta / (8 * 60 * 60)) - 1)
    return {
        "candles": {
            "rows": len(candles),
            "start_time_utc": iso(candles[0].open_time) if candles else None,
            "end_time_utc": iso(candles[-1].open_time) if candles else None,
            "missing_15m_bar_gaps": candle_gaps,
            "non_monotonic_timestamps": non_monotonic_candles,
        },
        "funding": {
            "rows": len(funding),
            "start_time_utc": iso(funding[0].funding_time) if funding else None,
            "end_time_utc": iso(funding[-1].funding_time) if funding else None,
            "missing_8h_gaps": funding_gaps,
            "non_monotonic_timestamps": non_monotonic_funding,
        },
    }


def with_zscores(funding: list[FundingPoint], window: int) -> list[FundingPoint]:
    result: list[FundingPoint] = []
    rates = [point.funding_rate for point in funding]
    for idx, point in enumerate(funding):
        zscore = None
        if idx >= window:
            prior = rates[idx - window : idx]
            avg = mean(prior)
            variance = sum((value - avg) ** 2 for value in prior) / len(prior)
            std = math.sqrt(variance)
            zscore = 0.0 if std <= 0 else (point.funding_rate - avg) / std
        result.append(
            FundingPoint(
                index=point.index,
                funding_time=point.funding_time,
                funding_rate=point.funding_rate,
                zscore=zscore,
            )
        )
    return result


def next_candle_after(candles: list[Candle], candle_times: list[datetime], ts: datetime) -> Candle | None:
    idx = bisect.bisect_right(candle_times, ts)
    if idx >= len(candles):
        return None
    return candles[idx]


def side_for_entry(direction: Direction) -> str:
    return "BUY" if direction == "LONG" else "SELL"


def side_for_exit(direction: Direction) -> str:
    return "SELL" if direction == "LONG" else "BUY"


def calculate_trade_return(
    *,
    cohort: str,
    fold: str,
    cell_key: str,
    direction: Direction,
    signal_index: int,
    exit_index: int,
    entry_candle: Candle,
    exit_candle: Candle,
    funding_samples: Iterable[FundingRateSample | dict[str, Any]],
    exit_reason: str,
    fill_config: FillModelConfig | None = None,
) -> Trade:
    fill_model = SimpleFillModel(fill_config)
    qty = 1.0
    entry_fill = fill_model.simulate(
        entry_candle.open,
        qty,
        order_type="MARKET",
        side=side_for_entry(direction),  # type: ignore[arg-type]
    )
    exit_fill = fill_model.simulate(
        exit_candle.open,
        qty,
        order_type="MARKET",
        side=side_for_exit(direction),  # type: ignore[arg-type]
    )
    if direction == "LONG":
        gross_pnl_abs = exit_fill.filled_price - entry_fill.filled_price
    else:
        gross_pnl_abs = entry_fill.filled_price - exit_fill.filled_price
    notional = entry_fill.filled_price * qty
    fees = entry_fill.fee_paid + exit_fill.fee_paid
    funding_paid = compute_funding_paid(
        direction=direction,
        notional=notional,
        opened_at=entry_candle.open_time,
        closed_at=exit_candle.open_time,
        funding_samples=funding_samples,
    )
    net_pnl_abs = gross_pnl_abs - fees - funding_paid
    gross_return_pct = gross_pnl_abs / notional if notional else 0.0
    fee_return_pct = fees / notional if notional else 0.0
    funding_paid_pct = funding_paid / notional if notional else 0.0
    net_return_pct = net_pnl_abs / notional if notional else 0.0
    return Trade(
        cohort=cohort,
        fold=fold,
        cell_key=cell_key,
        direction=direction,
        signal_funding_index=signal_index,
        exit_funding_index=exit_index,
        signal_time_utc="",
        entry_time_utc=iso(entry_candle.open_time),
        exit_time_utc=iso(exit_candle.open_time),
        entry_requested_price=entry_candle.open,
        exit_requested_price=exit_candle.open,
        entry_fill_price=entry_fill.filled_price,
        exit_fill_price=exit_fill.filled_price,
        hold_funding_intervals=max(0, exit_index - signal_index),
        exit_reason=exit_reason,
        gross_return_pct=gross_return_pct,
        fee_return_pct=fee_return_pct,
        funding_paid_pct=funding_paid_pct,
        funding_credit_pct=-funding_paid_pct,
        net_return_pct=net_return_pct,
        r_return=net_return_pct / RISK_UNIT_PCT,
    )


def _trade_with_signal_time(trade: Trade, signal_time: datetime) -> Trade:
    return Trade(
        cohort=trade.cohort,
        fold=trade.fold,
        cell_key=trade.cell_key,
        direction=trade.direction,
        signal_funding_index=trade.signal_funding_index,
        exit_funding_index=trade.exit_funding_index,
        signal_time_utc=iso(signal_time),
        entry_time_utc=trade.entry_time_utc,
        exit_time_utc=trade.exit_time_utc,
        entry_requested_price=trade.entry_requested_price,
        exit_requested_price=trade.exit_requested_price,
        entry_fill_price=trade.entry_fill_price,
        exit_fill_price=trade.exit_fill_price,
        hold_funding_intervals=trade.hold_funding_intervals,
        exit_reason=trade.exit_reason,
        gross_return_pct=trade.gross_return_pct,
        fee_return_pct=trade.fee_return_pct,
        funding_paid_pct=trade.funding_paid_pct,
        funding_credit_pct=trade.funding_credit_pct,
        net_return_pct=trade.net_return_pct,
        r_return=trade.r_return,
    )


def funding_samples_for_calc(funding: list[FundingPoint]) -> list[FundingRateSample]:
    return [
        FundingRateSample(funding_time=point.funding_time, funding_rate=point.funding_rate)
        for point in funding
    ]


def direction_from_z(zscore: float, threshold: float, *, inverse: bool = False) -> Direction | None:
    direction: Direction | None = None
    if zscore > threshold:
        direction = "SHORT"
    elif zscore < -threshold:
        direction = "LONG"
    if direction is None:
        return None
    if inverse:
        return "LONG" if direction == "SHORT" else "SHORT"
    return direction


def mean_reverted(zscore: float | None, direction: Direction) -> bool:
    if zscore is None:
        return False
    if direction == "SHORT":
        return zscore <= 0.0
    return zscore >= 0.0


def find_exit_index(
    funding: list[FundingPoint],
    *,
    signal_index: int,
    direction: Direction,
    max_holding_intervals: int,
) -> tuple[int, str] | None:
    max_index = min(len(funding) - 1, signal_index + max_holding_intervals)
    for idx in range(signal_index + 1, max_index + 1):
        if mean_reverted(funding[idx].zscore, direction):
            return idx, "ZSCORE_MEAN_REVERTED"
    if max_index > signal_index:
        return max_index, "MAX_HOLD"
    return None


def simulate_signal_cohort(
    *,
    cohort: str,
    cell: Cell,
    fold: FoldWindow,
    funding: list[FundingPoint],
    candles: list[Candle],
    candle_times: list[datetime],
    funding_samples: list[FundingRateSample],
    inverse: bool = False,
) -> list[Trade]:
    trades: list[Trade] = []
    idx = 0
    while idx < len(funding):
        point = funding[idx]
        if point.funding_time < fold.oos_start:
            idx += 1
            continue
        if point.funding_time > fold.oos_end:
            break
        if point.zscore is None:
            idx += 1
            continue
        direction = direction_from_z(point.zscore, cell.Z, inverse=inverse)
        if direction is None:
            idx += 1
            continue
        exit_info = find_exit_index(
            funding,
            signal_index=idx,
            direction=direction,
            max_holding_intervals=cell.H,
        )
        if exit_info is None:
            idx += 1
            continue
        exit_idx, exit_reason = exit_info
        exit_point = funding[exit_idx]
        entry_candle = next_candle_after(candles, candle_times, point.funding_time)
        exit_candle = next_candle_after(candles, candle_times, exit_point.funding_time)
        if entry_candle is None or exit_candle is None:
            idx += 1
            continue
        if exit_candle.open_time > fold.oos_end:
            idx += 1
            continue
        trade = calculate_trade_return(
            cohort=cohort,
            fold=fold.name,
            cell_key=cell.key,
            direction=direction,
            signal_index=idx,
            exit_index=exit_idx,
            entry_candle=entry_candle,
            exit_candle=exit_candle,
            funding_samples=funding_samples,
            exit_reason=exit_reason,
        )
        trades.append(_trade_with_signal_time(trade, point.funding_time))
        idx = exit_idx + 1
    return trades


def shifted_funding_series(funding: list[FundingPoint], shift: int) -> list[FundingPoint]:
    shifted: list[FundingPoint] = []
    for idx, point in enumerate(funding):
        source_idx = idx - shift
        zscore = funding[source_idx].zscore if source_idx >= 0 else None
        rate = funding[source_idx].funding_rate if source_idx >= 0 else point.funding_rate
        shifted.append(
            FundingPoint(
                index=point.index,
                funding_time=point.funding_time,
                funding_rate=rate,
                zscore=zscore,
            )
        )
    return shifted


def simulate_random_control(
    *,
    selected_main_trades: list[Trade],
    cell: Cell,
    fold: FoldWindow,
    funding: list[FundingPoint],
    candles: list[Candle],
    candle_times: list[datetime],
    funding_samples: list[FundingRateSample],
    seed: int,
) -> list[Trade]:
    if not selected_main_trades:
        return []
    rng = random.Random(seed)
    durations = [max(1, trade.hold_funding_intervals) for trade in selected_main_trades]
    candidates = [
        idx
        for idx, point in enumerate(funding)
        if fold.oos_start <= point.funding_time <= fold.oos_end
    ]
    rng.shuffle(candidates)
    used: set[int] = set()
    trades: list[Trade] = []
    for ordinal, duration in enumerate(durations):
        chosen: int | None = None
        for idx in candidates:
            exit_idx = idx + duration
            if exit_idx >= len(funding):
                continue
            exit_point = funding[exit_idx]
            if exit_point.funding_time > fold.oos_end:
                continue
            occupied = set(range(idx, exit_idx + 1))
            if used & occupied:
                continue
            entry_candle = next_candle_after(candles, candle_times, funding[idx].funding_time)
            exit_candle = next_candle_after(candles, candle_times, exit_point.funding_time)
            if entry_candle is None or exit_candle is None or exit_candle.open_time > fold.oos_end:
                continue
            chosen = idx
            used |= occupied
            direction: Direction = "LONG" if rng.random() < 0.5 else "SHORT"
            trade = calculate_trade_return(
                cohort="control_random_entry",
                fold=fold.name,
                cell_key=cell.key,
                direction=direction,
                signal_index=idx,
                exit_index=exit_idx,
                entry_candle=entry_candle,
                exit_candle=exit_candle,
                funding_samples=funding_samples,
                exit_reason="MATCHED_RANDOM_HOLD",
            )
            trades.append(_trade_with_signal_time(trade, funding[idx].funding_time))
            break
        if chosen is None:
            continue
    return trades


def profit_factor(returns: Iterable[float]) -> float:
    values = list(returns)
    gains = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses == 0:
        return 999.0 if gains > 0 else 0.0
    return gains / losses


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = pct * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def max_drawdown_r(returns: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in returns:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def metrics_for_trades(trades: list[Trade], *, include_distribution: bool = True) -> dict[str, Any]:
    returns = [trade.r_return for trade in trades]
    result: dict[str, Any] = {
        "trades": len(trades),
        "er": mean(returns) if returns else 0.0,
        "profit_factor": profit_factor(returns),
        "win_rate": (sum(1 for value in returns if value > 0) / len(returns)) if returns else 0.0,
        "median_r": median(returns) if returns else 0.0,
        "worst_trade_r": min(returns) if returns else 0.0,
        "best_trade_r": max(returns) if returns else 0.0,
        "max_drawdown_r": max_drawdown_r(returns),
        "max_drawdown_pct_of_reference_equity": max_drawdown_r(returns) * RISK_UNIT_PCT,
        "mean_funding_credit_pct": mean([trade.funding_credit_pct for trade in trades]) if trades else 0.0,
        "mean_fee_pct": mean([trade.fee_return_pct for trade in trades]) if trades else 0.0,
    }
    if include_distribution:
        result["distribution_r"] = {
            "min": percentile(returns, 0.0),
            "p10": percentile(returns, 0.10),
            "p25": percentile(returns, 0.25),
            "median": percentile(returns, 0.50),
            "p75": percentile(returns, 0.75),
            "p90": percentile(returns, 0.90),
            "max": percentile(returns, 1.0),
            "values": returns,
        }
    return result


def fold_metrics(trades: list[Trade], folds: list[FoldWindow]) -> dict[str, dict[str, Any]]:
    return {
        fold.name: metrics_for_trades([trade for trade in trades if trade.fold == fold.name])
        for fold in folds
    }


def effective_folds(candles: list[Candle]) -> list[FoldWindow]:
    if not candles:
        return [
            FoldWindow(name, train_start, train_end, oos_start, oos_end)
            for name, train_start, train_end, oos_start, oos_end in FOLD_WINDOWS
        ]
    db_end = min(candles[-1].open_time, CONFIRMATION_CAP)
    folds = []
    for name, train_start, train_end, oos_start, oos_end in FOLD_WINDOWS:
        effective_end = min(oos_end, db_end)
        folds.append(FoldWindow(name, train_start, train_end, oos_start, effective_end))
    return folds


def evaluate_cell(
    *,
    cell: Cell,
    base_funding: list[FundingPoint],
    folds: list[FoldWindow],
    candles: list[Candle],
    candle_times: list[datetime],
    funding_samples: list[FundingRateSample],
) -> dict[str, Any]:
    funding = with_zscores(base_funding, cell.W)
    trades: list[Trade] = []
    for fold in folds:
        trades.extend(
            simulate_signal_cohort(
                cohort="main_funding_tilt",
                cell=cell,
                fold=fold,
                funding=funding,
                candles=candles,
                candle_times=candle_times,
                funding_samples=funding_samples,
            )
        )
    per_fold = fold_metrics(trades, folds)
    selection_fold_names = {"fold_1", "fold_2", "fold_3"}
    selection_ers = [
        per_fold[name]["er"]
        for name in ("fold_1", "fold_2", "fold_3")
        if name in per_fold
    ]
    selection_trades = sum(
        per_fold[name]["trades"]
        for name in ("fold_1", "fold_2", "fold_3")
        if name in per_fold
    )
    selection_trades_list = [
        trade for trade in trades if trade.fold in selection_fold_names
    ]
    return {
        "cell": asdict(cell),
        "cell_key": cell.key,
        "selection_mean_oos_er_folds_1_3": mean(selection_ers) if selection_ers else 0.0,
        "selection_trades_folds_1_3": selection_trades,
        "selection_profit_factor_folds_1_3": metrics_for_trades(selection_trades_list, include_distribution=False)[
            "profit_factor"
        ],
        "per_fold": per_fold,
        "all_oos": metrics_for_trades(trades, include_distribution=False),
    }


def select_cell(cell_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        cell_rows,
        key=lambda row: (
            -float(row["selection_mean_oos_er_folds_1_3"]),
            -float(row["selection_profit_factor_folds_1_3"]),
            -int(row["selection_trades_folds_1_3"]),
            int(row["cell"]["W"]),
            float(row["cell"]["Z"]),
            int(row["cell"]["H"]),
        ),
    )[0]


def selected_cell_from_row(row: dict[str, Any]) -> Cell:
    cell = row["cell"]
    return Cell(W=int(cell["W"]), Z=float(cell["Z"]), H=int(cell["H"]))


def evaluate_selected_with_controls(
    *,
    cell: Cell,
    base_funding: list[FundingPoint],
    folds: list[FoldWindow],
    candles: list[Candle],
    candle_times: list[datetime],
    funding_samples: list[FundingRateSample],
) -> dict[str, Any]:
    funding = with_zscores(base_funding, cell.W)
    shifted = shifted_funding_series(funding, TIME_SHIFT_FUNDING_INTERVALS)
    cohorts: dict[str, list[Trade]] = {
        "main_funding_tilt": [],
        "control_inverse_signal": [],
        "control_time_shifted_funding": [],
        "control_random_entry": [],
    }
    for fold_index, fold in enumerate(folds):
        main_trades = simulate_signal_cohort(
            cohort="main_funding_tilt",
            cell=cell,
            fold=fold,
            funding=funding,
            candles=candles,
            candle_times=candle_times,
            funding_samples=funding_samples,
        )
        cohorts["main_funding_tilt"].extend(main_trades)
        cohorts["control_inverse_signal"].extend(
            simulate_signal_cohort(
                cohort="control_inverse_signal",
                cell=cell,
                fold=fold,
                funding=funding,
                candles=candles,
                candle_times=candle_times,
                funding_samples=funding_samples,
                inverse=True,
            )
        )
        cohorts["control_time_shifted_funding"].extend(
            simulate_signal_cohort(
                cohort="control_time_shifted_funding",
                cell=cell,
                fold=fold,
                funding=shifted,
                candles=candles,
                candle_times=candle_times,
                funding_samples=funding_samples,
            )
        )
        cohorts["control_random_entry"].extend(
            simulate_random_control(
                selected_main_trades=main_trades,
                cell=cell,
                fold=fold,
                funding=funding,
                candles=candles,
                candle_times=candle_times,
                funding_samples=funding_samples,
                seed=RANDOM_SEED + fold_index,
            )
        )
    metrics = {
        name: {
            "overall": metrics_for_trades(trades),
            "per_fold": fold_metrics(trades, folds),
        }
        for name, trades in cohorts.items()
    }
    comparisons: list[dict[str, Any]] = []
    for fold in folds:
        main = metrics["main_funding_tilt"]["per_fold"][fold.name]
        for control in (
            "control_random_entry",
            "control_time_shifted_funding",
            "control_inverse_signal",
        ):
            ctrl = metrics[control]["per_fold"][fold.name]
            comparisons.append(
                {
                    "fold": fold.name,
                    "control": control,
                    "main_er": main["er"],
                    "control_er": ctrl["er"],
                    "main_trades": main["trades"],
                    "control_trades": ctrl["trades"],
                    "main_beats_control": bool(
                        main["trades"] > 0
                        and ctrl["trades"] > 0
                        and main["er"] > ctrl["er"]
                    ),
                }
            )
    return {
        "cohort_trades": cohorts,
        "cohort_metrics": metrics,
        "main_vs_controls_per_fold": comparisons,
    }


def degradation_pct(selection_er: float, confirmation_er: float) -> float:
    if selection_er <= 0:
        return 999.0
    return max(0.0, (selection_er - confirmation_er) / abs(selection_er))


def apply_frozen_gates(
    *,
    selected_row: dict[str, Any],
    grid_rows: list[dict[str, Any]],
    selected_eval: dict[str, Any],
) -> dict[str, Any]:
    main_overall = selected_eval["cohort_metrics"]["main_funding_tilt"]["overall"]
    main_folds = selected_eval["cohort_metrics"]["main_funding_tilt"]["per_fold"]
    selection_er = float(selected_row["selection_mean_oos_er_folds_1_3"])
    confirmation_er = float(main_folds["fold_4"]["er"])
    degradation = degradation_pct(selection_er, confirmation_er)
    positive_grid_cells = sum(
        1 for row in grid_rows if float(row["selection_mean_oos_er_folds_1_3"]) > 0.0
    )
    stop_reasons: list[str] = []
    if main_overall["trades"] < 30:
        stop_reasons.append(f"oos_trades_lt_30:{main_overall['trades']}")
    if main_overall["er"] <= 0.10:
        stop_reasons.append(f"overall_er_lte_0_10:{main_overall['er']:.6f}")
    if main_overall["profit_factor"] <= 1.2:
        stop_reasons.append(f"overall_pf_lte_1_2:{main_overall['profit_factor']:.6f}")
    for fold_name, fold_row in main_folds.items():
        if fold_row["er"] <= 0.0:
            stop_reasons.append(f"{fold_name}_er_lte_0:{fold_row['er']:.6f}")
    if degradation >= 0.40:
        stop_reasons.append(f"degradation_gte_40pct:{degradation:.6f}")
    if positive_grid_cells < 9:
        stop_reasons.append(f"positive_grid_cells_lt_9:{positive_grid_cells}")
    failed_comparisons = [
        row
        for row in selected_eval["main_vs_controls_per_fold"]
        if not row["main_beats_control"]
    ]
    if failed_comparisons:
        stop_reasons.append(f"main_does_not_beat_all_controls:{len(failed_comparisons)}_failures")
    return {
        "thresholds": {
            "min_oos_trades": 30,
            "min_er_r": 0.10,
            "min_profit_factor": 1.2,
            "positive_er_every_fold": True,
            "max_degradation_pct": 0.40,
            "min_positive_grid_cells_folds_1_3": 9,
            "main_beats_all_controls_every_fold": True,
        },
        "measurements": {
            "oos_trades": main_overall["trades"],
            "overall_er": main_overall["er"],
            "overall_profit_factor": main_overall["profit_factor"],
            "selection_mean_oos_er_folds_1_3": selection_er,
            "confirmation_fold_4_er": confirmation_er,
            "degradation_pct": degradation,
            "positive_grid_cells_folds_1_3": positive_grid_cells,
            "failed_control_comparisons": failed_comparisons,
        },
        "stop_reasons": stop_reasons,
        "verdict": "FAIL" if stop_reasons else "PASS",
    }


def render_report(payload: dict[str, Any]) -> str:
    selected = payload["selected_cell"]
    gates = payload["frozen_gate_evaluation"]
    cohorts = payload["selected_cell_evaluation"]["cohort_metrics"]
    lines = [
        "# FUNDING_TILT_FINAL_EXPERIMENT - NUMERIC VALIDATION REPORT",
        "",
        f"generated_at_utc: `{payload['manifest']['generated_at_utc']}`",
        f"db_path: `{payload['manifest']['db_path']}`",
        f"verdict: `{payload['verdict']}`",
        "",
        "## Selected Cell",
        "",
        f"W: `{selected['cell']['W']}`",
        f"Z: `{selected['cell']['Z']}`",
        f"H: `{selected['cell']['H']}`",
        f"selection_mean_oos_er_folds_1_3: `{selected['selection_mean_oos_er_folds_1_3']:.6f}`",
        f"selection_trades_folds_1_3: `{selected['selection_trades_folds_1_3']}`",
        "",
        "## Frozen Gates",
        "",
        f"stop_reasons: `{gates['stop_reasons']}`",
        "",
        "| measurement | value |",
        "| --- | ---: |",
    ]
    for key, value in gates["measurements"].items():
        if key == "failed_control_comparisons":
            value = len(value)
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "## Main vs Controls Per Fold",
            "",
            "| fold | control | main_trades | control_trades | main_er | control_er | main_beats |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["selected_cell_evaluation"]["main_vs_controls_per_fold"]:
        lines.append(
            f"| `{row['fold']}` | `{row['control']}` | {row['main_trades']} | {row['control_trades']} | "
            f"{row['main_er']:.6f} | {row['control_er']:.6f} | `{row['main_beats_control']}` |"
        )
    lines.extend(
        [
            "",
            "## Cohort Overall Metrics",
            "",
            "| cohort | trades | ER | PF | worst_R | max_DD_R | mean_funding_credit_pct |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, row in cohorts.items():
        m = row["overall"]
        lines.append(
            f"| `{name}` | {m['trades']} | {m['er']:.6f} | {m['profit_factor']:.6f} | "
            f"{m['worst_trade_r']:.6f} | {m['max_drawdown_r']:.6f} | {m['mean_funding_credit_pct']:.8f} |"
        )
    lines.extend(
        [
            "",
            "## Full 27 Cell Table",
            "",
            "| cell | W | Z | H | mean_OOS_ER_folds_1_3 | trades_folds_1_3 | PF_folds_1_3 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["grid_27_cells"]:
        cell = row["cell"]
        lines.append(
            f"| `{row['cell_key']}` | {cell['W']} | {cell['Z']} | {cell['H']} | "
            f"{row['selection_mean_oos_er_folds_1_3']:.6f} | {row['selection_trades_folds_1_3']} | "
            f"{row['selection_profit_factor_folds_1_3']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Per Fold Main Distribution",
            "",
            "| fold | trades | ER | PF | worst_R | max_DD_R | p10_R | median_R | p90_R |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    main_folds = cohorts["main_funding_tilt"]["per_fold"]
    for fold_name, m in main_folds.items():
        dist = m["distribution_r"]
        lines.append(
            f"| `{fold_name}` | {m['trades']} | {m['er']:.6f} | {m['profit_factor']:.6f} | "
            f"{m['worst_trade_r']:.6f} | {m['max_drawdown_r']:.6f} | "
            f"{(dist['p10'] or 0.0):.6f} | {(dist['median'] or 0.0):.6f} | {(dist['p90'] or 0.0):.6f} |"
        )
    lines.extend(
        [
            "",
            "## Control Matching",
            "",
            f"random_seed: `{RANDOM_SEED}`",
            f"time_shift_funding_intervals: `{TIME_SHIFT_FUNDING_INTERVALS}`",
            "fee_rate_taker: `0.0004`",
            "market_slippage_bps: `3.0`",
            "risk_unit_pct: `0.01`",
            "",
            f"## Verdict: {payload['verdict']}",
            "",
        ]
    )
    return "\n".join(lines)


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return json_ready(asdict(value))
    if isinstance(value, datetime):
        return iso(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    return value


def run_diagnostic(*, db_path: Path | None, json_path: Path, report_path: Path) -> dict[str, Any]:
    resolved_db, db_resolution = resolve_db_path(db_path)
    if not resolved_db.exists():
        raise FileNotFoundError(f"DB not found: {resolved_db}")
    with sqlite3.connect(f"file:{resolved_db.resolve().as_posix()}?mode=ro", uri=True) as conn:
        schema = inspect_schema(conn)
        if schema["missing_required"]:
            raise RuntimeError(f"Required schema missing: {schema['missing_required']}")
        candles = load_candles(conn)
        base_funding = load_funding(conn)
    if not candles:
        raise RuntimeError("No BTCUSDT 15m candles found.")
    if not base_funding:
        raise RuntimeError("No BTCUSDT funding rows found.")
    folds = effective_folds(candles)
    candle_times = [candle.open_time for candle in candles]
    funding_samples = funding_samples_for_calc(base_funding)
    cells = [Cell(W=W, Z=Z, H=H) for W in GRID_W for Z in GRID_Z for H in GRID_H]
    grid_rows = [
        evaluate_cell(
            cell=cell,
            base_funding=base_funding,
            folds=folds,
            candles=candles,
            candle_times=candle_times,
            funding_samples=funding_samples,
        )
        for cell in cells
    ]
    selected_row = select_cell(grid_rows)
    selected_cell = selected_cell_from_row(selected_row)
    selected_eval = evaluate_selected_with_controls(
        cell=selected_cell,
        base_funding=base_funding,
        folds=folds,
        candles=candles,
        candle_times=candle_times,
        funding_samples=funding_samples,
    )
    gates = apply_frozen_gates(
        selected_row=selected_row,
        grid_rows=grid_rows,
        selected_eval=selected_eval,
    )
    payload: dict[str, Any] = {
        "manifest": {
            "diagnostic": "FUNDING_TILT_EDGE_DISCOVERY_V1",
            "research_only": True,
            "production_changes": False,
            "db_path": str(resolved_db),
            "db_resolution": db_resolution,
            "json_path": str(json_path),
            "report_path": str(report_path),
            "generated_at_utc": iso(datetime.now(timezone.utc)),
            "symbol": SYMBOL,
            "timeframe": TIMEFRAME,
        },
        "frozen_contract": {
            "grid": {"W": GRID_W, "Z": GRID_Z, "H": GRID_H},
            "selection": "best mean OOS ER across folds 1-3 only; fold 4 untouched confirmation",
            "folds": [asdict(fold) for fold in folds],
            "risk_unit_pct": RISK_UNIT_PCT,
            "random_seed": RANDOM_SEED,
            "time_shift_funding_intervals": TIME_SHIFT_FUNDING_INTERVALS,
            "fee_rate_taker": FillModelConfig().fee_rate_taker,
            "market_slippage_bps": FillModelConfig().slippage_bps_market,
        },
        "schema": schema,
        "data_quality": data_quality(candles, base_funding),
        "grid_27_cells": grid_rows,
        "selected_cell": selected_row,
        "selected_cell_evaluation": {
            "cohort_metrics": selected_eval["cohort_metrics"],
            "main_vs_controls_per_fold": selected_eval["main_vs_controls_per_fold"],
            "trades": {
                name: [asdict(trade) for trade in trades]
                for name, trades in selected_eval["cohort_trades"].items()
            },
        },
        "frozen_gate_evaluation": gates,
    }
    payload["verdict"] = gates["verdict"]
    serializable = json_ready(payload)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(serializable, indent=2, sort_keys=False, allow_nan=False) + "\n", encoding="utf-8")
    sha = hashlib.sha256(json_path.read_bytes()).hexdigest().upper()
    payload["manifest"]["json_sha256"] = sha
    serializable["manifest"]["json_sha256"] = sha
    json_path.write_text(json.dumps(serializable, indent=2, sort_keys=False, allow_nan=False) + "\n", encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(serializable), encoding="utf-8")
    return serializable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_diagnostic(
        db_path=args.db_path,
        json_path=args.json_path,
        report_path=args.report_path,
    )
    print(
        json.dumps(
            {
                "json_path": str(args.json_path),
                "report_path": str(args.report_path),
                "selected_cell": payload["selected_cell"]["cell"],
                "grid_positive_cells_folds_1_3": payload["frozen_gate_evaluation"]["measurements"][
                    "positive_grid_cells_folds_1_3"
                ],
                "main_vs_controls_per_fold": payload["selected_cell_evaluation"]["main_vs_controls_per_fold"],
                "stop_reasons": payload["frozen_gate_evaluation"]["stop_reasons"],
                "verdict": payload["verdict"],
            },
            indent=2,
            sort_keys=False,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
