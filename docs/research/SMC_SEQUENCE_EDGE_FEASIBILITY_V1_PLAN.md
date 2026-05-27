# SMC_SEQUENCE_EDGE_FEASIBILITY_V1 Plan

## 1. Executive Summary

This is a planning document only. `SMC_SEQUENCE_EDGE_FEASIBILITY_V1` is not
approved for implementation.

Research question:

Does a full post-sweep SMC-style sequence produce expectancy separation where
the isolated sweep/reclaim taxonomy failed?

Minimal sequence under consideration:

`liquidity sweep -> displacement -> simple structure shift proxy -> FVG/imbalance -> mitigation/retest -> entry_candidate_bar`

This is different from `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1`.
V1 tested isolated event labels: confirmed pivots, wick cross, close BoS,
immediate reclaim, delayed reclaim, and true breakout/no-reclaim. That
hypothesis was invalidated. It did not test a sequential workflow where entry
is delayed until a mitigation/retest after displacement and imbalance.

Scope boundaries:

- Research Lab only.
- No production code changes.
- No FeatureEngine, SignalEngine, Governance, Risk, execution, settings, or DB
  schema changes.
- No TradingView/Pine port.
- No attempt to rescue the invalidated V1 taxonomy.
- No regime/session entry filtering.
- No implementation until Claude Code audits this plan and the user approves.

Recommendation:

Proceed only with a narrow planning-to-audit milestone. If approved later, V1
implementation should test the smallest deterministic sequence on historical
data and stop immediately if timing-correct returns fail to beat trial-00095,
sweep-only, and deterministic controls.

## 2. Why This Is Different From V1

V1 conclusion:

- Implementation: PASS.
- Methodology: PASS.
- Production contamination: NONE.
- Hypothesis: INVALIDATED.
- Key lesson: delayed labels measured from `detection_bar` create fake edge.

V1 invalidated this question:

"Does classifying isolated wick/close/reclaim/true-breakout events improve the
current sweep/reclaim edge?"

It did not invalidate this question:

"Does a complete sequence after liquidity is taken create a realistic entry
edge?"

The proposed SMC diagnostic must therefore measure outcomes only from a
realistic `entry_candidate_bar` or `label_available_bar`, never from the
original sweep bar unless the full signal was knowable there.

## 3. External Research Synthesis

External sources are inspiration only. They are not authority, no proprietary
Pine code should be copied, and no external package should become a production
dependency.

Sources reviewed:

- Makuchaku/eFe Super OrderBlock / FVG / BoS Tools:
  https://es.tradingview.com/script/aZACDmTC-Super-OrderBlock-FVG-BoS-Tools-by-makuchaku-eFe/
- LuxAlgo Liquidity Sweeps:
  https://www.luxalgo.com/library/indicator/liquidity-sweeps/
- joshyattridge smart-money-concepts:
  https://github.com/joshyattridge/smart-money-concepts
- coding-kitties PyIndicators:
  https://github.com/coding-kitties/PyIndicators

Relevant extracted ideas:

- Makuchaku/eFe separates close-based BoS from high/low pivot cross behavior.
  The page states the tool draws OrderBlock, FVG, and BoS boxes until first
  retest/mitigation, and notes that high/low crossover BoS was added to help
  identify liquidity sweep scenarios while default BoS remains close crossing
  fractal pivots.
- LuxAlgo describes liquidity sweeps as either wick-through-and-retrace or
  close-through followed by retest and an opposing wick. It also treats the
  sweep area as a possible later support/resistance or entry zone.
- smart-money-concepts exposes deterministic Python concepts for FVG, swing
  highs/lows, BOS/CHOCH, OB, and liquidity. Its README defines FVG as a
  three-candle gap and swing points as highest/lowest values over lookback and
  look-forward windows.
- PyIndicators documents CHOCH/BOS with fractal swing detection, liquidity
  sweeps, clustered buyside/sellside liquidity, liquidity voids, and recursive
  fractal sweep concepts. This supports deterministic research design but also
  warns that hierarchy can add lookahead/repainting risk.

Interpretation for btc-bot:

- BoS, FVG, mitigation, and displacement should be tested as sequence elements,
  not as standalone entry signals.
- Mitigation/retest is the earliest plausible entry candidate in a full SMC
  workflow.
- Any delayed sequence must explicitly separate first detection from final
  tradable timing.

## 4. Repository Inventory

Existing production primitives:

- `core/feature_engine.py`
  - `compute_atr`
  - `compute_ema`
  - `detect_equal_levels`
  - `detect_sweep_reclaim`
  - CVD divergence from `_cvd_price_history`
  - TFI from `snapshot.aggtrades_bucket_60s`
  - force-order rate/spike/decreasing from `snapshot.force_order_events_60s`
- `core/signal_engine.py`
  - Current sweep gate, reclaim gate, TFI/CVD direction inference, confluence
    score, entry/stop/TP geometry.
  - This file is baseline context only; do not modify it in this milestone.
- `core/regime_engine.py`
  - Deterministic regimes: NORMAL, COMPRESSION, UPTREND, DOWNTREND,
    CROWDED_LEVERAGE, POST_LIQUIDATION.
  - Regime should be metadata only for this research, not an entry filter.
- `core/context_engine.py`
  - UTC session and volatility metadata. Session should be metadata only.
- `core/models.py`
  - Runtime contracts for `MarketSnapshot`, `Features`, `SignalCandidate`,
    diagnostics, regime, context, and executable signal.
- `core/governance.py`
  - Existing duplicate-level veto for live candidates. Do not reuse this
    stateful runtime component in research; implement research-only
    de-duplication if implementation is later approved.

Existing data and replay primitives:

- `backtest/replay_loader.py`
  - Builds historical `MarketSnapshot` from SQLite `candles`, `funding`,
    `open_interest`, `aggtrade_buckets`, `force_orders`, and 15m/1h/4h candles.
- `backtest/backtest_runner.py`
  - Runtime-parity backtest runner for accepted signal populations.
- `storage/schema.sql`, `storage/repositories.py`, `storage/state_store.py`
  - DB schema and persistence contracts. Do not migrate schema for this
    milestone.

Existing Research Lab patterns:

- `research_lab/analysis_sweep_reclaim_event_taxonomy_diagnostic_v1.py`
  - Best template for timing discipline, event rows, deterministic controls,
    local JSON/report output, and no production imports.
- `research_lab/analysis_sweep_acceptance_continuation.py`
  - Price-action sequence research pattern.
- `research_lab/analysis_sweep_acceptance_retest_continuation.py`
  - Retest/impulse sequence pattern.
- `research_lab/analysis_btc_5m_sweep_reclaim_feasibility.py`
  - 5m versus 15m feasibility pattern and trial-00095 parameter replay context.
- `research_lab/analysis_btc_5m_multi_candle_event_setup_feasibility.py`
  - Multi-candle setup and data audit pattern.
- `research_lab/analysis_trial_00095_conditional_edge.py`
  - Frozen trial-00095 comparison pattern.
- `research_lab/diagnostics/event_study_v1.py`
  - Event-study pattern over feature snapshots.

Relevant tests:

- `tests/test_research_lab_sweep_reclaim_event_taxonomy_diagnostic_v1.py`
- `tests/test_sweep_acceptance_continuation.py`
- `tests/test_sweep_acceptance_retest_continuation.py`
- `tests/test_research_lab_multi_candle_events.py`
- `tests/test_research_backtest_runner.py`
- `tests/test_feature_engine.py`
- `tests/test_signal_engine.py`

Canonical local data candidates:

- `research_lab/data/crowded_unwind_backtest.db`
  - BTCUSDT 15m/1h/4h candles from 2020-09-01 to 2026-03-28.
  - Includes `aggtrade_buckets`, `funding`, `open_interest`, `force_orders`,
    `trade_log`, and `signal_candidates`.
  - Best V1 canonical source because it supports trial-00095 comparison and
    optional TFI/flow metadata.
- `research_lab/snapshots/btc_5m_2022_2026.db`
  - BTCUSDT 5m candles from 2022-01-01 to 2026-04-02.
  - Price-only; no TFI/CVD/funding/OI/force-orders.
  - Suitable only as optional price-action sensitivity check.
- `research_lab/snapshots/replay-run13-regime-aware-trial-00063.db`
  - BTCUSDT 15m/1h/4h candles and trial replay tables.
  - Force-orders are empty in this file, so not preferred for this diagnostic.

## 5. SMC Component Gap Analysis

Already available:

- Sweep/reclaim: `core/feature_engine.py` and V1 research diagnostic.
- ATR/volatility: `core/feature_engine.py`; repeated research helpers.
- Equal levels: `core/feature_engine.py`.
- TFI/CVD/force-order inputs: available from `aggtrade_buckets`,
  `cvd_price_history`, and `force_orders` in richer SQLite datasets.
- Regime/context metadata: `core/regime_engine.py`, `core/context_engine.py`.
- Historical replay harness: `backtest/replay_loader.py`,
  `backtest/backtest_runner.py`, Research Lab analysis scripts.

Missing deterministic SMC primitives:

- Swing hierarchy: no production or research implementation for short,
  intermediate, and HTF nested swings.
- BOS/CHOCH/MSS: no dedicated deterministic implementation beyond V1
  close-based BoS labels.
- FVG/imbalance: no current local primitive.
- Displacement/impulse after sweep: current TFI impulse exists in
  `SignalEngine`, but no price-action displacement sequence classifier exists.
- Order block/rejection block: no local primitive.
- Mitigation/retest of FVG or OB zones: no local primitive.
- Premium/discount or HTF dealing range: no local primitive.

Recommended gap strategy:

- V1 should implement minimal deterministic research-only proxies for
  displacement, simple structure shift, FVG, and mitigation.
- V1 should not implement order blocks, recursive swing hierarchy, full CHOCH
  semantics, premium/discount, or HTF dealing range.

## 6. Proposed V1 Event Sequence

V1 should test one narrow sequence:

1. Base liquidity event.
2. Directional displacement after liquidity is taken.
3. Simple structure shift proxy in the expected direction.
4. Simple FVG/imbalance appears during or immediately after displacement.
5. Price mitigates/retests the FVG zone.
6. `entry_candidate_bar` occurs only when mitigation/retest is confirmed.
7. Outcomes are measured from `entry_candidate_bar` and
   `label_available_bar`.

Recommended base event:

- Primary: current bot equal-level sweep approximation using the same
  deterministic equal-level and sweep concepts from `core/feature_engine.py`,
  reimplemented or wrapped research-only to avoid live side effects.
- Secondary optional benchmark: V1 confirmed-pivot wick-cross events from
  `research_lab/analysis_sweep_reclaim_event_taxonomy_diagnostic_v1.py` if
  cheap to reuse.
- Do not multiply events by treating both sources as independent signals. Use
  one `sequence_source` field and compare sources separately.

Direction convention:

- Low-side liquidity swept -> candidate long sequence.
- High-side liquidity swept -> candidate short sequence.

Synthetic example:

- Bar 100: price sweeps below equal low. This is `detection_bar`.
- Bars 101-103: bullish displacement prints with ATR-normalized body/range
  expansion and breaks a recent local swing high. This is
  `confirmation_bar`.
- Bars 101-103 also create bullish FVG zone.
- Bar 108: price returns into the FVG zone and closes back in the intended
  direction. This is `entry_candidate_bar`.
- Returns are measured from bar 108, not bar 100.

## 7. Timing Model

Every event row must include:

- `detection_bar`: first liquidity event bar.
- `displacement_bar`: first bar satisfying displacement proxy.
- `structure_shift_bar`: first bar satisfying simple structure shift proxy.
- `fvg_created_bar`: bar where FVG is knowable.
- `confirmation_bar`: max of displacement, structure shift, and FVG creation.
- `mitigation_bar`: bar that retests/mitigates the FVG zone after confirmation.
- `entry_candidate_bar`: earliest realistic entry opportunity.
- `label_available_bar`: bar where the full sequence label is knowable.
- `return_start_bar_detection`: for audit only, not success claims.
- `return_start_bar_entry_candidate`: primary outcome start.
- `return_start_bar_label_available`: must equal or be no earlier than
  `entry_candidate_bar`.

Timing rules:

- No pivot, swing, or level can be used before its right-side confirmation.
- FVG is only known when the third candle in the three-candle pattern closes.
- Structure shift is only known when the break candle closes.
- Mitigation/retest is only known when the mitigation/retest bar closes.
- If execution delay is modeled, `entry_candidate_bar` should be
  `mitigation_bar + 1`; otherwise it can be the mitigation close, but this must
  be declared consistently.

Recommended V1 entry timing:

- Primary conservative model: enter on the next bar open after the mitigation
  bar closes, approximated as returns from `mitigation_bar + 1` close/open
  depending on available output convention.
- Secondary diagnostic model: returns from mitigation close for sensitivity.
- The report must lead with conservative `entry_candidate_bar` results.

## 8. Minimal Deterministic Proxies

### Base Liquidity Event

Primary equal-level sweep proxy:

- Build equal highs/lows from prior candles only.
- Use ATR-scaled cluster tolerance and minimum hits.
- Mark one liquidity level as taken once and retire it.
- Low sweep: `low < level - sweep_buf_atr * atr`.
- High sweep: `high > level + sweep_buf_atr * atr`.

Do not require immediate reclaim for SMC V1; the sequence is tested after the
liquidity event.

### Displacement

Minimal deterministic proxy:

- Long candidate after low sweep:
  - A post-sweep candle closes above its open.
  - `abs(close - open) / atr >= displacement_body_atr`.
  - `(high - low) / atr >= displacement_range_atr`.
  - Close is in upper body percentile, for example
    `(close - low) / (high - low) >= 0.65`.
- Short candidate after high sweep:
  - Mirror conditions: bearish body and close in lower range percentile.

Suggested starting thresholds:

- `displacement_body_atr >= 0.50`
- `displacement_range_atr >= 1.00`
- Search window: `1..6` bars after sweep.

Optional metadata only:

- TFI sign alignment from `aggtrade_buckets`.
- CVD delta direction.
- Force-order presence.

Do not gate V1 on TFI/CVD/force-orders initially; first prove the price-action
sequence itself separates.

### Simple Structure Shift Proxy

Avoid discretionary CHOCH language in V1. Use a deterministic local swing break:

- Confirm local swings with `left=2`, `right=2` or `left=3`, `right=3`.
- Long candidate: after low sweep, close breaks above the most recent confirmed
  swing high that existed before or at the sweep.
- Short candidate: after high sweep, close breaks below the most recent
  confirmed swing low that existed before or at the sweep.
- Break must occur after sweep and within `structure_window_bars`, suggested
  `1..10` bars.

This is a structure-shift proxy, not a full CHOCH/MSS engine.

### FVG / Imbalance

Use a minimal three-candle gap:

- Bullish FVG at center candle `i` is known at `i + 1` close when
  `high[i - 1] < low[i + 1]`.
- Bearish FVG at center candle `i` is known at `i + 1` close when
  `low[i - 1] > high[i + 1]`.
- Zone boundaries:
  - Bullish: bottom `high[i - 1]`, top `low[i + 1]`.
  - Bearish: bottom `high[i + 1]`, top `low[i - 1]`.
- Minimum gap size: `fvg_min_atr`, suggested `0.05 ATR`.
- FVG must form after sweep and no later than `fvg_window_bars`, suggested
  `1..8` bars.

Do not join consecutive FVGs in V1. One zone per sequence.

### Mitigation / Retest

Mitigation occurs only after the FVG is known:

- Bullish mitigation: a later candle's low enters the bullish FVG zone.
- Bearish mitigation: a later candle's high enters the bearish FVG zone.
- Conservative confirmation:
  - Bullish: mitigation candle closes above FVG midpoint or closes bullish.
  - Bearish: mitigation candle closes below FVG midpoint or closes bearish.
- Suggested search window: `1..20` bars after FVG creation.
- One mitigation entry per FVG. Retire the FVG after first entry candidate.

### Entry Candidate

Recommended primary definition:

- `entry_candidate_bar = mitigation_bar + 1`
- Entry price approximation: next bar open if available; otherwise next bar
  close for forward-return event study.
- If `mitigation_bar + 1` does not exist, sequence is incomplete and excluded
  from outcome cohorts.

Report both:

- Conservative returns from `entry_candidate_bar`.
- Audit-only returns from `detection_bar` to expose lookahead bias.

Success claims can only use `entry_candidate_bar` or later.

## 9. Data Requirements

Canonical V1 source:

- `research_lab/data/crowded_unwind_backtest.db`
- BTCUSDT 15m primary pass.
- Date range available locally: 2020-09-01 to 2026-03-28.
- Tables available: `candles`, `aggtrade_buckets`, `funding`,
  `open_interest`, `force_orders`, `trade_log`, `signal_candidates`.

Why 15m first:

- Trial-00095 baseline is 15m.
- The richer DB has 1h/4h context plus flow data.
- Direct comparison to trial-00095 is mandatory.
- It avoids mixing the SMC question with the previously failed 5m frequency
  migration question.

Optional sensitivity:

- `research_lab/snapshots/btc_5m_2022_2026.db`
- BTCUSDT 5m price-only.
- Use only after primary 15m results pass basic viability gates.

Expected event count estimate:

- Unknown until implementation preflight.
- V1 taxonomy produced large 5m event populations, but full sequence should
  be much rarer.
- Predeclared viability gates:
  - At least 100 OOS events.
  - At least one event per month on average.
  - No walk-forward fold below 50 events for decision-grade claims.

## 10. Test Plan

Required unit tests before any diagnostic run:

- FVG detection:
  - bullish and bearish three-candle FVG.
  - no FVG when candle overlap exists.
  - FVG is not available before the third candle closes.
- Displacement:
  - body/range ATR thresholds pass and fail deterministically.
  - direction-specific body checks.
- Structure shift proxy:
  - local swing cannot be used before right-side confirmation.
  - long break requires close above prior confirmed swing high.
  - short break requires close below prior confirmed swing low.
- Mitigation/retest:
  - wick touch versus close confirmation behavior.
  - entry candidate offset after mitigation.
  - no entry before FVG is known.
- Timing model:
  - `detection_bar <= confirmation_bar <= mitigation_bar <= entry_candidate_bar`.
  - `label_available_bar >= entry_candidate_bar`.
  - delayed labels fail tests if measured only from detection for success.
- Duplicate prevention:
  - one sequence per retired liquidity level.
  - one entry per FVG.
  - overlapping FVGs do not inflate independent sequences.
- Outcome metrics:
  - forward returns from detection and entry are both computed.
  - primary summary uses entry timing.
  - MAE/MFE windows start from entry timing.
- Data quality:
  - OHLC validation.
  - monotonic timestamps.
  - missing gap count.
- Synthetic SQLite integration:
  - construct deterministic candles with one full sequence.
  - expected event count exactly one.
  - expected `entry_candidate_bar` exact index.
- Control cohort:
  - deterministic shifted timestamps produce no lookahead timing leakage.

Optional reference tests:

- Compare selected FVG/swing outputs against `smart-money-concepts` or
  PyIndicators only as skipped/offline benchmark tests.
- Do not add those packages as production dependencies.

## 11. Scope Boundaries

V1 scope:

- Research-only script and tests if approved later.
- Minimal sequence: equal-level sweep -> displacement -> simple structure shift
  proxy -> simple FVG -> mitigation/retest -> entry candidate.
- BTCUSDT 15m primary dataset.
- Optional 5m price-only sensitivity only if primary pass is not already
  invalidated.
- Metadata-only TFI/CVD/force-orders/regime/session.
- JSON and Markdown research output.

Suggested implementation files if approved later:

- `research_lab/analysis_smc_sequence_edge_feasibility_v1.py`
- `tests/test_research_lab_smc_sequence_edge_feasibility_v1.py`
- `docs/analysis/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_<date>.md`
- `research_lab/analysis_output/smc_sequence_edge_feasibility_v1_<date>.json`

V2 deferred:

- Full CHOCH/MSS semantics.
- Order blocks and rejection blocks.
- Recursive/hierarchical swing structure.
- Joined/stacked FVGs.
- OB/FVG confluence scoring.

V3+ deferred:

- HTF bias alignment.
- Premium/discount zones.
- Dealing ranges.
- Multi-timeframe nested liquidity.
- Portfolio-level integration.
- FeatureEngine facts and feature flags.
- SignalEngine interpretation.

Never in this planning milestone:

- Production code changes.
- Live behavior changes.
- Settings/profile changes.
- DB schema migrations.
- Dashboard/UI changes.
- Pine code copying.
- Regime/session entry filters.
- Detection-bar-only success claims.

## 12. Invalidation Criteria

These STOP conditions must be evaluated before any FeatureEngine or SignalEngine
work is considered.

Timing and lookahead:

- FAIL if entry-timed median return is not materially better than detection
  controls.
- FAIL if the apparent edge exists only from `detection_bar`.
- FAIL if win rate drops to approximately 50% from `entry_candidate_bar`.
- FAIL if any delayed label is available before its true confirmation.

Baseline separation:

- FAIL if full sequence median return <= sweep-only median return.
- FAIL if full sequence median return <= deterministic shifted control.
- FAIL if full sequence median return <= current trial-00095 baseline proxy.
- FAIL if full sequence does not beat V1 raw wick-cross baseline
  (`0.000237` median 5-bar signed return) on comparable timing.
- FAIL if full sequence does not improve over V1 delayed-reclaim
  label-available result (`0.000054` median 5-bar signed return) by a
  practically meaningful amount.

Trial-00095 benchmark:

- FAIL if simulated sequence ER < 2.0.
- FAIL if simulated sequence PF < 4.0.
- FAIL if max drawdown > 10% or exceeds the trial-00095 comparable drawdown.
- FAIL if improvement over trial-00095 is < 15% ER and < 20% PF while sample
  size is reduced by more than 30%.

Sample size and frequency:

- INCONCLUSIVE if OOS events < 100.
- FRAGILE if any walk-forward fold has < 50 events.
- TOO RARE if average frequency < 1 event per month.
- NOT VIABLE if collecting 50 events requires more than four years.

Stability:

- FAIL if positive results are concentrated in one period shorter than three
  months.
- FRAGILE if 0/4 or 1/4 walk-forward folds are positive.
- FAIL if post-fee/slippage expectancy disappears.

Late-entry problem:

- FAIL if median MFE occurs before `entry_candidate_bar`.
- FAIL if mitigation/retest entry is consistently after the favorable move.
- FAIL if MAE/MFE ratio worsens versus sweep-only or trial-00095 baseline.

Novelty:

- FAIL if displacement proxy is >90% correlated with existing TFI/confluence
  accepted signals and adds no new event population.
- FAIL if overlap with trial-00095 accepted entries is high and performance is
  not better.

Duplicate inflation:

- FAIL if the same liquidity level generates multiple independent sequences.
- FAIL if event count drops >50% after proper de-duplication, unless the report
  explicitly marks previous counts as inflated and invalid.

Complexity:

- FAIL if the plan requires V2 components to make V1 look viable.
- FAIL if the sequence is so complex that it cannot be tested with deterministic
  unit tests.

Pass/inconclusive/fail rules:

- PASS requires beating sweep-only, deterministic control, and trial-00095
  baseline on entry-timed outcomes with adequate sample size.
- INCONCLUSIVE means sample size/frequency is insufficient; no production work.
- FAIL means stop the SMC sequence branch unless a new, separately approved
  planning milestone changes the research question.

## 13. Baseline Comparison Plan

Mandatory comparisons:

- Trial-00095 accepted trade baseline.
  - Use frozen trial-00095 replay artifacts or reproduce via existing Research
    Lab replay patterns.
  - Compare ER, PF, max drawdown, trade count, and overlap.
- Current equal-level sweep/reclaim proxy.
  - Use the current equal-level sweep/reclaim approximation as the primary base
    event source.
- Sweep-only cohort.
  - Same liquidity source without requiring displacement, FVG, or mitigation.
- V1 taxonomy references.
  - Raw wick cross median: `0.000237`.
  - Immediate reclaim median: `0.000184`.
  - Delayed reclaim label-available median: `0.000054`.
  - True breakout label-available median: `-0.000268`.
- Random/control cohort.
  - Deterministic shifted event timestamps, preserving direction and broad time
    distribution.
- Entry timing sensitivity.
  - Detection-bar returns shown only as audit evidence.
  - Entry-candidate returns are the primary basis for any conclusion.

Comparison to trial-00095 is mandatory. If full SMC does not beat trial-00095,
it is not useful enough to justify live-path complexity.

## 14. Implementation Effort Estimate

This is only an estimate for a future approved implementation.

Expected files:

- One research script: 800-1,300 lines.
- One focused test file: 250-450 lines.
- One generated Markdown report.
- One generated JSON output, likely ignored if large, with hash recorded.

Expected runtime:

- 15m BTC primary pass: likely 1-5 minutes depending sequence search indexing.
- 5m optional sensitivity: likely 5-15 minutes if implemented naively; should
  use indexes similar to V1 taxonomy diagnostic if run over full history.

Timeline:

- Plan audit and revision: 0.5-1 day.
- Implementation after approval: 2-4 days.
- Test hardening and report generation: 1-2 days.
- Claude audit: separate.

## 15. Risk Assessment

Lookahead/repainting risk:

- Swing and pivot confirmation can leak future data if right-side bars are used
  before confirmation.
- FVG is a three-candle pattern and is only known after the third candle closes.
- Mitigation is a delayed event and must not backdate entry.
- CHOCH/MSS language is discretionary unless reduced to deterministic rules.

Duplicate inflation risk:

- One liquidity level can spawn many FVGs if not retired.
- One FVG can be touched many times if not retired after first valid mitigation.
- Overlapping zones can multiply identical opportunities.

Late-entry risk:

- Full SMC confirmation may arrive after the move has already paid.
- V1 proved this with delayed reclaim and true breakout.
- The report must explicitly compare MFE before and after entry.

Data risk:

- 5m local DB lacks flow/context data.
- 15m rich DB is better for trial-00095 comparison but may not match lower
  timeframe discretionary SMC expectations.
- Force-order availability differs by DB.

Methodology risk:

- Adding too many SMC components can overfit after V1 failure.
- Parameter rescue would invalidate the milestone.
- Regime/session filtering has already degraded edge in prior research and must
  remain metadata only.

## 16. Open Questions

- Should V1 use only current equal-level sweeps, or include V1 pivot sweeps as a
  separate source comparison?
  - Recommendation: current equal-level primary, pivot source optional
    comparison only.
- Should entry be modeled from mitigation close or next bar open?
  - Recommendation: next bar open/next bar close approximation as primary
    conservative model; mitigation close only as sensitivity.
- Should TFI alignment be a gate?
  - Recommendation: metadata only in V1; gate only in a later milestone if the
    price-action sequence passes.
- Should 5m be included?
  - Recommendation: no for primary V1; optional sensitivity after 15m pass.

## 17. Recommendation

Proceed with this plan only if the user wants a separate full-SMC research
question after accepting V1 taxonomy invalidation.

Recommended next step:

- Send this plan to Claude Code for audit.
- Do not implement until audit passes and user explicitly approves.

Do not proceed if the goal is to rescue V1. V1 is closed and invalidated.

The only valid hypothesis here is new:

"A full post-sweep sequence with displacement, simple structure shift, FVG, and
mitigation may create a realistic entry edge where isolated event taxonomy did
not."

The default expectation should remain skeptical. Trial-00095 is the benchmark.
