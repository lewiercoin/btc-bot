from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from core.models import SessionBucket, VolatilityBucket


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
    sweep_proximity_atr: float = 0.4
    reclaim_buf_atr: float = 0.19
    wick_min_atr: float = 0.15
    level_min_age_bars: int = 5
    min_hits: int = 3

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
class SymbolStrategyOverride:
    symbol: str
    min_sweep_depth_pct: float | None = None


@dataclass(frozen=True)
class MultiAssetConfig:
    enabled: bool = False
    enabled_symbols: tuple[str, ...] = ("BTCUSDT",)
    symbol_overrides: tuple[SymbolStrategyOverride, ...] = ()
    max_total_risk_pct_open: float = 0.0070
    max_gross_notional_pct: float = 1.0
    max_directional_notional_pct: float = 0.75
    max_open_positions_total: int = 2
    max_open_positions_per_symbol: int = 1


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
    health_failures_before_safe_mode: int = 10  # Raised for initial config phase (was: 3)
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
class ContextConfig:
    atr_low_threshold: float = 0.002
    atr_high_threshold: float = 0.004
    session_volatility_whitelist: dict[
        SessionBucket, tuple[VolatilityBucket, ...]
    ] = field(
        default_factory=lambda: {
            SessionBucket.ASIA: (
                VolatilityBucket.LOW,
                VolatilityBucket.NORMAL,
                VolatilityBucket.HIGH,
            ),
            SessionBucket.EU: (
                VolatilityBucket.LOW,
                VolatilityBucket.NORMAL,
                VolatilityBucket.HIGH,
            ),
            SessionBucket.EU_US: (
                VolatilityBucket.LOW,
                VolatilityBucket.NORMAL,
                VolatilityBucket.HIGH,
            ),
            SessionBucket.US: (
                VolatilityBucket.LOW,
                VolatilityBucket.NORMAL,
                VolatilityBucket.HIGH,
            ),
        }
    )
    neutral_mode: bool = True
    policy_version: str = "v1.0.0"


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
    futures_ws_market_base_url: str = "wss://fstream.binance.com/stream"
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
    multi_asset: MultiAssetConfig = field(default_factory=MultiAssetConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    data_quality: DataQualityConfig = field(default_factory=DataQualityConfig)
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    storage: StorageConfig | None = None
    context: ContextConfig = field(default_factory=ContextConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)

    @property
    def config_hash(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "mode": self.mode.value,
            "strategy": asdict(self.strategy),
            "multi_asset": asdict(self.multi_asset),
            "risk": asdict(self.risk),
            "execution": asdict(self.execution),
            "data_quality": asdict(self.data_quality),
            "context": {
                "atr_low_threshold": self.context.atr_low_threshold,
                "atr_high_threshold": self.context.atr_high_threshold,
                "neutral_mode": self.context.neutral_mode,
                "policy_version": self.context.policy_version,
                "session_volatility_whitelist": {
                    k.value: sorted(v.value for v in vs)
                    for k, vs in self.context.session_volatility_whitelist.items()
                },
            },
            "exchange": {
                "futures_rest_base_url": self.exchange.futures_rest_base_url,
                "futures_ws_base_url": self.exchange.futures_ws_base_url,
                "futures_ws_market_base_url": self.exchange.futures_ws_market_base_url,
                "futures_ws_stream_base_url": self.exchange.futures_ws_stream_base_url,
                "recv_window_ms": self.exchange.recv_window_ms,
                "isolated_only": self.exchange.isolated_only,
                "api_key_env": self.exchange.api_key_env,
                "api_secret_env": self.exchange.api_secret_env,
            },
            "proxy": {
                "enabled": self.proxy.enabled,
                "proxy_enabled_env": self.proxy.proxy_enabled_env,
                "proxy_url_env": self.proxy.proxy_url_env,
                "proxy_type_env": self.proxy.proxy_type_env,
                "sticky_minutes_env": self.proxy.sticky_minutes_env,
                "failover_list_env": self.proxy.failover_list_env,
            },
            "alerts": {
                "telegram_enabled": self.alerts.telegram_enabled,
                "telegram_bot_token_env": self.alerts.telegram_bot_token_env,
                "telegram_chat_id_env": self.alerts.telegram_chat_id_env,
            },
            "storage": {
                "project_root": str(self.storage.project_root) if self.storage else None,
                "db_path": str(self.storage.db_path) if self.storage else None,
                "schema_path": str(self.storage.schema_path) if self.storage else None,
                "logs_dir": str(self.storage.logs_dir) if self.storage else None,
            },
            "python_version": self._get_python_version(),
            "dependency_hash": self._get_dependency_hash(),
            "settings_profile": os.getenv("BOT_SETTINGS_PROFILE", "unknown"),
        }
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def _get_python_version(self) -> str:
        """Read Python version from .python-version file."""
        if self.storage:
            python_version_file = self.storage.project_root / ".python-version"
            if python_version_file.exists():
                return python_version_file.read_text().strip()
        return "unknown"

    def _get_dependency_hash(self) -> str:
        """Compute hash of requirements.lock for dependency tracking."""
        if self.storage:
            lockfile = self.storage.project_root / "requirements.lock"
            if lockfile.exists():
                data = lockfile.read_bytes()
                return hashlib.sha256(data).hexdigest()
        return "unknown"


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


def validate_multi_asset_config(config: MultiAssetConfig) -> MultiAssetConfig:
    symbols = tuple(symbol.upper() for symbol in config.enabled_symbols)
    if not symbols:
        raise ValueError("multi_asset.enabled_symbols must contain at least one symbol.")
    if len(set(symbols)) != len(symbols):
        raise ValueError("multi_asset.enabled_symbols contains duplicate symbols.")
    if not config.enabled and len(symbols) > 1:
        raise ValueError("multi_asset.enabled must be true when more than one symbol is enabled.")
    if config.enabled and "BTCUSDT" not in symbols:
        raise ValueError("multi_asset.enabled requires BTCUSDT in enabled_symbols.")

    overrides: list[SymbolStrategyOverride] = []
    seen_overrides: set[str] = set()
    for override in config.symbol_overrides:
        symbol = override.symbol.upper()
        if symbol in seen_overrides:
            raise ValueError(f"Duplicate multi_asset.symbol_overrides entry for {symbol}.")
        if symbol not in symbols:
            raise ValueError(f"Override symbol {symbol} is not listed in multi_asset.enabled_symbols.")
        seen_overrides.add(symbol)
        overrides.append(dataclasses.replace(override, symbol=symbol))

    normalized = dataclasses.replace(config, enabled_symbols=symbols, symbol_overrides=tuple(overrides))
    if normalized.max_total_risk_pct_open <= 0:
        raise ValueError("multi_asset.max_total_risk_pct_open must be positive.")
    if normalized.max_gross_notional_pct <= 0:
        raise ValueError("multi_asset.max_gross_notional_pct must be positive.")
    if normalized.max_directional_notional_pct <= 0:
        raise ValueError("multi_asset.max_directional_notional_pct must be positive.")
    if normalized.max_open_positions_total < 1:
        raise ValueError("multi_asset.max_open_positions_total must be at least 1.")
    if normalized.max_open_positions_per_symbol < 1:
        raise ValueError("multi_asset.max_open_positions_per_symbol must be at least 1.")
    return normalized


def resolve_symbol_config(
    baseline: StrategyConfig,
    symbol: str,
    multi_asset: MultiAssetConfig,
) -> StrategyConfig:
    normalized_symbol = symbol.upper()
    validated = validate_multi_asset_config(multi_asset)
    override = next((item for item in validated.symbol_overrides if item.symbol == normalized_symbol), None)
    if override is None:
        return dataclasses.replace(baseline, symbol=normalized_symbol)

    values: dict[str, Any] = {"symbol": normalized_symbol}
    if override.min_sweep_depth_pct is not None:
        values["min_sweep_depth_pct"] = override.min_sweep_depth_pct
    return dataclasses.replace(baseline, **values)


def _load_runtime_overlay(root: Path) -> dict[str, Any]:
    raw_path = os.getenv("BOT_SETTINGS_PATH")
    overlay_path = Path(raw_path) if raw_path else root / "settings.json"
    if not overlay_path.exists():
        return {}
    payload = json.loads(overlay_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Runtime settings overlay must be a JSON object: {overlay_path}")
    return payload


def _section_overrides(payload: dict[str, Any], section: str, cfg_type: type[Any]) -> dict[str, Any]:
    raw = payload.get(section, {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"Runtime settings overlay section {section!r} must be a JSON object.")

    allowed = {field.name for field in dataclasses.fields(cfg_type)}
    unknown = sorted(set(raw) - allowed)
    if unknown:
        names = ", ".join(unknown)
        raise ValueError(f"Unknown {section} runtime setting(s): {names}")
    return dict(raw)


def _apply_runtime_overlay(settings: AppSettings, *, root: Path, profile: str) -> AppSettings:
    if profile not in {"live", "experiment"}:
        return settings

    payload = _load_runtime_overlay(root)
    if not payload:
        return settings

    if "schema_version" in payload and payload["schema_version"] != settings.schema_version:
        raise ValueError(
            f"Runtime settings overlay schema_version={payload['schema_version']!r} "
            f"does not match settings schema_version={settings.schema_version!r}."
        )

    strategy_overrides = _section_overrides(payload, "strategy", StrategyConfig)
    risk_overrides = _section_overrides(payload, "risk", RiskConfig)
    strategy = dataclasses.replace(settings.strategy, **strategy_overrides)
    risk = dataclasses.replace(settings.risk, **risk_overrides)
    return dataclasses.replace(settings, strategy=strategy, risk=risk)


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
    settings = dataclasses.replace(settings, multi_asset=validate_multi_asset_config(settings.multi_asset))
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
        live_settings = dataclasses.replace(settings, strategy=live_strategy)
        return _apply_runtime_overlay(live_settings, root=root, profile=profile)

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
    experiment_settings = dataclasses.replace(settings, strategy=experiment_strategy, risk=experiment_risk)
    return _apply_runtime_overlay(experiment_settings, root=root, profile=profile)


SETTINGS = load_settings()
SETTINGS_DICT = _serialize_settings(SETTINGS)
