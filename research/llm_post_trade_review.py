from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from research.analyze_trades import (
    AnalyzeTradesConfig,
    ClosedTradeRecord,
    TradeAnalysisReport,
    analyze_closed_trades,
    load_closed_trades,
)
from settings import load_settings


@dataclass(slots=True, frozen=True)
class ReviewBuildConfig:
    winners_sample_size: int = 5
    losers_sample_size: int = 5
    max_feature_keys_per_trade: int = 12


@dataclass(slots=True)
class LLMReviewPackage:
    generated_at_utc: datetime
    query: AnalyzeTradesConfig
    analysis: TradeAnalysisReport
    sampled_trades: dict[str, list[dict[str, Any]]]
    response_schema: dict[str, Any]
    system_prompt: str
    user_prompt: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        query_payload = asdict(self.query)
        query_payload["start_ts_utc"] = self.query.start_ts_utc.isoformat() if self.query.start_ts_utc else None
        query_payload["end_ts_utc"] = self.query.end_ts_utc.isoformat() if self.query.end_ts_utc else None
        return {
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "query": query_payload,
            "analysis": self.analysis.to_dict(),
            "sampled_trades": self.sampled_trades,
            "response_schema": self.response_schema,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "notes": list(self.notes),
        }


def build_llm_review_package(
    connection: sqlite3.Connection,
    query: AnalyzeTradesConfig | None = None,
    *,
    build_config: ReviewBuildConfig | None = None,
    now_provider: Callable[[], datetime] | None = None,
) -> LLMReviewPackage:
    normalized_query = query or AnalyzeTradesConfig()
    review_cfg = build_config or ReviewBuildConfig()
    generated_at = _to_utc((now_provider or (lambda: datetime.now(timezone.utc)))())

    analysis = analyze_closed_trades(connection, normalized_query, now_provider=lambda: generated_at)
    trades = load_closed_trades(connection, normalized_query)
    sampled = _sample_trades_for_review(trades, review_cfg)
    schema = _review_response_schema()

    system_prompt = _system_prompt_template()
    user_prompt = _build_user_prompt(analysis, sampled, normalized_query)

    notes = [
        "Offline only: this module prepares review payloads and does not execute live decisions.",
        "All timestamps are normalized to UTC.",
    ]
    return LLMReviewPackage(
        generated_at_utc=generated_at,
        query=normalized_query,
        analysis=analysis,
        sampled_trades=sampled,
        response_schema=schema,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        notes=notes,
    )


def save_review_package_json(package: LLMReviewPackage, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(package.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


def _sample_trades_for_review(trades: list[ClosedTradeRecord], config: ReviewBuildConfig) -> dict[str, list[dict[str, Any]]]:
    winners_sorted = sorted(trades, key=lambda item: (item.pnl_r, item.trade_id), reverse=True)
    losers_sorted = sorted(trades, key=lambda item: (item.pnl_r, item.trade_id))

    winners = _trade_context_rows(winners_sorted, max(config.winners_sample_size, 0), config.max_feature_keys_per_trade)
    used_trade_ids = {row["trade_id"] for row in winners}
    losers = _trade_context_rows(
        [trade for trade in losers_sorted if trade.trade_id not in used_trade_ids],
        max(config.losers_sample_size, 0),
        config.max_feature_keys_per_trade,
    )
    return {"winners": winners, "losers": losers}


def _trade_context_rows(
    ordered_trades: list[ClosedTradeRecord],
    limit: int,
    max_feature_keys: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in ordered_trades[:limit]:
        hold_minutes = max((trade.closed_at - trade.opened_at).total_seconds() / 60.0, 0.0)
        rows.append(
            {
                "trade_id": trade.trade_id,
                "signal_id": trade.signal_id,
                "symbol": trade.symbol,
                "direction": trade.direction,
                "regime": trade.regime,
                "confluence_score": trade.confluence_score,
                "opened_at": trade.opened_at.isoformat(),
                "closed_at": trade.closed_at.isoformat(),
                "hold_minutes": hold_minutes,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "size": trade.size,
                "fees_total": trade.fees_total,
                "slippage_bps_avg": trade.slippage_bps_avg,
                "pnl_abs": trade.pnl_abs,
                "pnl_r": trade.pnl_r,
                "mae": trade.mae,
                "mfe": trade.mfe,
                "exit_reason": trade.exit_reason,
                "features_focus": _features_focus(trade.features_at_entry_json, max_feature_keys),
            }
        )
    return rows


def _features_focus(features: dict[str, Any], max_feature_keys: int) -> dict[str, Any]:
    if max_feature_keys <= 0:
        return {}
    priority_keys = (
        "atr_15m",
        "sweep_depth_pct",
        "funding_pct_60d",
        "oi_zscore_60d",
        "cvd_15m",
        "tfi_60s",
        "force_order_rate_60s",
        "force_order_spike",
    )
    focus: dict[str, Any] = {}
    for key in priority_keys:
        if key in features:
            focus[key] = features[key]
        if len(focus) >= max_feature_keys:
            return focus

    for key in sorted(features):
        if key in focus:
            continue
        focus[key] = features[key]
        if len(focus) >= max_feature_keys:
            break
    return focus


def _review_response_schema() -> dict[str, Any]:
    return {
        "summary": {
            "edge_quality": "string",
            "risk_discipline": "string",
            "execution_quality": "string",
            "confidence": "LOW | MEDIUM | HIGH",
        },
        "strengths": [
            {
                "title": "string",
                "evidence_trade_ids": ["string"],
            }
        ],
        "weaknesses": [
            {
                "title": "string",
                "evidence_trade_ids": ["string"],
                "impact": "string",
            }
        ],
        "parameter_hypotheses": [
            {
                "parameter": "string",
                "proposed_change": "string",
                "rationale": "string",
                "expected_effect": "string",
            }
        ],
        "risk_flags": [
            {
                "flag": "string",
                "severity": "LOW | MEDIUM | HIGH",
                "evidence_trade_ids": ["string"],
            }
        ],
        "next_actions": [
            {
                "action": "string",
                "priority": "P0 | P1 | P2",
                "owner": "research | strategy | execution",
            }
        ],
    }


def _system_prompt_template() -> str:
    return (
        "You are an offline BTC futures post-trade reviewer. "
        "Use only the provided data, avoid speculation, and output strict JSON that matches response_schema. "
        "Do not include markdown. Do not suggest live-path automation."
    )


def _build_user_prompt(
    analysis: TradeAnalysisReport,
    sampled: dict[str, list[dict[str, Any]]],
    query: AnalyzeTradesConfig,
) -> str:
    query_payload = {
        "symbol": query.symbol.upper() if query.symbol else None,
        "start_ts_utc": query.start_ts_utc.isoformat() if query.start_ts_utc else None,
        "end_ts_utc": query.end_ts_utc.isoformat() if query.end_ts_utc else None,
        "limit": query.limit,
    }
    payload = {
        "query": query_payload,
        "analysis": analysis.to_dict(),
        "sampled_trades": sampled,
        "instruction": (
            "Review the strategy behavior, highlight robust vs fragile patterns, "
            "and propose auditable offline parameter hypotheses."
        ),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_cli_timestamp(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    return _to_utc(datetime.fromisoformat(raw))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an offline LLM post-trade review payload from SQLite trade logs.")
    parser.add_argument("--db-path", type=Path, help="Path to SQLite DB. Defaults to settings.storage.db_path.")
    parser.add_argument("--symbol", type=str, default=None, help="Optional symbol filter, e.g. BTCUSDT.")
    parser.add_argument("--start-ts", type=str, default=None, help="Inclusive UTC start timestamp (ISO-8601).")
    parser.add_argument("--end-ts", type=str, default=None, help="Exclusive UTC end timestamp (ISO-8601).")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of closed trades.")
    parser.add_argument("--output-json", type=Path, default=None, help="Optional path for review package JSON.")
    parser.add_argument("--winners", type=int, default=5, help="Number of winning trades to sample.")
    parser.add_argument("--losers", type=int, default=5, help="Number of losing trades to sample.")
    parser.add_argument("--max-feature-keys", type=int, default=12, help="Max feature keys per sampled trade.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = load_settings()
    if args.db_path is not None:
        db_path = args.db_path
    elif settings.storage is not None:
        db_path = settings.storage.db_path
    else:
        raise ValueError("DB path not provided and settings.storage is unavailable.")

    query = AnalyzeTradesConfig(
        symbol=args.symbol,
        start_ts_utc=_parse_cli_timestamp(args.start_ts),
        end_ts_utc=_parse_cli_timestamp(args.end_ts),
        limit=args.limit,
    )
    build_cfg = ReviewBuildConfig(
        winners_sample_size=args.winners,
        losers_sample_size=args.losers,
        max_feature_keys_per_trade=args.max_feature_keys,
    )

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        package = build_llm_review_package(connection, query, build_config=build_cfg)
    finally:
        connection.close()

    if args.output_json is not None:
        save_review_package_json(package, args.output_json)
    else:
        print(json.dumps(package.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
