from __future__ import annotations

from dataclasses import MISSING, Field, fields
from functools import lru_cache
from typing import Any

from settings import RiskConfig, StrategyConfig

from research_lab.constants import (
    PARAM_STATUS_ACTIVE,
    PARAM_STATUS_DEFERRED,
    PARAM_STATUS_FROZEN,
    PARAM_STATUS_UNSUPPORTED,
)
from research_lab.types import ParamSpec

_INFRA_REASON = "infrastructure params; not strategy params"
_FROZEN_REASONS: dict[str, str] = {
    "weight_force_order_spike": "force_orders table has 0 rows; feature unavailable",
    "ema_fast": "controls ema50_4h feature used by regime engine; feature name implies design intent for 50-period; architecture param frozen in v0.1",
    "ema_slow": "controls ema200_4h feature used by regime engine; feature name implies design intent for 200-period; architecture param frozen in v0.1",
    "crowded_funding_extreme_pct": "regime crowded-leverage funding threshold; frozen at baseline-calibrated value in v0.1",
    "crowded_oi_zscore_min": "regime crowded-leverage OI threshold; frozen at baseline-calibrated value in v0.1",
    "regime_direction_whitelist": "composite dict type; SHORT disabled in v1.1; frozen in v0.1",
    "direction_tfi_threshold_inverse": "derived constraint; changes with direction_tfi_threshold",
    "no_trade_windows_utc": "tuple of tuples; composite type; frozen in v0.1",
    "session_start_hour_utc": "correlated pair; independent sampling produces ~50% invalid pairs; frozen in v0.1",
    "session_end_hour_utc": "correlated pair; independent sampling produces ~50% invalid pairs; frozen in v0.1",
    "symbol": _INFRA_REASON,
    "tf_setup": _INFRA_REASON,
    "tf_context": _INFRA_REASON,
    "tf_bias": _INFRA_REASON,
    "flow_bucket_tf": _INFRA_REASON,
}

_DEFERRED_REASONS: dict[str, str] = {}

_RANGE_OVERRIDES: dict[str, dict[str, Any]] = {
    "atr_period": {"low": 8, "high": 50, "step": 1},
    "ema_fast": {"low": 5, "high": 200, "step": 1},
    "ema_slow": {"low": 20, "high": 500, "step": 1},
    "equal_level_lookback": {"low": 10, "high": 300, "step": 1},
    "equal_level_tol_atr": {"low": 0.01, "high": 0.3, "step": 0.01},
    "sweep_buf_atr": {"low": 0.01, "high": 1.0, "step": 0.01},
    "reclaim_buf_atr": {"low": 0.0, "high": 0.2, "step": 0.01},
    "wick_min_atr": {"low": 0.05, "high": 1.0, "step": 0.05},
    "funding_window_days": {"low": 7, "high": 180, "step": 1},
    "oi_z_window_days": {"low": 7, "high": 180, "step": 1},
    "confluence_min": {"low": 2.5, "high": 4.5, "step": 0.1},
    "ema_trend_gap_pct": {"low": 0.0001, "high": 0.02, "step": 0.0001},
    "compression_atr_norm_max": {"low": 0.0001, "high": 0.05, "step": 0.0001},
    "crowded_funding_extreme_pct": {"low": 50.0, "high": 99.9, "step": 0.1},
    "crowded_oi_zscore_min": {"low": 0.1, "high": 5.0, "step": 0.1},
    "post_liq_tfi_abs_min": {"low": 0.01, "high": 1.0, "step": 0.01},
    "min_sweep_depth_pct": {"low": 0.00001, "high": 0.02, "step": 0.00001},
    "entry_offset_atr": {"low": 0.0, "high": 2.0, "step": 0.01},
    "invalidation_offset_atr": {"low": 0.01, "high": 5.0, "step": 0.01},
    "min_stop_distance_pct": {"low": 0.0001, "high": 0.02, "step": 0.0001},
    "tp1_atr_mult": {"low": 0.5, "high": 5.0, "step": 0.1},
    "tp2_atr_mult": {"low": 1.0, "high": 8.0, "step": 0.1},
    "weight_sweep_detected": {"low": 0.0, "high": 5.0, "step": 0.05},
    "weight_reclaim_confirmed": {"low": 0.0, "high": 5.0, "step": 0.05},
    "weight_cvd_divergence": {"low": 0.0, "high": 5.0, "step": 0.05},
    "weight_tfi_impulse": {"low": 0.0, "high": 5.0, "step": 0.05},
    "weight_regime_special": {"low": 0.0, "high": 5.0, "step": 0.05},
    "weight_ema_trend_alignment": {"low": 0.0, "high": 5.0, "step": 0.05},
    "weight_funding_supportive": {"low": 0.0, "high": 5.0, "step": 0.05},
    "direction_tfi_threshold": {"low": 0.01, "high": 0.5, "step": 0.01},
    "tfi_impulse_threshold": {"low": 0.05, "high": 0.5, "step": 0.01},
    "risk_per_trade_pct": {"low": 0.001, "high": 0.05, "step": 0.0005},
    "max_leverage": {"low": 2, "high": 9, "step": 1},
    "high_vol_leverage": {"low": 1, "high": 9, "step": 1},
    "min_rr": {"low": 1.5, "high": 4.0, "step": 0.05},
    "max_open_positions": {"low": 1, "high": 3, "step": 1},
    "max_trades_per_day": {"low": 1, "high": 6, "step": 1},
    "max_consecutive_losses": {"low": 1, "high": 10, "step": 1},
    "daily_dd_limit": {"low": 0.005, "high": 0.2, "step": 0.001},
    "weekly_dd_limit": {"low": 0.01, "high": 0.4, "step": 0.001},
    "max_hold_hours": {"low": 1, "high": 72, "step": 1},
    "high_vol_stop_distance_pct": {"low": 0.001, "high": 0.1, "step": 0.001},
    "partial_exit_pct": {"low": 0.01, "high": 0.99, "step": 0.01},
    "trailing_atr_mult": {"low": 0.1, "high": 5.0, "step": 0.1},
    "cooldown_minutes_after_loss": {"low": 0, "high": 240, "step": 5},
    "duplicate_level_tolerance_pct": {"low": 0.0001, "high": 0.01, "step": 0.0001},
    "duplicate_level_window_hours": {"low": 1, "high": 168, "step": 1},
    "session_start_hour_utc": {"low": 0, "high": 23, "step": 1},
    "session_end_hour_utc": {"low": 0, "high": 23, "step": 1},
}

_DOMAIN_OVERRIDES: dict[str, str] = {
    "symbol": "categorical",
    "tf_setup": "categorical",
    "tf_context": "categorical",
    "tf_bias": "categorical",
    "flow_bucket_tf": "categorical",
    "regime_direction_whitelist": "composite",
    "no_trade_windows_utc": "composite",
}

_CHOICES_OVERRIDES: dict[str, tuple[Any, ...]] = {
    "symbol": ("BTCUSDT",),
    "tf_setup": ("15m",),
    "tf_context": ("1h",),
    "tf_bias": ("4h",),
    "flow_bucket_tf": ("60s",),
}


def _field_default(field: Field[Any]) -> Any:
    if field.default is not MISSING:
        return field.default
    if field.default_factory is not MISSING:  # type: ignore[truthy-function]
        return field.default_factory()
    raise ValueError(f"Field {field.name!r} has no default value.")


def _infer_domain_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "categorical"
    if isinstance(value, (dict, tuple, list)):
        return "composite"
    return "categorical"


def _build_section_specs(section_name: str, cfg_type: type[Any]) -> dict[str, ParamSpec]:
    result: dict[str, ParamSpec] = {}
    for cfg_field in fields(cfg_type):
        name = cfg_field.name
        default_value = _field_default(cfg_field)
        status = PARAM_STATUS_ACTIVE
        reason: str | None = None
        if name in _FROZEN_REASONS:
            status = PARAM_STATUS_FROZEN
            reason = _FROZEN_REASONS[name]
        elif name in _DEFERRED_REASONS:
            status = PARAM_STATUS_DEFERRED
            reason = _DEFERRED_REASONS[name]

        domain_type = _DOMAIN_OVERRIDES.get(name, _infer_domain_type(default_value))
        range_override = _RANGE_OVERRIDES.get(name, {})
        choices = _CHOICES_OVERRIDES.get(name)

        result[name] = ParamSpec(
            name=name,
            target_section=section_name,
            default_value=default_value,
            status=status,
            domain_type=domain_type,
            low=range_override.get("low"),
            high=range_override.get("high"),
            choices=choices,
            step=range_override.get("step"),
            reason=reason,
        )
    return result


@lru_cache(maxsize=1)
def build_param_registry() -> dict[str, ParamSpec]:
    registry = {}
    registry.update(_build_section_specs("strategy", StrategyConfig))
    registry.update(_build_section_specs("risk", RiskConfig))
    registry["force_order_history_points"] = ParamSpec(
        name="force_order_history_points",
        target_section="strategy",
        default_value=180,
        status=PARAM_STATUS_UNSUPPORTED,
        domain_type="int",
        low=30,
        high=500,
        step=1,
        reason="in FeatureEngineConfig only, not in StrategyConfig; not settable via AppSettings",
    )
    return registry


def get_active_params() -> dict[str, ParamSpec]:
    return {name: spec for name, spec in build_param_registry().items() if spec.status == PARAM_STATUS_ACTIVE}


def get_frozen_params() -> dict[str, ParamSpec]:
    return {name: spec for name, spec in build_param_registry().items() if spec.status == PARAM_STATUS_FROZEN}


def get_default_vector() -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for name, spec in build_param_registry().items():
        if spec.status == PARAM_STATUS_UNSUPPORTED:
            continue
        defaults[name] = spec.default_value
    return defaults


def split_to_strategy_risk(params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = build_param_registry()
    strategy_params: dict[str, Any] = {}
    risk_params: dict[str, Any] = {}

    unknown = [name for name in params if name not in registry]
    if unknown:
        raise KeyError(f"Unknown parameter(s): {', '.join(sorted(unknown))}")

    for name, value in params.items():
        spec = registry[name]
        if spec.status == PARAM_STATUS_UNSUPPORTED:
            raise ValueError(f"Unsupported parameter in current AppSettings API: {name}")
        if spec.target_section == "strategy":
            strategy_params[name] = value
            continue
        if spec.target_section == "risk":
            risk_params[name] = value
            continue
        raise ValueError(f"Unsupported target section for parameter {name}: {spec.target_section}")

    return strategy_params, risk_params
