from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RecoveryReport:
    healthy: bool
    safe_mode: bool
    issues: list[str] = field(default_factory=list)


class RecoveryCoordinator:
    def run_startup_sync(self) -> RecoveryReport:
        raise NotImplementedError
