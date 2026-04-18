from __future__ import annotations

from pathlib import Path

import pytest

from settings import load_settings


def test_load_settings_research_profile_uses_dataclass_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)
    settings = load_settings(project_root=tmp_path, profile="research")

    assert settings.strategy.min_sweep_depth_pct == 0.00286
    assert settings.strategy.confluence_min == 4.5
    assert settings.strategy.allow_long_in_uptrend is True


def test_load_settings_live_profile_applies_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)
    settings = load_settings(project_root=tmp_path, profile="live")

    assert settings.strategy.min_sweep_depth_pct == 0.0001
    assert settings.strategy.confluence_min == 4.5
    assert settings.strategy.allow_long_in_uptrend is True


def test_load_settings_default_profile_is_research(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)
    settings = load_settings(project_root=tmp_path)

    assert settings.strategy.min_sweep_depth_pct == 0.00286
    assert settings.strategy.confluence_min == 4.5
    assert settings.strategy.allow_long_in_uptrend is True


def test_load_settings_invalid_profile_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)

    with pytest.raises(ValueError, match="Invalid settings profile"):
        load_settings(project_root=tmp_path, profile="invalid")
