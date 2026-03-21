from __future__ import annotations

from pathlib import Path

from backtest.replay_loader import ReplayLoader


class BacktestRunner:
    def __init__(self, replay_loader: ReplayLoader) -> None:
        self.replay_loader = replay_loader

    def run(self, dataset: Path) -> None:
        raise NotImplementedError
