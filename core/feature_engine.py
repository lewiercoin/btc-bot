from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import sqrt
from typing import Iterable

from core.models import Features, MarketSnapshot


@dataclass(slots=True)
class FeatureEngineConfig:
    atr_period: int = 14
    ema_fast: int = 50
    ema_slow: int = 200
    equal_level_lookback: int = 50
    equal_level_tol_atr: float = 0.25
    sweep_buf_atr: float = 0.15
    reclaim_buf_atr: float = 0.05
    wick_min_atr: float = 0.40
    funding_window_days: int = 60
    oi_z_window_days: int = 60
    force_order_history_points: int = 180
    cvd_divergence_window_bars: int = 10


def _mean(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def _std(values: Iterable[float]) -> float:
    vals = list(values)
    if len(vals) < 2:
        return 0.0
    avg = _mean(vals)
    variance = sum((v - avg) ** 2 for v in vals) / len(vals)
    return sqrt(variance)


def percentile_rank(values: list[float], value: float) -> float:
    if not values:
        return 50.0
    lower_or_equal = sum(1 for item in values if item <= value)
    return (lower_or_equal / len(values)) * 100.0


def zscore(values: list[float], value: float) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    sd = _std(values)
    if sd == 0:
        return 0.0
    return (value - avg) / sd


def compute_ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    if period <= 1:
        return float(values[-1])
    multiplier = 2 / (period + 1)
    ema = float(values[0])
    for value in values[1:]:
        ema = (float(value) - ema) * multiplier + ema
    return ema


def compute_atr(candles: list[dict], period: int) -> float:
    if len(candles) < 2:
        return 0.0
    true_ranges: list[float] = []
    for index in range(1, len(candles)):
        prev_close = float(candles[index - 1]["close"])
        high = float(candles[index]["high"])
        low = float(candles[index]["low"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    if not true_ranges:
        return 0.0
    window = true_ranges[-period:] if len(true_ranges) >= period else true_ranges
    return _mean(window)


def detect_equal_levels(levels: list[float], tolerance: float, min_hits: int = 2) -> list[float]:
    if not levels:
        return []
    sorted_levels = sorted(float(v) for v in levels)
    clusters: list[list[float]] = []
    current_cluster: list[float] = [sorted_levels[0]]

    for level in sorted_levels[1:]:
        if abs(level - current_cluster[-1]) <= tolerance:
            current_cluster.append(level)
        else:
            clusters.append(current_cluster)
            current_cluster = [level]
    clusters.append(current_cluster)

    merged = [round(_mean(cluster), 2) for cluster in clusters if len(cluster) >= min_hits]
    return merged


def detect_sweep_reclaim(
    candles_15m: list[dict],
    equal_lows: list[float],
    equal_highs: list[float],
    atr_15m: float,
    config: FeatureEngineConfig,
) -> tuple[bool, bool, float | None, float | None, str | None, float | None, float | None, float | None]:
    if len(candles_15m) < 2 or atr_15m <= 0:
        return False, False, None, None, None, None, None, None

    latest = candles_15m[-1]
    open_price = float(latest["open"])
    close_price = float(latest["close"])
    high_price = float(latest["high"])
    low_price = float(latest["low"])
    body_low = min(open_price, close_price)
    body_high = max(open_price, close_price)

    sweep_buffer = config.sweep_buf_atr * atr_15m
    reclaim_buffer = config.reclaim_buf_atr * atr_15m
    wick_min = config.wick_min_atr * atr_15m

    for level in equal_lows:
        swept = low_price < (level - sweep_buffer)
        reclaimed = close_price > (level + reclaim_buffer)
        wick_ok = (body_low - low_price) >= wick_min
        close_vs_reclaim_buffer_atr = (close_price - (level + reclaim_buffer)) / atr_15m
        wick_vs_min_atr = ((body_low - low_price) - wick_min) / atr_15m
        sweep_vs_buffer_atr = ((level - sweep_buffer) - low_price) / atr_15m
        if swept:
            depth_pct = abs(level - low_price) / level if level else 0.0
            return (
                True,
                bool(reclaimed and wick_ok),
                float(level),
                depth_pct,
                "LOW",
                close_vs_reclaim_buffer_atr,
                wick_vs_min_atr,
                sweep_vs_buffer_atr,
            )

    for level in equal_highs:
        swept = high_price > (level + sweep_buffer)
        reclaimed = close_price < (level - reclaim_buffer)
        wick_ok = (high_price - body_high) >= wick_min
        close_vs_reclaim_buffer_atr = ((level - reclaim_buffer) - close_price) / atr_15m
        wick_vs_min_atr = ((high_price - body_high) - wick_min) / atr_15m
        sweep_vs_buffer_atr = (high_price - (level + sweep_buffer)) / atr_15m
        if swept:
            depth_pct = abs(high_price - level) / level if level else 0.0
            return (
                True,
                bool(reclaimed and wick_ok),
                float(level),
                depth_pct,
                "HIGH",
                close_vs_reclaim_buffer_atr,
                wick_vs_min_atr,
                sweep_vs_buffer_atr,
            )

    return False, False, None, None, None, None, None, None


class FeatureEngine:
    def __init__(self, config: FeatureEngineConfig | None = None) -> None:
        self.config = config or FeatureEngineConfig()
        self._oi_history: deque[tuple[datetime, float]] = deque()
        self._force_order_rate_history: deque[float] = deque(maxlen=self.config.force_order_history_points)
        self._cvd_price_history: deque[tuple[datetime, float, float]] = deque(maxlen=500)

    def reset(self) -> None:
        """Reset rolling runtime windows used for OI/CVD/force-order derived features.

        FeatureEngine keeps bounded internal windows for metrics that are not fully
        reconstructable from a single MarketSnapshot payload. Calling reset() makes
        subsequent compute() output independent from any prior calls.
        """
        self._oi_history.clear()
        self._force_order_rate_history.clear()
        self._cvd_price_history.clear()

    def compute(self, snapshot: MarketSnapshot, schema_version: str, config_hash: str) -> Features:
        timestamp = snapshot.timestamp.astimezone(timezone.utc)
        atr_15m = compute_atr(snapshot.candles_15m, self.config.atr_period)
        atr_4h = compute_atr(snapshot.candles_4h, self.config.atr_period)
        atr_4h_norm = 0.0 if snapshot.price == 0 else atr_4h / snapshot.price

        closes_4h = [float(candle["close"]) for candle in snapshot.candles_4h]
        ema50_4h = compute_ema(closes_4h, self.config.ema_fast)
        ema200_4h = compute_ema(closes_4h, self.config.ema_slow)

        recent_15m = snapshot.candles_15m[-self.config.equal_level_lookback :] if snapshot.candles_15m else []
        lows = [float(candle["low"]) for candle in recent_15m]
        highs = [float(candle["high"]) for candle in recent_15m]
        level_tolerance = atr_15m * self.config.equal_level_tol_atr if atr_15m > 0 else 0.0
        equal_lows = detect_equal_levels(lows, tolerance=level_tolerance, min_hits=3)
        equal_highs = detect_equal_levels(highs, tolerance=level_tolerance, min_hits=3)

        (
            sweep_detected,
            reclaim_detected,
            sweep_level,
            sweep_depth_pct,
            sweep_side,
            close_vs_reclaim_buffer_atr,
            wick_vs_min_atr,
            sweep_vs_buffer_atr,
        ) = detect_sweep_reclaim(snapshot.candles_15m, equal_lows, equal_highs, atr_15m, self.config)

        funding_rates = self._funding_window_rates(snapshot.funding_history, timestamp)
        funding_8h = funding_rates[-1] if funding_rates else 0.0
        funding_sma3 = _mean(funding_rates[-3:]) if funding_rates else 0.0
        funding_sma9 = _mean(funding_rates[-9:]) if funding_rates else 0.0
        funding_pct_60d = percentile_rank(funding_rates, funding_8h) if funding_rates else 50.0

        oi_value, oi_zscore_60d, oi_delta_pct = self._compute_oi_stats(snapshot.open_interest, timestamp)

        cvd_15m = float(snapshot.aggtrades_bucket_15m.get("cvd", 0.0))
        self._cvd_price_history.append((timestamp, float(snapshot.price), cvd_15m))
        cvd_bullish_divergence, cvd_bearish_divergence = self._compute_cvd_divergence()

        tfi_60s = float(snapshot.aggtrades_bucket_60s.get("tfi", 0.0))
        force_order_rate_60s = len(snapshot.force_order_events_60s) / 60.0
        self._force_order_rate_history.append(force_order_rate_60s)
        force_order_spike = self._is_force_order_spike(force_order_rate_60s)
        force_order_decreasing = self._is_force_order_decreasing()

        return Features(
            schema_version=schema_version,
            config_hash=config_hash,
            timestamp=timestamp,
            atr_15m=atr_15m,
            atr_4h=atr_4h,
            atr_4h_norm=atr_4h_norm,
            ema50_4h=ema50_4h,
            ema200_4h=ema200_4h,
            equal_lows=equal_lows,
            equal_highs=equal_highs,
            sweep_detected=sweep_detected,
            reclaim_detected=reclaim_detected,
            sweep_level=sweep_level,
            sweep_depth_pct=sweep_depth_pct,
            sweep_side=sweep_side,
            close_vs_reclaim_buffer_atr=close_vs_reclaim_buffer_atr,
            wick_vs_min_atr=wick_vs_min_atr,
            sweep_vs_buffer_atr=sweep_vs_buffer_atr,
            funding_8h=funding_8h,
            funding_sma3=funding_sma3,
            funding_sma9=funding_sma9,
            funding_pct_60d=funding_pct_60d,
            oi_value=oi_value,
            oi_zscore_60d=oi_zscore_60d,
            oi_delta_pct=oi_delta_pct,
            cvd_15m=cvd_15m,
            cvd_bullish_divergence=cvd_bullish_divergence,
            cvd_bearish_divergence=cvd_bearish_divergence,
            tfi_60s=tfi_60s,
            force_order_rate_60s=force_order_rate_60s,
            force_order_spike=force_order_spike,
            force_order_decreasing=force_order_decreasing,
            passive_etf_bias_5d=snapshot.etf_bias_daily,
        )

    def _funding_window_rates(self, funding_history: list[dict], now: datetime) -> list[float]:
        window_start = now - timedelta(days=self.config.funding_window_days)
        values: list[float] = []
        for row in funding_history:
            ts = row.get("funding_time")
            if isinstance(ts, datetime):
                ts_utc = ts.astimezone(timezone.utc)
                if ts_utc >= window_start:
                    values.append(float(row.get("funding_rate", 0.0)))
        if not values:
            values = [float(row.get("funding_rate", 0.0)) for row in funding_history]
        return values

    def _compute_oi_stats(self, oi_value: float, now: datetime) -> tuple[float, float, float]:
        self._oi_history.append((now, float(oi_value)))
        threshold = now - timedelta(days=self.config.oi_z_window_days)
        while self._oi_history and self._oi_history[0][0] < threshold:
            self._oi_history.popleft()

        values = [value for _, value in self._oi_history]
        prev = values[-2] if len(values) >= 2 else oi_value
        delta_pct = 0.0 if prev == 0 else (oi_value - prev) / prev
        return float(oi_value), zscore(values, float(oi_value)), delta_pct

    def _compute_cvd_divergence(self) -> tuple[bool, bool]:
        window = max(int(self.config.cvd_divergence_window_bars), 3)
        if len(self._cvd_price_history) < window:
            return False, False

        recent = list(self._cvd_price_history)[-window:]
        prices = [price for _, price, _ in recent]
        rolling_cvd: list[float] = []
        running_cvd = 0.0
        for _, _, cvd_value in recent:
            running_cvd += cvd_value
            rolling_cvd.append(running_cvd)

        previous_prices = prices[:-1]
        if not previous_prices:
            return False, False

        prev_high_idx = max(range(len(previous_prices)), key=lambda idx: previous_prices[idx])
        prev_low_idx = min(range(len(previous_prices)), key=lambda idx: previous_prices[idx])
        current_price = prices[-1]
        current_cvd = rolling_cvd[-1]
        prev_price_high = previous_prices[prev_high_idx]
        prev_price_low = previous_prices[prev_low_idx]
        prev_cvd_at_high = rolling_cvd[prev_high_idx]
        prev_cvd_at_low = rolling_cvd[prev_low_idx]

        bullish = current_price < prev_price_low and current_cvd > prev_cvd_at_low
        bearish = current_price > prev_price_high and current_cvd < prev_cvd_at_high
        return bullish, bearish

    def _is_force_order_spike(self, current_rate: float) -> bool:
        history = list(self._force_order_rate_history)
        if len(history) < 6:
            return False
        baseline = history[:-1]
        avg = _mean(baseline)
        sd = _std(baseline)
        if sd == 0:
            return current_rate > avg and current_rate > 0
        return current_rate > (avg + 2 * sd)

    def _is_force_order_decreasing(self) -> bool:
        history = list(self._force_order_rate_history)
        if len(history) < 3:
            return False
        return history[-1] < history[-2] < history[-3]
