from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from backtest.backtest_runner import BacktestConfig, BacktestRunner
from core.funding import compute_funding_paid
from core.models import ExecutableSignal, Features, MarketSnapshot, RegimeState, SignalCandidate, SettlementMetrics
from core.risk_engine import RiskConfig, RiskEngine
from orchestrator import BotOrchestrator
from settings import BotMode, load_settings
from storage.db import init_db
from storage.repositories import insert_position, insert_trade_log_open, save_executable_signal
from storage.state_store import StateStore


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "storage" / "schema.sql"


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, _schema_path())
    return conn


def _make_features(ts: datetime) -> Features:
    return Features(
        schema_version="v1.0",
        config_hash="hash-test",
        timestamp=ts,
        atr_15m=10.0,
        atr_4h=50.0,
        atr_4h_norm=0.01,
        ema50_4h=110.0,
        ema200_4h=100.0,
        funding_8h=0.0001,
        funding_sma3=0.0001,
        funding_sma9=0.0001,
        funding_pct_60d=50.0,
        oi_value=1.0,
        oi_zscore_60d=0.0,
        oi_delta_pct=0.0,
        cvd_15m=0.0,
        cvd_bullish_divergence=True,
        cvd_bearish_divergence=False,
        tfi_60s=0.2,
        force_order_rate_60s=0.0,
        force_order_spike=False,
        force_order_decreasing=False,
    )


def _make_candidate(ts: datetime) -> SignalCandidate:
    return SignalCandidate(
        signal_id="sig-test",
        timestamp=ts,
        direction="LONG",
        setup_type="funding-fee-test",
        entry_reference=100.0,
        invalidation_level=95.0,
        tp_reference_1=110.0,
        tp_reference_2=120.0,
        confluence_score=5.0,
        regime=RegimeState.NORMAL,
        reasons=["funding-window-crossed"],
        features_json={"atr_15m": 10.0},
    )


def _make_executable(ts: datetime) -> ExecutableSignal:
    return ExecutableSignal(
        signal_id="sig-test",
        timestamp=ts,
        direction="LONG",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
        rr_ratio=2.0,
        approved_by_governance=True,
        governance_notes=["approved"],
    )


def _insert_candidate_row(conn: sqlite3.Connection, candidate: SignalCandidate) -> None:
    conn.execute(
        """
        INSERT INTO signal_candidates (
            signal_id, timestamp, direction, setup_type, confluence_score, regime,
            reasons_json, features_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate.signal_id,
            candidate.timestamp.isoformat(),
            candidate.direction,
            candidate.setup_type,
            candidate.confluence_score,
            candidate.regime.value,
            '["funding-window-crossed"]',
            '{"atr_15m": 10.0}',
            "v1.0",
            "hash-test",
        ),
    )


def _insert_funding_row(conn: sqlite3.Connection, *, funding_time: datetime, funding_rate: float = 0.0001) -> None:
    conn.execute(
        "INSERT INTO funding (symbol, funding_time, funding_rate) VALUES (?, ?, ?)",
        ("BTCUSDT", funding_time.isoformat(), funding_rate),
    )


class _SnapshotLoader:
    def __init__(self, snapshots: list[MarketSnapshot]) -> None:
        self._snapshots = snapshots

    def iter_snapshots(self, **kwargs):
        yield from self._snapshots


class _NoOpAuditLogger:
    def log_info(self, *args, **kwargs) -> None:
        return None

    def log_warning(self, *args, **kwargs) -> None:
        return None

    def log_error(self, *args, **kwargs) -> None:
        return None

    def log_trade(self, *args, **kwargs) -> None:
        return None


class _NoOpHealthMonitor:
    def check(self):
        return None


class _NoOpTelegram:
    def send_alert(self, *args, **kwargs) -> None:
        return None


def _snapshot(ts: datetime, *, price: float) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=ts,
        price=price,
        bid=price - 0.5,
        ask=price + 0.5,
        candles_15m=[
            {
                "open_time": ts,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": 1.0,
            }
        ],
    )


def test_compute_funding_paid_is_directional() -> None:
    opened_at = datetime(2026, 4, 25, 0, 15, tzinfo=timezone.utc)
    closed_at = datetime(2026, 4, 25, 16, 15, tzinfo=timezone.utc)
    funding_samples = [
        {"funding_time": datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc), "funding_rate": 0.0001},
        {"funding_time": datetime(2026, 4, 25, 16, 0, tzinfo=timezone.utc), "funding_rate": -0.0002},
    ]

    long_funding = compute_funding_paid(
        direction="LONG",
        notional=10_000.0,
        opened_at=opened_at,
        closed_at=closed_at,
        funding_samples=funding_samples,
    )
    short_funding = compute_funding_paid(
        direction="SHORT",
        notional=10_000.0,
        opened_at=opened_at,
        closed_at=closed_at,
        funding_samples=funding_samples,
    )

    assert long_funding == -1.0
    assert short_funding == 1.0


def test_state_store_migrates_trade_log_with_funding_paid_default() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE trade_log (
            trade_id TEXT PRIMARY KEY,
            signal_id TEXT NOT NULL,
            position_id TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            direction TEXT NOT NULL,
            regime TEXT NOT NULL,
            confluence_score REAL NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            size REAL NOT NULL,
            fees_total REAL NOT NULL DEFAULT 0,
            slippage_bps_avg REAL NOT NULL DEFAULT 0,
            pnl_abs REAL NOT NULL DEFAULT 0,
            pnl_r REAL NOT NULL DEFAULT 0,
            mae REAL NOT NULL DEFAULT 0,
            mfe REAL NOT NULL DEFAULT 0,
            exit_reason TEXT,
            features_at_entry_json TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            config_hash TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE bot_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            timestamp TEXT NOT NULL,
            mode TEXT NOT NULL,
            healthy INTEGER NOT NULL,
            safe_mode INTEGER NOT NULL,
            open_positions_count INTEGER NOT NULL DEFAULT 0,
            consecutive_losses INTEGER NOT NULL DEFAULT 0,
            daily_dd_pct REAL NOT NULL DEFAULT 0,
            weekly_dd_pct REAL NOT NULL DEFAULT 0,
            last_trade_at TEXT,
            last_error TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO trade_log (
            trade_id, signal_id, position_id, opened_at, closed_at, direction, regime,
            confluence_score, entry_price, exit_price, size, fees_total, slippage_bps_avg,
            pnl_abs, pnl_r, mae, mfe, exit_reason, features_at_entry_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "legacy-trade",
            "sig-legacy",
            "pos-legacy",
            datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc).isoformat(),
            None,
            "LONG",
            "normal",
            4.0,
            100.0,
            None,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            None,
            "{}",
            "v1.0",
            "hash-test",
        ),
    )
    conn.commit()

    store = StateStore(conn, mode="PAPER")
    store.ensure_initialized()

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(trade_log)").fetchall()}
    row = conn.execute("SELECT funding_paid FROM trade_log WHERE trade_id = ?", ("legacy-trade",)).fetchone()

    assert "funding_paid" in columns
    assert row is not None
    assert float(row["funding_paid"]) == 0.0


def test_backtest_runner_records_funding_paid_for_multi_period_trade(tmp_path) -> None:
    conn = _make_conn()
    try:
        open_ts = datetime(2026, 4, 25, 0, 15, tzinfo=timezone.utc)
        close_ts = datetime(2026, 4, 25, 8, 15, tzinfo=timezone.utc)
        _insert_funding_row(conn, funding_time=datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc))
        conn.commit()

        snapshots = [
            _snapshot(open_ts, price=100.0),
            _snapshot(close_ts, price=105.0),
        ]
        runner = BacktestRunner(
            conn,
            settings=load_settings(project_root=tmp_path, profile="research"),
            replay_loader=_SnapshotLoader(snapshots),
        )
        candidate = _make_candidate(open_ts)
        executable = _make_executable(open_ts)
        features = _make_features(open_ts)
        signal_calls = {"count": 0}

        def generate_signal(*args, **kwargs):
            if signal_calls["count"] == 0:
                signal_calls["count"] += 1
                return candidate
            return None

        governance = SimpleNamespace(
            evaluate=lambda current_candidate: SimpleNamespace(approved=True),
            to_executable=lambda current_candidate, current_decision: replace(executable, signal_id=current_candidate.signal_id),
        )
        runner._build_engines = lambda: (  # type: ignore[method-assign]
            SimpleNamespace(compute=lambda **kwargs: replace(features, timestamp=kwargs["snapshot"].timestamp)),
            SimpleNamespace(classify=lambda current_features: RegimeState.NORMAL),
            SimpleNamespace(generate=generate_signal),
            governance,
            RiskEngine(RiskConfig(min_rr=1.0, max_hold_hours=0)),
        )

        result = runner.run(
            BacktestConfig(
                start_date=open_ts,
                end_date=close_ts,
                symbol="BTCUSDT",
                slippage_bps_limit=0.0,
                slippage_bps_market=0.0,
                fee_rate_maker=0.0,
                fee_rate_taker=0.0,
            )
        )
        row = conn.execute(
            "SELECT funding_paid, pnl_abs FROM trade_log WHERE trade_id = ?",
            (result.trades[0].trade_id,),
        ).fetchone()
    finally:
        conn.close()

    assert len(result.trades) == 1
    assert result.trades[0].funding_paid > 0.0
    assert row is not None
    assert float(row["funding_paid"]) == result.trades[0].funding_paid
    assert float(row["pnl_abs"]) == result.trades[0].pnl_abs


def test_paper_runtime_settlement_deducts_funding_from_pnl(tmp_path) -> None:
    conn = _make_conn()
    try:
        opened_at = datetime(2026, 4, 25, 0, 15, tzinfo=timezone.utc)
        closed_at = datetime(2026, 4, 25, 8, 15, tzinfo=timezone.utc)
        candidate = _make_candidate(opened_at)
        executable = _make_executable(opened_at)
        _insert_candidate_row(conn, candidate)
        save_executable_signal(conn, executable)
        insert_position(
            conn,
            position_id="paper-pos",
            signal_id=executable.signal_id,
            symbol="BTCUSDT",
            direction="LONG",
            status="OPEN",
            entry_price=100.0,
            size=2.0,
            leverage=2,
            stop_loss=95.0,
            take_profit_1=110.0,
            take_profit_2=120.0,
            opened_at=opened_at,
            updated_at=opened_at,
        )
        insert_trade_log_open(
            conn,
            trade_id="paper-trade",
            signal_id=executable.signal_id,
            position_id="paper-pos",
            opened_at=opened_at,
            direction="LONG",
            regime="normal",
            confluence_score=5.0,
            entry_price=100.0,
            size=2.0,
            features_at_entry_json={"atr_15m": 10.0},
            schema_version="v1.0",
            config_hash="hash-test",
        )
        _insert_funding_row(conn, funding_time=datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc))
        conn.commit()

        settings = load_settings(project_root=tmp_path, profile="research")
        settings = replace(settings, mode=BotMode.PAPER)
        bundle = SimpleNamespace(
            market_data=SimpleNamespace(websocket_client=None, rest_client=None),
            feature_engine=None,
            regime_engine=None,
            signal_engine=None,
            governance=None,
            risk_engine=RiskEngine(RiskConfig(min_rr=1.0, max_hold_hours=0)),
            execution_engine=None,
            audit_logger=_NoOpAuditLogger(),
        )
        orchestrator = BotOrchestrator(
            settings=settings,
            conn=conn,
            bundle=bundle,
            health_monitor=_NoOpHealthMonitor(),
            telegram_notifier=_NoOpTelegram(),
        )

        closed_events = orchestrator._process_trade_lifecycle(_snapshot(closed_at, price=105.0))
        row = conn.execute(
            "SELECT funding_paid, pnl_abs, exit_price, closed_at FROM trade_log WHERE trade_id = ?",
            ("paper-trade",),
        ).fetchone()
    finally:
        conn.close()

    assert len(closed_events) == 1
    assert row is not None
    assert float(row["funding_paid"]) > 0.0
    assert float(row["pnl_abs"]) == closed_events[0]["pnl_abs"]
    assert float(row["pnl_abs"]) < 10.0
    assert float(row["exit_price"]) == 105.0
    assert row["closed_at"] == closed_at.isoformat()


def test_state_store_settle_trade_close_persists_funding_paid() -> None:
    conn = _make_conn()
    try:
        opened_at = datetime(2026, 4, 25, 0, 15, tzinfo=timezone.utc)
        closed_at = datetime(2026, 4, 25, 8, 15, tzinfo=timezone.utc)
        candidate = _make_candidate(opened_at)
        executable = _make_executable(opened_at)
        _insert_candidate_row(conn, candidate)
        save_executable_signal(conn, executable)
        insert_position(
            conn,
            position_id="pos-store",
            signal_id=executable.signal_id,
            symbol="BTCUSDT",
            direction="LONG",
            status="OPEN",
            entry_price=100.0,
            size=1.0,
            leverage=2,
            stop_loss=95.0,
            take_profit_1=110.0,
            take_profit_2=120.0,
            opened_at=opened_at,
            updated_at=opened_at,
        )
        insert_trade_log_open(
            conn,
            trade_id="trade-store",
            signal_id=executable.signal_id,
            position_id="pos-store",
            opened_at=opened_at,
            direction="LONG",
            regime="normal",
            confluence_score=5.0,
            entry_price=100.0,
            size=1.0,
            features_at_entry_json={},
            schema_version="v1.0",
            config_hash="hash-test",
        )
        store = StateStore(conn, mode="PAPER")
        store.settle_trade_close(
            position_id="pos-store",
            closed_at=closed_at,
            settlement=SettlementMetrics(
                exit_price=105.0,
                pnl_abs=4.99,
                pnl_r=0.998,
                mae=0.0,
                mfe=5.0,
                exit_reason="TIMEOUT",
                funding_paid=0.01,
            ),
        )
        row = conn.execute(
            "SELECT funding_paid, pnl_abs FROM trade_log WHERE trade_id = ?",
            ("trade-store",),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert float(row["funding_paid"]) == 0.01
    assert float(row["pnl_abs"]) == 4.99
