# MARKET_TRUTH_LAYER_V3 Audit

Date: 2026-04-23
Scope: data-source audit, timing audit, schema design, feature recompute readiness, paper-fill sanity check
Mode: code audit + read-only production audit

## 1. Executive Verdict

Current production system does **not** yet operate on persistent market truth.

Before this change set:
- `MarketSnapshot` existed only in memory for the decision cycle.
- exact raw inputs used by the cycle were not persisted per cycle,
- `decision_outcomes` could not be linked back to a concrete market snapshot,
- deterministic recomputation of features from persisted truth was not possible.

After this change set in repo:
- `market_snapshots` persistence exists,
- `feature_snapshots` persistence exists,
- `decision_outcomes` can link to `snapshot_id` and `feature_snapshot_id`,
- a deterministic recompute/compare module exists in [validation/recompute_features.py](<C:\development\btc-bot\validation\recompute_features.py>).

This is enough to establish the V3 storage contract.

It is **not** enough yet to claim full backtest parity on production, because the new tables must first be deployed and filled by live paper/runtime cycles.

## 2. Current Data Flow Audit

### 2.1 Where market data enters the bot

Primary runtime construction happens in [data/market_data.py](<C:\development\btc-bot\data\market_data.py>) inside `MarketDataAssembler.build_snapshot()`.

Inputs:
- REST:
  - `fetch_book_ticker()` from [data/rest_client.py](<C:\development\btc-bot\data\rest_client.py>)
  - `fetch_klines()` for `15m`, `1h`, `4h`
  - `fetch_funding_history()`
  - `fetch_open_interest()`
- WebSocket:
  - `get_recent_agg_trades()` from [data/websocket_client.py](<C:\development\btc-bot\data\websocket_client.py>)
  - `get_recent_force_orders()`

Primary vs fallback:
- aggTrades: WS first, REST fallback via `fetch_agg_trades_window()`
- forceOrder: WS only
- candles, funding, OI, bookTicker: REST only

### 2.2 Where the decision snapshot is created

Decision-cycle snapshot is created in:
- [orchestrator.py](<C:\development\btc-bot\orchestrator.py>) → `BotOrchestrator._build_snapshot()`
- delegated to `MarketDataAssembler.build_snapshot()`

Timing:
- snapshot is built at the start of `run_decision_cycle()`,
- then lifecycle processing runs,
- then `FeatureEngine.compute(snapshot, ...)`,
- then `RegimeEngine.classify(features)`,
- then `SignalEngine`.

This ordering is deterministic, but before V3 the raw snapshot was ephemeral.

### 2.3 What was already persisted before V3

Persisted:
- `oi_samples`
- `cvd_price_history`
- `decision_outcomes`
- `trade_log`
- `runtime_metrics`

Not persisted per cycle:
- exact `bookTicker` used
- exact `candles_15m/1h/4h` arrays used
- exact `funding_history` window used
- exact aggTrade event set used
- exact forceOrder event set used
- per-cycle exchange timestamps for those inputs

### 2.4 Can exact cycle input be reconstructed today on production?

**Answer: NO.**

Why:
- current production DB does not contain per-cycle `market_snapshots`,
- historical raw replay tables are stale relative to current runtime,
- `trade_log.features_at_entry_json` does not contain enough raw market context to rebuild feature inputs,
- `decision_outcomes` had no snapshot linkage.

That was the core gap V3 addresses.

## 3. Final `market_snapshots` Schema

Implemented in:
- [storage/schema.sql](<C:\development\btc-bot\storage\schema.sql>)
- [storage/state_store.py](<C:\development\btc-bot\storage\state_store.py>) via idempotent migrations

### REQUIRED

Identity:
- `snapshot_id`
- `cycle_timestamp`
- `symbol`

Core 15m truth row:
- `timeframe`
- `open`
- `high`
- `low`
- `close`
- `volume`

Base market inputs:
- `open_interest`
- `bid_price`
- `ask_price`
- `source`
- `data_quality_flag`

Raw payload stores:
- `book_ticker_json`
- `open_interest_json`
- `candles_15m_json`
- `candles_1h_json`
- `candles_4h_json`
- `funding_history_json`
- `aggtrade_events_60s_json`
- `aggtrade_events_15m_json`
- `aggtrade_bucket_60s_json`
- `aggtrade_bucket_15m_json`
- `force_order_events_60s_json`
- `captured_at`

### OPTIONAL

- `exchange_timestamp`
- `funding_rate`
- `latency_ms`
- `source_meta_json`

Rationale:
- the explicit scalar columns make SQL-level audits cheap,
- the JSON payloads preserve exact normalized exchange truth used by the bot,
- strategy logic is untouched.

## 4. Layer Binding

Implemented binding:
- `decision_outcomes.snapshot_id`
- `decision_outcomes.feature_snapshot_id`
- `feature_snapshots.snapshot_id`

Path now available:

`market_snapshots.snapshot_id -> feature_snapshots.snapshot_id -> decision_outcomes.snapshot_id`

This gives the required:

`snapshot -> feature -> decision`

## 5. Feature Recompute Engine

Implemented:
- [validation/recompute_features.py](<C:\development\btc-bot\validation\recompute_features.py>)

Current recompute coverage:
- `atr_15m`
- `atr_4h`
- `atr_4h_norm`
- `ema50_4h`
- `ema200_4h`
- `tfi_60s` proxy
- `force_order_rate_60s`
- reclaim-distance diagnostics:
  - `close_vs_reclaim_buffer_atr`
  - `wick_vs_min_atr`
  - `sweep_vs_buffer_atr`

Comparison output per field:
- `expected`
- `actual`
- `abs_diff`
- `rel_diff_pct`
- `threshold_rel_pct`
- `status`

This module is deterministic and does not change runtime decisions.

## 6. Drift Thresholds

Defined in recompute module:
- ATR fields: 2.0%
- EMA fields: 1.0%
- TFI / force-order / reclaim-distance diagnostics: 5.0% default, tighter where directly numeric

Status semantics:
- `OK`
- `WARNING`
- `CRITICAL`

## 7. Timing Validation

### Current production verdict

**FAIL for exact proof, due to missing pre-V3 telemetry.**

Reason:
- production currently has `runtime_metrics.last_ws_message_at`,
- but it does not yet persist a per-cycle raw truth record with exchange timestamps and snapshot build latency,
- therefore exact lookahead / stale-data proof cannot be reconstructed post hoc for historical cycles.

### V3 timing fields now added

Per snapshot:
- `exchange_timestamp`
- `latency_ms`
- `source_meta_json`

This is the minimum contract needed to later produce:
- avg latency
- max latency
- stale-cycle percentage
- drift between cycle time and source time

## 8. Paper Fill Sanity Check

Source: production `trade_log` via server query on 2026-04-23.

### Verdict: FAIL

Evidence from recent paper trades:
- trade `2026-04-23T00:30:01Z -> 2026-04-23T00:30:21Z`
  - duration: ~20s
  - `exit_reason=TP`
  - `mae=0`
- trade `2026-04-22T19:15:05Z -> 2026-04-22T19:15:10Z`
  - duration: ~5s
  - `exit_reason=TP`
  - `pnl_abs=-790.91`
- trade `2026-04-22T00:15:01Z -> 2026-04-22T00:15:09Z`
  - duration: ~8s
  - `exit_reason=TP`
  - `pnl_abs=-481.33`

Interpretation:
- immediate TP closures in seconds still appear,
- `TP` with strongly negative PnL is semantically inconsistent,
- `mae=0` clusters still appear in the recent sample.

This does **not** block Market Truth Layer itself, but it means paper execution/lifecycle still needs a separate audit closure before trusting fill realism.

## 9. Risks and Remaining Gaps

Still missing for full parity:
- deployed runtime must actually populate new `market_snapshots` and `feature_snapshots`,
- historical cycles before V3 remain unrecoverable at raw-truth level,
- current live paper execution semantics still show suspicious TP/MAE patterns,
- candles/funding/open-interest replay tables on production were previously stale after 2026-04-17, so parity claims for recent periods remain limited until post-V3 truth capture fills in.

## 10. Acceptance Status vs V3 Goal

### Now true in code
- each future decision cycle can have a persisted `market_snapshot`
- each future cycle can have a persisted `feature_snapshot`
- `decision_outcomes` can link to both
- feature recomputation from raw truth is implemented

### Not yet true on production history
- historical cycles before deployment do not have market truth rows
- current production cannot yet produce a 200-cycle drift report from the new layer

## 11. Recommended Next Step

1. Deploy this V3 storage/instrumentation slice.
2. Let paper mode run until at least 200 decision cycles are captured.
3. Run:

```bash
c:\development\btc-bot\.venv\Scripts\python.exe validation\recompute_features.py --db storage\btc_bot.db --limit 200 --markdown-out validation\feature_drift_report.md
```

4. Review timing and fill reports before treating replay parity as closed.
