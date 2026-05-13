# REGIME-REVERSAL-RESEARCH-V1 Hypothesis

## Classification

This is the final 15m portfolio viability test.

If this setup fails, the next milestone is strategic assessment, not another setup attempt.

## Thesis

Regime_reversal tests whether a confirmed RegimeEngine state transition can be traded after the prior directional regime exhausts.

This is not top/bottom anticipation. The setup must not short an uptrend or buy a downtrend based on indicator extremes. It enters only after RegimeEngine confirms that the prior regime ended.

## Valid Transitions

- Downtrend -> normal/uptrend: LONG.
- Uptrend -> normal/downtrend: SHORT.

The current regime must persist for at least two cycles before entry, and the entry window closes after twelve cycles.

## Critical Diagnostics

- Entry delay from transition to entry.
- False reversal rate: losing trades where regime reverted to the prior regime during the trade.
- Whipsaw rate: quick regime flips in the RegimeEngine timeline.

## Hard Stops

- Total trades < 10.
- Post-transition ER < 1.0.
- False reversal rate >= 50%.
- Whipsaw rate >= 50%.
- Average entry delay > 6 cycles.

No diagnostic iteration is allowed for this final test.
