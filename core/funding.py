from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from core.models import Direction


@dataclass(slots=True, frozen=True)
class FundingRateSample:
    funding_time: datetime
    funding_rate: float


def compute_funding_paid(
    *,
    direction: Direction,
    notional: float,
    opened_at: datetime,
    closed_at: datetime,
    funding_samples: Iterable[FundingRateSample | dict[str, Any]],
) -> float:
    if notional <= 0:
        return 0.0

    opened_at_utc = _to_utc(opened_at)
    closed_at_utc = _to_utc(closed_at)
    if closed_at_utc <= opened_at_utc:
        return 0.0

    directional_multiplier = 1.0 if direction == "LONG" else -1.0
    total_rate = 0.0
    for sample in normalize_funding_samples(funding_samples):
        if opened_at_utc < sample.funding_time <= closed_at_utc:
            total_rate += sample.funding_rate
    return float(notional) * total_rate * directional_multiplier


def normalize_funding_samples(
    funding_samples: Iterable[FundingRateSample | dict[str, Any]],
) -> list[FundingRateSample]:
    normalized: list[FundingRateSample] = []
    for sample in funding_samples:
        if isinstance(sample, FundingRateSample):
            normalized.append(
                FundingRateSample(
                    funding_time=_to_utc(sample.funding_time),
                    funding_rate=float(sample.funding_rate),
                )
            )
            continue

        funding_time = sample.get("funding_time")
        if funding_time is None:
            continue
        normalized.append(
            FundingRateSample(
                funding_time=_to_utc(funding_time),
                funding_rate=float(sample.get("funding_rate", 0.0)),
            )
        )
    normalized.sort(key=lambda item: item.funding_time)
    return normalized


def _to_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        parsed = value
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
