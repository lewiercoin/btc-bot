# VOLATILITY_BREAKOUTS_EDGE_DISCOVERY_V1_PLAN

Planning date: 2026-05-28
Milestone: VOLATILITY_BREAKOUTS_EDGE_DISCOVERY_V1_PLANNING
Mode: Quant Research / Edge Discovery Mode
Status: PLANNING_COMPLETE - awaiting Claude audit before any implementation

## Scope

This is a planning-only research milestone.

Allowed output:

- Source research.
- Repo data surface inspection.
- One extracted deterministic mechanism.
- Timing model.
- MFE accessibility design.
- Baseline comparison design.
- Control cohort design.
- Pre-result invalidation criteria.
- One recommendation.

Not allowed in this milestone:

- No diagnostic scripts.
- No backtests or experiments.
- No result data.
- No production code changes.
- No FeatureEngine, SignalEngine, Governance, Risk, execution, orchestrator, settings, or trial-00095 changes.
- No candidate promotion.

Selected mechanism:

- `VOLUME_CONFIRMED_RANGE_BREAKOUT`

Rejected for this milestone:

- `BB_KC_SQUEEZE_DONCHIAN_BREAKOUT`, because it has more layers, more parameters, and greater risk of late state recognition.
- Any pure ATR-slope expansion setup, because `VOLATILITY-BREAKOUT-RESEARCH-V1` already failed with ER 0.52 after entering mid-to-late expansion.

## Prior Research Context

Recent research changed the research question from pattern existence to tradable accessibility.

| Diagnostic or report | Key result | Planning implication |
| --- | --- | --- |
| `VOLATILITY_BREAKOUTS_RECONNAISSANCE_V1` | Data sufficient, literature mixed, recommendation PROCEED to planning. | Full plan can proceed, but implementation is not yet approved. |
| `VOLATILITY-BREAKOUT-RESEARCH-V1` | Failed with ER 0.52; 15m ATR expansion detection entered too late. | Do not rescue ATR-slope expansion; choose a different mechanism with earlier knowable state. |
| `LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1` | 15m and 5m both STOP; MFE 100% consumed before entry. | MFE accessibility is mandatory, and faster timing alone does not save a weak mechanism. |
| `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` | No post-sweep knowable state had positive median net return after costs. | Primary returns must start at realistic entry, never detection. |

This plan opens a genuinely new mechanism family: price range breakout confirmed by contemporaneous volume and taker-flow participation. It is not a sweep/reclaim variant, not liquidation reversal, and not ATR-slope rescue.

## Research Question

When BTCUSDT compresses into a deterministic recent range, does a completed-bar breakout with elevated volume and aligned taker flow preserve enough post-entry MFE to be tradable after realistic next-bar entry?

Primary hypothesis:

- Range boundaries are fully known before the breakout bar.
- Breakout, volume spike, and TFI alignment become knowable at breakout-bar close.
- Entry at the next 15m bar (`i+1`) may capture continuation before MFE is consumed.
- Volume and taker-flow confirmation should beat ordinary range breaks and volume-only or price-only controls.

## Source Research Method

Search coverage included:

- Academic and preprint sources on Bitcoin technical trading rules, Bollinger/Donchian breakouts, volatility regimes, and crypto backtesting.
- GitHub implementations of crypto breakout systems and Donchian/channel strategies.
- TradingView/Pine sources for Donchian, Bollinger BandWidth, squeeze, and channel breakout logic.
- Freqtrade documentation for next-candle execution, vectorized rules, and lookahead pitfalls.
- Industry strategy writeups with breakout metrics, volume confirmation rules, and false-breakout warnings.

Source inspection standard:

- Prefer code or implementation artifacts when available.
- Treat blogs and TradingView pages as mechanism vocabulary unless source code is inspectable.
- Classify lookahead and determinism explicitly.
- Extract mechanisms, not performance claims.

## Source Coverage Matrix

| # | Source | URL | Type | Inspected artifact | Extracted mechanism | Classification | Determinism | Lookahead/repainting | Data availability | Applicability |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Gerritsen et al., The profitability of technical trading rules in the Bitcoin market | https://research-portal.uu.nl/en/publications/the-profitability-of-technical-trading-rules-in-the-bitcoin-marke | Academic paper | Abstract and repository metadata | Trading range breakout had Bitcoin forecasting power, especially in strong trends. | Benchmark candidate | Deterministic daily rule family | No lookahead visible in abstract; full paper needed for exact rule | OHLC available | Supports range breakout family, not exact 15m rule |
| 2 | Finance Research Letters DOI page for Gerritsen et al. | https://doi.org/10.1016/j.frl.2019.08.011 | Academic citation | DOI metadata | Same trading-range-breakout evidence. | Benchmark candidate | Deterministic concept | Full methodology not visible | OHLC available | Confirms peer-reviewed source |
| 3 | Arda, Bollinger Bands under Varying Market Regimes | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5775962 | SSRN preprint | Abstract | BTC/USDT breakout behavior depends on volatility structure and directional persistence. | Useful concept | Deterministic indicator family | Abstract only; code not inspected | OHLC available | Supports regime dependence and warns against universal rule |
| 4 | Day et al., The profitability of Bollinger Bands trading bitcoin futures | https://ideas.repec.org/a/taf/apeclt/v30y2023i11p1437-1443.html | Academic paper | RePEc abstract | Bollinger futures trading had positive holding-period returns. | Benchmark candidate | Deterministic Bollinger rule | Full rule details not visible | OHLC available | Supports volatility-band trading evidence, but not selected mechanism |
| 5 | Kaya and Mostowfi, Low-volatility strategies for highly liquid cryptocurrencies | https://www.sciencedirect.com/science/article/pii/S1544612321004116 | Academic paper | Abstract/highlights | Volatility state carries information in highly liquid crypto portfolios. | Useful concept | Deterministic portfolio sort | Not a breakout rule | OHLC available | Supports volatility state relevance only |
| 6 | Poluri, Donchian Channel Breakout with ATR-Based Risk Management | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6272239 | SSRN working paper | Abstract/search artifact | BTC daily Donchian breakout with ATR risk control. | Needs validation | Deterministic concept | Abstract only | OHLC available | Supports Donchian stack but not enough for implementation source |
| 7 | Gate Research momentum indicator backtest | https://www.gate.com/tr/research/article/gate-research-application-and-backtesting-of-momentum-indicators-in-the-crypto-market | Industry backtest | Article metrics | Bollinger breakout sample reports high PF over few trades. | Benchmark candidate | Deterministic described rule | TradingView settings not audited | OHLC available | Evidence that selective breakouts can look strong, but sample small |
| 8 | Boring Edge Bitcoin Donchian backtest | https://boringedge.com/bitcoin-donchian-channel-breakout-turtle-trading-backtest/ | Industry backtest | Article rules/metrics | Bitcoin Donchian trend breakout had low frequency, low win rate, large winners. | Benchmark candidate | Deterministic described rule | Not independently reproducible | OHLC available | Sets expectation: trend profile, low frequency, high drawdown |
| 9 | Fractiz Breakout Continuation | https://www.fractiz.com/strategies/breakout-continuation/ | Strategy/backtest page | Rule description and metrics | Close outside prior N-bar high/low with bracket exits. | Benchmark candidate | Deterministic | Uses prior N bars excluding current bar | OHLC available | Useful realistic PF/win-rate anchor |
| 10 | richkuo/go-trader | https://github.com/richkuo/go-trader | GitHub repo | Strategy file reference | Donchian breakout implementation with shifted channel. | Useful implementation | Deterministic | Shifted prior values reduce lookahead | OHLC available | Good timing reference |
| 11 | go-trader raw Donchian file | https://raw.githubusercontent.com/richkuo/go-trader/main/shared_strategies/donchian_breakout.py | GitHub raw code | Raw file | Prior-bar channel concept. | Useful implementation | Deterministic | No future bars apparent from inspected artifact | OHLC available | Supports using prior range only |
| 12 | SC4RECOIN simple crypto breakout strategy | https://github.com/SC4RECOIN/simple-crypto-breakout-strategy | GitHub repo | README and file tree | Prior-day range breakout, end-of-day close. | Useful concept | Deterministic | Live target uses prior completed daily candle | OHLC available | Confirms crypto range breakout pattern |
| 13 | SC4RECOIN backtester | https://raw.githubusercontent.com/SC4RECOIN/simple-crypto-breakout-strategy/main/backtester/trader.py | GitHub raw code | `backtester/trader.py` | Computes target from prior completed day range and trades intraday break. | Useful implementation | Deterministic | No future bars in target; intrabar fills depend on high/low assumptions | OHLC available | Useful but intrabar fill assumptions not used in this plan |
| 14 | SC4RECOIN live trader | https://raw.githubusercontent.com/SC4RECOIN/simple-crypto-breakout-strategy/main/trader/trader.go | GitHub raw code | `trader/trader.go` | Places stop-market order based on previous day range. | Useful implementation | Deterministic/stateful live execution | Uses previous day candle; no future data | OHLC available | Supports prior-range target concept; execution not relevant |
| 15 | PyQuantLab OBV/ATR breakout | https://www.pyquantlab.com/articles/Breakout%20Strategy%20with%20OBV%20and%20ATR%20Confirmation.html | Quant blog with code | Article code snippets and metrics | Price high/low breakout confirmed by OBV and ATR. | Useful concept | Deterministic | Uses fixed forward horizon in example; entry realism simplified | OHLCV available; OBV can be approximated from volume | Supports volume-confirmed breakout concept |
| 16 | Freqtrade strategy customization docs | https://github.com/freqtrade/freqtrade/blob/develop/docs/strategy-customization.md | Official docs | Strategy entry and lookahead sections | Entry signals open on subsequent candle; rolling calculations avoid lookahead. | Useful methodology | Deterministic framework guidance | Explicitly warns against future data and resample/merge lookahead | OHLCV available | Strong timing discipline reference |
| 17 | Freqtrade strategy repository | https://github.com/freqtrade/freqtrade-strategies | GitHub repo | README | Community strategies require pair/timeframe-specific backtests. | Useful caution | Varies by strategy | Strategy-specific | OHLCV available | Supports not trusting generic strategy claims |
| 18 | TradingView Donchian Breakout Strategy | https://www.tradingview.com/script/hyYvFjux-Donchian-Breakout-Strategy/ | TradingView open-source page | Description and release notes | Donchian breakout with trailing lower-channel stop and trend filter. | Useful concept | Deterministic if code inspected | Release notes mention bar timing and removed lookahead setting | OHLC available | Important warning for prior/current bar timing |
| 19 | TradingView Bollinger BandWidth Squeeze Breakout | https://www.tradingview.com/script/6H7qOTkZ-Bollinger-BandWidth-Squeeze-Breakout/ | TradingView protected script | Description | BBW compression and breakout bias. | Needs validation | Concept deterministic | Source protected; repaint cannot be audited | OHLC available | Not selected for V1 diagnostic |
| 20 | TradingView Apex Volatility Squeeze & Breakout | https://www.tradingview.com/script/cebymIj7-Apex-Volatility-Squeeze-Breakout-Pineify/ | TradingView script page | Description | Squeeze zone, band cross labels, optional volume confirmation. | Useful vocabulary | Deterministic concept | Source partly inaccessible in fetched artifact | OHLCV available | Supports volume confirmation vocabulary, not source authority |
| 21 | DEXTools crypto trading strategies guide | https://www.dextools.io/tutorials/crypto-trading-strategies-beginners-guide-2026 | Industry guide | Breakout, range, volume filter, backtest pitfalls sections | Horizontal range breakout waits for close beyond range and volume confirmation. | Useful concept | Deterministic described rule | Not code; claims need validation | OHLCV available | Closest conceptual match to selected mechanism |
| 22 | DEXTools crypto backtesting guide | https://www.dextools.io/tutorials/what-is-backtesting-in-crypto-guide-2026 | Industry guide | Donchian example and pitfalls | Trend breakout has low win rate and large average wins; costs matter. | Useful caution | Deterministic described rule | Not code | OHLCV available | Sets realistic metrics and cost caution |
| 23 | CSDN/DEV Freqtrade advanced strategy analysis | https://blog.csdn.net/henrylin9999/article/details/153775208 | Blog/code snippet | BreakoutTrendStrategy snippet | Close above prior rolling high plus volume multiple and ATR rising. | Useful concept but not authority | Deterministic snippet | Needs `.shift(1)` on rolling high to avoid lookahead | OHLCV available | Supports volume multiple range breakout, but ATR-rising part rejected |
| 24 | trustdan trend-following backtesting strategies | https://github.com/trustdan/trend-following-backtesting-strategies | GitHub repo | README performance matrix | Turtle/Seykota style trend following with Donchian/ATR variants. | Benchmark candidate | Deterministic per script | Individual scripts not fully inspected | OHLC available | Warns naive variants can underperform |
| 25 | CoinQuant ETH Bollinger Bands backtest | https://www.coinquant.ai/blog/bollinger-bands-backtest-on-ethereum-what-6-months-of-data-shows | Blog/backtest | Article rules/metrics | BB squeeze/reversion variant produced weak PF. | Negative benchmark | Deterministic described rule | No obvious future data | OHLCV available | Warns squeeze alone is insufficient |
| 26 | StockCharts Keltner Channels | https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/keltner-channels | Indicator docs | Definition page | EMA plus/minus ATR envelope. | Definition source | Deterministic | Definition only | OHLC available | Not selected for V1, useful background |

## Source Research Conclusion

Accepted for V1 planning:

- Completed-bar range breakout.
- Volume confirmation using completed breakout-bar volume versus prior baseline.
- Directional taker-flow confirmation using `aggtrade_buckets.tfi`.
- Next-bar entry after all conditions are known.

Rejected for V1 planning:

- ATR-slope expansion as primary signal, because that is a failed local mechanism.
- Protected or unaudited TradingView squeeze scripts as implementation authority.
- Intrabar stop/limit fills based on high/low assumptions.
- Retest entries, because they add timing delay and likely consume MFE.
- Pattern-drawn discretionary breakouts such as triangles or flags.

## Repo Data Surface Inspection

Schema and coverage were inspected read-only through Python `sqlite3`.

### Actual Tables and Columns

Primary DB: `research_lab/data/crowded_unwind_backtest.db`

| Table | Columns | Use |
| --- | --- | --- |
| `candles` | `id`, `symbol`, `timeframe`, `open_time`, `open`, `high`, `low`, `close`, `volume` | range detection, breakout, MFE/MAE, candle volume |
| `aggtrade_buckets` | `id`, `symbol`, `bucket_time`, `timeframe`, `taker_buy_volume`, `taker_sell_volume`, `tfi`, `cvd` | volume confirmation, TFI alignment |
| `funding` | `id`, `symbol`, `funding_time`, `funding_rate` | optional metadata only |
| `open_interest` | `id`, `symbol`, `timestamp`, `oi_value` | optional metadata only |
| `force_orders` | `id`, `symbol`, `event_time`, `side`, `qty`, `price` | not required |

Secondary DB: `storage/btc_bot.db`

- Same relevant table shapes.
- More recent BTCUSDT candles but one 15m gap and no useful force orders.
- Not required for primary planning.

### Coverage

| Data surface | Count | Range UTC | Quality note |
| --- | ---: | --- | --- |
| Research DB BTCUSDT 15m candles | 195,347 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:30:00+00:00 | 0 detected 15m gaps, 0 OHLC violations, 10 zero-volume candles |
| Research DB BTCUSDT 1h candles | 48,837 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:00:00+00:00 | context only |
| Research DB BTCUSDT 4h candles | 12,210 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:00:00+00:00 | context only |
| Research DB BTCUSDT 15m aggtrade buckets | 195,150 | 2020-09-01T00:00:00+00:00 to 2026-03-28T21:00:00+00:00 | 0 non-positive volume buckets |
| Research DB BTCUSDT 60s aggtrade buckets | 2,927,122 | 2020-09-01T00:00:00+00:00 to 2026-03-28T21:14:00+00:00 | optional fine alignment |
| Storage DB BTCUSDT 15m candles | 200,907 | 2020-09-01T00:00:00+00:00 to 2026-05-25T21:45:00+00:00 | 1 gap of 12,600 seconds |
| Storage DB BTCUSDT 15m aggtrade buckets | 200,622 | 2020-09-01T00:00:00+00:00 to 2026-05-24T23:45:00+00:00 | 0 non-positive volume buckets |

### Data Sufficiency Assessment

Sufficient:

- Range boundaries and breakout close from `candles`.
- Candle volume spike from `candles.volume`.
- Directional taker-flow confirmation from `aggtrade_buckets.tfi`.
- MFE/MAE from post-entry candle highs/lows.

Potential issues:

- `candles` has 10 zero-volume 15m bars in the primary DB; diagnostic must skip or flag zero-volume breakout bars and document counts.
- `aggtrade_buckets` has slightly fewer 15m rows than candles; diagnostic must require an aligned 15m bucket for any TFI-confirmed event or classify the event as data-gap excluded before results.
- 60s buckets are optional. V1 should use 15m buckets to avoid unnecessary timeframe alignment complexity.

Verdict:

- Data is sufficient for `VOLUME_CONFIRMED_RANGE_BREAKOUT`.

## Extracted Mechanism

Mechanism name: `VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1`

Definition:

- Consolidation range: prior completed 20 bars define a bounded range.
- Compression gate: prior 20-bar range width percentile is low enough versus recent history.
- Breakout: completed bar close breaks above prior range high or below prior range low by a minimum distance.
- Volume confirmation: breakout-bar volume is materially above prior completed-bar volume baseline.
- Directional flow confirmation: breakout-bar TFI aligns with breakout direction.
- Entry candidate: next bar after breakout confirmation.
- Primary returns: measured from next-bar open/close assumption defined in diagnostic, never from range start or intrabar breakout.

Observable inputs:

- `candles.open_time`, `open`, `high`, `low`, `close`, `volume`.
- `aggtrade_buckets.bucket_time`, `taker_buy_volume`, `taker_sell_volume`, `tfi`.

Deterministic rule:

For each BTCUSDT 15m bar `i`:

1. Require at least 140 prior bars.
2. Define `range_window = bars i-20 through i-1`.
3. Define:
   - `range_high = max(high over range_window)`
   - `range_low = min(low over range_window)`
   - `range_width_pct = (range_high - range_low) / close[i-1]`
4. Define recent range-width baseline from completed bars only:
   - compute 20-bar range width for each bar ending in `i-120` through `i-1`
   - `range_width_threshold = percentile_35(recent_range_widths)`
5. Compression condition:
   - `range_width_pct <= range_width_threshold`
6. Breakout condition:
   - long: `close[i] > range_high`
   - short: `close[i] < range_low`
7. Breakout distance condition:
   - `abs(close[i] - boundary) / close[i] >= 0.0015`
   - This avoids one-tick breaks without introducing ATR-slope rescue.
8. Volume condition:
   - `volume[i] >= 1.5 * median(volume over bars i-20 through i-1)`
   - Require `volume[i] > 0`.
9. TFI condition:
   - long: aligned 15m `aggtrade_buckets.tfi[i] > 0`
   - short: aligned 15m `aggtrade_buckets.tfi[i] < 0`
10. If all conditions pass:
   - signal direction is breakout direction.
   - `state_known_bar = i`
   - `entry_candidate_bar = i+1`

Earliest knowable bar:

- Bar `i` at close.

Required confirmation bars:

- None after breakout close. The signal uses bar `i` and prior completed bars only.

Required data tables:

- `candles`
- `aggtrade_buckets`

Invalidation condition:

- Median net return after costs <= 0.
- Post-entry ER < 1.2.
- Profit factor < 1.5.
- MFE consumed before entry > 70%.
- Any primary control cohort beats candidate on ER.
- Walk-forward fewer than 3 of 4 folds positive.
- Sample size < 100.
- Any lookahead/timing violation found.

Expected edge behavior:

- Prior compression indicates accumulated pending directional pressure.
- Close beyond the range boundary confirms that the market accepted price outside the range.
- Elevated volume indicates participation, not thin wick noise.
- TFI alignment indicates aggressive flow supports breakout direction.
- Next-bar entry should preserve enough continuation MFE if the mechanism is tradable.

## Novelty and Rescue Assessment

Why this is new:

- Uses range boundary known before breakout, not ATR expansion state.
- Uses completed breakout close plus volume/TFI confirmation.
- Entry occurs at `i+1`, not mid-expansion after multiple ATR-slope bars.
- Hypothesis is continuation after range acceptance, not sweep/reclaim reversal or liquidation exhaustion.

Why this is not ATR-slope rescue:

- ATR slope is not a trigger.
- ATR expansion is not a confirmation requirement.
- The prior failure point, late expansion-state recognition, is avoided by making the boundary and baseline known before the breakout bar.
- Breakout distance uses fixed percent threshold for noise control, not ATR-rising detection.

## Timing Model

| Bar | Definition | `VOLUME_CONFIRMED_RANGE_BREAKOUT` |
| --- | --- | --- |
| `range_detection_bar` | Last bar needed to define range and compression state | `i-1` |
| `detection_bar` | Bar where raw breakout occurs | `i` |
| `state_known_bar` | First bar where full signal is knowable without future data | `i` at close |
| `confirmation_bar` | Bar confirming breakout, volume, and TFI | `i` |
| `entry_candidate_bar` | Earliest realistic entry | `i+1` |
| `label_available_bar` | Bar where primary entry label is available | `i+1` |
| `return_start_bar` | Bar primary returns start from | `i+1` |

Primary returns:

- Must start at `entry_candidate_bar = i+1`.
- Must not start at `range_detection_bar`, `detection_bar`, range boundary, or intrabar breakout price.

Detection-bar returns:

- Audit-only.
- Can measure opportunity existing before entry, but cannot validate tradable returns.

Entry price assumption for diagnostic:

- Primary diagnostic should use `open[i+1]` as conservative next-bar entry.
- Secondary sensitivity may record `close[i]` fill as audit-only only if clearly labeled non-primary.

## MFE Accessibility Design

For each candidate event:

Direction:

- Long breakout: favorable move is price above entry.
- Short breakout: favorable move is price below entry.

MFE before entry:

- Long: `max(high from bar i through i) - close[i]`
- Short: `close[i] - min(low from bar i through i)`
- Because the signal becomes knowable only at close of `i`, pre-entry MFE is intrabar breakout-bar opportunity that was not fully tradable under completed-bar rules.

MFE after entry:

- Long: `max(high from i+1 through i+20) - entry_price`
- Short: `entry_price - min(low from i+1 through i+20)`

MAE after entry:

- Long: `entry_price - min(low from i+1 through i+20)`
- Short: `max(high from i+1 through i+20) - entry_price`

Total MFE:

- `max(0, MFE_before_entry) + max(0, MFE_after_entry)`

MFE consumed:

- `MFE_before_entry / total_mfe` when `total_mfe > 0`.
- If total MFE is zero, classify as 100% consumed/failed for accessibility summary.

Time metrics:

- Detection to entry: `1` bar, 15 minutes.
- Entry to post-entry MFE: offset of max favorable price in bars `i+1` through `i+20`.
- Breakout-bar close to entry gap: `open[i+1] - close[i]` signed by direction.

Accessibility gate:

- Median MFE consumed before entry > 70% => STOP.
- Median MFE consumed before entry < 50% => timing promising.
- A 1-bar delay is theoretically earlier than the failed ATR-slope expansion diagnostic; the diagnostic must prove this empirically.

## Return and Cost Model

Primary horizon:

- 20 bars after entry (`i+1` through `i+20`), matching a 5-hour 15m continuation window.

Primary return proxy:

- Long: `(exit_reference - entry_price) / entry_price`
- Short: `(entry_price - exit_reference) / entry_price`

For planning, the diagnostic should report:

- fixed 5-bar, 10-bar, and 20-bar forward returns from entry;
- MFE/MAE over 20 bars;
- R-multiple proxy using structural stop;
- cost-adjusted net returns.

Cost assumption:

- Minimum round-trip cost: 0.10% (`0.001`) for fees/slippage proxy unless a current project-standard cost is explicitly loaded.
- Sensitivity: 0.15% round trip audit-only.

Primary metrics:

- event count;
- median net return;
- mean net return;
- expectancy ratio (ER);
- profit factor;
- win rate;
- median MFE consumed before entry;
- control cohort comparison;
- walk-forward fold stability.

## Baseline Comparison

Trial-00095 reference:

- ER approximately 2.1.
- PF approximately 4.6.
- 271 historical trades.
- Win rate approximately 56%.
- Walk-forward validated.
- Active PAPER deployment.

Comparison questions:

1. Is the candidate genuinely different?

- Trial-00095: sweep/reclaim reversal with flow/confluence.
- Candidate: range breakout continuation with volume and TFI confirmation.
- Expected overlap should be low, but diagnostic must measure overlap if trial-00095 trade timestamps are available.

2. Is the candidate good enough standalone?

- Must have post-entry ER > 1.2 to justify implementation follow-up.
- Must have PF > 1.5 for explore.
- To challenge trial-00095 as replacement, must approach ER > 2.1 and PF > 4.0.

3. Is the candidate useful as orthogonal edge?

- Could be worth exploring with ER > 1.5 and low overlap, even if PF < trial-00095.
- Must not increase portfolio drawdown materially in later validation.

Benchmark decision rules:

- ER > 2.1 and PF > 4.0: candidate may challenge benchmark after walk-forward.
- ER > 1.5, PF > 1.5, low overlap: alternative/orthogonal edge candidate.
- ER < 1.2 or PF < 1.2: STOP unless data gap explains sample failure.
- ER < 0 after costs: STOP.

## Control Cohort Design

Controls must be deterministic and defined before results.

Control 1: Price-only range breakouts

- Same range and compression conditions.
- Same breakout close and distance threshold.
- No volume or TFI confirmation.
- Entry at `i+1`.
- Purpose: test whether volume/TFI adds information beyond price breakout alone.
- Invalidation: if price-only control beats main on ER, the volume-confirmed mechanism is not adding useful information.

Control 2: Breakout without volume spike

- Same range, compression, breakout, distance, and TFI direction.
- Require `volume[i] < 1.0 * median(volume over i-20 through i-1)`.
- Entry at `i+1`.
- Purpose: isolate volume participation.
- Invalidation: if low-volume breakouts perform similarly or better, volume spike does not add edge.

Control 3: Opposite-flow breakout

- Same range, compression, breakout, distance, and volume spike.
- Require TFI opposite direction:
  - long breakout with `tfi[i] < 0`
  - short breakout with `tfi[i] > 0`
- Entry at `i+1`.
- Purpose: test whether taker-flow alignment matters.
- Invalidation: if opposite-flow cohort performs similarly or better, TFI alignment is noise.

Control 4: Shifted-entry control

- Same exact main signal.
- Entry delayed to `i+3`.
- Purpose: test whether early entry timing matters and whether MFE is rapidly consumed.
- Invalidation: if delayed entry performs similarly or better, the claimed early timing advantage is weak.

Control 5: Random deterministic offset

- Same event timestamps shifted by +137 bars, preserving direction alternation by event index.
- Exclude shifted bars that overlap real candidate events.
- Entry at shifted bar +1.
- Purpose: control for market drift and data-mining.
- Invalidation: if random-offset control performs similarly or better, candidate lacks signal content.

Control 6: Wide-range breakout

- Same breakout and volume/TFI requirements.
- Require prior 20-bar range width above trailing 65th percentile instead of below 35th percentile.
- Purpose: test whether compression/range condition matters.
- Invalidation: if wide-range breakouts beat main, the compression thesis is wrong.

## Walk-Forward Design

Primary research range:

- Use primary research DB BTCUSDT 15m candles from 2020-09-01 to 2026-03-28.
- If aligned 15m `aggtrade_buckets` missing for a candle, exclude the event before outcome measurement and count exclusions.

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
- No fold has catastrophic PF below 0.8 with adequate sample.

No optimization:

- Initial diagnostic uses fixed planning thresholds.
- No post-result threshold tuning inside V1.

## Invalidation Criteria

STOP gates:

- Median net return after costs <= 0.
- Post-entry ER < 1.2.
- Profit factor < 1.2.
- Win rate < 45% and average win/loss ratio does not compensate.
- Median MFE consumed before entry > 70%.
- Any primary control cohort beats main on ER.
- Walk-forward: fewer than 2 of 4 folds positive.
- Sample size < 100 candidate events.
- More than 10% of candidate events excluded due to missing aligned `aggtrade_buckets`.
- Signal requires future bars or confirmed pivots without label delay.
- Result depends on changing thresholds after seeing outcomes.

EXPLORE gates:

- Median net return after costs > 0.
- Post-entry ER > 1.5.
- Profit factor > 1.5.
- Win rate > 45% with average win/loss ratio >= 1.5, or win rate > 52%.
- Median MFE consumed before entry < 60%.
- Main cohort beats all controls on ER.
- Walk-forward: at least 3 of 4 folds positive.
- Sample size >= 200 events.
- Trial-00095 overlap demonstrably low or not applicable due missing exact trade table.

IMPLEMENT diagnostic planning gate:

- Source research supports mechanism.
- Data is sufficient.
- Timing model is realistic.
- Controls and invalidation criteria are defined.
- Theoretical MFE accessibility is plausible because entry is only 1 bar after breakout confirmation.

INCONCLUSIVE gates:

- Sample size between 50 and 99 events.
- Data gaps prevent aligned TFI validation.
- Controls are underpowered due small sample.
- Outcome is mixed: ER 1.2-1.5 but weak walk-forward.

## Diagnostic Artifact Design

If implemented after audit approval, expected artifacts:

- `research_lab/diagnostics/volume_confirmed_range_breakout_feasibility_v1.py`
- `research_lab/reports/volume_confirmed_range_breakout_feasibility_v1.md`
- `research_lab/reports/volume_confirmed_range_breakout_feasibility_v1.json`
- `tests/test_research_lab/test_volume_confirmed_range_breakout_feasibility_v1.py`

Expected report sections:

- Executive summary with one result recommendation: STOP / EXPLORE / INCONCLUSIVE.
- Data coverage and exclusion counts.
- Mechanism definition and timing verification.
- Candidate metrics.
- MFE accessibility.
- Control cohort comparison.
- Trial-00095 comparison.
- Walk-forward fold metrics.
- Invalidation gate table.

Expected tests:

- Range excludes current bar.
- Breakout signal known only at bar `i` close.
- Entry and return start equal `i+1`.
- TFI alignment uses same 15m bucket only.
- MFE before and after entry calculations.
- Control cohorts are mutually classified and deterministic.
- Diagnostic reproducibility.

## Scope Boundaries

Allowed after planning approval:

- Research-only diagnostic under `research_lab/diagnostics`.
- Research-only tests under `tests/test_research_lab`.
- Research reports under `research_lab/reports`.

Not allowed:

- No production strategy code.
- No FeatureEngine or SignalEngine changes.
- No Governance/Risk/execution changes.
- No settings changes.
- No trial-00095 modification.
- No promotion logic.
- No ATR-slope rescue.
- No lower-timeframe pivot to 5m/1m inside this V1.

## Recommendation: IMPLEMENT ONE DIAGNOSTIC

Diagnostic name: `VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1`

Mechanism summary: Detect a completed 15m close outside a prior compressed 20-bar range, require breakout-bar volume spike and aligned 15m TFI, then enter on the next 15m bar and measure returns only from that realistic entry.

Timing: range known at bar `i-1`, breakout/volume/TFI state known at bar `i` close, entry at bar `i+1` (1-bar / 15-minute delay).

Expected MFE accessibility: Plausibly better than failed ATR-slope expansion because confirmation delay is one bar and range boundaries are known before breakout; target threshold is median MFE consumed below 60%, hard STOP above 70%.

Estimated sample size: likely 100-400 events over 2020-09-01 to 2026-03-28, depending on compression and volume filters. If fewer than 100 events, result is inconclusive or STOP by sample gate.

Estimated timeline: 1 week for diagnostic implementation, focused tests, report, and JSON artifact.

Next: Codex implements the diagnostic only after Claude approves this planning document.
