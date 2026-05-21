from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.models import ExecutableSignal
from execution.paper_execution_engine import PaperExecutionEngine


class RecordingPersister:
    def __init__(self) -> None:
        self.positions = 0
        self.executions = 0
        self.commits = 0

    def insert_position(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.positions += 1

    def insert_execution_fill_event(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.executions += 1

    def commit(self) -> None:
        self.commits += 1


def _signal() -> ExecutableSignal:
    return ExecutableSignal(
        signal_id="sig-symbol-gate",
        timestamp=datetime(2026, 5, 21, 10, 30, tzinfo=timezone.utc),
        direction="LONG",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
        rr_ratio=2.0,
        approved_by_governance=True,
        governance_notes=["approved"],
    )


def test_paper_execution_defaults_allowed_symbols_to_engine_symbol() -> None:
    persister = RecordingPersister()
    engine = PaperExecutionEngine(position_persister=persister, symbol="BTCUSDT")

    engine.execute_signal(_signal(), size=1.0, leverage=3, snapshot_price=100.0)

    assert persister.positions == 1
    assert persister.executions == 1
    assert persister.commits == 1


def test_paper_execution_rejects_symbol_before_persister_writes() -> None:
    persister = RecordingPersister()
    engine = PaperExecutionEngine(
        position_persister=persister,
        symbol="ETHUSDT",
        allowed_symbols=("BTCUSDT",),
    )

    with pytest.raises(ValueError, match="paper_execution_symbol_not_allowed"):
        engine.execute_signal(_signal(), size=1.0, leverage=3, snapshot_price=100.0)

    assert persister.positions == 0
    assert persister.executions == 0
    assert persister.commits == 0
