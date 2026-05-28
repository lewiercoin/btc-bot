# REGIME_SHIFT_DETECTION_RECONNAISSANCE_V1

**Date:** 2026-05-28
**Researcher:** Codex
**Type:** Quick reconnaissance (data + literature + metrics)

---

## Executive Summary

Regime shift detection has enough data and external support to justify a full planning milestone, but it should not move directly to diagnostic implementation. The local research database has clean BTCUSDT 15m OHLCV from 2020-09-01 through 2026-03-28, plus 15m and 60s `aggtrade_buckets`, funding, open interest, and 2022-2024 force-order data. That is sufficient to derive deterministic volatility, trend/range, flow, funding/OI, and liquidation-stress regime indicators.

The literature base is stronger than the last two failed edge families, but it is also more dangerous methodologically. Hidden Markov Models, Markov-switching GARCH, volatility clustering, ADX/choppiness filters, and regime-aware strategy selection are well supported as modeling frameworks. However, many reported results use daily data, full-sample regime labeling, smoothed state probabilities, or exogenous data we do not store. Those are useful for research design but not automatically tradable on a 15m bot.

The key feasibility issue is not data availability. It is timing and leakage. A regime label must be knowable at bar `i` using only data through bar `i`, and any action must start at `i+1` or later. Full-sample HMM smoothing, in-sample state relabeling, and post-hoc regime interpretation are not acceptable as trading signals. If this family proceeds, the planning document must select one concrete mechanism and explicitly separate online-filtered regime probability from audit-only smoothed labels.

Recommendation: `PROCEED` to a full planning milestone, with constraints. The next plan should test either an interpretable deterministic regime-shift mechanism or an offline-only HMM/GARCH feasibility mechanism with strict walk-forward training and filtered probabilities only. No diagnostic code should be implemented from this reconnaissance alone.

---

## 1. Data Availability Assessment

### Local Database Coverage

Primary database inspected: `research_lab/data/crowded_unwind_backtest.db`

Secondary database inspected: `storage/btc_bot.db`

Inspection method: read-only Python `sqlite3`; no diagnostic code or backtests were implemented.

Relevant primary tables:

| Table | Use for regime shifts | Status |
| --- | --- | --- |
| `candles` | OHLCV, returns, realized volatility, ATR, ADX, trend/range states | Available |
| `aggtrade_buckets` | Taker buy/sell volume, TFI, CVD, flow dominance shifts | Available |
| `funding` | Derivatives crowding and stress context | Available |
| `open_interest` | OI trend/acceleration, leverage regime context | Available |
| `force_orders` | Liquidation-stress regime context, 2022-2024 only | Available but partial |
| `feature_snapshots` | Stored runtime features | Empty |
| `market_snapshots` | Stored runtime snapshots | Empty |
| `decision_outcomes` | Stored regime decisions | Empty |

BTCUSDT coverage:

| Dataset | Rows | Date range UTC | Quality |
| --- | ---: | --- | --- |
| Research DB 15m candles | 195,347 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:30:00+00:00 | 0 gaps, 0 OHLC violations, 10 zero-volume bars |
| Research DB 1h candles | 48,837 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:00:00+00:00 | usable higher-timeframe context |
| Research DB 4h candles | 12,210 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:00:00+00:00 | usable higher-timeframe context |
| Research DB 15m `aggtrade_buckets` | 195,150 | 2020-09-01T00:00:00+00:00 to 2026-03-28T21:00:00+00:00 | taker buy/sell, TFI, CVD |
| Research DB 60s `aggtrade_buckets` | 2,927,122 | 2020-09-01T00:00:00+00:00 to 2026-03-28T21:14:00+00:00 | optional finer flow regime features |
| Research DB `funding` | 6,105 | 2020-09-01T00:00:00+00:00 to 2026-03-28T16:00:00+00:00 | 8h-style funding context |
| Research DB `open_interest` | 524,971 | 2020-09-01T00:00:00+00:00 to 2026-03-29T00:00:00+00:00 | dense OI context |
| Research DB `force_orders` | 146,864 | 2022-01-01T00:02:07.244000+00:00 to 2024-12-01T23:58:59.379000+00:00 | partial liquidation stress |
| `storage/btc_bot.db` 15m candles | 200,907 | 2020-09-01T00:00:00+00:00 to 2026-05-25T21:45:00+00:00 | more recent, one 3.5h gap |

### Regime Detection Feasibility

Assessment: `SUFFICIENT`

Feasible from candles: realized volatility, ATR/price, Bollinger BandWidth, ADX/DI, Choppiness Index, EMA slope, return persistence, range width, and drawdown/run-up state.

Feasible from `aggtrade_buckets`: TFI sign/magnitude, CVD slope, taker buy/sell dominance, flow volatility, flow reversal, and volume participation regimes.

Feasible from derivatives data: funding extremes/sign flips, OI z-score/acceleration, and liquidation-stress clusters for 2022-2024 only.

### Indicator Requirements

| Indicator or model | Feasible locally? | Required input | Notes |
| --- | --- | --- | --- |
| ATR / normalized ATR | Yes | OHLC | already conceptually used in repo |
| Bollinger BandWidth | Yes | close | deterministic |
| ADX / DI | Yes | OHLC | custom calculation required |
| Choppiness Index | Yes | OHLC | custom calculation required |
| realized volatility | Yes | close returns | deterministic |
| volatility clustering | Yes | returns / squared returns | deterministic or GARCH |
| HMM on returns/volatility | Partially | OHLC-derived features | tooling not installed locally |
| Markov-switching regression | Partially | returns/features | `statsmodels` not installed locally |
| GARCH / MS-GARCH | Partially | returns | `arch` not installed; MS-GARCH likely external |
| order-book regimes | No | L1/L2 book history | not available |
| news/sentiment regimes | No | external text/search data | not available |

Local package check:

| Package | Installed? | Implication |
| --- | --- | --- |
| `numpy` | Yes | deterministic numeric feature work feasible |
| `pandas` | Yes | time-series feature work feasible |
| `hmmlearn` | No | HMM plan would need dependency decision |
| `arch` | No | GARCH plan would need dependency decision |
| `statsmodels` | No | Markov regression plan would need dependency decision |
| `sklearn` | No | clustering/PCA plan would need dependency decision |

### Missing Data / Gaps

Non-blockers: order book and sentiment/search data are not required for first-pass deterministic volatility/trend regimes; force orders are optional context; stored runtime regime labels are empty, but raw data is enough to derive labels.

Risks: HMM/GARCH dependencies are not installed, full-sample regime labels can leak future data, regime changes can be detected too late for entry, and stochastic models require fixed seeds plus explicit train/validation separation.

### Verdict

`SUFFICIENT`

We have enough raw data for deterministic and model-based regime research. The blocker is methodological, not data availability.

---

## 2. Literature Review

### Source Coverage Matrix

| # | Source | URL | Type | Classification | Mechanism / metrics | Lookahead risk | Applicability |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Hamilton, Markov switching framework | https://www.jstor.org/stable/1912559 | Academic classic | Model-quality concept | latent regime process for nonstationary time series | high if smoothed states used as live labels | foundational, not crypto-specific |
| 2 | Dynamic volatility modelling of Bitcoin with TV-MS-GARCH | https://www.sciencedirect.com/science/article/pii/S1062940821000164 | Academic paper | Model-quality | Bitcoin volatility regimes with time-varying transition probabilities | model fit may be in-sample | supports BTC volatility regime research |
| 3 | Exploring predictability of cryptocurrencies via Bayesian HMMs | https://arxiv.org/abs/2011.03741 | Academic paper | Model-quality | multi-state HMMs for BTC, ETH, XRP forecasting | must avoid smoothed hindsight states | directly crypto-relevant |
| 4 | Modelling and predicting Bitcoin conditional variance | https://arxiv.org/abs/2401.03393 | Academic paper | Model-quality | Markov-switching GARCH vs stochastic volatility | volatility forecasts, not entries | useful for risk/regime forecasting |
| 5 | Hierarchical HMMs for bearish/bullish markets | https://arxiv.org/abs/2007.14874 | Academic paper | Useful concept | hierarchical HMM classifies bull/bear structures | post-hoc state labels possible | relevant classification framework |
| 6 | Regime-Aware Adaptive Forecasting for Bitcoin | https://link.springer.com/article/10.1007/s10614-026-11338-3 | Academic paper | Model-quality but complex | Gaussian HMM regimes feed specialized forecasters | ML orchestration risk, many degrees of freedom | supports regime-aware modeling, too complex for V1 |
| 7 | Bitcoin Price Regime Shifts: Bayesian MCMC and HMM | https://www.mdpi.com/2227-7390/13/10/1577 | Academic paper | Useful concept | two-state HMM for Bitcoin macro regime shifts | macro variables may not be locally available | supports HMM regime framing |
| 8 | Bubble regime identification in Bitcoin/Ethereum | https://www.sciencedirect.com/science/article/abs/pii/S0165176519304203 | Academic paper | Useful concept | attention-linked bubble regimes | Google search data not local | not directly testable without external data |
| 9 | Low-volatility strategies for liquid cryptocurrencies | https://www.sciencedirect.com/science/article/pii/S1544612321004116 | Academic paper | Benchmark concept | volatility state has predictive portfolio value | cross-sectional not BTC-only entry | supports volatility regime relevance |
| 10 | Regime-switching factor investing with HMMs | https://www.mdpi.com/1911-8074/13/12/311 | Academic paper | Benchmark concept | HMM selects asset/factor exposure by regime | portfolio-level, daily/monthly | supports regime filters as allocation layer |
| 11 | hmmlearn documentation | https://hmmlearn.readthedocs.io/en/stable/api.html | Official docs | Implementation reference | GaussianHMM, Viterbi, posterior probabilities | fitting on full sample leaks if not walk-forward | feasible if dependency approved |
| 12 | statsmodels MarkovRegression docs | https://www.statsmodels.org/stable/_modules/statsmodels/tsa/regime_switching/markov_regression.html | Official docs/code | Implementation reference | first-order Markov switching regression | full-sample fitting/smoothing risk | feasible if dependency approved |
| 13 | arch volatility docs | https://arch.readthedocs.io/en/stable/univariate/volatility.html | Official docs | Implementation reference | ARCH/GARCH volatility models | forecast must be one-step-ahead only | feasible if dependency approved |
| 14 | R MSGARCH package | https://www.rdocumentation.org/packages/MSGARCH/versions/0.17.7 | Package docs | Implementation reference | Markov-switching GARCH estimation and state probabilities | package outside Python stack | concept useful, tooling mismatch |
| 15 | hidden-regime Python package | https://github.com/hidden-regime/hidden-regime | GitHub repo | Useful implementation | HMM pipeline with temporal isolation and event studies | external package, educational disclaimer | good methodology reference |
| 16 | CryptoMarket Regime Classifier | https://github.com/akash-kumar5/CryptoMarket_Regime_Classifier | GitHub repo | Needs validation | OHLCV indicators, HMM labels, LSTM prediction | LSTM and PCA add complexity/overfit risk | useful feature vocabulary only |
| 17 | Sakeeb91 market-regime-detection | https://github.com/Sakeeb91/market-regime-detection | GitHub repo | Useful concept | HMM regime detection for adaptive strategies | repo-specific validation needed | implementation vocabulary |
| 18 | PyQuantLab HMM regime detection | https://www.pyquantlab.com/articles/Market%20Regime%20Detection%20using%20Hidden%20Markov%20Models.html | Blog/code article | Useful implementation concept | Gaussian HMM on market features for bull/bear states | backtest setup needs audit | useful for mechanism sketch |
| 19 | TradingView CHOP Filter ADX + Choppiness | https://www.tradingview.com/script/EGiOI371-CHOP-Filter-ADX-Choppiness-Index/ | TradingView script | Useful deterministic concept | ADX plus Choppiness separates trend/range | source page not enough for production | locally reproducible |
| 20 | TradingView Market Regime Detector Trend + Volatility | https://www.tradingview.com/script/WqotL644-Market-Regime-Detector-Trend-Volatility-AI-Trading-Tech/ | TradingView script | Useful deterministic concept | ADX trend strength plus relative ATR gives four regimes | thresholds discretionary | locally reproducible |
| 21 | TradingView HMM Market Regimes LuxAlgo | https://www.tradingview.com/script/GiOi09Bh-Hidden-Markov-Model-Market-Regimes-LuxAlgo/ | TradingView script | Needs validation | HMM-like probabilities from return/volatility | Pine implementation must be audited for repaint | concept only |
| 22 | TradingView K-Means Regime Detector | https://www.tradingview.com/script/PCUBiICi-K-Means-Regime-Detector/ | TradingView script | Needs validation | clustering into trending/ranging/volatile regimes | clustering stability and repaint risk | concept only |
| 23 | TradingView Market Regime Lite | https://www.tradingview.com/script/YRDJGi8r-Market-Regime-Lite/ | TradingView script | Useful concept | ADX, ATR, volume, structure score regimes | discretionary scoring | locally reproducible if simplified |
| 24 | TradingView Volatility Regime Classifier | https://www.tradingview.com/script/zagpmoKH-Volatility-Regime-Classifier-QuantRegime/ | TradingView script | Useful concept | Hurst, ADX, Choppiness multi-engine classifier | source/thresholds need audit | concept only |
| 25 | QuantStart HMM regime detection | https://www.quantstart.com/articles/hidden-markov-models-for-regime-detection-using-r/ | Quant blog | Useful concept | HMM as risk filter for strategy selection | old R example, not crypto | supports filter rather than entry-first approach |
| 26 | PyMC Labs Bayesian HMM market regimes | https://www.pymc-labs.com/blog-posts/bayesian-hmm-market-regime-detection-pymc | Quant blog | Useful caution | Bayesian HMM identifies regimes; notes hindsight validation | explicitly separates validation from live accuracy | strong lookahead warning |

### Literature Summary

- Total sources inspected: 26.
- Academic/model-quality sources: 10.
- Implementation/package references: 6.
- TradingView/industry concept sources: 7.
- Sources with direct crypto relevance: 9.
- Sources with explicit HMM/MS-GARCH modeling: 12.

Common mechanisms:

- HMM latent states based on returns and volatility;
- Markov-switching GARCH volatility states;
- deterministic ADX plus volatility filters;
- choppiness/range versus trend classification;
- funding/OI/flow stress as regime context;
- regime as strategy selector rather than standalone entry.

Consensus on effectiveness: `MIXED BUT STRONGER FOUNDATION THAN PRIOR FAMILIES`

Regime detection is well supported as a modeling and filtering framework. Evidence that it creates a standalone tradable entry edge is weaker. The safest research direction is regime as a conditional filter or transition event, not a direct price prediction label.

---

## 3. Mechanism Extraction (Preliminary)

### Common Regime Families

1. Volatility regime shift: low realized volatility transitions into high volatility, or high volatility compresses into normal volatility. Inputs are ATR/price, realized volatility, BB width, and squared returns. Feasibility is high; the main risk is late recognition.

2. Trend/range transition: ADX/DI and choppiness detect shift from ranging to trending or trend exhaustion. Inputs are ADX, DI, CHOP, EMA slope, and return persistence. Feasibility is high; ADX lag is the main risk.

3. Flow dominance shift: TFI/CVD changes from balanced to persistent taker buy/sell dominance. Inputs are `aggtrade_buckets`. Feasibility is high; flow noise and overlap with failed volume-breakout logic are the main risks.

4. Crowding/stress regime shift: OI/funding expands, then funding/OI or liquidation stress changes regime. Inputs are funding, open interest, and force_orders. Feasibility is partial because force_orders end 2024-12-01.

5. Probabilistic HMM/GARCH state shift: filtered probability of a latent regime crosses threshold. Inputs are returns, volatility, and trend/flow features. Data exists, tooling is missing, and lookahead risk is high if smoothing is used.

### Detection Signals

Candidate deterministic signals:

- ATR, realized volatility, or BB width percentile crossing;
- ADX/DI and Choppiness threshold changes;
- EMA slope sign/acceleration;
- TFI/CVD rolling z-score persistence;
- OI z-score expansion and funding sign/extreme.

Candidate model-based signals:

- HMM filtered regime probability `P(state_t | data_0:t)`;
- GARCH one-step-ahead volatility forecast;
- Markov-switching filtered probability, not smoothed probability;
- K-means cluster assignment using rolling trained scaler/model.

### Timing Model (Preliminary)

For deterministic regime transition:

| Bar | Definition |
| --- | --- |
| `detection_bar` | bar `i` where regime metric crosses threshold |
| `state_known_bar` | bar `i` at close |
| `confirmation_bar` | bar `i` or `i+k` if persistence required |
| `entry_candidate_bar` | `state_known_bar + 1` |
| `return_start_bar` | same as `entry_candidate_bar` |

For HMM/GARCH regime transition:

| Bar | Definition |
| --- | --- |
| `training_cutoff_bar` | last bar included in model fit |
| `observation_bar` | bar `i` appended to feature stream |
| `state_known_bar` | bar `i` after online filtered probability is computed |
| `entry_candidate_bar` | bar `i+1` |
| `return_start_bar` | bar `i+1` |

Forbidden:

- using full-sample HMM states as if known live;
- using smoothed probability `P(state_t | data_0:T)` for trading labels;
- relabeling hidden states after seeing future returns and measuring from the original bar.

### Preliminary Mechanism Candidates

1. `VOLATILITY_REGIME_TRANSITION_FILTER`

- Detect transition from low to high realized volatility using ATR/BB width percentiles; candles only.

2. `TREND_RANGE_STATE_SHIFT`

- Combine ADX and Choppiness to detect range-to-trend or trend-to-range transitions; candles only; ADX lag risk.

3. `FLOW_DOMINANCE_REGIME_SHIFT`

- Detect persistent TFI/CVD dominance transition over rolling windows; `aggtrade_buckets`; may not predict price direction standalone.

4. `FILTERED_HMM_REGIME_SHIFT`

- Train HMM in rolling windows and use filtered probabilities only; returns, realized volatility, volume/TFI features; dependency and leakage complexity.

Most promising for full planning:

- `TREND_RANGE_STATE_SHIFT` if the project wants deterministic implementation first.
- `FILTERED_HMM_REGIME_SHIFT` if the project accepts dependency/tooling and stricter methodology.

---

## 4. Metrics Assessment

### Realistic ER/PF Expectations

Regime detection should be evaluated differently from direct entry systems:

- As a standalone entry edge, expected ER/PF is uncertain and likely weak.
- As a filter or selector, value may appear as drawdown reduction, fewer bad trades, and better regime-specific expectancy.
- Literature often reports forecasting accuracy, volatility forecast quality, Sharpe, VaR, or classification quality, not ER/PF.

Practical expectations before local validation:

- standalone regime-transition entry ER: 0.8-1.5;
- regime filter lift on another edge: meaningful if it reduces drawdown or improves PF without killing sample size;
- direct HMM strategy PF: likely unstable unless walk-forward and transaction costs are strict;
- deterministic trend/range filters: likely robust as filters, weaker as standalone alpha.

### Comparison to Trial-00095 Baseline

Trial-00095 benchmark:

- ER about 2.1; PF about 4.6; 271 trades; win rate about 56%; walk-forward validated.

Regime shift detection likely cannot beat trial-00095 as a standalone entry without substantial evidence. Its best path may be:

- orthogonal edge around structural transitions;
- filter for when trial-00095 should stand down;
- risk sizing / drawdown control layer;
- setup selector between trend-following and mean-reversion families.

Competitive assessment: `POTENTIALLY USEFUL, NOT YET COMPETITIVE`

This family has a stronger theoretical foundation than volume-confirmed breakout, but the expected metric path is not raw PF dominance. The full plan must define whether the target is standalone entry, filter lift, or risk-regime control.

### Trade Frequency Expectations

Regime transitions should be less frequent than ordinary signals:

- deterministic volatility/trend transitions: likely weekly to monthly depending thresholds;
- HMM state changes: potentially too frequent unless persistence threshold used;
- funding/OI stress shifts: episodic, concentrated during leverage cycles;
- flow-dominance shifts: frequent but noisy at 15m.

Expected useful sample:

- raw state observations: thousands; actual transitions: likely hundreds; high-confidence transitions after persistence filters: possibly 100-400 events.

### Risk Characteristics

Main risks:

- detection lag, full-sample lookahead, state relabeling after outcomes, overfitting thresholds/state count, unstable hidden-state identity across retrains, crypto regime instability, and sample-size collapse under high-confidence filters.

Important lesson from volume-confirmed breakout:

- good MFE accessibility does not prove predictive power;
- regime shift diagnostics must test whether the state adds information beyond ordinary volatility/trend controls.

### Assessment

`PROMISING BUT HIGH METHODOLOGY RISK`

Proceed only if the next milestone narrows the family to one testable mechanism with explicit online knowability.

---

## 5. Data Gaps / Blockers Identification

### Critical Data Gaps

None for deterministic OHLCV/flow regime research.

Potential blockers for model-heavy variants:

- `hmmlearn`, `arch`, `statsmodels`, and `sklearn` are not installed locally;
- full MS-GARCH support may require external packages;
- order-book and sentiment/search data are absent;
- stored runtime feature/regime labels are empty.

Blocker? `NO` for reconnaissance and deterministic planning; `PARTIAL` for HMM/GARCH implementation planning.

### Missing Indicators

Indicators requiring custom calculation:

- ADX/DI, Choppiness Index, realized volatility, BB width, ATR percentile, Hurst estimate if used, rolling flow dominance, and OI/funding z-scores.

Feasible? `YES`

Model tools requiring dependency decision:

- HMM: `hmmlearn` or custom/simple implementation;
- GARCH: `arch` or equivalent;
- Markov switching regression: `statsmodels`;
- clustering/PCA: `sklearn` or deterministic custom alternatives.

### Computational Complexity

| Component | Complexity | Feasibility |
| --- | --- | --- |
| deterministic indicators | O(N), rolling update online | feasible |
| ADX/CHOP/ATR percentiles | O(N) offline, incremental possible | feasible |
| HMM rolling fit | potentially expensive | feasible offline, caution online |
| GARCH rolling fit | expensive | offline first only |
| flow/OI/funding context | O(N) with alignment | feasible |

Real-time feasibility:

- deterministic regime filters are feasible on 15m cycles;
- HMM/GARCH retraining every bar is not appropriate without a separate infrastructure plan;
- periodic retrain plus online filtering may be feasible but must be audited.

### Overfitting and Lookahead Risks

High-risk patterns:

- choosing HMM state count after seeing returns, mapping states with future returns, using smoothed states, threshold tuning after failure, or adding filters to rescue failed volatility breakout/liquidation logic.

Mitigations:

- define mechanism before results, train only on past windows, freeze state interpretation within each validation fold, use deterministic controls, compare against simple ADX/volatility baselines, and measure MFE before/after entry.

### Overall Assessment

`NO DATA BLOCKERS, TOOLING/METHODOLOGY CAUTION`

The family is viable for planning, but only with strict leakage controls.

---

## 6. Recommendation

### Verdict: PROCEED

### Rationale

Proceed to a full planning milestone because the data is sufficient and the literature foundation is stronger than the prior order-flow and volatility breakout families. The repo has enough BTCUSDT OHLCV, flow, funding, OI, and partial liquidation data to derive useful regime features. Academic and implementation sources support HMMs, Markov-switching volatility models, volatility clustering, and deterministic trend/range filters as legitimate regime tools.

The recommendation is cautious because regime detection is prone to attractive but invalid research. A post-hoc regime label can explain history beautifully while being untradable live. Full-sample HMM smoothing, state relabeling, and threshold tuning would violate the project timing discipline. The next milestone must choose one mechanism and define online knowability before any diagnostic code exists.

This family should not be framed as "build an HMM and trade the labels." It should be framed as: identify one regime transition that becomes knowable early enough, then test whether it adds information beyond simple volatility/trend controls and trial-00095 context.

### If PROCEED

- Next milestone: `REGIME_SHIFT_DETECTION_EDGE_DISCOVERY_V1_PLANNING`
- Estimated timeline: 3-5 days.
- Output: planning document only.

Key focus areas:

1. Mechanism selection: choose exactly one of deterministic `TREND_RANGE_STATE_SHIFT`, deterministic `VOLATILITY_REGIME_TRANSITION_FILTER`, or online-filtered `FILTERED_HMM_REGIME_SHIFT`; do not combine all regime ideas into one diagnostic.

2. Timing discipline: define `state_known_bar`, `confirmation_bar`, `entry_candidate_bar`, and `return_start_bar`; for HMM/GARCH, use filtered probabilities only and keep smoothed labels audit-only.

3. Control cohorts: simple volatility percentile baseline, ADX-only or CHOP-only baseline, shifted transition timing, same-state non-transition control, and opposite-regime transition control.

4. Invalidation gates: STOP if state labels require future data, controls match/beat candidate, MFE consumed before entry exceeds 70%, or standalone ER/PF is weak with no filter lift.

5. Benchmark comparison: compare to trial-00095 as benchmark, not as a target to tune around; decide whether the candidate is standalone edge, filter, or risk-regime metadata before implementation.

### If PIVOT

Not recommended now.

Suggested alternatives if planning rejects the family:

- funding/OI stress without liquidation reversal;
- trial-00095 live validation focus;
- portfolio risk-regime sizing as research-lab infrastructure, not edge discovery.

### If BLOCKED

Not blocked.

Critical blocker absent for deterministic regime planning. HMM/GARCH tooling would require a dependency decision, but that is a planning constraint rather than a reason to stop reconnaissance.

### Final Boundary

This report does not approve implementation, diagnostic code, production changes, trial-00095 modification, dependency installation, or promotion. It recommends only a full planning milestone for one regime-shift mechanism.
