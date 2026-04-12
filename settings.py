from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class BotMode(StrEnum):
    PAPER = "PAPER"
    LIVE = "LIVE"


def _default_regime_direction_whitelist() -> dict[str, tuple[str, ...]]:
    return {
        "normal": ("LONG",),
        "compression": ("LONG",),
        "downtrend": ("LONG", "SHORT"),
        "uptrend": (),
        "crowded_leverage": ("SHORT",),
        "post_liquidation": ("LONG",),
    }


def build_signal_regime_direction_whitelist(strategy: "StrategyConfig") -> dict[str, tuple[str, ...]]:
    whitelist = {
        regime: tuple(allowed_directions)
        for regime, allowed_directions in strategy.regime_direction_whitelist.items()
    }
    if not strategy.allow_long_in_uptrend:
        return whitelist

    existing = list(whitelist.get("uptrend", ()))
    if "LONG" not in existing:
        existing.append("LONG")
    whitelist["uptrend"] = tuple(existing)
    return whitelist


@dataclass(frozen=True)
class StrategyConfig:
    symbol: str = "BTCUSDT"
    tf_setup: str = "15m"
    tf_context: str = "1h"
    tf_bias: str = "4h"
    flow_bucket_tf: str = "60s"

    atr_period: int = 14
    ema_fast: int = 50
    ema_slow: int = 200

    equal_level_lookback: int = 50
    equal_level_tol_atr: float = 0.25
    sweep_buf_atr: float = 0.15
    reclaim_buf_atr: float = 0.05
    wick_min_atr: float = 0.40

    funding_window_days: int = 60
    oi_z_window_days: int = 60
    confluence_min: float = 3.0
    ema_trend_gap_pct: float = 0.0025
    compression_atr_norm_max: float = 0.0055
    crowded_funding_extreme_pct: float = 85.0
    crowded_oi_zscore_min: float = 1.5
    post_liq_tfi_abs_min: float = 0.2

    min_sweep_depth_pct: float = 0.0001
    entry_offset_atr: float = 0.05
    invalidation_offset_atr: float = 0.75
    min_stop_distance_pct: float = 0.0015
    tp1_atr_mult: float = 2.5
    tp2_atr_mult: float = 4.0
    weight_sweep_detected: float = 1.25
    weight_reclaim_confirmed: float = 1.25
    weight_cvd_divergence: float = 0.75
    weight_tfi_impulse: float = 0.50
    weight_force_order_spike: float = 0.40
    weight_regime_special: float = 0.35
    weight_ema_trend_alignment: float = 0.25
    weight_funding_supportive: float = 0.20
    direction_tfi_threshold: float = 0.05
    direction_tfi_threshold_inverse: float = -0.05
    tfi_impulse_threshold: float = 0.10
    allow_long_in_uptrend: bool = False
    regime_direction_whitelist: dict[str, tuple[str, ...]] = field(default_factory=_default_regime_direction_whitelist)


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade_pct: float = 0.01
    max_leverage: int = 5
    high_vol_leverage: int = 3
    min_rr: float = 2.8

    max_open_positions: int = 2
    max_trades_per_day: int = 3
    max_consecutive_losses: int = 3
    daily_dd_limit: float = 0.03
    weekly_dd_limit: float = 0.06
    max_hold_hours: int = 24
    high_vol_stop_distance_pct: float = 0.01
    partial_exit_pct: float = 0.5
    trailing_atr_mult: float = 1.0

    cooldown_minutes_after_loss: int = 60
    duplicate_level_tolerance_pct: float = 0.001
    duplicate_level_window_hours: int = 24
    session_start_hour_utc: int = 0
    session_end_hour_utc: int = 23
    no_trade_windows_utc: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class ExecutionConfig:
    entry_timeout_seconds: int = 90
    position_monitor_interval_seconds: int = 15
    decision_cycle_on_15m_close: bool = True
    rest_timeout_seconds: int = 10
    ws_heartbeat_seconds: int = 30
    ws_reconnect_seconds: int = 5
    live_entry_order_type: str = "LIMIT"
    live_fill_poll_seconds: float = 1.0
    health_check_interval_seconds: int = 30
    health_failures_before_safe_mode: int = 3
    kill_switch_max_exec_errors: int = 2
    loop_idle_sleep_seconds: float = 0.5


@dataclass(frozen=True)
class ExchangeConfig:
    futures_rest_base_url: str = "https://fapi.binance.com"
    futures_ws_base_url: str = "wss://fstream.binance.com/ws"
    recv_window_ms: int = 5000
    isolated_only: bool = True
    api_key_env: str = "BINANCE_API_KEY"
    api_secret_env: str = "BINANCE_API_SECRET"

    @property
    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "")

    @property
    def api_secret(self) -> str:
        return os.getenv(self.api_secret_env, "")


@dataclass(frozen=True)
class StorageConfig:
    project_root: Path
    db_path: Path
    schema_path: Path
    logs_dir: Path


@dataclass(frozen=True)
class AlertConfig:
    telegram_enabled: bool = False
    telegram_bot_token_env: str = "TELEGRAM_BOT_TOKEN"
    telegram_chat_id_env: str = "TELEGRAM_CHAT_ID"

    @property
    def telegram_bot_token(self) -> str:
        return os.getenv(self.telegram_bot_token_env, "")

    @property
    def telegram_chat_id(self) -> str:
        return os.getenv(self.telegram_chat_id_env, "")


@dataclass(frozen=True)
class AppSettings:
    schema_version: str
    mode: BotMode
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    storage: StorageConfig | None = None
    alerts: AlertConfig = field(default_factory=AlertConfig)

    @property
    def config_hash(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "mode": self.mode.value,
            "strategy": asdict(self.strategy),
            "risk": asdict(self.risk),
            "execution": asdict(self.execution),
        }
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(data).hexdigest()


def _parse_mode(raw_mode: str) -> BotMode:
    try:
        return BotMode(raw_mode.upper())
    except ValueError as exc:
        raise ValueError(f"Invalid BOT_MODE={raw_mode!r}. Use PAPER or LIVE.") from exc


def _serialize_settings(settings: AppSettings) -> dict[str, Any]:
    payload = asdict(settings)
    payload["mode"] = settings.mode.value
    if settings.storage:
        payload["storage"]["project_root"] = str(settings.storage.project_root)
        payload["storage"]["db_path"] = str(settings.storage.db_path)
        payload["storage"]["schema_path"] = str(settings.storage.schema_path)
        payload["storage"]["logs_dir"] = str(settings.storage.logs_dir)
    payload["config_hash"] = settings.config_hash
    return payload


def load_settings(project_root: Path | None = None) -> AppSettings:
    root = project_root or Path(__file__).resolve().parent
    mode = _parse_mode(os.getenv("BOT_MODE", "PAPER"))
    storage = StorageConfig(
        project_root=root,
        db_path=root / "storage" / "btc_bot.db",
        schema_path=root / "storage" / "schema.sql",
        logs_dir=root / "logs",
    )
    return AppSettings(
        schema_version="v1.0",
        mode=mode,
        storage=storage,
    )


SETTINGS = load_settings()
SETTINGS_DICT = _serialize_settings(SETTINGS)
