# OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1_PLAN

**Date:** 2026-06-01
**Researcher:** Codex
**Type:** Quant Research Planning / OANDA session edge feasibility
**Scope:** Planning only; no diagnostic implementation; no production changes

---

## Executive Summary

This plan defines one research diagnostic for the strongest OANDA-native
session structure found in `OANDA_SESSION_EDGE_RECONNAISSANCE_V1`:
`ASIA_RANGE_LONDON_BREAKOUT` on `EUR_USD M15`.

The mechanism is not a sweep/reclaim rescue. Prior OANDA sweep/reclaim
diagnostics remain invalidated:

- `XAU_USD H1` strict BTC transfer: `STOP` due to sample collapse.
- `EUR_USD M15` sweep/reclaim: `STOP` due to negative expectancy and control
  outperformance.

The new research question is whether a forex-native session structure has
tradable expectancy:

> Build the full Asia range from `00:00-07:00 UTC`, wait for a close-confirmed
> London breakout during `07:00-09:00 UTC`, enter at the next bar open, and
> measure returns only from that realistic entry.

Reconnaissance showed strong structure:

| Metric | Result |
| --- | ---: |
| Instrument/timeframe | `EUR_USD M15` |
| Candidate events | 424 |
| Events/year | 176.4 |
| Follow-through | 84.43% |
| False breakout | 18.16% |
| Median MFE consumed | 11.54% |
| Stable folds | 4 / 4 |

The reconnaissance does not prove profitability. This plan freezes the exact
diagnostic rules, controls, cost model, walk-forward gates, and invalidation
criteria needed to test whether the structure survives realistic entry and
costs.

Recommendation of this planning document: `IMPLEMENT ONE DIAGNOSTIC`.

---

## 1. Prior Context

### OANDA Sweep/Reclaim Transfer Is Closed

`OANDA_XAUUSD_SWEEP_RECLAIM_TRANSFER_FEASIBILITY_V1` tested strict BTC-style
sweep/reclaim transfer on `XAU_USD H1` and returned `STOP`.

Key failure mode:

| Metric | Result |
| --- | ---: |
| Main events | 11 |
| ER | 0.66 |
| Positive folds | 1 / 4 |
| Main STOP reasons | sample < 100; ER < 1.0; fewer than 2 positive folds |

`OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1` tested a narrower
`EUR_USD M15` same-bar sweep/reclaim structure and also returned `STOP`.

Key failure mode:

| Metric | Result |
| --- | ---: |
| Main events | 1,547 |
| ER | -0.2226 |
| Profit factor | 0.7146 |
| Win rate | 42.79% |
| Median net | -0.0159% |
| Median MFE consumed | 11.63% |
| Positive folds | 0 / 4 |

The EUR diagnostic proved timing was not the problem. The structure was
accessible, but expectancy was negative after costs and controls beat the main
cohort. That invalidates OANDA sweep/reclaim as a transfer family.

### Session Reconnaissance Opened a New Family

`OANDA_SESSION_EDGE_RECONNAISSANCE_V1` intentionally avoided sweep/reclaim and
measured forex-native session structure. It compared four pre-declared
candidates:

1. `ASIA_RANGE_LONDON_BREAKOUT`
2. `LONDON_OPEN_RANGE_BREAKOUT`
3. `NY_REVERSAL_AFTER_LONDON_EXTENSION`
4. `ROLLOVER_FADE_OR_AVOIDANCE`

All four candidates were structurally viable, but `ASIA_RANGE_LONDON_BREAKOUT`
ranked highest:

| Rank | Candidate | Count | FT | FB | MFE consumed | Folds |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `ASIA_RANGE_LONDON_BREAKOUT` | 424 | 84.43% | 18.16% | 11.54% | 4 / 4 |
| 2 | `NY_REVERSAL_AFTER_LONDON_EXTENSION` | 367 | 84.74% | 19.07% | 16.46% | 4 / 4 |
| 3 | `LONDON_OPEN_RANGE_BREAKOUT` | 587 | 79.90% | 25.21% | 14.12% | 4 / 4 |
| 4 | `ROLLOVER_FADE_OR_AVOIDANCE` | 228 | 82.46% | 28.51% | 36.36% | 4 / 4 |

Sequential research path:

1. Test `ASIA_RANGE_LONDON_BREAKOUT`.
2. If it returns `STOP`, consider `NY_REVERSAL_AFTER_LONDON_EXTENSION`.
3. If both stop, return to multi-asset crypto expansion.

---

## 2. Scope Boundaries

### In Scope

- Plan exactly one diagnostic:
  `OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1`.
- Use `EUR_USD` only.
- Use `M15` only.
- Use full Asia range `00:00-07:00 UTC`.
- Use London breakout window `07:00-09:00 UTC`.
- Freeze breakout buffer, entry, exit horizon, cost model, risk model,
  controls, walk-forward folds, and invalidation gates before implementation.
- Measure returns from realistic entry only.
- Measure MFE accessibility before and after entry.
- Compare against BTC `trial-00095` honestly as benchmark, not target.

### Out of Scope

- No diagnostic code in this milestone.
- No production code.
- No OANDA bot port.
- No live or paper trading changes.
- No `settings.py` change.
- No Optuna or broad auto-search.
- No SMC OB/FVG/mitigation.
- No sweep/reclaim rescue.
- No NY reversal diagnostic in this milestone.
- No multi-candidate diagnostic.
- No compression filter after reconnaissance.
- No weekday/session filter after results.
- No promotion or runtime activation.

### Boundary Statement

This is a new OANDA-native session edge family. It tests time-of-day liquidity
expansion from the Asia range into the London open. It does not reuse
equal-level sweep/reclaim logic and must not be interpreted as a rescue of
failed OANDA sweep/reclaim diagnostics.

---

## 3. OANDA Data Inventory

Use the same `EUR_USD M15` candle inventory validated during session
reconnaissance unless the implementation refreshes OANDA data. If refreshed,
the diagnostic must report both planned and actual date ranges.

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

OANDA historical candles are mid-price OHLC. They do not include historical
bid/ask spread per candle. The diagnostic must model costs explicitly.

No credentials may be printed, committed, logged in reports, or embedded in
artifacts.

---

## 4. Attribution-Informed Feature Map

This is not a full transfer of BTC `trial-00095`. It is an OANDA-native
session diagnostic that keeps only OHLC and timing information.

### Lost BTC Features

| Feature | BTC evidence | OANDA availability | Impact |
| --- | ---: | --- | --- |
| `tfi_15m_prev` | Corr vs R: 0.2268; aligned ER 2.391 vs opposed ER 0.816 | Not available | Major loss |
| CVD | Directional flow input | Not available | Lost |
| Open interest | Corr vs R: 0.1270 | Not available | Lost |
| Funding | Corr vs R: 0.1111 | Not available | Lost |
| Force orders/liquidations | Crypto leverage input | Not available | Lost |

### Retained / New OANDA-Native Inputs

| Input | Source | Role |
| --- | --- | --- |
| OHLC candles | OANDA M15 | Range, breakout, ATR, returns |
| UTC timestamp | OANDA candle time | Session alignment |
| Asia range | 00:00-07:00 UTC OHLC | Source range |
| London breakout close | 07:00-09:00 UTC close | Detection state |
| ATR14 | OHLC-derived | Buffer, MFE threshold, risk context |
| Weekday/session metadata | Timestamp-derived | Reporting only, not primary filter |

### Expected Degradation / Difference

This diagnostic should not expect BTC `trial-00095` performance. It is not
trying to replicate BTC microstructure. It tests a different causal path:

- BTC edge: sweep/reclaim plus crypto-native flow/crowding data.
- OANDA session edge: Asia range compression and London institutional
  expansion.

Expected ER ranges if the edge exists:

- Strong OANDA session edge: ER 1.5 to 2.0.
- Marginal but interesting: ER 1.0 to 1.5.
- Failed session edge: ER < 1.0 or median net <= 0.

---

## 5. Transferability Matrix

| Component | BTC / prior source | OANDA session diagnostic | Decision |
| --- | --- | --- | --- |
| Equal-level sweep | Failed OANDA transfer | Not used | Exclude |
| Same-bar reclaim | Failed OANDA transfer | Not used | Exclude |
| TFI/CVD | Binance aggTrades | Not available | Exclude |
| Funding/OI | Binance futures | Not available | Exclude |
| Force orders | Binance futures | Not available | Exclude |
| ATR14 | OHLC | Available | Retain |
| Range construction | OHLC | Available | Retain |
| Close-confirmed breakout | OHLC | Available | Retain |
| Session timing | Timestamp | Available | Primary mechanism |
| Cost model | Broker/exchange | Historical spread unavailable | Model explicitly |

This mechanism is not a degraded sweep/reclaim transfer. It is an
OANDA-specific session structure test using only available deterministic data.

---

## 6. Proposed Mechanism

### Diagnostic Name

`OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1`

### Mechanism Summary

For each trading day, build the complete Asia range from `00:00-07:00 UTC`.
During the London open window `07:00-09:00 UTC`, detect the first M15 candle
that closes above the Asia high plus a small ATR buffer or below the Asia low
minus the same buffer. Enter in the breakout direction at the next M15 bar
open. Measure primary returns from that entry only.

### Frozen Decisions

| Decision | Frozen Value | Rationale |
| --- | --- | --- |
| Instrument | `EUR_USD` | Primary instrument from reconnaissance |
| Timeframe | `M15` | Reconnaissance sample and timing basis |
| Source range | Asia `00:00-07:00 UTC` | Full session, no optimization |
| Breakout window | London `07:00-09:00 UTC` | Fixed from reconnaissance |
| Breakout buffer | `0.05 * ATR14` | Small noise filter, avoids exact micro-breaks |
| Entry | `i+1 open` | Realistic after close confirmation |
| Primary horizon | 5 bars | 75 minutes; aligned with prior diagnostics |
| Secondary horizon | 8 bars | Matches reconnaissance follow-through window |
| Tertiary horizon | 10 bars | Optional sensitivity only |
| Risk reference | Opposite Asia extreme plus `0.05 * ATR14` | Natural range breakout invalidation |
| Primary cost | 0.015% round trip | Conservative EUR_USD modeled cost |
| Cost sensitivity | 0.010%, 0.015%, 0.020% | Low/base/stress |
| Compression filter | None | Avoid post-reconnaissance filter creep |

### Deterministic Rule

For each date `D`:

1. Use completed `EUR_USD M15` bars from `00:00-07:00 UTC`.
2. Compute:
   - `asia_high = max(high)`
   - `asia_low = min(low)`
   - `asia_mid = (asia_high + asia_low) / 2`
   - `atr14` available at each London breakout bar.
3. During `07:00-09:00 UTC`, scan bars in chronological order.
4. LONG breakout if bar `i` closes above:
   - `asia_high + 0.05 * ATR14_i`
5. SHORT breakout if bar `i` closes below:
   - `asia_low - 0.05 * ATR14_i`
6. Use only the first breakout per day for the primary cohort.
7. State is known at bar `i` close.
8. Entry candidate is bar `i+1 open`.
9. Primary returns start at bar `i+1 open`.

If both long and short conditions somehow qualify on the same bar, the event
is invalid and excluded because a single close cannot be both above the high
buffer and below the low buffer under valid OHLC data.

### Direction

- Close above Asia high plus buffer -> LONG candidate.
- Close below Asia low minus buffer -> SHORT candidate.

Direction splits must be reported. Direction-specific filters are not part of
the primary diagnostic.

---

## 7. Timing Model

| Field | Definition | Planned Value |
| --- | --- | --- |
| `range_start_bar` | First Asia session M15 bar | `00:00 UTC` |
| `range_end_bar` | Final Asia session M15 bar | Last completed bar before `07:00 UTC` |
| `range_known_bar` | First bar where full Asia range is known | `07:00 UTC` open |
| `detection_bar` | London bar closing beyond buffered Asia range | bar `i` |
| `state_known_bar` | First moment breakout state is knowable | bar `i` close |
| `confirmation_bar` | Same as close-confirmed breakout | bar `i` |
| `entry_candidate_bar` | Earliest realistic entry | bar `i+1` |
| `label_available_bar` | Primary outcome horizon end | bar `i+1+5` close |
| `return_start_bar` | Bar from which primary returns are measured | bar `i+1 open` |

Critical rule:

Primary returns must start at `entry_candidate_bar`. Detection-bar returns are
audit-only and may not be used as primary validation.

Lookahead guard:

- Asia range uses only bars completed before `07:00 UTC`.
- Breakout is known only at the close of bar `i`.
- No future bars may affect detection, direction, entry, or risk reference.

---

## 8. MFE Accessibility Design

For every main and control event:

### LONG Candidate

- `MFE_before_entry`: max favorable move from detection close through
  `entry_candidate_bar - 1`.
- `MFE_after_entry`: max high minus entry price from `entry_candidate_bar`
  through primary horizon.
- `MAE_after_entry`: entry price minus min low over the same post-entry horizon.

### SHORT Candidate

- `MFE_before_entry`: max favorable move from detection close through
  `entry_candidate_bar - 1`.
- `MFE_after_entry`: entry price minus min low from `entry_candidate_bar`
  through primary horizon.
- `MAE_after_entry`: max high minus entry price over the same post-entry
  horizon.

### Consumption Metric

`mfe_consumed_pct = MFE_before_entry / (MFE_before_entry + MFE_after_entry)`

STOP gate:

- Median `mfe_consumed_pct > 70%`.

EXPLORE target:

- Median `mfe_consumed_pct < 60%`.

Reconnaissance baseline:

- `ASIA_RANGE_LONDON_BREAKOUT` median MFE consumed: `11.54%`.

The diagnostic must verify whether this remains true after the frozen
`0.05 * ATR14` breakout buffer, next-open entry, and primary 5-bar horizon.

---

## 9. Return and Cost Model

### Entry and Exit

Primary entry:

- `entry_price = open` of bar `i+1`.

Primary exit:

- close of bar `i+1+5`.

Sensitivity exits:

- close of bar `i+1+8`.
- close of bar `i+1+10`.

### Stop / R Denominator

For LONG:

- `stop_reference = asia_low - 0.05 * ATR14_i`
- `risk_pct = abs(entry_price - stop_reference) / entry_price`

For SHORT:

- `stop_reference = asia_high + 0.05 * ATR14_i`
- `risk_pct = abs(stop_reference - entry_price) / entry_price`

Events with non-positive or invalid `risk_pct` are excluded and counted.

R return:

- `net_return_pct / risk_pct`

Raw net return percent must also be reported. The R denominator is a risk
normalizer, not a simulated stop execution. This diagnostic does not claim an
intrabar stop-loss fill unless a later implementation milestone explicitly
models stop execution.

### Cost Model

OANDA candles are mid-price OHLC. Historical bid/ask spread is unavailable.

| Scenario | Round-trip cost |
| --- | ---: |
| Low | 0.010% |
| Primary | 0.015% |
| Stress | 0.020% |

Primary gates use `0.015%`.

Rationale:

- EUR_USD spread is materially tighter than XAU_USD.
- Reconnaissance median MFE after entry was approximately `0.0855%`.
- A `0.015%` round-trip cost is about 18% of that median MFE, so it is
  meaningful enough to reject weak structure.

If the mechanism only looks viable at `0.010%` and fails at `0.015%`, the
result is not robust enough for `EXPLORE`.

### Primary Metrics

- event count
- median net return percent
- mean R / ER
- median R
- profit factor on R returns
- win rate
- median MFE consumed
- MFE/MAE after entry
- direction split
- fold metrics
- control cohort comparison

---

## 10. Baseline Comparison

### BTC Baseline

Reference: `trial_00095_conditional_edge_attribution_v1.md`

| Metric | BTC trial-00095 |
| --- | ---: |
| Accepted trades | 274 |
| ER | 2.121 |
| PF | 4.216 |
| Win rate | 56.57% |
| Core feature family | Sweep/reclaim + crypto flow/crowding |
| TFI/OI/funding available | Yes |

### Planned OANDA Diagnostic

| Metric | OANDA `ASIA_RANGE_LONDON_BREAKOUT` |
| --- | ---: |
| Instrument | `EUR_USD` |
| Timeframe | `M15` |
| Recon events | 424 |
| Recon follow-through | 84.43% |
| Recon false breakout | 18.16% |
| Recon MFE consumed | 11.54% |
| Core feature family | Session range breakout |
| TFI/OI/funding available | No |

### Interpretation

OANDA does not need to match BTC `trial-00095` to be useful. It could add
orthogonal trade frequency in a different market. But it must be positive
after realistic costs, beat controls, and pass walk-forward gates.

Pre-result interpretation:

- ER > 1.5 and PF > 1.5: strong OANDA session candidate.
- ER 1.3 to 1.5 with controls beaten: explore.
- ER 1.0 to 1.3: weak, likely inconclusive unless folds and controls are very
  strong.
- ER < 1.0: STOP.

---

## 11. Control Cohorts

Controls are pre-defined before diagnostic results. Each control must use the
same cost model, primary horizon, R model, MFE accessibility logic, and
walk-forward fold assignment whenever applicable.

Decision-grade control rule:

- A control needs at least 25 events to count for the outperformance gate.
- Smaller controls are reported as informational only.

### Control 1: Random Session Timing

- Use main event dates and directions.
- Shift entry timing by deterministic `+137` M15 bars.
- Preserve horizon and cost model.
- Purpose: control for random market drift and serial correlation.

### Control 2: Opposite Direction Entry

- Same Asia range and same London breakout detection.
- Enter opposite direction at `i+1 open`.
- Purpose: test whether breakout direction carries information.

### Control 3: Same Breakout Rule Outside London

- Build the same Asia range.
- Detect the same buffered range breakout during `13:00-16:00 UTC` instead of
  `07:00-09:00 UTC`.
- Purpose: isolate whether London timing matters.

### Control 4: Breakout Without Prior Asia Range Compression

- Use the same London breakout detection.
- Do not require the Asia range to be narrow or compressed.
- Since the primary diagnostic also has no compression filter, this control
  must be implemented as a metadata/segmentation control:
  - compare top-half versus bottom-half Asia range width buckets.
- Purpose: verify whether the edge is simply volatility exposure rather than
  range-to-expansion structure.

### Control 5: Compression Without Breakout

- Identify Asia ranges in the lower half of range width or ATR-normalized
  range.
- No London breakout through the buffered Asia high/low during `07:00-09:00`.
- Use a deterministic proxy entry at `09:00 UTC` in the direction of London
  net movement up to that point, or report as non-directional if that rule
  creates lookahead risk.
- Purpose: test whether compression alone has directional value.

Primary implementation note:

- If the deterministic entry cannot be defined without lookahead, this control
  should be reported as structure-only and excluded from ER outperformance.

### Control 6: Shifted Entry +2 Bars

- Same main detection.
- Entry at `i+3 open`.
- Purpose: test whether the edge decays when entry is delayed.

### Control 7: Weekday-Shuffled Control

- Deterministically rotate weekdays by a fixed offset while preserving candle
  order and event count, or reassign each event to the next available same-time
  event day.
- Purpose: test whether the result depends on weekday calendar effects rather
  than session structure.

Implementation must avoid stochastic randomness. If a shuffle is used, the
seed and mapping must be fixed and reported.

### Control 8: Previous-Day Range Breakout Control

- Use the previous trading day's high/low range instead of the same-day Asia
  range.
- Detect breakout during `07:00-09:00 UTC`.
- Purpose: test whether the same-day Asia range is the informative reference,
  not any arbitrary prior range.

---

## 12. Walk-Forward Design

Use the same four chronological folds as prior OANDA diagnostics:

| Fold | Period |
| --- | --- |
| Fold 1 | 2024-01-01 to 2024-07-01 |
| Fold 2 | 2024-07-01 to 2025-01-01 |
| Fold 3 | 2025-01-01 to 2026-01-01 |
| Fold 4 | 2026-01-01 to latest available |

Fold positive definition:

- fold event count >= 25
- fold median net return > 0 after `0.015%` cost
- fold ER > 1.0

EXPLORE requires:

- at least 3 of 4 folds positive.

STOP triggers:

- fewer than 2 of 4 folds positive.

If a refreshed dataset extends beyond the reconnaissance range, fold boundaries
must remain the same unless the report clearly states the extended final fold.

---

## 13. Data Quality Requirements

Before event detection, the diagnostic must verify:

- candles sorted by timestamp
- timestamps are UTC or explicitly normalized to UTC
- timeframe is exactly M15
- OHLC integrity:
  - high >= open
  - high >= close
  - high >= low
  - low <= open
  - low <= close
- duplicate timestamp count
- gaps above expected OANDA market closures
- max gap duration
- data gate

DATA_BLOCKED if:

- fewer than 18 months of `EUR_USD M15` candles
- fewer than 30,000 complete candles
- OHLC bad rows > 0
- duplicate timestamps > 0
- session alignment cannot be trusted
- OANDA data access unavailable and no validated cached dataset exists

Weekend/market-closure gaps must be preserved, not forward-filled.

---

## 14. Parameter Discipline

Frozen before implementation:

| Parameter | Value |
| --- | --- |
| Instrument | `EUR_USD` |
| Timeframe | `M15` |
| Asia range | `00:00-07:00 UTC` |
| Breakout window | `07:00-09:00 UTC` |
| Breakout buffer | `0.05 * ATR14` |
| Entry price | `i+1 open` |
| Primary horizon | 5 bars |
| Secondary horizon | 8 bars |
| Optional sensitivity horizon | 10 bars |
| Stop/risk buffer | `0.05 * ATR14` beyond opposite Asia extreme |
| Primary cost | 0.015% |
| Cost sensitivity | 0.010%, 0.015%, 0.020% |
| Compression filter | None |

Allowed descriptive analysis:

- direction split
- weekday split
- Asia range width buckets
- Asia range ATR buckets
- cost sensitivity
- 8-bar and 10-bar horizon sensitivity

Not allowed:

- changing Asia range window after results
- changing London breakout window after results
- changing breakout buffer after results
- adding compression filter after results
- adding weekday filter after results
- selecting only long or short after seeing outcomes
- adding sweep/reclaim/SMC filters
- switching to NY reversal inside this diagnostic
- using Optuna or broad search
- promoting to runtime

---

## 15. Invalidation Criteria

### STOP Gates

Return `STOP` if any major gate fires:

- sample size < 100
- primary event count collapses below 200 despite reconnaissance baseline 424
- median net return <= 0 after `0.015%` round-trip cost
- ER < 1.0
- profit factor < 1.2
- median MFE consumed > 70%
- any decision-grade control cohort beats main on ER
- fewer than 2 of 4 folds positive
- result depends on `0.010%` cost or non-primary horizon to look viable
- signal requires future bars
- primary returns start from detection bar instead of `i+1 open`
- diagnostic becomes a sweep/reclaim, SMC, or multi-mechanism test

### EXPLORE Gates

Return `EXPLORE` only if all are true:

- sample size >= 200
- median net return > 0 after `0.015%` cost
- ER > 1.3
- profit factor > 1.5
- median MFE consumed < 60%
- main cohort beats all decision-grade controls on ER
- at least 3 of 4 folds positive
- timing model verified with entry at `i+1 open`
- primary 5-bar horizon is viable without relying on sensitivity horizons

### INCONCLUSIVE Gates

Return `INCONCLUSIVE` if:

- event count is 100-199
- ER is 1.0-1.3 with stable but weak folds
- folds are mixed but no hard STOP gate fires
- controls are too small to decide
- cost sensitivity dominates the verdict
- structure remains accessible but expectancy is marginal

---

## 16. Expected Diagnostic Artifacts

If approved, the next implementation milestone should produce:

- Diagnostic script:
  - `research_lab/diagnostics/oanda_asia_range_london_breakout_feasibility_v1.py`
- Markdown report:
  - `research_lab/reports/oanda_asia_range_london_breakout_feasibility_v1.md`
- JSON artifact:
  - `research_lab/reports/oanda_asia_range_london_breakout_feasibility_v1.json`
- Focused tests:
  - `tests/test_research_lab/test_oanda_asia_range_london_breakout_feasibility_v1.py`

Report must include:

- executive summary with one recommendation
- data quality
- frozen parameter table
- timing model verification
- main cohort metrics
- all control cohort metrics
- MFE accessibility
- walk-forward fold results
- cost sensitivity
- horizon sensitivity
- BTC baseline comparison
- OANDA sweep/reclaim boundary statement
- invalidation gate evaluation
- JSON SHA256

If JSON artifact exceeds GitHub practicality limits, do not commit it. Store it
locally and document path, SHA256, and summary in the markdown report.

---

## 17. Audit Questions for Claude

1. Does the plan preserve both OANDA sweep/reclaim STOP results?
2. Does it avoid rescuing sweep/reclaim with session filters?
3. Is the mechanism exactly one: `ASIA_RANGE_LONDON_BREAKOUT`?
4. Are instrument and timeframe frozen to `EUR_USD M15`?
5. Are Asia range and London breakout windows frozen before results?
6. Is the `0.05 * ATR14` breakout buffer justified before results?
7. Is entry realistic at `i+1 open`?
8. Are primary returns measured from `entry_candidate_bar`, not detection?
9. Is MFE accessibility included with the 70% STOP threshold?
10. Are the 8 control cohorts pre-defined before implementation?
11. Are STOP / EXPLORE / INCONCLUSIVE gates clear?
12. Does the plan avoid Optuna and broad search?
13. Does the plan avoid production changes and OANDA bot porting?
14. Does the plan acknowledge lost BTC crypto-native features?
15. Is the recommendation narrow enough for one diagnostic?

---

## Recommendation: IMPLEMENT ONE DIAGNOSTIC

**Diagnostic name:** `OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1`

**Mechanism summary:** Build the `EUR_USD M15` Asia range from
`00:00-07:00 UTC`, detect the first close-confirmed London breakout during
`07:00-09:00 UTC` beyond `0.05 * ATR14`, enter at `i+1 open`, and measure
returns from entry only.

**Timing:** Asia range known at `07:00 UTC`; breakout detected on bar `i`;
state known at bar `i` close; entry at bar `i+1 open`; primary returns start
at bar `i+1 open`.

**Expected MFE accessibility:** reconnaissance baseline median MFE consumed
`11.54%`, target < `60%`, STOP if > `70%`.

**Estimated sample size:** reconnaissance baseline `424` events over 2.4 years
before the frozen `0.05 * ATR14` diagnostic buffer is applied exactly as
planned; diagnostic remains decision-grade if sample >= `200`.

**Estimated timeline:** 3-5 days for diagnostic implementation, tests, and
report after planning audit approval.

**Next:** Codex implements the research-only diagnostic only if Claude approves
this planning document and the user confirms the implementation milestone.
