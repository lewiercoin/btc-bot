from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from settings import load_settings
from storage.db import connect, init_db


def main() -> None:
    settings = load_settings()
    assert settings.storage is not None

    settings.storage.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)
    print(f"Initialized database: {settings.storage.db_path}")


if __name__ == "__main__":
    main()
