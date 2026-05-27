# SMC Source Coverage And Reverse Engineering Review

**Date:** 2026-05-27  
**Scope:** audit / decision memo only  
**Production impact:** none  

## 1. Executive Verdict

V1 taxonomy plus `SMC_SEQUENCE_EDGE_FEASIBILITY_V1` did not fully exploit every
idea in the external Makuchaku/LuxAlgo/GitHub/ICT source space. They did,
however, test the two most obvious interpretations:

- isolated sweep/reclaim event classification;
- a minimal sequential workflow from sweep to displacement, structure proxy,
  FVG, mitigation, and realistic `entry_candidate_bar`.

Those two interpretations failed for different reasons. V1 taxonomy failed
because separated labels did not create useful expectancy once delayed labels
were measured from the bar where they were knowable. SMC sequence failed because
the pattern did contain signal, but realistic mitigation entry arrived too late:
median MFE before entry was `0.011565`, while post-entry 5-bar MFE was only
`0.004916`.

Ideas tested:

- high/low liquidity cross versus close-based BoS;
- immediate and delayed reclaim;
- true breakout / no reclaim;
- displacement after sweep;
- simple structure shift proxy;
- simple three-candle FVG;
- mitigation/retest entry at `mitigation_bar + 1`;
- deterministic controls and timing separation.

Ideas not fully tested:

- HTF liquidity selection such as daily/weekly/monthly levels;
- order block / rejection block / breaker block entries;
- premium/discount dealing range;
- recursive swing hierarchy;
- flow-confirmed early entry using TFI/CVD/force orders;
- early impulse entry before mitigation;
- limit-order-at-zone modeling instead of next-bar-after-mitigation;
- explicit continuation-versus-reversal classifier before MFE is consumed.

Ideas probably not worth testing as direct strategy expansions:

- another isolated CHOCH/FVG/OB label taxonomy;
- session/regime filters as rescue;
- delayed reclaim, true breakout, or mitigation entry with detection-bar
  performance claims;
- visual-only SMC patterns without a realistic entry timing model.

Ideas that could still justify a separate plan:

- MFE accessibility / earliest-knowable-signal diagnostic;
- flow-confirmed sweep impulse diagnostic;
- HTF liquidity quality map as a pre-sweep level-selection study;
- order-block/FVG zone limit-entry simulation, if it models actual order
  placement before the mitigation touch and not after confirmation.

Strong recommendation:

**PLAN ONE MORE META-DIAGNOSTIC: MFE accessibility / earliest knowable signal.**

Do not implement another SMC strategy now. The only research still worth doing
is not "more SMC features"; it is reverse engineering when the move becomes
knowable and whether that moment is before most MFE is gone. If that diagnostic
finds no early knowable signal, stop SMC-source research and monitor
trial-00095.

Do not ask whether the SMC pattern exists visually. Ask whether any part of it
is knowable early enough to trade with positive expectancy after costs.

## 2. Source Coverage Matrix

| Source idea | Source origin | Tested in V1 taxonomy? | Tested in SMC sequence? | Fully tested? | Result | Notes |
| ----------- | ------------- | ---------------------- | ----------------------- | ------------- | ------ | ----- |
| High/low pivot crossover | Makuchaku/eFe, smartmoneyconcepts swing/liquidity | Yes | As base context indirectly | Mostly | Failed as isolated label | V1 tested strict wick cross and confirmed pivots. |
| Close-based BoS | Makuchaku/eFe, smartmoneyconcepts BOS/CHOCH | Yes | Simple local structure break proxy | Partially | Weak/failed standalone | Full CHOCH semantics not tested. |
| Immediate wick reclaim | LuxAlgo, TV sweep scripts | Yes | No, not required | Yes enough | Underperformed raw wick cross | Not worth rescue as standalone feature. |
| Delayed reclaim | LuxAlgo close/retest idea | Yes | No, replaced by mitigation timing | Yes enough for reclaim | Lookahead edge collapsed | Label-available timing killed edge. |
| True breakout / no reclaim | LuxAlgo alternate scenario | Yes | No | Yes enough | Negative when knowable | Entering after no-reclaim confirmation was late/exhausted. |
| Sweep area / reaction zone | LuxAlgo | Partially | Partially via FVG mitigation | Not fully | Inconclusive/late | Sweep level itself was not tested as a limit reaction zone. |
| Displacement | ICT/SMC common pattern | No | Yes | Partially | Signal existed before entry | Detection-bar returns strong; tradability after mitigation failed. |
| FVG / imbalance | Makuchaku/eFe, smartmoneyconcepts, PyIndicators | No | Yes, simple 3-candle FVG | Partially | Late-entry failure | FVG creation as early signal was not separately traded. |
| Mitigation / retest | Makuchaku/eFe, LuxAlgo, ICT | No | Yes | Yes for `mitigation_bar + 1` model | Failed | Median 8 bars after sweep; much MFE already gone. |
| CHOCH / MSS | smartmoneyconcepts, PyIndicators, ICT | No | Proxy only | No | Untested as full definition | But adding full semantics risks lookahead unless tightly defined. |
| Order block | Makuchaku/eFe, smartmoneyconcepts, Backtrex/HorizonAI articles | No | No | No | Untested | Potentially only useful if it enables earlier limit entry. |
| Rejection block / RJB / PPDD | Makuchaku/eFe | No | No | No | Untested | Likely visual/zone refinement; weak priority without MFE accessibility proof. |
| Recursive fractal hierarchy | PyIndicators | No | No | No | Untested | High repaint/lookahead risk; maybe useful only for level quality. |
| HTF bias | ICT/SMC articles, TradingView strategy descriptions | No | No | No | Untested | Prior context filters degraded edge, but HTF level selection differs from regime gating. |
| Premium / discount | ICT/SMC articles | No | No | No | Untested | Could be metadata for level quality, not entry trigger. |
| Session / killzone timing | ICT/TradingView strategy descriptions | Metadata only historically | Metadata only | Not for SMC | Prior evidence negative for filtering | Testing as hard filter is low expected value. |
| Liquidity cluster selection | smartmoneyconcepts liquidity, PyIndicators internal/external liquidity | Partially | Equal-level source only | No | Current equal-level baseline remains strong | HTF/external liquidity quality still untested. |
| Volume / CVD / TFI / force-order confirmation | btc-bot native features, flow sources | Metadata/context in bot | Metadata only in SMC V1 | No | Untested as early gate | This is a plausible early confirmation path. |
| Continuation vs reversal split | LuxAlgo scenarios, V1 taxonomy | Partially | Direction fixed by sweep side | No | Standalone split failed | Needs early classification before MFE consumption. |
| Early entry vs confirmation entry | Reverse-engineering issue | Detection vs label timing only | Detection vs entry timing yes | Partially | Confirmation entry late | Needs earliest-knowable diagnostic. |
| MFE-before-entry decay | V1 lesson extended | Not explicitly | Yes | Yes for mitigation SMC | Decisive failure | Most useful new diagnostic pattern. |

## 3. What Exactly Failed?

### A. Event Taxonomy Failure

The event taxonomy did not prove that "liquidity sweeps do not matter." It
proved that the tested event labels were not enough.

What failed:

- immediate reclaim did not outperform raw wick cross;
- delayed reclaim looked strong from detection but collapsed from
  label-available timing;
- true breakout/no-reclaim reversed negative from label-available timing;
- close-based BoS and wick-cross separation did not create a tradable edge by
  itself.

This means isolated classification was not sufficient. It does not prove that
level quality, flow, or earlier impulse information is worthless.

### B. SMC Sequence Failure

Full SMC was not completely exhausted. The implemented SMC sequence tested a
specific and important version:

`equal-level sweep -> displacement -> structure proxy -> FVG -> mitigation -> next-bar entry`

That version failed. The failure is not "there is no sequence signal." The
sequence had strong detection-bar return and improved over sweep-only. The
failure is that the tradable entry was late:

- full sequence detection 5-bar median: `0.004348`;
- full sequence entry 5-bar median: `0.000558`;
- full sequence entry 5-bar net median after 0.10% cost: `-0.000442`;
- PF proxy: `1.061` versus trial-00095 threshold `4.0`.

Therefore the mitigation-entry SMC version failed. A different hypothesis would
need to target an earlier tradable moment.

### C. Timing Failure

Tradability disappeared between sweep detection and mitigation entry.

Evidence:

- median bars from sweep detection to entry candidate: `8`;
- median MFE before entry: `0.011565`;
- post-entry 5-bar MFE median: `0.004916`;
- post-entry net median negative after costs.

Failure sequence:

- delayed reclaim failed at label availability;
- true breakout failed after no-reclaim confirmation;
- SMC sequence retained signal through detection/displacement/FVG, but the
  mitigation/next-bar entry consumed too much of the move;
- costs converted the small remaining edge into negative median net return.

The critical failure point is not FVG existence. It is the delay between the
observable impulse and the approved entry.

## 4. Reverse Quant Engineering

Start from the failure point:

**Most favorable excursion happened before realistic entry.**

The research question should move from "which SMC object exists?" to "when does
the accessible edge begin, and what was knowable at that time?"

At which bar does MFE begin?

- In the SMC sequence diagnostic, MFE begins in the post-sweep impulse before
  mitigation.
- The median sequence spent eight bars from sweep to entry.
- The median pre-entry MFE was more than twice the post-entry 5-bar MFE.

Which earliest observable facts existed before most MFE was consumed?

Likely candidates:

- liquidity sweep itself;
- displacement candle body/range expansion;
- close through local structure proxy;
- FVG creation at the third candle close;
- TFI/CVD/force-order impulse at or near displacement.

What was not yet knowable?

- whether mitigation would occur;
- whether FVG would hold;
- whether no-reclaim/true-breakout label would remain true;
- whether the eventual visual SMC setup would look "clean."

Is there any deterministic early signal before mitigation that is not pure
lookahead?

Possibly. The legal candidates are:

- displacement close;
- structure-break close;
- FVG-created bar close;
- flow-confirmed displacement bar;
- pre-existing liquidity quality before the sweep.

These are knowable before mitigation. They may still fail after costs, but they
are legitimate to test.

Does displacement itself contain tradable information before mitigation?

The SMC diagnostic suggests yes, because detection-bar performance for complete
future sequences was high. But that number is contaminated by future sequence
selection: at detection time we do not know which sweeps will later complete
the sequence. A valid diagnostic must ask:

- among all sweeps, can displacement/FVG creation identify the winners before
  mitigation?
- do displacement-only or displacement-plus-flow cohorts beat current bot
  baseline from their own entry bars?

Does TFI/CVD/force-order flow provide earlier confirmation than FVG mitigation?

This remains untested. btc-bot already uses TFI/CVD/force-order concepts in
`core/feature_engine.py` and `core/signal_engine.py`, but SMC V1 treated them
as metadata. Flow could be the only practical way to tell whether the sweep is
absorption/reversal or continuation before the retest.

Does waiting for FVG mitigation kill the edge?

For the tested definition, yes. The data directly says mitigation+1 arrived
after most accessible MFE was gone. The visual SMC pattern is therefore
operationally late on BTCUSDT 15m under this implementation.

Is the tradable edge actually in the impulse after sweep, not the retest?

This is the strongest remaining hypothesis. SMC V1 found that the sequence
filter identifies movement, but the prescribed entry waits too long. If any
source-derived edge remains, it is probably in early impulse classification,
not in mitigation entry confirmation.

Is current trial-00095 already capturing the only accessible part of the move?

Possibly. Trial-00095 enters on a tighter current equal-level sweep/reclaim
logic with TFI/quality filters. It may be closer to the accessible phase than
SMC mitigation. The fact that multiple delayed confirmation variants failed
supports this.

Is the SMC pattern visually correct but operationally late?

For the tested version, yes. This is the central lesson. The sequence can exist
and still be a bad bot signal because the bot cannot trade the screenshot in
hindsight.

## 5. Was Claude Too Conservative?

Necessary and correct constraints:

- no detection-bar success claims for delayed labels;
- explicit `label_available_bar` / `entry_candidate_bar`;
- no FeatureEngine/SignalEngine work after failed diagnostics;
- no post-hoc parameter rescue;
- trial-00095 as mandatory benchmark;
- no regime/session filtering rescue after prior negative evidence.

These constraints prevented false positives. V1 delayed reclaim and SMC
detection-bar performance both looked good until timing was enforced.

Potentially over-narrow constraints:

- SMC V1 used mitigation+1 as the primary entry. That is conservative and
  realistic, but it tests only one school of SMC execution.
- Flow confirmation was kept metadata-only. That was appropriate for a minimal
  price-action test, but it means the source-space around microstructure is not
  exhausted.
- HTF liquidity quality was deferred. That avoided scope creep, but it leaves
  external/internal liquidity hierarchy untested.
- Order blocks were deferred. Given the late-entry failure, OBs could matter
  only if they support earlier resting-limit entry; they were not tested.

Did Claude reject ideas prematurely?

No for V1/V2 production progression. The invalidations are solid. But yes in a
narrow sense: the methodology did not exhaust every source idea. It only
invalidated two concrete interpretations. The correct conclusion is:

Claude was right about V1 taxonomy and mitigation-entry SMC invalidation, but
the broader source-space is not fully exhausted. Further exploration is low
expected value unless tied to the specific failure mode: MFE happened before
entry.

## 6. Are We Too Attached To Trial-00095?

Trial-00095 is the benchmark, not a religion.

It should not be sacred. It should be challenged by evidence. But "evidence"
does not mean attractive visual logic or better detection-bar returns. It means
entry-timed, cost-adjusted, sample-sufficient, stable performance that beats
the current validated baseline.

Evidence that would justify challenging trial-00095:

- timing-correct net expectancy above trial-00095 quality;
- PF/ER comparable or superior with enough sample;
- walk-forward stability;
- low overlap if claiming a new edge family;
- clear tradable entry timing;
- no dependence on future-known labels.

Evidence that does not justify challenging trial-00095:

- detection-bar returns from labels known later;
- visual SMC pattern completion;
- "almost as good" PF with more complexity;
- regime/session cherry-picks;
- parameter tuning after a failed diagnostic;
- source popularity.

Future research should benchmark against trial-00095 but not be forced to copy
its logic. A genuinely different edge family could exist, especially a
microstructure/flow edge around sweep impulse. But pausing or modifying
trial-00095 requires much stronger evidence than these SMC diagnostics
produced.

## 7. Open-Source / Article Research Gap

Internet review summary:

- `smartmoneyconcepts` / Joshua Attridge package: useful benchmark candidate.
  It exposes FVG, swing highs/lows, BOS/CHOCH, OB, liquidity, previous high/low,
  and session tools. It also documents look-forward swing detection, which is
  a lookahead risk unless delayed correctly. Useful for offline comparison, not
  production dependency. Source: https://pypi.org/project/smartmoneyconcepts/0.0.16/
- `smc-toolkit`: useful concept / benchmark candidate. It advertises vectorized
  BOS, CHOCH, FVG, OB, and swing structure for quantitative analysis. Source:
  https://pypi.org/project/smc-toolkit/
- `coding-kitties/PyIndicators`: useful concept map. It includes FVG, market
  structure break, CHOCH/BOS fractal, and internal/external liquidity zones
  using multi-timeframe pivot analysis. Useful for hierarchy ideas, but
  hierarchy increases lookahead risk. Source:
  https://github.com/coding-kitties/PyIndicators
- TradingView "Liquidity Sweep & FVG Strategy": useful concept, not code to
  copy. It models HTF levels, one entry per sweep, FVG edge entry, structure
  stops, ZigZag targets, session filters, and realistic commission/slippage.
  It differs from our SMC V1 by emphasizing HTF levels and FVG edge entry.
  Source: https://www.tradingview.com/script/ZwDGpu55-Liquidity-Sweep-FVG-Strategy/
- HorizonAI / Backtrex articles: useful methodology reminders, not evidence.
  They emphasize converting SMC concepts into testable rules and warn that
  discretionary definitions are hard to validate. Sources:
  https://www.horizontrading.ai/learn/backtesting-smart-money-concepts and
  https://backtrex.com/en/use-cases/smc-ict
- GitHub `order-block` topic contains many visual indicators and a few
  backtest-style repos, including ICT Silver Bullet session examples. Treat as
  idea sources only; most are not BTC perpetual futures evidence. Source:
  https://github.com/topics/order-block

Classification:

- useful concept: FVG edge entry, HTF level selection, order-block zone scoring,
  internal/external liquidity hierarchy;
- benchmark candidate: `smartmoneyconcepts`, `smc-toolkit`, PyIndicators;
- bad/repainting risk: swing hierarchy without right-side delay, ZigZag levels
  used before confirmation;
- discretionary/visual only: many SMC articles and indicator guides;
- not directly applicable: NQ/FX session-specific Silver Bullet logic unless
  revalidated on BTC perpetuals.

What these sources model differently from our two tests:

- HTF level selection before sweep;
- order block / FVG edge limit entries;
- session windows, especially NY;
- target selection toward external liquidity;
- internal/external liquidity maps;
- "one entry per sweep" zone management;
- sometimes entry inside FVG before close confirmation.

The most relevant gap is not another FVG detector. It is whether an order can
be placed at a zone before the retest is confirmed without becoming lookahead.

## 8. Possible Alternative Research Directions

### 1. MFE Accessibility / Earliest-Knowable Signal Diagnostic

- Hypothesis: The move is accessible only within a narrow window after sweep;
  later SMC confirmation arrives too late.
- Different from failed tests: does not add SMC labels; maps where MFE occurs
  and what facts were knowable at each bar.
- Earliest realistic signal bar: sweep close, displacement close, structure
  break close, FVG-created close.
- Lookahead risk: medium; must bucket by facts known at each bar, not by future
  completion.
- Data required: BTCUSDT 15m rich DB and optionally 5m price-only.
- Complexity: low/medium.
- Pass/fail: pass only if a knowable pre-mitigation fact has positive net
  expectancy and beats controls/trial-00095 proxy; fail if all accessible
  points are weak after costs.
- Reason to reject now if weak: if it cannot beat trial-00095 or only works
  from future-completed sequence membership.

### 2. Early Impulse / Displacement Entry

- Hypothesis: The tradable edge is in the displacement after sweep, not the
  mitigation retest.
- Different from failed tests: entry is at displacement or structure-break
  close/next bar, before mitigation.
- Earliest realistic signal bar: displacement close.
- Lookahead risk: high if restricted to sweeps that later form FVG/mitigation;
  must evaluate all sweeps with displacement.
- Data required: candles, ATR, TFI optional.
- Complexity: medium.
- Pass/fail: must beat sweep-only, deterministic control, and trial-00095
  quality after costs from displacement entry.
- Reason to reject now if weak: if MFE begins before displacement close or
  displacement entry PF remains near 1.

### 3. Flow-Confirmed Sweep Continuation/Reversal

- Hypothesis: TFI/CVD/force-order/OI distinguishes absorption from continuation
  earlier than FVG mitigation.
- Different from failed tests: uses microstructure confirmation before visual
  SMC completion.
- Earliest realistic signal bar: sweep bar close or displacement bar close with
  available TFI/CVD/force-order bucket.
- Lookahead risk: medium; bucket alignment must use only current/closed flow
  data.
- Data required: `aggtrade_buckets`, force-orders, OI, candles.
- Complexity: medium/high.
- Pass/fail: must improve entry-timed net expectancy and PF versus trial-00095;
  must prove novelty versus current TFI-heavy signal engine.
- Reason to reject now if weak: if it duplicates current trial-00095 confluence
  without performance improvement.

### 4. Liquidity Cluster Quality / HTF Level Map

- Hypothesis: Not every liquidity pool is equal; HTF/external liquidity levels
  have better post-sweep behavior than local equal levels or pivots.
- Different from failed tests: changes pre-sweep level selection, not
  post-sweep confirmation.
- Earliest realistic signal bar: before sweep; level quality is known in
  advance.
- Lookahead risk: medium; HTF levels and recursive pivots must be confirmed
  before use.
- Data required: 15m/1h/4h, possibly daily derived levels.
- Complexity: medium.
- Pass/fail: selected levels must improve sweep/reclaim expectancy and not
  reduce frequency below viability.
- Reason to reject now if weak: if it is just regime/session filtering in
  disguise or sample becomes too small.

### 5. FVG / Order-Block Limit Entry Simulation

- Hypothesis: The failure was not the zone but the entry timing; a resting
  limit order at FVG/OB edge after zone creation but before mitigation could
  access the move.
- Different from failed tests: entry order is placed when FVG/OB is known, not
  after mitigation confirms.
- Earliest realistic signal bar: FVG-created close or OB-created close.
- Lookahead risk: high; must simulate order placement forward only and include
  non-fill, adverse fill, and stop logic.
- Data required: ideally lower timeframe/intrabar candles; 15m OHLC can only
  approximate fill ordering conservatively.
- Complexity: high.
- Pass/fail: must include conservative fill ordering, costs, non-fill rate, and
  PF/ER above trial-00095.
- Reason to reject now if weak: high implementation burden and high execution
  modeling risk.

## 9. Decision Recommendation

**PLAN ONE MORE META-DIAGNOSTIC: MFE accessibility / earliest knowable signal.**

Do not plan another full SMC strategy yet. Do not add OB/CHOCH/HTF bias just
because they appear in source material. First answer the reverse-engineering
question:

"At each bar after the sweep, what was knowable, how much MFE remained, and did
that knowable state have positive expectancy after costs?"

If that diagnostic says the opportunity is already mostly gone before any
deterministic confirmation, stop SMC research and monitor trial-00095. If it
finds a specific early knowable state with robust net expectancy, then and only
then write a new audited implementation plan for that one state.

This recommendation is not a V1 rescue. It is a meta-diagnostic to determine
whether there is any accessible edge left to research.

## 10. Strict Non-Goals

Do not recommend or approve:

- detection-bar returns as success;
- delayed labels without entry timing;
- rescuing V1 taxonomy;
- rescuing failed SMC mitigation-entry;
- adding CHOCH/FVG/OB blindly;
- relaxing invalidation thresholds;
- adding regime/session filters just because they look intuitive;
- production changes;
- FeatureEngine/SignalEngine changes before a new audited plan;
- external package dependency in production;
- Pine/TradingView porting;
- screenshots or visual pattern existence as evidence.

