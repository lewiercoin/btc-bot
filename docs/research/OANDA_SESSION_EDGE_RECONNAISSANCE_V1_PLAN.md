# OANDA_SESSION_EDGE_RECONNAISSANCE_V1_PLAN

**Type:** Market-structure reconnaissance planning  
**Scope:** OANDA-native session edge reconnaissance, no diagnostic implementation  
**Status:** Approved by Claude Code (2026-06-01)

---

## 1. Purpose

Recent OANDA research invalidated direct transfer of the BTC sweep/reclaim edge:

- `XAU_USD H1` strict BTC transfer: `STOP` due to sample collapse.
- `EUR_USD M15` same-bar sweep/reclaim: `STOP` due to negative expectancy, despite good sample and MFE accessibility.

Conclusion so far:

> OANDA sweep/reclaim transfer is invalidated, but OANDA itself is not invalidated.

This milestone searches for **OANDA-native / forex-native structure**, specifically session-driven behavior. Forex has structural features that crypto does not:

- Asia range compression
- London open liquidity expansion
- New York overlap
- rollover liquidity gaps
- day-of-week and session-specific behavior

This is reconnaissance only. It must identify whether any session-based structure is strong enough to justify a future full planning document.

---

## 2. Milestone

**Name:** `OANDA_SESSION_EDGE_RECONNAISSANCE_V1`  
**Type:** Quick reconnaissance / structure inventory  
**Builder:** Codex or Cascade  
**Auditor:** Claude Code  
**Expected timeline:** 3-5 days  
**Deliverable:** one markdown report, optional lightweight JSON artifact  

Target report:

`docs/research/OANDA_SESSION_EDGE_RECONNAISSANCE_V1_REPORT.md`

Optional artifact:

`research_lab/reports/oanda_session_edge_reconnaissance_v1.json`

If JSON is large, do not commit it. Save locally and document path + SHA256 in the markdown report.

---

## 3. Critical Boundary

This is **not** a sweep/reclaim rescue.

Forbidden interpretations:

- "Sweep/reclaim failed, so tune it with sessions."
- "Add London filter to make failed sweep/reclaim pass."
- "Use session filter on the previous OANDA diagnostic."
- "Try to rescue EUR_USD M15 sweep/reclaim."

This is a new edge family:

> Session-driven forex structure.

Sweep/reclaim diagnostics remain invalidated.

---

## 4. Scope

### In Scope

- Read prior OANDA reports.
- Inspect OANDA `EUR_USD M15` and `XAU_USD M15` candle availability.
- Define fixed UTC session windows.
- Measure session range behavior.
- Measure breakout frequency.
- Measure follow-through after breakout.
- Measure false breakout / reversal tendency.
- Measure MFE accessibility.
- Measure direction asymmetry.
- Measure day-of-week effects.
- Compare candidate session mechanisms.
- Recommend exactly one next step.

### Out of Scope

- No production code.
- No OANDA bot port.
- No live or paper trading changes.
- No Optuna.
- No broad parameter optimization.
- No full PnL diagnostic.
- No SMC logic.
- No OB/FVG/mitigation.
- No sweep/reclaim rescue.
- No selecting parameters after seeing PnL.
- No promotion or settings changes.

---

## 5. Required Source Context

Builder must read:

1. `docs/research/OANDA_SWEEP_RECLAIM_TRANSFER_FEASIBILITY_V1_PLAN.md`
2. `research_lab/reports/oanda_xauusd_sweep_reclaim_transfer_feasibility_v1.md`
3. `docs/research/OANDA_SWEEP_RECLAIM_MARKET_STRUCTURE_RECONNAISSANCE_V1_REPORT.md`
4. `docs/research/OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1_PLAN.md`
5. `research_lab/reports/oanda_eurusd_m15_sweep_reclaim_feasibility_v1.md`
6. `docs/QUANT_RESEARCH_OPERATING_MODEL.md`
7. `docs/BLUEPRINT_RESEARCH_LAB.md`
8. `AGENTS.md`

Optional external source review is recommended but not mandatory for this reconnaissance. If used, sources must be classified as:

- useful concept
- model-quality
- opinion-based
- needs validation
- not applicable

---

## 6. Data Requirements

### Primary Instrument

`EUR_USD`

### Comparison Instrument

`XAU_USD`

XAU is comparison only. It must not become the selected diagnostic target unless the report explicitly justifies why EUR failed structurally and XAU is materially better.

### Timeframe

`M15`

No H1/M30/5M expansion in this milestone.

### Date Range

Use same OANDA inventory range as prior research if available:

- Start: `2024-01-01`
- End: latest available / current cached end

Minimum acceptable:

- at least 18 months of M15 candles
- at least 30,000 M15 candles per primary instrument

### Data Quality Checks

For each instrument:

- candle count
- first timestamp
- last timestamp
- OHLC integrity
- duplicate timestamps
- gaps > expected market closures
- max gap duration
- data gate: `PASS`, `PARTIAL`, `BLOCKED`

---

## 7. Fixed Session Definitions

All sessions must be UTC.

### Asia Range

`00:00-07:00 UTC`

Purpose:
- compression / range formation window

### London Open

`07:00-09:00 UTC`

Purpose:
- early European volatility expansion

### London Continuation

`09:00-12:00 UTC`

Purpose:
- follow-through after London open

### New York Overlap

`13:00-16:00 UTC`

Purpose:
- highest institutional overlap, continuation or reversal

### Rollover / Illiquid Window

`21:00-23:00 UTC`

Purpose:
- liquidity gap / avoidance / abnormal spread-risk proxy

No session boundaries may be changed after seeing results.

---

## 8. Candidate Mechanisms To Compare

This reconnaissance compares structure only. It does not run full profitability diagnostics.

### Candidate A: ASIA_RANGE_LONDON_BREAKOUT

Definition:

- Build Asia range from `00:00-07:00 UTC`.
- Detect London breakout if price closes above Asia high or below Asia low during `07:00-09:00 UTC`.
- Measure follow-through after breakout.

Structure questions:

- How often does London break Asia range?
- Does breakout direction show follow-through?
- How much MFE occurs after breakout confirmation?
- How often is breakout false?

### Candidate B: LONDON_OPEN_RANGE_BREAKOUT

Definition:

- Build London opening range from first N bars of `07:00-08:00 UTC`.
- Detect breakout during `08:00-12:00 UTC`.
- Measure continuation.

Structure questions:

- Does the opening hour define a useful range?
- Does later London session expand from it?
- Is breakout accessible after confirmation?

### Candidate C: NY_REVERSAL_AFTER_LONDON_EXTENSION

Definition:

- Measure London directional extension from `07:00-12:00 UTC`.
- During `13:00-16:00 UTC`, measure whether price tends to reverse or continue.
- Candidate reversal if London move exceeds ATR/session-range threshold.

Structure questions:

- Does NY overlap fade extended London moves?
- Is reversal MFE accessible after confirmation?
- Are continuations more common than reversals?

### Candidate D: ROLLOVER_FADE_OR_AVOIDANCE

Definition:

- Measure abnormal range, gaps, and failed movement during `21:00-23:00 UTC`.
- Determine whether this window is tradable or should be avoided.

Structure questions:

- Is rollover structurally noisy?
- Does it produce false breakouts?
- Is it more useful as avoidance metadata than entry signal?

---

## 9. Structural Metrics

For each candidate mechanism and instrument:

### Frequency

- number of candidate events
- events per month
- events per year
- long vs short split
- day-of-week split

Minimum decision-grade structure:

- at least 100 events per year, or
- at least 200 total events over available history

### Range / Volatility

- session range as percent of price
- session range as ATR multiple
- compression percentile
- expansion percentile

### Breakout / Reversal Behavior

For breakout candidates:

- breakout count
- breakout rate
- close-confirmed breakout count
- same-session follow-through rate
- continuation vs reversal split

For reversal candidates:

- extension count
- reversal count
- continuation count
- reversal rate

### MFE / MAE Accessibility

For each structural event:

- state-known bar
- entry candidate bar
- MFE before entry
- MFE after entry
- MAE after entry
- MFE consumed %
- time from entry to max MFE

MFE gate:

- structure is timing-viable if median MFE consumed < 70%
- preferred candidate has median MFE consumed < 60%

### False Breakout Definition

For breakout candidates:

False breakout if:

- breakout close occurs,
- then within next `N` bars price closes back inside the source range,
- and fails to make at least `0.5 * ATR` favorable excursion.

Use pre-declared values:

- `N = 4` bars on M15
- favorable excursion threshold = `0.5 * ATR14`

Report:

- false breakout rate
- median bars to failure
- false breakout rate by session and direction

### Follow-Through Definition

Follow-through if:

- after breakout confirmation, price reaches at least `0.5 * ATR14` favorable excursion within next `8` bars.

Report:

- follow-through rate
- median MFE
- median time to MFE
- follow-through by direction and weekday

---

## 10. Timing Model

For each candidate, define:

### Breakout Candidate Timing

- `range_known_bar`: final bar of range-building session
- `detection_bar`: bar that closes outside range
- `state_known_bar`: close of detection bar
- `entry_candidate_bar`: next bar open
- `return_start_bar`: next bar open

### Reversal Candidate Timing

- `extension_known_bar`: final bar of London extension measurement
- `detection_bar`: first NY bar confirming reversal condition
- `state_known_bar`: detection bar close
- `entry_candidate_bar`: next bar open
- `return_start_bar`: next bar open

Primary returns, if later diagnostic is built, must start at `entry_candidate_bar`, not detection.

This reconnaissance may report structural MFE only, but it must still respect timing fields.

---

## 11. Decision Criteria

### PROCEED_TO_FULL_PLANNING

Recommend proceed if exactly one candidate mechanism has:

- at least 200 total events
- at least 100 events/year preferred
- median MFE consumed < 70%
- preferably < 60%
- follow-through or reversal rate meaningfully above random baseline
- false breakout rate < 50%
- consistent behavior across at least 3 of 4 chronological folds
- not dependent on one weekday or one short period
- clear timing model with no lookahead

### STOP_SESSION_EDGE

Recommend stop if:

- no candidate reaches 200 total events
- false breakout rate >= 50% across candidates
- MFE consumed > 70% across candidates
- all structures appear random or contradictory
- no candidate has stable fold behavior
- session behavior is only useful as avoidance metadata, not entry edge

### DATA_BLOCKED

Recommend data blocked if:

- OANDA data missing
- candle gaps invalidate session measurement
- fewer than 18 months of M15 data
- timestamp/session alignment cannot be trusted

### INCONCLUSIVE

Recommend inconclusive if:

- sample exists but structure is mixed
- candidate has 100-199 events
- one candidate looks promising but fold stability is weak
- false breakout and follow-through metrics conflict

---

## 12. Controls For Future Diagnostic

Reconnaissance must define likely future controls, but does not need to run full PnL cohorts.

Potential future controls:

1. Random session timing.
2. Opposite direction entry.
3. Same breakout rule outside target session.
4. Breakout without compression.
5. Compression without breakout.
6. Shifted entry +2 bars.
7. Weekday-shuffled control.
8. Previous-day range breakout control.

These must be documented now to prevent post-hoc diagnostic design.

---

## 13. Deliverable Format

Target file:

`docs/research/OANDA_SESSION_EDGE_RECONNAISSANCE_V1_REPORT.md`

Required sections:

1. Executive Summary
2. Prior OANDA Research Boundary
3. Data Inventory
4. Fixed Session Definitions
5. Candidate Mechanism Definitions
6. Structural Frequency Matrix
7. Range and Volatility Analysis
8. Breakout / Reversal Behavior
9. MFE Accessibility
10. False Breakout and Follow-Through
11. Direction / Weekday / Session Splits
12. Candidate Ranking
13. Future Controls
14. Recommendation

Optional JSON:

`research_lab/reports/oanda_session_edge_reconnaissance_v1.json`

If JSON is large, do not commit. Document local path and SHA256 in the markdown report.

---

## 14. Required Interpretation Language

Allowed:

- "OANDA sweep/reclaim transfer is invalidated."
- "OANDA session structure remains unproven."
- "This candidate is structurally viable for planning."
- "This reconnaissance does not prove edge."
- "A separate diagnostic is required."

Not allowed:

- "OANDA has edge."
- "London breakout works."
- "Proceed to production."
- "Use Optuna to tune until it passes."
- "Add session filter to rescue sweep/reclaim."

---

## 15. Expected Recommendation

The report must end with exactly one of:

### Option A: PROCEED_TO_FULL_PLANNING

Specify one mechanism, for example:

`OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1_PLAN`

or

`OANDA_LONDON_OPEN_RANGE_BREAKOUT_FEASIBILITY_V1_PLAN`

### Option B: STOP_SESSION_EDGE

Session structure is insufficient.

### Option C: DATA_BLOCKED

Data quality prevents conclusion.

### Option D: INCONCLUSIVE

Structure exists but not enough evidence for a diagnostic plan.

---

## 16. Audit Questions For Claude

1. Does the plan avoid rescuing failed sweep/reclaim?
2. Are sessions fixed before results?
3. Are candidate mechanisms pre-declared?
4. Is this reconnaissance, not diagnostic implementation?
5. Are MFE accessibility and timing discipline included?
6. Are false breakout and follow-through definitions pre-declared?
7. Are data quality gates explicit?
8. Is Optuna explicitly out of scope?
9. Does the report require exactly one recommendation?
10. Does it avoid production changes?
