# FILTERED_HMM_REGIME_SHIFT_EDGE_DISCOVERY_V1_PLAN

Planning date: 2026-05-28
Milestone: FILTERED_HMM_REGIME_SHIFT_EDGE_DISCOVERY_V1_PLANNING
Mode: Quant Research / Edge Discovery Mode
Status: PLANNING_COMPLETE - awaiting Claude audit before any implementation

## Scope

This is a planning-only research milestone.

Allowed output: source research, repo data surface inspection, one extracted HMM-based mechanism, timing model, HMM lag model, MFE accessibility design, baseline comparison design, control cohort design, pre-result invalidation criteria, dependency requirements, and one recommendation.

Not allowed in this milestone: diagnostic scripts, backtests or experiments, result data, production code changes, FeatureEngine/SignalEngine/Governance/Risk/execution/orchestrator/settings/trial-00095 changes, dependency installation, or candidate promotion.

Selected mechanism:

- `FILTERED_HMM_REGIME_SHIFT`

Tradeable V1 form:

- `HMM_RANGE_TO_TREND_FILTERED_PROBABILITY_CROSSING`

Why this form: a Gaussian HMM trained on returns and realized volatility identifies latent regime states. Filtered (forward-only) probabilities crossing a threshold indicate a range-to-trend transition. Direction from momentum/DI context at threshold crossing. Entry at i+1 after filtered probability is known.

Rejected for this planning milestone:

- `TREND_RANGE_STATE_SHIFT` (deterministic ADX/CHOP), because the diagnostic returned STOP: ER=-0.027, PF=0.954, 321 events, 0/4 walk-forward folds positive. The mechanism has no edge despite acceptable timing (21.5% MFE consumed before entry).
- Markov-switching GARCH, because `arch` package is not installed, MS-GARCH is fragile on crypto data, and computational cost is higher than HMM for V1 feasibility.
- Custom Bayesian state filter, because lower expected signal power than HMM while still requiring non-trivial implementation.
- Any rescue of failed deterministic regime-shift logic. This plan does not reuse ADX/CHOP thresholds, volume breakout logic, or liquidation reversal rules from failed families.

## Prior Research Context

| Diagnostic or report | Key result | Planning implication |
| --- | --- | --- |
| `REGIME_SHIFT_DETECTION_RECONNAISSANCE_V1` | DONE, PROCEED. Data sufficient, 26 sources, 12 HMM/GARCH sources, methodology risks flagged. | Full plan can proceed for HMM mechanism. |
| `TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1` | STOP. ER=-0.027, PF=0.954, 321 events, 0/4 folds positive. Good timing (21.5% MFE consumed), no edge. | Deterministic ADX/CHOP regime transition has no predictive power. HMM tests a fundamentally different hypothesis: latent state clusters vs indicator crossovers. |
| `VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1` | STOP. ER=-0.092, PF=0.857, 3 controls beat main, 14.95% MFE consumed. | Good timing insufficient; mechanism must add information beyond controls. |
| `LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1` | STOP. 15m and 5m both had 100% MFE consumed. | MFE accessibility mandatory. |
| `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` | No post-sweep state had positive median net return after costs. | Primary returns must start at realistic entry, never detection. |

This plan opens a probabilistic regime-transition mechanism. It is fundamentally different from deterministic ADX/CHOP: HMM identifies latent state clusters from multivariate features (returns, volatility, volume) rather than applying fixed indicator thresholds. The hypothesis is that latent states capture regime structure that deterministic thresholds cannot.

## Research Question

When a Gaussian HMM trained on BTCUSDT 15m returns and realized volatility transitions from a low-volatility range state to a high-volatility trend state — as measured by filtered (forward-only) probability crossing a threshold — does next-bar directional entry preserve enough post-entry MFE and expectancy to be tradable after costs?

Primary hypothesis:

- A Gaussian HMM with 2-3 states learns distinct volatility/return distributions corresponding to range and trend regimes.
- Filtered probabilities P(state_t | data_0:t) computed using only the forward pass provide online-knowable regime estimates.
- When filtered probability of the high-volatility trend state crosses a threshold (e.g., 0.7), this indicates a regime transition.
- Direction from momentum/DI context at the transition bar provides directional entry.
- Entry at i+1 may capture continuation before MFE is consumed.
- HMM may detect regime transitions earlier or more accurately than deterministic ADX/CHOP because it jointly models returns and volatility distributions.

Primary risks:

- Smoothing temptation: hmmlearn's `predict_proba` and `score_samples` use the forward-backward algorithm, which computes smoothed P(state_t | data_0:T). Using these directly for trading signals would be lookahead. The diagnostic must implement a custom forward-only pass.
- State relabeling: mapping state 0 = "trend" after seeing which state had positive returns is cherry-picking. State interpretation must be frozen per fold based on emission parameters (mean return, variance), not outcomes.
- Overfitting: state count, covariance type, training window size, initialization seed, and probability threshold create many degrees of freedom.
- State identity drift: state 0 in fold 1 may represent a different regime than state 0 in fold 2 after retraining. Careful feature-based interpretation freezing is required.
- HMM lag: filtered probabilities update gradually (not instantaneously like threshold crossings). The move may be partially consumed before P(trend) exceeds threshold.

## Source Research Method

Search coverage included: HMM theory and implementation references, hmmlearn API documentation (filtered vs smoothed probability distinction), Bitcoin/crypto HMM regime detection papers, walk-forward HMM training methodology, state interpretation stability, Markov-switching model references, and regime-aware strategy design.

Source inspection standard: prefer primary API documentation and academic sources, inspect code implementations where available, classify lookahead and smoothing risk explicitly, extract mechanism components and methodology constraints rather than performance claims.

## Source Coverage Matrix

| # | Source | URL | Type | Extracted mechanism | Classification | Lookahead risk | Applicability |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Hamilton, Markov switching framework | https://www.jstor.org/stable/1912559 | Academic classic | Latent regime process for nonstationary time series | Model-quality concept | High if smoothed states used as live labels | Foundational theory |
| 2 | Dynamic volatility modelling of Bitcoin with TV-MS-GARCH | https://www.sciencedirect.com/science/article/pii/S1062940821000164 | Academic paper | Bitcoin volatility regimes with time-varying transition probabilities | Model-quality | In-sample model fit risk | Supports BTC volatility regime research |
| 3 | Exploring predictability of cryptocurrencies via Bayesian HMMs | https://arxiv.org/abs/2011.03741 | Academic paper | Multi-state HMMs for BTC, ETH, XRP forecasting | Model-quality | Must avoid smoothed hindsight states | Directly crypto-relevant |
| 4 | Modelling and predicting Bitcoin conditional variance | https://arxiv.org/abs/2401.03393 | Academic paper | Markov-switching GARCH vs stochastic volatility | Model-quality | Volatility forecasts, not entries | Risk/regime forecasting reference |
| 5 | Hierarchical HMMs for bearish/bullish markets | https://arxiv.org/abs/2007.14874 | Academic paper | Hierarchical HMM classifies bull/bear structures | Useful concept | Post-hoc state labels possible | Classification framework |
| 6 | Regime-Aware Adaptive Forecasting for Bitcoin | https://link.springer.com/article/10.1007/s10614-026-11338-3 | Academic paper | Gaussian HMM regimes feed specialized forecasters | Model-quality but complex | ML orchestration risk, many degrees of freedom | Too complex for V1 |
| 7 | Bitcoin Price Regime Shifts: Bayesian MCMC and HMM | https://www.mdpi.com/2227-7390/13/10/1577 | Academic paper | Two-state HMM for Bitcoin macro regime shifts | Useful concept | Macro variables may not be locally available | Supports HMM regime framing |
| 8 | Bubble regime identification in Bitcoin/Ethereum | https://www.sciencedirect.com/science/article/abs/pii/S0165176519304203 | Academic paper | Attention-linked bubble regimes | Useful concept | Google search data not local | Not directly testable |
| 9 | Low-volatility strategies for liquid cryptocurrencies | https://www.sciencedirect.com/science/article/pii/S1544612321004116 | Academic paper | Volatility state has predictive portfolio value | Benchmark concept | Cross-sectional not BTC-only | Supports volatility regime relevance |
| 10 | Regime-switching factor investing with HMMs | https://www.mdpi.com/1911-8074/13/12/311 | Academic paper | HMM selects asset/factor exposure by regime | Benchmark concept | Portfolio-level, daily/monthly | Supports regime filters |
| 11 | hmmlearn API documentation (v0.3.3) | https://hmmlearn.readthedocs.io/en/latest/api.html | Official docs | GaussianHMM: fit, predict, predict_proba, score_samples, decode | Implementation reference | **CRITICAL**: predict_proba and score_samples use forward-backward (smoothed). Custom forward pass required for filtered probabilities. | Primary implementation reference |
| 12 | hmmlearn Tutorial | https://hmmlearn.readthedocs.io/en/latest/tutorial.html | Official docs | Training, inference, multiple sequences, persistence | Implementation reference | fit() on full sample leaks if not walk-forward; states reorder across retrains | Training methodology reference |
| 13 | statsmodels MarkovRegression | https://www.statsmodels.org/stable/_modules/statsmodels/tsa/regime_switching/markov_regression.html | Official docs/code | First-order Markov switching regression | Implementation reference | Full-sample fitting/smoothing risk | Alternative not selected for V1 |
| 14 | arch volatility docs | https://arch.readthedocs.io/en/stable/univariate/volatility.html | Official docs | ARCH/GARCH volatility models | Implementation reference | Forecast must be one-step-ahead only | Not selected for V1 |
| 15 | hidden-regime Python package | https://github.com/hidden-regime/hidden-regime | GitHub repo | HMM pipeline with temporal isolation and event studies | Useful implementation | Educational disclaimer | Good methodology reference |
| 16 | CryptoMarket Regime Classifier | https://github.com/akash-kumar5/CryptoMarket_Regime_Classifier | GitHub repo | OHLCV indicators, HMM labels, LSTM prediction | Needs validation | LSTM and PCA add complexity/overfit risk | Feature vocabulary only |
| 17 | Sakeeb91 market-regime-detection | https://github.com/Sakeeb91/market-regime-detection | GitHub repo | HMM regime detection for adaptive strategies | Useful concept | Repo-specific validation needed | Implementation vocabulary |
| 18 | PyQuantLab HMM regime detection | https://www.pyquantlab.com/articles/Market%20Regime%20Detection%20using%20Hidden%20Markov%20Models.html | Blog/code article | Gaussian HMM on market features for bull/bear states | Useful implementation concept | Backtest setup needs audit | Mechanism sketch reference |
| 19 | PyMC Labs Bayesian HMM market regimes | https://www.pymc-labs.com/blog-posts/bayesian-hmm-market-regime-detection-pymc | Quant blog | Bayesian HMM identifies regimes; notes hindsight validation | Useful caution | Explicitly separates validation from live accuracy | Strong lookahead warning |
| 20 | QuantStart HMM regime detection | https://www.quantstart.com/articles/hidden-markov-models-for-regime-detection-using-r/ | Quant blog | HMM as risk filter for strategy selection | Useful concept | Old R example, not crypto | Supports filter approach |
| 21 | BSIC Regime Detection and Risk Allocation Using HMMs | https://bsic.it/regime-detection-and-risk-allocation-using-hidden-markov-models/ | Quant blog | 2-state Gaussian HMM on SPY returns + rolling vol, walk-forward retraining on 2-year window, posterior probabilities for allocation | Useful implementation | Uses posterior (smoothed) probabilities; walk-forward retraining reduces but does not eliminate smoothing risk | Walk-forward HMM methodology reference |
| 22 | QuantInsti Regime-Adaptive Trading with HMM | https://blog.quantinsti.com/regime-adaptive-trading-python/ | Blog/code | HMM regime detection on Bitcoin with walk-forward backtesting, specialist models per regime | Useful implementation | Walk-forward used but HMM trained on full training window then applied to next period | Bitcoin HMM walk-forward reference |
| 23 | Machimbo et al., Applications of HMMs in Detecting Regime Changes in Bitcoin Markets (2025) | https://journalajpas.com/index.php/AJPAS/article/view/781 | Academic paper | HMM and Markov-switching models for Bitcoin regime changes | Useful concept | Must verify filtered vs smoothed usage | Recent BTC HMM reference |
| 24 | Markov and Hidden Markov Models for Regime Detection in Cryptocurrencies (2026 preprint) | https://www.preprints.org/manuscript/202603.0831 | Academic preprint | Markov and HMM for crypto regime detection with focus on Bitcoin | Useful concept | Preprint, must verify methodology | Most recent BTC HMM reference |
| 25 | fHMM: Hidden Markov Models for Financial Time Series in R | https://www.jstatsoft.org/article/view/v109i09 | Academic paper | fHMM R package for hierarchical HMMs; state interpretation stability discussion | Useful concept | R package, not Python; addresses state relabeling | State interpretation stability reference |
| 26 | Ramon van Handel, Hidden Markov Models Lecture Notes (Princeton) | https://web.math.princeton.edu/~rvan/orf557/hmm080728.pdf | Academic lecture notes | Filter stability, contraction estimates, forward algorithm theory | Model-quality theory | Academic reference, no trading context | Forward filter theory and stability |
| 27 | Forward algorithm - Wikipedia | https://en.wikipedia.org/wiki/Forward_algorithm | Encyclopedia | Forward algorithm computes P(state_t | data_0:t) using only past observations | Definition reference | Forward-only is strictly causal | Confirms filtered probability definition |
| 28 | Freqtrade strategy customization docs | https://github.com/freqtrade/freqtrade/blob/develop/docs/strategy-customization.md | Official framework docs | Signals from completed candles open on next candle | Methodology reference | Explicitly warns against future data | Timing discipline reference |
| 29 | Freqtrade lookahead analysis docs | https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md | Official framework docs | Lookahead-bias detection tool | Methodology reference | Highlights future-data risk | Audit checks reference |

## Source Research Conclusion

Accepted for V1 planning:

- Gaussian HMM with 2 states (low-vol/range and high-vol/trend) as primary; 3-state as sensitivity check only.
- Custom forward-only algorithm for filtered probabilities P(state_t | data_0:t), because hmmlearn's native methods use smoothed posteriors.
- Rolling window training with frozen model parameters per validation fold.
- State interpretation based on emission parameters (mean return magnitude, variance), not on outcome returns.
- Direction from momentum/DI context at transition, not from HMM state labels directly.
- hmmlearn dependency required for model fitting (EM algorithm), but inference uses custom forward pass.

Rejected for V1 planning:

- hmmlearn `predict_proba` or `score_samples` as trading signals (these are smoothed posteriors using forward-backward, which is lookahead).
- Smoothed Viterbi path as live labels (audit-only allowed).
- State count selection after seeing results (must fix 2 states before running).
- Post-hoc state relabeling based on which state had positive returns.
- Combining HMM with failed ADX/CHOP logic as a rescue mechanism.
- GARCH or Markov-switching regression (dependency and complexity not justified for V1).

## Repo Data Surface Inspection

Schema and coverage were inspected read-only through Python `sqlite3` in the reconnaissance milestone.

Primary DB: `research_lab/data/crowded_unwind_backtest.db`

| Table | Columns | Use for HMM |
| --- | --- | --- |
| `candles` | `id`, `symbol`, `timeframe`, `open_time`, `open`, `high`, `low`, `close`, `volume` | Returns, realized volatility, ATR, volume features, MFE/MAE |
| `aggtrade_buckets` | `id`, `symbol`, `bucket_time`, `timeframe`, `taker_buy_volume`, `taker_sell_volume`, `tfi`, `cvd` | Optional TFI/CVD flow context for direction |
| `funding` | `id`, `symbol`, `funding_time`, `funding_rate` | Not required for V1 |
| `open_interest` | `id`, `symbol`, `timestamp`, `oi_value` | Not required for V1 |

Primary BTCUSDT candle coverage:

| Timeframe | Rows | Range UTC | Quality |
| --- | ---: | --- | --- |
| 15m | 195,347 | 2020-09-01T00:00:00+00:00 to 2026-03-28T20:30:00+00:00 | 0 gaps, 0 OHLC violations, 10 zero-volume bars |

Data sufficiency:

- Log returns from close-to-close: available from `candles`.
- Realized volatility (rolling std of returns): available from `candles`.
- Volume z-score: available from `candles.volume`.
- Optional TFI/CVD for direction context: available from `aggtrade_buckets`.
- MFE/MAE from post-entry highs/lows: available from `candles`.

Dependency requirement:

| Package | Installed? | Required for | Implication |
| --- | --- | --- | --- |
| `numpy` | Yes | Feature computation, forward algorithm | No issue |
| `pandas` | Yes | Data loading, alignment | No issue |
| `hmmlearn` | **No** | GaussianHMM model fitting (EM algorithm) | **Must be installed before diagnostic implementation** |
| `scipy` | Check required | Multivariate normal PDF for custom forward pass | May already be available as numpy dependency |

Dependency gate: `pip install hmmlearn` must be approved and executed before any diagnostic implementation. hmmlearn is a well-maintained scikit-learn-compatible package with minimal transitive dependencies (numpy, scikit-learn, scipy). Installation does not affect production code.

## Extracted Mechanism

Mechanism name: `FILTERED_HMM_REGIME_SHIFT_FEASIBILITY_V1`

Tradeable event: `HMM_RANGE_TO_TREND_FILTERED_PROBABILITY_CROSSING`

Definition:

- Feature engineering: compute log returns, realized volatility (rolling 14-bar std of log returns), and volume z-score (rolling 20-bar z-score) from completed candles only.
- Model: Gaussian HMM with 2 components, diagonal covariance, trained on rolling windows using hmmlearn's EM algorithm with a fixed random seed.
- Filtered probability: custom forward-only pass using fitted model parameters (startprob_, transmat_, means_, covars_) to compute P(state_t | data_0:t) at each bar.
- State interpretation: after each training window, identify the "trend state" as the state with higher mean absolute return and higher variance. This is frozen for the entire validation fold.
- Transition event: filtered P(trend_state) crosses above threshold (0.7) while the prior bar's filtered P(trend_state) was below threshold.
- Direction: sign of 20-bar close-to-close momentum at transition bar. If momentum is near zero (< ATR * 0.1), use +DI/-DI spread from ADX calculation if available, otherwise skip event.
- Entry candidate: bar i+1 after threshold crossing is observed at bar i close.
- Primary returns: measured from entry_candidate_bar = i+1, not from detection bar or raw move start.

Observable inputs:

- `candles.open_time`, `candles.open`, `candles.high`, `candles.low`, `candles.close`, `candles.volume`.

Optional inputs:

- `aggtrade_buckets.tfi` for directional flow confirmation (audit-only enrichment, not required for primary signal).

### Feature Definitions

Feature 1: Log return

- `log_return[i] = ln(close[i] / close[i-1])`
- Requires close[i-1] > 0.

Feature 2: Realized volatility

- `realized_vol[i] = std(log_return[i-13] through log_return[i])`
- 14-bar rolling standard deviation of log returns.
- Requires at least 14 prior returns.

Feature 3: Volume z-score

- `vol_zscore[i] = (volume[i] - mean(volume[i-19] through volume[i])) / std(volume[i-19] through volume[i])`
- 20-bar rolling z-score of volume.
- If std is zero, set z-score to 0.

Feature vector at bar i: `X[i] = [log_return[i], realized_vol[i], vol_zscore[i]]`

Feature warmup: first valid feature vector at bar 20 (14 for realized vol + 20 for volume z-score, overlapping). Additional 150 bars for HMM training stability. Total warmup: 170 bars minimum before first eligible event.

### HMM Configuration

State count: 2 (primary). 3-state as documented sensitivity check only, not to be tried after seeing 2-state results fail.

Covariance type: `diag` (diagonal). Rationale: fewer parameters than `full`, reduces overfitting risk, still captures per-feature variance differences between states. `full` as audit-only sensitivity if 2-state diag produces EXPLORE.

Number of EM iterations: 100 (hmmlearn default convergence with tol=0.01).

Random seed: 42 (fixed before any results). Sensitivity check: seeds 0, 123, 456 audit-only to verify result stability.

Training window: 500 bars (approximately 5.2 days of 15m data). Rationale: long enough to capture regime structure, short enough to adapt to regime changes.

Retrain frequency: every 100 bars (approximately 25 hours). Between retrains, the model parameters are frozen and only filtered probabilities update.

### State Interpretation Rules

After each model fit:

1. Examine `model.means_` to identify which state has higher mean absolute return and higher variance.
2. Label the state with higher variance as `TREND_STATE`.
3. Label the state with lower variance as `RANGE_STATE`.
4. This mapping is frozen for the entire validation window between retrains.
5. If both states have similar variance (ratio < 1.2), flag the fold as ambiguous and exclude from primary metrics.

Forbidden:

- Mapping states based on which state had positive subsequent returns.
- Changing state interpretation after seeing validation results.
- Trying different state counts after results are known.

### Filtered Probability Computation

CRITICAL: hmmlearn does not expose a forward-only probability API. The `predict_proba` method uses the forward-backward algorithm, which computes smoothed posteriors P(state_t | data_0:T) — this is lookahead.

The diagnostic must implement a custom forward pass:

1. Extract fitted parameters: `startprob_`, `transmat_`, `means_`, `covars_`.
2. For each new observation x_t:
   - Compute emission likelihood: P(x_t | state_k) from multivariate Gaussian with means_[k] and covars_[k].
   - Forward update: `alpha_t[k] = P(x_t | state_k) * sum_j(alpha_{t-1}[j] * transmat_[j, k])`.
   - Normalize: `filtered_prob_t[k] = alpha_t[k] / sum_k(alpha_t[k])`.
3. `filtered_prob_t` is P(state_t | data_0:t) — strictly causal, no future data.

This is the ONLY probability used for trading signal generation.

Smoothed posteriors from `predict_proba` are computed audit-only to compare filtered vs smoothed accuracy and lag.

### Threshold Crossing Rules

Primary threshold: P(TREND_STATE | data_0:t) >= 0.7.

Transition event fires when:

- `filtered_prob[i][TREND_STATE] >= 0.7`
- `filtered_prob[i-1][TREND_STATE] < 0.7`
- Prior latched range period existed within last 50 bars (at least one bar with filtered_prob[RANGE_STATE] >= 0.7 in recent history).

Staleness limit: if no bar had P(RANGE_STATE) >= 0.7 within the last 50 bars before the transition, the event is stale and excluded.

### Direction Assignment

At transition bar i:

1. Compute 20-bar momentum: `momentum = close[i] - close[i-20]`.
2. If `momentum > 0`: direction = LONG.
3. If `momentum < 0`: direction = SHORT.
4. If `abs(momentum) < ATR[i] * 0.1`: skip event (ambiguous direction).

ATR[i] is the 14-bar average true range at bar i, already computable from candles.

### Deterministic Rule Summary

For each BTCUSDT 15m bar i:

1. Require at least 170 prior candles (feature warmup + training window).
2. Compute feature vector X[i] = [log_return, realized_vol, vol_zscore].
3. If i is a retrain bar (every 100 bars), refit HMM on X[i-499:i+1] and freeze state interpretation.
4. Compute filtered probability using custom forward pass with current model parameters.
5. If filtered P(TREND_STATE) >= 0.7 and prior bar < 0.7:
   - Require recent range period (P(RANGE_STATE) >= 0.7 within last 50 bars).
   - Assign direction from 20-bar momentum.
   - Set `detection_bar = i`, `entry_candidate_bar = i+1`.
6. Exclude events without valid i+1 bar and outcome horizon.

## HMM Lag Model

HMM filtered probabilities have inherent lag because:

1. The forward algorithm accumulates evidence over time — single-bar transitions do not cause instant probability jumps.
2. The transition matrix constrains how fast probability mass can shift between states.
3. Feature smoothing (14-bar realized vol) adds additional lag.

HMM lag audit metric:

- For each event, define an audit-only `raw_move_start_bar`.
- Long event raw start: earliest bar in `[last_high_range_prob_bar + 1, detection_bar]` where close breaks the prior 10-bar high.
- Short event raw start: earliest bar in the same window where close breaks the prior 10-bar low.
- If no raw start exists, set `raw_move_start_bar = detection_bar`.
- `hmm_lag_bars = detection_bar - raw_move_start_bar`.

Lag-adjusted accessibility:

- `lag_mfe_before_entry` measures favorable movement from `raw_move_start_bar` through `entry_candidate_bar - 1`.
- `lag_mfe_after_entry` measures favorable movement from `entry_candidate_bar` through the outcome horizon.
- `lag_mfe_consumed_pct = lag_mfe_before_entry / (lag_mfe_before_entry + lag_mfe_after_entry)`.

Lag invalidation:

- If median `hmm_lag_bars > 5` and median `lag_mfe_consumed_pct > 70%`, STOP.
- This lag audit cannot rescue the mechanism. It can only explain failure.

Comparison to ADX lag: the deterministic diagnostic showed median ADX lag of 6 bars with 69.6% lag-adjusted MFE consumed (borderline). HMM filtered probabilities may have less lag because they are continuous (not threshold-based) and adapt to learned state dynamics. Or they may have more lag because the forward algorithm is conservative. The diagnostic must measure this empirically.

## Timing Model

| Bar | Definition | `FILTERED_HMM_REGIME_SHIFT` |
| --- | --- | --- |
| `training_cutoff_bar` | Last bar in current training window | Most recent retrain point |
| `observation_bar` | Bar where new feature vector is computed | `i` |
| `state_known_bar` | Bar where filtered probability is computed from data through i | `i` at close |
| `detection_bar` | Bar where filtered P(TREND) crosses threshold | `i` |
| `entry_candidate_bar` | Earliest realistic entry | `i+1` |
| `return_start_bar` | Bar primary returns start from | `i+1` |

Primary returns must start at `entry_candidate_bar = i+1`, never at `raw_move_start_bar`, `training_cutoff_bar`, or `observation_bar`.

Detection-bar returns are audit-only and used only to measure MFE consumed before realistic entry.

Entry price assumption: primary diagnostic uses `open[i+1]`; if `open[i+1]` is missing or non-positive, exclude the event before outcome measurement.

## MFE Accessibility Design

For each candidate event:

Direction:

- Long: favorable move is price above entry.
- Short: favorable move is price below entry.

Primary MFE before entry:

- Long: `max(high from detection_bar through entry_candidate_bar - 1) - close[detection_bar]`
- Short: `close[detection_bar] - min(low from detection_bar through entry_candidate_bar - 1)`

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
- If total MFE is zero, classify as 100% consumed.

Lag-adjusted MFE:

- Same calculations but start before-entry window at `raw_move_start_bar`.
- Audit-only to quantify HMM lag.

Time metrics:

- Detection to entry: 1 bar, 15 minutes.
- Raw move start to detection: `hmm_lag_bars`.
- Entry to MFE: offset of post-entry max favorable price.

Accessibility gates:

- Median primary MFE consumed before entry > 70% => STOP.
- Median primary MFE consumed before entry < 60% => timing acceptable.
- Median lag-adjusted MFE consumed > 70% with HMM lag > 5 bars => STOP.

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

- Long: minimum low in the 20 bars before detection_bar.
- Short: maximum high in the 20 bars before detection_bar.
- If structural stop distance is zero or invalid, exclude R-multiple but keep return metrics.

Cost assumption:

- Minimum round-trip cost: 0.10% (`0.001`).
- Sensitivity: 0.15% round trip audit-only.

Primary metrics: event count, median net return, mean net return, expectancy ratio, profit factor, win rate, average win/loss ratio, median MFE consumed before entry, median HMM lag bars, lag-adjusted MFE consumed, control comparison, walk-forward stability, state interpretation consistency, and seed sensitivity.

## Baseline Comparison

Trial-00095 reference: ER approximately 2.1, PF approximately 4.6, 271 historical trades, win rate approximately 56%, walk-forward validated, active PAPER deployment.

Deterministic ADX/CHOP reference: ER=-0.027, PF=0.954, 321 events, 0/4 folds positive.

Primary comparison decision:

- This V1 mechanism is planned as a standalone entry feasibility diagnostic.
- It is not planned as a trial-00095 filter-lift diagnostic.
- If standalone entry fails, a secondary question is whether HMM regime state adds information as a filter. But filter-lift cannot rescue a failed standalone result in V1.

Comparison questions:

1. Does HMM beat deterministic ADX/CHOP?

- ADX/CHOP STOP result is the floor. HMM must outperform ER=-0.027 meaningfully.
- If HMM also returns STOP with similar metrics, the regime-transition family is invalidated.

2. Is the candidate good enough standalone?

- Must have post-entry ER > 1.2 to avoid STOP.
- Must have PF > 1.5 for EXPLORE.
- To challenge trial-00095: must approach ER > 2.1 and PF > 4.0.

3. Is the candidate useful as orthogonal edge?

- Could be worth exploring with ER > 1.5, PF > 1.5, low overlap, and different regime exposure.
- Must beat all controls and show walk-forward stability.

## Control Cohort Design

Controls must be deterministic (or deterministic given the same random seed) and defined before results.

Control 1: Simple volatility percentile transition

- Detect 14-bar realized volatility rising from below 35th percentile to above 65th percentile.
- Direction from 20-bar close-to-close momentum.
- Entry at `i+1`.
- Purpose: test whether HMM adds information beyond simple volatility regime transition.
- Invalidation: if this control beats main on ER, HMM complexity is not justified.

Control 2: Deterministic ADX/CHOP regime transition

- Same mechanism as `TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1` (prior diagnostic).
- Latched ADX <= 20 AND CHOP >= 61.8 to ADX >= 25 AND CHOP <= 38.2.
- Direction from +DI/-DI.
- Entry at `i+1`.
- Purpose: direct comparison between HMM and deterministic approach. Prior diagnostic showed STOP, but running it as a control within the same framework provides apples-to-apples comparison.
- Invalidation: if ADX/CHOP matches or beats HMM, the probabilistic model adds no value over deterministic thresholds.

Control 3: HMM with wrong state interpretation

- Same HMM model and filtered probabilities.
- Map states oppositely: label the LOW-variance state as "trend" and HIGH-variance state as "range".
- Same threshold crossing rules, same direction assignment.
- Entry at `i+1`.
- Purpose: test whether state interpretation matters. If wrong interpretation performs similarly, the HMM states are not capturing meaningful regime differences.
- Invalidation: if wrong interpretation matches or beats main on ER.

Control 4: Shifted transition timing

- Same exact main HMM signal.
- Entry delayed to `i+3` instead of `i+1`.
- Purpose: test timing sensitivity and MFE decay after HMM probability crossing.
- Invalidation: if delayed entry performs similarly or better, next-bar timing is not critical.

Control 5: Random deterministic offset

- Shift main event timestamps by +137 bars, preserving direction.
- Exclude shifted events that overlap main events or lack outcome horizon.
- Entry at shifted bar +1.
- Purpose: control for market drift and data mining.
- Invalidation: if random-offset performs similarly or better, candidate lacks signal content.

Control 6 (audit-only): HMM with smoothed probabilities

- Same HMM model, but use `predict_proba` (forward-backward smoothed posteriors) instead of custom forward pass.
- Same threshold crossing and direction rules.
- Entry at `i+1`.
- Purpose: quantify the difference between filtered and smoothed probabilities. Smoothed should show better apparent accuracy but is not tradable live.
- NOT used for invalidation: smoothed is expected to outperform filtered. This control only measures the gap. If smoothed and filtered perform identically, the forward-backward pass adds no lookahead advantage (unlikely).

## Walk-Forward Design

Primary research range:

- Use primary research DB BTCUSDT 15m candles from 2020-09-01 to 2026-03-28.

HMM training regime:

- Within each fold, HMM is retrained every 100 bars on a rolling 500-bar window.
- State interpretation is frozen per retrain cycle.
- No cross-fold parameter sharing.

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

- Initial diagnostic uses fixed planning thresholds (P=0.7, 2 states, diag covariance, seed 42, 500-bar training, 100-bar retrain).
- No post-result threshold tuning inside V1.
- If thresholds fail, the result is STOP or INCONCLUSIVE, not "try P=0.6."

State interpretation consistency check:

- Across all retrains within a fold, count how often the trend-state assignment flips (high-variance state changes from state 0 to state 1 or vice versa).
- If state interpretation flips in more than 30% of retrains, flag as unstable.
- If unstable across multiple folds, this is evidence of overfitting or non-meaningful state structure.

Seed sensitivity check:

- After primary results with seed 42, run seeds 0, 123, 456 audit-only.
- If primary result changes verdict (STOP vs EXPLORE) across seeds, the mechanism is seed-sensitive and unreliable.

## Invalidation Criteria

STOP gates:

- Median net return after costs <= 0.
- Post-entry ER < 1.2.
- Profit factor < 1.2.
- Win rate < 45% and average win/loss ratio does not compensate.
- Median primary MFE consumed before entry > 70%.
- Median `hmm_lag_bars > 5` and median lag-adjusted MFE consumed > 70%.
- Any primary control cohort (1-5) beats main on ER.
- Walk-forward: fewer than 2 of 4 folds positive.
- Sample size < 100 candidate events.
- State interpretation flips in > 30% of retrains.
- Seed sensitivity: verdict changes across seeds.
- Smoothed probabilities used for trading signal (implementation violation).
- State labels relabeled after seeing returns (methodology violation).
- More than 5% of candles excluded due to invalid OHLC or feature issues.

EXPLORE gates:

- Median net return after costs > 0.
- Post-entry ER > 1.5.
- Profit factor > 1.5.
- Win rate > 45% with average win/loss ratio >= 1.5, or win rate > 52%.
- Median primary MFE consumed before entry < 60%.
- Median lag-adjusted MFE consumed < 70%.
- Main cohort beats all primary controls (1-5) on ER.
- Walk-forward: at least 3 of 4 folds positive.
- Sample size >= 200 events.
- State interpretation stable (< 30% flips across retrains).
- Seed sensitivity: verdict consistent across seeds.
- HMM outperforms deterministic ADX/CHOP baseline (control 2) meaningfully.
- Trial-00095 overlap is low if exact trade timestamps are available.

INCONCLUSIVE gates:

- Sample size between 50 and 99 events.
- Mixed fold results with ER 1.2 to 1.5.
- State interpretation marginally unstable (20-30% flips).
- Controls are underpowered due to sample size.
- Seed sensitivity marginal (metrics vary but verdict stable).

## Diagnostic Artifact Design

If implemented after Claude audit approval, expected artifacts:

- `research_lab/diagnostics/filtered_hmm_regime_shift_feasibility_v1.py`
- `research_lab/reports/filtered_hmm_regime_shift_feasibility_v1.md`
- `research_lab/reports/filtered_hmm_regime_shift_feasibility_v1.json`
- `tests/test_research_lab/test_filtered_hmm_regime_shift_feasibility_v1.py`

Expected report sections:

- Executive summary with one result recommendation: STOP / EXPLORE / INCONCLUSIVE.
- Data coverage and exclusion counts.
- HMM configuration and training summary.
- Feature engineering verification.
- Filtered vs smoothed probability comparison (audit-only).
- Mechanism/timing verification.
- HMM lag audit.
- Candidate metrics.
- MFE accessibility.
- Control cohort comparison (including ADX/CHOP baseline).
- Trial-00095 and ADX/CHOP benchmark comparison.
- Walk-forward fold metrics.
- State interpretation consistency.
- Seed sensitivity analysis.
- Invalidation gate table.

Expected tests:

- Feature computation correctness (log returns, realized vol, volume z-score).
- Custom forward pass produces valid probabilities (sum to 1, non-negative).
- Filtered probabilities differ from smoothed posteriors.
- Training uses only past data (no future bars in training window).
- State interpretation based on emission parameters, not returns.
- Entry and return start at i+1.
- MFE before and after entry calculations.
- Control cohorts are correctly isolated and deterministic.
- Seed reproducibility (same seed = same results).
- Diagnostic reproducibility.

## Scope Boundaries

Allowed after planning approval:

- Research-only diagnostic under `research_lab/diagnostics`.
- Research-only tests under `tests/test_research_lab`.
- Research reports under `research_lab/reports`.
- `pip install hmmlearn` (dependency approval required).

Not allowed:

- No production strategy code.
- No FeatureEngine or SignalEngine changes.
- No Governance/Risk/execution changes.
- No settings changes.
- No trial-00095 modification.
- No promotion logic.
- No ADX/CHOP rescue.
- No GARCH/MS-GARCH implementation.
- No threshold tuning after results.

## Dependency Approval Request

Package: `hmmlearn`
Version: latest stable (0.3.3 as of planning date)
Installation: `pip install hmmlearn`
Transitive dependencies: numpy, scipy, scikit-learn (all commonly available)
Impact on production: None. hmmlearn is used only in `research_lab/diagnostics/` and `tests/test_research_lab/`.
Justification: Gaussian HMM EM training requires optimized forward-backward algorithm for parameter estimation. While the forward pass for filtered probabilities is custom, model fitting (learning means, covariances, transition matrix) requires hmmlearn's EM implementation.

This dependency must be approved before diagnostic implementation begins.

## Recommendation: IMPLEMENT ONE DIAGNOSTIC

Diagnostic name: `FILTERED_HMM_REGIME_SHIFT_FEASIBILITY_V1`

Mechanism summary: Train a 2-state Gaussian HMM on rolling 500-bar windows of BTCUSDT 15m log returns, realized volatility, and volume z-score. Compute filtered (forward-only) probabilities at each bar. When P(high-vol trend state) crosses above 0.7 from below, with recent range history, enter directionally at i+1 using 20-bar momentum for direction.

Timing: features known at bar i close, filtered probability computed at bar i, entry at bar i+1 (1-bar / 15-minute delay).

Expected MFE accessibility: plausibly better than deterministic ADX/CHOP because filtered probabilities may react faster than heavily smoothed ADX. ADX/CHOP showed 21.5% MFE consumed (good timing, no edge). If HMM also shows good timing but no edge, the regime-transition family is invalidated.

Expected sample size: likely 100-500 events over 2020-09-01 to 2026-03-28, depending on probability threshold behavior. If fewer than 100 events, result is STOP by sample gate.

Key risk: this is the highest-complexity diagnostic attempted. Overfitting risk is extreme. The plan mitigates this through fixed parameters before results, walk-forward training, state interpretation freezing, seed sensitivity checks, and 6 control cohorts. If HMM returns STOP, the regime-transition family (both deterministic and probabilistic) should be considered exhausted.

Estimated timeline: 3-5 days for diagnostic implementation, focused tests, report, and JSON artifact.

Next: Cascade implements the diagnostic only after Claude approves this planning document and hmmlearn dependency is approved.
