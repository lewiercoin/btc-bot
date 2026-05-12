from __future__ import annotations

import os
import sys

if __package__ in {None, ""}:
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    if _script_dir in sys.path:
        sys.path.remove(_script_dir)
    _project_root = os.path.dirname(_script_dir)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

import argparse
import json
import math
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig, BacktestResult, BacktestRunner
from core.models import Features, RegimeState, SignalCandidate, TradeLog
from research_lab.setups import CompressionBreakoutLong
from research_lab.setups.compression_breakout import CompressionBreakoutConfig
from settings import load_settings
from storage.repositories import fetch_funding_rates

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = Path("research_lab/runs/compression_breakout_backtest.json")
DEFAULT_MARKDOWN_PATH = Path("research_lab/reports/compression_breakout_validation_report.md")


@dataclass(slots=True)
class CompressionDecisionRecord:
    timestamp: datetime
    regime: str
    candidate_generated: bool
    rejection_reasons: list[str] = field(default_factory=list)
    signal_id: str | None = None
    candidate_reasons: list[str] = field(default_factory=list)
    confluence_score: float | None = None
    atr_percentile: float | None = None
    range_width_atr: float | None = None
    compression_duration_bars: int | None = None
    internal_compression_detected: bool | None = None
    breakout_size_atr: float | None = None
    tfi_60s: float | None = None
    oi_delta_pct: float | None = None
    governance_veto_reason: str | None = None
    risk_block_reason: str | None = None
    trade_opened: bool = False
    trade_closed: bool = False
    trade_id: str | None = None
    pnl_abs: float | None = None
    pnl_r: float | None = None
    mfe: float | None = None
    exit_reason: str | None = None


class CompressionBreakoutBacktestRunner(BacktestRunner):
    """Backtests compression_breakout_long only, outside the live path."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        setup: CompressionBreakoutLong | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(connection, **kwargs)
        self.setup = setup or CompressionBreakoutLong()
        self.decision_records: list[CompressionDecisionRecord] = []
        self._records_by_object_id: dict[int, CompressionDecisionRecord] = {}
        self._records_by_signal_id: dict[str, CompressionDecisionRecord] = {}
        self._atr_4h_norm_history: list[float] = []

    def run(self, config: BacktestConfig) -> BacktestResult:
        symbol = config.symbol.upper()
        initial_equity = max(float(config.initial_equity), 1e-8)

        self._signal_counter = 0
        self._position_counter = 0
        self._trade_counter = 0
        self.decision_records = []
        self._records_by_object_id = {}
        self._records_by_signal_id = {}
        self._atr_4h_norm_history = []

        replay_loader = self._custom_replay_loader or self._build_default_replay_loader(config)
        fill_model = self._custom_fill_model or self._build_default_fill_model(config)
        funding_samples = fetch_funding_rates(self.connection, symbol=symbol)
        feature_engine, regime_engine, context_engine, _signal_engine, governance, risk_engine = self._build_engines()

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
            now = _to_utc(snapshot.timestamp)
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
            self._attach_research_atr_history(snapshot=snapshot, features=features)
            regime = regime_engine.classify(features)
            _context = context_engine.classify(features)
            candidate = self._generate_candidate(snapshot=snapshot, features=features, regime=regime)

            if candidate is not None:
                self._signal_counter += 1
                candidate.signal_id = self._make_signal_id(now, self._signal_counter)
                self._register_candidate_id(candidate)
                governance_decision = governance.evaluate(candidate)
                self._register_governance_decision(candidate, governance_decision)
                if governance_decision.approved:
                    executable = governance.to_executable(candidate, governance_decision)
                    risk_decision = risk_engine.evaluate(
                        signal=executable,
                        equity=equity,
                        open_positions=len(open_positions),
                    )
                    self._register_risk_decision(candidate.signal_id, risk_decision)
                    if risk_decision.allowed:
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

            equity_curve.append((now, equity))

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
        self._attach_trade_outcomes(trades)
        performance = self._summarize_trades(trades, initial_equity=initial_equity)
        return BacktestResult(performance=performance, trades=trades, equity_curve=equity_curve)

    def _build_default_replay_loader(self, config: BacktestConfig):
        from backtest.backtest_runner import ReplayLoader, ReplayLoaderConfig

        return ReplayLoader(
            self.connection,
            ReplayLoaderConfig(
                candles_15m_lookback=max(config.candles_15m_lookback, 300),
                candles_1h_lookback=config.candles_1h_lookback,
                candles_4h_lookback=max(config.candles_4h_lookback, 300),
                funding_lookback=config.funding_lookback,
            ),
        )

    def _build_default_fill_model(self, config: BacktestConfig):
        from backtest.backtest_runner import FillModelConfig, SimpleFillModel

        return SimpleFillModel(
            FillModelConfig(
                slippage_bps_limit=config.slippage_bps_limit,
                slippage_bps_market=config.slippage_bps_market,
                fee_rate_maker=config.fee_rate_maker,
                fee_rate_taker=config.fee_rate_taker,
            )
        )

    def _summarize_trades(self, trades: list[Any], *, initial_equity: float):
        from backtest.performance import summarize

        return summarize(trades, initial_equity=initial_equity)

    def _generate_candidate(
        self,
        *,
        snapshot: Any,
        features: Features,
        regime: RegimeState,
    ) -> SignalCandidate | None:
        evaluation = self.setup.evaluate_structure(
            features=features,
            snapshot=snapshot,
            regime=regime,
            config=self.settings.strategy,
        )
        candidate = self.setup.generate_signal_candidate(
            features=features,
            snapshot=snapshot,
            regime=regime,
            config=self.settings.strategy,
        )
        record = self._record_decision(
            features=features,
            regime=regime,
            evaluation=evaluation,
            candidate=candidate,
        )
        if candidate is not None:
            self._records_by_object_id[id(candidate)] = record
        return candidate

    def _attach_research_atr_history(self, *, snapshot: Any, features: Features) -> None:
        if float(features.atr_4h_norm) > 0:
            self._atr_4h_norm_history.append(float(features.atr_4h_norm))
        max_window = 500
        if len(self._atr_4h_norm_history) > max_window:
            self._atr_4h_norm_history = self._atr_4h_norm_history[-max_window:]
        snapshot.source_meta["research_atr_4h_norm_history"] = list(self._atr_4h_norm_history)

    def _record_decision(
        self,
        *,
        features: Features,
        regime: RegimeState,
        evaluation: Any,
        candidate: SignalCandidate | None,
    ) -> CompressionDecisionRecord:
        metrics = dict(getattr(evaluation, "metrics", {}) or {})
        record = CompressionDecisionRecord(
            timestamp=_to_utc(features.timestamp),
            regime=regime.value,
            candidate_generated=candidate is not None,
            rejection_reasons=list(getattr(evaluation, "reasons", []) or []),
            signal_id=None if candidate is None else candidate.signal_id,
            candidate_reasons=[] if candidate is None else list(candidate.reasons),
            confluence_score=None if candidate is None else float(candidate.confluence_score),
            atr_percentile=_optional_float(metrics.get("atr_percentile")),
            range_width_atr=_optional_float(metrics.get("range_width_atr")),
            compression_duration_bars=_optional_int(metrics.get("compression_duration_bars")),
            internal_compression_detected=_optional_bool(metrics.get("internal_compression_detected")),
            breakout_size_atr=_optional_float(metrics.get("breakout_size_atr")),
            tfi_60s=float(features.tfi_60s),
            oi_delta_pct=float(features.oi_delta_pct),
        )
        self.decision_records.append(record)
        return record

    def _register_candidate_id(self, candidate: SignalCandidate) -> None:
        record = self._records_by_object_id.get(id(candidate))
        if record is None:
            return
        record.signal_id = candidate.signal_id
        self._records_by_signal_id[candidate.signal_id] = record

    def _register_governance_decision(self, candidate: SignalCandidate, decision: Any) -> None:
        record = self._records_by_signal_id.get(candidate.signal_id)
        if record is None:
            return
        if not bool(getattr(decision, "approved", False)):
            notes = list(getattr(decision, "notes", []) or [])
            record.governance_veto_reason = str(notes[0]) if notes else "governance_rejected"

    def _register_risk_decision(self, signal_id: str, decision: Any) -> None:
        record = self._records_by_signal_id.get(signal_id)
        if record is None:
            return
        if bool(getattr(decision, "allowed", False)):
            record.trade_opened = True
            return
        reason = getattr(decision, "reason", None)
        record.risk_block_reason = str(reason) if reason is not None else "risk_rejected"

    def _attach_trade_outcomes(self, trades: list[TradeLog]) -> None:
        for trade in trades:
            record = self._records_by_signal_id.get(trade.signal_id)
            if record is None:
                continue
            record.trade_opened = True
            record.trade_closed = trade.closed_at is not None
            record.trade_id = trade.trade_id
            record.pnl_abs = float(trade.pnl_abs)
            record.pnl_r = float(trade.pnl_r)
            record.mfe = float(trade.mfe)
            record.exit_reason = trade.exit_reason


def build_compression_report(
    *,
    result: BacktestResult,
    records: list[CompressionDecisionRecord],
    source_db_path: Path,
    start_date: str,
    end_date: str,
    initial_equity: float,
) -> dict[str, Any]:
    trades = list(result.trades)
    by_regime = _performance_by_regime(trades, initial_equity=initial_equity)
    generated = [record for record in records if record.candidate_generated]
    closed = [record for record in records if record.trade_closed]
    internal_compression_closed = [record for record in closed if bool(record.internal_compression_detected)]
    followed_through = [record for record in closed if record.mfe is not None and record.mfe >= 1.0]
    return {
        "milestone": "COMPRESSION-BREAKOUT-RESEARCH-V1",
        "setup_type": "compression_breakout_long",
        "source_db_path": str(source_db_path),
        "date_range": {"start": start_date, "end": end_date},
        "performance": _dataclass_to_jsonable(result.performance),
        "per_regime": by_regime,
        "decision_summary": {
            "cycles": len(records),
            "candidates": len(generated),
            "closed_trades": len(closed),
            "internal_compression_closed_trades": len(internal_compression_closed),
            "top_rejection_reasons": _top_rejection_reasons(records),
            "breakout_followthrough_rate": _safe_div(len(followed_through), len(closed)),
            "avg_compression_duration_bars": _average(
                record.compression_duration_bars for record in generated if record.compression_duration_bars is not None
            ),
            "avg_breakout_size_atr": _average(
                record.breakout_size_atr for record in generated if record.breakout_size_atr is not None
            ),
        },
        "signals": [_record_to_json(record) for record in generated],
        "closed_records": [_record_to_json(record) for record in closed],
    }


def write_compression_markdown_report(report: dict[str, Any], output_path: Path) -> None:
    perf = report["performance"]
    summary = report["decision_summary"]
    lines = [
        "# Compression Breakout Validation Report",
        "",
        f"Milestone: `{report['milestone']}`",
        f"Setup: `{report['setup_type']}`",
        f"Date range: `{report['date_range']['start']}` -> `{report['date_range']['end']}`",
        "",
        "## Overall",
        "",
        f"- Trades: {perf['trades_count']}",
        f"- Expectancy R: {perf['expectancy_r']}",
        f"- Profit factor: {perf['profit_factor']}",
        f"- Max drawdown pct: {perf['max_drawdown_pct']}",
        f"- Sharpe: {perf['sharpe_ratio']}",
        "",
        "## Decision Funnel",
        "",
        f"- Decision cycles: {summary['cycles']}",
        f"- Candidates: {summary['candidates']}",
        f"- Closed trades: {summary['closed_trades']}",
        f"- Internal compression closed trades: {summary['internal_compression_closed_trades']}",
        f"- Breakout follow-through rate: {summary['breakout_followthrough_rate']}",
        f"- Avg compression duration bars: {summary['avg_compression_duration_bars']}",
        f"- Avg breakout size ATR: {summary['avg_breakout_size_atr']}",
        "",
        "## Per Regime",
        "",
        "| Regime | Trades | ER | PF | DD |",
        "|---|---:|---:|---:|---:|",
    ]
    for regime, row in sorted(report["per_regime"].items()):
        lines.append(
            f"| {regime} | {row['trades_count']} | {row['expectancy_r']} | "
            f"{row['profit_factor']} | {row['max_drawdown_pct']} |"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_compression_backtest(
    *,
    source_db_path: Path,
    start_date: str,
    end_date: str,
    output_path: Path,
    initial_equity: float = 10_000.0,
) -> dict[str, Any]:
    conn = sqlite3.connect(source_db_path)
    conn.row_factory = sqlite3.Row
    try:
        settings = load_settings(project_root=PROJECT_ROOT, profile="research")
        runner = CompressionBreakoutBacktestRunner(
            conn,
            settings=settings,
            setup=CompressionBreakoutLong(CompressionBreakoutConfig()),
        )
        result = runner.run(
            BacktestConfig(
                start_date=start_date,
                end_date=end_date,
                symbol=settings.strategy.symbol,
                initial_equity=initial_equity,
            )
        )
        report = build_compression_report(
            result=result,
            records=runner.decision_records,
            source_db_path=source_db_path,
            start_date=start_date,
            end_date=end_date,
            initial_equity=initial_equity,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(_sanitize_json(report), indent=2, sort_keys=True), encoding="utf-8")
        write_compression_markdown_report(report, DEFAULT_MARKDOWN_PATH)
        return report
    finally:
        conn.close()


def _performance_by_regime(trades: list[TradeLog], *, initial_equity: float) -> dict[str, dict[str, Any]]:
    from backtest.performance import summarize

    regimes = sorted({str(trade.regime) for trade in trades})
    return {
        regime: _dataclass_to_jsonable(
            summarize([trade for trade in trades if str(trade.regime) == regime], initial_equity=initial_equity)
        )
        for regime in regimes
    }


def _top_rejection_reasons(records: list[CompressionDecisionRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        if record.candidate_generated:
            continue
        for reason in record.rejection_reasons:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:20])


def _record_to_json(record: CompressionDecisionRecord) -> dict[str, Any]:
    return _sanitize_json(asdict(record))


def _dataclass_to_jsonable(value: Any) -> dict[str, Any]:
    return _sanitize_json(asdict(value))


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, datetime):
        return _to_utc(value).isoformat()
    if isinstance(value, float):
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        if math.isnan(value):
            return "nan"
        return round(value, 6)
    return value


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_div(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _average(values: Any) -> float | None:
    items = [float(value) for value in values]
    if not items:
        return None
    return round(sum(items) / len(items), 6)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest compression_breakout_long research setup.")
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-03-29")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    run_compression_backtest(
        source_db_path=args.source_db,
        start_date=args.start_date,
        end_date=args.end_date,
        output_path=args.output,
        initial_equity=args.initial_equity,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
