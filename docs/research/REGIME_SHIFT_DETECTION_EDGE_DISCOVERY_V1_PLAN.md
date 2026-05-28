# REGIME_SHIFT_DETECTION_EDGE_DISCOVERY_V1_PLAN

Planning date: 2026-05-28
Milestone: REGIME_SHIFT_DETECTION_EDGE_DISCOVERY_V1_PLANNING
Mode: Quant Research / Edge Discovery Mode
Status: PLANNING_COMPLETE - awaiting Claude audit before any implementation

## Scope

This is a planning-only research milestone.

Allowed output: source research, repo data surface inspection, one extracted deterministic mechanism, timing model, ADX lag model, MFE accessibility design, baseline comparison design, control cohort design, pre-result invalidation criteria, and one recommendation.

Not allowed in this milestone: diagnostic scripts, backtests or experiments, result data, production code changes, FeatureEngine/SignalEngine/Governance/Risk/execution/orchestrator/settings/trial-00095 changes, dependency installation, or candidate promotion.

Selected mechanism:

- `TREND_RANGE_STATE_SHIFT`

Tradeable V1 form:

- `RANGE_TO_TREND_STATE_SHIFT`

Why this narrower form: `TREND_RANGE_STATE_SHIFT` is the family selected by the user, but a standalone diagnostic needs a directional entry. Range-to-trend has direction through `+DI/-DI`; trend-to-range is more naturally an exit, stand-down filter, or mean-reversion context, so it is retained as a control cohort.

Rejected for this planning milestone:

- `FILTERED_HMM_REGIME_SHIFT`, because the user selected deterministic planning first and the repo does not currently have HMM/GARCH dependencies installed.
- Pure volatility percentile transition, because it is a required baseline control rather than the selected mechanism.
- Any rescue of failed volatility breakout logic. This plan does not use range breakout, volume spike, TFI confirmation, ATR slope, or breakout continuation rules from the failed volatility family.

## Prior Research Context

Recent research changed the standard from "pattern exists" to "state is knowable early enough and adds information after controls."

| Diagnostic or report | Key result | Planning implication |
| --- | --- | --- |
| `REGIME_SHIFT_DETECTION_RECONNAISSANCE_V1` | DONE, PROCEED. Data sufficient, 26 sources, regime families identified, methodology risks flagged. | Full plan can proceed for one mechanism only. |
| `VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1` | STOP. ER=-0.092, PF=0.857, 3 controls beat main, despite only 14.95% MFE consumed. | Good timing is insufficient; mechanism must add predictive information beyond controls. |
| `LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1` | STOP. 15m and 5m both had 100% MFE consumed. | MFE before and after entry remains mandatory. |
| `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` | No post-sweep state had positive median net return after costs. | Primary returns must start at realistic entry, never detection. |

This plan opens a deterministic regime-transition mechanism. It is not a price breakout rescue, not an HMM label exercise, and not a trial-00095 parameter filter.

## Research Question

When BTCUSDT transitions from a range regime to a trend regime, as measured by completed-bar ADX and Choppiness Index states, does next-bar directional entry preserve enough post-entry MFE and expectancy to be tradable after costs?

Primary hypothesis:

- ADX measures trend strength.
- Choppiness Index measures whether price action is range-like or trend-like.
- Requiring both indicators to agree may identify transitions that are cleaner than either indicator alone.
- A latched range state followed by an explicit trend state may mark the beginning of tradable directional persistence.
- Entry at the next 15m bar after transition confirmation may still be early enough if the regime transition has persistence beyond the ADX lag.

Primary risk:

- ADX is intentionally smoothed and lagging. The plan must not hide that lag. If the favorable move is already consumed by the time ADX confirms, the mechanism is invalid.

## Source Research Method

Search coverage included ADX calculation/interpretation references, Choppiness Index formula and implementation references, ADX+CHOP trend/range concepts, crypto trend-following research, regime-transition papers, code implementations where available, and backtesting methodology references for completed-candle timing and lookahead control.

Source inspection standard: prefer primary indicator definitions and code over strategy blogs, inspect implementation code where available, treat TradingView pages as mechanism vocabulary unless code is inspectable, classify lookahead/repainting risk explicitly, and extract deterministic mechanism components rather than performance claims.

## Source Coverage Matrix

| # | Source | URL | Type | Inspected artifact | Extracted mechanism | Classification | Determinism | Lookahead/repainting | Data availability | Applicability |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | StockCharts ChartSchool - Average Directional Index | https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-directional-index-adx | Indicator documentation | ADX calculation, Wilder smoothing, trend-strength thresholds | ADX from TR, +DM, -DM, +DI, -DI, DX, Wilder smoothing; ADX >25 trend, <20 no trend | Model-quality definition | Deterministic from OHLC | No lookahead if computed on completed bars; explicitly lagging | `candles` | Primary ADX definition |
| 2 | TradingView Help - Average Directional Index | https://www.tradingview.com/support/solutions/43000589099-average-directional-index-adx/ | Indicator documentation | Built-in ADX interpretation | ADX measures trend strength; +DI/-DI used for direction through DMI | Useful definition | Deterministic | No lookahead for built-in completed-bar use | `candles` | Confirms platform interpretation |
| 3 | TradingView Help - Directional Movement DMI | https://www.tradingview.com/support/solutions/43000502250-directional-movement-dmi/ | Indicator documentation | DMI inputs | Default DI length 14 and ADX smoothing 14 | Useful definition | Deterministic | No lookahead if current candle closed | `candles` | Confirms fixed V1 period choice |
| 4 | TA-Lib ADX documentation | https://ta-lib.github.io/ta-doc/indicator/ADX.htm | Library documentation | ADX function reference | ADX attributed to Wilder, implemented as standard TA function | Implementation reference | Deterministic | Library itself no lookahead; caller can misuse data alignment | `candles` | Useful calculation benchmark if dependency existed |
| 5 | QuantConnect LEAN AverageDirectionalIndex.cs | https://raw.githubusercontent.com/QuantConnect/Lean/master/Indicators/AverageDirectionalIndex.cs | GitHub code | C# indicator implementation | Computes TR, +DM, -DM, Wilder smoothing, +DI/-DI, ADX; warmup period 2*n | Model-quality implementation | Deterministic streaming update | No future bars; stateful online indicator | `candles` | Strong implementation reference |
| 6 | bukosabino/ta ADXIndicator | https://raw.githubusercontent.com/bukosabino/ta/master/ta/trend.py | GitHub code | `ADXIndicator`, `adx`, `adx_pos`, `adx_neg` | Python implementation of ADX/+DI/-DI from OHLC series | Useful implementation | Deterministic | Vectorized calculations must be aligned carefully | `candles` | Good Python reference |
| 7 | Linn Software - Choppiness Index | https://www.linnsoft.com/techind/choppiness-index | Indicator documentation | Formula section | CHOP = 100 * log10(sum(TR) / (max high - min low)) / log10(period) | Model-quality definition | Deterministic from OHLC | No lookahead if rolling window ends at current bar | `candles` | Primary CHOP formula |
| 8 | Stock Indicators for Python - Choppiness Index | https://python.stockindicators.dev/indicators/Chop/ | Library documentation | CHOP docs and source links | CHOP measures trendiness/choppiness on 0-100 scale; first N values unavailable | Useful implementation reference | Deterministic | No lookahead if updated sequentially | `candles` | Warmup and output behavior reference |
| 9 | QuantConnect LEAN ChoppinessIndex.cs | https://raw.githubusercontent.com/QuantConnect/Lean/master/Indicators/ChoppinessIndex.cs | GitHub code | C# indicator implementation | Rolling highs/lows plus rolling true range sum; returns 100 if no movement | Model-quality implementation | Deterministic streaming update | No future bars; online update only | `candles` | Strong implementation reference |
| 10 | QuantConnect docs - Choppiness Index | https://www.quantconnect.com/docs/v2/writing-algorithms/indicators/supported-indicators/choppiness-index | Official docs | Indicator use and manual update examples | CHOP determines choppy sideways versus trending market | Useful definition | Deterministic | No lookahead in manual update model | `candles` | Confirms online knowability |
| 11 | Offline Pixel Pine CHOP guide | https://offline-pixel.github.io/pinescript-strategies/pine-script-ChoppinessIndex.html | Pine guide | Formula and thresholds | CHOP formula; common thresholds 61.8 choppy and 38.2 trending | Useful concept | Deterministic | Pine built-in must use closed bar for research | `candles` | Supports threshold choices |
| 12 | EODHD Choppiness Index in Python | https://eodhd.com/financial-academy/backtesting-strategies-examples/detecting-ranging-and-trending-markets-with-choppiness-index-in-python | Blog/code article | Python CHOP implementation and interpretation | CHOP >=61.8 consolidating, <=38.2 trending | Useful concept | Deterministic | Educational backtest needs audit | `candles` | Supports CHOP range/trend threshold |
| 13 | TradingView CHOP scripts page | https://www.tradingview.com/scripts/choppinessindex/ | TradingView script index | ADX+CHOP hybrid descriptions | ADX above threshold plus low CHOP indicates clean trend; low ADX plus high CHOP indicates range | Useful concept | Deterministic concept | Individual scripts may repaint; source not all inspected | `candles` | Supports combination, not authority |
| 14 | PineWiz ADX playbook | https://www.pinewiz.com/playbook/adx | Pine strategy guide | ADX regime examples | ADX cross from range threshold to trend threshold as early-regime event | Useful concept | Deterministic concept | Needs Pine code audit for exact timing | `candles` | Supports transition framing |
| 15 | CrossTrade ADX guide | https://crosstrade.io/learn/technical-indicators/adx | Industry guide | ADX trend/range interpretation | ADX as regime filter: low values chop, higher values trend | Useful concept | Deterministic | No code, no backtest authority | `candles` | Supports filter role, not implementation proof |
| 16 | QuantStock ADX strategy guide | https://quantstock.org/strategy-guide/adx | Strategy guide | ADX use cases | ADX filters trend-following and range-bound conditions | Useful concept | Deterministic | Strategy claims need validation | `candles` | Supports ADX-only control design |
| 17 | Szetela et al. - Trend and volume on Bitcoin | https://link.springer.com/article/10.1007/s40822-021-00166-5 | Academic paper | Open-access article, ADX methodology | Uses Wilder ADX on Bitcoin to measure trend strength/direction; finds weak volume-trend dependency | Benchmark/caution | Deterministic daily ADX | No trading signal; no entry timing claim | `candles`, volume | Supports BTC-specific ADX relevance and volume caution |
| 18 | Gerritsen et al. - Technical trading rules in Bitcoin | https://dspace.library.uu.nl/handle/1874/407735 | Academic paper | Abstract and metadata | Trend-following rules, especially range breakout, showed forecasting power in strongly trending markets | Benchmark candidate | Deterministic rule family | Daily data and exact rules require full paper | `candles` | Supports trend regime relevance, not selected rule |
| 19 | Technical trading and cryptocurrencies | https://link.springer.com/article/10.1007/s10479-019-03357-1 | Academic paper | Technical trading rule framework | Crypto technical rules can be studied systematically across parameterizations | Benchmark/caution | Deterministic families | Risk of multiple-testing and data snooping | `candles` | Supports strict pre-result thresholds |
| 20 | A Decade of Evidence of Trend Following in Cryptocurrencies | https://arxiv.org/abs/2009.12155 | Academic/preprint | Abstract | Crypto markets may suit trend following; reports walk-forward trend-following evidence | Benchmark candidate | Systematic trend rules | Cross-asset/portfolio, not BTC 15m entry | `candles` | Supports trend persistence hypothesis |
| 21 | Market regime detection via realized covariances | https://www.sciencedirect.com/science/article/abs/pii/S0264999322000785 | Academic paper | Abstract/highlights | Regime detection via volatility/covariance models | Useful regime concept | Model-based, not selected | Potential hindsight labels | OHLC-derived returns | Supports regime research framing |
| 22 | Trend Following Trading Under a Regime Switching Model | https://scholarworks.wmich.edu/math_pubs/38/ | Academic paper | Abstract | Catch bull market early, ride trend, exit on evidence of bear phase under partial information | Useful concept | Model-based, not selected | Model probabilities not locally implemented | OHLC | Supports transition entry concept |
| 23 | Freqtrade strategy customization docs | https://github.com/freqtrade/freqtrade/blob/develop/docs/strategy-customization.md | Official framework docs | Strategy timing and lookahead warnings | Signals from completed candles open on next candle; incomplete candles are repainting | Methodology reference | Deterministic framework guidance | Explicit lookahead warning | Applies to `candles` | Strong timing discipline reference |
| 24 | Freqtrade lookahead analysis docs | https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md | Official framework docs | Lookahead-bias tool docs | Vectorized full-data backtests require explicit lookahead checks | Methodology reference | Deterministic if used correctly | Highlights future-data risk | Applies to diagnostics | Supports audit checks |

## Source Research Conclusion

Accepted for V1 planning: standard 14-period ADX with 14-period smoothing, standard 14-period Choppiness Index, completed-bar state classification only, hysteresis-style transition from explicit range to explicit trend, direction from `+DI/-DI`, next-bar entry, and controls that isolate ADX, CHOP, simple volatility, timing, and transition value.

Rejected for V1 planning: full-sample hidden states or smoothed HMM/GARCH labels, Pine/TradingView visual state colors as authority, retrospective state relabeling, post-result threshold selection, combining ADX/CHOP with failed volume-confirmed breakout logic, and using trend-to-range as primary directional entry.

## Repo Data Surface Inspection

Schema and coverage were inspected read-only through Python `sqlite3`.

Primary DB: `research_lab/data/crowded_unwind_backtest.db`

| Table | Columns | Use |
| --- | --- | --- |
| `candles` | `id`, `symbol`, `timeframe`, `open_time`, `open`, `high`, `low`, `close`, `volume` | ADX, CHOP, MFE/MAE, returns |
| `aggtrade_buckets` | `id`, `symbol`, `bucket_time`, `timeframe`, `taker_buy_volume`, `taker_sell_volume`, `tfi`, `cvd` | not required for selected V1 |
| `funding` | `id`, `symbol`, `funding_time`, `funding_rate` | not required |
| `open_interest` | `id`, `symbol`, `timestamp`, `oi_value` | not required |
| `force_orders` | `id`, `symbol`, `event_time`, `side`, `qty`, `price` | not required |

Primary BTCUSDT candle coverage:

| Timeframe | Rows | Range UTC | Quality |
| --- | ---: | --- | --- |
| 15m | 195,347 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:30:00+00:00 | 0 gaps, 0 OHLC violations, 10 zero-volume candles |
| 1h | 48,837 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:00:00+00:00 | 0 OHLC violations |
| 4h | 12,210 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:00:00+00:00 | 0 OHLC violations |

Secondary DB: `storage/btc_bot.db`

- Same relevant table shapes.
- BTCUSDT 15m candles: 200,907 rows, 2020-09-01T00:00:00+00:00 to 2026-05-25T21:45:00+00:00.
- One 15m gap of 12,600 seconds.
- Not selected as primary planning source because the research DB has 0 15m gaps and matches prior diagnostics.

Data sufficiency:

- ADX needs high, low, close. Available.
- CHOP needs high, low, close and true range. Available.
- Warmup needs enough history. Available.
- Volume, aggtrade, funding, OI, and force orders are not required for this V1 mechanism.

Implementation feasibility:

- Custom deterministic indicator code is required.
- No external dependency is required.
- `numpy` and `pandas` are available, but the diagnostic can also be implemented with deterministic Python lists if desired.
- Indicator outputs must be aligned so bar `i` uses only candles through bar `i`.

## Extracted Mechanism

Mechanism name: `TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1`

Tradeable event: `RANGE_TO_TREND_STATE_SHIFT`

Definition:

- Range state: completed-bar ADX indicates weak trend and CHOP indicates choppy/range market.
- Trend state: completed-bar ADX indicates trend strength and CHOP indicates trending market.
- Direction: `+DI > -DI` indicates long trend; `-DI > +DI` indicates short trend.
- Transition: prior latched state is range, current explicit state is trend, and the transition is known at current bar close.
- Entry candidate: next bar after transition confirmation.
- Primary returns: measured from next-bar open, not from detection bar.

Observable inputs: `candles.open_time`, `candles.open`, `candles.high`, `candles.low`, and `candles.close`.

No required inputs: no `aggtrade_buckets`, `force_orders`, `funding`, `open_interest`, or external data.

### Indicator Definitions

ADX period:

- `di_period = 14`
- `adx_smoothing = 14`

True Range:

- `tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))`

Directional Movement:

- `up_move = high[i] - high[i-1]`
- `down_move = low[i-1] - low[i]`
- `plus_dm[i] = up_move if up_move > down_move and up_move > 0 else 0`
- `minus_dm[i] = down_move if down_move > up_move and down_move > 0 else 0`

Wilder smoothing:

- first smoothed value is the sum of the first 14 raw values.
- subsequent smoothed value: `smooth[i] = smooth[i-1] - smooth[i-1] / 14 + raw[i]`

Directional indicators:

- `plus_di[i] = 100 * smoothed_plus_dm[i] / smoothed_tr[i]`
- `minus_di[i] = 100 * smoothed_minus_dm[i] / smoothed_tr[i]`
- if denominator is zero, indicators are zero and the bar is excluded from event generation.

DX and ADX:

- `dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i])`
- first ADX value is the average of first 14 DX values.
- subsequent ADX uses Wilder smoothing over DX.

ADX warmup:

- Require at least 150 candles before the first eligible event.
- Reason: StockCharts notes that Wilder smoothing can require around 150 periods for stable ADX values.

Choppiness Index period:

- `chop_period = 14`

Choppiness Index:

- `sum_tr = sum(tr over bars i-13 through i)`
- `range_high = max(high over bars i-13 through i)`
- `range_low = min(low over bars i-13 through i)`
- `chop[i] = 100 * log10(sum_tr / (range_high - range_low)) / log10(14)`
- if `range_high == range_low`, set CHOP to 100 and exclude from directional event generation.

### State Rules

Explicit range state:

- `adx[i] <= 20`
- `chop[i] >= 61.8`

Explicit trend state:

- `adx[i] >= 25`
- `chop[i] <= 38.2`
- `abs(plus_di[i] - minus_di[i]) >= 5`

Direction:

- Long if `plus_di[i] > minus_di[i]`.
- Short if `minus_di[i] > plus_di[i]`.
- No event if `plus_di[i] == minus_di[i]`.

Latched state machine:

- If explicit range state is true, `latched_state = RANGE`.
- If explicit trend state is true, `latched_state = TREND_LONG` or `TREND_SHORT`.
- Neutral bars do not create a new state.
- A candidate transition occurs when current explicit state is trend and prior latched state at `i-1` is range.
- The last explicit range bar must be no more than 12 bars before `i`; otherwise the transition is stale and excluded.

Rationale for hysteresis: ADX and CHOP have gray zones by design. Requiring a direct one-bar jump from range thresholds to trend thresholds would likely under-sample the mechanism. The latched model is deterministic, uses only past state, and the 12-bar staleness limit prevents ancient ranges from being classified as fresh transitions.

Deterministic rule:

For each BTCUSDT 15m bar `i`:

1. Require at least 150 prior candles.
2. Compute ADX, +DI, -DI, and CHOP through bar `i`.
3. Update explicit state using bar `i`.
4. If bar `i` is explicit trend:
   - require prior latched state at `i-1` was range.
   - require last explicit range bar in `[i-12, i-1]`.
   - assign direction from `+DI/-DI`.
   - set `detection_bar = i`.
   - set `state_known_bar = i`.
   - set `entry_candidate_bar = i+1`.
5. Exclude events without a valid `i+1` entry bar and outcome horizon.

Earliest knowable bar:

- Bar `i` at close.

Required confirmation bars:

- No future confirmation bars.
- Optional diagnostic variant may require one persistence bar, but that would be a separate timing model and not the primary V1 rule. The primary V1 rule uses `confirmation_bar = i`.

Required data tables:

- `candles`

Invalidation condition:

- Median net return after costs <= 0.
- Post-entry ER < 1.2.
- Profit factor < 1.2.
- Median MFE consumed before entry > 70%.
- ADX lag audit shows median lag > 3 bars and lag-adjusted MFE consumed > 70%.
- Any primary control cohort beats main on ER.
- Walk-forward fewer than 2 of 4 folds positive.
- Sample size < 100 candidate events.
- Any lookahead/timing violation found.

Expected edge behavior:

- Range state indicates compressed, low-trend conditions.
- Trend state indicates directional movement has become strong enough to persist.
- CHOP should reject false ADX strength inside choppy structures.
- ADX should reject low-CHOP directional noise without enough trend strength.
- If valid, post-entry continuation should persist long enough to overcome ADX lag and costs.

## ADX Lag Model

ADX lag is structural, not incidental.

Reasons: ADX uses smoothed TR, smoothed +DM, smoothed -DM, DX, and smoothed ADX. The default 14/14 calculation means current ADX is a delayed representation of prior directional movement, and source documentation explicitly warns that ADX has lag and can require long warmup for stable values.

Planning consequence: the diagnostic must not claim that ADX detects the first trend impulse. It tests whether the trend persists after ADX/CHOP confirmation. If the move is mostly complete before confirmation, the mechanism fails even if state labels are accurate.

ADX lag audit metric:

- For each event, define an audit-only `raw_move_start_bar`.
- Long event raw start: earliest bar in `[last_explicit_range_bar + 1, detection_bar]` where close breaks the prior 10-bar high in the event direction.
- Short event raw start: earliest bar in the same window where close breaks the prior 10-bar low.
- If no raw start exists, set `raw_move_start_bar = detection_bar`.
- `adx_lag_bars = detection_bar - raw_move_start_bar`.

Lag-adjusted accessibility:

- `lag_mfe_before_entry` measures favorable movement from `raw_move_start_bar` through `entry_candidate_bar - 1`.
- `lag_mfe_after_entry` measures favorable movement from `entry_candidate_bar` through the outcome horizon.
- `lag_mfe_consumed_pct = lag_mfe_before_entry / (lag_mfe_before_entry + lag_mfe_after_entry)`.

Lag invalidation:

- If median `adx_lag_bars > 3` and median `lag_mfe_consumed_pct > 70%`, STOP.
- This lag audit cannot rescue the mechanism. It can only explain failure.

## Timing Model

| Bar | Definition | `TREND_RANGE_STATE_SHIFT` |
| --- | --- | --- |
| `pre_state_bar` | Last bar before transition decision | `i-1`, prior latched state must be RANGE |
| `detection_bar` | Bar where explicit trend state is observed | `i` |
| `state_known_bar` | First bar where full state is knowable without future data | `i` at close |
| `confirmation_bar` | Bar confirming ADX/CHOP trend state | `i` |
| `entry_candidate_bar` | Earliest realistic entry | `i+1` |
| `label_available_bar` | Bar where entry label is available | `i+1` |
| `return_start_bar` | Bar primary returns start from | `i+1` |

Primary returns must start at `entry_candidate_bar = i+1`, never at `raw_move_start_bar`, `pre_state_bar`, `detection_bar`, or intrabar threshold crossing.

Detection-bar returns are audit-only and used only to measure MFE consumed before realistic entry.

Entry price assumption: primary diagnostic uses `open[i+1]`; if `open[i+1]` is missing or non-positive, exclude the event before outcome measurement. No same-bar close fill is primary.

## MFE Accessibility Design

For each candidate event:

Direction:

- Long: favorable move is price above entry.
- Short: favorable move is price below entry.

Primary MFE before entry:

- Long: `max(high from detection_bar through entry_candidate_bar - 1) - close[detection_bar]`
- Short: `close[detection_bar] - min(low from detection_bar through entry_candidate_bar - 1)`
- With primary timing, this is usually the detection bar only.

Primary MFE after entry:

- Long: `max(high from entry_candidate_bar through entry_candidate_bar + 20) - entry_price`
- Short: `entry_price - min(low from entry_candidate_bar through entry_candidate_bar + 20)`

Primary MAE after entry:

- Long: `entry_price - min(low from entry_candidate_bar through entry_candidate_bar + 20)`
- Short: `max(high from entry_candidate_bar through entry_candidate_bar + 20) - entry_price`

Total MFE:

- `max(0, mfe_before_entry) + max(0, mfe_after_entry)`

MFE consumed:

- `mfe_before_entry / total_mfe` when `total_mfe > 0`.
- If total MFE is zero, classify the event as 100% consumed for accessibility summary.

Lag-adjusted MFE:

- Same calculations, but start the before-entry window at `raw_move_start_bar`.
- This is audit-only and exists to quantify ADX lag.

Time metrics:

- Detection to entry: 1 bar, 15 minutes.
- Raw move start to detection: `adx_lag_bars`.
- Raw move start to entry: `entry_candidate_bar - raw_move_start_bar`.
- Entry to MFE: offset of post-entry max favorable price.

Accessibility gates:

- Median primary MFE consumed before entry > 70% => STOP.
- Median primary MFE consumed before entry < 60% => timing acceptable.
- Median lag-adjusted MFE consumed > 70% with ADX lag > 3 bars => STOP.

## Return and Cost Model

Primary horizon:

- 20 bars after entry (`i+1` through `i+20`), equal to 5 hours on 15m data.

Additional horizons:

- 5 bars.
- 10 bars.
- 40 bars audit-only for trend persistence.

Primary return proxy:

- Long: `(exit_reference - entry_price) / entry_price`
- Short: `(entry_price - exit_reference) / entry_price`

Exit references: fixed 5-bar, 10-bar, and 20-bar closes from entry, MFE/MAE over 20 bars, and R-multiple proxy using structural stop.

Structural stop proxy:

- Long: minimum low between `last_explicit_range_bar` and `detection_bar`.
- Short: maximum high between `last_explicit_range_bar` and `detection_bar`.
- If structural stop distance is zero or invalid, exclude R-multiple but keep return metrics.

Cost assumption:

- Minimum round-trip cost: 0.10% (`0.001`) for fees/slippage proxy unless a current project-standard cost is explicitly loaded.
- Sensitivity: 0.15% round trip audit-only.

Primary metrics: event count, median net return, mean net return, expectancy ratio, profit factor, win rate, average win/loss ratio, median MFE consumed before entry, median ADX lag bars, lag-adjusted MFE consumed, control comparison, and walk-forward stability.

## Baseline Comparison

Trial-00095 reference: ER approximately 2.1, PF approximately 4.6, 271 historical trades, win rate approximately 56%, walk-forward validated, active PAPER deployment.

Primary comparison decision:

- This V1 mechanism is planned as a standalone entry feasibility diagnostic.
- It is not planned as a trial-00095 filter-lift diagnostic.
- Filter-lift analysis may be reported as audit-only context if trial-00095 trade timestamps are available, but it must not rescue a failed standalone result.

Comparison questions:

1. Is the candidate genuinely different?

- Trial-00095: sweep/reclaim reversal with flow/confluence.
- Candidate: deterministic range-to-trend regime transition using ADX and CHOP.
- No sweep, reclaim, liquidation, breakout-volume, or TFI requirement.

2. Is the candidate good enough standalone?

- Must have post-entry ER > 1.2 to avoid STOP.
- Must have PF > 1.5 for EXPLORE.
- To challenge trial-00095 as replacement, must approach ER > 2.1 and PF > 4.0.

3. Is the candidate useful as orthogonal edge?

- Could be worth exploring with ER > 1.5, PF > 1.5, low overlap, and different regime exposure.
- Must beat all controls and show walk-forward stability.

Benchmark decision rules:

- ER > 2.1 and PF > 4.0: candidate may challenge benchmark after walk-forward.
- ER > 1.5, PF > 1.5, low overlap: alternative/orthogonal edge candidate.
- ER 1.2 to 1.5: INCONCLUSIVE unless filter-lift is the explicitly approved next milestone.
- ER < 1.2 or PF < 1.2: STOP.
- ER < 0 after costs: STOP.

## Control Cohort Design

Controls must be deterministic and defined before results.

Control 1: Simple volatility percentile transition

- Detect 14-bar realized volatility rising from below 35th percentile to above 65th percentile.
- Direction from 20-bar close-to-close momentum.
- Entry at `i+1`.
- Purpose: test whether ADX/CHOP adds information beyond simple volatility regime transition.
- Invalidation: if this control beats main on ER, the selected mechanism does not justify complexity.

Control 2: ADX-only transition

- Prior latched state: `adx <= 20`.
- Current trend state: `adx >= 25`.
- Direction from `+DI/-DI`.
- No CHOP requirement.
- Entry at `i+1`.
- Purpose: isolate CHOP contribution.
- Invalidation: if ADX-only beats main, CHOP filter is not adding value.

Control 3: CHOP-only transition

- Prior latched state: `chop >= 61.8`.
- Current trend state: `chop <= 38.2`.
- Direction from 20-bar close-to-close momentum.
- No ADX requirement.
- Entry at `i+1`.
- Purpose: isolate ADX contribution.
- Invalidation: if CHOP-only beats main, ADX lag may be harmful.

Control 4: Shifted-entry timing

- Same exact main signal.
- Entry delayed to `i+3`.
- Purpose: test timing sensitivity and MFE decay after state confirmation.
- Invalidation: if delayed entry performs similarly or better, next-bar timing is not capturing unique accessible edge.

Control 5: Same-state non-transition

- Select bars with explicit trend state and similar ADX/CHOP bins to candidate events.
- Exclude bars where prior latched state was range.
- Entry at `i+1`.
- Purpose: test whether transition matters beyond simply being in a trend state.
- Invalidation: if non-transition trend state beats main, transition event adds no information.

Control 6: Opposite-regime transition

- Trend-to-range transition: prior latched state trend, current explicit range.
- Direction uses prior trend direction, then tests continuation from `i+1`.
- Purpose: negative control for using the wrong regime transition.
- Invalidation: if trend-to-range continuation beats range-to-trend continuation, the primary transition thesis is suspect.

Control 7: Deterministic random-offset control

- Shift main event timestamps by +137 bars.
- Preserve original event direction.
- Exclude shifted events that overlap main candidate events or lack outcome horizon.
- Entry at shifted bar +1.
- Purpose: control for market drift and data mining.
- Invalidation: if random-offset performs similarly or better, candidate lacks signal content.

## Walk-Forward Design

Primary research range:

- Use primary research DB BTCUSDT 15m candles from 2020-09-01 to 2026-03-28.

Suggested folds:

| Fold | Date range |
| --- | --- |
| Fold 1 | 2020-09-01 to 2021-12-31 |
| Fold 2 | 2022-01-01 to 2023-06-30 |
| Fold 3 | 2023-07-01 to 2024-12-31 |
| Fold 4 | 2025-01-01 to 2026-03-28 |

Walk-forward pass:

- At least 3 of 4 folds have positive median net return.
- At least 3 of 4 folds have ER > 1.0.
- No fold has catastrophic PF below 0.8 when sample size is adequate.

No optimization:

- Initial diagnostic uses fixed planning thresholds.
- No post-result threshold tuning inside V1.
- If thresholds fail, the result is STOP or INCONCLUSIVE, not "try ADX 22."

## Invalidation Criteria

STOP gates:

- Median net return after costs <= 0.
- Post-entry ER < 1.2.
- Profit factor < 1.2.
- Win rate < 45% and average win/loss ratio does not compensate.
- Median primary MFE consumed before entry > 70%.
- Median `adx_lag_bars > 3` and median lag-adjusted MFE consumed > 70%.
- Any primary control cohort beats main on ER.
- Walk-forward: fewer than 2 of 4 folds positive.
- Sample size < 100 candidate events.
- More than 5% of candles excluded due invalid OHLC or indicator denominator issues.
- Signal requires future bars, full-sample labels, or post-hoc relabeling.
- Result depends on changing thresholds after seeing outcomes.

EXPLORE gates:

- Median net return after costs > 0.
- Post-entry ER > 1.5.
- Profit factor > 1.5.
- Win rate > 45% with average win/loss ratio >= 1.5, or win rate > 52%.
- Median primary MFE consumed before entry < 60%.
- Median lag-adjusted MFE consumed before entry < 70%.
- Main cohort beats all controls on ER.
- Walk-forward: at least 3 of 4 folds positive.
- Sample size >= 200 events.
- Trial-00095 overlap is low if exact trade timestamps are available.

INCONCLUSIVE gates:

- Sample size between 50 and 99 events.
- Mixed fold results with ER 1.2 to 1.5.
- Controls are underpowered due sample size.
- Indicator denominator exclusions exceed 5% but can be traced to data quality rather than logic.

## Diagnostic Artifact Design

If implemented after Claude audit approval, expected artifacts:

- `research_lab/diagnostics/trend_range_state_shift_feasibility_v1.py`
- `research_lab/reports/trend_range_state_shift_feasibility_v1.md`
- `research_lab/reports/trend_range_state_shift_feasibility_v1.json`
- `tests/test_research_lab/test_trend_range_state_shift_feasibility_v1.py`

Expected report sections: executive summary with one result recommendation, data coverage and exclusions, ADX/CHOP calculation verification, mechanism/timing verification, ADX lag audit, candidate metrics, MFE accessibility, controls, trial-00095 comparison, walk-forward fold metrics, and invalidation gate table.

Expected tests: ADX/CHOP use only current and prior completed candles, first eligible event occurs after warmup, state machine is deterministic, transition cannot use future bars, entry and return start equal `i+1`, MFE calculations are correct, ADX lag audit cannot affect selection, controls are isolated, and output is reproducible.

## Scope Boundaries

Allowed after planning approval: research-only diagnostic under `research_lab/diagnostics`, research-only tests under `tests/test_research_lab`, and reports under `research_lab/reports`.

Not allowed: production strategy code, FeatureEngine/SignalEngine changes, Governance/Risk/execution changes, settings changes, trial-00095 modification, promotion logic, HMM/GARCH dependency installation, volatility breakout rescue, threshold tuning after results, or lower-timeframe pivot inside this V1.

## Recommendation: IMPLEMENT ONE DIAGNOSTIC

Diagnostic name: `TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1`

Mechanism summary: Detect a completed-bar transition from a latched range state (`ADX <= 20` and `CHOP >= 61.8`) to an explicit trend state (`ADX >= 25`, `CHOP <= 38.2`, directional `+DI/-DI` spread), enter on the next 15m bar, and measure returns only from that realistic entry.

Timing: prior state at `i-1`, transition detected and known at bar `i` close, entry at bar `i+1` (1-bar / 15-minute delay), primary returns from `i+1`.

Expected MFE accessibility: Primary entry delay is only one bar, but ADX lag is structurally larger. The diagnostic is worth implementing only because the lag is measurable before any result interpretation. STOP if median primary MFE consumed exceeds 70%, or if ADX lag exceeds 3 bars while lag-adjusted MFE consumed exceeds 70%.

Estimated sample size: likely 100-400 events over 2020-09-01 to 2026-03-28 after warmup and state filters. If fewer than 100 events, STOP by sample gate.

Estimated timeline: 1 week for diagnostic implementation, focused tests, report, and JSON artifact.

Next: Codex implements the diagnostic only after Claude approves this planning document.
