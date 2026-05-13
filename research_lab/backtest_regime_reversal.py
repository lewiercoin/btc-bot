from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from backtest.backtest_runner import BacktestConfig, BacktestRunner, _to_utc
from backtest.fill_model import FillModelConfig, SimpleFillModel
from backtest.performance import summarize
from backtest.replay_loader import ReplayLoader, ReplayLoaderConfig
from core.models import RegimeState, SignalCandidate, TradeLog
from research_lab.evaluate_regime_gates import evaluate_gates
from research_lab.setups.regime_reversal import RegimeReversalConfig, RegimeReversalLong, RegimeReversalShort
from storage.repositories import fetch_funding_rates


class RegimeReversalBacktestRunner(BacktestRunner):
    """Research-only replay runner for the final 15m portfolio test."""

    def __init__(self, connection: sqlite3.Connection, *, setup_config: RegimeReversalConfig | None = None) -> None:
        super().__init__(connection)
        self.setup_config = setup_config or RegimeReversalConfig()
        self.long_setup = RegimeReversalLong(self.setup_config)
        self.short_setup = RegimeReversalShort(self.setup_config)
        self._regime_history: list[str] = []
        self._regime_timeline: list[tuple[datetime, str]] = []
        self._candidates_by_signal_id: dict[str, SignalCandidate] = {}
        self._used_transition_ids: set[str] = set()

    def _persist_closed_trades(self, closed_records: list[Any]) -> None:
        del closed_records
        return

    def run_with_report(self, config: BacktestConfig) -> dict[str, Any]:
        symbol = config.symbol.upper()
        initial_equity = max(float(config.initial_equity), 1e-8)

        self._signal_counter = 0
        self._position_counter = 0
        self._trade_counter = 0
        self._regime_history = []
        self._regime_timeline = []
        self._candidates_by_signal_id = {}
        self._used_transition_ids = set()

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
        transition_records: list[dict[str, Any]] = []
        rejection_reasons: Counter[str] = Counter()
        candidate_records: list[dict[str, Any]] = []

        for snapshot in replay_loader.iter_snapshots(start_date=config.start_date, end_date=config.end_date, symbol=symbol):
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
            regime = regime_engine.classify(features)
            regime_counts[regime.value] += 1
            if not self._regime_history or self._regime_history[-1] != regime.value:
                transition_records.append(
                    {
                        "timestamp": now.isoformat(),
                        "from_regime": self._regime_history[-1] if self._regime_history else None,
                        "to_regime": regime.value,
                        "cycle_index": cycles - 1,
                    }
                )
            self._regime_history.append(regime.value)
            if len(self._regime_history) > 500:
                self._regime_history = self._regime_history[-500:]
            self._regime_timeline.append((now, regime.value))
            snapshot.source_meta["research_regime_history"] = list(self._regime_history)

            context = context_engine.classify(features)
            del context

            long_eval = self.long_setup.evaluate_structure(snapshot=snapshot, features=features, regime=regime)
            short_eval = self.short_setup.evaluate_structure(snapshot=snapshot, features=features, regime=regime)
            candidate = self._select_candidate(snapshot=snapshot, features=features, regime=regime)
            if candidate is None:
                for reason in long_eval.reasons + short_eval.reasons:
                    rejection_reasons[reason] += 1
                continue

            transition_id = str(candidate.features_json.get("transition_id"))
            if transition_id in self._used_transition_ids:
                rejection_reasons["duplicate_transition_candidate"] += 1
                continue

            self._signal_counter += 1
            candidate.signal_id = self._make_signal_id(now, self._signal_counter)
            self._candidates_by_signal_id[candidate.signal_id] = candidate
            self._used_transition_ids.add(transition_id)
            candidate_records.append(_candidate_record(candidate))

            governance_decision = governance.evaluate(candidate)
            if not governance_decision.approved:
                for reason in governance_decision.notes:
                    rejection_reasons[f"governance:{reason}"] += 1
                continue

            executable = governance.to_executable(candidate, governance_decision)
            risk_decision = risk_engine.evaluate(signal=executable, equity=equity, open_positions=len(open_positions))
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
        closed_trade_records = self._closed_trade_records(trades)
        transition_stats = _transition_stats(self._regime_timeline)
        decision_summary = self._decision_summary(
            cycles=cycles,
            transition_records=transition_records,
            candidate_records=candidate_records,
            closed_trade_records=closed_trade_records,
            rejection_reasons=rejection_reasons,
            transition_stats=transition_stats,
        )
        return {
            "metadata": {
                "setup": "regime_reversal",
                "classification": "FINAL_15M_PORTFOLIO_TEST",
                "start_date": _iso_date(config.start_date),
                "end_date": _iso_date(config.end_date),
                "symbol": symbol,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "research_only": True,
            },
            "config": asdict(self.setup_config),
            "performance": _performance_dict(summarize(trades, initial_equity=initial_equity)),
            "per_prior_regime": _group_performance(
                trades,
                key=lambda trade: str((trade.features_at_entry_json or {}).get("prior_regime", "unknown")),
            ),
            "per_direction": _group_performance(trades, key=lambda trade: str(trade.direction)),
            "regime_distribution": dict(sorted(regime_counts.items())),
            "transition_distribution": transition_stats,
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
            prior_regime = str(features.get("prior_regime", ""))
            opened_at = _to_utc(trade.opened_at)
            closed_at = _to_utc(trade.closed_at) if trade.closed_at is not None else None
            regimes_during_trade = [
                regime
                for ts, regime in self._regime_timeline
                if ts >= opened_at and (closed_at is None or ts <= closed_at)
            ]
            false_reversal = bool(float(trade.pnl_r) < 0 and prior_regime in regimes_during_trade)
            records.append(
                {
                    "trade_id": trade.trade_id,
                    "signal_id": trade.signal_id,
                    "opened_at": opened_at.isoformat(),
                    "closed_at": closed_at.isoformat() if closed_at is not None else None,
                    "direction": trade.direction,
                    "regime": trade.regime,
                    "prior_regime": prior_regime,
                    "current_regime": features.get("current_regime"),
                    "transition_id": features.get("transition_id"),
                    "cycles_since_transition": int(features.get("cycles_since_transition", 0)),
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "pnl_r": trade.pnl_r,
                    "pnl_abs": trade.pnl_abs,
                    "exit_reason": trade.exit_reason,
                    "false_reversal": false_reversal,
                    "regime_reverted_during_trade": prior_regime in regimes_during_trade,
                    "tfi_60s": float(features.get("tfi_60s", 0.0)),
                    "reasons": list(candidate.reasons if candidate is not None else []),
                }
            )
        return records

    def _decision_summary(
        self,
        *,
        cycles: int,
        transition_records: list[dict[str, Any]],
        candidate_records: list[dict[str, Any]],
        closed_trade_records: list[dict[str, Any]],
        rejection_reasons: Counter[str],
        transition_stats: dict[str, Any],
    ) -> dict[str, Any]:
        entries = len(candidate_records)
        closed_count = len(closed_trade_records)
        delays = [int(record.get("cycles_since_transition", 0)) for record in closed_trade_records]
        false_reversals = sum(1 for record in closed_trade_records if record.get("false_reversal"))
        transition_entries = sum(
            1
            for record in candidate_records
            if int(record.get("cycles_since_transition", 999)) <= self.setup_config.max_entry_delay_cycles
        )
        return {
            "cycles": cycles,
            "transition_events": len(transition_records),
            "transition_cycle_rate": len(transition_records) / max(cycles, 1),
            "candidates": entries,
            "closed_trades": closed_count,
            "transition_entries": transition_entries,
            "transition_entry_rate": transition_entries / max(entries, 1),
            "avg_entry_delay_cycles": sum(delays) / max(len(delays), 1),
            "median_entry_delay_cycles": _percentile(delays, 0.50),
            "p95_entry_delay_cycles": _percentile(delays, 0.95),
            "false_reversals": false_reversals,
            "false_reversal_rate": false_reversals / max(closed_count, 1),
            "whipsaw_rate": float(transition_stats["whipsaw_rate"]),
            "quick_flip_transitions": int(transition_stats["quick_flip_transitions"]),
            "top_rejection_reasons": dict(rejection_reasons.most_common(20)),
        }


def write_reports(report: dict[str, Any], *, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "regime_reversal_results.json"
    gate_path = output_dir / "regime_gate_results.json"
    validation_path = output_dir / "regime_reversal_validation_report.md"
    transition_path = output_dir / "regime_transition_distribution.md"
    audit_path = output_dir / "REGIME_REVERSAL_AUDIT_PACKAGE.md"

    gate_results = evaluate_gates(report)
    results_path.write_text(json.dumps(_json_safe(report), indent=2, sort_keys=True), encoding="utf-8")
    gate_path.write_text(json.dumps(_json_safe(gate_results), indent=2, sort_keys=True), encoding="utf-8")
    validation_path.write_text(_render_validation_report(report, gate_results), encoding="utf-8")
    transition_path.write_text(_render_transition_report(report), encoding="utf-8")
    audit_path.write_text(_render_audit_package(report, gate_results), encoding="utf-8")
    return {
        "results": results_path,
        "gates": gate_path,
        "validation": validation_path,
        "transitions": transition_path,
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
        "prior_regime": features.get("prior_regime"),
        "current_regime": features.get("current_regime"),
        "transition_id": features.get("transition_id"),
        "cycles_since_transition": int(features.get("cycles_since_transition", 0)),
        "confluence_score": candidate.confluence_score,
        "entry_reference": candidate.entry_reference,
        "tfi_60s": float(features.get("tfi_60s", 0.0)),
        "reasons": list(candidate.reasons),
    }


def _transition_stats(timeline: list[tuple[datetime, str]]) -> dict[str, Any]:
    if not timeline:
        return {
            "total_regime_runs": 0,
            "total_transitions": 0,
            "quick_flip_transitions": 0,
            "whipsaw_rate": 0.0,
            "run_length_cycles": {},
            "transition_pairs": {},
        }
    runs: list[dict[str, Any]] = []
    current = timeline[0][1]
    start = 0
    for index, (_ts, regime) in enumerate(timeline[1:], start=1):
        if regime == current:
            continue
        runs.append({"regime": current, "start": start, "end": index - 1, "length": index - start})
        current = regime
        start = index
    runs.append({"regime": current, "start": start, "end": len(timeline) - 1, "length": len(timeline) - start})

    pairs: Counter[str] = Counter()
    quick_flips = 0
    for index in range(1, len(runs)):
        prior = runs[index - 1]
        current_run = runs[index]
        pairs[f"{prior['regime']}->{current_run['regime']}"] += 1
        if int(current_run["length"]) <= 2:
            quick_flips += 1
    lengths = [int(run["length"]) for run in runs]
    transitions = max(len(runs) - 1, 0)
    return {
        "total_regime_runs": len(runs),
        "total_transitions": transitions,
        "quick_flip_transitions": quick_flips,
        "whipsaw_rate": quick_flips / max(transitions, 1),
        "run_length_cycles": {
            "min": min(lengths),
            "median": _percentile(lengths, 0.50),
            "p95": _percentile(lengths, 0.95),
            "max": max(lengths),
        },
        "transition_pairs": dict(pairs.most_common()),
    }


def _group_performance(trades: list[TradeLog], *, key: Callable[[TradeLog], str]) -> dict[str, dict[str, Any]]:
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
        "# REGIME-REVERSAL-RESEARCH-V1 Validation Report",
        "",
        "Final 15m portfolio test: state transition entries after RegimeEngine confirms shift.",
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
        f"- Transition events: {summary['transition_events']} ({summary['transition_cycle_rate']:.2%})",
        f"- Candidates: {summary['candidates']}",
        f"- Closed trades: {summary['closed_trades']}",
        f"- Average entry delay: {summary['avg_entry_delay_cycles']:.2f} cycles",
        f"- Median entry delay: {summary['median_entry_delay_cycles']} cycles",
        f"- P95 entry delay: {summary['p95_entry_delay_cycles']} cycles",
        f"- False reversal rate: {summary['false_reversal_rate']:.2%}",
        f"- Whipsaw rate: {summary['whipsaw_rate']:.2%}",
        "",
        "## Per-Prior-Regime Performance",
        "",
        "| Prior Regime | Trades | ER | PF | Win Rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for regime, metrics in report["per_prior_regime"].items():
        lines.append(
            f"| {regime} | {metrics['trades_count']} | {float(metrics['expectancy_r']):.4f} | "
            f"{metrics['profit_factor']} | {float(metrics['win_rate']):.2%} |"
        )
    lines.extend(["", "## Per-Direction Performance", "", "| Direction | Trades | ER | PF | Win Rate |", "|---|---:|---:|---:|---:|"])
    for direction, metrics in report["per_direction"].items():
        lines.append(
            f"| {direction} | {metrics['trades_count']} | {float(metrics['expectancy_r']):.4f} | "
            f"{metrics['profit_factor']} | {float(metrics['win_rate']):.2%} |"
        )
    lines.extend(["", "## Top Rejection Reasons", ""])
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


def _render_transition_report(report: dict[str, Any]) -> str:
    stats = report["transition_distribution"]
    summary = report["decision_summary"]
    lines = [
        "# Regime Transition Distribution",
        "",
        "This report measures whether RegimeEngine transitions are stable enough for 15m state-transition entries.",
        "",
        f"- Replay cycles: {summary['cycles']}",
        f"- Total transitions: {stats['total_transitions']}",
        f"- Quick flip transitions: {stats['quick_flip_transitions']}",
        f"- Whipsaw rate: {stats['whipsaw_rate']:.2%}",
        f"- Run length median: {stats['run_length_cycles'].get('median', 0)} cycles",
        f"- Run length p95: {stats['run_length_cycles'].get('p95', 0)} cycles",
        "",
        "## Transition Pairs",
        "",
        "| Pair | Count |",
        "|---|---:|",
    ]
    for pair, count in stats["transition_pairs"].items():
        lines.append(f"| {pair} | {count} |")
    lines.append("")
    return "\n".join(lines)


def _render_audit_package(report: dict[str, Any], gate_results: dict[str, Any]) -> str:
    perf = report["performance"]
    summary = report["decision_summary"]
    lines = [
        "# AUDIT PACKAGE: REGIME-REVERSAL-RESEARCH-V1",
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
        f"- False reversal rate: {summary['false_reversal_rate']:.2%}",
        f"- Whipsaw rate: {summary['whipsaw_rate']:.2%}",
        f"- Average entry delay: {summary['avg_entry_delay_cycles']:.2f} cycles",
        f"- Transition entry rate: {summary['transition_entry_rate']:.2%}",
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
            "- Entry requires confirmed RegimeEngine transition; no top/bottom anticipation.",
            "- Per final-test framing, failed or marginal gates lead to strategic assessment, not another setup iteration.",
            "",
        ]
    )
    return "\n".join(lines)


def _percentile(values: list[int | float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = min(max(int(round((len(ordered) - 1) * q)), 0), len(ordered) - 1)
    return ordered[index]


def _iso_date(value: datetime | date | str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run regime_reversal research backtest.")
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
        runner = RegimeReversalBacktestRunner(connection)
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
