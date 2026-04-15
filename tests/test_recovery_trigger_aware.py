"""Tests for trigger-aware startup recovery logic (SAFE-MODE-AUTO-RECOVERY-MVP).

Verifies that:
- Technical triggers (snapshot_build_failed, health_check_failure_threshold,
  feed_start_failed, exchange_sync_failed) are cleared optimistically on restart.
- Capital-protection triggers (daily_dd, weekly_dd, consecutive_losses) are preserved.
- Unknown / missing triggers are preserved (conservative default).
- set_safe_mode() is ALWAYS called before returning (fixes DB divergence bug).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, call

import pytest

from core.models import BotState
from execution.recovery import NoOpRecoverySyncSource, RecoveryCoordinator

UTC = timezone.utc

_ENTRY_AT = datetime(2026, 4, 13, 14, 0, 0, tzinfo=UTC)
_NOW = datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC)


def _make_state(**kwargs) -> BotState:
    defaults: dict = dict(
        mode="PAPER",
        healthy=True,
        safe_mode=True,
        open_positions_count=0,
        consecutive_losses=0,
        daily_dd_pct=0.0,
        weekly_dd_pct=0.0,
        last_trade_at=None,
        last_error=None,
        safe_mode_entry_at=_ENTRY_AT,
    )
    defaults.update(kwargs)
    return BotState(**defaults)


def _make_state_store(bot_state: BotState) -> MagicMock:
    state_store = MagicMock()
    state_store.ensure_initialized.return_value = bot_state
    state_store.load.return_value = bot_state
    state_store.get_open_positions_snapshot.return_value = []
    state_store.set_safe_mode.return_value = bot_state
    return state_store


def _make_coordinator(state_store: MagicMock) -> RecoveryCoordinator:
    return RecoveryCoordinator(
        symbol="BTCUSDT",
        max_allowed_leverage=8,
        isolated_only=True,
        state_store=state_store,
        audit_logger=MagicMock(),
        exchange_sync=NoOpRecoverySyncSource(),
    )


class TestTechnicalTriggerClearsOnRestart:

    @pytest.mark.parametrize("trigger,detail", [
        ("snapshot_build_failed", "Binance unreachable"),
        ("snapshot_build_failed", "HTTPError('503: Service Unavailable; Retry-After: 60')"),
        ("health_check_failure_threshold", ""),
        ("health_check_failure_threshold", "websocket_dead"),
        ("feed_start_failed", "connection refused"),
        ("exchange_sync_failed", "timeout"),
    ])
    def test_technical_trigger_clears_safe_mode(self, trigger: str, detail: str) -> None:
        last_error = f"{trigger}:{detail}" if detail else trigger
        state = _make_state(safe_mode=True, last_error=last_error)
        state_store = _make_state_store(state)
        coordinator = _make_coordinator(state_store)

        report = coordinator.run_startup_sync()

        assert report.safe_mode is False
        assert report.healthy is True
        assert report.issues == []

        state_store.set_safe_mode.assert_called_once()
        enabled_arg = state_store.set_safe_mode.call_args.args[0]
        assert enabled_arg is False


class TestCapitalTriggerPreservesOnRestart:

    @pytest.mark.parametrize("last_error", [
        "daily_dd>0.1850",
        "weekly_dd>0.0630",
        "consecutive_losses>5",
        "daily_dd>0.1850;consecutive_losses>5",
        "recovery_inconsistency:phantom_position",
        "critical_execution_errors>3",
    ])
    def test_capital_trigger_preserves_safe_mode(self, last_error: str) -> None:
        state = _make_state(safe_mode=True, last_error=last_error)
        state_store = _make_state_store(state)
        coordinator = _make_coordinator(state_store)

        report = coordinator.run_startup_sync()

        assert report.safe_mode is True
        assert report.healthy is False

        state_store.set_safe_mode.assert_called_once()
        enabled_arg = state_store.set_safe_mode.call_args.args[0]
        assert enabled_arg is True

    def test_capital_trigger_preserves_original_reason(self) -> None:
        last_error = "daily_dd>0.1850"
        state = _make_state(safe_mode=True, last_error=last_error)
        state_store = _make_state_store(state)
        coordinator = _make_coordinator(state_store)

        coordinator.run_startup_sync()

        call_kwargs = state_store.set_safe_mode.call_args
        reason_arg = call_kwargs.kwargs.get("reason") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert reason_arg == last_error


class TestUnknownTriggerPreservesOnRestart:

    def test_none_last_error_preserves_safe_mode(self) -> None:
        state = _make_state(safe_mode=True, last_error=None)
        state_store = _make_state_store(state)
        coordinator = _make_coordinator(state_store)

        report = coordinator.run_startup_sync()

        assert report.safe_mode is True
        state_store.set_safe_mode.assert_called_once()
        enabled_arg = state_store.set_safe_mode.call_args.args[0]
        assert enabled_arg is True

    def test_empty_last_error_preserves_safe_mode(self) -> None:
        state = _make_state(safe_mode=True, last_error="")
        state_store = _make_state_store(state)
        coordinator = _make_coordinator(state_store)

        report = coordinator.run_startup_sync()

        assert report.safe_mode is True
        state_store.set_safe_mode.assert_called_once()


class TestDbDivergenceFix:

    def test_technical_trigger_always_writes_db(self) -> None:
        """set_safe_mode(False) must be called — no return without DB write."""
        state = _make_state(safe_mode=True, last_error="snapshot_build_failed:error")
        state_store = _make_state_store(state)
        coordinator = _make_coordinator(state_store)

        coordinator.run_startup_sync()

        state_store.set_safe_mode.assert_called_once()

    def test_capital_trigger_always_writes_db(self) -> None:
        """set_safe_mode(True) must be called — no return without DB write."""
        state = _make_state(safe_mode=True, last_error="daily_dd>0.1850")
        state_store = _make_state_store(state)
        coordinator = _make_coordinator(state_store)

        coordinator.run_startup_sync()

        state_store.set_safe_mode.assert_called_once()


class TestNoSafeModePath:

    def test_no_previous_safe_mode_clears_and_proceeds(self) -> None:
        state = _make_state(safe_mode=False, last_error=None, safe_mode_entry_at=None)
        state_store = _make_state_store(state)
        coordinator = _make_coordinator(state_store)

        report = coordinator.run_startup_sync()

        assert report.safe_mode is False
        assert report.healthy is True
        state_store.set_safe_mode.assert_called_once()
        enabled_arg = state_store.set_safe_mode.call_args.args[0]
        assert enabled_arg is False
