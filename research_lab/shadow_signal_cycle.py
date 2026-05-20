"""Real shadow signal diagnostics for the multi-asset sidecar.

This module is intentionally self-contained under research_lab. It does not
import runtime data collectors, execution code, orchestrator code, or production
storage. The active systemd heartbeat does not call this module until a later
audited deployment changes the timer command.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from research_lab.models.portfolio_state import (
    PortfolioRiskConfig,
    PortfolioRiskState,
    PortfolioSignal,
    ResearchPortfolioGate,
    SYMBOL_ORDER,
    SymbolRiskState,
)


MIN_SWEEP_DEPTH_PCT = 0.00649
ETH_SHADOW_MIN_SWEEP_DEPTH_PCT = 0.0075
NEAR_MISS_FLOOR_MULT = 0.80
STRATEGY_PROFILE = "trial_00095_transfer"


@dataclass(frozen=True)
class ShadowSymbolConfig:
    symbol: str
    risk_policy_profile: str
    shadow_mode: str
    candidate_risk_pct: float
    min_sweep_depth_pct: float = MIN_SWEEP_DEPTH_PCT


@dataclass(frozen=True)
class ShadowCandle:
    open_time_utc: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class ShadowMarketSnapshot:
    symbol: str
    timestamp_utc: str
    candles_15m: tuple[ShadowCandle, ...]
    candles_4h: tuple[ShadowCandle, ...]
    funding_rate: float | None = None
    open_interest: float | None = None
    source: str = "unknown"


@dataclass(frozen=True)
class ShadowSymbolDecision:
    symbol: str
    timestamp_utc: str
    data_status: str
    signal_generated: bool
    signal_blocker: str | None
    sweep_detected: bool
    reclaim_detected: bool
    sweep_depth_pct: float | None
    min_sweep_depth_pct: float
    regime: str
    context_session: str
    confluence_score_preview: float
    candidate_direction_preview: str | None
    symbol_governance_shadow_decision: str
    symbol_risk_shadow_decision: str
    portfolio_shadow_decision: str
    portfolio_veto_reason: str | None
    candidate_risk_pct: float
    portfolio_risk_after_pct: float
    reasons: tuple[str, ...]
    features: dict[str, float | int | str | None]
    near_miss: bool
    depth_bucket: str | None
    details: dict[str, object]


@dataclass(frozen=True)
class ShadowCycleResult:
    decisions: tuple[ShadowSymbolDecision, ...]
    signal_candidates: int
    portfolio_decisions: int
    near_miss_rows: int


class ShadowMarketProvider(Protocol):
    def get_snapshot(self, symbol: str, now: datetime) -> ShadowMarketSnapshot | None:
        """Return a symbol snapshot, or None when data is unavailable."""


def default_symbol_configs() -> tuple[ShadowSymbolConfig, ...]:
    return (
        ShadowSymbolConfig(
            symbol="BTCUSDT",
            risk_policy_profile="btc_035_shadow_compare",
            shadow_mode="shadow_compare_only",
            candidate_risk_pct=0.0035,
        ),
        ShadowSymbolConfig(
            symbol="ETHUSDT",
            risk_policy_profile="eth_035_shadow_candidate",
            shadow_mode="shadow_no_orders",
            candidate_risk_pct=0.0035,
            min_sweep_depth_pct=ETH_SHADOW_MIN_SWEEP_DEPTH_PCT,
        ),
        ShadowSymbolConfig(
            symbol="SOLUSDT",
            risk_policy_profile="sol_015_shadow_candidate",
            shadow_mode="shadow_no_orders",
            candidate_risk_pct=0.0015,
        ),
    )


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class BinanceRestShadowMarketProvider:
    """Read-only Binance USD-M REST provider for manual shadow smoke tests."""

    def __init__(self, base_url: str = "https://fapi.binance.com", timeout_seconds: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _get_json(self, path: str, params: dict[str, str | int]) -> object:
        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}{path}?{query}"
        with urllib.request.urlopen(url, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _klines(self, symbol: str, interval: str, limit: int) -> tuple[ShadowCandle, ...]:
        payload = self._get_json(
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        if not isinstance(payload, list):
            return ()
        candles: list[ShadowCandle] = []
        for row in payload:
            if not isinstance(row, list) or len(row) < 6:
                continue
            open_time = datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
            candles.append(
                ShadowCandle(
                    open_time_utc=to_utc_iso(open_time),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        return tuple(candles)

    def get_snapshot(self, symbol: str, now: datetime) -> ShadowMarketSnapshot | None:
        try:
            candles_15m = self._klines(symbol, "15m", 80)
            candles_4h = self._klines(symbol, "4h", 80)
            open_interest_payload = self._get_json("/fapi/v1/openInterest", {"symbol": symbol})
            open_interest = (
                float(open_interest_payload["openInterest"])
                if isinstance(open_interest_payload, dict) and "openInterest" in open_interest_payload
                else None
            )
        except Exception:
            return None
        return ShadowMarketSnapshot(
            symbol=symbol,
            timestamp_utc=to_utc_iso(now),
            candles_15m=candles_15m,
            candles_4h=candles_4h,
            open_interest=open_interest,
            source="binance_rest_read_only",
        )


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for value in values[period:]:
        ema = (value - ema) * multiplier + ema
    return ema


def _regime_from_4h(candles_4h: tuple[ShadowCandle, ...]) -> str:
    closes = [candle.close for candle in candles_4h]
    ema50 = _ema(closes, 50)
    ema20 = _ema(closes, 20)
    if ema50 is None or ema20 is None:
        return "unknown"
    if ema20 > ema50:
        return "uptrend"
    if ema20 < ema50:
        return "downtrend"
    return "sideways"


def _session_from_timestamp(timestamp_utc: str) -> str:
    hour = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00")).hour
    if 0 <= hour < 8:
        return "asia"
    if 8 <= hour < 13:
        return "london"
    if 13 <= hour < 21:
        return "new_york"
    return "late_us"


def evaluate_shadow_symbol(
    config: ShadowSymbolConfig,
    snapshot: ShadowMarketSnapshot | None,
) -> ShadowSymbolDecision:
    timestamp = snapshot.timestamp_utc if snapshot else to_utc_iso(utc_now())
    base_details: dict[str, object] = {
        "orders_allowed": False,
        "operational_mode": "real_shadow_cycle",
        "setup_type": "sweep_reclaim",
        "shadow_source": "sidecar",
        "m4_source": False,
    }
    if snapshot is None:
        return ShadowSymbolDecision(
            symbol=config.symbol,
            timestamp_utc=timestamp,
            data_status="unavailable",
            signal_generated=False,
            signal_blocker="data_unavailable",
            sweep_detected=False,
            reclaim_detected=False,
            sweep_depth_pct=None,
            min_sweep_depth_pct=config.min_sweep_depth_pct,
            regime="unknown",
            context_session="unknown",
            confluence_score_preview=0.0,
            candidate_direction_preview=None,
            symbol_governance_shadow_decision="not_evaluated",
            symbol_risk_shadow_decision="not_evaluated",
            portfolio_shadow_decision="not_evaluated",
            portfolio_veto_reason="data_unavailable",
            candidate_risk_pct=config.candidate_risk_pct,
            portfolio_risk_after_pct=0.0,
            reasons=("data_unavailable",),
            features={},
            near_miss=False,
            depth_bucket=None,
            details={**base_details, "data_status": "unavailable", "reasons": ["data_unavailable"]},
        )

    candles = snapshot.candles_15m
    regime = _regime_from_4h(snapshot.candles_4h)
    session = _session_from_timestamp(snapshot.timestamp_utc)
    if len(candles) < 8:
        return ShadowSymbolDecision(
            symbol=config.symbol,
            timestamp_utc=snapshot.timestamp_utc,
            data_status="unavailable",
            signal_generated=False,
            signal_blocker="insufficient_15m_candles",
            sweep_detected=False,
            reclaim_detected=False,
            sweep_depth_pct=None,
            min_sweep_depth_pct=config.min_sweep_depth_pct,
            regime=regime,
            context_session=session,
            confluence_score_preview=0.0,
            candidate_direction_preview=None,
            symbol_governance_shadow_decision="not_evaluated",
            symbol_risk_shadow_decision="not_evaluated",
            portfolio_shadow_decision="not_evaluated",
            portfolio_veto_reason="insufficient_data",
            candidate_risk_pct=config.candidate_risk_pct,
            portfolio_risk_after_pct=0.0,
            reasons=("insufficient_15m_candles",),
            features={"candles_15m": len(candles), "candles_4h": len(snapshot.candles_4h)},
            near_miss=False,
            depth_bucket=None,
            details={**base_details, "data_status": "unavailable", "reasons": ["insufficient_15m_candles"]},
        )

    trigger = candles[-1]
    lookback = candles[-41:-1] if len(candles) >= 41 else candles[:-1]
    frozen_level = min(candle.low for candle in lookback)
    sweep_detected = trigger.low < frozen_level
    sweep_depth = (frozen_level - trigger.low) / frozen_level if sweep_detected else None
    reclaim_detected = sweep_detected and trigger.close > frozen_level
    deep_enough = sweep_depth is not None and sweep_depth >= config.min_sweep_depth_pct
    signal_generated = bool(deep_enough and reclaim_detected)
    near_miss = bool(
        sweep_depth is not None
        and not deep_enough
        and sweep_depth >= config.min_sweep_depth_pct * NEAR_MISS_FLOOR_MULT
    )
    reasons: list[str] = []
    if signal_generated:
        reasons.extend(["sweep_depth_pass", "reclaim_pass"])
        blocker = None
    elif not sweep_detected:
        reasons.append("no_sweep")
        blocker = "no_sweep"
    elif not deep_enough:
        reasons.append("sweep_too_shallow")
        blocker = "sweep_too_shallow"
    elif not reclaim_detected:
        reasons.append("reclaim_missing")
        blocker = "reclaim_missing"
    else:
        reasons.append("no_signal")
        blocker = "no_signal"

    confluence = 0.0
    if deep_enough:
        confluence += 2.0
    if reclaim_detected:
        confluence += 1.5
    if regime == "uptrend":
        confluence += 0.5

    features: dict[str, float | int | str | None] = {
        "frozen_level": frozen_level,
        "trigger_low": trigger.low,
        "trigger_close": trigger.close,
        "candles_15m": len(candles),
        "candles_4h": len(snapshot.candles_4h),
        "open_interest": snapshot.open_interest,
        "funding_rate": snapshot.funding_rate,
        "source": snapshot.source,
    }
    depth_bucket = None
    if near_miss:
        depth_bucket = "near_miss_high" if sweep_depth and sweep_depth >= config.min_sweep_depth_pct * 0.9 else "near_miss_low"

    data_status = "ready"
    return ShadowSymbolDecision(
        symbol=config.symbol,
        timestamp_utc=snapshot.timestamp_utc,
        data_status=data_status,
        signal_generated=signal_generated,
        signal_blocker=blocker,
        sweep_detected=sweep_detected,
        reclaim_detected=reclaim_detected,
        sweep_depth_pct=sweep_depth,
        min_sweep_depth_pct=config.min_sweep_depth_pct,
        regime=regime,
        context_session=session,
        confluence_score_preview=confluence,
        candidate_direction_preview="LONG" if signal_generated else None,
        symbol_governance_shadow_decision="approve_shadow" if signal_generated else "no_candidate",
        symbol_risk_shadow_decision="approve_shadow" if signal_generated else "no_candidate",
        portfolio_shadow_decision="pending" if signal_generated else "not_evaluated",
        portfolio_veto_reason=None if signal_generated else blocker,
        candidate_risk_pct=config.candidate_risk_pct,
        portfolio_risk_after_pct=0.0,
        reasons=tuple(reasons),
        features=features,
        near_miss=near_miss,
        depth_bucket=depth_bucket,
        details={
            **base_details,
            "data_status": data_status,
            "reasons": reasons,
            "feature_quality": {
                "candles_15m": len(candles),
                "candles_4h": len(snapshot.candles_4h),
            },
        },
    )


def apply_shadow_portfolio_gate(
    decisions: tuple[ShadowSymbolDecision, ...],
    *,
    portfolio_state: PortfolioRiskState | None = None,
    symbol_states: dict[str, SymbolRiskState] | None = None,
    config: PortfolioRiskConfig | None = None,
) -> tuple[ShadowSymbolDecision, ...]:
    gate_config = config or PortfolioRiskConfig()
    gate = ResearchPortfolioGate(gate_config)
    generated = [
        signal
        for signal in (build_shadow_portfolio_signal(decision) for decision in decisions)
        if signal is not None
    ]
    gate_decisions = gate.evaluate_batch(
        generated,
        symbol_states=symbol_states or {},
        portfolio_state=portfolio_state or PortfolioRiskState(),
        now=_cycle_now_from_decisions(decisions),
    )
    by_signal_id = {gate_decision.signal.signal_id: gate_decision for gate_decision in gate_decisions}
    updated: list[ShadowSymbolDecision] = []
    for decision in decisions:
        signal = build_shadow_portfolio_signal(decision)
        if signal is None:
            updated.append(decision)
            continue
        gate_decision = by_signal_id[signal.signal_id]
        updated.append(
            _replace_portfolio(
                decision,
                portfolio_shadow_decision="approve_shadow" if gate_decision.approved else "veto_shadow",
                portfolio_veto_reason=gate_decision.veto_reason,
                portfolio_risk_after_pct=gate_decision.portfolio_risk_after_pct
                if gate_decision.portfolio_risk_after_pct is not None
                else 0.0,
            )
        )
    return tuple(sorted(updated, key=_decision_sort_key))


def build_shadow_portfolio_signal(decision: ShadowSymbolDecision) -> PortfolioSignal | None:
    if not decision.signal_generated or decision.candidate_direction_preview is None:
        return None
    timestamp = datetime.fromisoformat(decision.timestamp_utc.replace("Z", "+00:00"))
    return PortfolioSignal(
        symbol=decision.symbol,
        timestamp=timestamp,
        direction=decision.candidate_direction_preview,
        signal_id=f"shadow-{decision.symbol}-{decision.timestamp_utc}",
        risk_pct=decision.candidate_risk_pct,
        gross_notional_pct=_shadow_gross_notional_pct(decision.symbol),
        confluence_score=decision.confluence_score_preview,
    )


def _shadow_gross_notional_pct(symbol: str) -> float:
    if symbol == "SOLUSDT":
        return 0.15
    return 0.30


def _cycle_now_from_decisions(decisions: tuple[ShadowSymbolDecision, ...]) -> datetime:
    for decision in decisions:
        return datetime.fromisoformat(decision.timestamp_utc.replace("Z", "+00:00"))
    return utc_now()


def _decision_sort_key(decision: ShadowSymbolDecision) -> tuple[datetime, int, str]:
    rank = {symbol: index for index, symbol in enumerate(SYMBOL_ORDER)}
    timestamp = datetime.fromisoformat(decision.timestamp_utc.replace("Z", "+00:00"))
    symbol = decision.symbol.upper()
    return (timestamp, rank.get(symbol, len(rank)), symbol)


def _replace_portfolio(
    decision: ShadowSymbolDecision,
    *,
    portfolio_shadow_decision: str,
    portfolio_veto_reason: str | None,
    portfolio_risk_after_pct: float,
) -> ShadowSymbolDecision:
    return ShadowSymbolDecision(
        **{
            **decision.__dict__,
            "portfolio_shadow_decision": portfolio_shadow_decision,
            "portfolio_veto_reason": portfolio_veto_reason,
            "portfolio_risk_after_pct": portfolio_risk_after_pct,
        }
    )


def persist_shadow_symbol_decision(
    conn: sqlite3.Connection,
    *,
    shadow_run_id: str,
    config_hash: str,
    decision: ShadowSymbolDecision,
    created_at_utc: str,
    resource_guard_status: str = "pass",
) -> None:
    conn.execute(
        """
        INSERT INTO shadow_decision_outcomes (
            shadow_run_id, symbol, timestamp_utc, strategy_profile,
            risk_policy_profile, shadow_mode, config_hash, signal_generated,
            signal_blocker, sweep_detected, reclaim_detected, sweep_depth_pct,
            min_sweep_depth_pct, regime, context_session,
            confluence_score_preview, candidate_direction_preview,
            symbol_governance_shadow_decision, symbol_risk_shadow_decision,
            portfolio_shadow_decision, portfolio_veto_reason, candidate_risk_pct,
            portfolio_risk_after_pct, resource_guard_status, details_json,
            created_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            shadow_run_id,
            decision.symbol,
            decision.timestamp_utc,
            STRATEGY_PROFILE,
            _risk_policy_for_symbol(decision.symbol),
            _shadow_mode_for_symbol(decision.symbol),
            config_hash,
            1 if decision.signal_generated else 0,
            decision.signal_blocker,
            1 if decision.sweep_detected else 0,
            1 if decision.reclaim_detected else 0,
            decision.sweep_depth_pct,
            decision.min_sweep_depth_pct,
            decision.regime,
            decision.context_session,
            decision.confluence_score_preview,
            decision.candidate_direction_preview,
            decision.symbol_governance_shadow_decision,
            decision.symbol_risk_shadow_decision,
            decision.portfolio_shadow_decision,
            decision.portfolio_veto_reason,
            decision.candidate_risk_pct,
            decision.portfolio_risk_after_pct,
            resource_guard_status,
            json.dumps(decision.details, sort_keys=True),
            created_at_utc,
        ),
    )


def _risk_policy_for_symbol(symbol: str) -> str:
    for config in default_symbol_configs():
        if config.symbol == symbol:
            return config.risk_policy_profile
    return "unknown_shadow_policy"


def _shadow_mode_for_symbol(symbol: str) -> str:
    for config in default_symbol_configs():
        if config.symbol == symbol:
            return config.shadow_mode
    return "shadow_no_orders"


def persist_signal_candidate_if_any(
    conn: sqlite3.Connection,
    *,
    shadow_run_id: str,
    decision: ShadowSymbolDecision,
    created_at_utc: str,
) -> str | None:
    if not decision.signal_generated:
        return None
    signal_id = f"shadow-signal-{decision.symbol}-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """
        INSERT INTO shadow_signal_candidates (
            signal_id, shadow_run_id, symbol, timestamp_utc, direction,
            setup_type, confluence_score, strategy_profile, risk_policy_profile,
            reasons_json, features_json, created_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            shadow_run_id,
            decision.symbol,
            decision.timestamp_utc,
            decision.candidate_direction_preview,
            "sweep_reclaim",
            decision.confluence_score_preview,
            STRATEGY_PROFILE,
            _risk_policy_for_symbol(decision.symbol),
            json.dumps(list(decision.reasons), sort_keys=True),
            json.dumps(decision.features, sort_keys=True),
            created_at_utc,
        ),
    )
    return signal_id


def persist_portfolio_decision(
    conn: sqlite3.Connection,
    *,
    shadow_run_id: str,
    decision: ShadowSymbolDecision,
    signal_id: str | None,
    created_at_utc: str,
) -> None:
    conn.execute(
        """
        INSERT INTO shadow_portfolio_decisions (
            shadow_run_id, symbol, timestamp_utc, signal_id,
            portfolio_shadow_decision, portfolio_veto_reason, candidate_risk_pct,
            portfolio_risk_before_pct, portfolio_risk_after_pct,
            gross_notional_after_pct, directional_notional_after_pct,
            details_json, created_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            shadow_run_id,
            decision.symbol,
            decision.timestamp_utc,
            signal_id,
            decision.portfolio_shadow_decision,
            decision.portfolio_veto_reason,
            decision.candidate_risk_pct,
            max(0.0, decision.portfolio_risk_after_pct - decision.candidate_risk_pct)
            if decision.portfolio_shadow_decision == "approve_shadow"
            else decision.portfolio_risk_after_pct,
            decision.portfolio_risk_after_pct,
            decision.portfolio_risk_after_pct,
            decision.portfolio_risk_after_pct,
            json.dumps({"orders_allowed": False, "shadow_source": "sidecar"}, sort_keys=True),
            created_at_utc,
        ),
    )


def persist_near_miss_if_applicable(
    conn: sqlite3.Connection,
    *,
    shadow_run_id: str,
    decision: ShadowSymbolDecision,
    created_at_utc: str,
) -> int:
    if not decision.near_miss or decision.sweep_depth_pct is None:
        return 0
    from research_lab.shadow_schema import insert_near_miss

    insert_near_miss(
        conn,
        shadow_run_id=shadow_run_id,
        symbol=decision.symbol,
        timestamp_utc=decision.timestamp_utc,
        sweep_depth_pct=decision.sweep_depth_pct,
        threshold=decision.min_sweep_depth_pct,
        depth_bucket=decision.depth_bucket or "near_miss",
        regime=decision.regime,
        session_hour=datetime.fromisoformat(decision.timestamp_utc.replace("Z", "+00:00")).hour,
        rejection_reasons=list(decision.reasons),
        created_at_utc=created_at_utc,
    )
    return 1


def run_real_shadow_cycle(
    conn: sqlite3.Connection,
    *,
    shadow_run_id: str,
    config_hash: str,
    provider: ShadowMarketProvider,
    now: datetime | None = None,
    symbol_configs: tuple[ShadowSymbolConfig, ...] | None = None,
) -> ShadowCycleResult:
    cycle_now = now or utc_now()
    configs = symbol_configs or default_symbol_configs()
    raw_decisions = tuple(
        evaluate_shadow_symbol(config, provider.get_snapshot(config.symbol, cycle_now))
        for config in configs
    )
    decisions = apply_shadow_portfolio_gate(raw_decisions)
    created_at = to_utc_iso(cycle_now)
    signal_count = 0
    portfolio_count = 0
    near_miss_count = 0
    for decision in decisions:
        persist_shadow_symbol_decision(
            conn,
            shadow_run_id=shadow_run_id,
            config_hash=config_hash,
            decision=decision,
            created_at_utc=created_at,
        )
        signal_id = persist_signal_candidate_if_any(
            conn,
            shadow_run_id=shadow_run_id,
            decision=decision,
            created_at_utc=created_at,
        )
        if signal_id:
            signal_count += 1
        persist_portfolio_decision(
            conn,
            shadow_run_id=shadow_run_id,
            decision=decision,
            signal_id=signal_id,
            created_at_utc=created_at,
        )
        portfolio_count += 1
        near_miss_count += persist_near_miss_if_applicable(
            conn,
            shadow_run_id=shadow_run_id,
            decision=decision,
            created_at_utc=created_at,
        )
    conn.commit()
    return ShadowCycleResult(
        decisions=decisions,
        signal_candidates=signal_count,
        portfolio_decisions=portfolio_count,
        near_miss_rows=near_miss_count,
    )
