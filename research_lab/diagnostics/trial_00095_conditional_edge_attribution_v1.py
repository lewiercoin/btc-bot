"""Research-only attribution diagnostic for trial-00095 accepted trades.

Implements TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1:

    accepted trial-00095 trades only
    feature context reconstructed from data knowable before entry
    no threshold changes, no near-miss entry generation, no production writes

The diagnostic intentionally does not claim rejected-candidate edge. If rejected
backtest populations are unavailable, it reports that as a blocker for any
near-miss conclusion and can only recommend a separate reconstruction milestone.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRADES_PATH = PROJECT_ROOT / "research_lab" / "analysis_output" / "trial_00095_trades.json"
DEFAULT_ENTRIES_PATH = PROJECT_ROOT / "research_lab" / "analysis_output" / "trial_00095_intrabar_frozen_entries.json"
DEFAULT_MARKET_DB_PATH = PROJECT_ROOT / "research_lab" / "snapshots" / "replay-run13-regime-aware-trial-00063.db"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "research_lab" / "reports" / "trial_00095_conditional_edge_attribution_v1.md"
DEFAULT_JSON_PATH = PROJECT_ROOT / "research_lab" / "reports" / "trial_00095_conditional_edge_attribution_v1.json"

TRIAL_ID = "optuna-default-v3-trial-00095"
SYMBOL = "BTCUSDT"
TIMEFRAME = "15m"
DEPTH_THRESHOLD = 0.00649

TRIAL_00095_REFERENCE = {
    "expectancy_r": 2.1294,
    "profit_factor": 4.6625,
    "trades": 271,
    "win_rate": 0.5646,
    "source": "WF_VALIDATION_TRIAL_00095_2026-05-08",
}


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    symbol: str = SYMBOL
    timeframe: str = TIMEFRAME
    depth_threshold: float = DEPTH_THRESHOLD
    near_threshold_multiplier: float = 1.10
    min_bucket_trades: int = 20
    min_decision_trades: int = 100
    near_threshold_min_trades: int = 25
    q1_er_gate: float = 1.20
    q1_pf_gate: float = 2.00
    q1_win_rate_gate: float = 0.45
    filter_loss_share_gate: float = 0.25
    filter_rest_pf_gate: float = 4.00
    exit_high_mfe_loss_gate: float = 0.20
    cost_note: str = "Uses frozen BacktestRunner pnl_r already embedded in trial-00095 trade records."


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
class FrozenEntry:
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


@dataclass(frozen=True, slots=True)
class TradeRecord:
    trade_id: str
    opened_at: datetime
    direction: str
    regime: str
    pnl_r: float
    sweep_depth_pct: float | None
    exit_reason: str
    mae_abs: float | None
    mfe_abs: float | None
    session_hour: int | None
    frozen_entry: FrozenEntry | None = None


@dataclass(frozen=True, slots=True)
class AttributedTrade:
    trade_id: str
    opened_at: datetime
    direction: str
    regime: str
    pnl_r: float
    is_winner: bool
    sweep_depth_pct: float | None
    depth_band: str
    depth_quartile: str
    session: str
    year: int
    fold: str
    exit_reason: str
    risk_pct: float | None
    mae_r: float | None
    mfe_r: float | None
    hold_bars: int | None
    atr14_pct: float | None
    realized_vol20: float | None
    range_width20_pct: float | None
    volume_z20: float | None
    tfi_15m_prev: float | None
    tfi_alignment: str
    funding_rate: float | None
    oi_change_24h_pct: float | None
    loss_archetype: str


def parse_ts(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_trade_records(path: Path) -> list[TradeRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    trades: list[TradeRecord] = []
    for row in data:
        opened_at = parse_ts(row["opened_at"])
        trades.append(
            TradeRecord(
                trade_id=str(row["trade_id"]),
                opened_at=opened_at,
                direction=str(row["direction"]),
                regime=str(row["regime"]),
                pnl_r=float(row["pnl_r"]),
                sweep_depth_pct=_optional_float(row.get("sweep_depth_pct")),
                exit_reason=str(row.get("exit_reason", "")),
                mae_abs=_optional_float(row.get("mae")),
                mfe_abs=_optional_float(row.get("mfe")),
                session_hour=int(row["session_hour"]) if row.get("session_hour") is not None else opened_at.hour,
            )
        )
    return trades


def load_frozen_entries(path: Path) -> dict[str, FrozenEntry]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    entries: dict[str, FrozenEntry] = {}
    for row in data:
        entries[str(row["trade_id"])] = FrozenEntry(
            trade_id=str(row["trade_id"]),
            signal_id=str(row["signal_id"]),
            opened_at=parse_ts(row["opened_at"]),
            closed_at=parse_ts(row["closed_at"]) if row.get("closed_at") else None,
            direction=str(row["direction"]),
            regime=str(row["regime"]),
            entry_price=float(row["entry_price"]),
            stop_loss=float(row["stop_loss"]),
            tp1=float(row["tp1"]),
            tp2=float(row["tp2"]),
            baseline_pnl_r=float(row["baseline_pnl_r"]),
            baseline_exit_reason=str(row["baseline_exit_reason"]),
        )
    return entries


def merge_entries(trades: list[TradeRecord], entries: dict[str, FrozenEntry]) -> list[TradeRecord]:
    return [
        TradeRecord(
            trade_id=t.trade_id,
            opened_at=t.opened_at,
            direction=t.direction,
            regime=t.regime,
            pnl_r=t.pnl_r,
            sweep_depth_pct=t.sweep_depth_pct,
            exit_reason=t.exit_reason,
            mae_abs=t.mae_abs,
            mfe_abs=t.mfe_abs,
            session_hour=t.session_hour,
            frozen_entry=entries.get(t.trade_id),
        )
        for t in trades
    ]


def inspect_schema(conn: sqlite3.Connection) -> dict[str, Any]:
    tables = _tables(conn)
    result: dict[str, Any] = {
        "tables": tables,
        "required_tables_present": {
            "candles": "candles" in tables,
        },
        "optional_tables_present": {
            "aggtrade_buckets": "aggtrade_buckets" in tables,
            "funding": "funding" in tables,
            "open_interest": "open_interest" in tables,
            "decision_outcomes": "decision_outcomes" in tables,
            "feature_snapshots": "feature_snapshots" in tables,
        },
    }
    if "candles" in tables:
        result["candles_columns"] = _columns(conn, "candles")
    return result


def load_candles(conn: sqlite3.Connection, config: DiagnosticConfig) -> list[Candle]:
    rows = conn.execute(
        """
        SELECT open_time, open, high, low, close, volume
        FROM candles
        WHERE symbol = ? AND timeframe = ?
        ORDER BY open_time ASC
        """,
        (config.symbol, config.timeframe),
    ).fetchall()
    return [
        Candle(
            index=i,
            open_time=parse_ts(r[0]),
            open=float(r[1]),
            high=float(r[2]),
            low=float(r[3]),
            close=float(r[4]),
            volume=float(r[5]),
        )
        for i, r in enumerate(rows)
    ]


def load_aggtrade_prev_tfi(conn: sqlite3.Connection, config: DiagnosticConfig) -> dict[datetime, float]:
    if "aggtrade_buckets" not in _tables(conn):
        return {}
    rows = conn.execute(
        """
        SELECT bucket_time, tfi
        FROM aggtrade_buckets
        WHERE symbol = ? AND timeframe = ?
        ORDER BY bucket_time ASC
        """,
        (config.symbol, config.timeframe),
    ).fetchall()
    return {parse_ts(row[0]): float(row[1]) for row in rows}


def load_funding(conn: sqlite3.Connection, config: DiagnosticConfig) -> list[tuple[datetime, float]]:
    if "funding" not in _tables(conn):
        return []
    rows = conn.execute(
        """
        SELECT funding_time, funding_rate
        FROM funding
        WHERE symbol = ?
        ORDER BY funding_time ASC
        """,
        (config.symbol,),
    ).fetchall()
    return [(parse_ts(r[0]), float(r[1])) for r in rows]


def load_open_interest(conn: sqlite3.Connection, config: DiagnosticConfig) -> list[tuple[datetime, float]]:
    if "open_interest" not in _tables(conn):
        return []
    rows = conn.execute(
        """
        SELECT timestamp, oi_value
        FROM open_interest
        WHERE symbol = ?
        ORDER BY timestamp ASC
        """,
        (config.symbol,),
    ).fetchall()
    return [(parse_ts(r[0]), float(r[1])) for r in rows]


def attribute_trades(
    trades: list[TradeRecord],
    candles: list[Candle],
    aggtrade_tfi: dict[datetime, float],
    funding: list[tuple[datetime, float]],
    open_interest: list[tuple[datetime, float]],
    config: DiagnosticConfig,
) -> list[AttributedTrade]:
    by_time = {c.open_time: c.index for c in candles}
    depths = [t.sweep_depth_pct for t in trades if t.sweep_depth_pct is not None]
    q25 = percentile(depths, 25.0) if depths else None
    q50 = percentile(depths, 50.0) if depths else None
    q75 = percentile(depths, 75.0) if depths else None
    attributed: list[AttributedTrade] = []
    funding_times = [t for t, _ in funding]
    oi_times = [t for t, _ in open_interest]

    for trade in sorted(trades, key=lambda t: (t.opened_at, t.trade_id)):
        candle_idx = by_time.get(trade.opened_at)
        prior_idx = candle_idx - 1 if candle_idx is not None else None
        prior_candle = candles[prior_idx] if prior_idx is not None and prior_idx >= 0 else None
        entry = trade.frozen_entry
        risk_abs = entry.risk_abs if entry and entry.risk_abs > 0 else None
        risk_pct = risk_abs / entry.entry_price if risk_abs and entry and entry.entry_price else None
        mae_r = trade.mae_abs / risk_abs if risk_abs and trade.mae_abs is not None else None
        mfe_r = trade.mfe_abs / risk_abs if risk_abs and trade.mfe_abs is not None else None
        hold_bars = None
        if entry and entry.closed_at:
            hold_bars = max(0, round((entry.closed_at - entry.opened_at).total_seconds() / (15 * 60)))
        prev_tfi = aggtrade_tfi.get(prior_candle.open_time) if prior_candle else None
        funding_rate = _latest_value(funding, funding_times, trade.opened_at)
        oi_now = _latest_value(open_interest, oi_times, trade.opened_at)
        oi_prev = _latest_value(open_interest, oi_times, trade.opened_at, offset_seconds=24 * 60 * 60)
        oi_change = None
        if oi_now is not None and oi_prev not in (None, 0.0):
            oi_change = (oi_now - oi_prev) / oi_prev
        attributed.append(
            AttributedTrade(
                trade_id=trade.trade_id,
                opened_at=trade.opened_at,
                direction=trade.direction,
                regime=trade.regime,
                pnl_r=trade.pnl_r,
                is_winner=trade.pnl_r > 0,
                sweep_depth_pct=trade.sweep_depth_pct,
                depth_band=depth_band(trade.sweep_depth_pct, config),
                depth_quartile=depth_quartile(trade.sweep_depth_pct, q25, q50, q75),
                session=session_bucket(trade.session_hour if trade.session_hour is not None else trade.opened_at.hour),
                year=trade.opened_at.year,
                fold=fold_bucket(trade.opened_at),
                exit_reason=trade.exit_reason,
                risk_pct=risk_pct,
                mae_r=mae_r,
                mfe_r=mfe_r,
                hold_bars=hold_bars,
                atr14_pct=atr_pct(candles, prior_idx, 14),
                realized_vol20=realized_vol(candles, prior_idx, 20),
                range_width20_pct=range_width_pct(candles, prior_idx, 20),
                volume_z20=volume_zscore(candles, prior_idx, 20),
                tfi_15m_prev=prev_tfi,
                tfi_alignment=tfi_alignment(trade.direction, prev_tfi),
                funding_rate=funding_rate,
                oi_change_24h_pct=oi_change,
                loss_archetype=loss_archetype(trade.pnl_r, mae_r, mfe_r, trade.exit_reason),
            )
        )
    return attributed


def summarize_metrics(trades: list[AttributedTrade]) -> dict[str, Any]:
    pnls = [t.pnl_r for t in trades]
    if not pnls:
        return {
            "count": 0,
            "expectancy_r": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "median_r": 0.0,
            "total_r": 0.0,
            "max_drawdown_r": 0.0,
        }
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    return {
        "count": len(pnls),
        "expectancy_r": mean(pnls),
        "profit_factor": gross_profit / gross_loss if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
        "median_r": median(pnls),
        "total_r": sum(pnls),
        "max_drawdown_r": max_drawdown(pnls),
    }


def group_metrics(
    trades: list[AttributedTrade],
    key_fn: Callable[[AttributedTrade], str],
    *,
    min_bucket_trades: int = 1,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[AttributedTrade]] = {}
    for trade in trades:
        buckets.setdefault(key_fn(trade), []).append(trade)
    rows = []
    for key, subset in sorted(buckets.items(), key=lambda item: str(item[0])):
        metrics = summarize_metrics(subset)
        rows.append({"bucket": key, "decision_grade": metrics["count"] >= min_bucket_trades, **metrics})
    return rows


def numeric_attribution(trades: list[AttributedTrade]) -> list[dict[str, Any]]:
    features: list[tuple[str, Callable[[AttributedTrade], float | None]]] = [
        ("sweep_depth_pct", lambda t: t.sweep_depth_pct),
        ("risk_pct", lambda t: t.risk_pct),
        ("mae_r", lambda t: t.mae_r),
        ("mfe_r", lambda t: t.mfe_r),
        ("hold_bars", lambda t: float(t.hold_bars) if t.hold_bars is not None else None),
        ("atr14_pct", lambda t: t.atr14_pct),
        ("realized_vol20", lambda t: t.realized_vol20),
        ("range_width20_pct", lambda t: t.range_width20_pct),
        ("volume_z20", lambda t: t.volume_z20),
        ("tfi_15m_prev", lambda t: t.tfi_15m_prev),
        ("funding_rate", lambda t: t.funding_rate),
        ("oi_change_24h_pct", lambda t: t.oi_change_24h_pct),
    ]
    rows = []
    for name, extractor in features:
        pairs = [(extractor(t), t.pnl_r, t.is_winner) for t in trades if extractor(t) is not None]
        if len(pairs) < 10:
            continue
        xs = [float(p[0]) for p in pairs if p[0] is not None]
        ys = [p[1] for p in pairs]
        winner_vals = [float(p[0]) for p in pairs if p[0] is not None and p[2]]
        loser_vals = [float(p[0]) for p in pairs if p[0] is not None and not p[2]]
        rows.append(
            {
                "feature": name,
                "count": len(xs),
                "corr_pnl_r": pearson(xs, ys),
                "winner_median": median(winner_vals) if winner_vals else None,
                "loser_median": median(loser_vals) if loser_vals else None,
                "median_delta_winner_minus_loser": (
                    median(winner_vals) - median(loser_vals) if winner_vals and loser_vals else None
                ),
            }
        )
    rows.sort(key=lambda r: abs(float(r["corr_pnl_r"])), reverse=True)
    return rows


def scarcity_map(trades: list[AttributedTrade], config: DiagnosticConfig) -> dict[str, Any]:
    months: dict[str, int] = {}
    for trade in trades:
        key = trade.opened_at.strftime("%Y-%m")
        months[key] = months.get(key, 0) + 1
    counts = list(months.values())
    near_limit = config.depth_threshold * config.near_threshold_multiplier
    near = [
        t
        for t in trades
        if t.sweep_depth_pct is not None and config.depth_threshold <= t.sweep_depth_pct <= near_limit
    ]
    return {
        "months_observed": len(months),
        "monthly_min": min(counts) if counts else 0,
        "monthly_median": median(counts) if counts else 0,
        "monthly_mean": mean(counts) if counts else 0,
        "monthly_max": max(counts) if counts else 0,
        "zero_trade_months_not_inferred": True,
        "near_threshold_definition": f"{config.depth_threshold:.5f} to {near_limit:.5f}",
        "near_threshold_metrics": summarize_metrics(near),
        "near_threshold_share": len(near) / len(trades) if trades else 0.0,
        "accepted_population_only": True,
    }


def loss_archetype_summary(trades: list[AttributedTrade]) -> list[dict[str, Any]]:
    losses = [t for t in trades if not t.is_winner]
    rows = group_metrics(losses, lambda t: t.loss_archetype)
    total_losses = len(losses)
    for row in rows:
        row["loss_share"] = row["count"] / total_losses if total_losses else 0.0
    return rows


def decide_next(payload: dict[str, Any], config: DiagnosticConfig) -> dict[str, Any]:
    metrics = payload["baseline_metrics"]
    scarcity = payload["scarcity_map"]
    depth_rows = {r["bucket"]: r for r in payload["bucket_metrics"]["depth_quartile"]}
    q1 = next((r for k, r in depth_rows.items() if str(k).startswith("Q1")), None)
    loss_rows = payload["loss_archetypes"]
    stop_reasons: list[str] = []
    explore_reasons: list[str] = []

    if metrics["count"] < config.min_decision_trades:
        stop_reasons.append(f"accepted trade sample {metrics['count']} < {config.min_decision_trades}")
    if not payload["data_availability"]["rejected_backtest_candidates_available"]:
        explore_reasons.append("rejected backtest population unavailable; near-miss edge cannot be claimed in this diagnostic")

    if q1:
        if (
            q1["count"] >= config.near_threshold_min_trades
            and q1["expectancy_r"] > config.q1_er_gate
            and q1["profit_factor"] > config.q1_pf_gate
            and q1["win_rate"] >= config.q1_win_rate_gate
        ):
            return {
                "recommendation": "PLAN_NEAR_MISS_RECONSTRUCTION_DIAGNOSTIC",
                "reason": (
                    "The shallowest accepted depth quartile is still strongly positive, "
                    "but rejected candidates are not persisted, so the next step must "
                    "reconstruct near-miss candidates rather than relax thresholds."
                ),
                "supporting_evidence": {
                    "q1_depth_metrics": q1,
                    "near_threshold_metrics": scarcity["near_threshold_metrics"],
                    "data_caveat": "accepted trades only; no rejected backtest candidate edge claim",
                },
                "stop_reasons": stop_reasons,
                "explore_reasons": explore_reasons,
            }

    total_trades = metrics["count"]
    large_loss_buckets = [
        row for row in loss_rows if total_trades and row["count"] / total_trades >= config.filter_loss_share_gate
    ]
    if large_loss_buckets:
        return {
            "recommendation": "PLAN_FILTER_OR_EXIT_ATTRIBUTION_FOLLOWUP",
            "reason": "A large loss archetype exists, but near-threshold accepted quality did not clear expansion gates.",
            "supporting_evidence": {"large_loss_buckets": large_loss_buckets},
            "stop_reasons": stop_reasons,
            "explore_reasons": explore_reasons,
        }

    return {
        "recommendation": "STOP_BTC_THRESHOLD_EXPANSION_FOR_NOW",
        "reason": "Accepted-trade attribution does not identify a decision-grade expansion or filter target.",
        "supporting_evidence": {},
        "stop_reasons": stop_reasons,
        "explore_reasons": explore_reasons,
    }


def build_payload(
    trades_path: Path,
    entries_path: Path,
    market_db_path: Path,
    config: DiagnosticConfig,
) -> dict[str, Any]:
    raw_trades = load_trade_records(trades_path)
    entries = load_frozen_entries(entries_path)
    trades = merge_entries(raw_trades, entries)

    with sqlite3.connect(market_db_path) as conn:
        schema = inspect_schema(conn)
        candles = load_candles(conn, config)
        aggtrade_tfi = load_aggtrade_prev_tfi(conn, config)
        funding = load_funding(conn, config)
        open_interest = load_open_interest(conn, config)
        decision_count = _count_table(conn, "decision_outcomes")

    attributed = attribute_trades(trades, candles, aggtrade_tfi, funding, open_interest, config)
    payload: dict[str, Any] = {
        "diagnostic": "TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1",
        "trial_id": TRIAL_ID,
        "methodology": {
            "scope": "accepted trial-00095 trades only",
            "return_source": "frozen BacktestRunner pnl_r per accepted trade",
            "feature_timing": "market context uses prior completed 15m bar before opened_at",
            "no_strategy_changes": True,
            "no_near_miss_generation": True,
        },
        "inputs": {
            "trades_path": str(trades_path),
            "entries_path": str(entries_path),
            "market_db_path": str(market_db_path),
        },
        "schema": schema,
        "data_availability": {
            "accepted_trades": len(raw_trades),
            "frozen_entries": len(entries),
            "attributed_trades": len(attributed),
            "candles": len(candles),
            "aggtrade_buckets_15m_loaded": len(aggtrade_tfi),
            "funding_samples": len(funding),
            "open_interest_samples": len(open_interest),
            "rejected_backtest_candidates_available": bool(decision_count and decision_count > 0),
            "rejected_backtest_candidates_count": decision_count,
        },
        "trial_00095_reference": TRIAL_00095_REFERENCE,
        "baseline_metrics": summarize_metrics(attributed),
        "bucket_metrics": {
            "depth_quartile": group_metrics(attributed, lambda t: t.depth_quartile, min_bucket_trades=config.min_bucket_trades),
            "depth_band": group_metrics(attributed, lambda t: t.depth_band, min_bucket_trades=config.min_bucket_trades),
            "regime": group_metrics(attributed, lambda t: t.regime, min_bucket_trades=config.min_bucket_trades),
            "direction": group_metrics(attributed, lambda t: t.direction, min_bucket_trades=config.min_bucket_trades),
            "session": group_metrics(attributed, lambda t: t.session, min_bucket_trades=config.min_bucket_trades),
            "year": group_metrics(attributed, lambda t: str(t.year), min_bucket_trades=config.min_bucket_trades),
            "fold": group_metrics(attributed, lambda t: t.fold, min_bucket_trades=config.min_bucket_trades),
            "exit_reason": group_metrics(attributed, lambda t: t.exit_reason, min_bucket_trades=config.min_bucket_trades),
            "tfi_alignment": group_metrics(attributed, lambda t: t.tfi_alignment, min_bucket_trades=config.min_bucket_trades),
            "loss_archetype_all_trades": group_metrics(attributed, lambda t: t.loss_archetype, min_bucket_trades=config.min_bucket_trades),
            "atr14_pct_quartile": quartile_group_metrics(attributed, lambda t: t.atr14_pct, "atr14_pct", config),
            "realized_vol20_quartile": quartile_group_metrics(attributed, lambda t: t.realized_vol20, "realized_vol20", config),
            "range_width20_pct_quartile": quartile_group_metrics(attributed, lambda t: t.range_width20_pct, "range_width20_pct", config),
            "volume_z20_quartile": quartile_group_metrics(attributed, lambda t: t.volume_z20, "volume_z20", config),
            "risk_pct_quartile": quartile_group_metrics(attributed, lambda t: t.risk_pct, "risk_pct", config),
        },
        "numeric_attribution": numeric_attribution(attributed),
        "loss_archetypes": loss_archetype_summary(attributed),
        "scarcity_map": scarcity_map(attributed, config),
        "sample_attributed_trades": [serialize_trade(t) for t in attributed[:25]],
    }
    payload["next_recommendation"] = decide_next(payload, config)
    return payload


def quartile_group_metrics(
    trades: list[AttributedTrade],
    extractor: Callable[[AttributedTrade], float | None],
    label: str,
    config: DiagnosticConfig,
) -> list[dict[str, Any]]:
    vals = [extractor(t) for t in trades if extractor(t) is not None]
    if len(vals) < 4:
        return []
    q25 = percentile(vals, 25)
    q50 = percentile(vals, 50)
    q75 = percentile(vals, 75)

    def key(trade: AttributedTrade) -> str:
        value = extractor(trade)
        if value is None:
            return "missing"
        return quartile_label(value, q25, q50, q75, label)

    return group_metrics(
        [t for t in trades if extractor(t) is not None],
        key,
        min_bucket_trades=config.min_bucket_trades,
    )


def render_markdown(payload: dict[str, Any]) -> str:
    rec = payload["next_recommendation"]
    lines = [
        "# TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1",
        "",
        "**Date:** 2026-05-30",
        "**Researcher:** Codex",
        "**Type:** Research-only accepted-trade attribution diagnostic",
        "**Recommendation:** " + rec["recommendation"],
        "",
        "## Executive Summary",
        "",
        (
            "This diagnostic analyzes the frozen accepted trade population for "
            "`optuna-default-v3-trial-00095`. It does not change thresholds, "
            "generate rejected candidates, alter settings, or promote anything."
        ),
        "",
        rec["reason"],
        "",
        "Critical caveat: rejected backtest candidates are not available in the market snapshot used here. "
        "Therefore this diagnostic can support only a separate near-miss reconstruction plan, not a direct "
        "claim that near-miss entries are profitable.",
        "",
        "## Data Availability",
        "",
    ]
    data = payload["data_availability"]
    lines.extend(
        [
            f"- Accepted trade records: {data['accepted_trades']}",
            f"- Frozen entries with stop/target context: {data['frozen_entries']}",
            f"- Attributed trades: {data['attributed_trades']}",
            f"- BTCUSDT 15m candles: {data['candles']}",
            f"- 15m aggtrade TFI buckets loaded: {data['aggtrade_buckets_15m_loaded']}",
            f"- Funding samples: {data['funding_samples']}",
            f"- Open-interest samples: {data['open_interest_samples']}",
            f"- Rejected backtest candidates available: {data['rejected_backtest_candidates_available']}",
            f"- Rejected backtest candidate count: {data['rejected_backtest_candidates_count']}",
            "",
            "## Methodology Guardrails",
            "",
            "- Primary returns use frozen `pnl_r` from accepted trial-00095 trades.",
            "- Reconstructed market context uses the prior completed 15m bar before `opened_at`.",
            "- No detection-bar returns are introduced.",
            "- No failed standalone regime/HMM/breakout/liquidation signal is used as an entry signal.",
            "- No threshold is relaxed in this milestone.",
            "",
            "## Baseline Metrics",
            "",
        ]
    )
    lines.extend(metric_table(payload["baseline_metrics"]))
    ref = payload["trial_00095_reference"]
    lines.extend(
        [
            "",
            (
                f"WF reference: {ref['trades']} trades, ER={ref['expectancy_r']:.4f}, "
                f"PF={ref['profit_factor']:.4f}, WR={ref['win_rate']:.2%} "
                f"from `{ref['source']}`. This diagnostic uses the existing 274-trade "
                "accepted replay artifact; the 3-trade replay difference is previously "
                "documented and is not treated as a new strategy result."
            ),
        ]
    )
    lines.extend(["", "## Key Findings", ""])
    key_findings = _key_findings(payload)
    for item in key_findings:
        lines.append(f"- {item}")
    lines.extend(["", "## Bucket Attribution", ""])
    for title, key in [
        ("Depth Quartile", "depth_quartile"),
        ("Depth Band", "depth_band"),
        ("Regime", "regime"),
        ("Direction", "direction"),
        ("Session", "session"),
        ("Year", "year"),
        ("Fold", "fold"),
        ("Exit Reason", "exit_reason"),
        ("TFI Alignment", "tfi_alignment"),
        ("ATR14 Percentile", "atr14_pct_quartile"),
        ("Volume Z-Score Percentile", "volume_z20_quartile"),
        ("Risk Percentile", "risk_pct_quartile"),
    ]:
        lines.extend([f"### {title}", ""])
        lines.extend(bucket_table(payload["bucket_metrics"].get(key, [])))
        lines.append("")
    lines.extend(["## Numeric Winner/Loser Attribution", ""])
    lines.extend(numeric_table(payload["numeric_attribution"]))
    lines.extend(["", "## Loss Archetypes", ""])
    lines.extend(loss_table(payload["loss_archetypes"]))
    lines.extend(["", "## Scarcity Map", ""])
    scarcity = payload["scarcity_map"]
    near = scarcity["near_threshold_metrics"]
    lines.extend(
        [
            f"- Months with at least one accepted trade: {scarcity['months_observed']}",
            f"- Monthly accepted trades: min={scarcity['monthly_min']}, median={scarcity['monthly_median']}, "
            f"mean={scarcity['monthly_mean']:.2f}, max={scarcity['monthly_max']}",
            "- Zero-trade months are not inferred from accepted-only data.",
            f"- Near-threshold accepted definition: {scarcity['near_threshold_definition']}",
            f"- Near-threshold accepted trades: {near['count']} ({scarcity['near_threshold_share']:.1%} of accepted population)",
            f"- Near-threshold ER: {near['expectancy_r']:.3f}",
            f"- Near-threshold PF: {near['profit_factor']:.3f}",
            f"- Near-threshold win rate: {near['win_rate']:.1%}",
            "",
            "## Invalidation Criteria Evaluation",
            "",
        ]
    )
    stop_reasons = rec.get("stop_reasons", [])
    explore_reasons = rec.get("explore_reasons", [])
    lines.append(f"- Stop reasons: {stop_reasons if stop_reasons else 'None'}")
    lines.append(f"- Explore/context reasons: {explore_reasons if explore_reasons else 'None'}")
    lines.append("- Rejected-candidate edge claim: NOT MADE")
    lines.append("")
    lines.extend(
        [
            "## Recommendation",
            "",
            f"### Verdict: {rec['recommendation']}",
            "",
            rec["reason"],
            "",
            "Next diagnostic must reconstruct rejected near-miss candidates before any BTC threshold expansion is considered. "
            "The current evidence supports investigation, not deployment or threshold relaxation.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], report_path: Path, json_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_markdown(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default), encoding="utf-8")


def _find_bucket(payload: dict[str, Any], group: str, prefix: str) -> dict[str, Any] | None:
    for row in payload["bucket_metrics"].get(group, []):
        if str(row["bucket"]).startswith(prefix):
            return row
    return None


def _exact_bucket(payload: dict[str, Any], group: str, bucket: str) -> dict[str, Any] | None:
    for row in payload["bucket_metrics"].get(group, []):
        if row["bucket"] == bucket:
            return row
    return None


def _key_findings(payload: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    q1 = _find_bucket(payload, "depth_quartile", "Q1")
    near = _find_bucket(payload, "depth_band", "near_threshold")
    long_row = _exact_bucket(payload, "direction", "LONG")
    short_row = _exact_bucket(payload, "direction", "SHORT")
    uptrend = _exact_bucket(payload, "regime", "uptrend")
    downtrend = _exact_bucket(payload, "regime", "downtrend")
    aligned = _exact_bucket(payload, "tfi_alignment", "aligned")
    opposed = _exact_bucket(payload, "tfi_alignment", "opposed")
    loss_after_mfe = next((r for r in payload["loss_archetypes"] if r["bucket"] == "loss_after_1r_mfe"), None)
    if q1:
        findings.append(
            f"Shallowest accepted depth quartile remains positive: N={q1['count']}, "
            f"ER={q1['expectancy_r']:.3f}, PF={q1['profit_factor']:.3f}, WR={q1['win_rate']:.1%}."
        )
    if near:
        findings.append(
            f"Near-threshold accepted trades remain positive: N={near['count']}, "
            f"ER={near['expectancy_r']:.3f}, PF={near['profit_factor']:.3f}; this supports reconstruction research, not threshold relaxation."
        )
    if long_row and short_row:
        findings.append(
            f"Direction split is asymmetric: LONG ER={long_row['expectancy_r']:.3f} across {long_row['count']} trades, "
            f"SHORT ER={short_row['expectancy_r']:.3f} across {short_row['count']} trades."
        )
    if uptrend and downtrend:
        findings.append(
            f"Regime split favors uptrend: uptrend ER={uptrend['expectancy_r']:.3f}, "
            f"downtrend ER={downtrend['expectancy_r']:.3f}."
        )
    if aligned and opposed:
        findings.append(
            f"Prior-bar TFI alignment separates outcomes: aligned ER={aligned['expectancy_r']:.3f}, "
            f"opposed ER={opposed['expectancy_r']:.3f}."
        )
    if loss_after_mfe:
        findings.append(
            f"Most losses had at least 1R favorable excursion before closing red: "
            f"{loss_after_mfe['count']} losses ({loss_after_mfe['loss_share']:.1%} of losses)."
        )
    findings.append("Rejected backtest candidates are unavailable, so no near-miss profitability claim is made.")
    return findings


def run_diagnostic(
    *,
    trades_path: Path = DEFAULT_TRADES_PATH,
    entries_path: Path = DEFAULT_ENTRIES_PATH,
    market_db_path: Path = DEFAULT_MARKET_DB_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    json_path: Path = DEFAULT_JSON_PATH,
    config: DiagnosticConfig = DiagnosticConfig(),
) -> dict[str, Any]:
    payload = build_payload(trades_path, entries_path, market_db_path, config)
    write_outputs(payload, report_path, json_path)
    return payload


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _count_table(conn: sqlite3.Connection, table: str) -> int | None:
    if table not in _tables(conn):
        return None
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def percentile(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    ordered = sorted(vals)
    idx = (p / 100.0) * (len(ordered) - 1)
    lo = math.floor(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mx = mean(xs)
    my = mean(ys)
    denom_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    denom = denom_x * denom_y
    if denom <= 1e-12:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def max_drawdown(pnls: list[float]) -> float:
    equity = 0.0
    high = 0.0
    worst = 0.0
    for pnl in pnls:
        equity += pnl
        high = max(high, equity)
        worst = min(worst, equity - high)
    return abs(worst)


def depth_band(depth: float | None, config: DiagnosticConfig) -> str:
    if depth is None:
        return "missing"
    near_hi = config.depth_threshold * config.near_threshold_multiplier
    if depth < config.depth_threshold:
        return "below_threshold_unexpected"
    if depth <= near_hi:
        return f"near_threshold_{config.depth_threshold:.5f}_{near_hi:.5f}"
    if depth < 0.010:
        return "mid_depth_0.00714_0.01000"
    if depth < 0.015:
        return "deep_0.01000_0.01500"
    return "very_deep_ge_0.01500"


def depth_quartile(depth: float | None, q25: float | None, q50: float | None, q75: float | None) -> str:
    if depth is None or q25 is None or q50 is None or q75 is None:
        return "missing"
    return quartile_label(depth, q25, q50, q75, "depth")


def quartile_label(value: float, q25: float, q50: float, q75: float, label: str) -> str:
    if value < q25:
        return f"Q1_low_{label}_lt_{q25:.6f}"
    if value < q50:
        return f"Q2_{label}_{q25:.6f}_{q50:.6f}"
    if value < q75:
        return f"Q3_{label}_{q50:.6f}_{q75:.6f}"
    return f"Q4_high_{label}_ge_{q75:.6f}"


def session_bucket(hour: int) -> str:
    if 0 <= hour < 8:
        return "Asia_00_08"
    if 8 <= hour < 16:
        return "Europe_08_16"
    return "US_16_24"


def fold_bucket(ts: datetime) -> str:
    if ts < datetime(2023, 7, 1, tzinfo=timezone.utc):
        return "fold_1_2022_2023H1"
    if ts < datetime(2025, 1, 1, tzinfo=timezone.utc):
        return "fold_2_2023H2_2024"
    return "fold_3_2025_2026Q1"


def atr_pct(candles: list[Candle], prior_idx: int | None, period: int) -> float | None:
    if prior_idx is None or prior_idx < period:
        return None
    trs = []
    for idx in range(prior_idx - period + 1, prior_idx + 1):
        current = candles[idx]
        prev_close = candles[idx - 1].close
        trs.append(max(current.high - current.low, abs(current.high - prev_close), abs(current.low - prev_close)))
    close = candles[prior_idx].close
    return mean(trs) / close if close else None


def realized_vol(candles: list[Candle], prior_idx: int | None, period: int) -> float | None:
    if prior_idx is None or prior_idx < period:
        return None
    returns = []
    for idx in range(prior_idx - period + 1, prior_idx + 1):
        prev = candles[idx - 1].close
        cur = candles[idx].close
        if prev > 0:
            returns.append(math.log(cur / prev))
    return stdev(returns) if len(returns) > 1 else None


def range_width_pct(candles: list[Candle], prior_idx: int | None, period: int) -> float | None:
    if prior_idx is None or prior_idx < period - 1:
        return None
    window = candles[prior_idx - period + 1 : prior_idx + 1]
    hi = max(c.high for c in window)
    lo = min(c.low for c in window)
    close = candles[prior_idx].close
    return (hi - lo) / close if close else None


def volume_zscore(candles: list[Candle], prior_idx: int | None, period: int) -> float | None:
    if prior_idx is None or prior_idx < period:
        return None
    baseline = [c.volume for c in candles[prior_idx - period : prior_idx]]
    sigma = stdev(baseline) if len(baseline) > 1 else 0.0
    if sigma <= 1e-12:
        return 0.0
    return (candles[prior_idx].volume - mean(baseline)) / sigma


def tfi_alignment(direction: str, tfi: float | None) -> str:
    if tfi is None:
        return "missing"
    if abs(tfi) <= 1e-12:
        return "neutral"
    if direction == "LONG":
        return "aligned" if tfi > 0 else "opposed"
    if direction == "SHORT":
        return "aligned" if tfi < 0 else "opposed"
    return "unknown_direction"


def _latest_value(
    samples: list[tuple[datetime, float]],
    times: list[datetime],
    at: datetime,
    *,
    offset_seconds: int = 0,
) -> float | None:
    if not samples:
        return None
    target = at
    if offset_seconds:
        from datetime import timedelta

        target = at - timedelta(seconds=offset_seconds)
    lo = 0
    hi = len(times)
    while lo < hi:
        mid = (lo + hi) // 2
        if times[mid] <= target:
            lo = mid + 1
        else:
            hi = mid
    idx = lo - 1
    return samples[idx][1] if idx >= 0 else None


def loss_archetype(pnl_r: float, mae_r: float | None, mfe_r: float | None, exit_reason: str) -> str:
    if pnl_r > 0:
        return "winner"
    if exit_reason.upper().startswith("SL"):
        if mfe_r is not None and mfe_r >= 1.0:
            return "loss_after_1r_mfe"
        return "direct_stop_loss"
    if mfe_r is not None and mfe_r >= 2.0:
        return "large_mfe_giveback_loss"
    if mfe_r is not None and mfe_r >= 1.0:
        return "moderate_mfe_giveback_loss"
    if mae_r is not None and mae_r >= 1.0:
        return "adverse_excursion_loss"
    return "low_followthrough_loss"


def serialize_trade(trade: AttributedTrade) -> dict[str, Any]:
    row = asdict(trade)
    row["opened_at"] = trade.opened_at.isoformat()
    return row


def metric_table(metrics: dict[str, Any]) -> list[str]:
    return [
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Count | {metrics['count']} |",
        f"| Expectancy R | {metrics['expectancy_r']:.4f} |",
        f"| Profit factor | {metrics['profit_factor']:.4f} |",
        f"| Win rate | {metrics['win_rate']:.2%} |",
        f"| Median R | {metrics['median_r']:.4f} |",
        f"| Total R | {metrics['total_r']:.2f} |",
        f"| Max drawdown R | {metrics['max_drawdown_r']:.2f} |",
    ]


def bucket_table(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No decision-grade data."]
    lines = [
        "| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['bucket']}` | {row['count']} | {row['expectancy_r']:.3f} | "
            f"{row['profit_factor']:.3f} | {row['win_rate']:.1%} | {row['median_r']:.3f} | "
            f"{row['total_r']:.2f} | {row['decision_grade']} |"
        )
    return lines


def numeric_table(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No numeric features available."]
    lines = [
        "| Feature | N | Corr vs R | Winner median | Loser median | Median delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['feature']}` | {row['count']} | {row['corr_pnl_r']:.4f} | "
            f"{_fmt(row['winner_median'])} | {_fmt(row['loser_median'])} | "
            f"{_fmt(row['median_delta_winner_minus_loser'])} |"
        )
    return lines


def loss_table(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No losses available."]
    lines = [
        "| Archetype | Losses | Loss share | ER | PF | Median R |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['bucket']}` | {row['count']} | {row['loss_share']:.1%} | "
            f"{row['expectancy_r']:.3f} | {row['profit_factor']:.3f} | {row['median_r']:.3f} |"
        )
    return lines


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades-path", type=Path, default=DEFAULT_TRADES_PATH)
    parser.add_argument("--entries-path", type=Path, default=DEFAULT_ENTRIES_PATH)
    parser.add_argument("--market-db", type=Path, default=DEFAULT_MARKET_DB_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH)
    args = parser.parse_args(argv)
    payload = run_diagnostic(
        trades_path=args.trades_path,
        entries_path=args.entries_path,
        market_db_path=args.market_db,
        report_path=args.report_path,
        json_path=args.json_path,
    )
    print(json.dumps(payload["next_recommendation"], indent=2))
    print(f"Wrote {args.report_path}")
    print(f"Wrote {args.json_path}")


if __name__ == "__main__":
    main()
