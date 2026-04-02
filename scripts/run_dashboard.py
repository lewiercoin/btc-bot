from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn


def run() -> None:
    uvicorn.run("dashboard.server:app", host="127.0.0.1", port=8080)


if __name__ == "__main__":
    run()

