from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig, BacktestRunner, _to_utc
from backtest.fill_model import FillModelConfig, SimpleFillModel
from backtest.performance import summarize
from backtest.replay_loader import ReplayLoader, ReplayLoaderConfig
from core.models import RegimeState, SignalCandidate, TradeLog
from research_lab.evaluate_volatility_gates import evaluate_gates
from research_lab.setups.volatility_breakout import (
    VolatilityBreakoutConfig,
    VolatilityBreakoutLong,
    VolatilityBreakoutShort,
)
from settings import build_signal_regime_direction_whitelist
from storage.repositories import fetch_funding_rates


class VolatilityBreakoutBacktestRunner(BacktestRunner):
    """Research-only replay runner for volatility_breakout candidates."""

    def __init__(self, connection: sqlite3.Connection, *, setup_config: VolatilityBreakoutConfig | None = None) -> None:
        super().__init__(connection)
        self.setup_config = setup_config or VolatilityBreakoutConfig()
        self.long_setup = VolatilityBreakoutLong(self.setup_config)
        self.short_setup = VolatilityBreakoutShort(self.setup_config)
        self._atr_history: list[float] = []
        self._atr_by_timestamp: dict[datetime, float] = {}
        self._candidates_by_signal_id: dict[str, SignalCandidate] = {}

    def _persist_closed_trades(self, closed_records: list[Any]) -> None:
        del closed_records
        return

    def run_with_report(self, config: BacktestConfig) -> dict[str, Any]:
        symbol = config.symbol.upper()
        initial_equity = max(float(config.initial_equity), 1e-8)

        self._signal_counter = 0
        self._position_counter = 0
        self._trade_counter = 0
        self._atr_history = []
        self._atr_by_timestamp = {}
        self._candidates_by_signal_id = {}

        replay_loader = ReplayLoader(
            self.connection,
            ReplayLoaderConfig(
                candles_15m_lookback=config.candles_15m_lookback,
                candles_1h_lookback=config.candles_1h_lookback,
                candles_4h_lookback=config.candles_4h_lookback,
                funding_lookback=config.funding_lookback,
            ),
        )
        fill_model = SimpleFillModel(
            FillModelConfig(
                slippage_bps_limit=config.slippage_bps_limit,
                slippage_bps_market=config.slippage_bps_market,
                fee_rate_maker=config.fee_rate_maker,
                fee_rate_taker=config.fee_rate_taker,
            )
        )
        funding_samples = fetch_funding_rates(self.connection, symbol=symbol)
        feature_engine, regime_engine, context_engine, _signal_engine, governance, risk_engine = self._build_engines()

        open_positions: list[Any] = []
        closed_records: list[Any] = []
        opened_trade_times: list[datetime] = []
        closed_pnl_events: list[tuple[datetime, float]] = []

        equity = initial_equity
        last_snapshot_ts: datetime | None = None
        last_close_price: float | None = None

        cycles = 0
        regime_counts: Counter[str] = Counter()
        expansion_cycles = 0
        compression_entry_cycles = 0
        rejection_reasons: Counter[str] = Counter()
        candidate_records: list[dict[str, Any]] = []

        for snapshot in replay_loader.iter_snapshots(
            start_date=config.start_date,
            end_date=config.end_date,
            symbol=symbol,
        ):
            now = _to_utc(snapshot.timestamp)
            cycles += 1
            self._runtime = self._compute_runtime_state(
                now=now,
                opened_trade_times=opened_trade_times,
                closed_records=closed_records,
                closed_pnl_events=closed_pnl_events,
                initial_equity=initial_equity,
            )
            last_snapshot_ts = now
            last_close_price = float(snapshot.price)

            equity += self._close_positions_if_needed(
                snapshot=snapshot,
                open_positions=open_positions,
                closed_records=closed_records,
                closed_pnl_events=closed_pnl_events,
                fill_model=fill_model,
                funding_samples=funding_samples,
                risk_engine=risk_engine,
            )
            self._runtime = self._compute_runtime_state(
                now=now,
                opened_trade_times=opened_trade_times,
                closed_records=closed_records,
                closed_pnl_events=closed_pnl_events,
                initial_equity=initial_equity,
            )

            features = feature_engine.compute(
                snapshot=snapshot,
                schema_version=self.settings.schema_version,
                config_hash=self.settings.config_hash,
            )
            self._atr_history.append(float(features.atr_4h_norm))
            if len(self._atr_history) > 500:
                self._atr_history = self._atr_history[-500:]
            self._atr_by_timestamp[now] = float(features.atr_4h_norm)
            snapshot.source_meta["research_atr_4h_norm_history"] = list(self._atr_history)

            regime = regime_engine.classify(features)
            regime_counts[regime.value] += 1
            context = context_engine.classify(features)
            del context

            long_eval = self.long_setup.evaluate_structure(snapshot=snapshot, features=features, regime=regime)
            short_eval = self.short_setup.evaluate_structure(snapshot=snapshot, features=features, regime=regime)
            if bool(long_eval.metrics.get("expansion", {}).get("expansion_state", False)):
                expansion_cycles += 1
            if bool(long_eval.metrics.get("compression_entry", False)):
                compression_entry_cycles += 1

            candidate = self._select_candidate(snapshot=snapshot, features=features, regime=regime)
            if candidate is None:
                for reason in long_eval.reasons + short_eval.reasons:
                    rejection_reasons[reason] += 1
                continue

            self._signal_counter += 1
            candidate.signal_id = self._make_signal_id(now, self._signal_counter)
            self._candidates_by_signal_id[candidate.signal_id] = candidate
            candidate_records.append(_candidate_record(candidate))

            governance_decision = governance.evaluate(candidate)
            if not governance_decision.approved:
                for reason in governance_decision.notes:
                    rejection_reasons[f"governance:{reason}"] += 1
                continue

            executable = governance.to_executable(candidate, governance_decision)
            risk_decision = risk_engine.evaluate(
                signal=executable,
                equity=equity,
                open_positions=len(open_positions),
            )
            if not risk_decision.allowed:
                rejection_reasons[f"risk:{risk_decision.reason or 'unknown'}"] += 1
                continue

            open_positions.append(
                self._open_position(
                    now=now,
                    candidate=candidate,
                    executable=executable,
                    risk_decision_size=risk_decision.size,
                    risk_decision_leverage=risk_decision.leverage,
                    fill_model=fill_model,
                    entry_order_type=config.entry_order_type,
                )
            )
            opened_trade_times.append(now)

        if open_positions and last_snapshot_ts is not None and last_close_price is not None:
            equity += self._force_close_remaining_positions(
                now=last_snapshot_ts,
                close_price=last_close_price,
                open_positions=open_positions,
                closed_records=closed_records,
                closed_pnl_events=closed_pnl_events,
                fill_model=fill_model,
                funding_samples=funding_samples,
                risk_engine=risk_engine,
            )
            del equity

        trades = [record.trade for record in closed_records]
        performance = summarize(trades, initial_equity=initial_equity)
        closed_trade_records = self._closed_trade_records(trades)
        decision_summary = self._decision_summary(
            cycles=cycles,
            expansion_cycles=expansion_cycles,
            compression_entry_cycles=compression_entry_cycles,
            candidate_records=candidate_records,
            closed_trade_records=closed_trade_records,
            rejection_reasons=rejection_reasons,
        )
        return {
            "metadata": {
                "setup": "volatility_breakout",
                "start_date": _iso_date(config.start_date),
                "end_date": _iso_date(config.end_date),
                "symbol": symbol,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "research_only": True,
            },
            "config": asdict(self.setup_config),
            "performance": _performance_dict(performance),
            "per_regime": _group_performance(trades, key=lambda trade: str(trade.regime)),
            "per_direction": _group_performance(trades, key=lambda trade: str(trade.direction)),
            "regime_distribution": dict(sorted(regime_counts.items())),
            "decision_summary": decision_summary,
            "candidate_records": candidate_records,
            "closed_trades": closed_trade_records,
        }

    def _select_candidate(self, *, snapshot, features, regime: RegimeState) -> SignalCandidate | None:
        candidates = [
            setup.generate_signal_candidate(snapshot=snapshot, features=features, regime=regime)
            for setup in (self.long_setup, self.short_setup)
        ]
        valid = [candidate for candidate in candidates if candidate is not None]
        if not valid:
            return None
        return max(valid, key=lambda candidate: float(candidate.confluence_score))

    def _closed_trade_records(self, trades: list[TradeLog]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for trade in trades:
            candidate = self._candidates_by_signal_id.get(trade.signal_id)
            features = dict(trade.features_at_entry_json or {})
            entry_ts = _to_utc(trade.opened_at)
            exit_ts = _to_utc(trade.closed_at) if trade.closed_at is not None else None
            entry_atr = float(features.get("atr_4h_norm", 0.0))
            exit_atr = self._atr_by_timestamp.get(exit_ts, 0.0) if exit_ts is not None else 0.0
            records.append(
                {
                    "trade_id": trade.trade_id,
                    "signal_id": trade.signal_id,
                    "opened_at": entry_ts.isoformat(),
                    "closed_at": exit_ts.isoformat() if exit_ts is not None else None,
                    "direction": trade.direction,
                    "regime": trade.regime,
                    "setup_type": features.get("setup_type"),
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "pnl_r": trade.pnl_r,
                    "pnl_abs": trade.pnl_abs,
                    "exit_reason": trade.exit_reason,
                    "atr_entry": entry_atr,
                    "atr_exit": exit_atr,
                    "expansion_continued": bool(exit_atr > entry_atr) if exit_atr > 0 and entry_atr > 0 else False,
                    "expansion_state": bool(features.get("expansion_state", False)),
                    "compression_entry": bool(features.get("compression_entry", False)),
                    "atr_slope_pct": float(features.get("atr_slope_pct", 0.0)),
                    "breakout_size_atr": float(features.get("breakout_size_atr", 0.0)),
                    "tfi_60s": float(features.get("tfi_60s", 0.0)),
                    "reasons": list(candidate.reasons if candidate is not None else []),
                }
            )
        return records

    def _decision_summary(
        self,
        *,
        cycles: int,
        expansion_cycles: int,
        compression_entry_cycles: int,
        candidate_records: list[dict[str, Any]],
        closed_trade_records: list[dict[str, Any]],
        rejection_reasons: Counter[str],
    ) -> dict[str, Any]:
        entries = len(candidate_records)
        expansion_entries = sum(1 for record in candidate_records if record.get("expansion_state") and not record.get("compression_entry"))
        compression_entries = sum(1 for record in candidate_records if record.get("compression_entry"))
        closed_count = len(closed_trade_records)
        continued = sum(1 for trade in closed_trade_records if trade.get("expansion_continued"))
        return {
            "cycles": cycles,
            "expansion_cycles": expansion_cycles,
            "expansion_cycle_rate": expansion_cycles / max(cycles, 1),
            "compression_entry_cycles": compression_entry_cycles,
            "candidates": entries,
            "closed_trades": closed_count,
            "expansion_entries": expansion_entries,
            "compression_entries": compression_entries,
            "expansion_entry_rate": expansion_entries / max(entries, 1),
            "compression_entry_rate": compression_entries / max(entries, 1),
            "expansion_continuations": continued,
            "expansion_continuation_rate": continued / max(closed_count, 1),
            "top_rejection_reasons": dict(rejection_reasons.most_common(20)),
        }


def write_reports(report: dict[str, Any], *, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "volatility_breakout_results.json"
    gate_path = output_dir / "volatility_gate_results.json"
    validation_path = output_dir / "volatility_breakout_validation_report.md"
    atr_path = output_dir / "atr_expansion_distribution.md"
    audit_path = output_dir / "VOLATILITY_BREAKOUT_AUDIT_PACKAGE.md"

    gate_results = evaluate_gates(report)
    results_path.write_text(json.dumps(_json_safe(report), indent=2, sort_keys=True), encoding="utf-8")
    gate_path.write_text(json.dumps(_json_safe(gate_results), indent=2, sort_keys=True), encoding="utf-8")
    validation_path.write_text(_render_validation_report(report, gate_results), encoding="utf-8")
    atr_path.write_text(_render_atr_report(report), encoding="utf-8")
    audit_path.write_text(_render_audit_package(report, gate_results), encoding="utf-8")
    return {
        "results": results_path,
        "gates": gate_path,
        "validation": validation_path,
        "atr": atr_path,
        "audit": audit_path,
    }


def _candidate_record(candidate: SignalCandidate) -> dict[str, Any]:
    features = dict(candidate.features_json or {})
    return {
        "timestamp": candidate.timestamp.isoformat(),
        "signal_id": candidate.signal_id,
        "direction": candidate.direction,
        "setup_type": candidate.setup_type,
        "regime": candidate.regime.value,
        "confluence_score": candidate.confluence_score,
        "entry_reference": candidate.entry_reference,
        "expansion_state": bool(features.get("expansion_state", False)),
        "compression_entry": bool(features.get("compression_entry", False)),
        "atr_4h_norm": float(features.get("atr_4h_norm", 0.0)),
        "atr_slope_pct": float(features.get("atr_slope_pct", 0.0)),
        "breakout_size_atr": float(features.get("breakout_size_atr", 0.0)),
        "tfi_60s": float(features.get("tfi_60s", 0.0)),
        "reasons": list(candidate.reasons),
    }


def _group_performance(trades: list[TradeLog], *, key) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[TradeLog]] = defaultdict(list)
    for trade in trades:
        groups[key(trade)].append(trade)
    return {name: _performance_dict(summarize(group)) for name, group in sorted(groups.items())}


def _performance_dict(performance) -> dict[str, Any]:
    raw = asdict(performance)
    return {key: _safe_number(value) for key, value in raw.items()}


def _safe_number(value: Any) -> Any:
    if isinstance(value, float) and (value == float("inf") or value == float("-inf")):
        return str(value)
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return _safe_number(value)


def _render_validation_report(report: dict[str, Any], gate_results: dict[str, Any]) -> str:
    perf = report["performance"]
    summary = report["decision_summary"]
    lines = [
        "# VOLATILITY-BREAKOUT-RESEARCH-V1 Validation Report",
        "",
        "## Scope",
        "",
        "Research-only validation of volatility_breakout using ATR expansion state, structure break, and aligned TFI momentum.",
        "",
        "## Overall Performance",
        "",
        f"- Trades: {perf['trades_count']}",
        f"- Expectancy R: {float(perf['expectancy_r']):.4f}",
        f"- Profit factor: {perf['profit_factor']}",
        f"- Win rate: {float(perf['win_rate']):.2%}",
        f"- Max DD: {float(perf['max_drawdown_pct']):.2%}",
        "",
        "## Decision Funnel",
        "",
        f"- Replay cycles: {summary['cycles']}",
        f"- Expansion cycles: {summary['expansion_cycles']} ({summary['expansion_cycle_rate']:.2%})",
        f"- Candidates: {summary['candidates']}",
        f"- Closed trades: {summary['closed_trades']}",
        f"- Expansion entry rate: {summary['expansion_entry_rate']:.2%}",
        f"- Compression entry rate: {summary['compression_entry_rate']:.2%}",
        f"- Expansion continuation rate: {summary['expansion_continuation_rate']:.2%}",
        "",
        "## Per-Regime Performance",
        "",
        "| Regime | Trades | ER | PF | Win Rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for regime, metrics in report["per_regime"].items():
        lines.append(
            f"| {regime} | {metrics['trades_count']} | {float(metrics['expectancy_r']):.4f} | "
            f"{metrics['profit_factor']} | {float(metrics['win_rate']):.2%} |"
        )
    lines.extend(
        [
            "",
            "## Per-Direction Performance",
            "",
            "| Direction | Trades | ER | PF | Win Rate |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for direction, metrics in report["per_direction"].items():
        lines.append(
            f"| {direction} | {metrics['trades_count']} | {float(metrics['expectancy_r']):.4f} | "
            f"{metrics['profit_factor']} | {float(metrics['win_rate']):.2%} |"
        )
    lines.extend(
        [
            "",
            "## Top Rejection Reasons",
            "",
        ]
    )
    for reason, count in summary["top_rejection_reasons"].items():
        lines.append(f"- {reason}: {count}")
    lines.extend(
        [
            "",
            "## Gate Results",
            "",
            f"Verdict: **{gate_results['verdict']}**",
            f"Reason: `{gate_results['reason']}`",
            "",
            "| Gate | Value | Status |",
            "|---|---:|---|",
        ]
    )
    for gate in gate_results["gates"]:
        value = gate["value"]
        rendered = f"{value:.4f}" if isinstance(value, float) else str(value)
        lines.append(f"| {gate['gate']} | {rendered} | {gate['status']} |")
    lines.append("")
    return "\n".join(lines)


def _render_atr_report(report: dict[str, Any]) -> str:
    summary = report["decision_summary"]
    candidates = report["candidate_records"]
    slopes = [float(record["atr_slope_pct"]) for record in candidates]
    lines = [
        "# ATR Expansion Distribution",
        "",
        "This report validates that volatility_breakout enters during ATR expansion, not compression.",
        "",
        f"- Replay cycles: {summary['cycles']}",
        f"- Expansion cycles: {summary['expansion_cycles']} ({summary['expansion_cycle_rate']:.2%})",
        f"- Candidate entries: {summary['candidates']}",
        f"- Expansion entry rate: {summary['expansion_entry_rate']:.2%}",
        f"- Compression entry rate: {summary['compression_entry_rate']:.2%}",
        "",
        "## Candidate ATR Slope",
        "",
        f"- Min slope: {min(slopes):.6f}" if slopes else "- Min slope: n/a",
        f"- Median slope: {_percentile(slopes, 0.50):.6f}" if slopes else "- Median slope: n/a",
        f"- P95 slope: {_percentile(slopes, 0.95):.6f}" if slopes else "- P95 slope: n/a",
        "",
        "## Regime Distribution",
        "",
        "| Regime | Cycles |",
        "|---|---:|",
    ]
    for regime, count in report["regime_distribution"].items():
        lines.append(f"| {regime} | {count} |")
    lines.append("")
    return "\n".join(lines)


def _render_audit_package(report: dict[str, Any], gate_results: dict[str, Any]) -> str:
    perf = report["performance"]
    summary = report["decision_summary"]
    lines = [
        "# AUDIT PACKAGE: VOLATILITY-BREAKOUT-RESEARCH-V1",
        "",
        "## Builder Verdict",
        "",
        f"Verdict: **{gate_results['verdict']}**",
        f"Reason: `{gate_results['reason']}`",
        "",
        "## Key Metrics",
        "",
        f"- Trades: {perf['trades_count']}",
        f"- ER: {float(perf['expectancy_r']):.4f}",
        f"- PF: {perf['profit_factor']}",
        f"- Expansion continuation: {summary['expansion_continuation_rate']:.2%}",
        f"- Expansion entry rate: {summary['expansion_entry_rate']:.2%}",
        f"- Compression entry rate: {summary['compression_entry_rate']:.2%}",
        "",
        "## Hard Gates",
        "",
        "| Gate | Value | Pass | Reject | Status |",
        "|---|---:|---|---|---|",
    ]
    for gate in gate_results["gates"]:
        value = gate["value"]
        rendered = f"{value:.4f}" if isinstance(value, float) else str(value)
        lines.append(
            f"| {gate['gate']} | {rendered} | {gate['pass_threshold']} | "
            f"{gate['reject_threshold']} | {gate['status']} |"
        )
    lines.extend(
        [
            "",
            "## Scope Boundaries",
            "",
            "- Research-only implementation.",
            "- No production modules changed.",
            "- No settings.py promotion.",
            "- Compression regime is blocked to avoid compression_breakout 2.0.",
            "",
        ]
    )
    return "\n".join(lines)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(max(int(round((len(ordered) - 1) * q)), 0), len(ordered) - 1)
    return ordered[index]


def _iso_date(value: datetime | date | str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run volatility_breakout research backtest.")
    parser.add_argument("--db", default="storage/btc_bot.db")
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2026-03-29")
    parser.add_argument("--output-dir", default="research_lab/reports")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        runner = VolatilityBreakoutBacktestRunner(connection)
        report = runner.run_with_report(
            BacktestConfig(
                start_date=args.start,
                end_date=args.end,
                symbol="BTCUSDT",
            )
        )
    paths = write_reports(report, output_dir=Path(args.output_dir))
    print(json.dumps({name: str(path) for name, path in paths.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
