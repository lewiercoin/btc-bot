from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.governance import GovernanceConfig, GovernanceLayer, GovernanceRuntimeState
from core.models import MarketSnapshot
from core.regime_engine import RegimeConfig, RegimeEngine
from core.risk_engine import RiskConfig, RiskEngine, RiskRuntimeState
from core.signal_engine import SignalConfig, SignalEngine
from data.market_data import MarketDataAssembler
from data.rest_client import BinanceFuturesRestClient, RestClientConfig
from data.websocket_client import BinanceFuturesWebsocketClient, WebsocketClientConfig
from execution.execution_engine import ExecutionEngine
from execution.live_execution_engine import LiveExecutionEngine
from execution.order_manager import OrderManager
from execution.paper_execution_engine import PaperExecutionEngine
from execution.recovery import BinanceRecoverySyncSource, NoOpRecoverySyncSource, RecoveryCoordinator
from monitoring.audit_logger import AuditLogger
from settings import AppSettings, BotMode
from storage.repositories import save_executable_signal, save_signal_candidate
from storage.state_store import StateStore

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

def build_default_bundle(
    settings: AppSettings,
    conn: sqlite3.Connection,
    governance_state_provider: Callable[[], GovernanceRuntimeState],
    risk_state_provider: Callable[[], RiskRuntimeState],
) -> EngineBundle:
    audit_logger = AuditLogger(connection=conn)
    rest_client = BinanceFuturesRestClient(
        RestClientConfig(
            base_url=settings.exchange.futures_rest_base_url,
            timeout_seconds=settings.execution.rest_timeout_seconds,
            max_retries=3,
            retry_backoff_seconds=0.75,
            api_key=settings.exchange.api_key,
            api_secret=settings.exchange.api_secret,
            recv_window_ms=settings.exchange.recv_window_ms,
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
        order_manager = OrderManager(
            rest_client=rest_client,
            audit_logger=audit_logger,
            symbol=settings.strategy.symbol,
        )
        execution_engine = LiveExecutionEngine(
            connection=conn,
            rest_client=rest_client,
            order_manager=order_manager,
            audit_logger=audit_logger,
            symbol=settings.strategy.symbol,
            entry_order_type=settings.execution.live_entry_order_type,
            entry_timeout_seconds=settings.execution.entry_timeout_seconds,
            poll_interval_seconds=settings.execution.live_fill_poll_seconds,
        )

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
            ),
            state_provider=governance_state_provider,
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
            ),
            state_provider=risk_state_provider,
        ),
        execution_engine=execution_engine,
        audit_logger=audit_logger,
    )


class BotOrchestrator:
    """Coordinates the pipeline. Decision, risk and execution stay in separate layers."""
    REFERENCE_EQUITY = 10_000.0

    def __init__(self, settings: AppSettings, conn: sqlite3.Connection, bundle: EngineBundle | None = None) -> None:
        self.settings = settings
        self.conn = conn
        self.state_store = StateStore(
            connection=conn,
            mode=settings.mode.value,
            reference_equity=self.REFERENCE_EQUITY,
        )
        self.bundle = bundle or build_default_bundle(
            settings=settings,
            conn=conn,
            governance_state_provider=self.state_store.get_governance_state,
            risk_state_provider=self.state_store.get_risk_state,
        )
        if self.settings.mode == BotMode.PAPER:
            exchange_sync = NoOpRecoverySyncSource()
        else:
            exchange_sync = BinanceRecoverySyncSource(self.bundle.market_data.rest_client)

        self.recovery = RecoveryCoordinator(
            symbol=self.settings.strategy.symbol,
            max_allowed_leverage=self.settings.risk.max_leverage,
            isolated_only=self.settings.exchange.isolated_only,
            state_store=self.state_store,
            audit_logger=self.bundle.audit_logger,
            exchange_sync=exchange_sync,
        )

    def start(self) -> None:
        LOG.info("Bot started in %s mode", self.settings.mode.value)
        self.state_store.ensure_initialized()
        self.state_store.refresh_runtime_state()

        recovery_report = self.recovery.run_startup_sync()
        if recovery_report.safe_mode:
            LOG.error("Startup recovery entered safe mode. New trades are blocked. issues=%s", recovery_report.issues)
            return

        self._start_data_feeds()
        state = self.state_store.load()
        if state and state.safe_mode:
            LOG.error("Safe mode active after feed startup. New trades are blocked.")
            return

        # Full event loop is planned for Phase F.
        self.run_decision_cycle()

    def run_decision_cycle(self) -> None:
        timestamp = datetime.now(timezone.utc)
        self.state_store.refresh_runtime_state(timestamp)
        state = self.state_store.load()
        if state and state.safe_mode:
            self.bundle.audit_logger.log_info("orchestrator", "Safe mode active. Decision cycle skipped.")
            return
        try:
            snapshot = self._build_snapshot(timestamp)
        except Exception as exc:
            self.bundle.audit_logger.log_error("data", f"Snapshot build failed: {exc}")
            self.state_store.mark_error(f"snapshot_build_failed:{exc}")
            return

        try:
            closed_count = self._process_trade_lifecycle(snapshot)
            if closed_count:
                self.bundle.audit_logger.log_info("lifecycle", f"Closed trades this cycle: {closed_count}")
        except Exception as exc:
            self.bundle.audit_logger.log_error("lifecycle", f"Lifecycle processing failed: {exc}")
            self.state_store.mark_error(f"lifecycle_failed:{exc}")
            return

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
            self.state_store.mark_healthy()
            return

        save_signal_candidate(self.conn, candidate, self.settings.schema_version, self.settings.config_hash)
        self.conn.commit()

        governance_decision = self.bundle.governance.evaluate(candidate)
        if not governance_decision.approved:
            self.bundle.audit_logger.log_info("governance", "Candidate rejected by governance.")
            self.state_store.mark_healthy()
            return
        executable = self.bundle.governance.to_executable(candidate, governance_decision)
        save_executable_signal(self.conn, executable)
        self.conn.commit()

        # 2) Risk gate
        risk_decision = self.bundle.risk_engine.evaluate(
            signal=executable,
            equity=self.REFERENCE_EQUITY,
            open_positions=self.state_store.get_open_positions(),
        )
        if not risk_decision.allowed:
            self.bundle.audit_logger.log_info("risk", f"Trade blocked: {risk_decision.reason}")
            self.state_store.mark_healthy()
            return

        # 3) Execution
        try:
            self.bundle.execution_engine.execute_signal(executable, size=risk_decision.size, leverage=risk_decision.leverage)
            self.state_store.record_trade_open(
                candidate=candidate,
                executable=executable,
                schema_version=self.settings.schema_version,
                config_hash=self.settings.config_hash,
            )
            self.state_store.mark_healthy()
        except Exception as exc:
            self.bundle.audit_logger.log_error("execution", f"Execution failed: {exc}")
            self.state_store.mark_error(f"execution_failed:{exc}")

    def _build_snapshot(self, timestamp: datetime) -> MarketSnapshot:
        return self.bundle.market_data.build_snapshot(
            symbol=self.settings.strategy.symbol,
            timestamp=timestamp,
        )

    def _process_trade_lifecycle(self, snapshot: MarketSnapshot) -> int:
        open_records = self.state_store.get_open_trade_records()
        if not open_records:
            return 0

        latest_high = float(snapshot.candles_15m[-1]["high"]) if snapshot.candles_15m else float(snapshot.price)
        latest_low = float(snapshot.candles_15m[-1]["low"]) if snapshot.candles_15m else float(snapshot.price)
        latest_close = float(snapshot.candles_15m[-1]["close"]) if snapshot.candles_15m else float(snapshot.price)

        closed = 0
        for record in open_records:
            decision = self.bundle.risk_engine.evaluate_exit(
                record.position,
                now=snapshot.timestamp,
                latest_high=latest_high,
                latest_low=latest_low,
                latest_close=latest_close,
            )
            if not decision.should_close or decision.exit_price is None or decision.reason is None:
                continue

            candles_path = self._candles_since_open(snapshot.candles_15m, record.position.opened_at)
            settlement = self.bundle.risk_engine.build_settlement_metrics(
                record.position,
                exit_price=decision.exit_price,
                exit_reason=decision.reason,
                candles_15m=candles_path,
            )
            self.state_store.settle_trade_close(
                position_id=record.position.position_id,
                settlement=settlement,
                closed_at=snapshot.timestamp,
            )
            closed += 1
        return closed

    @staticmethod
    def _candles_since_open(candles_15m: list[dict], opened_at: datetime) -> list[dict]:
        result: list[dict] = []
        for candle in candles_15m:
            candle_ts = candle.get("open_time")
            if isinstance(candle_ts, datetime):
                if candle_ts >= opened_at:
                    result.append(candle)
            else:
                result.append(candle)
        return result

    def _start_data_feeds(self) -> None:
        websocket_client = self.bundle.market_data.websocket_client
        if websocket_client is None:
            return

        try:
            websocket_client.start(symbol=self.settings.strategy.symbol)
            self.bundle.audit_logger.log_info("recovery", "Market data feeds started after cold start.")
        except Exception as exc:
            reason = f"feed_start_failed:{exc}"
            self.bundle.audit_logger.log_error("recovery", "Failed to start market data feeds.", payload={"error": str(exc)})
            self.state_store.set_safe_mode(True, reason=reason, now=datetime.now(timezone.utc))
