from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.governance import GovernanceConfig, GovernanceLayer
from core.models import Features, GovernanceRuntimeState, MarketSnapshot, RiskRuntimeState, SignalDiagnostics
from core.regime_engine import RegimeConfig, RegimeEngine
from core.risk_engine import RiskConfig, RiskEngine
from core.signal_engine import SignalConfig, SignalEngine
from data.market_data import MarketDataAssembler, MarketDataConfig
from data.proxy_transport import ProxyTransport
from data.rest_client import BinanceFuturesRestClient, RestClientConfig
from data.websocket_client import BinanceFuturesWebsocketClient, WebsocketClientConfig
from execution.execution_engine import ExecutionEngine
from execution.live_execution_engine import LiveExecutionEngine
from execution.order_manager import OrderManager
from execution.paper_execution_engine import PaperExecutionEngine
from execution.recovery import BinanceRecoverySyncSource, NoOpRecoverySyncSource, RecoveryCoordinator
from monitoring.audit_logger import AuditLogger
from monitoring.health import HealthMonitor, HealthStatus
from monitoring.metrics import (
    CYCLE_DURATION_MS,
    ERRORS_TOTAL,
    FEATURE_QUALITY_DEGRADED,
    FEATURE_QUALITY_READY,
    FEATURE_QUALITY_UNAVAILABLE,
    GOVERNANCE_VETOES,
    RISK_BLOCKS,
    SIGNALS_GENERATED,
    TRADES_CLOSED,
    TRADES_OPENED,
    MetricsRegistry,
)
from monitoring.telegram_notifier import TelegramConfig, TelegramNotifier
from settings import AppSettings, BotMode, build_signal_regime_direction_whitelist
from storage.position_persister import SqlitePositionPersister
from storage.repositories import (
    fetch_funding_rates,
    fetch_cvd_price_history,
    fetch_oi_samples,
    get_daily_metrics,
    save_executable_signal,
    save_signal_candidate,
)
from storage.state_store import StateStore
from core.funding import compute_funding_paid

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
    signal_whitelist = build_signal_regime_direction_whitelist(settings.strategy)
    audit_logger = AuditLogger(connection=conn)
    
    # Initialize proxy transport if enabled
    proxy_transport = None
    if settings.proxy.proxy_enabled and settings.proxy.proxy_url:
        proxy_transport = ProxyTransport(
            proxy_url=settings.proxy.proxy_url,
            proxy_type=settings.proxy.proxy_type,
            sticky_minutes=settings.proxy.sticky_minutes,
            failover_list=settings.proxy.failover_list,
        )
        LOG.info(
            "Proxy transport enabled: type=%s, sticky=%d min, failover_count=%d",
            settings.proxy.proxy_type,
            settings.proxy.sticky_minutes,
            len(settings.proxy.failover_list),
        )
    
    rest_client = BinanceFuturesRestClient(
        RestClientConfig(
            base_url=settings.exchange.futures_rest_base_url,
            timeout_seconds=settings.execution.rest_timeout_seconds,
            max_retries=3,
            retry_backoff_seconds=0.75,
            api_key=settings.exchange.api_key,
            api_secret=settings.exchange.api_secret,
            recv_window_ms=settings.exchange.recv_window_ms,
            proxy_transport=proxy_transport,
        )
    )
    websocket_client = BinanceFuturesWebsocketClient(
        WebsocketClientConfig(
            ws_base_url=settings.exchange.futures_ws_base_url,
            ws_market_base_url=settings.exchange.futures_ws_market_base_url,
            heartbeat_seconds=settings.execution.ws_heartbeat_seconds,
            reconnect_seconds=settings.execution.ws_reconnect_seconds,
        )
    )
    position_persister = SqlitePositionPersister(conn)

    if settings.mode == BotMode.PAPER:
        execution_engine: ExecutionEngine = PaperExecutionEngine(
            position_persister=position_persister,
            symbol=settings.strategy.symbol.upper(),
        )
    else:
        order_manager = OrderManager(
            rest_client=rest_client,
            audit_logger=audit_logger,
            symbol=settings.strategy.symbol,
        )
        execution_engine = LiveExecutionEngine(
            position_persister=position_persister,
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
            config=MarketDataConfig(
                candles_limit=300,
                funding_limit=max(settings.strategy.funding_window_days * 3 + 3, 200),
                funding_window_days=settings.strategy.funding_window_days,
                agg_trades_limit=1000,
                flow_coverage_ready=settings.data_quality.flow_coverage_ready,
                flow_coverage_degraded=settings.data_quality.flow_coverage_degraded,
            ),
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
                oi_baseline_days=settings.data_quality.oi_baseline_days,
                cvd_divergence_bars=settings.data_quality.cvd_divergence_bars,
                flow_coverage_ready=settings.data_quality.flow_coverage_ready,
                flow_coverage_degraded=settings.data_quality.flow_coverage_degraded,
                funding_coverage_ready=settings.data_quality.funding_coverage_ready,
                funding_coverage_degraded=settings.data_quality.funding_coverage_degraded,
            )
        ),
        regime_engine=RegimeEngine(
            RegimeConfig(
                ema_trend_gap_pct=settings.strategy.ema_trend_gap_pct,
                compression_atr_norm_max=settings.strategy.compression_atr_norm_max,
                crowded_funding_extreme_pct=settings.strategy.crowded_funding_extreme_pct,
                crowded_oi_zscore_min=settings.strategy.crowded_oi_zscore_min,
                post_liq_tfi_abs_min=settings.strategy.post_liq_tfi_abs_min,
            )
        ),
        signal_engine=SignalEngine(
            SignalConfig(
                confluence_min=settings.strategy.confluence_min,
                min_sweep_depth_pct=settings.strategy.min_sweep_depth_pct,
                ema_trend_gap_pct=settings.strategy.ema_trend_gap_pct,
                entry_offset_atr=settings.strategy.entry_offset_atr,
                invalidation_offset_atr=settings.strategy.invalidation_offset_atr,
                min_stop_distance_pct=settings.strategy.min_stop_distance_pct,
                tp1_atr_mult=settings.strategy.tp1_atr_mult,
                tp2_atr_mult=settings.strategy.tp2_atr_mult,
                weight_sweep_detected=settings.strategy.weight_sweep_detected,
                weight_reclaim_confirmed=settings.strategy.weight_reclaim_confirmed,
                weight_cvd_divergence=settings.strategy.weight_cvd_divergence,
                weight_tfi_impulse=settings.strategy.weight_tfi_impulse,
                weight_force_order_spike=settings.strategy.weight_force_order_spike,
                weight_regime_special=settings.strategy.weight_regime_special,
                weight_ema_trend_alignment=settings.strategy.weight_ema_trend_alignment,
                weight_funding_supportive=settings.strategy.weight_funding_supportive,
                direction_tfi_threshold=settings.strategy.direction_tfi_threshold,
                direction_tfi_threshold_inverse=settings.strategy.direction_tfi_threshold_inverse,
                tfi_impulse_threshold=settings.strategy.tfi_impulse_threshold,
                allow_uptrend_pullback=settings.strategy.allow_uptrend_pullback,
                uptrend_pullback_tfi_threshold=settings.strategy.uptrend_pullback_tfi_threshold,
                uptrend_pullback_min_sweep_depth_pct=settings.strategy.uptrend_pullback_min_sweep_depth_pct,
                uptrend_pullback_confluence_min=settings.strategy.uptrend_pullback_confluence_min,
                regime_direction_whitelist=signal_whitelist,
            )
        ),
        governance=GovernanceLayer(
            GovernanceConfig(
                cooldown_minutes_after_loss=settings.risk.cooldown_minutes_after_loss,
                duplicate_level_tolerance_pct=settings.risk.duplicate_level_tolerance_pct,
                duplicate_level_window_hours=settings.risk.duplicate_level_window_hours,
                max_trades_per_day=settings.risk.max_trades_per_day,
                max_consecutive_losses=settings.risk.max_consecutive_losses,
                daily_dd_limit=settings.risk.daily_dd_limit,
                weekly_dd_limit=settings.risk.weekly_dd_limit,
                session_start_hour_utc=settings.risk.session_start_hour_utc,
                session_end_hour_utc=settings.risk.session_end_hour_utc,
                no_trade_windows_utc=settings.risk.no_trade_windows_utc,
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
                high_vol_stop_distance_pct=settings.risk.high_vol_stop_distance_pct,
                partial_exit_pct=settings.risk.partial_exit_pct,
                trailing_atr_mult=settings.risk.trailing_atr_mult,
            ),
            state_provider=risk_state_provider,
        ),
        execution_engine=execution_engine,
        audit_logger=audit_logger,
    )


class BotOrchestrator:
    """Coordinates runtime loops while keeping decision/risk/execution layers separated."""

    REFERENCE_EQUITY = 10_000.0

    def __init__(
        self,
        settings: AppSettings,
        conn: sqlite3.Connection,
        bundle: EngineBundle | None = None,
        *,
        health_monitor: HealthMonitor | None = None,
        telegram_notifier: TelegramNotifier | None = None,
        now_provider: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
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
        self.metrics = MetricsRegistry()
        self._stop_event = threading.Event()
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._sleep_fn = sleep_fn or time.sleep
        self._critical_execution_errors = 0
        self._consecutive_health_failures = 0
        self._current_utc_day: date | None = None
        self._next_decision_at: datetime | None = None
        self._next_monitor_at: datetime | None = None
        self._next_health_at: datetime | None = None

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

        self.health_monitor = health_monitor or HealthMonitor(
            websocket_client=self.bundle.market_data.websocket_client,
            connection=self.conn,
            rest_client=self.bundle.market_data.rest_client,
        )
        self.telegram_notifier = telegram_notifier or TelegramNotifier(
            TelegramConfig(
                enabled=self.settings.alerts.telegram_enabled,
                bot_token=self.settings.alerts.telegram_bot_token,
                chat_id=self.settings.alerts.telegram_chat_id,
            ),
            audit_logger=self.bundle.audit_logger,
        )

    def start(self) -> None:
        self._stop_event.clear()
        LOG.info("Bot started in %s mode", self.settings.mode.value)
        self.state_store.ensure_initialized()
        startup_ts = self._now()
        self.state_store.persist_config_snapshot(
            config_hash=self.settings.config_hash,
            strategy_snapshot=asdict(self.settings.strategy),
            captured_at=startup_ts,
        )
        bootstrap_summary = self._bootstrap_feature_engine_history(startup_ts)
        self._record_bootstrap_summary(bootstrap_summary)
        self.state_store.refresh_runtime_state(startup_ts)

        recovery_report = self.recovery.run_startup_sync()
        if recovery_report.safe_mode:
            LOG.warning(
                "Startup recovery entered safe mode. New trades are blocked but lifecycle monitoring will continue. issues=%s",
                recovery_report.issues,
            )

        self._start_data_feeds()
        now = self._now()
        self._initialize_runtime_schedule(now)
        LOG.info(
            "Runtime loop started | mode=%s | symbol=%s | next_decision_at=%s | next_health_at=%s | next_monitor_at=%s",
            self.settings.mode.value,
            self.settings.strategy.symbol,
            self._next_decision_at.isoformat() if self._next_decision_at else "none",
            self._next_health_at.isoformat() if self._next_health_at else "none",
            self._next_monitor_at.isoformat() if self._next_monitor_at else "none",
        )
        self.bundle.audit_logger.log_info(
            "orchestrator",
            "Runtime loop started.",
            payload={"mode": self.settings.mode.value, "symbol": self.settings.strategy.symbol},
        )
        try:
            self._run_event_loop()
        finally:
            self._shutdown()

    def stop(self, reason: str = "manual_stop") -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        LOG.info("Stop requested (%s).", reason)
        self.bundle.audit_logger.log_info("orchestrator", "Stop requested.", payload={"reason": reason})

    def run_decision_cycle(self, now: datetime | None = None) -> None:
        cycle_started = time.perf_counter()
        timestamp = (now or self._now()).astimezone(timezone.utc)
        cycle_outcome = "unknown"
        snapshot_id: str | None = None
        feature_snapshot_id: str | None = None
        self._update_runtime_metrics(
            last_decision_cycle_started_at=timestamp,
            decision_cycle_status="running",
        )
        LOG.info("Decision cycle started | timestamp=%s", timestamp.isoformat())
        try:
            self.state_store.refresh_runtime_state(timestamp)
            try:
                snapshot = self._build_snapshot(timestamp)
                snapshot_id = self.state_store.record_market_snapshot(snapshot)
                self._update_runtime_metrics(
                    last_snapshot_built_at=timestamp,
                    last_snapshot_symbol=snapshot.symbol,
                    last_15m_candle_open_at=self._latest_candle_open_at(snapshot.candles_15m),
                    last_1h_candle_open_at=self._latest_candle_open_at(snapshot.candles_1h),
                    last_4h_candle_open_at=self._latest_candle_open_at(snapshot.candles_4h),
                    last_ws_message_at=self._last_ws_message_at(),
                )
            except Exception as exc:
                cycle_outcome = "snapshot_failed"
                self._record_decision_outcome(
                    timestamp=timestamp,
                    outcome_group=cycle_outcome,
                    outcome_reason=cycle_outcome,
                    snapshot_id=snapshot_id,
                    details={"error": str(exc)},
                )
                self.bundle.audit_logger.log_error("data", f"Snapshot build failed: {exc}")
                self.state_store.mark_error(f"snapshot_build_failed:{exc}")
                self.metrics.inc(ERRORS_TOTAL)
                self._send_critical_error_alert("data", f"Snapshot build failed: {exc}")
                return

            try:
                closed_events = self._process_trade_lifecycle(snapshot)
                if closed_events:
                    self.metrics.inc(TRADES_CLOSED, len(closed_events))
                    self.bundle.audit_logger.log_trade(
                        "lifecycle",
                        f"Closed trades this cycle: {len(closed_events)}",
                        payload={"closed_positions": [item["position_id"] for item in closed_events]},
                    )
                    self._notify_closed_trades(closed_events)
            except Exception as exc:
                cycle_outcome = "lifecycle_failed"
                self._record_decision_outcome(
                    timestamp=timestamp,
                    outcome_group=cycle_outcome,
                    outcome_reason=cycle_outcome,
                    snapshot_id=snapshot_id,
                    details={"error": str(exc)},
                )
                self.bundle.audit_logger.log_error("lifecycle", f"Lifecycle processing failed: {exc}")
                self.state_store.mark_error(f"lifecycle_failed:{exc}")
                self.metrics.inc(ERRORS_TOTAL)
                self._send_critical_error_alert("lifecycle", f"Lifecycle processing failed: {exc}")
                return

            state = self.state_store.load()
            if state and state.safe_mode:
                cycle_outcome = "safe_mode_skip"
                self._record_decision_outcome(
                    timestamp=timestamp,
                    outcome_group=cycle_outcome,
                    outcome_reason=cycle_outcome,
                    snapshot_id=snapshot_id,
                )
                self.bundle.audit_logger.log_decision(
                    "orchestrator",
                    "Safe mode active. New trade decisions skipped.",
                    payload={"safe_mode": True},
                )
                return

            features = self.bundle.feature_engine.compute(
                snapshot=snapshot,
                schema_version=self.settings.schema_version,
                config_hash=self.settings.config_hash,
            )
            feature_snapshot_id = self.state_store.record_feature_snapshot(
                snapshot_id=snapshot_id,
                features=features,
            )
            self._record_feature_quality(features)
            regime = self.bundle.regime_engine.classify(features)
            diagnostics = self.bundle.signal_engine.diagnose(features, regime)
            candidate = self.bundle.signal_engine.generate(features, regime, diagnostics=diagnostics)
            if candidate is None:
                cycle_outcome = "no_signal"
                self._log_no_signal_diagnostics(timestamp, diagnostics)
                self._record_decision_outcome(
                    timestamp=timestamp,
                    outcome_group=cycle_outcome,
                    outcome_reason=diagnostics.blocked_by or cycle_outcome,
                    regime=regime.value,
                    snapshot_id=snapshot_id,
                    feature_snapshot_id=feature_snapshot_id,
                    details=self._signal_diagnostics_payload(diagnostics),
                )
                self.bundle.audit_logger.log_decision(
                    "decision",
                    "No signal candidate.",
                    payload=self._signal_diagnostics_payload(diagnostics),
                )
                self.state_store.mark_healthy()
                return

            self.metrics.inc(SIGNALS_GENERATED)
            self.bundle.audit_logger.log_decision(
                "decision",
                "Signal candidate generated.",
                payload={
                    "signal_id": candidate.signal_id,
                    "direction": candidate.direction,
                    "confluence_score": candidate.confluence_score,
                    "regime": candidate.regime.value,
                },
            )
            save_signal_candidate(self.conn, candidate, self.settings.schema_version, self.settings.config_hash)
            self.conn.commit()

            governance_decision = self.bundle.governance.evaluate(candidate)
            if not governance_decision.approved:
                cycle_outcome = "governance_veto"
                self._record_decision_outcome(
                    timestamp=timestamp,
                    outcome_group=cycle_outcome,
                    outcome_reason=cycle_outcome,
                    regime=candidate.regime.value,
                    signal_id=candidate.signal_id,
                    snapshot_id=snapshot_id,
                    feature_snapshot_id=feature_snapshot_id,
                    details={"notes": governance_decision.notes},
                )
                self.bundle.audit_logger.log_decision(
                    "governance",
                    "Candidate rejected by governance.",
                    payload={"notes": governance_decision.notes},
                )
                self.state_store.mark_healthy()
                self.metrics.inc(GOVERNANCE_VETOES)
                return

            executable = self.bundle.governance.to_executable(candidate, governance_decision)
            save_executable_signal(self.conn, executable)
            self.conn.commit()

            risk_decision = self.bundle.risk_engine.evaluate(
                signal=executable,
                equity=self.REFERENCE_EQUITY,
                open_positions=self.state_store.get_open_positions(),
            )
            if not risk_decision.allowed:
                cycle_outcome = "risk_block"
                self._record_decision_outcome(
                    timestamp=timestamp,
                    outcome_group=cycle_outcome,
                    outcome_reason=cycle_outcome,
                    regime=candidate.regime.value,
                    signal_id=candidate.signal_id,
                    snapshot_id=snapshot_id,
                    feature_snapshot_id=feature_snapshot_id,
                    details={"reason": risk_decision.reason},
                )
                self.bundle.audit_logger.log_decision(
                    "risk",
                    f"Trade blocked: {risk_decision.reason}",
                    payload={"reason": risk_decision.reason},
                )
                self.state_store.mark_healthy()
                self.metrics.inc(RISK_BLOCKS)
                return

            try:
                paper_fill_price = float(snapshot.price) if self.settings.mode == BotMode.PAPER else None
                self.bundle.execution_engine.execute_signal(
                    executable,
                    size=risk_decision.size,
                    leverage=risk_decision.leverage,
                    snapshot_price=paper_fill_price,
                    bid_price=snapshot.bid if self.settings.mode == BotMode.PAPER else None,
                    ask_price=snapshot.ask if self.settings.mode == BotMode.PAPER else None,
                    snapshot_id=snapshot.snapshot_id if self.settings.mode == BotMode.PAPER else None,
                )
                self.state_store.record_trade_open(
                    candidate=candidate,
                    executable=executable,
                    schema_version=self.settings.schema_version,
                    config_hash=self.settings.config_hash,
                    filled_entry_price=paper_fill_price,
                )
                self.state_store.mark_healthy()
                self.metrics.inc(TRADES_OPENED)
                filled_entry_price = paper_fill_price if paper_fill_price is not None else executable.entry_price
                trade_payload = {
                    "symbol": self.settings.strategy.symbol,
                    "signal_id": executable.signal_id,
                    "direction": executable.direction,
                    "entry_price": filled_entry_price,
                    "signal_entry_reference": executable.entry_price,
                    "size": risk_decision.size,
                    "leverage": risk_decision.leverage,
                }
                cycle_outcome = "signal_generated"
                self._record_decision_outcome(
                    timestamp=timestamp,
                    outcome_group=cycle_outcome,
                    outcome_reason=cycle_outcome,
                    regime=candidate.regime.value,
                    signal_id=candidate.signal_id,
                    snapshot_id=snapshot_id,
                    feature_snapshot_id=feature_snapshot_id,
                    details=trade_payload,
                )
                self.bundle.audit_logger.log_trade("execution", "Trade opened.", payload=trade_payload)
                self._send_telegram_alert(TelegramNotifier.ALERT_ENTRY, trade_payload)
            except Exception as exc:
                cycle_outcome = "execution_failed"
                self._record_decision_outcome(
                    timestamp=timestamp,
                    outcome_group=cycle_outcome,
                    outcome_reason=cycle_outcome,
                    regime=candidate.regime.value,
                    signal_id=candidate.signal_id,
                    snapshot_id=snapshot_id,
                    feature_snapshot_id=feature_snapshot_id,
                    details={"error": str(exc)},
                )
                self._critical_execution_errors += 1
                self.bundle.audit_logger.log_error("execution", f"Execution failed: {exc}")
                self.state_store.mark_error(f"execution_failed:{exc}")
                self.metrics.inc(ERRORS_TOTAL)
                self._send_critical_error_alert("execution", f"Execution failed: {exc}")
        finally:
            duration_ms = (time.perf_counter() - cycle_started) * 1000.0
            self.metrics.set_gauge(CYCLE_DURATION_MS, duration_ms)
            self._update_runtime_metrics(
                last_decision_cycle_finished_at=timestamp,
                last_decision_outcome=cycle_outcome,
                decision_cycle_status="blocked" if cycle_outcome == "safe_mode_skip" else "idle",
                last_ws_message_at=self._last_ws_message_at(),
            )
            LOG.info(
                "Decision cycle finished | timestamp=%s | outcome=%s | duration_ms=%.1f",
                timestamp.isoformat(),
                cycle_outcome,
                duration_ms,
            )

    def send_daily_summary(self, day: date | None = None) -> None:
        summary_day = day or self._now().date()
        self.state_store.sync_daily_metrics(summary_day)
        metrics_row = get_daily_metrics(self.conn, summary_day) or {}
        payload = {
            "date": summary_day.isoformat(),
            "trades_count": int(metrics_row.get("trades_count", 0)),
            "wins": int(metrics_row.get("wins", 0)),
            "losses": int(metrics_row.get("losses", 0)),
            "pnl_abs": float(metrics_row.get("pnl_abs", 0.0)),
            "expectancy_r": float(metrics_row.get("expectancy_r", 0.0)),
        }
        self.bundle.audit_logger.log_info("summary", "Daily summary generated.", payload=payload)
        self._send_telegram_alert(TelegramNotifier.ALERT_DAILY_SUMMARY, payload)

    def _run_event_loop(self) -> None:
        while not self._stop_event.is_set():
            now = self._now()
            self._handle_daily_rollover(now)

            if self._next_health_at and now >= self._next_health_at:
                self._run_health_check(now)
                self._next_health_at = now + timedelta(seconds=self.settings.execution.health_check_interval_seconds)

            if self._next_monitor_at and now >= self._next_monitor_at:
                self._run_position_monitor_cycle(now)
                self._next_monitor_at = now + timedelta(seconds=self.settings.execution.position_monitor_interval_seconds)

            if self._next_decision_at and now >= self._next_decision_at:
                self.run_decision_cycle(now=now)
                self._next_decision_at = self._advance_decision_deadline(self._next_decision_at, now)

            self._evaluate_kill_switch(now)
            sleep_seconds = self._compute_sleep_seconds(now)
            self._sleep(sleep_seconds)

    def _run_position_monitor_cycle(self, now: datetime) -> None:
        if not self.state_store.get_open_trade_records():
            return

        try:
            snapshot = self._build_snapshot(now)
            closed_events = self._process_trade_lifecycle(snapshot)
            if closed_events:
                self.metrics.inc(TRADES_CLOSED, len(closed_events))
                self.bundle.audit_logger.log_trade(
                    "lifecycle",
                    f"Closed trades in monitor cycle: {len(closed_events)}",
                    payload={"closed_positions": [item["position_id"] for item in closed_events]},
                )
                self._notify_closed_trades(closed_events)
        except Exception as exc:
            self.bundle.audit_logger.log_error("lifecycle", f"Monitor lifecycle failed: {exc}")
            self.metrics.inc(ERRORS_TOTAL)
            self._send_critical_error_alert("lifecycle", f"Monitor lifecycle failed: {exc}")

    def _run_health_check(self, now: datetime) -> None:
        status = self.health_monitor.check()
        self._update_runtime_metrics(
            last_health_check_at=now,
            last_ws_message_at=self._last_ws_message_at(),
            last_runtime_warning=None if status.healthy else self._format_health_warning(status),
        )
        if status.healthy:
            self._consecutive_health_failures = 0
            return

        self._consecutive_health_failures += 1
        payload = {
            "websocket_alive": status.websocket_alive,
            "db_writable": status.db_writable,
            "exchange_reachable": status.exchange_reachable,
            "consecutive_failures": self._consecutive_health_failures,
        }
        self.bundle.audit_logger.log_warning("health", "Health check failed.", payload=payload)
        if self._consecutive_health_failures >= self.settings.execution.health_failures_before_safe_mode:
            self._activate_safe_mode(reason="health_check_failure_threshold", now=now, extra_payload=payload)

    def _evaluate_kill_switch(self, now: datetime) -> None:
        state = self.state_store.refresh_runtime_state(now)
        reasons: list[str] = []
        if state.daily_dd_pct > self.settings.risk.daily_dd_limit:
            reasons.append(f"daily_dd>{self.settings.risk.daily_dd_limit:.4f}")
        if state.weekly_dd_pct > self.settings.risk.weekly_dd_limit:
            reasons.append(f"weekly_dd>{self.settings.risk.weekly_dd_limit:.4f}")
        if state.consecutive_losses > self.settings.risk.max_consecutive_losses:
            reasons.append(f"consecutive_losses>{self.settings.risk.max_consecutive_losses}")
        if self._critical_execution_errors > self.settings.execution.kill_switch_max_exec_errors:
            reasons.append(f"critical_execution_errors>{self.settings.execution.kill_switch_max_exec_errors}")

        if reasons and not state.safe_mode:
            self._activate_safe_mode(reason=";".join(reasons), now=now)

    def _activate_safe_mode(self, *, reason: str, now: datetime, extra_payload: dict | None = None) -> None:
        current = self.state_store.load()
        if current and current.safe_mode:
            return

        updated = self.state_store.set_safe_mode(True, reason=reason, now=now)
        payload = {
            "reason": reason,
            "safe_mode": True,
            "open_positions_count": updated.open_positions_count,
            "daily_dd_pct": updated.daily_dd_pct,
            "weekly_dd_pct": updated.weekly_dd_pct,
            "consecutive_losses": updated.consecutive_losses,
        }
        if extra_payload:
            payload.update(extra_payload)

        LOG.warning("Kill-switch activated: %s", reason)
        self.bundle.audit_logger.log_warning("kill_switch", "Safe mode activated.", payload=payload)
        self._send_telegram_alert(TelegramNotifier.ALERT_KILL_SWITCH, payload)

    def _notify_closed_trades(self, closed_events: list[dict]) -> None:
        for event in closed_events:
            self._send_telegram_alert(TelegramNotifier.ALERT_EXIT, event)

    def _send_critical_error_alert(self, component: str, message: str) -> None:
        self._send_telegram_alert(
            TelegramNotifier.ALERT_CRITICAL_ERROR,
            {"component": component, "message": message},
        )

    def _send_telegram_alert(self, alert_type: str, payload: dict) -> None:
        try:
            self.telegram_notifier.send_alert(alert_type, payload)
        except Exception as exc:
            self.bundle.audit_logger.log_error(
                "telegram",
                f"Notifier failed for alert_type={alert_type}: {exc}",
                payload={"alert_payload": payload},
            )

    def _build_snapshot(self, timestamp: datetime) -> MarketSnapshot:
        return self.bundle.market_data.build_snapshot(
            symbol=self.settings.strategy.symbol,
            timestamp=timestamp,
        )

    def _update_runtime_metrics(self, **fields: object) -> None:
        if "config_hash" not in fields:
            fields["config_hash"] = self.settings.config_hash
        try:
            self.state_store.update_runtime_metrics(**fields)
        except Exception as exc:
            LOG.warning("Runtime metrics update failed: %s", exc)

    def _record_decision_outcome(
        self,
        *,
        timestamp: datetime,
        outcome_group: str,
        outcome_reason: str,
        regime: str | None = None,
        signal_id: str | None = None,
        snapshot_id: str | None = None,
        feature_snapshot_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        try:
            self.state_store.record_decision_outcome(
                cycle_timestamp=timestamp,
                outcome_group=outcome_group,
                outcome_reason=outcome_reason,
                config_hash=self.settings.config_hash,
                regime=regime,
                signal_id=signal_id,
                snapshot_id=snapshot_id,
                feature_snapshot_id=feature_snapshot_id,
                details=details,
            )
        except Exception as exc:
            LOG.warning("Decision outcome persistence failed: %s", exc)

    def _bootstrap_feature_engine_history(self, now: datetime) -> dict[str, object]:
        symbol = self.settings.strategy.symbol
        oi_since = now.astimezone(timezone.utc) - timedelta(days=self.settings.data_quality.oi_baseline_days)
        oi_rows = fetch_oi_samples(
            self.conn,
            symbol=symbol,
            since_ts=oi_since,
        )
        feature_config = getattr(self.bundle.feature_engine, "config", None)
        cvd_window_bars = int(
            getattr(
                feature_config,
                "cvd_divergence_window_bars",
                self.settings.data_quality.cvd_divergence_bars,
            )
        )
        cvd_rows = fetch_cvd_price_history(
            self.conn,
            symbol=symbol,
            timeframe="15m",
            limit=max(self.settings.data_quality.cvd_divergence_bars, cvd_window_bars) + 1,
        )
        if hasattr(self.bundle.feature_engine, "bootstrap_oi_history"):
            oi_summary = self.bundle.feature_engine.bootstrap_oi_history(oi_rows)
        else:
            oi_summary = {"loaded_samples": len(oi_rows), "skipped": "feature_engine_has_no_bootstrap"}
        if hasattr(self.bundle.feature_engine, "bootstrap_cvd_price_history"):
            cvd_summary = self.bundle.feature_engine.bootstrap_cvd_price_history(cvd_rows)
        else:
            cvd_summary = {"loaded_bars": len(cvd_rows), "skipped": "feature_engine_has_no_bootstrap"}
        return {
            "oi": oi_summary,
            "cvd": cvd_summary,
        }

    def _record_bootstrap_summary(self, summary: dict[str, object]) -> None:
        LOG.info("Feature bootstrap summary | %s", json.dumps(summary, sort_keys=True))
        self.bundle.audit_logger.log_info(
            "feature_quality",
            "Feature bootstrap summary.",
            payload=summary,
        )

    def _record_feature_quality(self, features: object) -> None:
        payload = self._feature_quality_payload(features)
        counts = {"ready": 0, "degraded": 0, "unavailable": 0}
        for item in payload.values():
            status = str(item.get("status", "unavailable"))
            if status in counts:
                counts[status] += 1
        self.metrics.set_gauge(FEATURE_QUALITY_READY, float(counts["ready"]))
        self.metrics.set_gauge(FEATURE_QUALITY_DEGRADED, float(counts["degraded"]))
        self.metrics.set_gauge(FEATURE_QUALITY_UNAVAILABLE, float(counts["unavailable"]))
        LOG.info(
            "Feature quality summary | ready=%s | degraded=%s | unavailable=%s | keys=%s",
            counts["ready"],
            counts["degraded"],
            counts["unavailable"],
            ",".join(sorted(payload)),
        )
        self._update_runtime_metrics(feature_quality_json=json.dumps(payload, sort_keys=True))

    @staticmethod
    def _feature_quality_payload(features: object) -> dict[str, dict[str, object]]:
        quality_map = getattr(features, "quality", {})
        if not isinstance(quality_map, dict):
            return {}
        return {
            name: {
                "status": quality.status,
                "reason": quality.reason,
                "metadata": quality.metadata,
                "provenance": quality.provenance,
            }
            for name, quality in sorted(quality_map.items())
            if hasattr(quality, "status")
        }

    def _log_no_signal_diagnostics(self, timestamp: datetime, diagnostics: SignalDiagnostics) -> None:
        message = (
            "Decision diagnostics | timestamp=%s | outcome=no_signal | blocked_by=%s | "
            "sweep_detected=%s | reclaim_detected=%s | sweep_side=%s | sweep_depth_pct=%s | "
            "direction_inferred=%s | regime=%s | direction_allowed=%s | confluence_preview=%s"
        )
        values: list[object] = [
            timestamp.isoformat(),
            self._log_optional_value(diagnostics.blocked_by),
            self._log_bool(diagnostics.sweep_detected),
            self._log_bool(diagnostics.reclaim_detected),
            self._log_optional_value(diagnostics.sweep_side),
            self._log_optional_float(diagnostics.sweep_depth_pct),
            self._log_optional_value(diagnostics.direction_inferred),
            diagnostics.regime.value,
            self._log_bool(diagnostics.direction_allowed),
            self._log_optional_float(diagnostics.confluence_preview),
        ]
        if diagnostics.blocked_by in {"no_reclaim", "uptrend_continuation_weak", "uptrend_pullback_weak"}:
            message += " | close_vs_buf_atr=%s | wick_vs_min_atr=%s | sweep_vs_buf_atr=%s"
            values.extend(
                [
                    self._log_optional_float_short(diagnostics.close_vs_reclaim_buffer_atr),
                    self._log_optional_float_short(diagnostics.wick_vs_min_atr),
                    self._log_optional_float_short(diagnostics.sweep_vs_buffer_atr),
                ]
            )
        LOG.info(message, *values)

    @staticmethod
    def _signal_diagnostics_payload(diagnostics: SignalDiagnostics) -> dict[str, object]:
        return {
            "timestamp": diagnostics.timestamp.isoformat(),
            "config_hash": diagnostics.config_hash,
            "blocked_by": diagnostics.blocked_by,
            "sweep_detected": diagnostics.sweep_detected,
            "reclaim_detected": diagnostics.reclaim_detected,
            "sweep_side": diagnostics.sweep_side,
            "sweep_level": diagnostics.sweep_level,
            "sweep_depth_pct": diagnostics.sweep_depth_pct,
            "direction_inferred": diagnostics.direction_inferred,
            "regime": diagnostics.regime.value,
            "direction_allowed": diagnostics.direction_allowed,
            "confluence_preview": diagnostics.confluence_preview,
            "candidate_reasons_preview": diagnostics.candidate_reasons_preview,
        }

    def _process_trade_lifecycle(self, snapshot: MarketSnapshot) -> list[dict]:
        open_records = self.state_store.get_open_trade_records()
        if not open_records:
            return []

        latest_high = float(snapshot.candles_15m[-1]["high"]) if snapshot.candles_15m else float(snapshot.price)
        latest_low = float(snapshot.candles_15m[-1]["low"]) if snapshot.candles_15m else float(snapshot.price)
        latest_close = float(snapshot.candles_15m[-1]["close"]) if snapshot.candles_15m else float(snapshot.price)

        closed_events: list[dict] = []
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
            funding_paid = self._compute_position_funding_paid(
                symbol=record.position.symbol,
                direction=record.position.direction,
                entry_price=record.position.entry_price,
                size=record.position.size,
                opened_at=record.position.opened_at,
                closed_at=snapshot.timestamp,
            )
            settlement = replace(
                settlement,
                pnl_abs=settlement.pnl_abs - funding_paid,
                funding_paid=funding_paid,
            )
            self.state_store.settle_trade_close(
                position_id=record.position.position_id,
                settlement=settlement,
                closed_at=snapshot.timestamp,
            )
            closed_events.append(
                {
                    "position_id": record.position.position_id,
                    "symbol": record.position.symbol,
                    "direction": record.position.direction,
                    "entry_price": record.position.entry_price,
                    "exit_price": settlement.exit_price,
                    "pnl_abs": settlement.pnl_abs,
                    "exit_reason": settlement.exit_reason,
                    "closed_at": snapshot.timestamp.isoformat(),
                }
            )
        return closed_events

    def _compute_position_funding_paid(
        self,
        *,
        symbol: str,
        direction: str,
        entry_price: float,
        size: float,
        opened_at: datetime,
        closed_at: datetime,
    ) -> float:
        funding_samples = fetch_funding_rates(
            self.conn,
            symbol=symbol,
            start_ts=opened_at,
            end_ts=closed_at,
        )
        return compute_funding_paid(
            direction=direction,
            notional=max(float(entry_price) * float(size), 0.0),
            opened_at=opened_at,
            closed_at=closed_at,
            funding_samples=funding_samples,
        )

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

    @staticmethod
    def _latest_candle_open_at(candles: list[dict]) -> datetime | None:
        if not candles:
            return None
        raw_value = candles[-1].get("open_time")
        if raw_value is None:
            return None
        if isinstance(raw_value, datetime):
            if raw_value.tzinfo is None:
                return raw_value.replace(tzinfo=timezone.utc)
            return raw_value.astimezone(timezone.utc)
        parsed = datetime.fromisoformat(str(raw_value))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _last_ws_message_at(self) -> datetime | None:
        websocket_client = self.bundle.market_data.websocket_client
        if websocket_client is None:
            return None
        last_message_at = websocket_client.last_message_at
        if last_message_at is None:
            return None
        if last_message_at.tzinfo is None:
            return last_message_at.replace(tzinfo=timezone.utc)
        return last_message_at.astimezone(timezone.utc)

    @staticmethod
    def _format_health_warning(status: HealthStatus) -> str:
        failures: list[str] = []
        if not status.websocket_alive:
            failures.append("websocket_alive=false")
        if not status.db_writable:
            failures.append("db_writable=false")
        if not status.exchange_reachable:
            failures.append("exchange_reachable=false")
        return ", ".join(failures) if failures else "health_check_failed"

    def _start_data_feeds(self) -> None:
        websocket_client = self.bundle.market_data.websocket_client
        if websocket_client is None:
            return

        try:
            websocket_client.start(symbol=self.settings.strategy.symbol)
            LOG.info("Market data feed thread started for %s.", self.settings.strategy.symbol)
            self.bundle.audit_logger.log_info("orchestrator", "Market data feeds started.")
        except Exception as exc:
            reason = f"feed_start_failed:{exc}"
            self.bundle.audit_logger.log_error("orchestrator", "Failed to start market data feeds.", payload={"error": str(exc)})
            self.state_store.set_safe_mode(True, reason=reason, now=self._now())
            self._send_critical_error_alert("orchestrator", f"Failed to start market data feeds: {exc}")

    def _stop_data_feeds(self) -> None:
        websocket_client = self.bundle.market_data.websocket_client
        if websocket_client is None:
            return
        try:
            websocket_client.stop()
            self.bundle.audit_logger.log_info("orchestrator", "Market data feeds stopped.")
        except Exception as exc:
            self.bundle.audit_logger.log_warning("orchestrator", "Failed to stop market data feeds.", payload={"error": str(exc)})

    def _initialize_runtime_schedule(self, now: datetime) -> None:
        now_utc = now.astimezone(timezone.utc)
        self._current_utc_day = now_utc.date()
        self._next_monitor_at = now_utc
        self._next_health_at = now_utc
        if self._is_15m_boundary(now_utc):
            self._next_decision_at = now_utc
        else:
            self._next_decision_at = self._next_15m_boundary(now_utc)

    def _handle_daily_rollover(self, now: datetime) -> None:
        now_utc = now.astimezone(timezone.utc)
        if self._current_utc_day is None:
            self._current_utc_day = now_utc.date()
            return
        if now_utc.date() == self._current_utc_day:
            return

        summary_day = self._current_utc_day
        self.send_daily_summary(summary_day)
        self._current_utc_day = now_utc.date()

    def _advance_decision_deadline(self, current: datetime, now: datetime) -> datetime:
        result = current
        while result <= now:
            result += timedelta(minutes=15)
        return result

    def _compute_sleep_seconds(self, now: datetime) -> float:
        idle_sleep = max(float(self.settings.execution.loop_idle_sleep_seconds), 0.05)
        targets = [self._next_monitor_at, self._next_health_at, self._next_decision_at]
        deltas = [
            (target - now).total_seconds()
            for target in targets
            if target is not None and (target - now).total_seconds() > 0
        ]
        if not deltas:
            return idle_sleep
        return max(min(min(deltas), idle_sleep), 0.05)

    def _shutdown(self) -> None:
        self._stop_data_feeds()
        try:
            self.state_store.refresh_runtime_state(self._now())
        except Exception:
            pass
        self.bundle.audit_logger.log_info(
            "orchestrator",
            "Runtime loop stopped.",
            payload={"metrics": self.metrics.snapshot()},
        )
        LOG.info("Bot stopped.")

    def _sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        self._sleep_fn(seconds)

    def _now(self) -> datetime:
        value = self._now_provider()
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _log_bool(value: bool | None) -> str:
        if value is None:
            return "none"
        return str(value).lower()

    @staticmethod
    def _log_optional_float(value: float | None) -> str:
        if value is None:
            return "none"
        return f"{value:.6f}"

    @staticmethod
    def _log_optional_float_short(value: float | None) -> str:
        if value is None:
            return "none"
        return f"{value:.3f}"

    @staticmethod
    def _log_optional_value(value: object | None) -> str:
        if value is None:
            return "none"
        return str(value)

    @staticmethod
    def _is_15m_boundary(now: datetime) -> bool:
        return now.minute % 15 == 0 and now.second == 0 and now.microsecond == 0

    @staticmethod
    def _next_15m_boundary(now: datetime) -> datetime:
        now_utc = now.astimezone(timezone.utc)
        base = now_utc.replace(second=0, microsecond=0)
        next_minute = ((base.minute // 15) + 1) * 15
        if next_minute >= 60:
            return base.replace(minute=0) + timedelta(hours=1)
        return base.replace(minute=next_minute)
