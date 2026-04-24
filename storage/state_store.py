from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from core.models import BotState, ExecutableSignal, FeatureSnapshot, Features, GovernanceRuntimeState, MarketSnapshot, Position, RiskRuntimeState, SettlementMetrics, SignalCandidate
from storage.repositories import (
    close_position,
    fetch_decision_outcome_counts,
    fetch_feature_snapshot,
    fetch_market_snapshot,
    fetch_closed_trade_pnl_series_between,
    fetch_recent_feature_snapshots,
    fetch_open_positions,
    fetch_open_trade_positions,
    fetch_recent_closed_trade_outcomes,
    fetch_trade_log_rows_for_day,
    get_config_snapshot,
    get_bot_state,
    get_daily_metrics,
    get_last_closed_loss_at,
    get_latest_position_for_signal,
    get_open_trade_log_for_position,
    get_open_positions_count,
    get_runtime_metrics,
    insert_feature_snapshot,
    insert_market_snapshot,
    insert_trade_log_open,
    insert_decision_outcome,
    sum_closed_pnl_abs_before,
    update_trade_log_close,
    upsert_bot_state,
    upsert_config_snapshot,
    upsert_daily_metrics,
    upsert_runtime_metrics,
)

LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenTradeRecord:
    trade_id: str
    position: Position


class StateStore:
    def __init__(self, connection: sqlite3.Connection, mode: str, reference_equity: float = 10_000.0) -> None:
        self.connection = connection
        self.mode = mode
        self.reference_equity = max(reference_equity, 1e-8)
        self._migrations_applied: bool = False

    def _apply_migrations(self) -> None:
        """Apply schema migrations idempotently. Runs once per StateStore instance."""
        if self._migrations_applied:
            return

        cursor = self.connection.cursor()

        # Check if bot_state table exists before attempting migration
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bot_state'")
        bot_state_exists = cursor.fetchone() is not None

        if bot_state_exists:
            cursor.execute("PRAGMA table_info(bot_state)")
            columns = {row[1] for row in cursor.fetchall()}

            if "safe_mode_entry_at" not in columns:
                cursor.execute("ALTER TABLE bot_state ADD COLUMN safe_mode_entry_at TEXT DEFAULT NULL")
                self.connection.commit()
                LOG.info("Migration applied: added safe_mode_entry_at column to bot_state")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS safe_mode_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                trigger TEXT,
                reason TEXT,
                probe_successes INTEGER DEFAULT 0,
                probe_failures INTEGER DEFAULT 0,
                remaining_triggers TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        self.connection.commit()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runtime_metrics (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                updated_at TEXT NOT NULL,
                last_decision_cycle_started_at TEXT,
                last_decision_cycle_finished_at TEXT,
                last_decision_outcome TEXT,
                decision_cycle_status TEXT,
                last_snapshot_built_at TEXT,
                last_snapshot_symbol TEXT,
                last_15m_candle_open_at TEXT,
                last_1h_candle_open_at TEXT,
                last_4h_candle_open_at TEXT,
                last_ws_message_at TEXT,
                last_health_check_at TEXT,
                last_runtime_warning TEXT,
                feature_quality_json TEXT,
                config_hash TEXT
            )
        """)
        self.connection.commit()

        cursor.execute("PRAGMA table_info(runtime_metrics)")
        runtime_columns = {row[1] for row in cursor.fetchall()}
        if "feature_quality_json" not in runtime_columns:
            cursor.execute("ALTER TABLE runtime_metrics ADD COLUMN feature_quality_json TEXT DEFAULT NULL")
            self.connection.commit()
            LOG.info("Migration applied: added feature_quality_json column to runtime_metrics")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oi_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                oi_value REAL NOT NULL,
                source TEXT NOT NULL DEFAULT 'unknown',
                captured_at TEXT NOT NULL,
                UNIQUE(symbol, timestamp)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_oi_samples_symbol_time
                ON oi_samples(symbol, timestamp)
        """)
        self.connection.commit()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cvd_price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                bar_time TEXT NOT NULL,
                price_close REAL NOT NULL,
                cvd REAL NOT NULL,
                tfi REAL,
                source TEXT NOT NULL DEFAULT 'unknown',
                captured_at TEXT NOT NULL,
                UNIQUE(symbol, timeframe, bar_time)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cvd_price_history_symbol_tf_time
                ON cvd_price_history(symbol, timeframe, bar_time)
        """)
        self.connection.commit()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_timestamp TEXT NOT NULL,
                outcome_group TEXT NOT NULL,
                outcome_reason TEXT NOT NULL,
                regime TEXT,
                config_hash TEXT NOT NULL,
                signal_id TEXT,
                snapshot_id TEXT,
                feature_snapshot_id TEXT,
                details_json TEXT
            )
        """)
        self.connection.commit()
        cursor.execute("PRAGMA table_info(decision_outcomes)")
        decision_columns = {row[1] for row in cursor.fetchall()}
        if "snapshot_id" not in decision_columns:
            cursor.execute("ALTER TABLE decision_outcomes ADD COLUMN snapshot_id TEXT DEFAULT NULL")
            self.connection.commit()
        if "feature_snapshot_id" not in decision_columns:
            cursor.execute("ALTER TABLE decision_outcomes ADD COLUMN feature_snapshot_id TEXT DEFAULT NULL")
            self.connection.commit()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                cycle_timestamp TEXT NOT NULL,
                exchange_timestamp TEXT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                funding_rate REAL,
                open_interest REAL,
                bid_price REAL,
                ask_price REAL,
                source TEXT NOT NULL,
                latency_ms REAL,
                data_quality_flag TEXT NOT NULL,
                book_ticker_json TEXT NOT NULL,
                open_interest_json TEXT NOT NULL,
                candles_15m_json TEXT NOT NULL,
                candles_1h_json TEXT NOT NULL,
                candles_4h_json TEXT NOT NULL,
                funding_history_json TEXT NOT NULL,
                aggtrade_events_60s_json TEXT NOT NULL,
                aggtrade_events_15m_json TEXT NOT NULL,
                aggtrade_bucket_60s_json TEXT NOT NULL,
                aggtrade_bucket_15m_json TEXT NOT NULL,
                force_order_events_60s_json TEXT NOT NULL,
                source_meta_json TEXT,
                captured_at TEXT NOT NULL,
                candles_15m_exchange_ts TEXT,
                candles_1h_exchange_ts TEXT,
                candles_4h_exchange_ts TEXT,
                funding_exchange_ts TEXT,
                oi_exchange_ts TEXT,
                aggtrades_exchange_ts TEXT,
                snapshot_build_started_at TEXT,
                snapshot_build_finished_at TEXT
            )
        """)
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_market_snapshots_cycle_ts
                ON market_snapshots(cycle_timestamp)
            """
        )
        self.connection.commit()

        # Quant-grade lineage migration: add per-input timestamps and build timing
        cursor.execute("PRAGMA table_info(market_snapshots)")
        snapshot_columns = {row[1] for row in cursor.fetchall()}

        quant_grade_columns = [
            "candles_15m_exchange_ts",
            "candles_1h_exchange_ts",
            "candles_4h_exchange_ts",
            "funding_exchange_ts",
            "oi_exchange_ts",
            "aggtrades_exchange_ts",
            "snapshot_build_started_at",
            "snapshot_build_finished_at",
        ]

        for col in quant_grade_columns:
            if col not in snapshot_columns:
                cursor.execute(f"ALTER TABLE market_snapshots ADD COLUMN {col} TEXT DEFAULT NULL")
                self.connection.commit()
                LOG.info(f"Migration applied: added {col} column to market_snapshots")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feature_snapshots (
                feature_snapshot_id TEXT PRIMARY KEY,
                snapshot_id TEXT NOT NULL,
                cycle_timestamp TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                config_hash TEXT NOT NULL,
                features_json TEXT NOT NULL,
                quality_json TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                FOREIGN KEY (snapshot_id) REFERENCES market_snapshots(snapshot_id)
            )
        """)
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_feature_snapshots_snapshot_id
                ON feature_snapshots(snapshot_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_feature_snapshots_cycle_ts
                ON feature_snapshots(cycle_timestamp)
            """
        )
        self.connection.commit()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_snapshots (
                config_hash TEXT PRIMARY KEY,
                captured_at TEXT NOT NULL,
                strategy_json TEXT NOT NULL
            )
        """)
        self.connection.commit()

        self._migrations_applied = True

    def ensure_initialized(self) -> BotState:
        self._apply_migrations()
        existing = self.load()
        if existing is not None:
            return existing
        state = BotState(
            mode=self.mode,
            healthy=True,
            safe_mode=False,
            open_positions_count=0,
            consecutive_losses=0,
            daily_dd_pct=0.0,
            weekly_dd_pct=0.0,
            last_trade_at=None,
            last_error=None,
        )
        self.save(state)
        return state

    def save(self, state: BotState) -> None:
        upsert_bot_state(self.connection, state=state, timestamp=datetime.now(timezone.utc))
        self.connection.commit()

    def load(self) -> BotState | None:
        raw = get_bot_state(self.connection)
        if raw is None:
            return None
        raw_entry_at = raw.get("safe_mode_entry_at")
        return BotState(
            mode=raw["mode"],
            healthy=bool(raw["healthy"]),
            safe_mode=bool(raw["safe_mode"]),
            open_positions_count=raw["open_positions_count"],
            consecutive_losses=raw["consecutive_losses"],
            daily_dd_pct=raw["daily_dd_pct"],
            weekly_dd_pct=raw["weekly_dd_pct"],
            last_trade_at=datetime.fromisoformat(raw["last_trade_at"]) if raw["last_trade_at"] else None,
            last_error=raw["last_error"],
            safe_mode_entry_at=datetime.fromisoformat(raw_entry_at) if raw_entry_at else None,
        )

    def get_open_positions(self) -> int:
        return get_open_positions_count(self.connection)

    def get_open_positions_snapshot(self) -> list[Position]:
        rows = fetch_open_positions(self.connection)
        positions: list[Position] = []
        for row in rows:
            positions.append(
                Position(
                    position_id=row["position_id"],
                    symbol=row["symbol"],
                    direction=row["direction"],
                    status=row["status"],
                    entry_price=float(row["entry_price"]),
                    size=float(row["size"]),
                    leverage=int(row["leverage"]),
                    stop_loss=float(row["stop_loss"]),
                    take_profit_1=float(row["take_profit_1"]),
                    take_profit_2=float(row["take_profit_2"]),
                    opened_at=datetime.fromisoformat(row["opened_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    signal_id=row["signal_id"],
                )
            )
        return positions

    def set_safe_mode(self, enabled: bool, reason: str | None = None, now: datetime | None = None) -> BotState:
        ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        state = self.refresh_runtime_state(ts)
        assert state is not None

        if enabled and not state.safe_mode:
            new_entry_at: datetime | None = ts
        elif enabled and state.safe_mode:
            new_entry_at = state.safe_mode_entry_at
        else:
            new_entry_at = None

        updated = replace(
            state,
            healthy=False if enabled else True,
            safe_mode=enabled,
            open_positions_count=self.get_open_positions(),
            last_error=reason if enabled else None,
            safe_mode_entry_at=new_entry_at,
        )
        self.save(updated)

        trigger = (reason or "").split(":")[0].strip() if reason else None
        event_type = "entered" if enabled else "cleared"
        try:
            self.connection.execute(
                """
                INSERT INTO safe_mode_events (event_type, trigger, reason, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (event_type, trigger, reason, ts.isoformat()),
            )
            self.connection.commit()
        except Exception as evt_exc:
            LOG.warning("Failed to write safe_mode event to audit table: %s", evt_exc)

        return updated

    def get_governance_state(self, now: datetime | None = None) -> GovernanceRuntimeState:
        ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        state = self.refresh_runtime_state(ts)
        assert state is not None
        metrics = get_daily_metrics(self.connection, ts.date()) or {}
        last_loss_at = get_last_closed_loss_at(self.connection)

        return GovernanceRuntimeState(
            trades_today=int(metrics.get("trades_count", 0)),
            consecutive_losses=state.consecutive_losses,
            daily_dd_pct=state.daily_dd_pct,
            weekly_dd_pct=state.weekly_dd_pct,
            last_trade_at=state.last_trade_at,
            last_loss_at=last_loss_at,
        )

    def get_risk_state(self) -> RiskRuntimeState:
        state = self.refresh_runtime_state()
        assert state is not None
        return RiskRuntimeState(
            consecutive_losses=state.consecutive_losses,
            daily_dd_pct=state.daily_dd_pct,
            weekly_dd_pct=state.weekly_dd_pct,
        )

    def sync_daily_metrics(self, day: date) -> None:
        rows = fetch_trade_log_rows_for_day(self.connection, day)
        trades_count = len(rows)

        closed_rows = [row for row in rows if row.get("closed_at")]
        wins = sum(1 for row in closed_rows if float(row.get("pnl_abs", 0.0)) > 0)
        losses = sum(1 for row in closed_rows if float(row.get("pnl_abs", 0.0)) < 0)
        pnl_abs = sum(float(row.get("pnl_abs", 0.0)) for row in closed_rows)
        pnl_r_sum = sum(float(row.get("pnl_r", 0.0)) for row in closed_rows)
        expectancy_r = pnl_r_sum / len(closed_rows) if closed_rows else 0.0

        state = self.load() or self.ensure_initialized()
        upsert_daily_metrics(
            self.connection,
            day=day,
            trades_count=trades_count,
            wins=wins,
            losses=losses,
            pnl_abs=pnl_abs,
            pnl_r_sum=pnl_r_sum,
            daily_dd_pct=state.daily_dd_pct,
            expectancy_r=expectancy_r,
        )
        self.connection.commit()

    def get_open_trade_records(self) -> list[OpenTradeRecord]:
        rows = fetch_open_trade_positions(self.connection)
        records: list[OpenTradeRecord] = []
        for row in rows:
            position = Position(
                position_id=row["position_id"],
                symbol=row["symbol"],
                direction=row["direction"],
                status=row["status"],
                entry_price=float(row["entry_price"]),
                size=float(row["size"]),
                leverage=int(row["leverage"]),
                stop_loss=float(row["stop_loss"]),
                take_profit_1=float(row["take_profit_1"]),
                take_profit_2=float(row["take_profit_2"]),
                opened_at=datetime.fromisoformat(row["opened_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                signal_id=row["signal_id"],
            )
            records.append(OpenTradeRecord(trade_id=row["trade_id"], position=position))
        return records

    def record_trade_open(
        self,
        *,
        candidate: SignalCandidate,
        executable: ExecutableSignal,
        schema_version: str,
        config_hash: str,
        filled_entry_price: float | None = None,
    ) -> None:
        position = get_latest_position_for_signal(self.connection, executable.signal_id)
        if not position:
            raise RuntimeError(f"No position found for signal_id={executable.signal_id}")

        opened_at = datetime.fromisoformat(position["opened_at"])
        entry_price = float(position["entry_price"] if filled_entry_price is None else filled_entry_price)
        if entry_price <= 0:
            raise RuntimeError(f"Invalid filled entry price for signal_id={executable.signal_id}: {entry_price}")
        insert_trade_log_open(
            self.connection,
            trade_id=f"trd-{uuid4().hex}",
            signal_id=executable.signal_id,
            position_id=position["position_id"],
            opened_at=opened_at,
            direction=executable.direction,
            regime=candidate.regime.value,
            confluence_score=candidate.confluence_score,
            entry_price=entry_price,
            size=float(position["size"]),
            features_at_entry_json=candidate.features_json,
            schema_version=schema_version,
            config_hash=config_hash,
        )

        state = self.refresh_runtime_state(opened_at)
        assert state is not None
        updated_state = replace(
            state,
            healthy=True,
            last_error=None,
            open_positions_count=self.get_open_positions(),
            last_trade_at=opened_at,
        )
        self.save(updated_state)
        self.sync_daily_metrics(opened_at.astimezone(timezone.utc).date())

    def settle_trade_close(
        self,
        *,
        position_id: str,
        settlement: SettlementMetrics,
        closed_at: datetime,
    ) -> None:
        open_trade = get_open_trade_log_for_position(self.connection, position_id)
        if not open_trade:
            raise RuntimeError(f"No open trade_log row for position_id={position_id}")

        close_position(self.connection, position_id=position_id, closed_at=closed_at)
        update_trade_log_close(
            self.connection,
            trade_id=open_trade["trade_id"],
            closed_at=closed_at,
            exit_price=settlement.exit_price,
            pnl_abs=settlement.pnl_abs,
            pnl_r=settlement.pnl_r,
            mae=settlement.mae,
            mfe=settlement.mfe,
            exit_reason=settlement.exit_reason,
        )

        opened_at = datetime.fromisoformat(open_trade["opened_at"])
        self.sync_daily_metrics(opened_at.astimezone(timezone.utc).date())
        self.sync_daily_metrics(closed_at.astimezone(timezone.utc).date())

        state = self.refresh_runtime_state(closed_at)
        assert state is not None
        updated_state = replace(
            state,
            healthy=True,
            last_error=None,
            open_positions_count=self.get_open_positions(),
        )
        self.save(updated_state)

    def mark_error(self, message: str) -> None:
        state = self.refresh_runtime_state()
        assert state is not None
        self.save(replace(state, healthy=False, last_error=message))

    def mark_healthy(self) -> None:
        state = self.refresh_runtime_state()
        assert state is not None
        self.save(replace(state, healthy=True, last_error=None, open_positions_count=self.get_open_positions()))

    def update_runtime_metrics(self, **fields: object) -> dict | None:
        self._apply_migrations()
        upsert_runtime_metrics(self.connection, **fields)
        self.connection.commit()
        return get_runtime_metrics(self.connection)

    def record_decision_outcome(
        self,
        *,
        cycle_timestamp: datetime,
        outcome_group: str,
        outcome_reason: str,
        config_hash: str,
        regime: str | None = None,
        signal_id: str | None = None,
        details: dict | None = None,
        snapshot_id: str | None = None,
        feature_snapshot_id: str | None = None,
    ) -> None:
        self._apply_migrations()
        insert_decision_outcome(
            self.connection,
            cycle_timestamp=cycle_timestamp,
            outcome_group=outcome_group,
            outcome_reason=outcome_reason,
            config_hash=config_hash,
            regime=regime,
            signal_id=signal_id,
            details=details,
            snapshot_id=snapshot_id,
            feature_snapshot_id=feature_snapshot_id,
        )
        self.connection.commit()

    def record_market_snapshot(self, snapshot: MarketSnapshot) -> str:
        self._apply_migrations()
        snapshot_id = snapshot.snapshot_id or f"ms-{uuid4().hex}"
        snapshot.snapshot_id = snapshot_id
        insert_market_snapshot(
            self.connection,
            snapshot_id=snapshot_id,
            snapshot=snapshot,
            captured_at=snapshot.timestamp,
        )
        self.connection.commit()
        return snapshot_id

    def record_feature_snapshot(self, *, snapshot_id: str, features: Features) -> str:
        self._apply_migrations()
        feature_snapshot = FeatureSnapshot(
            feature_snapshot_id=f"fs-{uuid4().hex}",
            snapshot_id=snapshot_id,
            cycle_timestamp=features.timestamp,
            schema_version=features.schema_version,
            config_hash=features.config_hash,
            features_json={
                "atr_15m": features.atr_15m,
                "atr_4h": features.atr_4h,
                "atr_4h_norm": features.atr_4h_norm,
                "ema50_4h": features.ema50_4h,
                "ema200_4h": features.ema200_4h,
                "sweep_detected": features.sweep_detected,
                "reclaim_detected": features.reclaim_detected,
                "sweep_level": features.sweep_level,
                "sweep_depth_pct": features.sweep_depth_pct,
                "sweep_side": features.sweep_side,
                "close_vs_reclaim_buffer_atr": features.close_vs_reclaim_buffer_atr,
                "wick_vs_min_atr": features.wick_vs_min_atr,
                "sweep_vs_buffer_atr": features.sweep_vs_buffer_atr,
                "funding_8h": features.funding_8h,
                "funding_sma3": features.funding_sma3,
                "funding_sma9": features.funding_sma9,
                "funding_pct_60d": features.funding_pct_60d,
                "oi_value": features.oi_value,
                "oi_zscore_60d": features.oi_zscore_60d,
                "oi_delta_pct": features.oi_delta_pct,
                "cvd_15m": features.cvd_15m,
                "cvd_bullish_divergence": features.cvd_bullish_divergence,
                "cvd_bearish_divergence": features.cvd_bearish_divergence,
                "tfi_60s": features.tfi_60s,
                "force_order_rate_60s": features.force_order_rate_60s,
                "force_order_spike": features.force_order_spike,
                "force_order_decreasing": features.force_order_decreasing,
                "passive_etf_bias_5d": features.passive_etf_bias_5d,
            },
            quality_json={
                key: {
                    "status": value.status,
                    "reason": value.reason,
                    "metadata": value.metadata,
                    "provenance": value.provenance,
                }
                for key, value in sorted(features.quality.items())
            },
        )
        insert_feature_snapshot(
            self.connection,
            feature_snapshot=feature_snapshot,
        )
        self.connection.commit()
        return feature_snapshot.feature_snapshot_id

    def get_market_snapshot(self, snapshot_id: str) -> dict | None:
        self._apply_migrations()
        return fetch_market_snapshot(self.connection, snapshot_id)

    def get_feature_snapshot(self, feature_snapshot_id: str) -> dict | None:
        self._apply_migrations()
        return fetch_feature_snapshot(self.connection, feature_snapshot_id)

    def get_recent_feature_snapshots(self, limit: int) -> list[dict]:
        self._apply_migrations()
        return fetch_recent_feature_snapshots(self.connection, limit)

    def get_decision_outcome_counts(
        self,
        *,
        since_ts: datetime,
        config_hash: str | None = None,
    ) -> dict[str, dict[str, int]]:
        self._apply_migrations()
        return fetch_decision_outcome_counts(
            self.connection,
            since_ts=since_ts,
            config_hash=config_hash,
        )

    def persist_config_snapshot(
        self,
        *,
        config_hash: str,
        strategy_snapshot: dict,
        captured_at: datetime,
    ) -> None:
        self._apply_migrations()
        upsert_config_snapshot(
            self.connection,
            config_hash=config_hash,
            captured_at=captured_at,
            strategy_snapshot=strategy_snapshot,
        )
        self.connection.commit()

    def get_config_snapshot(self, config_hash: str) -> dict | None:
        self._apply_migrations()
        return get_config_snapshot(self.connection, config_hash)

    def refresh_runtime_state(self, now: datetime | None = None) -> BotState:
        ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        self.ensure_initialized()
        self.sync_daily_metrics(ts.date())

        current = self.load()
        assert current is not None
        consecutive_losses = self._compute_consecutive_losses(ts)
        daily_dd_pct = self._compute_daily_dd_pct(ts)
        weekly_dd_pct = self._compute_weekly_dd_pct(ts)

        refreshed = replace(
            current,
            open_positions_count=self.get_open_positions(),
            consecutive_losses=consecutive_losses,
            daily_dd_pct=daily_dd_pct,
            weekly_dd_pct=weekly_dd_pct,
        )
        self.save(refreshed)
        self.sync_daily_metrics(ts.date())
        return refreshed

    def _compute_consecutive_losses(self, now: datetime) -> int:
        outcomes = fetch_recent_closed_trade_outcomes(self.connection, limit=100)
        now_date = _to_utc(now).date()
        losses = 0
        for row in outcomes:
            closed_at_raw = row.get("closed_at")
            if not closed_at_raw:
                continue
            closed_at = closed_at_raw if isinstance(closed_at_raw, datetime) else datetime.fromisoformat(str(closed_at_raw))
            if _to_utc(closed_at).date() != now_date:
                break
            pnl_abs = float(row["pnl_abs"])
            if pnl_abs < 0:
                losses += 1
                continue
            if pnl_abs > 0:
                break
        return losses

    def _compute_daily_dd_pct(self, now: datetime) -> float:
        day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        return self._compute_period_drawdown_pct(day_start, day_end)

    def _compute_weekly_dd_pct(self, now: datetime) -> float:
        weekday = now.weekday()  # Monday=0
        week_start_date = now.date() - timedelta(days=weekday)
        week_start = datetime.combine(week_start_date, datetime.min.time(), tzinfo=timezone.utc)
        week_end = week_start + timedelta(days=7)
        return self._compute_period_drawdown_pct(week_start, week_end)

    def _compute_period_drawdown_pct(self, start_ts: datetime, end_ts: datetime) -> float:
        closed_before = sum_closed_pnl_abs_before(self.connection, start_ts)
        starting_equity = max(self.reference_equity + closed_before, 1e-8)

        peak_equity = starting_equity
        current_equity = starting_equity
        max_drawdown = 0.0

        for row in fetch_closed_trade_pnl_series_between(self.connection, start_ts, end_ts):
            current_equity += float(row["pnl_abs"])
            if current_equity > peak_equity:
                peak_equity = current_equity
            drawdown = (peak_equity - current_equity) / max(peak_equity, 1e-8)
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return min(max(max_drawdown, 0.0), 1.0)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
