from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.governance import GovernanceConfig, GovernanceLayer
from core.models import MarketSnapshot
from core.regime_engine import RegimeConfig, RegimeEngine
from core.risk_engine import RiskConfig, RiskEngine
from core.signal_engine import SignalConfig, SignalEngine
from data.market_data import MarketDataAssembler
from data.rest_client import BinanceFuturesRestClient, RestClientConfig
from data.websocket_client import BinanceFuturesWebsocketClient, WebsocketClientConfig
from execution.execution_engine import ExecutionEngine
from execution.live_execution_engine import LiveExecutionEngine
from execution.paper_execution_engine import PaperExecutionEngine
from monitoring.audit_logger import AuditLogger
from settings import AppSettings, BotMode

LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class EngineBundle:
    market_data: MarketDataAssembler
    feature_engine: FeatureEngine
    regime_engine: RegimeEngine
    signal_engine: SignalEngine
    governance: GovernanceLayer
    risk_engine: RiskEngine
    execution_engine: ExecutionEngine
    audit_logger: AuditLogger


def build_default_bundle(settings: AppSettings, conn: sqlite3.Connection) -> EngineBundle:
    rest_client = BinanceFuturesRestClient(
        RestClientConfig(
            base_url=settings.exchange.futures_rest_base_url,
            timeout_seconds=settings.execution.rest_timeout_seconds,
            max_retries=3,
            retry_backoff_seconds=0.75,
        )
    )
    websocket_client = BinanceFuturesWebsocketClient(
        WebsocketClientConfig(
            ws_base_url=settings.exchange.futures_ws_base_url,
            heartbeat_seconds=settings.execution.ws_heartbeat_seconds,
            reconnect_seconds=settings.execution.ws_reconnect_seconds,
        )
    )

    if settings.mode == BotMode.PAPER:
        execution_engine: ExecutionEngine = PaperExecutionEngine(connection=conn)
    else:
        execution_engine = LiveExecutionEngine()

    return EngineBundle(
        market_data=MarketDataAssembler(
            rest_client=rest_client,
            websocket_client=websocket_client,
            db_connection=conn,
        ),
        feature_engine=FeatureEngine(
            FeatureEngineConfig(
                atr_period=settings.strategy.atr_period,
                ema_fast=settings.strategy.ema_fast,
                ema_slow=settings.strategy.ema_slow,
                equal_level_lookback=settings.strategy.equal_level_lookback,
                equal_level_tol_atr=settings.strategy.equal_level_tol_atr,
                sweep_buf_atr=settings.strategy.sweep_buf_atr,
                reclaim_buf_atr=settings.strategy.reclaim_buf_atr,
                wick_min_atr=settings.strategy.wick_min_atr,
                funding_window_days=settings.strategy.funding_window_days,
                oi_z_window_days=settings.strategy.oi_z_window_days,
            )
        ),
        regime_engine=RegimeEngine(RegimeConfig()),
        signal_engine=SignalEngine(
            SignalConfig(
                confluence_min=settings.strategy.confluence_min,
            )
        ),
        governance=GovernanceLayer(
            GovernanceConfig(
                max_trades_per_day=settings.risk.max_trades_per_day,
                max_consecutive_losses=settings.risk.max_consecutive_losses,
                daily_dd_limit=settings.risk.daily_dd_limit,
                weekly_dd_limit=settings.risk.weekly_dd_limit,
            )
        ),
        risk_engine=RiskEngine(
            RiskConfig(
                risk_per_trade_pct=settings.risk.risk_per_trade_pct,
                max_leverage=settings.risk.max_leverage,
                high_vol_leverage=settings.risk.high_vol_leverage,
                min_rr=settings.risk.min_rr,
                max_open_positions=settings.risk.max_open_positions,
                max_consecutive_losses=settings.risk.max_consecutive_losses,
                daily_dd_limit=settings.risk.daily_dd_limit,
                weekly_dd_limit=settings.risk.weekly_dd_limit,
                max_hold_hours=settings.risk.max_hold_hours,
            )
        ),
        execution_engine=execution_engine,
        audit_logger=AuditLogger(connection=conn),
    )


class BotOrchestrator:
    """Coordinates the pipeline. Decision, risk and execution stay in separate layers."""

    def __init__(self, settings: AppSettings, conn: sqlite3.Connection, bundle: EngineBundle | None = None) -> None:
        self.settings = settings
        self.conn = conn
        self.bundle = bundle or build_default_bundle(settings=settings, conn=conn)

    def start(self) -> None:
        LOG.info("Bot started in %s mode", self.settings.mode.value)
        # Full event loop is planned for Phase F.
        self.run_decision_cycle()

    def run_decision_cycle(self) -> None:
        timestamp = datetime.now(timezone.utc)
        snapshot = self._build_snapshot(timestamp)

        # 1) Decision logic
        features = self.bundle.feature_engine.compute(
            snapshot=snapshot,
            schema_version=self.settings.schema_version,
            config_hash=self.settings.config_hash,
        )
        regime = self.bundle.regime_engine.classify(features)
        candidate = self.bundle.signal_engine.generate(features, regime)
        if candidate is None:
            self.bundle.audit_logger.log_info("decision", "No signal candidate.")
            return

        governance_decision = self.bundle.governance.evaluate(candidate)
        if not governance_decision.approved:
            self.bundle.audit_logger.log_info("governance", "Candidate rejected by governance.")
            return
        executable = self.bundle.governance.to_executable(candidate, governance_decision)

        # 2) Risk gate
        risk_decision = self.bundle.risk_engine.evaluate(
            signal=executable,
            equity=1.0,
            open_positions=0,
        )
        if not risk_decision.allowed:
            self.bundle.audit_logger.log_info("risk", f"Trade blocked: {risk_decision.reason}")
            return

        # 3) Execution
        self.bundle.execution_engine.execute_signal(executable, size=risk_decision.size, leverage=risk_decision.leverage)

    def _build_snapshot(self, timestamp: datetime) -> MarketSnapshot:
        return self.bundle.market_data.build_snapshot(
            symbol=self.settings.strategy.symbol,
            timestamp=timestamp,
        )
