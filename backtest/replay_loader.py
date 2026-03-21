from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ReplayBatch:
    records: list[dict]


class ReplayLoader:
    def load(self, source: Path) -> ReplayBatch:
        raise NotImplementedError
