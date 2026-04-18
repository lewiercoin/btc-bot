from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtest.backtest_runner import BacktestRunner
from core.models import GovernanceRuntimeState, RiskRuntimeState
from orchestrator import build_default_bundle
from settings import build_signal_regime_direction_whitelist, load_settings
from storage.db import init_db


def _make_conn(schema_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn, schema_path)
    return conn


def _build_custom_settings():
    os.environ["BOT_MODE"] = "PAPER"
    base = load_settings()
    strategy = replace(
        base.strategy,
        ema_trend_gap_pct=0.0099,
        compression_atr_norm_max=0.0044,
        crowded_funding_extreme_pct=92.0,
        crowded_oi_zscore_min=2.5,
        post_liq_tfi_abs_min=0.33,
        min_sweep_depth_pct=0.0009,
        entry_offset_atr=0.12,
        invalidation_offset_atr=0.44,
        min_stop_distance_pct=0.0021,
        tp1_atr_mult=1.8,
        tp2_atr_mult=2.6,
        weight_sweep_detected=1.11,
        weight_reclaim_confirmed=1.12,
        weight_cvd_divergence=0.62,
        weight_tfi_impulse=0.45,
        weight_force_order_spike=0.39,
        weight_regime_special=0.29,
        weight_ema_trend_alignment=0.21,
        weight_funding_supportive=0.17,
        direction_tfi_threshold=0.07,
        direction_tfi_threshold_inverse=-0.08,
        tfi_impulse_threshold=0.13,
        allow_long_in_uptrend=True,
        regime_direction_whitelist={"normal": ("LONG",), "uptrend": ("SHORT",)},
    )
    risk = replace(
        base.risk,
        cooldown_minutes_after_loss=75,
        duplicate_level_tolerance_pct=0.0022,
        duplicate_level_window_hours=36,
        session_start_hour_utc=2,
        session_end_hour_utc=20,
        no_trade_windows_utc=((8, 9), (13, 14)),
        high_vol_stop_distance_pct=0.015,
        partial_exit_pct=0.35,
        trailing_atr_mult=1.4,
    )
    return replace(base, strategy=strategy, risk=risk)


def _assert_live_bundle_config_injection() -> None:
    settings = _build_custom_settings()
    assert settings.storage is not None
    conn = _make_conn(settings.storage.schema_path)
    try:
        bundle = build_default_bundle(
            settings=settings,
            conn=conn,
            governance_state_provider=lambda: GovernanceRuntimeState(),
            risk_state_provider=lambda: RiskRuntimeState(),
        )
        regime_cfg = bundle.regime_engine.config
        signal_cfg = bundle.signal_engine.config
        governance_cfg = bundle.governance.config
        risk_cfg = bundle.risk_engine.config

        assert regime_cfg.ema_trend_gap_pct == settings.strategy.ema_trend_gap_pct
        assert regime_cfg.compression_atr_norm_max == settings.strategy.compression_atr_norm_max
        assert regime_cfg.crowded_funding_extreme_pct == settings.strategy.crowded_funding_extreme_pct
        assert regime_cfg.crowded_oi_zscore_min == settings.strategy.crowded_oi_zscore_min
        assert regime_cfg.post_liq_tfi_abs_min == settings.strategy.post_liq_tfi_abs_min

        assert signal_cfg.min_sweep_depth_pct == settings.strategy.min_sweep_depth_pct
        assert signal_cfg.ema_trend_gap_pct == settings.strategy.ema_trend_gap_pct
        assert signal_cfg.entry_offset_atr == settings.strategy.entry_offset_atr
        assert signal_cfg.invalidation_offset_atr == settings.strategy.invalidation_offset_atr
        assert signal_cfg.min_stop_distance_pct == settings.strategy.min_stop_distance_pct
        assert signal_cfg.tp1_atr_mult == settings.strategy.tp1_atr_mult
        assert signal_cfg.tp2_atr_mult == settings.strategy.tp2_atr_mult
        assert signal_cfg.weight_sweep_detected == settings.strategy.weight_sweep_detected
        assert signal_cfg.weight_reclaim_confirmed == settings.strategy.weight_reclaim_confirmed
        assert signal_cfg.weight_cvd_divergence == settings.strategy.weight_cvd_divergence
        assert signal_cfg.weight_tfi_impulse == settings.strategy.weight_tfi_impulse
        assert signal_cfg.weight_force_order_spike == settings.strategy.weight_force_order_spike
        assert signal_cfg.weight_regime_special == settings.strategy.weight_regime_special
        assert signal_cfg.weight_ema_trend_alignment == settings.strategy.weight_ema_trend_alignment
        assert signal_cfg.weight_funding_supportive == settings.strategy.weight_funding_supportive
        assert signal_cfg.direction_tfi_threshold == settings.strategy.direction_tfi_threshold
        assert signal_cfg.direction_tfi_threshold_inverse == settings.strategy.direction_tfi_threshold_inverse
        assert signal_cfg.tfi_impulse_threshold == settings.strategy.tfi_impulse_threshold
        assert signal_cfg.regime_direction_whitelist == build_signal_regime_direction_whitelist(settings.strategy)

        assert governance_cfg.cooldown_minutes_after_loss == settings.risk.cooldown_minutes_after_loss
        assert governance_cfg.duplicate_level_tolerance_pct == settings.risk.duplicate_level_tolerance_pct
        assert governance_cfg.duplicate_level_window_hours == settings.risk.duplicate_level_window_hours
        assert governance_cfg.session_start_hour_utc == settings.risk.session_start_hour_utc
        assert governance_cfg.session_end_hour_utc == settings.risk.session_end_hour_utc
        assert governance_cfg.no_trade_windows_utc == settings.risk.no_trade_windows_utc

        assert risk_cfg.high_vol_stop_distance_pct == settings.risk.high_vol_stop_distance_pct
        assert risk_cfg.partial_exit_pct == settings.risk.partial_exit_pct
        assert risk_cfg.trailing_atr_mult == settings.risk.trailing_atr_mult
        print("live bundle config injection smoke: OK")
    finally:
        conn.close()


def _assert_backtest_config_injection() -> None:
    settings = _build_custom_settings()
    assert settings.storage is not None
    conn = _make_conn(settings.storage.schema_path)
    try:
        runner = BacktestRunner(conn, settings=settings)
        _, regime_engine, signal_engine, governance, risk_engine = runner._build_engines()  # type: ignore[attr-defined]

        assert regime_engine.config.ema_trend_gap_pct == settings.strategy.ema_trend_gap_pct
        assert regime_engine.config.compression_atr_norm_max == settings.strategy.compression_atr_norm_max
        assert regime_engine.config.crowded_funding_extreme_pct == settings.strategy.crowded_funding_extreme_pct
        assert regime_engine.config.crowded_oi_zscore_min == settings.strategy.crowded_oi_zscore_min
        assert regime_engine.config.post_liq_tfi_abs_min == settings.strategy.post_liq_tfi_abs_min

        assert signal_engine.config.ema_trend_gap_pct == settings.strategy.ema_trend_gap_pct
        assert signal_engine.config.entry_offset_atr == settings.strategy.entry_offset_atr
        assert signal_engine.config.weight_cvd_divergence == settings.strategy.weight_cvd_divergence
        assert signal_engine.config.direction_tfi_threshold == settings.strategy.direction_tfi_threshold
        assert signal_engine.config.direction_tfi_threshold_inverse == settings.strategy.direction_tfi_threshold_inverse
        assert signal_engine.config.tfi_impulse_threshold == settings.strategy.tfi_impulse_threshold
        assert signal_engine.config.min_stop_distance_pct == settings.strategy.min_stop_distance_pct
        assert signal_engine.config.regime_direction_whitelist == build_signal_regime_direction_whitelist(settings.strategy)

        assert governance.config.cooldown_minutes_after_loss == settings.risk.cooldown_minutes_after_loss
        assert governance.config.duplicate_level_tolerance_pct == settings.risk.duplicate_level_tolerance_pct
        assert governance.config.duplicate_level_window_hours == settings.risk.duplicate_level_window_hours
        assert governance.config.session_start_hour_utc == settings.risk.session_start_hour_utc
        assert governance.config.session_end_hour_utc == settings.risk.session_end_hour_utc
        assert governance.config.no_trade_windows_utc == settings.risk.no_trade_windows_utc

        assert risk_engine.config.high_vol_stop_distance_pct == settings.risk.high_vol_stop_distance_pct
        assert risk_engine.config.partial_exit_pct == settings.risk.partial_exit_pct
        assert risk_engine.config.trailing_atr_mult == settings.risk.trailing_atr_mult
        print("backtest engine config injection smoke: OK")
    finally:
        conn.close()


def main() -> None:
    _assert_live_bundle_config_injection()
    _assert_backtest_config_injection()
    print("config injection smoke: OK")


if __name__ == "__main__":
    main()
