"""
Test config_hash reproducibility (REMEDIATION-B1).

Verify that config_hash includes full runtime surface:
- All config fields (strategy, risk, execution, data_quality, exchange, proxy, alerts, storage)
- Python version from .python-version
- Dependency hash from requirements.lock
- Settings profile from BOT_SETTINGS_PROFILE env var

Rationale: Post-incident forensics requires exact runtime state reproduction.
"""
import os
import tempfile
from pathlib import Path

from settings import AppSettings, BotMode, StorageConfig


def test_config_hash_includes_python_version(monkeypatch):
    """Config hash changes when Python version changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        python_version_file = root / ".python-version"
        python_version_file.write_text("3.12.3")

        storage = StorageConfig(
            project_root=root,
            db_path=root / "btc_bot.db",
            schema_path=root / "schema.sql",
            logs_dir=root / "logs",
        )
        settings1 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage)
        hash1 = settings1.config_hash

        # Change Python version
        python_version_file.write_text("3.13.0")
        settings2 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage)
        hash2 = settings2.config_hash

        assert hash1 != hash2, "Config hash must change when Python version changes"


def test_config_hash_includes_dependency_hash():
    """Config hash changes when requirements.lock changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        lockfile = root / "requirements.lock"
        lockfile.write_text("requests==2.32.0 --hash=sha256:abc123")

        storage = StorageConfig(
            project_root=root,
            db_path=root / "btc_bot.db",
            schema_path=root / "schema.sql",
            logs_dir=root / "logs",
        )
        settings1 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage)
        hash1 = settings1.config_hash

        # Change dependencies
        lockfile.write_text("requests==2.33.0 --hash=sha256:def456")
        settings2 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage)
        hash2 = settings2.config_hash

        assert hash1 != hash2, "Config hash must change when dependencies change"


def test_config_hash_includes_settings_profile(monkeypatch):
    """Config hash changes when BOT_SETTINGS_PROFILE changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        storage = StorageConfig(
            project_root=root,
            db_path=root / "btc_bot.db",
            schema_path=root / "schema.sql",
            logs_dir=root / "logs",
        )

        monkeypatch.setenv("BOT_SETTINGS_PROFILE", "experiment")
        settings1 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage)
        hash1 = settings1.config_hash

        monkeypatch.setenv("BOT_SETTINGS_PROFILE", "live")
        settings2 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage)
        hash2 = settings2.config_hash

        assert hash1 != hash2, "Config hash must change when BOT_SETTINGS_PROFILE changes"


def test_config_hash_includes_exchange_config():
    """Config hash changes when exchange config changes."""
    from settings import ExchangeConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        storage = StorageConfig(
            project_root=root,
            db_path=root / "btc_bot.db",
            schema_path=root / "schema.sql",
            logs_dir=root / "logs",
        )

        exchange1 = ExchangeConfig(futures_rest_base_url="https://fapi.binance.com")
        settings1 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage, exchange=exchange1)
        hash1 = settings1.config_hash

        exchange2 = ExchangeConfig(futures_rest_base_url="https://testnet.binancefuture.com")
        settings2 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage, exchange=exchange2)
        hash2 = settings2.config_hash

        assert hash1 != hash2, "Config hash must change when exchange URL changes"


def test_config_hash_includes_storage_paths():
    """Config hash changes when storage paths change."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        storage1 = StorageConfig(
            project_root=root,
            db_path=root / "btc_bot.db",
            schema_path=root / "schema.sql",
            logs_dir=root / "logs",
        )
        settings1 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage1)
        hash1 = settings1.config_hash

        storage2 = StorageConfig(
            project_root=root,
            db_path=root / "custom_db.db",  # Different path
            schema_path=root / "schema.sql",
            logs_dir=root / "logs",
        )
        settings2 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage2)
        hash2 = settings2.config_hash

        assert hash1 != hash2, "Config hash must change when storage paths change"


def test_config_hash_deterministic():
    """Config hash is deterministic for identical settings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        python_version_file = root / ".python-version"
        python_version_file.write_text("3.12.3")
        lockfile = root / "requirements.lock"
        lockfile.write_text("requests==2.32.0")

        storage = StorageConfig(
            project_root=root,
            db_path=root / "btc_bot.db",
            schema_path=root / "schema.sql",
            logs_dir=root / "logs",
        )

        settings1 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage)
        settings2 = AppSettings(schema_version="v1.0", mode=BotMode.PAPER, storage=storage)

        assert settings1.config_hash == settings2.config_hash, "Config hash must be deterministic"
