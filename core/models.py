from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

Direction = Literal["LONG", "SHORT"]
PositionStatus = Literal["OPEN", "PARTIAL", "CLOSED"]
BotMode = Literal["PAPER", "LIVE"]


class RegimeState(str, Enum):
    NORMAL = "normal"
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    COMPRESSION = "compression"
    CROWDED_LEVERAGE = "crowded_leverage"
    POST_LIQUIDATION = "post_liquidation"


@dataclass(slots=True)
class MarketSnapshot:
    symbol: str
    timestamp: datetime
    price: float
    bid: float
    ask: float
    candles_15m: list[dict[str, Any]] = field(default_factory=list)
    candles_1h: list[dict[str, Any]] = field(default_factory=list)
    candles_4h: list[dict[str, Any]] = field(default_factory=list)
    funding_history: list[dict[str, Any]] = field(default_factory=list)
    open_interest: float = 0.0
    aggtrades_bucket_60s: dict[str, Any] = field(default_factory=dict)
    aggtrades_bucket_15m: dict[str, Any] = field(default_factory=dict)
    force_order_events_60s: list[dict[str, Any]] = field(default_factory=list)
    etf_bias_daily: float | None = None
    dxy_daily: float | None = None


@dataclass(slots=True)
class Features:
    schema_version: str
    config_hash: str
    timestamp: datetime
    atr_15m: float
    atr_4h: float
    atr_4h_norm: float
    ema50_4h: float
    ema200_4h: float
    equal_lows: list[float] = field(default_factory=list)
    equal_highs: list[float] = field(default_factory=list)
    sweep_detected: bool = False
    reclaim_detected: bool = False
    sweep_level: float | None = None
    sweep_depth_pct: float | None = None
    sweep_side: str | None = None
    funding_8h: float = 0.0
    funding_sma3: float = 0.0
    funding_sma9: float = 0.0
    funding_pct_60d: float = 0.0
    oi_value: float = 0.0
    oi_zscore_60d: float = 0.0
    oi_delta_pct: float = 0.0
    cvd_15m: float = 0.0
    cvd_bullish_divergence: bool = False
    cvd_bearish_divergence: bool = False
    tfi_60s: float = 0.0
    force_order_rate_60s: float = 0.0
    force_order_spike: bool = False
    force_order_decreasing: bool = False
    passive_etf_bias_5d: float | None = None


@dataclass(slots=True)
class SignalCandidate:
    signal_id: str
    timestamp: datetime
    direction: Direction
    setup_type: str
    entry_reference: float
    invalidation_level: float
    tp_reference_1: float
    tp_reference_2: float
    confluence_score: float
    regime: RegimeState
    reasons: list[str] = field(default_factory=list)
    features_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutableSignal:
    signal_id: str
    timestamp: datetime
    direction: Direction
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    rr_ratio: float
    approved_by_governance: bool
    governance_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Position:
    position_id: str
    symbol: str
    direction: Direction
    status: PositionStatus
    entry_price: float
    size: float
    leverage: int
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    opened_at: datetime
    updated_at: datetime
    signal_id: str


@dataclass(slots=True)
class TradeLog:
    trade_id: str
    signal_id: str
    opened_at: datetime
    closed_at: datetime | None
    direction: str
    regime: str
    confluence_score: float
    entry_price: float
    exit_price: float | None
    size: float
    fees: float
    slippage_bps: float
    pnl_abs: float
    pnl_r: float
    mae: float
    mfe: float
    exit_reason: str | None
    features_at_entry_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DailyStats:
    day: date
    trades_count: int
    wins: int
    losses: int
    pnl_abs: float
    pnl_r_sum: float
    daily_dd_pct: float
    expectancy_r: float


@dataclass(slots=True)
class BotState:
    mode: BotMode
    healthy: bool
    safe_mode: bool
    open_positions_count: int
    consecutive_losses: int
    daily_dd_pct: float
    weekly_dd_pct: float
    last_trade_at: datetime | None
    last_error: str | None
    safe_mode_entry_at: datetime | None = None


@dataclass(slots=True)
class GovernanceRuntimeState:
    trades_today: int = 0
    consecutive_losses: int = 0
    daily_dd_pct: float = 0.0
    weekly_dd_pct: float = 0.0
    last_trade_at: datetime | None = None
    last_loss_at: datetime | None = None


@dataclass(slots=True)
class RiskRuntimeState:
    consecutive_losses: int = 0
    daily_dd_pct: float = 0.0
    weekly_dd_pct: float = 0.0


@dataclass(slots=True)
class SettlementMetrics:
    exit_price: float
    pnl_abs: float
    pnl_r: float
    mae: float
    mfe: float
    exit_reason: str
