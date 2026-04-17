# Strategy Assessment — 2026-04-17

## Scope

Read-only diagnosis of why the live bot still produces `no_signal` after `DEPLOYMENT-REMEDIATION-2026-04-17` restored fresh data and runtime health.

This checkpoint does **not** tune parameters, change strategy logic, or mutate deployment state.

## Data Sources

- deployed SQLite DB: `/home/btc-bot/btc-bot/storage/btc_bot.db`
- audit trail / decision rows: `alerts_errors`
- pipeline output tables: `signal_candidates`, `executable_signals`, `trade_log`
- live snapshot reconstruction via current deployed code:
  - `orchestrator.py`
  - `core/signal_engine.py`
  - `core/regime_engine.py`
  - `core/feature_engine.py`
  - `settings.py`

## Pipeline Breakdown

Assessment window starts at the clean-redeploy restart:

- `since = 2026-04-17T13:32:54Z`

Observed fresh-data cycles:

- `2026-04-17T13:45:02Z`
- `2026-04-17T14:00:03Z`
- `2026-04-17T14:15:04Z`
- `2026-04-17T14:30:02Z`

Stage counts in that window:

| Stage | Count | Evidence |
|---|---:|---|
| Decision cycle entered | 4 | `alerts_errors`: `decision -> "No signal candidate."` |
| SignalCandidate created | 0 | `signal_candidates_since = 0` |
| ExecutableSignal created | 0 | `executable_signals_since = 0` |
| Closed trades | 0 | `closed_trades_since = 0` |

Conclusion from the pipeline counts:

- rejection occurs at `SignalCandidate` generation
- nothing reaches governance, risk, execution, or trade lifecycle

## Current Market Snapshot

### Probe A — `2026-04-17T14:36:06Z`

- `price = 77619.95`
- `regime = uptrend`
- `sweep_detected = true`
- `reclaim_detected = false`
- `sweep_side = HIGH`
- `sweep_depth_pct = 0.04896`
- `cvd_bullish_divergence = false`
- `cvd_bearish_divergence = false`
- `tfi_60s = -0.38116`
- `force_order_spike = false`

Counterfactual stage reconstruction:

- direction could resolve to `SHORT`
- counterfactual `confluence_score = 7.95`
- `confluence_min = 3.6`
- candidate still remains `null` because `reclaim_detected = false`
- even if reclaim appeared, `uptrend` allows no entries in Trial #63

### Probe B — `2026-04-17T14:40:01Z`

- `price = 77823.15`
- `regime = uptrend`
- `sweep_detected = true`
- `reclaim_detected = false`
- `sweep_side = HIGH`
- `sweep_depth_pct = 0.04980`
- `cvd_bullish_divergence = false`
- `cvd_bearish_divergence = false`
- `tfi_60s = 0.35943`
- `force_order_spike = false`

Stage reconstruction:

- direction does **not** resolve
- confluence is not even evaluated to a usable candidate
- candidate remains `null`

Stable pattern across both probes:

- strong `uptrend`
- high-side sweep present
- reclaim absent
- no CVD divergence
- no liquidation-spike structure

## Trial #63 Edge Requirements

Relevant requirements from the deployed code path:

1. `SignalEngine.generate()` requires:
   - `sweep_detected = true`
   - `reclaim_detected = true`
   - `sweep_level` present
   - `sweep_depth_pct >= min_sweep_depth_pct`
2. Direction must be inferred from divergence or TFI thresholds.
3. Direction must be allowed for the current regime.
4. Only then is confluence scored and compared against `confluence_min`.

Trial #63 thresholds / regime policy:

- `min_sweep_depth_pct = 0.00286`
- `confluence_min = 3.6`
- allowed directions:
  - `normal -> LONG`
  - `compression -> LONG`
  - `downtrend -> LONG/SHORT`
  - `uptrend -> none`
  - `crowded_leverage -> SHORT`
  - `post_liquidation -> LONG`

## Gap Analysis

What the current market satisfies:

- sweep exists
- sweep depth easily exceeds threshold
- market data is fresh
- runtime is healthy

What the current market does **not** satisfy:

- no reclaim after the sweep
- no durable reversal evidence via CVD divergence
- no regime allowance for entries in `uptrend`
- no liquidation-spike / post-liquidation structure

Important negative finding:

- `confluence_min = 3.6` is **not** the active bottleneck in the observed sample
- at `14:36:06Z`, counterfactual confluence would already pass, but the candidate still fails earlier on reclaim and regime policy

## ETF Bias / K2 Impact

`daily_external_bias` is still partial because ETF sources warn on missing keys, but this is not the cause of the current `no_signal`:

- current `SignalEngine` does not use ETF bias
- current `RegimeEngine` does not use ETF bias
- missing ETF data therefore does not explain rejection in the active pipeline

K2 remains a data-completeness issue, not a blocker for this assessment.

## Verdict

Classification: **market conditions / outside Trial #63 domain**

Why:

- fresh-data cycles reach the decision loop normally
- all observed rejections happen before `SignalCandidate` creation
- the live market is a strong `uptrend`
- the visible setup is a high-side sweep without reclaim
- Trial #63 does not permit entries in `uptrend`
- the sample does not show governance veto, risk veto, stale data, or an obviously too-high confluence threshold

## Implication

The bot is currently behaving according to strategy design on a healthy runtime.

If more participation during strong uptrends is desired, that is a future research or tuning question, not a remediation or runtime-bug question.
