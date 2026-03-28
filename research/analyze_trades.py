from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Callable

from settings import load_settings


@dataclass(slots=True, frozen=True)
class AnalyzeTradesConfig:
    symbol: str | None = None
    start_ts_utc: datetime | None = None
    end_ts_utc: datetime | None = None
    limit: int | None = None
    trade_id_prefix: str | None = None
    trade_ids: tuple[str, ...] | None = None


@dataclass(slots=True, frozen=True)
class ClosedTradeRecord:
    trade_id: str
    signal_id: str
    position_id: str
    symbol: str
    direction: str
    regime: str
    confluence_score: float
    opened_at: datetime
    closed_at: datetime
    entry_price: float
    exit_price: float
    size: float
    fees_total: float
    slippage_bps_avg: float
    pnl_abs: float
    pnl_r: float
    mae: float
    mfe: float
    exit_reason: str
    features_at_entry_json: dict[str, Any]
    schema_version: str
    config_hash: str


@dataclass(slots=True)
class GroupMetrics:
    key: str
    trades_count: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    pnl_abs_sum: float
    pnl_r_sum: float
    expectancy_r: float


@dataclass(slots=True)
class TradeAnalysisReport:
    generated_at_utc: datetime
    symbol: str | None
    start_ts_utc: datetime | None
    end_ts_utc: datetime | None
    trades_count: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    pnl_abs_sum: float
    pnl_r_sum: float
    expectancy_r: float
    avg_winner_r: float
    avg_loser_r: float
    profit_factor: float
    avg_hold_minutes: float
    median_hold_minutes: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    direction_breakdown: list[GroupMetrics] = field(default_factory=list)
    regime_breakdown: list[GroupMetrics] = field(default_factory=list)
    exit_reason_breakdown: list[GroupMetrics] = field(default_factory=list)
    confluence_bucket_breakdown: list[GroupMetrics] = field(default_factory=list)
    top_winners: list[dict[str, Any]] = field(default_factory=list)
    top_losers: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["generated_at_utc"] = self.generated_at_utc.isoformat()
        payload["start_ts_utc"] = self.start_ts_utc.isoformat() if self.start_ts_utc is not None else None
        payload["end_ts_utc"] = self.end_ts_utc.isoformat() if self.end_ts_utc is not None else None
        payload["profit_factor"] = _json_float(self.profit_factor)
        return payload


def analyze_closed_trades(
    connection: sqlite3.Connection,
    config: AnalyzeTradesConfig | None = None,
    *,
    now_provider: Callable[[], datetime] | None = None,
) -> TradeAnalysisReport:
    query = config or AnalyzeTradesConfig()
    trades = load_closed_trades(connection, query)
    generated_at = _to_utc((now_provider or (lambda: datetime.now(timezone.utc)))())
    return _build_report(trades, query, generated_at=generated_at)


def load_closed_trades(connection: sqlite3.Connection, config: AnalyzeTradesConfig) -> list[ClosedTradeRecord]:
    symbol = config.symbol.upper() if config.symbol else None
    clauses = ["t.closed_at IS NOT NULL"]
    params: list[Any] = []

    if symbol:
        clauses.append("p.symbol = ?")
        params.append(symbol)
    if config.start_ts_utc is not None:
        clauses.append("t.closed_at >= ?")
        params.append(_to_utc(config.start_ts_utc).isoformat())
    if config.end_ts_utc is not None:
        clauses.append("t.closed_at < ?")
        params.append(_to_utc(config.end_ts_utc).isoformat())
    if config.trade_id_prefix:
        clauses.append("t.trade_id LIKE ?")
        params.append(f"{config.trade_id_prefix}%")
    if config.trade_ids is not None:
        if len(config.trade_ids) == 0:
            clauses.append("1 = 0")
        else:
            placeholders = ", ".join("?" for _ in config.trade_ids)
            clauses.append(f"t.trade_id IN ({placeholders})")
            params.extend(config.trade_ids)

    sql = f"""
        SELECT
            t.trade_id,
            t.signal_id,
            t.position_id,
            p.symbol,
            t.direction,
            t.regime,
            t.confluence_score,
            t.opened_at,
            t.closed_at,
            t.entry_price,
            t.exit_price,
            t.size,
            t.fees_total,
            t.slippage_bps_avg,
            t.pnl_abs,
            t.pnl_r,
            t.mae,
            t.mfe,
            t.exit_reason,
            t.features_at_entry_json,
            t.schema_version,
            t.config_hash
        FROM trade_log t
        JOIN positions p ON p.position_id = t.position_id
        WHERE {" AND ".join(clauses)}
        ORDER BY t.closed_at ASC
    """
    if config.limit is not None:
        sql += "\nLIMIT ?"
        params.append(max(int(config.limit), 0))

    rows = connection.execute(sql, tuple(params)).fetchall()
    result: list[ClosedTradeRecord] = []
    for row in rows:
        features_payload = _parse_json_object(row["features_at_entry_json"])
        closed_at = _parse_required_timestamp(row["closed_at"], field_name="closed_at")
        exit_price = float(row["exit_price"]) if row["exit_price"] is not None else float(row["entry_price"])
        exit_reason = str(row["exit_reason"]) if row["exit_reason"] is not None else "UNKNOWN"
        result.append(
            ClosedTradeRecord(
                trade_id=str(row["trade_id"]),
                signal_id=str(row["signal_id"]),
                position_id=str(row["position_id"]),
                symbol=str(row["symbol"]).upper(),
                direction=str(row["direction"]),
                regime=str(row["regime"]),
                confluence_score=float(row["confluence_score"]),
                opened_at=_parse_required_timestamp(row["opened_at"], field_name="opened_at"),
                closed_at=closed_at,
                entry_price=float(row["entry_price"]),
                exit_price=exit_price,
                size=float(row["size"]),
                fees_total=float(row["fees_total"]),
                slippage_bps_avg=float(row["slippage_bps_avg"]),
                pnl_abs=float(row["pnl_abs"]),
                pnl_r=float(row["pnl_r"]),
                mae=float(row["mae"]),
                mfe=float(row["mfe"]),
                exit_reason=exit_reason,
                features_at_entry_json=features_payload,
                schema_version=str(row["schema_version"]),
                config_hash=str(row["config_hash"]),
            )
        )
    return result


def save_report_json(report: TradeAnalysisReport, output_path: Path) -> None:
    payload = report.to_dict()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _build_report(trades: list[ClosedTradeRecord], config: AnalyzeTradesConfig, *, generated_at: datetime) -> TradeAnalysisReport:
    trade_count = len(trades)
    wins = sum(1 for trade in trades if trade.pnl_abs > 0)
    losses = sum(1 for trade in trades if trade.pnl_abs < 0)
    breakeven = trade_count - wins - losses

    pnl_abs_sum = sum(trade.pnl_abs for trade in trades)
    pnl_r_sum = sum(trade.pnl_r for trade in trades)
    win_rate = (wins / trade_count) if trade_count else 0.0
    expectancy_r = (pnl_r_sum / trade_count) if trade_count else 0.0

    winner_rs = [trade.pnl_r for trade in trades if trade.pnl_r > 0]
    loser_rs = [trade.pnl_r for trade in trades if trade.pnl_r < 0]
    avg_winner_r = (sum(winner_rs) / len(winner_rs)) if winner_rs else 0.0
    avg_loser_r = (sum(loser_rs) / len(loser_rs)) if loser_rs else 0.0

    gross_profit = sum(trade.pnl_abs for trade in trades if trade.pnl_abs > 0)
    gross_loss = abs(sum(trade.pnl_abs for trade in trades if trade.pnl_abs < 0))
    if gross_loss <= 0:
        profit_factor = math.inf if gross_profit > 0 else 0.0
    else:
        profit_factor = gross_profit / gross_loss

    hold_minutes = [
        max((trade.closed_at - trade.opened_at).total_seconds() / 60.0, 0.0)
        for trade in trades
    ]
    avg_hold_minutes = (sum(hold_minutes) / len(hold_minutes)) if hold_minutes else 0.0
    median_hold_minutes = float(median(hold_minutes)) if hold_minutes else 0.0

    max_wins, max_losses = _max_streaks(trades)

    report = TradeAnalysisReport(
        generated_at_utc=generated_at,
        symbol=config.symbol.upper() if config.symbol else None,
        start_ts_utc=_to_utc(config.start_ts_utc) if config.start_ts_utc else None,
        end_ts_utc=_to_utc(config.end_ts_utc) if config.end_ts_utc else None,
        trades_count=trade_count,
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        win_rate=win_rate,
        pnl_abs_sum=pnl_abs_sum,
        pnl_r_sum=pnl_r_sum,
        expectancy_r=expectancy_r,
        avg_winner_r=avg_winner_r,
        avg_loser_r=avg_loser_r,
        profit_factor=profit_factor,
        avg_hold_minutes=avg_hold_minutes,
        median_hold_minutes=median_hold_minutes,
        max_consecutive_wins=max_wins,
        max_consecutive_losses=max_losses,
        direction_breakdown=_group_metrics(trades, key_fn=lambda item: item.direction, unknown_key="UNKNOWN"),
        regime_breakdown=_group_metrics(trades, key_fn=lambda item: item.regime, unknown_key="UNKNOWN"),
        exit_reason_breakdown=_group_metrics(trades, key_fn=lambda item: item.exit_reason, unknown_key="UNKNOWN"),
        confluence_bucket_breakdown=_group_metrics(trades, key_fn=_confluence_bucket, unknown_key="UNKNOWN"),
        top_winners=_top_trades(trades, reverse=True),
        top_losers=_top_trades(trades, reverse=False),
    )
    return report


def _group_metrics(
    trades: list[ClosedTradeRecord],
    *,
    key_fn: Callable[[ClosedTradeRecord], str],
    unknown_key: str,
) -> list[GroupMetrics]:
    grouped: dict[str, list[ClosedTradeRecord]] = {}
    for trade in trades:
        raw_key = key_fn(trade)
        key = raw_key if raw_key else unknown_key
        grouped.setdefault(key, []).append(trade)

    result: list[GroupMetrics] = []
    for key in sorted(grouped):
        subset = grouped[key]
        count = len(subset)
        wins = sum(1 for trade in subset if trade.pnl_abs > 0)
        losses = sum(1 for trade in subset if trade.pnl_abs < 0)
        breakeven = count - wins - losses
        pnl_abs_sum = sum(trade.pnl_abs for trade in subset)
        pnl_r_sum = sum(trade.pnl_r for trade in subset)
        result.append(
            GroupMetrics(
                key=key,
                trades_count=count,
                wins=wins,
                losses=losses,
                breakeven=breakeven,
                win_rate=(wins / count) if count else 0.0,
                pnl_abs_sum=pnl_abs_sum,
                pnl_r_sum=pnl_r_sum,
                expectancy_r=(pnl_r_sum / count) if count else 0.0,
            )
        )
    return result


def _confluence_bucket(trade: ClosedTradeRecord) -> str:
    floor = int(math.floor(trade.confluence_score))
    return f"{floor}-{floor + 1}"


def _top_trades(trades: list[ClosedTradeRecord], *, reverse: bool) -> list[dict[str, Any]]:
    ordered = sorted(trades, key=lambda item: (item.pnl_r, item.trade_id), reverse=reverse)
    result: list[dict[str, Any]] = []
    for trade in ordered[:5]:
        hold_minutes = max((trade.closed_at - trade.opened_at).total_seconds() / 60.0, 0.0)
        result.append(
            {
                "trade_id": trade.trade_id,
                "direction": trade.direction,
                "regime": trade.regime,
                "confluence_score": trade.confluence_score,
                "opened_at": trade.opened_at.isoformat(),
                "closed_at": trade.closed_at.isoformat(),
                "hold_minutes": hold_minutes,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "pnl_abs": trade.pnl_abs,
                "pnl_r": trade.pnl_r,
                "mae": trade.mae,
                "mfe": trade.mfe,
                "exit_reason": trade.exit_reason,
            }
        )
    return result


def _max_streaks(trades: list[ClosedTradeRecord]) -> tuple[int, int]:
    max_wins = 0
    max_losses = 0
    wins = 0
    losses = 0
    for trade in trades:
        if trade.pnl_abs > 0:
            wins += 1
            losses = 0
        elif trade.pnl_abs < 0:
            losses += 1
            wins = 0
        else:
            wins = 0
            losses = 0
        if wins > max_wins:
            max_wins = wins
        if losses > max_losses:
            max_losses = losses
    return max_wins, max_losses


def _parse_required_timestamp(raw: Any, *, field_name: str) -> datetime:
    if raw is None:
        raise ValueError(f"Expected non-null {field_name}.")
    if isinstance(raw, datetime):
        return _to_utc(raw)
    if isinstance(raw, str):
        return _to_utc(datetime.fromisoformat(raw))
    raise ValueError(f"Unsupported timestamp value for {field_name}: {raw!r}")


def _parse_json_object(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    return {}


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _json_float(value: float) -> float | str:
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    if math.isnan(value):
        return "nan"
    return value


def _parse_cli_timestamp(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    return _to_utc(datetime.fromisoformat(raw))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline analysis of closed trades from SQLite trade_log.")
    parser.add_argument("--db-path", type=Path, help="Path to SQLite DB. Defaults to settings.storage.db_path.")
    parser.add_argument("--symbol", type=str, default=None, help="Optional symbol filter, e.g. BTCUSDT.")
    parser.add_argument("--start-ts", type=str, default=None, help="Inclusive UTC start timestamp (ISO-8601).")
    parser.add_argument("--end-ts", type=str, default=None, help="Exclusive UTC end timestamp (ISO-8601).")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of closed trades.")
    parser.add_argument("--output-json", type=Path, default=None, help="Optional path for JSON report output.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = load_settings()
    if args.db_path is not None:
        db_path = args.db_path
    elif settings.storage is not None:
        db_path = settings.storage.db_path
    else:
        raise ValueError("DB path not provided and settings.storage is unavailable.")

    config = AnalyzeTradesConfig(
        symbol=args.symbol,
        start_ts_utc=_parse_cli_timestamp(args.start_ts),
        end_ts_utc=_parse_cli_timestamp(args.end_ts),
        limit=args.limit,
    )

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        report = analyze_closed_trades(connection, config)
    finally:
        connection.close()

    if args.output_json is not None:
        save_report_json(report, args.output_json)
    else:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
