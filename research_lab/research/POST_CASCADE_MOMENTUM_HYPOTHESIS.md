# Post Cascade Momentum Hypothesis

## Market Structure

After a liquidation cascade, forced exits may clear weak positioning. If the aftermath state persists, momentum can continue in the cascade direction with cleaner structure than during the liquidation event itself.

## Edge

- Counterparty: surviving participants continuing in the cascade direction.
- Timing: enter after `post_liquidation` regime confirms, not during force-order spike.
- Data: regime state, historical force-order direction, TFI, price structure.
- Exclusions: no CVD divergence, no compression-breakout simultaneity, no real-time cascade catching.

## Long

Enter long after an upward cascade:

- regime is `post_liquidation`;
- recent force orders are dominated by short-liquidation/upward pressure;
- TFI remains positive;
- stop sits below recent structure.

## Short

Enter short after a downward cascade:

- regime is `post_liquidation`;
- recent force orders are dominated by long-liquidation/downward pressure;
- TFI remains negative;
- stop sits above recent structure.

## Checkpoint 1 Result

Using a research-only DB copy with server force orders, the full V3-range replay produced zero `post_liquidation` cycles. The setup therefore did not get a valid hypothesis test on the target regime. The checkpoint is blocked by absent target-regime state, not by measured negative edge.
