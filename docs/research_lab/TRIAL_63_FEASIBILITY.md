# Trial #63 Revalidation Feasibility Report

**Date:** 2026-04-28  
**Scope:** RECLAIM-EDGE-REVALIDATION-V1 / Step 0 source discovery  
**Status:** GO

## Verdict

Trial #63 can be revalidated with existing tools and data.

The exact candidate exists in the production Research Lab store as `run13-regime-aware-trial-00063`. The stored protocol hash matches local `research_lab/configs/default_protocol.json`, and the current `replay-candidate` CLI supports exact candidate replay by `--candidate-id`.

Operational caveat: do not run the replay against production `research_lab/research_lab.db` in place. The production store has the older `trials` schema and current code would add lineage columns and then write replay results. Full revalidation should copy the store first and use a dedicated revalidation store path.

## Q1: Trial #63 Config Source

- **Found:** YES
- **Primary source:** production `/home/btc-bot/btc-bot/research_lab/research_lab.db`
- **Trial ID:** `run13-regime-aware-trial-00063`
- **Created:** `2026-04-13T14:40:48.304591+00:00`
- **Protocol hash:** `af280ec9e9a36eaa8eef23eade9ed98ec15f2594cb5009d4f5dc826cba04eb1f`
- **Source quality:** exact stored `params_json`, `metrics_json`, and `funnel_json`
- **Secondary source:** commit `d245617` (`PAPER-TRADING-TRIAL63: apply trial #63 params to settings.py`)

## Q2: Trial #63 Parameter Vector

Exact params were extracted to `research_lab/trial_63_baseline_config.json`.

Key values:

```json
{
  "allow_long_in_uptrend": false,
  "atr_period": 14,
  "confluence_min": 3.6,
  "entry_offset_atr": 0.01,
  "invalidation_offset_atr": 0.01,
  "max_open_positions": 1,
  "max_trades_per_day": 3,
  "min_rr": 2.1,
  "tp1_atr_mult": 1.9000000000000001,
  "tp2_atr_mult": 3.9000000000000004
}
```

Original stored metrics:

```json
{
  "expectancy_r": 0.9944299033801505,
  "profit_factor": 2.486013742226806,
  "max_drawdown_pct": 0.05436286815986479,
  "trades_count": 183,
  "win_rate": 0.5245901639344263
}
```

## Q3: Current Production Config

Deployed repository on production:

- **Commit:** `cef65952`
- **Branch:** `modeling-context-closure`

Current `settings.py` defaults / research-live baseline:

```json
{
  "confluence_min": 4.5,
  "min_rr": 2.1,
  "allow_long_in_uptrend": true,
  "allow_uptrend_pullback": false,
  "raw_uptrend_whitelist": [],
  "max_open_positions": 1,
  "max_trades_per_day": 3,
  "max_consecutive_losses": 15,
  "daily_dd_limit": 0.2,
  "weekly_dd_limit": 0.3
}
```

Current `experiment` profile:

```json
{
  "confluence_min": 3.6,
  "min_rr": 1.6,
  "allow_long_in_uptrend": true,
  "allow_uptrend_pullback": false,
  "raw_uptrend_whitelist": [],
  "max_open_positions": 2,
  "max_trades_per_day": 6,
  "max_consecutive_losses": 15,
  "daily_dd_limit": 0.2,
  "weekly_dd_limit": 0.3
}
```

Note: Step 0 inspected deployed files and settings profiles. It did not query the live service environment variables or process command line.

## Q4: Delta Analysis

Trial #63 vs current defaults / research-live baseline:

| Parameter | Trial #63 | Current default | Changed |
|---|---:|---:|---|
| `allow_long_in_uptrend` | `false` | `true` | YES |
| `confluence_min` | `3.6` | `4.5` | YES |
| `daily_dd_limit` | `0.185` | `0.2` | YES |
| `max_consecutive_losses` | `5` | `15` | YES |
| `weekly_dd_limit` | `0.063` | `0.3` | YES |
| `min_rr` | `2.1` | `2.1` | NO |
| `max_open_positions` | `1` | `1` | NO |
| `max_trades_per_day` | `3` | `3` | NO |

Trial #63 vs current `experiment` profile:

| Parameter | Trial #63 | Experiment profile | Changed |
|---|---:|---:|---|
| `allow_long_in_uptrend` | `false` | `true` | YES |
| `confluence_min` | `3.6` | `3.6` | NO |
| `min_rr` | `2.1` | `1.6` | YES |
| `max_open_positions` | `1` | `2` | YES |
| `max_trades_per_day` | `3` | `6` | YES |
| `max_consecutive_losses` | `5` | `15` | YES |
| `daily_dd_limit` | `0.185` | `0.2` | YES |
| `weekly_dd_limit` | `0.063` | `0.3` | YES |

Conclusion: current runtime profiles must not be conflated with exact Trial #63. Full replay must rebuild candidate settings from the stored `params_json`, not from current `settings.py`.

## Q5: Backtest Funding Simulation

- **Implemented:** YES
- **Funding source:** `storage.repositories.fetch_funding_rates` in `backtest/backtest_runner.py`
- **Funding calculation:** `SimpleFillModel.calculate_funding()` delegates to `core.funding.compute_funding_paid()`
- **Trade output:** `TradeLog.funding_paid` is populated and net PnL subtracts funding.

Relevant code references:

- `backtest/backtest_runner.py:151` fetches funding samples.
- `backtest/backtest_runner.py:538` subtracts `record.funding_paid` from net PnL.
- `backtest/backtest_runner.py:575` writes `funding_paid` to the trade log.
- `backtest/backtest_runner.py:734` accrues funding.
- `backtest/fill_model.py:93` exposes `calculate_funding()`.
- `core/funding.py:16` computes directional funding paid.

## Q6: Backtest Fill Model

- **Model:** deterministic requested-price plus static slippage and fee rates.
- **Not a true bid/ask spread model.**
- `SimpleFillModel` applies adverse slippage by side:
  - `MARKET`: `3.0` bps
  - `LIMIT`: `1.0` bps
  - maker/taker fees: `0.04%`
- `ReplayLoader` currently sets `MarketSnapshot.bid == ask == close_price` for historical replay snapshots.

Relevant code references:

- `backtest/fill_model.py:51` defines `SimpleFillModel`.
- `backtest/fill_model.py:72` applies side-based slippage to requested price.
- `backtest/replay_loader.py:142` sets replay `bid` to close.
- `backtest/replay_loader.py:143` sets replay `ask` to close.
- `execution/paper_execution_engine.py:30` uses bid/ask when available in paper fills.

## Q7: Backtest-Paper Gap

The gap is a fill-model mismatch, not simply "snapshot price with zero spread".

Backtest:

- Uses requested strategy price.
- Adds static adverse slippage of `3` bps for market fills and `1` bp for limit fills.
- Does not use historical bid/ask spread in replay snapshots.

Paper:

- Uses actual ask for BUY and bid for SELL when available.
- Falls back to snapshot price if bid/ask is unavailable.
- Charges the same `0.04%` taker fee.

Step 0 estimate:

- If BTC spread is tighter than `3` bps, backtest market fills may be conservative versus paper.
- If spread widens above `3` bps, backtest may understate execution drag.
- Full revalidation should report this as a known limitation and, if market snapshot bid/ask history is available for the replay period, quantify actual spread distribution separately.

This is not a blocker for Step 1 replay, but it must be stated in the final revalidation report.

## Q8: Single-Candidate Replay Path

CLI exists:

```powershell
.\.venv\Scripts\python.exe -m research_lab replay-candidate --help
```

Supported arguments:

```text
--candidate-id CANDIDATE_ID
--source-db-path SOURCE_DB_PATH
--store-path STORE_PATH
--snapshots-dir SNAPSHOTS_DIR
--protocol-path PROTOCOL_PATH
--start-date START_DATE
--end-date END_DATE
```

Recommended full replay command template on production:

```bash
cd /home/btc-bot/btc-bot
cp research_lab/research_lab.db research_lab/trial_63_revalidation_store.db
python3 -m research_lab replay-candidate \
  --candidate-id run13-regime-aware-trial-00063 \
  --source-db-path storage/btc_bot.db \
  --store-path research_lab/trial_63_revalidation_store.db \
  --snapshots-dir research_lab/snapshots \
  --protocol-path research_lab/configs/default_protocol.json \
  --start-date 2022-01-01 \
  --end-date 2026-03-01
```

The source DB has the required replay tables on production:

| Table | Rows |
|---|---:|
| `candles` | 258901 |
| `funding` | 6164 |
| `open_interest` | 526496 |
| `aggtrade_buckets` | 3122658 |
| `force_orders` | 7129 |
| `trade_log` | 790 |

## Q9: Trial #63 Replay Support

- **Supports Trial #63:** YES, via exact `--candidate-id run13-regime-aware-trial-00063`.
- `research_lab/workflows/replay_candidate.py` loads trials from `store_path`, finds exact `trial_id`, builds candidate settings from stored params, creates a source DB snapshot, evaluates the candidate, runs post-hoc walk-forward, saves trial, saves walk-forward, and saves recommendation.

Important write behavior:

- `load_trials()` calls `init_store(store_path)`.
- Current `init_store()` adds missing lineage columns if the store is old.
- `replay_candidate()` then writes results back to `store_path`.
- Therefore full replay must use a copied store path, not production `research_lab/research_lab.db`.

No glue script is required for Step 1 replay.

## Q10: Run #13 Protocol JSON

- **Exists:** YES
- **Path:** `research_lab/configs/default_protocol.json`
- **Hash:** `af280ec9e9a36eaa8eef23eade9ed98ec15f2594cb5009d4f5dc826cba04eb1f`
- **Matches Trial #63 stored `protocol_hash`:** YES

No `run13*.json` file exists locally or on production, but `default_protocol.json` is the Run #13 protocol by hash.

Protocol:

```json
{
  "walkforward_mode": "post_hoc",
  "window_mode": "anchored_expanding",
  "train_days": 730,
  "validation_days": 365,
  "step_days": 365,
  "min_trades_per_window": 5,
  "min_expectancy_r_per_window": 0.0,
  "min_profit_factor_per_window": 1.0,
  "max_drawdown_pct_per_window": 50.0,
  "min_sharpe_ratio_per_window": 0.0,
  "min_trades_full_candidate": 100,
  "max_trades_full_candidate": 10000,
  "fragility_degradation_threshold_pct": 30.0,
  "promotion_requires_all_windows_pass": false,
  "promotion_requires_median_pass": true
}
```

## Feasibility Decision

**Verdict:** GO

Reasons:

- Exact Trial #63 source row found.
- Exact Trial #63 params, metrics, funnel, and protocol hash recovered.
- Protocol JSON exists and hash matches the stored candidate.
- Source database exists on production and contains required replay tables.
- Current backtest simulates fees and funding.
- Current replay CLI supports exact candidate replay.
- No code or glue-script changes are required.

Required controls for Steps 1-6:

- Use copied Research Lab store, not production `research_lab/research_lab.db`.
- Treat fill model as a known limitation: static slippage, not true historical bid/ask spread.
- Rebuild settings from stored Trial #63 params, not from current `settings.py` or `experiment` profile.
- Report current-vs-Trial config deltas explicitly in the full revalidation report.

## Next Step

Proceed to RECLAIM-EDGE-REVALIDATION-V1 Steps 1-6 after user approval.

Suggested Step 1 handoff should include:

- Copy store to `research_lab/trial_63_revalidation_store.db`.
- Run exact candidate replay with `--candidate-id run13-regime-aware-trial-00063`.
- Compare new metrics to original stored metrics.
- Rebuild post-hoc walk-forward with `default_protocol.json`.
- Publish final report at `docs/research_lab/TRIAL_63_REVALIDATION.md`.
