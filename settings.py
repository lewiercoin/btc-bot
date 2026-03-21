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


@dataclass(frozen=True)
class ExecutionConfig:
    entry_timeout_seconds: int = 90
    position_monitor_interval_seconds: int = 15
    decision_cycle_on_15m_close: bool = True
    rest_timeout_seconds: int = 10
    ws_heartbeat_seconds: int = 30
    ws_reconnect_seconds: int = 5


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
