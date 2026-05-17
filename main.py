from __future__ import annotations

import argparse
import contextlib
import logging
import os
import signal
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

from orchestrator import BotOrchestrator
from settings import BotMode, load_settings
from storage.db import connect, init_db

LOG = logging.getLogger(__name__)
DEFAULT_RUNTIME_LOCK_PATH = "/tmp/btc-bot-runtime.lock"


def _parse_settings_profile(raw: str) -> str:
    profile = raw.strip().lower()
    if profile not in {"live", "experiment"}:
        raise ValueError(f"Invalid BOT_SETTINGS_PROFILE={raw!r}. Use 'live' or 'experiment'.")
    return profile


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_profile = _parse_settings_profile(os.getenv("BOT_SETTINGS_PROFILE", "live"))
    parser = argparse.ArgumentParser(description="BTC bot entrypoint")
    parser.add_argument("--mode", choices=["PAPER", "LIVE"], help="override BOT_MODE env")
    parser.add_argument(
        "--settings-profile",
        choices=["live", "experiment"],
        default=default_profile,
        help="runtime settings profile (default: BOT_SETTINGS_PROFILE or live)",
    )
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


def runtime_lock_path() -> Path:
    raw_path = os.getenv("BTC_BOT_RUNTIME_LOCK_PATH", DEFAULT_RUNTIME_LOCK_PATH).strip()
    return Path(raw_path or DEFAULT_RUNTIME_LOCK_PATH)


def acquire_runtime_lock(lock_path: Path | None = None) -> TextIO:
    path = lock_path or runtime_lock_path()
    lock_fd: TextIO | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = path.open("a+", encoding="utf-8")
        try:
            import fcntl

            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            import msvcrt

            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
    except (ImportError, OSError):
        if lock_fd is not None:
            lock_fd.close()
        LOG.error(
            "Another bot runtime instance is already running. "
            "Lock file: %s. If no other bot is running, remove the lock file manually.",
            path,
        )
        raise SystemExit(1)
    lock_fd.seek(0)
    lock_fd.truncate()
    lock_fd.write(f"{os.getpid()}\n")
    lock_fd.flush()
    return lock_fd


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
    os.environ["BOT_SETTINGS_PROFILE"] = args.settings_profile

    settings = load_settings(profile=args.settings_profile)
    if args.settings_profile == "experiment" and settings.mode == BotMode.LIVE:
        raise ValueError("The 'experiment' settings profile is PAPER-only. Use mode PAPER.")
    assert settings.storage is not None

    configure_logging(logs_dir=settings.storage.logs_dir, level=args.log_level)
    runtime_lock: TextIO | None = acquire_runtime_lock() if settings.mode in {BotMode.PAPER, BotMode.LIVE} else None
    LOG.info(
        "Starting bot | mode=%s | profile=%s | symbol=%s | config_hash=%s",
        settings.mode.value,
        args.settings_profile,
        settings.strategy.symbol,
        settings.config_hash,
    )
    LOG.info(
        "Runtime settings | settings_profile=%s | mode=%s | confluence_min=%.2f | min_rr=%.2f | "
        "max_trades_per_day=%d | max_open_positions=%d | regime_whitelist[crowded_leverage]=%s",
        args.settings_profile,
        settings.mode.value,
        settings.strategy.confluence_min,
        settings.risk.min_rr,
        settings.risk.max_trades_per_day,
        settings.risk.max_open_positions,
        ",".join(settings.strategy.regime_direction_whitelist.get("crowded_leverage", ())),
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
        if runtime_lock is not None:
            with contextlib.suppress(Exception):
                runtime_lock.close()
        LOG.info("Shutdown complete.")


if __name__ == "__main__":
    main()
