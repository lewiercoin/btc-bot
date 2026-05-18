# External Model Consultation Prompt: Portfolio Setup Research

Use this prompt with external models to brainstorm Research Lab hypothesis cards.
The target output is strategy research design, not production code.

---

## Prompt

You are an expert quant researcher specializing in BTC perpetual futures, market
microstructure, systematic strategy design, walk-forward validation, and
anti-overfit research methodology.

I need a rigorous external consultation for a production-grade BTC trading bot.
The goal is to brainstorm and refine an offline Research Lab hypothesis card for
a possible new setup family. Do not recommend runtime integration. Do not write
production code. Treat this as pre-implementation research design only.

### System Context

The bot is a production trading system with a deterministic decision pipeline:

```text
MarketSnapshot -> Features -> Regime -> SignalCandidate -> Governance -> Risk -> Execution
```

The live path is not open for changes during this consultation. The system has a
strict Research Lab workflow:

```text
hypothesis -> offline experiment -> deterministic gates -> report -> audit -> human decision
```

LLMs/AI are allowed only offline for hypothesis generation, interpretation, and
reporting. They are not allowed in the live decision loop or execution path.

Allowed future implementation scope, if a hypothesis is approved later:

- `research_lab/**`
- `tests/test_research_lab*`
- `docs/analysis/**`
- `docs/MILESTONE_TRACKER.md`
- `research_lab/configs/**`

Forbidden for this direction unless a later audited promotion explicitly allows
it:

- `core/**`
- `orchestrator.py`
- `execution/**`
- `settings.py`
- paper/live runtime behavior
- risk engine or order execution behavior

### Current Baseline

The active baseline is `trial-00095`, a 15m liquidity sweep/reclaim setup.

Known offline baseline characteristics:

- Timeframe: 15m
- Setup family: liquidity sweep/reclaim
- Trades: 47
- Expectancy: ER 2.110
- Profit factor: 3.95
- Max drawdown: 4.49R
- Quality: strong
- Problem: low frequency

Production/PAPER monitoring currently shows many shallow-sweep rejections and
low signal frequency. However, near-miss monitoring does not currently justify
lowering sweep thresholds. Lowering the sweep threshold is not the objective of
this consultation.

Strategic goal:

Build toward a future portfolio of setup families:

- sweep/reclaim for stop-run / liquidity-grab / volatile days
- another setup for trend continuation or range conditions
- each setup must have its own evidence, metrics, governance, and audit trail

### Prior Research Failures You Must Respect

Do not repeat these paths under a new name.

1. Sweep family / Range Sweep Specialist
   - Completed and closed.
   - Context expansion and threshold variants did not solve the frequency
     problem.
   - Parameter tuning cannot force more high-quality trades from the same edge.

2. 5m sweep/reclaim feasibility
   - Quality passed, frequency failed.
   - 5m produced 61 trades vs 47 on 15m, only 1.30x, below the >=2x frequency
     gate.
   - ER 2.351, PF 6.63, WR 72.1%, but frequency not enough.

3. 15m signal plus 5m energy overlay
   - Failed.
   - 5m confirmation came too late.
   - Timeout rate 78-91%.
   - FALLBACK mode degraded ER from baseline.
   - Lesson: delayed lower-timeframe confirmation can confirm after the optimal
     entry has passed.

4. 5m multi-candle event setups
   - Compression fakeout reclaim and crowded unwind reversal both failed.
   - Event count increased, edge quality collapsed.
   - Compression best variant: negative ER, PF below acceptable gates.
   - Crowded unwind: severe negative ER and drawdown.

5. Absorption / CVD continuation
   - Failed.
   - CVD divergence was not predictive in BTC perpetuals.
   - TFI was not enough to rescue the thesis.
   - Lesson: CVD divergence should not be used as a primary edge without a new,
     highly constrained reason.

6. Crowded unwind / liquidation capture
   - Failed.
   - Force/liquidation events appear too fast for 15m decision timing.
   - Lesson: do not build an active-cascade capture setup unless the cadence and
     data support it.

7. Compression breakout and regime-reversal style research
   - Failed or weak.
   - Sequential state transitions were hard to catch at the current cadence.
   - State-level timing was often too late.

### Available Feature Families

The bot/research data can use deterministic historical features such as:

- Structure:
  - equal_lows / equal_highs
  - recent swing levels
  - ATR
  - EMA50/EMA200, including 4h trend context

- Flow:
  - TFI 60s / taker flow imbalance
  - aggtrade buckets
  - CVD / CVD divergence, but prior evidence is negative

- Derivatives:
  - open interest z-score / delta
  - funding percentile over 60d

- Liquidation / force-order context:
  - force_order_spike / force_order_decreasing where historical coverage
    permits
  - but force-order data should not be assumed reliable as a universal primary
    trigger

Important: current signal logic already uses several of these as confluence
after the sweep gate. The research question is whether there is a distinct,
non-sweep setup family, not whether to add more confluence to the current
runtime.

### Naive Candidate To Critique

An external brainstorming idea proposed a setup called:

```text
PRECISION_FLOW_ENTRY_FEASIBILITY_V1
```

Naive LONG concept:

- price is near equal_lows / support or pullback structure
- no valid liquidity sweep required
- flow confirms re-accumulation or continuation
- possible scoring:
  - close within +/- 1 ATR of equal_lows: required
  - CVD bullish divergence: +2.0
  - TFI > 0.08: +1.5
  - OI delta > 0 and z-score rising: +1.0
  - force_order_decreasing: +1.0
  - funding_pct_60d < 40: +0.5
  - EMA50_4h > EMA200_4h: +0.5
  - entry threshold >= 4.0

Internal consultation criticized this as too broad: a proxy stack rather than a
falsifiable setup. It may repeat failed absorption/crowded/compression paths.

Internal re-scope suggestions included:

1. `TREND_PULLBACK_REACCEPT_V1`
   - 4h trend alignment
   - pre-existing 15m structure level frozen before trigger
   - bounded pullback into that level
   - falling or non-expanding OI into pullback
   - 15m close re-accepts/reclaims the level
   - TFI supports the reclaim candle
   - CVD diagnostic-only

2. `BREAKOUT_RETEST_CONT_V1`
   - confirmed structural breakout
   - no entry on breakout candle
   - first controlled retest of broken level
   - entry on retest hold/reclaim
   - OI not crowded/chasing
   - TFI not opposing continuation

3. `RANGE_REACCEPT_OUTSIDE_VALUE_V1`
   - lower priority
   - flat/range regime
   - brief excursion outside mature range
   - fast re-acceptance back inside
   - risk: may be a disguised sweep/reclaim cousin

### What I Need From You

Please produce a rigorous expert memo. Be skeptical. Do not optimize for
enthusiasm.

Answer these questions:

1. Brutally critique the naive `Precision Flow Entry` idea.
   - hidden lookahead risks
   - ambiguous structure definitions
   - feature collinearity
   - proxy-feature traps
   - BTC perp microstructure issues
   - timing/cadence mismatch
   - data availability problems

2. Decide whether the idea should be:
   - rejected,
   - narrowed before testing,
   - or tested as a Research Lab feasibility milestone.

3. If narrowed, propose 1-3 falsifiable setup hypotheses.
   For each, include:
   - market structure thesis
   - counterparty or market mechanism
   - exact trigger timing compatible with 15m or 5m replay
   - required features
   - optional diagnostic features
   - exit/invalidation concept
   - target regimes
   - data requirements
   - likely failure modes
   - why it is different from failed absorption/crowded/compression/sweep paths

4. Take a hard position on CVD:
   - exclude entirely,
   - diagnostic-only,
   - or use only under a specific constrained definition.
   Justify the choice given prior failure evidence.

5. Propose the single best first Research Lab hypothesis card.
   Use this structure:

```text
hypothesis_id:
name:
status:
scope:
edge_rationale:
counterparty_or_market_mechanism:
required_data:
timeframe:
baseline_reference:
variables:
frozen_assumptions:
expected_observation:
acceptance_criteria:
kill_criteria:
failure_modes:
out_of_scope:
```

6. Define hard gates.
   Include at minimum:
   - minimum OOS trades
   - ER threshold
   - PF threshold
   - max drawdown threshold
   - OOS retention / walk-forward stability
   - cost sensitivity at 1x / 1.5x / 2x costs
   - overlap vs trial-00095
   - concentration by month/quarter
   - directional imbalance
   - timeout share

7. Define what counts as:
   - PASS
   - FAIL
   - INCONCLUSIVE
   - METHODOLOGY BUG

8. Include anti-overfit safeguards:
   - fixed protocol before run
   - chronological walk-forward
   - final untouched OOS block
   - coarse thresholds only
   - no post-hoc threshold rescue
   - matched baseline comparison
   - ablation tests that cannot be used to rescue the candidate

9. Give a do-not-build list:
   - ideas that are seductive but already falsified or too close to prior
     failures.

10. End with your final recommendation:
    - exact first hypothesis to test, or
    - reject this direction and propose a better one.

### Hard Constraints For Your Answer

- Do not suggest runtime integration.
- Do not suggest modifying `core/**`, `orchestrator.py`, `settings.py`,
  execution, risk, or live/PAPER runtime.
- Do not suggest live trading or paper deployment.
- Do not propose black-box ML in the execution path.
- Do not relax gates to make the candidate pass.
- Do not use generic trading advice.
- Ground every idea in falsifiable offline research design.

The output should be dense, technical, and audit-ready.

