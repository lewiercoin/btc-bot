"""Backtest runner for Session Sweep Specialist (sweep_reclaim family Variant 4).

Standalone script that:
1. Runs the standard sweep_reclaim signal engine
2. Applies Session time-of-day pre-filter (Asia hours 00:00-08:00 UTC)
3. Overrides direction whitelist: LONG only across ALL regimes
4. Records per-cycle decision diagnostics with session hour tracking
5. Computes independence overlap with trial-00095
6. Generates validation report + audit package

Microstructure hypothesis: Sweeps during thin-liquidity sessions have higher
reversion probability. Mechanistically different from regime-based V1-V3.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PROJECT_ROOT))

from backtest.backtest_runner import BacktestConfig, BacktestResult
from backtest.performance import PerformanceReport, summarize
from core.models import Features, RegimeState, SignalCandidate, TradeLog
from core.signal_engine import SignalEngine
from research_lab.research_backtest_runner import ResearchBacktestRunner
from research_lab.setups.session_sweep_specialist import (
    SessionSweepConfig,
    get_session_directions,
    is_in_session,
)
from settings import load_settings

DEFAULT_START = "2022-01-01"
DEFAULT_END = "2026-03-29"
DEFAULT_INITIAL_EQUITY = 10_000.0
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "research_lab" / "reports"
DEFAULT_JSON_PATH = DEFAULT_OUTPUT_DIR / "session_sweep_specialist_results.json"
DEFAULT_MARKDOWN_PATH = DEFAULT_OUTPUT_DIR / "session_sweep_specialist_validation_report.md"
DEFAULT_AUDIT_PATH = DEFAULT_OUTPUT_DIR / "SESSION_SWEEP_SPECIALIST_AUDIT_PACKAGE.md"


# ---------------------------------------------------------------------------
# Per-cycle decision record
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SessionDecisionRecord:
    timestamp: str
    utc_hour: int
    regime: str
    session_accepted: bool
    candidate_generated: bool = False
    candidate_direction: str | None = None
    trade_opened: bool = False
    trade_closed: bool = False
    pnl_r: float | None = None
    rejection_reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Session Sweep Backtest Runner
# ---------------------------------------------------------------------------

class SessionSweepBacktestRunner(ResearchBacktestRunner):
    """Extends ResearchBacktestRunner with session time-of-day pre-filter."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        settings=None,
        replay_loader=None,
        fill_model=None,
        session_config: SessionSweepConfig | None = None,
    ) -> None:
        super().__init__(connection, settings=settings, replay_loader=replay_loader, fill_model=fill_model)
        self.session_config = session_config or SessionSweepConfig()
        self.decision_records: list[SessionDecisionRecord] = []

        # Counters for funnel diagnostics
        self.cycles_total = 0
        self.cycles_session_rejected = 0
        self.cycles_session_passed = 0
        self.cycles_signal_generated = 0
        self.cycles_governance_rejected = 0
        self.cycles_risk_rejected = 0

        # Per-hour cycle counters (for session distribution analysis)
        self.hour_cycle_counts: dict[int, int] = {}
        # Per-regime cycle counters (regime-agnostic but useful for diagnostics)
        self.regime_cycle_counts: dict[str, int] = {}
        # Per-hour trade counts
        self.hour_trade_counts: dict[int, int] = {}

    def _build_engines(self):
        """Override to set LONG-only direction whitelist across ALL regimes."""
        engines = super()._build_engines()
        feature_engine, regime_engine, context_engine, signal_engine, governance, risk_engine = engines

        # Override whitelist: LONG only in ALL regimes (no regime filter)
        directions = get_session_directions(self.session_config)
        new_whitelist = dict(signal_engine.config.regime_direction_whitelist)
        for regime_name in new_whitelist:
            new_whitelist[regime_name] = directions
        signal_engine.config.regime_direction_whitelist = new_whitelist

        return feature_engine, regime_engine, context_engine, signal_engine, governance, risk_engine

    def run(self, config: BacktestConfig) -> BacktestResult:
        """Full replay with session time-of-day pre-filter."""
        symbol = config.symbol.upper()
        initial_equity = max(float(config.initial_equity), 1e-8)

        self._signal_counter = 0
        self._position_counter = 0
        self._trade_counter = 0
        self.signals_generated = 0
        self.signals_regime_blocked = 0
        self.signals_governance_rejected = 0
        self.signals_risk_rejected = 0
        self.decision_records = []

        self.cycles_total = 0
        self.cycles_session_rejected = 0
        self.cycles_session_passed = 0
        self.cycles_signal_generated = 0
        self.cycles_governance_rejected = 0
        self.cycles_risk_rejected = 0
        self.hour_cycle_counts = {}
        self.regime_cycle_counts = {}
        self.hour_trade_counts = {}

        replay_loader = self._custom_replay_loader or self._build_default_replay_loader(config)
        fill_model = self._custom_fill_model or self._build_default_fill_model(config)

        from storage.repositories import fetch_funding_rates
        funding_samples = fetch_funding_rates(self.connection, symbol=symbol)
        feature_engine, regime_engine, context_engine, signal_engine, governance, risk_engine = self._build_engines()

        open_positions: list[Any] = []
        closed_records: list[Any] = []
        opened_trade_times: list[datetime] = []
        closed_pnl_events: list[tuple[datetime, float]] = []

        equity = initial_equity
        equity_curve: list[tuple[datetime, float]] = []
        last_snapshot_ts: datetime | None = None
        last_close_price: float | None = None

        for snapshot in replay_loader.iter_snapshots(
            start_date=config.start_date,
            end_date=config.end_date,
            symbol=symbol,
        ):
            now = self._to_utc(snapshot.timestamp)
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

            self.cycles_total += 1

            # Track hour distribution
            utc_hour = now.hour if now.tzinfo is None else now.astimezone(timezone.utc).hour
            self.hour_cycle_counts[utc_hour] = self.hour_cycle_counts.get(utc_hour, 0) + 1

            features = feature_engine.compute(
                snapshot=snapshot,
                schema_version=self.settings.schema_version,
                config_hash=self.settings.config_hash,
            )
            regime = regime_engine.classify(features)
            regime_key = regime.value
            self.regime_cycle_counts[regime_key] = self.regime_cycle_counts.get(regime_key, 0) + 1

            record = SessionDecisionRecord(
                timestamp=now.isoformat(),
                utc_hour=utc_hour,
                regime=regime_key,
                session_accepted=False,
            )

            # --- Pre-filter: Must be in session window ---
            in_session, session_reason = is_in_session(now, self.session_config)
            if not in_session:
                record.rejection_reasons.append(session_reason)
                self.cycles_session_rejected += 1
                self.decision_records.append(record)
                equity_curve.append((now, equity))
                continue

            record.session_accepted = True

            # --- Session passed: run signal engine (regime-agnostic) ---
            self.cycles_session_passed += 1
            context = context_engine.classify(features)
            base_candidate, uptrend_candidate, candidate = self._resolve_signal_candidates(
                snapshot=snapshot,
                features=features,
                regime=regime,
                context=context,
                signal_engine=signal_engine,
            )
            self.signals_generated += int(base_candidate is not None) + int(uptrend_candidate is not None)

            if candidate is not None:
                self.cycles_signal_generated += 1
                record.candidate_generated = True
                record.candidate_direction = candidate.direction
                self._signal_counter += 1
                candidate.signal_id = self._make_signal_id(now, self._signal_counter)
                candidate.setup_type = f"session_sweep_{candidate.direction.lower()}"
                candidate.reasons = [
                    f"setup_type=session_sweep_specialist",
                    f"session={self.session_config.session_label}",
                    f"utc_hour={utc_hour}",
                    f"regime={regime_key}",
                    *candidate.reasons,
                ]

                governance_decision = governance.evaluate(candidate)
                if governance_decision.approved:
                    executable = governance.to_executable(candidate, governance_decision)
                    risk_decision = risk_engine.evaluate(
                        signal=executable,
                        equity=equity,
                        open_positions=len(open_positions),
                    )
                    if risk_decision.allowed:
                        record.trade_opened = True
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
                        self.hour_trade_counts[utc_hour] = self.hour_trade_counts.get(utc_hour, 0) + 1
                    else:
                        self.cycles_risk_rejected += 1
                        self.signals_risk_rejected += 1
                        record.rejection_reasons.append("risk_rejected")
                else:
                    self.cycles_governance_rejected += 1
                    self.signals_governance_rejected += 1
                    record.rejection_reasons.append("governance_rejected")
            else:
                record.rejection_reasons.append("no_signal_candidate")

            self.decision_records.append(record)
            equity_curve.append((now, equity))

        # Force-close remaining positions
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
            equity_curve.append((last_snapshot_ts, equity))

        trades = [record.trade for record in closed_records]
        self._persist_closed_trades(closed_records)
        performance = self._summarize_trades(trades, initial_equity=initial_equity)
        return BacktestResult(
            performance=performance,
            trades=trades,
            equity_curve=equity_curve,
        )


# ---------------------------------------------------------------------------
# Independence analysis
# ---------------------------------------------------------------------------

def compute_overlap(
    session_trades: list[TradeLog],
    trial_00095_timestamps: list[str],
    cycle_seconds: int = 900,
) -> dict[str, Any]:
    """Compute trade overlap between Session Sweep and trial-00095."""
    def _floor_cycle(ts_str: str) -> int:
        if isinstance(ts_str, datetime):
            ts = ts_str
        else:
            ts_str_clean = ts_str.replace("Z", "+00:00")
            ts = datetime.fromisoformat(ts_str_clean)
        epoch = int(ts.timestamp())
        return (epoch // cycle_seconds) * cycle_seconds

    trial_cycles = {_floor_cycle(ts) for ts in trial_00095_timestamps}

    session_cycles = []
    for trade in session_trades:
        cycle = _floor_cycle(trade.opened_at.isoformat() if isinstance(trade.opened_at, datetime) else str(trade.opened_at))
        session_cycles.append(cycle)

    session_set = set(session_cycles)
    overlap_cycles = session_set & trial_cycles
    total = len(session_set)
    overlap_count = len(overlap_cycles)
    overlap_rate = overlap_count / total if total > 0 else 0.0

    return {
        "session_trades": len(session_trades),
        "session_unique_cycles": total,
        "trial_00095_unique_cycles": len(trial_cycles),
        "overlap_cycles": overlap_count,
        "overlap_rate": round(overlap_rate, 4),
        "independence_gate_passed": overlap_rate < 0.30,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _safe_div(a: float, b: float) -> float | None:
    if b == 0:
        return None
    return round(a / b, 6)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float):
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        if math.isnan(value):
            return "nan"
        return round(value, 6)
    return value


def _perf_dict(perf: PerformanceReport) -> dict[str, Any]:
    return _sanitize(asdict(perf))


def build_report(
    *,
    result: BacktestResult,
    runner: SessionSweepBacktestRunner,
    config: SessionSweepConfig,
    source_db_path: str,
    start_date: str,
    end_date: str,
    initial_equity: float,
    overlap_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trades = result.trades
    per_regime = _performance_by(trades, key="regime", initial_equity=initial_equity)
    per_direction = _performance_by(trades, key="direction", initial_equity=initial_equity)

    # Top rejection reasons
    reason_counts: dict[str, int] = {}
    for rec in runner.decision_records:
        if not rec.candidate_generated:
            for r in rec.rejection_reasons:
                tag = r.split("|")[0]
                reason_counts[tag] = reason_counts.get(tag, 0) + 1
    top_rejections = dict(sorted(reason_counts.items(), key=lambda x: (-x[1], x[0]))[:20])

    return {
        "milestone": "SWEEP-RECLAIM-FAMILY-EXPANSION-V1",
        "variant": "session_sweep_specialist",
        "hypothesis": "Sweeps during low-liquidity sessions (Asia 00:00-08:00 UTC) have higher reversion probability due to thinner order books",
        "source_db_path": str(source_db_path),
        "date_range": {"start": start_date, "end": end_date},
        "config": _sanitize(asdict(config) if hasattr(config, "__dataclass_fields__") else vars(config)),
        "performance": _perf_dict(result.performance),
        "per_regime": per_regime,
        "per_direction": per_direction,
        "hour_cycle_distribution": {str(k): v for k, v in sorted(runner.hour_cycle_counts.items())},
        "hour_trade_distribution": {str(k): v for k, v in sorted(runner.hour_trade_counts.items())},
        "regime_cycle_distribution": runner.regime_cycle_counts,
        "decision_funnel": {
            "cycles_total": runner.cycles_total,
            "cycles_session_rejected": runner.cycles_session_rejected,
            "cycles_session_passed": runner.cycles_session_passed,
            "cycles_signal_generated": runner.cycles_signal_generated,
            "cycles_governance_rejected": runner.cycles_governance_rejected,
            "cycles_risk_rejected": runner.cycles_risk_rejected,
            "trades_opened": len(trades),
            "top_rejection_reasons": top_rejections,
        },
        "independence": overlap_result or {"status": "not_computed"},
        "builder_verdict": _compute_verdict(result.performance, overlap_result, len(trades)),
    }


def _compute_verdict(perf: PerformanceReport, overlap: dict[str, Any] | None, trade_count: int) -> dict[str, Any]:
    issues: list[str] = []
    verdict = "CANDIDATE"

    # INSUFFICIENT_SAMPLE takes precedence
    insufficient_sample = trade_count < 20
    if insufficient_sample:
        issues.append(f"INSUFFICIENT_SAMPLE: {trade_count} trades < 20 minimum")
        verdict = "INSUFFICIENT_SAMPLE"

    if perf.expectancy_r < 1.0:
        issues.append(f"HARD_STOP: ER {perf.expectancy_r:.4f} < 1.0")
        if not insufficient_sample:
            verdict = "HYPOTHESIS_FAILED"
    elif perf.expectancy_r < 1.5:
        issues.append(f"MARGINAL_ER: ER {perf.expectancy_r:.4f} < 1.5 gate")
        if verdict == "CANDIDATE":
            verdict = "ITERATE"

    if overlap and not overlap.get("independence_gate_passed", True):
        rate = overlap.get("overlap_rate", "unknown")
        issues.append(f"OVERLAP_TOO_HIGH: {rate} >= 0.30")
        if verdict == "CANDIDATE":
            verdict = "NOT_INDEPENDENT"

    if perf.win_rate < 0.50 and verdict == "CANDIDATE":
        issues.append(f"LOW_WIN_RATE: {perf.win_rate:.2%} < 50%")

    if perf.profit_factor < 2.5 and verdict == "CANDIDATE":
        issues.append(f"LOW_PF: {perf.profit_factor:.4f} < 2.5")

    return {
        "verdict": verdict,
        "issues": issues,
        "gates": {
            "er_above_1_5": perf.expectancy_r >= 1.5,
            "er_above_1_0": perf.expectancy_r >= 1.0,
            "min_trades_20": trade_count >= 20,
            "overlap_below_30": overlap.get("independence_gate_passed") if overlap else None,
            "win_rate_above_50": perf.win_rate >= 0.50,
            "pf_above_2_5": perf.profit_factor >= 2.5,
        },
    }


def _performance_by(trades: list[TradeLog], *, key: str, initial_equity: float) -> dict[str, Any]:
    groups: dict[str, list[TradeLog]] = {}
    for t in trades:
        val = str(getattr(t, key, "unknown"))
        groups.setdefault(val, []).append(t)
    return {k: _perf_dict(summarize(v, initial_equity=initial_equity)) for k, v in sorted(groups.items())}


# ---------------------------------------------------------------------------
# Markdown report writers
# ---------------------------------------------------------------------------

def write_validation_report(report: dict[str, Any], output_path: Path) -> None:
    perf = report["performance"]
    funnel = report["decision_funnel"]
    verdict_info = report["builder_verdict"]
    independence = report.get("independence", {})
    hour_dist = report.get("hour_cycle_distribution", {})
    hour_trades = report.get("hour_trade_distribution", {})

    lines = [
        "# Session Sweep Specialist — Validation Report",
        "",
        f"**Milestone:** `{report['milestone']}`",
        f"**Variant:** `{report['variant']}`",
        f"**Date range:** `{report['date_range']['start']}` → `{report['date_range']['end']}`",
        f"**Hypothesis:** {report['hypothesis']}",
        "",
        f"## Builder Verdict: **{verdict_info['verdict']}**",
        "",
    ]
    if verdict_info["issues"]:
        for issue in verdict_info["issues"]:
            lines.append(f"- {issue}")
        lines.append("")

    lines.extend([
        "## Gates",
        "",
        "| Gate | Value | Pass |",
        "|---|---|---|",
    ])
    for gate, passed in verdict_info["gates"].items():
        icon = "PASS" if passed else ("FAIL" if passed is False else "PENDING")
        lines.append(f"| {gate} | — | {icon} |")

    lines.extend([
        "",
        "## Overall Performance",
        "",
        f"- **Trades:** {perf['trades_count']}",
        f"- **Expectancy R:** {perf['expectancy_r']}",
        f"- **Profit factor:** {perf['profit_factor']}",
        f"- **Win rate:** {perf['win_rate']}",
        f"- **Max drawdown:** {perf['max_drawdown_pct']}",
        f"- **Sharpe:** {perf['sharpe_ratio']}",
        f"- **PnL abs:** {perf['pnl_abs']}",
        "",
        "## Hour Distribution (session window)",
        "",
        "| UTC Hour | Cycles | Trades |",
        "|---:|---:|---:|",
    ])
    for hour_str in sorted(hour_dist.keys(), key=int):
        h = int(hour_str)
        cycles = hour_dist.get(hour_str, 0)
        trades_h = hour_trades.get(hour_str, 0)
        marker = " *" if 0 <= h < 8 else ""
        lines.append(f"| {h:02d}{marker} | {cycles} | {trades_h} |")

    lines.extend([
        "",
        "## Decision Funnel",
        "",
        f"- Total cycles: {funnel['cycles_total']}",
        f"- Session rejected: {funnel['cycles_session_rejected']}",
        f"- Session passed: {funnel['cycles_session_passed']}",
        f"- Signal generated: {funnel['cycles_signal_generated']}",
        f"- Governance rejected: {funnel['cycles_governance_rejected']}",
        f"- Risk rejected: {funnel['cycles_risk_rejected']}",
        f"- Trades opened: {funnel['trades_opened']}",
        "",
        "## Per Regime (within session)",
        "",
        "| Regime | Trades | ER | PF | DD |",
        "|---|---:|---:|---:|---:|",
    ])
    for regime, row in sorted(report.get("per_regime", {}).items()):
        lines.append(f"| {regime} | {row['trades_count']} | {row['expectancy_r']} | {row['profit_factor']} | {row['max_drawdown_pct']} |")

    lines.extend([
        "",
        "## Per Direction",
        "",
        "| Direction | Trades | ER | PF | DD |",
        "|---|---:|---:|---:|---:|",
    ])
    for direction, row in sorted(report.get("per_direction", {}).items()):
        lines.append(f"| {direction} | {row['trades_count']} | {row['expectancy_r']} | {row['profit_factor']} | {row['max_drawdown_pct']} |")

    lines.extend([
        "",
        "## Independence Analysis",
        "",
    ])
    if independence.get("status") == "not_computed":
        lines.append("Pending — requires trial-00095 trade timestamps from server")
    else:
        lines.extend([
            f"- Session trades: {independence.get('session_trades', 'N/A')}",
            f"- Session unique cycles: {independence.get('session_unique_cycles', 'N/A')}",
            f"- Trial-00095 unique cycles: {independence.get('trial_00095_unique_cycles', 'N/A')}",
            f"- Overlap cycles: {independence.get('overlap_cycles', 'N/A')}",
            f"- **Overlap rate:** {independence.get('overlap_rate', 'N/A')}",
            f"- **Gate passed:** {independence.get('independence_gate_passed', 'N/A')}",
        ])

    lines.extend([
        "",
        "## Top Rejection Reasons",
        "",
        "| Reason | Count |",
        "|---|---:|",
    ])
    for reason, count in funnel.get("top_rejection_reasons", {}).items():
        lines.append(f"| {reason} | {count} |")

    lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_audit_package(report: dict[str, Any], output_path: Path) -> None:
    verdict_info = report["builder_verdict"]
    perf = report["performance"]
    funnel = report["decision_funnel"]
    independence = report.get("independence", {})
    hour_trades = report.get("hour_trade_distribution", {})

    lines = [
        "# SESSION SWEEP SPECIALIST — AUDIT PACKAGE",
        "",
        f"**Builder:** Cascade",
        f"**Milestone:** {report['milestone']}",
        f"**Variant:** {report['variant']}",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
        f"## Verdict: **{verdict_info['verdict']}**",
        "",
        "### Key Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Trades | {perf['trades_count']} |",
        f"| Expectancy R | {perf['expectancy_r']} |",
        f"| Profit Factor | {perf['profit_factor']} |",
        f"| Win Rate | {perf['win_rate']} |",
        f"| Max Drawdown | {perf['max_drawdown_pct']} |",
        f"| Sharpe | {perf['sharpe_ratio']} |",
        "",
        "### Validation Gates",
        "",
        "| Gate | Result |",
        "|---|---|",
    ]
    for gate, passed in verdict_info["gates"].items():
        icon = "PASS" if passed else ("FAIL" if passed is False else "PENDING")
        lines.append(f"| {gate} | {icon} |")

    lines.extend([
        "",
        "### Issues",
        "",
    ])
    if verdict_info["issues"]:
        for issue in verdict_info["issues"]:
            lines.append(f"- {issue}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "### Config",
        "",
        "```json",
        json.dumps(report.get("config", {}), indent=2, sort_keys=True),
        "```",
        "",
        "### Decision Funnel",
        "",
        f"- Cycles total: {funnel['cycles_total']}",
        f"- Session rejected: {funnel['cycles_session_rejected']}",
        f"- Session passed: {funnel['cycles_session_passed']}",
        f"- Signal generated: {funnel['cycles_signal_generated']}",
        f"- Trades opened: {funnel['trades_opened']}",
        "",
        "### Trades Per Hour (session window)",
        "",
        "| UTC Hour | Trades |",
        "|---:|---:|",
    ])
    for hour_str in sorted(hour_trades.keys(), key=int):
        lines.append(f"| {int(hour_str):02d} | {hour_trades[hour_str]} |")

    lines.extend([
        "",
        "### Per-Direction Breakdown",
        "",
        "| Direction | Trades | ER | PF | Win Rate |",
        "|---|---:|---:|---:|---:|",
    ])
    for d, row in sorted(report.get("per_direction", {}).items()):
        lines.append(f"| {d} | {row['trades_count']} | {row['expectancy_r']} | {row['profit_factor']} | {row['win_rate']} |")

    lines.extend([
        "",
        "### Per-Regime Breakdown (within session)",
        "",
        "| Regime | Trades | ER | PF | Win Rate |",
        "|---|---:|---:|---:|---:|",
    ])
    for r, row in sorted(report.get("per_regime", {}).items()):
        lines.append(f"| {r} | {row['trades_count']} | {row['expectancy_r']} | {row['profit_factor']} | {row['win_rate']} |")

    lines.extend([
        "",
        "### Independence Analysis",
        "",
    ])
    if independence.get("status") == "not_computed":
        lines.append("Pending — requires trial-00095 timestamps from server replay")
    else:
        gate_icon = "PASS" if independence.get("independence_gate_passed") else "FAIL"
        lines.extend([
            f"- Overlap rate: {independence.get('overlap_rate', 'N/A')} (gate: < 0.30)",
            f"- **Gate: {gate_icon}**",
        ])

    lines.extend([
        "",
        "### Cross-Variant Summary (V1 + V2 + V3 + V4)",
        "",
        "| Variant | Mechanism | Context | Direction | Trades | ER | Finding |",
        "|---|---|---|---|---:|---:|---|",
        "| V1 | Regime | Normal | LONG | 16 | 0.02 | Zero edge |",
        "| V1 | Regime | Normal | SHORT | 5 | -0.92 | Destructive |",
        "| V2 | Regime | Downtrend | LONG | 127 | 0.76 | Moderate (overlaps) |",
        "| V2 | Regime | Uptrend | SHORT | 32 | 0.09 | Zero edge |",
        "| V3 | Regime | Crowded_leverage | LONG | 34 | 0.30 | Below threshold |",
    ])
    # V4 rows added dynamically
    for d, drow in sorted(report.get("per_direction", {}).items()):
        lines.append(f"| V4 | Microstructure | Asia session | {d} | {drow['trades_count']} | {drow['expectancy_r']} | V4 result |")

    lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_session_backtest(
    *,
    source_db_path: Path,
    start_date: str = DEFAULT_START,
    end_date: str = DEFAULT_END,
    initial_equity: float = DEFAULT_INITIAL_EQUITY,
    output_json: Path = DEFAULT_JSON_PATH,
    output_md: Path = DEFAULT_MARKDOWN_PATH,
    output_audit: Path = DEFAULT_AUDIT_PATH,
    session_config: SessionSweepConfig | None = None,
) -> dict[str, Any]:
    config = session_config or SessionSweepConfig()
    conn = sqlite3.connect(str(source_db_path))
    conn.row_factory = sqlite3.Row
    try:
        settings = load_settings(project_root=PROJECT_ROOT, profile="research")
        runner = SessionSweepBacktestRunner(conn, settings=settings, session_config=config)
        result = runner.run(
            BacktestConfig(
                start_date=start_date,
                end_date=end_date,
                symbol=settings.strategy.symbol,
                initial_equity=initial_equity,
            )
        )

        report = build_report(
            result=result,
            runner=runner,
            config=config,
            source_db_path=str(source_db_path),
            start_date=start_date,
            end_date=end_date,
            initial_equity=initial_equity,
        )

        # Write outputs
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(_sanitize(report), indent=2, sort_keys=True), encoding="utf-8")
        write_validation_report(report, output_md)
        write_audit_package(report, output_audit)

        print(f"Trades: {result.performance.trades_count}")
        print(f"ER: {result.performance.expectancy_r:.4f}")
        print(f"PF: {result.performance.profit_factor:.4f}")
        print(f"Win rate: {result.performance.win_rate:.2%}")
        print(f"Verdict: {report['builder_verdict']['verdict']}")
        print(f"Session window: {config.session_label} ({config.session_start_hour:02d}:00-{config.session_end_hour:02d}:00 UTC)")
        print(f"Hour trade distribution: {runner.hour_trade_counts}")
        return report
    finally:
        conn.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest Session Sweep Specialist (sweep_reclaim family variant 4)")
    parser.add_argument("--source-db", type=Path, required=True, help="Path to source SQLite database")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--initial-equity", type=float, default=DEFAULT_INITIAL_EQUITY)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MARKDOWN_PATH)
    parser.add_argument("--output-audit", type=Path, default=DEFAULT_AUDIT_PATH)
    parser.add_argument("--session-start", type=int, default=0, help="Session start hour UTC (inclusive)")
    parser.add_argument("--session-end", type=int, default=8, help="Session end hour UTC (exclusive)")
    parser.add_argument("--session-label", default="asia", help="Session label for reporting")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = SessionSweepConfig(
        session_start_hour=args.session_start,
        session_end_hour=args.session_end,
        session_label=args.session_label,
    )
    run_session_backtest(
        source_db_path=args.source_db,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_equity=args.initial_equity,
        output_json=args.output_json,
        output_md=args.output_md,
        output_audit=args.output_audit,
        session_config=config,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
