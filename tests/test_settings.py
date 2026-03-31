from __future__ import annotations

from pathlib import Path

import pytest

from settings import BotMode, _parse_mode, load_settings


def test_parse_mode_accepts_case_insensitive_values() -> None:
    assert _parse_mode("paper") is BotMode.PAPER
    assert _parse_mode("LIVE") is BotMode.LIVE


def test_parse_mode_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        _parse_mode("sandbox")


def test_load_settings_uses_defaults_and_project_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)
    settings = load_settings(project_root=tmp_path)

    assert settings.mode is BotMode.PAPER
    assert settings.storage is not None
    assert settings.storage.project_root == tmp_path
    assert settings.storage.db_path == tmp_path / "storage" / "btc_bot.db"
    assert settings.storage.schema_path == tmp_path / "storage" / "schema.sql"
    assert settings.storage.logs_dir == tmp_path / "logs"


def test_load_settings_respects_bot_mode_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BOT_MODE", "live")
    settings = load_settings(project_root=tmp_path)
    assert settings.mode is BotMode.LIVE


def test_config_hash_is_stable_for_same_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BOT_MODE", "paper")
    first = load_settings(project_root=tmp_path)
    second = load_settings(project_root=tmp_path)
    assert first.config_hash == second.config_hash
