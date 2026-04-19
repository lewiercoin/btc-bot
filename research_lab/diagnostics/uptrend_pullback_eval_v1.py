from __future__ import annotations

import argparse
import json
import math
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from backtest.backtest_runner import BacktestConfig, BacktestResult, BacktestRunner
from backtest.performance import summarize
from core.models import ExecutableSignal, Features, RegimeState, SignalCandidate, SignalDiagnostics, TradeLog
from research_lab.db_snapshot import create_trial_snapshot, open_snapshot_connection, verify_required_tables
from settings import load_settings
from storage.db import init_db

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = Path("research_lab/runs/uptrend_pullback_eval_v1.json")
MILESTONE_NAME = "UPTREND-PULLBACK-EVAL-V1"


@dataclass(slots=True)
class PullbackEventRecord:
    event_id: str
    timestamp: datetime
    candidate_generated: bool
    pre_candidate_blocked_by: str | None
    signal_id: str | None
    candidate_reasons: list[str]
    confluence_score: float | None
    tfi_60s: float
    sweep_depth_pct: float | None
    ema_gap_pct: float
    funding_8h: float
    governance_veto_reason: str | None = None
    risk_block_reason: str | None = None
    trade_opened: bool = False
    trade_closed: bool = False
    trade_id: str | None = None
    pnl_abs: float | None = None
    pnl_r: float | None = None
    exit_reason: str | None = None
    outcome_bucket: str | None = None


def _safe_div(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def _safe_round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _first_reason(reasons: list[str] | None, fallback: str) -> str:
    if reasons:
        return str(reasons[0])
    return fallback


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, datetime):
        return _to_utc(value).isoformat()
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
    return value


def _ema_gap_pct(features: Features) -> float:
    if features.ema200_4h == 0:
        return 0.0
    return (features.ema50_4h - features.ema200_4h) / features.ema200_4h


def _is_pullback_detected(features: Features, regime: RegimeState) -> bool:
    return (
        regime is RegimeState.UPTREND
        and features.sweep_detected
        and features.sweep_side == "LOW"
        and features.sweep_level is not None
        and not features.reclaim_detected
    )


def _is_pullback_candidate(candidate: SignalCandidate | None) -> bool:
    if candidate is None:
        return False
    return "uptrend_pullback_entry" in candidate.reasons


def _outcome_bucket(pnl_r: float | None) -> str | None:
    if pnl_r is None:
        return None
    magnitude = abs(float(pnl_r))
    if magnitude < 0.05:
        return "breakeven"
    if pnl_r > 0:
        if magnitude < 1.0:
            return "win_lt_1R"
        if magnitude < 2.0:
            return "win_1R_to_2R"
        return "win_ge_2R"
    if magnitude < 1.0:
        return "loss_lt_1R"
    if magnitude < 2.0:
        return "loss_1R_to_2R"
    return "loss_ge_2R"


def _numeric_stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
        }
    ordered = sorted(float(value) for value in values)
    count = len(ordered)
    midpoint = count // 2
    if count % 2 == 0:
        median_value = (ordered[midpoint - 1] + ordered[midpoint]) / 2.0
    else:
        median_value = ordered[midpoint]
    return {
        "count": count,
        "mean": _safe_round(sum(ordered) / count, 4),
        "median": _safe_round(median_value, 4),
        "min": _safe_round(ordered[0], 4),
        "max": _safe_round(ordered[-1], 4),
    }


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_decimal(value: float) -> str:
    return f"{value:.2f}"


def _bucket_value(
    value: float | None,
    *,
    lower_bounds: list[float],
    formatter: Callable[[float], str],
) -> tuple[str, float]:
    if value is None:
        return "missing", float("-inf")
    numeric = float(value)
    if numeric < lower_bounds[0]:
        return f"<{formatter(lower_bounds[0])}", lower_bounds[0] - 1.0
    for index, lower in enumerate(lower_bounds):
        upper = lower_bounds[index + 1] if index + 1 < len(lower_bounds) else None
        if upper is None:
            return f"{formatter(lower)}+", lower
        if numeric < upper:
            return f"{formatter(lower)}-{formatter(upper)}", lower
    return f"{formatter(lower_bounds[-1])}+", lower_bounds[-1]


def _feature_bucket(feature_name: str, value: float | None) -> tuple[str, float]:
    if feature_name == "confluence_score":
        return _bucket_value(value, lower_bounds=[8.0, 9.0, 10.0, 11.0, 12.0], formatter=_format_decimal)
    if feature_name == "tfi_60s":
        return _bucket_value(value, lower_bounds=[0.13, 0.20, 0.30, 0.40, 0.50], formatter=_format_decimal)
    if feature_name == "sweep_depth_pct":
        return _bucket_value(value, lower_bounds=[0.0030, 0.0050, 0.0075, 0.0100, 0.0150], formatter=_format_percent)
    if feature_name == "ema_gap_pct":
        return _bucket_value(value, lower_bounds=[0.0, 0.01, 0.02, 0.03, 0.05], formatter=_format_percent)
    raise ValueError(f"Unsupported feature bucket: {feature_name}")


class _PullbackSignalProxy:
    def __init__(self, wrapped: Any, runner: "UptrendPullbackEvaluationRunner") -> None:
        self._wrapped = wrapped
        self._runner = runner

    def generate(self, features: Features, regime: RegimeState) -> SignalCandidate | None:
        diagnostics = self._wrapped.diagnose(features, regime)
        record: PullbackEventRecord | None = None
        if _is_pullback_detected(features, regime):
            record = self._runner.register_detected_event(features, diagnostics)
        candidate = self._wrapped.generate(features, regime, diagnostics=diagnostics)
        if _is_pullback_candidate(candidate):
            self._runner.register_candidate(
                record=record,
                candidate=candidate,
                features=features,
                diagnostics=diagnostics,
            )
        return candidate

    def __getattr__(self, item: str) -> Any:
        return getattr(self._wrapped, item)


class _PullbackGovernanceProxy:
    def __init__(self, wrapped: Any, runner: "UptrendPullbackEvaluationRunner") -> None:
        self._wrapped = wrapped
        self._runner = runner

    def evaluate(self, candidate: SignalCandidate) -> Any:
        decision = self._wrapped.evaluate(candidate)
        self._runner.register_governance_decision(candidate, decision)
        return decision

    def __getattr__(self, item: str) -> Any:
        return getattr(self._wrapped, item)


class _PullbackRiskProxy:
    def __init__(self, wrapped: Any, runner: "UptrendPullbackEvaluationRunner") -> None:
        self._wrapped = wrapped
        self._runner = runner

    def evaluate(self, signal: ExecutableSignal, equity: float, open_positions: int) -> Any:
        decision = self._wrapped.evaluate(signal, equity=equity, open_positions=open_positions)
        self._runner.register_risk_decision(signal, decision)
        return decision

    def __getattr__(self, item: str) -> Any:
        return getattr(self._wrapped, item)


class UptrendPullbackEvaluationRunner(BacktestRunner):
    def __init__(self, connection, **kwargs: Any) -> None:
        super().__init__(connection, **kwargs)
        self.pullback_events: list[PullbackEventRecord] = []
        self._records_by_object_id: dict[int, PullbackEventRecord] = {}
        self._records_by_signal_id: dict[str, PullbackEventRecord] = {}
        self._event_counter = 0

    def _build_engines(self):  # type: ignore[override]
        feature_engine, regime_engine, signal_engine, governance, risk_engine = super()._build_engines()
        return (
            feature_engine,
            regime_engine,
            _PullbackSignalProxy(signal_engine, self),
            _PullbackGovernanceProxy(governance, self),
            _PullbackRiskProxy(risk_engine, self),
        )

    def run(self, config: BacktestConfig) -> BacktestResult:
        self.pullback_events = []
        self._records_by_object_id = {}
        self._records_by_signal_id = {}
        self._event_counter = 0
        result = super().run(config)
        self.attach_trade_outcomes(result.trades)
        return result

    def register_detected_event(
        self,
        features: Features,
        diagnostics: SignalDiagnostics,
    ) -> PullbackEventRecord:
        self._event_counter += 1
        record = PullbackEventRecord(
            event_id=f"pullback-event-{self._event_counter:05d}",
            timestamp=_to_utc(features.timestamp),
            candidate_generated=False,
            pre_candidate_blocked_by=diagnostics.blocked_by,
            signal_id=None,
            candidate_reasons=[],
            confluence_score=diagnostics.confluence_preview,
            tfi_60s=float(features.tfi_60s),
            sweep_depth_pct=None if features.sweep_depth_pct is None else float(features.sweep_depth_pct),
            ema_gap_pct=_ema_gap_pct(features),
            funding_8h=float(features.funding_8h),
        )
        self.pullback_events.append(record)
        return record

    def register_candidate(
        self,
        *,
        record: PullbackEventRecord | None,
        candidate: SignalCandidate,
        features: Features,
        diagnostics: SignalDiagnostics,
    ) -> None:
        resolved = record or self.register_detected_event(features, diagnostics)
        resolved.candidate_generated = True
        resolved.pre_candidate_blocked_by = None
        resolved.candidate_reasons = list(candidate.reasons)
        resolved.confluence_score = float(candidate.confluence_score)
        self._records_by_object_id[id(candidate)] = resolved

    def register_governance_decision(self, candidate: SignalCandidate, decision: Any) -> None:
        record = self._records_by_object_id.get(id(candidate))
        if record is None:
            return
        record.signal_id = candidate.signal_id
        self._records_by_signal_id[candidate.signal_id] = record
        if not bool(getattr(decision, "approved", False)):
            notes = list(getattr(decision, "notes", []) or [])
            record.governance_veto_reason = _first_reason(notes, "governance_rejected")

    def register_risk_decision(self, signal: ExecutableSignal, decision: Any) -> None:
        record = self._records_by_signal_id.get(signal.signal_id)
        if record is None:
            return
        if bool(getattr(decision, "allowed", False)):
            record.trade_opened = True
            return
        reason = getattr(decision, "reason", None)
        record.risk_block_reason = str(reason) if reason is not None else "risk_rejected"

    def attach_trade_outcomes(self, trades: list[TradeLog]) -> None:
        for trade in trades:
            record = self._records_by_signal_id.get(trade.signal_id)
            if record is None:
                continue
            record.trade_opened = True
            record.trade_closed = trade.closed_at is not None
            record.trade_id = trade.trade_id
            record.pnl_abs = float(trade.pnl_abs)
            record.pnl_r = float(trade.pnl_r)
            record.exit_reason = trade.exit_reason
            record.outcome_bucket = _outcome_bucket(record.pnl_r)


def _build_stage_counts(records: list[PullbackEventRecord]) -> dict[str, Any]:
    detected_count = len(records)
    candidate_records = [record for record in records if record.candidate_generated]
    governance_veto_records = [record for record in candidate_records if record.governance_veto_reason is not None]
    governance_pass_records = [record for record in candidate_records if record.governance_veto_reason is None]
    risk_block_records = [record for record in governance_pass_records if record.risk_block_reason is not None]
    trade_open_records = [record for record in candidate_records if record.trade_opened]
    trade_closed_records = [record for record in trade_open_records if record.trade_closed]
    pre_candidate_counts = Counter(
        record.pre_candidate_blocked_by
        for record in records
        if not record.candidate_generated and record.pre_candidate_blocked_by is not None
    )
    governance_reason_counts = Counter(
        record.governance_veto_reason
        for record in governance_veto_records
        if record.governance_veto_reason is not None
    )
    risk_reason_counts = Counter(
        record.risk_block_reason
        for record in risk_block_records
        if record.risk_block_reason is not None
    )
    outcome_counts = Counter(
        record.outcome_bucket
        for record in trade_closed_records
        if record.outcome_bucket is not None
    )
    return {
        "detected": {
            "count": detected_count,
            "pct_of_detected": 1.0 if detected_count else None,
        },
        "candidate_generated": {
            "count": len(candidate_records),
            "pct_of_detected": _safe_round(_safe_div(len(candidate_records), detected_count)),
        },
        "pre_candidate_filtered": {
            "count": detected_count - len(candidate_records),
            "pct_of_detected": _safe_round(_safe_div(detected_count - len(candidate_records), detected_count)),
            "by_reason": dict(pre_candidate_counts),
        },
        "governance_veto": {
            "count": len(governance_veto_records),
            "pct_of_candidates": _safe_round(_safe_div(len(governance_veto_records), len(candidate_records))),
            "by_reason": dict(governance_reason_counts),
        },
        "governance_pass": {
            "count": len(governance_pass_records),
            "pct_of_candidates": _safe_round(_safe_div(len(governance_pass_records), len(candidate_records))),
        },
        "risk_block": {
            "count": len(risk_block_records),
            "pct_of_governance_pass": _safe_round(_safe_div(len(risk_block_records), len(governance_pass_records))),
            "by_reason": dict(risk_reason_counts),
        },
        "trade_opened": {
            "count": len(trade_open_records),
            "pct_of_candidates": _safe_round(_safe_div(len(trade_open_records), len(candidate_records))),
            "pct_of_governance_pass": _safe_round(_safe_div(len(trade_open_records), len(governance_pass_records))),
        },
        "trade_closed": {
            "count": len(trade_closed_records),
            "pct_of_trade_opened": _safe_round(_safe_div(len(trade_closed_records), len(trade_open_records))),
        },
        "pnl_outcome_buckets": dict(outcome_counts),
    }


def _feature_value(record: PullbackEventRecord, feature_name: str) -> float | None:
    value = getattr(record, feature_name)
    if value is None:
        return None
    return float(value)


def _build_feature_segments(records: list[PullbackEventRecord]) -> dict[str, list[dict[str, Any]]]:
    candidate_records = [record for record in records if record.candidate_generated]
    features = ("confluence_score", "tfi_60s", "sweep_depth_pct", "ema_gap_pct")
    report: dict[str, list[dict[str, Any]]] = {}
    for feature_name in features:
        grouped: dict[str, list[PullbackEventRecord]] = defaultdict(list)
        sort_order: dict[str, float] = {}
        for record in candidate_records:
            label, sort_key = _feature_bucket(feature_name, _feature_value(record, feature_name))
            grouped[label].append(record)
            sort_order[label] = sort_key
        rows: list[dict[str, Any]] = []
        total_candidates = len(candidate_records)
        for label in sorted(grouped, key=lambda item: sort_order[item]):
            bucket_records = grouped[label]
            trades = [record for record in bucket_records if record.trade_opened and record.pnl_r is not None]
            wins = [record for record in trades if record.pnl_r is not None and record.pnl_r > 0]
            losses = [record for record in trades if record.pnl_r is not None and record.pnl_r < 0]
            rows.append(
                {
                    "bucket": label,
                    "candidate_count": len(bucket_records),
                    "candidate_share": _safe_round(_safe_div(len(bucket_records), total_candidates)),
                    "governance_veto_count": sum(1 for record in bucket_records if record.governance_veto_reason is not None),
                    "governance_veto_rate": _safe_round(
                        _safe_div(
                            sum(1 for record in bucket_records if record.governance_veto_reason is not None),
                            len(bucket_records),
                        )
                    ),
                    "risk_block_count": sum(1 for record in bucket_records if record.risk_block_reason is not None),
                    "risk_block_rate": _safe_round(
                        _safe_div(
                            sum(1 for record in bucket_records if record.risk_block_reason is not None),
                            len(bucket_records),
                        )
                    ),
                    "trade_count": len(trades),
                    "trade_rate": _safe_round(_safe_div(len(trades), len(bucket_records))),
                    "win_count": len(wins),
                    "loss_count": len(losses),
                    "win_rate": _safe_round(_safe_div(len(wins), len(trades))),
                    "avg_pnl_r": _safe_round(
                        sum(float(record.pnl_r) for record in trades if record.pnl_r is not None) / len(trades), 4
                    )
                    if trades
                    else None,
                    "median_pnl_r": _numeric_stats(
                        [float(record.pnl_r) for record in trades if record.pnl_r is not None]
                    )["median"],
                    "pnl_abs_sum": _safe_round(
                        sum(float(record.pnl_abs) for record in trades if record.pnl_abs is not None),
                        2,
                    ),
                }
            )
        report[feature_name] = rows
    return report


def _build_cohort_comparison(records: list[PullbackEventRecord]) -> dict[str, Any]:
    candidate_records = [record for record in records if record.candidate_generated]
    profitable_trades = [
        record
        for record in candidate_records
        if record.trade_opened and record.pnl_r is not None and float(record.pnl_r) > 0
    ]
    if profitable_trades:
        viable_definition = "closed trade with pnl_r > 0"
        viable = profitable_trades
        junk_definition = "governance veto, risk block, or closed trade with pnl_r <= 0"
        junk = [
            record
            for record in candidate_records
            if record.governance_veto_reason is not None
            or record.risk_block_reason is not None
            or (record.trade_opened and record.pnl_r is not None and float(record.pnl_r) <= 0)
        ]
    else:
        viable_definition = "trade opened"
        viable = [record for record in candidate_records if record.trade_opened]
        junk_definition = "governance veto or risk block"
        junk = [
            record
            for record in candidate_records
            if record.governance_veto_reason is not None or record.risk_block_reason is not None
        ]

    junk_reason_mix = Counter()
    for record in junk:
        if record.governance_veto_reason is not None:
            junk_reason_mix[f"governance:{record.governance_veto_reason}"] += 1
        elif record.risk_block_reason is not None:
            junk_reason_mix[f"risk:{record.risk_block_reason}"] += 1
        elif record.exit_reason is not None:
            junk_reason_mix[f"trade:{record.exit_reason}"] += 1

    features = ("confluence_score", "tfi_60s", "sweep_depth_pct", "ema_gap_pct")
    feature_stats: dict[str, Any] = {}
    for feature_name in features:
        viable_values = [float(value) for value in (_feature_value(record, feature_name) for record in viable) if value is not None]
        junk_values = [float(value) for value in (_feature_value(record, feature_name) for record in junk) if value is not None]
        viable_stats = _numeric_stats(viable_values)
        junk_stats = _numeric_stats(junk_values)
        viable_mean = viable_stats["mean"]
        junk_mean = junk_stats["mean"]
        feature_stats[feature_name] = {
            "viable": viable_stats,
            "junk": junk_stats,
            "delta_mean": _safe_round(
                (float(viable_mean) - float(junk_mean))
                if viable_mean is not None and junk_mean is not None
                else None,
                4,
            ),
        }

    return {
        "viable_definition": viable_definition,
        "junk_definition": junk_definition,
        "viable_count": len(viable),
        "junk_count": len(junk),
        "feature_stats": feature_stats,
        "junk_reason_mix": dict(junk_reason_mix),
    }


def _pick_bucket(rows: list[dict[str, Any]], *, prefer_high: bool) -> dict[str, Any] | None:
    eligible = [row for row in rows if int(row["trade_count"]) > 0 and row["avg_pnl_r"] is not None]
    if not eligible:
        return None
    if prefer_high:
        return max(eligible, key=lambda row: (float(row["avg_pnl_r"]), int(row["trade_count"])))
    return min(eligible, key=lambda row: (float(row["avg_pnl_r"]), -int(row["trade_count"])))


def _build_interpretation(
    *,
    stage_counts: dict[str, Any],
    feature_segments: dict[str, list[dict[str, Any]]],
    cohort_comparison: dict[str, Any],
) -> list[str]:
    lines: list[str] = []
    pre_candidate = stage_counts["pre_candidate_filtered"]["by_reason"]
    if pre_candidate:
        top_reason, top_count = max(pre_candidate.items(), key=lambda item: item[1])
        lines.append(
            f"Most detected pullbacks died before candidate generation via {top_reason} ({top_count} filtered events)."
        )
    governance_reasons = stage_counts["governance_veto"]["by_reason"]
    if governance_reasons:
        top_reason, top_count = max(governance_reasons.items(), key=lambda item: item[1])
        lines.append(f"Top governance veto was {top_reason} ({top_count} candidates).")
    risk_reasons = stage_counts["risk_block"]["by_reason"]
    if risk_reasons:
        top_reason, top_count = max(risk_reasons.items(), key=lambda item: item[1])
        lines.append(f"Top risk block was {top_reason} ({top_count} candidates).")

    best_confluence = _pick_bucket(feature_segments.get("confluence_score", []), prefer_high=True)
    if best_confluence is not None:
        lines.append(
            "Best confluence bucket was "
            f"{best_confluence['bucket']} with avg_pnl_r={best_confluence['avg_pnl_r']} "
            f"across {best_confluence['trade_count']} trades."
        )

    weakest_tfi = _pick_bucket(feature_segments.get("tfi_60s", []), prefer_high=False)
    if weakest_tfi is not None:
        lines.append(
            "Weakest TFI bucket was "
            f"{weakest_tfi['bucket']} with avg_pnl_r={weakest_tfi['avg_pnl_r']} "
            f"across {weakest_tfi['trade_count']} trades."
        )

    if not lines:
        lines.append("No pullback candidates were detected in the selected period.")
    return lines


def _serialize_records(records: list[PullbackEventRecord]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for record in records:
        payload.append(
            {
                "event_id": record.event_id,
                "timestamp": _to_utc(record.timestamp).isoformat(),
                "candidate_generated": record.candidate_generated,
                "pre_candidate_blocked_by": record.pre_candidate_blocked_by,
                "signal_id": record.signal_id,
                "candidate_reasons": list(record.candidate_reasons),
                "confluence_score": _safe_round(record.confluence_score, 4),
                "tfi_60s": _safe_round(record.tfi_60s, 4),
                "sweep_depth_pct": _safe_round(record.sweep_depth_pct, 6),
                "ema_gap_pct": _safe_round(record.ema_gap_pct, 6),
                "funding_8h": _safe_round(record.funding_8h, 6),
                "governance_veto_reason": record.governance_veto_reason,
                "risk_block_reason": record.risk_block_reason,
                "trade_opened": record.trade_opened,
                "trade_closed": record.trade_closed,
                "trade_id": record.trade_id,
                "pnl_abs": _safe_round(record.pnl_abs, 2),
                "pnl_r": _safe_round(record.pnl_r, 4),
                "exit_reason": record.exit_reason,
                "outcome_bucket": record.outcome_bucket,
            }
        )
    return payload


def build_uptrend_pullback_report(
    *,
    settings: Any,
    result: BacktestResult,
    records: list[PullbackEventRecord],
    start_ts: datetime,
    end_ts: datetime,
    source_db_path: Path,
    initial_equity: float,
) -> dict[str, Any]:
    stage_counts = _build_stage_counts(records)
    feature_segments = _build_feature_segments(records)
    cohort_comparison = _build_cohort_comparison(records)
    pullback_signal_ids = {record.signal_id for record in records if record.signal_id is not None}
    pullback_trades = [trade for trade in result.trades if trade.signal_id in pullback_signal_ids]
    performance = summarize(pullback_trades, initial_equity=float(initial_equity))
    interpretation = _build_interpretation(
        stage_counts=stage_counts,
        feature_segments=feature_segments,
        cohort_comparison=cohort_comparison,
    )
    return {
        "meta": {
            "milestone": MILESTONE_NAME,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_db_path": str(source_db_path),
            "period_start_utc": _to_utc(start_ts).isoformat(),
            "period_end_utc": _to_utc(end_ts).isoformat(),
            "symbol": settings.strategy.symbol.upper(),
            "allow_uptrend_pullback": bool(settings.strategy.allow_uptrend_pullback),
            "config_hash": settings.config_hash,
            "sample_size": {
                "detected": stage_counts["detected"]["count"],
                "candidate_generated": stage_counts["candidate_generated"]["count"],
                "trade_opened": stage_counts["trade_opened"]["count"],
                "trade_closed": stage_counts["trade_closed"]["count"],
            },
            "performance": {
                "trades_count": performance.trades_count,
                "pnl_abs": _safe_round(performance.pnl_abs, 2),
                "pnl_r_sum": _safe_round(performance.pnl_r_sum, 4),
                "expectancy_r": _safe_round(performance.expectancy_r, 4),
                "profit_factor": _safe_round(performance.profit_factor, 4)
                if performance.profit_factor != float("inf")
                else "inf",
            },
        },
        "funnel": stage_counts,
        "feature_segments": feature_segments,
        "cohort_comparison": cohort_comparison,
        "interpretation": interpretation,
        "pullback_events": _serialize_records(records),
    }


def _print_report_summary(report: dict[str, Any], *, output_path: Path | None) -> None:
    meta = report["meta"]
    funnel = report["funnel"]
    print("")
    print(f"{MILESTONE_NAME} summary")
    print(f"period_utc: {meta['period_start_utc']} -> {meta['period_end_utc']}")
    print(f"source_db: {meta['source_db_path']}")
    print(f"flag_state: allow_uptrend_pullback={meta['allow_uptrend_pullback']}")
    print(
        "funnel: "
        f"detected={funnel['detected']['count']} "
        f"generated={funnel['candidate_generated']['count']} "
        f"governance_veto={funnel['governance_veto']['count']} "
        f"risk_block={funnel['risk_block']['count']} "
        f"trade_opened={funnel['trade_opened']['count']} "
        f"trade_closed={funnel['trade_closed']['count']}"
    )
    print(f"pnl_outcome_buckets: {json.dumps(funnel['pnl_outcome_buckets'], sort_keys=True)}")
    for line in report["interpretation"]:
        print(f"- {line}")
    if output_path is not None:
        print(f"evaluation_report_json: {output_path}")


def run_uptrend_pullback_evaluation(
    *,
    source_db_path: Path,
    start_ts: datetime,
    end_ts: datetime,
    output_path: Path | None = None,
    initial_equity: float = 10_000.0,
) -> dict[str, Any]:
    settings = load_settings(project_root=PROJECT_ROOT, profile="research")
    settings = replace(settings, strategy=replace(settings.strategy, allow_uptrend_pullback=True))
    assert settings.storage is not None

    with tempfile.TemporaryDirectory(prefix="uptrend-pullback-eval-") as temp_dir:
        snapshot_path = create_trial_snapshot(
            source_db_path=source_db_path,
            snapshots_dir=Path(temp_dir),
            trial_id="uptrend_pullback_eval_v1",
        )
        conn = open_snapshot_connection(snapshot_path)
        try:
            verify_required_tables(conn)
            init_db(conn, settings.storage.schema_path)
            runner = UptrendPullbackEvaluationRunner(conn, settings=settings)
            result = runner.run(
                BacktestConfig(
                    start_date=start_ts,
                    end_date=end_ts,
                    initial_equity=float(initial_equity),
                    symbol=settings.strategy.symbol.upper(),
                )
            )
            report = build_uptrend_pullback_report(
                settings=settings,
                result=result,
                records=runner.pullback_events,
                start_ts=start_ts,
                end_ts=end_ts,
                source_db_path=source_db_path,
                initial_equity=float(initial_equity),
            )
        finally:
            conn.close()

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(_sanitize_json(report), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    _print_report_summary(report, output_path=output_path)
    return report


def _parse_iso_datetime(raw: str) -> datetime:
    value = datetime.fromisoformat(str(raw))
    return _to_utc(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate UPTREND pullback candidates.")
    parser.add_argument("--db-path", type=Path, default=Path("storage/btc_bot.db"))
    parser.add_argument("--start-date", required=True, help="Inclusive start datetime (ISO-8601 UTC).")
    parser.add_argument("--end-date", required=True, help="Exclusive end datetime (ISO-8601 UTC).")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    start_ts = _parse_iso_datetime(args.start_date)
    end_ts = _parse_iso_datetime(args.end_date)
    if end_ts <= start_ts:
        raise SystemExit("--end-date must be later than --start-date.")
    run_uptrend_pullback_evaluation(
        source_db_path=args.db_path,
        start_ts=start_ts,
        end_ts=end_ts,
        output_path=args.output,
        initial_equity=float(args.initial_equity),
    )


if __name__ == "__main__":
    main()
