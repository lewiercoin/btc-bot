# Crowded Unwind Hypothesis

## Market Structure

Funding rate extremes plus elevated open interest indicate crowded leverage. A force-order spike marks liquidation or forced unwind beginning now. The setup enters opposite the crowded side to test whether the unwind is tradeable.

## Edge

- Counterparty: overleveraged traders forced to close or liquidate.
- Timing: concurrent crowding plus force spike, not a delayed prediction.
- Data: funding, OI, force orders, and TFI only.
- Exclusions: no CVD divergence and no compression/breakout sequencing.

## Long

Enter long when shorts are crowded:

- funding is very negative;
- OI is elevated;
- force orders spike;
- TFI or OI delta confirms unwind pressure.

## Short

Enter short when longs are crowded:

- funding is very positive;
- OI is elevated;
- force orders spike;
- TFI or OI delta confirms unwind pressure.

## Invalidation

- no force spike;
- funding has normalized;
- OI is not elevated;
- volatility panic dominates the event;
- regime veto blocks the context.

## Checkpoint 1 Result

The local V3 database had no force orders, so a research-only DB copy was backfilled from server force-order data. After backfill the setup generated 71 closed trades, but ER and liquidation capture failed hard gates. Current formulation should be rejected unless audit identifies a concrete measurement flaw.
