from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import main


def run() -> None:
    os.environ["BOT_MODE"] = "LIVE"
    os.environ["BOT_SETTINGS_PROFILE"] = "live"
    main(["--settings-profile", "live"])


if __name__ == "__main__":
    run()
