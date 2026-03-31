## PROMPT START

I have a production-grade BTC perpetual futures trading bot built in Python. I need you to find, recommend, or design a **quant-algo-agentic-AI system** that can perform systematic research, parameter optimization, and strategy tuning on this bot — **offline, not in the live execution path**.

---

### IMPORTANT CONTEXT: Prior Attempt

A previous version of this prompt was sent to another AI (Perplexity), which generated an optimization system design that was audited and found to have **6 blocking integration errors**:

1. Wrong class names (`RegimeEngineConfig` does not exist — it's embedded in `StrategyConfig` in `settings.py`)
2. Incorrect import paths (configs are not in separate engine modules — they live in `settings.py`)
3. `BacktestRunner` API mismatch (constructor takes `sqlite3.Connection` + `AppSettings`, not individual engine configs)
4. `analyze_closed_trades()` wrong signature (takes `AnalyzeTradesConfig`, not a generic config)
5. Wrong table names in DB queries (`candles_15m` does not exist — it's `candles` with `timeframe` column)
6. Wrong data volume estimates (off by 10–100×)

**Your recommendation must be grounded in the actual API and schema described below. Any system that generates code using the wrong class names, import paths, or table names will fail immediately.**

---

### Bot Architecture (deterministic pipeline)

```
MarketSnapshot → FeatureEngine → RegimeEngine → SignalEngine → GovernanceLayer → RiskEngine → Execution
```

Each engine is a pure function of its config + input. The pipeline is fully deterministic — no randomness in the core decision path.

**Critical architecture note**: There is **no separate `FeatureEngineConfig`, `RegimeEngineConfig`, `SignalEngineConfig`, or `GovernanceConfig` class visible to the optimization layer.** All tunable parameters for feature computation, regime detection, signal generation, governance, and risk management live in **two frozen dataclasses** in `settings.py`:

```python
# settings.py
@dataclass(frozen=True)
class StrategyConfig:   # FeatureEngine + RegimeEngine + SignalEngine params
    ...

@dataclass(frozen=True)
class RiskConfig:       # RiskEngine + Governance params
    ...

@dataclass(frozen=True)
class AppSettings:
    strategy: StrategyConfig
    risk: RiskConfig
    ...
```

The optimization system must build an `AppSettings` object from a flat parameter dict and pass it to `BacktestRunner`.

---

### Actual Tunable Parameter Space (~55 parameters)

All defaults are current production values as of 2026-03-31.

**`StrategyConfig` — FeatureEngine parameters (11 params):**
```python
atr_period: int = 14
ema_fast: int = 50
ema_slow: int = 200
equal_level_lookback: int = 50
equal_level_tol_atr: float = 0.25
sweep_buf_atr: float = 0.15
reclaim_buf_atr: float = 0.05
wick_min_atr: float = 0.40
funding_window_days: int = 60
oi_z_window_days: int = 60
force_order_history_points: int = 180   # NOTE: force_orders table has 0 records — this param affects a currently empty feature
```

**`StrategyConfig` — RegimeEngine parameters (5 params):**
```python
ema_trend_gap_pct: float = 0.0025
compression_atr_norm_max: float = 0.0055
crowded_funding_extreme_pct: float = 85.0
crowded_oi_zscore_min: float = 1.5
post_liq_tfi_abs_min: float = 0.2
```

**`StrategyConfig` — SignalEngine parameters (17 params):**
```python
confluence_min: float = 3.0
min_sweep_depth_pct: float = 0.0001
entry_offset_atr: float = 0.05
invalidation_offset_atr: float = 0.75   # stop-loss width (v1 widened from 0.25 to 0.75)
min_stop_distance_pct: float = 0.0015   # absolute floor on stop distance
tp1_atr_mult: float = 2.5               # take-profit 1 (v1 changed from 2.0)
tp2_atr_mult: float = 4.0               # take-profit 2 (v1 changed from 3.5)
weight_sweep_detected: float = 1.25
weight_reclaim_confirmed: float = 1.25
weight_cvd_divergence: float = 0.75
weight_tfi_impulse: float = 0.50
weight_force_order_spike: float = 0.40
weight_regime_special: float = 0.35
weight_ema_trend_alignment: float = 0.25
weight_funding_supportive: float = 0.20
direction_tfi_threshold: float = 0.05
direction_tfi_threshold_inverse: float = -0.05
tfi_impulse_threshold: float = 0.10
```

**`StrategyConfig` — Regime direction whitelist (1 categorical param):**
```python
regime_direction_whitelist: dict[str, tuple[str, ...]] = {
    "normal": ("LONG",),
    "compression": ("LONG",),
    "downtrend": ("LONG",),
    "uptrend": (),           # blocked
    "crowded_leverage": (),  # blocked
    "post_liquidation": ("LONG",),
}
# This controls which directions (LONG/SHORT/both) are allowed per regime.
# Strategy v1.1 disabled SHORT globally — SHORT had 0% WR across 68 trades.
# This is a discrete/categorical parameter, not continuous.
```

**`RiskConfig` — Risk + Governance parameters (19 params):**
```python
# Sizing
risk_per_trade_pct: float = 0.01
max_leverage: int = 5
high_vol_leverage: int = 3
min_rr: float = 2.8
# Position management
max_open_positions: int = 2
max_hold_hours: int = 24
high_vol_stop_distance_pct: float = 0.01
partial_exit_pct: float = 0.5          # % of position closed at TP1 (v1 added)
trailing_atr_mult: float = 1.0         # trailing stop on remainder after TP1 (v1 added)
# Governance / trade limits
max_trades_per_day: int = 3
max_consecutive_losses: int = 3
daily_dd_limit: float = 0.03
weekly_dd_limit: float = 0.06
cooldown_minutes_after_loss: int = 60
duplicate_level_tolerance_pct: float = 0.001
duplicate_level_window_hours: int = 24
session_start_hour_utc: int = 0
session_end_hour_utc: int = 23
no_trade_windows_utc: tuple[tuple[int, int], ...] = ()
```

**Parameter constraints (must be enforced):**
- `ema_fast < ema_slow`
- `tp1_atr_mult < tp2_atr_mult`
- `invalidation_offset_atr > 0`
- `min_rr > 1.0`
- `risk_per_trade_pct` in (0.001, 0.05)
- `max_leverage` in (1, 10)

---

### Backtest Infrastructure

**`BacktestRunner` — correct constructor and usage:**
```python
from backtest.backtest_runner import BacktestRunner, BacktestConfig
from storage.db import connect
from settings import load_settings, AppSettings, StrategyConfig, RiskConfig

# Build settings with custom params
settings = load_settings()  # returns AppSettings
settings = AppSettings(
    strategy=StrategyConfig(**strategy_params),
    risk=RiskConfig(**risk_params),
    # other settings fields copied from original
)

conn = connect(db_path)  # sqlite3.Connection with row_factory set
runner = BacktestRunner(conn, settings=settings)
result: BacktestResult = runner.run(BacktestConfig(
    start_date="2025-01-01",
    end_date="2025-03-31",
    initial_equity=10_000.0,
))
```

**`BacktestResult` fields:**
```python
result.performance.expectancy_r      # float — expected R per trade
result.performance.profit_factor     # float
result.performance.max_drawdown_pct  # float (0.0–1.0)
result.performance.sharpe_ratio      # float (annualized, sample variance)
result.performance.pnl_abs           # float
result.performance.win_rate          # float (0.0–1.0)
result.performance.trades_count      # int
result.trades                        # list[TradeLog]
result.equity_curve                  # list[tuple[datetime, float]]
```

**`scripts/run_backtest.py`** — CLI + instrumented runner with signal funnel output:
```
python scripts/run_backtest.py --start-date 2025-01-01 --end-date 2025-03-31 --output-json results.json
```
JSON output includes:
```json
{
  "performance": { "expectancy_r": ..., "profit_factor": ..., ... },
  "signal_funnel": {
    "signals_generated": 556,
    "signals_regime_blocked": 405,
    "signals_governance_rejected": 66,
    "signals_risk_rejected": 7,
    "trades_opened": 78
  }
}
```
The signal funnel data is critical for governance analysis — it shows **where in the pipeline signals are rejected**.

**Single backtest run performance:** ~2–5 seconds on a single core for a 90-day window at 15m resolution (~8,640 bars). This enables thousands of parameter sweeps per hour.

---

### SQLite Schema (actual table names)

```sql
-- All timeframes in one table
candles (symbol, timeframe, open_time, open, high, low, close, volume)
-- timeframe values: '15m', '1h', '4h'

funding (symbol, funding_time, funding_rate)
open_interest (symbol, timestamp, oi_value)
aggtrade_buckets (symbol, bucket_time, timeframe, taker_buy_volume, taker_sell_volume, tfi, cvd)
-- timeframe values: '60s', '15m'

force_orders (event_time, symbol, ...)   -- WARNING: 0 records, feature unreliable
trade_log (trade_id, opened_at, closed_at, direction, regime, pnl_abs, pnl_r, ...)
positions (...)
```

---

### Actual Data Volumes (2020-09-01 to 2026-03-28)

```
candles 15m:        195,347 bars   (~5.5 years)
candles 1h:          48,837 bars
candles 4h:          12,210 bars
funding:              6,105 records
open_interest:      524,971 records (5-min resolution)
aggtrade 60s:     2,021,396 records
aggtrade 15m:       134,766 records
force_orders:             0 records   ← EMPTY — optimization should treat force_order features as noise
```

This data volume enables **multi-year walk-forward** with statistically meaningful windows.

---

### Current Baseline (Strategy v1.1, 87-day backtest)

```
Period: 2025-01-01 to 2025-03-28
Initial equity: $10,000
Trades: 78
Win rate: 43.6%
Profit factor: 1.40
PnL: +$2,932
Max drawdown: 17.0%
Sharpe: 4.37

Signal funnel:
  556 generated
  405 regime blocked (73%)   ← regime_direction_whitelist + regime type filtering
   66 governance rejected (12%)
    7 risk rejected (1%)    ← primarily min_rr filter
   78 trades opened (14%)
```

**Key insight**: 73% of signals are blocked by regime gating. SHORT was disabled in v1.1 after 0% WR across 68 trades. The regime_direction_whitelist is the single highest-leverage parameter to investigate.

---

### `research/analyze_trades.py` — correct API:

```python
from research.analyze_trades import analyze_closed_trades, AnalyzeTradesConfig

config = AnalyzeTradesConfig(
    symbol="BTCUSDT",
    # optional filters: start_date, end_date, direction, regime, exit_reason
)
report = analyze_closed_trades(conn, config)
# report contains breakdowns by: direction, regime, exit_reason, confluence_bucket
```

---

### Hard Constraints

1. **No ML/AI in the live execution path** — core pipeline must remain deterministic
2. **LLM allowed only offline** — for hypothesis generation, result interpretation, reporting
3. **No randomness in core engines** — stochastic optimization is fine, but isolated
4. **Parameter changes must be explainable** — no black-box optimization
5. **Walk-forward validation required** — no pure in-sample curve-fitting
6. **Every experiment must be auditable** — full parameter set + results stored
7. **Minimum trade count filter** — reject parameter sets with <30 trades in window (statistical floor)
8. **Human approval gate** before any parameter change reaches production config
9. **Python 3.11+**, SQLite storage, frozen dataclasses for configs

---

### What I Need the Research System To Do

1. **Systematic Parameter Exploration**
   - Grid search, random search, Bayesian optimization (Optuna/Ax), or evolutionary algorithms
   - Over the ~55 parameter space defined above
   - Using `BacktestRunner` as the objective function
   - Multi-objective: maximize `expectancy_r`, minimize `max_drawdown_pct`, maximize `profit_factor`
   - Respect parameter constraints listed above

2. **Walk-Forward Analysis**
   - Train on N months, validate on M months, roll forward
   - Flag parameters that are fragile (large performance gap train vs. test)
   - Detect regime sensitivity (does the best config depend on which period?)
   - **True nested walk-forward**: the validation protocol itself must be fixed before optimization starts — agent must not be able to modify walk-forward windows or acceptance thresholds during a run

3. **Signal Funnel Analysis** (high priority given 73% regime block rate)
   - Per-rule attribution: which governance/regime rule blocks the most value-additive signals?
   - Is the current `min_rr=2.8` filter rejecting good trades?
   - What is the win rate of regime-blocked signals if they were allowed?
   - Optimal `confluence_min` threshold (currently 3.0)

4. **Sensitivity Analysis**
   - For each continuous parameter: how does `expectancy_r` respond to ±10% / ±25% / ±50% change?
   - Identify which parameters matter vs. which are noise
   - Special focus: `invalidation_offset_atr`, `tp1_atr_mult`, `tp2_atr_mult`, `partial_exit_pct`

5. **Regime-Conditional Analysis**
   - Which parameter sets work best in trending vs. compression regimes?
   - Should regime-specific configs be used instead of one global config?
   - Given that post_liquidation, uptrend, crowded_leverage have very few trades — flag regimes with <10 trades as statistically unreliable

6. **Agentic Loop (optional but preferred)**
   - Generate parameter hypothesis → run backtest → analyze results → generate next hypothesis
   - LLM in the loop for hypothesis generation and result interpretation
   - **Fixed validation protocol** — agent cannot modify walk-forward windows
   - Human approval gate before any change to production `settings.py`
   - Full experiment log: every parameter set tested + results

7. **Output Requirements**
   - Experiment log: every parameter set + full `BacktestResult` + `signal_funnel` data
   - Pareto frontier of multi-objective results (not flattened to single scalar)
   - Stability report: parameter variance across walk-forward windows
   - Actionable recommendation with reasoning and estimated improvement over baseline

---

### Integration Points (actual, verified)

```python
# 1. Settings construction
from settings import load_settings, AppSettings, StrategyConfig, RiskConfig

# 2. BacktestRunner
from backtest.backtest_runner import BacktestRunner, BacktestConfig, BacktestResult
runner = BacktestRunner(conn, settings=app_settings)
result = runner.run(BacktestConfig(start_date=..., end_date=..., initial_equity=10_000.0))

# 3. Trade analysis
from research.analyze_trades import analyze_closed_trades, AnalyzeTradesConfig
report = analyze_closed_trades(conn, AnalyzeTradesConfig())

# 4. DB connection
from storage.db import connect, init_db
conn = connect(db_path)   # sets row_factory automatically

# 5. CLI (single run, JSON output with signal_funnel)
python scripts/run_backtest.py --start-date 2025-01-01 --end-date 2025-03-31 --output-json results.json
```

---

### What I'm Looking For

Please recommend one or more of the following:

**A) Existing open-source frameworks** that can be adapted:
- Quant optimization: Optuna, Ax, DEAP, PyGAD, scikit-optimize
- Experiment tracking: MLflow, Weights & Biases, Optuna dashboard
- Agentic: LangChain, CrewAI, AutoGen, custom Python agent loop
- Trading-specific: QuantConnect LEAN research, Zipline research modules

**B) Custom architecture design** if no existing system fits:
- Component diagram
- Data flow
- LLM integration points
- Fixed validation protocol design
- Experiment storage schema
- Human-in-the-loop gates

**C) Hybrid approach** combining existing tools:
- Which tool for which function
- Glue code complexity
- Integration effort estimate

For each recommendation, explain:
1. How it maps to the `AppSettings` / `BacktestRunner` API described above
2. Walk-forward support (built-in or custom) and how to prevent agent from gaming it
3. Multi-objective support (Pareto, not scalar collapse)
4. Agentic/autonomous capability with human gate
5. Effort to integrate (days, not months)
6. Risks specific to this codebase (e.g., frozen dataclass immutability, SQLite concurrency)

Prioritize solutions that:
- Work correctly with the actual API (not hypothetical wrapper APIs)
- Respect the deterministic core constraint
- Produce explainable, auditable results
- Can run on a single machine (no cloud infra required)
- Handle the SQLite concurrency issue (multiple experiment workers reading the same DB)
- Account for the low trade count problem (~78 trades in 87 days at current settings)

## PROMPT END
