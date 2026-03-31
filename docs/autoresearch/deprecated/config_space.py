"""
Parameter space definition for BTC bot research.
Analogous to train.py in karpathy/autoresearch — THIS IS THE FILE THE AGENT MODIFIES.

The agent adjusts:
  - Parameter ranges (widen, narrow, shift)
  - Which parameters to optimize vs. fix at defaults
  - Constraints between parameters
  - Multi-objective weighting
  - Optuna trial count
  - Walk-forward window sizes
  - Regime-conditional parameter spaces

All changes to this file are tracked via git, creating a full audit trail.
"""

import optuna
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Experiment Settings (agent can modify)
# ---------------------------------------------------------------------------

N_TRIALS = 200               # Number of Optuna trials per experiment
STUDY_NAME_PREFIX = "btc"    # Prefix for Optuna study names

# Walk-forward settings
WF_TRAIN_BARS = 500          # Training window (1h bars)
WF_TEST_BARS = 150           # Test window (1h bars)
WF_STEP_BARS = 150           # Step forward (1h bars)
WF_DEGRADATION_MAX = 0.30    # Max allowed degradation (30%)

# Fitness scalarization weights (must sum context, not necessarily 1.0)
FITNESS_WEIGHTS = {
    "expectancy_r": 0.4,
    "profit_factor": 0.3,
    "max_drawdown": 0.3,      # This is subtracted (penalty)
}

# ---------------------------------------------------------------------------
# Parameter Space Definition
# ---------------------------------------------------------------------------
# For each parameter, define:
#   - "type": "int" | "float" | "fixed"
#   - "low", "high": range bounds (for int/float)
#   - "default": production default value
#   - "value": fixed value (for type="fixed", skips optimization)
#
# To EXCLUDE a parameter from optimization, change its type to "fixed"
# and set "value" to the desired constant.
# To INCLUDE a parameter, set type to "int" or "float" with a range.
# ---------------------------------------------------------------------------

PARAM_SPACE: dict[str, dict[str, Any]] = {
    # === FeatureEngine ===
    "atr_period": {
        "type": "int", "low": 7, "high": 28, "default": 14,
    },
    "ema_fast": {
        "type": "int", "low": 20, "high": 100, "default": 50,
    },
    "ema_slow": {
        "type": "int", "low": 100, "high": 400, "default": 200,
    },
    "equal_level_lookback": {
        "type": "int", "low": 20, "high": 100, "default": 50,
    },
    "equal_level_tol_atr": {
        "type": "float", "low": 0.10, "high": 0.50, "default": 0.25,
    },
    "sweep_buf_atr": {
        "type": "float", "low": 0.05, "high": 0.30, "default": 0.15,
    },
    "reclaim_buf_atr": {
        "type": "float", "low": 0.01, "high": 0.15, "default": 0.05,
    },
    "wick_min_atr": {
        "type": "float", "low": 0.20, "high": 0.80, "default": 0.40,
    },
    "funding_window_days": {
        "type": "int", "low": 14, "high": 120, "default": 60,
    },
    "oi_z_window_days": {
        "type": "int", "low": 14, "high": 120, "default": 60,
    },

    # === RegimeEngine ===
    "ema_trend_gap_pct": {
        "type": "float", "low": 0.001, "high": 0.010, "default": 0.0025,
    },
    "compression_atr_norm_max": {
        "type": "float", "low": 0.002, "high": 0.010, "default": 0.0055,
    },
    "crowded_funding_extreme_pct": {
        "type": "float", "low": 70.0, "high": 95.0, "default": 85.0,
    },
    "crowded_oi_zscore_min": {
        "type": "float", "low": 0.5, "high": 3.0, "default": 1.5,
    },
    "post_liq_tfi_abs_min": {
        "type": "float", "low": 0.05, "high": 0.50, "default": 0.2,
    },

    # === SignalEngine ===
    "confluence_min": {
        "type": "float", "low": 1.5, "high": 5.0, "default": 3.0,
    },
    "min_sweep_depth_pct": {
        "type": "float", "low": 0.00005, "high": 0.001, "default": 0.0001,
    },
    "entry_offset_atr": {
        "type": "float", "low": 0.01, "high": 0.15, "default": 0.05,
    },
    "invalidation_offset_atr": {
        "type": "float", "low": 0.10, "high": 0.50, "default": 0.25,
    },
    "tp1_atr_mult": {
        "type": "float", "low": 1.0, "high": 4.0, "default": 2.0,
    },
    "tp2_atr_mult": {
        "type": "float", "low": 2.0, "high": 6.0, "default": 3.5,
    },
    "weight_sweep_detected": {
        "type": "float", "low": 0.0, "high": 2.0, "default": 1.25,
    },
    "weight_reclaim_confirmed": {
        "type": "float", "low": 0.0, "high": 2.0, "default": 1.25,
    },
    "weight_cvd_divergence": {
        "type": "float", "low": 0.0, "high": 2.0, "default": 0.75,
    },
    "weight_tfi_impulse": {
        "type": "float", "low": 0.0, "high": 2.0, "default": 0.50,
    },
    "weight_force_order_spike": {
        "type": "float", "low": 0.0, "high": 2.0, "default": 0.40,
    },
    "weight_regime_special": {
        "type": "float", "low": 0.0, "high": 2.0, "default": 0.35,
    },
    "weight_ema_trend_alignment": {
        "type": "float", "low": 0.0, "high": 2.0, "default": 0.25,
    },
    "weight_funding_supportive": {
        "type": "float", "low": 0.0, "high": 2.0, "default": 0.20,
    },
    "direction_tfi_threshold": {
        "type": "float", "low": 0.01, "high": 0.15, "default": 0.05,
    },
    "tfi_impulse_threshold": {
        "type": "float", "low": 0.05, "high": 0.25, "default": 0.10,
    },

    # === Governance ===
    "cooldown_minutes_after_loss": {
        "type": "int", "low": 15, "high": 180, "default": 60,
    },
    "duplicate_level_tolerance_pct": {
        "type": "float", "low": 0.0005, "high": 0.005, "default": 0.001,
    },
    "duplicate_level_window_hours": {
        "type": "int", "low": 6, "high": 72, "default": 24,
    },
    "max_trades_per_day": {
        "type": "int", "low": 1, "high": 10, "default": 3,
    },
    "max_consecutive_losses": {
        "type": "int", "low": 1, "high": 5, "default": 3,
    },
    "daily_dd_limit": {
        "type": "float", "low": 0.01, "high": 0.10, "default": 0.03,
    },
    "weekly_dd_limit": {
        "type": "float", "low": 0.03, "high": 0.15, "default": 0.06,
    },
    "session_start_hour_utc": {
        "type": "int", "low": 0, "high": 23, "default": 0,
    },
    "session_end_hour_utc": {
        "type": "int", "low": 0, "high": 23, "default": 23,
    },

    # === Risk ===
    "risk_per_trade_pct": {
        "type": "float", "low": 0.005, "high": 0.03, "default": 0.01,
    },
    "max_leverage": {
        "type": "int", "low": 2, "high": 10, "default": 5,
    },
    "high_vol_leverage": {
        "type": "int", "low": 1, "high": 5, "default": 3,
    },
    "min_rr": {
        "type": "float", "low": 1.5, "high": 5.0, "default": 2.8,
    },
    "max_open_positions": {
        "type": "int", "low": 1, "high": 4, "default": 2,
    },
    "max_hold_hours": {
        "type": "int", "low": 4, "high": 72, "default": 24,
    },
    "high_vol_stop_distance_pct": {
        "type": "float", "low": 0.005, "high": 0.03, "default": 0.01,
    },
}


# ---------------------------------------------------------------------------
# Suggest params for an Optuna trial
# ---------------------------------------------------------------------------

def suggest_params(trial: optuna.Trial) -> dict[str, Any]:
    """
    Map PARAM_SPACE to Optuna trial suggestions.
    Parameters with type="fixed" are set to their fixed value.
    """
    params = {}
    for name, spec in PARAM_SPACE.items():
        if spec["type"] == "fixed":
            params[name] = spec["value"]
        elif spec["type"] == "int":
            params[name] = trial.suggest_int(name, spec["low"], spec["high"])
        elif spec["type"] == "float":
            params[name] = trial.suggest_float(name, spec["low"], spec["high"])
        else:
            raise ValueError(f"Unknown param type: {spec['type']} for {name}")
    return params


def get_defaults() -> dict[str, Any]:
    """Return all parameters at their default (production) values."""
    return {
        name: spec.get("value", spec["default"])
        for name, spec in PARAM_SPACE.items()
    }


# ---------------------------------------------------------------------------
# Cross-parameter constraints
# ---------------------------------------------------------------------------

def check_constraints(params: dict[str, Any]) -> bool:
    """
    Validate cross-parameter constraints. Returns True if valid.
    Add/modify constraints here as needed.
    """
    # EMA fast must be less than EMA slow
    if params.get("ema_fast", 50) >= params.get("ema_slow", 200):
        return False

    # TP1 must be less than TP2
    if params.get("tp1_atr_mult", 2.0) >= params.get("tp2_atr_mult", 3.5):
        return False

    # High vol leverage must not exceed max leverage
    if params.get("high_vol_leverage", 3) > params.get("max_leverage", 5):
        return False

    # Daily DD limit must be less than weekly
    if params.get("daily_dd_limit", 0.03) >= params.get("weekly_dd_limit", 0.06):
        return False

    return True


# ---------------------------------------------------------------------------
# Build frozen configs from flat param dict
# ---------------------------------------------------------------------------

def build_configs(params: dict[str, Any]) -> dict[str, Any]:
    """
    Convert flat parameter dict into engine-specific frozen dataclass configs.

    ADAPT THIS to your actual settings.py dataclass structure.
    The mapping below assumes your configs accept these keyword arguments.
    """
    from settings import (
        FeatureEngineConfig, RegimeEngineConfig, SignalEngineConfig,
        GovernanceConfig, RiskConfig
    )

    feature = FeatureEngineConfig(
        atr_period=params.get("atr_period", 14),
        ema_fast=params.get("ema_fast", 50),
        ema_slow=params.get("ema_slow", 200),
        equal_level_lookback=params.get("equal_level_lookback", 50),
        equal_level_tol_atr=params.get("equal_level_tol_atr", 0.25),
        sweep_buf_atr=params.get("sweep_buf_atr", 0.15),
        reclaim_buf_atr=params.get("reclaim_buf_atr", 0.05),
        wick_min_atr=params.get("wick_min_atr", 0.40),
        funding_window_days=params.get("funding_window_days", 60),
        oi_z_window_days=params.get("oi_z_window_days", 60),
    )

    regime = RegimeEngineConfig(
        ema_trend_gap_pct=params.get("ema_trend_gap_pct", 0.0025),
        compression_atr_norm_max=params.get("compression_atr_norm_max", 0.0055),
        crowded_funding_extreme_pct=params.get("crowded_funding_extreme_pct", 85.0),
        crowded_oi_zscore_min=params.get("crowded_oi_zscore_min", 1.5),
        post_liq_tfi_abs_min=params.get("post_liq_tfi_abs_min", 0.2),
    )

    signal = SignalEngineConfig(
        confluence_min=params.get("confluence_min", 3.0),
        min_sweep_depth_pct=params.get("min_sweep_depth_pct", 0.0001),
        entry_offset_atr=params.get("entry_offset_atr", 0.05),
        invalidation_offset_atr=params.get("invalidation_offset_atr", 0.25),
        tp1_atr_mult=params.get("tp1_atr_mult", 2.0),
        tp2_atr_mult=params.get("tp2_atr_mult", 3.5),
        weight_sweep_detected=params.get("weight_sweep_detected", 1.25),
        weight_reclaim_confirmed=params.get("weight_reclaim_confirmed", 1.25),
        weight_cvd_divergence=params.get("weight_cvd_divergence", 0.75),
        weight_tfi_impulse=params.get("weight_tfi_impulse", 0.50),
        weight_force_order_spike=params.get("weight_force_order_spike", 0.40),
        weight_regime_special=params.get("weight_regime_special", 0.35),
        weight_ema_trend_alignment=params.get("weight_ema_trend_alignment", 0.25),
        weight_funding_supportive=params.get("weight_funding_supportive", 0.20),
        direction_tfi_threshold=params.get("direction_tfi_threshold", 0.05),
        tfi_impulse_threshold=params.get("tfi_impulse_threshold", 0.10),
    )

    governance = GovernanceConfig(
        cooldown_minutes_after_loss=params.get("cooldown_minutes_after_loss", 60),
        duplicate_level_tolerance_pct=params.get("duplicate_level_tolerance_pct", 0.001),
        duplicate_level_window_hours=params.get("duplicate_level_window_hours", 24),
        max_trades_per_day=params.get("max_trades_per_day", 3),
        max_consecutive_losses=params.get("max_consecutive_losses", 3),
        daily_dd_limit=params.get("daily_dd_limit", 0.03),
        weekly_dd_limit=params.get("weekly_dd_limit", 0.06),
        session_start_hour_utc=params.get("session_start_hour_utc", 0),
        session_end_hour_utc=params.get("session_end_hour_utc", 23),
    )

    risk = RiskConfig(
        risk_per_trade_pct=params.get("risk_per_trade_pct", 0.01),
        max_leverage=params.get("max_leverage", 5),
        high_vol_leverage=params.get("high_vol_leverage", 3),
        min_rr=params.get("min_rr", 2.8),
        max_open_positions=params.get("max_open_positions", 2),
        max_hold_hours=params.get("max_hold_hours", 24),
        high_vol_stop_distance_pct=params.get("high_vol_stop_distance_pct", 0.01),
    )

    return {
        "feature": feature,
        "regime": regime,
        "signal": signal,
        "governance": governance,
        "risk": risk,
    }
