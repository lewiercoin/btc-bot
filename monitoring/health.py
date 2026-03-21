from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HealthStatus:
    websocket_alive: bool
    db_writable: bool
    exchange_reachable: bool

    @property
    def healthy(self) -> bool:
        return self.websocket_alive and self.db_writable and self.exchange_reachable


class HealthMonitor:
    def check(self) -> HealthStatus:
        raise NotImplementedError
