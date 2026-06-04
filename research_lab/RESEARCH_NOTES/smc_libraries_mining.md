# SMC Libraries Mining - joshyattridge vs PyIndicators

Sources reviewed:
- joshyattridge/smart-money-concepts GitHub README and source: https://github.com/joshyattridge/smart-money-concepts
- PyIndicators GitHub README: https://github.com/coding-kitties/PyIndicators
- PyIndicators published wheel `pyindicators==0.22.0` downloaded from PyPI for code inspection
- Existing btc-bot research reports, especially `SESSION_SWEEP_SPECIALIST_AUDIT_PACKAGE.md` and `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1`

## TL;DR

| Dimension | joshyattridge/smart-money-concepts | PyIndicators |
| --- | --- | --- |
| Best use | Reference implementation for sessions, liquidity clusters, PDH/PDL/PWH/PWL | Idea library for block/zone lifecycle, OTE, and indicator/signal/stats pattern |
| Code availability | GitHub source available, MIT, simple pandas/numpy | GitHub main branch is docs-heavy; actual package code inspected from PyPI wheel |
| Main value for btc-bot | `sessions()`, `liquidity().Swept`, `previous_high_low()` | Breaker/Mitigation/Rejection Blocks, OTE, `ob_quality`, `ob_is_hpz` |
| Main risk | Naive timezone/session handling and lookahead-prone swing labels | Clean-looking docs may mask untested heuristics; package/repo source mismatch |
| Adopt directly? | No; reimplement formulas with UTC and audit contracts | No; reimplement selected mechanics and keep package as cross-check only |

## joshyattridge Pass 1 - Comprehension

The library implements ICT/SMC-style indicators over OHLC/volume pandas DataFrames. It expects lowercase OHLC columns and returns DataFrames with event flags and levels.

Relevant functions:

- `sessions(ohlc, session, start_time, end_time, time_zone="UTC")`: labels candles as active/inactive for named sessions and returns running session high/low.
- `liquidity(ohlc, swing_highs_lows, range_percent=0.01)`: groups multiple swing highs/lows within a range and returns the first candle index that sweeps the grouped level.
- `previous_high_low(ohlc, time_frame="1D")`: returns previous period high/low and broken flags.

Core mechanics are simple and inspectable: swing labels feed liquidity clustering; sessions are fixed clock windows; previous highs/lows are resampled OHLC periods.

## joshyattridge Pass 2 - Critical Examination

Main problems:

- `sessions()` uses fixed UTC-style clock windows and does not model exchange holidays, weekends, DST transitions, or regional market calendar reality.
- Timezone conversion uses `Etc/GMT` string replacement. `Etc/GMT` signs are counterintuitive and this can easily invert offsets if used carelessly.
- `sessions()` mutates `ohlc.index` after `ohlc = pd.to_datetime(ohlc.index)` behavior without a defensive copy in the shown function body.
- Running session high/low does not reset by named trading date with an explicit session id; it relies on active/inactive calculations and zeros.
- `liquidity()` uses overall dataset high-low range times `range_percent`, so cluster tolerance is path-dependent and non-local. That is dangerous for walk-forward replay.
- `previous_high_low()` uses resampling; timezone and period boundary assumptions must be made explicit before using on Binance UTC data.

Cargo-cult elements:

- ICT labels are names, not evidence. `liquidity`, `kill zone`, and `order block` are only useful after accessibility and expectancy tests.
- The existing btc-bot session-sweep specialist already failed as a direct context filter. A new `reclaim_session` must not be a renamed repeat of that failure.

## joshyattridge Pass 3 - Domain Mapping

Potential btc-bot touchpoints in a future implementation:

- `research_lab/level_scanner.py` or equivalent offline module for sessions, PDH/PDL/PWH/PWL, EQH/EQL.
- `core/regime_engine.py` or future `RegimeContext` only after DATA-INTEGRITY-V1 and MODELING-V1 scope.
- `governance/` only for session block/allow policy, not for alpha generation.
- `signal_engine.py`: do not touch for this research phase.

Adoption constraints:

- Reimplement, do not copy. MIT allows copying with attribution, but btc-bot needs deterministic local contracts, UTC normalization, quality flags, and no hidden index mutation.
- Session output can be informational in V1: `session_tag`, `session_active`, `session_high`, `session_low`, `minutes_since_session_open`.
- `liquidity.Swept` can be a cross-validation oracle for a local level scanner, not a production dependency.

## joshyattridge Pass 4 - Cost/Benefit

Estimated effort:

- Codex: 6-10h for local deterministic session/PDH/liquidity scanner spec and tests.
- Claude audit: 2-3h focused on timezone, no lookahead, and replay stability.

Best realistic result:

- Better level factory for setup portfolio.
- Cleaner session tags for MODELING-V1 `RegimeContext`.
- Cross-validation against known library outputs on historical data.

Worst realistic result:

- Rebuilds the already failed session-sweep idea.
- Introduces lookahead through swing confirmation or global range tolerance.
- Creates a false throughput story without rejected-candidate reconstruction.

Ratio:

- Worth it for a level scanner foundation: confidence 3/5.
- Not worth it as direct `reclaim_session` signal: confidence 2/5.

## joshyattridge Pass 5 - Synthesis

Recommendations:

1. Reimplement session tagging and session extremes in local code; use the library only as off-the-shelf validation. Confidence 3/5.
2. Reimplement PDH/PDL/PWH/PWL with explicit UTC period boundaries. Confidence 4/5.
3. Treat `liquidity.Swept` as a comparison target, not a production algorithm. Confidence 3/5.
4. Do not revive simple Asia-session filtering as an edge; existing research falsified that direction. Confidence 5/5.

Map:

- Copy to `research_lab/external_refs/`: optional README snippets and source metadata only.
- Reimplement: sessions, previous highs/lows, liquidity clusters.
- Omit: hidden dependency on the package at runtime.

## PyIndicators Pass 1 - Comprehension

PyIndicators is a broad pandas/polars indicator library. GitHub README describes many indicators; the actual package source was inspected from PyPI wheel `pyindicators==0.22.0` because the GitHub main snapshot is mostly docs and support files.

Relevant concepts:

- `breaker_blocks`: failed order blocks that flip into support/resistance after market structure shift.
- `mitigation_blocks`: origin candle of an impulse leading to a market structure shift.
- `rejection_blocks`: swing candles with large wick-to-range ratio; wick area becomes a future interaction zone.
- `optimal_trade_entry`: 61.8%-78.6% retracement zone after market structure shift.
- `market_structure_ob`: detects MSB and adds OB boundaries, `ob_quality` 0-100, and `ob_is_hpz` quality flag.
- API pattern: indicator function adds columns, signal function compresses entries to directional signal, stats function summarizes counts/rates.

## PyIndicators Pass 2 - Critical Examination

Main problems:

- GitHub source availability is confusing: README advertises functionality, while the main branch snapshot does not expose a conventional package tree. The PyPI wheel has the code.
- Many algorithms are heuristic ICT translations, not proven edge.
- Pivot detection often requires future bars for confirmation. If used naively, it creates label-available timing errors.
- Several functions use active-zone state machines. They are useful references, but their states must be replayed bar-by-bar in btc-bot tests.
- `market_structure_break` includes a 50-bar momentum z-score and pivot detection; this is a different edge family from current reclaim.
- The docs are polished; polish is not evidence of tradeability.

Critical project-specific issue:

- btc-bot's recent `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` found that post-sweep confirmations usually arrive after favorable excursion is consumed. Breaker, mitigation, and OTE are delayed-confirmation concepts, so they begin under suspicion.

## PyIndicators Pass 3 - Domain Mapping

Potential future modules:

- `research_lab/level_scanner.py`: detect and store zones/levels offline.
- `research_lab/setups/*`: prototype setup candidates in research only.
- Future `core/models.py`: if promoted, setup facts should travel as dataclasses or feature facts, not pandas columns.
- Future `RegimeContext`: can rank/select setup families, but only after audited MODELING-V1 blueprint.

Rules:

- No production code in current task.
- No dependency addition to `requirements.txt`.
- No direct changes to `signal_engine.py`.
- Any indicator using future-confirmed pivots must expose `label_available_bar`.

Copy vs reimplement:

- Copy directly: none in this phase.
- Reimplement: state-machine ideas, output schemas, stats convention.
- Cross-validate: run PyPI package outputs against local implementation on 6m BTC in a future research-only diagnostic.

## PyIndicators Pass 4 - Cost/Benefit

Estimated effort:

- Codex: 14-24h to implement one clean candidate setup plus level scanner and accessibility tests; 30-45h for all five candidates.
- Claude audit: 4-8h for one candidate; 10-15h for full portfolio.

Best realistic result:

- A disciplined setup-candidate backlog with comparable schemas.
- A local pattern of `indicator facts -> setup signal -> stats` for research lab.
- One or two candidates may increase near-miss throughput if they trigger at earliest knowable timing.

Worst realistic result:

- Repeats already invalidated late-entry SMC work.
- Adds dozens of columns and names with no accessible edge.
- Confuses level detection with entry logic and violates layer separation.

Ratio:

- Good as mining/spec material: 3/5.
- Risky as direct setup implementation: 2/5 until accessibility tests pass.

## PyIndicators Pass 5 - Synthesis

Recommendations:

1. Adopt the 3-layer API convention in research lab: `detect_*_facts`, `*_candidate_signal`, `get_*_stats`. Confidence 4/5.
2. Reuse `ob_quality` / `ob_is_hpz` as a concept for ranking setup facts, not as magic thresholds. Confidence 3/5.
3. Prioritize rejection-style earliest-knowable wick evidence over mitigation/OTE delayed re-entry. Confidence 3/5.
4. Any breaker/mitigation/OTE test must report MFE before entry vs after entry. Confidence 5/5.
5. Do not add PyIndicators as a dependency. Confidence 4/5.

## Sessions Deep-Dive

Algorithm in joshyattridge:

1. Convert the DataFrame index to datetime.
2. Choose default fixed session times, e.g. Sydney 21:00-06:00, Tokyo 00:00-09:00, London 07:00-16:00, New York 13:00-22:00, kill zones.
3. For each candle, compare `HH:MM` against start/end.
4. If active, set `Active=1`, running `High=max(current high, previous high)`, `Low=min(current low, previous low)`.
5. If inactive, leave zeros.

Edge cases:

- DST: fixed UTC windows are acceptable for crypto if we define them as UTC sessions, but not if pretending to represent local London/New York clocks.
- Weekend/holidays: crypto trades continuously; traditional session naming is behavioral shorthand, not market-open truth.
- Session spanning midnight: handled by `start >= end`, but session date/id must be explicit in btc-bot.
- Missing candles: running high/low can silently ignore gaps unless scanner checks expected cadence.
- Timezone: do not accept arbitrary local `time_zone` in btc-bot; normalize input to UTC first and define sessions in UTC.
- Boundary inclusivity: library uses inclusive start and end; btc-bot should choose `[start, end)` to avoid double-labeling boundary candles.

## Liquidity.Swept Algorithm

Pseudocode:

```text
input: ohlc, swing_high_low labels, range_percent
pip_range = (global_high - global_low) * range_percent

for each swing high i not already consumed:
    cluster = [level_i]
    range = [level_i - pip_range, level_i + pip_range]
    swept = first future bar where high >= range_high, else 0
    for later swing high j before swept:
        if level_j inside range:
            add to cluster
            mark j consumed
    if cluster size > 1:
        emit bullish liquidity at i, average level, end index, swept index

repeat symmetrically for swing lows:
    swept = first future bar where low <= range_low
```

Edge cases:

- Uses global high-low, so early historical rows can depend on far-future price range. Reimplement with rolling/local ATR tolerance.
- `Swept=0` is ambiguous: could mean not swept or first row if index 0 were possible. Use nullable integer in btc-bot.
- Swing labels can be future-confirmed. Store `formed_bar`, `confirmed_bar`, and `swept_bar`.
- Multiple nearby clusters can be consumed greedily. Local implementation needs deterministic tie-break rules.

## Five New Setup Candidates

### 1. `reclaim_session`

Mechanics:

- Use session extremes and kill-zone tags as level/context facts.
- Candidate triggers only if existing sweep/reclaim occurs against a current or previous session high/low.
- It must not be a time-window-only filter.

Complement to `reclaim_swing`:

- Adds level provenance: session high/low rather than only equal highs/lows.
- May increase throughput if session extremes create more valid levels without relaxing reclaim quality.

Edge hypothesis:

- Session extremes concentrate stop liquidity in crypto even without formal market hours.

Confidence: 2/5, because prior session-sweep specialist failed.

### 2. `reclaim_breaker`

Mechanics:

- Detect a failed prior zone after market structure shift.
- A reclaim against the breaker zone can be considered only if entry timing is no later than current reclaim timing.

Complement:

- Captures failed support/resistance flip rather than equal-level sweep.

Edge hypothesis:

- Failed OB zones may provide structurally cleaner levels than generic equal highs/lows.

Confidence: 2/5.

### 3. `reclaim_mitigation`

Mechanics:

- Identify origin candle of an impulse that created MSS.
- Reclaim/entry occurs on revisit to origin zone.

Complement:

- More origin-based than sweep-based.

Edge hypothesis:

- Origin zones may concentrate unfilled inventory.

Confidence: 1/5, because delayed mitigation entries were already specifically problematic in SMC_SEQUENCE_EDGE_FEASIBILITY_V1.

### 4. `reclaim_rejection`

Mechanics:

- Detect large wick rejection at confirmed or earliest-knowable swing extreme.
- Candidate uses wick zone as level; reclaim must occur with existing flow/confluence.

Complement:

- Closest to current reclaim mechanics: wick rejection is already a first-bar observable, not necessarily a late retest.

Edge hypothesis:

- Strong wick rejection plus current TFI/CVD confluence may identify accessible MFE earlier than mitigation/OTE.

Confidence: 3/5.

### 5. `ote_pullback`

Mechanics:

- After MSS, define 61.8%-78.6% retracement of impulse leg.
- Candidate on pullback into OTE zone.

Complement:

- Trend-continuation pullback family, less directly tied to stop sweep.

Edge hypothesis:

- Could add throughput in directional regimes where reclaim_swing is scarce.

Confidence: 2/5, due delayed-entry risk and separate strategy-family complexity.

## Recommended Implementation Order

1. `level_scanner` foundation: sessions, PDH/PDL/PWH/PWL, EQH/EQL. Rationale: needed by all candidates and can be validated without trade claims. Confidence 4/5.
2. `reclaim_rejection` research diagnostic. Rationale: earliest-knowable and closest to existing reclaim mechanics. Confidence 3/5.
3. `reclaim_session` as level-provenance test, not session filter. Rationale: may avoid repeating failed session-only subset test. Confidence 2/5.
4. `reclaim_breaker` only after MFE accessibility design is approved. Confidence 2/5.
5. `ote_pullback` as separate trend-continuation family, not reclaim expansion. Confidence 2/5.
6. Defer `reclaim_mitigation`. Confidence 1/5.

## Candidate Confidence Summary

| Candidate | Confidence |
| --- | ---: |
| `reclaim_session` | 2/5 |
| `reclaim_breaker` | 2/5 |
| `reclaim_mitigation` | 1/5 |
| `reclaim_rejection` | 3/5 |
| `ote_pullback` | 2/5 |
