from __future__ import annotations

from pathlib import Path

from research_lab.settings_adapter import build_candidate_settings
from settings import load_settings


def test_build_candidate_settings_is_immutable_and_preserves_non_strategy_sections(tmp_path: Path) -> None:
    base = load_settings(project_root=tmp_path)
    candidate = build_candidate_settings(base, {"tp1_atr_mult": 3.0})

    assert candidate.strategy.tp1_atr_mult == 3.0
    assert base.strategy.tp1_atr_mult == 1.9
    assert candidate.execution == base.execution

