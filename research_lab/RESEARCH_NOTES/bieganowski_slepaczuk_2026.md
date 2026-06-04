# Bieganowski & Slepaczuk 2026 - Explainable Patterns in Cryptocurrency Microstructure

Sources reviewed:
- arXiv abstract/html: https://arxiv.org/abs/2602.00776
- arXiv source package, especially `sections/03_data.tex`, `04_methodology.tex`, `05_models.tex`, `06_shap_explanations.tex`, `07_backtest.tex`, `09_robustness.tex`
- BTC SHAP summary image from the arXiv source package: `charts/BTC/summary.png`

## TL;DR

The paper is directly relevant as an offline microstructure-feature reference, not as a live decision-path model. Its strongest transferable value is a compact, scale-aware feature vocabulary around top-of-book imbalance, spread, short-window trade flow, VWAP-to-mid deviations, and volatility. GMADL and purged walk-forward are useful methodology references, but the paper's 1-second/3-second horizon does not map directly to btc-bot's 15m reclaim edge. Recommendation: use this as `MicrostructureContext` informational telemetry first, never as a `signal_engine.py` input until a separate offline promotion gate proves independent value.

## Pass 1 - Comprehension

The paper argues that short-horizon crypto returns can be represented by a portable microstructure feature set. It uses Binance Futures perpetual order book and trade data at 1-second frequency from January 1, 2022 to October 12, 2025 across BTC, LTC, ETC, ENJ, and ROSE.

The methodology is:

- define a 3-second future log-return target on mid price;
- engineer top-of-book, order-flow, VWAP deviation, and realized-volatility features;
- train CatBoost models with Optuna-selected hyperparameters;
- select/explain models with GMADL, a direction-aware return-weighted metric;
- evaluate with rolling time-series cross-validation with a purge gap;
- inspect SHAP rankings and dependence curves across assets;
- validate economic significance through conservative taker and maker backtests.

The main claimed properties are cross-asset stability of feature importance, consistent SHAP dependence shapes, and a flash-crash contrast where taker execution benefits from imbalance-informed directional flow while maker execution suffers adverse selection.

## Pass 2 - Critical Examination

Strongest critique: the paper studies ultra-short-horizon 1s/3s prediction, while btc-bot's current edge is a 15m liquidity sweep/reclaim process. Transfer from "predict next 3 seconds" to "classify a 15m setup context" is not automatic.

Unverified assumptions:

- Taker backtest performance may depend on latency and book access that btc-bot does not have.
- SHAP stability across assets does not prove strategy stability after fees, latency, outages, and exchange microstructure changes.
- The authors retain features in original scale because CatBoost can handle it, but btc-bot needs auditable, deterministic formulas and scale-aware parquet outputs.
- The paper says short gaps are forward-filled, but btc-bot data-integrity rules cannot silently fill missing live/replay data without explicit quality flags.
- Flash-crash profitability may overweight rare stress events and may not improve ordinary throughput.

Cargo-cult risk:

- Copying CatBoost/SHAP/GMADL into a live setup selector would violate the project's LLM/ML-offline rule unless the model remains research-only.
- Treating orderbook imbalance as a direct signal would create a second, much faster strategy family, not a reclaim extension.
- Using maker conclusions is not useful for current btc-bot execution because paper/live execution is taker-like and not a queue-position market maker.

## Pass 3 - Domain Mapping

Affected btc-bot modules if adopted later:

- `core/models.py`: would need an optional `MicrostructureContext` dataclass or an informational field in `Features`.
- `core/feature_engine.py`: integration around `FeatureEngine.compute()` lines 319-356, after deterministic OHLC sweep features and before returning `Features`.
- `data/market_data.py` / snapshot assembly: would need reliable bid/ask quantities and possibly orderbook-depth snapshots, not just price/bid/ask.
- `storage/schema.sql` / audit logging: if promoted beyond research, context values need persisted feature snapshots.
- `research_lab/**`: first implementation target for offline replay and backtest correlation.

Non-negotiable rules:

- Determinism: OK only if formulas are pure functions of timestamped snapshots and replay data.
- Auditability: OK only if feature values and quality flags are logged/persisted.
- LLM/ML offline only: CatBoost/SHAP/Optuna must remain research lab tools.
- Reclaim edge protection: do not touch `signal_engine.py`; start as telemetry only.
- Setup portfolio: useful as future `RegimeContext`/`MicrostructureContext`, not as a monolithic new engine.

Copy vs reimplement:

- Copy directly: none of the paper's code; the source package has prose and figures, not a clean reusable feature module.
- Reimplement: all formulas in btc-bot conventions with explicit UTC alignment, quality flags, parquet-friendly outputs, deterministic unit tests.
- External refs to store: paper URL, PDF/source hash, and a local note describing the reconstructed 10-feature vocabulary. Do not store large images unless operator explicitly wants a reference archive.

## Pass 4 - Cost/Benefit Analysis

Estimated effort:

- Codex implementation: 10-16h for offline `MicrostructureContext` feature calculations, fixture tests, and replay artifact generation.
- Claude audit: 3-5h, mainly data lineage, no hidden fill, and decision-path isolation.

Best realistic result:

- Better explanation of why trial-00095 wins/loses by spread, imbalance, taker pressure, and realized volatility.
- Possible future context filter or setup ranker after independent RUN validation.
- Better Tardis/data-integrity specification for top-of-book and trade features.

Worst realistic result:

- Adds high-frequency telemetry that is expensive, noisy, and irrelevant to 15m reclaim throughput.
- Encourages accidental ML/live leakage or overfitting to flash-crash behavior.
- Produces many missing/unavailable quality flags because current snapshots do not preserve full L1 size/depth history.

Worth it?

- Informational-only context: yes, confidence 3/5.
- Decision-relevant signal input: no for V1, confidence 4/5.
- GMADL as research selection metric: maybe, confidence 3/5.

## Pass 5 - Synthesis

Highest-priority recommendations:

1. Build `MicrostructureContext` as logged, informational telemetry only. Confidence 3/5.
2. Use paper features to improve offline attribution of trial-00095 trades and near-misses, not to alter live signal generation. Confidence 4/5.
3. Adopt purged/nested validation language in microstructure research protocols where labels overlap. Confidence 3/5.
4. Treat spread/imbalance extremes as risk-context candidates before treating them as alpha. Confidence 3/5.
5. Do not port CatBoost into runtime. Confidence 5/5.

External refs map:

- `research_lab/external_refs/bieganowski_slepaczuk_2026/metadata.md`: optional future reference with paper URLs and extracted feature list.
- Reimplement in btc-bot: formulas, quality flags, UTC bucketing, parquet schema.
- Omit: live ML forecast, maker strategy, latency-sensitive 3-second taker loop.

## Reconstructed 10 Features With Formulas

Important caveat: the paper source does not expose a clean table of all formulas. The following feature names are reconstructed from the BTC SHAP summary image in the source package and formulas are standard interpretations consistent with the paper text. Before implementation, operator should approve these definitions as btc-bot local contracts.

Notation:

- Best bid price/size: $b_t, q^b_t$
- Best ask price/size: $a_t, q^a_t$
- Mid: $m_t=(a_t+b_t)/2$
- Trades in window $W_t$: price $p_k$, quantity $v_k$, aggressor sign $s_k \in \{+1,-1\}$ where +1 is buyer-initiated.

1. `imbalance_L1`

   $$\mathrm{imbalance}_{L1,t}=\frac{q^b_t-q^a_t}{q^b_t+q^a_t}$$

2. `net_order_flow`

   $$\mathrm{net\_order\_flow}_t=\sum_{k \in W_t} s_k v_k$$

   btc-bot equivalent is closest to 60s/15m CVD/TFI.

3. `vwap_buy_to_mid`

   $$\mathrm{vwap\_buy\_to\_mid}_t=\frac{\sum_{k \in W_t, s_k=+1}p_k v_k}{\sum_{k \in W_t, s_k=+1}v_k}\frac{1}{m_t}-1$$

   Fallback to 0/unavailable if no buy trades in the window.

4. `vwap_sell_to_mid`

   $$\mathrm{vwap\_sell\_to\_mid}_t=\frac{\sum_{k \in W_t, s_k=-1}p_k v_k}{\sum_{k \in W_t, s_k=-1}v_k}\frac{1}{m_t}-1$$

   Fallback to 0/unavailable if no sell trades in the window.

5. `volatility_10s_annualized`

   $$\sigma_{10s,t}=\mathrm{std}\left(\log(m_i/m_{i-1})\right)_{i \in [t-10s,t]}\sqrt{N_{\mathrm{year}}}$$

   For btc-bot telemetry, store unannualized and annualized variants to avoid misleading scale.

6. `spread`

   $$\mathrm{spread}_t=a_t-b_t$$

7. `concentration_of_volume`

   Proposed local definition:

   $$\mathrm{volume\_concentration}_t=\frac{\max(V^+_t,V^-_t)}{V^+_t+V^-_t}$$

   where $V^+$ and $V^-$ are buy/sell aggressive volumes in $W_t$. This is the least certain reconstructed formula.

8. `volume_traded`

   $$\mathrm{volume\_traded}_t=\sum_{k \in W_t} v_k$$

9. `trade_price_variance`

   $$\mathrm{trade\_price\_variance}_t=\mathrm{var}\left(\log(p_k/m_t)\right)_{k \in W_t}$$

10. `number_of_trades`

   $$\mathrm{number\_of\_trades}_t=|W_t|$$

## GMADL Formula And Python Pseudocode

Paper formula:

$$
\ell_i = -\left(\frac{1}{1+e^{-a R_i \hat{R}_i}}-\frac{1}{2}\right)|R_i|^b,\quad a,b>0
$$

Full objective is the mean over samples. Lower is better if used as a loss; directionally correct large-return predictions become more negative/rewarded.

Pseudocode only:

```python
function gmadl(realized_returns, predicted_returns, a, b):
    losses = []
    for R, R_hat in aligned_pairs(realized_returns, predicted_returns):
        directional_term = sigmoid(a * R * R_hat) - 0.5
        magnitude_weight = abs(R) ** b
        losses.append(-directional_term * magnitude_weight)
    return mean(losses)
```

Use in btc-bot research only:

- as an offline ranking/diagnostic metric for candidate microstructure models;
- never as live `SignalCandidate` logic;
- always compared with PF/expectancy/trade accessibility, not as a standalone approval metric.

## WF Purging vs WF_LIGHT_PROTOCOL

Agreement:

- Both recognize time-series leakage risk.
- Both require train-before-validation ordering.
- Both treat validation as forward-looking, not random k-fold.
- Both separate selection/tuning from out-of-sample reporting in principle.

Differences:

- The paper uses a deliberate temporal gap between train and validation, motivated by overlapping labels and slow features.
- btc-bot's accepted `WF_LIGHT_PROTOCOL` is preliminary-only; it is not decision-grade promotion by itself.
- The paper tunes hyperparameters inside training windows; btc-bot has post-hoc and nested modes in `research_lab/walkforward.py`, with nested mode more aligned to proper selection.
- btc-bot must persist protocol hash, config hash, search-space signature, and source DB lineage; paper prose is less explicit about audit artifact persistence.

Recommendation:

- For microstructure features with 1s/3s labels, use explicit purge windows.
- For 15m reclaim attribution, purge is less about label overlap and more about ensuring near-miss reconstruction does not use future-confirmed labels.

## Mapping 10 Features To Existing btc-bot Modules

| Paper feature | Existing btc-bot surface | V1 mapping |
| --- | --- | --- |
| `imbalance_L1` | `MarketSnapshot.book_ticker`, bid/ask fields | New informational field, quality unavailable if bid/ask qty missing |
| `net_order_flow` | `aggtrades_bucket_60s`, `aggtrades_bucket_15m`, `cvd_15m`, `tfi_60s` | Reuse as normalized signed flow telemetry |
| `vwap_buy_to_mid` | `aggtrade_events_60s` or bucket details if available | New informational field |
| `vwap_sell_to_mid` | `aggtrade_events_60s` or bucket details if available | New informational field |
| `volatility_10s_annualized` | No 10s mid-price stream persisted in current `Features`; 15m ATR exists | Research-only if tick/mid history is available |
| `spread` | `MarketSnapshot.bid`, `MarketSnapshot.ask` | New informational field; spread-to-mid preferred |
| `concentration_of_volume` | `aggtrade_events_60s` | New informational field after local formula approval |
| `volume_traded` | `aggtrade_events_60s`, `aggtrade_events_15m` | Existing raw source, add explicit context output |
| `trade_price_variance` | `aggtrade_events_60s` | New informational field |
| `number_of_trades` | `aggtrade_events_60s` | New informational field |

Integration point:

- `core/feature_engine.py:319` after sweep/reclaim detection and before quality defaults/flow calculations.
- Existing return construction at `core/feature_engine.py:358` would need an informational container only after operator approval.

## Open Questions

1. Do we have reliable bid/ask quantity in `book_ticker` across historical replay, or only prices?
2. Should `MicrostructureContext` use 60s windows to match current flow buckets, or 10s/3s windows to match the paper?
3. Should unavailable buy/sell VWAP be encoded as `None` plus quality flag, or `0.0` plus unavailable flag?
4. Is the next research goal trade attribution for trial-00095, or near-miss reconstruction for throughput expansion?
5. Should Tardis backfill include top-of-book quote updates, or only liquidation/force-order events?
6. What exact purge duration should be required for 1s/3s microstructure labels?
7. Should flash-crash periods be included in optimization, held out as stress tests, or both?

## Recommendation Confidence

| Recommendation | Confidence |
| --- | ---: |
| Build informational-only `MicrostructureContext` | 3/5 |
| Keep ML/GMADL/CatBoost in `research_lab` only | 5/5 |
| Use spread/imbalance as risk context before alpha | 3/5 |
| Reuse paper formulas directly without local validation | 1/5 |
| Add purge-window language for microstructure research | 3/5 |
| Use paper to justify live throughput expansion now | 1/5 |
