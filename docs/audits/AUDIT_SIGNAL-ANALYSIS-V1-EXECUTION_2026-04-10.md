# AUDIT: SIGNAL-ANALYSIS-V1 (EXECUTION)
Date: 2026-04-10
Auditor: Claude Code
Commit: fea17aa
Builder: Cascade

## Verdict: DONE

## Execution Integrity: PASS
## Data Isolation: PASS (production DB read-only, run artifacts gitignored)
## Conditional Gate: PASS (D3 correctly skipped at 0/3 qualifying segments)
## Audit Fixes: PASS (dead variable removed, p-threshold comment added)
## D4 Completeness: PASS (all PENDING values populated, active branch resolved)
## Artifact Consistency: PASS (D4 numbers match Cascade execution summary)

---

## D2 Result — Verified

11,841 events across 145,921 bars (2022-01-01 → 2026-03-01).
All events in P1_MATURE bucket by construction (feature engine config = bucket boundaries).

| Segment | n | mean_fwd4 | p | hit_rate | Edge |
|---|---|---|---|---|---|
| S1 bear collapse | 1,596 | -0.008 | 0.836 | 28.0% | NO |
| S2 bear range | 2,196 | -0.063 | 0.075 | 25.1% | NO |
| S3 recovery/pre-ETF | 2,373 | -0.068 | **0.022** | 26.4% | NO (sig. negative) |
| S4 ETF/halving | 1,859 | -0.057 | 0.115 | 28.6% | NO |
| S5 rally to ATH | 2,091 | -0.084 | **0.012** | 27.4% | NO (sig. negative) |
| S6 recent | 1,726 | -0.050 | 0.232 | 27.3% | NO |

**P1+MATURE edge: 0/6**

Decision tree: **Branch 4 — No signal at this granularity → Stop optimization, redesign feature level**

---

## Strategic Assessment

**The finding is definitive and unambiguous. Three independent lines of evidence converge:**

**1. All 6 segments negative.** Not one year, not one regime shows positive mean forward return
at bar+4. This is not noise in one bucket — it is consistent across bear market, recovery,
ETF launch, halving rally, and consolidation.

**2. Hit rates are mathematically losing.** 25–29% hit rate with a 1:2 SL/TP model requires
33.3% breakeven. Every regime is below breakeven. This is not a p-value artifact — it is a
structural P&L distribution problem. The signal sends price into the stop more than twice as
often as it reaches the target.

**3. Two segments are significantly negative.** S3 (p=0.022) and S5 (p=0.012) are not just
"not positive" — they are reliably negative. This means the sweep+reclaim event at 15m
timeframe with default parameters is informationally anti-predictive in those regimes.

**The optimization history makes sense in retrospect:** Runs 1–4 produced apparent edge only
through volume lever exploitation (weight_sweep_detected=4.95, sweep_proximity_atr=1.8) or
small-sample artifacts (31 trades over 4 years). The optimizer was doing its job — it found
the configurations that maximize objectives on a signal that has no structural edge. It had
nowhere useful to go.

---

## One verification before declaring full signal death

D2 computed bar+1, bar+4, bar+16, bar+96 forward returns for all 11,841 events.
D4 reports only bar+4. Before committing to full feature-level redesign, verify bar+16
and bar+96 mean returns per segment from the local event_study_v1.json.

Rationale: if bar+96 returns are also negative, the signal has no edge at any hold horizon
and redesign is the only path. If bar+96 returns are positive in some segments, the signal
may have edge at longer hold horizons — a different exit model, not a signal redesign.

This is a 15-minute data query on existing local JSON, not a new campaign.

---

## Recommended Next Step

**SIGNAL-HORIZON-CHECK** — one-time data query, not a milestone.

Ask Cascade to run a 20-line Python snippet against the local
`research_lab/runs/event_study_v1.json`:

For each segment, compute:
- mean_fwd1, mean_fwd4, mean_fwd16, mean_fwd96
- hit_rate_fwd16 (% positive raw return at bar+16)
- hit_rate_fwd96 (% positive raw return at bar+96)

Decision:
- If bar+16 and bar+96 also negative across all segments → full signal redesign confirmed
- If bar+96 positive in 4+ segments → exit model redesign, not signal redesign
  (same structural event, different harvesting mechanism)

This query takes 15 minutes and changes the redesign scope. It should run before any
architectural decision about what to build next.

No commit needed. Output to stdout. Results go directly to Claude Code.
