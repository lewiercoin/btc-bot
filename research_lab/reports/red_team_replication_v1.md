# RED_TEAM_REPLICATION_V1

## Final Verdict

- M6 verdict: `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`
- Part A verdict: `SMC_GATES_DESTROYED_RAW_EDGE`
- Part B verdict: `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`
- JSON SHA256: `96128632F84C93AD77E26D301B44D81139B0E952E7E0812B352AAD7842FE2AE0`

## Part A Comparison

| Run | Status | Event N | Net 5b PF | Net 5b Median | MFE Before/After | Flip Gate |
|---|---|---:|---:|---:|---:|---|
| A1_BASELINE | RUN | 1271 | 1.061059 | -0.000442 | 2.352473 | False |
| P1 | RUN | 1212 | 0.966565 | -0.000469 | 2.419803 | False |
| P2 | RUN | 1306 | 0.986126 | -0.000477 | 2.438766 | False |
| P3 | RUN | 903 | 1.216467 | -0.000206 | 1.939245 | False |
| P4 | RUN | 1312 | 1.070718 | -0.000428 | 2.349981 | False |
| P5 | RUN | 1271 | 1.457767 | 0.000558 | 2.352473 | False |
| A3_RAW_SWEEP_RECLAIM | RUN | 14236 | 2.847015 | 0.001811 | 0.384914 | True |

## Part A Notes

- Analytical baseline check: `True`
- Analytical tolerance: `1e-06`
- Prior raw baseline SHA (informational only): `8CA802FD610DFE552225C9318A455345D8917D688ABBD2B3647CA69C4B6A78A4`
- Observed A.1 stable SHA: `5A6B8505C1726EE1527FBF1131A75C4E053AF3E0188696F53FABA8E369B5482F`

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
