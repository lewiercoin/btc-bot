# LLM Research Prompt: Quant-Algo-Agentic System for Trading Bot Tuning

Use this prompt with a frontier LLM (Claude, GPT-4, Gemini) to find or design an agentic research system for parameter optimization.

---

## PROMPT START

I have a production-grade BTC perpetual futures trading bot built in Python. I need you to find, recommend, or design a **quant-algo-agentic-AI system** that can perform systematic research, parameter optimization, and strategy tuning on this bot — **offline, not in the live execution path**.

### Bot Architecture (deterministic pipeline)

```
MarketSnapshot → FeatureEngine → RegimeEngine → SignalEngine → GovernanceLayer → RiskEngine → Execution
```

Each engine is a pure function of its config + input. The pipeline is fully deterministic — no randomness in the core decision path. All engines accept frozen dataclass configs. The bot uses SQLite for storage and has a complete backtest infrastructure.

### Tunable Parameter Space (~45 parameters)

**FeatureEngine (9 params):**
- `atr_period: int = 14` — ATR lookback
- `ema_fast: int = 50`, `ema_slow: int = 200` — EMA periods for trend
- `equal_level_lookback: int = 50`, `equal_level_tol_atr: float = 0.25` — support/resistance detection
- `sweep_buf_atr: float = 0.15`, `reclaim_buf_atr: float = 0.05` — liquidity sweep/reclaim buffers
- `wick_min_atr: float = 0.40` — minimum wick size
- `funding_window_days: int = 60`, `oi_z_window_days: int = 60` — lookback for funding/OI z-scores

**RegimeEngine (5 params):**
- `ema_trend_gap_pct: float = 0.0025` — EMA gap threshold for trending regime
- `compression_atr_norm_max: float = 0.0055` — ATR threshold for compression regime
- `crowded_funding_extreme_pct: float = 85.0` — funding percentile for crowded leverage
- `crowded_oi_zscore_min: float = 1.5` — OI z-score for crowded leverage
- `post_liq_tfi_abs_min: float = 0.2` — TFI threshold for post-liquidation regime

**SignalEngine (14 params):**
- `confluence_min: float = 3.0` — minimum score to generate signal
- `min_sweep_depth_pct: float = 0.0001` — minimum sweep depth
- `entry_offset_atr: float = 0.05` — entry price offset from level
- `invalidation_offset_atr: float = 0.25` — stop-loss offset
- `tp1_atr_mult: float = 2.0`, `tp2_atr_mult: float = 3.5` — take-profit multipliers
- 8 confluence weights: `weight_sweep_detected: 1.25`, `weight_reclaim_confirmed: 1.25`, `weight_cvd_divergence: 0.75`, `weight_tfi_impulse: 0.50`, `weight_force_order_spike: 0.40`, `weight_regime_special: 0.35`, `weight_ema_trend_alignment: 0.25`, `weight_funding_supportive: 0.20`
- `direction_tfi_threshold: float = 0.05` — TFI threshold for direction inference
- `tfi_impulse_threshold: float = 0.10` — TFI threshold for impulse detection

**Governance (8 params):**
- `cooldown_minutes_after_loss: int = 60`
- `duplicate_level_tolerance_pct: float = 0.001`
- `duplicate_level_window_hours: int = 24`
- `max_trades_per_day: int = 3`
- `max_consecutive_losses: int = 3`
- `daily_dd_limit: float = 0.03` (3%)
- `weekly_dd_limit: float = 0.06` (6%)
- `session_start_hour_utc / session_end_hour_utc`

**Risk (7 params):**
- `risk_per_trade_pct: float = 0.01` (1%)
- `max_leverage: int = 5`, `high_vol_leverage: int = 3`
- `min_rr: float = 2.8` — minimum reward:risk ratio
- `max_open_positions: int = 2`
- `max_hold_hours: int = 24`
- `high_vol_stop_distance_pct: float = 0.01`

### Backtest Infrastructure

- **BacktestRunner**: Replays historical bars through the full pipeline. Deterministic — same config + same data = same result.
- **ReplayLoader**: Loads candles (15m/1h/4h), funding, OI, aggtrade buckets (60s/15m) from SQLite.
- **FillModel**: Simulates order fills using OHLC candle data (checks if price was touched).
- **PerformanceAnalyzer**: Computes PnL, R-multiples, profit factor, expectancy, Sharpe, max drawdown, equity curve.
- **analyze_trades.py**: Offline analysis — breakdowns by direction, regime, exit reason, confluence bucket. Exports JSON.
- **run_backtest.py**: CLI entry point. `--start-date`, `--end-date`, `--initial-equity`, `--output-json`.

A single backtest run (1000 bars) takes ~2-5 seconds. This enables thousands of parameter sweeps.

### Data Available

- **Candles**: 15m (2500+), 1h (1000+), 4h (1000+) — covering months
- **Funding rates**: 200+ records
- **Open interest**: 500+ 5-minute records
- **Aggtrade buckets**: 17000+ records (60s and 15m CVD/TFI/volume/trade_count)
- Storage: SQLite, single-file DB

### Hard Constraints (from engineering discipline)

1. **No ML/AI in the live execution path** — the core pipeline must remain deterministic
2. **LLM allowed only for offline research, post-trade analysis, reporting** — never in real-time decision loop
3. **No randomness in core engines** — any stochastic logic must be isolated and flagged
4. **Parameter changes must be explainable** — no black-box optimization
5. **Walk-forward validation required** — no pure in-sample curve-fitting
6. **Every decision must be auditable** — changes must be traceable to analysis
7. **Python 3.12+**, SQLite storage, frozen dataclasses for configs

### What I Need the Research System To Do

1. **Systematic Parameter Exploration**
   - Grid search, random search, Bayesian optimization, or evolutionary algorithms
   - Over the ~45 parameter space defined above
   - Using BacktestRunner as the objective function
   - Multi-objective: maximize expectancy_r, minimize max_drawdown, maximize profit_factor
   - Respect parameter constraints (e.g., ema_fast < ema_slow, tp1 < tp2)

2. **Walk-Forward Analysis**
   - Split historical data into train/test windows
   - Optimize on train, validate on test
   - Rolling windows to detect parameter stability vs. regime sensitivity
   - Flag parameters that are fragile (overfit)

3. **Regime-Aware Tuning**
   - The bot has explicit regime states: TRENDING, COMPRESSION, CROWDED_LEVERAGE, POST_LIQUIDATION, NEUTRAL
   - Research system should analyze which parameters work best per regime
   - Suggest regime-conditional parameter sets if beneficial

4. **Sensitivity Analysis**
   - For each parameter: how much does expectancy change per unit change?
   - Identify which parameters matter most vs. which are noise
   - Partial dependence plots or equivalent

5. **Governance Filter Analysis**
   - Current rejection rate is ~93% (only 4 trades from 58 signals in 11 days)
   - Research system should analyze: which governance rules kill the most signals, and whether those rejections are value-additive or value-destructive

6. **Agentic Loop (optional but preferred)**
   - The system should be able to run autonomously:
     - Generate parameter hypothesis → run backtest → analyze results → generate next hypothesis
   - LLM-in-the-loop for hypothesis generation and result interpretation
   - Human approval gate before applying changes to production config
   - Full audit trail of experiments

7. **Output Requirements**
   - Experiment log: every parameter set tested + results
   - Best parameter sets ranked by multi-objective score
   - Stability report: which parameters are robust vs. fragile
   - Actionable recommendations with reasoning
   - All outputs as JSON or structured data for downstream processing

### Integration Points

The research system must interface with:
- `settings.py` — reads/writes frozen dataclass configs
- `backtest/backtest_runner.py` — `BacktestRunner.run(config)` returns results
- `research/analyze_trades.py` — `analyze_closed_trades(conn, config)` returns `TradeAnalysisReport`
- `storage/db.py` — SQLite connection for historical data access
- `scripts/run_backtest.py` — CLI interface for single runs

### What I'm Looking For

Please recommend one or more of the following:

**A) Existing open-source frameworks** that can be adapted:
- Quant optimization libraries (Optuna, Ax, DEAP, PyGAD, etc.)
- Agentic AI frameworks (LangChain, CrewAI, AutoGen, etc.)
- Trading-specific research platforms (Zipline, Backtrader research modules, QuantConnect LEAN, etc.)
- Experiment tracking (MLflow, Weights & Biases, Optuna dashboard, etc.)

**B) Custom architecture design** if no existing system fits:
- Component diagram
- Data flow
- LLM integration points
- Human-in-the-loop gates
- Experiment storage schema

**C) Hybrid approach** combining existing tools:
- Which tool for which function
- Glue code required
- Integration complexity estimate

For each recommendation, explain:
1. How it maps to my parameter space and backtest infrastructure
2. Walk-forward support (built-in or must be implemented)
3. Multi-objective optimization support
4. Agentic/autonomous capability
5. Effort to integrate (days, not months)
6. Risks and limitations

Prioritize solutions that:
- Respect my deterministic core constraint
- Keep LLM in the research loop, not the execution loop
- Produce explainable, auditable results
- Can run on a single machine (no cloud infra required)
- Are production-quality, not toy/demo code

## PROMPT END
