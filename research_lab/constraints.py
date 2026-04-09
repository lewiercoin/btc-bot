from __future__ import annotations

from typing import Any


def validate_param_vector(params: dict[str, Any]) -> list[str]:
    violations: list[str] = []

    ema_fast = params.get("ema_fast")
    ema_slow = params.get("ema_slow")
    if ema_fast is not None and ema_slow is not None and not (int(ema_fast) < int(ema_slow)):
        violations.append("ema_fast must be < ema_slow")

    tp1_atr_mult = params.get("tp1_atr_mult")
    tp2_atr_mult = params.get("tp2_atr_mult")
    if tp1_atr_mult is not None and tp2_atr_mult is not None and not (float(tp1_atr_mult) < float(tp2_atr_mult)):
        violations.append("tp1_atr_mult must be < tp2_atr_mult")

    invalidation_offset_atr = params.get("invalidation_offset_atr")
    if invalidation_offset_atr is not None and not (float(invalidation_offset_atr) > 0.0):
        violations.append("invalidation_offset_atr must be > 0")

    min_rr = params.get("min_rr")
    if min_rr is not None and not (float(min_rr) > 1.0):
        violations.append("min_rr must be > 1.0")

    risk_per_trade_pct = params.get("risk_per_trade_pct")
    if risk_per_trade_pct is not None and not (0.001 <= float(risk_per_trade_pct) <= 0.05):
        violations.append("risk_per_trade_pct must be in [0.001, 0.05]")

    max_leverage = params.get("max_leverage")
    if max_leverage is not None and not (1 < int(max_leverage) < 10):
        violations.append("max_leverage must be in (1, 10)")

    high_vol_leverage = params.get("high_vol_leverage")
    if high_vol_leverage is not None and max_leverage is not None and not (int(high_vol_leverage) <= int(max_leverage)):
        violations.append("high_vol_leverage must be <= max_leverage")

    partial_exit_pct = params.get("partial_exit_pct")
    if partial_exit_pct is not None and not (0.0 < float(partial_exit_pct) < 1.0):
        violations.append("partial_exit_pct must be in (0.0, 1.0)")

    session_start_hour_utc = params.get("session_start_hour_utc")
    session_end_hour_utc = params.get("session_end_hour_utc")
    if (
        session_start_hour_utc is not None
        and session_end_hour_utc is not None
        and int(session_start_hour_utc) > int(session_end_hour_utc)
    ):
        violations.append("session_start_hour_utc must be <= session_end_hour_utc")

    return violations


def assert_valid(params: dict[str, Any]) -> None:
    violations = validate_param_vector(params)
    if violations:
        raise ValueError("; ".join(violations))
