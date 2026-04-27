from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from core.models import TradeLog

_UNKNOWN_THRESHOLD_PCT = 20.0

_ATR_LOW = 0.002
_ATR_HIGH = 0.004


def _classify_session(opened_at: datetime) -> str:
    if opened_at.tzinfo is None:
        dt = opened_at.replace(tzinfo=timezone.utc)
    else:
        dt = opened_at.astimezone(timezone.utc)
    h = dt.hour
    if h >= 22 or h <= 6:
        return "ASIA"
    if 7 <= h <= 13:
        return "EU"
    if 14 <= h <= 15:
        return "EU_US"
    if 16 <= h <= 21:
        return "US"
    return "UNKNOWN_SESSION"


def _extract_atr_4h_norm(features_json: str | None) -> float | None:
    if not features_json:
        return None
    try:
        data = json.loads(features_json)
        val = data.get("atr_4h_norm")
        if val is not None:
            return float(val)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def _classify_volatility(atr: float | None) -> str:
    if atr is None:
        return "UNKNOWN"
    if atr < _ATR_LOW:
        return "LOW"
    if atr > _ATR_HIGH:
        return "HIGH"
    return "NORMAL"


def _bucket_stats(entries: list[tuple[int, float]]) -> dict[str, Any]:
    n = len(entries)
    if n == 0:
        return {"n": 0, "win_rate": 0.0, "expectancy_r": 0.0, "profit_factor": None}
    wins = sum(w for w, _ in entries)
    total_r = sum(r for _, r in entries)
    win_r = sum(r for _, r in entries if r > 0)
    loss_r = sum(abs(r) for _, r in entries if r <= 0)
    return {
        "n": n,
        "win_rate": round(wins / n, 4),
        "expectancy_r": round(total_r / n, 4),
        "profit_factor": round(win_r / loss_r, 4) if loss_r > 0 else None,
    }


def compute_context_diagnostics(trades: list[TradeLog]) -> dict[str, Any]:
    """
    Segment backtest trades by session and volatility bucket.

    Returns diagnostic breakdown only — NOT an optimization objective.
    Context buckets must NOT be used as hard filters until MODELING-V1-ACTIVATION
    milestone is approved.

    Args:
        trades: closed TradeLog records from a BacktestResult.

    Returns:
        dict with session_buckets, volatility_buckets, grade, and RESEARCH_ONLY note.
    """
    n_total = len(trades)
    if n_total == 0:
        return {
            "trades_total": 0,
            "unknown_volatility_pct": 100.0,
            "grade": "EMPTY",
            "note": "RESEARCH_ONLY — context breakdown is diagnostic, not an optimization objective.",
            "session_buckets": {},
            "volatility_buckets": {},
        }

    session_data: dict[str, list[tuple[int, float]]] = {}
    volatility_data: dict[str, list[tuple[int, float]]] = {}
    n_unknown_vol = 0

    for trade in trades:
        opened_at = trade.opened_at
        if isinstance(opened_at, str):
            opened_at = datetime.fromisoformat(opened_at)

        pnl_r = float(trade.pnl_r) if trade.pnl_r is not None else 0.0
        win = 1 if pnl_r > 0 else 0
        entry: tuple[int, float] = (win, pnl_r)

        session = _classify_session(opened_at)
        session_data.setdefault(session, []).append(entry)

        atr = _extract_atr_4h_norm(getattr(trade, "features_at_entry_json", None))
        vol = _classify_volatility(atr)
        if vol == "UNKNOWN":
            n_unknown_vol += 1
        volatility_data.setdefault(vol, []).append(entry)

    unknown_pct = n_unknown_vol / n_total * 100
    grade = "PARTIAL" if unknown_pct > _UNKNOWN_THRESHOLD_PCT else "FULL"

    return {
        "trades_total": n_total,
        "unknown_volatility_pct": round(unknown_pct, 1),
        "grade": grade,
        "note": "RESEARCH_ONLY — context breakdown is diagnostic, not an optimization objective.",
        "session_buckets": {k: _bucket_stats(v) for k, v in sorted(session_data.items())},
        "volatility_buckets": {k: _bucket_stats(v) for k, v in sorted(volatility_data.items())},
    }
