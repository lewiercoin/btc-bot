from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import main
from settings import load_settings


def _print_banner() -> None:
    settings = load_settings()
    lines = [
        "=" * 72,
        "BTC BOT PAPER MODE",
        f"mode={settings.mode.value}",
        f"symbol={settings.strategy.symbol}",
        f"config_hash={settings.config_hash}",
        "=" * 72,
    ]
    print("\n".join(lines))


def run() -> None:
    os.environ["BOT_MODE"] = "PAPER"
    _print_banner()
    try:
        main(["--mode", "PAPER"])
    except KeyboardInterrupt:
        print("Paper run interrupted by user. Exiting gracefully.")


if __name__ == "__main__":
    run()
