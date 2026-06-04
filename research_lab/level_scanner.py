from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import time
from typing import Any

import pandas as pd


SCANNER_VERSION = "level_scanner_v1"

OUTPUT_COLUMNS = [
    "level_id",
    "symbol",
    "timeframe",
    "category",
    "side",
    "price",
    "top",
    "bottom",
    "formed_at",
    "available_at",
    "expired_at",
    "swept_at",
    "source",
    "lookback_bars",
    "tolerance_abs",
    "tolerance_atr",
    "quality_score",
    "is_hpz",
    "metadata_json",
    "session_tag",
    "period_tag",
    "anchor_type",
    "anchor_timestamp",
    "active_from",
    "active_until",
    "scanner_version",
]


@dataclass(frozen=True, slots=True)
class SessionWindow:
    name: str
    start: str
    end: str


@dataclass(frozen=True, slots=True)
class ScannerConfig:
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    source: str = "local"
    sessions: tuple[SessionWindow, ...] = (
        SessionWindow("asia", "00:00", "08:00"),
        SessionWindow("london", "07:00", "16:00"),
        SessionWindow("new_york", "13:00", "22:00"),
        SessionWindow("asian_kill_zone", "00:00", "04:00"),
        SessionWindow("london_open_kill_zone", "06:00", "09:00"),
        SessionWindow("new_york_kill_zone", "11:00", "14:00"),
        SessionWindow("london_close_kill_zone", "14:00", "16:00"),
    )
    include_session_extremes: bool = True
    include_previous_periods: bool = True
    include_equal_clusters: bool = True
    include_anchored_vwap: bool = True
    include_round_numbers: bool = True
    include_liquidation_placeholder: bool = True
    atr_period: int = 14
    swing_left_bars: int = 3
    swing_right_bars: int = 1
    equal_cluster_min_hits: int = 2
    equal_cluster_lookback_bars: int = 96
    equal_cluster_tolerance_atr: float = 0.25
    round_intervals: tuple[float, ...] = (1000.0, 5000.0, 10000.0)
    round_padding_intervals: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


def scan_levels(ohlcv_df: pd.DataFrame, config: ScannerConfig) -> pd.DataFrame:
    """Convert OHLCV history into deterministic, auditable level facts.

    This module is research-only. It emits level facts and never constructs
    signal candidates, confluence scores, risk decisions, or execution inputs.
    """
    frame = _normalize_ohlcv(ohlcv_df)
    records: list[dict[str, Any]] = []

    if config.include_session_extremes:
        records.extend(_scan_session_extremes(frame, config))
    if config.include_previous_periods:
        records.extend(_scan_previous_period_levels(frame, config))
    if config.include_equal_clusters:
        records.extend(_scan_equal_clusters(frame, config))
    if config.include_anchored_vwap:
        records.extend(_scan_anchored_vwap(frame, config))
    if config.include_round_numbers:
        records.extend(_scan_round_numbers(frame, config))
    if config.include_liquidation_placeholder:
        records.extend(_scan_liquidation_placeholder(config))

    output = pd.DataFrame.from_records(records, columns=OUTPUT_COLUMNS)
    if output.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    output = output.sort_values(["available_at", "category", "price", "side"], kind="stable").reset_index(drop=True)
    return output[OUTPUT_COLUMNS]


def make_level_id(
    *,
    source: str,
    category: str,
    symbol: str,
    timeframe: str,
    price: float,
    formed_at: pd.Timestamp,
) -> str:
    formed = _utc_timestamp(formed_at).isoformat()
    payload = f"{source}|{category}|{symbol}|{timeframe}|{price:.8f}|{formed}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def empty_level_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def _normalize_ohlcv(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
    if ohlcv_df.empty:
        raise ValueError("ohlcv_df must not be empty")

    frame = ohlcv_df.copy()
    rename = {column: str(column).lower() for column in frame.columns}
    frame = frame.rename(columns=rename)

    if "timestamp" in frame.columns:
        timestamps = pd.to_datetime(frame.pop("timestamp"), utc=True)
        frame.index = timestamps
    else:
        frame.index = pd.to_datetime(frame.index, utc=True)

    required = {"open", "high", "low", "close"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"ohlcv_df missing required columns: {missing}")
    if "volume" not in frame.columns:
        frame["volume"] = 0.0

    frame = frame.sort_index(kind="stable")
    if frame.index.has_duplicates:
        raise ValueError("ohlcv_df index must not contain duplicate timestamps")

    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)

    return frame[["open", "high", "low", "close", "volume"]]


def _scan_session_extremes(frame: pd.DataFrame, config: ScannerConfig) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if len(frame) < 2:
        return records

    for session in config.sessions:
        start = _parse_hhmm(session.start)
        end = _parse_hhmm(session.end)
        session_ids = _session_ids(frame.index, session.name, start, end)
        for session_id, group in frame.groupby(session_ids, sort=True):
            if session_id is None or group.empty:
                continue
            formed_at = group.index[-1]
            available_at = _next_timestamp(frame.index, formed_at)
            high_price = float(group["high"].max())
            low_price = float(group["low"].min())
            metadata = {
                "session": session.name,
                "session_start_utc": session.start,
                "session_end_utc": session.end,
                "session_id": str(session_id),
                "bar_count": int(len(group)),
                "interval": "[start,end)",
            }
            records.append(
                _level_record(
                    config=config,
                    category="session_extreme",
                    side="HIGH",
                    price=high_price,
                    top=high_price,
                    bottom=high_price,
                    formed_at=formed_at,
                    available_at=available_at,
                    source="local",
                    session_tag=f"{session.name}_high",
                    metadata=metadata,
                    active_from=group.index[0],
                    active_until=formed_at,
                )
            )
            records.append(
                _level_record(
                    config=config,
                    category="session_extreme",
                    side="LOW",
                    price=low_price,
                    top=low_price,
                    bottom=low_price,
                    formed_at=formed_at,
                    available_at=available_at,
                    source="local",
                    session_tag=f"{session.name}_low",
                    metadata=metadata,
                    active_from=group.index[0],
                    active_until=formed_at,
                )
            )
    return records


def _scan_previous_period_levels(frame: pd.DataFrame, config: ScannerConfig) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for period_tag, rule in (("PD", "1D"), ("PW", "W-MON")):
        resampled = frame.resample(rule, label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )
        resampled = resampled.dropna(subset=["open", "high", "low", "close"])
        if len(resampled) < 2:
            continue
        for idx in range(len(resampled) - 1):
            period_start = resampled.index[idx]
            next_start = resampled.index[idx + 1]
            period_rows = frame[(frame.index >= period_start) & (frame.index < next_start)]
            if period_rows.empty:
                continue
            formed_at = period_rows.index[-1]
            available_at = _first_timestamp_at_or_after(frame.index, next_start)
            high_price = float(resampled.iloc[idx]["high"])
            low_price = float(resampled.iloc[idx]["low"])
            metadata = {
                "period_tag": period_tag,
                "period_start_utc": _utc_timestamp(period_start).isoformat(),
                "period_available_from_utc": _utc_timestamp(next_start).isoformat(),
                "resample_rule": rule,
            }
            records.append(
                _level_record(
                    config=config,
                    category="previous_period",
                    side="HIGH",
                    price=high_price,
                    top=high_price,
                    bottom=high_price,
                    formed_at=formed_at,
                    available_at=available_at,
                    source="local",
                    period_tag=f"{period_tag}H",
                    metadata=metadata,
                    active_from=available_at,
                    active_until=_next_period_end(frame.index, available_at, rule),
                )
            )
            records.append(
                _level_record(
                    config=config,
                    category="previous_period",
                    side="LOW",
                    price=low_price,
                    top=low_price,
                    bottom=low_price,
                    formed_at=formed_at,
                    available_at=available_at,
                    source="local",
                    period_tag=f"{period_tag}L",
                    metadata=metadata,
                    active_from=available_at,
                    active_until=_next_period_end(frame.index, available_at, rule),
                )
            )
    return records


def _scan_equal_clusters(frame: pd.DataFrame, config: ScannerConfig) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    atr = _compute_atr_series(frame, config.atr_period)
    pivots = _confirmed_pivots(frame, config.swing_left_bars, config.swing_right_bars)
    for side in ("HIGH", "LOW"):
        side_pivots = [pivot for pivot in pivots if pivot["side"] == side]
        active_clusters: list[dict[str, Any]] = []
        emitted: set[tuple[str, tuple[int, ...]]] = set()
        for pivot in side_pivots:
            tolerance_abs = float(atr.loc[pivot["available_at"]] * config.equal_cluster_tolerance_atr)
            if tolerance_abs <= 0:
                tolerance_abs = float(pivot["price"] * 0.001)
            cutoff_idx = int(pivot["index"]) - config.equal_cluster_lookback_bars
            active_clusters = [
                cluster for cluster in active_clusters if max(cluster["indices"]) >= cutoff_idx
            ]
            matched = None
            for cluster in active_clusters:
                if abs(float(pivot["price"]) - float(cluster["price"])) <= max(tolerance_abs, float(cluster["tolerance_abs"])):
                    matched = cluster
                    break
            if matched is None:
                matched = {
                    "side": side,
                    "prices": [],
                    "indices": [],
                    "formed_ats": [],
                    "available_ats": [],
                    "tolerance_abs": tolerance_abs,
                }
                active_clusters.append(matched)
            matched["prices"].append(float(pivot["price"]))
            matched["indices"].append(int(pivot["index"]))
            matched["formed_ats"].append(pivot["formed_at"])
            matched["available_ats"].append(pivot["available_at"])
            matched["price"] = sum(matched["prices"]) / len(matched["prices"])
            matched["tolerance_abs"] = max(float(matched["tolerance_abs"]), tolerance_abs)
            if len(matched["prices"]) < config.equal_cluster_min_hits:
                continue
            cluster_key = (side, tuple(matched["indices"]))
            if cluster_key in emitted:
                continue
            emitted.add(cluster_key)
            price = float(matched["price"])
            top = price + float(matched["tolerance_abs"])
            bottom = price - float(matched["tolerance_abs"])
            available_at = max(matched["available_ats"])
            swept_at = _find_swept_at(frame, side, price, float(matched["tolerance_abs"]), available_at)
            metadata = {
                "hit_count": len(matched["prices"]),
                "pivot_indices": matched["indices"],
                "pivot_prices": [round(value, 8) for value in matched["prices"]],
                "swing_left_bars": config.swing_left_bars,
                "swing_right_bars": config.swing_right_bars,
                "lookback_bars": config.equal_cluster_lookback_bars,
                "tolerance_atr": config.equal_cluster_tolerance_atr,
            }
            records.append(
                _level_record(
                    config=config,
                    category="equal_cluster",
                    side=side,
                    price=price,
                    top=top,
                    bottom=bottom,
                    formed_at=min(matched["formed_ats"]),
                    available_at=available_at,
                    swept_at=swept_at,
                    source="local",
                    lookback_bars=config.equal_cluster_lookback_bars,
                    tolerance_abs=float(matched["tolerance_abs"]),
                    tolerance_atr=config.equal_cluster_tolerance_atr,
                    quality_score=min(100.0, len(matched["prices"]) * 25.0),
                    is_hpz=len(matched["prices"]) >= 3,
                    metadata=metadata,
                )
            )
    return records


def _scan_anchored_vwap(frame: pd.DataFrame, config: ScannerConfig) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    pivots = _confirmed_pivots(frame, config.swing_left_bars, config.swing_right_bars)
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    for pivot in pivots:
        anchor_time = pivot["available_at"]
        active = frame.loc[anchor_time:]
        if active.empty:
            continue
        active_typical = typical.loc[anchor_time:]
        volume = active["volume"].clip(lower=0.0)
        if float(volume.sum()) > 0:
            vwap = float((active_typical * volume).sum() / volume.sum())
            volume_source = "volume_weighted"
        else:
            vwap = float(active_typical.mean())
            volume_source = "typical_price_average_no_volume"
        anchor_type = "swing_high" if pivot["side"] == "HIGH" else "swing_low"
        metadata = {
            "anchor_type": anchor_type,
            "anchor_side": pivot["side"],
            "anchor_price": round(float(pivot["price"]), 8),
            "volume_source": volume_source,
            "active_bar_count": int(len(active)),
        }
        records.append(
            _level_record(
                config=config,
                category="anchored_vwap",
                side="MID",
                price=vwap,
                top=vwap,
                bottom=vwap,
                formed_at=pivot["formed_at"],
                available_at=anchor_time,
                source="local",
                anchor_type=anchor_type,
                anchor_timestamp=anchor_time,
                metadata=metadata,
                active_from=anchor_time,
                active_until=frame.index[-1],
            )
        )
    return records


def _scan_round_numbers(frame: pd.DataFrame, config: ScannerConfig) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    min_price = float(frame["low"].min())
    max_price = float(frame["high"].max())
    formed_at = frame.index[0]
    available_at = frame.index[0]
    seen: set[float] = set()
    for interval in sorted(set(config.round_intervals)):
        if interval <= 0:
            continue
        start = (int(min_price // interval) - config.round_padding_intervals) * interval
        end = (int(max_price // interval) + config.round_padding_intervals + 1) * interval
        level = start
        while level <= end:
            price = round(float(level), 8)
            level += interval
            if price <= 0 or price in seen:
                continue
            seen.add(price)
            metadata = {"interval": interval, "price_min": min_price, "price_max": max_price}
            records.append(
                _level_record(
                    config=config,
                    category="round_number",
                    side="ROUND",
                    price=price,
                    top=price,
                    bottom=price,
                    formed_at=formed_at,
                    available_at=available_at,
                    source="local",
                    metadata=metadata,
                    active_from=formed_at,
                    active_until=frame.index[-1],
                )
            )
    return records


def _scan_liquidation_placeholder(config: ScannerConfig) -> list[dict[str, Any]]:
    # Explicit placeholder: Tardis backfill is a separate milestone. Returning
    # no rows keeps downstream consumers stable without inventing fake levels.
    _ = config
    return []


def _level_record(
    *,
    config: ScannerConfig,
    category: str,
    side: str,
    price: float,
    top: float | None,
    bottom: float | None,
    formed_at: pd.Timestamp,
    available_at: pd.Timestamp,
    source: str,
    expired_at: pd.Timestamp | None = None,
    swept_at: pd.Timestamp | None = None,
    lookback_bars: int | None = None,
    tolerance_abs: float | None = None,
    tolerance_atr: float | None = None,
    quality_score: float | None = None,
    is_hpz: bool | None = None,
    metadata: dict[str, Any] | None = None,
    session_tag: str | None = None,
    period_tag: str | None = None,
    anchor_type: str | None = None,
    anchor_timestamp: pd.Timestamp | None = None,
    active_from: pd.Timestamp | None = None,
    active_until: pd.Timestamp | None = None,
) -> dict[str, Any]:
    formed = _utc_timestamp(formed_at)
    available = _utc_timestamp(available_at)
    merged_metadata = dict(config.metadata)
    merged_metadata.update(metadata or {})
    hash_category = _hash_category(
        category=category,
        side=side,
        session_tag=session_tag,
        period_tag=period_tag,
        anchor_type=anchor_type,
        available_at=available,
    )
    record = {
        "level_id": make_level_id(
            source=source,
            category=hash_category,
            symbol=config.symbol,
            timeframe=config.timeframe,
            price=price,
            formed_at=formed,
        ),
        "symbol": config.symbol,
        "timeframe": config.timeframe,
        "category": category,
        "side": side,
        "price": float(price),
        "top": None if top is None else float(top),
        "bottom": None if bottom is None else float(bottom),
        "formed_at": formed,
        "available_at": available,
        "expired_at": None if expired_at is None else _utc_timestamp(expired_at),
        "swept_at": None if swept_at is None else _utc_timestamp(swept_at),
        "source": source,
        "lookback_bars": lookback_bars,
        "tolerance_abs": tolerance_abs,
        "tolerance_atr": tolerance_atr,
        "quality_score": quality_score,
        "is_hpz": is_hpz,
        "metadata_json": json.dumps(merged_metadata, sort_keys=True, separators=(",", ":")),
        "session_tag": session_tag,
        "period_tag": period_tag,
        "anchor_type": anchor_type,
        "anchor_timestamp": None if anchor_timestamp is None else _utc_timestamp(anchor_timestamp),
        "active_from": None if active_from is None else _utc_timestamp(active_from),
        "active_until": None if active_until is None else _utc_timestamp(active_until),
        "scanner_version": SCANNER_VERSION,
    }
    return record


def _hash_category(
    *,
    category: str,
    side: str,
    session_tag: str | None,
    period_tag: str | None,
    anchor_type: str | None,
    available_at: pd.Timestamp,
) -> str:
    """Return a stable category discriminator for collision-free level ids.

    The base milestone formula intentionally uses category, not every output
    field. In real data, broad categories can collide for semantically distinct
    rows, e.g. PDH and PWH at the same price or a doji-like candle that is both
    swing high and swing low. The discriminator keeps ids deterministic while
    preserving the public output category.
    """
    parts = [category, side]
    for value in (session_tag, period_tag, anchor_type):
        if value:
            parts.append(value)
    parts.append(_utc_timestamp(available_at).isoformat())
    return ":".join(parts)


def _parse_hhmm(value: str) -> time:
    hour_str, minute_str = value.split(":", 1)
    return time(int(hour_str), int(minute_str))


def _session_ids(index: pd.DatetimeIndex, name: str, start: time, end: time) -> list[str | None]:
    ids: list[str | None] = []
    for timestamp in index:
        ts = _utc_timestamp(timestamp)
        current = ts.time().replace(second=0, microsecond=0)
        if start < end:
            active = start <= current < end
            session_date = ts.date()
        else:
            active = current >= start or current < end
            session_date = ts.date() if current >= start else (ts - pd.Timedelta(days=1)).date()
        ids.append(f"{name}:{session_date.isoformat()}" if active else None)
    return ids


def _confirmed_pivots(frame: pd.DataFrame, left: int, right: int) -> list[dict[str, Any]]:
    pivots: list[dict[str, Any]] = []
    if left < 1 or right < 1 or len(frame) <= left + right:
        return pivots
    high = frame["high"].to_numpy()
    low = frame["low"].to_numpy()
    for idx in range(left, len(frame) - right):
        high_window = high[idx - left : idx + right + 1]
        low_window = low[idx - left : idx + right + 1]
        if high[idx] == high_window.max() and (high_window == high[idx]).sum() == 1:
            pivots.append(
                {
                    "index": idx,
                    "side": "HIGH",
                    "price": float(high[idx]),
                    "formed_at": frame.index[idx],
                    "available_at": frame.index[idx + right],
                }
            )
        if low[idx] == low_window.min() and (low_window == low[idx]).sum() == 1:
            pivots.append(
                {
                    "index": idx,
                    "side": "LOW",
                    "price": float(low[idx]),
                    "formed_at": frame.index[idx],
                    "available_at": frame.index[idx + right],
                }
            )
    return sorted(pivots, key=lambda item: (item["available_at"], item["side"]))


def _compute_atr_series(frame: pd.DataFrame, period: int) -> pd.Series:
    prev_close = frame["close"].shift(1)
    tr = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(max(period, 1), min_periods=1).mean()
    return atr.fillna(0.0)


def _find_swept_at(
    frame: pd.DataFrame,
    side: str,
    price: float,
    tolerance_abs: float,
    available_at: pd.Timestamp,
) -> pd.Timestamp | None:
    future = frame[frame.index > available_at]
    if side == "HIGH":
        swept = future[future["high"] >= price + tolerance_abs]
    else:
        swept = future[future["low"] <= price - tolerance_abs]
    if swept.empty:
        return None
    return swept.index[0]


def _next_timestamp(index: pd.DatetimeIndex, timestamp: pd.Timestamp) -> pd.Timestamp:
    position = index.searchsorted(timestamp, side="right")
    if position >= len(index):
        return _utc_timestamp(timestamp)
    return _utc_timestamp(index[position])


def _first_timestamp_at_or_after(index: pd.DatetimeIndex, timestamp: pd.Timestamp) -> pd.Timestamp:
    position = index.searchsorted(timestamp, side="left")
    if position >= len(index):
        return _utc_timestamp(timestamp)
    return _utc_timestamp(index[position])


def _next_period_end(index: pd.DatetimeIndex, available_at: pd.Timestamp, rule: str) -> pd.Timestamp | None:
    later = index[index >= available_at]
    if later.empty:
        return None
    if rule == "1D":
        end = _utc_timestamp(available_at).normalize() + pd.Timedelta(days=1)
    else:
        end = _utc_timestamp(available_at) + pd.Timedelta(days=7)
    candidates = later[later < end]
    return None if candidates.empty else _utc_timestamp(candidates[-1])


def _utc_timestamp(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("UTC") if pd.Timestamp(value).tzinfo else pd.Timestamp(value, tz="UTC")
