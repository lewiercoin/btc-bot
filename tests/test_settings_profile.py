from __future__ import annotations

import json
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


def test_load_settings_experiment_profile_applies_multi_asset_runtime_overlay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)
    (tmp_path / "settings.json").write_text(
        json.dumps(
            {
                "schema_version": "v1.0",
                "multi_asset": {
                    "enabled": True,
                    "enabled_symbols": ["btcusdt", "ethusdt", "solusdt"],
                    "symbol_overrides": [
                        {"symbol": "ethusdt", "min_sweep_depth_pct": 0.0075},
                        {"symbol": "solusdt", "min_sweep_depth_pct": 0.0075},
                    ],
                    "max_open_positions_total": 2,
                    "max_open_positions_per_symbol": 1,
                },
            }
        ),
        encoding="utf-8",
    )

    settings = load_settings(project_root=tmp_path, profile="experiment")

    assert settings.multi_asset.enabled is True
    assert settings.multi_asset.enabled_symbols == ("BTCUSDT", "ETHUSDT", "SOLUSDT")
    assert [item.symbol for item in settings.multi_asset.symbol_overrides] == ["ETHUSDT", "SOLUSDT"]
    assert [item.min_sweep_depth_pct for item in settings.multi_asset.symbol_overrides] == [0.0075, 0.0075]


def test_load_settings_experiment_profile_multi_asset_overlay_changes_config_hash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)
    baseline = load_settings(project_root=tmp_path, profile="experiment")
    (tmp_path / "settings.json").write_text(
        json.dumps(
            {
                "schema_version": "v1.0",
                "multi_asset": {
                    "enabled": True,
                    "enabled_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
                },
            }
        ),
        encoding="utf-8",
    )

    changed = load_settings(project_root=tmp_path, profile="experiment")

    assert baseline.multi_asset.enabled is False
    assert changed.multi_asset.enabled is True
    assert baseline.config_hash != changed.config_hash


def test_load_settings_experiment_profile_rejects_invalid_multi_asset_overlay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)
    (tmp_path / "settings.json").write_text(
        json.dumps(
            {
                "schema_version": "v1.0",
                "multi_asset": {
                    "enabled": True,
                    "enabled_symbols": ["BTCUSDT", "ETHUSDT"],
                    "symbol_overrides": [
                        {"symbol": "SOLUSDT", "min_sweep_depth_pct": 0.0075},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not listed"):
        load_settings(project_root=tmp_path, profile="experiment")


def test_load_settings_experiment_profile_rejects_unknown_symbol_override_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("BOT_MODE", raising=False)
    (tmp_path / "settings.json").write_text(
        json.dumps(
            {
                "schema_version": "v1.0",
                "multi_asset": {
                    "enabled": True,
                    "enabled_symbols": ["BTCUSDT", "ETHUSDT"],
                    "symbol_overrides": [
                        {"symbol": "ETHUSDT", "min_sweep_depth_pct": 0.0075, "risk": 0.001},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown multi_asset.symbol_overrides"):
        load_settings(project_root=tmp_path, profile="experiment")


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
