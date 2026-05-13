# VOLATILITY-BREAKOUT-RESEARCH-V1 Hypothesis

## Thesis

Volatility_breakout tests whether BTC can be traded during an active ATR expansion state after price has already broken recent structure and directional flow is aligned.

This is not compression_breakout. Compression_breakout tried to enter while ATR was low and wait for a future breakout. Volatility_breakout enters only when ATR is already rising and the breakout is already visible.

## Market Structure

- ATR expansion state: ATR_4h_norm is rising over the last six 15m decision cycles.
- Structure break: price breaks the prior 12-candle 15m range by at least 0.5 ATR_15m.
- Momentum alignment: TFI_60s supports the breakout direction.
- Overheat veto: ATR_4h_norm must stay below the empirical panic threshold.

## Timing Rule

Entry must happen during expansion, not during compression.

The setup blocks `compression`, `crowded_leverage`, and `post_liquidation` regimes. Compression entries are explicitly treated as timing violations because they collapse this setup back into the failed compression_breakout hypothesis.

## Validation Gates

- Expansion state ER > 1.5.
- Expansion continuation rate >= 60%.
- Minimum total trades >= 20.
- Expansion entry rate >= 80%.
- No missing reasons[] on generated trades.

Hard-stop failures:

- Total trades < 10.
- Expansion ER < 1.0.
- Expansion continuation rate < 50%.
- Expansion entry rate < 50%.
