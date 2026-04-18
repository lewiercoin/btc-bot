# RUN14_UPTREND_CONTINUATION

## Status

Local optimization is in progress.

This report is the destination artifact for the run14 study defined in `docs/research_lab/protocols/UPTREND_CONTINUATION_V1.md` and executed with `research_lab/configs/run14_uptrend_continuation.json`.

## Objective

Test whether a research-only, tightly gated uptrend continuation overlay can add BTC uptrend participation without broadly degrading the Trial #63 reversal baseline.

## Local Execution

Command:

```powershell
python -m research_lab optimize --source-db-path storage/btc_bot.db --store-path research_lab/research_lab.db --snapshots-dir research_lab/snapshots --protocol-path research_lab/configs/run14_uptrend_continuation.json --start-date 2022-01-01 --end-date 2026-03-01 --n-trials 80 --study-name run14-uptrend-continuation --seed 42 --warm-start-from-store
```

Protocol characteristics:

- `walkforward_mode=post_hoc`
- `window_mode=anchored_expanding`
- `train_days=730`
- `validation_days=365`
- `step_days=365`
- `min_trades_full_candidate=120`
- `max_trades_full_candidate=300`
- active search surface limited to four research-only continuation parameters

## Research Surface

Sampled parameters:

- `allow_uptrend_continuation`
- `uptrend_continuation_reclaim_strength_min`
- `uptrend_continuation_participation_min`
- `uptrend_continuation_confluence_multiplier`

Frozen baseline behavior:

- Trial #63 reversal parameters unchanged
- no live settings changes
- no `core/**` promotion changes
- no broad `allow_long_in_uptrend` relaxation

## Baseline Reference

Trial #63 / Run #13 reference metrics:

- expectancy_r: +0.994
- profit_factor: 2.486
- max_drawdown_pct: 5.4%
- trades: 183

## Pending Result Capture

To be filled after local run completion:

- total trials evaluated
- accepted vs rejected counts
- Pareto candidates
- walk-forward pass / fail summary
- best candidate parameter vector
- overall metrics versus baseline
- uptrend-long isolated contribution
- non-uptrend / legacy edge comparison
- recommendation

## Preliminary Notes

Implementation for this study was added as a research-only overlay inside `research_lab/**`.

The live strategy path remains unchanged.
