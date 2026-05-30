# RESEARCH_LESSONS_SYNTHESIS_AND_TRIAL_00095_REVERSE_ENGINEERING_V1_PLAN

Planning date: 2026-05-30
Milestone: RESEARCH_LESSONS_SYNTHESIS_AND_TRIAL_00095_REVERSE_ENGINEERING_V1
Mode: Quant Research / Edge Discovery Mode
Status: PLANNING_COMPLETE - awaiting Claude audit before any implementation

## Scope

This is a research synthesis and diagnostic-planning milestone. It is not a diagnostic implementation.

Allowed output: synthesis of prior research, failure-mode taxonomy, timeframe coverage audit, trial-00095 reverse-engineering questions, candidate next diagnostics, pre-result invalidation criteria, and one recommended next diagnostic.

Not allowed: diagnostic code, backtests, new experiments, production code changes, settings changes, trial-00095 modification, dependency installation, promotion, or reopening closed families as standalone entry signals.

Known cleanup items are deliberately out of scope:

- `hmmlearn` dependency tracking should be handled in a cleanup milestone.
- trailing whitespace in recent tracker/audit markdown should be handled in a cleanup milestone.
- `explore_gate_passed` naming in HMM reports is a clarity issue only, not a result bug. STOP gates have precedence.

## Executive Summary

The research program has now produced two kinds of evidence.

First, trial-00095 remains the only validated BTCUSDT 15m edge. It passed walk-forward validation with ER about 2.13, PF about 4.66, 271 campaign trades, 56% win rate, and acceptable OOS validation counts. It is a sweep/reclaim mean-reversion edge with flow/confluence, and prior diagnostics show that later SMC confirmations arrive too late or fail after realistic entry timing.

Second, three post-trial exploratory families have been invalidated:

- liquidation burst reversal failed primarily on timing and MFE accessibility;
- volatility breakout failed despite excellent MFE accessibility, meaning no predictive power;
- regime shift detection failed despite acceptable MFE accessibility, meaning no predictive power and no advantage over simple controls.

The correct next step is not another speculative standalone edge family. The correct next step is to understand the validated edge: why trial-00095 wins, why it loses, what gates create scarcity, whether near-misses contain any safe expansion population, and whether exits/risk or symbol transfer offer cleaner trade-count improvement than relaxing BTC thresholds.

This plan recommends one next diagnostic:

`TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1`

The diagnostic should analyze the existing validated trial-00095 population and its surrounding feature context. It should not change thresholds, generate new entries, or apply failed regime/HMM signals as entries. Its job is to produce an attribution map that tells the next builder whether to pursue near-miss expansion, filter lift, exit/risk work, runtime forensics, or multi-asset scaling.

## Prior Research Inventory

| Milestone / artifact | Family | Mechanism | Timeframe | Data used | Entry timing | Result | Failure mode |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `WF_VALIDATION_TRIAL_00095_2026-05-08` | sweep/reclaim baseline | Optuna trial-00095 sweep/reclaim with flow/confluence | 15m | BTC replay, 2022-2026 | existing BacktestRunner timing | VALIDATED_BASELINE | not failed; benchmark |
| `TRIAL_00095_CONDITIONAL_EDGE_ANALYSIS_2026-05-13` | baseline attribution | depth quartiles, feature correlation, regime/session breakdown | 15m | 274 replay trades + production rejected sweep sample | accepted trade replay | DEFERRED | useful but incomplete; rejected backtest population unavailable |
| `OOS_WF_THRESHOLD_STABILITY_2026-05-13` | parameter stability | ceteris paribus sweep-depth threshold grid | 15m | BTC replay OOS windows | BacktestRunner timing | DEFERRED | baseline conservative, lower thresholds rejected, exact threshold uncertain |
| `AUDIT_GRID_SEARCH_TRIAL00095_2026-05-12` | parameter expansion | depth/reclaim/sweep grid to increase trade count | 15m | 60-grid campaign | BacktestRunner timing | INVALIDATED_CONTROLLED_RELAXATION | higher frequency degraded ER/PF or triggered safety flags |
| `TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_2026-05-18` | exit surface | distribution clipping on frozen realized R | 15m | 274 frozen trades | not full intrabar replay | DEFERRED | loss cap looked useful in distribution only; needed executable validation |
| `TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION_2026-05-18` | exit/risk | executable hard loss caps on frozen entries | 15m | 274 frozen entries | post-entry 15m threshold touch | INVALIDATED_NO_ROBUST_IMPROVEMENT | loss caps cut too many recovering winners |
| `SWEEP_RECLAIM_SINGULAR_EDGE_ASSESSMENT_2026-05-13` | strategic synthesis | 6 setup families + 4 context variants | mostly 15m | research reports | varied | VALIDATED_BASELINE_CONTEXT | trial-00095 is singular edge; context expansion failed |
| `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1` | sweep taxonomy | raw wick, reclaim labels, true breakout/no reclaim | 5m | 447k BTC 5m candles | label-aware timing | INVALIDATED_TIMING | delayed labels created fake edge when measured from detection |
| `SMC_SEQUENCE_EDGE_FEASIBILITY_V1` | SMC sequence | sweep -> displacement -> FVG/mitigation sequence | 15m | 195k BTC 15m candles | median entry 8 bars after sweep | INVALIDATED_TIMING | MFE consumed before entry, net after costs negative |
| `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` | meta-MFE | 28 post-sweep knowable states | 15m | candles, aggtrade, force orders, funding, OI | each state's own knowable bar | INVALIDATED_TIMING_AND_NO_EDGE | no state had positive median net after entry |
| `LIQUIDATION_BURST_REVERSAL_ENTRY_FEASIBILITY_V1` | order-flow/liquidation | sweep + liquidation burst reversal | 15m | candles + force_orders | i+3, 45 min | INVALIDATED_TIMING | median MFE consumed 100%, controls beat main |
| `LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1` | order-flow/liquidation | same mechanism on 5m | 5m | fetched BTC 5m + force_orders | i+3, 15 min | INVALIDATED_TIMING | 100% MFE consumed even at 5m |
| `VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1` | volatility breakout | compressed range breakout + volume + TFI | 15m | candles + aggtrade_buckets | i+1 | INVALIDATED_NO_EDGE | MFE accessible, but ER/PF negative and controls beat main |
| `TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1` | regime shift | ADX+CHOP range-to-trend transition | 15m | candles | i+1 | INVALIDATED_NO_EDGE | MFE accessible, ER/PF weak, 0/4 folds positive |
| `FILTERED_HMM_REGIME_SHIFT_FEASIBILITY_V1` | regime shift | 2-state Gaussian HMM filtered probability transition | 15m | candles/features + hmmlearn | i+1 | INVALIDATED_CONTROL_BEAT_MAIN | MFE accessible, all primary controls beat main, state flips unstable |
| `BTC_5M_SWEEP_RECLAIM_FEASIBILITY_V1` | timeframe | trial-00095-like sweep/reclaim on 5m | 5m vs 15m | standalone 5m harness | simplified harness | INCONCLUSIVE_TIMEFRAME_VALUE | quality improved but frequency gate failed |
| `15M_SIGNAL_5M_ENERGY_OVERLAY_FEASIBILITY` | MTF overlay | 15m signal waits for 5m energy candle | 15m + 5m | standalone harness | after 15m close | INVALIDATED_TIMING | 5m energy appeared too late or too rarely |
| `BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_V1` | 5m setup expansion | compression fakeout reclaim, crowded unwind reversal | 5m | 5m candles, OI/funding/force_orders | setup-specific | INVALIDATED_NO_EDGE | frequency improved but quality collapsed |
| `ETH_TRIAL_00095_TRANSFER_FEASIBILITY_V1` | multi-asset transfer | frozen BTC trial-00095 on ETH | 15m | audited ETH dataset | existing pipeline | VALIDATED_TRANSFER_CANDIDATE | passed gates, not runtime approval |
| `SOL_TRIAL_00095_TRANSFER_FEASIBILITY_V1` | multi-asset transfer | frozen BTC trial-00095 on SOL | 15m | audited SOL dataset | existing pipeline | DEFERRED_RISK | strong ER/PF/trades, failed standalone DD gate; portfolio passed |
| `MULTI_ASSET_FULL_PIPELINE_REPLAY_V1` | portfolio scaling | BTC+ETH frozen trial-00095 through full pipeline | 15m | BTC/ETH datasets | existing pipeline + portfolio gate | VALIDATED_PORTFOLIO_PATH | supports architecture scoping, not diagnostic edge change |

## Failure Mode Taxonomy

### Timing Failures

Timing failures mean the market pattern may exist, but the actionable state is known too late.

Examples:

- SMC mitigation sequence: median entry 8 bars after sweep; favorable excursion mostly happened before entry.
- liquidation burst reversal: 100% median MFE consumed on both 15m and 5m.
- 15m signal + 5m energy overlay: confirmation arrives after the useful entry window.
- delayed sweep/reclaim labels: detection-bar returns looked attractive, label-available returns collapsed.

Rule:

- Do not rescue these with detection-bar returns.
- Only an earlier deterministic signal can reopen the family.

### Predictive Failures

Predictive failures mean timing was acceptable, but the signal did not forecast profitable movement.

Examples:

- volume-confirmed range breakout: 14.95% MFE consumed, but ER=-0.092 and controls beat main.
- trend/range regime shift: 21.5% MFE consumed, but ER=-0.027 and 0/4 folds positive.
- HMM regime shift: 22.8% MFE consumed, but ER=-0.122 and all primary controls beat main.
- 5m multi-candle setups: frequency increased but ER/PF/DD were unacceptable.

Rule:

- Do not add filters to rescue these as standalone entries.
- If reused at all, they must be controls or attribution features around trial-00095, not entry signals.

### Control-Cohort Failures

Control failures are especially decisive because they show the proposed mechanism adds less information than a simpler or random baseline.

Examples:

- liquidation burst controls outperformed main.
- volume breakout no-volume, shifted-entry, and random-offset controls outperformed main.
- HMM controls all beat main, including random offset and deterministic ADX/CHOP baseline.

Rule:

- If a control beats main, the mechanism is invalid unless a data bug is found.

### Sample and Infrastructure Limits

Some directions remain limited by data availability or artifact availability, not necessarily edge absence.

Examples:

- backtest rejected sweep population is not persisted, limiting fair live-vs-backtest rejected-sweep comparison.
- standalone 5m harness results are useful for relative comparison but not directly comparable to official BacktestRunner metrics.
- exact `trial_trades` tables are not available in several new diagnostic databases, forcing rough overlap only.
- runtime recent-trade analysis must query the production server, not local `storage/btc_bot.db`.

Rule:

- The next attribution diagnostic must explicitly report what populations are available and which claims are blocked by missing rejected candidates.

## Trial-00095 Success Hypothesis

Known facts:

- trial-00095 is the active benchmark: ER about 2.13, PF about 4.66, 271 campaign trades, 56% win rate, walk-forward validated.
- The mechanism is sweep/reclaim mean reversion with flow/confluence.
- It is LONG-biased and strongest in uptrend conditions, but prior context specialization failed to improve it.
- Deeper sweeps produce better accepted-trade outcomes, but the exact `0.00649` threshold is conservative rather than proven optimal.
- Lowering the sweep threshold increases trade count but degrades quality or triggers safety flags.
- ETH transfer appears decision-grade offline; SOL is high-frequency/high-ER but DD-heavy.
- Exit clipping looked attractive in distribution but failed executable intrabar validation.

Working hypothesis:

> trial-00095 works because it captures a specific liquidity mean-reversion response that persists long enough for 15m entry, while its depth/flow/confluence thresholds reject shallow noise. The main trade-count bottleneck is not missing a generic regime, breakout, or HMM state. It is scarcity of deep enough sweep/reclaim events and the risk of diluting edge when relaxing gates.

What remains unknown:

- Which exact feature combinations separate winners from losers after controlling for depth and regime?
- Whether near-miss populations just below threshold have any stable positive expectancy under realistic entry.
- Whether current PAPER/runtime trade distribution matches historical accepted-trade distribution.
- Whether BTC trade count should be expanded through near-misses or through ETH/multi-asset scaling.
- Whether any filter can improve drawdown without destroying sample size.

## Timeframe Coverage Audit

| Research | 15m | 5m | 1h/4h | MTF entry | MTF context | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| trial-00095 WF validation | yes | no | yes, through existing feature context | no | yes | validated baseline |
| trial-00095 conditional edge analysis | yes | no | yes, some features such as ATR 4h | no | yes | useful but incomplete |
| OOS threshold stability | yes | no | existing pipeline context | no | yes | lower thresholds rejected |
| BTC 5m sweep/reclaim feasibility | comparison 15m | yes | supplementary context from replay DB | no | partial | 5m quality pass, frequency fail |
| 15m signal + 5m energy overlay | yes | yes | no | yes | no | hybrid fail |
| BTC 5m multi-candle setups | baseline comparison | yes | OI/funding/force_orders context | yes | partial | fail |
| sweep taxonomy diagnostic | no | yes | no | yes | no | delayed labels fail |
| SMC sequence | yes | no | no | no | no | late entry fail |
| MFE accessibility | yes | no | metadata rows available | no | partial | no post-sweep state positive |
| liquidation burst reversal 15m/5m | yes | yes follow-up | no | yes | force-order context | fail on both |
| volatility breakout | yes | no | no | no | no | no edge |
| regime shift deterministic/HMM | yes | no | no | no | no | no edge |
| ETH/SOL transfer | yes | no | 1h derived/available where needed | no | existing pipeline context | ETH pass, SOL DD fail |

Interpretation:

- The project has not been purely 15m. It has tested 5m standalone, 15m+5m overlays, and 5m follow-ups for timing accessibility.
- Most validated pipeline evidence still comes from 15m BacktestRunner-style trial-00095.
- 1h/4h features exist in the strategy context, but most recent edge-family diagnostics were intentionally single-timeframe for methodological clarity.
- The most promising MTF evidence is not a new 5m signal; it is the observation that 5m sweep/reclaim quality improved but did not solve frequency. The subsequent 15m+5m energy overlay failed.

## Open Research Gaps

1. Trial-00095 winner/loser attribution

- Prior analysis covered depth quartiles and simple correlations.
- It did not produce a full attribution map across depth, confluence, TFI, regime, session, ATR, funding/OI, entry MAE/MFE, and loss modes.

2. Near-miss feasibility

- Runtime near-miss diagnostics exist for `sweep_too_shallow`.
- Backtest rejected-sweep population is limited unless reconstructed.
- A future diagnostic must build a fair historical near-miss population before claiming expansion.

3. Recent runtime trade forensics

- Useful for hypothesis generation, but must query production server per `docs/DATA_SOURCES.md`.
- Small sample cannot validate parameter changes.

4. Multi-asset scaling

- ETH transfer is the clearest trade-count expansion path already supported by evidence.
- SOL has strong standalone/portfolio promise but DD risk remains.
- This is a scaling path, not a BTC edge-research path.

5. Filter lift around trial-00095

- Failed regime/HMM signals should not become standalone entries.
- They may be tested only as attribution/filter candidates if the diagnostic is explicitly framed as "does this reduce bad trial-00095 trades without killing sample?"

6. Exit and risk policy

- Simple hard loss controls did not robustly improve trial-00095.
- More nuanced exit/risk work should wait for attribution: identify loss archetypes before designing exit interventions.

## Candidate Next Diagnostics

### Candidate A: `TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1`

Purpose: explain trial-00095 winners, losers, and scarcity using the existing validated trade population and reconstructable feature context.

Output:

- feature bucket performance;
- winner/loser attribution;
- loss archetypes;
- trade scarcity map;
- candidate next hypotheses.

Risk: primarily analytical. Lowest risk because it starts from validated trades and does not change the strategy.

### Candidate B: `TRIAL_00095_NEAR_MISS_EXPANSION_FEASIBILITY_V1`

Purpose: test whether rejected near-miss sweeps can increase trade count without destroying PF/DD.

Risks:

- can easily become threshold rescue;
- requires reconstructing or collecting a fair rejected-sweep population;
- must not use local stale runtime data for current near-misses.

Prerequisite: Candidate A should identify which near-miss buckets are worth testing.

### Candidate C: `TRIAL_00095_REGIME_FILTER_LIFT_V1`

Purpose: test whether deterministic regime/HMM/GARCH features improve trial-00095 by filtering bad trades, not by generating entries.

Risks:

- failed standalone regime signals may be misused as rescue filters;
- sample size may collapse below decision-grade levels;
- filter lift must beat simple baselines and preserve enough trades.

Prerequisite: Candidate A should show a plausible regime-conditioned loss pattern.

### Candidate D: `RECENT_RUNTIME_TRADE_FORENSIC_V1`

Purpose: inspect recent PAPER/runtime trades and blocked signals for operational failure modes.

Risks:

- small sample;
- must query production server, not local DB;
- operational anomalies should not be mistaken for strategy evidence.

Best use: generate hypotheses after the attribution plan, or run in parallel as an operations report if the user needs immediate PAPER health context.

## Recommended Next Diagnostic

Recommended diagnostic:

`TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1`

Reason:

- It starts from the validated edge rather than rescuing failed families.
- It explains success and failure before modifying the system.
- It can determine whether the next practical path is near-miss expansion, filter lift, exits/risk, runtime forensics, or multi-asset scaling.
- It avoids speculative new entry signals.
- It treats trial-00095 as benchmark, not religion: the goal is to understand where it is strong, where it is weak, and what claims remain unsupported.

Primary research questions:

1. Which pre-entry features separate winners from losers inside trial-00095?
2. Are losses concentrated in specific regimes, sessions, volatility states, depth buckets, TFI/CVD states, or funding/OI contexts?
3. Is trade scarcity caused by the depth gate, reclaim gate, flow/confluence gates, risk/governance vetoes, or market regime?
4. Are near-threshold accepted trades still profitable enough to justify future near-miss reconstruction?
5. Are the worst losses structurally different from ordinary losers, or just part of the edge distribution?
6. Do the findings support expanding BTC entries, filtering BTC entries, changing exits/risk, or scaling through ETH?

Required data:

- frozen trial-00095 trade list;
- feature snapshots or reconstructable features at entry;
- trial-00095 configuration;
- historical candles/aggtrade/funding/OI as available;
- optional production server recent trades only if explicitly included as a separate runtime context section.

Important data caveat:

- Backtest accepted trades are available, but rejected backtest candidates may not be persisted. If rejected populations are unavailable, the diagnostic must not claim near-miss edge. It may only recommend a separate near-miss reconstruction diagnostic.

## Pre-Result Invalidation Criteria

STOP this synthesis-to-diagnostic path if:

- the proposed diagnostic requires changing trial-00095 thresholds before attribution;
- primary returns are measured from detection rather than actual trial entry;
- failed standalone HMM/regime/breakout/liquidation signals are used as entry signals;
- the attribution cannot reconstruct enough features to analyze winner/loser cohorts;
- the diagnostic reduces to a post-hoc filter selected after seeing outcomes;
- runtime data is sourced from local `storage/btc_bot.db` rather than production server;
- sample size falls below decision-grade after segmentation and no broad patterns remain.

EXPLORE follow-up if attribution shows:

- a stable feature bucket explains a meaningful share of losses;
- a candidate filter improves PF/DD without killing sample size;
- near-threshold accepted trades show a monotonic quality gradient that justifies reconstructing rejected near-misses;
- loss archetypes suggest an exit/risk intervention different from already-failed simple hard caps;
- multi-asset scaling remains stronger than BTC threshold relaxation for trade-count improvement.

INCONCLUSIVE if:

- accepted-trade features are incomplete;
- winner/loser patterns are weak or contradictory;
- segmentation leaves too few trades per bucket;
- runtime trade sample is too small for anything beyond hypothesis generation.

## Scope Boundaries

The next diagnostic may:

- read research artifacts and historical market data;
- reconstruct features for frozen trial-00095 accepted trades;
- group trades by pre-entry conditions;
- compare winners and losers;
- define future hypotheses.

The next diagnostic must not:

- change trial-00095;
- change settings;
- promote to PAPER/LIVE;
- tune thresholds after seeing results;
- implement near-miss expansion inside the same milestone;
- use failed families as standalone entries;
- treat recent runtime sample as statistically decisive;
- query stale local runtime DB for live status/trades.

## Audit Questions For Claude

Claude should verify:

- Does this synthesis include the relevant prior milestones?
- Does it separate timing failures from no-edge failures?
- Does it avoid rescuing closed families?
- Does it treat trial-00095 as benchmark rather than untouchable doctrine?
- Does it honestly document timeframe coverage?
- Is the recommended diagnostic narrow enough?
- Are invalidation criteria defined before results?
- Does it correctly handle runtime data sourcing?
- Does it prevent threshold tuning and post-hoc filtering?

## Recommendation: PLAN ONE DIAGNOSTIC

Diagnostic name: `TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1`

Mechanism summary: Analyze frozen trial-00095 accepted trades and reconstructable pre-entry features to identify winner/loser drivers, loss archetypes, trade scarcity bottlenecks, and evidence-supported next hypotheses without changing the strategy.

Expected output: attribution report, feature bucket tables, loss archetype map, trade scarcity map, and exactly one next recommendation: near-miss reconstruction, filter-lift planning, exit/risk planning, runtime forensic, multi-asset scaling, or STOP.

Next: Claude audits this synthesis plan. If approved, builder implements only `TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1` as a research-only diagnostic.
