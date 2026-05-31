# OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1_PLAN

**Date:** 2026-05-31
**Researcher:** Codex
**Type:** Quant Research Planning / OANDA sweep-reclaim feasibility
**Scope:** Planning only; no diagnostic implementation; no production changes

---

## Executive Summary

This plan defines one research diagnostic for the OANDA `EUR_USD` `M15`
sweep/reclaim structure found in
`OANDA_SWEEP_RECLAIM_MARKET_STRUCTURE_RECONNAISSANCE_V1`. The prior
`XAU_USD H1` strict BTC transfer remains `STOP`; this plan does not reinterpret
that result and does not rescue the failed diagnostic.

The reconnaissance showed that OANDA sweep/reclaim structure is not absent.
The best planning candidate is `EUR_USD M15` same-bar close reclaim:

- Instrument: `EUR_USD`
- Timeframe: `M15`
- Reclaim window: `0` bars, same-bar close reclaim
- Structural candidates: `3,419`
- Reclaim rate: `14.29%`
- Median MFE consumed before realistic next-bar entry: `11.96%`
- Data quality: `PASS`

This is still a degraded transfer of the BTC `trial-00095` idea. OANDA lacks
TFI, CVD, open interest, funding, and force-order/liquidation data. The
diagnostic must therefore test whether the price-action structure alone has
tradable expectancy after realistic OANDA costs. It must not claim equivalence
to `trial-00095`.

Recommendation of this planning document: `IMPLEMENT ONE DIAGNOSTIC`.

---

## 1. Prior Context

### Closed OANDA Transfer Diagnostic

`OANDA_XAUUSD_SWEEP_RECLAIM_TRANSFER_FEASIBILITY_V1` tested strict BTC-style
transfer on `XAU_USD H1` and correctly returned `STOP`.

Key results:

| Metric | Value |
| --- | ---: |
| Main events | 11 |
| ER proxy | 0.6581 |
| Profit factor proxy | 16.6979 |
| Win rate | 72.73% |
| Median net return at 0.05% cost | 0.2868% |
| Median MFE consumed | 16.54% |
| Positive folds | 1 / 4 |
| STOP reasons | sample < 100; ER < 1.0; fewer than 2 positive folds |

The result remains valid for strict `XAU_USD H1` BTC-style transfer.

### Reconnaissance Finding

`OANDA_SWEEP_RECLAIM_MARKET_STRUCTURE_RECONNAISSANCE_V1` showed that the STOP
was not caused by absence of OANDA sweep/reclaim structure. It was caused by
strict transfer assumptions: `XAU_USD H1`, BTC-like depth thresholding, and a
definition that collapsed the sample.

Reconnaissance table for same-bar reclaim:

| Instrument | TF | Same-bar reclaims | Reclaim rate | Median MFE consumed |
| --- | --- | ---: | ---: | ---: |
| `EUR_USD` | `H1` | 878 | 15.53% | 13.90% |
| `EUR_USD` | `M15` | 3,419 | 14.29% | 11.96% |
| `EUR_USD` | `M30` | 1,800 | 15.40% | 13.04% |
| `XAU_USD` | `H1` | 733 | 13.76% | 17.24% |
| `XAU_USD` | `M15` | 3,294 | 14.30% | 12.70% |
| `XAU_USD` | `M30` | 1,569 | 14.08% | 13.91% |

The planning candidate is `EUR_USD M15` because it has the largest same-bar
decision-grade sample and the lowest median MFE consumed among the pre-declared
instrument/timeframe combinations.

---

## 2. Scope Boundaries

### In Scope

- Plan exactly one diagnostic:
  `OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1`.
- Use `EUR_USD` only.
- Use `M15` only.
- Use same-bar close reclaim only.
- Define deterministic OHLC-only sweep/reclaim rules.
- Define entry timing, cost model, MFE accessibility, controls, walk-forward,
  and invalidation gates before implementation.
- Compare results to BTC `trial-00095` as benchmark, not as a guaranteed
  target.

### Out of Scope

- No diagnostic code in this milestone.
- No production code.
- No OANDA bot port.
- No live or paper trading change.
- No `settings.py` change.
- No SMC OB/FVG/mitigation logic.
- No hybrid SMC plus btc-bot signal.
- No multi-instrument diagnostic.
- No XAU retry in this milestone.
- No parameter tuning after diagnostic results.
- No claim that OANDA has edge before a full diagnostic.

### Boundary Statement

This is not an SMC rescue and not a retry of the failed `XAU_USD H1`
diagnostic. It is a new, narrower diagnostic plan derived from a separate
market-structure reconnaissance that found decision-grade `EUR_USD M15`
same-bar reclaim structure.

---

## 3. OANDA Data Inventory

### Frozen Dataset Target

| Field | Value |
| --- | --- |
| Instrument | `EUR_USD` |
| Granularity | `M15` |
| Source | OANDA practice REST API, mid-price candles |
| Start | 2024-01-01T22:00:00Z |
| End | 2026-05-29T20:45:00Z |
| Complete candles | 59,989 |
| OHLC bad rows | 0 |
| Duplicate timestamps | 0 |
| Gaps > 72h | 0 |
| Max gap | 49.25 hours |
| Data gate | PASS |

The diagnostic should use the same date range as reconnaissance unless the
implementation refreshes OANDA data. If refreshed data extends the end date,
the diagnostic must report both the planned range and actual fetched range.

### Candle Semantics

OANDA historical candles are mid-price OHLC. They do not include historical
bid/ask spread per candle. The diagnostic must model transaction costs
explicitly and run cost sensitivity.

---

## 4. Attribution-Informed Feature Map

The BTC `trial-00095` edge is not pure OHLC price action. The accepted-trade
attribution diagnostic found important crypto-native contributors that are not
available on OANDA.

### Retained Features

| Feature | BTC evidence | OANDA availability | Decision |
| --- | ---: | --- | --- |
| Equal-level liquidity | Core setup | OHLC available | Retain |
| Sweep/reclaim state | Core setup | OHLC available | Retain |
| Sweep depth | Corr vs R: 0.1362 | OHLC available | Retain with OANDA-specific threshold |
| ATR context | Corr vs R: -0.0384 | OHLC available | Retain |
| Range width | Context feature | OHLC available | Retain as metadata |
| Session | Accepted trades split by session | Timestamp available | Retain as metadata |

### Lost or Degraded Features

| Feature | BTC evidence | OANDA availability | Impact |
| --- | ---: | --- | --- |
| `tfi_15m_prev` | Corr vs R: 0.2268; aligned ER 2.391 vs opposed ER 0.816 | Not available | Major degradation |
| CVD | Directional flow input | Not available | Lost |
| Open interest | Corr vs R: 0.1270 | Not available | Lost |
| Funding | Corr vs R: 0.1111 | Not available | Lost |
| Force orders/liquidations | Crypto leverage input | Not available | Lost |
| Exchange volume | BTC exchange volume | OANDA tick volume only | Not primary |

### Expected Degradation

This diagnostic should not expect BTC `trial-00095` performance. Pre-result
expectations:

- Strong OANDA transfer: ER > 1.3 and PF > 1.5 after costs.
- Marginal transfer: ER 1.0 to 1.3 with stable folds and controls beaten.
- Failed transfer: ER < 1.0, median net <= 0, unstable folds, or control
  outperformance.

---

## 5. Transferability Matrix

| Component | BTC / prior source | OANDA `EUR_USD M15` | Decision |
| --- | --- | --- | --- |
| Equal-level detection | `core/feature_engine.py` | Available from OHLC | Transfer |
| Sweep detection | `core/feature_engine.py` | Available from OHLC | Transfer |
| Reclaim close | `core/feature_engine.py` | Available from OHLC | Transfer |
| Sweep depth percent | BTC threshold incompatible | Available from OHLC | Redefine for OANDA |
| ATR buffers | BTC/OANDA diagnostics | Available from OHLC | Retain |
| Entry timing | Research timing model | Next bar open | Retain |
| TFI/CVD | Binance aggTrades | Not available | Remove |
| Funding/OI | Binance futures | Not available | Remove |
| Force orders | Binance futures | Not available | Remove |
| Costs | Exchange/broker | Mid candles only | Model cost |

---

## 6. Proposed Mechanism

### Diagnostic Name

`OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1`

### Mechanism Summary

Detect a prior equal-level liquidity area on `EUR_USD M15`. If a completed bar
sweeps below/above that level and closes back through the level with a
same-bar reclaim buffer, enter at the next bar open in the reversal direction.
Measure returns only from the next bar open.

### Frozen Planning Decisions

| Decision | Frozen Value | Rationale |
| --- | --- | --- |
| Instrument | `EUR_USD` | Best reconnaissance candidate; cleaner OANDA data than XAU |
| Timeframe | `M15` | Largest same-bar sample; compatible with BTC 15m operating cadence |
| Reclaim window | `0` bars | Earliest knowable reclaim; avoids delayed MFE consumption |
| Entry price | Next bar open (`i+1 open`) | Realistic after bar `i` close confirmation |
| Primary cost | 0.015% round trip | Conservative EUR_USD mid-point cost estimate |
| Cost sensitivity | 0.010%, 0.015%, 0.025% | Low/base/stress EUR_USD costs |
| Primary horizon | 5 bars | 75 minutes; comparable to short-horizon reversal test |
| Secondary horizon | 10 bars | Sensitivity only |

### Sweep Depth Threshold

Frozen diagnostic threshold:

- `min_sweep_depth_pct = 0.0003` or `0.03%`

Rationale:

- Reconnaissance `EUR_USD M15` depth distribution:
  - p10: 0.02%
  - p25: 0.03%
  - p50: 0.04%
  - p75: 0.06%
  - p90: 0.09%
- BTC trial-00095 threshold around 0.649% is structurally incompatible with
  `EUR_USD M15`.
- p25 preserves a decision-grade sample while filtering the smallest structural
  scratches.
- This threshold is selected from market-structure distribution only, before
  any OANDA return diagnostic.

No post-result threshold relaxation is allowed. The diagnostic may report
descriptive depth buckets, but the primary result must use `0.03%`.

### ATR and Equal-Level Parameters

Primary diagnostic parameters:

- `atr_period = 14`
- `equal_level_lookback = 50`
- `equal_level_tol_atr = 0.09`
- `sweep_buf_atr = 0.46`
- `sweep_proximity_atr = 0.40`
- `reclaim_buf_atr = 0.07`
- `wick_min_atr = 0.20` as metadata, not a hard reclaim gate
- `level_min_age_bars = 5`
- `min_hits = 3`

Rationale:

- These values preserve the structure definition used in the OANDA
  reconnaissance so the baseline sample remains interpretable.
- The only OANDA-specific threshold introduced for the diagnostic is
  `min_sweep_depth_pct = 0.03%`.

### Reclaim Confirmation Rule

For downside sweep / long reversal candidate:

- prior equal low level known before bar `i`
- bar `i` low crosses below level by `sweep_buf_atr * ATR`
- bar `i` close is greater than `level + reclaim_buf_atr * ATR`
- sweep depth percent is at least `0.03%`
- state is known only after bar `i` closes

For upside sweep / short reversal candidate:

- prior equal high level known before bar `i`
- bar `i` high crosses above level by `sweep_buf_atr * ATR`
- bar `i` close is less than `level - reclaim_buf_atr * ATR`
- sweep depth percent is at least `0.03%`
- state is known only after bar `i` closes

The reclaim buffer is buffered, not exact. It uses `0.07 ATR` to match the
reconnaissance measurement. Exact reclaim may be reported as descriptive
metadata only and must not become the primary result.

### Entry and Exit Measurement

Primary entry:

- entry at bar `i+1 open`

Primary outcome:

- exit at bar `i+1+5 close`

Secondary outcome:

- exit at bar `i+1+10 close`

Risk/R model:

- Long stop/invalidation reference: sweep low minus `0.05 * ATR`.
- Short stop/invalidation reference: sweep high plus `0.05 * ATR`.
- `risk_pct = abs(entry_price - stop_reference) / entry_price`.
- R return = net return percent divided by `risk_pct`.
- Events with non-positive risk are invalid and excluded.
- Raw net return percent must also be reported.

This makes ER closer to a tradable risk-normalized measure instead of a
fixed-percent proxy.

---

## 7. Timing Model

| Field | Definition | Value |
| --- | --- | --- |
| `level_known_bar` | Last prior bar used to form equal level | `i-1` |
| `detection_bar` | Bar that sweeps the prior equal level | `i` |
| `reclaim_bar` | Bar that closes back through reclaim buffer | `i` |
| `state_known_bar` | First moment reclaim state is knowable | bar `i` close |
| `confirmation_bar` | Bar confirming sweep + same-bar reclaim | `i` |
| `entry_candidate_bar` | Earliest realistic entry after confirmation | `i+1` |
| `label_available_bar` | Outcome horizon close | `i+1+5` primary |
| `return_start_bar` | Bar from which primary returns start | `i+1` |

Critical rule:

Primary returns must start at `entry_candidate_bar`. Detection-bar movement may
be used only for MFE-before-entry audit metrics.

---

## 8. MFE Accessibility Design

For every main and control event:

- `MFE_before_entry`: favorable move from `detection_bar` close through
  `entry_candidate_bar - 1`.
- `MFE_after_entry`: favorable move from `entry_candidate_bar` open through
  primary horizon.
- `MAE_after_entry`: adverse move from `entry_candidate_bar` open through
  primary horizon.
- `total_mfe = MFE_before_entry + MFE_after_entry`.
- `mfe_consumed_pct = MFE_before_entry / total_mfe`.
- `entry_to_mfe_bars`: bar offset of post-entry max favorable excursion.

STOP gate:

- Median `mfe_consumed_pct > 70%`.

EXPLORE target:

- Median `mfe_consumed_pct < 60%`.

Reconnaissance baseline:

- `EUR_USD M15` same-bar close reclaim median MFE consumed: `11.96%`.

The diagnostic must verify whether this remains true after the frozen
`0.03%` depth threshold and next-open entry.

---

## 9. Return and Cost Model

### Price Source

OANDA candles are mid-price OHLC. The diagnostic must not pretend historical
bid/ask spread is known.

### Cost Assumptions

| Scenario | Round-trip cost |
| --- | ---: |
| Low | 0.010% |
| Primary | 0.015% |
| Stress | 0.025% |

Primary gates use `0.015%`.

If the mechanism passes only at `0.010%` and fails at `0.015%`, it is not
robust enough to proceed.

### Metrics

Primary metrics:

- event count
- mean R / ER
- median R
- median net return percent
- profit factor on R returns
- win rate
- median MFE consumed
- fold stability
- control cohort comparison

Secondary metrics:

- raw gross return percent
- 10-bar horizon sensitivity
- direction split
- session split
- depth bucket attribution

---

## 10. Baseline Comparison

| Metric | BTC trial-00095 | Planned OANDA EUR_USD M15 |
| --- | ---: | ---: |
| Instrument | BTCUSDT perpetual | EUR_USD OANDA |
| Timeframe | 15m | M15 |
| Accepted/event sample | 274 accepted BTC trades | Recon baseline 3,419 candidates |
| ER | 2.121 | Unknown |
| PF | 4.216 | Unknown |
| Win rate | 56.57% | Unknown |
| TFI available | Yes | No |
| OI/funding available | Yes | No |
| Force orders available | Yes | No |
| Median MFE consumed | N/A for baseline attribution | Recon baseline 11.96% |

Expected result should be lower than BTC if the transfer works at all. The
diagnostic is worth implementing only because the structure sample and MFE
accessibility are decision-grade.

---

## 11. Control Cohorts

Controls are pre-defined before results. The diagnostic must compute the same
cost, horizon, R model, MFE accessibility, and folds for controls whenever
applicable.

### Control 1: Sweep Without Reclaim

- Equal-level sweep occurs.
- Same-bar close reclaim does not occur.
- Entry at `i+1 open` in reversal direction.
- Purpose: test whether reclaim adds information beyond sweep.

### Control 2: Reclaim Without Equal-Level Sweep

- Local prior high/low is swept and reclaimed.
- No equal-level cluster existed before the event.
- Entry at `i+1 open`.
- Purpose: test equal-level contribution.

### Control 3: Random Offset Entry

- Use main event timestamps shifted by `+137` bars.
- Same direction as source event.
- Entry at shifted event `+1 open`.
- Purpose: control random timing.

### Control 4: Shifted Entry +2 Bars

- Same main event detection.
- Entry delayed to `i+3 open`.
- Purpose: test timing sensitivity.

### Control 5: Shifted Entry +3 Bars

- Same main event detection.
- Entry delayed to `i+4 open`.
- Purpose: test whether edge decays quickly.

### Control 6: Opposite Direction

- Same main event detection.
- Enter opposite direction at `i+1 open`.
- Purpose: test directional information.

### Control 7: Shallow Sweep Control

- Equal-level sweep and same-bar reclaim.
- Sweep depth below `0.03%` but above minimal structural floor `0.01%`.
- Purpose: test whether depth threshold adds information.

### Control 8: Wide-Range / High-Volatility Control

- Main event rule, but prior 50-bar range width in top quartile.
- Purpose: test whether high-volatility context dominates the signal.

Decision control rule:

- A control must have at least 25 events to count as decision-grade
  outperformance.
- Smaller controls are reported as informational only.

---

## 12. Walk-Forward Design

Use four chronological folds over the OANDA data range:

| Fold | Period |
| --- | --- |
| Fold 1 | 2024-01-01 to 2024-07-01 |
| Fold 2 | 2024-07-01 to 2025-01-01 |
| Fold 3 | 2025-01-01 to 2026-01-01 |
| Fold 4 | 2026-01-01 to latest available |

EXPLORE requires at least 3 of 4 folds positive.

STOP triggers if fewer than 2 of 4 folds are positive.

Fold positive definition:

- fold event count >= 25
- fold median net return > 0
- fold ER > 1.0

---

## 13. Data Quality Requirements

Diagnostic must report:

- instrument
- granularity
- source
- candle count
- first and last timestamp
- OHLC bad rows
- duplicate timestamps
- gaps above expected OANDA market closures
- max gap duration
- data gate

DATA_BLOCKED if:

- fewer than 18 months of `EUR_USD M15` candles
- OHLC bad rows > 0
- duplicate timestamps > 0
- data gaps prevent reliable M15 sequencing
- OANDA credentials/data access unavailable

No credentials may be printed, committed, or included in artifacts.

---

## 14. Parameter Discipline

Frozen before implementation:

| Parameter | Value |
| --- | ---: |
| Instrument | `EUR_USD` |
| Timeframe | `M15` |
| Reclaim window | `0` bars |
| `min_sweep_depth_pct` | 0.03% |
| `reclaim_buf_atr` | 0.07 |
| `entry_price` | next bar open |
| Primary cost | 0.015% |
| Primary horizon | 5 bars |

Allowed descriptive sensitivity:

- cost: 0.010%, 0.015%, 0.025%
- horizon: 5 bars primary, 10 bars secondary
- direction split
- session split
- depth buckets

Not allowed:

- changing `min_sweep_depth_pct` after results
- changing reclaim buffer after results
- selecting 5-bar reclaim because it has more events
- adding SMC filters
- adding session filters after seeing outcomes
- switching to XAU or M30/M15 alternatives after seeing outcomes
- promoting any result to runtime

---

## 15. Invalidation Criteria

### STOP Gates

Trigger `STOP` if any major gate fires:

- sample size < 100
- median net return <= 0 after 0.015% cost
- ER < 1.0
- profit factor < 1.2
- median MFE consumed > 70%
- any decision-grade control cohort beats main on ER
- fewer than 2 of 4 folds positive
- result depends on a non-primary cost/horizon to look viable
- signal requires future bars or detection-bar returns
- primary event count collapses unexpectedly below 200 after frozen threshold

### EXPLORE Gates

Return `EXPLORE` only if all are true:

- sample size >= 200
- median net return > 0 after 0.015% cost
- ER > 1.3
- profit factor > 1.5
- median MFE consumed < 60%
- main cohort beats all decision-grade controls on ER
- at least 3 of 4 folds positive
- timing model verified with entry at `i+1 open`

### INCONCLUSIVE Gates

Return `INCONCLUSIVE` if:

- event count is between 100 and 199
- ER is between 1.0 and 1.3 with stable but weak folds
- folds are mixed but no hard STOP gate fires
- controls are too small to decide
- cost sensitivity is ambiguous

---

## 16. Expected Diagnostic Artifacts

If this plan is approved, the next implementation milestone should produce:

- `research_lab/diagnostics/oanda_eurusd_m15_sweep_reclaim_feasibility_v1.py`
- `research_lab/reports/oanda_eurusd_m15_sweep_reclaim_feasibility_v1.md`
- `research_lab/reports/oanda_eurusd_m15_sweep_reclaim_feasibility_v1.json`
- `tests/test_research_lab/test_oanda_eurusd_m15_sweep_reclaim_feasibility_v1.py`

Report must include:

- executive summary with one recommendation
- data quality
- timing model verification
- main cohort metrics
- all control cohort metrics
- MFE accessibility
- walk-forward folds
- cost sensitivity
- BTC baseline comparison
- invalidation gate evaluation
- JSON SHA256

If JSON artifact exceeds GitHub practicality limits, do not commit it. Store it
locally and document path, SHA256, and summary in the markdown report.

---

## 17. Audit Questions for Claude

1. Does the plan preserve the prior `XAU_USD H1` STOP result?
2. Does the plan avoid SMC rescue?
3. Is the mechanism exactly one: `EUR_USD M15` same-bar reclaim?
4. Are instrument, timeframe, reclaim window, depth threshold, entry price,
   reclaim buffer, cost, and horizon frozen before results?
5. Is the `0.03%` sweep depth threshold justified from reconnaissance structure
   rather than returns?
6. Are primary returns measured from `entry_candidate_bar`, not detection?
7. Is MFE accessibility included with the 70% STOP threshold?
8. Are controls pre-defined before implementation?
9. Are STOP / EXPLORE / INCONCLUSIVE gates clear?
10. Does the plan avoid production changes and promotion?
11. Does the plan acknowledge degraded transfer from lost TFI/OI/funding/force
    order data?
12. Is the recommendation narrow enough for one diagnostic?

---

## Recommendation: IMPLEMENT ONE DIAGNOSTIC

**Diagnostic name:** `OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1`

**Mechanism summary:** `EUR_USD M15` equal-level sweep with same-bar buffered
close reclaim, entry at next bar open, returns measured from entry only.

**Timing:** detection and reclaim on bar `i`; state known at bar `i` close;
entry at bar `i+1 open`.

**Expected MFE accessibility:** reconnaissance baseline median MFE consumed
`11.96%`, target < `60%`, STOP if > `70%`.

**Estimated sample size:** reconnaissance baseline `3,419` same-bar reclaim
candidates before the frozen `0.03%` depth threshold; expected diagnostic
sample remains decision-grade if >= `200`.

**Estimated timeline:** 3-5 days for diagnostic implementation after planning
audit approval.

**Next:** Codex implements the diagnostic only if Claude approves this planning
document and the user confirms the implementation milestone.
