from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RUNTIME_MIN_HITS = 3
CLUSTER_PREVIEW_LIMIT = 5
LEVEL_PREVIEW_LIMIT = 8


@dataclass(slots=True)
class ClusterSummary:
    mean: float
    hits: int
    minimum: float
    maximum: float
    qualifies: bool


@dataclass(slots=True)
class LevelCheck:
    side: str
    level: float
    sweep_threshold: float
    reclaim_threshold: float
    extreme_price: float
    close_price: float
    wick_size: float
    wick_min: float
    swept: bool
    reclaimed: bool
    wick_ok: bool
    depth_pct: float


@dataclass(slots=True)
class DetectionDiagnostic:
    recent_15m_count: int
    atr_15m: float
    atr_4h: float
    level_tolerance: float
    sweep_buffer: float
    reclaim_buffer: float
    wick_min: float
    equal_lows: list[float]
    equal_highs: list[float]
    low_clusters: list[ClusterSummary]
    high_clusters: list[ClusterSummary]
    low_checks: list[LevelCheck]
    high_checks: list[LevelCheck]
    runtime_match: LevelCheck | None


@dataclass(slots=True)
class GateSummary:
    lines: list[str]
    active_blocker: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose live feature detection using the current runtime "
            "feature settings."
        )
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="Override symbol. Defaults to settings.strategy.symbol.",
    )
    return parser.parse_args(argv)


def _build_proxy_transport(settings: Any) -> Any:
    from data.proxy_transport import ProxyTransport

    if not settings.proxy.proxy_enabled or not settings.proxy.proxy_url:
        return None
    return ProxyTransport(
        proxy_url=settings.proxy.proxy_url,
        proxy_type=settings.proxy.proxy_type,
        sticky_minutes=settings.proxy.sticky_minutes,
        failover_list=settings.proxy.failover_list,
    )


def _build_rest_client(settings: Any) -> Any:
    from data.rest_client import BinanceFuturesRestClient, RestClientConfig

    proxy_transport = _build_proxy_transport(settings)
    return BinanceFuturesRestClient(
        RestClientConfig(
            base_url=settings.exchange.futures_rest_base_url,
            timeout_seconds=settings.execution.rest_timeout_seconds,
            max_retries=3,
            retry_backoff_seconds=0.75,
            api_key=settings.exchange.api_key,
            api_secret=settings.exchange.api_secret,
            recv_window_ms=settings.exchange.recv_window_ms,
            proxy_transport=proxy_transport,
        )
    )


def _build_feature_config(settings: Any) -> Any:
    from core.feature_engine import FeatureEngineConfig

    strategy = settings.strategy
    return FeatureEngineConfig(
        atr_period=strategy.atr_period,
        ema_fast=strategy.ema_fast,
        ema_slow=strategy.ema_slow,
        equal_level_lookback=strategy.equal_level_lookback,
        equal_level_tol_atr=strategy.equal_level_tol_atr,
        sweep_buf_atr=strategy.sweep_buf_atr,
        reclaim_buf_atr=strategy.reclaim_buf_atr,
        wick_min_atr=strategy.wick_min_atr,
        funding_window_days=strategy.funding_window_days,
        oi_z_window_days=strategy.oi_z_window_days,
    )


def _open_bias_connection(settings: Any) -> sqlite3.Connection | None:
    from storage.db import connect_readonly

    if settings.storage is None:
        return None
    db_path = settings.storage.db_path
    if not db_path.exists():
        return None
    return connect_readonly(db_path)


def _cluster_levels(levels: list[float], tolerance: float) -> list[ClusterSummary]:
    if not levels:
        return []
    sorted_levels = sorted(float(value) for value in levels)
    clusters: list[list[float]] = []
    current_cluster: list[float] = [sorted_levels[0]]
    for level in sorted_levels[1:]:
        if abs(level - current_cluster[-1]) <= tolerance:
            current_cluster.append(level)
        else:
            clusters.append(current_cluster)
            current_cluster = [level]
    clusters.append(current_cluster)
    summaries = [
        ClusterSummary(
            mean=round(sum(cluster) / len(cluster), 2),
            hits=len(cluster),
            minimum=min(cluster),
            maximum=max(cluster),
            qualifies=len(cluster) >= RUNTIME_MIN_HITS,
        )
        for cluster in clusters
    ]
    summaries.sort(key=lambda item: (-item.hits, item.mean))
    return summaries


def _evaluate_levels(
    *,
    side: str,
    levels: list[float],
    latest_candle: dict,
    atr_15m: float,
    config: Any,
) -> list[LevelCheck]:
    open_price = float(latest_candle["open"])
    close_price = float(latest_candle["close"])
    high_price = float(latest_candle["high"])
    low_price = float(latest_candle["low"])
    body_low = min(open_price, close_price)
    body_high = max(open_price, close_price)
    sweep_buffer = config.sweep_buf_atr * atr_15m
    reclaim_buffer = config.reclaim_buf_atr * atr_15m
    wick_min = config.wick_min_atr * atr_15m

    checks: list[LevelCheck] = []
    for level in levels:
        if side == "LOW":
            sweep_threshold = level - sweep_buffer
            reclaim_threshold = level + reclaim_buffer
            extreme_price = low_price
            wick_size = body_low - low_price
            swept = low_price < sweep_threshold
            reclaimed = close_price > reclaim_threshold
            depth_pct = abs(level - low_price) / level if level else 0.0
        else:
            sweep_threshold = level + sweep_buffer
            reclaim_threshold = level - reclaim_buffer
            extreme_price = high_price
            wick_size = high_price - body_high
            swept = high_price > sweep_threshold
            reclaimed = close_price < reclaim_threshold
            depth_pct = abs(high_price - level) / level if level else 0.0
        checks.append(
            LevelCheck(
                side=side,
                level=float(level),
                sweep_threshold=float(sweep_threshold),
                reclaim_threshold=float(reclaim_threshold),
                extreme_price=float(extreme_price),
                close_price=float(close_price),
                wick_size=float(wick_size),
                wick_min=float(wick_min),
                swept=bool(swept),
                reclaimed=bool(reclaimed),
                wick_ok=bool(wick_size >= wick_min),
                depth_pct=float(depth_pct),
            )
        )
    return checks


def _find_runtime_match(low_checks: list[LevelCheck], high_checks: list[LevelCheck]) -> LevelCheck | None:
    for check in low_checks:
        if check.swept:
            return check
    for check in high_checks:
        if check.swept:
            return check
    return None


def _build_diagnostic(snapshot: Any, config: Any) -> DetectionDiagnostic:
    from core.feature_engine import compute_atr, detect_equal_levels

    atr_15m = compute_atr(snapshot.candles_15m, config.atr_period)
    atr_4h = compute_atr(snapshot.candles_4h, config.atr_period)
    recent_15m = snapshot.candles_15m[-config.equal_level_lookback :] if snapshot.candles_15m else []
    lows = [float(candle["low"]) for candle in recent_15m]
    highs = [float(candle["high"]) for candle in recent_15m]
    level_tolerance = atr_15m * config.equal_level_tol_atr if atr_15m > 0 else 0.0
    equal_lows = detect_equal_levels(lows, tolerance=level_tolerance, min_hits=RUNTIME_MIN_HITS)
    equal_highs = detect_equal_levels(highs, tolerance=level_tolerance, min_hits=RUNTIME_MIN_HITS)
    latest_candle = snapshot.candles_15m[-1] if snapshot.candles_15m else {}
    low_checks = _evaluate_levels(
        side="LOW",
        levels=equal_lows,
        latest_candle=latest_candle,
        atr_15m=atr_15m,
        config=config,
    )
    high_checks = _evaluate_levels(
        side="HIGH",
        levels=equal_highs,
        latest_candle=latest_candle,
        atr_15m=atr_15m,
        config=config,
    )
    return DetectionDiagnostic(
        recent_15m_count=len(recent_15m),
        atr_15m=float(atr_15m),
        atr_4h=float(atr_4h),
        level_tolerance=float(level_tolerance),
        sweep_buffer=float(config.sweep_buf_atr * atr_15m),
        reclaim_buffer=float(config.reclaim_buf_atr * atr_15m),
        wick_min=float(config.wick_min_atr * atr_15m),
        equal_lows=equal_lows,
        equal_highs=equal_highs,
        low_clusters=_cluster_levels(lows, level_tolerance),
        high_clusters=_cluster_levels(highs, level_tolerance),
        low_checks=low_checks,
        high_checks=high_checks,
        runtime_match=_find_runtime_match(low_checks, high_checks),
    )


def _fmt_timestamp(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    return value.astimezone(timezone.utc).isoformat()


def _fmt_float(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _fmt_list(values: list[float], *, limit: int = LEVEL_PREVIEW_LIMIT, digits: int = 2) -> str:
    if not values:
        return "[]"
    shown = ", ".join(f"{value:.{digits}f}" for value in values[:limit])
    if len(values) <= limit:
        return f"[{shown}]"
    return f"[{shown}, ... (+{len(values) - limit} more)]"


def _sweep_margin(check: LevelCheck) -> float:
    if check.side == "LOW":
        return check.sweep_threshold - check.extreme_price
    return check.extreme_price - check.sweep_threshold


def _reclaim_margin(check: LevelCheck) -> float:
    if check.side == "LOW":
        return check.close_price - check.reclaim_threshold
    return check.reclaim_threshold - check.close_price


def _wick_margin(check: LevelCheck) -> float:
    return check.wick_size - check.wick_min


def _closest_sweep_miss(checks: list[LevelCheck]) -> LevelCheck | None:
    misses = [check for check in checks if not check.swept]
    if not misses:
        return None
    return min(misses, key=lambda item: abs(_sweep_margin(item)))


def _describe_clusters(name: str, clusters: list[ClusterSummary]) -> list[str]:
    if not clusters:
        return [f"{name}: none"]
    lines = [f"{name}: top_{min(len(clusters), CLUSTER_PREVIEW_LIMIT)}"]
    for index, cluster in enumerate(clusters[:CLUSTER_PREVIEW_LIMIT], start=1):
        lines.append(
            "  "
            f"{index}. mean={_fmt_float(cluster.mean)} hits={cluster.hits} "
            f"range=[{_fmt_float(cluster.minimum)}, {_fmt_float(cluster.maximum)}] "
            f"qualifies={'yes' if cluster.qualifies else 'no'}"
        )
    return lines


def _describe_side(side: str, checks: list[LevelCheck]) -> list[str]:
    if not checks:
        return [f"{side}: no qualifying equal levels after min_hits={RUNTIME_MIN_HITS}"]
    lines = [f"{side}: qualifying_levels={len(checks)} preview={_fmt_list([check.level for check in checks])}"]
    swept = next((check for check in checks if check.swept), None)
    if swept is not None:
        lines.append(
            f"{side}: first_swept_level={_fmt_float(swept.level)} sweep_margin={_fmt_float(_sweep_margin(swept), 4)} "
            f"reclaim_margin={_fmt_float(_reclaim_margin(swept), 4)} wick_margin={_fmt_float(_wick_margin(swept), 4)}"
        )
        return lines
    closest_miss = _closest_sweep_miss(checks)
    if closest_miss is not None:
        lines.append(
            f"{side}: closest_sweep_miss_level={_fmt_float(closest_miss.level)} "
            f"actual_extreme={_fmt_float(closest_miss.extreme_price)} "
            f"required_threshold={_fmt_float(closest_miss.sweep_threshold)} "
            f"miss_margin={_fmt_float(abs(_sweep_margin(closest_miss)), 4)}"
        )
    return lines


def _build_gate_summary(features: Any, diagnostic: DetectionDiagnostic) -> GateSummary:
    lines: list[str] = []
    if not diagnostic.equal_lows and not diagnostic.equal_highs:
        lines.append(
            "No qualifying equal lows or equal highs formed within the current "
            "ATR-based tolerance and min_hits gate."
        )
        return GateSummary(lines=lines, active_blocker="equal_level_detection")

    if diagnostic.runtime_match is None:
        lines.append(
            "Latest 15m candle did not breach any qualifying equal level beyond "
            "the sweep buffer."
        )
        low_miss = _closest_sweep_miss(diagnostic.low_checks)
        high_miss = _closest_sweep_miss(diagnostic.high_checks)
        if low_miss is not None:
            lines.append(
                f"LOW closest miss: level={_fmt_float(low_miss.level)} "
                f"low={_fmt_float(low_miss.extreme_price)} "
                f"threshold={_fmt_float(low_miss.sweep_threshold)} "
                f"miss_by={_fmt_float(abs(_sweep_margin(low_miss)), 4)}"
            )
        if high_miss is not None:
            lines.append(
                f"HIGH closest miss: level={_fmt_float(high_miss.level)} "
                f"high={_fmt_float(high_miss.extreme_price)} "
                f"threshold={_fmt_float(high_miss.sweep_threshold)} "
                f"miss_by={_fmt_float(abs(_sweep_margin(high_miss)), 4)}"
            )
        return GateSummary(lines=lines, active_blocker="sweep_detected")

    match = diagnostic.runtime_match
    lines.append(
        f"Runtime matched {match.side} sweep on level={_fmt_float(match.level)} "
        f"with depth_pct={_fmt_float(match.depth_pct, 6)}."
    )
    lines.append(
        f"Sweep margin={_fmt_float(_sweep_margin(match), 4)} "
        f"reclaim_margin={_fmt_float(_reclaim_margin(match), 4)} "
        f"wick_margin={_fmt_float(_wick_margin(match), 4)}"
    )
    if not match.reclaimed and not match.wick_ok:
        lines.append(
            f"Reclaim failed because close={_fmt_float(match.close_price)} did "
            f"not clear reclaim_threshold={_fmt_float(match.reclaim_threshold)}."
        )
        lines.append(
            f"Wick failed because wick_size={_fmt_float(match.wick_size)} is "
            f"below wick_min={_fmt_float(match.wick_min)}."
        )
        return GateSummary(lines=lines, active_blocker="reclaim_detected")
    if not match.reclaimed:
        lines.append(
            f"Reclaim failed because close={_fmt_float(match.close_price)} did "
            f"not clear reclaim_threshold={_fmt_float(match.reclaim_threshold)}."
        )
        return GateSummary(lines=lines, active_blocker="reclaim_detected")
    if not match.wick_ok:
        lines.append(
            f"Wick filter failed because wick_size={_fmt_float(match.wick_size)} "
            f"is below wick_min={_fmt_float(match.wick_min)}."
        )
        return GateSummary(lines=lines, active_blocker="reclaim_detected")
    lines.append("Sweep gate passed and reclaim gate passed for the matched level.")
    return GateSummary(lines=lines, active_blocker="none")


def _print_section(title: str) -> None:
    print()
    print(f"[{title}]")


def _print_report(
    *,
    settings: Any,
    symbol: str,
    snapshot: Any,
    feature_config: Any,
    features: Any,
    diagnostic: DetectionDiagnostic,
    db_attached: bool,
) -> None:
    latest_15m = snapshot.candles_15m[-1] if snapshot.candles_15m else None
    latest_1h = snapshot.candles_1h[-1] if snapshot.candles_1h else None
    latest_4h = snapshot.candles_4h[-1] if snapshot.candles_4h else None
    gate_summary = _build_gate_summary(features, diagnostic)
    manual_sweep_detected = diagnostic.runtime_match is not None
    manual_reclaim_detected = bool(
        diagnostic.runtime_match
        and diagnostic.runtime_match.reclaimed
        and diagnostic.runtime_match.wick_ok
    )
    consistency = (
        manual_sweep_detected == features.sweep_detected
        and manual_reclaim_detected == features.reclaim_detected
    )

    print("=== FEATURE DETECTION DIAGNOSTIC ===")
    print(f"generated_at_utc: {_fmt_timestamp(datetime.now(timezone.utc))}")
    print(f"symbol: {symbol}")
    print("settings_profile: live")
    print(f"mode_resolved: {settings.mode.value}")
    print(f"config_hash: {settings.config_hash}")

    _print_section("DATA_SOURCE")
    print(f"rest_base_url: {settings.exchange.futures_rest_base_url}")
    print(f"proxy_enabled: {'yes' if settings.proxy.proxy_enabled and settings.proxy.proxy_url else 'no'}")
    print(f"db_bias_context_attached: {'yes' if db_attached else 'no'}")
    print("market_snapshot_source: REST klines + REST funding/open interest + REST aggTrades fallback")
    print(
        "force_order_window_source: websocket unavailable in this one-off "
        "diagnostic, so force_order_events_60s=0"
    )

    _print_section("SNAPSHOT")
    print(f"snapshot_timestamp_utc: {_fmt_timestamp(snapshot.timestamp)}")
    print(f"price_mid: {_fmt_float(snapshot.price)}")
    print(f"candles_15m_count: {len(snapshot.candles_15m)}")
    print(f"candles_1h_count: {len(snapshot.candles_1h)}")
    print(f"candles_4h_count: {len(snapshot.candles_4h)}")
    print(f"funding_count: {len(snapshot.funding_history)}")
    print(f"force_order_events_60s_count: {len(snapshot.force_order_events_60s)}")
    if latest_15m is not None:
        print(f"latest_15m_open_utc: {_fmt_timestamp(latest_15m['open_time'])}")
        print(f"latest_15m_close_utc: {_fmt_timestamp(latest_15m['open_time'] + timedelta(minutes=15))}")
        print(
            "latest_15m_ohlc: "
            f"O={_fmt_float(float(latest_15m['open']))} "
            f"H={_fmt_float(float(latest_15m['high']))} "
            f"L={_fmt_float(float(latest_15m['low']))} "
            f"C={_fmt_float(float(latest_15m['close']))}"
        )
    if latest_1h is not None:
        print(f"latest_1h_open_utc: {_fmt_timestamp(latest_1h['open_time'])}")
    if latest_4h is not None:
        print(f"latest_4h_open_utc: {_fmt_timestamp(latest_4h['open_time'])}")

    _print_section("FEATURE_CONFIG")
    print(f"equal_level_lookback: {feature_config.equal_level_lookback}")
    print(f"equal_level_tol_atr: {_fmt_float(feature_config.equal_level_tol_atr, 6)}")
    print(f"min_hits_runtime: {RUNTIME_MIN_HITS}")
    print(f"sweep_buf_atr: {_fmt_float(feature_config.sweep_buf_atr, 6)}")
    print(f"reclaim_buf_atr: {_fmt_float(feature_config.reclaim_buf_atr, 6)}")
    print(f"wick_min_atr: {_fmt_float(feature_config.wick_min_atr, 6)}")
    print(f"atr_period: {feature_config.atr_period}")

    _print_section("INTERMEDIATE_STATE")
    print(f"atr_15m: {_fmt_float(diagnostic.atr_15m, 6)}")
    print(f"atr_4h: {_fmt_float(diagnostic.atr_4h, 6)}")
    print(f"recent_15m_bars_used: {diagnostic.recent_15m_count}")
    print(f"level_tolerance_abs: {_fmt_float(diagnostic.level_tolerance, 6)}")
    print(f"sweep_buffer_abs: {_fmt_float(diagnostic.sweep_buffer, 6)}")
    print(f"reclaim_buffer_abs: {_fmt_float(diagnostic.reclaim_buffer, 6)}")
    print(f"wick_min_abs: {_fmt_float(diagnostic.wick_min, 6)}")
    print(f"equal_lows_count: {len(diagnostic.equal_lows)}")
    print(f"equal_highs_count: {len(diagnostic.equal_highs)}")
    print(f"equal_lows_preview: {_fmt_list(diagnostic.equal_lows)}")
    print(f"equal_highs_preview: {_fmt_list(diagnostic.equal_highs)}")
    for line in _describe_clusters("low_clusters", diagnostic.low_clusters):
        print(line)
    for line in _describe_clusters("high_clusters", diagnostic.high_clusters):
        print(line)
    for line in _describe_side("LOW", diagnostic.low_checks):
        print(line)
    for line in _describe_side("HIGH", diagnostic.high_checks):
        print(line)

    _print_section("GATE_RESULT")
    print(f"sweep_detected: {features.sweep_detected}")
    print(f"reclaim_detected: {features.reclaim_detected}")
    print(f"sweep_side: {features.sweep_side}")
    print(f"sweep_level: {_fmt_float(features.sweep_level)}")
    print(f"sweep_depth_pct: {_fmt_float(features.sweep_depth_pct, 6)}")
    print(f"manual_runtime_consistency: {'yes' if consistency else 'no'}")
    print(f"active_blocker: {gate_summary.active_blocker}")
    print("why:")
    for line in gate_summary.lines:
        print(f"- {line}")


def main(argv: list[str] | None = None) -> int:
    from core.feature_engine import FeatureEngine
    from data.market_data import MarketDataAssembler
    from settings import load_settings

    args = parse_args(argv)
    settings = load_settings(profile="live")
    symbol = str(args.symbol or settings.strategy.symbol).upper()
    db_connection = _open_bias_connection(settings)
    try:
        rest_client = _build_rest_client(settings)
        assembler = MarketDataAssembler(
            rest_client=rest_client,
            websocket_client=None,
            db_connection=db_connection,
        )
        snapshot = assembler.build_snapshot(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc).replace(second=0, microsecond=0),
        )
        feature_config = _build_feature_config(settings)
        feature_engine = FeatureEngine(feature_config)
        features = feature_engine.compute(
            snapshot=snapshot,
            schema_version=settings.schema_version,
            config_hash=settings.config_hash,
        )
        diagnostic = _build_diagnostic(snapshot, feature_config)
        _print_report(
            settings=settings,
            symbol=symbol,
            snapshot=snapshot,
            feature_config=feature_config,
            features=features,
            diagnostic=diagnostic,
            db_attached=db_connection is not None,
        )
        return 0
    except Exception as exc:
        print("=== FEATURE DETECTION DIAGNOSTIC ===")
        print("status: error")
        print(f"error_type: {type(exc).__name__}")
        print(f"error: {exc}")
        return 1
    finally:
        if db_connection is not None:
            db_connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
