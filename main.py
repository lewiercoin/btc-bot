from __future__ import annotations

from settings import load_settings
from orchestrator import BotOrchestrator
from storage.db import connect, init_db


def main() -> None:
    settings = load_settings()
    assert settings.storage is not None

    settings.storage.logs_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)

    orchestrator = BotOrchestrator(settings=settings, conn=conn)
    orchestrator.start()


if __name__ == "__main__":
    main()
