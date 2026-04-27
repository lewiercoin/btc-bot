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
    assert settings.strategy.allow_uptrend_pullback is False


def test_load_settings_live_profile_applies_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)
    settings = load_settings(project_root=tmp_path, profile="live")

    assert settings.strategy.min_sweep_depth_pct == 0.0001
    assert settings.strategy.confluence_min == 4.5
    assert settings.strategy.allow_long_in_uptrend is True
    assert settings.strategy.allow_uptrend_pullback is False


def test_load_settings_default_profile_is_research(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)
    settings = load_settings(project_root=tmp_path)

    assert settings.strategy.min_sweep_depth_pct == 0.00286
    assert settings.strategy.confluence_min == 4.5
    assert settings.strategy.allow_long_in_uptrend is True
    assert settings.strategy.allow_uptrend_pullback is False


def test_load_settings_research_profile_allows_env_toggle_for_uptrend_pullback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALLOW_UPTREND_PULLBACK", "true")

    settings = load_settings(project_root=tmp_path, profile="research")

    assert settings.strategy.allow_uptrend_pullback is True


def test_load_settings_live_profile_forces_uptrend_pullback_off_even_when_env_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALLOW_UPTREND_PULLBACK", "true")

    settings = load_settings(project_root=tmp_path, profile="live")

    assert settings.strategy.allow_uptrend_pullback is False


def test_load_settings_experiment_profile_applies_runtime_throughput_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)
    settings = load_settings(project_root=tmp_path, profile="experiment")

    assert settings.strategy.min_sweep_depth_pct == 0.0001
    assert settings.strategy.confluence_min == 3.6
    assert settings.strategy.direction_tfi_threshold == 0.05
    assert settings.strategy.direction_tfi_threshold_inverse == -0.03
    assert settings.strategy.tfi_impulse_threshold == 0.10
    assert settings.strategy.regime_direction_whitelist["crowded_leverage"] == ("LONG", "SHORT")
    assert settings.risk.min_rr == 1.6
    assert settings.risk.max_open_positions == 2
    assert settings.risk.max_trades_per_day == 6
    assert settings.risk.cooldown_minutes_after_loss == 30
    assert settings.risk.duplicate_level_tolerance_pct == 0.0004
    assert settings.risk.duplicate_level_window_hours == 24


def test_load_settings_experiment_profile_forces_uptrend_pullback_off_even_when_env_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALLOW_UPTREND_PULLBACK", "true")

    settings = load_settings(project_root=tmp_path, profile="experiment")

    assert settings.strategy.allow_uptrend_pullback is False


def test_load_settings_invalid_profile_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)

    with pytest.raises(ValueError, match="Invalid settings profile"):
        load_settings(project_root=tmp_path, profile="invalid")
