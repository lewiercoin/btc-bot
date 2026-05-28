# ORDER_FLOW_LIQUIDATION_EDGE_DISCOVERY_V1_PLAN

Planning date: 2026-05-28
Milestone: ORDER_FLOW_LIQUIDATION_EDGE_DISCOVERY_V1_PLANNING
Mode: Quant Research / Edge Discovery Mode
Status: PLANNING_COMPLETE - awaiting Claude audit before any implementation

## Scope

This is a planning-only research milestone.

Allowed output:

- Source research.
- Repo data surface inspection.
- One extracted deterministic mechanism.
- Timing model.
- MFE accessibility design.
- Baseline comparison design.
- Control cohort design.
- Pre-result invalidation criteria.
- One recommendation.

Not allowed in this milestone:

- No diagnostic scripts.
- No backtests or experiments.
- No result data.
- No production code changes.
- No FeatureEngine, SignalEngine, Governance, Risk, execution, orchestrator, or settings changes.
- No candidate promotion.

## Prior Research Context

Recent diagnostics changed the research question from pattern existence to earliest knowability.

| Diagnostic | Key result | Research implication |
| --- | --- | --- |
| `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1` | Delayed labels measured from `detection_bar` created fake edge. | Primary returns must start from `label_available_bar` or `entry_candidate_bar`. |
| `SMC_SEQUENCE_EDGE_FEASIBILITY_V1` | Median MFE before mitigation entry was `0.011565`; median MFE after entry was `0.004916`; net return after costs was `-0.000442`. | Full post-sweep SMC sequence arrives too late. |
| `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` | 28 post-sweep knowable states were tested; none had positive median net return after costs. | Post-sweep price-action confirmation is exhausted as an edge family. |

This plan therefore does not attempt to rescue SMC. It opens an orthogonal information family: order flow, liquidation, and derivatives crowding data.

## Research Question

Can a liquidation/order-flow state become knowable close enough to a sweep event to preserve tradable MFE, before later price-action confirmation consumes the move?

Primary hypothesis:

Forced liquidation flow after a liquidity sweep may mark exhaustion earlier than displacement, mitigation, or other price-action confirmation. If liquidation burst information is knowable by bar `i+2` and entry occurs at bar `i+3`, the signal may preserve more MFE than the failed SMC mitigation entry at approximately bar `i+8`.

## Source Research Method

Search coverage included:

- GitHub: order flow imbalance, liquidation map, aggTrades, liquidation cascade, CVD.
- TradingView/Pine: order flow, CVD, footprint imbalance, unusual volume/delta.
- Academic and quant literature: market microstructure, OFI, order imbalance, futures order flow.
- Exchange documentation: Binance USD-M futures aggTrade, forceOrder, open interest, funding.

The goal was mechanism extraction, not copying code or accepting screenshots.

## Source Coverage Matrix

| Source | URL | Type | Inspected artifact | Extracted mechanism | Classification | Determinism | Lookahead | Data availability | Applicability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Binance USD-M Futures Aggregate Trade Streams | https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams | Exchange docs | Stream description and response fields, lines 77-110 | Aggressive trade flow can be aggregated every 100ms; `m` identifies whether buyer is maker, allowing taker buy/sell inference. | Useful concept | Deterministic from exchange messages | No lookahead; event-time stream | Partial: repo has `aggtrade_buckets`, not raw `aggtrade` | Testable only at 60s/15m bucket level unless raw trades are backfilled |
| Binance USD-M Futures Liquidation Order Streams | https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Liquidation-Order-Streams | Exchange docs | Stream description and response fields, lines 77-112 | `<symbol>@forceOrder` provides forced liquidation snapshots; side, quantity, price, event time can define liquidation bursts. | Useful concept | Deterministic from exchange messages | No lookahead; snapshot caveat | Available in research DB for BTCUSDT 2022-01-01 to 2024-12-01 | Directly testable with caveat that Binance pushes only the largest liquidation order per symbol per 1000ms |
| Binance Open Interest endpoint | https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest | Exchange docs | API description and response fields, lines 93-117 | Current OI can define crowding state and OI delta before liquidation bursts. | Useful concept | Deterministic REST snapshot | No lookahead if sampled at or before bar close | Available as `open_interest` | Testable as context or control, not primary trigger in V1 diagnostic |
| Binance Funding Rate endpoint | https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History | Exchange docs | API description and response fields, lines 93-133 | Funding extremes can proxy crowded positioning before unwind. | Useful concept | Deterministic scheduled data | No lookahead if using known funding timestamps only | Available as `funding` | Testable as context; V1 should not combine with liquidation trigger until primary mechanism is validated |
| Binance Public Data | https://github.com/binance/binance-public-data | GitHub repo / data docs | README lines 225-299 | Historical futures `aggTrades` include price, quantity, timestamp, and buyer-maker flag; supports reconstructing CVD/TFI from raw trades if imported. | Useful concept | Deterministic archive files | No lookahead if timestamp aligned | Not currently raw in local DB; bucketed equivalents exist | Useful for future raw-trade inventory/backfill, not required for liquidation V1 |
| `aoki-h-jp/py-liquidation-map` | https://github.com/aoki-h-jp/py-liquidation-map | GitHub repo | README lines 239-348; `liqmap/mapping.py` raw lines 0-4 | Uses historical aggTrades, maps buyer-maker side, filters large notional trades, projects leverage-based liquidation levels. | Needs validation | Deterministic code | No direct future-bar signal; visualization may be descriptive | Raw aggTrades absent locally; liquidation events present separately | Useful concept for large forced-flow/crowding maps; not the V1 diagnostic |
| `vsching/liquidation-heatmap` | https://github.com/vsching/liquidation-heatmap | GitHub repo | README lines 280-291 and 413-416; `src/data_fetcher.py` raw lines 0-6 | Computes leverage liquidation levels and estimates heatmap intensity from order book depth and price distance. | Not applicable for V1 | Deterministic formula, but order-book inference is approximate | No future bars, but requires live/depth assumptions | Repo lacks historical order book depth | Not testable with current local data; do not use as diagnostic trigger |
| TradingView: Liquidity Structure & Order Flow [UAlgo] | https://www.tradingview.com/script/dKS9hKkg-Liquidity-Structure-Order-Flow-UAlgo/ | TradingView/Pine | Description/code excerpt lines 207-220 | Unusual volume state: volume z-score over 200 bars plus `abs(delta)/volume` threshold. | Useful concept | Deterministic if delta is available | No lookahead for current-bar close; profile rebuild on last bar is visual-only | Bucketed TFI/CVD and candle volume available | Candidate for later diagnostic, but V1 should not combine it with liquidation burst |
| TradingView: OrderFlow IQ | https://www.tradingview.com/script/GX4WhZ8h-TradingIQ-OrderFlow-IQ/ | TradingView indicator | Description lines 38-58 and 121-136 | Footprint rows, stacked imbalances, CVD, bar VWAP, max/min delta, buy/sell volume. | Discretionary only for this repo | Deterministic only with tick/footprint data | No explicit lookahead in description, but code not auditable here | Required tick price-row data absent | Not applicable for V1; useful as vocabulary only |
| TradingView: CVD Background | https://www.tradingview.com/script/JeRHI32w-CVD-Background-Institutional-Order-Flow-Bias-Model/ | TradingView/Pine | Description lines 37-152 | Lower-timeframe delta aggregation, CVD sign as regime filter. | Needs validation | Deterministic if lower-timeframe delta is defined | No source code visible in fetched page; repaint claim not independently verified | Repo has 60s/15m TFI/CVD buckets | Useful context; not a standalone V1 trigger |
| TradingView: Order Flow Pro - CVD | https://www.tradingview.com/script/y9bQtJSn/ | TradingView protected script | Description lines 39-86 and 359-361 | CVD above/below CVD moving average defines bullish/bearish flow regime. | Bad/repainting risk cannot be audited; protected source | Formula concept deterministic, implementation hidden | Source closed; no independent lookahead review | Bucketed CVD available | Do not use as implementation source |
| Tripathi, Dixit, Vipul: Information content of order imbalance | https://www.sciencedirect.com/science/article/abs/pii/S1544612320316779 | Academic paper | Abstract/highlights lines 49-67 | OIB can predict short-term returns; effect strongest in first five minutes and decays within thirty minutes. | Benchmark concept | Deterministic research variable | No direct implementation lookahead from abstract | Our 15m bars are coarser than the strongest window | Supports earlier-than-price-action timing requirement |
| Locke and Onayev: Order flow, dealer profitability, and price formation | https://www.sciencedirect.com/science/article/abs/pii/S0304405X07000633 | Academic paper | Abstract/introduction lines 49-56 and 83-87 | Futures prices move strongly with order flow in the short run; long-run effect can reverse/slip. | Benchmark concept | Deterministic empirical variable | No implementation rule | Aggtrade bucket data approximates trade-flow state | Supports measuring short-horizon MFE/MAE and avoiding delayed entries |
| Su et al.: The Price Impact of Generalized Order Flow Imbalance | https://arxiv.org/abs/2112.02947 | Academic paper | Abstract lines 31-40 | Generalized OFI improves explanation of short-term price changes at 30s, 1m, and 5m horizons. | Benchmark concept | Deterministic with LOB snapshots | No implementation rule | Full LOB snapshots absent | Not directly testable; supports OFI family but not V1 mechanism |
| Anantha and Jain: Forecasting High Frequency Order Flow Imbalance | https://arxiv.org/abs/2408.03594 | Academic paper | Abstract lines 31-40 | Bid/offer event asymmetry and lagged dependence can forecast near-term OFI. | Needs validation | Model-driven; Hawkes process stochastic | No direct implementation rule | Order-book event data absent; stochastic model not allowed in core path | Not applicable for V1; future offline research only |
| Bugaenko: Empirical Study of Market Impact Conditional on OFI | https://arxiv.org/abs/2004.08290 | Academic paper | Abstract lines 31-42 | Signed order-flow imbalance relates to market impact; ML forecast is suggested. | Useful concept but not implementation source | Deterministic for signed flow, ML component excluded | No source code in paper | Bucketed signed flow available | Use only deterministic signed-flow ideas; no ML in core decision path |

## Source Research Conclusion

The external source review supports order-flow/liquidation research as a genuinely new information family, but it narrows V1 to a single testable mechanism.

Rejected for V1:

- Footprint stacked imbalance: requires tick-level price-row bid/ask volume that the repo does not store.
- Order-book OFI: requires L1/L2 order-book updates that the repo does not store historically.
- Liquidation heatmap level prediction: requires inferred position distributions or order-book depth assumptions not present in local research data.
- Protected TradingView CVD scripts: source cannot be audited for lookahead/repainting.
- ML/Hawkes OFI forecasting: stochastic/modeling work is outside the deterministic research mechanism for this milestone.

Accepted for V1 planning:

- Liquidation burst reversal after sweep, because the repo has `candles` and `force_orders`, the rule is deterministic, and the state can be known by bar close without future price-action confirmation.

## Repo Data Surface Inspection

The requested `sqlite3` CLI is not installed in this environment, so schema and coverage were inspected read-only through Python `sqlite3`.

### Expected vs Actual Database Paths

| Requested surface | Actual status |
| --- | --- |
| `storage/market_data.db` | Missing locally. |
| `storage/btc_bot.db` | Present; local runtime/research-sized DB. |
| `research_lab/data/crowded_unwind_backtest.db` | Present; primary research DB for this plan. |

### Actual Market Data Tables

The handoff named `aggtrade` and `funding_rate`, but local schemas use:

- `aggtrade_buckets`, not raw `aggtrade`.
- `funding`, not `funding_rate`.
- `force_orders`.
- `open_interest`.
- `candles`.

### `research_lab/data/crowded_unwind_backtest.db` Coverage

| Table | Count | Range UTC | Notes |
| --- | ---: | --- | --- |
| `candles` | 256,394 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:30:00+00:00 | BTCUSDT only; 15m/1h/4h. |
| `candles` BTCUSDT 15m | 195,347 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:30:00+00:00 | 0 detected 15m gaps. |
| `aggtrade_buckets` | 3,122,272 | 2020-09-01T00:00:00+00:00 to 2026-03-28T21:14:00+00:00 | BTCUSDT 60s and 15m buckets. |
| `aggtrade_buckets` BTCUSDT 15m | 195,150 | 2020-09-01T00:00:00+00:00 to 2026-03-28T21:00:00+00:00 | 6 gaps larger than 15m; max 87,300 seconds. |
| `aggtrade_buckets` BTCUSDT 60s | 2,927,122 | 2020-09-01T00:00:00+00:00 to 2026-03-28T21:14:00+00:00 | 13 gaps larger than 60s; max 86,460 seconds. |
| `force_orders` | 146,864 | 2022-01-01T00:02:07.244000+00:00 to 2024-12-01T23:58:59.379000+00:00 | BTCUSDT only; critical coverage gap after 2024-12-01. |
| `force_orders` BUY | 61,539 | 2022-01-01T00:02:07.244000+00:00 to 2024-12-01T23:57:15.315000+00:00 | Total qty 14,501.5175. |
| `force_orders` SELL | 85,325 | 2022-01-01T00:11:40.894000+00:00 to 2024-12-01T23:58:59.379000+00:00 | Total qty 24,868.5311. |
| `funding` | 6,105 | 2020-09-01T00:00:00+00:00 to 2026-03-28T16:00:00+00:00 | BTCUSDT only. |
| `open_interest` | 524,971 | 2020-09-01T00:00:00+00:00 to 2026-03-29T00:00:00+00:00 | BTCUSDT only. |
| `cvd_price_history` | 0 | n/a | Empty. |

### `storage/btc_bot.db` Coverage

| Table | Count | Range UTC | Notes |
| --- | ---: | --- | --- |
| `candles` | 579,280 | 2020-09-01T00:00:00+00:00 to 2026-05-25T21:45:00+00:00 | BTCUSDT, ETHUSDT, SOLUSDT. |
| `candles` BTCUSDT 15m | 200,907 | 2020-09-01T00:00:00+00:00 to 2026-05-25T21:45:00+00:00 | 1 gap: 2026-03-28T20:30 to 2026-03-29T00:00. |
| `aggtrade_buckets` | 7,961,948 | 2020-09-01T00:00:00+00:00 to 2026-05-24T23:59:00+00:00 | BTCUSDT, ETHUSDT, SOLUSDT; 60s and 15m buckets. |
| `force_orders` | 0 | n/a | Not usable for liquidation research. |
| `funding` | 15,636 | 2020-09-01T00:00:00+00:00 to 2026-05-25T16:00:00.001000+00:00 | BTC/ETH/SOL. |
| `open_interest` | 541,649 | 2020-09-01T00:00:00+00:00 to 2026-05-25T21:50:00+00:00 | BTCUSDT only. |
| `cvd_price_history` | 0 | n/a | Empty. |

### Data Sufficiency Assessment

Sufficient for V1 diagnostic planning:

- BTCUSDT 15m candles with clean 2020-2026 coverage.
- BTCUSDT force-order liquidation events from 2022-01-01 through 2024-12-01.
- BTCUSDT OI/funding context across the research range.
- BTCUSDT 60s/15m TFI/CVD buckets for optional metadata only.

Insufficient for V1:

- Raw `aggtrade` table is absent; trade-size class and true tick-level CVD reconstruction cannot be audited from current DB alone.
- `force_orders` coverage ends 2024-12-01, so any diagnostic must use the overlapping 2022-01-01 to 2024-12-01 window for primary liquidation results.
- Binance `forceOrder` stream is a snapshot stream, not a complete liquidation tape; the diagnostic must treat observed liquidation burst as a lower-bound proxy.
- Local `storage/btc_bot.db` has zero force orders and must not be used as the liquidation result source.

## Extracted Mechanism

Mechanism name: `LIQUIDATION_BURST_REVERSAL_ENTRY_FEASIBILITY_V1`

Definition:

- Sweep detection: equal-level wick cross using the existing deterministic sweep logic concept from trial-00095 lineage.
- Liquidation burst: observed `force_orders.qty * force_orders.price` notional in `[sweep_bar_start, sweep_bar+2_end]` exceeds a rolling baseline multiple.
- Directional confirmation: liquidation side aligns with forced-flow exhaustion:
  - Downward sweep of equal lows expects SELL force orders, interpreted as long liquidation pressure.
  - Upward sweep of equal highs expects BUY force orders, interpreted as short liquidation pressure.
- Entry candidate: bar `sweep_bar+3`, the first full bar after the 3-bar liquidation-burst window is knowable.
- Primary returns: measured from `entry_candidate_bar`, never from `detection_bar`.

Observable inputs:

- `candles`: OHLCV for sweep detection and post-entry MFE/MAE.
- `force_orders`: event time, side, quantity, price for liquidation burst.
- `open_interest`: optional pre-event crowding context only.
- `funding`: optional pre-event crowding context only.

Deterministic rule:

1. For each BTCUSDT 15m bar `i`, detect a sweep event using only candles up to and including bar `i`.
2. Determine sweep direction:
   - `sweep_side = LOW`: candidate direction is LONG reversal after forced selling.
   - `sweep_side = HIGH`: candidate direction is SHORT reversal after forced buying.
3. Compute expected liquidation notional in bars `i`, `i+1`, and `i+2`:
   - LOW sweep: sum `qty * price` where `force_orders.side = SELL`.
   - HIGH sweep: sum `qty * price` where `force_orders.side = BUY`.
4. Compute baseline liquidation notional from completed pre-sweep bars only, for example a rolling 96-bar 15m median or mean absolute notional by side ending at bar `i-1`.
5. Signal condition:
   - `liquidation_burst_notional > 2.0 * baseline_side_notional`
   - and baseline coverage is sufficient.
6. If true:
   - `state_known_bar = i+2`
   - `entry_candidate_bar = i+3`
   - primary return starts at bar `i+3`.

Earliest knowable bar:

- `i+2`, at close of the third 15m bar in the liquidation burst window.

Required confirmation bars:

- 2 bars after sweep detection, because bars `i`, `i+1`, and `i+2` are required to measure the burst.

Required data tables:

- `candles`
- `force_orders`

Optional metadata tables:

- `open_interest`
- `funding`
- `aggtrade_buckets`

Invalidation condition:

- Any STOP gate in the "Pre-Result Invalidation Criteria" section triggers invalidation.

Expected edge behavior:

- A liquidity sweep forces crowded positions out.
- A clustered burst of forced liquidation flow marks exhaustion rather than discretionary continuation.
- Entry at bar `i+3` should be earlier than SMC mitigation entry and preserve enough post-entry MFE.
- The signal should beat ordinary sweep controls and opposite-side liquidation controls.

Novelty assessment:

- This is not SMC rescue. The trigger is not displacement, reclaim, mitigation, FVG, order block, CHOCH, or price-action confirmation.
- It uses an orthogonal data source: exchange liquidation events.
- Trial-00095 may already use TFI/CVD and cluster confluence, but it does not use `force_orders` burst notional as the primary trigger.

## Timing Model

| Bar | Definition | Liquidation burst reversal model |
| --- | --- | --- |
| `detection_bar` | First bar where raw event occurs | Sweep detected at bar `i` using completed bar `i` OHLC. |
| `state_known_bar` | First bar where state is knowable without future data | Bar `i+2`, after liquidation notional for bars `i` through `i+2` is known. |
| `confirmation_bar` | Bar that confirms the state | Bar `i+2`, when burst notional can be compared to pre-sweep baseline. |
| `entry_candidate_bar` | Earliest realistic entry bar | Bar `i+3`, next bar after confirmation. |
| `label_available_bar` | Bar where outcome label is known | Not used for signal; only outcome windows such as `i+3` to `i+23` for research metrics. |
| `return_start_bar` | Bar from which primary returns are measured | Bar `i+3`; must equal `entry_candidate_bar`. |

Timing rule:

- Primary returns must start at `entry_candidate_bar`.
- Detection-bar returns may be computed only as audit-only opportunity metrics.
- Same-bar entry on `i+2` is not allowed unless a later approved diagnostic explicitly models intrabar order timing, which this plan does not.

## MFE Accessibility Design

For every candidate event:

- `MFE_before_entry`:
  - LONG: `max(high[bar i : i+2]) - close[i]`
  - SHORT: `close[i] - min(low[bar i : i+2])`
- `MFE_after_entry`:
  - LONG: `max(high[bar i+3 : i+23]) - close[i+3]`
  - SHORT: `close[i+3] - min(low[bar i+3 : i+23])`
- `MAE_after_entry`:
  - LONG: `close[i+3] - min(low[bar i+3 : i+23])`
  - SHORT: `max(high[bar i+3 : i+23]) - close[i+3]`
- `% MFE consumed before entry`:
  - `MFE_before_entry / (MFE_before_entry + MFE_after_entry) * 100`
- Time from detection to entry:
  - `3` bars by design.
- Time from entry to MFE:
  - offset from bar `i+3` to the post-entry bar where max favorable excursion occurs.

Theoretical accessibility expectation:

- SMC mitigation failed with median entry delay around 8 bars and 69.8% of MFE consumed before entry.
- This mechanism enters after 3 bars. If sweep-to-entry MFE consumption scales with time, it should have a realistic chance to remain below the 70% hard failure line.
- Prior MFE accessibility states showed `direction_resolved_known` around 2 bars with 52.3% MFE consumed, but `force_order_burst_known` as previously defined arrived too late and consumed 100%. V1 must therefore use the explicit `[i, i+2]` burst window and must not inherit the later prior state timing.

Primary question:

- Is the 3-bar liquidation confirmation delay short enough to leave positive net return and less than 70% MFE consumed before entry?

## Baseline Comparison Design

Benchmark:

- trial-00095
- ER approximately 2.1
- PF approximately 4.6
- Entry timing: sweep + reclaim around 1-2 bars from sweep
- 271 historical trades
- Walk-forward validated

Comparison questions:

1. Is liquidation burst reversal genuinely different from trial-00095?
   - Yes by mechanism: `force_orders` burst notional is primary.
   - Trial-00095 uses sweep/reclaim plus TFI/CVD/cluster confluence.
   - V1 must measure overlap against trial-00095 event timestamps to prove portfolio distinctness.
2. Is it worth implementing if weaker than trial-00095?
   - Only if it has different risk profile, low overlap, and ER greater than 1.5 with PF greater than 4.0.
   - If ER and PF both lag trial-00095 and overlap is high, stop.
3. What would make it a serious challenger?
   - ER greater than 2.1 or materially different risk profile with ER greater than 1.5.
   - PF greater than 4.0.
   - At least 3 of 4 walk-forward folds positive.
   - MFE consumed before entry below 70%.
   - Candidate beats deterministic controls.

Metrics to compare:

- Event count.
- Median net return after costs.
- Win rate.
- Profit factor proxy.
- ER proxy if diagnostic maps to R-based exits.
- MFE before entry.
- MFE after entry.
- MFE consumed percentage.
- Fold-level stability.
- Overlap with trial-00095 events.

## Control Cohort Design

Controls must be deterministic and defined before results.

### Control 1: Non-liquidation sweeps

Definition:

- Same sweep detection rule.
- Same event direction.
- Liquidation notional in `[i, i+2]` is less than `0.5 * baseline_side_notional`.
- Entry at bar `i+3`.

Purpose:

- Tests whether liquidation burst adds information beyond ordinary sweep behavior.

Invalidation:

- If non-liquidation sweeps perform similarly or better, the candidate is invalid.

### Control 2: Opposite-side liquidation bursts

Definition:

- LOW sweep with BUY force-order burst, or HIGH sweep with SELL force-order burst.
- Same burst threshold and entry timing.

Purpose:

- Tests whether the direction of forced liquidation matters or whether any high liquidation activity is just noise.

Invalidation:

- If opposite-side bursts perform similarly or better, the directional mechanism is invalid.

### Control 3: Deterministic shifted-entry control

Definition:

- For each candidate event, shift the entry timestamp by +137 bars when enough future bars exist.
- Preserve direction.
- Measure the same MFE/MAE/return windows.

Purpose:

- Controls for broad market drift and data-mining.

Invalidation:

- If shifted entries perform similarly or better, the candidate is invalid.

### Control 4: Flow-only ablation

Definition:

- Liquidation burst threshold met without requiring a sweep event.
- Entry at the next bar after the same 3-bar burst window.

Purpose:

- Tests whether the sweep is necessary or whether liquidation burst alone is the actual signal.

Interpretation:

- If flow-only beats sweep-plus-flow, the mechanism should be reframed before any implementation.
- This does not authorize scope expansion in V1; it is an ablation control only.

## Pre-Result Invalidation Criteria

STOP gates:

- Median net return after costs <= 0.
- Win rate < 51%.
- Profit factor proxy < 1.2.
- MFE consumed before entry > 70%.
- Candidate does not beat the non-liquidation sweep control.
- Candidate does not beat the opposite-side liquidation control.
- Candidate does not beat deterministic shifted-entry control.
- Walk-forward has fewer than 2 of 4 folds positive.
- Sample size < 100 events.
- Signal requires future bars beyond `state_known_bar`.
- Result depends on changing burst thresholds after seeing outcomes.
- Result only works when returns start at `detection_bar`.
- Force-order coverage gaps are silently ignored.

EXPLORE gates:

- Median net return after costs > 0.
- Win rate > 55%.
- Profit factor proxy > 1.5.
- MFE consumed before entry < 50%.
- Candidate beats all controls.
- Walk-forward has at least 3 of 4 folds positive.
- Sample size >= 200 events.
- Overlap with trial-00095 is low enough to support independent portfolio value, or performance materially exceeds trial-00095.

INCONCLUSIVE gates:

- Sample size < 100 events.
- Usable force-order overlap coverage < 2 years.
- Required data table missing.
- Force-order coverage quality cannot be established.
- Baseline liquidation notional cannot be computed without large gaps.

## Data Quality Rules For Future Diagnostic

Any later diagnostic must:

- Restrict primary liquidation analysis to the overlap window where `candles` and `force_orders` both exist: 2022-01-01 through 2024-12-01.
- Report excluded bars and events outside force-order coverage.
- Report force-order side counts and notional by fold.
- Report gaps in `aggtrade_buckets` if flow metadata is included.
- Treat Binance `forceOrder` as snapshot/liquidation proxy data, not complete liquidation tape.
- Use UTC-normalized timestamps only.
- Align force-order events into deterministic 15m buckets by event time.
- Never silently drop missing force-order or candle data.

## Expected Diagnostic Artifact If Approved Later

If Claude approves this planning document, the next milestone should implement exactly one diagnostic:

- Name: `LIQUIDATION_BURST_REVERSAL_ENTRY_FEASIBILITY_V1`
- Scope: research-only.
- Inputs: `research_lab/data/crowded_unwind_backtest.db`.
- Outputs: one markdown report under `docs/analysis/` and one reproducible local JSON artifact under ignored analysis output.
- Tests: deterministic unit tests for timestamp bucketing, side mapping, baseline calculation, timing bars, MFE before/after entry, and controls.
- No production code.

## Scope Boundary Confirmation

This plan does not:

- Modify `core/**`.
- Modify `execution/**`.
- Modify `orchestrator.py`.
- Modify `settings.py`.
- Modify research lab infrastructure.
- Implement diagnostic code.
- Run a backtest.
- Generate result data.
- Promote a candidate.

## Recommendation: IMPLEMENT ONE DIAGNOSTIC

**Diagnostic name:** `LIQUIDATION_BURST_REVERSAL_ENTRY_FEASIBILITY_V1`

**Mechanism summary:** After an equal-level sweep, require a same-direction forced liquidation notional burst in bars `i` through `i+2`, then enter reversal at bar `i+3` and measure all primary returns from that entry bar.

**Timing:** detection at bar `i`, state known at bar `i+2`, entry at bar `i+3` for a 3-bar delay.

**Expected MFE accessibility:** Estimated below the 70% hard failure threshold because entry delay is 3 bars rather than the failed SMC mitigation delay of approximately 8 bars; the diagnostic must prove this and stop if measured consumption is greater than 70%.

**Estimated sample size:** At least 100 events is plausible from 146,864 BTCUSDT force-order rows and prior force-order state counts above 1,000, but the diagnostic must report the actual sweep-plus-liquidation sample before any performance claim.

**Estimated timeline:** 1 week for diagnostic implementation, focused tests, local run, and report.

**Next:** Codex implements the single research diagnostic only after Claude audits and approves this planning document.
