from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from core.models import Position
from data.rest_client import BinanceFuturesRestClient
from monitoring.audit_logger import AuditLogger
from storage.state_store import StateStore


@dataclass(slots=True)
class RecoveryReport:
    healthy: bool
    safe_mode: bool
    issues: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExchangePosition:
    symbol: str
    direction: str
    size: float
    leverage: int
    isolated: bool


@dataclass(slots=True)
class ExchangeOrder:
    symbol: str
    order_id: str
    side: str
    position_side: str


class ExchangeSyncSource(Protocol):
    def fetch_active_positions(self, symbol: str) -> list[ExchangePosition]:
        raise NotImplementedError

    def fetch_open_orders(self, symbol: str) -> list[ExchangeOrder]:
        raise NotImplementedError


class BinanceRecoverySyncSource:
    def __init__(self, rest_client: BinanceFuturesRestClient) -> None:
        self.rest_client = rest_client

    def fetch_active_positions(self, symbol: str) -> list[ExchangePosition]:
        positions: list[ExchangePosition] = []
        for row in self.rest_client.fetch_active_positions(symbol):
            direction = str(row.get("direction") or "").upper()
            if direction not in {"LONG", "SHORT"}:
                continue
            positions.append(
                ExchangePosition(
                    symbol=str(row["symbol"]).upper(),
                    direction=direction,
                    size=float(row["size"]),
                    leverage=int(row["leverage"]),
                    isolated=bool(row["isolated"]),
                )
            )
        return positions

    def fetch_open_orders(self, symbol: str) -> list[ExchangeOrder]:
        orders: list[ExchangeOrder] = []
        for row in self.rest_client.fetch_open_orders(symbol):
            orders.append(
                ExchangeOrder(
                    symbol=str(row["symbol"]).upper(),
                    order_id=str(row["order_id"]),
                    side=str(row["side"]).upper(),
                    position_side=str(row["position_side"]).upper(),
                )
            )
        return orders


class NoOpRecoverySyncSource:
    """Paper-mode startup sync source: no exchange state, deterministic cold start."""

    def fetch_active_positions(self, symbol: str) -> list[ExchangePosition]:
        _ = symbol
        return []

    def fetch_open_orders(self, symbol: str) -> list[ExchangeOrder]:
        _ = symbol
        return []


class RecoveryCoordinator:
    def __init__(
        self,
        *,
        symbol: str,
        max_allowed_leverage: int,
        isolated_only: bool,
        state_store: StateStore,
        audit_logger: AuditLogger,
        exchange_sync: ExchangeSyncSource,
    ) -> None:
        self.symbol = symbol.upper()
        self.max_allowed_leverage = max_allowed_leverage
        self.isolated_only = isolated_only
        self.state_store = state_store
        self.audit_logger = audit_logger
        self.exchange_sync = exchange_sync

    def run_startup_sync(self) -> RecoveryReport:
        now = datetime.now(timezone.utc)
        self.state_store.ensure_initialized()
        last_state = self.state_store.load()
        local_positions = self.state_store.get_open_positions_snapshot()

        if isinstance(self.exchange_sync, NoOpRecoverySyncSource):
            self.state_store.set_safe_mode(False, reason=None, now=now)
            self.audit_logger.log_info(
                "recovery",
                "Paper-mode startup recovery skipped exchange consistency checks.",
                payload={
                    "symbol": self.symbol,
                    "local_positions": len(local_positions),
                    "exchange_positions": 0,
                    "exchange_orders": 0,
                    "previous_safe_mode": bool(last_state.safe_mode) if last_state else False,
                },
            )
            return RecoveryReport(healthy=True, safe_mode=False, issues=[])

        try:
            exchange_positions = self.exchange_sync.fetch_active_positions(self.symbol)
            exchange_orders = self.exchange_sync.fetch_open_orders(self.symbol)
        except Exception as exc:
            issue = f"exchange_sync_failed:{exc}"
            self.state_store.set_safe_mode(True, reason=issue, now=now)
            self.audit_logger.log_error(
                "recovery",
                "Exchange sync failed during startup recovery.",
                payload={"issue": issue},
            )
            return RecoveryReport(healthy=False, safe_mode=True, issues=[issue])

        issues = self._validate_recovery_state(
            local_positions=local_positions,
            exchange_positions=exchange_positions,
            exchange_orders=exchange_orders,
        )
        if issues:
            reason = "recovery_inconsistency:" + ",".join(issues)
            self.state_store.set_safe_mode(True, reason=reason, now=now)
            self.audit_logger.log_error(
                "recovery",
                "Startup recovery found state inconsistency.",
                payload={
                    "issues": issues,
                    "symbol": self.symbol,
                    "local_positions": len(local_positions),
                    "exchange_positions": len(exchange_positions),
                    "exchange_orders": len(exchange_orders),
                    "previous_safe_mode": bool(last_state.safe_mode) if last_state else False,
                },
            )
            return RecoveryReport(healthy=False, safe_mode=True, issues=issues)

        self.state_store.set_safe_mode(False, reason=None, now=now)
        self.audit_logger.log_info(
            "recovery",
            "Startup recovery sync completed without inconsistencies.",
            payload={
                "symbol": self.symbol,
                "local_positions": len(local_positions),
                "exchange_positions": len(exchange_positions),
                "exchange_orders": len(exchange_orders),
                "previous_safe_mode": bool(last_state.safe_mode) if last_state else False,
            },
        )
        return RecoveryReport(healthy=True, safe_mode=False, issues=[])

    def _validate_recovery_state(
        self,
        *,
        local_positions: list[Position],
        exchange_positions: list[ExchangePosition],
        exchange_orders: list[ExchangeOrder],
    ) -> list[str]:
        issues: list[str] = []
        exchange_position_keys: set[str] = set()
        local_position_keys: set[str] = set()

        for position in exchange_positions:
            if position.symbol != self.symbol:
                continue
            if self.isolated_only and not position.isolated:
                issues.append("isolated_mode_mismatch")
            if position.leverage <= 0 or position.leverage > self.max_allowed_leverage:
                issues.append("leverage_mismatch")
            exchange_position_keys.add(self._position_key(position.symbol, position.direction))

        for local in local_positions:
            if local.symbol.upper() != self.symbol:
                continue
            local_position_keys.add(self._position_key(local.symbol, local.direction))

        if exchange_position_keys - local_position_keys:
            issues.append("unknown_position")
        if local_position_keys - exchange_position_keys:
            issues.append("phantom_position")

        orphan_found = False
        has_any_exchange_position = bool(exchange_position_keys)
        for order in exchange_orders:
            if order.symbol != self.symbol:
                continue
            if order.position_side in {"LONG", "SHORT"}:
                key = self._position_key(order.symbol, order.position_side)
                if key not in exchange_position_keys:
                    orphan_found = True
                    break
                continue
            if not has_any_exchange_position:
                orphan_found = True
                break
        if orphan_found:
            issues.append("orphan_orders")

        # Preserve deterministic and concise issue list.
        return sorted(set(issues))

    @staticmethod
    def _position_key(symbol: str, direction: str) -> str:
        return f"{symbol.upper()}:{direction.upper()}"
