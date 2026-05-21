from __future__ import annotations

from pathlib import Path

import pytest

from settings import (
    BotMode,
    MultiAssetConfig,
    StrategyConfig,
    SymbolStrategyOverride,
    _parse_mode,
    build_signal_regime_direction_whitelist,
    load_settings,
    resolve_symbol_config,
    validate_multi_asset_config,
)


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
    assert settings.multi_asset.enabled is False
    assert settings.multi_asset.enabled_symbols == ("BTCUSDT",)


def test_load_settings_respects_bot_mode_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BOT_MODE", "live")
    settings = load_settings(project_root=tmp_path)
    assert settings.mode is BotMode.LIVE


def test_config_hash_is_stable_for_same_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BOT_MODE", "paper")
    first = load_settings(project_root=tmp_path)
    second = load_settings(project_root=tmp_path)
    assert first.config_hash == second.config_hash


def test_config_hash_changes_when_uptrend_pullback_flag_changes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ALLOW_UPTREND_PULLBACK", raising=False)
    baseline = load_settings(project_root=tmp_path)
    monkeypatch.setenv("ALLOW_UPTREND_PULLBACK", "true")
    enabled = load_settings(project_root=tmp_path)

    assert baseline.strategy.allow_uptrend_pullback is False
    assert enabled.strategy.allow_uptrend_pullback is True
    assert baseline.config_hash != enabled.config_hash


def test_build_signal_regime_direction_whitelist_preserves_defaults_when_flag_disabled() -> None:
    strategy = StrategyConfig(allow_long_in_uptrend=False)

    assert build_signal_regime_direction_whitelist(strategy) == strategy.regime_direction_whitelist


def test_build_signal_regime_direction_whitelist_adds_long_in_uptrend_when_enabled() -> None:
    strategy = StrategyConfig(
        allow_long_in_uptrend=True,
        regime_direction_whitelist={"normal": ("LONG",), "uptrend": ("SHORT",)},
    )

    assert build_signal_regime_direction_whitelist(strategy) == {
        "normal": ("LONG",),
        "uptrend": ("SHORT", "LONG"),
    }


def test_resolve_symbol_config_returns_requested_symbol_with_baseline_params() -> None:
    baseline = StrategyConfig(symbol="BTCUSDT", min_sweep_depth_pct=0.00649)

    resolved = resolve_symbol_config(
        baseline,
        "ethusdt",
        MultiAssetConfig(enabled=True, enabled_symbols=("BTCUSDT", "ETHUSDT")),
    )

    assert resolved.symbol == "ETHUSDT"
    assert resolved.min_sweep_depth_pct == baseline.min_sweep_depth_pct
    assert resolved.confluence_min == baseline.confluence_min


def test_resolve_symbol_config_applies_non_none_override_only() -> None:
    baseline = StrategyConfig(symbol="BTCUSDT", min_sweep_depth_pct=0.00649)
    multi_asset = MultiAssetConfig(
        enabled=True,
        enabled_symbols=("BTCUSDT", "ETHUSDT"),
        symbol_overrides=(SymbolStrategyOverride(symbol="ETHUSDT", min_sweep_depth_pct=0.0),),
    )

    resolved = resolve_symbol_config(baseline, "ETHUSDT", multi_asset)

    assert resolved.symbol == "ETHUSDT"
    assert resolved.min_sweep_depth_pct == 0.0
    assert baseline.min_sweep_depth_pct == 0.00649


def test_validate_multi_asset_config_rejects_disabled_multiple_symbols() -> None:
    with pytest.raises(ValueError, match="enabled must be true"):
        validate_multi_asset_config(MultiAssetConfig(enabled=False, enabled_symbols=("BTCUSDT", "ETHUSDT")))


def test_validate_multi_asset_config_rejects_duplicate_and_unknown_overrides() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        validate_multi_asset_config(
            MultiAssetConfig(
                enabled=True,
                enabled_symbols=("BTCUSDT", "ETHUSDT"),
                symbol_overrides=(
                    SymbolStrategyOverride(symbol="ETHUSDT", min_sweep_depth_pct=0.0075),
                    SymbolStrategyOverride(symbol="ethusdt", min_sweep_depth_pct=0.00649),
                ),
            )
        )

    with pytest.raises(ValueError, match="not listed"):
        validate_multi_asset_config(
            MultiAssetConfig(
                enabled=True,
                enabled_symbols=("BTCUSDT", "ETHUSDT"),
                symbol_overrides=(SymbolStrategyOverride(symbol="SOLUSDT", min_sweep_depth_pct=0.0075),),
            )
        )
