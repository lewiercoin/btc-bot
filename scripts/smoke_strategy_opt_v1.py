from __future__ import annotations

import sqlite3
import sys
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtest.backtest_runner import BacktestConfig, BacktestRunner
from backtest.fill_model import FillModel, FillResult
from core.models import Features, MarketSnapshot, RegimeState, SignalCandidate
from core.risk_engine import RiskConfig, RiskEngine
from core.signal_engine import SignalEngine
from settings import load_settings
from storage.db import init_db


def _make_conn(schema_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn, schema_path)
    return conn


def _build_features(*, now: datetime, bullish: bool) -> Features:
    return Features(
        schema_version="v1.0",
        config_hash="smoke",
        timestamp=now,
        atr_15m=10.0,
        atr_4h=50.0,
        atr_4h_norm=0.007,
        ema50_4h=70500.0,
        ema200_4h=70000.0,
        sweep_detected=True,
        reclaim_detected=True,
        sweep_level=70000.0,
        sweep_depth_pct=0.001,
        sweep_side="LOW" if bullish else "HIGH",
        funding_8h=-0.0001 if bullish else 0.0001,
        funding_sma3=0.0,
        funding_sma9=0.0,
        funding_pct_60d=50.0,
        oi_value=1.0,
        oi_zscore_60d=0.1,
        oi_delta_pct=0.0,
        cvd_15m=1.0,
        cvd_bullish_divergence=bullish,
        cvd_bearish_divergence=not bullish,
        tfi_60s=0.12 if bullish else -0.12,
        force_order_rate_60s=0.0,
        force_order_spike=False,
        force_order_decreasing=False,
    )


def _assert_regime_gating_and_stop_floor() -> None:
    now = datetime(2026, 3, 29, 10, 0, tzinfo=timezone.utc)
    engine = SignalEngine()

    allowed_short = engine.generate(_build_features(now=now, bullish=False), RegimeState.DOWNTREND)
    assert allowed_short is not None, "SHORT in DOWNTREND should be allowed in SHORT-REBUILD-P0"

    blocked_short = engine.generate(_build_features(now=now, bullish=False), RegimeState.POST_LIQUIDATION)
    assert blocked_short is None, "SHORT in POST_LIQUIDATION must remain blocked by regime whitelist"

    allowed_long = engine.generate(_build_features(now=now, bullish=True), RegimeState.DOWNTREND)
    assert allowed_long is not None, "LONG in DOWNTREND should be allowed"

    stop_distance = abs(allowed_long.entry_reference - allowed_long.invalidation_level)
    floor_distance = abs(allowed_long.entry_reference) * engine.config.min_stop_distance_pct
    assert stop_distance >= floor_distance, "SL distance must honor min_stop_distance_pct floor"
    print("regime gating + stop floor smoke: OK")


class _ZeroFeeFillModel(FillModel):
    def simulate(
        self,
        requested_price: float,
        qty: float,
        *,
        order_type: str = "MARKET",
        side: str = "BUY",
    ) -> FillResult:
        _ = order_type
        _ = side
        if requested_price <= 0 or qty <= 0:
            raise ValueError("invalid fill request")
        return FillResult(
            filled_price=float(requested_price),
            slippage_bps=0.0,
            fee_paid=0.0,
        )


class _ReplayLoader:
    def __init__(self, snapshots: list[MarketSnapshot]) -> None:
        self._snapshots = snapshots

    def iter_snapshots(self, *, start_date, end_date, symbol):  # type: ignore[no-untyped-def]
        _ = symbol
        start_ts = _to_utc(start_date if isinstance(start_date, datetime) else datetime.combine(start_date, time.min, tzinfo=timezone.utc))
        end_ts = _to_utc(end_date if isinstance(end_date, datetime) else datetime.combine(end_date, time.min, tzinfo=timezone.utc))
        for snapshot in self._snapshots:
            ts = _to_utc(snapshot.timestamp)
            if start_ts <= ts <= end_ts:
                yield snapshot


class _FeatureEngine:
    def compute(self, snapshot, schema_version: str, config_hash: str):  # type: ignore[no-untyped-def]
        _ = schema_version
        _ = config_hash
        return {"timestamp": snapshot.timestamp}


class _RegimeEngine:
    def classify(self, features):  # type: ignore[no-untyped-def]
        _ = features
        return RegimeState.NORMAL


class _SignalEngine:
    def __init__(self, *, first_timestamp: datetime) -> None:
        self.first_timestamp = first_timestamp

    def generate(self, features, regime):  # type: ignore[no-untyped-def]
        timestamp = features["timestamp"]
        if timestamp != self.first_timestamp:
            return None
        return SignalCandidate(
            signal_id="smoke-sig-opt-v1",
            timestamp=timestamp,
            direction="LONG",
            setup_type="smoke_partial_trailing",
            entry_reference=100.0,
            invalidation_level=96.5,
            tp_reference_1=110.0,
            tp_reference_2=125.0,
            confluence_score=4.0,
            regime=regime,
            reasons=["smoke"],
            features_json={"atr_15m": 4.0},
        )


class _GovernanceDecision:
    def __init__(self) -> None:
        self.approved = True
        self.notes = ["smoke"]


class _Governance:
    def evaluate(self, candidate):  # type: ignore[no-untyped-def]
        _ = candidate
        return _GovernanceDecision()

    def to_executable(self, candidate, decision):  # type: ignore[no-untyped-def]
        _ = decision
        from core.models import ExecutableSignal

        rr_ratio = (candidate.tp_reference_1 - candidate.entry_reference) / max(
            abs(candidate.entry_reference - candidate.invalidation_level), 1e-8
        )
        return ExecutableSignal(
            signal_id=candidate.signal_id,
            timestamp=candidate.timestamp,
            direction=candidate.direction,
            entry_price=candidate.entry_reference,
            stop_loss=candidate.invalidation_level,
            take_profit_1=candidate.tp_reference_1,
            take_profit_2=candidate.tp_reference_2,
            rr_ratio=rr_ratio,
            approved_by_governance=True,
            governance_notes=["smoke"],
        )


class _Runner(BacktestRunner):
    def __init__(self, connection: sqlite3.Connection, *, settings, replay_loader, fill_model) -> None:
        super().__init__(connection, settings=settings, replay_loader=replay_loader, fill_model=fill_model)
        self._first_timestamp = replay_loader._snapshots[0].timestamp

    def _build_engines(self):  # type: ignore[override]
        risk_engine = RiskEngine(
            RiskConfig(
                min_rr=1.0,
                partial_exit_pct=0.5,
                trailing_atr_mult=1.0,
            )
        )
        return _FeatureEngine(), _RegimeEngine(), _SignalEngine(first_timestamp=self._first_timestamp), _Governance(), risk_engine


def _make_snapshots(symbol: str) -> list[MarketSnapshot]:
    t0 = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)
    t2 = t1 + timedelta(minutes=15)

    def snapshot(ts: datetime, *, high: float, low: float, close: float) -> MarketSnapshot:
        return MarketSnapshot(
            symbol=symbol,
            timestamp=ts,
            price=close,
            bid=close,
            ask=close,
            candles_15m=[
                {
                    "open_time": ts - timedelta(minutes=15),
                    "open": close,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": 1.0,
                }
            ],
            candles_1h=[],
            candles_4h=[],
            funding_history=[],
            open_interest=0.0,
            aggtrades_bucket_60s={},
            aggtrades_bucket_15m={},
            force_order_events_60s=[],
        )

    return [
        snapshot(t0, high=101.0, low=99.0, close=100.0),
        snapshot(t1, high=111.0, low=104.0, close=109.0),
        snapshot(t2, high=116.0, low=111.0, close=112.0),
    ]


def _assert_partial_exit_and_trailing() -> None:
    settings = load_settings()
    assert settings.storage is not None
    conn = _make_conn(settings.storage.schema_path)
    symbol = settings.strategy.symbol.upper()
    snapshots = _make_snapshots(symbol)
    runner = _Runner(
        conn,
        settings=replace(settings, strategy=replace(settings.strategy, symbol=symbol)),
        replay_loader=_ReplayLoader(snapshots),
        fill_model=_ZeroFeeFillModel(),
    )
    result = runner.run(
        BacktestConfig(
            start_date=snapshots[0].timestamp,
            end_date=snapshots[-1].timestamp,
            symbol=symbol,
            initial_equity=10_000.0,
            entry_order_type="LIMIT",
        )
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "TP_TRAIL"
    assert float(trade.size) > 0.0
    # TP1 at 110.0 on 50% + trailing stop at 112.0 on 50% => weighted exit 111.0
    assert abs(float(trade.exit_price or 0.0) - 111.0) < 1e-9
    print("partial exit + trailing smoke: OK")


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def main() -> None:
    _assert_regime_gating_and_stop_floor()
    _assert_partial_exit_and_trailing()
    print("strategy optimization v1 smoke: OK")


if __name__ == "__main__":
    main()
