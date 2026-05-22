from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from monitoring.telegram_notifier import TelegramConfig, TelegramNotifier
from settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Send one Telegram test alert using runtime settings.")
    parser.add_argument(
        "--profile",
        default=os.getenv("BOT_SETTINGS_PROFILE", "experiment"),
        choices=("live", "experiment"),
        help="Settings profile to load.",
    )
    parser.add_argument(
        "--message",
        default="BTC bot Telegram test alert.",
        help="Plain text message to send.",
    )
    args = parser.parse_args()

    settings = load_settings(profile=args.profile)
    notifier = TelegramNotifier(
        TelegramConfig(
            enabled=settings.alerts.telegram_enabled,
            bot_token=settings.alerts.telegram_bot_token,
            chat_id=settings.alerts.telegram_chat_id,
        )
    )
    if not settings.alerts.telegram_enabled:
        print("telegram_enabled=false")
        return 2
    if not settings.alerts.telegram_bot_token or not settings.alerts.telegram_chat_id:
        print("telegram credentials missing")
        return 2

    sent = notifier.send(args.message)
    print("sent=true" if sent else "sent=false")
    return 0 if sent else 1


if __name__ == "__main__":
    sys.exit(main())
