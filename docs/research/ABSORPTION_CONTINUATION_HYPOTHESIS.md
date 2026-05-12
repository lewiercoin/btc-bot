# Absorption Continuation Hypothesis

Milestone: `ABSORPTION-CONTINUATION-RESEARCH-V1`

## Hypothesis

`absorption_continuation_long` should only trade established uptrend structure after a controlled pullback into a value or liquidity zone. The setup is valid only when flow confirms absorption: sellers are being absorbed, TFI is bullish, OI is stable or rising, and leverage is not crowded.

This is not a generic EMA pullback setup.

## Counterparty Model

- Pullback sellers fade the trend before support fails.
- Early shorts assume reversal during a controlled retest.
- Late buyers wait for obvious breakout confirmation and enter after risk/reward has degraded.

The setup attempts to enter before the continuation becomes obvious, while structural invalidation is still close.

## Required Structure

- Regime is `uptrend`.
- Price is above EMA200 and EMA50 is above EMA200.
- EMA200 slope is positive.
- Price is not overextended from EMA200.
- Pullback depth is controlled, initially 0.5% to 3.0%.
- Price is near EMA50 or a recent equal-low liquidity level.
- Price has not broken the prior swing low.

## Required Confirmation

- CVD bullish divergence or positive CVD slope proxy.
- TFI above absorption threshold.
- OI delta is stable or positive enough to avoid unwind behavior.
- Funding and OI z-score are not crowded.
- No volatility panic or active liquidation cascade.

## Invalidation

The setup is invalid if the pullback breaks higher-low structure, if a low sweep fails to reclaim, or if leverage/volatility context indicates forced unwind rather than controlled absorption.

Stops must be structural: below the pullback low or prior swing low, with a small ATR buffer. Fixed ATR-only stops are not sufficient evidence of structural invalidation.

## Research Gates

- Uptrend ER must exceed 1.5.
- Uptrend trade count must materially exceed sweep-reclaim uptrend coverage.
- Trend-day capture must be at least 50%, with below 30% treated as rejection.
- Overlap with sweep-reclaim should be below 20%; below 30% is acceptable with explanation; above 50% is rejection.
- Range bleed must stay above -1.0 ER.
- Walk-forward must pass 2/2 windows.
- No blocking safety flags.
- Every signal must include explicit `reasons[]`.

## Verdict Rule

The research outcome must be one of:

- `REJECT`
- `ITERATE`
- `CANDIDATE_FOR_PHASE_2_5`

The setup must not be rescued by blind parameter loosening or by mixing results with sweep-reclaim.
