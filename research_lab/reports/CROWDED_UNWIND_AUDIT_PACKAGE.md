# Crowded Unwind Audit Package

Milestone: `CROWDED-UNWIND-RESEARCH-V1`  
Builder: Codex  
Branch: `research/crowded-unwind-v1`  
Verdict: `REJECT`

## Executive Summary

Checkpoint 1 implemented `crowded_unwind_long` and `crowded_unwind_short` as research-only setups. The first replay against local `storage/btc_bot.db` produced zero candidates because the local V3 database had no `force_orders` rows. I did not mutate the original local DB.

For a valid research replay, I created an untracked research-only copy of the local database and imported server `force_orders` for the V3 range:

- Original local DB: `storage/btc_bot.db`
- Research-only DB copy: `research_lab/data/crowded_unwind_backtest.db` (untracked)
- Imported force orders: `146864`
- Force order time range: `2022-01-01T00:02:07.244000+00:00` -> `2024-12-01T23:58:59.379000+00:00`
- Original local `storage/btc_bot.db` remains unchanged.

Full-range replay on the backfilled research DB:

- Date range: `2022-01-01` -> `2026-03-29`
- Decision cycles: `148596`
- Candidates: `95`
- Closed trades: `71`
- Crowded leverage trades: `71`
- ER: `-0.352508`
- PF: `0.40411`
- Max drawdown pct: `0.168535`
- Liquidation capture rate: `0.323944`

## Hard Gate Results

| Gate | Requirement | Actual | Result |
|---|---:|---:|---|
| Crowded leverage ER | `> 1.5` | `-0.352508` | FAIL |
| Liquidation capture | `>= 50%` | `0.323944` | FAIL |
| Minimum trades | `>= 20` | `71` | PASS |
| Crowded trade count | `>= 10` | `71` | PASS |
| Overlap vs sweep_reclaim | `< 30%` | not run | BLOCKED |
| Walk-forward | `2/2` | not run | BLOCKED |
| Safety flags | none blocking | none | PASS |
| Explainability | reasons[] complete | yes | PASS |

## Direction Breakdown

| Direction | Trades | ER | PF | DD |
|---|---:|---:|---:|---:|
| LONG | `21` | `-0.312456` | `0.417328` | `0.05837` |
| SHORT | `50` | `-0.36933` | `0.399153` | `0.123592` |

## Interpretation

This is not a data-sparsity failure after force-order backfill. The setup reached valid sample size, but both directions lost money and liquidation capture stayed below the 40% reject threshold. Force-order spikes plus funding/OI crowding, as currently formulated, are not predictive enough for a tradeable unwind.

## Verdict

`CROWDED-UNWIND-RESEARCH-V1` should be rejected for the current formulation.

The handoff allowed one diagnostic iteration only for marginal cases. This result is not marginal:

- target-regime ER is negative;
- liquidation capture is below reject threshold;
- PF is below 1.0 in both directions.

Recommended next step: Claude Code audit this checkpoint and decide whether to close crowded_unwind or authorize a tightly scoped diagnostic iteration only if it identifies a concrete measurement flaw rather than parameter rescue.
