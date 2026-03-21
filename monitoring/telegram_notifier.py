from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TelegramConfig:
    enabled: bool
    bot_token: str
    chat_id: str


class TelegramNotifier:
    def __init__(self, config: TelegramConfig) -> None:
        self.config = config

    def send(self, text: str) -> None:
        if not self.config.enabled:
            return
        raise NotImplementedError("Telegram delivery is planned for Phase E.")
