# ORDER_FLOW_LIQUIDATION_EDGE_DISCOVERY_V1 Plan

Date: 2026-05-28
Status: planning only, not approved for implementation
Builder: Codex
Audit target: Claude Code

## 1. Executive Verdict

**YES: Plan `ORDER_FLOW_LIQUIDATION_EDGE_DISCOVERY_V1`.**

This is not another SMC rescue. The three closed sweep/SMC diagnostics showed
that candle-confirmation states arrive too late. The remaining plausible source
of a tradable post-sweep edge is earlier microstructure information:
liquidation bursts, aggressive taker imbalance, CVD/price absorption, OI/funding
crowding, and force-order exhaustion.

The repo already has enough surface area to justify a plan:

- live aggregation supports aggTrade and forceOrder streams
  (`data/websocket_client.py:134-139`, `data/websocket_client.py:220-239`);
- runtime snapshots carry funding, OI, aggTrade buckets, and force-order windows
  (`core/models.py:90-124`);
- FeatureEngine computes funding/OI/CVD/TFI/force-order facts
  (`core/feature_engine.py:329-356`);
- ReplayLoader can build historical snapshots with the same data families
  (`backtest/replay_loader.py:111-151`, `backtest/replay_loader.py:201-292`);
- the canonical research DB has rich aggTrade/OI/funding history and partial
  liquidation history.

The main gap is not architecture. It is data quality and mechanism isolation:
force-order history is incomplete after 2024-12-01 in
`research_lab/data/crowded_unwind_backtest.db`, and current bot logic uses flow
mostly as direction/confluence rather than as a primary early classifier.

## 2. Lessons From Failed SMC/Sweep Research

Delayed price-action labels created fake edge when measured from detection time.
The SMC mitigation/retest sequence found real movement but entered too late:
median 8 bars from sweep to entry, with much larger MFE before entry than after
entry. The MFE accessibility diagnostic then tested 28 post-sweep knowable
states and found no positive median net return after costs. Therefore the next
family must not add CHOCH/FVG/OB labels or wait for prettier candle structure.
It must ask whether microstructure facts are knowable at or near the sweep,
before favorable excursion is consumed. Detection-bar returns remain audit-only
unless the flow state is genuinely known at detection-bar close.

## 3. Existing Bot Order-Flow Inventory

| Data Source | Available Historically? | Available Live? | Available in Replay? | Timestamp Alignment Known? | Used in Current Edge? | Currently Decisive or Metadata? |
| --- | --- | --- | --- | --- | --- | --- |
| aggTrades | Yes. `aggtrade_buckets` exists (`storage/schema.sql:42-51`); research DB has 3,122,272 rows, including 195,150 15m and 2,927,122 60s buckets. | Yes. WebSocket subscribes to `<symbol>@aggTrade` (`data/websocket_client.py:134-139`) and MarketData aggregates 60s/15m buckets (`data/market_data.py:26-55`, `data/market_data.py:265-272`). | Yes. Replay selects `taker_buy_volume`, `taker_sell_volume`, `tfi`, `cvd` (`backtest/replay_loader.py:241-264`). | Mostly. Buckets have `bucket_time`; snapshots persist `aggtrades_exchange_ts` (`storage/schema.sql:247-261`). Needs closed-bucket confirmation for sub-15m states. | Yes. TFI/CVD drive direction and confluence (`core/signal_engine.py:218-226`, `core/signal_engine.py:266-271`). | Decisive for direction/confluence, but not yet a standalone mechanism. |
| CVD | Yes. Stored in `aggtrade_buckets.cvd` and `cvd_price_history` (`storage/schema.sql:49-64`); backfill script can populate history from aggTrade buckets (`scripts/backfill_cvd_history.py:183-216`). | Yes. MarketData persists CVD price bars from aggTrade buckets (`data/market_data.py:482-500`). | Yes. Replay loads 15m CVD from aggTrade buckets (`backtest/replay_loader.py:241-264`); CVD history bootstrap exists (`core/feature_engine.py:259-278`). | Medium. CVD is bucket-close aligned; divergence requires prior CVD/price history and gap checks (`core/feature_engine.py:500-571`). | Yes. CVD divergence can infer direction and add score (`core/signal_engine.py:218-223`, `core/signal_engine.py:259-264`). | Decisive if divergence is exclusive; otherwise metadata/confluence. Prior MFE diagnostic found CVD divergence weak as post-sweep state. |
| TFI | Yes. Computed as `(taker_buy - taker_sell) / total` in bootstrap and live aggregation (`scripts/bootstrap_history.py:123-149`, `data/market_data.py:26-55`). | Yes. Live aggTrade buckets include TFI (`data/market_data.py:184-187`). | Yes. Replay returns TFI for 60s/15m buckets (`backtest/replay_loader.py:241-264`, `backtest/replay_loader.py:372-375`). | Mostly. Bucket close must be enforced for live/replay parity. | Yes. Direction thresholds and impulse scoring use TFI (`core/signal_engine.py:224-226`, `core/signal_engine.py:266-271`). | Decisive in current edge. New research must prove novelty beyond TFI thresholds. |
| Force orders / liquidations | Partially. `force_orders` table exists (`storage/schema.sql:67-73`); research DB has 146,864 rows from 2022-01-01 to 2024-12-01 only. `param_registry.py:19` notes structural censoring and backfill limitations. | Yes. WebSocket subscribes to `<symbol>@forceOrder` (`data/websocket_client.py:134-139`) and buffers recent events (`data/websocket_client.py:100-111`, `data/websocket_client.py:232-239`). Dedicated collector exists (`scripts/server/run_force_order_collector.py:33-34`, `scripts/server/run_force_order_collector.py:267-300`). | Yes. Replay selects force orders and builds a 60s window (`backtest/replay_loader.py:276-292`, `backtest/replay_loader.py:379`). | Risky. Binance stream publishes only the largest liquidation order per symbol per 1000ms, per official docs, so burst intensity is censored. | Yes but lightly. FeatureEngine computes rate/spike/decreasing (`core/feature_engine.py:352-356`, `core/feature_engine.py:574-585`); SignalEngine adds a small score (`core/signal_engine.py:272-274`). | Metadata/small confluence today. Could become decisive only if censoring and coverage pass audit. |
| Open interest | Yes. `open_interest` table exists (`storage/schema.sql:24-29`); research DB has 524,971 rows from 2020-09-01 to 2026-03-29. | Yes. REST fetch exists (`data/rest_client.py:347-367`) and MarketData fetches/persists samples (`data/market_data.py:123-126`). | Yes. Replay selects last-known OI (`backtest/replay_loader.py:223-237`, `backtest/replay_loader.py:346-350`). | Medium. Binance public OI stats are interval data; live current OI and historical OI must be aligned as last-known samples. | Yes. OI z-score feeds crowded leverage and features (`core/feature_engine.py:336-337`, `core/regime_engine.py:49-54`). | Mostly regime/context today, not decisive entry timing. |
| Funding | Yes. `funding` table exists (`storage/schema.sql:16-21`); research DB has 6,105 rows from 2020-09-01 to 2026-03-28. | Yes. REST funding history fetch exists (`data/rest_client.py:332-345`) and MarketData loads a window (`data/market_data.py:119-121`, `data/market_data.py:341-376`). | Yes. Replay slices funding history (`backtest/replay_loader.py:111-114`, `backtest/replay_loader.py:201-219`). | High at 8h cadence, but not an intrabar trigger. Funding is known only at published funding timestamps or via last known rate. | Yes. Funding supports confluence and regime (`core/signal_engine.py:286-291`, `core/regime_engine.py:49-54`). | Metadata/context. Should not be used alone for timing. |
| Regime labels | Yes, reconstructable from features. Not a stored historical label in research DB. | Yes. RegimeEngine classifies every cycle (`core/regime_engine.py:17-32`). | Yes, BacktestRunner builds RegimeEngine with strategy config (`backtest/backtest_runner.py:273-283`). | Depends on feature alignment. | Yes. SignalEngine and Governance use regime context. | Context/guardrail. Not a primary proposed edge. |

### Inventory Gaps

- The main research DB has empty `decision_outcomes`, `feature_snapshots`, and
  `market_snapshots`; accepted `signal_candidates` exist but only 106 rows. This
  limits rejected-population reconstruction from persisted live-style decisions.
- Force-order history is partial: rows end at 2024-12-01, while candles/aggTrade,
  funding, and OI run into 2026.
- Binance forceOrder stream is censored by design: only the largest liquidation
  order per symbol per 1000ms is pushed. Any burst-intensity model must treat
  force-order count/size as lower-bound proxies, not complete liquidation flow.
- Current Research Lab blueprint still lists `weight_force_order_spike` frozen
  because the original v0.1 table had zero rows (`docs/BLUEPRINT_RESEARCH_LAB.md:124`),
  while `param_registry.py:19` has the later, more accurate reason: historical
  rows exist but are structurally censored.
- No production code change is needed for a diagnostic. The next script can read
  SQLite tables directly, as prior diagnostics did
  (`research_lab/analysis_mfe_accessibility_earliest_knowable_signal_v1.py:33-34`,
  `research_lab/analysis_mfe_accessibility_earliest_knowable_signal_v1.py:1639-1648`).

## 4. External Source / Open-Source Research Synthesis

### Source: Binance USD-M Liquidation Order Streams

- **URL:** https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Liquidation-Order-Streams
- **Core idea:** Binance exposes a force-order stream for symbol liquidations,
  but it is a snapshot stream, not full tick-level liquidation history. The docs
  state that only the largest liquidation order within each 1000ms interval is
  pushed for a symbol.
- **Data required:** force-order event time, side, quantity, price, symbol.
- **Deterministic?** YES for observed snapshots; NO for full hidden liquidation
  intensity.
- **Lookahead risk?** LOW if event time and closed decision bar are respected.
- **btc-bot has required data?** PARTIAL. Live stream and historical table exist,
  but historical coverage/censoring are material issues.
- **Suggests new edge family?** YES.
- **Classification:** useful concept and data-source benchmark, not a strategy.

### Source: Binance USD-M Aggregate Trade Streams

- **URL:** https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams
- **Core idea:** The stream provides market trade information aggregated every
  100ms for fills with the same price and taker side. This is the natural source
  for TFI/CVD and aggressive-flow imbalance.
- **Data required:** trade time, price, quantity, buyer-maker flag.
- **Deterministic?** YES after bucketization.
- **Lookahead risk?** LOW if the bucket is closed before use.
- **btc-bot has required data?** YES. Live aggregation and historical buckets
  already exist.
- **Suggests new edge family?** YES.
- **Classification:** implementation candidate for data plumbing; mechanism must
  still be validated.

### Source: Binance Open Interest Statistics

- **URL:** https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics
- **Core idea:** Public endpoint provides interval OI statistics at periods such
  as 5m, 15m, 1h. The docs note public historical availability limits for recent
  data, so long history depends on prior backfill or alternate datasets.
- **Data required:** timestamped OI, symbol, period.
- **Deterministic?** YES as last-known interval data.
- **Lookahead risk?** MEDIUM if aligned to future interval close by mistake.
- **btc-bot has required data?** YES historically in the research DB; live current
  OI also exists.
- **Suggests new edge family?** YES, as crowding context, not as a standalone
  timing signal.
- **Classification:** useful concept and implementation candidate.

### Source: Binance Funding Rate History

- **URL:** https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History
- **Core idea:** Funding history gives the cost paid by crowded perp positioning
  at discrete funding times. It identifies crowding/carry pressure, but it does
  not time intraday reversal by itself.
- **Data required:** funding time, funding rate, mark price if available.
- **Deterministic?** YES.
- **Lookahead risk?** LOW if last-known funding rate is used.
- **btc-bot has required data?** YES.
- **Suggests new edge family?** PARTIAL. Useful only combined with OI and force
  orders.
- **Classification:** useful concept; not a standalone implementation candidate.

### Source: Cont, Kukanov, Stoikov - The Price Impact of Order Book Events

- **URL:** https://ideas.repec.org/p/arx/papers/1011.6402.html
- **Core idea:** Short-horizon price changes are more tightly related to order
  flow imbalance at the best bid/ask than to raw trade volume. This supports
  studying imbalance and depth, not just candle outcomes.
- **Data required:** best bid/ask depth events, market orders, cancellations.
- **Deterministic?** YES in principle.
- **Lookahead risk?** LOW with event-time data.
- **btc-bot has required data?** PARTIAL/NO. The bot has aggTrade-derived TFI/CVD
  but not full order-book depth and cancellation events.
- **Suggests new edge family?** YES, but the first btc-bot implementation must
  use a reduced taker-flow proxy unless depth history is added later.
- **Classification:** benchmark concept, not directly implementable with current
  data.

### Source: Bookmap Absorption Indicator / Crypto Order Flow Material

- **URLs:** https://bookmap.com/absorption/ and https://bookmap.com/crypto/
- **Core idea:** Absorption is the interaction where aggressive flow trades into
  passive liquidity but price stops extending. The crypto examples explicitly
  combine CVD/volume dots/liquidation indicators with visible liquidity.
- **Data required:** executed aggressive volume, passive liquidity/DOM or iceberg
  proxies, price response.
- **Deterministic?** UNCLEAR in vendor form; can be reduced to a deterministic
  proxy.
- **Lookahead risk?** MEDIUM because visual absorption is easy to label after the
  turn.
- **btc-bot has required data?** PARTIAL. TFI/CVD/force orders exist, but full
  DOM/iceberg data does not.
- **Suggests new edge family?** YES: absorption after stop-run using available
  taker-flow proxies.
- **Classification:** useful concept; vendor/visual implementation is
  discretionary, not a benchmark.

### Source: hgnx/binance-liquidation-tracker

- **URL:** https://github.com/hgnx/binance-liquidation-tracker
- **Core idea:** Small Python project records Binance Futures forced liquidation
  orders in real time and filters by notional/symbol. It demonstrates the same
  raw data source as btc-bot's force-order collector.
- **Data required:** Binance forceOrder WebSocket events.
- **Deterministic?** YES for event collection.
- **Lookahead risk?** LOW for collection, none for strategy because it does not
  define one.
- **btc-bot has required data?** YES/PARTIAL. btc-bot already has a better
  integrated collector and schema.
- **Suggests new edge family?** NO by itself.
- **Classification:** benchmark candidate for ingestion only; not a strategy.

### Source: LiveVolatile Liquidation Cascade Article

- **URL:** https://www.livevolatile.com/blog/crypto-liquidation-cascades-profit-strategy-2026
- **Core idea:** Liquidation cascades are framed as forced selling/buying loops
  that can culminate in capitulation and reversal, with OI, funding, liquidation
  clusters, and volatility as inputs.
- **Data required:** liquidation clusters, OI, funding, volatility, price.
- **Deterministic?** UNCLEAR. Several claims are marketing-style and not
  reproducible from public code.
- **Lookahead risk?** HIGH if "capitulation" is labeled after recovery.
- **btc-bot has required data?** PARTIAL. It has observed force orders, OI,
  funding, ATR, not a full liquidation heatmap.
- **Suggests new edge family?** YES conceptually, but not as authority.
- **Classification:** useful concept with high skepticism; not a benchmark.

### Source: BloFin Funding + Open Interest Signals

- **URL:** https://blofin.com/en/academy/education/funding-and-open-interest-signals
- **Core idea:** Funding is crowding cost, OI is total active exposure, and high
  funding is not an automatic reversal signal. The useful interpretation is
  crowding plus forced repositioning risk, not simple contrarian entry.
- **Data required:** funding, OI, price/volume context.
- **Deterministic?** YES for data; interpretation must be tested.
- **Lookahead risk?** MEDIUM if "crowding unwind" is identified after OI drops.
- **btc-bot has required data?** YES.
- **Suggests new edge family?** YES as a crowding/unwind classifier.
- **Classification:** useful concept, not implementation authority.

## 5. Candidate Mechanisms

### Mechanism: Liquidation Exhaustion Reversal

**Hypothesis:** A force-order burst through a liquidity level followed by
declining same-direction aggressive flow predicts reversal because forced
selling/buying has exhausted available stop-flow.

**Earliest knowable bar:** Detection bar close if the force-order burst and
sweep are both inside the closed 60s/15m window; otherwise `state_known_bar + 1`
after burst decay is confirmed.

**Required data:** Candles, ATR, equal-level sweep, force_orders, TFI, CVD, OI,
funding.

**Expected sample count:** Force-order-burst states had 1,567 post-sweep events
in MFE V1, but the new universe should start from all force-order bursts. Expect
several thousand pre-filter events before quality gates, with coverage only
through 2024-12-01 unless data is extended.

**Likely overlap with trial-00095:** MEDIUM. Trial-00095 has force-order score
but small weight; it is not primarily a liquidation burst strategy.

**How it could fail:** The Binance stream is censored, burst decay is known too
late, or forced flow is continuation rather than exhaustion.

### Mechanism: Absorption After Stop-Run

**Hypothesis:** After a sweep, aggressive taker flow continues in the sweep
direction but price fails to extend; this divergence identifies passive
absorption and predicts reversal earlier than reclaim/mitigation.

**Earliest knowable bar:** Earliest closed 60s or 15m bucket after the sweep
where aggressive flow is extreme and price extension stalls.

**Required data:** aggtrade_buckets 60s/15m, CVD, TFI, candles, ATR, sweep level.

**Expected sample count:** High. MFE V1 produced 13,257 CVD absorption proxy
observations, but they were post-sweep and negative; a new diagnostic must
redefine absorption around the actual stop-run bar and test earlier timing.

**Likely overlap with trial-00095:** HIGH/MEDIUM. Trial-00095 already uses TFI
and CVD divergence; novelty must be proven by overlap and incremental metrics.

**How it could fail:** CVD divergence remains interpretive/noisy, or it is just
trial-00095 direction logic under another name.

### Mechanism: Crowded Unwind

**Hypothesis:** Extreme OI expansion plus one-sided funding plus a liquidation
event predicts a forced unwind and short-horizon mean reversion after crowding
breaks.

**Earliest knowable bar:** `state_known_bar` when OI/funding are already
last-known and a liquidation/force-order burst closes in the current bar.

**Required data:** OI, funding, force_orders, price, ATR, TFI/CVD for direction.

**Expected sample count:** Medium. OI/funding coverage is strong, but combining
with force orders and sweep/cascade filters may reduce events below 300 unless
the force-order universe is broadened beyond sweep events.

**Likely overlap with trial-00095:** LOW/MEDIUM. RegimeEngine uses crowded
leverage, but current SignalEngine is still sweep/reclaim-led.

**How it could fail:** Funding/OI are slow context, not timing; the unwind may
already be complete by the observable liquidation burst.

### Mechanism: Flow-Confirmed Continuation

**Hypothesis:** Some sweeps are not reversals. If sweep direction, TFI, CVD, and
OI expansion align, the correct trade is continuation, not reclaim.

**Earliest knowable bar:** Detection-bar close or next bar after closed flow
bucket confirms direction.

**Required data:** Sweep events, aggtrade_buckets, CVD, OI delta, ATR, forward
returns.

**Expected sample count:** High if all sweeps are used; lower if requiring OI
expansion and CVD alignment.

**Likely overlap with trial-00095:** MEDIUM. Current bot is LONG-dominant and
reclaim-led; continuation/no-reclaim rejected populations are not current
accepted trades.

**How it could fail:** MFE V1 no-reclaim/reject states were negative after
entry timing, so continuation needs genuinely earlier flow evidence, not delayed
no-reclaim labels.

### Mechanism: Volatility Expansion Failure With Flow Exhaustion

**Hypothesis:** ATR/range expansion plus force-order burst and decaying TFI
predicts short-horizon reversion because urgency failed to produce continuation.

**Earliest knowable bar:** Bar close of the expansion/burst state; entry at next
bar open.

**Required data:** Candles, ATR, TFI, force_orders, sweep anchor optional.

**Expected sample count:** Medium/high.

**Likely overlap with trial-00095:** LOW if not requiring reclaim; MEDIUM if
anchored to equal-level sweeps.

**How it could fail:** Volatility expansion failure may be another delayed
confirmation where the reversal already occurred inside the same candle.

## 6. Reverse Engineering Question

Central question:

**At the moment of sweep / liquidation / aggressive flow burst, what flow facts
are knowable before MFE is consumed?**

The diagnostic should not ask whether a liquidation/flow pattern looks tradable.
It should ask whether the decisive flow information is knowable early enough to
trade with positive expectancy after costs.

Required timeline view:

```text
Bar 0: Sweep detected, force-order burst detected
       state: sweep_plus_force_burst_known
       primary entry: Bar 1 open

Bar 1: 60s/15m TFI impulse confirmed, price extension checked
       state: tfi_impulse_or_absorption_known
       primary entry: Bar 2 open

Bar 2: Force-order decay or continuation confirmed
       state: force_decay_or_continuation_known
       primary entry: Bar 3 open

Bar 3: Reclaim/current trial-00095 candidate proxy may be known
       state: trial_00095_candidate_or_reclaim_known
       primary entry: Bar 4 open

Bar 5: Displacement confirmation states from prior diagnostics
       audit only unless explicitly tested as early entry

Bar 8: SMC mitigation/retest states
       already proven too late for this family
```

For every state, compute remaining MFE/MAE and net returns from
`entry_candidate_bar`, not from the original detection bar. Detection-bar
returns remain audit-only, used to expose edge decay and lookahead illusions.

## 7. Possible Minimal Diagnostic

Proposed next diagnostic name:

`ORDER_FLOW_LIQUIDATION_ACCESSIBILITY_V1`

Goal:

For each sweep, force-order burst, and crowding/liquidation event, test whether
early flow states classify reversal versus continuation before the move is
consumed.

Candidate event universe:

- all force-order bursts by 60s/15m notional z-score;
- all equal-level sweeps with any force-order activity in the prior/current/next
  60s window;
- all sweeps with extreme TFI/CVD movement;
- all OI expansion plus force-order burst windows;
- all funding-extreme plus liquidation windows;
- current trial-00095 accepted/reconstructed candidates as benchmark only.

Candidate knowable states:

- `force_order_burst_known`
- `force_order_notional_z_known`
- `force_order_directional_burst_known`
- `force_order_decay_1bar_known`
- `force_order_continuation_1bar_known`
- `tfi_impulse_known`
- `tfi_extreme_reversal_known`
- `tfi_extreme_continuation_known`
- `cvd_price_absorption_known`
- `cvd_price_continuation_known`
- `price_no_extension_with_aggressive_flow_known`
- `oi_expansion_known`
- `oi_drop_after_force_known`
- `funding_extreme_known`
- `funding_oi_crowding_known`
- `crowded_liquidation_unwind_known`
- `sweep_plus_force_burst_known`
- `sweep_plus_absorption_known`
- `sweep_plus_continuation_flow_known`
- `trial_00095_candidate_overlap_known`

Timing discipline:

- `detection_bar`: first bar where event seed exists;
- `state_known_bar`: bar where the flow/crowding state is fully known;
- `entry_candidate_bar`: `state_known_bar + 1` by default;
- `return_start_bar`: same as entry candidate unless the diagnostic explicitly
  models next-open unavailability.

Primary outputs:

- state-by-state median net return after costs;
- PF proxy, win rate, mean/median MFE and MAE;
- MFE consumed before each state;
- time from seed event to state;
- time from state to MFE;
- overlap with trial-00095 accepted/reconstructed candidates;
- force-order coverage and censoring diagnostics;
- deterministic shifted control;
- 4-fold walk-forward summary.

Estimated complexity:

- similar to MFE accessibility V1, but with a broader event universe and stronger
  force-order coverage validation;
- 1-2 weeks implementation if approved, depending on how much rejected/live
  decision reconstruction is included.

## 8. Baselines and Controls

Mandatory baselines:

- **Trial-00095:** PF 4.6625, ER 2.1, 271 trades from WF validation
  (`docs/analysis/WF_VALIDATION_TRIAL_00095_2026-05-08.md:50`,
  `docs/analysis/SWEEP_RECLAIM_SINGULAR_EDGE_ASSESSMENT_2026-05-13.md:12`).
- **Current SignalEngine accepted candidates:** reconstruct via current replay
  where possible; do not rely on sparse `signal_candidates` rows alone.
- **Sweep-only:** prior diagnostics already show post-sweep states were negative,
  but sweep-only remains the relevant anchor.
- **Force-order-burst-only:** new baseline to test whether liquidation data adds
  value without sweep anchoring.
- **TFI/CVD-only:** tests whether the new mechanism is just existing flow logic
  renamed.
- **Rejected populations:** `no_reclaim`, `sweep_too_shallow`,
  `direction_unresolved`, and `confluence_below_min` reconstructed from
  SignalEngine diagnostics if historical feature replay is possible.

Controls:

- deterministic shifted-event control using fixed bar offsets;
- random timestamp control with fixed seed only inside research script, never in
  live path;
- opposite-direction control, such as testing buy-liquidation absorption for
  SHORT when the hypothesis is LONG;
- force-order sparse-period control to prevent pre-2025 data from dominating;
- 4-fold time-based walk-forward minimum.

## 9. Invalidation Criteria

Hard STOP conditions for any implementation:

- No state has positive median net expectancy after realistic costs.
- Best state PF proxy is below 1.2 after costs.
- Best state win rate is `<= 51%`.
- Apparent edge exists only from `detection_bar`, not from
  `entry_candidate_bar`.
- Best state does not beat deterministic shifted control.
- Best state does not beat force-order-burst-only and sweep-only baselines.
- Best state is more than 90% overlapping with trial-00095 entries and does not
  materially improve timing or net expectancy.
- Best state sample is below 300 events.
- Force-order coverage is too incomplete: less than 50% of eligible event periods
  have force-order data, or the best result exists only before/after the
  available force-order window.
- Timestamp alignment is invalid: flow samples are not knowable at the claimed
  `state_known_bar`.
- CVD/TFI state arrives too late: median `k > 5` bars and net expectancy is not
  positive.
- MFE consumed before state is `>= 70%`.
- Edge works in fewer than 2 of 4 walk-forward folds.
- Slippage/funding/fees remove the edge.
- Mechanism requires full order-book depth or liquidation heatmaps not present in
  current btc-bot data, unless the result is explicitly classified as a data-gap
  recommendation rather than a strategy signal.
- Mechanism cannot be expressed deterministically from timestamped data.

Pass threshold for opening a later strategy-family diagnostic:

- sample `>= 300` events;
- median net return after costs `> 0`;
- PF proxy `>= 1.2`;
- win rate `> 51%`;
- positive in at least 2 of 4 folds;
- overlap with trial-00095 below 90%, or a clear incremental timing/quality
  improvement if overlap is high;
- MFE consumed before state `< 70%`;
- data coverage and timestamp checks pass.

## 10. What To Cut / What To Preserve

If order-flow/liquidation research shows promise:

Preserved:

- deterministic pipeline: MarketSnapshot -> Features -> Regime -> SignalEngine
  -> Governance -> Risk -> Execution;
- equal-level sweep as one event anchor, not the only anchor;
- FeatureEngine's current funding/OI/CVD/TFI/force-order facts as baseline
  primitives;
- Research Lab isolation and approval-gated promotion;
- trial-00095 PAPER validation as active benchmark.

Replaced:

- any future attempt to expand SMC price-action confirmations as primary entry;
- naive force-order spike scoring if a richer burst/decay/absorption state proves
  materially better;
- static confluence-only treatment of flow if flow state becomes a first-class
  classifier after separate approval.

Moved to metadata:

- regime/session cuts unless a new audited diagnostic proves timing-correct
  incremental value;
- funding alone;
- CVD divergence alone if absorption state only works with price/no-extension
  context.

Removed:

- no current production component should be removed in this planning milestone;
- future removal would require a separate audited implementation plan.

Instrumented more deeply:

- force-order burst notional, direction, decay, and coverage/censoring metadata;
- per-candidate flow state timeline;
- rejected decision population in historical replay;
- event overlap with trial-00095;
- earliest knowable bar and MFE consumed for any proposed flow state.

Trial-00095 is the benchmark, not religion. If an order-flow family later beats
trial-00095 with ER > 2.5, PF > 5.0, cost-aware walk-forward validation, and
acceptable frequency, it is a legitimate replacement candidate. If it fails,
trial-00095 remains the validated strategy.

## 11. Recommended Next Step

**PLAN `ORDER_FLOW_LIQUIDATION_ACCESSIBILITY_V1`: full diagnostic per Section 7.**

The repo has enough historical aggTrade/OI/funding data and partial force-order
data to plan the diagnostic now, while the force-order coverage gap can be a
hard invalidation/data-quality gate inside the plan. Expected outcome is not a
strategy, but a decision on whether early liquidation/order-flow states contain
any timing-correct edge after costs. If this recommendation is wrong, the most
likely failure mode is force-order censoring/coverage proving too severe, in
which case the diagnostic should stop with `INCONCLUSIVE_DATA_GAP` or
`STOP_ORDER_FLOW_RESEARCH`.

## Appendix A: Repo Inspection References

- Core architecture: `docs/BLUEPRINT_V1.md:29-40`, `docs/BLUEPRINT_V1.md:146-166`.
- Research Lab boundary: `docs/BLUEPRINT_RESEARCH_LAB.md:3-31`,
  `docs/BLUEPRINT_RESEARCH_LAB.md:195-216`.
- MarketSnapshot flow fields: `core/models.py:90-124`.
- FeatureEngine flow/funding/OI computation: `core/feature_engine.py:329-356`.
- FeatureEngine OI/CVD/force helpers: `core/feature_engine.py:437-585`.
- Signal diagnostics/rejections: `core/signal_engine.py:71-120`.
- Signal direction and confluence: `core/signal_engine.py:218-293`.
- Regime crowding/post-liquidation: `core/regime_engine.py:49-61`.
- Storage tables: `storage/schema.sql:16-73`,
  `storage/schema.sql:204-221`, `storage/schema.sql:223-267`.
- Runtime snapshot persistence: `storage/repositories.py:49-97`.
- Decision/feature persistence: `storage/repositories.py:111`,
  `storage/repositories.py:370`, `storage/state_store.py:900-988`.
- Replay flow fields: `backtest/replay_loader.py:111-151`,
  `backtest/replay_loader.py:201-292`, `backtest/replay_loader.py:346-379`.
- Live flow ingestion: `data/websocket_client.py:134-139`,
  `data/websocket_client.py:220-239`, `data/market_data.py:119-188`.
- Force-order collector: `scripts/server/run_force_order_collector.py:33-34`,
  `scripts/server/run_force_order_collector.py:267-300`.
- Trial-00095 settings: `settings.json:4-38`.
- Force-order registry caveat: `research_lab/param_registry.py:19`.
