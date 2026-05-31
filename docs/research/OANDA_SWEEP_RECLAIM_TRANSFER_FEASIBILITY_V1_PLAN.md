# OANDA_SWEEP_RECLAIM_TRANSFER_FEASIBILITY_V1_PLAN

**Date:** 2026-05-31
**Researcher:** Codex
**Type:** Quant Research Planning / Cross-market edge transfer feasibility
**Scope:** Planning only; no diagnostic implementation; no production changes

---

## Executive Summary

This plan defines a narrow diagnostic to test whether the price-action core of
the validated `btc-bot` sweep/reclaim edge can transfer to OANDA, starting with
`XAU_USD` H1. The goal is not to validate the older `smc-signal-bot` SMC
strategy. The older OANDA bot is an infrastructure reference only, mainly for
its OANDA connector and instrument context.

The transfer is intentionally treated as degraded. Trial-00095 used
crypto-native inputs such as TFI, CVD, open interest, funding, and force-order
data. OANDA spot/CFD data does not provide those surfaces in equivalent form.
The first OANDA diagnostic must therefore test only the transferable
price-action core: equal-level liquidity, sweep depth, reclaim confirmation,
ATR/range context, and realistic OANDA costs.

Pre-flight OANDA inventory is no longer blocked. `XAU_USD` H1 candles are
available through OANDA practice credentials, with 14,260 complete candles from
2024-01-01 to 2026-05-29 and zero OHLC integrity violations. Spread/cost
modeling remains a caveat because historical candle data is mid-price OHLC and
does not provide historical bid/ask spread per candle. The diagnostic must use
a conservative cost model with sensitivity checks.

Planned next step if approved: implement one research diagnostic,
`OANDA_XAUUSD_SWEEP_RECLAIM_TRANSFER_FEASIBILITY_V1`.

---

## 1. Scope Boundaries

### In Scope

- Inspect `btc-bot` validated sweep/reclaim research context.
- Use `trial-00095` as benchmark, not as a transferable guarantee.
- Use `smc-signal-bot` only as an OANDA connector/instrument reference.
- Define one OANDA diagnostic for `XAU_USD` H1.
- Test price-action-only sweep/reclaim transfer.
- Define realistic timing, costs, MFE accessibility, controls, and gates.

### Out of Scope

- No production code changes.
- No OANDA bot port.
- No live trading changes.
- No `settings.py` changes.
- No promotion logic.
- No diagnostic implementation in this planning milestone.
- No SMC OB/FVG/mitigation validation.
- No hybrid SMC plus btc-bot strategy.
- No multi-symbol expansion in the first diagnostic.
- No parameter tuning after seeing OANDA outcomes.

### Boundary Statement

This is not an SMC rescue. The `smc-signal-bot` repo currently demonstrates an
implemented OANDA/Telegram SMC signal bot, not decision-grade edge validation.
The research question here is whether the validated `btc-bot` price-action
sweep/reclaim core can transfer to `XAU_USD`.

---

## 2. Internal Source Inspection

### btc-bot Sources

| Source | Purpose | Relevant Finding |
| --- | --- | --- |
| `docs/QUANT_RESEARCH_OPERATING_MODEL.md` | Research authority | Requires timing discipline, MFE accessibility, controls, and pre-result invalidation gates. |
| `research_lab/reports/trial_00095_conditional_edge_attribution_v1.md` | Baseline attribution | Trial-00095 has ER 2.121, PF 4.216, WR 56.57%; TFI alignment is important. |
| `core/feature_engine.py` | Feature extraction | Equal levels and sweep/reclaim logic are OHLC-compatible; TFI/CVD/funding/OI/force-order features are crypto-specific. |
| `core/signal_engine.py` | Candidate generation | Direction, confluence, and gating depend partly on unavailable crypto-native features. |
| `docs/MILESTONE_TRACKER.md` | Prior lessons | Delayed confirmations and post-sweep SMC states failed due to MFE consumption and negative net returns. |

### smc-signal-bot Sources

| Source | Purpose | Relevant Finding |
| --- | --- | --- |
| `connectors/oanda_client.py` | OANDA reference | Existing OANDA REST integration pattern is available for future implementation reference. |
| `engine/signal_generator.py` | OANDA signal flow reference | Scans `EUR_USD`, `XAU_USD`, `BTC_USD`, but implements SMC scoring, not trial-00095. |
| `paper_trading/runner.py` | Paper loop reference | Provides paper-signal scaffolding, not decision-grade backtest evidence. |
| `paper_trading/analyzer.py` | Paper results analysis | Uses lightweight readiness thresholds; not enough for edge transfer proof. |
| `02-smc-conventions.md` | SMC scope | Explicitly framed the bot as signal/MVP work rather than historical backtest validation. |

### btc-smc-bot Sources

`btc-smc-bot` is historical context only. It should not be used to justify the
OANDA diagnostic unless a future planning milestone finds specific reusable
lessons. This plan does not depend on it.

---

## 3. OANDA Data Inventory Checkpoint

### Credential Status

OANDA practice access is available locally. No credentials are stored in this
planning document and no credential value is required for audit.

### Candle Inventory

| Field | Value |
| --- | --- |
| Instrument | `XAU_USD` |
| Granularity | `H1` |
| Source | OANDA practice REST API, mid-price candles |
| Start | 2024-01-01T23:00:00Z |
| End | 2026-05-29T20:00:00Z |
| Complete candles | 14,260 |
| Requests | 4 paginated requests |
| OHLC bad rows | 0 |
| Gaps > 24h | 129 |
| Gaps > 72h | 3 |
| Max gap | 74 hours |
| Data gate | PASS |

The gaps are expected to include OANDA market closures, weekends, and holidays.
The diagnostic must use timestamp-aware horizons and must not treat weekend
closures as missing intraday data.

### Instrument Availability

| Instrument | Inventory Status |
| --- | --- |
| `XAU_USD` | Enabled; historical H1 candles available |
| `EUR_USD` | Enabled; historical candles available; secondary inventory only |
| `BTC_USD` | Not enabled on this OANDA account |

### Spread / Cost Caveat

OANDA candle history provides mid OHLC, not historical bid/ask OHLC. Therefore
the first diagnostic must model costs conservatively rather than assume
historical spreads are known.

Primary cost model:

- `XAU_USD` round-trip cost: `0.05%`

Sensitivity model:

- Low cost: `0.03%`
- Primary cost: `0.05%`
- Stress cost: `0.10%`

If the candidate only passes at `0.03%` and fails at `0.05%`, the transfer is
not robust enough to continue.

---

## 4. Attribution-Informed Feature Map

Trial-00095 attribution shows that the accepted BTC trade population is not
pure OHLC price action. It uses a blend of sweep/reclaim, directional flow, and
crypto-native leverage/crowding features.

### Retained Features

| Feature | Trial-00095 Evidence | OANDA Availability | Transfer Action |
| --- | ---: | --- | --- |
| `sweep_depth_pct` | Corr vs R: 0.1362 | Yes, OHLC | Retain as primary transfer feature |
| Equal-level / range context | Core price-action setup | Yes, OHLC | Retain |
| Reclaim confirmation | Core price-action setup | Yes, OHLC | Retain |
| `atr14_pct` | Context feature, corr -0.0384 | Yes, OHLC | Retain as volatility context |
| EMA / trend regime | Regime context | Yes, OHLC | Retain as simple context only |
| `volume_z20` | Weak corr -0.0032 | Partial, tick volume only | Optional metadata, not primary gate |

### Lost or Degraded Features

| Feature | Trial-00095 Evidence | OANDA Availability | Impact |
| --- | ---: | --- | --- |
| `tfi_15m_prev` | Corr vs R: 0.2268; aligned ER 2.391 vs opposed ER 0.816 | No equivalent directional volume | Major degradation |
| `oi_change_24h_pct` | Corr vs R: 0.1270 | Not available on OANDA spot/CFD feed | Lost |
| `funding_rate` | Corr vs R: 0.1111 | Not available | Lost |
| Force orders / liquidations | Confluence input | Not available | Lost |
| CVD / aggTrades | Directional flow input | Not available | Lost |

### Transfer Implication

This is a degraded transfer of trial-00095, not a full replication. Expected
performance should be lower than BTC trial-00095. The diagnostic should not
expect ER near 2.1 unless controls and walk-forward strongly support it.

Pre-result expected range:

- Competitive OANDA transfer: ER 1.3 to 1.8 after costs.
- Marginal but interesting: ER 1.0 to 1.3 after costs with strong controls.
- Failed transfer: ER below 1.0 or median net return <= 0.

---

## 5. Transferability Matrix

| Component | btc-bot Source | OANDA Available? | Transfer Decision |
| --- | --- | --- | --- |
| Equal-level detection | OHLC | Yes | Transfer |
| Sweep detection | OHLC | Yes | Transfer |
| Sweep depth | OHLC | Yes | Transfer |
| Reclaim confirmation | OHLC | Yes | Transfer |
| ATR | OHLC | Yes | Transfer |
| EMA / trend state | OHLC | Yes | Transfer as context |
| Range width / compression | OHLC | Yes | Transfer as metadata |
| TFI | Binance aggTrades | No | Remove |
| CVD | Binance aggTrades | No | Remove |
| Funding | Binance futures | No | Remove |
| Open interest | Binance futures | No | Remove |
| Force orders | Binance futures | No | Remove |
| Liquidation state | Binance futures | No | Remove |
| Volume spike | Binance/volume | Partial tick-volume | Metadata only, not primary |
| Costs/spread | Exchange/broker | Partial | Conservative modeled cost |

If the diagnostic requires reintroducing unavailable crypto-specific features
or replacing them with unvalidated proxies, it is no longer a clean OANDA
transfer test.

---

## 6. Proposed Mechanism

### Diagnostic Name

`OANDA_XAUUSD_SWEEP_RECLAIM_TRANSFER_FEASIBILITY_V1`

### Mechanism Summary

Detect an equal-level liquidity area on `XAU_USD` H1, require a sweep beyond
the level and a close-based reclaim, then enter on the next bar after reclaim
confirmation. Measure returns from the entry candidate only, after conservative
OANDA costs.

### Observable Inputs

- `XAU_USD` H1 OANDA mid-price candles:
  - `time`
  - `open`
  - `high`
  - `low`
  - `close`
  - `volume` if available
- Derived OHLC indicators:
  - ATR14
  - equal-level clusters
  - sweep depth percent
  - reclaim close
  - range width
  - optional EMA context

### Deterministic Rule

For each completed H1 bar `i`:

1. Build equal-level liquidity candidates from prior completed bars only.
2. Detect sweep:
   - downside sweep: bar low crosses below known equal low level by required
     sweep buffer/depth.
   - upside sweep: bar high crosses above known equal high level by required
     sweep buffer/depth.
3. Detect reclaim:
   - downside sweep -> bullish reclaim if close returns above swept level plus
     reclaim buffer.
   - upside sweep -> bearish reclaim if close returns below swept level minus
     reclaim buffer.
4. Confirm signal at bar `i` close only if both sweep and reclaim are known.
5. Enter at bar `i+1` open or conservative proxy price.
6. Compute primary returns from `i+1`, not from the sweep/reclaim bar.

### Direction

- Sweep below equal lows with reclaim -> LONG candidate.
- Sweep above equal highs with reclaim -> SHORT candidate.

Given trial-00095 attribution, direction asymmetry must be measured explicitly.
BTC trial-00095 was strongly LONG-biased: LONG ER 2.377, SHORT ER -0.805. The
OANDA diagnostic must report direction splits rather than assuming symmetry.

### Non-Goals

- No OB/FVG/mitigation.
- No SMC sequence scoring.
- No AI/LLM gate.
- No OANDA order execution.
- No tuning against observed results.

---

## 7. Timing Model

| Field | Definition | Planned Value |
| --- | --- | --- |
| `level_known_bar` | Bar where equal-level liquidity is knowable from completed prior bars | Prior to sweep; must not include current/future bar in level construction |
| `detection_bar` | Bar where sweep and reclaim event occurs | Bar `i` |
| `sweep_bar` | Bar where level is crossed | Bar `i` |
| `reclaim_bar` | Bar where reclaim close is confirmed | Bar `i` close |
| `state_known_bar` | First bar where signal is knowable without future data | Bar `i` close |
| `confirmation_bar` | Same as reclaim confirmation | Bar `i` |
| `entry_candidate_bar` | First realistic entry after confirmation | Bar `i+1` |
| `label_available_bar` | Outcome horizon end | Bar `i+1+horizon` |
| `return_start_bar` | Bar for primary returns | Bar `i+1` |

Primary returns must start at `entry_candidate_bar`. Returns from
`detection_bar` are audit-only and may only be used to measure opportunity
consumed before realistic entry.

### Entry Price

Preferred diagnostic entry price:

- `entry_candidate_bar.open` if OANDA candle open is available and timestamp
  alignment is reliable.

Conservative fallback:

- `entry_candidate_bar.close` if using close-only replay simplifies
  implementation, but this must be labeled as later and more conservative.

The diagnostic must not enter on the same close that confirms reclaim unless a
separate order-timing proof is provided.

---

## 8. MFE Accessibility Design

For every candidate event:

### LONG Candidate

- `MFE_before_entry = max(high - detection_close)` from `detection_bar` through
  `entry_candidate_bar - 1`.
- `MFE_after_entry = max(high - entry_price)` from `entry_candidate_bar`
  through `entry_candidate_bar + horizon`.
- `MAE_after_entry = max(entry_price - low)` over the same post-entry horizon.

### SHORT Candidate

- `MFE_before_entry = max(detection_close - low)` from `detection_bar` through
  `entry_candidate_bar - 1`.
- `MFE_after_entry = max(entry_price - low)` from `entry_candidate_bar`
  through `entry_candidate_bar + horizon`.
- `MAE_after_entry = max(high - entry_price)` over the same post-entry horizon.

### Consumption Metric

`mfe_consumed_pct = MFE_before_entry / (MFE_before_entry + MFE_after_entry)`

STOP if median `mfe_consumed_pct > 70%`.

Target if the transfer is promising:

- median `mfe_consumed_pct < 60%`
- median net return after costs > 0
- post-entry ER > 1.3

### Horizon

Initial horizon:

- 5 H1 bars for direct comparison to earlier short-horizon diagnostics.
- 10 H1 bars as secondary sensitivity.

The primary result must be declared before implementation and must not be
changed after results are known.

---

## 9. Return and Cost Model

### Primary Return Metric

Primary metrics are measured from `entry_candidate_bar`:

- median net return after costs
- ER proxy
- profit factor proxy
- win rate
- MFE/MAE after entry
- fold stability

### Cost Model

Primary OANDA XAU cost assumption:

- round-trip cost: `0.05%`

Sensitivity:

- `0.03%`
- `0.05%`
- `0.10%`

Diagnostic verdict uses `0.05%` as the primary gate. `0.03%` can be reported
only as optimistic sensitivity. `0.10%` is the stress case.

### Spread Caveat

Historical OANDA mid candles do not encode the bid/ask spread paid at entry
and exit. A positive result that is not robust to `0.05%` round-trip cost is not
sufficient to continue.

---

## 10. Baseline Comparison

### BTC Baseline

Reference: `trial_00095_conditional_edge_attribution_v1.md`

| Metric | BTC trial-00095 |
| --- | ---: |
| Accepted trades | 274 |
| WF reference trades | 271 |
| ER | 2.121 |
| PF | 4.216 |
| WR | 56.57% |
| WF reference ER | 2.129 |
| WF reference PF | 4.663 |
| WF reference WR | 56.46% |

### OANDA Candidate Comparison

The diagnostic must compare:

- ER after OANDA costs.
- PF after OANDA costs.
- Win rate.
- Trade count.
- Direction splits.
- MFE consumed before entry.
- Fold stability.
- Control cohort superiority.
- Sensitivity to costs.

### Benchmark Interpretation

OANDA does not need to match BTC trial-00095 to be useful, because it could add
orthogonal trade frequency in a different market. However, it must remain
positive after realistic costs and must beat deterministic controls.

Pre-result benchmark rules:

- ER > 1.5 and PF > 1.5: strong transfer candidate.
- ER 1.3 to 1.5 with strong controls: explore.
- ER 1.0 to 1.3: marginal; require strong sample and fold stability.
- ER < 1.0: STOP.

---

## 11. Control Cohorts

Controls are defined before results.

### Control 1: Sweep Without Reclaim

- Equal level exists.
- Sweep occurs.
- No reclaim on detection bar.
- Entry at same relative timing.

Purpose: prove reclaim adds information beyond sweep alone.

### Control 2: Reclaim Without Prior Equal-Level Sweep

- Close crosses back through a local level proxy.
- No qualifying prior equal-level sweep.

Purpose: prove liquidity sweep context matters.

### Control 3: Random Offset Entry

- Deterministic offset from candidate entries, e.g. `+137` bars.
- Same direction distribution if possible.

Purpose: control for random market drift and session/regime bias.

### Control 4: Shifted Entry

- Same signal as main cohort.
- Entry delayed by `+2` bars and `+3` bars.

Purpose: test whether timing matters and whether the signal decays quickly.

### Control 5: Opposite Direction

- Same signal event.
- Enter opposite direction at the same entry bar.

Purpose: test directional information.

### Control 6: Shallow Sweep Control

- Equal level and reclaim exist.
- Sweep depth below main threshold.

Purpose: test whether depth threshold adds information.

### Control 7: Wide-Range / High-Volatility Control

- Candidate-like events in high ATR/range states.
- Same timing and cost model.

Purpose: test whether results are just volatility exposure.

### Control Invalidation

If any major control cohort beats the main cohort on primary ER at the
`0.05%` cost assumption, the mechanism is invalidated or must be reduced to an
inconclusive planning result.

---

## 12. Walk-Forward Design

The diagnostic should split the available OANDA `XAU_USD` H1 dataset into four
chronological folds where possible.

Proposed folds:

1. 2024-H1
2. 2024-H2
3. 2025
4. 2026-to-latest

If fold sizes are too uneven, the diagnostic may use four equal chronological
folds by candle count, but the chosen fold policy must be declared in the
diagnostic output and not changed after results.

Fold pass:

- median net return after costs > 0
- ER > 1.0
- sample count sufficient for that fold

EXPLORE requires at least 3 of 4 folds positive.

---

## 13. Data Quality Requirements

Before event detection:

- Verify candles are sorted by timestamp.
- Verify all timestamps are UTC.
- Verify OHLC integrity:
  - high >= open
  - high >= close
  - high >= low
  - low <= open
  - low <= close
- Preserve weekend/holiday gaps rather than forward-filling.
- Exclude incomplete current candle.
- Do not silently drop gaps; document gap counts.

If data fetch returns fewer than 10,000 complete H1 candles for the primary
window, diagnostic result is `DATA_INCONCLUSIVE` or STOP depending on missing
range.

---

## 14. Parameter Discipline

This diagnostic must not optimize thresholds against OANDA outcomes.

Initial parameter policy:

- Start from trial-00095-inspired sweep/reclaim definitions where transferable.
- Remove unavailable crypto-specific gates.
- Use a small, predeclared sensitivity grid only if needed to prove robustness,
  not to select a winner.

Allowed sensitivity dimensions:

- cost assumption: 0.03%, 0.05%, 0.10%
- horizon: 5 bars, 10 bars
- entry price: next open primary; next close conservative sensitivity

Not allowed:

- post-result tuning of sweep depth
- adding SMC filters after failure
- replacing TFI with discretionary volume proxies after seeing outcomes
- switching to a better symbol after XAU failure within the same diagnostic

---

## 15. Invalidation Criteria

### STOP Gates

STOP if any apply:

- Required OANDA H1 candle data becomes unavailable or inconsistent.
- Sample size < 100 events.
- Median net return after `0.05%` round-trip cost <= 0.
- ER after costs < 1.0.
- PF after costs < 1.2.
- Median MFE consumed before entry > 70%.
- Any major control cohort beats main cohort on ER.
- Walk-forward fewer than 2 of 4 folds positive.
- Signal requires future bars.
- Entry is measured from detection bar instead of entry candidate bar.
- Result only works under `0.03%` cost and fails under `0.05%`.
- Mechanism becomes SMC/OB/FVG/mitigation rather than sweep/reclaim transfer.

### EXPLORE Gates

EXPLORE if all apply:

- Sample size >= 200 events.
- Median net return after `0.05%` cost > 0.
- ER after costs > 1.3.
- PF after costs > 1.5.
- Median MFE consumed before entry < 60%.
- Main cohort beats all controls on ER.
- At least 3 of 4 folds positive.
- Direction splits do not reveal catastrophic one-sided failure unless a
  predeclared direction-only follow-up is recommended.

### INCONCLUSIVE Gates

INCONCLUSIVE if:

- Sample size 100-199 with positive but unstable results.
- ER 1.0 to 1.3 and controls are mixed.
- Spread/cost assumptions dominate the verdict.
- Fold results are mixed but not decisively negative.

---

## 16. Expected Diagnostic Artifacts

If approved, implementation should produce:

- Diagnostic script:
  - `research_lab/diagnostics/oanda_xauusd_sweep_reclaim_transfer_feasibility_v1.py`
- Markdown report:
  - `research_lab/reports/oanda_xauusd_sweep_reclaim_transfer_feasibility_v1.md`
- JSON artifact:
  - `research_lab/reports/oanda_xauusd_sweep_reclaim_transfer_feasibility_v1.json`
- Focused tests:
  - `tests/test_research_lab/test_oanda_xauusd_sweep_reclaim_transfer_feasibility_v1.py`

If the JSON artifact is large, do not commit it. Save it locally, document the
path, SHA256, and summary in the Markdown report, and commit only lightweight
reproducible artifacts.

---

## 17. Audit Questions for Claude

Claude should verify:

1. Did the plan separate SMC validation from btc-bot edge transfer?
2. Did the plan avoid treating `smc-signal-bot` as edge-validated?
3. Did the plan clearly identify unavailable crypto-native features?
4. Did the plan acknowledge this is a degraded transfer?
5. Did the plan include the OANDA data inventory result without exposing
   credentials?
6. Did the plan define a conservative spread/cost model?
7. Did the plan enforce returns from `entry_candidate_bar` only?
8. Did the plan include MFE accessibility with the 70% STOP threshold?
9. Did the plan define controls before results?
10. Did the plan avoid production code and full bot port scope creep?
11. Is the first diagnostic narrow enough?
12. Does the final recommendation follow from the available evidence?

---

## 18. Recommendation

## Recommendation: IMPLEMENT ONE DIAGNOSTIC

**Diagnostic name:** `OANDA_XAUUSD_SWEEP_RECLAIM_TRANSFER_FEASIBILITY_V1`

**Mechanism summary:** Transfer the OHLC-only sweep/reclaim core from
`btc-bot` to `XAU_USD` H1 on OANDA, excluding unavailable crypto-native
features and measuring post-entry returns after conservative OANDA costs.

**Timing:** equal levels known from prior completed bars; sweep and reclaim
confirmed at bar `i` close; entry at bar `i+1`; primary returns from bar `i+1`
only.

**Expected MFE accessibility:** target median MFE consumed before entry below
60%; STOP if above 70%.

**Estimated sample size:** unknown until diagnostic event reconstruction, but
the candle inventory has 14,260 H1 candles and should support a decision-grade
test if event frequency is not extremely sparse.

**Estimated timeline:** 3-5 days for diagnostic implementation, tests, and
report.

**Next:** Builder implements the research-only diagnostic after Claude approves
this planning document. No OANDA bot port, no SMC validation, and no production
changes are authorized by this plan.
