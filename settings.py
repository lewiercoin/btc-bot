from __future__ import annotations

import dataclasses
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


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _validate_profile(profile: str, *, allowed: tuple[str, ...]) -> str:
    normalized = profile.strip().lower()
    if normalized not in allowed:
        allowed_str = "', '".join(allowed)
        raise ValueError(f"Invalid settings profile {profile!r}. Use '{allowed_str}'.")
    return normalized


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

    equal_level_lookback: int = 196
    equal_level_tol_atr: float = 0.02
    sweep_buf_atr: float = 0.17
    reclaim_buf_atr: float = 0.19
    wick_min_atr: float = 0.15

    funding_window_days: int = 82
    oi_z_window_days: int = 62
    confluence_min: float = 4.5
    ema_trend_gap_pct: float = 0.0063
    compression_atr_norm_max: float = 0.0023
    crowded_funding_extreme_pct: float = 85.0
    crowded_oi_zscore_min: float = 1.5
    post_liq_tfi_abs_min: float = 0.53

    min_sweep_depth_pct: float = 0.00286
    entry_offset_atr: float = 0.01
    invalidation_offset_atr: float = 0.01
    min_stop_distance_pct: float = 0.0032
    tp1_atr_mult: float = 1.9
    tp2_atr_mult: float = 3.9
    weight_sweep_detected: float = 2.1
    weight_reclaim_confirmed: float = 4.25
    weight_cvd_divergence: float = 3.9
    weight_tfi_impulse: float = 1.4
    weight_force_order_spike: float = 0.40
    weight_regime_special: float = 2.35
    weight_ema_trend_alignment: float = 5.0
    weight_funding_supportive: float = 4.45
    direction_tfi_threshold: float = 0.08
    direction_tfi_threshold_inverse: float = -0.05
    tfi_impulse_threshold: float = 0.13
    allow_long_in_uptrend: bool = True
    allow_uptrend_pullback: bool = False
    uptrend_pullback_tfi_threshold: float = 0.13
    uptrend_pullback_min_sweep_depth_pct: float = 0.0030
    uptrend_pullback_confluence_min: float = 8.0
    regime_direction_whitelist: dict[str, tuple[str, ...]] = field(default_factory=_default_regime_direction_whitelist)


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade_pct: float = 0.007
    max_leverage: int = 8
    high_vol_leverage: int = 8
    min_rr: float = 2.1

    max_open_positions: int = 1
    max_trades_per_day: int = 3
    max_consecutive_losses: int = 15
    daily_dd_limit: float = 0.20
    weekly_dd_limit: float = 0.30
    max_hold_hours: int = 3
    high_vol_stop_distance_pct: float = 0.035
    partial_exit_pct: float = 0.26
    trailing_atr_mult: float = 2.9

    cooldown_minutes_after_loss: int = 95
    duplicate_level_tolerance_pct: float = 0.0007
    duplicate_level_window_hours: int = 114
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
class DataQualityConfig:
    oi_baseline_days: int = 60
    cvd_divergence_bars: int = 30
    flow_coverage_ready: float = 0.90
    flow_coverage_degraded: float = 0.70
    funding_coverage_ready: float = 0.90
    funding_coverage_degraded: float = 0.70


@dataclass(frozen=True)
class ProxyConfig:
    enabled: bool = False
    proxy_enabled_env: str = "PROXY_ENABLED"
    proxy_url_env: str = "PROXY_URL"
    proxy_type_env: str = "PROXY_TYPE"
    sticky_minutes_env: str = "PROXY_STICKY_MINUTES"
    failover_list_env: str = "PROXY_FAILOVER_LIST"

    @property
    def proxy_enabled(self) -> bool:
        raw = os.getenv(self.proxy_enabled_env, "false").lower()
        return raw in ("true", "1", "yes", "y")

    @property
    def proxy_url(self) -> str:
        return os.getenv(self.proxy_url_env, "")

    @property
    def proxy_type(self) -> str:
        return os.getenv(self.proxy_type_env, "http").lower()

    @property
    def sticky_minutes(self) -> int:
        try:
            return int(os.getenv(self.sticky_minutes_env, "30"))
        except ValueError:
            return 30

    @property
    def failover_list(self) -> list[str]:
        raw = os.getenv(self.failover_list_env, "")
        if not raw:
            return []
        return [url.strip() for url in raw.split(",") if url.strip()]


@dataclass(frozen=True)
class ExchangeConfig:
    futures_rest_base_url: str = "https://fapi.binance.com"
    futures_ws_base_url: str = "wss://fstream.binance.com/ws"
    futures_ws_market_base_url: str = "wss://fstream.binance.com/market"
    futures_ws_stream_base_url: str = "wss://fstream.binance.com/stream"
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
    data_quality: DataQualityConfig = field(default_factory=DataQualityConfig)
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
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
            "data_quality": asdict(self.data_quality),
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


def load_settings(project_root: Path | None = None, *, profile: str = "research") -> AppSettings:
    root = project_root or Path(__file__).resolve().parent
    mode = _parse_mode(os.getenv("BOT_MODE", "PAPER"))
    profile = _validate_profile(profile, allowed=("research", "live", "experiment"))
    storage = StorageConfig(
        project_root=root,
        db_path=root / "storage" / "btc_bot.db",
        schema_path=root / "storage" / "schema.sql",
        logs_dir=root / "logs",
    )
    settings = AppSettings(
        schema_version="v1.0",
        mode=mode,
        storage=storage,
    )
    research_strategy = dataclasses.replace(
        settings.strategy,
        allow_uptrend_pullback=_env_flag("ALLOW_UPTREND_PULLBACK", settings.strategy.allow_uptrend_pullback),
    )
    if profile == "research":
        return dataclasses.replace(settings, strategy=research_strategy)

    live_strategy = dataclasses.replace(
        research_strategy,
        min_sweep_depth_pct=0.0001,
        confluence_min=4.5,
        allow_uptrend_pullback=False,
    )
    if profile == "live":
        return dataclasses.replace(settings, strategy=live_strategy)

    experiment_whitelist = {
        regime: tuple(allowed_directions)
        for regime, allowed_directions in live_strategy.regime_direction_whitelist.items()
    }
    experiment_whitelist["crowded_leverage"] = ("LONG", "SHORT")
    experiment_strategy = dataclasses.replace(
        live_strategy,
        confluence_min=3.6,
        direction_tfi_threshold=0.05,
        direction_tfi_threshold_inverse=-0.03,
        tfi_impulse_threshold=0.10,
        regime_direction_whitelist=experiment_whitelist,
    )
    experiment_risk = dataclasses.replace(
        settings.risk,
        min_rr=1.6,
        max_open_positions=2,
        max_trades_per_day=6,
        cooldown_minutes_after_loss=30,
        duplicate_level_tolerance_pct=0.0004,
        duplicate_level_window_hours=24,
    )
    return dataclasses.replace(settings, strategy=experiment_strategy, risk=experiment_risk)


SETTINGS = load_settings()
SETTINGS_DICT = _serialize_settings(SETTINGS)
