from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class DailyEtfBias:
    day: date
    etf_bias_5d: float | None
    dxy_close: float | None
    notes: str | None = None


class EtfBiasCollector:
    """Passive collector for external context. It does not gate trading in v1.0."""

    def collect_daily(self, day: date) -> DailyEtfBias:
        raise NotImplementedError
