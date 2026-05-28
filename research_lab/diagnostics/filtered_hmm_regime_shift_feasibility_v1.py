"""Research-only filtered HMM regime shift feasibility diagnostic.

Implements FILTERED_HMM_REGIME_SHIFT_FEASIBILITY_V1:

    2-state Gaussian HMM on [log_return, realized_vol, vol_zscore]
    Rolling 500-bar training, 100-bar retrain cycle
    Custom forward-only filtered probabilities P(state_t | data_0:t)
    Entry at bar i+1 when P(trend_state) crosses 0.7 from below
    Direction from 20-bar momentum

CRITICAL: hmmlearn predict_proba uses smoothed posteriors (lookahead).
This diagnostic implements a custom forward pass for filtered probabilities.

This module is intentionally isolated from the live path. It reads SQLite market
data and writes research artifacts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

import numpy as np

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from hmmlearn.hmm import GaussianHMM


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "research_lab" / "data" / "crowded_unwind_backtest.db"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "research_lab" / "reports" / "filtered_hmm_regime_shift_feasibility_v1.md"
DEFAULT_JSON_PATH = PROJECT_ROOT / "research_lab" / "reports" / "filtered_hmm_regime_shift_feasibility_v1.json"

TRIAL_00095_REFERENCE = {
    "er": 2.1,
    "profit_factor": 4.6,
    "trades": 271,
    "win_rate": 0.56,
    "source": "approved planning document / milestone tracker reference",
}

ADX_CHOP_REFERENCE = {
    "er": -0.027,
    "profit_factor": 0.954,
    "events": 321,
    "verdict": "STOP",
    "source": "TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1 diagnostic result",
}

FOLD_WINDOWS = (
    ("fold_1", datetime(2020, 9, 1, tzinfo=timezone.utc), datetime(2021, 12, 31, 23, 59, tzinfo=timezone.utc)),
    ("fold_2", datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2023, 6, 30, 23, 59, tzinfo=timezone.utc)),
    ("fold_3", datetime(2023, 7, 1, tzinfo=timezone.utc), datetime(2024, 12, 31, 23, 59, tzinfo=timezone.utc)),
    ("fold_4", datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2026, 3, 28, 23, 59, tzinfo=timezone.utc)),
)


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    # Feature parameters
    realized_vol_period: int = 14
    volume_zscore_period: int = 20
    # HMM parameters
    n_states: int = 2
    covariance_type: str = "diag"
    training_window: int = 500
    retrain_interval: int = 100
    n_iter: int = 100
    random_seed: int = 42
    # Threshold parameters
    prob_threshold: float = 0.7
    staleness_limit: int = 50
    # Direction parameters
    momentum_lookback: int = 20
    atr_period: int = 14
    ambiguity_atr_fraction: float = 0.1
    # Outcome parameters
    outcome_horizon_bars: int = 20
    outcome_5bar: int = 5
    outcome_10bar: int = 10
    outcome_40bar: int = 40
    # Cost model
    round_trip_cost_pct: float = 0.0010
    round_trip_cost_sensitivity: float = 0.0015
    # Controls
    random_offset_bars: int = 137
    shifted_entry_delay_bars: int = 3
    volatility_low_pct: float = 35.0
    volatility_high_pct: float = 65.0
    # ADX/CHOP for control 2
    di_period: int = 14
    adx_smoothing: int = 14
    chop_period: int = 14
    adx_range_threshold: float = 20.0
    adx_trend_threshold: float = 25.0
    chop_range_threshold: float = 61.8
    chop_trend_threshold: float = 38.2
    di_spread_threshold: float = 5.0
    adx_staleness_limit: int = 12
    # Misc
    raw_move_lookback: int = 10
    max_serialized_events_per_cohort: int = 200
    feature_warmup: int = 170


@dataclass(frozen=True, slots=True)
class Candle:
    index: int
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True)
class HMMEvent:
    detection_bar: int
    direction: str
    filtered_prob_trend: float
    filtered_prob_trend_prev: float
    trend_state_idx: int
    momentum: float


@dataclass(slots=True)
class LagAudit:
    raw_move_start_bar: int
    hmm_lag_bars: int
    lag_mfe_before_entry: float
    lag_mfe_after_entry: float
    lag_mfe_consumed_pct: float


@dataclass(slots=True)
class CohortEvent:
    cohort: str
    detection_bar: int
    state_known_bar: int
    entry_candidate_bar: int
    return_start_bar: int
    direction: str
    detection_time_utc: str
    entry_time_utc: str
    entry_price: float
    exit_bar: int
    exit_price: float
    gross_return_pct: float
    net_return_pct: float
    return_5bar_pct: float | None
    return_10bar_pct: float | None
    return_20bar_pct: float
    return_40bar_pct: float | None
    mfe_before_entry: float
    mfe_after_entry: float
    mae_after_entry: float
    total_mfe: float
    mfe_consumed_pct: float
    entry_to_mfe_bars: int | None
    structural_stop: float | None
    r_multiple: float | None
    lag_audit: dict[str, Any] | None
    metadata: dict[str, Any]


# --- Utility functions ---

def parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc) if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    text = str(raw).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def fmt_float(value: Any, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    if value == float("inf"):
        return "inf"
    return f"{float(value):.{digits}f}"


# --- Data Loading ---

def load_candles(conn: sqlite3.Connection, config: DiagnosticConfig) -> list[Candle]:
    """Load BTCUSDT 15m candles from research DB."""
    query = """
        SELECT open_time, open, high, low, close, volume
        FROM candles
        WHERE symbol = ? AND timeframe = ?
        ORDER BY open_time ASC
    """
    rows = conn.execute(query, (config.symbol, config.timeframe)).fetchall()
    candles = []
    for i, row in enumerate(rows):
        candles.append(Candle(
            index=i,
            open_time=parse_ts(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        ))
    return candles


def data_quality(candles: list[Candle]) -> dict[str, Any]:
    """Basic data quality checks."""
    n = len(candles)
    gaps = 0
    ohlc_violations = 0
    zero_volume = 0

    for i in range(1, n):
        expected_gap = (candles[i].open_time - candles[i - 1].open_time).total_seconds()
        if expected_gap > 900 * 1.5:  # 15m = 900s, allow 50% tolerance
            gaps += 1
        c = candles[i]
        if c.high < c.low or c.open <= 0 or c.close <= 0:
            ohlc_violations += 1
        if c.volume == 0:
            zero_volume += 1

    return {
        "total_bars": n,
        "start_time_utc": iso(candles[0].open_time) if candles else "N/A",
        "end_time_utc": iso(candles[-1].open_time) if candles else "N/A",
        "gaps": gaps,
        "ohlc_violations": ohlc_violations,
        "zero_volume_bars": zero_volume,
    }


# --- Feature Computation ---

def compute_features(candles: list[Candle], config: DiagnosticConfig) -> np.ndarray:
    """Compute feature matrix [log_return, realized_vol, vol_zscore].

    Returns array of shape (n_candles, 3). NaN for bars without sufficient history.
    """
    n = len(candles)
    features = np.full((n, 3), np.nan)

    # Log returns
    for i in range(1, n):
        if candles[i - 1].close > 0 and candles[i].close > 0:
            features[i, 0] = math.log(candles[i].close / candles[i - 1].close)

    # Realized volatility (rolling std of log returns over realized_vol_period)
    rv_period = config.realized_vol_period
    for i in range(rv_period, n):
        window = features[i - rv_period + 1: i + 1, 0]
        if not np.any(np.isnan(window)):
            features[i, 1] = np.std(window, ddof=1)

    # Volume z-score
    vz_period = config.volume_zscore_period
    for i in range(vz_period - 1, n):
        volumes = [candles[j].volume for j in range(i - vz_period + 1, i + 1)]
        vol_mean = np.mean(volumes)
        vol_std = np.std(volumes, ddof=1)
        if vol_std > 0:
            features[i, 2] = (candles[i].volume - vol_mean) / vol_std
        else:
            features[i, 2] = 0.0

    return features


def compute_atr(candles: list[Candle], period: int = 14) -> np.ndarray:
    """Compute ATR for each bar (NaN for insufficient history)."""
    n = len(candles)
    atr = np.full(n, np.nan)
    tr = np.zeros(n)

    for i in range(1, n):
        high_i = candles[i].high
        low_i = candles[i].low
        prev_close = candles[i - 1].close
        tr[i] = max(high_i - low_i, abs(high_i - prev_close), abs(low_i - prev_close))

    for i in range(period, n):
        atr[i] = np.mean(tr[i - period + 1: i + 1])

    return atr


# --- HMM Training and Inference ---

def train_hmm(
    feature_window: np.ndarray,
    config: DiagnosticConfig,
    seed: int | None = None,
) -> GaussianHMM | None:
    """Train a Gaussian HMM on a feature window. Returns None if training fails."""
    if seed is None:
        seed = config.random_seed

    # Remove rows with NaN
    valid_mask = ~np.any(np.isnan(feature_window), axis=1)
    valid_data = feature_window[valid_mask]

    if len(valid_data) < 50:  # Minimum viable training data
        return None

    model = GaussianHMM(
        n_components=config.n_states,
        covariance_type=config.covariance_type,
        n_iter=config.n_iter,
        random_state=seed,
        tol=0.01,
    )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(valid_data)
        if not model.monitor_.converged:
            # Still use the model - partial convergence is acceptable
            pass
        return model
    except Exception:
        return None


def _get_mean_variance_per_state(model: GaussianHMM) -> np.ndarray:
    """Extract mean variance per state from model covariances.

    Handles all hmmlearn covars_ shapes robustly.
    Returns 1D array of shape (n_components,) with mean variance per state.
    """
    covars = np.asarray(model.covars_)
    if covars.ndim == 3:
        # Shape (n_components, n_features, n_features) - use trace
        return np.array([np.trace(covars[k]) / covars[k].shape[0] for k in range(model.n_components)])
    elif covars.ndim == 2:
        # Shape (n_components, n_features) - mean across features
        return covars.mean(axis=1)
    else:
        # Shape (n_components,) - spherical
        return covars.ravel()


def interpret_states(model: GaussianHMM) -> int:
    """Identify trend state index based on emission parameters.

    The trend state is the one with higher variance (mean of diagonal covariance).
    Returns the index of the trend state.
    """
    mean_var = _get_mean_variance_per_state(model)
    trend_state_idx = int(np.argmax(mean_var))
    return trend_state_idx


def state_interpretation_ambiguous(model: GaussianHMM) -> bool:
    """Check if state interpretation is ambiguous (variance ratio < 1.2)."""
    mean_var = _get_mean_variance_per_state(model)

    if len(mean_var) < 2:
        return True
    min_var = float(np.min(mean_var))
    max_var = float(np.max(mean_var))
    if min_var <= 0:
        return True
    ratio = max_var / min_var
    return ratio < 1.2


def forward_pass_filtered(
    observations: np.ndarray,
    model: GaussianHMM,
) -> np.ndarray:
    """Custom forward-only pass to compute filtered probabilities.

    P(state_t | data_0:t) using only the forward algorithm.
    This is strictly causal - no future data used.

    Returns array of shape (n_observations, n_states) with filtered probabilities.
    """
    n_obs = len(observations)
    n_states = model.n_components
    filtered_probs = np.zeros((n_obs, n_states))

    # Get emission log-likelihoods
    # _compute_log_likelihood gives log P(x_t | state_k)
    log_emission = model._compute_log_likelihood(observations)

    # Initial step
    log_startprob = np.log(model.startprob_ + 1e-300)
    log_alpha = log_startprob + log_emission[0]
    # Normalize in log space
    log_norm = np.logaddexp.reduce(log_alpha)
    log_alpha -= log_norm
    filtered_probs[0] = np.exp(log_alpha)

    # Forward recursion
    log_transmat = np.log(model.transmat_ + 1e-300)

    for t in range(1, n_obs):
        # alpha_t[k] = P(x_t | state_k) * sum_j(alpha_{t-1}[j] * transmat[j, k])
        # In log space: log_alpha_t[k] = log_emission[t, k] + logsumexp(log_alpha_{t-1} + log_transmat[:, k])
        log_alpha_new = np.zeros(n_states)
        for k in range(n_states):
            log_alpha_new[k] = log_emission[t, k] + np.logaddexp.reduce(
                log_alpha + log_transmat[:, k]
            )
        # Normalize
        log_norm = np.logaddexp.reduce(log_alpha_new)
        log_alpha_new -= log_norm
        log_alpha = log_alpha_new
        filtered_probs[t] = np.exp(log_alpha)

    return filtered_probs


# --- Event Detection ---

def detect_hmm_events(
    candles: list[Candle],
    features: np.ndarray,
    atr: np.ndarray,
    config: DiagnosticConfig,
    seed: int | None = None,
) -> tuple[list[HMMEvent], dict[str, Any]]:
    """Detect HMM threshold crossing events using rolling window training.

    Returns (events, training_stats).
    """
    n = len(candles)
    events: list[HMMEvent] = []
    training_stats: dict[str, Any] = {
        "total_retrains": 0,
        "failed_retrains": 0,
        "ambiguous_retrains": 0,
        "trend_state_flips": 0,
        "state_interpretations": [],
    }

    current_model: GaussianHMM | None = None
    current_trend_state: int | None = None
    prev_trend_state: int | None = None
    filtered_probs = np.zeros((n, config.n_states))

    # Track bars where range state was dominant (for staleness check)
    last_range_dominant_bar: int | None = None

    # Determine first valid feature bar
    first_valid = config.feature_warmup

    # Running forward pass state
    log_alpha: np.ndarray | None = None

    for i in range(first_valid, n):
        # Check if retrain is needed
        bars_since_first = i - first_valid
        need_retrain = (
            current_model is None
            or bars_since_first % config.retrain_interval == 0
        )

        if need_retrain:
            # Training window: last training_window bars up to and including i
            train_start = max(0, i - config.training_window + 1)
            train_end = i + 1
            train_data = features[train_start:train_end]

            model = train_hmm(train_data, config, seed=seed)
            training_stats["total_retrains"] += 1

            if model is None:
                training_stats["failed_retrains"] += 1
                # Keep using previous model if available
                if current_model is None:
                    continue
            else:
                current_model = model
                prev_trend_state = current_trend_state
                current_trend_state = interpret_states(current_model)

                if state_interpretation_ambiguous(current_model):
                    training_stats["ambiguous_retrains"] += 1

                if prev_trend_state is not None and current_trend_state != prev_trend_state:
                    training_stats["trend_state_flips"] += 1

                training_stats["state_interpretations"].append({
                    "bar": i,
                    "trend_state_idx": current_trend_state,
                    "ambiguous": state_interpretation_ambiguous(current_model),
                })

                # Reset forward pass state after retrain
                log_alpha = None

        if current_model is None or current_trend_state is None:
            continue

        # Compute filtered probability for current bar using custom forward pass
        obs = features[i:i + 1]
        if np.any(np.isnan(obs)):
            continue

        log_emission = current_model._compute_log_likelihood(obs)

        if log_alpha is None:
            # Initialize forward pass
            log_startprob = np.log(current_model.startprob_ + 1e-300)
            log_alpha = log_startprob + log_emission[0]
        else:
            # Forward step
            log_transmat = np.log(current_model.transmat_ + 1e-300)
            log_alpha_new = np.zeros(config.n_states)
            for k in range(config.n_states):
                log_alpha_new[k] = log_emission[0, k] + np.logaddexp.reduce(
                    log_alpha + log_transmat[:, k]
                )
            log_alpha = log_alpha_new

        # Normalize
        log_norm = np.logaddexp.reduce(log_alpha)
        log_alpha_normalized = log_alpha - log_norm
        prob = np.exp(log_alpha_normalized)
        filtered_probs[i] = prob

        # Track range-dominant bars
        range_state = 1 - current_trend_state
        if prob[range_state] >= config.prob_threshold:
            last_range_dominant_bar = i

        # Check for threshold crossing
        trend_prob = prob[current_trend_state]
        prev_trend_prob = filtered_probs[i - 1, current_trend_state] if i > first_valid else 0.0

        if (
            trend_prob >= config.prob_threshold
            and prev_trend_prob < config.prob_threshold
            and last_range_dominant_bar is not None
            and (i - last_range_dominant_bar) <= config.staleness_limit
        ):
            # Assign direction from momentum
            if i >= config.momentum_lookback:
                momentum = candles[i].close - candles[i - config.momentum_lookback].close
                atr_i = atr[i] if not np.isnan(atr[i]) else 1.0

                if abs(momentum) < atr_i * config.ambiguity_atr_fraction:
                    continue  # Ambiguous direction, skip

                direction = "LONG" if momentum > 0 else "SHORT"

                events.append(HMMEvent(
                    detection_bar=i,
                    direction=direction,
                    filtered_prob_trend=float(trend_prob),
                    filtered_prob_trend_prev=float(prev_trend_prob),
                    trend_state_idx=current_trend_state,
                    momentum=float(momentum),
                ))

    return events, training_stats


# --- Event Building ---

def compute_lag_audit(
    candles: list[Candle],
    detection_bar: int,
    entry_bar: int,
    direction: str,
    config: DiagnosticConfig,
) -> LagAudit:
    """Compute HMM lag audit for an event."""
    lookback = config.raw_move_lookback
    search_start = max(0, detection_bar - config.staleness_limit)

    raw_move_start = detection_bar  # Default: no lag detected

    if direction == "LONG":
        # Find earliest bar breaking prior 10-bar high
        for j in range(search_start, detection_bar):
            ref_start = max(0, j - lookback)
            prior_high = max(candles[k].high for k in range(ref_start, j)) if j > ref_start else candles[j].high
            if candles[j].close > prior_high:
                raw_move_start = j
                break
    else:
        # Find earliest bar breaking prior 10-bar low
        for j in range(search_start, detection_bar):
            ref_start = max(0, j - lookback)
            prior_low = min(candles[k].low for k in range(ref_start, j)) if j > ref_start else candles[j].low
            if candles[j].close < prior_low:
                raw_move_start = j
                break

    hmm_lag_bars = detection_bar - raw_move_start

    # Lag MFE before entry (from raw_move_start to entry_bar - 1)
    if direction == "LONG":
        lag_mfe_before = max(
            (candles[k].high for k in range(raw_move_start, entry_bar)),
            default=candles[detection_bar].close,
        ) - candles[raw_move_start].close
    else:
        lag_mfe_before = candles[raw_move_start].close - min(
            (candles[k].low for k in range(raw_move_start, entry_bar)),
            default=candles[detection_bar].close,
        )

    lag_mfe_before = max(0.0, lag_mfe_before)

    # Lag MFE after entry
    n = len(candles)
    horizon_end = min(entry_bar + config.outcome_horizon_bars, n)
    if direction == "LONG":
        entry_price = candles[entry_bar].open
        lag_mfe_after = max(
            (candles[k].high for k in range(entry_bar, horizon_end)),
            default=entry_price,
        ) - entry_price
    else:
        entry_price = candles[entry_bar].open
        lag_mfe_after = entry_price - min(
            (candles[k].low for k in range(entry_bar, horizon_end)),
            default=entry_price,
        )

    lag_mfe_after = max(0.0, lag_mfe_after)

    total = lag_mfe_before + lag_mfe_after
    consumed = (lag_mfe_before / total * 100.0) if total > 0 else 100.0

    return LagAudit(
        raw_move_start_bar=raw_move_start,
        hmm_lag_bars=hmm_lag_bars,
        lag_mfe_before_entry=lag_mfe_before,
        lag_mfe_after_entry=lag_mfe_after,
        lag_mfe_consumed_pct=consumed,
    )


def build_cohort_event(
    candles: list[Candle],
    detection_bar: int,
    entry_bar: int,
    direction: str,
    config: DiagnosticConfig,
    cohort: str,
    metadata: dict[str, Any],
    include_lag_audit: bool = False,
) -> CohortEvent | None:
    """Build a CohortEvent with full MFE/MAE calculations."""
    n = len(candles)
    exit_bar = entry_bar + config.outcome_horizon_bars - 1

    if entry_bar >= n or exit_bar >= n:
        return None

    entry_price = candles[entry_bar].open
    if entry_price <= 0:
        return None

    exit_price = candles[exit_bar].close

    # Primary return
    if direction == "LONG":
        gross_return = (exit_price - entry_price) / entry_price
    else:
        gross_return = (entry_price - exit_price) / entry_price

    net_return = gross_return - config.round_trip_cost_pct

    # Multi-horizon returns
    def horizon_return(bars: int) -> float | None:
        target_bar = entry_bar + bars - 1
        if target_bar >= n:
            return None
        ref_price = candles[target_bar].close
        if direction == "LONG":
            return (ref_price - entry_price) / entry_price - config.round_trip_cost_pct
        else:
            return (entry_price - ref_price) / entry_price - config.round_trip_cost_pct

    return_5bar = horizon_return(config.outcome_5bar)
    return_10bar = horizon_return(config.outcome_10bar)
    return_20bar = net_return  # Same as primary
    return_40bar = horizon_return(config.outcome_40bar)

    # MFE before entry (detection_bar to entry_bar - 1)
    if detection_bar < entry_bar:
        if direction == "LONG":
            mfe_before = max(candles[k].high for k in range(detection_bar, entry_bar)) - candles[detection_bar].close
        else:
            mfe_before = candles[detection_bar].close - min(candles[k].low for k in range(detection_bar, entry_bar))
    else:
        mfe_before = 0.0
    mfe_before = max(0.0, mfe_before)

    # MFE/MAE after entry
    horizon_end = min(entry_bar + config.outcome_horizon_bars, n)
    if direction == "LONG":
        mfe_after = max(candles[k].high for k in range(entry_bar, horizon_end)) - entry_price
        mae_after = entry_price - min(candles[k].low for k in range(entry_bar, horizon_end))
        # Entry to MFE bars
        mfe_price = max(candles[k].high for k in range(entry_bar, horizon_end))
        mfe_bar_offset = next(
            (k - entry_bar for k in range(entry_bar, horizon_end) if candles[k].high == mfe_price),
            None,
        )
    else:
        mfe_after = entry_price - min(candles[k].low for k in range(entry_bar, horizon_end))
        mae_after = max(candles[k].high for k in range(entry_bar, horizon_end)) - entry_price
        mfe_price = min(candles[k].low for k in range(entry_bar, horizon_end))
        mfe_bar_offset = next(
            (k - entry_bar for k in range(entry_bar, horizon_end) if candles[k].low == mfe_price),
            None,
        )

    mfe_after = max(0.0, mfe_after)
    mae_after = max(0.0, mae_after)

    total_mfe = mfe_before + mfe_after
    mfe_consumed = (mfe_before / total_mfe * 100.0) if total_mfe > 0 else 100.0

    # Structural stop
    stop_lookback_start = max(0, detection_bar - 20)
    if direction == "LONG":
        structural_stop = min(candles[k].low for k in range(stop_lookback_start, detection_bar + 1))
        stop_distance = entry_price - structural_stop
    else:
        structural_stop = max(candles[k].high for k in range(stop_lookback_start, detection_bar + 1))
        stop_distance = structural_stop - entry_price

    if stop_distance > 0:
        if direction == "LONG":
            r_multiple = (exit_price - entry_price) / stop_distance
        else:
            r_multiple = (entry_price - exit_price) / stop_distance
    else:
        structural_stop = None
        r_multiple = None

    # Lag audit
    lag_audit_dict = None
    if include_lag_audit:
        la = compute_lag_audit(candles, detection_bar, entry_bar, direction, config)
        lag_audit_dict = {
            "raw_move_start_bar": la.raw_move_start_bar,
            "hmm_lag_bars": la.hmm_lag_bars,
            "lag_mfe_before_entry": la.lag_mfe_before_entry,
            "lag_mfe_after_entry": la.lag_mfe_after_entry,
            "lag_mfe_consumed_pct": la.lag_mfe_consumed_pct,
        }

    return CohortEvent(
        cohort=cohort,
        detection_bar=detection_bar,
        state_known_bar=detection_bar,
        entry_candidate_bar=entry_bar,
        return_start_bar=entry_bar,
        direction=direction,
        detection_time_utc=iso(candles[detection_bar].open_time),
        entry_time_utc=iso(candles[entry_bar].open_time),
        entry_price=entry_price,
        exit_bar=exit_bar,
        exit_price=exit_price,
        gross_return_pct=gross_return * 100.0,
        net_return_pct=net_return * 100.0,
        return_5bar_pct=return_5bar * 100.0 if return_5bar is not None else None,
        return_10bar_pct=return_10bar * 100.0 if return_10bar is not None else None,
        return_20bar_pct=return_20bar * 100.0,
        return_40bar_pct=return_40bar * 100.0 if return_40bar is not None else None,
        mfe_before_entry=mfe_before,
        mfe_after_entry=mfe_after,
        mae_after_entry=mae_after,
        total_mfe=total_mfe,
        mfe_consumed_pct=mfe_consumed,
        entry_to_mfe_bars=mfe_bar_offset,
        structural_stop=structural_stop,
        r_multiple=r_multiple,
        lag_audit=lag_audit_dict,
        metadata=metadata,
    )


# --- Control Cohorts ---

def build_main_cohort(
    candles: list[Candle],
    hmm_events: list[HMMEvent],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Build main HMM cohort events."""
    events: list[CohortEvent] = []
    for he in hmm_events:
        entry_bar = he.detection_bar + 1
        evt = build_cohort_event(
            candles, he.detection_bar, entry_bar, he.direction, config,
            cohort="main_hmm_filtered",
            metadata={
                "filtered_prob_trend": he.filtered_prob_trend,
                "filtered_prob_trend_prev": he.filtered_prob_trend_prev,
                "trend_state_idx": he.trend_state_idx,
                "momentum": he.momentum,
            },
            include_lag_audit=True,
        )
        if evt:
            events.append(evt)
    return events


def build_control_simple_volatility(
    candles: list[Candle],
    features: np.ndarray,
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Control 1: Simple volatility percentile transition."""
    n = len(candles)
    events: list[CohortEvent] = []

    # Compute realized vol percentile thresholds from rolling 500-bar window
    for i in range(config.feature_warmup, n):
        if np.isnan(features[i, 1]):
            continue

        # Rolling percentiles over last 500 bars
        window_start = max(0, i - config.training_window + 1)
        vol_window = features[window_start:i + 1, 1]
        vol_window = vol_window[~np.isnan(vol_window)]

        if len(vol_window) < 50:
            continue

        low_thresh = np.percentile(vol_window, config.volatility_low_pct)
        high_thresh = np.percentile(vol_window, config.volatility_high_pct)

        current_vol = features[i, 1]
        prev_vol = features[i - 1, 1] if i > 0 and not np.isnan(features[i - 1, 1]) else None

        if prev_vol is not None and prev_vol < low_thresh and current_vol > high_thresh:
            # Volatility transition detected
            if i >= config.momentum_lookback:
                momentum = candles[i].close - candles[i - config.momentum_lookback].close
                if abs(momentum) < 1.0:  # Near zero
                    continue
                direction = "LONG" if momentum > 0 else "SHORT"
                entry_bar = i + 1
                evt = build_cohort_event(
                    candles, i, entry_bar, direction, config,
                    cohort="control_simple_volatility",
                    metadata={"control": "volatility percentile transition"},
                )
                if evt:
                    events.append(evt)

    return events


def build_control_adx_chop(
    candles: list[Candle],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Control 2: Deterministic ADX/CHOP regime transition (prior diagnostic baseline)."""
    n = len(candles)
    events: list[CohortEvent] = []

    # Compute ADX/CHOP indicators inline (simplified Wilder smoothing)
    period = config.di_period

    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n

    for i in range(1, n):
        high_i = candles[i].high
        low_i = candles[i].low
        prev_close = candles[i - 1].close
        tr[i] = max(high_i - low_i, abs(high_i - prev_close), abs(low_i - prev_close))
        up_move = high_i - candles[i - 1].high
        down_move = candles[i - 1].low - low_i
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Wilder smoothing
    if n < period + 1:
        return events

    smooth_tr = [0.0] * n
    smooth_plus_dm = [0.0] * n
    smooth_minus_dm = [0.0] * n

    smooth_tr[period] = sum(tr[1:period + 1])
    smooth_plus_dm[period] = sum(plus_dm[1:period + 1])
    smooth_minus_dm[period] = sum(minus_dm[1:period + 1])

    for i in range(period + 1, n):
        smooth_tr[i] = smooth_tr[i - 1] - smooth_tr[i - 1] / period + tr[i]
        smooth_plus_dm[i] = smooth_plus_dm[i - 1] - smooth_plus_dm[i - 1] / period + plus_dm[i]
        smooth_minus_dm[i] = smooth_minus_dm[i - 1] - smooth_minus_dm[i - 1] / period + minus_dm[i]

    # DI and ADX
    plus_di = [0.0] * n
    minus_di = [0.0] * n
    dx = [0.0] * n
    adx = [0.0] * n

    for i in range(period, n):
        if smooth_tr[i] > 0:
            plus_di[i] = 100.0 * smooth_plus_dm[i] / smooth_tr[i]
            minus_di[i] = 100.0 * smooth_minus_dm[i] / smooth_tr[i]
        di_sum = plus_di[i] + minus_di[i]
        if di_sum > 0:
            dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / di_sum

    # ADX smoothing
    adx_start = period + config.adx_smoothing - 1
    if adx_start < n:
        adx[adx_start] = sum(dx[period:adx_start + 1]) / config.adx_smoothing
        for i in range(adx_start + 1, n):
            adx[i] = (adx[i - 1] * (config.adx_smoothing - 1) + dx[i]) / config.adx_smoothing

    # CHOP
    chop = [0.0] * n
    chop_period = config.chop_period
    for i in range(chop_period, n):
        atr_sum = sum(tr[i - chop_period + 1: i + 1])
        high_n = max(candles[k].high for k in range(i - chop_period + 1, i + 1))
        low_n = min(candles[k].low for k in range(i - chop_period + 1, i + 1))
        hl_range = high_n - low_n
        if hl_range > 0 and atr_sum > 0:
            chop[i] = 100.0 * math.log10(atr_sum / hl_range) / math.log10(chop_period)

    # State machine
    warmup = max(config.feature_warmup, adx_start + 1)
    latched_range = False
    last_range_bar: int | None = None

    for i in range(warmup, n):
        is_range = (adx[i] <= config.adx_range_threshold and chop[i] >= config.chop_range_threshold)
        is_trend = (
            adx[i] >= config.adx_trend_threshold
            and chop[i] <= config.chop_trend_threshold
            and abs(plus_di[i] - minus_di[i]) >= config.di_spread_threshold
        )

        if is_range:
            latched_range = True
            last_range_bar = i

        if is_trend and latched_range and last_range_bar is not None:
            if (i - last_range_bar) <= config.adx_staleness_limit:
                direction = "LONG" if plus_di[i] > minus_di[i] else "SHORT"
                entry_bar = i + 1
                evt = build_cohort_event(
                    candles, i, entry_bar, direction, config,
                    cohort="control_adx_chop",
                    metadata={"control": "deterministic ADX/CHOP transition"},
                )
                if evt:
                    events.append(evt)
            latched_range = False

    return events


def build_control_wrong_interpretation(
    candles: list[Candle],
    features: np.ndarray,
    atr: np.ndarray,
    config: DiagnosticConfig,
    seed: int | None = None,
) -> list[CohortEvent]:
    """Control 3: HMM with wrong state interpretation (swap trend/range labels)."""
    n = len(candles)
    events: list[CohortEvent] = []

    current_model: GaussianHMM | None = None
    current_trend_state: int | None = None
    first_valid = config.feature_warmup
    log_alpha: np.ndarray | None = None
    filtered_probs = np.zeros((n, config.n_states))
    last_range_dominant_bar: int | None = None

    for i in range(first_valid, n):
        bars_since_first = i - first_valid
        need_retrain = (current_model is None or bars_since_first % config.retrain_interval == 0)

        if need_retrain:
            train_start = max(0, i - config.training_window + 1)
            train_data = features[train_start:i + 1]
            model = train_hmm(train_data, config, seed=seed)

            if model is not None:
                current_model = model
                # WRONG interpretation: use the LOW-variance state as "trend"
                correct_trend = interpret_states(current_model)
                current_trend_state = 1 - correct_trend  # SWAP
                log_alpha = None
            elif current_model is None:
                continue

        if current_model is None or current_trend_state is None:
            continue

        obs = features[i:i + 1]
        if np.any(np.isnan(obs)):
            continue

        log_emission = current_model._compute_log_likelihood(obs)

        if log_alpha is None:
            log_startprob = np.log(current_model.startprob_ + 1e-300)
            log_alpha = log_startprob + log_emission[0]
        else:
            log_transmat = np.log(current_model.transmat_ + 1e-300)
            log_alpha_new = np.zeros(config.n_states)
            for k in range(config.n_states):
                log_alpha_new[k] = log_emission[0, k] + np.logaddexp.reduce(
                    log_alpha + log_transmat[:, k]
                )
            log_alpha = log_alpha_new

        log_norm = np.logaddexp.reduce(log_alpha)
        prob = np.exp(log_alpha - log_norm)
        filtered_probs[i] = prob

        range_state = 1 - current_trend_state
        if prob[range_state] >= config.prob_threshold:
            last_range_dominant_bar = i

        trend_prob = prob[current_trend_state]
        prev_trend_prob = filtered_probs[i - 1, current_trend_state] if i > first_valid else 0.0

        if (
            trend_prob >= config.prob_threshold
            and prev_trend_prob < config.prob_threshold
            and last_range_dominant_bar is not None
            and (i - last_range_dominant_bar) <= config.staleness_limit
        ):
            if i >= config.momentum_lookback:
                momentum = candles[i].close - candles[i - config.momentum_lookback].close
                atr_i = atr[i] if not np.isnan(atr[i]) else 1.0
                if abs(momentum) < atr_i * config.ambiguity_atr_fraction:
                    continue
                direction = "LONG" if momentum > 0 else "SHORT"
                entry_bar = i + 1
                evt = build_cohort_event(
                    candles, i, entry_bar, direction, config,
                    cohort="control_wrong_interpretation",
                    metadata={"control": "HMM with swapped state labels"},
                )
                if evt:
                    events.append(evt)

    return events


def build_control_shifted_entry(
    candles: list[Candle],
    hmm_events: list[HMMEvent],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Control 4: Same main signal, entry delayed to i+3."""
    events: list[CohortEvent] = []
    for he in hmm_events:
        entry_bar = he.detection_bar + config.shifted_entry_delay_bars
        evt = build_cohort_event(
            candles, he.detection_bar, entry_bar, he.direction, config,
            cohort="control_shifted_entry",
            metadata={"control": "same signal, entry delayed to i+3"},
        )
        if evt:
            events.append(evt)
    return events


def build_control_random_offset(
    candles: list[Candle],
    hmm_events: list[HMMEvent],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Control 5: Shift main event timestamps by +137 bars."""
    n = len(candles)
    events: list[CohortEvent] = []
    main_bars = {he.detection_bar for he in hmm_events}

    for he in hmm_events:
        shifted_detection = he.detection_bar + config.random_offset_bars
        if shifted_detection in main_bars:
            continue
        entry_bar = shifted_detection + 1
        if entry_bar >= n:
            continue
        evt = build_cohort_event(
            candles, shifted_detection, entry_bar, he.direction, config,
            cohort="control_random_offset",
            metadata={"control": "timestamps shifted +137 bars"},
        )
        if evt:
            events.append(evt)

    return events


def build_control_smoothed(
    candles: list[Candle],
    features: np.ndarray,
    atr: np.ndarray,
    config: DiagnosticConfig,
    seed: int | None = None,
) -> list[CohortEvent]:
    """Control 6 (audit-only): HMM with smoothed probabilities (forward-backward).

    Uses predict_proba which is NOT tradable live (lookahead).
    Audit-only to quantify filtered vs smoothed gap.
    """
    n = len(candles)
    events: list[CohortEvent] = []

    first_valid = config.feature_warmup
    current_model: GaussianHMM | None = None
    current_trend_state: int | None = None
    smoothed_probs = np.zeros((n, config.n_states))
    last_range_dominant_bar: int | None = None

    for i in range(first_valid, n):
        bars_since_first = i - first_valid
        need_retrain = (current_model is None or bars_since_first % config.retrain_interval == 0)

        if need_retrain:
            train_start = max(0, i - config.training_window + 1)
            train_data = features[train_start:i + 1]

            # Remove NaN rows for training
            valid_mask = ~np.any(np.isnan(train_data), axis=1)
            valid_data = train_data[valid_mask]

            if len(valid_data) < 50:
                continue

            model = train_hmm(train_data, config, seed=seed)
            if model is not None:
                current_model = model
                current_trend_state = interpret_states(current_model)

                # Compute smoothed posteriors for the entire window up to i
                # This uses forward-backward (lookahead within window)
                window_data = features[train_start:i + 1]
                valid_window_mask = ~np.any(np.isnan(window_data), axis=1)
                valid_window = window_data[valid_window_mask]

                if len(valid_window) > 0:
                    try:
                        posteriors = current_model.predict_proba(valid_window)
                        # Map back to original indices
                        valid_indices = np.where(valid_window_mask)[0]
                        for vi, idx in enumerate(valid_indices):
                            abs_idx = train_start + idx
                            if abs_idx < n:
                                smoothed_probs[abs_idx] = posteriors[vi]
                    except Exception:
                        pass

        if current_model is None or current_trend_state is None:
            continue

        # Use smoothed probability for threshold crossing
        trend_prob = smoothed_probs[i, current_trend_state]
        prev_trend_prob = smoothed_probs[i - 1, current_trend_state] if i > first_valid else 0.0

        range_state = 1 - current_trend_state
        if smoothed_probs[i, range_state] >= config.prob_threshold:
            last_range_dominant_bar = i

        if (
            trend_prob >= config.prob_threshold
            and prev_trend_prob < config.prob_threshold
            and last_range_dominant_bar is not None
            and (i - last_range_dominant_bar) <= config.staleness_limit
        ):
            if i >= config.momentum_lookback:
                momentum = candles[i].close - candles[i - config.momentum_lookback].close
                atr_i = atr[i] if not np.isnan(atr[i]) else 1.0
                if abs(momentum) < atr_i * config.ambiguity_atr_fraction:
                    continue
                direction = "LONG" if momentum > 0 else "SHORT"
                entry_bar = i + 1
                evt = build_cohort_event(
                    candles, i, entry_bar, direction, config,
                    cohort="control_smoothed_audit",
                    metadata={"control": "smoothed probabilities (audit-only, NOT tradable)"},
                )
                if evt:
                    events.append(evt)

    return events


# --- Metrics ---

def metric_summary(events: list[CohortEvent]) -> dict[str, Any]:
    """Compute summary metrics for a cohort."""
    if not events:
        return {
            "count": 0,
            "er": None,
            "profit_factor": None,
            "median_net_return_pct": None,
            "mean_net_return_pct": None,
            "win_rate": None,
            "avg_win_pct": None,
            "avg_loss_pct": None,
            "win_loss_ratio": None,
            "median_mfe_consumed_pct": None,
            "median_hmm_lag_bars": None,
            "median_lag_mfe_consumed_pct": None,
            "folds": [],
        }

    net_returns = [e.net_return_pct for e in events]
    wins = [r for r in net_returns if r > 0]
    losses = [r for r in net_returns if r <= 0]

    win_rate = len(wins) / len(net_returns) if net_returns else 0.0
    avg_win = mean(wins) if wins else 0.0
    avg_loss = abs(mean(losses)) if losses else 0.0001
    win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")

    # Expectancy ratio
    if avg_loss > 0:
        er = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_loss
    else:
        er = float("inf") if avg_win > 0 else 0.0

    # Profit factor
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # MFE consumed
    mfe_consumed_vals = [e.mfe_consumed_pct for e in events]

    # HMM lag (from lag_audit if available)
    lag_bars = [e.lag_audit["hmm_lag_bars"] for e in events if e.lag_audit is not None]
    lag_mfe_consumed = [e.lag_audit["lag_mfe_consumed_pct"] for e in events if e.lag_audit is not None]

    # Walk-forward folds
    folds = []
    for fold_name, fold_start, fold_end in FOLD_WINDOWS:
        fold_events = [
            e for e in events
            if fold_start <= parse_ts(e.detection_time_utc) <= fold_end
        ]
        if fold_events:
            fold_net = [e.net_return_pct for e in fold_events]
            fold_wins = [r for r in fold_net if r > 0]
            fold_losses = [r for r in fold_net if r <= 0]
            fold_avg_win = mean(fold_wins) if fold_wins else 0.0
            fold_avg_loss = abs(mean(fold_losses)) if fold_losses else 0.0001
            fold_win_rate = len(fold_wins) / len(fold_net)
            if fold_avg_loss > 0:
                fold_er = (fold_win_rate * fold_avg_win - (1 - fold_win_rate) * fold_avg_loss) / fold_avg_loss
            else:
                fold_er = float("inf") if fold_avg_win > 0 else 0.0

            folds.append({
                "fold": fold_name,
                "count": len(fold_events),
                "er": fold_er,
                "median_net_return_pct": median(fold_net),
                "win_rate": fold_win_rate,
                "positive_median_net": median(fold_net) > 0,
            })
        else:
            folds.append({
                "fold": fold_name,
                "count": 0,
                "er": None,
                "median_net_return_pct": None,
                "win_rate": None,
                "positive_median_net": False,
            })

    return {
        "count": len(events),
        "er": er,
        "profit_factor": profit_factor,
        "median_net_return_pct": median(net_returns),
        "mean_net_return_pct": mean(net_returns),
        "win_rate": win_rate,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "win_loss_ratio": win_loss_ratio,
        "median_mfe_consumed_pct": median(mfe_consumed_vals) if mfe_consumed_vals else None,
        "median_hmm_lag_bars": median(lag_bars) if lag_bars else None,
        "median_lag_mfe_consumed_pct": median(lag_mfe_consumed) if lag_mfe_consumed else None,
        "folds": folds,
    }


# --- Invalidation Gates ---

def apply_gates(
    metrics: dict[str, dict[str, Any]],
    training_stats: dict[str, Any],
) -> dict[str, Any]:
    """Apply pre-result invalidation criteria."""
    main = metrics.get("main_hmm_filtered", {})
    stop_reasons: list[str] = []

    # Sample gate
    count = main.get("count", 0)
    if count < 100:
        stop_reasons.append(f"sample_size={count} < 100")

    # Median net return
    median_net = main.get("median_net_return_pct")
    if median_net is not None and median_net <= 0:
        stop_reasons.append(f"median_net_return={fmt_float(median_net, 4)}% <= 0")

    # ER gate
    er = main.get("er")
    if er is not None and er < 1.2:
        stop_reasons.append(f"ER={fmt_float(er, 4)} < 1.2")

    # Profit factor gate
    pf = main.get("profit_factor")
    if pf is not None and pf < 1.2:
        stop_reasons.append(f"PF={fmt_float(pf, 4)} < 1.2")

    # MFE consumed gate
    mfe_consumed = main.get("median_mfe_consumed_pct")
    if mfe_consumed is not None and mfe_consumed > 70:
        stop_reasons.append(f"median_mfe_consumed={fmt_float(mfe_consumed, 1)}% > 70%")

    # HMM lag + lag MFE combined gate
    hmm_lag = main.get("median_hmm_lag_bars")
    lag_mfe = main.get("median_lag_mfe_consumed_pct")
    if hmm_lag is not None and lag_mfe is not None:
        if hmm_lag > 5 and lag_mfe > 70:
            stop_reasons.append(f"hmm_lag={hmm_lag} > 5 AND lag_mfe_consumed={fmt_float(lag_mfe, 1)}% > 70%")

    # Control comparison gates (controls 1-5 must not beat main)
    primary_controls = [
        "control_simple_volatility",
        "control_adx_chop",
        "control_wrong_interpretation",
        "control_shifted_entry",
        "control_random_offset",
    ]
    main_er = main.get("er")
    if main_er is not None:
        for ctrl_name in primary_controls:
            ctrl = metrics.get(ctrl_name, {})
            ctrl_er = ctrl.get("er")
            ctrl_count = ctrl.get("count", 0)
            if ctrl_er is not None and ctrl_count >= 20 and ctrl_er >= main_er:
                stop_reasons.append(f"{ctrl_name} (ER={fmt_float(ctrl_er, 4)}) beats main (ER={fmt_float(main_er, 4)})")

    # Walk-forward gate
    folds = main.get("folds", [])
    positive_folds = sum(1 for f in folds if f.get("positive_median_net", False))
    if len(folds) >= 4 and positive_folds < 2:
        stop_reasons.append(f"walk_forward: {positive_folds}/4 folds positive < 2")

    # State interpretation stability
    total_retrains = training_stats.get("total_retrains", 0)
    flips = training_stats.get("trend_state_flips", 0)
    if total_retrains > 0:
        flip_rate = flips / total_retrains
        if flip_rate > 0.30:
            stop_reasons.append(f"state_interpretation_flips={flips}/{total_retrains} ({flip_rate:.1%}) > 30%")

    # Determine recommendation
    recommendation = "STOP" if stop_reasons else "EXPLORE"

    # EXPLORE validation (stricter)
    explore_gate_passed = True
    if recommendation == "EXPLORE":
        if er is not None and er < 1.5:
            explore_gate_passed = False
        if pf is not None and pf < 1.5:
            explore_gate_passed = False
        if count < 200:
            explore_gate_passed = False
        if positive_folds < 3:
            explore_gate_passed = False

    if recommendation == "EXPLORE" and not explore_gate_passed:
        recommendation = "INCONCLUSIVE"

    return {
        "recommendation": recommendation,
        "stop_reasons": stop_reasons,
        "explore_gate_passed": explore_gate_passed,
        "positive_folds": positive_folds,
        "total_folds": len(folds),
        "state_flip_rate": flips / total_retrains if total_retrains > 0 else 0.0,
    }


# --- Seed Sensitivity ---

def run_seed_sensitivity(
    candles: list[Candle],
    features: np.ndarray,
    atr: np.ndarray,
    config: DiagnosticConfig,
    primary_recommendation: str,
) -> dict[str, Any]:
    """Run seed sensitivity check with seeds 0, 123, 456."""
    sensitivity_seeds = [0, 123, 456]
    results = []

    for seed in sensitivity_seeds:
        events, stats = detect_hmm_events(candles, features, atr, config, seed=seed)
        cohort = build_main_cohort(candles, events, config)
        m = metric_summary(cohort)
        gates = apply_gates({"main_hmm_filtered": m}, stats)

        results.append({
            "seed": seed,
            "count": m["count"],
            "er": m["er"],
            "profit_factor": m["profit_factor"],
            "median_net_return_pct": m["median_net_return_pct"],
            "recommendation": gates["recommendation"],
        })

    # Check if verdict is consistent
    verdicts = [r["recommendation"] for r in results]
    verdict_consistent = all(v == primary_recommendation for v in verdicts)

    return {
        "seeds_tested": sensitivity_seeds,
        "results": results,
        "verdict_consistent": verdict_consistent,
        "primary_recommendation": primary_recommendation,
    }


# --- Report Rendering ---

def render_report(payload: dict[str, Any]) -> str:
    """Render markdown report."""
    recommendation = payload["invalidation_gates"]["recommendation"]
    main = payload["cohort_metrics"].get("main_hmm_filtered", {})
    training_stats = payload.get("training_stats", {})

    lines = [
        f"# FILTERED_HMM_REGIME_SHIFT_FEASIBILITY_V1 — Diagnostic Report",
        "",
        f"Generated: {payload['manifest']['generated_at_utc']}",
        f"Recommendation: **{recommendation}**",
        "",
        "## Data Quality",
        "",
        f"- Total bars: {payload['data_quality']['total_bars']}",
        f"- Range: {payload['data_quality']['start_time_utc']} to {payload['data_quality']['end_time_utc']}",
        f"- Gaps: {payload['data_quality']['gaps']}",
        f"- OHLC violations: {payload['data_quality']['ohlc_violations']}",
        f"- Zero-volume bars: {payload['data_quality']['zero_volume_bars']}",
        "",
        "## HMM Configuration",
        "",
        f"- States: {payload['config']['n_states']}",
        f"- Covariance type: `{payload['config']['covariance_type']}`",
        f"- Training window: {payload['config']['training_window']} bars",
        f"- Retrain interval: {payload['config']['retrain_interval']} bars",
        f"- Random seed: {payload['config']['random_seed']}",
        f"- Probability threshold: {payload['config']['prob_threshold']}",
        "",
        "## Training Statistics",
        "",
        f"- Total retrains: {training_stats.get('total_retrains', 'N/A')}",
        f"- Failed retrains: {training_stats.get('failed_retrains', 'N/A')}",
        f"- Ambiguous retrains: {training_stats.get('ambiguous_retrains', 'N/A')}",
        f"- State interpretation flips: {training_stats.get('trend_state_flips', 'N/A')}",
        "",
        "## Timing Model",
        "",
        f"- Detection bar: i",
        f"- State known bar: i (at close)",
        f"- Entry candidate bar: i+1",
        f"- Return start bar: i+1",
        f"- Primary returns from detection bar: False",
        "",
        "## Main Cohort Metrics",
        "",
        f"- Event count: {main.get('count', 0)}",
        f"- Expectancy ratio (ER): {fmt_float(main.get('er'), 4)}",
        f"- Profit factor (PF): {fmt_float(main.get('profit_factor'), 4)}",
        f"- Median net return: {fmt_float(main.get('median_net_return_pct'), 4)}%",
        f"- Mean net return: {fmt_float(main.get('mean_net_return_pct'), 4)}%",
        f"- Win rate: {fmt_float(main.get('win_rate'), 4)}",
        f"- Avg win: {fmt_float(main.get('avg_win_pct'), 4)}%",
        f"- Avg loss: {fmt_float(main.get('avg_loss_pct'), 4)}%",
        f"- Win/loss ratio: {fmt_float(main.get('win_loss_ratio'), 4)}",
        "",
        "## MFE Accessibility",
        "",
        f"- Median MFE consumed before entry: {fmt_float(main.get('median_mfe_consumed_pct'), 1)}%",
        f"- Median HMM lag (bars): {fmt_float(main.get('median_hmm_lag_bars'), 1)}",
        f"- Median lag-adjusted MFE consumed: {fmt_float(main.get('median_lag_mfe_consumed_pct'), 1)}%",
        "",
        "## Control Cohort Comparison",
        "",
        "| Cohort | Count | ER | PF | Median Net | Win Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for name, m in payload["cohort_metrics"].items():
        lines.append(
            f"| `{name}` | {m.get('count', 0)} | {fmt_float(m.get('er'), 4)} | "
            f"{fmt_float(m.get('profit_factor'), 4)} | {fmt_float(m.get('median_net_return_pct'), 4)}% | "
            f"{fmt_float(m.get('win_rate'), 4)} |"
        )

    lines.extend([
        "",
        "## Benchmark Comparison",
        "",
        f"- Trial-00095 reference: ER={TRIAL_00095_REFERENCE['er']}, PF={TRIAL_00095_REFERENCE['profit_factor']}",
        f"- ADX/CHOP reference: ER={ADX_CHOP_REFERENCE['er']}, PF={ADX_CHOP_REFERENCE['profit_factor']} (STOP)",
        "",
        "## Walk-Forward Metrics",
        "",
        "| Fold | Count | ER | Median Net | Win Rate | Positive |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ])

    for fold in main.get("folds", []):
        lines.append(
            f"| `{fold['fold']}` | {fold['count']} | {fmt_float(fold.get('er'), 4)} | "
            f"{fmt_float(fold.get('median_net_return_pct'), 4)}% | {fmt_float(fold.get('win_rate'), 4)} | "
            f"`{fold.get('positive_median_net', False)}` |"
        )

    # Seed sensitivity
    seed_sens = payload.get("seed_sensitivity", {})
    lines.extend([
        "",
        "## Seed Sensitivity",
        "",
        f"- Verdict consistent across seeds: `{seed_sens.get('verdict_consistent', 'N/A')}`",
        "",
        "| Seed | Count | ER | PF | Recommendation |",
        "| ---: | ---: | ---: | ---: | --- |",
    ])
    for r in seed_sens.get("results", []):
        lines.append(
            f"| {r['seed']} | {r['count']} | {fmt_float(r.get('er'), 4)} | "
            f"{fmt_float(r.get('profit_factor'), 4)} | `{r['recommendation']}` |"
        )

    lines.extend([
        "",
        "## Invalidation Gate Evaluation",
        "",
        f"- Recommendation: `{recommendation}`",
        f"- STOP reasons: `{payload['invalidation_gates']['stop_reasons']}`",
        f"- EXPLORE gate passed: `{payload['invalidation_gates']['explore_gate_passed']}`",
        f"- Walk-forward: {payload['invalidation_gates']['positive_folds']}/{payload['invalidation_gates']['total_folds']} folds positive",
        f"- State flip rate: {payload['invalidation_gates']['state_flip_rate']:.1%}",
        "",
        "## Artifact",
        "",
        f"- JSON path: `{payload['manifest']['json_path']}`",
        f"- JSON SHA256: `{payload['manifest'].get('json_sha256', 'pending')}`",
        "",
        f"## Recommendation: {recommendation}",
        "",
    ])

    if recommendation == "STOP":
        lines.append(f"**Reason:** {'; '.join(payload['invalidation_gates']['stop_reasons'])}")
    elif recommendation == "EXPLORE":
        lines.append("**Reason:** All STOP gates cleared and EXPLORE criteria met.")
    else:
        lines.append("**Reason:** Between STOP and EXPLORE thresholds.")

    lines.extend([
        "",
        "**Next:** Claude Code audits this diagnostic implementation and result before any follow-up work.",
    ])

    return "\n".join(lines) + "\n"


# --- Main Diagnostic Runner ---

def build_all_cohorts(
    candles: list[Candle],
    features: np.ndarray,
    atr: np.ndarray,
    hmm_events: list[HMMEvent],
    config: DiagnosticConfig,
) -> dict[str, list[CohortEvent]]:
    """Build all cohorts: main + 6 controls."""
    print(f"  Building main cohort from {len(hmm_events)} HMM events...")
    main_events = build_main_cohort(candles, hmm_events, config)

    print(f"  Building control 1: simple volatility...")
    ctrl_vol = build_control_simple_volatility(candles, features, config)

    print(f"  Building control 2: ADX/CHOP...")
    ctrl_adx = build_control_adx_chop(candles, config)

    print(f"  Building control 3: wrong interpretation...")
    ctrl_wrong = build_control_wrong_interpretation(candles, features, atr, config, seed=config.random_seed)

    print(f"  Building control 4: shifted entry...")
    ctrl_shifted = build_control_shifted_entry(candles, hmm_events, config)

    print(f"  Building control 5: random offset...")
    ctrl_random = build_control_random_offset(candles, hmm_events, config)

    print(f"  Building control 6: smoothed (audit-only)...")
    ctrl_smoothed = build_control_smoothed(candles, features, atr, config, seed=config.random_seed)

    cohorts = {
        "main_hmm_filtered": main_events,
        "control_simple_volatility": ctrl_vol,
        "control_adx_chop": ctrl_adx,
        "control_wrong_interpretation": ctrl_wrong,
        "control_shifted_entry": ctrl_shifted,
        "control_random_offset": ctrl_random,
        "control_smoothed_audit": ctrl_smoothed,
    }

    for name, evts in cohorts.items():
        print(f"    {name}: {len(evts)} events")

    return cohorts


def run_diagnostic(
    *,
    db_path: Path,
    report_path: Path,
    json_path: Path,
    config: DiagnosticConfig,
) -> dict[str, Any]:
    """Run the full HMM regime shift diagnostic."""
    print(f"Loading candles from {db_path}...")
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        candles = load_candles(conn, config)

    if not candles:
        raise RuntimeError("No candles loaded from database")

    print(f"Loaded {len(candles)} candles")
    quality = data_quality(candles)

    print("Computing features...")
    features = compute_features(candles, config)
    atr = compute_atr(candles, config.atr_period)

    print("Detecting HMM events (rolling window training + filtered probabilities)...")
    hmm_events, training_stats = detect_hmm_events(candles, features, atr, config)
    print(f"  Detected {len(hmm_events)} threshold crossing events")

    print("Building all cohorts...")
    cohorts = build_all_cohorts(candles, features, atr, hmm_events, config)

    print("Computing metrics...")
    metrics = {name: metric_summary(events) for name, events in cohorts.items()}

    print("Applying invalidation gates...")
    gates = apply_gates(metrics, training_stats)
    recommendation = gates["recommendation"]
    print(f"  Primary recommendation: {recommendation}")

    print("Running seed sensitivity check...")
    seed_sensitivity = run_seed_sensitivity(candles, features, atr, config, recommendation)
    print(f"  Verdict consistent: {seed_sensitivity['verdict_consistent']}")

    payload = {
        "manifest": {
            "diagnostic": "FILTERED_HMM_REGIME_SHIFT_FEASIBILITY_V1",
            "research_only": True,
            "production_changes": False,
            "db_path": str(db_path),
            "report_path": str(report_path),
            "json_path": str(json_path),
            "generated_at_utc": iso(datetime.now(timezone.utc)),
        },
        "config": asdict(config),
        "data_quality": quality,
        "training_stats": training_stats,
        "timing_model": {
            "detection_bar": "i",
            "state_known_bar": "i (at close)",
            "entry_candidate_bar": "i+1",
            "return_start_bar": "i+1",
            "primary_returns_from_detection_bar": False,
        },
        "cohort_metrics": metrics,
        "benchmark_comparison": {
            "trial_00095": TRIAL_00095_REFERENCE,
            "adx_chop": ADX_CHOP_REFERENCE,
        },
        "invalidation_gates": gates,
        "seed_sensitivity": seed_sensitivity,
        "events_sample": {
            name: [asdict(e) for e in events[:config.max_serialized_events_per_cohort]]
            for name, events in cohorts.items()
        },
    }

    # Remove state_interpretations from training_stats for JSON (too verbose)
    serializable_training_stats = {
        k: v for k, v in training_stats.items() if k != "state_interpretations"
    }
    serializable_training_stats["state_interpretation_count"] = len(training_stats.get("state_interpretations", []))
    payload["training_stats"] = serializable_training_stats

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False, default=str)
    json_path.write_text(json_text, encoding="utf-8")
    sha = hashlib.sha256(json_path.read_bytes()).hexdigest().upper()
    payload["manifest"]["json_sha256"] = sha

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(payload), encoding="utf-8")

    print(f"\nDiagnostic complete.")
    print(f"  Report: {report_path}")
    print(f"  JSON:   {json_path}")
    print(f"  Recommendation: {recommendation}")

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_diagnostic(
        db_path=args.db_path,
        report_path=args.report_path,
        json_path=args.json_path,
        config=DiagnosticConfig(),
    )
    print(json.dumps(payload["invalidation_gates"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
