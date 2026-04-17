from __future__ import annotations

import argparse
import logging
import os
import signal
from logging.handlers import RotatingFileHandler

from orchestrator import BotOrchestrator
from settings import load_settings
from storage.db import connect, init_db

LOG = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BTC bot entrypoint")
    parser.add_argument("--mode", choices=["PAPER", "LIVE"], help="override BOT_MODE env")
    parser.add_argument("--log-level", default="INFO", help="logging level (e.g. INFO, DEBUG)")
    return parser.parse_args(argv)


def configure_logging(*, logs_dir, level: str = "INFO") -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        logs_dir / "btc_bot.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def install_signal_handlers(orchestrator: BotOrchestrator) -> None:
    def _handle_signal(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        LOG.warning("Received signal %s. Initiating graceful shutdown.", signum)
        orchestrator.stop(reason=f"signal:{signum}")

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.mode:
        os.environ["BOT_MODE"] = args.mode.upper()

    settings = load_settings(profile="live")
    assert settings.storage is not None

    configure_logging(logs_dir=settings.storage.logs_dir, level=args.log_level)
    LOG.info(
        "Starting bot | mode=%s | symbol=%s | config_hash=%s",
        settings.mode.value,
        settings.strategy.symbol,
        settings.config_hash,
    )

    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)

    orchestrator = BotOrchestrator(settings=settings, conn=conn)
    install_signal_handlers(orchestrator)
    try:
        orchestrator.start()
    except KeyboardInterrupt:
        LOG.warning("KeyboardInterrupt received. Requesting shutdown.")
        orchestrator.stop(reason="keyboard_interrupt")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        LOG.info("Shutdown complete.")


if __name__ == "__main__":
    main()
