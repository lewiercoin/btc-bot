"""OANDA_SESSION_EDGE_RECONNAISSANCE_V1.

Research-only structure inventory for OANDA-native session behavior. This is
not a profitability diagnostic and does not touch the live trading path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EUR_DATA = PROJECT_ROOT / "research_lab" / "analysis_output" / "oanda_eur_usd_m15_candles_20240101_20260529.json"
DEFAULT_XAU_DATA = PROJECT_ROOT / "research_lab" / "analysis_output" / "oanda_xau_usd_m15_candles_20240101_20260529.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "research" / "OANDA_SESSION_EDGE_RECONNAISSANCE_V1_REPORT.md"
DEFAULT_JSON = PROJECT_ROOT / "research_lab" / "reports" / "oanda_session_edge_reconnaissance_v1.json"

FOLD_WINDOWS = (
    ("fold_1_2024H1", datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 7, 1, tzinfo=timezone.utc)),
    ("fold_2_2024H2", datetime(2024, 7, 1, tzinfo=timezone.utc), datetime(2025, 1, 1, tzinfo=timezone.utc)),
    ("fold_3_2025", datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ("fold_4_2026", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc)),
)

SESSION_DEFINITIONS = {
    "asia_range": ("00:00", "07:00"),
    "london_open": ("07:00", "09:00"),
    "london_continuation": ("09:00", "12:00"),
    "new_york_overlap": ("13:00", "16:00"),
    "rollover": ("21:00", "23:00"),
}

FOLLOW_THROUGH_BARS = 8
FALSE_BREAKOUT_BARS = 4
ATR_MULTIPLE = 0.5
MFE_GATE = 0.70
PREFERRED_MFE_GATE = 0.60
MIN_TOTAL_EVENTS = 200
MIN_EVENTS_PER_YEAR = 100
MAX_FALSE_BREAKOUT_RATE = 0.50


@dataclass(frozen=True, slots=True)
class Candle:
    index: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class SessionRange:
    session_date: str
    start_index: int
    end_index: int
    high: float
    low: float
    open: float
    close: float
    range_pct: float
    range_atr: float
    direction: str


@dataclass(frozen=True, slots=True)
class StructureEvent:
    candidate: str
    instrument: str
    session_date: str
    direction: str
    range_known_bar: int
    detection_bar: int
    state_known_bar: int
    entry_candidate_bar: int
    return_start_bar: int
    entry_time_utc: str
    weekday: str
    source_range_pct: float
    source_range_atr: float
    atr14: float
    threshold_price_move: float
    mfe_before_entry: float
    mfe_after_entry: float
    mae_after_entry: float
    mfe_consumed_pct: float
    entry_to_mfe_bars: int | None
    follow_through: bool
    false_breakout: bool
    reversed: bool


def parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def load_candles(path: Path) -> list[Candle]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    candles = [
        Candle(
            index=index,
            timestamp=parse_ts(row["time"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("volume", 0.0)),
        )
        for index, row in enumerate(rows)
    ]
    return candles


def data_quality(candles: list[Candle]) -> dict[str, Any]:
    bad_ohlc = 0
    duplicates = 0
    gaps_gt_24h = 0
    gaps_gt_72h = 0
    max_gap_hours = 0.0
    seen: set[str] = set()
    prev: datetime | None = None
    for candle in candles:
        key = iso(candle.timestamp)
        if key in seen:
            duplicates += 1
        seen.add(key)
        if not (
            candle.high >= candle.low
            and candle.high >= candle.open
            and candle.high >= candle.close
            and candle.low <= candle.open
            and candle.low <= candle.close
        ):
            bad_ohlc += 1
        if prev is not None:
            gap_hours = (candle.timestamp - prev).total_seconds() / 3600.0
            max_gap_hours = max(max_gap_hours, gap_hours)
            if gap_hours > 24:
                gaps_gt_24h += 1
            if gap_hours > 72:
                gaps_gt_72h += 1
        prev = candle.timestamp
    gate = "PASS" if len(candles) >= 30000 and bad_ohlc == 0 and duplicates == 0 else "BLOCKED"
    return {
        "count": len(candles),
        "first": iso(candles[0].timestamp) if candles else None,
        "last": iso(candles[-1].timestamp) if candles else None,
        "ohlc_bad_rows": bad_ohlc,
        "duplicates": duplicates,
        "gaps_gt_24h": gaps_gt_24h,
        "gaps_gt_72h": gaps_gt_72h,
        "max_gap_hours": round(max_gap_hours, 2),
        "data_gate": gate,
    }


def compute_atr(candles: list[Candle], end_index: int, period: int = 14) -> float:
    if end_index < 1:
        return 0.0
    start = max(1, end_index - period + 1)
    values: list[float] = []
    for idx in range(start, end_index + 1):
        candle = candles[idx]
        prev_close = candles[idx - 1].close
        values.append(
            max(
                candle.high - candle.low,
                abs(candle.high - prev_close),
                abs(candle.low - prev_close),
            )
        )
    return mean(values) if values else 0.0


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute), tzinfo=timezone.utc)


def in_window(ts: datetime, start: str, end: str) -> bool:
    current = ts.timetz()
    return _parse_hhmm(start) <= current < _parse_hhmm(end)


def by_session_date(candles: list[Candle]) -> dict[str, list[Candle]]:
    grouped: dict[str, list[Candle]] = defaultdict(list)
    for candle in candles:
        grouped[candle.timestamp.date().isoformat()].append(candle)
    return dict(grouped)


def window_candles(day: list[Candle], start: str, end: str) -> list[Candle]:
    return [candle for candle in day if in_window(candle.timestamp, start, end)]


def make_range(candles: list[Candle], session_date: str, atr: float) -> SessionRange | None:
    if not candles:
        return None
    high = max(candle.high for candle in candles)
    low = min(candle.low for candle in candles)
    open_price = candles[0].open
    close_price = candles[-1].close
    mid = (high + low) / 2.0
    range_pct = 0.0 if mid == 0 else (high - low) / mid
    direction = "UP" if close_price >= open_price else "DOWN"
    return SessionRange(
        session_date=session_date,
        start_index=candles[0].index,
        end_index=candles[-1].index,
        high=high,
        low=low,
        open=open_price,
        close=close_price,
        range_pct=range_pct,
        range_atr=(high - low) / atr if atr > 0 else 0.0,
        direction=direction,
    )


def direction_for_breakout(candle: Candle, source: SessionRange) -> str | None:
    if candle.close > source.high:
        return "LONG"
    if candle.close < source.low:
        return "SHORT"
    return None


def favorable_adverse(
    candles: list[Candle],
    detection_index: int,
    entry_index: int,
    horizon: int,
    direction: str,
) -> dict[str, Any] | None:
    exit_index = entry_index + horizon
    if entry_index >= len(candles) or exit_index >= len(candles):
        return None
    detection = candles[detection_index]
    entry = candles[entry_index]
    before = candles[detection_index:entry_index]
    after = candles[entry_index:exit_index + 1]
    if direction == "LONG":
        mfe_before = max((c.high - detection.close for c in before), default=0.0)
        mfe_after = max((c.high - entry.open for c in after), default=0.0)
        mae_after = max((entry.open - c.low for c in after), default=0.0)
        best = max(((c.high, offset) for offset, c in enumerate(after)), default=(0.0, None))
    else:
        mfe_before = max((detection.close - c.low for c in before), default=0.0)
        mfe_after = max((entry.open - c.low for c in after), default=0.0)
        mae_after = max((c.high - entry.open for c in after), default=0.0)
        best = max(((-c.low, offset) for offset, c in enumerate(after)), default=(0.0, None))
    mfe_before = max(0.0, mfe_before)
    mfe_after = max(0.0, mfe_after)
    total = mfe_before + mfe_after
    return {
        "mfe_before_entry": mfe_before,
        "mfe_after_entry": mfe_after,
        "mae_after_entry": max(0.0, mae_after),
        "mfe_consumed_pct": mfe_before / total if total > 0 else 0.0,
        "entry_to_mfe_bars": best[1],
    }


def has_follow_through(candles: list[Candle], entry_index: int, direction: str, threshold: float) -> bool:
    if entry_index >= len(candles):
        return False
    entry = candles[entry_index]
    window = candles[entry_index:min(len(candles), entry_index + FOLLOW_THROUGH_BARS + 1)]
    if direction == "LONG":
        return any(candle.high - entry.open >= threshold for candle in window)
    return any(entry.open - candle.low >= threshold for candle in window)


def is_false_breakout(
    candles: list[Candle],
    detection_index: int,
    entry_index: int,
    direction: str,
    source: SessionRange,
    threshold: float,
) -> bool:
    if entry_index >= len(candles):
        return False
    entry = candles[entry_index]
    window = candles[entry_index:min(len(candles), entry_index + FALSE_BREAKOUT_BARS + 1)]
    if direction == "LONG":
        favorable = max((candle.high - entry.open for candle in window), default=0.0)
        closes_back_inside = any(candle.close < source.high for candle in candles[detection_index + 1:min(len(candles), detection_index + FALSE_BREAKOUT_BARS + 1)])
    else:
        favorable = max((entry.open - candle.low for candle in window), default=0.0)
        closes_back_inside = any(candle.close > source.low for candle in candles[detection_index + 1:min(len(candles), detection_index + FALSE_BREAKOUT_BARS + 1)])
    return closes_back_inside and favorable < threshold


def event_from_breakout(
    candidate: str,
    instrument: str,
    candles: list[Candle],
    source: SessionRange,
    detection: Candle,
    direction: str,
    atr: float,
) -> StructureEvent | None:
    entry_index = detection.index + 1
    metrics = favorable_adverse(candles, detection.index, entry_index, FOLLOW_THROUGH_BARS, direction)
    if metrics is None or atr <= 0:
        return None
    threshold = ATR_MULTIPLE * atr
    follow = has_follow_through(candles, entry_index, direction, threshold)
    false_break = is_false_breakout(candles, detection.index, entry_index, direction, source, threshold)
    return StructureEvent(
        candidate=candidate,
        instrument=instrument,
        session_date=source.session_date,
        direction=direction,
        range_known_bar=source.end_index,
        detection_bar=detection.index,
        state_known_bar=detection.index,
        entry_candidate_bar=entry_index,
        return_start_bar=entry_index,
        entry_time_utc=iso(candles[entry_index].timestamp),
        weekday=candles[entry_index].timestamp.strftime("%A"),
        source_range_pct=source.range_pct,
        source_range_atr=source.range_atr,
        atr14=atr,
        threshold_price_move=threshold,
        follow_through=follow,
        false_breakout=false_break,
        reversed=false_break,
        **metrics,
    )


def first_breakout(window: list[Candle], source: SessionRange) -> tuple[Candle, str] | None:
    for candle in window:
        direction = direction_for_breakout(candle, source)
        if direction:
            return candle, direction
    return None


def build_asia_london_events(instrument: str, candles: list[Candle]) -> list[StructureEvent]:
    events: list[StructureEvent] = []
    for session_date, day in by_session_date(candles).items():
        asia = window_candles(day, *SESSION_DEFINITIONS["asia_range"])
        london = window_candles(day, *SESSION_DEFINITIONS["london_open"])
        if not asia or not london:
            continue
        atr = compute_atr(candles, asia[-1].index)
        source = make_range(asia, session_date, atr)
        breakout = first_breakout(london, source) if source else None
        if breakout and source:
            event = event_from_breakout("ASIA_RANGE_LONDON_BREAKOUT", instrument, candles, source, breakout[0], breakout[1], atr)
            if event:
                events.append(event)
    return events


def build_london_open_events(instrument: str, candles: list[Candle]) -> list[StructureEvent]:
    events: list[StructureEvent] = []
    for session_date, day in by_session_date(candles).items():
        opening_range = window_candles(day, "07:00", "08:00")
        continuation = window_candles(day, "08:00", "12:00")
        if not opening_range or not continuation:
            continue
        atr = compute_atr(candles, opening_range[-1].index)
        source = make_range(opening_range, session_date, atr)
        breakout = first_breakout(continuation, source) if source else None
        if breakout and source:
            event = event_from_breakout("LONDON_OPEN_RANGE_BREAKOUT", instrument, candles, source, breakout[0], breakout[1], atr)
            if event:
                events.append(event)
    return events


def build_ny_reversal_events(instrument: str, candles: list[Candle]) -> list[StructureEvent]:
    events: list[StructureEvent] = []
    for session_date, day in by_session_date(candles).items():
        london = window_candles(day, "07:00", "12:00")
        ny = window_candles(day, *SESSION_DEFINITIONS["new_york_overlap"])
        if not london or not ny:
            continue
        atr = compute_atr(candles, london[-1].index)
        source = make_range(london, session_date, atr)
        if source is None or atr <= 0 or abs(source.close - source.open) < ATR_MULTIPLE * atr:
            continue
        direction = "SHORT" if source.close > source.open else "LONG"
        reference = source.close
        detection: Candle | None = None
        for candle in ny:
            if direction == "SHORT" and candle.close < reference - ATR_MULTIPLE * atr:
                detection = candle
                break
            if direction == "LONG" and candle.close > reference + ATR_MULTIPLE * atr:
                detection = candle
                break
        if detection is None:
            continue
        event = event_from_breakout("NY_REVERSAL_AFTER_LONDON_EXTENSION", instrument, candles, source, detection, direction, atr)
        if event:
            events.append(event)
    return events


def build_rollover_events(instrument: str, candles: list[Candle]) -> list[StructureEvent]:
    events: list[StructureEvent] = []
    for session_date, day in by_session_date(candles).items():
        pre_rollover = window_candles(day, "19:00", "21:00")
        rollover = window_candles(day, *SESSION_DEFINITIONS["rollover"])
        if not pre_rollover or not rollover:
            continue
        atr = compute_atr(candles, pre_rollover[-1].index)
        source = make_range(pre_rollover, session_date, atr)
        breakout = first_breakout(rollover, source) if source else None
        if breakout and source:
            # Candidate is framed as fade/avoidance: measure opposite-direction behavior.
            direction = "SHORT" if breakout[1] == "LONG" else "LONG"
            event = event_from_breakout("ROLLOVER_FADE_OR_AVOIDANCE", instrument, candles, source, breakout[0], direction, atr)
            if event:
                events.append(event)
    return events


def fold_for_timestamp(value: datetime) -> str:
    for name, start, end in FOLD_WINDOWS:
        if start <= value < end:
            return name
    return "outside"


def summarize_events(events: list[StructureEvent], months: float) -> dict[str, Any]:
    if not events:
        return {
            "count": 0,
            "events_per_month": 0.0,
            "events_per_year": 0.0,
            "follow_through_rate": None,
            "false_breakout_rate": None,
            "median_mfe_consumed_pct": None,
            "median_mfe_after_entry": None,
            "median_mae_after_entry": None,
            "median_range_pct": None,
            "median_range_atr": None,
            "direction_counts": {},
            "weekday_counts": {},
            "folds": {},
            "stable_positive_folds": 0,
        }
    folds: dict[str, dict[str, Any]] = {}
    for fold_name, _, _ in FOLD_WINDOWS:
        subset = [event for event in events if fold_for_timestamp(parse_ts(event.entry_time_utc)) == fold_name]
        folds[fold_name] = {
            "count": len(subset),
            "follow_through_rate": mean([event.follow_through for event in subset]) if subset else None,
            "false_breakout_rate": mean([event.false_breakout for event in subset]) if subset else None,
            "median_mfe_consumed_pct": median([event.mfe_consumed_pct for event in subset]) if subset else None,
            "stable": bool(
                len(subset) >= 25
                and mean([event.follow_through for event in subset]) > 0.50
                and mean([event.false_breakout for event in subset]) < MAX_FALSE_BREAKOUT_RATE
                and median([event.mfe_consumed_pct for event in subset]) < MFE_GATE
            ) if subset else False,
        }
    return {
        "count": len(events),
        "events_per_month": len(events) / months if months else 0.0,
        "events_per_year": len(events) / months * 12 if months else 0.0,
        "follow_through_rate": mean([event.follow_through for event in events]),
        "false_breakout_rate": mean([event.false_breakout for event in events]),
        "median_mfe_consumed_pct": median([event.mfe_consumed_pct for event in events]),
        "median_mfe_after_entry": median([event.mfe_after_entry for event in events]),
        "median_mae_after_entry": median([event.mae_after_entry for event in events]),
        "median_range_pct": median([event.source_range_pct for event in events]),
        "median_range_atr": median([event.source_range_atr for event in events]),
        "direction_counts": dict(Counter(event.direction for event in events)),
        "weekday_counts": dict(Counter(event.weekday for event in events)),
        "folds": folds,
        "stable_positive_folds": sum(1 for row in folds.values() if row["stable"]),
    }


def months_covered(candles: list[Candle]) -> float:
    if len(candles) < 2:
        return 0.0
    return max((candles[-1].timestamp - candles[0].timestamp).days / 30.4375, 0.01)


def build_all_events(instrument: str, candles: list[Candle]) -> dict[str, list[StructureEvent]]:
    return {
        "ASIA_RANGE_LONDON_BREAKOUT": build_asia_london_events(instrument, candles),
        "LONDON_OPEN_RANGE_BREAKOUT": build_london_open_events(instrument, candles),
        "NY_REVERSAL_AFTER_LONDON_EXTENSION": build_ny_reversal_events(instrument, candles),
        "ROLLOVER_FADE_OR_AVOIDANCE": build_rollover_events(instrument, candles),
    }


def rank_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    ranking: list[dict[str, Any]] = []
    primary = payload["instruments"]["EUR_USD"]["candidates"]
    for name, metrics in primary.items():
        count = metrics["count"]
        follow = metrics["follow_through_rate"] or 0.0
        false = metrics["false_breakout_rate"] if metrics["false_breakout_rate"] is not None else 1.0
        mfe = metrics["median_mfe_consumed_pct"] if metrics["median_mfe_consumed_pct"] is not None else 1.0
        stable = metrics["stable_positive_folds"]
        score = 0.0
        score += min(count / MIN_TOTAL_EVENTS, 2.0)
        score += max(0.0, follow - 0.5) * 4.0
        score += max(0.0, MAX_FALSE_BREAKOUT_RATE - false) * 4.0
        score += max(0.0, MFE_GATE - mfe) * 2.0
        score += stable * 0.5
        ranking.append(
            {
                "candidate": name,
                "score": score,
                "count": count,
                "follow_through_rate": metrics["follow_through_rate"],
                "false_breakout_rate": metrics["false_breakout_rate"],
                "median_mfe_consumed_pct": metrics["median_mfe_consumed_pct"],
                "stable_positive_folds": stable,
            }
        )
    return sorted(ranking, key=lambda row: row["score"], reverse=True)


def make_recommendation(payload: dict[str, Any]) -> dict[str, Any]:
    if any(row["data_quality"]["data_gate"] != "PASS" for row in payload["instruments"].values()):
        return {"verdict": "DATA_BLOCKED", "reason": "One or more required M15 datasets failed data quality gates."}
    ranking = rank_candidates(payload)
    viable = [
        row for row in ranking
        if row["count"] >= MIN_TOTAL_EVENTS
        and row["median_mfe_consumed_pct"] is not None
        and row["median_mfe_consumed_pct"] < MFE_GATE
        and row["follow_through_rate"] is not None
        and row["follow_through_rate"] > 0.50
        and row["false_breakout_rate"] is not None
        and row["false_breakout_rate"] < MAX_FALSE_BREAKOUT_RATE
        and row["stable_positive_folds"] >= 3
    ]
    if len(viable) == 1:
        best = viable[0]
        return {
            "verdict": "PROCEED_TO_FULL_PLANNING",
            "reason": (
                f"{best['candidate']} has {best['count']} EUR_USD M15 events, "
                f"follow-through {best['follow_through_rate']:.2%}, false breakout {best['false_breakout_rate']:.2%}, "
                f"median MFE consumed {best['median_mfe_consumed_pct']:.2%}, and {best['stable_positive_folds']}/4 stable folds."
            ),
            "candidate": best["candidate"],
        }
    if len(viable) > 1:
        best = viable[0]
        return {
            "verdict": "PROCEED_TO_FULL_PLANNING",
            "reason": (
                f"Multiple candidates passed structure gates; highest-ranked is {best['candidate']} with "
                f"{best['count']} events and {best['stable_positive_folds']}/4 stable folds."
            ),
            "candidate": best["candidate"],
        }
    if all(row["count"] < MIN_TOTAL_EVENTS for row in ranking):
        return {"verdict": "STOP_SESSION_EDGE", "reason": "No EUR_USD session candidate reached 200 total events."}
    if all((row["false_breakout_rate"] is not None and row["false_breakout_rate"] >= MAX_FALSE_BREAKOUT_RATE) for row in ranking):
        return {"verdict": "STOP_SESSION_EDGE", "reason": "All EUR_USD candidates have false breakout rates >= 50%."}
    if all((row["median_mfe_consumed_pct"] is not None and row["median_mfe_consumed_pct"] > MFE_GATE) for row in ranking):
        return {"verdict": "STOP_SESSION_EDGE", "reason": "All EUR_USD candidates consume more than 70% median MFE before entry."}
    return {
        "verdict": "INCONCLUSIVE",
        "reason": "Session structure exists, but no EUR_USD candidate passed all proceed gates.",
        "top_candidate": ranking[0] if ranking else None,
    }


def pct(value: Any, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{float(value) * 100:.{digits}f}%"


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def serialize_event_sample(events: list[StructureEvent], limit: int = 25) -> list[dict[str, Any]]:
    return [asdict(event) for event in events[:limit]]


def artifact_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_reconnaissance(eur_path: Path, xau_path: Path) -> dict[str, Any]:
    instruments = {
        "EUR_USD": load_candles(eur_path),
        "XAU_USD": load_candles(xau_path),
    }
    payload: dict[str, Any] = {
        "created_at_utc": iso(datetime.now(timezone.utc)),
        "milestone": "OANDA_SESSION_EDGE_RECONNAISSANCE_V1",
        "scope_boundary": "Session-driven forex structure only; sweep/reclaim transfer remains invalidated.",
        "session_definitions": SESSION_DEFINITIONS,
        "instruments": {},
    }
    for instrument, candles in instruments.items():
        events = build_all_events(instrument, candles)
        months = months_covered(candles)
        payload["instruments"][instrument] = {
            "data_quality": data_quality(candles),
            "months_covered": months,
            "candidates": {
                name: summarize_events(candidate_events, months)
                for name, candidate_events in events.items()
            },
            "event_samples": {
                name: serialize_event_sample(candidate_events)
                for name, candidate_events in events.items()
            },
        }
    payload["candidate_ranking"] = rank_candidates(payload)
    payload["recommendation"] = make_recommendation(payload)
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _candidate_table(payload: dict[str, Any], instrument: str) -> list[str]:
    lines = [
        "| Candidate | Count | Events/yr | Follow-through | False breakout | Median MFE consumed | Stable folds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in payload["instruments"][instrument]["candidates"].items():
        lines.append(
            f"| `{name}` | {row['count']} | {fmt(row['events_per_year'], 1)} | "
            f"{pct(row['follow_through_rate'])} | {pct(row['false_breakout_rate'])} | "
            f"{pct(row['median_mfe_consumed_pct'])} | {row['stable_positive_folds']} / 4 |"
        )
    return lines


def _fold_table(row: dict[str, Any]) -> list[str]:
    lines = [
        "| Fold | Count | Follow-through | False breakout | Median MFE consumed | Stable |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, fold in row["folds"].items():
        lines.append(
            f"| `{name}` | {fold['count']} | {pct(fold['follow_through_rate'])} | "
            f"{pct(fold['false_breakout_rate'])} | {pct(fold['median_mfe_consumed_pct'])} | {fold['stable']} |"
        )
    return lines


def write_report(path: Path, payload: dict[str, Any], json_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = payload["recommendation"]
    lines: list[str] = [
        "# OANDA_SESSION_EDGE_RECONNAISSANCE_V1",
        "",
        f"**Date:** {payload['created_at_utc']}",
        "**Type:** OANDA-native session edge reconnaissance; not a profitability diagnostic",
        f"**Recommendation:** {rec['verdict']}",
        "",
        "## 1. Executive Summary",
        "",
        "This report evaluates OANDA-native session structure after direct sweep/reclaim transfer was invalidated.",
        "It does not rescue sweep/reclaim, does not use SMC logic, does not run Optuna, and does not modify production code.",
        "",
        f"Result: `{rec['verdict']}`.",
        "",
        rec["reason"],
        "",
        "## 2. Prior OANDA Research Boundary",
        "",
        "- `XAU_USD H1` strict BTC sweep/reclaim transfer remains `STOP` due sample collapse.",
        "- `EUR_USD M15` same-bar sweep/reclaim remains `STOP` due negative expectancy and control outperformance.",
        "- This milestone tests session-driven forex structure only.",
        "- Any future edge claim requires a separate full planning document and diagnostic.",
        "",
        "## 3. Data Inventory",
        "",
        "| Instrument | Candles | First | Last | OHLC Bad | Duplicates | Gaps >72h | Max Gap Hours | Gate |",
        "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for instrument, data in payload["instruments"].items():
        dq = data["data_quality"]
        lines.append(
            f"| `{instrument}` | {dq['count']} | {dq['first']} | {dq['last']} | {dq['ohlc_bad_rows']} | "
            f"{dq['duplicates']} | {dq['gaps_gt_72h']} | {dq['max_gap_hours']} | `{dq['data_gate']}` |"
        )
    lines.extend([
        "",
        "## 4. Fixed Session Definitions",
        "",
        "| Session | UTC Window | Purpose |",
        "| --- | --- | --- |",
        "| `asia_range` | 00:00-07:00 | Compression / range formation |",
        "| `london_open` | 07:00-09:00 | Early European volatility expansion |",
        "| `london_continuation` | 09:00-12:00 | London follow-through |",
        "| `new_york_overlap` | 13:00-16:00 | Institutional overlap / reversal or continuation |",
        "| `rollover` | 21:00-23:00 | Illiquid window / fade or avoidance |",
        "",
        "## 5. Candidate Mechanism Definitions",
        "",
        "- `ASIA_RANGE_LONDON_BREAKOUT`: Asia range from 00:00-07:00, breakout close during 07:00-09:00.",
        "- `LONDON_OPEN_RANGE_BREAKOUT`: 07:00-08:00 opening range, breakout during 08:00-12:00.",
        "- `NY_REVERSAL_AFTER_LONDON_EXTENSION`: London 07:00-12:00 extension, reversal confirmation during 13:00-16:00.",
        "- `ROLLOVER_FADE_OR_AVOIDANCE`: 19:00-21:00 pre-rollover range, fade breakout during 21:00-23:00.",
        "",
        "## 6. Structural Frequency Matrix",
        "",
        "### EUR_USD M15",
        "",
    ])
    lines.extend(_candidate_table(payload, "EUR_USD"))
    lines.extend(["", "### XAU_USD M15 (comparison only)", ""])
    lines.extend(_candidate_table(payload, "XAU_USD"))
    lines.extend([
        "",
        "## 7. Range and Volatility Analysis",
        "",
        "| Instrument | Candidate | Median Range % | Median Range ATR |",
        "| --- | --- | ---: | ---: |",
    ])
    for instrument, data in payload["instruments"].items():
        for name, row in data["candidates"].items():
            lines.append(f"| `{instrument}` | `{name}` | {pct(row['median_range_pct'], 4)} | {fmt(row['median_range_atr'], 2)} |")
    lines.extend([
        "",
        "## 8. Breakout / Reversal Behavior",
        "",
        "| Instrument | Candidate | Count | Follow-through | False breakout | Direction counts |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ])
    for instrument, data in payload["instruments"].items():
        for name, row in data["candidates"].items():
            lines.append(
                f"| `{instrument}` | `{name}` | {row['count']} | {pct(row['follow_through_rate'])} | "
                f"{pct(row['false_breakout_rate'])} | `{row['direction_counts']}` |"
            )
    lines.extend([
        "",
        "## 9. MFE Accessibility",
        "",
        "| Instrument | Candidate | Median MFE Consumed | Median MFE After Entry | Median MAE After Entry |",
        "| --- | --- | ---: | ---: | ---: |",
    ])
    for instrument, data in payload["instruments"].items():
        for name, row in data["candidates"].items():
            lines.append(
                f"| `{instrument}` | `{name}` | {pct(row['median_mfe_consumed_pct'])} | "
                f"{fmt(row['median_mfe_after_entry'], 6)} | {fmt(row['median_mae_after_entry'], 6)} |"
            )
    lines.extend([
        "",
        "## 10. False Breakout and Follow-Through",
        "",
        f"- False breakout: closes back inside source range within `{FALSE_BREAKOUT_BARS}` bars and fails to make `{ATR_MULTIPLE} * ATR14` favorable excursion.",
        f"- Follow-through: reaches `{ATR_MULTIPLE} * ATR14` favorable excursion within `{FOLLOW_THROUGH_BARS}` bars after entry candidate.",
        "- Entry candidate is always the next bar open after state-known close.",
        "",
    ])
    for candidate in payload["candidate_ranking"]:
        row = payload["instruments"]["EUR_USD"]["candidates"][candidate["candidate"]]
        lines.extend([f"### EUR_USD {candidate['candidate']}", ""])
        lines.extend(_fold_table(row))
        lines.append("")
    lines.extend([
        "## 11. Direction / Weekday / Session Splits",
        "",
    ])
    for instrument, data in payload["instruments"].items():
        lines.append(f"### {instrument}")
        lines.append("")
        for name, row in data["candidates"].items():
            lines.append(f"- `{name}` direction counts: `{row['direction_counts']}`; weekday counts: `{row['weekday_counts']}`")
        lines.append("")
    lines.extend([
        "## 12. Candidate Ranking",
        "",
        "| Rank | Candidate | Score | Count | Follow-through | False breakout | Median MFE Consumed | Stable folds |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for index, row in enumerate(payload["candidate_ranking"], start=1):
        lines.append(
            f"| {index} | `{row['candidate']}` | {fmt(row['score'], 3)} | {row['count']} | "
            f"{pct(row['follow_through_rate'])} | {pct(row['false_breakout_rate'])} | "
            f"{pct(row['median_mfe_consumed_pct'])} | {row['stable_positive_folds']} / 4 |"
        )
    lines.extend([
        "",
        "## 13. Future Controls",
        "",
        "If a candidate proceeds to full planning, future controls should include:",
        "",
        "1. Random session timing.",
        "2. Opposite direction entry.",
        "3. Same breakout rule outside target session.",
        "4. Breakout without compression.",
        "5. Compression without breakout.",
        "6. Shifted entry +2 bars.",
        "7. Weekday-shuffled control.",
        "8. Previous-day range breakout control.",
        "",
        "## 14. Recommendation",
        "",
        f"### Verdict: {rec['verdict']}",
        "",
        f"**Reason:** {rec['reason']}",
        "",
    ])
    if rec["verdict"] == "PROCEED_TO_FULL_PLANNING":
        lines.append(f"**Next:** Create a full planning document for `{rec['candidate']}`. This reconnaissance does not prove edge.")
    elif rec["verdict"] == "STOP_SESSION_EDGE":
        lines.append("**Next:** Stop OANDA session edge research and revisit multi-asset crypto or a separately planned OANDA autoresearch framework.")
    elif rec["verdict"] == "DATA_BLOCKED":
        lines.append("**Next:** Resolve OANDA M15 data availability before further session research.")
    else:
        lines.append("**Next:** Treat session structure as unproven; decide whether to build a hardened OANDA autoresearch framework or return to multi-asset crypto.")
    lines.extend([
        "",
        "## Artifact",
        "",
        f"- JSON path: `{json_path.as_posix()}`",
        f"- JSON SHA256: `{artifact_sha256(json_path) if json_path.exists() else 'pending'}`",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eur-data", type=Path, default=DEFAULT_EUR_DATA)
    parser.add_argument("--xau-data", type=Path, default=DEFAULT_XAU_DATA)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = run_reconnaissance(args.eur_data, args.xau_data)
    write_json(args.json_path, payload)
    write_report(args.report_path, payload, args.json_path)
    print(json.dumps({"recommendation": payload["recommendation"], "report": str(args.report_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
