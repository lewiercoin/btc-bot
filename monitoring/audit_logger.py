from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


class AuditLogger:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def log_info(self, component: str, message: str, payload: dict[str, Any] | None = None) -> None:
        self._write_alert("audit", "info", component, message, payload or {})

    def log_error(self, component: str, message: str, payload: dict[str, Any] | None = None) -> None:
        self._write_alert("error", "critical", component, message, payload or {})

    def _write_alert(self, event_type: str, severity: str, component: str, message: str, payload: dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT INTO alerts_errors (timestamp, type, severity, component, message, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                event_type,
                severity,
                component,
                message,
                json.dumps(payload),
            ),
        )
        self.connection.commit()
