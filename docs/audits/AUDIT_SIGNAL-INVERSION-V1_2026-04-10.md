# AUDIT: SIGNAL-INVERSION-V1
Date: 2026-04-10
Auditor: Claude Code
Commit: ab664e2
Builder: Cascade

## Verdict: DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: PASS
## Error Handling: PASS
## Smoke Coverage: PASS (101/101, +13 signal engine tests)
## Tech Debt: LOW
## AGENTS.md Compliance: WARN (minor — see below)
## Methodology Integrity: PASS
## Promotion Safety: N/A (no candidate promoted)
## Reproducibility & Lineage: PASS
## Data Isolation: PASS
## Search Space Governance: PASS
## Artifact Consistency: PASS
## Boundary Coupling: PASS

---

## Deliverable Verification

**D1 — Direction flip (PASS)**
`signal_engine.py:106-109`: inversion is correct.
- LONG now requires sweep_side == "HIGH" (was "LOW")
- SHORT now requires sweep_side == "LOW" (was "HIGH")
Logic consistent with failed-reclaim thesis.

**D2 — Backtest (NEGATIVE — informative result)**
563 trades, WR=10.5%, ExpR=-0.94, PF=0.28.
D2 acceptance criterion (ExpR > 0) not met.
This is a valid experimental outcome, not an implementation failure.
The NEGATIVE result precisely identifies the architectural bottleneck.

**D3 — Direction audit (PASS)**
DIRECTION_AUDIT_V1.md is thorough and correct. All 9 components assessed.
Whitelist fix: NORMAL/COMPRESSION/POST_LIQUIDATION → symmetric (LONG, SHORT).
Rationale is sound — whitelist should not encode sweep direction assumptions.
Flag for future: `allow_long_in_uptrend` counterpart not blocking.

**D4 — Tests (PASS)**
8 → 13 signal engine tests. Inversion-specific cases added.
101/101 green. No regressions.

---

## The Core Finding

Event study: 11,841 events, 62–66% implied WIN rate for inverse SHORT.
Full backtest: 563 trades (95% filtered), 10.5% WR.

The discrepancy is caused entirely by `_infer_direction`. The function uses CVD/TFI
as direction DETERMINANTS, not filters. For inverted SHORT on LOW sweep, it requires
CVD bearish divergence — which is structurally rare at support sweeps (sellers were
just active, not returning). 95% of events never enter the execution stack.

The 5% that pass (CVD bearish + LOW sweep + reclaim) are not "failed reclaims" in the
inverse sense — they are events where selling pressure persisted THROUGH the reclaim.
This subset performs even worse because it selects for the most adverse microstructure
conditions for a SHORT.

**The architecture encodes the original (wrong) thesis at the direction determination
layer.** Flipping 2 lines in the validation step is insufficient — the direction source
must change from CVD/TFI to sweep_side.

Required architecture:
  Current:  CVD/TFI → infer direction → validate against sweep_side
  Required: sweep_side → determine direction → CVD/TFI as confluence weight only

This is precisely documented in DIRECTION_AUDIT_V1.md. The diagnosis is correct.

---

## Warning

**AGENTS.md Compliance: WARN**
Tracker was updated to DONE by the builder (commit ab664e2). Per CLAUDE.md, builders
do not self-mark as done — Claude Code audits after push.
The content is accurate, so this is a process deviation, not a substantive error.
Non-blocking but noted for discipline record.

---

## Observations

- Whitelist symmetry change (NORMAL/COMPRESSION/POST_LIQUIDATION: LONG-only → symmetric)
  is correct for the inverted thesis AND correct for future symmetry. Even if the
  inversion fails architecturally, a direction-symmetric whitelist is more principled
  than a LONG-biased one. This change stands regardless of what happens with the
  signal direction.

- The 507:56 SHORT:LONG ratio in D2 confirms the direction flip was implemented
  correctly — the engine is now generating mostly SHORTs (LOW sweeps dominate the
  data, as expected from the 47.67% sweep_detected base rate on 15m BTC).

- The per-regime D2 breakdown (normal: 0/18 wins, downtrend: 447 trades all losing)
  confirms this is not a regime-filter issue — it is the direction determination
  bottleneck at the `_infer_direction` gate.

---

## Recommended Next Step

**SIGNAL-ENGINE-REARCH-V1** — rearchitect `_infer_direction`.

Scope (bounded):
1. Derive trade direction FROM sweep_side: LOW → SHORT, HIGH → LONG (inverse thesis)
   OR LOW → LONG, HIGH → SHORT (original thesis) — the direction constant is now a
   design parameter, not hard-coded in the microstructure inference chain
2. CVD/TFI remain in `_confluence_score` as confluence weights — no change to scoring
3. Remove CVD/TFI as direction-blocking gates in `_infer_direction`
4. `_infer_direction` becomes: return SHORT if sweep_side == "LOW", LONG if "HIGH"
   (one line, two branches, no microstructure dependency)
5. Re-run D2-equivalent backtest to confirm trade count approaches raw event count
   and expectancy is positive
6. If positive: design Run #5 on rearchitected signal engine

Two acceptance criteria for the rearch:
- Trade count materially increases (from 563 toward ~3,000–8,000 after confluence gate)
- ExpR > 0 with default params on full 2022–2026 period

Builder: Cascade (full context, continuity).
