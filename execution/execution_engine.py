from __future__ import annotations

from abc import ABC, abstractmethod

from core.models import ExecutableSignal


class ExecutionEngine(ABC):
    """Execution layer only. No strategic filtering and no risk gating here."""

    @abstractmethod
    def execute_signal(self, signal: ExecutableSignal, size: float, leverage: int) -> None:
        raise NotImplementedError
