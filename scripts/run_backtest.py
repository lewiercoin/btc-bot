from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtest.backtest_runner import BacktestConfig, BacktestRunner
from backtest.replay_loader import ReplayLoader, ReplayLoaderConfig
from core.feature_engine import FeatureEngine, FeatureEngineConfig
from research.analyze_trades import AnalyzeTradesConfig, analyze_closed_trades
from settings import load_settings
from storage.db import connect, init_db


class _SignalCountingProxy:
    def __init__(self, wrapped: Any, runner: "InstrumentedBacktestRunner") -> None:
        self._wrapped = wrapped
        self._runner = runner

    def _is_regime_blocked(self, features: Any, regime: Any) -> bool:
        # Mirror SignalEngine prechecks to count explicit regime whitelist rejections only.
        if not bool(getattr(features, "sweep_detected", False)):
            return False
        if not bool(getattr(features, "reclaim_detected", False)):
            return False
        if getattr(features, "sweep_level", None) is None:
            return False
        sweep_depth_pct = getattr(features, "sweep_depth_pct", None)
        min_depth = getattr(self._wrapped.config, "min_sweep_depth_pct", None)
        if sweep_depth_pct is not None and min_depth is not None and float(sweep_depth_pct) < float(min_depth):
            return False

        infer_direction = getattr(self._wrapped, "_infer_direction", None)
        direction_allowed = getattr(self._wrapped, "_is_direction_allowed_for_regime", None)
        if infer_direction is None or direction_allowed is None:
            return False
        direction = infer_direction(features)
        if direction is None:
            return False
        return not bool(direction_allowed(direction=direction, regime=regime))

    def generate(self, features: Any, regime: Any) -> Any:
        if self._is_regime_blocked(features, regime):
            self._runner.signals_regime_blocked += 1
            self._runner.signals_generated += 1
            return None
        candidate = self._wrapped.generate(features, regime)
        if candidate is not None:
            self._runner.signals_generated += 1
            self._runner.signal_regime_counts[regime.value] = self._runner.signal_regime_counts.get(regime.value, 0) + 1
        return candidate

    def __getattr__(self, item: str) -> Any:
        return getattr(self._wrapped, item)


class _GovernanceCountingProxy:
    def __init__(self, wrapped: Any, runner: "InstrumentedBacktestRunner") -> None:
        self._wrapped = wrapped
        self._runner = runner

    def evaluate(self, candidate: Any) -> Any:
        decision = self._wrapped.evaluate(candidate)
        if not bool(getattr(decision, "approved", False)):
            self._runner.signals_governance_rejected += 1
        return decision

    def __getattr__(self, item: str) -> Any:
        return getattr(self._wrapped, item)


class _RiskCountingProxy:
    def __init__(self, wrapped: Any, runner: "InstrumentedBacktestRunner") -> None:
        self._wrapped = wrapped
        self._runner = runner

    def evaluate(self, signal: Any, equity: float, open_positions: int) -> Any:
        decision = self._wrapped.evaluate(signal, equity=equity, open_positions=open_positions)
        if not bool(getattr(decision, "allowed", False)):
            self._runner.signals_risk_rejected += 1
        return decision

    def __getattr__(self, item: str) -> Any:
        return getattr(self._wrapped, item)


class InstrumentedBacktestRunner(BacktestRunner):
    def __init__(self, connection: sqlite3.Connection, **kwargs: Any) -> None:
        super().__init__(connection, **kwargs)
        self.signals_generated = 0
        self.signals_regime_blocked = 0
        self.signals_governance_rejected = 0
        self.signals_risk_rejected = 0
        self.signal_regime_counts: dict[str, int] = {}

    def _build_engines(self):  # type: ignore[override]
        feature_engine, regime_engine, signal_engine, governance, risk_engine = super()._build_engines()
        return (
            feature_engine,
            regime_engine,
            _SignalCountingProxy(signal_engine, self),
            _GovernanceCountingProxy(governance, self),
            _RiskCountingProxy(risk_engine, self),
        )


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_date_only(raw: str) -> bool:
    token = raw.strip()
    return "T" not in token and " " not in token


def _parse_iso_datetime(raw: str, *, is_end: bool) -> datetime:
    parsed = datetime.fromisoformat(raw)
    value = _to_utc(parsed)
    if is_end and _is_date_only(raw):
        value += timedelta(days=1)
    return value


def _count_bars(connection: sqlite3.Connection, *, symbol: str, config: BacktestConfig) -> int:
    loader = ReplayLoader(
        connection,
        ReplayLoaderConfig(
            candles_15m_lookback=config.candles_15m_lookback,
            candles_1h_lookback=config.candles_1h_lookback,
            candles_4h_lookback=config.candles_4h_lookback,
            funding_lookback=config.funding_lookback,
        ),
    )
    count = 0
    for _ in loader.iter_snapshots(start_date=config.start_date, end_date=config.end_date, symbol=symbol):
        count += 1
    return count


def _zero_trade_diagnostics(
    connection: sqlite3.Connection,
    *,
    settings,
    backtest_config: BacktestConfig,
    symbol: str,
) -> list[str]:
    loader = ReplayLoader(
        connection,
        ReplayLoaderConfig(
            candles_15m_lookback=backtest_config.candles_15m_lookback,
            candles_1h_lookback=backtest_config.candles_1h_lookback,
            candles_4h_lookback=backtest_config.candles_4h_lookback,
            funding_lookback=backtest_config.funding_lookback,
        ),
    )
    engine = FeatureEngine(
        FeatureEngineConfig(
            atr_period=settings.strategy.atr_period,
            ema_fast=settings.strategy.ema_fast,
            ema_slow=settings.strategy.ema_slow,
            equal_level_lookback=settings.strategy.equal_level_lookback,
            equal_level_tol_atr=settings.strategy.equal_level_tol_atr,
            sweep_buf_atr=settings.strategy.sweep_buf_atr,
            reclaim_buf_atr=settings.strategy.reclaim_buf_atr,
            wick_min_atr=settings.strategy.wick_min_atr,
            funding_window_days=settings.strategy.funding_window_days,
            oi_z_window_days=settings.strategy.oi_z_window_days,
        )
    )

    bars = 0
    missing_agg_60s = 0
    missing_agg_15m = 0
    zero_oi = 0
    empty_force_orders = 0

    numeric_fields = (
        "cvd_15m",
        "tfi_60s",
        "force_order_rate_60s",
        "oi_value",
        "oi_zscore_60d",
        "oi_delta_pct",
        "funding_8h",
        "sweep_depth_pct",
    )
    bool_fields = (
        "sweep_detected",
        "reclaim_detected",
        "force_order_spike",
        "cvd_bullish_divergence",
        "cvd_bearish_divergence",
    )
    numeric_zero_counts = {name: 0 for name in numeric_fields}
    bool_true_counts = {name: 0 for name in bool_fields}

    for snapshot in loader.iter_snapshots(start_date=backtest_config.start_date, end_date=backtest_config.end_date, symbol=symbol):
        bars += 1
        if not snapshot.aggtrades_bucket_60s:
            missing_agg_60s += 1
        if not snapshot.aggtrades_bucket_15m:
            missing_agg_15m += 1
        if float(snapshot.open_interest) == 0.0:
            zero_oi += 1
        if not snapshot.force_order_events_60s:
            empty_force_orders += 1

        features = engine.compute(
            snapshot=snapshot,
            schema_version=settings.schema_version,
            config_hash=settings.config_hash,
        )
        for field in numeric_fields:
            value = getattr(features, field)
            if value is None or abs(float(value)) < 1e-12:
                numeric_zero_counts[field] += 1
        for field in bool_fields:
            if bool(getattr(features, field)):
                bool_true_counts[field] += 1

    if bars == 0:
        return ["No 15m bars in selected range. Check candles(timeframe='15m') coverage."]

    lines: list[str] = []
    lines.append(f"bars={bars}")
    lines.append(
        "snapshot gaps: "
        f"agg_60s_missing={missing_agg_60s}/{bars}, "
        f"agg_15m_missing={missing_agg_15m}/{bars}, "
        f"open_interest_zero={zero_oi}/{bars}, "
        f"force_orders_empty={empty_force_orders}/{bars}"
    )
    high_zero = sorted(
        ((name, count / bars) for name, count in numeric_zero_counts.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    lines.append(
        "numeric zero/none ratios: "
        + ", ".join(f"{name}={ratio:.1%}" for name, ratio in high_zero if ratio >= 0.5)
    )
    low_true = sorted(
        ((name, count / bars) for name, count in bool_true_counts.items()),
        key=lambda item: item[1],
    )
    lines.append(
        "boolean true ratios: "
        + ", ".join(f"{name}={ratio:.1%}" for name, ratio in low_true)
    )
    return lines


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, float):
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        if math.isnan(value):
            return "nan"
    return value


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run backtest on persisted SQLite history.")
    parser.add_argument("--start-date", required=True, help="Inclusive start datetime (ISO-8601, UTC).")
    parser.add_argument("--end-date", required=True, help="Exclusive end datetime (ISO-8601, UTC). Date-only values are treated as next-day exclusive.")
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    parser.add_argument(
        "--compare-uptrend-pullback",
        action="store_true",
        help="Run the same backtest twice with allow_uptrend_pullback OFF then ON and print the delta.",
    )
    parser.add_argument(
        "--evaluate-uptrend-pullback",
        action="store_true",
        help="Run the research-only UPTREND pullback evaluation harness and emit a funnel/segmentation report.",
    )
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def _run_backtest_summary(
    conn: sqlite3.Connection,
    *,
    settings,
    run_config: BacktestConfig,
    symbol: str,
) -> dict[str, Any]:
    bars_processed = _count_bars(conn, symbol=symbol, config=run_config)
    runner = InstrumentedBacktestRunner(conn, settings=settings)
    result = runner.run(run_config)

    trades_opened = len(result.trades)
    trades_closed = len(result.trades)
    wins = sum(1 for trade in result.trades if float(trade.pnl_abs) > 0)
    losses = sum(1 for trade in result.trades if float(trade.pnl_abs) < 0)
    breakeven = trades_closed - wins - losses

    return {
        "bars_processed": bars_processed,
        "runner": runner,
        "result": result,
        "trades_opened": trades_opened,
        "trades_closed": trades_closed,
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
    }


def _print_summary(
    conn: sqlite3.Connection,
    *,
    label: str,
    settings,
    run_config: BacktestConfig,
    symbol: str,
    start_ts: datetime,
    end_ts: datetime,
    summary: dict[str, Any],
) -> None:
    runner = summary["runner"]
    perf = summary["result"].performance

    print(f"{label} summary")
    print(f"symbol: {symbol}")
    print(f"range_utc: {start_ts.isoformat()} -> {end_ts.isoformat()}")
    print(f"bars_processed: {summary['bars_processed']}")
    print(f"signals_generated: {runner.signals_generated}")
    print(
        "signal_funnel: "
        f"generated={runner.signals_generated} "
        f"regime_blocked={runner.signals_regime_blocked} "
        f"governance_rejected={runner.signals_governance_rejected} "
        f"risk_rejected={runner.signals_risk_rejected} "
        f"-> trades_opened={summary['trades_opened']}"
    )
    print(f"signal_regime_distribution: {json.dumps(runner.signal_regime_counts, sort_keys=True)}")
    print(f"trades_opened: {summary['trades_opened']}")
    print(f"trades_closed: {summary['trades_closed']}")
    print(f"wins/losses/breakeven: {summary['wins']}/{summary['losses']}/{summary['breakeven']}")
    print(f"pnl_abs: {perf.pnl_abs:.6f}")
    print(f"pnl_r_sum: {perf.pnl_r_sum:.6f}")
    print(f"profit_factor: {perf.profit_factor}")
    print(f"expectancy_r: {perf.expectancy_r:.6f}")
    print(f"max_consecutive_losses: {perf.max_consecutive_losses}")

    if summary["trades_closed"] == 0:
        print("diagnostic: no trades generated")
        for line in _zero_trade_diagnostics(conn, settings=settings, backtest_config=run_config, symbol=symbol):
            print(f"- {line}")


def main() -> None:
    args = _parse_args()
    start_ts = _parse_iso_datetime(str(args.start_date), is_end=False)
    end_ts = _parse_iso_datetime(str(args.end_date), is_end=True)
    if end_ts <= start_ts:
        raise SystemExit("--end-date must be later than --start-date.")

    settings = load_settings()
    assert settings.storage is not None
    symbol = settings.strategy.symbol.upper()

    if args.evaluate_uptrend_pullback:
        if args.compare_uptrend_pullback:
            raise SystemExit("Use either --evaluate-uptrend-pullback or --compare-uptrend-pullback, not both.")
        from research_lab.diagnostics.uptrend_pullback_eval_v1 import run_uptrend_pullback_evaluation

        output_path = args.output_json or Path("research_lab/runs/uptrend_pullback_eval_v1.json")
        run_uptrend_pullback_evaluation(
            source_db_path=settings.storage.db_path,
            start_ts=start_ts,
            end_ts=end_ts,
            output_path=output_path,
            initial_equity=float(args.initial_equity),
        )
        return

    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)
    try:
        run_config = BacktestConfig(
            start_date=start_ts,
            end_date=end_ts,
            initial_equity=float(args.initial_equity),
            symbol=symbol,
        )
        if args.compare_uptrend_pullback:
            base_settings = replace(settings, strategy=replace(settings.strategy, allow_uptrend_pullback=False))
            pullback_settings = replace(settings, strategy=replace(settings.strategy, allow_uptrend_pullback=True))

            off_summary = _run_backtest_summary(conn, settings=base_settings, run_config=run_config, symbol=symbol)
            on_summary = _run_backtest_summary(conn, settings=pullback_settings, run_config=run_config, symbol=symbol)

            _print_summary(
                conn,
                label="UPTREND_PULLBACK_OFF",
                settings=base_settings,
                run_config=run_config,
                symbol=symbol,
                start_ts=start_ts,
                end_ts=end_ts,
                summary=off_summary,
            )
            print("")
            _print_summary(
                conn,
                label="UPTREND_PULLBACK_ON",
                settings=pullback_settings,
                run_config=run_config,
                symbol=symbol,
                start_ts=start_ts,
                end_ts=end_ts,
                summary=on_summary,
            )

            off_perf = off_summary["result"].performance
            on_perf = on_summary["result"].performance
            print("")
            print("UPTREND_PULLBACK delta")
            print(f"signals_generated_delta: {on_summary['runner'].signals_generated - off_summary['runner'].signals_generated}")
            print(
                "uptrend_signal_delta: "
                f"{on_summary['runner'].signal_regime_counts.get('uptrend', 0) - off_summary['runner'].signal_regime_counts.get('uptrend', 0)}"
            )
            print(f"trades_opened_delta: {on_summary['trades_opened'] - off_summary['trades_opened']}")
            print(f"pnl_abs_delta: {on_perf.pnl_abs - off_perf.pnl_abs:.6f}")
            print(f"expectancy_r_delta: {on_perf.expectancy_r - off_perf.expectancy_r:.6f}")

            if args.output_json is not None:
                payload = {
                    "symbol": symbol,
                    "start_ts_utc": start_ts.isoformat(),
                    "end_ts_utc": end_ts.isoformat(),
                    "off": {
                        "allow_uptrend_pullback": False,
                        "bars_processed": off_summary["bars_processed"],
                        "signals_generated": off_summary["runner"].signals_generated,
                        "signal_regime_distribution": off_summary["runner"].signal_regime_counts,
                        "trades_opened": off_summary["trades_opened"],
                        "trades_closed": off_summary["trades_closed"],
                        "performance": asdict(off_perf),
                    },
                    "on": {
                        "allow_uptrend_pullback": True,
                        "bars_processed": on_summary["bars_processed"],
                        "signals_generated": on_summary["runner"].signals_generated,
                        "signal_regime_distribution": on_summary["runner"].signal_regime_counts,
                        "trades_opened": on_summary["trades_opened"],
                        "trades_closed": on_summary["trades_closed"],
                        "performance": asdict(on_perf),
                    },
                    "delta": {
                        "signals_generated": on_summary["runner"].signals_generated - off_summary["runner"].signals_generated,
                        "uptrend_signals": on_summary["runner"].signal_regime_counts.get("uptrend", 0) - off_summary["runner"].signal_regime_counts.get("uptrend", 0),
                        "trades_opened": on_summary["trades_opened"] - off_summary["trades_opened"],
                        "pnl_abs": on_perf.pnl_abs - off_perf.pnl_abs,
                        "expectancy_r": on_perf.expectancy_r - off_perf.expectancy_r,
                    },
                }
                args.output_json.parent.mkdir(parents=True, exist_ok=True)
                args.output_json.write_text(
                    json.dumps(_sanitize_json(payload), indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                print(f"analysis_report_json: {args.output_json}")
            return

        summary = _run_backtest_summary(conn, settings=settings, run_config=run_config, symbol=symbol)
        _print_summary(
            conn,
            label="Backtest",
            settings=settings,
            run_config=run_config,
            symbol=symbol,
            start_ts=start_ts,
            end_ts=end_ts,
            summary=summary,
        )

        if args.output_json is not None:
            result = summary["result"]
            runner = summary["runner"]
            run_trade_ids = tuple(trade.trade_id for trade in result.trades)
            analysis = analyze_closed_trades(
                conn,
                AnalyzeTradesConfig(
                    symbol=symbol,
                    start_ts_utc=start_ts,
                    end_ts_utc=end_ts,
                    trade_ids=run_trade_ids,
                ),
            )
            payload = {
                "symbol": symbol,
                "start_ts_utc": start_ts.isoformat(),
                "end_ts_utc": end_ts.isoformat(),
                "bars_processed": summary["bars_processed"],
                "signals_generated": runner.signals_generated,
                "signal_regime_distribution": runner.signal_regime_counts,
                "signals_regime_blocked": runner.signals_regime_blocked,
                "signals_governance_rejected": runner.signals_governance_rejected,
                "signals_risk_rejected": runner.signals_risk_rejected,
                "trades_opened": summary["trades_opened"],
                "trades_closed": summary["trades_closed"],
                "wins": summary["wins"],
                "losses": summary["losses"],
                "breakeven": summary["breakeven"],
                "performance": asdict(result.performance),
                "analysis": analysis.to_dict(),
            }
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(
                json.dumps(_sanitize_json(payload), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            print(f"analysis_report_json: {args.output_json}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
