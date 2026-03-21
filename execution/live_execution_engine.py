from __future__ import annotations

from core.models import ExecutableSignal
from execution.execution_engine import ExecutionEngine


class LiveExecutionEngine(ExecutionEngine):
    def execute_signal(self, signal: ExecutableSignal, size: float, leverage: int) -> None:
        raise NotImplementedError("Live execution integration is planned for Phase D.")
