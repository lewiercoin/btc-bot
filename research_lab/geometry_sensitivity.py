from __future__ import annotations

import argparse
import dataclasses
import json
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from backtest.backtest_runner import BacktestConfig, BacktestResult
from core.models import TradeLog
from settings import AppSettings, load_settings

from research_lab.constraints import assert_valid
from research_lab.constants import MIN_TRADES_DEFAULT
from research_lab.db_snapshot import verify_required_tables
from research_lab.funnel import InstrumentedBacktestRunner
from research_lab.objective import metrics_from_result
from research_lab.settings_adapter import build_candidate_settings
from research_lab.types import ObjectiveMetrics, SignalFunnel, TrialEvaluation


GEOMETRY_KEYS = (
    "entry_offset_atr",
    "invalidation_offset_atr",
    "min_stop_distance_pct",
    "tp1_atr_mult",
    "min_rr",
)

GEOMETRY_VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "name": "baseline_current",
        "description": "Active settings profile values.",
        "params": {},
    },
    {
        "name": "min_stop_relief_only",
        "description": "Current 0.01/0.01 ATR geometry with lower min stop.",
        "params": {
            "entry_offset_atr": 0.01,
            "invalidation_offset_atr": 0.01,
            "min_stop_distance_pct": 0.0015,
            "tp1_atr_mult": 1.9,
            "min_rr": 1.6,
        },
    },
    {
        "name": "mid_pullback_geometry",
        "description": "Moderate entry/stop separation, lower min stop.",
        "params": {
            "entry_offset_atr": 0.03,
            "invalidation_offset_atr": 0.25,
            "min_stop_distance_pct": 0.0015,
            "tp1_atr_mult": 1.9,
            "min_rr": 1.6,
        },
    },
    {
        "name": "signal_defaults_geometry",
        "description": "SignalConfig-like geometry with experiment min_rr.",
        "params": {
            "entry_offset_atr": 0.05,
            "invalidation_offset_atr": 0.75,
            "min_stop_distance_pct": 0.0015,
            "tp1_atr_mult": 2.5,
            "min_rr": 1.6,
        },
    },
    {
        "name": "signal_defaults_rr21",
        "description": "SignalConfig-like geometry with conservative min_rr.",
        "params": {
            "entry_offset_atr": 0.05,
            "invalidation_offset_atr": 0.75,
            "min_stop_distance_pct": 0.0015,
            "tp1_atr_mult": 2.5,
            "min_rr": 2.1,
        },
    },
    {
        "name": "wide_conservative_geometry",
        "description": "Wider invalidation and target, conservative RR.",
        "params": {
            "entry_offset_atr": 0.10,
            "invalidation_offset_atr": 1.00,
            "min_stop_distance_pct": 0.0020,
            "tp1_atr_mult": 3.0,
            "min_rr": 2.1,
        },
    },
)

SLIPPAGE_STRESS_VARIANT_NAME = "min_stop_relief_only"
SLIPPAGE_STRESS_MULTIPLIERS = (2.0, 3.0)


class _ReadOnlyInstrumentedBacktestRunner(InstrumentedBacktestRunner):
    def _persist_closed_trades(self, closed_records: list[Any]) -> None:
        return None


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_date_only(raw: str) -> bool:
    token = raw.strip()
    return "T" not in token and " " not in token


def _parse_iso_datetime(raw: str, *, is_end: bool) -> datetime:
    parsed = _to_utc(datetime.fromisoformat(raw))
    if is_end and _is_date_only(raw):
        return parsed + timedelta(days=1)
    return parsed


def _open_read_only_connection(source_db_path: Path) -> sqlite3.Connection:
    db_uri = f"file:{source_db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _base_candidate_defaults(base_settings: AppSettings) -> dict[str, Any]:
    defaults = {}
    defaults.update(dataclasses.asdict(base_settings.strategy))
    defaults.update(dataclasses.asdict(base_settings.risk))
    return defaults


def _reject_evaluation(trial_id: str, params: dict[str, Any], reason: str) -> TrialEvaluation:
    return TrialEvaluation(
        trial_id=trial_id,
        params=params,
        metrics=ObjectiveMetrics(
            expectancy_r=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            trades_count=0,
            sharpe_ratio=0.0,
            pnl_abs=0.0,
            win_rate=0.0,
        ),
        funnel=SignalFunnel(
            signals_generated=0,
            signals_regime_blocked=0,
            signals_governance_rejected=0,
            signals_risk_rejected=0,
            signals_executed=0,
        ),
        rejected_reason=reason,
    )


def _variant_trial_id(name: str, params: dict[str, Any], start_date: Any, end_date: Any) -> str:
    payload = json.dumps(
        {"name": name, "params": params, "start_date": str(start_date), "end_date": str(end_date)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"geometry-{name}-{uuid.uuid5(uuid.NAMESPACE_DNS, payload).hex[:10]}"


def _selected_geometry_params(base_settings: AppSettings, overrides: dict[str, Any]) -> dict[str, Any]:
    defaults = _base_candidate_defaults(base_settings)
    defaults.update(overrides)
    return {key: defaults[key] for key in GEOMETRY_KEYS}


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    clipped = min(max(float(q), 0.0), 1.0)
    index = clipped * (len(sorted_values) - 1)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def _trade_distribution(trades: list[TradeLog]) -> dict[str, float]:
    pnl_r = sorted(float(trade.pnl_r) for trade in trades)
    if not pnl_r:
        return {
            "avg_r": 0.0,
            "median_r": 0.0,
            "min_r": 0.0,
            "p10_r": 0.0,
            "p50_r": 0.0,
            "p90_r": 0.0,
            "max_r": 0.0,
        }
    return {
        "avg_r": sum(pnl_r) / len(pnl_r),
        "median_r": _quantile(pnl_r, 0.5),
        "min_r": pnl_r[0],
        "p10_r": _quantile(pnl_r, 0.1),
        "p50_r": _quantile(pnl_r, 0.5),
        "p90_r": _quantile(pnl_r, 0.9),
        "max_r": pnl_r[-1],
    }


def _trade_costs(trades: list[TradeLog]) -> dict[str, float]:
    if not trades:
        return {
            "total_fees": 0.0,
            "total_funding_paid": 0.0,
            "avg_slippage_bps": 0.0,
            "median_slippage_bps": 0.0,
            "fees_to_abs_pnl": 0.0,
            "funding_to_abs_pnl": 0.0,
        }
    slippage = sorted(float(trade.slippage_bps) for trade in trades)
    total_fees = sum(float(trade.fees) for trade in trades)
    total_funding = sum(float(trade.funding_paid) for trade in trades)
    abs_pnl = sum(abs(float(trade.pnl_abs)) for trade in trades)
    return {
        "total_fees": total_fees,
        "total_funding_paid": total_funding,
        "avg_slippage_bps": sum(slippage) / len(slippage),
        "median_slippage_bps": _quantile(slippage, 0.5),
        "fees_to_abs_pnl": total_fees / max(abs_pnl, 1e-8),
        "funding_to_abs_pnl": total_funding / max(abs_pnl, 1e-8),
    }


def _risk_adjusted_metrics(result: BacktestResult) -> dict[str, float]:
    perf = result.performance
    max_dd = float(perf.max_drawdown_pct)
    return {
        "return_over_max_drawdown": float(perf.pnl_abs) / max(max_dd, 1e-8),
        "expectancy_over_max_drawdown": float(perf.expectancy_r) / max(max_dd, 1e-8),
        "max_consecutive_losses": float(perf.max_consecutive_losses),
    }


def _per_regime_breakdown(trades: list[TradeLog]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[TradeLog]] = {}
    for trade in trades:
        grouped.setdefault(str(trade.regime), []).append(trade)

    breakdown: dict[str, dict[str, float]] = {}
    for regime, regime_trades in sorted(grouped.items()):
        pnl_r = [float(trade.pnl_r) for trade in regime_trades]
        pnl_abs = [float(trade.pnl_abs) for trade in regime_trades]
        wins = sum(1 for value in pnl_abs if value > 0)
        gross_profit = sum(value for value in pnl_abs if value > 0)
        gross_loss_abs = abs(sum(value for value in pnl_abs if value < 0))
        breakdown[regime] = {
            "trades_count": float(len(regime_trades)),
            "expectancy_r": sum(pnl_r) / max(len(pnl_r), 1),
            "win_rate": wins / max(len(regime_trades), 1),
            "profit_factor": gross_profit / gross_loss_abs if gross_loss_abs > 0 else (1_000_000.0 if gross_profit > 0 else 0.0),
            "pnl_abs": sum(pnl_abs),
        }
    return breakdown


def _evaluate_geometry_variant(
    conn: sqlite3.Connection,
    *,
    base_settings: AppSettings,
    variant_name: str,
    variant_params: dict[str, Any],
    backtest_config: BacktestConfig,
    min_trades: int,
) -> tuple[TrialEvaluation, BacktestResult | None]:
    full_vector = _base_candidate_defaults(base_settings)
    full_vector.update(variant_params)
    trial_id = _variant_trial_id(variant_name, variant_params, backtest_config.start_date, backtest_config.end_date)

    try:
        assert_valid(full_vector)
    except ValueError as exc:
        return _reject_evaluation(trial_id, dict(variant_params), str(exc)), None

    candidate_settings = build_candidate_settings(base_settings, variant_params)
    runner = _ReadOnlyInstrumentedBacktestRunner(conn, settings=candidate_settings)
    result = runner.run(backtest_config)
    metrics = metrics_from_result(result)
    rejected_reason = None
    if metrics.trades_count < int(min_trades):
        rejected_reason = f"MIN_TRADES_NOT_MET: trades_count={metrics.trades_count} < min_trades={int(min_trades)}"

    return (
        TrialEvaluation(
            trial_id=trial_id,
            params=_selected_geometry_params(base_settings, variant_params),
            metrics=metrics,
            funnel=SignalFunnel(
                signals_generated=runner.signals_generated,
                signals_regime_blocked=runner.signals_regime_blocked,
                signals_governance_rejected=runner.signals_governance_rejected,
                signals_risk_rejected=runner.signals_risk_rejected,
                signals_executed=len(result.trades),
            ),
            rejected_reason=rejected_reason,
            baseline_version=base_settings.config_hash,
        ),
        result,
    )


def _evaluation_to_dict(
    variant: dict[str, Any],
    evaluation: TrialEvaluation,
    result: BacktestResult | None,
    elapsed_seconds: float,
    *,
    slippage_stress_multiplier: float | None = None,
) -> dict[str, Any]:
    metrics = evaluation.metrics
    funnel = evaluation.funnel
    trades = list(result.trades) if result is not None else []
    extended_metrics = {}
    if result is not None:
        extended_metrics = {}
        extended_metrics.update(_risk_adjusted_metrics(result))
        extended_metrics.update(_trade_distribution(trades))
        extended_metrics.update(_trade_costs(trades))
    return {
        "name": variant["name"],
        "description": variant["description"],
        "trial_id": evaluation.trial_id,
        "params": evaluation.params,
        "slippage_stress_multiplier": slippage_stress_multiplier,
        "metrics": {
            "expectancy_r": metrics.expectancy_r,
            "profit_factor": metrics.profit_factor,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "trades_count": metrics.trades_count,
            "sharpe_ratio": metrics.sharpe_ratio,
            "pnl_abs": metrics.pnl_abs,
            "win_rate": metrics.win_rate,
        },
        "funnel": {
            "signals_generated": funnel.signals_generated,
            "signals_regime_blocked": funnel.signals_regime_blocked,
            "signals_governance_rejected": funnel.signals_governance_rejected,
            "signals_risk_rejected": funnel.signals_risk_rejected,
            "signals_executed": funnel.signals_executed,
        },
        "extended_metrics": extended_metrics,
        "per_regime": _per_regime_breakdown(trades),
        "rejected_reason": evaluation.rejected_reason,
        "elapsed_seconds": elapsed_seconds,
    }


def _stress_backtest_config(backtest_config: BacktestConfig, multiplier: float) -> BacktestConfig:
    return dataclasses.replace(
        backtest_config,
        slippage_bps_limit=float(backtest_config.slippage_bps_limit) * float(multiplier),
        slippage_bps_market=float(backtest_config.slippage_bps_market) * float(multiplier),
    )


def run_geometry_sensitivity(
    *,
    base_settings: AppSettings,
    source_db_path: Path,
    backtest_config: BacktestConfig,
    variants: Iterable[dict[str, Any]] = GEOMETRY_VARIANTS,
    min_trades: int = MIN_TRADES_DEFAULT,
    max_variants: int | None = None,
    slippage_stress_multipliers: Iterable[float] = SLIPPAGE_STRESS_MULTIPLIERS,
) -> dict[str, Any]:
    selected_variants = list(variants)
    if max_variants is not None:
        selected_variants = selected_variants[: int(max_variants)]

    started_at = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    conn = _open_read_only_connection(source_db_path)
    try:
        verify_required_tables(conn)
        for variant in selected_variants:
            start = time.perf_counter()
            evaluation, result = _evaluate_geometry_variant(
                conn,
                base_settings=base_settings,
                variant_name=str(variant["name"]),
                variant_params=dict(variant["params"]),
                backtest_config=backtest_config,
                min_trades=min_trades,
            )
            elapsed = time.perf_counter() - start
            results.append(_evaluation_to_dict(variant, evaluation, result, elapsed))

            if str(variant["name"]) == SLIPPAGE_STRESS_VARIANT_NAME:
                for multiplier in slippage_stress_multipliers:
                    start = time.perf_counter()
                    stressed_config = _stress_backtest_config(backtest_config, multiplier)
                    stressed_evaluation, stressed_result = _evaluate_geometry_variant(
                        conn,
                        base_settings=base_settings,
                        variant_name=f"{variant['name']}_slippage_x{float(multiplier):g}",
                        variant_params=dict(variant["params"]),
                        backtest_config=stressed_config,
                        min_trades=min_trades,
                    )
                    elapsed = time.perf_counter() - start
                    results.append(
                        _evaluation_to_dict(
                            {
                                "name": f"{variant['name']}_slippage_x{float(multiplier):g}",
                                "description": f"{variant['description']} Slippage stress x{float(multiplier):g}.",
                                "params": dict(variant["params"]),
                            },
                            stressed_evaluation,
                            stressed_result,
                            elapsed,
                            slippage_stress_multiplier=float(multiplier),
                        )
                    )
    finally:
        conn.close()

    completed_at = datetime.now(timezone.utc)
    ranked = sorted(
        results,
        key=lambda item: (
            -float(item["metrics"]["expectancy_r"]),
            -float(item["metrics"]["profit_factor"]),
            float(item["metrics"]["max_drawdown_pct"]),
            -int(item["metrics"]["trades_count"]),
        ),
    )
    return {
        "run_type": "geometry_sensitivity",
        "source_db_path": str(source_db_path),
        "settings_profile": base_settings.config_hash,
        "date_range": {
            "start": str(backtest_config.start_date),
            "end": str(backtest_config.end_date),
        },
        "symbol": backtest_config.symbol,
        "min_trades": int(min_trades),
        "slippage_bps_limit": float(backtest_config.slippage_bps_limit),
        "slippage_bps_market": float(backtest_config.slippage_bps_market),
        "slippage_stress_variant": SLIPPAGE_STRESS_VARIANT_NAME,
        "slippage_stress_multipliers": [float(item) for item in slippage_stress_multipliers],
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "elapsed_seconds": (completed_at - started_at).total_seconds(),
        "results": results,
        "ranked_names": [str(item["name"]) for item in ranked],
    }


def write_geometry_report(report: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run explicit geometry sensitivity variants without mutating source DB.")
    parser.add_argument("--source-db-path", type=Path, default=Path("storage/btc_bot.db"))
    parser.add_argument("--start-date", required=True, type=str)
    parser.add_argument("--end-date", required=True, type=str)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--profile", choices=("research", "live", "experiment"), default="experiment")
    parser.add_argument("--min-trades", type=int, default=0)
    parser.add_argument("--max-variants", type=int, default=None)
    parser.add_argument(
        "--slippage-stress-multipliers",
        type=str,
        default="2,3",
        help="Comma-separated multipliers for min_stop_relief_only slippage stress. Use empty string to disable.",
    )
    return parser


def _parse_slippage_stress_multipliers(raw: str) -> tuple[float, ...]:
    token = raw.strip()
    if not token:
        return ()
    return tuple(float(item.strip()) for item in token.split(",") if item.strip())


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    start_ts = _parse_iso_datetime(args.start_date, is_end=False)
    end_ts = _parse_iso_datetime(args.end_date, is_end=True)
    if end_ts <= start_ts:
        raise ValueError("--end-date must be later than --start-date.")

    settings = load_settings(profile=str(args.profile))
    report = run_geometry_sensitivity(
        base_settings=settings,
        source_db_path=args.source_db_path,
        backtest_config=BacktestConfig(
            start_date=start_ts,
            end_date=end_ts,
            symbol=settings.strategy.symbol,
        ),
        min_trades=int(args.min_trades),
        max_variants=args.max_variants,
        slippage_stress_multipliers=_parse_slippage_stress_multipliers(str(args.slippage_stress_multipliers)),
    )
    output_path = write_geometry_report(report, args.output_json)
    print(output_path)
    print(json.dumps({"ranked_names": report["ranked_names"], "elapsed_seconds": report["elapsed_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
