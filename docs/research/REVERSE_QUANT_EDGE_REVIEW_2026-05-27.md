# Reverse Quant Edge Review

**Date:** 2026-05-27  
**Scope:** independent reverse quant engineering review  
**Production impact:** none  
**Implementation status:** not approved, not started  

## 1. Executive Verdict

If I were designing btc-bot's edge from scratch today, I would choose:

**OPEN ONE MORE meta-diagnostic before deciding.**

More specifically: run one MFE-accessibility / earliest-knowable-signal study,
then decide whether to keep the current sweep/reclaim edge as the primary
architecture or pivot toward order-flow/liquidation microstructure.

I would not rebuild the bot around classical SMC. The two completed studies
were not broad enough to exhaust every source idea, but they were strong enough
to reject two natural interpretations:

- isolated pivot/wick/close/reclaim taxonomy;
- 15m SMC confirmation sequence ending in mitigation/retest entry.

The source-space is not fully exhausted because the failed SMC sequence
explicitly showed that the move existed before entry. That means the remaining
question is not "does SMC exist?" It is "when did the exploitable move become
knowable?" If no deterministic fact appears before most MFE is consumed, the
open-source SMC thread is effectively exhausted for this bot.

Trial-00095 is the current benchmark, not a religion.

What I would keep from trial-00095:

- equal-level liquidity sweep as a useful event anchor;
- deep sweep quality as a real but imperfect signal;
- TFI/CVD/funding/confluence as a compact multi-factor scoring surface;
- strict PAPER/live validation discipline.

What I would challenge:

- the assumption that the first production candidate is the earliest useful
  bar;
- the absence of a systematic rejected-population replay in the legacy
  `BacktestRunner`;
- the static bar-level fill model for any future zone/limit-order research;
- treating SMC price-action confirmation as more valuable than flow-confirmed
  impulse timing.

Hard answer: I would **keep the liquidity idea but abandon SMC-style
confirmation as the next strategy path**. The best next research object is not
CHOCH/FVG/OB. It is the time-accessibility curve of MFE after a sweep and the
earliest facts available before that curve decays.

## 2. What The Two Failed Attempts Really Proved

### A. What V1 Taxonomy Invalidated

`SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1` invalidated the claim that a
pivot/wick/close/reclaim taxonomy alone improves the edge.

It tested:

- confirmed pivots and active liquidity levels;
- equal touch versus strict wick cross;
- wick crossing liquidity versus close-based BoS;
- immediate close reclaim;
- delayed close reclaim;
- true breakout / no reclaim within a window;
- `detection_bar` versus `label_available_bar`.

The decisive result was timing. In
`docs/analysis/SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27.md`,
delayed reclaim looked strong from detection (`0.001189` 5-bar median signed
return, `76.07%` win rate) but collapsed from the label-available bar
(`0.000054`, `50.96%`). True breakout moved from apparently strong
(`0.001028`) to negative (`-0.000268`) when measured from the bar where the
label was knowable.

That invalidates delayed labels as direct live inputs. It does not prove that
liquidity sweeps have no value.

### B. What SMC Sequence Invalidated

`SMC_SEQUENCE_EDGE_FEASIBILITY_V1` invalidated a specific operational version
of SMC:

`liquidity sweep -> displacement -> structure shift proxy -> FVG/imbalance -> mitigation/retest -> entry_candidate_bar`

The implementation preserved timing discipline:

- `entry_candidate_bar = mitigation_bar + 1`;
- primary outcomes from entry, not original sweep detection;
- deterministic control cohort;
- MFE measured before entry and after entry.

The result in
`docs/analysis/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md` was not "no
movement." It was "movement too early." Full-sequence events had:

- `1,271` events;
- median `8` bars from sweep detection to entry candidate;
- detection 5-bar median return `0.004348`;
- entry 5-bar median return `0.000558`;
- entry 5-bar net median after 0.10% round-trip cost `-0.000442`;
- entry 5-bar PF proxy `1.061`, far below the trial-00095 threshold;
- median MFE before entry `0.011565`;
- post-entry 5-bar MFE `0.004916`.

This invalidates mitigation-confirmed SMC entry on BTCUSDT 15m as tested. It
does not invalidate early impulse or flow-confirmed sweep models.

### C. What Neither Attempt Tested

Neither attempt tested:

- order book imbalance before and during the sweep;
- resting liquidity wall removal;
- liquidation cascade exhaustion using real liquidation/force-order intensity;
- CVD absorption at the sweep bar or displacement bar as a primary classifier;
- lower-timeframe execution after a 15m context signal;
- pre-sweep liquidity pool quality based on HTF overlap;
- resting limit orders placed after FVG/OB creation but before mitigation;
- fill probability, non-fill, and adverse-selection modeling for zone entries;
- an MFE accessibility curve by phase.

### D. Forbidden Conclusions

Do not conclude:

- "SMC as a whole is false."
- "Liquidity sweeps have no edge."
- "Detection-bar returns are valid evidence."
- "More CHOCH/FVG/OB labels will rescue the failed sequence."
- "Trial-00095 must never be challenged."
- "Trial-00095 is weak because SMC failed."

The correct conclusion is narrower: the tested SMC confirmations were too late,
and isolated taxonomy did not add explanatory or tradable value.

## 3. Source Coverage Gap Analysis

| Idea / component | Source origin | Tested by V1 taxonomy? | Tested by SMC sequence? | Fully exhausted? | Could still matter? | Why / why not |
| ---------------- | ------------- | ---------------------- | ----------------------- | ---------------- | ------------------- | ------------- |
| Wick sweep | LuxAlgo, Makuchaku/eFe, ICT sweep sources, current bot | Yes | Yes, as anchor | Mostly | Yes | Current edge still uses it; V1 says raw wick-cross taxonomy is not enough. |
| Close BoS | Makuchaku/eFe, smartmoneyconcepts | Yes | Simple structure proxy | Partially | Low alone, medium in sequence | Standalone close BoS failed; full CHOCH semantics not fully tested. |
| Delayed reclaim | LuxAlgo, sweep/reclaim indicators | Yes | Indirectly | Yes enough | Low | Label-available returns collapsed; do not revisit as direct signal. |
| True breakout | LuxAlgo alternate scenario, BoS sources | Yes | Indirectly | Yes enough | Low | Became negative when label was knowable. |
| Sweep area / reaction zone | LuxAlgo | Partially | Mitigation zone proxy | No | Medium | Tested as FVG mitigation after confirmation, not as pre-placed reaction-zone order. |
| Displacement | ICT/SMC, Makuchaku/eFe, PyIndicators | No | Yes | Partially | High | Sequence showed movement after sweep; displacement may be the tradable phase. |
| CHOCH/MSS | smartmoneyconcepts, PyIndicators, SMC repos | No | Local structure break proxy only | No | Medium/low | Could help label reversal, but likely late unless paired with early entry. |
| FVG | smartmoneyconcepts, PyIndicators, FVG articles | No | Yes, simple 3-candle gap | Partially | Medium | FVG creation may matter; mitigation-confirmed entry failed. |
| Mitigation | LuxAlgo, SMC/FVG/OB sources | No | Yes | Mostly for 15m next-bar entry | Low | Main failure point; late-entry problem is severe. |
| Order block | Makuchaku/eFe, smartmoneyconcepts, PyIndicators | No | No | No | Medium but risky | Could support pre-placed zone entries, but likely same fill/timing problem. |
| Rejection / breaker / RJB | Makuchaku/eFe, PyIndicators | No | No | No | Low/medium | Mostly a zone-state variant; needs fill realism before strategy use. |
| Recursive fractals | PyIndicators, swing hierarchy sources | Confirmed pivots only | Local swings only | No | Medium for level quality | Useful as pre-sweep liquidity quality, not as post-sweep confirmation. |
| HTF liquidity | smartmoneyconcepts previous high/low, ICT sources | No | No | No | Medium | Known before sweep, so timing is better than delayed confirmation. |
| Premium/discount | ICT/SMC sources | No | No | No | Low/medium | May over-filter; must be tested as pre-known location metadata only. |
| Killzone/session | smartmoneyconcepts sessions, ICT sources | Metadata/history only | Metadata only | Mostly | Low | Prior context/session specialization degraded edge; do not use as rescue. |
| Order flow / CVD | open-source order-flow repos, current bot | Partially in current edge | Metadata only in SMC | No | High | This is the strongest remaining path because it can be known early. |
| Liquidation data | WickHunter, Bookmap-style examples, current force orders | Partial force-order feature | Metadata only | No | High | Force orders can identify cascade exhaustion earlier than FVG mitigation. |
| OI/funding unwind | crypto derivatives research practice, current bot | Current regime/confluence only | Metadata only | No | Medium/high | Already present but not studied as primary post-sweep classifier. |
| Early impulse entry | Reverse inference from SMC result | No | No, sequence waited for mitigation | No | High | The failed SMC result points directly here. |
| Continuation vs reversal split | LuxAlgo, SMC, order-flow | Partial direction inference | No | No | High | Sweep can precede either reversal or continuation; current logic may blur this. |
| MFE accessibility | Quant best practice, V1/SMC audits | No | Measured globally | No | Very high | This is the decisive diagnostic before any new strategy family. |

## 4. Reverse Engineering The Failure Point

The actual failure is:

**Most favorable excursion occurs before realistic SMC entry.**

That reframes the problem. The question is not whether a pattern can be drawn
after the fact. The question is whether the portion of the move that survives
after a realistic signal is large enough to pay fees, slippage, funding, and
drawdown.

### Where The Edge Appears

The SMC sequence result says the edge appears between:

1. sweep detection;
2. displacement;
3. possibly structure shift / FVG creation.

The `0.004348` detection-bar median signed return for full-sequence events is
not tradable as a full-sequence signal, but it is a locator. It tells us the
market did move in the eventual sequence direction. The sequence classifier
found real movement; it just found it too late.

### Where The Edge Disappears

It disappears by the mitigation entry:

- median `8` bars from sweep to entry on 15m means roughly 2 hours;
- median MFE before entry is more than 2x post-entry MFE;
- entry net median is negative after 0.10% round-trip cost.

For BTC perpetual futures, a 15m SMC retest model is operationally late. The
visual pattern may be correct while the trade is dead.

### What Was Knowable Before MFE Was Consumed

From the repo and research scripts, the facts knowable before mitigation are:

- sweep detected by `core/feature_engine.py:156`;
- equal-level cluster from `core/feature_engine.py:125`;
- sweep depth and side from `core/feature_engine.py:179-221`;
- 60s TFI and force-order rate from `core/feature_engine.py:352-356`;
- CVD divergence from `core/feature_engine.py:544-571`;
- funding/OI crowding from `core/feature_engine.py:329-337`;
- SignalEngine direction and confluence from `core/signal_engine.py:218-293`.

The facts not currently represented as first-class live features are:

- displacement immediately after sweep;
- MFE remaining after each post-sweep phase;
- order-book liquidity wall removal;
- liquidation intensity and decay beyond simple force-order spike/decreasing;
- execution delay and fill probability for early entries.

### The Tradable Moment Is Probably Earlier Than SMC Confirmation

The likely tradable moment is closer to:

- sweep bar close;
- first displacement bar close;
- flow absorption / exhaustion around the sweep;
- liquidation cascade exhaustion;
- possibly FVG creation close, if an order is placed before mitigation.

It is probably not:

- delayed reclaim label;
- true-breakout/no-reclaim label;
- mitigation/retest confirmation;
- next bar after mitigation.

### Did Mitigation Fail Because SMC Is Wrong?

Not necessarily. It failed because the tested SMC entry is late on BTCUSDT
15m. SMC may still describe an after-the-fact path:

`sweep -> impulse -> imbalance -> return`

But description is not execution. A visually valid mitigation is irrelevant if
most favorable excursion occurred before the bot can enter.

### Would Lower Timeframe Entry Solve It?

Maybe, but this is not free.

Potential benefit:

- 1m/5m execution could enter after displacement or zone creation before the
  15m mitigation bar closes.

Risks:

- more noise;
- worse false positives;
- stronger fill-order ambiguity inside 15m candles;
- higher sensitivity to fees/slippage;
- need for tick/order-book data to avoid optimistic fills.

Lower timeframe should only be studied after the MFE accessibility diagnostic
shows that a realistic early state exists.

### Is Trial-00095 Already Catching The Accessible Part?

Possibly. Trial-00095 uses same-bar equal-level sweep/reclaim with TFI/CVD,
funding, depth, and trend confluence. It is operationally closer to the
accessible part of the move than SMC mitigation. The current production edge
may work exactly because it avoids waiting for aesthetic confirmation.

But the repo also shows a gap: `BacktestRunner` accepted trades are recorded,
while older backtest rejected populations are not persisted with full
`decision_outcomes`. Live does persist rejected candidates via
`orchestrator.py:575-587` and `storage/schema.sql:204-221`. That means the
best path is to learn from rejected and near-miss populations, not invent more
visual structure.

### Does The Rejection Pipeline Discard Earliest Useful Signals?

Potentially yes, and the likely layer is `SignalEngine.diagnose`, not
Governance/Risk.

The main gates are:

- `no_sweep`;
- `sweep_too_shallow`;
- `no_reclaim`;
- `direction_unresolved`;
- `confluence_below_min`.

Those are in `core/signal_engine.py:83-120`. A future diagnostic should ask:

- among `sweep_too_shallow`, did flow/force-order/OI identify a subset with
  accessible MFE?
- among `no_reclaim`, did displacement/TFI identify continuation before the
  reclaim gate?
- among `direction_unresolved`, did CVD/OI/force-order timing resolve the move
  earlier than candle structure?

This is not an argument to loosen gates live. It is an argument to study the
reject population with realistic timing.

## 5. Best-Practice Comparison

What btc-bot already does well:

- deterministic core pipeline;
- feature snapshots and decision outcomes in live/PAPER;
- explicit config hash and schema lineage;
- walk-forward validation for trial-00095;
- control cohorts in V1/SMC diagnostics;
- label-available and entry-candidate timing discipline;
- fees/funding/slippage included in core backtest and PAPER accounting;
- no LLM in live decision path.

What a strong quant research lab would add or tighten:

- rejected-population persistence in replay/backtest, not only live;
- event-time studies around every rejection reason;
- MFE/MAE timing curves, not only aggregate MFE/MAE;
- purged/embargoed validation when features have overlapping horizons;
- parameter robustness surfaces around edge families, not only best trials;
- fill probability and non-fill modeling for limit/zone entries;
- order book / liquidation data if the hypothesis is microstructure;
- latency-aware entry: decision close time, exchange time, snapshot build
  latency, order route latency;
- feature ablation/importance on accepted and rejected populations separately;
- conservative intrabar path assumptions for any 1m/5m execution split.

What they would not do:

- copy TradingView/Pine logic;
- accept detection-bar returns for delayed sequences;
- stack CHOCH/FVG/OB labels until something passes;
- use session/regime filters as post-hoc rescue after prior context tests
  failed;
- claim a zone entry works without fill-order assumptions.

Open-source comparison:

- `joshyattridge/smart-money-concepts` is useful as deterministic indicator
  vocabulary: FVG, swing highs/lows, BOS/CHOCH, OB, liquidity, previous
  high/low, sessions. It is a benchmark candidate for definitions, not an edge
  proof. Source: https://github.com/joshyattridge/smart-money-concepts
- `coding-kitties/PyIndicators` broadens the deterministic vocabulary:
  FVG, order blocks, breaker blocks, mitigation blocks, rejection blocks,
  OTE, CHOCH/BOS, liquidity sweeps, liquidity pools. Useful concept source,
  but not production dependency. Source: https://github.com/coding-kitties/PyIndicators
- `crypto-liquidity-ai-trading-bot` points away from candle-only SMC and
  toward order-book imbalance, liquidity walls, gaps, and sweep monitoring. It
  reports modest backtest claims (PF 1.42, DD -12.4%) with explicit limitations;
  useful concept/benchmark candidate, not trustworthy evidence. Source:
  https://github.com/aitradingbotspro/crypto-liquidity-ai-trading-bot
- Bookmap BTCUSDT material frames stop runs, absorption, and exhaustion as
  order-flow events, not candle labels. Useful concept source for
  microstructure research, discretionary/visual if used without data. Source:
  https://bookmap.com/content/instruments/btcusdt
- `backtesting.py` highlights a best-practice issue: when stop and limit are
  hit in the same bar, conservative ordering matters. This is directly relevant
  to future FVG/OB limit-entry simulation. Source:
  https://github.com/kernc/backtesting.py/blob/master/backtesting/backtesting.py

The best-practice gap is clear: btc-bot is strong on pipeline determinism and
auditability, but the next edge question requires more event-accessibility and
microstructure timing work than another candle-pattern detector.

## 6. Are We Overfitting To Trial-00095?

Trial-00095 is still the best validated baseline.

Evidence:

- WF validation reported PF `4.6625`, max drawdown `6.51%`, and `271` trades
  in `docs/analysis/WF_VALIDATION_TRIAL_00095_2026-05-08.md`;
- singular edge assessment described trial-00095 as the only viable 15m
  sweep/reclaim family after multiple failed context/setup attempts;
- conditional edge analysis found deeper accepted sweeps produced better ER
  by quartile, but also warned that the threshold boundary may be overfit and
  rejected backtest populations were unavailable.

That means trial-00095 should be the benchmark, not the design prison.

What evidence would justify challenging it:

- entry-timed, cost-adjusted expectancy that beats trial-00095 on comparable
  OOS / walk-forward data;
- a diagnostic that explains a real failure mode of trial-00095, such as
  rejected sweeps with high accessible MFE;
- robust performance across folds with enough trades and realistic fill
  modeling;
- evidence that live/PAPER distribution shifted away from trial-00095's
  historical qualifying population.

What evidence does not justify challenging it:

- visual SMC screenshots;
- detection-bar returns from delayed labels;
- a small cherry-picked regime/session subset;
- gross returns before costs;
- a model with lower PF/ER but more conceptual elegance;
- a single GitHub repo or TradingView strategy claim.

Should every new idea beat trial-00095 directly? Ultimately yes, but not as the
first diagnostic step. Some research should first explain a failure mode:

- where does MFE occur?
- what was knowable?
- which rejected bucket had missed opportunity?
- did execution timing kill the move?

Only after that should it be forced to beat trial-00095 as a strategy.

ER/PF are necessary but not sufficient. Future comparisons also need:

- event frequency and time-to-50-trades;
- net returns after fees/slippage/funding;
- fill probability;
- MFE-before-entry / MFE-after-entry;
- latency sensitivity;
- opportunity cost versus simply running trial-00095.

## 7. Identify The Decisive Problem Moment

The deciding moment is:

**after sweep detection and before delayed confirmation.**

Pipeline location:

- `core/feature_engine.py:156-223` detects sweep/reclaim from the latest 15m
  candle and equal levels;
- `core/signal_engine.py:83-120` rejects or accepts based on sweep depth,
  reclaim, direction, regime direction whitelist, and confluence;
- delayed SMC research waited through displacement, structure, FVG, mitigation,
  and next-bar entry in `research_lab/analysis_smc_sequence_edge_feasibility_v1.py:575-628`.

The SMC failure shows tradability decays while waiting. The current bot's live
pipeline can act at the sweep/reclaim bar, but may discard useful early states:

- `sweep_too_shallow` may discard shallow but flow-confirmed liquidation
  exhaustion;
- `no_reclaim` may discard continuation opportunities;
- `direction_unresolved` may discard cases where order flow resolves direction
  before candle structure;
- static confluence may underweight time-local force-order/CVD behavior.

Governance and Risk are not the primary suspects:

- Governance duplicate-level veto at `core/governance.py:66-67` can remove
  repeats, but current production stats show candidates are rarely reaching
  governance;
- Risk min RR at `core/risk_engine.py:57` matters after candidates exist, but
  the SMC failures happened before a candidate became tradable;
- execution fill realism matters for future limit/zone ideas, but not for the
  conclusion that mitigation entry was late.

Backtest/PAPER difference to watch:

- live/PAPER records decision outcomes and feature snapshots via
  `orchestrator.py:566-587` and `storage/schema.sql:204-277`;
- standard `BacktestRunner` reuses core engines but does not persist the full
  rejected population in the same way, which limits fair distribution-shift and
  near-miss analysis;
- `backtest/fill_model.py:51-91` uses deterministic static slippage/fees, so
  future order-book/limit-entry work needs stronger execution modeling.

The edge either becomes tradable at the sweep/displacement/flow phase or dies
by the mitigation phase.

## 8. New Research Directions

### 1. MFE Accessibility / Earliest-Knowable Signal Diagnostic

- Hypothesis: The decisive edge question is whether any deterministic fact
  appears before most favorable excursion is consumed.
- Differs from failed attempts: it is not a strategy and does not require SMC
  sequence success; it maps opportunity decay by phase.
- Earliest realistic signal bar: each phase gets its own timestamp: sweep,
  reclaim, first displacement, TFI/CVD threshold, force-order spike,
  structure break, FVG creation, mitigation.
- Required data: candles, feature snapshots, aggtrade buckets, force orders,
  OI/funding, decision outcomes; ideally replay data with rejected
  populations.
- Complexity: medium.
- Lookahead risk: medium; every fact must be timestamped by availability.
- Expected sample size: high if built around all sweeps/rejections.
- Pass/fail criteria: pass only if a pre-entry fact retains positive net
  expectancy and enough MFE remains after that fact; fail if MFE is mostly gone
  before any knowable fact.
- Why it might beat trial-00095: it can discover whether trial-00095 enters too
  late, too early, or discards a useful rejected bucket.
- Why it might fail: it may prove the accessible edge is already exactly what
  trial-00095 captures.

### 2. Early Displacement / Impulse Entry After Sweep

- Hypothesis: the tradable part of SMC is the impulse after sweep, not the
  mitigation.
- Differs from failed attempts: enters at first displacement close or next open,
  not after FVG mitigation.
- Earliest realistic signal bar: displacement bar close after confirmed sweep.
- Required data: 15m candles, ATR, TFI/CVD/force-order metadata, costs.
- Complexity: medium.
- Lookahead risk: moderate; displacement must be known only after the candle
  closes.
- Expected sample size: medium/high, higher than full SMC mitigation.
- Pass/fail criteria: entry-timed net median > trial-00095 proxy, PF/ER robust,
  no collapse versus controls, stable folds.
- Why it might beat trial-00095: it targets the exact phase where SMC showed
  MFE existed.
- Why it might fail: impulse entries chase exhaustion and may suffer adverse
  selection after costs.

### 3. Order-Flow Absorption / Continuation Split

- Hypothesis: sweep outcomes depend on whether aggressive flow is absorbed or
  continues; CVD/TFI/force orders can resolve direction earlier than candle
  structure.
- Differs from failed attempts: classifies sweep using flow at or immediately
  after the sweep, not delayed price-action labels.
- Earliest realistic signal bar: sweep bar close or first closed 60s bucket
  after sweep, depending on data alignment.
- Required data: `aggtrade_buckets`, CVD history, force orders, OI/funding,
  candles.
- Complexity: medium/high.
- Lookahead risk: high if 60s buckets are not aligned to closed exchange
  timestamps.
- Expected sample size: high among all sweep and near-miss events.
- Pass/fail criteria: must separate reversal versus continuation with
  entry-timed positive net expectancy and novelty versus existing TFI.
- Why it might beat trial-00095: it could prevent entering sweeps where flow is
  still one-sided and add continuation cases that current reclaim logic misses.
- Why it might fail: current trial-00095 may already encode the useful part via
  TFI/CVD weights.

### 4. Liquidation Unwind / Crowding Reversal

- Hypothesis: the strongest post-sweep reversals occur after liquidation
  exhaustion: force-order spike, TFI extreme, OI/funding crowding, then flow
  decay.
- Differs from failed attempts: uses derivatives microstructure as primary
  evidence, not SMC geometry.
- Earliest realistic signal bar: force-order spike/decay observation around
  sweep; possibly one 60s bucket after event.
- Required data: force orders, OI, funding, aggtrades, candles.
- Complexity: high.
- Lookahead risk: medium/high; decay confirmation can become delayed and must
  be timed.
- Expected sample size: lower than all sweeps but likely higher quality.
- Pass/fail criteria: net PF/ER above trial-00095 or a clearly orthogonal edge
  with stable OOS; MFE after signal must exceed MFE before signal.
- Why it might beat trial-00095: it attacks the actual crypto futures
  mechanism behind stop runs and liquidation cascades.
- Why it might fail: force-order data may be sparse, delayed, or already
  exhausted before detection.

### 5. Liquidity Pool Quality Scoring

- Hypothesis: the accessible edge is not post-sweep confirmation; it is
  choosing better pre-sweep liquidity pools.
- Differs from failed attempts: classifies levels before they are swept, so no
  delayed-label timing problem.
- Earliest realistic signal bar: before sweep, once level quality is known.
- Required data: 15m/1h/4h candles, equal-level clusters, level age, touches,
  HTF previous highs/lows, distance to level, volatility.
- Complexity: medium.
- Lookahead risk: medium; HTF pivots and recursive swings must be confirmed
  before use.
- Expected sample size: high for levels, medium for swept qualified levels.
- Pass/fail criteria: selected pools must improve sweep/reclaim expectancy
  without reducing frequency below viability; must beat raw equal-level
  selection and trial-00095 accepted baseline in OOS.
- Why it might beat trial-00095: it improves the input population rather than
  waiting for late confirmation.
- Why it might fail: quality scoring may become disguised overfit filtering.

Rejected directions for now:

- full CHOCH/FVG/OB taxonomy expansion;
- session/killzone rescue;
- premium/discount filter as a standalone gate;
- lower-timeframe execution split before MFE accessibility is mapped;
- broad open-source strategy shopping without a failure-mode hypothesis.

## 9. What To Cut If Redesigned From Scratch

### Keep

- deterministic pipeline shape;
- equal-level sweep anchor;
- depth and reclaim diagnostics;
- TFI/CVD/force-order/funding/OI feature availability;
- feature snapshots and decision outcomes;
- governance/risk authority boundaries;
- PAPER-first validation.

### Delete Or Stop Expanding

- SMC mitigation-confirmed entry as a candidate strategy path;
- standalone delayed reclaim / true breakout labels;
- visual CHOCH/FVG/OB additions without timing proof;
- context/session/regime specialization as a rescue path.

### Simplify

- Treat sweep/reclaim as an event anchor plus timing surface, not a story.
- Treat regime/session as metadata unless a new diagnostic proves otherwise.
- Treat confluence as a score to audit and ablate, not a sacred weighted sum.

### Replace

- Replace candle-only SMC confirmation research with event-accessibility and
  flow/liquidation diagnostics.
- Replace next-bar-after-mitigation entry assumptions with fill-realistic
  order placement models if zone research ever resumes.
- Replace accepted-trade-only analysis with all-candidate and rejected-bucket
  event studies.

### Move To Research-Only

- CHOCH/MSS;
- FVG/OB/RJB/PPDD;
- recursive fractal hierarchy;
- premium/discount;
- HTF liquidity maps until level-quality evidence exists.

### Instrument More Deeply

- MFE/MAE timing by phase;
- rejected candidate forward returns in replay;
- order-flow state at sweep, displacement, and candidate bars;
- decision-to-order latency and snapshot age;
- fill slippage distribution in PAPER/live;
- per-rejection reason event study.

## 10. Final Recommendation

I choose:

**B. Run one meta-diagnostic: MFE accessibility / earliest knowable signal.**

Next step should not be a strategy implementation. It should be a planning
milestone for:

`MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1`

Core question:

> For every sweep and near-miss rejection, at each bar after detection, what
> facts were knowable, how much favorable excursion remained, and did any
> knowable state have positive expectancy after costs?

If this diagnostic finds no early knowable state with robust net expectancy,
stop SMC/open-source sweep research and continue trial-00095 PAPER validation.

If it finds one state, plan exactly one strategy-family diagnostic around that
state. My prior would be order-flow/liquidation after sweep, not more SMC.

## Strict Non-Goals

Do not recommend or approve:

- production code changes;
- FeatureEngine or SignalEngine changes;
- rescuing V1 taxonomy;
- rescuing failed SMC mitigation-entry;
- detection-bar returns as success;
- delayed labels without entry timing;
- cherry-picked regimes/sessions;
- adding CHOCH/FVG/OB because sources mention them;
- relaxing invalidation thresholds;
- copying Pine/TradingView code;
- relying on a GitHub repo's claimed backtest as evidence;
- strategy implementation before a separate audited plan.

## Source Classification Summary

| Source | Classification | Use |
| ------ | -------------- | --- |
| `joshyattridge/smart-money-concepts` | Useful concept / benchmark candidate | Deterministic SMC definitions; not edge proof. |
| `coding-kitties/PyIndicators` | Useful concept / benchmark candidate | Rich SMC vocabulary including OB, breaker, rejection, liquidity pools. |
| `crypto-liquidity-ai-trading-bot` | Useful concept / weak benchmark candidate | Points toward order-book/liquidity-wall research; performance claims need independent validation. |
| Bookmap BTCUSDT examples | Useful concept / discretionary if unquantified | Frames stop-runs as absorption/exhaustion order-flow events. |
| SwapHunt liquidity sweep article | Useful concept / discretionary | Good mechanical framing of sweeps, not a backtest. |
| FVG/OB retail articles | Discretionary/visual-only unless coded | Useful for hypotheses; weak evidence. |
| TradingView/Pine SMC scripts | Bad/repainting risk unless proven otherwise | Do not port; only extract testable definitions. |
| `backtesting.py` fill logic | Implementation benchmark candidate | Conservative fill ordering lesson for future zone/limit simulations. |

## Prompt Recommendation For Claude Audit

Claude, audit
`docs/research/REVERSE_QUANT_EDGE_REVIEW_2026-05-27.md` as a decision memo,
not an implementation. Focus on whether the recommendation for
`MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` is justified by the V1/SMC
failures, repo evidence, and external source review. Specifically challenge:

- whether this memo overstates the remaining value of SMC/open-source sources;
- whether the proposed meta-diagnostic is truly different from the failed
  attempts;
- whether trial-00095 is being treated correctly as benchmark, not religion;
- whether order-flow/liquidation is a justified future family or just another
  speculative rescue;
- whether any proposed next step risks production contamination or lookahead
  bias.

