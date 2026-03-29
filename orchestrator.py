from __future__ import annotations

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.governance import GovernanceConfig, GovernanceLayer
from core.models import GovernanceRuntimeState, MarketSnapshot, RiskRuntimeState
from core.regime_engine import RegimeConfig, RegimeEngine
from core.risk_engine import RiskConfig, RiskEngine
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
from monitoring.health import HealthMonitor
from monitoring.metrics import (
    CYCLE_DURATION_MS,
    ERRORS_TOTAL,
    GOVERNANCE_VETOES,
    RISK_BLOCKS,
    SIGNALS_GENERATED,
    TRADES_CLOSED,
    TRADES_OPENED,
    MetricsRegistry,
)
from monitoring.telegram_notifier import TelegramConfig, TelegramNotifier
from settings import AppSettings, BotMode
from storage.position_persister import SqlitePositionPersister
from storage.repositories import get_daily_metrics, save_executable_signal, save_signal_candidate
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
                entry_offset_atr=settings.strategy.entry_offset_atr,
                invalidation_offset_atr=settings.strategy.invalidation_offset_atr,
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
        self.state_store.refresh_runtime_state(self._now())

        recovery_report = self.recovery.run_startup_sync()
        if recovery_report.safe_mode:
            LOG.warning(
                "Startup recovery entered safe mode. New trades are blocked but lifecycle monitoring will continue. issues=%s",
                recovery_report.issues,
            )

        self._start_data_feeds()
        now = self._now()
        self._initialize_runtime_schedule(now)
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
        try:
            self.state_store.refresh_runtime_state(timestamp)
            try:
                snapshot = self._build_snapshot(timestamp)
            except Exception as exc:
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
                self.bundle.audit_logger.log_error("lifecycle", f"Lifecycle processing failed: {exc}")
                self.state_store.mark_error(f"lifecycle_failed:{exc}")
                self.metrics.inc(ERRORS_TOTAL)
                self._send_critical_error_alert("lifecycle", f"Lifecycle processing failed: {exc}")
                return

            state = self.state_store.load()
            if state and state.safe_mode:
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
            regime = self.bundle.regime_engine.classify(features)
            candidate = self.bundle.signal_engine.generate(features, regime)
            if candidate is None:
                self.bundle.audit_logger.log_decision("decision", "No signal candidate.")
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
                self.bundle.audit_logger.log_decision(
                    "risk",
                    f"Trade blocked: {risk_decision.reason}",
                    payload={"reason": risk_decision.reason},
                )
                self.state_store.mark_healthy()
                self.metrics.inc(RISK_BLOCKS)
                return

            try:
                self.bundle.execution_engine.execute_signal(executable, size=risk_decision.size, leverage=risk_decision.leverage)
                self.state_store.record_trade_open(
                    candidate=candidate,
                    executable=executable,
                    schema_version=self.settings.schema_version,
                    config_hash=self.settings.config_hash,
                )
                self.state_store.mark_healthy()
                self.metrics.inc(TRADES_OPENED)
                trade_payload = {
                    "symbol": self.settings.strategy.symbol,
                    "signal_id": executable.signal_id,
                    "direction": executable.direction,
                    "entry_price": executable.entry_price,
                    "size": risk_decision.size,
                    "leverage": risk_decision.leverage,
                }
                self.bundle.audit_logger.log_trade("execution", "Trade opened.", payload=trade_payload)
                self._send_telegram_alert(TelegramNotifier.ALERT_ENTRY, trade_payload)
            except Exception as exc:
                self._critical_execution_errors += 1
                self.bundle.audit_logger.log_error("execution", f"Execution failed: {exc}")
                self.state_store.mark_error(f"execution_failed:{exc}")
                self.metrics.inc(ERRORS_TOTAL)
                self._send_critical_error_alert("execution", f"Execution failed: {exc}")
        finally:
            duration_ms = (time.perf_counter() - cycle_started) * 1000.0
            self.metrics.set_gauge(CYCLE_DURATION_MS, duration_ms)

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
