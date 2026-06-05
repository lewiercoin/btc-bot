# RED_TEAM_REPLICATION_V1

## Final Verdict

- M6 verdict: `BASELINE_NOT_REPRODUCIBLE`
- Part A verdict: `BASELINE_NOT_REPRODUCIBLE`
- Part B verdict: `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`
- JSON SHA256: `AAE5A20A66AAFD207DA2DED39F1A951EAE33497A27DEF0F18FE9A051D03DC23F`

## Part A Comparison

| Run | Status | Event N | Net 5b PF | Net 5b Median | MFE Before/After | Flip Gate |
|---|---|---:|---:|---:|---:|---|
| A1_BASELINE | RUN | 1271 | 1.061059 | -0.000442 | 2.352473 | False |
| P1 | NOT_RUN | n/a | n/a | n/a | n/a | False |
| P2 | NOT_RUN | n/a | n/a | n/a | n/a | False |
| P3 | NOT_RUN | n/a | n/a | n/a | n/a | False |
| P4 | NOT_RUN | n/a | n/a | n/a | n/a | False |
| P5 | NOT_RUN | n/a | n/a | n/a | n/a | False |
| A3_RAW_SWEEP_RECLAIM | NOT_RUN | n/a | n/a | n/a | n/a | False |

## Part A Notes

- Expected prior baseline SHA: `8CA802FD610DFE552225C9318A455345D8917D688ABBD2B3647CA69C4B6A78A4`
- Observed A.1 stable SHA: `5A6B8505C1726EE1527FBF1131A75C4E053AF3E0188696F53FABA8E369B5482F`
- SHA match: `False`

## Part B Canonical Result

- Canonical DB path: `F:\crowded_unwind_backtest.db`
- Trail rule classification: `NOT_DERIVABLE_FROM_FROZEN_ARTIFACT`
- Canonical verdict: `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`
- Full Pearson: `0.785963`
- SL Pearson: `0.954062`
- TP_TRAIL Pearson: `0.611562`
- Count: `274`
- ER: `2.348494`
- PF: `4.101065`
- WR: `0.489051`

This is not a re-derivation of the edge; it is a reproduction check that the recorded trades behave as recorded.

## Database Binding

- Bound verdict: `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`
- Canonical binds: `True`
- Snapshot results, if present, are comparison-only and never substitute for canonical results.
