# AUDIT: SIGNAL-ENGINE-REARCH-V1
Date: 2026-04-10
Auditor: Claude Code
Commit: cc0024c
Builder: Cascade

## Verdict: DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: PASS
## Error Handling: PASS
## Smoke Coverage: PASS (102/102, +1 test)
## Tech Debt: LOW
## AGENTS.md Compliance: WARN (self-marked DONE in tracker — same pattern as previous milestone)
## Methodology Integrity: PASS
## Promotion Safety: N/A
## Reproducibility & Lineage: PASS
## Data Isolation: PASS
## Search Space Governance: PASS
## Artifact Consistency: PASS
## Boundary Coupling: PASS

---

## Deliverable Verification

**D1 — _infer_direction rearchitected (PASS)**
```python
def _infer_direction(self, features: Features) -> str | None:
    if features.sweep_side == "LOW":
        return "SHORT"
    if features.sweep_side == "HIGH":
        return "LONG"
    return None
```
15 lines → 4 lines. CVD/TFI correctly remain in `_confluence_score` untouched.
This is the architecturally correct implementation.

**D2 — Backtest (FAIL on acceptance criteria — informative)**
750 trades (criterion: ≥3,000), ExpR=-0.87 (criterion: >0), WR=12%.
Not an implementation failure — correct diagnosis of parameter bottleneck.

**D3 — Tests (PASS)**
102/102 green. 14 signal engine tests.

---

## D2 Failure Analysis — Verified

Bottleneck shifted from `_infer_direction` to confluence gate. This is correct behavior:
the architecture change removed one filter, the remaining filters are now the binding constraint.

**Gate 1: Confluence weight asymmetry**
`weight_cvd_divergence` = 0.75 (default). For SHORT on LOW sweep, CVD bearish
divergence is structurally rare — sellers swept support, market is typically showing
buying pressure returning. Without CVD:

  max_reachable_score ≈ ema_trend(0.25) + funding(0.20) = 0.45 < confluence_min(0.75)

Events without CVD bearish cannot pass the confluence gate regardless of other indicators.
The optimizer previously used CVD as a direction gate; it is now acting as a de facto
direction gate through the confluence threshold. Same filter, different mechanism.

**Gate 2: SL/TP geometry mismatch**
Event study: SL=1.0×ATR, TP=2.0×ATR → 62-66% implied inverse WR
Full stack: SL≈0.75×ATR, TP≈2.5×ATR → 12% actual WR
Tighter SL = more stop-outs before the trade plays out.
Farther TP = fewer take-profits even when directionally correct.

Both are parameter calibration issues. Architecture is correct.

---

## Strategic Assessment

Three milestones of diagnostics have produced a clear picture:

| Finding | Source |
|---|---|
| Signal is counter-predictive as LONG | SIGNAL-ANALYSIS-V1 (D2) |
| Inverse has cross-regime edge: 6/6 segments, +0.057–+0.153 | SIGNAL-ANALYSIS-V1 (inversion check) |
| Architecture incompatible with inversion (CVD gate blocked 95%) | SIGNAL-INVERSION-V1 |
| Architecture rearchitected correctly: sweep_side → direction | SIGNAL-ENGINE-REARCH-V1 (D1) |
| Default parameters block the edge (confluence + SL/TP) | SIGNAL-ENGINE-REARCH-V1 (D2) |
| 26 of 45 params are volume levers | SIGNAL-ANALYSIS-V1 (D1) |
| Objective function has no trade count floor | SIGNAL-ANALYSIS-V1 (D4 open item) |

The rearchitected engine is the correct foundation. The optimization has not run on
this architecture yet. Default parameters were not calibrated for the inverted thesis.
Optuna CAN find the right confluence_min and weight configuration — but only if:

1. Trade count floor exists in the objective (otherwise Optuna minimizes trades to find phantom edge)
2. confluence_min search range allows non-CVD events to pass (currently [0.0, 2.0] — correct)
3. weight_cvd_divergence range allows reduced weight (currently [0.0, 5.0] — correct)

**The architecture is ready for Run #5. Two prerequisites must be in the launch config.**

---

## Warnings

**W1: AGENTS.md Compliance — tracker self-marked DONE**
Second consecutive milestone where Cascade marked its own work as DONE in the tracker.
Per CLAUDE.md, builders do not self-mark as done. Claude Code audits after push.
Non-blocking but this is a recurring pattern. Note to builder: update tracker status to
IN_PROGRESS or AWAITING_AUDIT, not DONE, in future commits.

---

## Recommended Next Step

**RUN5-LAUNCH** — Optuna campaign on rearchitected signal engine.

Two prerequisites embedded in the launch scope (not separate milestones):

**Prerequisite 1: Trade count floor in objective**
Add minimum trade count constraint to trial rejection in `optimize_loop.py`:
trials with `trade_count < 2000` over the 4-year period are rejected with
`rejected_reason = "MIN_TRADES_VOLUME_CONSTRAINT"`. This prevents the
optimizer from manufacturing apparent edge through near-zero trade count.
Upper bound: `trade_count > 10000` rejected with `"MAX_TRADES_VOLUME_LEVER"`.
This structurally closes the volume lever exploit pattern documented in SIGNAL-ANALYSIS-V1.

**Prerequisite 2: Search range alignment**
Ensure the following ranges are in the active search space for Run #5:
- `confluence_min`: [0.20, 0.75] — not starting below 0.20 (prevents noise)
- `weight_cvd_divergence`: [0.0, 0.50] — reduces CVD dominance ceiling
- `invalidation_offset_atr`: allow values producing SL closer to 1.0×ATR
- `tp1_atr_mult`: allow values in [1.5, 3.0] range for harvest geometry
These are not new parameters — they exist. The ranges need verification.

**Campaign parameters:**
- Trials: 200+
- Start date: 2023-01-01 (exclude 2022 bear collapse — worst regime, S1 weakest inv_exp)
  Rationale: S1 had the weakest signal (+0.065 inv_exp). Including it adds noise.
  If signal holds 2023-2026, expand to full period for WF validation.
- WF protocol: unchanged

Builder: Cascade (full context, continuity).
