# Research Landscape Reset — 2026-06-04

Author: Claude Code (independent auditor)
Trigger: M4 cancellation + 5 consecutive HYPOTHESIS_INVALIDATED outcomes
between 2026-05-27 and 2026-06-04.

This document is a snapshot of the research lab landscape as of today, a
written justification for stopping further setup-discovery diagnostics in
the current sweep / SMC / liquidity / order-flow family, and a list of
**genuinely new directions** the operator may pick from.

It is not a plan and not a handoff. It exists to prevent another wasted
30-hour milestone before the operator has had a chance to look at the full
state of play.

---

## 1. State of the closed research families

All of the families below have been independently audited as
`HYPOTHESIS_INVALIDATED` or `CLOSED`. Each row lists the verdict file or
analysis report so the lineage is reproducible.

| Family | Last verdict | Date | Closing artifact |
|---|---|---|---|
| Trial-00095 baseline | DEPLOYED / OPTIMAL | 2026-05-27 | `docs/audits/AUDIT_TRIAL_00095_ATTRIBUTION_V1_2026-05-30.md` |
| SWEEP_RECLAIM family (4 specialists: session, range, trend, special-regime) | CLOSED | 2026-05-13 | `docs/audits/AUDIT_SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27.md` |
| SMC sequence (sweep → displacement → CHoCH → FVG → mitigation) | HYPOTHESIS_INVALIDATED | 2026-05-27 | `docs/audits/AUDIT_SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md` |
| MFE accessibility timeline (27 knowable states inc. TFI/CVD proxies) | `STOP_SMC_RESEARCH_TRIAL_00095_ALREADY_OPTIMAL` | 2026-05-27 | `docs/analysis/MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1_2026-05-27.md` |
| Order-flow / liquidation edge discovery | CLOSED | 2026-05-28 | `docs/audits/AUDIT_ORDER_FLOW_LIQUIDATION_EDGE_DISCOVERY_V1_PLAN_2026-05-28.md` + 3 derived diagnostics, all INVALIDATED |
| Liquidation burst reversal (15m + 5m + entry + timeframe followup) | FULLY INVALIDATED | 2026-05-28 | `docs/audits/AUDIT_LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1_2026-05-28.md` |
| Volatility breakouts (volume-confirmed range breakout) | CLOSED | 2026-05-xx | tracker entry |
| Regime shift detection (ADX/CHOP + filtered HMM) | CLOSED, family exhausted | 2026-05-xx | tracker entry + `docs/audits/AUDIT_filtered_HMM_*` |
| NY reversal after London | HYPOTHESIS_INVALIDATED | 2026-06-xx | tracker entry |
| Asia range London breakout | HYPOTHESIS_INVALIDATED | 2026-xx | tracker entry |
| OANDA EURUSD M15 sweep reclaim transfer | HYPOTHESIS_INVALIDATED | 2026-xx | tracker entry |
| OANDA XAU sweep reclaim transfer | tested, closed | 2026-xx | tracker entry |
| RECLAIM_REJECTION_DIAGNOSTIC_V1 (M3) | HYPOTHESIS_INVALIDATED | 2026-06-04 | `docs/audits/AUDIT_M3_RECLAIM_REJECTION_DIAGNOSTIC_V1_2026-06-04.md` |

That is **5 consecutive setup-family invalidations in the BTCUSDT 15m
domain in 8 days**, plus full closure of regime-shift, volatility-breakout,
order-flow/liquidation, and cross-market OANDA families. Trial-00095 (the
single validated edge) is the production reference.

---

## 2. Why M4 was cancelled

The cancellation of M4 (`CONFLUENCE_GATE_ACCESSIBILITY_DIAGNOSTIC_V1`) was
not a process error — Codex started work in good faith. The original M3
audit identified the confluence-gate wait as the suspected bottleneck, and
M4 was designed to diagnose it.

The retroactive landscape review revealed that
`MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` already measured 27
knowable states from the same primary database, including:

| M4-proposed proxy | Existing equivalent state | k med (bars) | net 5b | PF | MFE consumed |
|---|---|---:|---:|---:|---:|
| P1_immediate_tfi_sign | `tfi_aligned_known` | 3 | -0.00096 | 0.680 | 0.55 |
| P2_short_window_cvd_delta | `cvd_absorption_proxy_known` | 4 | -0.00082 | 0.728 | 0.68 |
| P3_no_confluence | `raw_sweep_known` | 0 | -0.00061 | 0.758 | 0.34 |
| (other M3 proxy) `confluence_threshold_known` | TFI ∧ CVD agree | 3 | -0.00087 | 0.740 | 0.54 |
| (best PF in entire 27-state table) | `deep_sweep_threshold_known` | 0 | -0.00012 | 0.890 | 0.56 |

All FAIL net expectancy after costs. The strongest cohort in the entire
table (`deep_sweep_threshold_known`, 3245 events) has PF 0.890 — still
losing. The diagnostic concluded:

> FAIL: no early knowable state has positive median net return after costs.
> FAIL: best state win rate is approximately random after entry timing.
> FAIL: best state PF proxy is too weak after costs.

M4 would have re-tested approximately the same proxies on approximately the
same dataset. Estimated incremental value: ~10% (slight differences in
trigger families and explicit F-3 gates per proxy). Estimated cost: 20-36
hours. ROI too low.

The deeper lesson is that the confluence-gate wait is not the bottleneck
in isolation — the entire post-sweep timing model fails because the
favorable excursion is consumed before any state-knowable signal can
arrive. Adding more proxies does not change the underlying physics. This
is the result the existing MFE accessibility diagnostic already reached.

---

## 3. External research vs internal coverage

A recent external search (Grok, 2026-06-04) returned five primary sources:
NautilusTrader, `smart-money-concepts` (Python), `PyIndicators`, arXiv
2602.00776 (order-flow imbalance + SHAP), arXiv 2108.09763 (BTC market
fragmentation and cross-impact). The first three are tools, the last two
are research papers.

Mapped against internal closed work:

| External source | Internal coverage | Status |
|---|---|---|
| `smart-money-concepts` (sweeps, EQH/EQL, BOS/CHoCH, FVG, kill zones) | SMC sequence + sweep_reclaim taxonomy, 4 specialist sweep cohorts | INVALIDATED |
| `PyIndicators` (liquidity sweeps, pools, voids, EQH/EQL) | same as above + level_scanner foundation | INVALIDATED |
| arXiv 2602.00776 (order flow imbalance, SHAP-explained, Binance perp tick) | ORDER_FLOW_LIQUIDATION_EDGE_DISCOVERY + 3 derived diagnostics | CLOSED, INVALIDATED |
| arXiv 2108.09763 (liquidation cascades, cross-impact) | LIQUIDATION_BURST_REVERSAL (15m, 5m, entry, timeframe followup) | FULLY INVALIDATED |
| NautilusTrader + Tardis (framework + tick data) | not tested — framework decision, not strategy | OPEN |

The closed internal families cover the actionable surface of all four
external research sources. The only genuinely untested item is the
**framework / data layer** (NautilusTrader / Tardis), which is a
production architecture change, not a setup hypothesis.

---

## 4. Trial-00095 conditional edge attribution — what it actually revealed

The independent audit from 2026-05-30
(`AUDIT_TRIAL_00095_ATTRIBUTION_V1_2026-05-30.md`) re-analyzed the 274
production trades of the validated trial-00095 edge and uncovered four
**concrete, actionable refinements** to the validated edge — none of which
have been implemented yet:

| Finding | Numbers | Refinement opportunity |
|---|---|---|
| Direction asymmetry | LONG ER 2.377 (252 trades), SHORT ER -0.805 (22 trades, 8%) | Reject SHORT signals. Immediate ER lift. |
| Regime concentration | Uptrend ER 2.614 (75% of trades), downtrend ER 0.690 (20%) | Test uptrend-only gating. Concentration is strong. |
| TFI alignment matters | Aligned ER 2.391, opposed ER 0.816 | Require TFI alignment as hard filter, not soft input. |
| Exit timing leakage | 92.4% of losers had ≥1R MFE before going red | Trailing stop or partial take-profit at 1R. Entry is fine, exit is sloppy. |
| Near-miss population unavailable | No `decision_outcomes` / `feature_snapshots` tables | Reconstruct rejected near-miss candidates before any threshold relaxation. |

Each refinement is bounded, has a numeric expected lift hypothesis, and
sits on a **validated edge** rather than chasing an invalidated one. The
recommendation in the existing audit (`PLAN_NEAR_MISS_RECONSTRUCTION_DIAGNOSTIC`)
correctly identified reconstruction as the prerequisite for threshold
relaxation, but the four direct refinements above can proceed in parallel.

This is qualitatively different work from the closed setup-discovery
diagnostics: it is **refinement of a known winner**, not discovery of a
new winner. Expected hit rate of useful outcomes is much higher.

---

## 5. Open directions the operator may choose from

Listed in order of estimated impact-per-hour. The operator picks one (or
explicitly chooses to pause research).

### Option D1 — Trial-00095 LONG-only and regime gating refinement (recommended)

**Hypothesis:** Removing SHORT signals and gating LONG signals to uptrend
regime lifts production ER materially without any threshold change.

**Why now:** Both effects already measured on production trade history.
SHORT cohort is 8% of trades with ER -0.805 — pure drag. Uptrend ER 2.614
vs downtrend 0.690 is a 4× spread on a 75/20 split.

**Scope:** Research-only deterministic backtest of the validated trial-00095
gate set with two amendments: `direction == LONG only`, `regime ∈ {uptrend}`.
Re-run on the same 274-trade window. Report ER, PF, WR, sample-size cost,
and decision-bar count loss vs baseline.

**Budget:** 6-10 hours implementation + 2-4 hours audit. Single milestone.

**Builder:** Codex.

**Risk:** Overfit to attribution sample. Mitigation: walk-forward across
2-3 disjoint windows before promotion discussion.

### Option D2 — Exit-timing rescue diagnostic

**Hypothesis:** 92.4% of trial-00095 losers had ≥1R MFE before going red.
A trailing stop or 50% take-profit at 1R captures part of that
opportunity without changing the validated entry.

**Why now:** Entry edge is validated; exit is the leak. Measured leak is
large (92% of losers).

**Scope:** Replay 274 trades with three alternative exit rules:
(a) trailing stop at 0.5R after 1R MFE reached;
(b) 50% partial at 1R + remainder runs to original target;
(c) hard exit at 1R MFE.
Report ER, PF, WR, max-drawdown impact per rule. Frozen pre-data.

**Budget:** 8-14 hours implementation + 2-4 hours audit.

**Builder:** Codex.

**Risk:** Slippage modeling. Mitigation: assume entry-side cost only, no
exit-side optimism.

### Option D3 — Near-miss rejected population reconstruction

**Hypothesis:** Reconstruction reveals whether near-threshold candidates
(0.00649 ≤ depth < 0.00714) have positive expectancy independent of
the accepted-trade attribution.

**Why now:** Recommended by existing trial-00095 attribution audit as the
prerequisite for any threshold-relaxation discussion. Without it, threshold
relaxation is blind.

**Scope:** Reconstruct missing `decision_outcomes` / `feature_snapshots` from
canonical DB + signal_engine replay. Generate rejected near-miss candidates.
Compute their (hypothetical) ER as if executed. Report distribution.

**Budget:** 16-24 hours implementation (data archaeology heavy) + 4-8 hours
audit.

**Builder:** Codex.

**Risk:** Reconstruction may not be 1:1 reproducible. Mitigation: explicit
divergence report at each step.

### Option D4 — NautilusTrader / Tardis framework feasibility study

**Hypothesis:** A tick-precision, multi-venue research framework with
liquidation data unblocks setup families that 60s aggtrade buckets cannot
adequately measure.

**Why now:** Five consecutive invalidations on 15m+aggtrade data suggest
the dataset itself may be the bottleneck for liquidation-anchored work.
This is a **measurement instrument upgrade**, not a new setup hypothesis.

**Scope:** Spike a minimal NautilusTrader project that replays BTCUSDT
perpetual ticks via Tardis for one closed-family hypothesis
(e.g., `LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1`). Compare results
to the existing 60s-bucket diagnostic. Report whether tick precision
changes the invalidation verdict for any closed family.

**Budget:** 30-60 hours implementation (steep learning curve), 4-8 hours
audit. Multi-week milestone.

**Builder:** Codex or Cascade. This is genuinely new tooling, so builder
choice should reflect Tardis SDK familiarity, not historical M3/M4
preference.

**Risk:** Large up-front cost with no guarantee that closed families
re-open. Mitigation: hard kill-switch after the first replayed family also
returns INVALIDATED.

### Option D5 — Pause research lab, stabilize production

**Hypothesis:** Five consecutive failures suggest diminishing returns on
discovery work. Production hardening (monitoring, dashboards, deploy
discipline, paper validation V3) is the higher-leverage activity until
new tooling or new data unblocks discovery.

**Why now:** Trial-00095 is the validated edge in production. The bot is
trading. Research effort is currently producing zero edge per 30-hour
milestone. Stability work would compound paid attention.

**Scope:** Operator-defined. Examples: P&L reconciliation hardening,
alert coverage matrix completion (`docs/audits/alert_coverage_matrix_2026-04-24.md`
has gaps), automatic drift detection on production database, deploy
runbook V3.

**Budget:** Variable. Open-ended.

**Builder:** Operator-chosen.

**Risk:** Loss of research momentum. Mitigation: time-box pause to 2-4
weeks then re-evaluate.

---

## 6. Recommendation

Pick **D1** (Trial-00095 LONG-only and regime gating refinement) as the
next milestone.

Rationale: cheapest, fastest, lowest-risk path to a measurable ER
improvement on a validated edge, using data that already exists. Even if
walk-forward kills it, the work product is reusable evidence for or
against direction/regime asymmetry across future setup candidates. ROI is
strictly positive in expectation.

D2 is the natural follow-up if D1 passes walk-forward. D3 is the
prerequisite for any threshold relaxation. D4 is a strategic question, not
a tactical one, and should be discussed before committing 30-60 hours. D5
is the right answer if the operator believes the research lab is
exhausted; this auditor does not yet recommend D5, but a clear-eyed
operator could.

The operator decides. This auditor does not.

---

## 7. Decision waiting on operator

- Approve **D1** → I generate the M5 handoff for Codex immediately.
- Approve **D2** → same.
- Approve **D3** → same, with explicit caveats on reconstruction fidelity.
- Approve **D4** → I issue the framework feasibility study handoff with
  builder selection question first.
- Approve **D5** → I update milestone tracker with pause state and stand
  down the audit cadence until operator re-opens research lab.
- Veto all five and propose a different direction → I revise.

There is no default action. The auditor will not pick.
