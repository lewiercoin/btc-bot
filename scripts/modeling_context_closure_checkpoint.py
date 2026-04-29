from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


REQUIRED_SIGNAL_KEYS = ("atr_4h_norm", "ema50_4h", "ema200_4h")
REQUIRED_TRADE_KEYS = ("atr_4h_norm",)


@dataclass(frozen=True)
class ModelingContextClosureCheckpoint:
    since: str
    generated_at: str
    runtime_config: dict[str, Any]
    sample: dict[str, int]
    telemetry: dict[str, Any]
    decision_outcomes: dict[str, Any]
    risk_blocks: dict[str, Any]
    recent_signal_candidates: list[dict[str, Any]]
    verdict: dict[str, Any]


def _parse_json_dict(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    try:
        data = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_iso_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _count_payload_completeness(rows: list[sqlite3.Row], keys: tuple[str, ...]) -> dict[str, Any]:
    total = len(rows)
    present_by_key = {key: 0 for key in keys}
    complete = 0
    for row in rows:
        payload = _parse_json_dict(row["payload_json"])
        has_all = True
        for key in keys:
            if payload.get(key) is not None:
                present_by_key[key] += 1
            else:
                has_all = False
        if has_all:
            complete += 1

    return {
        "total": total,
        "present_by_key": present_by_key,
        "complete_payload_count": complete,
        "complete_payload_share": (complete / total) if total else None,
    }


def build_checkpoint(
    conn: sqlite3.Connection,
    *,
    since: str,
    min_closed_trades: int = 10,
    max_unknown_volatility_share: float = 0.20,
    now: datetime | None = None,
) -> ModelingContextClosureCheckpoint:
    since_ts = _normalize_iso_timestamp(since)
    conn.row_factory = sqlite3.Row

    # Query runtime config snapshot
    bot_state_row = conn.execute("SELECT mode, timestamp FROM bot_state WHERE id = 1").fetchone()
    mode = str(bot_state_row["mode"]) if bot_state_row else "UNKNOWN"

    config_hash_row = conn.execute(
        "SELECT config_hash FROM decision_outcomes WHERE cycle_timestamp >= ? ORDER BY cycle_timestamp DESC LIMIT 1",
        (since_ts,),
    ).fetchone()
    config_hash = str(config_hash_row["config_hash"]) if config_hash_row else None

    # Infer min_rr from risk blocks (lowest rejected R:R gives lower bound on threshold)
    min_rr_sample = conn.execute(
        """
        SELECT MIN(es.rr_ratio) as min_rejected_rr
        FROM decision_outcomes do
        JOIN executable_signals es ON do.signal_id = es.signal_id
        WHERE do.cycle_timestamp >= ?
          AND do.outcome_group = 'risk_block'
          AND es.rr_ratio IS NOT NULL
        """,
        (since_ts,),
    ).fetchone()
    min_rr_lower_bound = (
        float(min_rr_sample["min_rejected_rr"]) if min_rr_sample and min_rr_sample["min_rejected_rr"] else None
    )

    runtime_config = {
        "mode": mode,
        "config_hash": config_hash,
        "note": "Full config requires settings.py access; showing observable runtime characteristics only",
        "inferred_min_rr_threshold": (
            f">= {min_rr_lower_bound:.3f}" if min_rr_lower_bound else "unknown (no risk blocks)"
        ),
    }

    sample = {
        "decision_cycles": conn.execute(
            "SELECT COUNT(*) FROM decision_outcomes WHERE cycle_timestamp >= ?",
            (since_ts,),
        ).fetchone()[0],
        "signal_candidates": conn.execute(
            "SELECT COUNT(*) FROM signal_candidates WHERE timestamp >= ?",
            (since_ts,),
        ).fetchone()[0],
        "trades_opened": conn.execute(
            "SELECT COUNT(*) FROM trade_log WHERE opened_at >= ?",
            (since_ts,),
        ).fetchone()[0],
        "trades_closed": conn.execute(
            "SELECT COUNT(*) FROM trade_log WHERE closed_at >= ?",
            (since_ts,),
        ).fetchone()[0],
    }

    signal_rows = conn.execute(
        """
        SELECT features_json AS payload_json
        FROM signal_candidates
        WHERE timestamp >= ?
        ORDER BY timestamp DESC
        """,
        (since_ts,),
    ).fetchall()
    signal_telemetry = _count_payload_completeness(signal_rows, REQUIRED_SIGNAL_KEYS)

    trade_rows = conn.execute(
        """
        SELECT features_at_entry_json AS payload_json
        FROM trade_log
        WHERE closed_at >= ?
        ORDER BY closed_at DESC
        """,
        (since_ts,),
    ).fetchall()
    trade_telemetry = _count_payload_completeness(trade_rows, REQUIRED_TRADE_KEYS)
    if trade_telemetry["total"]:
        trade_telemetry["unknown_volatility_share"] = (
            (trade_telemetry["total"] - trade_telemetry["present_by_key"]["atr_4h_norm"])
            / trade_telemetry["total"]
        )
    else:
        trade_telemetry["unknown_volatility_share"] = None

    outcome_rows = conn.execute(
        """
        SELECT outcome_group, outcome_reason, regime, COUNT(*) AS n
        FROM decision_outcomes
        WHERE cycle_timestamp >= ?
        GROUP BY outcome_group, outcome_reason, regime
        ORDER BY n DESC, outcome_group, outcome_reason, regime
        """,
        (since_ts,),
    ).fetchall()
    by_outcome: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    regime_distribution: dict[str, int] = {}
    for row in outcome_rows:
        outcome_group = str(row["outcome_group"])
        outcome_reason = str(row["outcome_reason"])
        regime = str(row["regime"]) if row["regime"] else "UNKNOWN"
        count = int(row["n"])
        by_outcome[outcome_group] = by_outcome.get(outcome_group, 0) + count
        by_reason[outcome_reason] = by_reason.get(outcome_reason, 0) + count
        regime_distribution[regime] = regime_distribution.get(regime, 0) + count

    risk_rows = conn.execute(
        """
        SELECT cycle_timestamp, signal_id, details_json
        FROM decision_outcomes
        WHERE cycle_timestamp >= ?
          AND outcome_group = 'risk_block'
        ORDER BY cycle_timestamp DESC
        """,
        (since_ts,),
    ).fetchall()
    risk_by_reason: dict[str, int] = {}
    recent_risk_blocks: list[dict[str, Any]] = []
    for row in risk_rows:
        details = _parse_json_dict(row["details_json"])
        reason = str(details.get("reason") or "risk_block")
        risk_by_reason[reason] = risk_by_reason.get(reason, 0) + 1
        recent_risk_blocks.append(
            {
                "cycle_timestamp": str(row["cycle_timestamp"]),
                "signal_id": str(row["signal_id"]) if row["signal_id"] else None,
                "reason": reason,
            }
        )

    recent_signal_candidates = []
    recent_signal_rows = conn.execute(
        """
        SELECT
            sc.signal_id,
            sc.timestamp,
            sc.regime,
            sc.direction,
            sc.confluence_score,
            es.rr_ratio,
            do.outcome_group,
            do.details_json,
            sc.features_json
        FROM signal_candidates sc
        LEFT JOIN executable_signals es
            ON es.signal_id = sc.signal_id
        LEFT JOIN decision_outcomes do
            ON do.id = (
                SELECT MAX(id)
                FROM decision_outcomes
                WHERE signal_id = sc.signal_id
            )
        WHERE sc.timestamp >= ?
        ORDER BY sc.timestamp DESC
        LIMIT 10
        """,
        (since_ts,),
    ).fetchall()
    for row in recent_signal_rows:
        details = _parse_json_dict(row["details_json"])
        features = _parse_json_dict(row["features_json"])
        recent_signal_candidates.append(
            {
                "signal_id": str(row["signal_id"]),
                "timestamp": str(row["timestamp"]),
                "regime": str(row["regime"]),
                "direction": str(row["direction"]),
                "confluence_score": float(row["confluence_score"]),
                "rr_ratio": None if row["rr_ratio"] is None else float(row["rr_ratio"]),
                "outcome_group": str(row["outcome_group"]) if row["outcome_group"] else None,
                "block_reason": details.get("reason"),
                "features_subset": {
                    "atr_4h_norm": features.get("atr_4h_norm"),
                    "ema50_4h": features.get("ema50_4h"),
                    "ema200_4h": features.get("ema200_4h"),
                },
            }
        )

    verdict_reasons = []
    if signal_telemetry["total"] == 0:
        verdict_reasons.append("no post-deploy signal candidates collected yet")
    elif signal_telemetry["complete_payload_share"] != 1.0:
        verdict_reasons.append("signal candidate telemetry is incomplete")

    if sample["trades_closed"] < min_closed_trades:
        verdict_reasons.append(
            f"closed_trades={sample['trades_closed']} < min_closed_trades={min_closed_trades}"
        )

    unknown_share = trade_telemetry["unknown_volatility_share"]
    if unknown_share is None:
        verdict_reasons.append("no closed post-deploy trades with runtime telemetry yet")
    elif unknown_share > max_unknown_volatility_share:
        verdict_reasons.append(
            "unknown_volatility_share="
            f"{unknown_share:.3f} > max_unknown_volatility_share={max_unknown_volatility_share:.3f}"
        )

    ready = not verdict_reasons
    verdict = {
        "ready_for_validation_rerun": ready,
        "status": "ready" if ready else "not_ready",
        "reasons": verdict_reasons,
        "thresholds": {
            "min_closed_trades": min_closed_trades,
            "max_unknown_volatility_share": max_unknown_volatility_share,
        },
    }

    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return ModelingContextClosureCheckpoint(
        since=since_ts,
        generated_at=generated_at,
        runtime_config=runtime_config,
        sample=sample,
        telemetry={
            "signal_candidates": signal_telemetry,
            "closed_trades": trade_telemetry,
        },
        decision_outcomes={
            "by_outcome": by_outcome,
            "by_reason": by_reason,
            "regime_distribution": regime_distribution,
        },
        risk_blocks={
            "count": len(risk_rows),
            "by_reason": risk_by_reason,
            "recent": recent_risk_blocks,
        },
        recent_signal_candidates=recent_signal_candidates,
        verdict=verdict,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Checkpoint readiness report for MODELING-CONTEXT-CLOSURE."
    )
    parser.add_argument("--db", default="storage/btc_bot.db", help="Path to database file.")
    parser.add_argument(
        "--since",
        required=True,
        help="Explicit UTC deploy checkpoint timestamp, e.g. 2026-04-27T13:18:00+00:00",
    )
    parser.add_argument(
        "--min-closed-trades",
        type=int,
        default=10,
        help="Minimum closed trade sample before validation rerun is considered ready.",
    )
    parser.add_argument(
        "--max-unknown-volatility-share",
        type=float,
        default=0.20,
        help="Maximum allowed share of closed trades missing atr_4h_norm.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def _print_text_report(report: ModelingContextClosureCheckpoint) -> None:
    print("MODELING-CONTEXT-CLOSURE CHECKPOINT")
    print(f"since: {report.since}")
    print(f"generated_at: {report.generated_at}")
    print(
        "sample: decision_cycles={decision_cycles} signal_candidates={signal_candidates} "
        "trades_opened={trades_opened} trades_closed={trades_closed}".format(**report.sample)
    )

    candidate = report.telemetry["signal_candidates"]
    trade = report.telemetry["closed_trades"]
    print(
        "candidate_telemetry: total={total} complete={complete_payload_count} share={share}".format(
            total=candidate["total"],
            complete_payload_count=candidate["complete_payload_count"],
            share=(
                "n/a"
                if candidate["complete_payload_share"] is None
                else f"{candidate['complete_payload_share']:.1%}"
            ),
        )
    )
    print(
        "closed_trade_telemetry: total={total} atr_4h_norm_present={present} unknown_share={unknown}".format(
            total=trade["total"],
            present=trade["present_by_key"]["atr_4h_norm"],
            unknown=(
                "n/a"
                if trade["unknown_volatility_share"] is None
                else f"{trade['unknown_volatility_share']:.1%}"
            ),
        )
    )
    print(f"regime_distribution: {json.dumps(report.decision_outcomes['regime_distribution'], sort_keys=True)}")
    print(f"risk_blocks: {json.dumps(report.risk_blocks['by_reason'], sort_keys=True)}")
    print(f"verdict: {report.verdict['status']}")
    for reason in report.verdict["reasons"]:
        print(f"reason: {reason}")


def main() -> int:
    args = _parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        report = build_checkpoint(
            conn,
            since=args.since,
            min_closed_trades=args.min_closed_trades,
            max_unknown_volatility_share=args.max_unknown_volatility_share,
        )
    except Exception as exc:
        print(f"Error: {exc}")
        return 1
    finally:
        conn.close()

    if args.json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        _print_text_report(report)

    return 0 if report.verdict["ready_for_validation_rerun"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
