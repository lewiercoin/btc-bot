# Absorption Trend-Day Capture

Milestone: `ABSORPTION-CONTINUATION-RESEARCH-V1`

Trend-day capture was not promoted to a final gate result for the current implementation because the setup failed earlier primary gates:

- only 4 total trades,
- uptrend ER `0.34088`,
- absorption confirmation hit rate `0.25`,
- minimum total trades gate failed.

The specific reference day `2026-05-11` is outside the local V3/grid-compatible replay dataset, which ends at `2026-03-29`.

Required future work if the hypothesis is redesigned:

1. identify clean trend days inside the available 2022-2026-03-29 replay range,
2. measure capture rate against those days,
3. separately export or backfill `2026-05-11` as a post-V3 out-of-sample case study.

Current trend-day capture verdict: not decision-useful because the setup already fails primary gates.
