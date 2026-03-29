# Independent Optimization Research Request

## Who I Am

I'm a senior quant systems auditor reviewing a BTC/USDT perpetual futures trading system. I need your independent opinion on optimization paths. You are NOT part of our build team — I want a fresh, unbiased perspective. Use web search, academic sources, quant forums, published research, and your own reasoning. Challenge my assumptions. If something is fundamentally flawed, say so.

**No code. Analysis, reasoning, and concrete optimization proposals only.**

---

## System Architecture (what we built)

Fully automated BTC/USDT perpetual futures system. 15-minute bar resolution. SQLite persistence. Deterministic replay backtest. Single symbol (BTCUSDT Binance Futures).

### Signal Generation Pipeline

```
Market Data (15m candles, 1h, 4h, aggtrades 60s/15m, funding, OI)
    → Feature Engine (computes ~20 features per bar)
    → Regime Engine (classifies market state)
    → Signal Engine (generates LONG/SHORT candidates with entry/SL/TP)
    → Governance (confluence scoring, minimum threshold)
    → Risk Engine (position sizing, drawdown limits)
    → Execution
```

### Signal Direction Logic (current)

Direction is determined by priority:
1. **CVD divergence** (highest priority): If cumulative volume delta shows bullish divergence (price falling but CVD rising) → LONG. Bearish divergence (price rising, CVD falling) → SHORT.
2. **TFI (Trade Flow Impulse)** on 60-second aggtrade buckets: If TFI > 0.05 → LONG; if TFI < -0.05 → SHORT.
3. If neither condition met → no signal.

### Entry Requirements (confluence scoring)

A signal requires minimum confluence score of 3.0 from these contributors:
- Liquidity sweep detected: +1.25
- Price reclaim after sweep: +1.25
- CVD divergence present: +0.75
- TFI impulse (|TFI| >= 0.10): +0.50
- Force order (liquidation) spike: +0.40
- Regime bonus (post-liquidation or crowded leverage): +0.35
- EMA trend alignment: +0.25
- Funding rate supportive: +0.20

### Entry/SL/TP Level Calculation

```
Base level = sweep_level (or EMA50_4h fallback)

LONG:
  Entry       = base + 0.05 × ATR_15m
  Stop Loss   = base - 0.25 × ATR_15m    (invalidation)
  TP1         = entry + 2.0 × ATR_15m
  TP2         = entry + 3.5 × ATR_15m     (not used in backtest — exits at TP1 only)

SHORT:
  Entry       = base - 0.05 × ATR_15m
  Stop Loss   = base + 0.25 × ATR_15m
  TP1         = entry - 2.0 × ATR_15m
  TP2         = entry - 3.5 × ATR_15m
```

Minimum reward:risk ratio enforced: 2.8

### Regime Classification (priority order)

1. **POST_LIQUIDATION**: force order spike + |TFI| >= 0.2 + force orders decreasing
2. **CROWDED_LEVERAGE**: funding rate in top/bottom 15th percentile (60d) AND |OI z-score 60d| >= 1.5
3. **COMPRESSION**: ATR_4h / price <= 0.55%
4. **UPTREND**: EMA50_4h > EMA200_4h by >= 0.25% AND ATR_4h_norm > 0.55%
5. **DOWNTREND**: EMA200_4h > EMA50_4h by >= 0.25% AND ATR_4h_norm > 0.55%
6. **NORMAL**: default

**Regime does NOT block any signals.** It only adds +0.35 confluence bonus for POST_LIQUIDATION and CROWDED_LEVERAGE.

### Risk Management

- Risk per trade: 1% of equity
- Position size: (equity × 0.01) / stop_distance
- Max open positions: 2
- Max consecutive losses before lockout: 3
- Daily drawdown limit: 3%
- Weekly drawdown limit: 6%
- Leverage: 5x default, 3x if stop distance >= 1% of price
- 24-hour timeout exit

### Execution Costs (backtest fill model)

- Entry: LIMIT order, 1 bps slippage, 4 bps maker fee
- Exit: MARKET order, 3 bps slippage, 4 bps taker fee
- Total round-trip friction: ~12 bps

---

## Backtest Results (87 days: 2026-01-01 → 2026-03-29)

### Headlines

| Metric | Value |
|---|---|
| Initial equity | $10,000 |
| Bars processed | 8,339 (15m bars) |
| Signals generated | 534 |
| Trades executed | 107 (20% signal→trade conversion) |
| Win rate | 15.0% |
| PnL | **-$4,704** (-47%) |
| PnL R-sum | -112.6R |
| Profit factor | 0.40 |
| Expectancy | -1.05R per trade |
| Max consecutive losses | 15 |
| Max drawdown | 47.8% |
| Sharpe ratio | -12.46 |
| Total fees paid | $3,274 (31% of initial equity) |

### Direction Breakdown

| Direction | Trades | Wins | Win Rate | PnL | Avg R |
|---|---|---|---|---|---|
| LONG | 58 | 16 | 27.6% | -$546 | -0.21R |
| SHORT | 49 | 0 | **0.0%** | -$4,158 | -2.05R |

**Every single SHORT trade lost money. Zero wins in 49 attempts.**

### Regime Breakdown

| Regime | Trades | Wins | Win Rate | Expectancy R |
|---|---|---|---|---|
| compression | 1 | 1 | 100% | +4.83R |
| normal | 6 | 2 | 33.3% | +0.33R |
| downtrend | 52 | 10 | 19.2% | -0.78R |
| crowded_leverage | 19 | 1 | 5.3% | -1.60R |
| uptrend | 29 | 2 | 6.9% | -1.67R |

### Exit Reasons

| Exit | Trades | Win Rate | Avg R |
|---|---|---|---|
| Stop Loss | 91 | 0% | -2.07R |
| Take Profit | 16 | 100% | +4.73R |

No trades exited via timeout. System is binary: full TP or full SL.

### Hold Duration

- 66.4% of trades (71/107) last exactly 1 bar (15 minutes) — immediate SL hits
- Median hold: 15 minutes
- Avg hold: 43 minutes
- Winners avg hold: ~30 minutes (2 bars)

### Confluence Score Performance

| Confluence Bucket | Trades | Win Rate | Expectancy R |
|---|---|---|---|
| 3.0 - 4.0 | 91 | 16.5% | -0.94R |
| 4.0 - 5.0 | 16 | 6.25% | -1.69R |

**Higher confluence scores perform WORSE.**

### MAE/MFE Analysis

- **Winners**: 9/16 had MAE = $0 (price went straight to TP). Avg MAE = $6.71.
- **Losing SHORTs**: 32/49 had MFE = $0 (price NEVER moved in their favor).
- **Losing LONGs**: 40/42 had positive MFE (avg $112.87) — price moved right, then reversed back through SL.

### Monthly

| Month | Trades | WR | PnL | LONG-only PnL |
|---|---|---|---|---|
| Jan | 42 | 19.0% | -$1,612 | -$537 |
| Feb | 37 | 13.5% | -$1,833 | +$94 |
| Mar | 28 | 10.7% | -$1,258 | -$104 |

### Top Winners (all LONG)

All 16 winners were LONG positions exiting via TP1 at ~+5R. Most occurred in "downtrend" regime (counter-trend bounce captures). Best winner: +$343, +5.51R (Feb 9, downtrend regime).

### Top Losers (mostly SHORT)

Worst loser: -$77, -4.12R (Jan 1, SHORT in crowded_leverage). The -4R losses suggest some trades have risk distance much larger than position sizing assumed.

---

## Market Context (Jan-Mar 2026)

BTC/USDT went from ~$93K (early Jan) down to ~$67K (late Feb), partial recovery to ~$70K (late Mar). Dominant regime was **downtrend** for most of the period, with episodes of crowded leverage. This was a sustained bear move with intermittent bounces.

---

## What I Already Know Is Wrong

1. **SHORT signals are systematically broken** — no trend filter, firing against dominant moves
2. **SL is too tight** — 0.30 × ATR_15m total risk distance gets eaten by single candles
3. **Fee drag is massive** — $3,274 on 107 trades from $10K capital
4. **Regime doesn't filter** — only adds confluence points, never blocks
5. **Higher confluence = worse performance** — scoring weights are miscalibrated
6. **Losing LONGs had $113 avg favorable excursion** before reversing — potential wasted edge

---

## What I Want From You

### 1. Independent Assessment

Do you agree with my diagnosis? What am I missing? Are there failure modes I haven't considered? Is the core concept (liquidity sweep → reclaim → reversal entry) viable at all on 15-minute BTC futures, or is the entire approach flawed for this timeframe/instrument?

### 2. Literature & Evidence Search

Search for published research, quantitative papers, and practitioner evidence on:
- **Liquidity sweep / stop-hunt trading strategies** on crypto futures — does this edge exist? What timeframes? What instruments?
- **CVD divergence as a directional signal** — is there academic or quantitative evidence for CVD divergence predictive power on crypto?
- **Optimal stop-loss placement** for crypto futures mean-reversion strategies — ATR multiples, fixed percentage, volatility-scaled, microstructure-based?
- **Regime filtering for crypto** — what regime classifiers actually improve risk-adjusted returns in published backtests?
- **Trade flow imbalance (TFI / order flow)** as a signal — at what timeframes does order flow have predictive power in crypto? Does it decay too fast for 15-minute bars?
- **Open interest + funding rate** as regime indicators — what thresholds and lookbacks are used in practice?

### 3. Optimization Proposals

For each proposal, I need:
- **What to change** (specific parameter, filter, logic)
- **Why it should work** (mechanism, evidence, reasoning)
- **Expected impact** (directional — will this reduce losses, increase wins, reduce fees?)
- **Risk** (what could go wrong, what assumption does this rely on)
- **Priority** (quick win vs deep rework)

Categories I want proposals in:
- **Signal direction filtering** — how to fix the SHORT problem without just disabling shorts
- **Stop-loss optimization** — wider SL, ATR multiple, volatility regime-adaptive SL
- **Regime-based signal blocking** — which regimes should block which directions
- **Confluence recalibration** — which factors actually predict winners vs losers
- **Fee reduction** — reduce trade count, increase selectivity, improve entry timing
- **Partial exits / trailing stops** — capturing the $113 avg MFE from losing LONGs
- **Timeframe considerations** — is 15m the right resolution? Would 1h or 4h improve?
- **Alternative direction models** — what should replace CVD/TFI for direction?

### 4. Contrarian View

Play devil's advocate: **what if the strategy concept is sound but the 87-day sample is just a bad draw?** BTC was in sustained downtrend Jan-Mar 2026. Is there evidence this strategy type performs better in ranging or recovery markets? What's the minimum sample size needed to evaluate a 15% win-rate system with 5:1 payoff?

### 5. Comparable Systems

Search for documented/published trading systems with similar characteristics (liquidity grab reversal, low win-rate high R:R, crypto futures) and report their:
- Typical win rates
- Typical profit factors
- Typical drawdown profiles
- How they handle regime filtering
- How they handle direction selection

---

## Output Format

Structure your response as:

1. **Assessment** — agreement/disagreement with my diagnosis + missed issues
2. **Literature Review** — what published evidence says about each signal component
3. **Optimization Proposals** — prioritized table, then detailed writeup per proposal
4. **Statistical Validity** — is 107 trades enough to judge? What would you need?
5. **Comparable Systems** — benchmarks from similar approaches
6. **Contrarian Arguments** — strongest case for the strategy being fixable vs unfixable
7. **Recommended Priority Path** — if you had to pick 3 changes to test first, which and why?

Be specific. Name papers, cite sources, give numbers. I don't want generic quant advice — I want actionable proposals grounded in evidence for BTC perpetual futures specifically.
