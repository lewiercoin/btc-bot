from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from monitoring.audit_logger import AuditLogger

LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class TelegramConfig:
    enabled: bool
    bot_token: str
    chat_id: str


class TelegramNotifier:
    ALERT_ENTRY = "entry"
    ALERT_EXIT = "exit"
    ALERT_KILL_SWITCH = "kill_switch"
    ALERT_CRITICAL_ERROR = "critical_error"
    ALERT_DAILY_SUMMARY = "daily_summary"

    def __init__(
        self,
        config: TelegramConfig,
        *,
        session: requests.Session | None = None,
        audit_logger: AuditLogger | None = None,
        timeout_seconds: int = 10,
        max_messages_per_second: int = 30,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.audit_logger = audit_logger
        self.timeout_seconds = timeout_seconds
        self._min_interval_seconds = 1.0 / max(max_messages_per_second, 1)
        self._last_sent_monotonic = 0.0

    def send(self, text: str) -> bool:
        if not self.config.enabled:
            return False
        if not self.config.bot_token or not self.config.chat_id:
            self._log_warning(
                "Telegram disabled due to missing bot token/chat id.",
                payload={"enabled": self.config.enabled},
            )
            return False

        self._respect_rate_limit()
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        request_payload = {
            "chat_id": self.config.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        try:
            response = self.session.post(url, json=request_payload, timeout=self.timeout_seconds)
            if response.status_code >= 400:
                self._log_error(
                    "Telegram API HTTP error.",
                    payload={"status_code": response.status_code, "body": response.text[:500]},
                )
                return False
            parsed = response.json()
            if isinstance(parsed, dict) and parsed.get("ok") is False:
                self._log_error("Telegram API returned ok=false.", payload={"response": parsed})
                return False
            return True
        except (requests.RequestException, ValueError) as exc:
            self._log_error("Telegram delivery failed.", payload={"error": str(exc)})
            return False

    def send_alert(self, alert_type: str, payload: dict[str, Any]) -> bool:
        message = self._format_alert(alert_type=alert_type, payload=payload)
        return self.send(message)

    def _format_alert(self, *, alert_type: str, payload: dict[str, Any]) -> str:
        normalized = alert_type.strip().lower()
        if normalized == self.ALERT_ENTRY:
            return (
                "[ENTRY]\n"
                f"symbol={payload.get('symbol', 'BTCUSDT')}\n"
                f"direction={payload.get('direction', '?')}\n"
                f"entry={payload.get('entry_price', '?')}\n"
                f"size={payload.get('size', '?')}"
            )
        if normalized == self.ALERT_EXIT:
            return (
                "[EXIT]\n"
                f"symbol={payload.get('symbol', 'BTCUSDT')}\n"
                f"direction={payload.get('direction', '?')}\n"
                f"exit={payload.get('exit_price', '?')}\n"
                f"pnl={payload.get('pnl_abs', '?')}"
            )
        if normalized == self.ALERT_KILL_SWITCH:
            return (
                "[KILL-SWITCH]\n"
                f"reason={payload.get('reason', 'unspecified')}\n"
                f"safe_mode={payload.get('safe_mode', True)}"
            )
        if normalized == self.ALERT_CRITICAL_ERROR:
            return (
                "[CRITICAL ERROR]\n"
                f"component={payload.get('component', '?')}\n"
                f"message={payload.get('message', '?')}"
            )
        if normalized == self.ALERT_DAILY_SUMMARY:
            return (
                "[DAILY SUMMARY]\n"
                f"date={payload.get('date', '?')}\n"
                f"trades={payload.get('trades_count', 0)}\n"
                f"pnl_abs={payload.get('pnl_abs', 0.0)}\n"
                f"wins={payload.get('wins', 0)} losses={payload.get('losses', 0)}"
            )

        return f"[ALERT:{alert_type}]\n{payload}"

    def _respect_rate_limit(self) -> None:
        now = time.monotonic()
        delta = now - self._last_sent_monotonic
        if delta < self._min_interval_seconds:
            time.sleep(self._min_interval_seconds - delta)
        self._last_sent_monotonic = time.monotonic()

    def _log_warning(self, message: str, payload: dict[str, Any]) -> None:
        if self.audit_logger:
            self.audit_logger.log_warning("telegram", message, payload)
            return
        LOG.warning("%s payload=%s", message, payload)

    def _log_error(self, message: str, payload: dict[str, Any]) -> None:
        if self.audit_logger:
            self.audit_logger.log_error("telegram", message, payload)
            return
        LOG.error("%s payload=%s", message, payload)
