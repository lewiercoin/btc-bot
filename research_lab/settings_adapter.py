from __future__ import annotations

import dataclasses
from typing import Any

from settings import AppSettings, RiskConfig, StrategyConfig

from research_lab.param_registry import split_param_targets


def build_candidate_settings(
    base_settings: AppSettings,
    overrides: dict[str, Any],
) -> AppSettings:
    """Build immutable AppSettings from base + flat override dict.

    Splits overrides into strategy vs risk fields using
    param_registry.split_to_strategy_risk(). Uses dataclasses.replace() and never
    mutates frozen instances. Preserves all non-strategy/risk sections.
    """

    strategy_overrides, risk_overrides, _ = split_param_targets(overrides)

    strategy_candidate: StrategyConfig = dataclasses.replace(base_settings.strategy, **strategy_overrides)
    risk_candidate: RiskConfig = dataclasses.replace(base_settings.risk, **risk_overrides)
    return dataclasses.replace(base_settings, strategy=strategy_candidate, risk=risk_candidate)


def extract_research_params(overrides: dict[str, Any]) -> dict[str, Any]:
    _, _, research_overrides = split_param_targets(overrides)
    return research_overrides


def diff_settings(
    base: AppSettings,
    candidate: AppSettings,
) -> dict[str, dict[str, Any]]:
    """Returns changed strategy/risk params only as from/to pairs."""

    diff: dict[str, dict[str, Any]] = {}

    for field in dataclasses.fields(StrategyConfig):
        name = field.name
        base_value = getattr(base.strategy, name)
        candidate_value = getattr(candidate.strategy, name)
        if base_value != candidate_value:
            diff[name] = {"from": base_value, "to": candidate_value}

    for field in dataclasses.fields(RiskConfig):
        name = field.name
        base_value = getattr(base.risk, name)
        candidate_value = getattr(candidate.risk, name)
        if base_value != candidate_value:
            diff[name] = {"from": base_value, "to": candidate_value}

    return diff

