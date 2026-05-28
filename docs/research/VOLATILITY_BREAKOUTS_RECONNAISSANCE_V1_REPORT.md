# VOLATILITY_BREAKOUTS_RECONNAISSANCE_V1

**Date:** 2026-05-28  
**Researcher:** Codex  
**Type:** Quick reconnaissance (data + literature + metrics)

---

## Executive Summary

Volatility breakouts have enough data and external support to justify a full planning milestone, but not enough evidence to justify immediate diagnostic implementation. The primary research database has clean BTCUSDT 15m OHLCV from 2020-09-01 through 2026-03-28, with no detected 15m gaps and no OHLC integrity violations. That is sufficient for Donchian, Bollinger, Keltner, ATR, range-width, and volume-confirmed breakout research.

The literature is mixed. Academic and industry sources support trading range breakout, Bollinger breakout, Donchian breakout, and volatility expansion rules in Bitcoin or trend-friendly markets. The same sources also show regime dependence, low trade frequency, whipsaw risk, and realistic profit factors often below the trial-00095 benchmark. The strongest implementation evidence favors simple deterministic prior-range/channel breakout rules with explicit volatility or volume context.

The repo has an important prior warning: `VOLATILITY-BREAKOUT-RESEARCH-V1` failed on 2026-05-13 with ER 0.52 because 15m ATR-expansion detection entered mid-to-late expansion. That failure should prevent a rescue of the same ATR-slope implementation, but it does not close the broader family. Donchian compression breakout, BB/KC squeeze release, Bollinger BandWidth release, and volume-confirmed range breakout remain distinct enough to plan rigorously.

Recommendation: `PROCEED` to `VOLATILITY_BREAKOUTS_EDGE_DISCOVERY_V1_PLANNING`, with one deterministic mechanism, explicit timing model, MFE accessibility design, controls, and pre-result invalidation gates. No diagnostic code should be written from this reconnaissance alone.

---

## 1. Data Availability Assessment

### Local Database Coverage

Primary database inspected: `research_lab/data/crowded_unwind_backtest.db`

Secondary database inspected: `storage/btc_bot.db`

Inspection method: read-only Python `sqlite3`; no diagnostic code or backtests were implemented.

Relevant primary tables:

| Table | Use | Status |
| --- | --- | --- |
| `candles` | OHLCV, range detection, ATR, Bollinger, Keltner, Donchian | Available |
| `aggtrade_buckets` | Taker volume, TFI/CVD, volume confirmation | Available |
| `funding` | Optional regime/context metadata | Available |
| `open_interest` | Optional crowding/context metadata | Available |
| `force_orders` | Not required for pure volatility breakouts | Optional |
| `oi_samples` | Not useful; empty | Non-blocker |

BTCUSDT local coverage:

| Dataset | Rows | Date range UTC | Quality |
| --- | ---: | --- | --- |
| Research DB 15m candles | 195,347 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:30:00+00:00 | 0 gaps, 0 OHLC violations |
| Research DB 1h candles | 48,837 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:00:00+00:00 | usable context |
| Research DB 4h candles | 12,210 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:00:00+00:00 | usable context |
| Research DB 15m `aggtrade_buckets` | 195,150 | 2020-09-01T00:00:00+00:00 to 2026-03-28T21:00:00+00:00 | taker buy/sell, TFI, CVD |
| Research DB 60s `aggtrade_buckets` | 2,927,122 | 2020-09-01T00:00:00+00:00 to 2026-03-28T21:14:00+00:00 | optional finer volume |
| Research DB `funding` | 6,105 | 2020-09-01T00:00:00+00:00 to 2026-03-28T16:00:00+00:00 | optional |
| Research DB `open_interest` | 524,971 | 2020-09-01T00:00:00+00:00 to 2026-03-29T00:00:00+00:00 | optional |
| Research DB `force_orders` | 146,864 | 2022-01-01T00:02:07.244000+00:00 to 2024-12-01T23:58:59.379000+00:00 | optional |
| `storage/btc_bot.db` 15m candles | 200,907 | 2020-09-01T00:00:00+00:00 to 2026-05-25T21:45:00+00:00 | more recent, one 3.5h gap |

### Range Detection Feasibility

Assessment: `SUFFICIENT`

Local OHLCV supports deterministic consolidation/range definitions:

- Donchian range: prior N-bar high and prior N-bar low.
- Range width: `(rolling_high - rolling_low) / close`.
- Bollinger BandWidth: `(upper_band - lower_band) / middle_band`.
- ATR compression: ATR/price or ATR percentile below rolling threshold.
- Swing support/resistance: possible only if pivot label delay is modeled.

No tick data, order book, news, sentiment, or on-chain data is required for first-pass planning.

### Breakout Confirmation Feasibility

Assessment: `SUFFICIENT`

Available confirmation inputs:

- close above/below prior range boundary;
- breakout distance as fraction of ATR;
- candle volume spike;
- 15m taker-volume spike from `aggtrade_buckets`;
- 60s taker-volume aggregation if finer participation is needed;
- directional TFI/CVD alignment;
- ATR or BandWidth expansion at completed-bar close.

The planning document should use completed-bar confirmation and next-bar entry unless it explicitly justifies same-bar close fills.

### Indicator Requirements

| Indicator | Feasible locally? | Required input |
| --- | --- | --- |
| Bollinger Bands / BandWidth | Yes | close |
| ATR | Yes | high, low, close |
| Keltner Channels | Yes | EMA, ATR |
| Donchian Channels | Yes | rolling high/low |
| Volume spike | Yes | candle volume or aggtrade volume |
| TFI/CVD confirmation | Yes | `aggtrade_buckets` |
| Order-book imbalance | No | L1/L2 data absent |
| Footprint imbalance | No | tick price-row bid/ask data absent |

### Missing Data / Gaps

Non-blockers:

- raw tick trades are not required for a first 15m breakout plan;
- order book data is not required for Donchian/Bollinger/Keltner mechanisms;
- external sentiment/news/on-chain data is not required;
- `force_orders` is optional and should not drive this family.

Risks to handle in planning:

- confirmed pivots can create lookahead if used without delayed `state_known_bar`;
- 15m expansion detection previously entered too late;
- 60s volume confirmation must align deterministically to 15m bars.

### Verdict

`SUFFICIENT`

The local data surface is adequate for a full planning document around deterministic 15m volatility breakout mechanisms.

---

## 2. Literature Review

### Source Coverage Matrix

| # | Source | URL | Type | Classification | Mechanism / metrics | Lookahead risk | Applicability |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Gerritsen et al., The profitability of technical trading rules in the Bitcoin market | https://www.sciencedirect.com/science/article/abs/pii/S1544612319303770 | Academic | Model-quality | Daily Bitcoin range breakout had forecasting power and Sharpe outperformance | None visible from abstract | Strong concept; daily timeframe |
| 2 | Utrecht repository page for Gerritsen et al. | https://research-portal.uu.nl/en/publications/the-profitability-of-technical-trading-rules-in-the-bitcoin-marke | Academic repository | Model-quality | Confirms trading range breakout value in strong trends | None visible | Accessible audit reference |
| 3 | Arda, Bollinger Bands under Varying Market Regimes | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5775962 | SSRN/preprint | Model-quality concept | BTC/USDT Bollinger breakout vs mean reversion; regime-dependent | Abstract only | Supports regime-aware planning |
| 4 | Day et al., The profitability of Bollinger Bands trading bitcoin futures | https://ideas.repec.org/a/taf/apeclt/v30y2023i11p1437-1443.html | Academic | Model-quality | Bollinger futures rule; AHPR above 20%, 60-day variant above 50% | Abstract only | Supports Bollinger evidence, more contrarian than breakout |
| 5 | Poluri, Donchian Channel Breakout with ATR-Based Risk Management | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6272239 | SSRN | Needs validation | BTC daily Donchian + ATR risk; outperformance but cost-sensitive | Abstract only | Relevant stack, needs full inspection |
| 6 | Low-volatility strategies for highly liquid cryptocurrencies | https://www.sciencedirect.com/science/article/pii/S1544612321004116 | Academic | Useful concept | Volatility-based crypto portfolios generated excess returns | Not direct breakout | Supports volatility as state variable |
| 7 | Gate Research momentum indicators backtest | https://www.gate.com/tr/research/article/gate-research-application-and-backtesting-of-momentum-indicators-in-the-crypto-market | Industry | Benchmark candidate | Bollinger breakout: 11 trades, 81.82% WR, PF 6.345, DD 2.20% | TradingView settings unaudited | Strong but short sample |
| 8 | Boring Edge Bitcoin Donchian backtest | https://boringedge.com/bitcoin-donchian-channel-breakout-turtle-trading-backtest/ | Blog/backtest | Benchmark candidate | 41 trades in 8.5y, 46.3% WR, 5.3x win/loss, 48.2% CAGR, -53.7% DD | Not fully reproducible | Useful low-frequency anchor |
| 9 | Fractiz Breakout Continuation | https://www.fractiz.com/strategies/breakout-continuation/ | Strategy/backtest page | Benchmark candidate | Donchian breakout samples PF 0.97-1.56, WR 33-38% | Uses prior N bars excluding current | Realistic whipsaw/risk anchor |
| 10 | richkuo/go-trader Donchian implementation | https://github.com/richkuo/go-trader | GitHub code | Useful implementation | Shifted rolling high/low; close crossover signal | Low; shifted by one bar | Directly testable locally |
| 11 | Raw go-trader Donchian code | https://raw.githubusercontent.com/richkuo/go-trader/main/shared_strategies/donchian_breakout.py | GitHub raw code | Useful implementation | Prior-bar channel explicitly avoids lookahead | Low | Good timing reference |
| 12 | LazyBear BB/KC squeeze gist | https://gist.github.com/agualbbus/b601fb2a9eaab86916fd | Pine gist | Useful concept | BB/KC squeeze state | Needs line review | Feasible from OHLCV |
| 13 | Trading Strategy AI Bollinger example | https://github.com/tradingstrategy-ai/tradingview-defi-strategy | GitHub/notebook | Useful concept | Bollinger + RSI with stop; not optimized | Full notebook not reviewed | Implementation reference only |
| 14 | TradingView Donchian Breakout by millerrh | https://www.tradingview.com/script/hyYvFjux-Donchian-Breakout-Strategy/ | TradingView | Useful concept | Donchian break with channel trailing stop; release notes warn on bar timing | Needs code inspection | Relevant timing warning |
| 15 | Apex Volatility Squeeze & Breakout | https://www.tradingview.com/script/cebymIj7-Apex-Volatility-Squeeze-Breakout-Pineify/ | TradingView | Opinion/useful vocabulary | BB width + Keltner/ATR squeeze states | Source not inspectable | Vocabulary only |
| 16 | Bollinger BandWidth Squeeze Breakout | https://www.tradingview.com/script/6H7qOTkZ-Bollinger-BandWidth-Squeeze-Breakout/ | TradingView | Useful concept | BBW compression tiers and expansion | Source not fully audited | Locally reproducible concept |
| 17 | trustdan trend-following Pine repo | https://github.com/trustdan/trend-following-backtesting-strategies | GitHub | Benchmark candidate | Top variants around PF 1.47; failed fast breakout PF 0.131; failed Keltner PF 0.744 | Individual scripts need review | Warning against naive fast breakouts |
| 18 | CoinQuant ETH Bollinger backtest | https://www.coinquant.ai/blog/bollinger-bands-backtest-on-ethereum-what-6-months-of-data-shows | Blog/backtest | Negative benchmark | 14 trades, 57.1% WR, PF 0.46, DD 27.79%, negative Sharpe | No obvious future data | Squeeze alone not enough |
| 19 | StockCharts Keltner Channels | https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/keltner-channels | Indicator docs | Definition source | EMA envelope using ATR | Definition only | Keltner calculation reference |

### Literature Summary

- Total sources inspected: 19.
- Model-quality or benchmark-candidate sources: 11.
- Opinion/vocabulary/definition sources: 8.
- Sources with directly testable deterministic mechanisms: 9.
- Sources with reported performance metrics: 8.
- Sources with code or implementation artifacts inspected: 4.

Common mechanisms:

- Donchian range breakout.
- Bollinger Band breakout.
- Bollinger BandWidth squeeze release.
- BB/KC squeeze release.
- ATR expansion breakout.
- Volume-confirmed range breakout.

Consensus on effectiveness: `MIXED`

The evidence supports planning, not implementation. Breakouts can work in trend/expansion regimes but are vulnerable to chop, costs, parameter sensitivity, and late detection.

---

## 3. Mechanism Extraction (Preliminary)

### Common Volatility Indicators

| Indicator | Definition | Local feasibility | Timing caveat |
| --- | --- | --- | --- |
| Donchian Channel | Prior N-bar high/low define breakout boundaries | `candles.high`, `candles.low` | Must exclude current bar |
| Bollinger Bands | SMA plus/minus K standard deviations | `candles.close` | Known at completed-bar close |
| Bollinger BandWidth | `(upper - lower) / middle` | derived from Bollinger Bands | use prior/completed values only |
| Keltner Channels | EMA plus/minus ATR multiple | OHLC candles | use completed EMA/ATR |
| ATR | rolling true range average | OHLC candles | slope can lag |
| Volume / TFI / CVD | candle or taker participation | `candles`, `aggtrade_buckets` | 60s buckets need deterministic alignment |

### Consolidation Range Definition

Preliminary deterministic definitions:

- Donchian compression: prior N-bar range width below rolling percentile.
- Bollinger compression: BandWidth below trailing percentile.
- BB/KC squeeze: Bollinger Bands inside Keltner Channels.
- ATR compression: ATR/price below trailing percentile.

Concrete planning candidate:

- lookback: prior 20 completed 15m bars;
- `range_high`: max high over prior 20 bars;
- `range_low`: min low over prior 20 bars;
- `range_width_pct`: `(range_high - range_low) / close`;
- compression: prior BandWidth below trailing 120-bar 25th percentile;
- breakout up: current close above prior `range_high`;
- breakout down: current close below prior `range_low`.

### Breakout Confirmation

Potential confirmation signals:

- close outside prior range/channel;
- breakout distance greater than minimum ATR fraction;
- breakout-bar volume above rolling baseline;
- TFI aligns with breakout direction;
- BandWidth or ATR expands versus prior bars;
- close location near high for upside break or low for downside break.

Signals to avoid initially:

- retest entries that delay too long unless MFE accessibility is explicitly measured;
- confirmed swing pivots without delayed label modeling;
- protected TradingView scripts;
- same-bar intrabar fills without lower-timeframe evidence.

### Timing Model (Bar-Unit)

Recommended completed-bar breakout timing:

| Bar | Definition |
| --- | --- |
| `range_detection_bar` | bar `i-1`, last completed bar used for range/compression state |
| `breakout_bar` | bar `i`, close breaks prior range/channel |
| `state_known_bar` | bar `i`, at breakout-bar close |
| `confirmation_bar` | bar `i`, if all confirmation uses bar `i` and prior bars |
| `entry_candidate_bar` | bar `i+1`, first realistic bar after confirmation |
| `return_start_bar` | bar `i+1` |

If follow-through is required, `state_known_bar` becomes `i+1`, `entry_candidate_bar` becomes `i+2`, and `return_start_bar` becomes `i+2`.

Primary returns must never start from range start or intrabar breakout price unless that entry is explicitly tradable.

### Stop Placement

Common stop designs:

- ATR stop: entry minus/plus K ATR.
- Range stop: beyond prior range boundary or opposite side of range.
- Hybrid stop: structural stop capped by ATR multiple.
- Time stop: exit if no follow-through within M bars.

Breakout systems usually need asymmetric reward/risk because win rates are often below 50%.

### Exit Strategy

Common exits:

- fixed R multiple target;
- Donchian trailing exit;
- ATR/Chandelier trailing stop;
- middle-band exit for Bollinger breakout;
- opposite channel breakout.

For the first diagnostic plan, exit design should be secondary to MFE/MAE accessibility: first prove post-entry movement exists.

### Preliminary Mechanism Candidates

| Candidate | Summary | Why it is testable |
| --- | --- | --- |
| `DONCHIAN_COMPRESSION_BREAKOUT_CONTINUATION` | narrow prior N-bar range, close breaks prior high/low, entry next bar | OHLC only, no future bars |
| `BOLLINGER_BANDWIDTH_SQUEEZE_RELEASE` | BandWidth below percentile, close breaks band, BandWidth rises | close-derived and deterministic |
| `BB_KC_SQUEEZE_DONCHIAN_BREAKOUT` | BB inside KC during setup, then Donchian break | OHLC-derived, structurally distinct |
| `VOLUME_CONFIRMED_RANGE_BREAKOUT` | prior range break plus volume/TFI alignment | OHLCV + `aggtrade_buckets` |

Most promising planning candidates:

- `VOLUME_CONFIRMED_RANGE_BREAKOUT`
- `BB_KC_SQUEEZE_DONCHIAN_BREAKOUT`

Reason: both are deterministic, locally testable, and materially different from the failed ATR-slope-only prior implementation.

---

## 4. Metrics Assessment

### Realistic ER/PF Expectations

External evidence suggests a wide but mostly modest range:

- academic Bitcoin trading-rule evidence supports range breakout Sharpe outperformance, not specific ER/PF;
- Boring Edge reports strong Bitcoin Donchian trend performance but only 41 trades in 8.5 years and high drawdown;
- Fractiz Donchian samples show PF about 0.97-1.56 with win rates around 33-38%;
- Gate Research reports a strong one-year Bollinger breakout sample with PF 6.345 over 11 trades;
- trustdan's trend-following repo reports best variants near PF 1.47 and failed variants below PF 1.0;
- CoinQuant's ETH squeeze variant reports PF 0.46.

Expected local range before validation:

- naive ER: 0.8-1.3;
- well-filtered ER: 1.2-2.0;
- optimistic ER: above 2.0 only if selective and orthogonal;
- realistic PF: 1.1-1.8;
- PF above 4.0 should be treated as suspicious until walk-forward validated;
- win rate: 30-50% for trend continuation, possibly higher for strict filtered samples.

### Comparison to Trial-00095 Baseline

Trial-00095 benchmark:

- ER about 2.1.
- PF about 4.6.
- 271 trades over roughly 4 years.
- Win rate about 56%.
- Walk-forward validated and active in PAPER.

Volatility breakout expectation:

- probably lower win rate;
- likely lower PF unless highly selective;
- potentially lower overlap because it targets expansion/continuation rather than sweep/reclaim reversal;
- likely different holding period and risk profile.

Competitive assessment: `MARGINAL BUT POTENTIALLY ORTHOGONAL`

This family is unlikely to beat trial-00095 on raw PF without strict filtering. It can still be worth planning if it captures different regimes and has acceptable standalone expectancy.

### Trade Frequency Expectations

| Mechanism style | Expected frequency |
| --- | --- |
| Daily Donchian/Turtle Bitcoin | about 5 trades/year in one industry source |
| 15m Donchian without compression | frequent but noisy |
| 15m squeeze + breakout + volume filter | roughly 2-8 events/month, to validate |
| strict BB/KC squeeze release | roughly 1-4 events/month, to validate |

Prior local volatility breakout result:

- 63 trades;
- ER 0.52;
- failure due to 15m detection latency;
- enough to reject that specific mechanism, not the whole family.

### Risk Characteristics

Expected risks:

- false breakouts in choppy regimes;
- lower win rate than reversal systems;
- long losing streaks;
- large drawdowns if stops are wide and entries are late;
- strong dependence on trend/volatility regime;
- high sensitivity to costs if frequency is high.

Required planning focus:

- MFE before entry versus MFE after entry;
- control cohorts for ordinary breakouts and non-compression breakouts;
- benchmark comparison to trial-00095;
- explicit STOP gates before results.

### Assessment

`MARGINAL`

The expected metrics are not clearly competitive with trial-00095, but the family is sufficiently orthogonal and data-supported to merit a full planning document.

---

## 5. Data Gaps / Blockers Identification

### Critical Data Gaps

None for first-pass planning.

Available data is enough for:

- Donchian ranges;
- Bollinger Bands and BandWidth;
- Keltner Channels;
- ATR;
- candle volume spikes;
- taker-volume and TFI/CVD confirmation;
- next-bar timing tests;
- MFE/MAE accessibility.

Not required initially:

- raw tick data;
- order book;
- force-order liquidation stream;
- sentiment/news/on-chain data.

Blocker? `NO`

### Missing Indicators

No missing indicator blocks planning.

Indicators requiring custom calculation:

- ATR;
- SMA/EMA;
- rolling standard deviation;
- Bollinger Bands and BandWidth;
- Keltner Channels;
- Donchian Channels;
- rolling volume multiple or z-score;
- range-width percentile.

Feasible to implement later? `YES`

### Computational Complexity

| Component | Complexity | Real-time feasibility |
| --- | --- | --- |
| Rolling range detection | O(N) offline, rolling update online | Yes |
| Breakout confirmation | O(1) per completed bar after indicators | Yes |
| Indicator calculation | O(N) offline, incremental online | Yes |
| MFE/MAE diagnostic | O(events * horizon), offline only | Yes |

Overall feasibility: `YES`

### Regulatory / Exchange Limitations

No regulatory or exchange blocker exists for offline research.

Any future live deployment would require separate execution, slippage, governance, and risk review. That is out of scope here.

### Prior-Failure Boundary

`VOLATILITY-BREAKOUT-RESEARCH-V1` failed because 15m ATR expansion detection entered after the best expansion phase had already passed.

This creates a planning constraint:

- do not rerun ATR-slope expansion as the same hypothesis;
- do not tune thresholds to rescue the failed setup;
- do not measure returns from range start or breakout intrabar price;
- require MFE accessibility from realistic entry.

It is not a blocker because the broader family includes distinct mechanisms that were not exhausted.

### Overall Assessment

`NO BLOCKERS`

Data is sufficient, indicators are feasible, computational cost is acceptable, and the prior failure narrows but does not close the research family.

---

## 6. Recommendation

### Verdict: PROCEED

### Rationale

Proceed to a full planning milestone because the local data surface is adequate and the external literature provides enough deterministic mechanisms to justify deeper review. The strongest candidates are not discretionary chart patterns; they are prior-range/channel breakout rules with compression and participation filters that can be stated precisely and audited for lookahead.

The recommendation is cautious. Expected standalone metrics are likely weaker than trial-00095 unless the next plan finds a selective and genuinely early mechanism. Trial-00095 remains the benchmark: ER about 2.1, PF about 4.6, and 271 historical trades. A volatility breakout candidate should not be treated as a replacement unless it is validated with realistic entry timing, MFE accessibility, controls, and walk-forward testing.

The prior failed volatility breakout result is a warning against ATR-slope rescue. The next planning document should choose one genuinely distinct mechanism, most likely `VOLUME_CONFIRMED_RANGE_BREAKOUT` or `BB_KC_SQUEEZE_DONCHIAN_BREAKOUT`, and define STOP gates before any diagnostic code exists.

### If PROCEED

- Next milestone: `VOLATILITY_BREAKOUTS_EDGE_DISCOVERY_V1_PLANNING`
- Estimated timeline: 3-5 days.
- Output: planning document only.

Key focus areas:

1. Mechanism selection

- Pick one deterministic rule.
- Reject pure ATR-slope expansion reruns as disguised rescue.

2. Timing discipline

- Define `range_detection_bar`, `breakout_bar`, `state_known_bar`, `entry_candidate_bar`, and `return_start_bar`.
- Primary returns start from realistic entry, not range start or intrabar breakout.

3. MFE accessibility

- Measure MFE before entry and after entry.
- Stop if more than 70% of MFE is consumed before realistic entry.

4. Controls

- non-compression breakouts;
- compression without breakout;
- breakout without volume confirmation;
- deterministic shifted-entry control;
- weak-close or opposite-flow breakout control.

5. Benchmark comparison

- Compare ER, PF, win rate, drawdown, frequency, overlap, and regime coverage to trial-00095.
- Allow continuation only if the mechanism is competitive or demonstrably orthogonal with acceptable standalone expectancy.

### Final Boundary

This report does not approve implementation, diagnostic code, production changes, trial-00095 modification, or promotion. It recommends only a full planning milestone for one deterministic volatility breakout mechanism.
