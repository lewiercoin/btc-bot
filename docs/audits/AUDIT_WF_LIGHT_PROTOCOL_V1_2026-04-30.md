# AUDIT: WF_LIGHT_PROTOCOL_V1
Date: 2026-04-30
Auditor: Claude Code
Commit: c54251c (modeling-context-closure)

## Verdict: MVP_DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: N/A
## Error Handling: N/A
## Smoke Coverage: PASS
## Tech Debt: LOW
## AGENTS.md Compliance: PASS
## Methodology Integrity: PASS
## Promotion Safety: WARN
## Reproducibility & Lineage: PASS
## Data Isolation: N/A
## Search Space Governance: PASS
## Artifact Consistency: PASS
## Boundary Coupling: PASS

---

## Audit Summary

Two-round audit. Round 1 (commit ada19b3, local) issued LOOKS_DONE with 3 blocking issues.
Round 2 (commit c54251c, pushed) confirms all 3 blockers resolved.

### Round 1 → Round 2 resolution

| Issue | Status |
|---|---|
| C1: promotion gate fields claimed as code-enforced (false) | RESOLVED — rationale corrected to advisory-only with honest disclosure |
| C2: missing `walkforward_mode`, `fragility_degradation_threshold_pct`, `min_trades_full_candidate`, `max_trades_full_candidate` | RESOLVED — all fields present in JSON |
| C3: no smoke test | RESOLVED — `scripts/smoke_wf_light_protocol.py` imports `build_windows()` from real code path, verifies 3 folds |

### File verification (actual files read from repo)

**`research_lab/configs/wf_light_protocol.json`**

All required fields confirmed:
- `walkforward_mode: "post_hoc"` — correct, pipeline-compatible
- `window_mode: "rolling"` — explicit, not defaulted
- `train_days: 50`, `validation_days: 20`, `step_days: 7`
- `min_trades_per_window: 15` — intentional light gate
- `min_trades_full_candidate: 50`, `max_trades_full_candidate: 200`
- `fragility_degradation_threshold_pct: 30.0` — matches default, confirmed in file
- `promotion_requires_all_windows_pass: false`, `promotion_requires_median_pass: true`
- Advisory-only fields present: `promotion_gate`, `requires_full_wf_before_live`, `max_promotion_target`

**`docs/WF_LIGHT_PROTOCOL_RATIONALE.md`**

Honest disclosure confirmed:
> "IMPORTANT: These fields are operator advisory only, not code-enforced. The research lab pipeline
> (approval.py, walkforward.py) does not read or enforce these constraints."

Explicit limitations section: 5 items documented. When-NOT-to-use: 4 scenarios. Comparison table present.
Escalation path documented: Light WF PASS → Paper → Full WF (mandatory) → Live.

**`scripts/smoke_wf_light_protocol.py`**

- Imports `build_windows` from `research_lab.walkforward` (real function, not reimplementation)
- Loads actual JSON via `json.load()`
- Calls `build_windows("2026-01-01", "2026-03-29", protocol)`
- Asserts `len(windows) == 3`
- Builder confirmed PASSED

### Independent fold arithmetic verification

With 87-day window, rolling mode, step=7:

| Fold | train_end | val_end | val_end ≤ day87? |
|---|---|---|---|
| 1 | day 50 | day 70 | ✓ |
| 2 | day 57 | day 77 | ✓ |
| 3 | day 64 | day 84 | ✓ |
| 4 | day 71 | day 91 | ✗ STOP |

3 folds confirmed independently.

Trade estimates at 1.6/day: train 50×1.6=80 ✓, val 20×1.6=32 ✓.

---

## Critical Issues
None. All C1–C3 resolved.

## Warnings

**W1 — Promotion Safety (advisory-only, no code enforcement)**
`approval.py` does not read `max_promotion_target`. An operator running `build-approval-bundle` on a
candidate evaluated with this protocol receives a standard bundle without restriction. Operator
discipline required. Documented honestly in rationale. Tracked as future v2 hardening.

**W2 — Role attribution in metadata**
`wf_light_protocol.json` metadata lists `"author": "Claude Code"` — should be builder (Claude/Windsurf).
Auditor issues verdicts, not authorship. Non-blocking cosmetic issue.

## Observations

- `min_trades_full_candidate: 50` is below `MIN_TRADES_DEFAULT: 30` (constants.py) but above it for
  full-candidate gate — intentional for preliminary screening, documented.
- `fragility_degradation_threshold_pct: 30.0` matches default protocol — conservative choice.
  Appropriate for a light protocol where train/val windows are small and degradation is noisier.
- Smoke test does not exercise `run_walkforward()` end-to-end. Full integration path remains unverified
  by automated test. Tracked as D2 below.

---

## Tracked Debt

| ID | Description | Priority |
|---|---|---|
| D2 | Smoke test does not exercise `run_walkforward()` end-to-end | LOW |
| D3 | `preliminary_only`/`paper_only` advisory-only — no code enforcement in `approval.py` | MEDIUM (v2) |

---

## Recommended Next Step

Protocol is ready for use. Decision for operator: run Optuna screening with `wf_light_protocol.json`
on the 87-day clean window (2026-01-01 → 2026-03-28), or backfill data gaps to unlock default protocol.
Claude Code recommends the operator review `docs/DECISIONS_LOG.md` and select based on urgency of
parameter search vs data quality investment.
