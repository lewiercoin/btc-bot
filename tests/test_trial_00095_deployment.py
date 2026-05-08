import json
import sqlite3
from datetime import datetime, timezone

from settings import load_settings
from scripts.monitor_trial_00095 import evaluate


def test_runtime_settings_overlay_applies_only_to_runtime_profiles(tmp_path):
    (tmp_path / "settings.json").write_text(
        json.dumps(
            {
                "schema_version": "v1.0",
                "strategy": {"confluence_min": 3.9, "weight_sweep_detected": 2.2},
                "risk": {"risk_per_trade_pct": 0.005, "max_open_positions": 1},
            }
        ),
        encoding="utf-8",
    )

    research = load_settings(project_root=tmp_path, profile="research")
    experiment = load_settings(project_root=tmp_path, profile="experiment")

    assert research.strategy.confluence_min != 3.9
    assert experiment.strategy.confluence_min == 3.9
    assert experiment.strategy.weight_sweep_detected == 2.2
    assert experiment.risk.risk_per_trade_pct == 0.005
    assert experiment.risk.max_open_positions == 1


def test_trial_monitor_triggers_hard_stop_after_weak_30_trade_sample(tmp_path):
    db_path = tmp_path / "bot.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE bot_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            timestamp TEXT NOT NULL,
            mode TEXT NOT NULL,
            healthy INTEGER NOT NULL,
            safe_mode INTEGER NOT NULL,
            open_positions_count INTEGER NOT NULL DEFAULT 0,
            consecutive_losses INTEGER NOT NULL DEFAULT 0,
            daily_dd_pct REAL NOT NULL DEFAULT 0,
            weekly_dd_pct REAL NOT NULL DEFAULT 0,
            last_trade_at TEXT,
            last_error TEXT,
            safe_mode_entry_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE trade_log (
            trade_id TEXT PRIMARY KEY,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            pnl_abs REAL NOT NULL DEFAULT 0,
            pnl_r REAL NOT NULL DEFAULT 0,
            exit_reason TEXT,
            config_hash TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO bot_state (id, timestamp, mode, healthy, safe_mode) VALUES (1, ?, 'PAPER', 1, 0)",
        ("2026-05-08T00:00:00+00:00",),
    )
    for index in range(30):
        conn.execute(
            """
            INSERT INTO trade_log (trade_id, opened_at, closed_at, pnl_abs, pnl_r, exit_reason, config_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"t{index}",
                "2026-05-09T00:00:00+00:00",
                f"2026-05-{9 + (index % 10):02d}T01:00:00+00:00",
                -10.0,
                -0.25,
                "SL",
                "hash",
            ),
        )
    conn.commit()

    result = evaluate(
        conn,
        {
            "candidate_id": "optuna-default-v3-trial-00095",
            "deployment_start_utc": "2026-05-08T00:00:00+00:00",
            "paper_only": True,
            "hard_stop_after_trades": 30,
            "hard_stop_min_expectancy_r": 1.0,
            "review_pf_after_30_trades_below": 2.0,
            "review_drawdown_pct_above": 0.12,
            "frequency_review_consecutive_months": 2,
            "frequency_review_min_trades_per_month": 2.0,
            "early_review_min_trades": 30,
            "early_review_months_min": 3,
        },
        now=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )

    assert result["trade_count"] == 30
    assert result["hard_stop"] is True
    assert any(str(alert).startswith("hard_stop_expectancy_r") for alert in result["alerts"])
